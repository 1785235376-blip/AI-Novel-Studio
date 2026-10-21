"""Real synthetic CPU artifacts across independent File-owner processes.

No PostgreSQL substitute: these contracts intentionally exercise File only.
Existing feature-test fixtures enable the local feature flags; provider/Host
controls remain deny-only. FFmpeg/Pillow here inspect real bytes.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

import pytest

pytestmark = pytest.mark.file_backend_only
ROOT = Path(__file__).resolve().parents[1]
WORKER = Path(__file__).with_name("studio_file_process_probe.py")


def worker_env():
    keys = ("PATH", "SystemRoot", "WINDIR", "COMSPEC", "TEMP", "TMP", "PATHEXT", "USERPROFILE")
    env = {key: os.environ[key] for key in keys if key in os.environ}
    env.update(PROJECT_ROOT=str(ROOT), LOCALAPPDATA=str(ROOT / ".runtime" / "process-localapp"),
        NOVEL_DATA_PATH=str(ROOT / ".runtime" / "process-global-data"), STORAGE_BACKEND="file",
        EXPERIMENTAL_FEATURES="narrative_production_v2,asset_lineage_v2", ENABLE_CLOUD="false",
        MOCK_PROVIDER="true", PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8")
    return env


def start(case, phase, *, kind="image", label=None):
    case.mkdir(parents=True, exist_ok=True); label = label or phase
    log = (case / (label + ".log")).open("wb")
    process = subprocess.Popen([sys.executable, str(WORKER), phase, str(case), "--kind", kind, "--label", label],
        cwd=ROOT, env=worker_env(), stdout=log, stderr=subprocess.STDOUT)
    return process, log, label


def finish(case, task):
    process, log, label = task
    try:
        code = process.wait(timeout=55)
    except subprocess.TimeoutExpired:
        process.kill(); process.wait(); raise
    finally:
        log.close()
    assert code == 0, (case / (label + ".log")).read_text(encoding="utf-8")
    return json.loads((case / (label + ".json")).read_text(encoding="utf-8"))


def run(case, phase, **kw):
    return finish(case, start(case, phase, **kw))


@pytest.mark.parametrize("kind", ["audio", "video", "image"])
def test_cpu_candidate_cold_review_return_and_history_restore(tmp_path, kind):
    assert shutil.which("ffmpeg") and shutil.which("ffprobe"), "installed CPU decoders required"
    case = tmp_path / kind
    rows = [run(case, "prepare", kind=kind)]
    rows.extend(run(case, phase) for phase in ["review", "adopt", "restore", "verify"])
    assert len({row["pid"] for row in rows}) == 5
    assert [row["status"] for row in rows] == ["PRIVATE_CANDIDATE_ON_DISK", "APPROVED_WITHOUT_AUTO_ADOPTION",
        "ADOPTED", "RESTORED_AS_NEW_VERSION", "COLD_READ_HISTORY_AND_PIN_PASS"]
    assert rows[0]["output_sha256"] == rows[-1]["output_sha256"]
    assert all(row["provider_called"] is False and row["backend"] == "file" for row in rows)


def test_two_cold_processes_cannot_both_adopt_the_same_canvas_version(tmp_path):
    case = tmp_path / "cas"
    run(case, "prepare"); run(case, "review")
    tasks = [start(case, "adopt-race", label="writer-" + str(i)) for i in range(2)]
    try:
        deadline = time.monotonic() + 25
        while not all((case / ("writer-" + str(i) + ".ready")).exists() for i in range(2)):
            assert time.monotonic() < deadline, "writers did not reach simultaneous CAS barrier"
            assert all(task[0].poll() is None for task in tasks), "writer exited before the CAS barrier"
            time.sleep(0.01)
        (case / "adopt.go").write_text("go", encoding="ascii")
        results = [finish(case, task) for task in tasks]
    finally:
        for process, log, _ in tasks:
            if process.poll() is None:process.kill(); process.wait()
            if not log.closed:log.close()
    assert sorted(row["status"] for row in results) == ["ADOPTED", "CAS_REJECTED"]
    run(case, "restore"); result = run(case, "verify")
    assert result["versions"] == [1, 2, 3]


def test_source_revision_in_another_process_blocks_cold_review(tmp_path):
    case = tmp_path / "source-pin"
    run(case, "prepare"); run(case, "change-source")
    result = run(case, "reject-review")
    assert result["status"] == "STALE_REVIEW_REJECTED_NO_PROMOTION"


def test_file_transaction_body_exception_is_rolled_back_for_a_cold_reader(tmp_path):
    case = tmp_path / "rollback"
    run(case, "prepare"); first = run(case, "rollback"); second = run(case, "verify-rollback")
    assert first["pid"] != second["pid"]
    assert first["status"] == "BODY_EXCEPTION_ROLLBACK_AND_RELEASE_PASS"
    assert second["status"] == "COLD_ROLLBACK_READ_PASS"
