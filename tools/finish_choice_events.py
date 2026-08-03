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

# Per-group option tooltips for the effect-description optimisation (v2.7).
# Keyed by eid; each entry is (en_tooltips, zh_tooltips), one string per option
# in the same order as GROUP_INFO. The generator also emits a custom_effect_tooltip
# key (PRC_OCS.{eid}.{letter}_tt) so the player sees concrete numbers.
GROUP_TT = {
    22: ([
        "Large planes: +10% naval-strike targeting.",
        "Large planes: +5% naval-strike attack, +5% bombing.",
        "Large planes: +10% naval-strike targeting, +5% naval-strike attack, +5% bombing, +5% cost.",
    ], [
        "大型飞机：对海瞄准 +10%。",
        "大型飞机：对海攻击 +5%、轰炸 +5%。",
        "大型飞机：对海瞄准 +10%、对海攻击 +5%、轰炸 +5%、造价 +5%。",
    ]),
    23: ([
        "Helicopters: +10% max speed, -5% fuel consumption, -5% cost.",
        "Helicopters: +5% reliability.",
        "Helicopters: +10% armor, +10% defense, +10% breakthrough, +15% fuel consumption, +10% cost.",
    ], [
        "直升机：最大速度 +10%、油耗 -5%、造价 -5%。",
        "直升机：可靠性 +5%。",
        "直升机：装甲 +10%、防御 +10%、突破 +10%、油耗 +15%、造价 +10%。",
    ]),
    24: ([
        "Intercontinental bombers: +5% reliability.",
        "Intercontinental bombers: +15% bombing, but -5% air defense and -10% air attack.",
        "Intercontinental bombers: +15% air defense, but -10% air attack and -10% bombing.",
    ], [
        "洲际轰炸机：可靠性 +5%。",
        "洲际轰炸机：轰炸 +15%，但空防 -5%、空战 -10%。",
        "洲际轰炸机：空防 +15%，但空战 -10%、轰炸 -10%。",
    ]),
    25: ([
        "Motherships: +10% agility, +10% max speed, +15% fuel consumption.",
        "Motherships: +10% reliability.",
        "Motherships: +10% air defense, +10% air attack, +10% cost.",
    ], [
        "空天母舰：机动 +10%、最大速度 +10%、油耗 +15%。",
        "空天母舰：可靠性 +10%。",
        "空天母舰：空防 +10%、空战 +10%、造价 +10%。",
    ]),
    26: ([
        "Fortification research: +50% research speed, one use (fortification/construction).",
        "No bonus; keep the progress for the current project.",
    ], [
        "要塞科技：研究速度 +50%，1 次（要塞/建筑类科技）。",
        "不获得奖励；进度留用于当前项目。",
    ]),
    27: ([
        "Fortification research: +75% research speed, one use (fortification/construction); grants a high land-scientist XP reward when available.",
        "No bonus; keep the progress for the current project.",
    ], [
        "要塞科技：研究速度 +75%，1 次（要塞/建筑类科技）；可用的非在职陆军科学家获得大量经验。",
        "不获得奖励；进度留用于当前项目。",
    ]),
    28: ([
        "Fortification research: +25% research speed, one use (fortification/construction).",
        "No bonus; keep the progress for the current project.",
    ], [
        "要塞科技：研究速度 +25%，1 次（要塞/建筑类科技）。",
        "不获得奖励；进度留用于当前项目。",
    ]),
    29: ([
        "Escort carriers: +15% naval range, +5% cost.",
        "Escort carriers: +5% max strength, +10% reliability.",
        "Escort carriers: +15% naval speed, +2.5% cost.",
    ], [
        "护航航母：海军航程 +15%、造价 +5%。",
        "护航航母：最大船体强度 +5%、可靠性 +10%。",
        "护航航母：航速 +15%、造价 +2.5%。",
    ]),
    30: ([
        "Escort carriers: +12.5% sub detection.",
        "Escort carriers: +5% sub detection, +5% surface detection.",
        "Escort carriers: +12.5% surface detection.",
    ], [
        "护航航母：潜艇探测 +12.5%。",
        "护航航母：潜艇探测 +5%、水面探测 +5%。",
        "护航航母：水面探测 +12.5%。",
    ]),
    31: ([
        "Ice carriers: -15% naval weather penalty (MtG: same bonus on ship_hull_mega_carrier).",
        "Ice carriers: -5% cost, +10% max strength (MtG: same on ship_hull_mega_carrier).",
    ], [
        "冰航母：海况惩罚 -15%（陆上天线/无 MtG 时按 mega_carrier 生效）。",
        "冰航母：造价 -5%、最大船体强度 +10%。",
    ]),
    32: ([
        "Midget submarines: -20% naval range, -10% sub visibility.",
        "Midget submarines: +10% reliability.",
        "Midget submarines: +20% naval range, +10% sub visibility.",
    ], [
        "袖珍潜艇：航程 -20%、潜艇可见度 -10%。",
        "袖珍潜艇：可靠性 +10%。",
        "袖珍潜艇：航程 +20%、潜艇可见度 +10%。",
    ]),
    33: ([
        "Modern battleships: +20% heavy-gun hit chance, +15% heavy attack, +15% heavy armor piercing.",
        "Modern battleships: +10% naval speed, +15% surface detection, -7% surface visibility.",
        "Modern battleships: +10% light-gun hit chance, +10% light attack, +15% light armor piercing.",
    ], [
        "现代战列舰：重炮命中 +20%、重炮攻击 +15%、重炮穿甲 +15%。",
        "现代战列舰：航速 +10%、水面探测 +15%、水面可见度 -7%。",
        "现代战列舰：轻型炮命中 +10%、轻型炮攻击 +10%、轻型炮穿甲 +15%。",
    ]),
    34: ([
        "Modern battleships: +15% armor, +10% max strength.",
        "Modern battleships: +25% anti-air attack, +7% reliability.",
        "Modern battleships: +15% enemy torpedo critical chance, +20% torpedo damage reduction.",
    ], [
        "现代战列舰：装甲 +15%、最大船体强度 +10%。",
        "现代战列舰：防空攻击 +25%、可靠性 +7%。",
        "现代战列舰：敌方鱼雷暴击率 +15%、鱼雷伤害减免 +20%。",
    ]),
    35: ([
        "Modern carriers: +20% surface detection, +20% sub detection.",
        "Modern carriers: +10% naval speed, -25% naval weather penalty.",
        "Modern carriers: +10% light-gun hit chance, +15% light attack, +15% light armor piercing.",
    ], [
        "现代航母：水面探测 +20%、潜艇探测 +20%。",
        "现代航母：航速 +10%、海况惩罚 -25%。",
        "现代航母：轻型炮命中 +10%、轻型炮攻击 +15%、轻型炮穿甲 +15%。",
    ]),
    36: ([
        "Modern carriers: +15% armor, +10% max strength.",
        "Modern carriers: +25% anti-air attack, +7% reliability.",
        "Modern carriers: +15% enemy torpedo critical chance, +20% torpedo damage reduction.",
    ], [
        "现代航母：装甲 +15%、最大船体强度 +10%。",
        "现代航母：防空攻击 +25%、可靠性 +7%。",
        "现代航母：敌方鱼雷暴击率 +15%、鱼雷伤害减免 +20%。",
    ]),
    37: ([
        "Nuclear missile submarines: -5% sub visibility, +2% surface detection, +5% cost.",
        "No bonus; a compromise line with no equipment changes.",
        "Nuclear missile submarines: +2% max strength, -20% naval weather penalty, +5% cost.",
    ], [
        "核导弹潜艇：潜艇可见度 -5%、水面探测 +2%、造价 +5%。",
        "不获得奖励；折中线不改变装备数值。",
        "核导弹潜艇：最大船体强度 +2%、海况惩罚 -20%、造价 +5%。",
    ]),
    38: ([
        "Nuclear submarines: -10% cost, -5% reliability, +10% sub visibility, -10% naval range.",
        "No bonus; a compromise line with no equipment changes.",
        "Nuclear submarines: +10% cost, +10% max strength, +5% reliability, -5% sub visibility.",
    ], [
        "核潜艇：造价 -10%、可靠性 -5%、潜艇可见度 +10%、航程 -10%。",
        "不获得奖励；折中线不改变装备数值。",
        "核潜艇：造价 +10%、最大船体强度 +10%、可靠性 +5%、潜艇可见度 -5%。",
    ]),
    39: ([
        "Rocket submarines: +10% naval range, +5% sub visibility, +7% cost.",
        "Rocket submarines: +3% reliability.",
        "Rocket submarines: -5% sub visibility, -5% naval range, +10% cost.",
    ], [
        "导弹潜艇：航程 +10%、潜艇可见度 +5%、造价 +7%。",
        "导弹潜艇：可靠性 +3%。",
        "导弹潜艇：潜艇可见度 -5%、航程 -5%、造价 +10%。",
    ]),
    40: ([
        "Submarine carriers: +10% naval range, +5% sub visibility.",
        "Submarine carriers: +5% max strength, -10% naval weather penalty.",
        "Submarine carriers: -10% sub visibility.",
    ], [
        "潜水母舰：航程 +10%、潜艇可见度 +5%。",
        "潜水母舰：最大船体强度 +5%、海况惩罚 -10%。",
        "潜水母舰：潜艇可见度 -10%。",
    ]),
    41: ([
        "Super-heavy battleships: +15% heavy-gun hit chance, +15% heavy attack, +10% heavy armor piercing.",
        "Super-heavy battleships: +10% naval speed, +15% surface detection, -5% surface visibility.",
        "Super-heavy battleships: +10% light-gun hit chance, +10% light attack, +10% light armor piercing.",
    ], [
        "超级战列舰：重炮命中 +15%、重炮攻击 +15%、重炮穿甲 +10%。",
        "超级战列舰：航速 +10%、水面探测 +15%、水面可见度 -5%。",
        "超级战列舰：轻型炮命中 +10%、轻型炮攻击 +10%、轻型炮穿甲 +10%。",
    ]),
    42: ([
        "Super-heavy battleships: +10% armor, +10% max strength.",
        "Super-heavy battleships: +25% anti-air attack, +5% reliability.",
        "Super-heavy battleships: +15% enemy torpedo critical chance, +15% torpedo damage reduction.",
    ], [
        "超级战列舰：装甲 +10%、最大船体强度 +10%。",
        "超级战列舰：防空攻击 +25%、可靠性 +5%。",
        "超级战列舰：敌方鱼雷暴击率 +15%、鱼雷伤害减免 +15%。",
    ]),
    43: ([
        "Grants the support-ship pick A technology.",
        "Grants the support-ship pick B technology.",
        "Grants the support-ship pick C technology.",
    ], [
        "解锁支援船·支援方案 A 科技。",
        "解锁支援船·支援方案 B 科技。",
        "解锁支援船·支援方案 C 科技。",
    ]),
    44: ([
        "Grants the naval repair-ship pick A technology.",
        "Grants the naval repair-ship pick B technology.",
        "Grants the naval repair-ship pick C technology.",
    ], [
        "解锁海军维修船·方案 A 科技。",
        "解锁海军维修船·方案 B 科技。",
        "解锁海军维修船·方案 C 科技。",
    ]),
    45: ([
        "Grants the underway-replenishment pick A technology.",
        "No bonus; a compromise line with no technology granted.",
        "Grants the underway-replenishment pick B technology.",
    ], [
        "解锁补给船·方案 A 科技。",
        "不获得奖励；折中线不授予科技。",
        "解锁补给船·方案 B 科技。",
    ]),
    46: ([
        "No bonus; gaseous separation costs nothing but grants nothing.",
        "Grants centrifugal isotope-separation technology; receiving the idea special_project_consumer_costs_high for 365 days (higher supply consumption).",
    ], [
        "不获得奖励；气体扩散法无成本、无额外收益。",
        "解锁离心法同位素分离科技；同时获得“特殊项目消耗高涨”国家精神 365 天（特殊项目消耗增加）。",
    ]),
    47: ([
        "No bonus; the reactor test results are classified.",
        "Public reveal: +10% ruling-party popularity, +100 political power, sets global nuclear-reactor-tested flags, and grants other countries a project bonus on the nuclear reactor.",
    ], [
        "不获得奖励；反应堆测试结果保密处理。",
        "向公众公开：执政党支持率 +10%、政治点 +100、设置全球反应堆测试完成标志，并向其他获得原子能科技的国家提供核反应堆项目加成。",
    ]),
}

GROUP_DESC_EN = "Choose the mutually exclusive prototype-reward bonus."
GROUP_DESC_ZH = "请选择互斥的原型产物奖励。"
NO_OP_TT_EN = "No effect — this option awards nothing."
NO_OP_TT_ZH = "无实际效果——该选项不授予任何奖励。"
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
        tt_en, tt_zh = GROUP_TT.get(eid, ([], []))
        for index, (en_opt, zh_opt) in enumerate(zip(opts_en, opts_zh)):
            en_rows.append(f" PRC_OCS.{eid}.{letter}:0 \"{en_opt}\"")
            zh_rows.append(f" PRC_OCS.{eid}.{letter}:0 \"{zh_opt}\"")
            te = tt_en[index] if index < len(tt_en) else NO_OP_TT_EN
            tz = tt_zh[index] if index < len(tt_zh) else NO_OP_TT_ZH
            en_rows.append(f" PRC_OCS.{eid}.{letter}_tt:0 \"{te}\"")
            zh_rows.append(f" PRC_OCS.{eid}.{letter}_tt:0 \"{tz}\"")
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