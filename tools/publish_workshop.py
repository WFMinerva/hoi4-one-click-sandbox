#!/usr/bin/env python3
"""One-shot Steam Workshop upload helper for One-Click Sandbox Start.

用法（在可正常连接 Steam 网络的机器上）:
    python tools/publish_workshop.py --steamcmd D:\\steamcmd\\steamcmd.exe
    python tools/publish_workshop.py --steamcmd F:\\steamcmd\\steamcmd.exe --username YourSteamName

脚本自动完成:
1. 从仓库同步 MOD 内容到 steamcmd 暂存目录（先清空旧目录，避免残留文件）。
2. 由 docs/publishing/Steam工坊中文简介_v2.4_BBCode.txt 生成 VDF（description + changenote，
   publishedfileid 固定为既有物品 3767025052，不新建工坊条目）。
3. 调用 steamcmd 执行 +workshop_build_item。

登录与 Steam Guard 验证码保持交互输入，不会写入命令行或本脚本。
"""

from __future__ import annotations

import argparse
import pathlib
import shutil
import subprocess
import sys

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
DESCRIPTION_FILE = ROOT / "docs" / "publishing" / "Steam工坊中文简介_v2.4_BBCode.txt"
CHANGENOTE = (
    "v2.4 更新：雷达科技归位空军特殊科研（完成后1-5级全亮）；"
    "直升机/装甲支援车/中型喷火坦克III型执行进化编制后设计与库存同现；"
    "船坞/民用工厂可重复点至上限20；全地图移除陆地碉堡（防空/海岸要塞保留）；"
    "政治点/指挥点/三军经验剥离为独立可重复决议；修复MOD本地部署加载结构。"
)


def as_posix(path: pathlib.Path) -> str:
    return path.as_posix()


def build_vdf(content_dir: pathlib.Path, steamcmd_dir: pathlib.Path,
              description: str) -> pathlib.Path:
    vdf = steamcmd_dir / "hoi4_ocs_workshop.vdf"
    preview = as_posix(content_dir / "thumbnail.png")
    escaped = description.replace("\\", "\\\\").replace('"', '\\"')
    text = (
        '"workshopitem"\n'
        '{\n'
        f'\t"appid"\t\t"{APPID}"\n'
        f'\t"publishedfileid"\t"{WORKSHOP_ID}"\n'
        f'\t"contentfolder"\t\t"{as_posix(content_dir)}"\n'
        f'\t"previewfile"\t\t"{preview}"\n'
        f'\t"description"\t\t"{escaped}"\n'
        f'\t"changenote"\t\t"{CHANGENOTE}"\n'
        '}\n'
    )
    vdf.write_text(text, encoding="utf-8", newline="\n")
    return vdf


def main() -> int:
    parser = argparse.ArgumentParser(description="Steam Workshop upload helper")
    parser.add_argument(
        "--steamcmd",
        type=pathlib.Path,
        required=True,
        help="steamcmd 可执行文件路径，例如 D:\\steamcmd\\steamcmd.exe",
    )
    parser.add_argument("--username", default=None, help="Steam 用户名（可选，交互输入）")
    args = parser.parse_args()

    steamcmd_exe = args.steamcmd
    if not steamcmd_exe.is_file():
        raise SystemExit(f"找不到 steamcmd：{steamcmd_exe}")
    steamcmd_dir = steamcmd_exe.parent

    content_dir = steamcmd_dir / "workshop_content" / CONTENT_FOLDER_NAME
    if content_dir.exists():
        shutil.rmtree(content_dir)
    content_dir.mkdir(parents=True)
    for item in MOD_ITEMS:
        src = ROOT / item
        if src.is_dir():
            shutil.copytree(src, content_dir / item)
        else:
            shutil.copy2(src, content_dir / item)
    print(f"暂存目录已同步：{content_dir}")

    if not DESCRIPTION_FILE.is_file():
        raise SystemExit(f"缺少工坊简介文件：{DESCRIPTION_FILE}")
    description = DESCRIPTION_FILE.read_text(encoding="utf-8")
    vdf = build_vdf(content_dir, steamcmd_dir, description)
    print(f"VDF 已生成：{vdf}")

    command = [str(steamcmd_exe)]
    if args.username:
        command += ["+login", args.username]
    else:
        command.append("+login")
    command += ["+workshop_build_item", as_posix(vdf), "+quit"]
    print("运行 steamcmd（登录与 Steam Guard 请按提示交互输入）...")
    return subprocess.call(command)


if __name__ == "__main__":
    sys.exit(main())