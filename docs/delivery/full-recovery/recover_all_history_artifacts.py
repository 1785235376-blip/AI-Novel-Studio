"""Recover exact historical Actions ZIP bytes into the explicitly named external archive.

Four binary gh-api downloads; no extraction, execution, browser credentials or signed-URL logging.
Existing verified PR45 archives are reused. Failed bytes/receipts remain immutable for review.
This evidence utility is outside the frozen product-source inputs.
"""
from __future__ import annotations

import concurrent.futures
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import threading
import time
import uuid
import zipfile

EVIDENCE = Path(__file__).resolve().parent
DEST = Path(r"D:\小说\AI-Novel-Studio-Recovery-Assets\all-history")
PR45 = Path(r"D:\小说\AI-Novel-Studio-Recovery-Assets\pr45-6658172")
REPOSITORY = "1785235376-blip/AI-Novel-Studio"
WORKERS = 4
MAX_ATTEMPTS = 3
TIMEOUT_SECONDS = 900
LOCK = threading.Lock()


def now():
    return datetime.now(timezone.utc).isoformat()


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def contained(path: Path, root: Path = DEST):
    actual, allowed = path.resolve(), root.resolve()
    if not actual.is_relative_to(allowed):
        raise ValueError("archive path escapes explicitly authorized directory")
    return actual


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write_atomic(path, value):
    path = contained(path)
    temporary = contained(path.with_name(path.name + ".tmp"))
    temporary.write_text(encoded(value) + "\n", encoding="utf-8", newline="\n")
    temporary.replace(path)


def safe_error(raw):
    text = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else str(raw)
    text = re.sub(r"https?://[^\s]+", "[redacted-url]", text)
    text = re.sub(r"(?im)(?:authorization|cookie|x-session-token|gh_token|github_token)\s*[:=]\s*[^\r\n]+", "[redacted-header]", text)
    return text[:1200]


def append_event(value):
    with LOCK:
        with contained(DEST / "progress.jsonl").open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(encoded({"at": now(), **value}) + "\n")


def archive_check(path, item):
    expected = item["digest"].removeprefix("sha256:")
    actual = digest(path)
    if actual != expected:
        return {"status": "DIGEST_MISMATCH", "sha256": actual, "github_digest": item["digest"], "bytes": path.stat().st_size}
    try:
        with zipfile.ZipFile(path) as archive:
            corrupt = archive.testzip()
            members = len(archive.infolist())
        if corrupt is not None:
            return {"status": "CRC_FAILED", "corrupt_member": corrupt, "sha256": actual, "bytes": path.stat().st_size}
    except (OSError, ValueError, zipfile.BadZipFile, NotImplementedError, RuntimeError) as failure:
        return {"status": "ZIP_CHECK_FAILED", "error_type": type(failure).__name__, "sha256": actual, "bytes": path.stat().st_size}
    return {"status": "VERIFIED", "sha256": actual, "github_digest": item["digest"], "bytes": path.stat().st_size,
            "zip_crc": "PASS", "members": members, "archive_path": str(path.resolve()), "verified_at": now()}


def preserve_red(path, artifact_id, label):
    source = contained(path)
    target = contained(DEST / "RED" / str(artifact_id) / (label + "-" + uuid.uuid4().hex + ".zip.part"))
    target.parent.mkdir(parents=True, exist_ok=True)
    source.rename(target)
    return str(target)


def base_receipt(item):
    run = item.get("workflow_run", {})
    return {"id": item["id"], "name": item["name"], "run_id": run.get("id"), "head_sha": run.get("head_sha"),
            "metadata_bytes": item["size_in_bytes"], "github_digest": item["digest"], "created_at": item.get("created_at"),
            "expires_at": item.get("expires_at"), "extraction_performed": False}


