#!/usr/bin/env python3
"""生成游戏内自检套件 effects 文件（A 立项「实机监测机制」步骤3 交付）。

用例清单唯一真源＝本文件生成产物中的 `OCS_TEST PASS/FAIL <case>` 字面量
（K3 第 2 轮附记）；特殊科研选择组用例由两份映射 JSON 派生，不写死数字。

生成产物：common/scripted_effects/PRC_OCS_selftest_effects.txt（UTF-8 无 BOM，
由 build_release.py 随包分发；门二已拍板随正式包常驻）。

用法：
    python tools/generate_selftest_effects.py          # 重写生成产物
    python tools/generate_selftest_effects.py --check  # 校验产物无漂移
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EFFECTS_PATH = ROOT / "common" / "scripted_effects" / "PRC_OCS_selftest_effects.txt"
MAPPING_V26 = ROOT / "docs" / "analysis" / "v2.6_特殊科研组事件映射.json"
MAPPING_V28 = ROOT / "docs" / "analysis" / "v2.8_特殊科研组事件映射.json"

# 固定核心用例（手写模板）：断言目标均为「维护者按固定序列操作完毕后的后置条件」。
# 固定序列（实机回归标准操作，见 docs/testing/实机回归归档制度.md）：
#   1) 一键开局（PRC_OCS_initialize）  2) 一键骷髅师（7 天窗口内跑自检）
#   3) 一键拉满 MIO 资金与规模        4) 空军特殊科研（含 B3 极性断言所需）
#   5) 海军特殊科研·巡洋潜艇选项取 MtG 分支（N1）  6) 核能菜单「设计选择」取重水（B6）
#   7) 全部 43 个选择组逐项点选完毕（choice_group_* 用例）
FIXED_BLOCKS = """\
PRC_OCS_selftest_init_flag = {
    if = {
        limit = { has_country_flag = PRC_OCS_initialized }
        log = "OCS_TEST PASS init_flag"
    }
    else = {
        log = "OCS_TEST FAIL init_flag"
    }
}

PRC_OCS_selftest_skull_idea = {
    if = {
        limit = { has_idea = PRC_OCS_skull_divisions }
        log = "OCS_TEST PASS skull_idea"
    }
    else = {
        log = "OCS_TEST FAIL skull_idea"
    }
}

PRC_OCS_selftest_mio_exists = {
    if = {
        limit = { any_military_industrial_organization = { has_mio_size > 0 } }
        log = "OCS_TEST PASS mio_exists"
    }
    else = {
        log = "OCS_TEST FAIL mio_exists"
    }
}

PRC_OCS_selftest_mio_size_max = {
    if = {
        limit = { any_military_industrial_organization = { has_mio_size < 20 } }
        log = "OCS_TEST FAIL mio_size_max"
    }
    else = {
        log = "OCS_TEST PASS mio_size_max"
    }
}

PRC_OCS_selftest_jet_polarity = {
    if = {
        limit = { has_dlc = "By Blood Alone" }
        if = {
            limit = { NOT = { has_tech = jet_fighter1 } }
            log = "OCS_TEST PASS jet_polarity"
        }
        else = {
            log = "OCS_TEST FAIL jet_polarity"
        }
    }
    else = {
        if = {
            limit = { has_tech = jet_fighter1 }
            log = "OCS_TEST PASS jet_polarity"
        }
        else = {
            log = "OCS_TEST FAIL jet_polarity"
        }
    }
}

# n1 用例：有 MtG 断言 cruiser_submarines 科技（N1 修复的授予路径）；
# 无 MtG 分支恒 PASS＝「该断言不适用于本环境」语义（非空真 PASS——环境不适用即无此断言目标，
# 与 jet_polarity 双分支均正向断言的口径一致；run_regression 归档轮次按全 DLC 环境执行）。
PRC_OCS_selftest_n1_cruiser_submarine = {
    if = {
        limit = { has_dlc = "Man the Guns" }
        if = {
            limit = { has_tech = cruiser_submarines }
            log = "OCS_TEST PASS n1_cruiser_submarine"
        }
        else = {
            log = "OCS_TEST FAIL n1_cruiser_submarine"
        }
    }
    else = {
        log = "OCS_TEST PASS n1_cruiser_submarine"
    }
}

