#!/usr/bin/env python3
"""Create a timestamped backup ZIP without changing project evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def included_files() -> list[Path]:
    excluded_parts = {".venv", ".git", "__pycache__"}
    paths: list[Path] = []
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(ROOT)
        if any(part in excluded_parts for part in relative.parts):
            continue
        if relative.parts and relative.parts[0] in {"qa", "qa_updated_docs", "archives"}:
            continue
        if path.suffix.lower() == ".pyc" or path.suffix.lower() == ".zip":
            continue
        paths.append(path)
    return paths


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=ROOT / "archives")
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    archive_path = args.out_dir / f"blocklist_project_backup_{stamp}.zip"
    suffix = 1
    while archive_path.exists():
        archive_path = args.out_dir / f"blocklist_project_backup_{stamp}_{suffix:02d}.zip"
        suffix += 1

    files = included_files()
    archive_name = ROOT.name
    manifest = {
        "schema_version": 1,
        "created_at_utc": utc_now(),
        "project": "Analysis of Public Blocklists from a Danish Perspective",
        "archive_file": archive_path.name,
        "file_count": len(files),
        "contents": [
            {
                "path": f"{archive_name}/{path.relative_to(ROOT)}",
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
            for path in files
        ],
        "excluded": [
            ".venv/",
            ".git/",
            "__pycache__/",
            "qa*/",
            "archives/",
            "existing ZIP files",
        ],
    }
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in files:
            archive.write(path, f"{archive_name}/{path.relative_to(ROOT)}")
        archive.writestr(
            f"{archive_name}/archive_manifest.json",
            json.dumps(manifest, indent=2, ensure_ascii=True) + "\n",
        )

    with zipfile.ZipFile(archive_path) as archive:
        broken = archive.testzip()
    if broken:
        print(f"archive_status=failed")
        print(f"archive_error=corrupt member {broken}")
        return 1
    print("archive_status=created")
    print(f"archive_path={archive_path}")
    print(f"archive_files={len(files)}")
    print(f"archive_bytes={archive_path.stat().st_size}")
    print(f"archive_sha256={sha256(archive_path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
