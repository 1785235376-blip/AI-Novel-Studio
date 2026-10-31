"""Bounded subprocess receipt writer and pytest module-provenance plugin."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def source_manifest(root):
    names = subprocess.check_output(
        ["git", "ls-files", "-z", "--", "app", "tests", "scripts"], cwd=root
    ).decode().split("\0")
    return {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
            for name in names if name and (root / name).is_file()}


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def pytest_sessionfinish(session, exitstatus):
    destination = os.environ.get("INDEPENDENT_FILE_SAFETY_MODULES")
    if not destination:
        return
    paths = {name: str(Path(module.__file__).resolve())
             for name, module in sorted(sys.modules.items())
             if (name == "app" or name.startswith("app.")
                 or name in {"test_file_backend_safety_independent", "file_backend_safety_independent_runner"})
             and getattr(module, "__file__", None)}
    reporter = session.config.pluginmanager.getplugin("terminalreporter")
    write_json(Path(destination), {
        "loaded_modules": paths, "pytest_exitstatus": int(exitstatus),
        "collected": session.testscollected,
        "results": {key: [{"nodeid": getattr(item, "nodeid", None),
                            "when": getattr(item, "when", None)} for item in value]
                    for key, value in reporter.stats.items()},
    })


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--expected-head", required=True)
    parser.add_argument("--timeout", type=int, default=600)
    args = parser.parse_args()
    root, output = args.root.resolve(), args.output.resolve()
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    if head != args.expected_head:
        raise SystemExit("frozen HEAD does not match expected immutable commit")
    status = subprocess.check_output(["git", "status", "--porcelain", "--", "app", "tests", "scripts"], cwd=root, text=True)
    if status:
        raise SystemExit("frozen source contains local changes")
    output.mkdir(parents=True, exist_ok=False)
    before = source_manifest(root)
    write_json(output / "source-before.json", before)
    command = [sys.executable, str(root / "scripts/run_studio_backend_tests.py"),
               "tests/test_file_backend_safety_independent.py", "-q", "-ra",
               "--junitxml=" + str(output / "results.xml")]
    env = os.environ.copy()
    env["PYTEST_PLUGINS"] = "file_backend_safety_independent_runner"
    env["INDEPENDENT_FILE_SAFETY_MODULES"] = str(output / "loaded-modules.json")
    env["STUDIO_TEST_RUN_ROOT"] = str(output / "runtime")
    started = time.time()
    timed_out = False
    with (output / "run.log").open("w", encoding="utf-8") as log:
        try:
            result = subprocess.run(command, cwd=root, env=env, stdout=log,
                                    stderr=subprocess.STDOUT, timeout=args.timeout)
            code = result.returncode
        except subprocess.TimeoutExpired:
            timed_out, code = True, None
    after = source_manifest(root)
    write_json(output / "source-after.json", after)
    modules_file = output / "loaded-modules.json"
    modules = json.loads(modules_file.read_text(encoding="utf-8")) if modules_file.exists() else None
    foreign = [] if modules else ["module provenance receipt missing"]
    if modules:
        for name, path in modules["loaded_modules"].items():
            if not Path(path).is_relative_to(root):
                foreign.append({"module": name, "path": path})
    terminal_ok = bool(modules and modules["pytest_exitstatus"] == 0
                       and modules["collected"] > 0
                       and not any(modules["results"].get(key) for key in ("failed", "error", "skipped", "xfailed", "xpassed")))
    receipt = {"source_head": head, "source_root": str(root), "command": command,
               "timeout_seconds": args.timeout, "timed_out": timed_out,
               "process_exit_code": code, "started_unix": started, "ended_unix": time.time(),
               "source_manifest_unchanged": before == after,
               "foreign_loaded_modules": foreign, "pytest_terminal_ok": terminal_ok,
               "passed": code == 0 and not timed_out and before == after and not foreign and terminal_ok}
    write_json(output / "receipt.json", receipt)
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    return 0 if receipt["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
