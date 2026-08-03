"""List vanilla special-project mutually exclusive buff choices.

The one-click completion (complete_special_project) never fires prototype
iteration rewards, so equipment-bonus/module choices are silently lost.
This tool scans vanilla project files and reports every unique prototype
reward option that grants a country-scope "choice buff" that can be ported
to a decision/event option.

Country-scope effects (portable):
  add_equipment_bonus, add_tech_bonus, research_technologies,
  set_technology, add_equipment_production

Project-context effects (NOT portable):
  equipment_bonus, enable_equipment_modules

Report: docs/analysis/v2.6_特殊科研互斥选项清单.md
Structured source: docs/analysis/v2.6_特殊科研互斥选项清单.json
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

try:
    from .hoi4_paths import resolve_vanilla_path
except ImportError:  # Direct execution: python tools/analyze_special_project_choices.py
    from hoi4_paths import resolve_vanilla_path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT = ROOT / "docs" / "analysis" / "v2.6_特殊科研互斥选项清单.md"
DEFAULT_JSON = ROOT / "docs" / "analysis" / "v2.6_特殊科研互斥选项清单.json"

SPECIALIZATION_FILES = {
    "air": ("air_projects.txt", "radar_projects.txt"),
    "land": ("land_projects.txt",),
    "naval": ("naval_projects.txt",),
    "nuclear": ("nuclear_projects.txt",),
    "rocket": ("rocket_projects.txt",),
}

# Effects that constitute a player-visible "choice buff".
BUFF_KEYS = {
    "add_equipment_bonus",
    "equipment_bonus",
    "enable_equipment_modules",
    "add_tech_bonus",
    "research_technologies",
    "set_technology",
    "add_equipment_production",
}

# COUNTRY-scope effects: valid inside decision/event options.
COUNTRY_BUFF_KEYS = {
    "add_equipment_bonus",
    "add_tech_bonus",
    "research_technologies",
    "set_technology",
    "add_equipment_production",
}
# Project/special-project-context effects: NOT portable to decision/event scope.
PROJECT_BUFF_KEYS = {
    "equipment_bonus",
    "enable_equipment_modules",
}
BUFF_KEY_LABELS = {
    "add_equipment_bonus": "装备加成(国)",
    "equipment_bonus": "装备加成(项目)",
    "enable_equipment_modules": "模块解锁(项目)",
    "add_tech_bonus": "研究加成(国)",
    "research_technologies": "直接研究(国)",
    "set_technology": "直接科技(国)",
    "add_equipment_production": "免费装备(国)",
}


@dataclass(frozen=True)
class Atom:
    value: str


@dataclass(frozen=True)
class Bare:
    value: str


@dataclass(frozen=True)
class Assignment:
    key: str
    value: Atom | "Block"


@dataclass(frozen=True)
class Block:
    entries: tuple[Assignment | Bare, ...]


def tokenize(text: str) -> list[str]:
    tokens: list[str] = []
    index = 0
    while index < len(text):
        char = text[index]
        if char.isspace():
            index += 1
        elif char == "#":
            while index < len(text) and text[index] != "\n":
                index += 1
        elif char in "{}=":
            tokens.append(char)
            index += 1
        elif char == '"':
            index += 1
            value: list[str] = []
            escaped = False
            while index < len(text):
                char = text[index]
                index += 1
                if escaped:
                    value.append(char)
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    break
                else:
                    value.append(char)
            tokens.append("".join(value))
        else:
            start = index
            while (
                index < len(text)
                and not text[index].isspace()
                and text[index] not in '#{}="'
            ):
                index += 1
            tokens.append(text[start:index])
    return tokens


def parse_block(tokens: list[str], index: int = 0, nested: bool = False) -> tuple[Block, int]:
    entries: list[Assignment | Bare] = []
    while index < len(tokens):
        token = tokens[index]
        if token == "}":
            if not nested:
                raise ValueError("unexpected closing brace")
            return Block(tuple(entries)), index + 1
        if token in ("{", "="):
            raise ValueError(f"unexpected token {token!r} at token index {index}")
        if index + 1 < len(tokens) and tokens[index + 1] == "=":
            if index + 2 >= len(tokens):
                raise ValueError(f"missing value for {token!r}")
            next_token = tokens[index + 2]
            if next_token == "{":
                value, index = parse_block(tokens, index + 3, nested=True)
            else:
                value = Atom(next_token)
                index += 3
            entries.append(Assignment(token, value))
        else:
            entries.append(Bare(token))
            index += 1
    return Block(tuple(entries)), index


def parse_file(path: Path) -> Block:
    text = path.read_text(encoding="utf-8-sig")
    parsed, index = parse_block(tokenize(text))
    if index < 0:
        raise AssertionError("unreachable")
    return parsed


def assignments(block: Block, key: str | None = None) -> list[Assignment]:
    return [
        entry
        for entry in block.entries
        if isinstance(entry, Assignment) and (key is None or entry.key == key)
    ]


def all_assignments(block: Block) -> list[Assignment]:
    return [entry for entry in block.entries if isinstance(entry, Assignment)]


def scalar(block: Block, key: str) -> str | None:
    for entry in assignments(block, key):
        if isinstance(entry.value, Atom):
            return entry.value.value
    return None


def walk_blocks(block: Block, key: str) -> list[Block]:
    return [
        entry.value
        for entry in assignments(block, key)
        if isinstance(entry.value, Block)
    ]


@dataclass
class ChoiceGroup:
    project: str
    specialization: str
    reward_token: str
    default_token: str | None
    options: list["ChoiceOption"] = field(default_factory=list)


@dataclass
class ChoiceOption:
    token: str
    is_default: bool
    buff_kinds: set[str]
    effect_text: str

    @property
    def has_buff(self) -> bool:
        return bool(self.buff_kinds)

    @property
    def portable(self) -> bool:
        """Has at least one COUNTRY-scope buff (usable in event options)."""
        return bool(self.buff_kinds & COUNTRY_BUFF_KEYS)


def has_block(block: Block, key: str) -> bool:
    return any(
        isinstance(entry, Assignment) and entry.key == key
        for entry in block.entries
    )


def _collect_buff_keys(block: Block, kinds: set[str]) -> None:
    for entry in all_assignments(block):
        if isinstance(entry.value, Block):
            if entry.key in BUFF_KEYS:
                kinds.add(entry.key)
            _collect_buff_keys(entry.value, kinds)


def collect_buff_kinds(option_block: Block) -> set[str]:
    kinds: set[str] = set()
    for entry in all_assignments(option_block):
        if entry.key == "iteration_output" and isinstance(entry.value, Block):
            _collect_buff_keys(entry.value, kinds)
    return kinds


def _indent(text: str) -> str:
    return "\n".join(f"\t{line}" if line else "" for line in text.splitlines())


def block_text(block: Block) -> str:
    """Render a block back to canonical script text (best effort).

    Atoms whose value contains a space are quoted, preserving DLC names such
    as "By Blood Alone" when the text is re-parsed or stored as JSON.
    """
    parts: list[str] = []
    for entry in block.entries:
        if isinstance(entry, Bare):
            parts.append(entry.value)
        elif isinstance(entry.value, Atom):
            value = entry.value.value
            if " " in value:
                value = f'"{value}"'
            parts.append(f"{entry.key} = {value}")
        else:
            parts.append(f"{entry.key} = {{")
            parts.append(_indent(block_text(entry.value)))
            parts.append("}")
    return "\n".join(parts)


def extract_buff_text(option_block: Block) -> str:
    """Return the iteration_output script of a buff-bearing option."""
    for entry in all_assignments(option_block):
        if entry.key == "iteration_output" and isinstance(entry.value, Block):
            text = block_text(entry.value)
            if any(marker in text for marker in BUFF_KEYS):
                return text
    return ""


def analyze_file(path: Path, specialization: str) -> list[ChoiceGroup]:
    root = parse_file(path)
    groups: list[ChoiceGroup] = []
    for entry in all_assignments(root):
        if not isinstance(entry.value, Block):
            continue
        if not entry.key.startswith("sp_"):
            continue
        for reward_block in walk_blocks(entry.value, "unique_prototype_rewards"):
            for reward in all_assignments(reward_block):
                if not isinstance(reward.value, Block):
                    continue
                reward_token = reward.key
                default_token: str | None = None
                options: list[ChoiceOption] = []
                for option_block in walk_blocks(reward.value, "option"):
                    token = scalar(option_block, "token") or ""
                    is_default = has_block(option_block, "default")
                    if is_default:
                        default_token = token
                    options.append(
                        ChoiceOption(
                            token=token,
                            is_default=is_default,
                            buff_kinds=collect_buff_kinds(option_block),
                            effect_text=extract_buff_text(option_block),
                        )
                    )
                groups.append(
                    ChoiceGroup(
                        project=entry.key,
                        specialization=specialization,
                        reward_token=reward_token,
                        default_token=default_token,
                        options=options,
                    )
                )
    return groups


def is_selectable_buff(group: ChoiceGroup) -> bool:
    """A real player choice: at least two options and at least one option
    carries a portability COUNTRY-scope buff."""
    if len(group.options) < 2:
        return False
    return any(option.portable for option in group.options)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--vanilla",
        type=Path,
        help="HOI4 原版根目录；省略时读取 HOI4_VANILLA_PATH 或探测已知盘符",
    )
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    args = parser.parse_args()

    vanilla_root = resolve_vanilla_path(args.vanilla)
    project_dir = vanilla_root / "common" / "special_projects" / "projects"
    all_groups: list[ChoiceGroup] = []
    for specialization, filenames in SPECIALIZATION_FILES.items():
        for filename in filenames:
            path = project_dir / filename
            if not path.exists():
                print(f"SKIP missing {path}")
                continue
            all_groups.extend(analyze_file(path, specialization))

    selectable = [group for group in all_groups if is_selectable_buff(group)]

    by_spec: dict[str, list[ChoiceGroup]] = defaultdict(list)
    for group in selectable:
        by_spec[group.specialization].append(group)

    lines: list[str] = []
    lines.append("# v2.6 特殊科研互斥选项清单（原版导出·可选 buff）")
    lines.append("")
    lines.append("> 本文件由 `tools/analyze_special_project_choices.py` 自动生成，")
    lines.append("> 输入为本机原版 `common/special_projects/projects/*_projects.txt`。")
    lines.append("> 仅统计 **可作为事件选项移植** 的互斥 buff 组：至少 2 个选项，")
    lines.append("> 且至少 1 个选项含国家作用域 buff（装备加成/研究加成/直接研究/直接科技/免费装备）。")
    lines.append("")
    for specialization in ("air", "land", "naval", "nuclear", "rocket"):
        groups = by_spec.get(specialization, [])
        lines.append(f"## {specialization.upper()}")
        lines.append("")
        lines.append(f"共 {len(groups)} 个可选 buff 组。")
        lines.append("")
        for group in groups:
            lines.append(f"### {group.project} — {group.reward_token}")
            lines.append("")
            default_note = (
                "（无显式 default，默认取第一个）"
                if group.default_token is None
                else f"默认：`{group.default_token}`"
            )
            lines.append(f"- 选项数：{len(group.options)}，{default_note}")
            lines.append("")
            lines.append("| 选项 token | 默认 | buff 效果 |")
            lines.append("|---|---|---|")
            for option in group.options:
                kind_text = ", ".join(
                    BUFF_KEY_LABELS[k]
                    for k in sorted(option.buff_kinds)
                ) or "—"
                lines.append(
                    f"| `{option.token}` | {'是' if option.is_default else ''} | {kind_text} |"
                )
            lines.append("")

    report_text = "\n".join(lines) + "\n"
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(report_text, encoding="utf-8")
    print(f"REPORT: {args.report}")

    payload = [
        {
            "project": g.project,
            "specialization": g.specialization,
            "reward": g.reward_token,
            "default": g.default_token,
            "options": [
                {
                    "token": o.token,
                    "default": o.is_default,
                    "buff_kinds": sorted(o.buff_kinds),
                    "portable": o.portable,
                    "effect": o.effect_text,
                }
                for o in g.options
            ],
        }
        for g in selectable
    ]
    args.json.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"JSON: {args.json}")
    print(f"TOTAL rewards: {len(all_groups)}, selectable buff groups: {len(selectable)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())