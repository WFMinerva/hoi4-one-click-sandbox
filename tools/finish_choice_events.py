"""Post-process generated choose-your-bonus events (idempotent).

Reads docs/analysis/v2.6_特殊科研组事件映射.json produced by
generate_special_project_choice_events.py, then:

  1. Appends the four dispatch menus (48 land, 49 nuclear, 50 air, 51 naval)
     to events/PRC_OCS_choice_events_more.txt.
  2. Rebuilds the generated bilingual localisation block (group events 22-47
     and menus 48-51).

Each dispatch menu shows one option per unpicked reward group and returns to
itself, so the player can pick groups in any order. The tail option (z) is
visible only when every group of that specialization is flagged, and sets the
per-country done flag so the corresponding decision disappears.

The localisation block is regenerated from group titles/option labels defined
below; stale keys from earlier runs are stripped first (from the first
"PRC_OCS.22.t" line), so the script can be re-run safely.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVENTS = ROOT / "events" / "PRC_OCS_choice_events_more.txt"
MAPPING = ROOT / "docs" / "analysis" / "v2.6_特殊科研组事件映射.json"
LOC_EN = ROOT / "localisation" / "english" / "PRC_OCS_l_english.yml"
LOC_ZH = ROOT / "localisation" / "simp_chinese" / "PRC_OCS_l_simp_chinese.yml"

EVENTS_MARKER = "# === v2.6 dispatch menus (48-51) appended by finish_choice_events.py ==="

# Per-group event data: eid -> (title_en, title_zh, menu_label_en, menu_label_zh,
#                               [option labels en], [option labels zh])
GROUP_INFO = {
    22: ("Earthshaker Bomb Prototype Focus", "地震炸弹原型方向", "Earthshaker Bomb", "地震炸弹",
         ["Naval targeting", "Raw power", "Both"],
         ["对舰打击", "纯粹火力", "两者兼顾"]),
    23: ("Helicopter Prototype Focus", "直升机原型方向", "Helicopter", "直升机",
         ["Speed", "Compromise", "Protection"],
         ["速度", "折中", "防护"]),
    24: ("Intercontinental Bomber Prototype Focus", "洲际轰炸机原型方向", "Intercontinental Bomber", "洲际轰炸机",
         ["Balanced", "Bombing payload", "Protection"],
         ["均衡", "轰炸载荷", "防护"]),
    25: ("Mothership Aircraft Prototype Focus", "空天母舰原型方向", "Mothership Aircraft", "空天母舰",
         ["Speed and agility", "Reliability", "Strength"],
         ["速度与机动", "可靠性", "强度"]),
    26: ("Stronghold Network — Concrete Reinforcement (I)", "要塞网络·混凝土加固（一）",
         "Concrete Reinforcement (I)", "混凝土加固（一）",
         ["Standardize and document", "Use in current project"],
         ["整理并记录成果", "用于当前项目"]),
    27: ("Stronghold Network — Concrete Reinforcement (II)", "要塞网络·混凝土加固（二）",
         "Concrete Reinforcement (II)", "混凝土加固（二）",
         ["Standardize and document", "Use in current project"],
         ["整理并记录成果", "用于当前项目"]),
    28: ("Stronghold Network — Communication Overhaul", "要塞网络·通信系统改造",
         "Communication Overhaul", "通信系统改造",
         ["Standardize and document", "Use in current project"],
         ["整理并记录成果", "用于当前项目"]),
    29: ("Escort Carrier — Design A", "护航航母·方案A",
         "Escort Carrier — Design A", "护航航母·方案A",
         ["Range", "Strength", "Speed"],
         ["航程", "强度", "速度"]),
    30: ("Escort Carrier — Design B", "护航航母·方案B",
         "Escort Carrier — Design B", "护航航母·方案B",
         ["Sub detection", "Compromise", "Surface detection"],
         ["潜侦", "折中", "面侦"]),
    31: ("Ice Carrier Prototype Focus", "冰航母原型方向", "Ice Carrier", "冰航母",
         ["Weather handling", "Strength"],
         ["耐海况", "强度"]),
    32: ("Midget Submarine Prototype Focus", "袖珍潜艇原型方向", "Midget Submarine", "袖珍潜艇",
         ["Stealth", "Reliability", "Range"],
         ["隐蔽", "可靠", "航程"]),
    33: ("Modern Battleship — Design A", "现代战列舰·方案A",
         "Modern Battleship — Design A", "现代战列舰·方案A",
         ["Heavy attack", "Speed", "Light attack"],
         ["重炮攻击", "速度", "轻型炮攻击"]),
    34: ("Modern Battleship — Design B", "现代战列舰·方案B",
         "Modern Battleship — Design B", "现代战列舰·方案B",
         ["Armor", "Anti-air", "Anti-torpedo"],
         ["装甲", "防空", "反鱼雷"]),
    35: ("Modern Carrier — Design A", "现代航母·方案A",
         "Modern Carrier — Design A", "现代航母·方案A",
         ["Detection", "Speed", "Light attack"],
         ["探测", "速度", "轻型炮攻击"]),
    36: ("Modern Carrier — Design B", "现代航母·方案B",
         "Modern Carrier — Design B", "现代航母·方案B",
         ["Armor", "Anti-air", "Anti-torpedo"],
         ["装甲", "防空", "反鱼雷"]),
    37: ("Nuclear Missile Submarine Prototype Focus", "核导弹潜艇原型方向", "Nuclear Missile Submarine", "核导弹潜艇",
         ["Stealth", "Compromise", "Strength"],
         ["隐蔽", "折中", "强度"]),
    38: ("Nuclear Submarine Prototype Focus", "核潜艇原型方向", "Nuclear Submarine", "核潜艇",
         ["Stealth", "Compromise", "Strength"],
         ["隐蔽", "折中", "强度"]),
    39: ("Rocket Launching Submarine Prototype Focus", "导弹潜艇原型方向", "Rocket Launching Submarine", "导弹潜艇",
         ["Stealth", "Compromise", "Strength"],
         ["隐蔽", "折中", "强度"]),
    40: ("Submarine Carrier Prototype Focus", "潜水母舰原型方向", "Submarine Carrier", "潜水母舰",
         ["Speed", "Compromise", "Protection"],
         ["速度", "折中", "防护"]),
    41: ("Super Heavy Battleship — Design A", "超级战列舰·方案A",
         "Super Heavy Battleship — Design A", "超级战列舰·方案A",
         ["Heavy attack", "Speed", "Light attack"],
         ["重炮攻击", "速度", "轻型炮攻击"]),
    42: ("Super Heavy Battleship — Design B", "超级战列舰·方案B",
         "Super Heavy Battleship — Design B", "超级战列舰·方案B",
         ["Armor", "Anti-air", "Anti-torpedo"],
         ["装甲", "防空", "反鱼雷"]),
    43: ("Support Ships — Support Focus", "支援船·支援方案",
         "Support Ships — Support Focus", "支援船·支援方案",
         ["Support focus A", "Compromise", "Support focus C"],
         ["支援方案A", "折中", "支援方案C"]),
    44: ("Support Ships — Repair Focus", "支援船·维修方案",
         "Support Ships — Repair Focus", "支援船·维修方案",
         ["Repair focus A", "Compromise", "Repair focus C"],
         ["维修方案A", "折中", "维修方案C"]),
    45: ("Underway Replenishment Prototype Focus", "补给船原型方向", "Underway Replenishment", "补给船",
         ["Range focus", "Compromise", "Cost focus"],
         ["航程向", "折中", "造价向"]),
    46: ("Nuclear Isotope Separation Prototype Focus", "核同位素分离原型方向",
         "Isotope Separation", "同位素分离",
         ["Gaseous separation", "Centrifugal separation"],
         ["气体扩散法", "离心分离法"]),
    47: ("Nuclear Reactor Tested Reward", "核反应堆测试完成奖励",
         "Reactor Tested Reward", "反应堆测试奖励",
         ["Classify the results", "Public reveal"],
         ["结果保密处理", "向公众公开"]),
}

# Menu display data: menu id -> (spec, title_en, title_zh, done_flag)
MENU_INFO = {
    48: ("land", "Land Special Projects — Remaining Prototype Bonuses",
         "陆军特殊科研·剩余原型奖励选择", "PRC_OCS_land_special_project_choices_done"),
    49: ("nuclear", "Nuclear Special Projects — Remaining Prototype Bonuses",
         "核能特殊科研·剩余原型奖励选择", "PRC_OCS_nuclear_special_project_choices_done"),
    50: ("air", "Air Special Projects — Remaining Prototype Bonuses",
         "空军特殊科研·剩余原型奖励选择", "PRC_OCS_air_special_project_choices_done"),
    51: ("naval", "Naval Special Projects — Remaining Prototype Bonuses",
         "海军特殊科研·剩余原型奖励选择", "PRC_OCS_naval_special_project_choices_done"),
}

GROUP_DESC_EN = "Choose the mutually exclusive prototype-reward bonus."
GROUP_DESC_ZH = "请选择互斥的原型产物奖励。"
MENU_DESC_EN = "Pick each remaining mutually exclusive prototype-reward bonus."
MENU_DESC_ZH = "请逐一选择剩余的互斥原型产物奖励。"
Z_LABEL_EN = "All remaining bonuses picked"
Z_LABEL_ZH = "全部剩余原型奖励已选定"


def _option_letter(index: int) -> str:
    """Menu option letter. 'd' is reserved for the desc key, so skip it."""
    letter = chr(ord("a") + index)
    if letter >= "d":
        letter = chr(ord(letter) + 1)
    return letter


def _mapping() -> list[dict]:
    return json.loads(MAPPING.read_text(encoding="utf-8"))


def _strip_generated_block(path: Path) -> str:
    """Return text with the previously generated localisation block removed."""
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    start = next(
        (i for i, line in enumerate(lines) if re.match(r"^\s*PRC_OCS\.22\.t", line)),
        None,
    )
    if start is not None:
        lines = lines[:start]
    return "\n".join(lines).rstrip() + "\n"


def _strip_events_menu_block(ev: str) -> str:
    lines = ev.splitlines()
    start = next(
        (i for i, line in enumerate(lines) if line.startswith(EVENTS_MARKER)),
        None,
    )
    if start is not None:
        lines = lines[:start]
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    mapping = _mapping()
    by_menu: dict[int, list[dict]] = {}
    for item in mapping:
        by_menu.setdefault(item["menu"], []).append(item)

    # --- 1. Rebuild the events file: strip stale menus, re-append menus. ---
    ev = _strip_events_menu_block(EVENTS.read_text(encoding="utf-8"))
    menu_lines = [EVENTS_MARKER, ""]
    for menu_id in (48, 49, 50, 51):
        spec, title_en, title_zh, done_flag = MENU_INFO[menu_id]
        entries = sorted(
            by_menu.get(menu_id, []), key=lambda item: item["eid"]
        )
        menu_lines.append("country_event = {")
        menu_lines.append(f" id = PRC_OCS.{menu_id}")
        menu_lines.append(f" title = PRC_OCS.{menu_id}.t")
        menu_lines.append(f" desc = PRC_OCS.{menu_id}.d")
        menu_lines.append(" picture = GFX_report_event_generic_research")
        menu_lines.append(" is_triggered_only = yes")
        menu_lines.append("")
        for index, item in enumerate(entries):
            letter = _option_letter(index)
            menu_lines.append(" option = {")
            menu_lines.append(f"  name = PRC_OCS.{menu_id}.{letter}")
            menu_lines.append("  trigger = {")
            menu_lines.append(
                f"   NOT = {{ has_country_flag = {item['flag']} }}"
            )
            menu_lines.append("  }")
            menu_lines.append(f"  country_event = {{ id = PRC_OCS.{item['eid']} }}")
            menu_lines.append(" }")
        menu_lines.append(" option = {")
        menu_lines.append(f"  name = PRC_OCS.{menu_id}.z")
        menu_lines.append("  trigger = {")
        for item in entries:
            menu_lines.append(f"   has_country_flag = {item['flag']}")
        menu_lines.append("  }")
        menu_lines.append("  hidden_effect = {")
        menu_lines.append(f"   set_country_flag = {done_flag}")
        menu_lines.append("  }")
        menu_lines.append(" }")
        menu_lines.append("}")
        menu_lines.append("")
    ev = ev + "\n".join(menu_lines)
    EVENTS.write_text(ev, encoding="utf-8")

    # --- 2. Rebuild bilingual localisation block (22-47 groups + menus). ---
    en_rows: list[str] = []
    zh_rows: list[str] = []
    for item in mapping:
        eid = item["eid"]
        en_title, zh_title, _men, _mzh, opts_en, opts_zh = GROUP_INFO[eid]
        en_rows.append(f" PRC_OCS.{eid}.t:0 \"{en_title}\"")
        en_rows.append(f" PRC_OCS.{eid}.d:0 \"{GROUP_DESC_EN}\"")
        zh_rows.append(f" PRC_OCS.{eid}.t:0 \"{zh_title}\"")
        zh_rows.append(f" PRC_OCS.{eid}.d:0 \"{GROUP_DESC_ZH}\"")
        letter = "a"
        for en_opt, zh_opt in zip(opts_en, opts_zh):
            en_rows.append(f" PRC_OCS.{eid}.{letter}:0 \"{en_opt}\"")
            zh_rows.append(f" PRC_OCS.{eid}.{letter}:0 \"{zh_opt}\"")
            letter = chr(ord(letter) + 1)
    for menu_id in (48, 49, 50, 51):
        spec, title_en, title_zh, _done_flag = MENU_INFO[menu_id]
        entries = sorted(
            by_menu.get(menu_id, []), key=lambda item: item["eid"]
        )
        en_rows.append(f" PRC_OCS.{menu_id}.t:0 \"{title_en}\"")
        en_rows.append(f" PRC_OCS.{menu_id}.d:0 \"{MENU_DESC_EN}\"")
        zh_rows.append(f" PRC_OCS.{menu_id}.t:0 \"{title_zh}\"")
        zh_rows.append(f" PRC_OCS.{menu_id}.d:0 \"{MENU_DESC_ZH}\"")
        for index, item in enumerate(entries):
            letter = _option_letter(index)
            _en_t, _zh_t, men, mzh = (
                *(GROUP_INFO[item["eid"]][0:2]),
                GROUP_INFO[item["eid"]][2],
                GROUP_INFO[item["eid"]][3],
            )
            en_rows.append(f" PRC_OCS.{menu_id}.{letter}:0 \"{men}\"")
            zh_rows.append(f" PRC_OCS.{menu_id}.{letter}:0 \"{mzh}\"")
        en_rows.append(f" PRC_OCS.{menu_id}.z:0 \"{Z_LABEL_EN}\"")
        zh_rows.append(f" PRC_OCS.{menu_id}.z:0 \"{Z_LABEL_ZH}\"")

    for path, rows in ((LOC_EN, en_rows), (LOC_ZH, zh_rows)):
        text = _strip_generated_block(path)
        text += "\n".join(rows) + "\n"
        path.write_text(text, encoding="utf-8-sig")

    print("Done: menus 48-51 appended, localisation block 22-51 regenerated.")


if __name__ == "__main__":
    main()