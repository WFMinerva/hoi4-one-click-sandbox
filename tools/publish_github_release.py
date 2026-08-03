#!/usr/bin/env python3
"""Validate, create/reuse a GitHub Release, and upload its verified ZIP."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPO = "WFMinerva/hoi4-one-click-sandbox"
VERSION_PATTERN = re.compile(r"\d+\.\d+(?:\.\d+)?")
REPO_PATTERN = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")


def ascii_asset_name(version: str) -> str:
    return f"OCS_one_click_sandbox_start_v{version}.zip"


def chinese_label(version: str) -> str:
    return f"开局一键爽玩 v{version} 正式包"


def expected_zip(version: str) -> Path:
    return ROOT / "dist" / f"开局一键爽玩_v{version}_正式版.zip"


def expected_hash_file(version: str) -> Path:
    return ROOT / "dist" / f"开局一键爽玩_v{version}_正式版_SHA256.txt"


def expected_body(version: str) -> Path:
    return ROOT / "docs" / "publishing" / f"v{version}更新说明.md"


def mod_version() -> str:
    text = (ROOT / "descriptor.mod").read_text(encoding="utf-8-sig")
    match = re.search(r'(?m)^\s*version\s*=\s*"([^"]+)"', text)
    if not match:
        raise SystemExit("descriptor.mod 缺少 version 字段")
    return match.group(1)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_output(*args: str) -> str:
    try:
        return subprocess.check_output(
            ["git", *args], cwd=ROOT, text=True, stderr=subprocess.STDOUT
        ).strip()
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f"git {' '.join(args)} 失败：{exc.output.strip()}") from exc


def ensure_local_preconditions(version: str) -> tuple[str, Path]:
    if not VERSION_PATTERN.fullmatch(version):
        raise SystemExit(f"正式版本号格式无效：{version!r}")
    descriptor_version = mod_version()
    if descriptor_version != version:
        raise SystemExit(
            f"参数版本 v{version} 与 descriptor.mod v{descriptor_version} 不一致"
        )
    dirty = git_output("status", "--porcelain")
    if dirty:
        raise SystemExit("工作区不干净，拒绝发布：\n" + dirty)

    tag = f"v{version}"
    head = git_output("rev-parse", "HEAD")
    tag_commit = git_output("rev-list", "-n", "1", tag)
    if head != tag_commit:
        raise SystemExit(
            f"HEAD {head[:12]} 不等于正式标签 {tag} {tag_commit[:12]}，拒绝发布"
        )

    body_path = expected_body(version)
    if not body_path.is_file():
        raise SystemExit(f"缺少发布说明：{body_path}")
    return tag, body_path


def run_release_gate() -> None:
    commands = (
        [sys.executable, "tools/validate_mod.py"],
        [sys.executable, "-m", "unittest", "tools.test_validate_mod"],
        [sys.executable, "tools/build_release.py"],
    )
    for command in commands:
        print("PRECHECK", " ".join(command))
        subprocess.run(command, cwd=ROOT, check=True)


def verify_built_archive(version: str) -> tuple[Path, str]:
    zip_path = expected_zip(version)
    hash_path = expected_hash_file(version)
    if not zip_path.is_file() or not hash_path.is_file():
        raise SystemExit("构建未生成正式 ZIP 或 SHA256 文件")
    actual = sha256(zip_path)
    recorded = hash_path.read_text(encoding="utf-8-sig").split(maxsplit=1)[0]
    if actual != recorded:
        raise SystemExit(f"正式包哈希与记录不一致：{actual} != {recorded}")
    return zip_path, actual


def get_token() -> str:
    data = subprocess.check_output(
        ["git", "credential", "fill"],
        cwd=ROOT,
        input="protocol=https\nhost=github.com\n\n",
        text=True,
    )
    password = None
    for line in data.splitlines():
        if line.startswith("password="):
            password = line.split("=", 1)[1]
    if not password:
        raise SystemExit("git credential fill 未返回 token")
    return password


def request(
    method: str,
    url: str,
    token: str,
    body: object | None = None,
    headers: dict[str, str] | None = None,
    data: bytes | None = None,
) -> tuple[int, object]:
    merged_headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    merged_headers.update(headers or {})
    req = urllib.request.Request(url, method=method, headers=merged_headers)
    if data is not None:
        req.data = data
    elif body is not None:
        req.data = json.dumps(body).encode("utf-8")
    try:
        with urllib.request.urlopen(req) as response:
            raw = response.read()
            code = response.status
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        code = exc.code
    try:
        return code, json.loads(raw)
    except Exception:
        return code, raw


def require_remote_tag(api: str, tag: str, local_commit: str, token: str) -> None:
    encoded_tag = urllib.parse.quote(tag, safe="")
    code, ref = request("GET", f"{api}/git/ref/tags/{encoded_tag}", token)
    if code != 200 or not isinstance(ref, dict):
        raise SystemExit(f"远端正式标签 {tag} 不存在或不可读：HTTP {code}")
    obj = ref.get("object", {})
    remote_sha = obj.get("sha") if isinstance(obj, dict) else None
    remote_type = obj.get("type") if isinstance(obj, dict) else None
    if remote_type == "tag" and remote_sha:
        code, annotated = request("GET", f"{api}/git/tags/{remote_sha}", token)
        if code != 200 or not isinstance(annotated, dict):
            raise SystemExit(f"无法解析远端附注标签 {tag}：HTTP {code}")
        target = annotated.get("object", {})
        remote_sha = target.get("sha") if isinstance(target, dict) else None
    if remote_sha != local_commit:
        raise SystemExit(
            f"远端标签 {tag} 指向 {remote_sha}，本地指向 {local_commit}，拒绝发布"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="GitHub Release creator/uploader")
    parser.add_argument("--version", required=True, help="正式版本号，例如 2.6")
    parser.add_argument("--repo", default=DEFAULT_REPO, help="GitHub owner/name")
    args = parser.parse_args()

    if not REPO_PATTERN.fullmatch(args.repo):
        raise SystemExit(f"GitHub 仓库格式无效：{args.repo!r}")
    tag, body_path = ensure_local_preconditions(args.version)
    run_release_gate()
    zip_path, local_hash = verify_built_archive(args.version)

    api = f"https://api.github.com/repos/{args.repo}"
    uploads = f"https://uploads.github.com/repos/{args.repo}"
    token = get_token()
    local_tag_commit = git_output("rev-list", "-n", "1", tag)
    require_remote_tag(api, tag, local_tag_commit, token)
    print("token acquired; local and remote tags verified")

    encoded_tag = urllib.parse.quote(tag, safe="")
    code, existing = request("GET", f"{api}/releases/tags/{encoded_tag}", token)
    publish_when_ready = False
    if code == 200 and isinstance(existing, dict):
        release_id = existing["id"]
        publish_when_ready = bool(existing.get("draft"))
        print(f"release {tag} already exists, reuse id {release_id}")
    elif code == 404:
        list_code, releases = request(
            "GET", f"{api}/releases?per_page=100", token
        )
        if list_code != 200 or not isinstance(releases, list):
            raise SystemExit(f"release list failed: {list_code} {releases}")
        existing = next(
            (
                release
                for release in releases
                if release.get("tag_name") == tag
            ),
            None,
        )
        if existing:
            release_id = existing["id"]
            publish_when_ready = bool(existing.get("draft"))
            print(
                f"unpublished release {tag} already exists, reuse id {release_id}"
            )
        else:
            payload = {
                "tag_name": tag,
                "target_commitish": local_tag_commit,
                "name": tag,
                "body": body_path.read_text(encoding="utf-8-sig").strip(),
                "draft": True,
                "prerelease": False,
            }
            code, created = request("POST", f"{api}/releases", token, body=payload)
            if code != 201 or not isinstance(created, dict):
                raise SystemExit(f"release create failed: {code} {created}")
            release_id = created["id"]
            publish_when_ready = True
            print(f"draft release created id {release_id}")
    else:
        raise SystemExit(f"release lookup failed: {code} {existing}")

    code, asset_list = request("GET", f"{api}/releases/{release_id}/assets", token)
    if code != 200 or not isinstance(asset_list, list):
        raise SystemExit(f"asset list failed: {code} {asset_list}")
    asset_name = ascii_asset_name(args.version)
    existing_asset = next(
        (asset for asset in asset_list if asset.get("name") == asset_name), None
    )
    expected_digest = f"sha256:{local_hash}"
    if existing_asset:
        remote_digest = existing_asset.get("digest")
        remote_size = existing_asset.get("size")
        if remote_digest != expected_digest or remote_size != zip_path.stat().st_size:
            raise SystemExit(
                f"同名附件与本地正式包不一致：digest={remote_digest}, "
                f"size={remote_size}；拒绝静默复用或覆盖"
            )
        asset_id = existing_asset["id"]
        print(f"asset {asset_name} already exists and matches {expected_digest}")
    else:
        query = urllib.parse.urlencode({"name": asset_name})
        code, asset = request(
            "POST",
            f"{uploads}/releases/{release_id}/assets?{query}",
            token,
            headers={"Content-Type": "application/zip"},
            data=zip_path.read_bytes(),
        )
        if code not in (200, 201) or not isinstance(asset, dict):
            raise SystemExit(f"asset upload failed: {code} {asset}")
        asset_id = asset["id"]
        print(f"asset uploaded id {asset_id}; digest {expected_digest}")

    code, result = request(
        "PATCH",
        f"{api}/releases/assets/{asset_id}",
        token,
        body={"label": chinese_label(args.version)},
    )
    if code != 200:
        raise SystemExit(f"label patch failed: {code} {result}")

    if publish_when_ready:
        code, result = request(
            "PATCH",
            f"{api}/releases/{release_id}",
            token,
            body={"draft": False},
        )
        if code != 200:
            raise SystemExit(f"release publish failed: {code} {result}")

    print(f"DONE https://github.com/{args.repo}/releases/tag/{tag}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
