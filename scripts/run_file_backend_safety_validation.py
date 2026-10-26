"""Archive an immutable synthetic File test group, including actual process exit.

The child invokes the established File/Mock isolation runner. Evidence includes
all tracked app/test/script hashes and loaded app modules, never environment or
user project content. A timeout is a failure even if JUnit was already emitted.
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=900)
    parser.add_argument("--allow-dirty", action="store_true")
    parser.add_argument("tests", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if not args.label.replace("-", "").replace("_", "").isalnum():
        parser.error("label must be a simple filename")
    tests = args.tests[1:] if args.tests[:1] == ["--"] else args.tests
    if not tests:
        parser.error("pytest arguments required after --")
    root = Path(__file__).resolve().parents[1]
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)

    def git(*parts):
        return subprocess.check_output(["git", *parts], cwd=root, text=True, encoding="utf-8").strip()

    def status():
        return git("status", "--porcelain", "--", "app", "tests", "scripts")

    def hashes():
        paths = git("ls-files", "--cached", "--others", "--exclude-standard", "--", "app", "tests", "scripts").splitlines()
        return {p: hashlib.sha256((root / p).read_bytes()).hexdigest()
                for p in paths if (root / p).is_file() and "__pycache__" not in p}

    dirty_before = status()
    if dirty_before and not args.allow_dirty:
        parser.error("source/test/script tree is mutable: " + dirty_before)
    before = hashes()
    loaded_path = output / (args.label + "-loaded-modules.json")
    child_code = r'''
import hashlib,json,os,runpy,sys
from pathlib import Path
source=Path(sys.argv.pop(1));loaded=Path(sys.argv.pop(1))
runner=runpy.run_path(str(source/'scripts/run_studio_backend_tests.py'))
code=1
try:
 code=runner['main']()
finally:
 modules={}
 for name,module in tuple(sys.modules.items()):
  if name=='app' or name.startswith('app.'):
   path=getattr(module,'__file__',None)
   if path and Path(path).is_file():
    p=Path(path).resolve();modules[name]={'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
 loaded.write_text(json.dumps({'pid':os.getpid(),'pytest_return_code':int(code),'modules':modules},indent=2),encoding='utf-8')
sys.exit(code)
'''
    command = [sys.executable, "-c", child_code, str(root), str(loaded_path), *tests]
    env = os.environ.copy()
    env["STUDIO_TEST_RUN_ROOT"] = str(args.run_root.resolve())
    started = time.perf_counter()
    receipt = {"schema_version": 1, "label": args.label,
               "source_commit": git("rev-parse", "HEAD"), "source_tree": git("rev-parse", "HEAD^{tree}"),
               "source_root": str(root), "code_worktree_status_before": dirty_before,
               "source_sha256_before": before, "command": command,
               "started_at_utc": datetime.now(timezone.utc).isoformat(),
               "platform": sys.platform, "timeout_seconds": args.timeout,
               "scope": "synthetic File/Mock; no hosted CI, real model, PostgreSQL or POSIX claim"}
    log_path = output / (args.label + ".log")
    timed_out = False
    with log_path.open("w", encoding="utf-8", newline="\n") as log:
        process = subprocess.Popen(command, cwd=root, env=env, stdout=log, stderr=subprocess.STDOUT)
        try:
            code = process.wait(timeout=args.timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
            else:
                process.kill()
            code = process.wait(timeout=30)
    after = hashes()
    dirty_after = status()
    loaded = json.loads(loaded_path.read_text(encoding="utf-8")) if loaded_path.exists() else None
    external = []
    if loaded:
        external = [name for name, row in loaded["modules"].items()
                    if not Path(row["path"]).is_relative_to(root)]
    valid = (not timed_out and code == 0 and before == after and dirty_before == dirty_after
             and loaded is not None and not external)
    receipt.update(exit_code=code, timed_out=timed_out, process_exited=True,
                   elapsed_seconds=time.perf_counter() - started,
                   completed_at_utc=datetime.now(timezone.utc).isoformat(),
                   source_sha256_after=after, code_worktree_status_after=dirty_after,
                   source_unchanged=before == after and dirty_before == dirty_after,
                   external_app_modules=external, loaded_modules_file=loaded_path.name,
                   log_file=log_path.name, log_sha256=hashlib.sha256(log_path.read_bytes()).hexdigest(),
                   complete_pass=valid)
    receipt_path = output / (args.label + ".receipt.json")
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    tail = log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-18:]
    print("\n".join(tail), flush=True)
    print(json.dumps({"receipt": str(receipt_path), "exit_code": code,
                      "timed_out": timed_out, "complete_pass": valid}), flush=True)
    return 0 if valid else (code if code else 2)


if __name__ == "__main__":
    raise SystemExit(main())
