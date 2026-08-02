#!/usr/bin/env python3
"""Generate the country-agnostic direct-scope MIO route table."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import analyze_mio_archetypes as ar  # noqa: E402
import hoi4_paths  # noqa: E402

INVENTORY = ROOT / "docs" / "analysis" / "v2.3_MIO架构第一轮盘点.json"
OUTPUT = ROOT / "common" / "scripted_effects" / "PRC_OCS_shared_mio_effects.txt"
PRC_EFFECT = ROOT / "common" / "scripted_effects" / "PRC_OCS_mio_effects.txt"


def ordered_scripted_routes(path: Path) -> dict[str, list[str]]:
    text = path.read_text(encoding="utf-8-sig")
    routes = {}
    for token in ar.covered_tokens(path):
        values = []
        for block in ar.braced_blocks(text, rf"\bmio:{re.escape(token)}\s*=\s*\{{"):
            values.extend(re.findall(r"\bcomplete_mio_trait\s*=\s*([A-Za-z0-9_-]+)", block))
        routes[token] = list(dict.fromkeys(values))
    return routes


def related(data: dict, key: str, valid: set[str]) -> set[str]:
    return {token for token in ar.relation_tokens(data, key) if token in valid}


def prune(selected: set[str], traits: dict[str, dict]) -> set[str]:
    selected = set(selected)
    changed = True
    while changed:
        changed = False
        for token in sorted(selected):
            all_parents = related(traits[token], "all_parents", set(traits))
            any_parents = related(traits[token], "any_parent", set(traits))
            if not all_parents.issubset(selected) or (any_parents and not any_parents & selected):
                selected.remove(token)
                changed = True
    return selected


def maximum_legal_route(traits: dict[str, dict]) -> set[str]:
    candidates = set(traits)
    pairs = set()
    for token in candidates:
        for other in related(traits[token], "mutually_exclusive", candidates):
            if token != other:
                pairs.add(tuple(sorted((token, other))))
    conflict_nodes = sorted({token for pair in pairs for token in pair})
    always = candidates - set(conflict_nodes)
    best = set()
    best_tie = None
    for mask in range(1 << len(conflict_nodes)):
        chosen = {token for index, token in enumerate(conflict_nodes) if mask & (1 << index)}
        if any(left in chosen and right in chosen for left, right in pairs):
            continue
        selected = prune(always | chosen, traits)
        tie = tuple(sorted(selected))
        if len(selected) > len(best) or (len(selected) == len(best) and (best_tie is None or tie < best_tie)):
            best = selected
            best_tie = tie
    return best


def validate_selected(org: ar.Organization, selected: set[str]) -> None:
    valid = set(org.traits)
    unknown = selected - valid
    if unknown:
        raise ValueError(f"{org.token}: unknown traits {sorted(unknown)}")
    for token in selected:
        data = org.traits[token]
        all_parents = related(data, "all_parents", valid)
        any_parents = related(data, "any_parent", valid)
        if not all_parents.issubset(selected):
            raise ValueError(f"{org.token}: {token} lacks all-parent {sorted(all_parents - selected)}")
        if any_parents and not any_parents & selected:
            raise ValueError(f"{org.token}: {token} lacks any-parent {sorted(any_parents)}")
        conflicts = related(data, "mutually_exclusive", valid) & selected
        if conflicts:
            raise ValueError(f"{org.token}: {token} conflicts with {sorted(conflicts)}")


def order_route(org: ar.Organization, selected: set[str]) -> list[str]:
    validate_selected(org, selected)
    pending = set(selected)
    completed = set()
    result = []
    while pending:
        eligible = []
        for token in pending:
            data = org.traits[token]
            all_parents = related(data, "all_parents", set(org.traits))
            any_parents = related(data, "any_parent", set(org.traits))
            if all_parents.issubset(completed) and (not any_parents or any_parents & completed):
                eligible.append(token)
        if not eligible:
            raise ValueError(f"{org.token}: cannot order {sorted(pending)}")
        eligible.sort(key=lambda token: (not token.startswith("generic_"), token))
        for token in eligible:
            pending.remove(token)
            completed.add(token)
            result.append(token)
    return result


def preferred_routes(inventory: dict, orgs: dict[str, ar.Organization]) -> dict[str, set[str]]:
    current = ordered_scripted_routes(OUTPUT)
    preferred = {token: set(route) for token, route in current.items() if token.startswith("GER_")}
    for row in inventory["test8_comparison"]["rows"]:
        token = row["organization"]
        preferred[token] = set(current[token]) | set(row["missing_from_script"])
    for sample in inventory["country_samples"]:
        for row in sample["rows"]:
            if row["unlocked_traits"]:
                preferred[row["organization"]] = set(row["unlocked_traits"])
    for token, selected in preferred.items():
        validate_selected(orgs[token], selected)
    return preferred


def ignored_sample_organizations(inventory: dict) -> set[str]:
    return {
        row["organization"]
        for sample in inventory["country_samples"]
        for row in sample["rows"]
        if not row["unlocked_traits"]
    }
def render_route(token: str, traits: list[str]) -> list[str]:
    if not traits:
        raise ValueError(f"{token}: empty route")
    t = "\t"
    lines = [
        f"{t*2}if = {{",
        f"{t*3}limit = {{",
        f"{t*4}has_military_industrial_organization = {token}",
        f"{t*3}}}",
        f"{t*3}mio:{token} = {{",
        f"{t*4}if = {{",
        f"{t*5}limit = {{",
        f"{t*6}NOT = {{ is_mio_trait_completed = {traits[-1]} }}",
        f"{t*5}}}",
    ]
    lines.extend(f"{t*5}complete_mio_trait = {trait}" for trait in traits)
    lines.extend([f"{t*4}}}", f"{t*3}}}", f"{t*2}}}", ""])
    return lines


def build(vanilla_root: Path | None = None) -> tuple[str, dict]:
    vanilla_root = hoi4_paths.resolve_vanilla_path(vanilla_root)
    organizations_dir = (
        vanilla_root
        / "common"
        / "military_industrial_organization"
        / "organizations"
    )
    orgs, duplicates, repairs = ar.load_organizations(organizations_dir)
    if duplicates:
        raise ValueError(f"duplicate organizations: {duplicates}")
    inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))
    preferred = preferred_routes(inventory, orgs)
    excluded_prc = set(ar.covered_tokens(PRC_EFFECT))
    ignored_samples = ignored_sample_organizations(inventory)
    routes = {}
    sources = Counter()
    for org in ar.organization_rows(orgs):
        if org.token in excluded_prc or org.token in ignored_samples:
            continue
        if org.token in preferred:
            selected = preferred[org.token]
            sources["save_or_existing"] += 1
        else:
            selected = maximum_legal_route(org.traits)
            sources["generated_maximum"] += 1
        routes[org.token] = order_route(org, selected)

    lines = [
        "# Generated universal MIO route table.",
        "# Sources: test7 (GER), test8 (ENG), test9 (JAP/SOV),",
        "# test10 (AST/CZE/ITA/USA), plus deterministic maximum legal",
        "# routes for remaining vanilla organizations.",
        "# Country identity is irrelevant: each route runs only when the",
        "# current player country owns the exact organization token.",
        "# Do not hand-edit; run tools/generate_universal_mio_effect.py.",
        "PRC_OCS_configure_shared_mios_effect = {",
        "\tif = {",
        "\t\tlimit = { has_dlc = \"Arms Against Tyranny\" }",
    ]
    last_country = None
    for token, traits in sorted(routes.items(), key=lambda item: (ar.country_code(orgs[item[0]]), item[0])):
        country = ar.country_code(orgs[token])
        if country != last_country:
            lines.extend(["", f"\t\t# {country}"])
            last_country = country
        lines.extend(render_route(token, traits))
    lines.extend(["\t}", "}", ""])
    stats = {
        "organizations": len(routes),
        "traits": sum(len(route) for route in routes.values()),
        "route_sources": dict(sources),
        "countries": len({ar.country_code(orgs[token]) for token in routes}),
        "excluded_prc_organizations": sorted(excluded_prc),
        "ignored_sample_organizations": sorted(ignored_samples),
        "source_repairs": repairs,
    }
    return "\n".join(lines), stats


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--vanilla",
        type=Path,
        help="HOI4 原版根目录；省略时读取 HOI4_VANILLA_PATH 或探测已知盘符",
    )
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    content, stats = build(args.vanilla)
    if args.check:
        if OUTPUT.read_text(encoding="utf-8-sig") != content:
            print("Universal MIO effect is out of date.", file=sys.stderr)
            return 1
    else:
        OUTPUT.write_text(content, encoding="utf-8")
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())