from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("r2_native_verifier", ROOT / "scripts/verify_windows_base.py")
verifier = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verifier)


def test_real_file_capture_does_not_wait_for_descendant_eof(tmp_path, capsys):
    marker = tmp_path / "descendant-can-exit"
    done = tmp_path / "descendant-exited"
    descendant = (
        "import pathlib,time; "
        f"p=pathlib.Path({str(marker)!r}); d=pathlib.Path({str(done)!r}); "
        "deadline=time.monotonic()+10; "
        "exec('while not p.exists() and time.monotonic()<deadline: time.sleep(0.02)'); "
        "d.write_text('done')"
    )
    parent = f"import subprocess,sys; subprocess.Popen([sys.executable,'-c',{descendant!r}]); print('parent-done',flush=True)"
    commands = []
    try:
        value = verifier.run_native_command([sys.executable, "-c", parent], root=tmp_path,
                                            environment=os.environ.copy(), commands=commands, timeout=3)
        assert value == "parent-done"
        assert not done.exists(), "Parent completed while descendant still held inherited output"
    finally:
        marker.touch()
        import time
        deadline = time.monotonic() + 12
        while not done.exists() and time.monotonic() < deadline:
            time.sleep(0.02)
    assert done.exists(), "The synthetic descendant must finish without being left behind"
    assert commands[0]["status"] == "PASS"
    assert commands[0]["stdout_file"] == "command-logs/001.stdout.log"
    progress = capsys.readouterr().out
    assert "command_start" in progress and "command_complete" in progress
    assert str(tmp_path) not in progress


def test_real_timeout_stays_failed_with_bounded_direct_child_cleanup(tmp_path, capsys):
    commands = []
    with pytest.raises(subprocess.TimeoutExpired):
        verifier.run_native_command([sys.executable, "-c", "import time; print('started',flush=True); time.sleep(30)"],
                                    root=tmp_path, environment=os.environ.copy(), commands=commands, timeout=0.2)
    entry = commands[0]
    assert entry["status"] == "TIMEOUT"
    assert entry["timeout_cleanup"]["parent_exited"] is True
    assert "started" in entry["stdout"]
    assert "command_timeout" in capsys.readouterr().out


def test_nonzero_exit_retains_file_output_and_is_not_success(tmp_path):
    commands = []
    with pytest.raises(RuntimeError, match="synthetic-error"):
        verifier.run_native_command([sys.executable, "-c", "import sys; print('synthetic-error',file=sys.stderr); sys.exit(7)"],
                                    root=tmp_path, environment=os.environ.copy(), commands=commands)
    assert commands[0]["exit_code"] == 7
    assert commands[0]["status"] == "FAILED"


def test_windows_timeout_targets_only_the_still_owned_pid_tree(monkeypatch, tmp_path):
    monkeypatch.setattr(verifier.sys, "platform", "win32")
    calls = []
    process = SimpleNamespace(pid=187654, returncode=None)
    process.poll = lambda: process.returncode
    process.kill = lambda: calls.append("direct-handle-fallback")
    process.wait = lambda timeout: 0

    def fake_run(arguments, **kwargs):
        calls.append((arguments, kwargs))
        process.returncode = 1
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(verifier.subprocess, "run", fake_run)
    with (tmp_path / "out").open("wb") as out, (tmp_path / "err").open("wb") as err:
        evidence = verifier.terminate_owned_command(process, {"SystemRoot": str(tmp_path)}, out, err)
    assert len(calls) == 1
    arguments, kwargs = calls[0]
    assert arguments == [str(tmp_path / "System32/taskkill.exe"), "/PID", "187654", "/T", "/F"]
    assert "/IM" not in arguments
    assert kwargs["timeout"] == 10
    assert kwargs["stdout"] is not subprocess.PIPE and kwargs["stderr"] is not subprocess.PIPE
    assert evidence["tree_cleanup"] == "TASKKILL_REPORTED_SUCCESS"
    assert evidence["parent_exited"] is True


def test_already_exited_parent_does_not_kill_reused_or_unrelated_pid(monkeypatch):
    monkeypatch.setattr(verifier.sys, "platform", "win32")
    monkeypatch.setattr(verifier.subprocess, "run", lambda *a, **k: pytest.fail("No taskkill after parent exit"))
    process = SimpleNamespace(pid=187654, poll=lambda: 0)
    evidence = verifier.terminate_owned_command(process, {"SystemRoot": "unused"}, None, None)
    assert evidence == {"pid": 187654, "parent_exited": True, "tree_cleanup": "NOT_VERIFIED"}


