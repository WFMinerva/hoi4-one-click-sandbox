#!/usr/bin/env python3
"""One-shot GitHub Release creator + ZIP asset uploader for One-Click Sandbox Start.

用法（在本机可正常连接 GitHub 的机器上）:
    python tools/publish_github_release.py --version 2.5

脚本自动完成:
1. 从 Git 凭据管理器取 GitHub token（`git credential fill`，不打印明文，无需 GH_TOKEN/gh）。
2. 按 tag 幂等检查：GET /releases/tags/v<版本> 已存在则复用 release_id，避免重复创建。
3. 创建/复用 GitHub Release（body 引 docs/publishing/v<版本>更新说明.md）。
4. 上传正式包 ZIP 附件：必须走 https://uploads.github.com/... （走 api.github.com 会 404），
   附件文件名用 ASCII（中文会被剥离），随后 PATCH label 设为中文显示名。

正式包本体在 dist/开局一键爽玩_v<版本>_正式版.zip（由 tools/build_release.py 生成）。
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPO = "WFMinerva/hoi4-one-click-sandbox"


def ascii_asset_name(version: str) -> str:
    return f"OCS_one_click_sandbox_start_v{version}.zip"


def chinese_label(version: str) -> str:
    return f"开局一键爽玩 v{version} 正式包"


def expected_zip(version: str) -> Path:
    return ROOT / "dist" / f"开局一键爽玩_v{version}_正式版.zip"


def expected_body(version: str) -> Path:
    return ROOT / "docs" / "publishing" / f"v{version}更新说明.md"


def get_token() -> str:
    data = subprocess.check_output(
        ["git", "credential", "fill"],
        input="protocol=https\nhost=github.com\n\n",
        text=True,
    )
    password = None
    for line in data.splitlines():
        if line.startswith("password="):
            password = line.split("=", 1)[1]
    if not password:
        sys.exit("git credential fill 未返回 token")
    return password


def request(method: str, url: str, token: str, body=None, headers=None,
            data=None) -> tuple[int, dict | bytes]:
    headers = headers or {}
    h = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    h.update(headers)
    req = urllib.request.Request(url, method=method, headers=h)
    if data is not None:
        req.data = data
    elif body is not None:
        req.data = json.dumps(body).encode("utf-8")
    try:
        with urllib.request.urlopen(req) as resp:
            raw = resp.read()
            code = resp.status
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        code = exc.code
    try:
        return code, json.loads(raw)
    except Exception:
        return code, raw


def main() -> int:
    parser = argparse.ArgumentParser(description="GitHub Release creator/uploader")
    parser.add_argument(
        "--version", required=True, help="正式版本号，例如 2.5（对应 tag v2.5）"
    )
    parser.add_argument("--repo", default=DEFAULT_REPO, help="GitHub 仓库 owner/name")
    parser.add_argument("--target", default="main", help="target_commitish")
    args = parser.parse_args()

    version = args.version
    tag = f"v{version}"
    zip_path = expected_zip(version)
    body_path = expected_body(version)
    if not zip_path.is_file():
        sys.exit(f"缺少正式包：{zip_path}（先运行 python tools/build_release.py）")
    if not body_path.is_file():
        sys.exit(f"缺少发布说明：{body_path}")

    api = f"https://api.github.com/repos/{args.repo}"
    uploads = f"https://uploads.github.com/repos/{args.repo}"

    token = get_token()
    print("token acquired (not printed)")

    # 1. idempotent: reuse existing release if any
    code, existing = request("GET", f"{api}/releases/tags/{tag}", token)
    if code == 200:
        release_id = existing["id"]
        print(f"release {tag} already exists, reuse id {release_id}")
    else:
        payload = {
            "tag_name": tag,
            "target_commitish": args.target,
            "name": tag,
            "body": body_path.read_text(encoding="utf-8-sig").strip(),
            "draft": False,
            "prerelease": False,
        }
        code, created = request("POST", f"{api}/releases", token, body=payload)
        if code != 201:
            sys.exit(f"release create failed: {code} {created}")
        release_id = created["id"]
        print(f"release created id {release_id}")

    # 2. asset-level idempotency: reuse existing asset with the same ASCII name
    asset_name = ascii_asset_name(version)
    code, asset_list = request("GET", f"{api}/releases/{release_id}/assets", token)
    existing_asset = None
    if code == 200 and isinstance(asset_list, list):
        existing_asset = next(
            (a for a in asset_list if a.get("name") == asset_name), None
        )
    if existing_asset:
        asset_id = existing_asset["id"]
        print(f"asset {asset_name} already exists, reuse id {asset_id}")
    else:
        # upload to uploads.github.com (NOT api.github.com; api.github.com returns 404)
        url = f"{uploads}/releases/{release_id}/assets?name={asset_name}"
        asset_data = zip_path.read_bytes()
        code, asset = request(
            "POST", url, token,
            headers={"Content-Type": "application/zip"},
            data=asset_data,
        )
        if code not in (200, 201):
            sys.exit(f"asset upload failed: {code} {asset}")
        asset_id = asset["id"]
        print(f"asset uploaded id {asset_id}")

    # 3. set Chinese display label
    code, _ = request(
        "PATCH", f"{api}/releases/assets/{asset_id}", token,
        body={"label": chinese_label(version)},
    )
    if code != 200:
        print(f"label patch failed (non-fatal): {code}")

    print(f"DONE {api}/releases/tags/{tag}")
    return 0


if __name__ == "__main__":
    sys.exit(main())