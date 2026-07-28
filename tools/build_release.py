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


def mod_version() -> str:
    """Read the mod version from descriptor.mod (single source of truth)."""
    text = (ROOT / "descriptor.mod").read_text(encoding="utf-8-sig")
    match = re.search(r'(?m)^\s*version\s*=\s*"([^"]+)"', text)
    if not match:
        raise SystemExit("无法从 descriptor.mod 读取 version 字段")
    return match.group(1)


def baseline_docs(version: str) -> list[Path]:
    """Baseline documents for the current version, selected by filename.

    Files under docs/baseline are named with their version (e.g.
    README_v2.1_正式版.md), so only the current version's documents are
    bundled into the release ZIP. Missing documents are a warning, not an
    error — but a release should normally add them first.
    """
    directory = ROOT / "docs" / "baseline"
    if not directory.is_dir():
        return []
    return sorted(
        path for path in directory.glob(f"*v{version}_*") if path.is_file()
    )


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
    zip_path = DIST / f"开局一键爽玩_v{version}_正式版.zip"
    hash_path = DIST / f"开局一键爽玩_v{version}_正式版_SHA256.txt"

    docs = baseline_docs(version)
    if not docs:
        raise SystemExit(
            f"docs/baseline 中没有 v{version} 基准文档，拒绝生成正式发布包"
        )

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
