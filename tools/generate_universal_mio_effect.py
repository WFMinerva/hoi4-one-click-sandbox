#!/usr/bin/env python3
"""Generate the country-agnostic direct-scope MIO route table."""

from __future__ import annotations

import argparse
import hashlib
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
MANIFEST = ROOT / "tools" / "mio_generator_manifest.json"


def canonical_output_bytes(content: str) -> bytes:
    """Return generator output bytes with platform line endings normalized."""
    return content.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")


def route_table_stats(content: str) -> dict[str, int]:
    routes = re.findall(
        r"(?m)^\s*mio:([A-Za-z0-9_-]+)\s*=\s*\{\s*$", content
    )
    return {
        "organizations": len(routes),
        "traits": len(
            re.findall(
                r"(?m)^\s*complete_mio_trait\s*=\s*[A-Za-z0-9_-]+\s*$", content
            )
        ),
    }


def manifest_payload(content: str, stats: dict) -> dict:
    observed = route_table_stats(content)
    expected = {
        "organizations": stats["organizations"],
        "traits": stats["traits"],
    }
    if observed != expected:
        raise ValueError(
            f"generated route statistics differ: expected {expected}, observed {observed}"
        )
    return {
        "schema": 1,
        "output": str(OUTPUT.relative_to(ROOT)).replace("\\", "/"),
        "sha256_lf": hashlib.sha256(canonical_output_bytes(content)).hexdigest(),
        **expected,
    }


def write_manifest(content: str, stats: dict, path: Path = MANIFEST) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        handle.write(
            json.dumps(manifest_payload(content, stats), ensure_ascii=False, indent=2)
            + "\n"
        )


