"""Post-process generated choose-your-bonus events (idempotent).

Reads docs/analysis/v2.6_特殊科研组事件映射.json (groups 22-47) and
docs/analysis/v2.8_特殊科研组事件映射.json (groups 54-69) produced by
generate_special_project_choice_events.py, then:

  1. Appends the five dispatch menus (48 land, 49 nuclear, 50 air, 51 naval,
     52 rocket) to events/PRC_OCS_choice_events_more.txt.
  2. Rebuilds the generated bilingual localisation block (group events 22-47
     and 54-69, and menus 48-52).

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
MAPPING_V28 = ROOT / "docs" / "analysis" / "v2.8_特殊科研组事件映射.json"
LOC_EN = ROOT / "localisation" / "english" / "PRC_OCS_l_english.yml"
LOC_ZH = ROOT / "localisation" / "simp_chinese" / "PRC_OCS_l_simp_chinese.yml"

EVENTS_MARKER = "# === v2.6/v2.8 dispatch menus (48-52) appended by finish_choice_events.py ==="

# Per-group event data: eid -> (title_en, title_zh, menu_label_en, menu_label_zh,
#                               [option labels en], [option labels zh])
GROUP_INFO = {
    22: ('Earthshaker Bomb Prototype Focus', '地震炸弹原型方向', 'Earthshaker Bomb', '地震炸弹',
         ['Precision is the Key', 'Destructive Power', 'Why Not Both?'],
         ['精准是关键', '破坏力', '为何不全都要？']),
    23: ('Helicopter Prototype Focus', '直升机原型方向', 'Helicopter', '直升机',
         ['Speed and Maneuverability', 'General Safety Precautions', 'Increased Armor'],
         ['速度与机动性', '普遍安全措施', '增强的装甲']),
    24: ('Intercontinental Bomber Prototype Focus', '洲际轰炸机原型方向', 'Intercontinental Bomber', '洲际轰炸机',
         ['Small Improvements', 'Greater Payload', 'Greater Protection'],
         ['小幅改进', '更大载荷', '更强防护']),
    25: ('Mothership Aircraft Prototype Focus', '空天母舰原型方向', 'Mothership Aircraft', '空天母舰',
         ['Agility and Speed', 'Safety and Reliability', 'Durability and Stronger Guns'],
         ['敏捷和速度', '安全和可靠性', '耐用性与更强火力']),
    26: ('Stronghold Network — Concrete Reinforcement (I)', '要塞网络·混凝土加固（一）', 'Concrete Reinforcement (I)', '混凝土加固（一）',
         ['Apply and Document Discovery', 'Use in Current Project'],
         ['应用并记录发现', '在当前项目中使用']),
    27: ('Stronghold Network — Concrete Reinforcement (II)', '要塞网络·混凝土加固（二）', 'Concrete Reinforcement (II)', '混凝土加固（二）',
         ['Apply and Document Discovery', 'Use in Current Project'],
         ['应用并记录发现', '在当前项目中使用']),
    28: ('Stronghold Network — Communication Overhaul', '要塞网络·通信系统改造', 'Communication Overhaul', '通信系统改造',
         ['Standardize', 'Further Study'],
         ['标准化', '深入研究']),
    29: ('Escort Carrier — Design A', '护航航母·方案A', 'Escort Carrier — Design A', '护航航母·方案A',
         ['Operational Range', 'Stronger Hull', 'Higher Speed'],
         ['行动范围', '加强船体', '更高速度']),
    30: ('Escort Carrier — Design B', '护航航母·方案B', 'Escort Carrier — Design B', '护航航母·方案B',
         ['Submarines', 'No preferences', 'Surface Ships'],
         ['潜艇', '无偏好', '水面舰艇']),
    31: ('Ice Carrier Prototype Focus', '冰航母原型方向', 'Ice Carrier', '冰航母',
         ['Forces of Nature', 'Enemy Forces'],
         ['自然力量', '敌方军队']),
    32: ('Midget Submarine Prototype Focus', '袖珍潜艇原型方向', 'Midget Submarine', '袖珍潜艇',
         ['Bit Stealthier', 'Bit Less Prone to Explode', 'Bit Longer Range'],
         ['略微增加隐匿性', '略微降低爆炸风险', '略微增加航程']),
    33: ('Modern Battleship — Design A', '现代战列舰·方案A', 'Modern Battleship — Design A', '现代战列舰·方案A',
         ['Raw Firepower', 'Maneuverability', 'Precision'],
         ['火力', '机动', '精准']),
    34: ('Modern Battleship — Design B', '现代战列舰·方案B', 'Modern Battleship — Design B', '现代战列舰·方案B',
         ['Structure', 'Anti-Air', 'Torpedo Protection'],
         ['结构', '防空', '鱼雷防护']),
    35: ('Modern Carrier — Design A', '现代航母·方案A', 'Modern Carrier — Design A', '现代航母·方案A',
         ['Awareness', 'Speed and Weatherproof', 'Light Ship Deterrence'],
         ['预警能力', '速度与天气适应能力', '轻型舰艇威慑力']),
    36: ('Modern Carrier — Design B', '现代航母·方案B', 'Modern Carrier — Design B', '现代航母·方案B',
         ['Enemy Artillery', 'Enemy Aircraft', 'Enemy Torpedoes'],
         ['敌方火炮', '敌方飞行器', '敌方鱼雷']),
    37: ('Nuclear Missile Submarine Prototype Focus', '核导弹潜艇原型方向', 'Nuclear Missile Submarine', '核导弹潜艇',
         ['Lay Low', 'Remain Calm', 'Endure Storm'],
         ['保持低调', '保持冷静', '忍受风暴']),
    38: ('Nuclear Submarine Prototype Focus', '核潜艇原型方向', 'Nuclear Submarine', '核潜艇',
         ['Cut Corners', 'Current Plans', 'Highest Quality'],
         ['削减成本', '保持现有设计', '追求最高质量']),
    39: ('Rocket Launching Submarine Prototype Focus', '导弹潜艇原型方向', 'Rocket Launching Submarine', '导弹潜艇',
         ['Range', 'Reliability', 'Stealth'],
         ['射程', '可靠性', '隐匿性']),
    40: ('Submarine Carrier Prototype Focus', '潜水母舰原型方向', 'Submarine Carrier', '潜水母舰',
         ['Extended Range', 'Reinforced Structure', 'Reduced Visibility'],
         ['延长航程', '加固结构', '低可见度']),
    41: ('Super Heavy Battleship — Design A', '超级战列舰·方案A', 'Super Heavy Battleship — Design A', '超级战列舰·方案A',
         ['Heavy Guns', 'Speed', 'Light Guns'],
         ['重炮', '速度', '轻炮']),
    42: ('Super Heavy Battleship — Design B', '超级战列舰·方案B', 'Super Heavy Battleship — Design B', '超级战列舰·方案B',
         ['Reinforced Armor and Hull', 'Anti-Air Artillery', 'Anti-Torpedo Measures'],
         ['加强装甲和船体', '防空火炮', '反鱼雷措施']),
    43: ('Support Ships — Support Focus', '支援船·支援方案', 'Support Ships — Support Focus', '支援船·支援方案',
         ['Needs of the few', 'Find the balance', 'Needs of the many'],
         ['需求少量', '寻找平衡', '需求大量']),
    44: ('Support Ships — Repair Focus', '支援船·维修方案', 'Support Ships — Repair Focus', '支援船·维修方案',
         ['Wider Coverage', 'Find the balance', 'Concentrated Efforts'],
         ['大范围覆盖', '寻找平衡', '集中使用']),
    45: ('Underway Replenishment Prototype Focus', '补给船原型方向', 'Underway Replenishment', '补给船',
         ['Longer Range', 'Find a Balance', 'Lower Convoy Usage'],
         ['更长的航程', '寻找平衡', '减少运输船消耗']),
    46: ('Nuclear Isotope Separation Prototype Focus', '核同位素分离原型方向', 'Isotope Separation', '同位素分离',
         ['Gaseous is a proven technique.', 'Centrifuges will be more efficient in the long-run.'],
         ['气体扩散法是一种经过验证的技术。', '离心分离法从长远来看效率更高。']),
    47: ('Nuclear Reactor Tested Reward', '核反应堆测试完成奖励', 'Reactor Tested Reward', '反应堆测试奖励',
         ['Keep the information classified for now', 'Celebrate the achievement publicly'],
         ['暂时保留这些信息加密', '公开庆祝这一成就']),
    54: ('Land Cruiser — Chassis Prototype Focus', '陆地巡洋舰·底盘原型方向', 'Land Cruiser — Chassis', '陆地巡洋舰·底盘',
         ['Redesign the Chassis Entirely', 'Reinforce the Chassis', 'Use Lighter Materials'],
         ['完全重新设计底盘', '加固底盘', '使用轻量化材料']),
    55: ('Land Cruiser — Engine Prototype Focus', '陆地巡洋舰·发动机原型方向', 'Land Cruiser — Engine', '陆地巡洋舰·发动机',
         ['Leave as Is', 'Modify Current Engine', 'Develop a New Engine'],
         ['保持现状', '调整当前引擎', '研发新引擎']),
    56: ('Land Cruiser — Turret Prototype Focus', '陆地巡洋舰·炮塔原型方向', 'Land Cruiser — Turret', '陆地巡洋舰·炮塔',
         ['Keep Original Design', 'Simplify Turret Design', 'Redesign Turret Mechanism'],
         ['保留原始设计', '简化炮塔设计', '重新设计炮塔结构']),
    57: ('Land Cruiser — Track Prototype Focus', '陆地巡洋舰·履带原型方向', 'Land Cruiser — Track', '陆地巡洋舰·履带',
         ['Proceed with Current Tracks', 'Reduce Armor Plating', 'Reinforce the Track System'],
         ['继续使用当前履带系统', '减少装甲覆层', '加固履带系统']),
    58: ('Land Cruiser — Communication Prototype Focus', '陆地巡洋舰·通信系统原型方向', 'Land Cruiser — Communication', '陆地巡洋舰·通信系统',
         ['Leave Current System', 'Install New Advanced System', 'Redesigned Internal Layout'],
         ['保持当前系统', '加装新的高级系统', '重新设计的内部布局']),
    59: ('Land Cruiser — Assembly Prototype Focus', '陆地巡洋舰·装配原型方向', 'Land Cruiser — Assembly', '陆地巡洋舰·装配',
         ['Across All Assembly Stages', 'Only to Key Components'],
         ['应用于所有组装阶段', '仅应用于关键部件']),
    60: ('Land Cruiser — Suspension Prototype Focus', '陆地巡洋舰·悬挂原型方向', 'Land Cruiser — Suspension', '陆地巡洋舰·悬挂',
         ['Full Hydropneumatic Suspension', 'Limit to Rear Units'],
         ['全液气悬挂', '仅限于后部部件']),
    61: ('Land Cruiser — Ammunition Prototype Focus', '陆地巡洋舰·弹药原型方向', 'Land Cruiser — Ammunition', '陆地巡洋舰·弹药',
         ['Maintain Current System', 'Use a Simplified Version', 'Adopt the New Storage System'],
         ['保持现有系统', '使用简化版本', '采用新的弹药存储系统']),
    62: ('Super Heavy Howitzer — Prototype Focus', '超重型榴弹炮·原型侧重', 'Super Heavy Howitzer', '超重型榴弹炮',
         ['Keep Balance', 'Focus on Firepower', 'Focus on Fast Production'],
         ['保持平衡', '专注火力', '专注快速生产']),
    63: ('Self-Propelled Super Heavy Howitzer — Prototype Focus', '自行超重型榴弹炮·原型侧重', 'Self-Propelled Super Heavy Howitzer', '自行超重型榴弹炮',
         ['Keep Balance', 'Focus on Firepower', 'Focus on Fast Production'],
         ['保持平衡', '专注火力', '专注快速生产']),
    64: ('Nuclear Torpedo Prototype Focus', '核鱼雷原型方向', 'Nuclear Torpedo', '核鱼雷',
         ['Powerful Warheads', 'Safer Storages'],
         ['强大的弹头', '更安全的鱼雷储存']),
    65: ('AIP Engine Prototype Focus', 'AIP 发动机原型方向', 'AIP Engine', 'AIP 发动机',
         ['Quieter Engines', 'Faster Engines', 'Less Fuel-Consuming Engines'],
         ['低噪音引擎', '高速引擎', '低油耗引擎']),
    66: ('Anechoic Tiles Prototype Focus', '消声瓦原型方向', 'Anechoic Tiles', '消声瓦',
         ['Aggressive Patrol Patterns', 'Reduced Acoustic Signature', 'Reduced Hull Costs'],
         ['攻击性巡逻模式', '减少声学特征', '降低船体成本']),
    67: ('Proximity Fuze Prototype Focus', '近炸引信原型方向', 'Proximity Fuze', '近炸引信',
         ['Adjust Ammo Supplies', 'Retain Current Ammo Supply'],
         ['调整弹药供应', '保持当前弹药供应']),
    68: ('Flying Bomb Design Choice', '飞行炸弹设计选择', 'Flying Bomb Design', '飞行炸弹设计',
         ['Balanced', 'Range', 'Payload'],
         ['平衡', '射程', '载荷']),
    69: ('Ballistic Missile Guidance System', '弹道导弹制导系统', 'Ballistic Missile Guidance', '弹道导弹制导',
         ['Mechanical is reliable.', 'Radio is the future!'],
         ['机械系统更可靠', '无线电是未来！']),
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
    52: ("rocket", "Rocket Special Projects — Remaining Prototype Bonuses",
         "火箭特殊科研·剩余原型奖励选择", "PRC_OCS_rocket_special_project_choices_done"),
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
    54: ([
        "Land cruisers: +5% reliability.",
        "Land cruisers: -3% reliability, +5% armor.",
        "Land cruisers: -5% armor.",
    ], [
        "陆地巡洋舰：可靠性 +5%。",
        "陆地巡洋舰：可靠性 -3%、装甲 +5%。",
        "陆地巡洋舰：装甲 -5%。",
    ]),
    55: ([
        "No effect — this option awards nothing.",
        "Land cruisers: +5% max speed.",
        "Land cruisers: +5% reliability, +5% max speed.",
    ], [
        "无实际效果——该选项不授予任何奖励。",
        "陆地巡洋舰：最大速度 +5%。",
        "陆地巡洋舰：可靠性 +5%、最大速度 +5%。",
    ]),
    56: ([
        "No effect — this option awards nothing.",
        "Land cruisers: -3% breakthrough, -2% cost.",
        "Land cruisers: +3% breakthrough, +3% max speed, +5% cost.",
    ], [
        "无实际效果——该选项不授予任何奖励。",
        "陆地巡洋舰：突破 -3%、造价 -2%。",
        "陆地巡洋舰：突破 +3%、最大速度 +3%、造价 +5%。",
    ]),
    57: ([
        "No effect — this option awards nothing.",
        "Land cruisers: -3% armor.",
        "Land cruisers: +5% reliability, +3% cost.",
    ], [
        "无实际效果——该选项不授予任何奖励。",
        "陆地巡洋舰：装甲 -3%。",
        "陆地巡洋舰：可靠性 +5%、造价 +3%。",
    ]),
    58: ([
        "No effect — this option awards nothing.",
        "Land cruisers: +3% breakthrough.",
        "Land cruisers: +3% breakthrough, +3% defense, +2% cost.",
    ], [
        "无实际效果——该选项不授予任何奖励。",
        "陆地巡洋舰：突破 +3%。",
        "陆地巡洋舰：突破 +3%、防御 +3%、造价 +2%。",
    ]),
    59: ([
        "Land cruisers: +7% reliability, +5% cost.",
        "Land cruisers: +3% reliability.",
    ], [
        "陆地巡洋舰：可靠性 +7%、造价 +5%。",
        "陆地巡洋舰：可靠性 +3%。",
    ]),
    60: ([
        "Land cruisers: +3% max speed, +3% reliability, +5% cost.",
        "Land cruisers: +3% reliability.",
    ], [
        "陆地巡洋舰：最大速度 +3%、可靠性 +3%、造价 +5%。",
        "陆地巡洋舰：可靠性 +3%。",
    ]),
    61: ([
        "No effect — this option awards nothing.",
        "Land cruisers: +3% breakthrough, +2% cost.",
        "Land cruisers: +5% breakthrough, +3% reliability, +5% cost.",
    ], [
        "无实际效果——该选项不授予任何奖励。",
        "陆地巡洋舰：突破 +3%、造价 +2%。",
        "陆地巡洋舰：突破 +5%、可靠性 +3%、造价 +5%。",
    ]),
    62: ([
        "No effect — this option awards nothing.",
        "Super-heavy howitzers: +10% cost, +5% soft attack, +10% collateral damage.",
        "Super-heavy howitzers: -15% cost, -5% soft attack, -10% collateral damage.",
    ], [
        "无实际效果——该选项不授予任何奖励。",
        "超重型榴弹炮：造价 +10%、软攻 +5%、附带损伤 +10%。",
        "超重型榴弹炮：造价 -15%、软攻 -5%、附带损伤 -10%。",
    ]),
    63: ([
        "No effect — this option awards nothing.",
        "Self-propelled super-heavy howitzers: +10% cost, +5% soft attack, +10% collateral damage.",
        "Self-propelled super-heavy howitzers: -15% cost, -5% soft attack, -10% collateral damage.",
    ], [
        "无实际效果——该选项不授予任何奖励。",
        "自行超重型榴弹炮：造价 +10%、软攻 +5%、附带损伤 +10%。",
        "自行超重型榴弹炮：造价 -15%、软攻 -5%、附带损伤 -10%。",
    ]),
    64: ([
        "Submarines: +2% torpedo hit chance, +10% torpedo attack, -10% reliability.",
        "Submarines: +10% reliability, +10% cost.",
    ], [
        "潜艇：鱼雷命中 +2%、鱼雷攻击 +10%、可靠性 -10%。",
        "潜艇：可靠性 +10%、造价 +10%。",
    ]),
    65: ([
        "Submarines: -5% sub visibility, +10% fuel consumption.",
        "Submarines: +10% naval speed, +10% fuel consumption.",
        "Submarines: -5% fuel consumption.",
    ], [
        "潜艇：潜艇可见度 -5%、油耗 +10%。",
        "潜艇：航速 +10%、油耗 +10%。",
        "潜艇：油耗 -5%。",
    ]),
    66: ([
        "Submarines: +5% cost, +10% surface detection.",
        "Submarines: +10% cost, -5% sub visibility.",
        "Submarines: -5% cost.",
    ], [
        "潜艇：造价 +5%、水面探测 +10%。",
        "潜艇：造价 +10%、潜艇可见度 -5%。",
        "潜艇：造价 -5%。",
    ]),
    67: ([
        "Anti-air equipment: -5% cost.",
        "Anti-air equipment: +15% air attack, +5% cost.",
    ], [
        "防空装备：造价 -5%。",
        "防空装备：对空攻击 +15%、造价 +5%。",
    ]),
    68: ([
        "No effect — this option awards nothing.",
        "Guided missiles: +5% max speed, +10% range, -5% bombing.",
        "Guided missiles: +15% bombing, -5% range.",
    ], [
        "无实际效果——该选项不授予任何奖励。",
        "制导导弹：最大速度 +5%、航程 +10%、轰炸 -5%。",
        "制导导弹：轰炸 +15%、航程 -5%。",
    ]),
    69: ([
        "Ballistic missiles: -10% cost.",
        "Ballistic missiles: +5% bombing, +10% cost.",
    ], [
        "弹道导弹：造价 -10%。",
        "弹道导弹：轰炸 +5%、造价 +10%。",
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
    """Menu option letter. 'd' (desc), 't' (title) and 'z' (tail option) are
    reserved keys, so they are skipped."""
    letters = "abcefghijklmnopqrsuvwxy"  # a-z minus d, t, z
    return letters[index]


def _mapping() -> list[dict]:
    v26 = json.loads(MAPPING.read_text(encoding="utf-8"))
    v28 = json.loads(MAPPING_V28.read_text(encoding="utf-8"))
    return v26 + v28


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
    for menu_id in (48, 49, 50, 51, 52):
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
    for menu_id in (48, 49, 50, 51, 52):
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

    print("Done: menus 48-52 appended, localisation block 22-47 + 54-69 regenerated.")


if __name__ == "__main__":
    main()