"""Phase 2B Windows AppContainer sandbox prototype tests.

Linux: fail-closed, no unsandboxed fallback, production isolation, protocol
probes, and source/API shape. Those tests always run.

Windows: real AppContainer launch, token proof, filesystem/network/process
probes, cleanup, and leak checks. They use skipif(sys.platform != "win32")
so they MUST run on a real Windows host. They are not xfail and are not
skipped on Windows.
"""

from __future__ import annotations

import inspect
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
import ctypes

from app.plugin_runtime_contracts import (
    new_execution_attempt_id,
    new_job_id,
    phase1_production_gate,
)
from app.plugin_test_worker_supervisor import (
    HostTestJobSpec,
    HostTestWorkerSupervisor,
    current_owned_worker_pids,
)
from app.plugin_worker_process import spawn_host_test_worker, spawn_sandboxed_host_test_worker
from app.plugin_worker_protocol import (
    MESSAGE_JOB_START,
    OPERATION_CRASH_FOR_TEST,
    OPERATION_EMIT_MALFORMED_FRAME_FOR_TEST,
    OPERATION_EMIT_OVERSIZED_FRAME_FOR_TEST,
    OPERATION_EMIT_TRUNCATED_FRAME_FOR_TEST,
    OPERATION_PING,
    OPERATION_PROBE_ALLOWED_READ,
    OPERATION_PROBE_ALLOWED_WRITE,
    OPERATION_PROBE_CHILD_PROCESS,
    OPERATION_PROBE_FORBIDDEN_HOST_READ,
    OPERATION_PROBE_FORBIDDEN_HOST_WRITE,
    OPERATION_PROBE_NETWORK,
    OPERATION_PROBE_TOKEN_IDENTITY,
    OPERATION_SLEEP,
    ProtocolError,
    REASON_UNKNOWN_FIELD,
    REASON_WORKER_CRASH,
    REASON_WORKER_TIMEOUT,
    WORKER_OPERATIONS,
    build_envelope,
    encode_frame,
    parse_envelope,
)
from app.plugin_worker_sandbox_errors import (
    PROCESS_MEMORY_LIMIT_BYTES,
    REASON_WINDOWS_SANDBOX_UNAVAILABLE,
    SandboxError,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
WINDOWS_ONLY = pytest.mark.skipif(sys.platform != "win32", reason="requires real win32 AppContainer host")


def _spec(operation: str, **kwargs) -> HostTestJobSpec:
    return HostTestJobSpec(
        job_id=new_job_id(),
        execution_attempt_id=new_execution_attempt_id(),
        operation=operation,
        **kwargs,
    )


def _read(rel: str) -> str:
    return (REPO_ROOT / rel).read_text(encoding="utf-8")


def test_spawn_sandboxed_signature_is_empty_and_not_generic():
    assert list(inspect.signature(spawn_sandboxed_host_test_worker).parameters) == []
    from app.plugin_worker_windows_sandbox import spawn_sandboxed_host_test_worker as sandbox_spawn

    assert list(inspect.signature(sandbox_spawn).parameters) == []
    import app.plugin_worker_process as process_mod
    import app.plugin_worker_windows_sandbox as sandbox_mod
    import app.plugin_test_worker_supervisor as supervisor_mod

    assert not hasattr(process_mod, "spawn_sandboxed")
    assert not hasattr(sandbox_mod, "spawn_sandboxed")
    assert not hasattr(supervisor_mod.HostTestWorkerSupervisor, "spawn")
    assert not hasattr(supervisor_mod.HostTestWorkerSupervisor, "run_command")
    assert not hasattr(supervisor_mod.HostTestWorkerSupervisor, "execute_path")
    assert not hasattr(supervisor_mod.HostTestWorkerSupervisor, "invoke_module")


def test_non_windows_sandbox_is_fail_closed_and_does_not_fallback():
    before = current_owned_worker_pids()
    with patch("app.plugin_worker_process.spawn_host_test_worker") as unsandboxed_proc, patch(
        "app.plugin_test_worker_supervisor.spawn_host_test_worker"
    ) as unsandboxed_sup:
        if sys.platform != "win32":
            with pytest.raises(SandboxError) as caught:
                spawn_sandboxed_host_test_worker()
            assert caught.value.code == REASON_WINDOWS_SANDBOX_UNAVAILABLE
            unsandboxed_proc.assert_not_called()
            unsandboxed_sup.assert_not_called()
    assert current_owned_worker_pids() == before
    if sys.platform != "win32":
        from app.plugin_worker_windows_sandbox import spawn_sandboxed_host_test_worker as sandbox_spawn

        with patch("app.plugin_worker_process.spawn_host_test_worker") as unsandboxed_proc, patch(
            "app.plugin_test_worker_supervisor.spawn_host_test_worker"
        ) as unsandboxed_sup:
            with pytest.raises(SandboxError) as caught:
                sandbox_spawn()
            assert caught.value.code == REASON_WINDOWS_SANDBOX_UNAVAILABLE
            with pytest.raises(SandboxError) as caught:
                HostTestWorkerSupervisor().start_sandboxed_test_worker()
            assert caught.value.code == REASON_WINDOWS_SANDBOX_UNAVAILABLE
            unsandboxed_proc.assert_not_called()
            unsandboxed_sup.assert_not_called()


def test_sandbox_failure_never_calls_unsandboxed_spawn():
    with patch("app.plugin_worker_process.spawn_host_test_worker") as unsandboxed_proc, patch(
        "app.plugin_test_worker_supervisor.spawn_host_test_worker"
    ) as unsandboxed_sup:
        with patch(
            "app.plugin_worker_process.sys.platform",
            "linux",
        ):
            with pytest.raises(SandboxError) as caught:
                spawn_sandboxed_host_test_worker()
            assert caught.value.code == REASON_WINDOWS_SANDBOX_UNAVAILABLE
        unsandboxed_proc.assert_not_called()
        unsandboxed_sup.assert_not_called()


def test_probe_operations_are_fixed_and_reject_arbitrary_payload_fields():
    for operation in (
        OPERATION_PROBE_ALLOWED_READ,
        OPERATION_PROBE_ALLOWED_WRITE,
        OPERATION_PROBE_FORBIDDEN_HOST_READ,
        OPERATION_PROBE_FORBIDDEN_HOST_WRITE,
        OPERATION_PROBE_NETWORK,
        OPERATION_PROBE_CHILD_PROCESS,
        OPERATION_PROBE_TOKEN_IDENTITY,
    ):
        assert operation in WORKER_OPERATIONS
        for extra in ("path", "url", "command", "executable", "host", "port"):
            envelope = build_envelope(
                MESSAGE_JOB_START,
                {"operation": operation, extra: "x"},
                job_id=new_job_id(),
                execution_attempt_id=new_execution_attempt_id(),
            )
            with pytest.raises(ProtocolError) as caught:
                parse_envelope(encode_frame(envelope)[4:])
            assert caught.value.code == REASON_UNKNOWN_FIELD


def test_worker_source_has_no_generic_subprocess_or_plugin_loader():
    source = _read("app/plugin_test_worker.py")
    assert "import subprocess" not in source
    assert "examples/plugins" not in source
    assert "plugin_catalog" not in source
    assert "eval(" not in source
    assert "exec(" not in source


def test_sandbox_source_forbids_global_acl_hardlink_and_loopback_exemption():
    sandbox = _read("app/plugin_worker_windows_sandbox.py")
    api = _read("app/plugin_worker_windows_api.py")
    combined = sandbox + "\n" + api
    assert "CreateHardLink" not in combined
    assert "os.link" not in combined
    assert "hardlink" in sandbox
    assert "shutil.copy2" in sandbox
    assert "CheckNetIsolation" not in combined
    assert "loopbackExempt" not in combined
    assert "internetClient" not in combined
    assert "CapabilityCount = 0" in api or "CapabilityCount=0" in api.replace(" ", "")
    assert "JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE" in api
    assert "ActiveProcessLimit = 1" in api
    assert "import pywin32" not in combined.lower()
    assert "from win32" not in combined
    assert "win32security" not in combined
    assert "TokenIsAppContainer" in api
    assert "CreateAppContainerProfile" in api
    assert "PROC_THREAD_ATTRIBUTE_SECURITY_CAPABILITIES" in api
    assert "LessPrivilegedAppContainer" not in combined
    assert "ALL_APPLICATION_PACKAGES_POLICY" not in combined
    assert "grant_appcontainer_acl(str(staging_root)" in sandbox
    assert "grant_appcontainer_acl(str(runtime_dir)" in sandbox
    assert "host_sentinel_dir), sid" not in sandbox
    assert "never modifies the Python installation" in sandbox or "Never hardlink" in sandbox


def test_production_startup_does_not_import_or_spawn_sandbox_worker():
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    script = (
        "import sys\n"
        "import app.main\n"
        "assert 'app.plugin_worker_windows_sandbox' not in sys.modules\n"
        "assert 'app.plugin_worker_windows_api' not in sys.modules\n"
        "assert 'app.plugin_test_worker_supervisor' not in sys.modules\n"
        "from app.api import plugin_runtime_status\n"
        "status = plugin_runtime_status()\n"
        "assert status['execution_supported'] is False\n"
        "assert status['sandbox'] == 'NOT_CONFIGURED'\n"
        "assert status['isolation'] == 'DENY_ALL'\n"
        "print('ok')\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "ok" in result.stdout
    assert current_owned_worker_pids() == ()


def test_execution_supported_and_os_sandbox_ready_remain_false():
    from app.api import plugin_runtime_status

    status = plugin_runtime_status()
    assert status["execution_supported"] is False
    assert status["sandbox"] == "NOT_CONFIGURED"
    gate = phase1_production_gate()
    assert gate.execution_supported is False
    assert gate.os_sandbox_ready is False
    assert gate.worker_runtime_ready is False


def test_memory_limit_constant_is_not_too_low_for_python():
    assert PROCESS_MEMORY_LIMIT_BYTES == 512 * 1024 * 1024


def test_win32_module_refuses_to_construct_off_windows():
    from app.plugin_worker_windows_api import Win32

    if sys.platform != "win32":
        with pytest.raises(SandboxError) as caught:
            Win32()
            assert caught.value.code == REASON_WINDOWS_SANDBOX_UNAVAILABLE


def test_windows_environment_block_is_sorted_validated_and_double_nul_terminated():
    from app.plugin_worker_windows_api import Win32

    api = Win32.__new__(Win32)
    api.ctypes = ctypes
    block = api._env_block({"TEMP": "t", "systemroot": "r", "WINDIR": "w"})
    units = list(block)
    text = "".join(units)
    assert text.endswith("\0\0")
    logical = [entry for entry in text.split("\0") if entry]
    assert [entry.split("=", 1)[0].casefold() for entry in logical] == ["systemroot", "temp", "windir"]
    assert units[-1] == "\0" and units[-2] == "\0"


@pytest.mark.parametrize("env", [
    {"": "x"}, {"A\0B": "x"}, {"A": "x\0y"},
    {"A=B": "x"}, {"PYTHONPATH": "x"}, {"Path": "a", "PATH": "b"},
])
def test_windows_environment_block_rejects_invalid_entries(env):
    from app.plugin_worker_windows_api import Win32

    api = Win32.__new__(Win32)
    api.ctypes = ctypes
    with pytest.raises(ValueError):
        api._env_block(env)


@pytest.fixture
def sandboxed_supervisor():
    sup = HostTestWorkerSupervisor()
    sessions: list = []

    def start():
        session = sup.start_sandboxed_test_worker()
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
    from app.plugin_worker_windows_sandbox import live_appcontainer_profiles, live_staging_directories

    assert live_appcontainer_profiles() == ()
    assert live_staging_directories() == ()


@WINDOWS_ONLY
def test_windows_token_is_appcontainer(sandboxed_supervisor):
    sup, start = sandboxed_supervisor
    session = start()
    launch = session.sandbox
    assert launch is not None
    assert launch.token_is_appcontainer is True
    assert launch.appcontainer_sid_present is True
    outcome = sup.run_test_job(session, _spec(OPERATION_PROBE_TOKEN_IDENTITY))
    assert outcome.accepted is True
    output = outcome.result_payload["output"]
    assert output["is_appcontainer"] is True
    assert output["appcontainer_sid_present"] is True


@WINDOWS_ONLY
def test_windows_handshake_ping_and_fixed_probes(sandboxed_supervisor):
    sup, start = sandboxed_supervisor
    session = start()
    ping = sup.run_test_job(session, _spec(OPERATION_PING))
    assert ping.accepted is True
    allowed_read = sup.run_test_job(session, _spec(OPERATION_PROBE_ALLOWED_READ))
    assert allowed_read.accepted is True
    assert allowed_read.result_payload["output"]["ok"] is True
    allowed_write = sup.run_test_job(session, _spec(OPERATION_PROBE_ALLOWED_WRITE))
    assert allowed_write.accepted is True
    write_out = allowed_write.result_payload["output"]
    assert write_out["output_ok"] is True
    assert write_out["input_write_denied"] is True
    assert write_out["tmp_ok"] is True
    launch = session.sandbox
    assert (launch.out_dir / "output.txt").read_text(encoding="utf-8") == "SANDBOX_OUTPUT_OK"
    assert not (launch.in_dir / "should_fail.txt").exists()
    assert (launch.tmp_dir / "tmp.txt").read_text(encoding="utf-8") == "SANDBOX_TMP_OK"


@WINDOWS_ONLY
def test_windows_forbidden_host_read_write_denied(sandboxed_supervisor):
    sup, start = sandboxed_supervisor
    session = start()
    launch = session.sandbox
    secret = launch.forbidden_read_path.read_text(encoding="utf-8")
    original = launch.forbidden_write_path.read_text(encoding="utf-8")
    denied_read = sup.run_test_job(session, _spec(OPERATION_PROBE_FORBIDDEN_HOST_READ))
    assert denied_read.accepted is True
    output = denied_read.result_payload["output"]
    assert output["denied"] is True
    assert output["secret_leaked"] is False
    denied_write = sup.run_test_job(session, _spec(OPERATION_PROBE_FORBIDDEN_HOST_WRITE))
    assert denied_write.accepted is True
    assert denied_write.result_payload["output"]["denied"] is True
    assert launch.forbidden_write_path.read_text(encoding="utf-8") == original
    assert "PWNED" not in launch.forbidden_write_path.read_text(encoding="utf-8")
    assert secret not in str(denied_read.result_payload)


@WINDOWS_ONLY
def test_windows_network_and_loopback_denied(sandboxed_supervisor):
    sup, start = sandboxed_supervisor
    session = start()
    outcome = sup.run_test_job(session, _spec(OPERATION_PROBE_NETWORK))
    assert outcome.accepted is True
    assert outcome.result_payload["output"]["denied"] is True


@WINDOWS_ONLY
def test_windows_child_process_containment(sandboxed_supervisor):
    sup, start = sandboxed_supervisor
    session = start()
    outcome = sup.run_test_job(session, _spec(OPERATION_PROBE_CHILD_PROCESS))
    assert outcome.accepted is True
    assert outcome.result_payload["output"]["denied"] is True


@WINDOWS_ONLY
def test_windows_timeout_cancel_crash_and_ipc(sandboxed_supervisor):
    sup, start = sandboxed_supervisor
    session = start()
    timed = sup.run_test_job(session, _spec(OPERATION_SLEEP, sleep_ms=4000, wall_timeout_ms=200))
    assert timed.accepted is False
    assert timed.reason_code == REASON_WORKER_TIMEOUT
    session = start()
    cancelled = sup.run_test_job(
        session,
        _spec(OPERATION_SLEEP, sleep_ms=4000, wall_timeout_ms=2000, cancel_after_ms=50),
    )
    assert cancelled.accepted is False
    session = start()
    crashed = sup.run_test_job(session, _spec(OPERATION_CRASH_FOR_TEST))
    assert crashed.accepted is False
    assert crashed.reason_code == REASON_WORKER_CRASH
    session = start()
    malformed = sup.run_test_job(session, _spec(OPERATION_EMIT_MALFORMED_FRAME_FOR_TEST))
    assert malformed.accepted is False
    session = start()
    oversized = sup.run_test_job(session, _spec(OPERATION_EMIT_OVERSIZED_FRAME_FOR_TEST))
    assert oversized.accepted is False
    session = start()
    truncated = sup.run_test_job(session, _spec(OPERATION_EMIT_TRUNCATED_FRAME_FOR_TEST))
    assert truncated.accepted is False


@WINDOWS_ONLY
def test_windows_job_close_kills_worker(sandboxed_supervisor):
    from app.plugin_worker_windows_api import Win32

    sup, start = sandboxed_supervisor
    session = start()
    launch = session.sandbox
    assert launch is not None
    assert launch.job_handle
    win = Win32()
    win.close_handle(launch.job_handle)
    launch.job_handle = None
    deadline = __import__("time").time() + 2.0
    while __import__("time").time() < deadline and session.owned.poll() is None:
        __import__("time").sleep(0.05)
    assert session.owned.poll() is not None


@WINDOWS_ONLY
def test_windows_repeated_lifecycle_and_cleanup(sandboxed_supervisor):
    from app.plugin_worker_windows_sandbox import live_appcontainer_profiles, live_staging_directories

    sup, start = sandboxed_supervisor
    staged_counts: list[int] = []
    for _ in range(20):
        session = start()
        ping = sup.run_test_job(session, _spec(OPERATION_PING))
        assert ping.accepted is True
        launch = session.sandbox
        staged_counts.append(launch.staged_file_count)
        assert launch.staged_file_count > 0
        assert launch.staged_bytes > 0
        staging = launch.staging_root
        profile = launch.profile_name
        sup.shutdown_test_worker(session)
        assert not staging.exists()
        assert profile not in live_appcontainer_profiles()
    assert current_owned_worker_pids() == ()
    assert live_appcontainer_profiles() == ()
    assert live_staging_directories() == ()
    assert all(count == staged_counts[0] for count in staged_counts)


@WINDOWS_ONLY
def test_windows_sandbox_launch_failure_does_not_fallback():
    with patch("app.plugin_worker_process.spawn_host_test_worker") as unsandboxed:
        with patch(
            "app.plugin_worker_windows_api.Win32.create_or_derive_profile",
            side_effect=SandboxError("SANDBOX_PROFILE_CREATE_FAILED"),
        ):
            with pytest.raises(SandboxError) as caught:
                spawn_sandboxed_host_test_worker()
            assert caught.value.code == "SANDBOX_PROFILE_CREATE_FAILED"
        unsandboxed.assert_not_called()
    assert current_owned_worker_pids() == ()