def fake_application(tmp_path, monkeypatch, *, fail_at=None, timeout_initdb=False, fail_stop=False):
    monkeypatch.setattr(verifier.sys, "platform", "win32")
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    windows = tmp_path / "windows"
    (windows / "System32").mkdir(parents=True)
    for name in ("msvcp140.dll", "vcruntime140.dll"):
        (windows / "System32" / name).write_bytes(b"synthetic-crt")
    monkeypatch.setenv("SystemRoot", str(windows))
    base = tmp_path / "application"
    base.mkdir()
    (base / "base-input-provenance.json").write_text(json.dumps({"files": [], "inputs": {"wheels": []}}))
    root = tmp_path / "smoke"
    calls = []

    def fake_command(arguments, **kwargs):
        args = [str(value) for value in arguments]
        executable = Path(args[0]).name
        calls.append(args)
        kwargs["commands"].append({"executable": executable, "status": "SYNTHETIC"})
        if executable == "python.exe":
            return json.dumps({"python": [3, 12, 9], "packages": {}, "psycopg_impl": "binary", "isolated": 1})
        if executable == "postgres.exe":
            return "postgres (PostgreSQL) 16.15"
        if executable == "initdb.exe":
            data = Path(args[args.index("-D") + 1])
            data.mkdir()
            if timeout_initdb:
                (data / "postmaster.pid").write_text("synthetic-owned-child")
                raise subprocess.TimeoutExpired(args, 60)
        if executable == "pg_ctl.exe":
            data = Path(args[args.index("-D") + 1])
            if args[-1] == "start":
                (data / "postmaster.pid").write_text("synthetic-owned-child")
            if args[-1] == "stop":
                if fail_stop:
                    raise RuntimeError("synthetic-owned-stop-failure")
                (data / "postmaster.pid").unlink(missing_ok=True)
        if executable == fail_at:
            raise RuntimeError("synthetic-native-failure")
        return "中文验证" if executable == "psql.exe" and "-tAc" in args else ""

    monkeypatch.setattr(verifier, "run_native_command", fake_command)
    return base, root, calls


@pytest.mark.parametrize("fail_at,timeout_initdb", [("createdb.exe", False), (None, True)])
def test_owned_cluster_stop_and_failure_receipt_are_preserved(tmp_path, monkeypatch, fail_at, timeout_initdb):
    base, root, calls = fake_application(tmp_path, monkeypatch, fail_at=fail_at, timeout_initdb=timeout_initdb)
    with pytest.raises((RuntimeError, subprocess.TimeoutExpired)):
        verifier.verify(base, root)
    stop = [args for args in calls if Path(args[0]).name == "pg_ctl.exe" and args[-1] == "stop"]
    assert len(stop) == 1
    assert stop[0][stop[0].index("-D") + 1] == str(root / "postgres-data")
    receipt = json.loads((root / "native-base-smoke.json").read_text())
    assert receipt["status"] == "FAILED"
    assert receipt["interactive_desktop"] == "NOT_RUN"


def test_failure_before_cluster_creation_does_not_stop_any_database(tmp_path, monkeypatch):
    base, root, calls = fake_application(tmp_path, monkeypatch, fail_at="initdb.exe")
    with pytest.raises(RuntimeError):
        verifier.verify(base, root)
    assert not any(Path(args[0]).name == "pg_ctl.exe" for args in calls)
    assert json.loads((root / "native-base-smoke.json").read_text())["status"] == "FAILED"


def test_owned_shutdown_failure_still_writes_failed_receipt(tmp_path, monkeypatch):
    base, root, calls = fake_application(tmp_path, monkeypatch, fail_stop=True)
    with pytest.raises(RuntimeError, match="synthetic-owned-stop-failure"):
        verifier.verify(base, root)
    receipt = json.loads((root / "native-base-smoke.json").read_text())
    assert receipt["status"] == "FAILED"
    assert receipt["shutdown_error"] == "synthetic-owned-stop-failure"


def test_success_closes_only_owned_cluster_and_never_promotes_gui_acceptance(tmp_path, monkeypatch):
    base, root, calls = fake_application(tmp_path, monkeypatch)
    receipt = verifier.verify(base, root)
    assert receipt["status"] == "PASS"
    assert receipt["interactive_desktop"] == "NOT_RUN"
    assert receipt["user_acceptance"] == "NOT_RUN"
    assert not (root / "postgres-data/postmaster.pid").exists()
    assert calls[-1][-1] == "stop"


def test_existing_work_root_cannot_reuse_real_data(tmp_path, monkeypatch):
    base, root, calls = fake_application(tmp_path, monkeypatch)
    root.mkdir()
    with pytest.raises(ValueError, match="fresh"):
        verifier.verify(base, root)
    assert not calls
