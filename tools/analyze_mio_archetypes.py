#!/usr/bin/env python3
"""Inventory vanilla MIO trait-tree archetypes without changing MOD content."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

try:
    from .hoi4_paths import resolve_vanilla_path
except ImportError:  # Direct execution: python tools/analyze_mio_archetypes.py
    from hoi4_paths import resolve_vanilla_path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_COVERAGE = (
    ROOT / "common" / "scripted_effects" / "PRC_OCS_shared_mio_effects.txt"
)
DEFAULT_ADDITIONAL_COVERAGE = (
    ROOT / "common" / "scripted_effects" / "PRC_OCS_mio_effects.txt"
)
DEFAULT_REPORT = ROOT / "docs" / "analysis" / "v2.3_MIO架构第一轮盘点.md"
DEFAULT_JSON = ROOT / "docs" / "analysis" / "v2.3_MIO架构第一轮盘点.json"

TRAIT_KEYS = ("trait", "add_trait")
RELATION_KEYS = (
    "any_parent",
    "all_parents",
    "mutually_exclusive",
    "relative_position_id",
)
_SAVE_TEXT_CACHE: dict[Path, str] = {}


@dataclass(frozen=True)
class Atom:
    value: str


@dataclass(frozen=True)
class Assignment:
    key: str
    value: Atom | "Block"


@dataclass(frozen=True)
class Bare:
    value: str


@dataclass(frozen=True)
class Block:
    entries: tuple[Assignment | Bare, ...]


@dataclass
class Organization:
    token: str
    source: str
    block: Block
    include: str | None
    traits: dict[str, dict]
    add_count: int
    override_count: int
    remove_count: int
    exact_hash: str
    shape_hash: str


def tokenize(text: str) -> list[str]:
    tokens: list[str] = []
    index = 0
    while index < len(text):
        char = text[index]
        if char.isspace():
            index += 1
        elif char == "#":
            while index < len(text) and text[index] != "\n":
                index += 1
        elif char in "{}=":
            tokens.append(char)
            index += 1
        elif char == '"':
            index += 1
            value: list[str] = []
            escaped = False
            while index < len(text):
                char = text[index]
                index += 1
                if escaped:
                    value.append(char)
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    break
                else:
                    value.append(char)
            tokens.append("".join(value))
        else:
            start = index
            while (
                index < len(text)
                and not text[index].isspace()
                and text[index] not in '#{}="'
            ):
                index += 1
            tokens.append(text[start:index])
    return tokens


def parse_block(tokens: list[str], index: int = 0, nested: bool = False) -> tuple[Block, int]:
    entries: list[Assignment | Bare] = []
    while index < len(tokens):
        token = tokens[index]
        if token == "}":
            if not nested:
                raise ValueError("unexpected closing brace")
            return Block(tuple(entries)), index + 1
        if token in ("{", "="):
            raise ValueError(f"unexpected token {token!r} at token index {index}")
        if index + 1 < len(tokens) and tokens[index + 1] == "=":
            if index + 2 >= len(tokens):
                raise ValueError(f"missing value for {token!r}")
            next_token = tokens[index + 2]
            if next_token == "{":
                value, index = parse_block(tokens, index + 3, nested=True)
            else:
                value = Atom(next_token)
                index += 3
            entries.append(Assignment(token, value))
        else:
            entries.append(Bare(token))
            index += 1
    # Vanilla BRA_organization.txt currently lacks the final closing brace for
    # BRA_fnm_organization. Clausewitz accepts the EOF-terminated final block;
    # retain it here and report the source imbalance instead of losing the MIO.
    return Block(tuple(entries)), index


def parse_file(path: Path) -> Block:
    text = path.read_text(encoding="utf-8-sig")
    parsed, index = parse_block(tokenize(text))
    if index < 0:
        raise AssertionError("unreachable")
    return parsed


def assignments(block: Block, key: str | None = None) -> list[Assignment]:
    return [
        entry
        for entry in block.entries
        if isinstance(entry, Assignment) and (key is None or entry.key == key)
    ]


def scalar(block: Block, key: str) -> str | None:
    for entry in assignments(block, key):
        if isinstance(entry.value, Atom):
            return entry.value.value
    return None


def blocks(block: Block, key: str) -> list[Block]:
    return [
        entry.value
        for entry in assignments(block, key)
        if isinstance(entry.value, Block)
    ]


def bare_values(block: Block) -> list[str]:
    return [entry.value for entry in block.entries if isinstance(entry, Bare)]


def value_repr(value: Atom | Block, variables: dict[str, str]) -> object:
    if isinstance(value, Atom):
        return variables.get(value.value, value.value)
    result: list[object] = []
    for entry in value.entries:
        if isinstance(entry, Bare):
            result.append(("bare", variables.get(entry.value, entry.value)))
        else:
            result.append(
                (
                    entry.key,
                    value_repr(entry.value, variables),
                )
            )
    return result


def trait_from_block(block: Block, variables: dict[str, str]) -> tuple[str, dict]:
    token = scalar(block, "token")
    if not token:
        raise ValueError("trait block without token")
    data: dict[str, object] = {}
    for entry in block.entries:
        if not isinstance(entry, Assignment) or entry.key in {
            "token",
            "name",
            "icon",
            "visible",
            "available",
            "on_complete",
            "ai_will_do",
            "equipment_bonus",
            "production_bonus",
            "organization_modifier",
            "special_project_completion_bonus",
        }:
            continue
        data[entry.key] = value_repr(entry.value, variables)
    return token, data


def removed_tokens(block: Block) -> list[str]:
    result: list[str] = []
    for remove in blocks(block, "remove_trait"):
        result.extend(bare_values(remove))
    return result


def merge_override(original: dict, override: dict) -> dict:
    merged = dict(original)
    merged.update(override)
    return merged


def stable_hash(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]


def relation_tokens(data: dict, key: str) -> list[str]:
    value = data.get(key)
    if value is None:
        return []
    if key == "relative_position_id" and isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [item[1] for item in value if isinstance(item, tuple) and item[0] == "bare"]
    return []


def node_position(data: dict) -> tuple[str, str]:
    position = data.get("position", [])
    coordinates: dict[str, str] = {}
    if isinstance(position, list):
        for item in position:
            if (
                isinstance(item, tuple)
                and len(item) == 2
                and item[0] in ("x", "y")
                and isinstance(item[1], str)
            ):
                coordinates[item[0]] = item[1]
    return coordinates.get("x", "?"), coordinates.get("y", "?")


def exact_fingerprint(traits: dict[str, dict]) -> object:
    return [(token, traits[token]) for token in sorted(traits)]


def shape_fingerprint(traits: dict[str, dict]) -> object:
    """Build a name-independent graph fingerprint from layout and typed edges."""
    attrs: dict[str, tuple] = {}
    for token, data in traits.items():
        attrs[token] = (
            node_position(data),
            str(data.get("special_trait_background", "no")),
            str(data.get("trait_type", "")),
        )

    colors = {token: stable_hash(attrs[token]) for token in traits}
    for _ in range(max(1, len(traits))):
        next_colors: dict[str, str] = {}
        for token, data in traits.items():
            links: list[tuple[str, str]] = []
            for relation in RELATION_KEYS:
                for target in relation_tokens(data, relation):
                    links.append((relation, colors.get(target, "external")))
            next_colors[token] = stable_hash((attrs[token], sorted(links)))
        if next_colors == colors:
            break
        colors = next_colors
    edge_counts = Counter()
    for token, data in traits.items():
        for relation in RELATION_KEYS:
            for target in relation_tokens(data, relation):
                edge_counts[(relation, colors[token], colors.get(target, "external"))] += 1
    return {
        "nodes": sorted(Counter(colors.values()).items()),
        "edges": sorted((key, count) for key, count in edge_counts.items()),
    }


def top_level_variables(roots: Iterable[Block]) -> dict[str, str]:
    variables: dict[str, str] = {}
    for root in roots:
        for entry in assignments(root):
            if entry.key.startswith("@") and isinstance(entry.value, Atom):
                variables[entry.key] = entry.value.value
    return variables


def load_organizations(
    directory: Path,
) -> tuple[dict[str, Organization], list[str], list[dict[str, int | str]]]:
    excluded_sources = {"mio.txt", "00_DEBUG_organization.txt", "_template_organization.txt"}
    files = sorted(path for path in directory.glob("*.txt") if path.name not in excluded_sources)
    source_repairs: list[dict[str, int | str]] = []
    roots: list[tuple[Path, Block]] = []
    for path in files:
        text = path.read_text(encoding="utf-8-sig")
        opening = text.count("{")
        closing = text.count("}")
        if opening != closing:
            source_repairs.append(
                {"source": path.name, "opening_braces": opening, "closing_braces": closing}
            )
        roots.append((path, parse_file(path)))
    variables = top_level_variables(root for _, root in roots)
    definitions: dict[str, tuple[str, Block]] = {}
    duplicates: list[str] = []
    for path, root in roots:
        for entry in assignments(root):
            if (
                isinstance(entry.value, Block)
                and entry.key.endswith("_organization")
                and not entry.key.startswith("@")
            ):
                if entry.key in definitions:
                    duplicates.append(entry.key)
                definitions[entry.key] = (path.name, entry.value)

    resolved: dict[str, Organization] = {}
    resolving: set[str] = set()

    def resolve(token: str) -> Organization:
        if token in resolved:
            return resolved[token]
        if token in resolving:
            raise ValueError(f"cyclic MIO include: {token}")
        if token not in definitions:
            raise ValueError(f"missing included MIO: {token}")
        resolving.add(token)
        source, block = definitions[token]
        include = scalar(block, "include")
        traits: dict[str, dict] = {}
        if include:
            traits.update(
                {name: dict(data) for name, data in resolve(include).traits.items()}
            )
        for removed in removed_tokens(block):
            traits.pop(removed, None)
        for key in TRAIT_KEYS:
            for trait_block in blocks(block, key):
                trait_token, data = trait_from_block(trait_block, variables)
                traits[trait_token] = data
        override_count = 0
        for override_block in blocks(block, "override_trait"):
            trait_token, data = trait_from_block(override_block, variables)
            override_count += 1
            traits[trait_token] = merge_override(traits.get(trait_token, {}), data)
        organization = Organization(
            token=token,
            source=source,
            block=block,
            include=include,
            traits=traits,
            add_count=len(blocks(block, "add_trait")),
            override_count=override_count,
            remove_count=len(removed_tokens(block)),
            exact_hash=stable_hash(exact_fingerprint(traits)),
            shape_hash=stable_hash(shape_fingerprint(traits)),
        )
        resolving.remove(token)
        resolved[token] = organization
        return organization

    for token in definitions:
        resolve(token)
    return resolved, sorted(set(duplicates)), source_repairs


def covered_tokens(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8-sig")
    return sorted(
        set(
            re.findall(
                r"\bmio:([A-Za-z0-9_-]+_organization)\s*=\s*\{",
                text,
            )
        )
    )


def braced_blocks(text: str, pattern: str) -> list[str]:
    result: list[str] = []
    for match in re.finditer(pattern, text):
        opening = text.find("{", match.start())
        if opening < 0:
            continue
        depth = 0
        quoted = False
        escaped = False
        for index in range(opening, len(text)):
            char = text[index]
            if quoted:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    quoted = False
                continue
            if char == '"':
                quoted = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    result.append(text[opening + 1 : index])
                    break
    return result


def save_unlocked_traits(save_path: Path, tokens: Iterable[str]) -> dict[str, list[str]]:
    text = cached_save_text(save_path)
    result: dict[str, list[str]] = {}
    for token in tokens:
        candidates = braced_blocks(
            text, rf"(?m)^\s*{re.escape(token)}\s*=\s*\{{"
        )
        trait_sets = [
            sorted(set(re.findall(r'\bunlocked\s*=\s*\{\s*trait\s*=\s*"([^"]+)"', block)))
            for block in candidates
        ]
        result[token] = max(trait_sets, key=len, default=[])
    return result


def save_organization_snapshots(save_path: Path, tokens: Iterable[str]) -> dict[str, dict]:
    text = cached_save_text(save_path)
    result: dict[str, dict] = {}
    for token in tokens:
        candidates = braced_blocks(
            text, rf"(?m)^\s*{re.escape(token)}\s*=\s*\{{"
        )
        snapshots = []
        for block in candidates:
            traits = sorted(
                set(
                    re.findall(
                        r'\bunlocked\s*=\s*\{\s*trait\s*=\s*"([^"]+)"', block
                    )
                )
            )
            snapshots.append(
                {
                    "unlocked_traits": traits,
                    "size": int(match.group(1))
                    if (match := re.search(r"(?m)^\s*size\s*=\s*(\d+)", block))
                    else None,
                    "points": int(match.group(1))
                    if (match := re.search(r"(?m)^\s*points\s*=\s*(\d+)", block))
                    else None,
                    "funds": float(match.group(1))
                    if (
                        match := re.search(
                            r"(?m)^\s*funds\s*=\s*(-?[0-9]+(?:\.[0-9]+)?)", block
                        )
                    )
                    else None,
                }
            )
        result[token] = max(
            snapshots,
            key=lambda item: (len(item["unlocked_traits"]), item["size"] or 0),
            default={
                "unlocked_traits": [],
                "size": None,
                "points": None,
                "funds": None,
            },
        )
        result[token]["found"] = bool(candidates)
    return result


def cached_save_text(save_path: Path) -> str:
    resolved = save_path.resolve()
    if resolved not in _SAVE_TEXT_CACHE:
        _SAVE_TEXT_CACHE[resolved] = resolved.read_text(
            encoding="utf-8-sig", errors="replace"
        )
    return _SAVE_TEXT_CACHE[resolved]


def scripted_traits(path: Path, tokens: Iterable[str]) -> dict[str, list[str]]:
    text = path.read_text(encoding="utf-8-sig")
    result: dict[str, list[str]] = {}
    for token in tokens:
        candidates = braced_blocks(
            text, rf"\bmio:{re.escape(token)}\s*=\s*\{{"
        )
        traits = set()
        for block in candidates:
            traits.update(
                re.findall(r"\bcomplete_mio_trait\s*=\s*([A-Za-z0-9_]+)", block)
            )
        result[token] = sorted(traits)
    return result


def country_code(organization: Organization) -> str:
    if organization.token.startswith("generic_"):
        return "GEN"
    match = re.match(r"^([A-Za-z0-9]{3})_organization\.txt$", organization.source)
    if match:
        return match.group(1).upper()
    match = re.match(r"^([A-Z0-9]{3})_", organization.token)
    return match.group(1) if match else "OTHER"


def organization_rows(organizations: dict[str, Organization]) -> list[Organization]:
    return sorted(
        (
            organization
            for organization in organizations.values()
            if not organization.token.startswith("generic_")
        ),
        key=lambda item: item.token,
    )


def class_representative(items: list[Organization], covered: set[str]) -> Organization:
    return min(
        items,
        key=lambda item: (
            item.token not in covered,
            country_code(item) not in {"GER", "ENG", "USA", "SOV", "JAP", "ITA", "FRA"},
            item.token,
        ),
    )


def recommend_countries(
    organizations: dict[str, Organization],
    covered_shapes: set[str],
    excluded_countries: set[str] | None = None,
) -> tuple[list[dict], list[str]]:
    excluded_countries = excluded_countries or set()
    rows = organization_rows(organizations)
    all_shapes = {organization.shape_hash for organization in rows}
    remaining_shapes = all_shapes - covered_shapes
    organizations_by_country: dict[str, list[Organization]] = defaultdict(list)
    for organization in rows:
        country = country_code(organization)
        if country not in {"GEN", "OTHER"} and country not in excluded_countries:
            organizations_by_country[country].append(organization)
    recommended = []
    while remaining_shapes:
        candidates = []
        for country, items in organizations_by_country.items():
            gained = {item.shape_hash for item in items} & remaining_shapes
            if gained:
                candidates.append(
                    (
                        len(gained),
                        country in {"USA", "SOV", "JAP", "ITA", "FRA"},
                        country,
                        gained,
                        items,
                    )
                )
        if not candidates:
            break
        gain_count, _major, country, gained, items = max(
            candidates, key=lambda item: (item[0], item[1], item[2])
        )
        recommended.append(
            {
                "country": country,
                "new_shapes": gain_count,
                "organization_count": len(items),
                "representative_organizations": sorted(
                    item.token for item in items if item.shape_hash in gained
                ),
            }
        )
        remaining_shapes -= gained
    return recommended, sorted(remaining_shapes)


def build_inventory(
    organizations: dict[str, Organization],
    covered: set[str],
    duplicates: list[str],
    source_repairs: list[dict[str, int | str]],
) -> dict:
    rows = organization_rows(organizations)
    shape_groups: dict[str, list[Organization]] = defaultdict(list)
    exact_groups: dict[str, list[Organization]] = defaultdict(list)
    include_groups: dict[str, list[Organization]] = defaultdict(list)
    for organization in rows:
        shape_groups[organization.shape_hash].append(organization)
        exact_groups[organization.exact_hash].append(organization)
        include_groups[organization.include or "(standalone)"].append(organization)

    missing_covered = sorted(covered - organizations.keys())
    current = [organizations[token] for token in sorted(covered & organizations.keys())]
    covered_shapes = {item.shape_hash for item in current}
    covered_exact = {item.exact_hash for item in current}

    shape_records = []
    for shape_hash, items in sorted(
        shape_groups.items(), key=lambda pair: (-len(pair[1]), pair[0])
    ):
        representative = class_representative(items, covered)
        shape_records.append(
            {
                "shape_hash": shape_hash,
                "organization_count": len(items),
                "trait_counts": sorted({len(item.traits) for item in items}),
                "countries": sorted({country_code(item) for item in items}),
                "includes": sorted({item.include or "(standalone)" for item in items}),
                "covered": any(item.token in covered for item in items),
                "covered_organizations": sorted(item.token for item in items if item.token in covered),
                "representative": representative.token,
                "organizations": [item.token for item in sorted(items, key=lambda item: item.token)],
            }
        )

    recommended_countries, remaining_shapes = recommend_countries(
        organizations, covered_shapes
    )

    return {
        "summary": {
            "all_definitions": len(organizations),
            "generic_definitions": sum(
                token.startswith("generic_") for token in organizations
            ),
            "country_organizations": len(rows),
            "include_families": len(include_groups),
            "exact_effective_trees": len(exact_groups),
            "structural_shapes": len(shape_groups),
            "covered_organizations": len(current),
            "covered_exact_trees": len(covered_exact),
            "covered_shapes": len(covered_shapes),
            "uncovered_shapes": len(shape_groups) - len(covered_shapes),
        },
        "duplicates": duplicates,
        "source_repairs": source_repairs,
        "missing_covered": missing_covered,
        "coverage_by_country": dict(
            sorted(Counter(country_code(item) for item in current).items())
        ),
        "include_families": [
            {
                "include": include,
                "count": len(items),
                "covered": sum(item.token in covered for item in items),
                "shape_count": len({item.shape_hash for item in items}),
                "countries": sorted({country_code(item) for item in items}),
            }
            for include, items in sorted(
                include_groups.items(), key=lambda pair: (-len(pair[1]), pair[0])
            )
        ],
        "recommended_countries": recommended_countries,
        "unassigned_shapes": remaining_shapes,
        "shapes": shape_records,
    }


def build_save_comparison(
    save_path: Path, coverage_file: Path, coverage: set[str]
) -> dict:
    england = sorted(token for token in coverage if token.startswith("ENG_"))
    save_traits = save_unlocked_traits(save_path, england)
    source_traits = scripted_traits(coverage_file, england)
    rows = []
    for token in england:
        save_set = set(save_traits[token])
        source_set = set(source_traits[token])
        rows.append(
            {
                "organization": token,
                "save_unlocked": len(save_set),
                "scripted": len(source_set),
                "missing_from_script": sorted(save_set - source_set),
                "extra_in_script": sorted(source_set - save_set),
            }
        )
    return {
        "save": save_path.stem,
        "organizations": len(england),
        "save_unlocked_total": sum(row["save_unlocked"] for row in rows),
        "scripted_total": sum(row["scripted"] for row in rows),
        "missing_total": sum(len(row["missing_from_script"]) for row in rows),
        "extra_total": sum(len(row["extra_in_script"]) for row in rows),
        "rows": rows,
    }


def build_country_sample(
    save_path: Path,
    tag: str,
    organizations: dict[str, Organization],
) -> dict:
    candidates = sorted(
        organization.token
        for organization in organization_rows(organizations)
        if country_code(organization) == tag
    )
    snapshots = save_organization_snapshots(save_path, candidates)
    rows = []
    for token in candidates:
        snapshot = snapshots[token]
        unlocked = set(snapshot["unlocked_traits"])
        effective = set(organizations[token].traits)
        rows.append(
            {
                "organization": token,
                "found": snapshot["found"],
                "unlocked": len(unlocked),
                "effective_traits": len(effective),
                "not_unlocked": sorted(effective - unlocked),
                "invalid_unlocked": sorted(unlocked - effective),
                "size": snapshot["size"],
                "points": snapshot["points"],
                "funds": snapshot["funds"],
                "unlocked_traits": sorted(unlocked),
            }
        )
    active_rows = [row for row in rows if row["unlocked"]]
    return {
        "tag": tag,
        "save": save_path.stem,
        "defined_organizations": len(candidates),
        "sampled_organizations": len(active_rows),
        "unlocked_total": sum(row["unlocked"] for row in active_rows),
        "invalid_total": sum(len(row["invalid_unlocked"]) for row in active_rows),
        "remaining_points_total": sum((row["points"] or 0) for row in active_rows),
        "inactive_but_present": [
            row["organization"]
            for row in rows
            if row["found"] and not row["unlocked"]
        ],
        "not_found": [
            row["organization"]
            for row in rows
            if not row["found"]
        ],
        "rows": rows,
    }


def audit_country_sample(
    sample: dict, organizations: dict[str, Organization]
) -> dict[str, int]:
    parent_gaps = 0
    mutual_conflicts = 0
    topology_failures = 0
    selected_traits = 0
    for row in sample["rows"]:
        selected = set(row["unlocked_traits"])
        if not selected:
            continue
        selected_traits += len(selected)
        organization = organizations[row["organization"]]
        for token in selected:
            data = organization.traits[token]
            any_parents = relation_tokens(data, "any_parent")
            all_parents = relation_tokens(data, "all_parents")
            if any_parents and not selected.intersection(any_parents):
                parent_gaps += 1
            parent_gaps += sum(parent not in selected for parent in all_parents)
            mutual_conflicts += len(
                selected.intersection(relation_tokens(data, "mutually_exclusive"))
            )
        pending = set(selected)
        completed: set[str] = set()
        while pending:
            eligible = []
            for token in pending:
                data = organization.traits[token]
                any_parents = relation_tokens(data, "any_parent")
                all_parents = relation_tokens(data, "all_parents")
                if all(parent in completed for parent in all_parents) and (
                    not any_parents
                    or any(parent in completed for parent in any_parents)
                ):
                    eligible.append(token)
            if not eligible:
                topology_failures += 1
                break
            completed.update(eligible)
            pending.difference_update(eligible)
    return {
        "selected_traits": selected_traits,
        "invalid_traits": sample["invalid_total"],
        "parent_gaps": parent_gaps,
        "mutual_conflicts": mutual_conflicts // 2,
        "topology_failures": topology_failures,
    }

def compact_list(values: list[str], limit: int = 8) -> str:
    if len(values) <= limit:
        return "、".join(values)
    return "、".join(values[:limit]) + f" 等 {len(values)} 项"


def render_report(inventory: dict, _vanilla_dir: Path, coverage_file: Path) -> str:
    summary = inventory["summary"]
    shapes = inventory["shapes"]
    uncovered = [shape for shape in shapes if not shape["covered"]]
    uncovered.sort(
        key=lambda shape: (
            -shape["organization_count"],
            shape["representative"],
        )
    )
    lines = [
        "# v2.3 MIO 架构第一轮盘点",
        "",
        "> 本报告分析原版定义、当前 PRC/GER/ENG 路线及 test8/test9/test10 实机样本，不修改 MOD 效果。",
        "",
        "## 结论",
        "",
        f"- 原版目录中识别到 **{summary['all_definitions']}** 个组织定义，其中 "
        f"**{summary['generic_definitions']}** 个通用模板、"
        f"**{summary['country_organizations']}** 个国家/可用组织。",
        f"- 国家组织按完整特质 token 区分有 **{summary['exact_effective_trees']}** 棵有效树；"
        f"忽略特质名称、保留节点布局和父子/互斥关系后，有 "
        f"**{summary['structural_shapes']}** 种结构。",
f"- 当前 PRC 独立路线与 GER/ENG 通用路线含 **{summary['covered_organizations']}** 个组织，"
        f"覆盖 **{summary['covered_shapes']}** 种已实现结构。",
        "- 234 种原版静态结构仅用于解析器核对；国策前置、互斥路线、外国共享公司和"
        "未实例化定义不属于本项目目标，不能据此推算剩余工作量。",
        "",
        "## 口径",
        "",
        "- “有效树”：递归展开 `include`，再应用顶层 `remove_trait`、`trait/add_trait`、"
        "`override_trait`。",
        "- “同结构”：忽略组织名和特质 token，保留节点坐标、特殊特质标记，以及 "
        "`any_parent`、`all_parents`、`relative_position_id`、`mutually_exclusive` "
        "的有向关系。",
        "- 可见性、数值加成和完成效果不参与结构指纹；它们仍会影响实际可点性，生成路线时必须"
        "再逐公司核对。",
        "- `mio.txt` 是示例/调试定义，本轮排除。",
        "- `00_DEBUG_organization.txt` 和 `_template_organization.txt` 也不属于正常国家内容，"
        "本轮排除。",
        "",
        "## 当前覆盖核对",
        "",
        f"- 国家分布：{json.dumps(inventory['coverage_by_country'], ensure_ascii=False)}。",
        f"- 当前脚本中找不到的组织："
        f"{compact_list(inventory['missing_covered']) if inventory['missing_covered'] else '无'}。",
        f"- 原版重复定义 token："
        f"{compact_list(inventory['duplicates']) if inventory['duplicates'] else '无'}。",
        f"- 原版源文件括号不平衡："
        f"{compact_list([item['source'] for item in inventory['source_repairs']]) if inventory['source_repairs'] else '无'}；"
        "分析器仅在文件末尾补齐未闭合块并保留记录。",
        "",
        "## 通用模板家族",
        "",
        "| 通用模板 | 国家组织数 | 结构数 | 当前覆盖组织数 | 涉及国家 |",
        "|---|---:|---:|---:|---|",
    ]
    for family in inventory["include_families"]:
        lines.append(
            f"| `{family['include']}` | {family['count']} | {family['shape_count']} | "
            f"{family['covered']} | {compact_list(family['countries'], 12)} |"
        )

    lines.extend(
        [
            "",
            "## 静态结构说明",
            "",
            f"原版共识别 **{summary['structural_shapes']}** 种静态结构。该数字仅作为解析完整性背景，"
            "不作为完成目标、未覆盖数量或国家测试推荐依据。",
        ]
    )
    comparison = inventory.get("test8_comparison")
    if comparison:
        lines.extend(
            [
                "",
                "## test8 英国存档与当前脚本差异",
                "",
                f"- test8 的 16 家英国 MIO 共记录 **{comparison['save_unlocked_total']}** 个已解锁特质；"
                f"当前脚本共写入 **{comparison['scripted_total']}** 个特质。",
                f"- test8 有、脚本没有：**{comparison['missing_total']}** 项；"
                f"脚本有、test8 没有：**{comparison['extra_total']}** 项。",
        "- 本节只记录差异，本轮未自动改写一键效果。",
                "",
                "| 组织 | test8 | 当前脚本 | test8 新增 | 脚本额外 |",
                "|---|---:|---:|---|---|",
            ]
        )
        for row in comparison["rows"]:
            lines.append(
                f"| `{row['organization']}` | {row['save_unlocked']} | {row['scripted']} | "
                f"{compact_list(row['missing_from_script']) or '—'} | "
                f"{compact_list(row['extra_in_script']) or '—'} |"
            )

    samples = inventory.get("country_samples", [])
    if samples:
        lines.extend(
            [
                "",
                "## 新增国家实机样本",
                "",
                "本轮严格口径只记录存档中实际已点出的公司和特质；国策前置、互斥路线另一侧、外国共享公司及未实例化定义全部忽略；"
                "这些排除项不计为漏点、剩余覆盖或后续工作量。",
                "",
                "| 国家 | 存档 | 有已解锁特质的组织 | 已解锁特质 | 结构数 | 相对当前新增结构 | 非法/失配特质 |",
                "|---|---|---:|---:|---:|---:|---:|",
            ]
        )
        for sample in samples:
            lines.append(
                f"| {sample['tag']} | `{sample['save']}` | "
                f"{sample['sampled_organizations']} | {sample['unlocked_total']} | "
                f"{sample['sampled_shapes']} | {sample['new_shapes_vs_current']} | "
                f"{sample['invalid_total']} |"
            )
        lines.append(
            f"\n- PRC/GER/ENG 当前脚本与这些存档累计确认 "
            f"**{inventory['combined_sample_coverage']['shapes']}** 种实际样本结构；"
            "不再与 234 种原版静态结构相减来推算剩余工作量。"
        )
        test10_audits = [
            sample["dependency_audit"]
            for sample in samples
            if sample["save"] == "test10"
        ]
        if test10_audits:
            test10_traits = sum(item["selected_traits"] for item in test10_audits)
            audit_failures = {
                key: sum(item[key] for item in test10_audits)
                for key in (
                    "invalid_traits",
                    "parent_gaps",
                    "mutual_conflicts",
                    "topology_failures",
                )
            }
            lines.append(
                f"- test10 四国共 **{test10_traits}** 个已点特质：原版树失配 "
                f"{audit_failures['invalid_traits']}、父节点缺失 "
                f"{audit_failures['parent_gaps']}、互斥冲突 "
                f"{audit_failures['mutual_conflicts']}、拓扑排序失败 "
                f"{audit_failures['topology_failures']}。"
            )
        for sample in samples:
            lines.extend(
                [
                    "",
                    f"### {sample['tag']} 逐组织",
                    "",
                    "| 组织 | 实际已解锁特质 |",
                    "|---|---:|",
                ]
            )
            for row in sample["rows"]:
                if not row["unlocked"]:
                    continue
                lines.append(
                    f"| `{row['organization']}` | {row['unlocked']} |"
                )

    lines.extend(
        [
            "",
            "## 建议执行方式",
            "",
            "1. 后续只从维护者实际点完的存档提取路线，不按原版静态定义推算完成比例。",
            "2. 每个实机存档抽取“已完成特质集合”，与该公司的有效树核对；相同结构可共享"
            "生成逻辑，但最终仍按公司 token 执行。",
            "3. 对实际已点集合生成父节点优先顺序；不处理未点出的国策、互斥或外国共享分支。"
            "特殊特质的完成顺序。",
            "4. 在覆盖表达到目标后再生成效果代码；本轮报告本身不授权修改一键初始化。",
            "",
            "## 数据来源",
            "",
            "- 原版 MIO：由 `--vanilla` 或 `HOI4_VANILLA_PATH` 指定（报告不固化机器绝对路径）",
            f"- GER/ENG 通用覆盖脚本：`common/scripted_effects/{coverage_file.name}`",
            f"- PRC 独立覆盖脚本：`common/scripted_effects/{DEFAULT_ADDITIONAL_COVERAGE.name}`",
            "- 生成器：`tools/analyze_mio_archetypes.py`",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--vanilla",
        type=Path,
        help="HOI4 原版根目录；省略时读取 HOI4_VANILLA_PATH 或探测已知盘符",
    )
    parser.add_argument("--coverage-file", type=Path, default=DEFAULT_COVERAGE)
    parser.add_argument(
        "--additional-coverage-file",
        type=Path,
        action="append",
        default=[DEFAULT_ADDITIONAL_COVERAGE],
    )
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument(
        "--save",
        type=Path,
        help="Optional melted plaintext save used to compare completed ENG traits.",
    )
    parser.add_argument(
        "--sample",
        action="append",
        default=[],
        metavar="TAG=PATH",
        help="Optional melted save sample for a country; may be repeated.",
    )
    args = parser.parse_args()

    vanilla_root = resolve_vanilla_path(args.vanilla)
    organizations_dir = (
        vanilla_root
        / "common"
        / "military_industrial_organization"
        / "organizations"
    )
    if not organizations_dir.is_dir():
        raise SystemExit(f"Vanilla MIO directory not found: {organizations_dir}")
    if not args.coverage_file.is_file():
        raise SystemExit(f"Coverage file not found: {args.coverage_file}")
    for path in args.additional_coverage_file:
        if not path.is_file():
            raise SystemExit(f"Additional coverage file not found: {path}")

    organizations, duplicates, source_repairs = load_organizations(organizations_dir)
    coverage = set(covered_tokens(args.coverage_file))
    for path in args.additional_coverage_file:
        coverage.update(covered_tokens(path))
    inventory = build_inventory(organizations, coverage, duplicates, source_repairs)
    if args.save:
        if not args.save.is_file():
            raise SystemExit(f"Melted save not found: {args.save}")
        inventory["test8_comparison"] = build_save_comparison(
            args.save, args.coverage_file, coverage
        )
    samples = []
    for specification in args.sample:
        if "=" not in specification:
            raise SystemExit(f"Invalid --sample value: {specification!r}")
        tag, raw_path = specification.split("=", 1)
        tag = tag.strip().upper()
        save_path = Path(raw_path)
        if not re.fullmatch(r"[A-Z0-9]{3}", tag):
            raise SystemExit(f"Invalid sample tag: {tag!r}")
        if not save_path.is_file():
            raise SystemExit(f"Melted sample not found: {save_path}")
        samples.append(build_country_sample(save_path, tag, organizations))
    if samples:
        current_shapes = {
            organizations[token].shape_hash
            for token in coverage
            if token in organizations
        }
        combined_shapes = set(current_shapes)
        for sample in samples:
            sampled_tokens = [
                row["organization"] for row in sample["rows"] if row["unlocked"]
            ]
            sampled_shapes = {
                organizations[token].shape_hash for token in sampled_tokens
            }
            sample["dependency_audit"] = audit_country_sample(sample, organizations)
            sample["sampled_shapes"] = len(sampled_shapes)
            sample["new_shapes_vs_current"] = len(sampled_shapes - current_shapes)
            combined_shapes |= sampled_shapes
        inventory["country_samples"] = samples
        inventory["combined_sample_coverage"] = {
            "shapes": len(combined_shapes),
            "new_shapes": len(combined_shapes - current_shapes),
        }
        next_recommendations, next_unassigned = recommend_countries(
            organizations,
            combined_shapes,
            excluded_countries=(
                {sample["tag"] for sample in samples}
                | {
                    country_code(organizations[token])
                    for token in coverage
                    if token in organizations
                }
            ),
        )
        inventory["next_recommended_countries"] = next_recommendations
        inventory["next_unassigned_shapes"] = next_unassigned

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        render_report(inventory, organizations_dir, args.coverage_file),
        encoding="utf-8",
    )
    args.json.write_text(
        json.dumps(inventory, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(inventory["summary"], ensure_ascii=False, indent=2))
    print(f"Report: {args.report}")
    print(f"JSON: {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
