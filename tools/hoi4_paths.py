#!/usr/bin/env python3
"""Resolve machine-specific Hearts of Iron IV installation paths."""

from __future__ import annotations

import os
from pathlib import Path


ENV_NAME = "HOI4_VANILLA_PATH"
KNOWN_LOCATIONS = (
    Path(r"F:\SteamLibrary\steamapps\common\Hearts of Iron IV"),
    Path(r"D:\SteamLibrary\steamapps\common\Hearts of Iron IV"),
)


def is_vanilla_root(path: Path) -> bool:
    """Return whether path has the minimum expected vanilla tree."""
    return (path / "common").is_dir()


def candidate_paths() -> list[Path]:
    """Return ordered, de-duplicated candidates for the current machine."""
    values: list[Path] = []
    configured = os.environ.get(ENV_NAME)
    if configured:
        values.append(Path(configured))
    values.extend(KNOWN_LOCATIONS)

    unique: list[Path] = []
    seen: set[str] = set()
    for path in values:
        key = str(path).casefold()
        if key not in seen:
            seen.add(key)
            unique.append(path)
    return unique


def resolve_vanilla_path(explicit: Path | None = None) -> Path:
    """Resolve an explicit path, environment override, or known installation."""
    if explicit is not None:
        if is_vanilla_root(explicit):
            return explicit
        raise SystemExit(f"无效的 HOI4 原版目录：{explicit}（缺少 common/）")

    for path in candidate_paths():
        if is_vanilla_root(path):
            return path
    raise SystemExit(
        "未找到 HOI4 原版目录；请传入 --vanilla <路径>，"
        f"或设置环境变量 {ENV_NAME}"
    )
