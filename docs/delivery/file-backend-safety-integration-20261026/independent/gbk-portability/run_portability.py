"""External fixed-A File/Mock isolation overlay; target source stays immutable."""
from __future__ import annotations
import hashlib
import json
import locale
import os
from pathlib import Path
import subprocess
import sys
import time

A = "856d1ed3341fe0c24df1daff9a8bc1242c260e6c"
SELECTORS = [
    "tests/test_taskcenter_collaboration_rebuilt.py::test_legacy_source_is_zero_write_unsupported",
    "tests/test_export_owner_independent_process.py::test_original_export_create_serializes_independent_processes",
]


def write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sources(root):
    names = subprocess.check_output(["git", "ls-files", "-z", "--", "app", "tests", "scripts"], cwd=root).decode().split("\0")
    return {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in names if name}


def child(root, output):
    # No PYTHONUTF8 or locale override: reproduce this machine's actual cp936.
    write(output / "encoding.json", {"locale_encoding": locale.getencoding(),
        "preferred_encoding": locale.getpreferredencoding(False), "utf8_mode": sys.flags.utf8_mode,
        "PYTHONUTF8": os.environ.get("PYTHONUTF8")})
    import pytest
    class Evidence:
        def pytest_sessionfinish(self, session, exitstatus):
            reporter = session.config.pluginmanager.getplugin("terminalreporter")
            write(output / "loaded-modules.json", {"exitstatus": int(exitstatus), "collected": session.testscollected,
                "loaded_modules": {name: str(Path(m.__file__).resolve()) for name, m in sorted(sys.modules.items())
                    if (name == "app" or name.startswith("app.") or name.startswith("test_")) and getattr(m, "__file__", None)},
                "results": {key: [{"nodeid": getattr(item, "nodeid", None), "when": getattr(item, "when", None)} for item in rows]
                    for key, rows in reporter.stats.items()}})
    original_main = pytest.main
    pytest.main = lambda args: original_main(args, plugins=[Evidence()])
    os.environ["STUDIO_TEST_RUN_ROOT"] = str(output / "runtime")
    sys.argv = ["run_studio_backend_tests.py", *SELECTORS, "-q", "-ra", "--junitxml=" + str(output / "results.xml")]
    # Virtual __file__ only makes the original isolation runner use target root.
    # The exact external bytes come from fixed A and are preserved beside receipt.
    namespace = {"__name__": "__main__", "__file__": str(root / "scripts/run_studio_backend_tests.py")}
    exec(compile((output / "runner-from-fixed-A.py").read_bytes(), namespace["__file__"], "exec"), namespace)


def main():
    root, output = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
    if len(sys.argv) > 3 and sys.argv[3] == "--child":
        child(root, output)
        return
    output.mkdir(parents=True, exist_ok=False)
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    status = subprocess.check_output(["git", "status", "--porcelain", "--", "app", "tests", "scripts"], cwd=root, text=True)
    assert not status, "target source must be clean"
    overlay = subprocess.check_output(["git", "show", A + ":scripts/run_studio_backend_tests.py"], cwd=root)
    (output / "runner-from-fixed-A.py").write_bytes(overlay)
    before = sources(root); write(output / "source-before.json", before)
    cmd = [sys.executable, str(Path(__file__).resolve()), str(root), str(output), "--child"]
    start = time.time(); timeout = False
    with (output / "run.log").open("w", encoding="utf-8") as log:
        try:
            result = subprocess.run(cmd, cwd=root, stdout=log, stderr=subprocess.STDOUT, timeout=180)
            code = result.returncode
        except subprocess.TimeoutExpired:
            code, timeout = None, True
    after = sources(root); write(output / "source-after.json", after)
    module_file = output / "loaded-modules.json"
    modules = json.loads(module_file.read_text(encoding="utf-8")) if module_file.exists() else None
    foreign = [name for name, path in modules["loaded_modules"].items() if not Path(path).is_relative_to(root)] if modules else ["missing receipt"]
    receipt = {"source_head": head, "source_root": str(root), "command": cmd, "selectors": SELECTORS,
        "isolation_overlay_source": A + ":scripts/run_studio_backend_tests.py",
        "isolation_overlay_sha256": hashlib.sha256(overlay).hexdigest(), "overlay_written_to_target": False,
        "process_exit_code": code, "timeout_seconds": 180, "timed_out": timeout,
        "started_unix": start, "ended_unix": time.time(), "source_manifest_unchanged": before == after,
        "foreign_loaded_modules": foreign}
    write(output / "receipt.json", receipt); print(json.dumps(receipt, indent=2))
    return 0 if code == 0 and not timeout and before == after and not foreign else 1


if __name__ == "__main__":
    raise SystemExit(main())
