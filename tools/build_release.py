#!/usr/bin/env python3
"""Validate and build a reproducible-style release ZIP from the repository."""

from __future__ import annotations

import csv
import hashlib
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MOD_DIR_NAME = "OCS_one_click_sandbox_start_v2_0"
DIST = ROOT / "dist"

MOD_ITEMS = (
    "common",
    "events",
    "localisation",
    "descriptor.mod",
    "thumbnail.png",
    "LICENSE",
    "NOTICE.md",
)

BASELINE_DOCS = (
    "README_v2.0_正式版.md",
    "v2.0_正式版实施清单.json",
    "v2.0_正式版静态复核.json",
    "v2.0_正式版静态复核.md",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def copy_item(source: Path, destination: Path) -> None:
    if source.is_dir():
        shutil.copytree(source, destination)
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def main() -> int:
    validation = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "validate_mod.py")],
        cwd=ROOT,
        check=False,
    )
    if validation.returncode:
        return validation.returncode

    DIST.mkdir(exist_ok=True)
    zip_path = DIST / "开局一键爽玩_v2.1_正式版.zip"
    hash_path = DIST / "开局一键爽玩_v2.1_正式版_SHA256.txt"

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

        baseline = ROOT / "docs" / "baseline"
        for name in BASELINE_DOCS:
            copy_item(baseline / name, staging / name)

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
        with zipfile.ZipFile(
            zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
        ) as archive:
            for path in sorted(
                (path for path in staging.rglob("*") if path.is_file()),
                key=lambda path: path.relative_to(staging).as_posix(),
            ):
                archive.write(path, path.relative_to(staging).as_posix())

    archive_hash = sha256(zip_path)
    hash_path.write_text(
        f"{archive_hash}  {zip_path.name}\n", encoding="utf-8", newline="\n"
    )
    print(f"已生成：{zip_path}")
    print(f"SHA-256：{archive_hash}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
