#!/usr/bin/env python3
"""Validate and build a deterministic release ZIP from the repository."""

from __future__ import annotations

import csv
import hashlib
import io
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MOD_DIR_NAME = "OCS_one_click_sandbox_start_v2_0"
DIST = ROOT / "dist"
ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)

MOD_ITEMS = (
    "common",
    "events",
    "localisation",
    "descriptor.mod",
    "thumbnail.png",
    "LICENSE",
    "NOTICE.md",
)
BINARY_SUFFIXES = {".png"}


def mod_version() -> str:
    """Read the mod version from descriptor.mod (single source of truth)."""
    text = (ROOT / "descriptor.mod").read_text(encoding="utf-8-sig")
    match = re.search(r'(?m)^\s*version\s*=\s*"([^"]+)"', text)
    if not match:
        raise SystemExit("无法从 descriptor.mod 读取 version 字段")
    return match.group(1)


def is_test_version(version: str) -> bool:
    """Return whether a descriptor version identifies a test build."""
    return "test" in version.casefold()


def package_docs(version: str) -> list[Path]:
    """Select version-matched baseline or testing documents."""
    directory = ROOT / "docs" / ("testing" if is_test_version(version) else "baseline")
    if not directory.is_dir():
        return []
    return sorted(
        path for path in directory.glob(f"*v{version}_*") if path.is_file()
    )


def release_payload_paths(version: str) -> list[Path]:
    """Return repository inputs whose bytes define a release archive."""
    paths = [ROOT / item for item in MOD_ITEMS]
    paths.append(ROOT / "packaging" / f"{MOD_DIR_NAME}.mod")
    paths.extend(package_docs(version))
    return paths


def verify_tagged_release_payload(version: str) -> None:
    """Refuse package drift once a stable version tag exists locally."""
    if is_test_version(version):
        return
    tag = f"v{version}"
    tagged = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", f"refs/tags/{tag}"],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if tagged.returncode:
        return

    relative_paths = [
        str(path.relative_to(ROOT)) for path in release_payload_paths(version)
    ]
    untracked = subprocess.check_output(
        ["git", "ls-files", "--others", "--exclude-standard", "--", *relative_paths],
        cwd=ROOT,
        text=True,
    ).strip()
    if untracked:
        raise SystemExit(f"v{version} 正式包输入含未跟踪文件，拒绝构建：\n{untracked}")

    comparison = subprocess.run(
        ["git", "diff", "--quiet", tag, "--", *relative_paths],
        cwd=ROOT,
        check=False,
    )
    if comparison.returncode == 1:
        changed = subprocess.check_output(
            ["git", "diff", "--name-only", tag, "--", *relative_paths],
            cwd=ROOT,
            text=True,
        ).strip()
        raise SystemExit(
            f"v{version} 已存在正式标签，包输入不得在标签后漂移：\n{changed}"
        )
    if comparison.returncode != 0:
        raise SystemExit(f"无法核对 v{version} 正式标签的包输入")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def copy_item(source: Path, destination: Path) -> None:
    if source.is_dir():
        shutil.copytree(source, destination)
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def normalize_release_text(path: Path) -> None:
    """Normalize staged text bytes without changing BOM or source files."""
    if path.suffix.casefold() in BINARY_SUFFIXES:
        return
    data = path.read_bytes()
    normalized = data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    if normalized != data:
        path.write_bytes(normalized)


def normalize_release_tree(root: Path) -> None:
    """Make release and Workshop staging independent of checkout line endings."""
    for path in sorted(
        (candidate for candidate in root.rglob("*") if candidate.is_file()),
        key=lambda candidate: candidate.relative_to(root).as_posix(),
    ):
        normalize_release_text(path)


def write_deterministic_zip(zip_path: Path, staging: Path) -> None:
    """Write stable bytes by fixing order, timestamps, permissions and storage."""
    files = sorted(
        (path for path in staging.rglob("*") if path.is_file()),
        key=lambda path: path.relative_to(staging).as_posix(),
    )
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_STORED) as archive:
        for path in files:
            archive_name = path.relative_to(staging).as_posix()
            info = zipfile.ZipInfo(archive_name, date_time=ZIP_TIMESTAMP)
            info.compress_type = zipfile.ZIP_STORED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes())


