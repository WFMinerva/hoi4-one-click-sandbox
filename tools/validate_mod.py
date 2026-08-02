#!/usr/bin/env python3
"""Repository-local static checks for One-Click Sandbox Start."""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
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
    ROOT / "common" / "scripted_effects" / "PRC_OCS_construction_effects.txt",
    ROOT / "common" / "scripted_effects" / "PRC_OCS_equipment_effects.txt",
    ROOT / "common" / "scripted_effects" / "PRC_OCS_military_effects.txt",
    ROOT / "common" / "scripted_effects" / "PRC_OCS_mio_effects.txt",
    ROOT / "common" / "scripted_effects" / "PRC_OCS_research_effects.txt",
    ROOT / "common" / "scripted_effects" / "PRC_OCS_special_project_effects.txt",
    ROOT / "common" / "scripted_effects" / "PRC_OCS_stockpile_effects.txt",
    ROOT / "common" / "scripted_effects" / "PRC_OCS_template_effects.txt",
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


@dataclass(frozen=True)
class Token:
    kind: str
    value: str
    line: int


@dataclass
class Block:
    assignments: list[Assignment] = field(default_factory=list)


@dataclass
class Assignment:
    key: str
    value: str | Block
    line: int


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


def check_version_metadata(version: str, errors: list[str]) -> None:
    """Keep stable-release entrypoints aligned with descriptor.mod."""
    if "test" in version.casefold():
        return

    requirements = (
        (
            ROOT / "README.md",
            (f"- 当前稳定基准：v{version}", f"v{version} 是当前稳定基准。"),
        ),
        (ROOT / "AGENTS.md", (f"当前稳定基准：**v{version}**",)),
        (ROOT / "docs" / "DEVELOPMENT.md", (f"v{version} 是当前稳定基准",)),
        (
            ROOT / "docs" / "maintenance" / "README_FIRST.md",
            (
                f"正式版本：**v{version}**",
                f"v{version}为当前稳定基准",
                f"开局一键爽玩_v{version}_正式版.zip",
            ),
        ),
        (
            ROOT / "docs" / "maintenance" / "测试状态与回归清单.md",
            (f"## 当前稳定线：v{version}",),
        ),
        (ROOT / "CHANGELOG.md", (f"## v{version}",)),
    )
    required_paths = (
        ROOT / "docs" / "baseline" / f"README_v{version}_正式版.md",
        ROOT / "docs" / "baseline" / f"v{version}_正式版静态复核.md",
        ROOT / "docs" / "publishing" / f"v{version}更新说明.md",
        ROOT / "docs" / "publishing" / f"Steam工坊中文简介_v{version}_BBCode.txt",
        ROOT / "docs" / "publishing" / f"v{version}工坊更新摘要.txt",
    )

    for path, markers in requirements:
        if not path.is_file():
            errors.append(f"稳定版入口缺失：{path.relative_to(ROOT)}")
            continue
        text = read_utf8(path)
        for marker in markers:
            if marker not in text:
                errors.append(
                    f"{path.relative_to(ROOT)} 未同步 v{version} 标记：{marker}"
                )
    for path in required_paths:
        if not path.is_file():
            errors.append(f"缺少 v{version} 配套文件：{path.relative_to(ROOT)}")


def tokenize_script(text: str) -> tuple[list[Token], list[str]]:
    """Tokenize the subset of Paradox script needed for structural checks."""
    tokens: list[Token] = []
    errors: list[str] = []
    index = 0
    line = 1
    while index < len(text):
        char = text[index]
        if char == "\n":
            line += 1
            index += 1
        elif char.isspace():
            index += 1
        elif char == "#":
            while index < len(text) and text[index] != "\n":
                index += 1
        elif char in "{}=":
            kind = {"{": "LBRACE", "}": "RBRACE", "=": "EQUALS"}[char]
            tokens.append(Token(kind, char, line))
            index += 1
        elif char == '"':
            start_line = line
            index += 1
            value: list[str] = []
            escaped = False
            closed = False
            while index < len(text):
                char = text[index]
                if char == "\n":
                    line += 1
                if escaped:
                    value.append(char)
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    index += 1
                    closed = True
                    break
                else:
                    value.append(char)
                index += 1
            if not closed:
                errors.append(f"第 {start_line} 行的字符串未闭合")
            tokens.append(Token("VALUE", "".join(value), start_line))
        else:
            start = index
            while (
                index < len(text)
                and not text[index].isspace()
                and text[index] not in '#{}="'
            ):
                index += 1
            tokens.append(Token("VALUE", text[start:index], line))
    return tokens, errors


