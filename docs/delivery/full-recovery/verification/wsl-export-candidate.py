"""Byte-preserving tracked/current-source export for isolated Linux validation."""
from __future__ import annotations
import hashlib
import json
import subprocess
import tarfile
from pathlib import Path

root = Path(__file__).resolve().parents[3]
runtime = Path(__file__).resolve().parent
names = subprocess.check_output(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"], cwd=root).split(b"\0")
selected = {}
for raw in names:
    if not raw:
        continue
    name = raw.decode("utf-8")
    path = root / name
    if name.startswith((".runtime/", ".venv/", "docs/delivery/full-recovery/")) or "node_modules" in Path(name).parts:
        continue
    if not path.is_file():
        continue
    assert path.resolve().is_relative_to(root.resolve()), name
    selected[name] = hashlib.sha256(path.read_bytes()).hexdigest()
manifest = root / ".github/ci/coverage_manifest.json.gz"
selected[manifest.relative_to(root).as_posix()] = hashlib.sha256(manifest.read_bytes()).hexdigest()
output = runtime / "candidate-source.tar"
with tarfile.open(output, "w") as archive:
    for name in sorted(selected):
        archive.add(root / name, arcname=name, recursive=False)
inventory = {
    "boundary": "Actual current source bytes; original Git history remains in Windows shared worktree. No checkout, CRLF smudge, runtime, credentials, userdata, venv or node_modules copied.",
    "files": selected,
    "files_digest": hashlib.sha256(json.dumps(selected, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
    "tar_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
}
(runtime / "candidate-source-inventory.json").write_text(json.dumps(inventory, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"files": len(selected), "files_digest": inventory["files_digest"], "tar_sha256": inventory["tar_sha256"]}))
