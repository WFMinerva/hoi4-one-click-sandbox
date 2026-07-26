#!/usr/bin/env python3
"""Repository-local static checks for One-Click Sandbox Start."""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MOD_DIR_NAME = "OCS_one_click_sandbox_start_v2_0"
OUTER_MOD = ROOT / "packaging" / f"{MOD_DIR_NAME}.mod"

REQUIRED_FILES = (
    ROOT / "LICENSE",
    ROOT / "NOTICE.md",
    ROOT / "descriptor.mod",
    ROOT / "thumbnail.png",
    ROOT / "common" / "decisions" / "PRC_OCS_decisions.txt",
    ROOT / "common" / "decisions" / "categories" / "PRC_OCS_categories.txt",
    ROOT / "common" / "scripted_effects" / "PRC_OCS_effects.txt",
    ROOT / "events" / "PRC_OCS_events.txt",
    ROOT / "localisation" / "english" / "PRC_OCS_l_english.yml",
    ROOT / "localisation" / "simp_chinese" / "PRC_OCS_l_simp_chinese.yml",
    OUTER_MOD,
)

# v2.0 — Script files are discovered automatically so split effect files
# are always included. Core script directories plus events/ are scanned.
SCRIPT_DIRS = (
    ROOT / "common",
    ROOT / "events",
)

LOCALISATION_FILES = (
    ROOT / "localisation" / "english" / "PRC_OCS_l_english.yml",
    ROOT / "localisation" / "simp_chinese" / "PRC_OCS_l_simp_chinese.yml",
)


def collect_script_files() -> list[Path]:
    """Gather every .txt file under SCRIPT_DIRS."""
    files: list[Path] = []
    for directory in SCRIPT_DIRS:
        if directory.is_dir():
            files.extend(sorted(directory.rglob("*.txt")))
    return files


def read_utf8(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def descriptor_value(text: str, key: str) -> str | None:
    match = re.search(rf'(?m)^\s*{re.escape(key)}\s*=\s*"([^"]+)"', text)
    return match.group(1) if match else None


def strip_comments_and_strings(text: str) -> str:
    output: list[str] = []
    in_string = False
    escaped = False
    for line in text.splitlines():
        for char in line:
            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
                continue
            if char == '"':
                in_string = True
            elif char == "#":
                break
            else:
                output.append(char)
        output.append("\n")
    return "".join(output)


def main() -> int:
    errors: list[str] = []
    warnings: list[str] = []

    for path in REQUIRED_FILES:
        if not path.is_file():
            errors.append(f"缺少必需文件：{path.relative_to(ROOT)}")

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    descriptor = read_utf8(ROOT / "descriptor.mod")
    outer = read_utf8(OUTER_MOD)

    for key in ("version", "name", "supported_version"):
        inside_value = descriptor_value(descriptor, key)
        outer_value = descriptor_value(outer, key)
        if inside_value != outer_value:
            errors.append(
                f"descriptor.mod 与 packaging 描述文件的 {key} 不一致："
                f"{inside_value!r} != {outer_value!r}"
            )

    expected_path = f"mod/{MOD_DIR_NAME}"
    if descriptor_value(outer, "path") != expected_path:
        errors.append(f"外部 .mod 的 path 必须为 {expected_path!r}")

    if descriptor_value(descriptor, "supported_version") != "1.19.*":
        warnings.append("supported_version 已偏离已验证基准 1.19.*")

    license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")
    if "GNU GENERAL PUBLIC LICENSE" not in license_text:
        errors.append("LICENSE 不是可识别的 GNU GPL 正文")
    if "Version 3, 29 June 2007" not in license_text:
        errors.append("LICENSE 不是 GNU GPL version 3")

    notice = read_utf8(ROOT / "NOTICE.md")
    for marker in ("HAPPYADONG", "GPL-3.0-only", "thumbnail.png", "All rights reserved"):
        if marker not in notice:
            errors.append(f"NOTICE.md 缺少许可证范围标记：{marker}")

    script_files = collect_script_files()

    for path in script_files:
        raw = path.read_bytes()
        if raw.startswith(b"\xef\xbb\xbf"):
            errors.append(
                f"{path.relative_to(ROOT)} 包含 UTF-8 BOM — 运行 python tools/fix_bom.py 修复"
            )
        try:
            text = read_utf8(path)
        except UnicodeDecodeError as exc:
            errors.append(f"{path.relative_to(ROOT)} 不是有效 UTF-8：{exc}")
            continue
        cleaned = strip_comments_and_strings(text)
        balance = 0
        for char in cleaned:
            if char == "{":
                balance += 1
            elif char == "}":
                balance -= 1
                if balance < 0:
                    break
        if balance != 0:
            errors.append(f"{path.relative_to(ROOT)} 的花括号不平衡（余额 {balance}）")

    for path in LOCALISATION_FILES:
        data = path.read_bytes()
        if not data.startswith(b"\xef\xbb\xbf"):
            errors.append(f"{path.relative_to(ROOT)} 缺少 UTF-8 BOM")
        try:
            data.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            errors.append(f"{path.relative_to(ROOT)} 不是有效 UTF-8：{exc}")

    combined_scripts = "\n".join(read_utf8(path) for path in script_files)
    required_markers = {
        "玩家限制 is_ai = no": "is_ai = no",
        "PRC 原始国家识别": "original_tag = PRC",
        "24 师创建效果": "create_unit",
        "拥有州作用域": "every_owned_state",
        "控制州限制": "is_controlled_by = ROOT",
    }
    for label, marker in required_markers.items():
        if marker not in combined_scripts:
            errors.append(f"未找到关键约束：{label}（{marker}）")

    for warning in warnings:
        print(f"WARNING: {warning}")
    for error in errors:
        print(f"ERROR: {error}")

    if errors:
        print(f"\n静态检查失败：{len(errors)} 个错误，{len(warnings)} 个警告。")
        return 1

    print(f"静态检查通过：{len(REQUIRED_FILES)} 个必需文件，{len(script_files)} 个脚本文件，{len(warnings)} 个警告。")
    return 0


if __name__ == "__main__":
    sys.exit(main())