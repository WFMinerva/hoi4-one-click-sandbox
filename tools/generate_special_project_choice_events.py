"""Generate remaining v2.6-test2 choose-your-bonus events from inventory JSON.

Each mutually exclusive reward group becomes exactly one country_event.
Groups that share the same project (e.g. stronghold network, _a/_b rewards)
each get their own event id and their own country flag; the flag is derived
from the reward key so groups are never merged or blocked by a shared flag.

Every option returns to the specialization dispatch menu afterwards
(air -> PRC_OCS.50, naval -> PRC_OCS.51, land -> PRC_OCS.48,
nuclear -> PRC_OCS.49) so the player can pick the next unpicked group.

Writes:
  events/PRC_OCS_choice_events_more.txt  (group events only)
  docs/analysis/v2.6_特殊科研组事件映射.json (id/flag/menu per group)
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from tools import analyze_special_project_choices as A

ROOT = Path(__file__).resolve().parents[1]
JSON = ROOT / "docs" / "analysis" / "v2.6_特殊科研互斥选项清单.json"
EVENTS_OUT = ROOT / "events" / "PRC_OCS_choice_events_more.txt"
MAPPING_OUT = ROOT / "docs" / "analysis" / "v2.6_特殊科研组事件映射.json"

DONE = {
    "sp_air_jet_engine_unique_reward",
    "sp_air_axial_jet_engine_unique_reward",
    "sp_air_supersonic_jet_unique_reward",
    "sp_naval_cruiser_submarine_unique_reward_a",
    "sp_naval_fleet_submarine_unique_reward_a",
    "sp_naval_torpedo_cruiser_unique_reward_a",
}
DROP_KEYS = A.PROJECT_BUFF_KEYS | {"scientist_effects", "facility_state_effects"}

SPEC_ZH = {"air": "空军", "land": "陆军", "naval": "海军", "nuclear": "核能"}
# Dispatch menu id per specialization (menus 48-51 appended by finish_choice_events).
MENU_IDS = {"air": 50, "naval": 51, "land": 48, "nuclear": 49}
FIRST_EVENT_ID = 22


def _flag(reward: str) -> str:
    """Per-reward unique country flag so _a/_b groups never share a flag."""
    return f"PRC_OCS_{reward}_choice_done"


def _filter(block: A.Block) -> A.Block:
    keep = []
    for a in A.all_assignments(block):
        if a.key in DROP_KEYS or a.key == "FROM":
            continue
        value = _filter(a.value) if isinstance(a.value, A.Block) else a.value
        keep.append(A.Assignment(a.key, value))
    return A.Block(tuple(keep))


def _body(text: str) -> str:
    """Return the filtered country_effects block rendered with A.block_text.
    A.block_text preserves DLC quotes (fixed upstream) and uses tab indentation.
    """
    if not text:
        return ""
    root, _ = A.parse_block(A.tokenize(text))
    assigns = A.all_assignments(root)
    if len(assigns) == 1 and assigns[0].key == "country_effects":
        return A.block_text(_filter(assigns[0].value))
    return A.block_text(_filter(root))


def _label(token: str) -> str:
    m = re.search(r"preference_(\w+)", token)
    if m:
        return m.group(1).replace("_", " ")
    m = re.search(r"_reward_(\w+)$", token)
    return m.group(1).replace("_", " ") if m else token.split("_")[-1]


def main() -> int:
    groups = json.loads(JSON.read_text(encoding="utf-8"))
    remaining = [
        g for g in groups if g["reward"] not in DONE
    ]
    remaining.sort(
        key=lambda g: (g["specialization"], g["project"], g["reward"])
    )
    lines: list[str] = []
    mapping: list[dict] = []
    nid = FIRST_EVENT_ID
    for g in remaining:
        eid = nid
        nid += 1
        flag = _flag(g["reward"])
        menu_id = MENU_IDS[g["specialization"]]
        mapping.append(
            {
                "eid": eid,
                "specialization": g["specialization"],
                "project": g["project"],
                "reward": g["reward"],
                "flag": flag,
                "menu": menu_id,
            }
        )
        lines.append("country_event = {")
        lines.append(f" id = PRC_OCS.{eid}")
        lines.append(f" title = PRC_OCS.{eid}.t")
        lines.append(f" desc = PRC_OCS.{eid}.d")
        lines.append(" picture = GFX_report_event_generic_research")
        lines.append(" is_triggered_only = yes")
        lines.append("")
        letter = "a"
        for option in g["options"]:
            lines.append(" option = {")
            lines.append(f"  name = PRC_OCS.{eid}.{letter}")
            lines.append("  hidden_effect = {")
            lines.append(f"   set_country_flag = {flag}")
            body = _body(option.get("effect") or "")
            for line in body.splitlines():
                lines.append(f"   {line}")
            lines.append("  }")
            lines.append(f"  country_event = {{ id = PRC_OCS.{menu_id} }}")
            lines.append(" }")
            letter = chr(ord(letter) + 1)
        lines.append("}")
        lines.append("")
    header = (
        "# v2.6-test2 extended choose-your-bonus events (generated).\n"
    )
    EVENTS_OUT.write_text(header + "\n".join(lines), encoding="utf-8")
    MAPPING_OUT.write_text(
        json.dumps(mapping, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"GROUPS: {len(mapping)}")
    for item in mapping:
        print(f"PRC_OCS.{item['eid']} <- {item['reward']} (menu {item['menu']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())