def verify_archive(zip_path: Path) -> int:
    """Verify every payload entry against the embedded manifest."""
    with zipfile.ZipFile(zip_path, "r") as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise SystemExit("发布包内存在重名条目")
        try:
            manifest_data = archive.read("MANIFEST_SHA256.csv")
        except KeyError as exc:
            raise SystemExit("发布包缺少 MANIFEST_SHA256.csv") from exc

        reader = csv.DictReader(
            io.StringIO(manifest_data.decode("utf-8-sig"), newline="")
        )
        expected_fields = ["sha256", "size", "path"]
        if reader.fieldnames != expected_fields:
            raise SystemExit("MANIFEST_SHA256.csv 表头无效")

        verified = 0
        manifest_paths: set[str] = set()
        for row in reader:
            entry_name = row["path"]
            if entry_name in manifest_paths:
                raise SystemExit(f"MANIFEST_SHA256.csv 重复记录：{entry_name}")
            manifest_paths.add(entry_name)
            try:
                data = archive.read(entry_name)
            except KeyError as exc:
                raise SystemExit(f"发布包缺少清单记录的文件：{entry_name}") from exc
            if len(data) != int(row["size"]):
                raise SystemExit(f"发布包文件大小与清单不符：{entry_name}")
            if sha256_bytes(data) != row["sha256"]:
                raise SystemExit(f"发布包文件哈希与清单不符：{entry_name}")
            verified += 1

        payload_names = set(names) - {"MANIFEST_SHA256.csv"}
        if payload_names != manifest_paths:
            extra = sorted(payload_names - manifest_paths)
            missing = sorted(manifest_paths - payload_names)
            raise SystemExit(
                f"发布包与清单条目不一致：未记录 {extra}；缺失 {missing}"
            )
        return verified


def main() -> int:
    validation = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "validate_mod.py")],
        cwd=ROOT,
        check=False,
    )
    if validation.returncode:
        return validation.returncode

    DIST.mkdir(exist_ok=True)
    version = mod_version()
    package_label = "测试版" if is_test_version(version) else "正式版"
    zip_path = DIST / f"开局一键爽玩_v{version}_{package_label}.zip"
    hash_path = DIST / f"开局一键爽玩_v{version}_{package_label}_SHA256.txt"

    docs = package_docs(version)
    if not docs:
        docs_directory = "docs/testing" if is_test_version(version) else "docs/baseline"
        raise SystemExit(
            f"{docs_directory} 中没有 v{version} 配套文档，拒绝生成{package_label}"
        )

    verify_tagged_release_payload(version)
    with tempfile.TemporaryDirectory(prefix="ocs_release_") as temp_name:
        staging = Path(temp_name)
        staged_mod = staging / MOD_DIR_NAME

        for item in MOD_ITEMS:
            copy_item(ROOT / item, staged_mod / item)

        copy_item(
            ROOT / "packaging" / f"{MOD_DIR_NAME}.mod",
            staging / f"{MOD_DIR_NAME}.mod",
        )
        copy_item(ROOT / "LICENSE", staging / "LICENSE")
        copy_item(ROOT / "NOTICE.md", staging / "NOTICE.md")

        for path in docs:
            copy_item(path, staging / path.name)

        normalize_release_tree(staging)

        manifest_path = staging / "MANIFEST_SHA256.csv"
        files = sorted(
            (path for path in staging.rglob("*") if path.is_file()),
            key=lambda path: path.relative_to(staging).as_posix(),
        )
        with manifest_path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(("sha256", "size", "path"))
            for path in files:
                writer.writerow(
                    (
                        sha256(path),
                        path.stat().st_size,
                        path.relative_to(staging).as_posix(),
                    )
                )

        if zip_path.exists():
            zip_path.unlink()
        write_deterministic_zip(zip_path, staging)

    verified_files = verify_archive(zip_path)
    archive_hash = sha256(zip_path)
    hash_path.write_text(
        f"{archive_hash}  {zip_path.name}\n", encoding="utf-8", newline="\n"
    )
    print(f"已生成：{zip_path}")
    print(f"清单验证通过：{verified_files} 个文件")
    print(f"SHA-256：{archive_hash}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
