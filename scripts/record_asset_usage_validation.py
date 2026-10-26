"""Archive a synthetic isolated test run and its exact source identity.

This wrapper records code identities, never environment values or project data.
The existing runner supplies File/Mock isolation and blocks external networking.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--run-root", required=True, type=Path)
    parser.add_argument("--require-clean-code", action="store_true")
    parser.add_argument("tests", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if not args.label.replace("-", "").replace("_", "").isalnum():
        parser.error("label must contain letters, numbers, hyphens or underscores")
    tests = args.tests[1:] if args.tests[:1] == ["--"] else args.tests
    if not tests:
        parser.error("pytest arguments are required after --")
    root = Path(__file__).resolve().parents[1]

    def git(*arguments):
        return subprocess.check_output(["git", *arguments], cwd=root, text=True, encoding="utf-8").strip()

    dirty = git("status", "--porcelain", "--", "app", "scripts", "tests")
    if args.require_clean_code and dirty:
        parser.error("source or tests are not frozen: " + dirty)
    source_paths = git("ls-files", "--cached", "--others", "--exclude-standard", "app/creative", "app/experimental/store.py",
                       "app/services/asset_library_service.py", "scripts/run_studio_backend_tests.py",
                       "scripts/record_asset_usage_validation.py", "tests/*asset_usage*").splitlines()
    hashes = {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
              for name in source_paths if (root / name).is_file()}
    command = [sys.executable, "scripts/run_studio_backend_tests.py", *tests]
    evidence = args.output_dir.resolve()
    evidence.mkdir(parents=True, exist_ok=True)
    log = evidence / (args.label + ".log")
    receipt = {
        "schema_version": 1, "label": args.label,
        "source_commit": git("rev-parse", "HEAD"), "source_tree": git("rev-parse", "HEAD^{tree}"),
        "code_worktree_status": dirty, "source_sha256": hashes,
        "command": command, "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "synthetic File/Mock isolated tests; Actions, PostgreSQL and real model NOT_RUN",
    }
    env = os.environ.copy()
    env["STUDIO_TEST_RUN_ROOT"] = str(args.run_root.resolve())
    started = time.perf_counter()
    with log.open("w", encoding="utf-8", newline="\n") as stream:
        process = subprocess.Popen(command, cwd=root, env=env, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
        assert process.stdout is not None
        for line in process.stdout:
            stream.write(line)
            stream.flush()
            print(line, end="", flush=True)
        code = process.wait()
    after_hashes = {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                    for name in source_paths if (root / name).is_file()}
    after_dirty = git("status", "--porcelain", "--", "app", "scripts", "tests")
    unchanged = after_hashes == hashes and after_dirty == dirty
    receipt.update(exit_code=code, elapsed_seconds=time.perf_counter() - started,
                   completed_at_utc=datetime.now(timezone.utc).isoformat(),
                   source_unchanged_during_run=unchanged, code_worktree_status_after=after_dirty,
                   log_file=log.name, log_sha256=hashlib.sha256(log.read_bytes()).hexdigest())
    receipt_path = evidence / (args.label + ".receipt.json")
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Archived receipt:", receipt_path, flush=True)
    return 2 if args.require_clean_code and not unchanged else code


if __name__ == "__main__":
    raise SystemExit(main())
