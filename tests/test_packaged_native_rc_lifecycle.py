"""RC regressions for exit classification and immutable Python payloads.

Lifecycle boundaries are controlled unit fixtures. Exit codes and bytecode
generation are observed from actual Python subprocesses, not mock outputs.
Native DesktopHost acceptance is recorded separately for the rebuilt package.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.packaging import packaged_desktop_launcher as launcher
from app.packaging import packaged_processes
from app.packaging.paths import WindowsPackagingPaths
from app.packaging.runtime_identity import RuntimeRole
from app.experimental.flags import enabled_flags, require_flag
from fastapi import HTTPException


ROOT = Path(__file__).resolve().parents[1]


def launcher_fixture(tmp_path, monkeypatch, *, host_code=0, child_crash=False, requested_stop=False, cleanup_failure=False):
    events = []
    stop_handler = []
    runtime = SimpleNamespace(
        reservations=SimpleNamespace(ports={RuntimeRole.BACKEND:58123,RuntimeRole.POSTGRESQL:55432}),
        inspector=object(), job=object(),
    )
    identity = SimpleNamespace(runtime_instance_id="rc-owned-test")
    runtime.startup = lambda: events.append("runtime.startup") or identity
    runtime.check_for_child_crash = lambda: events.append("runtime.check") or (object() if child_crash else None)

    def shutdown():
        events.append("runtime.shutdown")
        if cleanup_failure:
            raise RuntimeError("owned cleanup failed")
    runtime.shutdown = shutdown
    factory = SimpleNamespace(config=SimpleNamespace(
        layout=SimpleNamespace(application=tmp_path / "Application"),
        paths=SimpleNamespace(cache=tmp_path / "Cache"),
        public_runtime_metadata=lambda **kwargs: kwargs,
    ), take_bootstrap_secret=lambda: "unit-only-bootstrap")
    processes = []

    class ObservedHost:
        failure_code = None

        def __init__(self, **kwargs):
            self.process = None

        def start(self, envelope):
            events.append("host.start")
            script = "import time;time.sleep(60)" if requested_stop else f"raise SystemExit({host_code})"
            self.process = subprocess.Popen([sys.executable,"-B","-c",script],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            processes.append(self.process)
            if not requested_stop:
                assert self.process.wait(timeout=10) == host_code

        def wait_session_ready(self, seconds):
            if requested_stop:
                stop_handler[0]()
            return True

        def is_running(self):
            return self.process.poll() is None

        def drain_valid_control_messages(self):
            return 0, []

        def block_actions(self):
            events.append("host.block_actions")

        def close(self):
            events.append("host.close")
            if self.process.poll() is None:
                self.process.terminate()
            self.process.wait(timeout=10)
            self.process.stdout.close()
            self.process.stderr.close()

    monkeypatch.setattr(sys,"argv",["packaged_desktop_launcher"])
    monkeypatch.setattr(launcher,"create_packaged_backend_runtime",lambda **kwargs:(runtime,factory))
    monkeypatch.setattr(launcher,"_install_stop_handlers",stop_handler.append)
    monkeypatch.setattr(launcher,"PackagedDesktopHost",ObservedHost)
    return events, processes


def test_ready_window_normal_exit_returns_zero_and_closes_owned_runtime(tmp_path, monkeypatch, capsys):
    events, processes = launcher_fixture(tmp_path, monkeypatch)
    assert launcher.main() == 0
    assert processes[0].returncode == 0
    assert events[-3:] == ["host.block_actions","host.close","runtime.shutdown"]
    output = capsys.readouterr().out
    assert "APPLICATION_READY " in output
    assert "unit-only-bootstrap" not in output


@pytest.mark.parametrize("host_code",[17,143])
def test_ready_window_nonzero_exit_is_not_reported_as_success(tmp_path, monkeypatch, host_code):
    events, processes = launcher_fixture(tmp_path, monkeypatch, host_code=host_code)
    assert launcher.main() == 2
    assert processes[0].returncode == host_code
    assert events[-3:] == ["host.block_actions","host.close","runtime.shutdown"]


def test_service_crash_is_not_masked_by_a_simultaneously_clean_host_exit(tmp_path, monkeypatch):
    events, processes = launcher_fixture(tmp_path, monkeypatch, child_crash=True)
    assert launcher.main() == 2
    assert processes[0].returncode == 0
    assert "runtime.check" in events
    assert events[-3:] == ["host.block_actions","host.close","runtime.shutdown"]


def test_requested_launcher_stop_keeps_original_graceful_stop_contract(tmp_path, monkeypatch):
    events, processes = launcher_fixture(tmp_path, monkeypatch, requested_stop=True)
    assert launcher.main() == 0
    assert processes[0].poll() is not None
    assert events[-3:] == ["host.block_actions","host.close","runtime.shutdown"]


def test_cleanup_error_after_clean_window_exit_remains_an_error(tmp_path, monkeypatch):
    events, processes = launcher_fixture(tmp_path, monkeypatch, cleanup_failure=True)
    with pytest.raises(RuntimeError, match="owned cleanup failed"):
        launcher.main()
    assert processes[0].returncode == 0
    assert events[-1] == "runtime.shutdown"


def backend_python_options(tmp_path, monkeypatch):
    paths = WindowsPackagingPaths.resolve(local_app_data=tmp_path/"Local",user_profile=tmp_path/"Profile")
    config = packaged_processes.PackagedProcessConfig(
        layout=SimpleNamespace(application=tmp_path/"Application",python=Path(sys.executable),backend=tmp_path,
                               frontend_dist=tmp_path/"Frontend"),
        paths=paths,version="0.7.0",
    )
    factory = packaged_processes.PackagedProcessFactory(config, object())
    factory.database_port = 55432
    captured = []
    # Restore Popen before the functional Python-import probe. Do not let a
    # process double leak into subprocess.run or pytest reporting.
    with monkeypatch.context() as controlled:
        controlled.setattr(packaged_processes.subprocess,"Popen",lambda argv,**kwargs:captured.append(argv) or object())
        controlled.setattr(packaged_processes,"PackagedManagedChild",lambda **kwargs:kwargs)
        factory._start_backend(58123,SimpleNamespace(runtime_instance_id="rc-owned-test"))
    argv = captured[0]
    return argv[1:argv.index("-m")]


@pytest.mark.parametrize("entry",["installed_ps","portable_cmd","backend_child"])
def test_packaged_python_entry_imports_without_mutating_its_payload(tmp_path, monkeypatch, entry):
    if entry == "backend_child":
        options = backend_python_options(tmp_path, monkeypatch)
    elif entry == "installed_ps":
        source = (ROOT/"scripts/installer/Launch-AI-Novel-Studio.ps1").read_text("utf-8")
        arguments = re.search(r"\$launcherArgs = @\((.*?)\)",source,re.S).group(1)
        values = re.findall(r"'([^']+)'",arguments)
        options = values[:values.index("-m")]
    else:
        source = (ROOT/"packaging/portable/AI-Novel-Studio-Portable.cmd").read_text("utf-8")
        command = next(line for line in source.splitlines() if line.startswith('"%PYTHON%" '))
        values = command.split()[1:]
        options = values[:values.index("-m")]
    payload = tmp_path/entry
    payload.mkdir()
    (payload/"rc_payload.py").write_text("value = 'retained-source'\n",encoding="utf-8")
    # -I ignores Python environment variables: the effective argv itself must
    # prevent the write, even when only this environment hint is present.
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    result = subprocess.run([sys.executable,*options,"-c",
        "import sys;sys.path.insert(0,sys.argv[1]);import rc_payload;print(rc_payload.value)",str(payload)],
        env=environment,capture_output=True,text=True,timeout=10)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "retained-source"
    assert not list(payload.rglob("*.pyc")), f"{entry} mutated its Application payload"
    assert (payload/"rc_payload.py").read_text("utf-8") == "value = 'retained-source'\n"


@pytest.mark.parametrize("inherited",["","*","branch_manuscript_v1,advanced_planning_v2,writing_recovery_v2","experimental.branch_manuscript_v1,unknown"])
def test_packaged_branch_prerequisite_is_explicit_without_inheriting_other_opt_ins(tmp_path, monkeypatch, inherited):
    monkeypatch.setenv("EXPERIMENTAL_FEATURES", inherited)
    monkeypatch.delenv("V1_ACCEPTANCE_MODE", raising=False)
    config = packaged_processes.PackagedProcessConfig(
        layout=SimpleNamespace(backend=tmp_path,frontend_dist=tmp_path/"Frontend"),
        paths=WindowsPackagingPaths.resolve(local_app_data=tmp_path/"Local",user_profile=tmp_path/"Profile"),
        version="0.7.0",
    )
    environment = os.environ.copy()
    environment.update(config.environment(database_port=55432,backend_port=58123))
    assert environment["EXPERIMENTAL_FEATURES"] == "branch_manuscript_v1"
    # Exercise the original flag dependency/gate implementation with the actual
    # final child environment. Global defaults and permissions remain unchanged.
    monkeypatch.setenv("EXPERIMENTAL_FEATURES",environment["EXPERIMENTAL_FEATURES"])
    assert enabled_flags() == frozenset({"branch_manuscript_v1"})
    require_flag("branch_manuscript_v1")
    for unrelated in ["advanced_planning_v2","writing_recovery_v2","writer_room_v2","realtime_collaboration_v1","declarative_agents_v2"]:
        with pytest.raises(HTTPException) as rejected:
            require_flag(unrelated)
        assert rejected.value.status_code == 404
        assert rejected.value.detail == {"code":"EXPERIMENTAL_FEATURE_DISABLED","feature":unrelated}
