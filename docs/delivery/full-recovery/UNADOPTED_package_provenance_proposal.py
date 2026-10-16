"""Compose verified base inputs with only the package's declared Launcher overlays."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import stat

OVERLAYS = {
    "Launcher/Launch-AI-Novel-Studio.ps1": "scripts/installer/Launch-AI-Novel-Studio.ps1",
    "Launcher/Launch-AI-Novel-Studio.cmd": "scripts/installer/Launch-AI-Novel-Studio.cmd",
    "Launcher/Uninstall-AI-Novel-Studio.ps1": "scripts/installer/Uninstall-AI-Novel-Studio.ps1",
}
PROVENANCE = "base-input-provenance.json"
PARENT_ARCHIVE = "base-input-provenance.original.json"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def checked_path(root: Path, relative: str) -> Path:
    path = root / relative
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("Provenance path escapes its declared root")
    for item in (root, *path.relative_to(root).parents):
        candidate = item if item == root else root / item
        if candidate.exists():
            info = candidate.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
                raise ValueError("Provenance input contains a link or reparse point")
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
        raise ValueError("Provenance input contains a link or reparse point")
    if not path.is_file():
        raise ValueError("Provenance input is not a regular file")
    return path


def compose(application: Path, source_root: Path) -> dict:
    application = application.absolute()
    source_root = source_root.absolute()
    parent_path = checked_path(application, PROVENANCE)
    parent_bytes = parent_path.read_bytes()
    parent = json.loads(parent_bytes)
    archive = application / PARENT_ARCHIVE
    if archive.exists():
        raise ValueError("Package provenance composition requires a fresh parent archive")
    original_entries = {}
    for item in parent["files"]:
        name = item["path"].replace("\\", "/")
        if name in original_entries:
            raise ValueError("Duplicate parent provenance entry")
        original_entries[name] = copy.deepcopy(item)
        path = checked_path(application, name)
        data = path.read_bytes()
        if name not in OVERLAYS and (len(data) != item["size"] or digest(data) != item["sha256"]):
            raise ValueError("Unchanged base input differs: " + name)
    overlays = []
    for destination, source_name in OVERLAYS.items():
        source_bytes = checked_path(source_root, source_name).read_bytes()
        staged_bytes = checked_path(application, destination).read_bytes()
        if staged_bytes != source_bytes:
            raise ValueError("Declared Launcher overlay differs from its source: " + destination)
        overlays.append({"destination_path": destination, "source_path": source_name,
                         "source_sha256": digest(source_bytes), "staged_sha256": digest(staged_bytes),
                         "size": len(staged_bytes), "original_base_entry": original_entries.get(destination)})
    # Preserve every original expected hash before composing the generated
    # package inventory. No arbitrary base mismatch is rebound to current bytes.
    archive.write_bytes(parent_bytes)
    inventory = []
    for path in sorted(application.rglob("*")):
        if not path.is_file() or path == parent_path or "__pycache__" in path.parts:
            continue
        name = path.relative_to(application).as_posix()
        data = checked_path(application, name).read_bytes()
        inventory.append({"path": name, "size": len(data), "sha256": digest(data)})
    result = copy.deepcopy(parent)
    result["kind"] = "composed-windows-application-inputs"
    result["files"] = inventory
    result["package_composition"] = {
        "parent_base_provenance_archive": PARENT_ARCHIVE,
        "parent_base_provenance_sha256": digest(parent_bytes),
        "original_base_files": len(parent["files"]),
        "unchanged_base_inputs_verified": True,
        "source_owned_overlays": overlays,
        "rule": "Only the three fixed source-owned Launcher destinations may supersede a parent entry; all other original size/hash expectations are enforced",
    }
    parent_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--application", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    args = parser.parse_args()
    result = compose(args.application, args.source_root)
    print(json.dumps({"status": "PASS", "files": len(result["files"]), "package_composition": result["package_composition"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
