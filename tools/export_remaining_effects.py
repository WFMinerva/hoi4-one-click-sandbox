"""Print the remaining special-project choice groups with their portable
effect scripts, for hand-authoring the v2.6-test2 events without re-reading
vanilla files. Reads docs/analysis/v2.6_特殊科研互斥选项清单.json."""

import json
from pathlib import Path

JSON = (
    Path(__file__).resolve().parents[1]
    / "docs" / "analysis" / "v2.6_特殊科研互斥选项清单.json"
)

DONE = {
    "sp_air_jet_engine_unique_reward",
    "sp_air_axial_jet_engine_unique_reward",
    "sp_air_supersonic_jet_unique_reward",
    "sp_naval_cruiser_submarine_unique_reward_a",
    "sp_naval_fleet_submarine_unique_reward_a",
    "sp_naval_torpedo_cruiser_unique_reward_a",
}

data = json.loads(JSON.read_text(encoding="utf-8"))
remaining = [g for g in data if g["reward"] not in DONE]
remaining.sort(key=lambda g: (g["specialization"], g["project"], g["reward"]))

for g in remaining:
    print(f"### {g['specialization'].upper()} | {g['project']} | {g['reward']}")
    for o in g["options"]:
        print(f"--- option {o['token']} default={o['default']}")
        print(o["effect"] or "(no portable effect)")
    print()
print(f"TOTAL groups remaining: {len(remaining)}")