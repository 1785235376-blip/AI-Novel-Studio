"""Recover public exact-head artifacts; keep large immutable archives outside Git."""
from __future__ import annotations

import concurrent.futures
import hashlib
import json
import pathlib
import subprocess
import zipfile

ROOT = pathlib.Path(__file__).resolve().parent
DEST = pathlib.Path(r"D:\小说\AI-Novel-Studio-Recovery-Assets\pr45-6658172")
DEST.mkdir(parents=True, exist_ok=True)
ARTIFACTS = json.loads((ROOT / "pr45-artifacts.json").read_text(encoding="utf-8-sig"))


def recover(item: dict) -> dict:
    archive = DEST / f"{item['id']}-{item['name']}.zip"
    expected = item.get("digest", "").removeprefix("sha256:")
    if not archive.exists():
        with archive.open("wb") as out:
            proc = subprocess.run(
                ["gh", "api", f"repos/1785235376-blip/AI-Novel-Studio/actions/artifacts/{item['id']}/zip"],
                stdout=out, stderr=subprocess.PIPE, check=False,
            )
        if proc.returncode:
            return {"id": item["id"], "name": item["name"], "status": "DOWNLOAD_FAILED", "bytes": archive.stat().st_size}
    actual = hashlib.file_digest(archive.open("rb"), "sha256").hexdigest()
    if actual != expected:
        return {"id": item["id"], "name": item["name"], "status": "DIGEST_MISMATCH", "expected": expected, "actual": actual}
    with zipfile.ZipFile(archive) as zf:
        corrupt = zf.testzip()
        members = [{"name": f.filename, "bytes": f.file_size, "crc": f.CRC} for f in zf.infolist()]
    return {
        "id": item["id"], "name": item["name"], "status": "VERIFIED" if corrupt is None else "CRC_FAILED",
        "run_id": item["workflow_run"]["id"], "archive_path": str(archive),
        "bytes": archive.stat().st_size, "sha256": actual, "github_digest": item["digest"],
        "expires_at": item["expires_at"], "members": members,
    }


results = []
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
    futures = [pool.submit(recover, item) for item in ARTIFACTS]
    for future in concurrent.futures.as_completed(futures):
        result = future.result()
        results.append(result)
        print(f"{result['id']} {result['status']} {result['name']}", flush=True)
        (ROOT / "pr45-artifact-verification.json").write_text(
            json.dumps(sorted(results, key=lambda r: r["id"]), ensure_ascii=False, indent=2), encoding="utf-8"
        )
print(json.dumps({"artifacts": len(results), "verified": sum(r["status"] == "VERIFIED" for r in results),
                  "bytes": sum(r.get("bytes", 0) for r in results)}), flush=True)