def parse_script(text: str) -> tuple[Block, list[str]]:
    """Parse assignments and nested blocks while preserving source lines."""
    tokens, errors = tokenize_script(text)
    root = Block()
    stack = [root]
    index = 0

    while index < len(tokens):
        token = tokens[index]
        if token.kind == "RBRACE":
            if len(stack) == 1:
                errors.append(f"第 {token.line} 行存在多余的右花括号")
            else:
                stack.pop()
            index += 1
            continue

        if token.kind == "LBRACE":
            anonymous = Block()
            stack[-1].assignments.append(
                Assignment("<anonymous>", anonymous, token.line)
            )
            stack.append(anonymous)
            index += 1
            continue

        if (
            token.kind == "VALUE"
            and index + 1 < len(tokens)
            and tokens[index + 1].kind == "EQUALS"
        ):
            if index + 2 >= len(tokens):
                errors.append(f"第 {token.line} 行的 {token.value} 缺少赋值")
                break
            value_token = tokens[index + 2]
            if value_token.kind == "LBRACE":
                child = Block()
                stack[-1].assignments.append(
                    Assignment(token.value, child, token.line)
                )
                stack.append(child)
            elif value_token.kind == "VALUE":
                stack[-1].assignments.append(
                    Assignment(token.value, value_token.value, token.line)
                )
            else:
                errors.append(f"第 {token.line} 行的 {token.value} 赋值无效")
            index += 3
            continue

        index += 1

    if len(stack) > 1:
        errors.append(f"文件结束时仍有 {len(stack) - 1} 个块未闭合")
    return root, errors


def walk_blocks(block: Block, context: tuple[str, ...] = ()):
    yield block, context
    for assignment in block.assignments:
        if isinstance(assignment.value, Block):
            yield from walk_blocks(
                assignment.value, (*context, f"{assignment.key}@{assignment.line}")
            )


def direct_scalars(block: Block, key: str) -> list[str]:
    return [
        assignment.value
        for assignment in block.assignments
        if assignment.key == key and isinstance(assignment.value, str)
    ]


def direct_blocks(block: Block, key: str) -> list[Block]:
    return [
        assignment.value
        for assignment in block.assignments
        if assignment.key == key and isinstance(assignment.value, Block)
    ]


def has_direct_scalar(block: Block, key: str, value: str) -> bool:
    return value in direct_scalars(block, key)


