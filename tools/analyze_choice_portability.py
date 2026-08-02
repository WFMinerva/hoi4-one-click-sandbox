"""Analyze which vanilla special-project choice buffs can be ported to events.

Reads docs/analysis/v2.6_特殊科研互斥选项清单.json and prints, per project,
which effect keys appear among buff-bearing options. Only COUNTRY-scope effects
(add_equipment_bonus, add_tech_bonus, set_technology, ...) are safely usable
inside decision/event options; project-context keys (equipment_bonus,
enable_equipment_modules) are NOT portable and must be skipped or reworked.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

JSON_PATH = (
    Path(__file__).resolve().parents[1]
    / "docs" / "analysis" / "v2.6_特殊科研互斥选项清单.json"
)

BUFF_KEYS = [
    "add_equipment_bonus",
    "equipment_bonus",
    "enable_equipment_modules",
    "add_tech_bonus",
    "research_technologies",
    "set_technology",
    "add_equipment_production",
]

# Project-context keys are NOT valid in decision/event scopes.
NON_PORTABLE = {"equipment_bonus", "enable_equipment_modules"}


def main() -> None:
    data = json.loads(JSON_PATH.read_text(encoding="utf-8"))

    per_project: dict[str, set[str]] = defaultdict(set)
    for group in data:
        for option in group["options"]:
            if not option["has_buff"]:
                continue
            text = option.get("effect") or ""
            for key in BUFF_KEYS:
                if key in text:
                    per_project[group["project"]].add(key)

    print(f"{'project':<48} {'portable':<5} kinds")
    print("-" * 110)
    for project in sorted(per_project):
        kinds = per_project[project]
        portable = all(k not in NON_PORTABLE for k in kinds)
        print(f"{project:<48} {'YES' if portable else 'NO ':<5} {', '.join(sorted(kinds))}")

    portable_groups = sum(
        1
        for project, kinds in per_project.items()
        if all(k not in NON_PORTABLE for k in kinds)
    )
    print(f"\nTOTAL projects with buff choices: {len(per_project)}")
    print(f"Fully portable to events: {portable_groups}")
    print(f"Has non-portable keys: {len(per_project) - portable_groups}")


if __name__ == "__main__":
    main()