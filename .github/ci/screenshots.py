"""Copy original PNG evidence into bounded, source-labelled artifact groups.

Never edits images or replaces the full original trace/receipt artifact.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil


def collect(root: Path, output: Path, source: str, limit: int = 24 * 1024 * 1024):
    root = root.resolve()
    files = sorted(root.rglob("*.png"))
    groups: list[list[tuple[Path, int]]] = []
    used = 0
    for path in files:
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            raise ValueError("screenshot evidence must remain inside its original root")
        size = path.stat().st_size
        if size > limit:
            raise ValueError("single PNG exceeds bounded artifact size; original remains in full artifact")
        if not groups or used + size > limit:
            groups.append([])
            used = 0
        if len(groups) > 4:
            raise ValueError("PNG evidence exceeds four bounded groups; original remains in full artifact")
        groups[-1].append((path, size))
        used += size
    manifests = []
    for index, group in enumerate(groups, 1):
        destination = output / f"part-{index}"
        destination.mkdir(parents=True, exist_ok=False)
        records = []
        for path, size in group:
            relative = path.relative_to(root)
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
            records.append({"path": relative.as_posix(), "bytes": size,
                            "sha256": hashlib.sha256(target.read_bytes()).hexdigest()})
        manifest = {"source_sha": source, "part": index, "parts": len(groups),
                    "png_bytes": sum(item["bytes"] for item in records),
                    "images_unmodified": True, "full_trace_artifact_retained": True,
                    "files": records}
        (destination / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        manifests.append(manifest)
    return manifests


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source", required=True)
    args = parser.parse_args()
    manifests = collect(args.root, args.output, args.source)
    if destination := os.environ.get("GITHUB_OUTPUT"):
        with open(destination, "a", encoding="utf-8") as result:
            for index in range(1, 5):
                result.write(f"part_{index}={'true' if index <= len(manifests) else 'false'}\n")
    print(json.dumps({"source_sha": args.source, "parts": len(manifests),
                      "png_count": sum(len(item["files"]) for item in manifests)}))
