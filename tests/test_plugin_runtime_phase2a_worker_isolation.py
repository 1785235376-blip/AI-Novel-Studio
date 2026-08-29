"""Hostile Python-environment tests for the Host-owned test worker.

Independent review of PR #24 showed that inherited PYTHONPATH executed
attacker sitecustomize and stdlib shadows. These tests require the correction
to keep that from happening. They do not load plugin packages.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pytest

from app.plugin_runtime_contracts import new_execution_attempt_id, new_job_id
from app.plugin_test_worker_supervisor import (
    HostTestJobSpec,
    HostTestWorkerSupervisor,
    current_owned_worker_pids,
)
from app.plugin_worker_process import (
    HOST_TEST_WORKER_ARGV,
    HOST_TEST_WORKER_MODULE,
    build_host_test_worker_environment,
    host_owned_root,
    host_test_worker_argv,
    host_test_worker_bootstrap_path,
    spawn_host_test_worker,
)
from app.plugin_worker_protocol import OPERATION_PING, OPERATION_SLEEP

REPO_ROOT = Path(__file__).resolve().parents[1]


def _spec(operation: str, **kwargs) -> HostTestJobSpec:
    return HostTestJobSpec(
        job_id=new_job_id(),
        execution_attempt_id=new_execution_attempt_id(),
        operation=operation,
        **kwargs,
    )


@pytest.fixture
def supervisor():
    sup = HostTestWorkerSupervisor()
    sessions: list = []

    def start():
        session = sup.start_test_worker()
        sessions.append(session)
        return session

    yield sup, start
    for session in sessions:
        try:
            sup.shutdown_test_worker(session)
        except Exception:
            pass
    leaks = current_owned_worker_pids()
    assert leaks == (), f"owned worker leak: {leaks}"


def _write_marker_module(directory: Path, name: str, marker: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{name}.py").write_text(
        "from pathlib import Path\n"
        f"Path({str(marker)!r}).write_text({name!r})\n",
        encoding="utf-8",
    )


def _child_environ(pid: int) -> dict[str, str]:
    raw = Path(f"/proc/{pid}/environ").read_bytes()
    env: dict[str, str] = {}
    for item in raw.split(b"\0"):
        if not item or b"=" not in item:
            continue
        key, value = item.split(b"=", 1)
        env[key.decode("utf-8", "replace")] = value.decode("utf-8", "replace")
    return env


def _child_cmdline(pid: int) -> list[str]:
    raw = Path(f"/proc/{pid}/cmdline").read_bytes()
    return [part.decode("utf-8", "replace") for part in raw.split(b"\0") if part]


def test_spawn_uses_isolated_bootstrap_argv():
    argv = host_test_worker_argv()
    bootstrap = host_test_worker_bootstrap_path()
    assert argv[:3] == ("-I", "-S", "-u")
    assert HOST_TEST_WORKER_ARGV == ("-I", "-S", "-u")
    assert argv[3] == str(bootstrap)
    assert bootstrap.is_file()
    assert bootstrap.name == "plugin_test_worker_bootstrap.py"
    assert HOST_TEST_WORKER_MODULE == "app.plugin_test_worker"
    import inspect
    assert list(inspect.signature(spawn_host_test_worker).parameters) == []


def test_allowlist_environment_drops_all_parent_python_star(monkeypatch):
    monkeypatch.setenv("PYTHONPATH", "/evil/path")
    monkeypatch.setenv("PYTHONHOME", "/evil/home")
    monkeypatch.setenv("PYTHONUSERBASE", "/evil/user")
    monkeypatch.setenv("PYTHONSTARTUP", "/evil/startup.py")
    monkeypatch.setenv("PYTHONINSPECT", "1")
    monkeypatch.setenv("PYTHONBREAKPOINT", "evil.hook")
    monkeypatch.setenv("PYTHONWARNINGS", "always")
    monkeypatch.setenv("PYTHONPROFILEIMPORTTIME", "1")
    monkeypatch.setenv("PYTHONPLATLIBDIR", "/evil/plat")
    monkeypatch.setenv("PYTHONSAFEPATH", "0")
    monkeypatch.setenv("PYTHONUTF8", "1")
    monkeypatch.setenv("PYTHONIOENCODING", "utf-8")
    monkeypatch.setenv("PYTHONDONTWRITEBYTECODE", "1")
    monkeypatch.setenv("PYTHONHASHSEED", "0")
    monkeypatch.setenv("PYTHONNOUSERSITE", "1")
    monkeypatch.setenv("PYTHONEXECUTABLE", "/evil/python")
    monkeypatch.setenv("NOT_PYTHON", "keep-me-not")  # not in allowlist either
    env = build_host_test_worker_environment()
    leaked = [key for key in env if key.upper().startswith("PYTHON")]
    assert leaked == []
    assert "NOT_PYTHON" not in env
    assert "PATH" not in env


def test_spawned_worker_environ_has_no_inherited_python_star(supervisor, monkeypatch):
    monkeypatch.setenv("PYTHONPATH", "/evil/path")
    monkeypatch.setenv("PYTHONHOME", "/evil/home")
    monkeypatch.setenv("PYTHONSTARTUP", "/evil/startup.py")
    sup, start = supervisor
    session = start()
    child_env = _child_environ(session.pid)
    leaked = [key for key in child_env if key.upper().startswith("PYTHON")]
    assert leaked == []
    cmdline = _child_cmdline(session.pid)
    assert "-I" in cmdline
    assert "-S" in cmdline
    assert "-u" in cmdline
    assert host_test_worker_argv()[3] in cmdline
    outcome = sup.run_test_job(session, _spec(OPERATION_PING))
    assert outcome.accepted is True


def test_sitecustomize_and_usercustomize_do_not_run(supervisor, monkeypatch, tmp_path):
    site_marker = tmp_path / "sitecustomize.marker"
    user_marker = tmp_path / "usercustomize.marker"
    hostile = tmp_path / "hostile"
    _write_marker_module(hostile, "sitecustomize", site_marker)
    _write_marker_module(hostile, "usercustomize", user_marker)
    monkeypatch.setenv("PYTHONPATH", str(hostile))
    monkeypatch.setenv("PYTHONUSERBASE", str(tmp_path / "userbase"))
    sup, start = supervisor
    session = start()
    outcome = sup.run_test_job(session, _spec(OPERATION_PING))
    assert outcome.accepted is True
    assert not site_marker.exists()
    assert not user_marker.exists()


@pytest.mark.parametrize("module_name", ["json", "uuid", "queue", "threading"])
def test_stdlib_shadow_modules_do_not_run(supervisor, monkeypatch, tmp_path, module_name):
    marker = tmp_path / f"{module_name}.marker"
    hostile = tmp_path / "hostile"
    _write_marker_module(hostile, module_name, marker)
    monkeypatch.setenv("PYTHONPATH", str(hostile))
    sup, start = supervisor
    session = start()
    outcome = sup.run_test_job(session, _spec(OPERATION_PING))
    assert outcome.accepted is True
    assert not marker.exists()


def test_hostile_app_package_is_not_imported(supervisor, monkeypatch, tmp_path):
    marker = tmp_path / "app_shadow.marker"
    worker_marker = tmp_path / "worker_shadow.marker"
    evil_app = tmp_path / "evil" / "app"
    evil_app.mkdir(parents=True)
    (evil_app / "__init__.py").write_text(
        "from pathlib import Path\n"
        f"Path({str(marker)!r}).write_text('APP_SHADOW')\n",
        encoding="utf-8",
    )
    (evil_app / "plugin_test_worker.py").write_text(
        "from pathlib import Path\n"
        f"Path({str(worker_marker)!r}).write_text('WORKER_SHADOW')\n"
        "raise SystemExit(99)\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("PYTHONPATH", str(tmp_path / "evil"))
    sup, start = supervisor
    session = start()
    outcome = sup.run_test_job(session, _spec(OPERATION_PING))
    assert outcome.accepted is True
    assert not marker.exists()
    assert not worker_marker.exists()


def test_hostile_pythonhome_does_not_load_attacker_code(supervisor, monkeypatch, tmp_path):
    marker = tmp_path / "pythonhome.marker"
    home = tmp_path / "fakehome"
    lib = home / "lib" / "python3.11"
    lib.mkdir(parents=True)
    _write_marker_module(lib, "sitecustomize", marker)
    _write_marker_module(lib, "json", marker)
    monkeypatch.setenv("PYTHONHOME", str(home))
    sup, start = supervisor
    session = start()
    outcome = sup.run_test_job(session, _spec(OPERATION_PING))
    assert outcome.accepted is True
    assert not marker.exists()


def test_hostile_user_site_does_not_run(supervisor, monkeypatch, tmp_path):
    marker = tmp_path / "usersite.marker"
    version = f"python{sys.version_info.major}.{sys.version_info.minor}"
    site_packages = tmp_path / "userbase" / "lib" / version / "site-packages"
    site_packages.mkdir(parents=True)
    _write_marker_module(site_packages, "usercustomize", marker)
    _write_marker_module(site_packages, "sitecustomize", marker)
    _write_marker_module(site_packages, "json", marker)
    monkeypatch.setenv("PYTHONUSERBASE", str(tmp_path / "userbase"))
    sup, start = supervisor
    session = start()
    outcome = sup.run_test_job(session, _spec(OPERATION_PING))
    assert outcome.accepted is True
    assert not marker.exists()


def test_pth_startup_hook_does_not_run(supervisor, monkeypatch, tmp_path):
    marker = tmp_path / "pth.marker"
    hostile = tmp_path / "site"
    hostile.mkdir()
    (hostile / "attacker_pth_marker.py").write_text(
        "from pathlib import Path\n"
        f"Path({str(marker)!r}).write_text('PTH')\n",
        encoding="utf-8",
    )
    (hostile / "attacker.pth").write_text("import attacker_pth_marker\n", encoding="utf-8")
    monkeypatch.setenv("PYTHONPATH", str(hostile))
    sup, start = supervisor
    session = start()
    outcome = sup.run_test_job(session, _spec(OPERATION_PING))
    assert outcome.accepted is True
    assert not marker.exists()


def test_hostile_cwd_does_not_replace_host_worker(supervisor, monkeypatch, tmp_path):
    marker = tmp_path / "cwd_json.marker"
    worker_marker = tmp_path / "cwd_worker.marker"
    _write_marker_module(tmp_path, "json", marker)
    evil_app = tmp_path / "app"
    evil_app.mkdir()
    (evil_app / "__init__.py").write_text("", encoding="utf-8")
    (evil_app / "plugin_test_worker.py").write_text(
        "from pathlib import Path\n"
        f"Path({str(worker_marker)!r}).write_text('CWD_WORKER')\n"
        "raise SystemExit(99)\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    sup, start = supervisor
    session = start()
    cwd = Path(f"/proc/{session.pid}/cwd").resolve()
    assert cwd == host_owned_root()
    outcome = sup.run_test_job(session, _spec(OPERATION_PING))
    assert outcome.accepted is True
    assert not marker.exists()
    assert not worker_marker.exists()


def test_worker_and_protocol_modules_originate_from_host_root():
    root = host_owned_root().resolve()
    import app.plugin_test_worker as worker
    import app.plugin_worker_protocol as protocol
    import app.plugin_test_worker_bootstrap as bootstrap

    worker_file = Path(worker.__file__).resolve()
    protocol_file = Path(protocol.__file__).resolve()
    bootstrap_file = Path(bootstrap.__file__).resolve()
    assert worker_file.parent == root / "app"
    assert protocol_file.parent == root / "app"
    assert bootstrap_file.parent == root / "app"
    assert worker_file.parent != Path("/tmp")
    # component-aware: host root must not treat a sibling *-evil path as inside
    evil = Path(str(root) + "-evil")
    with pytest.raises(ValueError):
        worker_file.relative_to(evil)


def test_bootstrap_path_ancestry_rejects_prefix_impersonation():
    root = host_owned_root().resolve()
    from app.plugin_test_worker_bootstrap import _is_within

    assert _is_within(root / "app" / "plugin_test_worker.py", root) is True
    assert _is_within(Path(str(root) + "-evil") / "app" / "plugin_test_worker.py", root) is False


def test_isolated_worker_timeout_cancel_crash_and_cleanup(supervisor, monkeypatch, tmp_path):
    monkeypatch.setenv("PYTHONPATH", str(tmp_path))
    sup, start = supervisor
    pids: list[int] = []

    session = start()
    pids.append(session.pid)
    assert sup.run_test_job(session, _spec(OPERATION_PING)).accepted is True
    timed = sup.run_test_job(session, _spec(OPERATION_SLEEP, sleep_ms=5000, wall_timeout_ms=150))
    assert timed.accepted is False
    assert timed.reason_code == "WORKER_TIMEOUT"

    crashed = start()
    pids.append(crashed.pid)
    from app.plugin_worker_protocol import OPERATION_CRASH_FOR_TEST

    crash = sup.run_test_job(crashed, _spec(OPERATION_CRASH_FOR_TEST, wall_timeout_ms=2000))
    assert crash.accepted is False
    assert crash.reason_code == "WORKER_CRASH"

    cancelled = start()
    pids.append(cancelled.pid)
    cancel = sup.run_test_job(
        cancelled,
        _spec(OPERATION_SLEEP, sleep_ms=5000, wall_timeout_ms=2000, cancel_after_ms=80),
    )
    assert cancel.accepted is False
    assert cancel.reason_code == "CANCELLED"
    sup.shutdown_test_worker(cancelled)

    time.sleep(0.1)
    for pid in pids:
        assert not Path(f"/proc/{pid}").exists()
    assert current_owned_worker_pids() == ()