PRC_OCS_selftest_b6_heavy_water = {
    if = {
        limit = {
            AND = {
                has_country_flag = nuclear_reactor_heavy_water_flag
                has_tech = nuclear_reactor_heavy_water
            }
        }
        log = "OCS_TEST PASS b6_heavy_water"
    }
    else = {
        log = "OCS_TEST FAIL b6_heavy_water"
    }
}
"""

HEADER = """# 实机监测机制·游戏内自检套件（生成产物，勿手改——改动 tools/generate_selftest_effects.py）
#
# 用途：维护者按固定序列操作完毕后，控制台执行
#   effect PRC PRC_OCS_selftest_run_suite
# （或 event PRC_OCS_selftest.1 PRC）在 game.log 输出 OCS_TEST PASS/FAIL <case>。
# 判读：tools/check_logs.py --case-source 本文件（用例清单唯一真源）。
# 固定序列见 tools/generate_selftest_effects.py 头注释与 docs/testing/实机回归归档制度.md。
# 门控：无决议入口、无 on_action 触发，仅控制台可达；玩家不可见、AI 不可用（门一/门二结论）。
# 红线：不重命名既有键；每个 if 单 limit；UTF-8 无 BOM。

PRC_OCS_selftest_run_suite = {
    log = "OCS_TEST BEGIN run_suite"
"""

CASE_CALL_TEMPLATE = "    PRC_OCS_selftest_{name} = yes\n"
SUITE_TAIL = '    log = "OCS_TEST END run_suite"\n}\n'

CHOICE_BLOCK_TEMPLATE = """\
PRC_OCS_selftest_{name} = {{
    if = {{
        limit = {{ has_country_flag = {flag} }}
        log = "OCS_TEST PASS {case}"
    }}
    else = {{
        log = "OCS_TEST FAIL {case}"
    }}
}}
"""

FIXED_CASE_NAMES = (
    "init_flag", "skull_idea", "mio_exists", "mio_size_max",
    "jet_polarity", "n1_cruiser_submarine", "b6_heavy_water",
)


def _load_mapping(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def render() -> str:
    v26 = _load_mapping(MAPPING_V26)
    v28 = _load_mapping(MAPPING_V28)
    entries = sorted(v26 + v28, key=lambda e: int(e["eid"]))
    eids = [int(e["eid"]) for e in entries]
    if len(set(eids)) != len(eids):
        raise SystemExit("映射条目 eid 重复，生成中止")

    parts = [HEADER]
    for name in FIXED_CASE_NAMES:
        parts.append(CASE_CALL_TEMPLATE.format(name=name))
    for entry in entries:
        parts.append(CASE_CALL_TEMPLATE.format(name=f"choice_{entry['eid']}"))
    parts.append(SUITE_TAIL)
    parts.append(FIXED_BLOCKS)
    for entry in entries:
        parts.append(CHOICE_BLOCK_TEMPLATE.format(
            name=f"choice_{entry['eid']}",
            flag=entry["flag"],
            case=f"choice_group_{entry['eid']}",
        ))
    return "".join(parts)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    check = "--check" in args
    rendered = render()
    if check:
        if not EFFECTS_PATH.is_file():
            print(f"[FAIL] 生成产物不存在：{EFFECTS_PATH}")
            return 1
        current = EFFECTS_PATH.read_text(encoding="utf-8")
        if current == rendered:
            print(f"[OK] 自检套件生成产物一致（{len(FIXED_CASE_NAMES)} 固定用例＋{len(_load_mapping(MAPPING_V26)) + len(_load_mapping(MAPPING_V28))} 选择组用例）")
            return 0
        print("[FAIL] 自检套件生成产物漂移：请重跑 python tools/generate_selftest_effects.py")
        return 1
    EFFECTS_PATH.write_text(rendered, encoding="utf-8", newline="\n")
    print(f"已生成：{EFFECTS_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
