# -*- coding: utf-8 -*-
"""v2.9-test4 F17: split PRC_OCS_research_all_effect into per-start-year
subsets (PRC_OCS_research_year_<bucket>_effect).

Reads the repository's PRC_OCS_research_effects.txt for the full technology
key set, and the vanilla common/technologies tree for start_year values.
Technologies without a start_year are skipped (they stay in research_all).

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


def start_years(vanilla_root: Path) -> dict[str, int]:
    mapping: dict[str, int] = {}
    for path in (vanilla_root / "common" / "technologies").rglob("*.txt"):
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        for m in re.finditer(r"^\s*([A-Za-z0-9_]+)\s*=\s*\{", text, re.M):
            key = m.group(1)
            if key in mapping or key in ("technologies",):
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
                mapping[key] = int(year.group(1))
    return mapping


def build(vanilla_root: Path) -> str:
    keys = research_all_keys()
    years = start_years(vanilla_root)
    buckets: dict[str, list[str]] = {name: [] for name, _ in BUCKETS}
    skipped: list[str] = []
    for key in sorted(keys):
        year = years.get(key)
        if year is None:
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
        "# Generated per-year research subsets (v2.9-test4 F17).",
        "# Sources: repository PRC_OCS_research_all_effect key set + vanilla",
        "# common/technologies start_year values. Technologies without a",
        "# start_year are skipped (still covered by research_all).",
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
    lines.append("# %d technologies skipped (no start_year): %s" % (
        len(skipped), ", ".join(sorted(skipped)[:12]),
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
