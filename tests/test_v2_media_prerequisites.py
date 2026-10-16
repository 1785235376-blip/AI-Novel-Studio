"""Actual bounded child processes for the read-only VIDEO prerequisite helper.

Synthetic executable fixtures test failure handling, not real decoder ability.
The separately named installed-tools test records actual available executables.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

import pytest


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "scripts/v2_media_prerequisites.mjs"


def probe(path=None):
    node = shutil.which("node")
    assert node, "Node is a required engineering test prerequisite"
    code = (f"import {{verifyInstalledMediaTools}} from {json.dumps(HELPER.as_uri())};"
            "try { console.log(JSON.stringify(await verifyInstalledMediaTools())); }"
            "catch(error) { console.log(JSON.stringify(error.receipt)); process.exitCode=1; }")
    env = dict(os.environ)
    if path is not None:
        env["PATH"] = str(path)
    return subprocess.run([node, "--input-type=module", "-e", code], env=env,
                          text=True, capture_output=True, timeout=15, check=False)


def executable(folder, name, behavior="success"):
    source = {
        "success": f"print({name!r} + ' version synthetic-fixture-only')",
        "nonzero": "raise SystemExit(7)",
        "invalid": "print('not a tool version receipt')",
        "timeout": "import time; time.sleep(30)",
        "oversize": "print('x' * 100000)",
    }[behavior]
    file = folder / name
    file.write_text(f"#!{sys.executable}\n{source}\n", encoding="utf-8")
    file.chmod(0o700)


def test_synthetic_success_checks_both_tools_in_order_without_install(tmp_path):
    for name in ("ffmpeg", "ffprobe"):
        executable(tmp_path, name)
    result = probe(tmp_path)
    assert result.returncode == 0, result.stderr
    receipt = json.loads(result.stdout)
    assert receipt["status"] == "PASS"
    assert receipt["mode"] == "EXISTING_TOOLS_ONLY" and receipt["install_attempted"] is False
    assert receipt["timeout_ms_per_tool"] == 5000
    assert [row["tool"] for row in receipt["tools"]] == ["ffmpeg", "ffprobe"]
    assert all(row["status"] == "PASS" and "synthetic-fixture-only" in row["version_output"] for row in receipt["tools"])


@pytest.mark.parametrize("tool", ["ffmpeg", "ffprobe"])
@pytest.mark.parametrize("behavior,reason", [
    ("missing", "MISSING"), ("nonzero", "NONZERO_OR_INVALID_VERSION"),
    ("invalid", "NONZERO_OR_INVALID_VERSION"), ("timeout", "TIMEOUT_OR_OUTPUT_LIMIT"),
    ("oversize", "TIMEOUT_OR_OUTPUT_LIMIT"),
])
def test_synthetic_missing_nonzero_invalid_timeout_and_output_limit_fail_closed(tmp_path, tool, behavior, reason):
    for name in ("ffmpeg", "ffprobe"):
        if name != tool or behavior != "missing":
            executable(tmp_path, name, behavior if name == tool else "success")
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    started = time.monotonic()
    result = probe(tmp_path)
    elapsed = time.monotonic() - started
    assert result.returncode == 1, result.stderr
    receipt = json.loads(result.stdout)
    assert receipt["status"] == "FAIL" and receipt["install_attempted"] is False
    assert receipt["tools"][-1]["tool"] == tool
    assert receipt["tools"][-1]["status"] == "FAIL"
    assert receipt["tools"][-1]["reason"] == reason
    if behavior == "nonzero":
        assert receipt["tools"][-1]["exit_code"] == 7
    if behavior == "timeout":
        assert 4.5 <= elapsed < 10
    if tool == "ffmpeg":
        assert len(receipt["tools"]) == 1  # No later probe after failure.
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == before


def test_actual_installed_ffmpeg_and_ffprobe_versions_are_available():
    # This is genuine local tool evidence, never a hosted-runner claim.
    result = probe()
    assert result.returncode == 0, result.stdout + result.stderr
    receipt = json.loads(result.stdout)
    assert receipt["status"] == "PASS"
    for row in receipt["tools"]:
        assert row["version_output"].startswith(row["tool"] + " version ")
        assert "synthetic-fixture-only" not in row["version_output"]
