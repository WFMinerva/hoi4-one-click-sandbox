#!/usr/bin/env python3
"""Validate and prepare or upload the current tagged Steam Workshop build."""

from __future__ import annotations

import argparse
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

try:
    from .build_release import normalize_release_tree
except ImportError:  # Direct execution: python tools/publish_workshop.py
    from build_release import normalize_release_tree

ROOT = pathlib.Path(__file__).resolve().parents[1]
MOD_ITEMS = (
    "common",
    "events",
    "localisation",
    "descriptor.mod",
    "thumbnail.png",
    "LICENSE",
    "NOTICE.md",
)
WORKSHOP_ID = "3767025052"
APPID = "394360"
CONTENT_FOLDER_NAME = "OCS_one_click_sandbox_start_v2_0"


def as_posix(path: pathlib.Path) -> str:
    return path.as_posix()


def mod_version() -> str:
    text = (ROOT / "descriptor.mod").read_text(encoding="utf-8-sig")
    match = re.search(r'(?m)^\s*version\s*=\s*"([^"]+)"', text)
    if not match:
        raise SystemExit("descriptor.mod 缺少 version 字段")
    return match.group(1)


def description_file(version: str) -> pathlib.Path:
    return (
        ROOT
        / "docs"
        / "publishing"
        / f"Steam工坊中文简介_v{version}_BBCode.txt"
    )


def changenote_file(version: str) -> pathlib.Path:
    return ROOT / "docs" / "publishing" / f"v{version}工坊更新摘要.txt"


def git_output(*args: str) -> str:
    try:
        return subprocess.check_output(
            ["git", *args], cwd=ROOT, text=True, stderr=subprocess.STDOUT
        ).strip()
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f"git {' '.join(args)} 失败：{exc.output.strip()}") from exc


def ensure_repository_preconditions(version: str) -> str:
    if "test" in version.casefold():
        raise SystemExit(f"测试版本 v{version} 禁止上传正式工坊物品")
    dirty = git_output("status", "--porcelain")
    if dirty:
        raise SystemExit("工作区不干净，拒绝工坊上传：\n" + dirty)

    tag = f"v{version}"
    tag_commit = git_output("rev-list", "-n", "1", tag)
    head = git_output("rev-parse", "HEAD")
    if head != tag_commit:
        raise SystemExit(
            f"HEAD {head[:12]} 不等于正式标签 {tag} {tag_commit[:12]}，"
            "拒绝工坊上传"
        )
    comparison = subprocess.run(
        ["git", "diff", "--quiet", tag_commit, "--", *MOD_ITEMS],
        cwd=ROOT,
        check=False,
    )
    if comparison.returncode == 1:
        raise SystemExit(f"当前 MOD 内容与正式标签 {tag} 不一致，拒绝上传")
    if comparison.returncode != 0:
        raise SystemExit("无法比较当前 MOD 内容与正式标签")
    return tag


def run_release_gate() -> None:
    commands = (
        [sys.executable, "tools/validate_mod.py"],
        [sys.executable, "-m", "unittest", "tools.test_validate_mod"],
        [sys.executable, "tools/build_release.py"],
    )
    for command in commands:
        print("PRECHECK", " ".join(command))
        subprocess.run(command, cwd=ROOT, check=True)


def vdf_escape(value: str) -> str:
    if "\x00" in value:
        raise SystemExit("VDF 文本包含 NUL 字符")
    return (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\r\n", "\n")
        .replace("\r", "\n")
    )


def build_vdf(
    content_dir: pathlib.Path,
    steamcmd_dir: pathlib.Path,
    description: str,
    changenote: str,
) -> pathlib.Path:
    vdf = steamcmd_dir / "hoi4_ocs_workshop.vdf"
    preview = as_posix(content_dir / "thumbnail.png")
    text = (
        '"workshopitem"\n'
        "{\n"
        f'\t"appid"\t\t"{APPID}"\n'
        f'\t"publishedfileid"\t"{WORKSHOP_ID}"\n'
        f'\t"contentfolder"\t\t"{as_posix(content_dir)}"\n'
        f'\t"previewfile"\t\t"{preview}"\n'
        f'\t"description"\t\t"{vdf_escape(description)}"\n'
        f'\t"changenote"\t\t"{vdf_escape(changenote)}"\n'
        "}\n"
    )
    vdf.write_text(text, encoding="utf-8", newline="\n")
    return vdf


def validate_sources(version: str) -> tuple[pathlib.Path, pathlib.Path]:
    missing = [item for item in MOD_ITEMS if not (ROOT / item).exists()]
    if missing:
        raise SystemExit(f"MOD 源文件缺失：{', '.join(missing)}")
    description = description_file(version)
    changenote = changenote_file(version)
    if not description.is_file():
        raise SystemExit(f"缺少工坊简介：{description}")
    if not changenote.is_file():
        raise SystemExit(f"缺少工坊更新摘要：{changenote}")
    return description, changenote


def replace_staging_content(content_dir: pathlib.Path) -> None:
    """Build a complete temporary stage before replacing the prior stage."""
    parent = content_dir.parent
    parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".ocs-stage-", dir=parent) as temp_name:
        staged = pathlib.Path(temp_name) / CONTENT_FOLDER_NAME
        staged.mkdir()
        for item in MOD_ITEMS:
            source = ROOT / item
            destination = staged / item
            if source.is_dir():
                shutil.copytree(source, destination)
            else:
                shutil.copy2(source, destination)
        normalize_release_tree(staged)
        if content_dir.exists():
            shutil.rmtree(content_dir)
        shutil.move(str(staged), str(content_dir))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--steamcmd",
        type=pathlib.Path,
        required=True,
        help="当前机器的 steamcmd.exe 路径",
    )
    parser.add_argument("--username", help="Steam 用户名；正式上传时必填")
    parser.add_argument(
        "--prepare-only",
        action="store_true",
        help="只生成暂存目录和 VDF，不启动 steamcmd",
    )
    args = parser.parse_args()

    if not args.prepare_only and not args.username:
        raise SystemExit("正式上传必须传入 --username；仅准备文件请用 --prepare-only")
    steamcmd_exe = args.steamcmd.resolve()
    if not steamcmd_exe.is_file():
        raise SystemExit(f"找不到 steamcmd：{steamcmd_exe}")

    version = mod_version()
    tag = ensure_repository_preconditions(version)
    description_path, changenote_path = validate_sources(version)
    run_release_gate()

    steamcmd_dir = steamcmd_exe.parent
    content_dir = steamcmd_dir / "workshop_content" / CONTENT_FOLDER_NAME
    replace_staging_content(content_dir)
    print(f"暂存目录已同步：{content_dir}（内容与 {tag} 一致）")

    description = description_path.read_text(encoding="utf-8").strip()
    changenote = changenote_path.read_text(encoding="utf-8-sig").strip()
    if not description or not changenote:
        raise SystemExit("工坊简介或更新摘要为空")
    vdf = build_vdf(content_dir, steamcmd_dir, description, changenote)
    print(f"VDF 已生成：{vdf}")

    if args.prepare_only:
        print("PREPARED：未启动 steamcmd")
        return 0

    command = [
        str(steamcmd_exe),
        "+login",
        args.username,
        "+workshop_build_item",
        as_posix(vdf),
        "+quit",
    ]
    print("运行 steamcmd（密码与 Steam Guard 请按提示交互输入）...")
    return subprocess.call(command)


if __name__ == "__main__":
    sys.exit(main())