def recover(item, known):
    artifact_id = item["id"]
    base = base_receipt(item)
    final = contained(DEST / (str(artifact_id) + ".zip"))
    # Re-check existing bytes before accepting the resume/reuse receipt. Never re-download a valid archive.
    if artifact_id in known:
        archive = contained(Path(known[artifact_id]["archive_path"]), PR45)
        if archive.is_file():
            result = archive_check(archive, item)
            if result["status"] == "VERIFIED":
                return {**base, **result, "disposition": "REUSED_VERIFIED_PR45"}
            append_event({"type": "PR45_REUSE_RED", "id": artifact_id, **result})
        else:
            append_event({"type": "PR45_REUSE_MISSING", "id": artifact_id})
    if final.is_file():
        result = archive_check(final, item)
        if result["status"] == "VERIFIED":
            return {**base, **result, "disposition": "REUSED_VERIFIED_ALL_HISTORY"}
        red = preserve_red(final, artifact_id, "existing-invalid")
        append_event({"type": "EXISTING_ARCHIVE_RED", "id": artifact_id, **result, "preserved_bytes": red})
    attempts = []
    for attempt in range(1, MAX_ATTEMPTS + 1):
        stage = contained(DEST / "inflight" / (str(artifact_id) + "-" + uuid.uuid4().hex + ".zip.part"))
        stage.parent.mkdir(parents=True, exist_ok=True)
        append_event({"type": "DOWNLOAD_STARTED", "id": artifact_id, "attempt": attempt})
        started = time.monotonic()
        code = None
        try:
            with stage.open("xb") as stream:
                result = subprocess.run(["gh", "api", f"repos/{REPOSITORY}/actions/artifacts/{artifact_id}/zip"],
                                        stdout=stream, stderr=subprocess.PIPE, timeout=TIMEOUT_SECONDS, check=False)
            code, stderr = result.returncode, result.stderr
            if code:
                match = re.search(rb"HTTP\s+(\d{3})", stderr)
                status = int(match.group(1)) if match else None
                observation = {"status": "DOWNLOAD_FAILED", "gh_exit_code": code, "http_status": status,
                               "safe_error": safe_error(stderr), "bytes": stage.stat().st_size}
            else:
                observation = archive_check(stage, item)
        except subprocess.TimeoutExpired:
            observation = {"status": "DOWNLOAD_TIMEOUT", "bytes": stage.stat().st_size}
        except Exception as failure:
            observation = {"status": "DOWNLOAD_EXCEPTION", "error_type": type(failure).__name__,
                           "safe_error": safe_error(failure), "bytes": stage.stat().st_size if stage.exists() else 0}
        observation.update(attempt=attempt, seconds=round(time.monotonic() - started, 3))
        if observation["status"] == "VERIFIED":
            if final.exists():
                raise ValueError("unexpected concurrent archive replacement")
            stage.rename(final)
            observation["archive_path"] = str(final)
            return {**base, **observation, "disposition": "DOWNLOADED_AND_VERIFIED", "prior_attempts": attempts}
        if stage.exists():
            observation["preserved_bytes"] = preserve_red(stage, artifact_id, "attempt-" + str(attempt))
        attempts.append(observation)
        append_event({"type": "ATTEMPT_RED", "id": artifact_id, **observation})
        # Missing/expired archives cannot be recreated from metadata. Keep their actual failure and do not hammer the API.
        if observation.get("http_status") in (401, 404, 410):
            break
        if attempt < MAX_ATTEMPTS:
            time.sleep(2 ** attempt)
    return {**base, "status": attempts[-1]["status"], "attempts": attempts, "disposition": "UNRECOVERED"}


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    contained(DEST)
    pages = json.loads((EVIDENCE / "actions-artifacts.json").read_text(encoding="utf-8-sig"))
    items = [item for page in pages for item in page["artifacts"]]
    if len(items) != len({item["id"] for item in items}):
        raise ValueError("duplicate historical artifact IDs")
    for item in items:
        if type(item["id"]) is not int or item["id"] <= 0 or not re.fullmatch(r"sha256:[0-9a-f]{64}", item.get("digest", "")):
            raise ValueError("artifact ID/digest does not satisfy strict input contract")
    known = {item["id"]: item for item in json.loads((EVIDENCE / "pr45-artifact-verification.json").read_text(encoding="utf-8-sig")) if item["status"] == "VERIFIED"}
    needed = sum(item["size_in_bytes"] for item in items if item["id"] not in known and not contained(DEST / (str(item["id"]) + ".zip")).exists())
    free = shutil.disk_usage(DEST).free
    if free < needed + 2 * 1024 ** 3:
        raise ValueError("insufficient disk capacity for remaining immutable archives")
    preflight = {"status": "RUNNING", "artifacts": len(items), "known_pr45": len(known), "workers": WORKERS,
                 "expected_metadata_bytes": sum(item["size_in_bytes"] for item in items), "remaining_metadata_bytes": needed,
                 "free_bytes_at_start": free, "destination": str(DEST.resolve()), "started_at": now(),
                 "extraction_performed": False, "signed_urls_logged": False, "headers_logged": False}
    write_atomic(DEST / "preflight.json", preflight)
    append_event({"type": "PREFLIGHT", **preflight})
    results = {}
    start = time.monotonic()
    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = {pool.submit(recover, item, known): item for item in sorted(items, key=lambda item: (item["id"] not in known, item["id"]))}
        for future in concurrent.futures.as_completed(futures):
            item = futures[future]
            try:
                row = future.result()
            except Exception as failure:
                row = {**base_receipt(item), "status": "UNCAUGHT_FAILURE", "error_type": type(failure).__name__, "safe_error": safe_error(failure)}
            results[row["id"]] = row
            append_event({"type": "ARCHIVE_RESULT", **row})
            summary = {**preflight, "completed": len(results), "verified": sum(result["status"] == "VERIFIED" for result in results.values()),
                       "failed": sum(result["status"] != "VERIFIED" for result in results.values()),
                       "verified_bytes": sum(result.get("bytes", 0) for result in results.values() if result["status"] == "VERIFIED"),
                       "elapsed_seconds": round(time.monotonic() - start, 3), "updated_at": now()}
            write_atomic(DEST / "summary.json", summary)
            write_atomic(DEST / "verification.json", sorted(results.values(), key=lambda result: result["id"]))
            if len(results) % 50 == 0 or len(results) == len(items):
                print(encoded({key: summary[key] for key in ("completed", "artifacts", "verified", "failed", "verified_bytes", "elapsed_seconds")}), flush=True)
    summary["status"] = "COMPLETE" if summary["verified"] == len(items) else "PARTIAL"
    summary["finished_at"] = now()
    write_atomic(DEST / "summary.json", summary)
    append_event({"type": "FINAL_SUMMARY", **summary})
    print(encoded(summary), flush=True)


if __name__ == "__main__":
    main()
