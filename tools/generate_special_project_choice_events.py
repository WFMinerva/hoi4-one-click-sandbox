"""Generate choose-your-bonus events from the choice inventories.

Two inventories feed the generator:

  * docs/analysis/v2.6_特殊科研互斥选项清单.json (country-scope "selectable"
    groups) -> events 22-47, frozen mapping (v2.6 mapping file).
  * docs/analysis/v2.8_特殊科研互斥选项清单.json (project-scope "replicable"
    groups) -> events 54-69. Each equipment_bonus is reworked into a named
    add_equipment_bonus so the mutually exclusive reward is no longer lost by
    complete_special_project.

Each mutually exclusive reward group becomes exactly one country_event.
Groups that share the same project each get their own event id and their own
country flag; the flag is derived from the reward key so groups are never
merged or blocked by a shared flag.

Every option returns to the specialization dispatch menu afterwards
(air -> PRC_OCS.50, naval -> PRC_OCS.51, land -> PRC_OCS.48,
nuclear -> PRC_OCS.49, rocket -> PRC_OCS.52) so the player can pick the next
unpicked group.

Writes:
  events/PRC_OCS_choice_events_more.txt  (group events only; menus appended by
                                          finish_choice_events.py)
  docs/analysis/v2.6_特殊科研组事件映射.json (id/flag/menu per v2.6 group)
  docs/analysis/v2.8_特殊科研组事件映射.json (id/flag/menu per v2.8 group)
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from tools import analyze_special_project_choices as A

ROOT = Path(__file__).resolve().parents[1]
JSON = ROOT / "docs" / "analysis" / "v2.6_特殊科研互斥选项清单.json"
JSON_V28 = ROOT / "docs" / "analysis" / "v2.8_特殊科研互斥选项清单.json"
EVENTS_OUT = ROOT / "events" / "PRC_OCS_choice_events_more.txt"
MAPPING_OUT = ROOT / "docs" / "analysis" / "v2.6_特殊科研组事件映射.json"
MAPPING_OUT_V28 = ROOT / "docs" / "analysis" / "v2.8_特殊科研组事件映射.json"

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
# Dispatch menu id per specialization (menus 48-52 appended by finish_choice_events).
MENU_IDS = {"air": 50, "naval": 51, "land": 48, "nuclear": 49, "rocket": 52}
FIRST_EVENT_ID = 22
FIRST_EVENT_ID_V28 = 54


def _flag(reward: str) -> str:
    """Per-reward unique country flag so _a/_b groups never share a flag."""
    return f"PRC_OCS_{reward}_choice_done"


def _bonus_name(reward: str, option_token: str) -> str:
    """Unique add_equipment_bonus name for a reworked option."""
    return f"PRC_OCS_{reward}_{option_token}_bonus"


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


def _rework_effect(text: str, reward: str, option_token: str) -> str:
    """Rework a project-context iteration_output into country-scope effects.

    equipment_bonus blocks become add_equipment_bonus with a unique name;
    enable_equipment_modules blocks are kept verbatim (they are valid in
    country scope). Everything else (country_effects progress/flags, empty
    blocks) is dropped, so no-op options yield an empty effect.
    """
    if not text:
        return ""
    root, _ = A.parse_block(A.tokenize(text))
    parts: list[str] = []
    for entry in A.all_assignments(root):
        if entry.key == "equipment_bonus" and isinstance(entry.value, A.Block):
            add_block = A.Block(
                (
                    A.Assignment("name", A.Atom(_bonus_name(reward, option_token))),
                    A.Assignment("bonus", entry.value),
                )
            )
            parts.append(
                A.block_text(
                    A.Block((A.Assignment("add_equipment_bonus", add_block),))
                )
            )
        elif entry.key == "enable_equipment_modules" and isinstance(
            entry.value, A.Block
        ):
            parts.append(A.block_text(A.Block((entry,))))
    return "\n".join(parts)


def _label(token: str) -> str:
    m = re.search(r"preference_(\w+)", token)
    if m:
        return m.group(1).replace("_", " ")
    m = re.search(r"_reward_(\w+)$", token)
    return m.group(1).replace("_", " ") if m else token.split("_")[-1]


def _group_event_lines(
    g: dict, eid: int, flag: str, menu_id: int, rework: bool
) -> list[str]:
    lines: list[str] = []
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
        lines.append(f"  custom_effect_tooltip = PRC_OCS.{eid}.{letter}_tt")
        lines.append("  hidden_effect = {")
        lines.append(f"   set_country_flag = {flag}")
        if rework:
            body = _rework_effect(
                option.get("effect") or "", g["reward"], option["token"]
            )
        else:
            body = _body(option.get("effect") or "")
        for line in body.splitlines():
            lines.append(f"   {line}")
        lines.append("  }")
        lines.append(f"  country_event = {{ id = PRC_OCS.{menu_id} }}")
        lines.append(" }")
        letter = chr(ord(letter) + 1)
    lines.append("}")
    lines.append("")
    return lines


def main() -> int:
    v26_groups = json.loads(JSON.read_text(encoding="utf-8"))
    v28_groups = json.loads(JSON_V28.read_text(encoding="utf-8"))

    remaining = [g for g in v26_groups if g["reward"] not in DONE]
    remaining.sort(key=lambda g: (g["specialization"], g["project"], g["reward"]))

    lines: list[str] = []
    mapping_v26: list[dict] = []
    mapping_v28: list[dict] = []

    nid = FIRST_EVENT_ID
    for g in remaining:
        eid = nid
        nid += 1
        flag = _flag(g["reward"])
        menu_id = MENU_IDS[g["specialization"]]
        mapping_v26.append(
            {
                "eid": eid,
                "specialization": g["specialization"],
                "project": g["project"],
                "reward": g["reward"],
                "flag": flag,
                "menu": menu_id,
            }
        )
        lines.extend(_group_event_lines(g, eid, flag, menu_id, rework=False))

    nid = FIRST_EVENT_ID_V28
    for g in v28_groups:
        eid = nid
        nid += 1
        flag = _flag(g["reward"])
        menu_id = MENU_IDS[g["specialization"]]
        mapping_v28.append(
            {
                "eid": eid,
                "specialization": g["specialization"],
                "project": g["project"],
                "reward": g["reward"],
                "flag": flag,
                "menu": menu_id,
            }
        )
        lines.extend(_group_event_lines(g, eid, flag, menu_id, rework=True))

    header = "# choose-your-bonus group events 22-47 (v2.6) + 54-69 (v2.8) — generated.\n"
    EVENTS_OUT.write_text(header + "\n".join(lines), encoding="utf-8")
    MAPPING_OUT.write_text(
        json.dumps(mapping_v26, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    MAPPING_OUT_V28.write_text(
        json.dumps(mapping_v28, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"v2.6 GROUPS: {len(mapping_v26)}")
    for item in mapping_v26:
        print(f"PRC_OCS.{item['eid']} <- {item['reward']} (menu {item['menu']})")
    print(f"v2.8 GROUPS: {len(mapping_v28)}")
    for item in mapping_v28:
        print(f"PRC_OCS.{item['eid']} <- {item['reward']} (menu {item['menu']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
