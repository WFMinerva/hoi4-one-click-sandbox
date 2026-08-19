#!/usr/bin/env python3
"""实机日志判读工具：白名单过滤 + [OCS_TEST] 标记提取 + 版本绑定 + result.json。

用途（A 立项「实机监测机制」步骤1 交付）：把四份日志（error.log/game.log/
text.log/setup.log）的「人脑判读经验」固化为机器可执行的白名单检查，并输出
机器可读结果，供回归归档与跨轮 diff。

用法：
    python tools/check_logs.py --logs <日志目录> --round <轮次标识>
        [--case-file <用例清单文件>] [--exempt-markers] [--out <result.json>]

判定铁律（K3 第 1/4 轮定案）：
- `[OCS_TEST]` 标记数为 0 ＝ 本轮 FAIL/无效（防空真，防忘开 -debug_mode/未触发）；
- 提供 --case-file 时，标记数须等于用例清单数且全部 PASS 才算 PASS；
- 仅「标记判读豁免」（--exempt-markers）轮次例外，豁免事实写入 result.json 并
  在摘要高亮（供自检套件落地前的首轮归档使用，默认不豁免）。
- error.log/game.log/text.log 按白名单逐行过滤；未命中白名单的行按「签名」聚合
  为新错误告警。setup.log 为加载日志（每行都是正常加载记录），不做白名单过滤，
  只做存在性/加载摘要检查（PRC_OCS 行数）。
- code_revisions.log 版本绑定失败时降级为人工登记版本号（记入 result.json）。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WHITELIST_PATH = ROOT / "tools" / "log_noise_whitelist.json"

FILTERED_LOGS = ("error.log", "game.log", "text.log")
SETUP_LOG = "setup.log"
VERSION_LOG = "code_revisions.log"

MARKER_RE = re.compile(r"\[OCS_TEST\]\s+(PASS|FAIL)\s+([A-Za-z0-9_.\-]+)")
MARKER_CASE_RE = re.compile(r"\[OCS_TEST\]\s+(?:PASS|FAIL)\s+([A-Za-z0-9_.\-]+)")
TIME_PREFIX_RE = re.compile(r"^\[[^\]]*\]\[[^\]]*\]\[[^\]]*\]:\s*")
# game.log 是运行日志（大量正常行），只对「错误样」行告警；error.log/text.log 是
# 错误通道，逐行全查。实现口径记录于立项文档 A⑥ 实施记录。
ERROR_LIKE_RE = re.compile(r"\b(error|invalid|unknown|exception|failed|warning)\b", re.IGNORECASE)


def _read_lines(path: Path) -> list[str]:
    """Read a log file line by line; tolerate missing files and bad encodings."""
    if not path.is_file():
        return []
    try:
        return path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []


def load_whitelist(path: Path = WHITELIST_PATH) -> list[dict]:
    try:
        with path.open(encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"[FAIL] 白名单文件不可读或格式错误：{path}（{exc}）") from exc
    if data.get("schema_version") != 1:
        raise SystemExit(f"白名单文件 schema_version 不支持：{data.get('schema_version')}")
    return data["entries"]


def whitelist_for_log(entries: list[dict], log_name: str) -> list[dict]:
    return [e for e in entries if e.get("log") == log_name]


def _line_matches(entry: dict, line: str) -> bool:
    pattern = entry["pattern"]
    if entry.get("regex"):
        return re.search(pattern, line) is not None
    return pattern in line


def _signature(line: str) -> str:
    """Normalize a log line to a stable signature for grouping.

    去掉时间前缀，并把引擎报错的行号（line : 54 等）归一为 line : <N>，使同一
    错误类型的不同位置报告聚合为一类新签名。
    """
    sig = TIME_PREFIX_RE.sub("", line).strip()
    sig = re.sub(r"line : \d+", "line : <N>", sig)
    return sig


def filter_log(lines: list[str], entries: list[dict], mode: str = "all") -> dict:
    """Return whitelist-filtering result for one log.

    `[OCS_TEST]` 标记行不在过滤范围（由 collect_markers 单独处理），直接跳过，
    避免自检输出被误判为新错误签名。
    mode="all"：未命中白名单的行全部计为新签名（error.log/text.log 用）；
    mode="error_like"：仅「错误样」行计为新签名，正常运行行忽略（game.log 用）。
    """
    matched = 0
    unmatched: dict[str, dict] = {}
    for line in lines:
        if not line.strip():
            continue
        if MARKER_RE.search(line):
            continue
        if any(_line_matches(e, line) for e in entries):
            matched += 1
            continue
        if mode == "error_like" and not ERROR_LIKE_RE.search(line):
            continue
        sig = _signature(line)
        bucket = unmatched.setdefault(sig, {"count": 0, "sample": line[:400]})
        bucket["count"] += 1
    return {"total_lines": len(lines), "whitelisted": matched, "unmatched": unmatched}


def collect_markers(lines_by_log: dict[str, list[str]]) -> dict:
    """Extract [OCS_TEST] PASS/FAIL markers from all four logs (game.log 为主)."""
    cases: list[dict] = []
    for log_name, lines in lines_by_log.items():
        for line in lines:
            m = MARKER_RE.search(line)
            if m:
                cases.append({"log": log_name, "status": m.group(1), "case": m.group(2)})
    total = len(cases)
    distinct = len({c["case"] for c in cases})
    failures = [c for c in cases if c["status"] != "PASS"]
    return {
        "total": total,
        "distinct_cases": distinct,
        "failed": failures,
        "cases": cases,
    }


def read_case_file(path: Path | None) -> list[str] | None:
    """Read expected case ids (one per line, '#' comments allowed)."""
    if path is None:
        return None
    cases = []
    for line in _read_lines(path):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        cases.append(line)
    return cases


def read_case_source(path: Path | None) -> list[str] | None:
    """Parse case ids from a selftest effects file（用例清单唯一真源，K3 第 2 轮附记）。"""
    if path is None:
        return None
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise SystemExit(f"[FAIL] 用例源文件不可读：{path}（{exc}）") from exc
    cases = sorted(set(MARKER_CASE_RE.findall(text)))
    if not cases:
        raise SystemExit(f"用例源文件未解析到任何 [OCS_TEST] 用例：{path}")
    return cases


def read_game_version(logs_dir: Path) -> dict:
    """Bind the game build from code_revisions.log; degrade to manual note on failure."""
    path = logs_dir / VERSION_LOG
    data: dict[str, str] = {}
    for line in _read_lines(path):
        if ":" in line:
            key, _, value = line.partition(":")
            data[key.strip()] = value.strip()
    if data.get("game_hash_short"):
        return {
            "source": VERSION_LOG,
            "game_hash_short": data["game_hash_short"],
            "game_timestamp": data.get("game_timestamp", ""),
            "manual_fallback": False,
        }
    return {
        "source": "manual",
        "game_hash_short": "",
        "game_timestamp": "",
        "manual_fallback": True,
        "note": "code_revisions.log 缺失或解析失败，需人工登记游戏版本号",
    }


def summarize_setup_log(lines: list[str]) -> dict:
    """Load-summary check for setup.log (load log; every line is a normal record)."""
    ocs_lines = sum(1 for line in lines if "PRC_OCS" in line)
    return {"exists": bool(lines), "total_lines": len(lines), "prc_ocs_lines": ocs_lines}


def build_verdict(markers: dict, expected_cases: list[str] | None, exempt: bool) -> tuple[str, list[str]]:
    reasons: list[str] = []
    if markers["total"] == 0:
        if exempt:
            # 豁免轮：跳过全部标记规则（自检套件落地前的归档轮次专用；
            # 豁免事实已在 result.json 记录并高亮，防静默滥用）
            return "PASS", ["标记数 0 但本轮为「标记判读豁免」轮次（豁免事实已记录）"]
        return "INVALID", ["标记数为 0：本轮无效（可能未开 -debug_mode/未触发自检），判定铁律拦截"]
    if markers["failed"]:
        reasons.append(f"存在 FAIL 标记：{markers['failed']}")
        return "FAIL", reasons
    if expected_cases is not None:
        if markers["total"] != len(expected_cases):
            distinct = len({c["case"] for c in markers["cases"]})
            reasons.append(
                f"标记数 {markers['total']}≠用例清单数 {len(expected_cases)}"
                f"（重复 {markers['total'] - distinct} 条）：疑似重复执行/陈旧日志叠加，铁律拦截")
            return "FAIL", reasons
        expected_set = set(expected_cases)
        got = {c["case"] for c in markers["cases"]}
        if got != expected_set:
            missing = sorted(expected_set - got)
            extra = sorted(got - expected_set)
            reasons.append(f"标记集合与用例清单不一致：缺 {missing}，多 {extra}")
            return "FAIL", reasons
        reasons.append(f"标记数 {markers['total']}＝用例清单数 {len(expected_cases)} 且全 PASS")
    else:
        reasons.append(f"标记 {markers['total']} 条全 PASS（未提供用例清单，未比对清单数）")
    return "PASS", reasons


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="实机日志判读：白名单过滤＋自检标记提取＋结果 JSON")
    parser.add_argument("--logs", type=Path, required=True, help="游戏日志目录（Documents\\Paradox Interactive\\Hearts of Iron IV\\logs）")
    parser.add_argument("--round", default="", help="轮次标识（如 v2.8-test5）")
    case_group = parser.add_mutually_exclusive_group()
    case_group.add_argument("--case-file", type=Path, default=None, help="自检用例清单文件（每行一个 case id，# 注释）")
    case_group.add_argument("--case-source", type=Path, default=None, help="自检 effects 文件（解析其 [OCS_TEST] 字面量为用例清单，唯一真源）")
    parser.add_argument("--exempt-markers", action="store_true", help="标记判读豁免（自检套件落地前的轮次专用；豁免事实入 result.json）")
    parser.add_argument("--out", type=Path, default=None, help="result.json 输出路径（默认 <logs 目录>/ocs_result.json）")
    args = parser.parse_args(argv)

    logs_dir = args.logs
    if not logs_dir.is_dir():
        print(f"[FAIL] 日志目录不存在：{logs_dir}", file=sys.stderr)
        return 2

    lines_by_log = {name: _read_lines(logs_dir / name) for name in (*FILTERED_LOGS, SETUP_LOG)}
    entries = load_whitelist()

    filter_results = {}
    clean = True
    new_signatures: list[dict] = []
    # game.log 用「错误样」口径（正常运行行不算新签名）；error.log/text.log 全行过滤。
    modes = {"game.log": "error_like", "error.log": "all", "text.log": "all"}
    for log_name in FILTERED_LOGS:
        result = filter_log(lines_by_log[log_name], whitelist_for_log(entries, log_name),
                            mode=modes[log_name])
        filter_results[log_name] = result
        if result["unmatched"]:
            clean = False
            for sig, bucket in sorted(result["unmatched"].items()):
                new_signatures.append({"log": log_name, "signature": sig, "count": bucket["count"], "sample": bucket["sample"]})

    markers = collect_markers(lines_by_log)
    expected_cases = read_case_source(args.case_source)
    if expected_cases is None:
        expected_cases = read_case_file(args.case_file)
    version = read_game_version(logs_dir)
    setup = summarize_setup_log(lines_by_log[SETUP_LOG])

    verdict, reasons = build_verdict(markers, expected_cases, args.exempt_markers)
    if not clean and verdict == "PASS":
        verdict = "FAIL"
        reasons.append("日志存在白名单外的新错误签名")

    result = {
        "schema_version": 1,
        "round": args.round,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "logs_dir": str(logs_dir),
        "game_version": version,
        "whitelist": {"clean": clean, "new_signatures": new_signatures},
        "markers": {
            "exempt": args.exempt_markers,
            "expected_cases": expected_cases,
            "total": markers["total"],
            "distinct_cases": markers["distinct_cases"],
            "failed": markers["failed"],
        },
        "setup_log": setup,
        "verdict": verdict,
        "verdict_reasons": reasons,
    }

    out_path = args.out or (logs_dir / "ocs_result.json")
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    # 人类可读摘要
    print("=== 实机日志判读摘要 ===")
    print(f"轮次: {args.round or '(未指定)'}  日志目录: {logs_dir}")
    print(f"游戏版本: {version.get('game_hash_short') or '(需人工登记)'}"
          + ("" if not version.get("manual_fallback") else "  [绑定失败，降级人工登记]"))
    print(f"标记: 共 {markers['total']} 条（{markers['distinct_cases']} 个用例），FAIL {len(markers['failed'])} 条"
          + ("；[豁免] 本轮跳过 0 标记铁律" if args.exempt_markers else ""))
    if expected_cases is not None:
        case_src = args.case_source if args.case_source is not None else args.case_file
        print(f"用例清单: {len(expected_cases)} 个（来自 {case_src}）")
    print(f"白名单过滤: {'干净' if clean else '发现新错误签名 ' + str(len(new_signatures)) + ' 类'}")
    for item in new_signatures[:10]:
        print(f"  - [{item['log']}] x{item['count']} {item['signature'][:120]}")
    if not setup["exists"]:
        print("[警告] setup.log 不存在")
    else:
        print(f"setup.log: {setup['total_lines']} 行，含 PRC_OCS 加载记录 {setup['prc_ocs_lines']} 行")
    print(f"判定: {verdict}  理由: {'；'.join(reasons)}")
    print(f"结果已写入: {out_path}")
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