def check_locked_output(path: Path = MANIFEST) -> int:
    if not OUTPUT.is_file():
        print(f"Generated MIO effect not found: {OUTPUT}", file=sys.stderr)
        return 1
    if not path.is_file():
        print(f"MIO generator manifest not found: {path}", file=sys.stderr)
        return 1
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Invalid MIO generator manifest: {exc}", file=sys.stderr)
        return 1
    content = OUTPUT.read_text(encoding="utf-8-sig")
    observed = route_table_stats(content)
    actual = {
        "schema": manifest.get("schema"),
        "output": manifest.get("output"),
        "sha256_lf": hashlib.sha256(canonical_output_bytes(content)).hexdigest(),
        **observed,
    }
    expected = {
        "schema": 1,
        "output": str(OUTPUT.relative_to(ROOT)).replace("\\", "/"),
        "sha256_lf": manifest.get("sha256_lf"),
        "organizations": manifest.get("organizations"),
        "traits": manifest.get("traits"),
    }
    if actual != expected:
        print(
            json.dumps(
                {"expected": expected, "observed": actual},
                ensure_ascii=False,
                indent=2,
            ),
            file=sys.stderr,
        )
        return 1
    print(
        json.dumps(
            {"mode": "locked-output", **observed},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


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


def _numeric_strength(value: object) -> float:
    if isinstance(value, (int, float)):
        return abs(float(value))
    if isinstance(value, str):
        try:
            return abs(float(value))
        except ValueError:
            return 0.0
    return 0.0


def trait_strength(data: dict) -> float:
    """Sum the absolute numeric bonus magnitude of a trait's equipment and
    production bonuses. Direction is ignored; organization-internal modifiers
    and non-numeric entries are not counted."""
    total = 0.0
    for key in ("equipment_bonus", "production_bonus"):
        entries = data.get(key)
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if isinstance(entry, tuple) and len(entry) == 2 and entry[0] != "bare":
                total += _numeric_strength(entry[1])
    return total


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
    best_score = None
    best_tie = None
    for mask in range(1 << len(conflict_nodes)):
        chosen = {token for index, token in enumerate(conflict_nodes) if mask & (1 << index)}
        if any(left in chosen and right in chosen for left, right in pairs):
            continue
        selected = prune(always | chosen, traits)
        # Iterate in sorted order: float addition is not associative, so a
        # raw set iteration would make the score (and thus the tie-break)
        # depend on PYTHONHASHSEED across processes.
        score = sum(trait_strength(traits[token]) for token in sorted(selected))
        tie = tuple(sorted(selected))
        if (
            best_score is None
            or score > best_score
            or (
                score == best_score
                and (
                    len(selected) > len(best)
                    or (len(selected) == len(best) and (best_tie is None or tie < best_tie))
                )
            )
        ):
            best = selected
            best_score = score
            best_tie = tie
    return best


def _parent_chain(
    org: ar.Organization, token: str, base: set[str]
) -> set[str] | None:
    """Return token plus every ancestor trait required so all_parents and
    any_parent constraints hold, or None when the chain is unsatisfiable."""
    valid = set(org.traits)
    add: set[str] = {token}
    queue = [token]
    while queue:
        current = queue.pop()
        data = org.traits[current]
        missing_all = related(data, "all_parents", valid) - base - add
        if missing_all:
            add |= missing_all
            queue.extend(missing_all)
        any_parents = related(data, "any_parent", valid)
        if any_parents and not (any_parents & (base | add)):
            return None
    return add


# v2.9-test2 D12: submarine stealth side (left) vs torpedo side (right).
# Derived from vanilla generic_submarine_organization: mutually-exclusive
# roots long_range_raiding (stealth) <-> decalin_fueled_torpedo (torpedo).
# Classification is by bonus direction (visibility/range vs torpedo/speed)
# rather than a pure BFS, because any_parent cross-references
# (highly_efficient/open_cycle share parents, simplified_pressure_hull
# requires both sides) make a plain tree diffusion ambiguous.
SUBMARINE_STEALTH_TRAITS = frozenset({
    "generic_mio_trait_long_range_raiding",
    "generic_mio_trait_efficient_fuel_engines",
    "generic_mio_trait_highly_efficient_diesel_electric_propulsion_systems",
    "generic_mio_trait_experimental_anechoic_tiles",
    "generic_mio_trait_advanced_periscope",
    "generic_mio_trait_emergency_main_ballast_tank_blow",
    "generic_mio_trait_radar_warning_receiver",
    "generic_mio_trait_crash_dive_flood_tanks",
    # v2.9-test6 (D10): improved_torpedo_detonators is reachable from the
    # stealth chain (any_parent includes highly_efficient_diesel_electric)
    # and simplified_pressure_hull_design needs it (all_parents =
    # anechoic + improved_torpedo); both stay on the stealth side so the
    # reroute keeps them (player feedback 2026-08-23 B3).
    "generic_mio_trait_improved_torpedo_detonators",
    "generic_mio_trait_simplified_pressure_hull_design",
})
SUBMARINE_TORPEDO_TRAITS = frozenset({
    "generic_mio_trait_decalin_fueled_torpedo",
    "generic_mio_trait_high_powered_engines",
    "generic_mio_trait_open_cycle_propulsion",
    "generic_mio_trait_submarine_mass_production",
    "generic_mio_trait_advanced_sonar",
    "generic_mio_trait_deck_guns",
    "generic_mio_trait_large_torpedo_banks",
    "generic_mio_trait_high_capacity_mine_storage",
})


def check_submarine_side_coverage(orgs: dict[str, ar.Organization]) -> None:
    """Every generic_ trait of the vanilla submarine archetype must fall into
    exactly one side; a vanilla update adding traits fails loudly here
    instead of silently misrouting submarines."""
    base = orgs.get("generic_submarine_organization")
    if base is None:
        return
    overlap = SUBMARINE_STEALTH_TRAITS & SUBMARINE_TORPEDO_TRAITS
    if overlap:
        raise ValueError(f"submarine side overlap: {sorted(overlap)}")
    generic_traits = {
        token for token in base.traits if token.startswith("generic_mio_trait_")
    }
    missing = generic_traits - (SUBMARINE_STEALTH_TRAITS | SUBMARINE_TORPEDO_TRAITS)
    if missing:
        raise ValueError(
            "submarine archetype traits not classified into a side: "
            + ", ".join(sorted(missing))
        )


def apply_org_type_preferences(
    org: ar.Organization, selected: set[str], orgs: dict[str, ar.Organization]
) -> set[str]:
    """Adjust a route by organization type (v2.9 player feedback T2).
    Applied to every route (generated maximum and sample-based preferred
    routes alike): drops the research traits of support-equipment
    manufacturers (useless once the mod grants all technologies), prefers the
    anti-personnel assault-gun ammunition over the anti-armor one, guarantees
    the production-techniques and long-range-fighter improvements for
    long-range aircraft manufacturers, and (v2.9-test2 D12) reroutes submarine
    manufacturers to the stealth side instead of the torpedo side. Falls back
    to the unmodified route whenever the preference cannot be satisfied
    legally."""
    base = set(selected)
    chain: set[str] = set()
    current: str | None = org.include
    while current and current not in chain:
        chain.add(current)
        parent = orgs.get(current)
        current = parent.include if parent else None
    is_support = "generic_support_equipment_organization" in chain
    is_assault = "generic_assault_guns_organization" in chain
    is_range = "generic_range_focused_aircraft_organization" in chain
    is_submarine = "generic_submarine_organization" in chain
    if not (is_support or is_assault or is_range or is_submarine):
        return base
    drop: set[str] = set()
    ensure: set[str] = set()
    if is_support:
        drop = {
            "generic_mio_trait_research_program",
            "generic_mio_trait_private_scientists_program",
        }
        ensure = {"generic_mio_trait_efficient_scale_up"}
    if is_assault:
        drop = {"generic_mio_trait_light_assault_gun_anti_tank_combo"}
        ensure = {"generic_mio_trait_light_assault_gun_improved_cannon_stabilization"}
    if is_range:
        ensure = {
            "generic_mio_trait_advanced_production_techniques",
            "generic_mio_trait_long_range_fighters",
        }
    if is_submarine:
        drop = set(SUBMARINE_TORPEDO_TRAITS)
        ensure = set(SUBMARINE_STEALTH_TRAITS)
    candidate = prune(base - drop, org.traits)
    # Fixpoint loop: ensure-items may depend (any_parent) on other ensure-items
    # that sort later (e.g. anechoic_tiles on highly_efficient_diesel_electric),
    # so a single pass would silently skip them.
    pending_ensure = set(ensure)
    while pending_ensure:
        progressed = False
        for token in sorted(pending_ensure):
            if token in candidate or token not in org.traits:
                pending_ensure.discard(token)
                continue
            add = _parent_chain(org, token, candidate)
            if add is None:
                continue
            conflicts = set()
            for extra in add:
                conflicts |= related(
                    org.traits[extra], "mutually_exclusive", set(org.traits)
                ) & candidate
            candidate = prune((candidate - conflicts) | add, org.traits)
            pending_ensure.discard(token)
            progressed = True
        if not progressed:
            break
    try:
        validate_selected(org, candidate)
    except ValueError:
        return base
    return candidate


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
        for token in sorted(pending):
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
def render_route(
    token: str, traits: list[str], guard_lines: tuple[str, ...] | None = None
) -> list[str]:
    if not traits:
        raise ValueError(f"{token}: empty route")
    t = "\t"
    limit_content: list[str] = []
    if guard_lines:
        limit_content.extend(f"{t*4}{line}" for line in guard_lines)
    limit_content.append(f"{t*4}has_military_industrial_organization = {token}")
    lines = [
        f"{t*2}if = {{",
        f"{t*3}limit = {{",
        *limit_content,
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
    check_submarine_side_coverage(orgs)
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
        # v2.9 T2: type preferences apply to every route (including the
        # sample-based ones) so the player-visible fixes are consistent
        # across all countries, not only the generated remainder.
        selected = apply_org_type_preferences(org, selected, orgs)
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
        lines.extend(render_route(token, traits, orgs[token].allowed_guard))
    lines.extend(["\t}", "}", ""])
    stats = {
        "organizations": len(routes),
        "traits": sum(len(route) for route in routes.values()),
        "route_sources": dict(sources),
        "countries": len({ar.country_code(orgs[token]) for token in routes}),
        "dlc_guarded_organizations": sum(
            1
            for token in routes
            if orgs[token].allowed_guard
            and any("has_dlc" in line for line in orgs[token].allowed_guard)
        ),
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
    parser.add_argument(
        "--no-vanilla",
        action="store_true",
        help="Check the committed output manifest without requiring HOI4 files (CI).",
    )
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    args = parser.parse_args()
    if args.no_vanilla:
        if not args.check:
            parser.error("--no-vanilla requires --check")
        return check_locked_output(args.manifest)
    content, stats = build(args.vanilla)
    if args.check:
        if OUTPUT.read_text(encoding="utf-8-sig") != content:
            print("Universal MIO effect is out of date.", file=sys.stderr)
            return 1
    else:
        with OUTPUT.open("w", encoding="utf-8", newline="") as handle:
            handle.write(content)
        write_manifest(content, stats, args.manifest)
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())