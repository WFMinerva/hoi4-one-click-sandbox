# -*- coding: utf-8 -*-
"""v2.9-test4 F17: split PRC_OCS_research_all_effect into per-start-year
subsets (PRC_OCS_research_year_<bucket>_effect).

Reads the repository's PRC_OCS_research_effects.txt for the full technology
key set, and the vanilla common/technologies tree for start_year values.

v2.9-test6 (D7/D8):
- LEGACY_KEYS (hidden pre-NSB/MtG/BBA leftover technologies, e.g. gwtank /
  fighter1 / naval_bomber1-3) are excluded from every year group and from
  research_all (player feedback 2026-08-23: "史前科技" clutter).
- Technologies without a start_year are placed by FORCED_BUCKETS (player
  point-checks) or, when their tree row (folder position y) is <= 2, into
  the <=1936 bucket; the rest stay in research_all only.
- `--check` compares the committed output (contract gate).

Buckets: <=1936, 1937..1944 (per year), 1945+.

Usage:
  python tools/generate_year_tech_effects.py            # write output file
  python tools/generate_year_tech_effects.py --check    # compare committed output
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESEARCH_EFFECTS = ROOT / "common" / "scripted_effects" / "PRC_OCS_research_effects.txt"
OUTPUT = ROOT / "common" / "scripted_effects" / "PRC_OCS_year_tech_effects.txt"

BUCKETS: list[tuple[str, int | None]] = [
    ("1936", 1936),
    ("1937", 1937),
    ("1938", 1938),
    ("1939", 1939),
    ("1940", 1940),
    ("1941", 1941),
    ("1942", 1942),
    ("1943", 1943),
    ("1944", 1944),
    ("1945", None),  # 1945+
]

# v2.9-test6 (D7): hidden leftover technologies (not shown in the vanilla tech
# tree). Researched only via set_technology they clutter the research history
# with "prehistoric" entries; excluded from research_all AND year groups.
# Keep in sync with the contract test (test_v29_test6_d7_d8_tech_contract).
LEGACY_KEYS = frozenset({
    # pre-NSB tank line
    "gwtank", "basic_light_tank", "improved_light_tank", "advanced_light_tank",
    "basic_medium_tank", "basic_heavy_tank", "improved_heavy_tank",
    "amphibious_tank", "amphibious_tank_2", "improved_light_spaa",
    # pre-BBA air line
    "early_fighter", "fighter1", "cv_fighter2", "naval_bomber1",
    "naval_bomber2", "naval_bomber3", "suicide_craft", "suicide_charge",
    "transport",
    # pre-MtG naval line
    "early_carrier", "basic_carrier", "early_battleship", "early_light_cruiser",
    "basic_light_cruiser", "basic_heavy_cruiser", "improved_destroyer",
    "coastal_defense_ships", "panzerschiffe", "ship_hull_super_heavy",
    "basic_submarine", "improved_submarine", "advanced_submarine",
    "pre_dreadnoughts",
})

# v2.9-test6 (D8): player point-checked technologies without a start_year.
# Forced into the bucket the player expects them under.
# v2.9-test7 (B1, player feedback 2026-08-24): the follow-up tiers of the
# damage-control / fire-control-methods lines join their tier-1s in 1936;
# improved_heavy_armor_scheme moves 1938 -> 1936 (player point-checked twice:
# "36年缺失", expects the whole early line under the 1936 button).
FORCED_BUCKETS: dict[str, str] = {
    "radio": "1936",
    "mechanical_computing": "1936",
    "basic_fire_control_system": "1936",
    "damage_control_1": "1936",
    "damage_control_2": "1936",
    "damage_control_3": "1936",
    "excavation1": "1936",
    "concentrated_industry": "1936",
    "dispersed_industry": "1936",
    "fire_control_methods_1": "1936",
    "fire_control_methods_2": "1936",
    "fire_control_methods_3": "1936",
    "improved_heavy_armor_scheme": "1936",
    "improved_fire_control_system": "1938",
    "advanced_fire_control_system": "1939",
}


def research_all_keys() -> set[str]:
    text = RESEARCH_EFFECTS.read_text(encoding="utf-8")
    m = re.search(r"PRC_OCS_research_all_effect\s*=\s*\{", text)
    if not m:
        raise SystemExit("PRC_OCS_research_all_effect not found")
    start = m.end()
    depth = 1
    i = start
    while i < len(text) and depth:
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
        i += 1
    block = text[m.start() : i]
    return set(
        re.findall(r"^\s*([A-Za-z0-9_]+)\s*=\s*1\s*$", block, re.M)
    )


def start_years(vanilla_root: Path) -> tuple[dict[str, int], dict[str, int]]:
    """Return (start_year mapping, tree-row y mapping) for vanilla techs."""
    years: dict[str, int] = {}
    rows: dict[str, int] = {}
    for path in (vanilla_root / "common" / "technologies").rglob("*.txt"):
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        for m in re.finditer(r"^\s*([A-Za-z0-9_]+)\s*=\s*\{", text, re.M):
            key = m.group(1)
            if key in years or key in ("technologies",):
                continue
            # balanced-brace scan for the whole technology block
            start = m.end()
            depth = 1
            i = start
            while i < len(text) and depth:
                if text[i] == "{":
                    depth += 1
                elif text[i] == "}":
                    depth -= 1
                i += 1
            block = text[m.start() : i]
            year = re.search(r"start_year\s*=\s*(\d{4})", block)
            if year:
                years[key] = int(year.group(1))
            # tree row: folder = { name = X position = { x = A y = B } }
            pos = re.search(
                r"folder\s*=\s*\{\s*name\s*=\s*\S+\s*position\s*=\s*\{\s*x\s*=\s*-?\d+\s*y\s*=\s*(-?\d+)\s*\}",
                block,
            )
            if pos:
                rows[key] = int(pos.group(1))
    return years, rows


def build(vanilla_root: Path) -> str:
    keys = research_all_keys()
    years, rows = start_years(vanilla_root)
    buckets: dict[str, list[str]] = {name: [] for name, _ in BUCKETS}
    skipped: list[str] = []
    for key in sorted(keys - LEGACY_KEYS):
        year = years.get(key)
        if year is None:
            forced = FORCED_BUCKETS.get(key)
            if forced is not None:
                buckets[forced].append(key)
                continue
            # no start_year: early tree rows (y <= 2) land in <=1936.
            if rows.get(key, 99) <= 2:
                buckets["1936"].append(key)
                continue
            skipped.append(key)
            continue
        bucket = None
        for name, limit in BUCKETS:
            if limit is None:
                bucket = name
            elif year <= limit:
                bucket = name
                break
        buckets[bucket].append(key)
    lines = [
        "# Generated per-year research subsets (v2.9-test4 F17; v2.9-test6 D7/D8).",
        "# Sources: repository PRC_OCS_research_all_effect key set + vanilla",
        "# common/technologies start_year / tree-row values. Hidden legacy",
        "# technologies (LEGACY_KEYS) are excluded; no-start_year techs land",
        "# in the <=1936 bucket (row y<=2 or FORCED_BUCKETS) or stay in",
        "# research_all only.",
        "# Do not hand-edit; run tools/generate_year_tech_effects.py.",
    ]
    for name, _ in BUCKETS:
        keys_in = buckets[name]
        lines.append("")
        lines.append("PRC_OCS_research_year_%s_effect = {" % name)
        lines.append("\tset_technology = {")
        for key in keys_in:
            lines.append("\t\t%s = 1" % key)
        lines.append("\t}")
        lines.append("}")
    lines.append("")
    lines.append("# %d technologies skipped (no start_year, late row): %s" % (
        len(skipped), ", ".join(sorted(skipped)[:12]),
    ))
    lines.append("# %d legacy technologies excluded: %s" % (
        len(sorted(keys & LEGACY_KEYS)),
        ", ".join(sorted(keys & LEGACY_KEYS)),
    ))
    return "\n".join(lines)


def main() -> int:
    import hoi4_paths  # noqa: F401  (resolves vanilla root)

    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--vanilla", type=Path, default=None)
    args = parser.parse_args()
    vanilla_root = hoi4_paths.resolve_vanilla_path(args.vanilla)
    content = build(vanilla_root)
    if args.check:
        if OUTPUT.read_text(encoding="utf-8") != content:
            print("Year-tech effects are out of date.", file=sys.stderr)
            return 1
    else:
        OUTPUT.write_text(content, encoding="utf-8", newline="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