def localisation_line_errors(text: str) -> list[str]:
    errors: list[str] = []
    header_pattern = re.compile(r"^l_[A-Za-z0-9_]+:\s*$")
    entry_pattern = re.compile(r'^\s*[^\s:#]+:\d*\s+".*"\s*$')
    for line_number, line in enumerate(text.splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if header_pattern.fullmatch(line) or entry_pattern.fullmatch(line):
            continue
        errors.append(f"第 {line_number} 行不是完整的单行本地化条目")
    return errors


def localisation_keys(path: Path) -> tuple[set[str], list[str]]:
    keys: set[str] = set()
    duplicates: list[str] = []
    pattern = re.compile(r"^\s*([^\s:#]+):\d*\s")
    for line_number, line in enumerate(read_utf8(path).splitlines(), 1):
        match = pattern.match(line)
        if not match:
            continue
        key = match.group(1)
        if key.startswith("l_"):
            continue
        if key in keys:
            duplicates.append(f"{key}（第 {line_number} 行）")
        keys.add(key)
    return keys, duplicates


def check_script_structure(
    parsed_scripts: dict[Path, Block],
    errors: list[str],
) -> tuple[int, int]:
    """Check project-specific invariants that marker searches cannot prove."""
    effect_definitions: dict[str, tuple[Path, int]] = {}
    effect_count = 0

    for path, root in parsed_scripts.items():
        relative = path.relative_to(ROOT)

        if path.parent == ROOT / "common" / "scripted_effects":
            for assignment in root.assignments:
                if not isinstance(assignment.value, Block):
                    continue
                effect_count += 1
                previous = effect_definitions.get(assignment.key)
                if previous:
                    errors.append(
                        f"scripted effect 重名：{assignment.key} 同时定义于 "
                        f"{previous[0].relative_to(ROOT)}:{previous[1]} 和 "
                        f"{relative}:{assignment.line}"
                    )
                else:
                    effect_definitions[assignment.key] = (path, assignment.line)

        for block, context in walk_blocks(root):
            limits = [
                assignment
                for assignment in block.assignments
                if assignment.key == "limit"
            ]
            if len(limits) > 1:
                location = " > ".join(context) or "<root>"
                lines = ", ".join(str(item.line) for item in limits)
                errors.append(
                    f"{relative} 的同一作用域存在多个 limit：{location}（第 {lines} 行）"
                )
            for limit in limits:
                if not isinstance(limit.value, Block):
                    errors.append(
                        f"{relative}:{limit.line} 的 limit 必须是花括号块"
                    )

            tag_prc = has_direct_scalar(block, "tag", "PRC")
            original_prc = has_direct_scalar(block, "original_tag", "PRC")
            if tag_prc != original_prc:
                location = " > ".join(context) or "<root>"
                errors.append(
                    f"{relative} 的 PRC 判断未同时包含 tag = PRC 与 "
                    f"original_tag = PRC：{location}"
                )

            for assignment in block.assignments:
                if assignment.key not in ("any_owned_state", "every_owned_state"):
                    continue
                if not isinstance(assignment.value, Block):
                    continue
                state_block = assignment.value
                controlled = has_direct_scalar(
                    state_block, "is_controlled_by", "ROOT"
                )
                for limit_block in direct_blocks(state_block, "limit"):
                    controlled = controlled or has_direct_scalar(
                        limit_block, "is_controlled_by", "ROOT"
                    )
                if not controlled:
                    errors.append(
                        f"{relative}:{assignment.line} 的 {assignment.key} "
                        "缺少 is_controlled_by = ROOT"
                    )

    decisions_path = ROOT / "common" / "decisions" / "PRC_OCS_decisions.txt"
    decision_count = 0
    decision_root = parsed_scripts[decisions_path]
    for category in decision_root.assignments:
        if not isinstance(category.value, Block):
            continue
        for decision in category.value.assignments:
            if not isinstance(decision.value, Block):
                continue
            block = decision.value
            if not direct_blocks(block, "complete_effect"):
                continue
            decision_count += 1
            visible = direct_blocks(block, "visible")
            available = direct_blocks(block, "available")
            ai_will_do = direct_blocks(block, "ai_will_do")
            if not visible or not has_direct_scalar(visible[0], "is_ai", "no"):
                errors.append(
                    f"{decisions_path.relative_to(ROOT)}:{decision.line} 的 "
                    f"{decision.key} 缺少 visible 内的 is_ai = no"
                )
            if not available or not has_direct_scalar(available[0], "is_ai", "no"):
                errors.append(
                    f"{decisions_path.relative_to(ROOT)}:{decision.line} 的 "
                    f"{decision.key} 缺少 available 内的 is_ai = no"
                )
            if not ai_will_do or not has_direct_scalar(
                ai_will_do[0], "factor", "0"
            ):
                errors.append(
                    f"{decisions_path.relative_to(ROOT)}:{decision.line} 的 "
                    f"{decision.key} 缺少 ai_will_do = {{ factor = 0 }}"
                )

    combined_assignments = [
        assignment.key
        for root in parsed_scripts.values()
        for block, _ in walk_blocks(root)
        for assignment in block.assignments
    ]
    if "create_unit" not in combined_assignments:
        errors.append("未找到 24 师创建所需的 create_unit 效果")

    return effect_count, decision_count


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
    version = descriptor_value(descriptor, "version")
    if version is None:
        errors.append("descriptor.mod 缺少 version 字段")
    else:
        name = descriptor_value(descriptor, "name") or ""
        if f"v{version}" not in name:
            errors.append(f"descriptor.mod 的 name 未包含版本 v{version}")
        check_version_metadata(version, errors)


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
    parsed_scripts: dict[Path, Block] = {}

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
        parsed, parse_errors = parse_script(text)
        parsed_scripts[path] = parsed
        for parse_error in parse_errors:
            errors.append(f"{path.relative_to(ROOT)}：{parse_error}")

    localisation_sets: dict[Path, set[str]] = {}
    for path in LOCALISATION_FILES:
        data = path.read_bytes()
        if not data.startswith(b"\xef\xbb\xbf"):
            errors.append(f"{path.relative_to(ROOT)} 缺少 UTF-8 BOM")
        try:
            data.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            errors.append(f"{path.relative_to(ROOT)} 不是有效 UTF-8：{exc}")
            continue
        decoded = data.decode("utf-8-sig")
        for format_error in localisation_line_errors(decoded):
            errors.append(f"{path.relative_to(ROOT)}：{format_error}")
        keys, duplicates = localisation_keys(path)
        localisation_sets[path] = keys
        for duplicate in duplicates:
            errors.append(f"{path.relative_to(ROOT)} 的本地化键重复：{duplicate}")

    if len(localisation_sets) == len(LOCALISATION_FILES):
        english, chinese = LOCALISATION_FILES
        only_english = sorted(localisation_sets[english] - localisation_sets[chinese])
        only_chinese = sorted(localisation_sets[chinese] - localisation_sets[english])
        if only_english:
            errors.append(
                f"英文存在但简中缺少的本地化键：{', '.join(only_english)}"
            )
        if only_chinese:
            errors.append(
                f"简中存在但英文缺少的本地化键：{', '.join(only_chinese)}"
            )

    effect_count = 0
    decision_count = 0
    if len(parsed_scripts) == len(script_files):
        effect_count, decision_count = check_script_structure(parsed_scripts, errors)

    for warning in warnings:
        print(f"WARNING: {warning}")
    for error in errors:
        print(f"ERROR: {error}")

    if errors:
        print(f"\n静态检查失败：{len(errors)} 个错误，{len(warnings)} 个警告。")
        return 1

    localisation_count = len(next(iter(localisation_sets.values()), ()))
    print(
        f"静态检查通过：{len(REQUIRED_FILES)} 个必需文件，"
        f"{len(script_files)} 个脚本文件，{effect_count} 个 scripted effects，"
        f"{decision_count} 个玩家决议，{localisation_count} 对本地化键，"
        f"{len(warnings)} 个警告。"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
