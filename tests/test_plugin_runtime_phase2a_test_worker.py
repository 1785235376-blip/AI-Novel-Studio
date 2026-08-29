from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from app.plugin_capability_policy import (
    REASON_ATTEMPT_NOT_RUNNING,
    REASON_JOB_ID_MISMATCH,
    REASON_STALE_EXECUTION_ATTEMPT,
    begin_retry,
    evaluate_late_result,
)
from app.plugin_runtime_contracts import (
    ExecutionLifecycleState,
    ExecutionResultEnvelope,
    phase1_production_gate,
    utcnow,
)
from app.plugin_test_worker_supervisor import (
    HostTestJobSpec,
    HostTestWorkerSupervisor,
    current_owned_worker_pids,
)
from app.plugin_worker_process import HOST_TEST_WORKER_ARGV, HOST_TEST_WORKER_MODULE
from app.plugin_worker_protocol import (
    HOST_TEST_WORKER_IDENTITY,
    MAX_FRAME_BYTES,
    MESSAGE_HELLO,
    MESSAGE_JOB_START,
    MESSAGE_READY,
    OPERATION_ATTEMPT_SUBPROCESS_FOR_TEST,
    OPERATION_CRASH_FOR_TEST,
    OPERATION_ECHO_SAFE,
    OPERATION_EMIT_MALFORMED_FRAME_FOR_TEST,
    OPERATION_EMIT_OVERSIZED_FRAME_FOR_TEST,
    OPERATION_EMIT_TRUNCATED_FRAME_FOR_TEST,
    OPERATION_PING,
    OPERATION_RETURN_FIXED_RESULT,
    OPERATION_SLEEP,
    PLUGIN_WORKER_PROTOCOL_VERSION,
    ProtocolError,
    REASON_CANCELLED,
    REASON_INVALID_JSON,
    REASON_INVALID_UTF8,
    REASON_OUTPUT_QUOTA_EXCEEDED,
    REASON_OVERSIZED_FRAME,
    REASON_PROTOCOL_VERSION_MISMATCH,
    REASON_TRAILING_GARBAGE,
    REASON_TRUNCATED_FRAME,
    REASON_UNKNOWN_FIELD,
    REASON_UNKNOWN_MESSAGE_TYPE,
    REASON_WORKER_CRASH,
    REASON_WORKER_TIMEOUT,
    build_envelope,
    decode_frame_payload,
    encode_frame,
    new_message_id,
    new_session_nonce,
    parse_envelope,
    validate_handshake,
)
from app.plugin_runtime_contracts import new_execution_attempt_id, new_job_id

REPO_ROOT = Path(__file__).resolve().parents[1]


def _child_pids(pid: int) -> list[int]:
    path = Path(f"/proc/{pid}/task/{pid}/children")
    try:
        text = path.read_text().strip()
    except OSError:
        return []
    return [int(part) for part in text.split() if part]


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


def _spec(operation: str, **kwargs) -> HostTestJobSpec:
    return HostTestJobSpec(
        job_id=new_job_id(),
        execution_attempt_id=new_execution_attempt_id(),
        operation=operation,
        **kwargs,
    )


def test_successful_handshake_and_ping(supervisor):
    sup, start = supervisor
    session = start()
    assert session.state == "READY"
    outcome = sup.run_test_job(session, _spec(OPERATION_PING))
    assert outcome.accepted is True
    assert outcome.result_payload["output"]["pong"] is True
    assert outcome.job_id
    assert outcome.execution_attempt_id
    assert outcome.lifecycle_state is ExecutionLifecycleState.SUCCEEDED


def test_protocol_version_mismatch_is_rejected():
    hello = build_envelope(MESSAGE_HELLO, {"worker_identity": HOST_TEST_WORKER_IDENTITY, "session_nonce": new_session_nonce()})
    ready = build_envelope(
        MESSAGE_READY,
        {"worker_identity": HOST_TEST_WORKER_IDENTITY, "session_nonce": hello["payload"]["session_nonce"]},
        protocol_version="2",
    )
    with pytest.raises(ProtocolError) as caught:
        validate_handshake(hello=hello, ready=ready)
    assert caught.value.code == REASON_PROTOCOL_VERSION_MISMATCH
    raw = encode_frame({**ready, "protocol_version": "2"})
    payload = raw[4:]
    with pytest.raises(ProtocolError) as caught:
        parse_envelope(payload)
    assert caught.value.code == REASON_PROTOCOL_VERSION_MISMATCH


def test_malformed_handshake_is_rejected():
    hello = build_envelope(MESSAGE_HELLO, {"worker_identity": HOST_TEST_WORKER_IDENTITY, "session_nonce": new_session_nonce()})
    ready = build_envelope(MESSAGE_READY, {"worker_identity": HOST_TEST_WORKER_IDENTITY, "session_nonce": "deadbeef"})
    with pytest.raises(ProtocolError):
        parse_envelope(encode_frame(ready)[4:])
    ready_ok = build_envelope(
        MESSAGE_READY,
        {"worker_identity": HOST_TEST_WORKER_IDENTITY, "session_nonce": new_session_nonce()},
    )
    with pytest.raises(ProtocolError):
        validate_handshake(hello=hello, ready=ready_ok)


def test_safe_fixed_result_and_echo(supervisor):
    sup, start = supervisor
    session = start()
    fixed = sup.run_test_job(session, _spec(OPERATION_RETURN_FIXED_RESULT))
    assert fixed.accepted is True
    assert fixed.result_payload["output"]["fixed"] == "host-test-worker"
    echoed = sup.run_test_job(session, _spec(OPERATION_ECHO_SAFE, echo_payload="payload_ok"))
    assert echoed.accepted is True
    assert echoed.result_payload["output"]["echo"] == "payload_ok"


def test_job_and_attempt_ids_bind_results(supervisor):
    sup, start = supervisor
    session = start()
    spec = _spec(OPERATION_PING)
    outcome = sup.run_test_job(session, spec)
    assert outcome.job_id == spec.job_id
    assert outcome.execution_attempt_id == spec.execution_attempt_id


def test_wrong_job_id_and_stale_attempt_rejected_via_phase1():
    job_id = new_job_id()
    attempt = new_execution_attempt_id()
    wrong_job = ExecutionResultEnvelope.parse({
        "job_id": new_job_id(),
        "execution_attempt_id": attempt,
        "produced_at": utcnow(),
        "status": "SUCCEEDED",
    })
    denied_job = evaluate_late_result(
        wrong_job,
        expected_job_id=job_id,
        expected_attempt_id=attempt,
        current_lifecycle=ExecutionLifecycleState.RUNNING,
    )
    assert denied_job.accepted is False
    assert denied_job.reason_code == REASON_JOB_ID_MISMATCH
    stale = ExecutionResultEnvelope.parse({
        "job_id": job_id,
        "execution_attempt_id": new_execution_attempt_id(),
        "produced_at": utcnow(),
        "status": "SUCCEEDED",
    })
    denied_stale = evaluate_late_result(
        stale,
        expected_job_id=job_id,
        expected_attempt_id=attempt,
        current_lifecycle=ExecutionLifecycleState.RUNNING,
    )
    assert denied_stale.accepted is False
    assert denied_stale.reason_code == REASON_STALE_EXECUTION_ATTEMPT


def test_worker_timeout_terminates_and_rejects_late_result(supervisor):
    sup, start = supervisor
    session = start()
    spec = _spec(OPERATION_SLEEP, sleep_ms=5_000, wall_timeout_ms=200)
    pid = session.pid
    outcome = sup.run_test_job(session, spec)
    assert outcome.accepted is False
    assert outcome.reason_code == REASON_WORKER_TIMEOUT
    assert outcome.lifecycle_state is ExecutionLifecycleState.TIMED_OUT
    time.sleep(0.05)
    assert not Path(f"/proc/{pid}").exists()
    late = evaluate_late_result(
        ExecutionResultEnvelope.parse({
            "job_id": spec.job_id,
            "execution_attempt_id": spec.execution_attempt_id,
            "produced_at": utcnow(),
            "status": "SUCCEEDED",
        }),
        expected_job_id=spec.job_id,
        expected_attempt_id=spec.execution_attempt_id,
        current_lifecycle=outcome.lifecycle_state,
    )
    assert late.accepted is False
    assert late.reason_code == REASON_ATTEMPT_NOT_RUNNING


def test_worker_cancellation(supervisor):
    sup, start = supervisor
    session = start()
    spec = _spec(OPERATION_SLEEP, sleep_ms=5_000, wall_timeout_ms=2_000, cancel_after_ms=80)
    outcome = sup.run_test_job(session, spec)
    assert outcome.accepted is False
    assert outcome.reason_code == REASON_CANCELLED
    assert outcome.lifecycle_state is ExecutionLifecycleState.CANCELLED
    late = evaluate_late_result(
        ExecutionResultEnvelope.parse({
            "job_id": spec.job_id,
            "execution_attempt_id": spec.execution_attempt_id,
            "produced_at": utcnow(),
            "status": "SUCCEEDED",
        }),
        expected_job_id=spec.job_id,
        expected_attempt_id=spec.execution_attempt_id,
        current_lifecycle=ExecutionLifecycleState.CANCELLED,
    )
    assert late.accepted is False


def test_worker_crash(supervisor):
    sup, start = supervisor
    session = start()
    outcome = sup.run_test_job(session, _spec(OPERATION_CRASH_FOR_TEST, wall_timeout_ms=2_000))
    assert outcome.accepted is False
    assert outcome.reason_code == REASON_WORKER_CRASH
    assert outcome.lifecycle_state is ExecutionLifecycleState.FAILED
    assert outcome.worker_exit_status == 17
    assert b"secret" not in bytes(session.stderr)
    assert b"api_key" not in bytes(session.stderr)


def test_malformed_and_oversized_and_truncated_frames(supervisor):
    sup, start = supervisor
    malformed = start()
    out = sup.run_test_job(malformed, _spec(OPERATION_EMIT_MALFORMED_FRAME_FOR_TEST))
    assert out.accepted is False
    assert out.reason_code in {REASON_INVALID_JSON, "MALFORMED_FRAME"}

    oversized = start()
    out = sup.run_test_job(oversized, _spec(OPERATION_EMIT_OVERSIZED_FRAME_FOR_TEST))
    assert out.accepted is False
    assert out.reason_code == REASON_OVERSIZED_FRAME

    truncated = start()
    out = sup.run_test_job(truncated, _spec(OPERATION_EMIT_TRUNCATED_FRAME_FOR_TEST))
    assert out.accepted is False
    assert out.reason_code == REASON_TRUNCATED_FRAME


def test_unknown_message_and_unknown_fields_fail_closed():
    nonce = new_session_nonce()
    hello = build_envelope(MESSAGE_HELLO, {"worker_identity": HOST_TEST_WORKER_IDENTITY, "session_nonce": nonce})
    with pytest.raises(ProtocolError) as caught:
        parse_envelope(encode_frame({**hello, "message_type": "INVOKE"})[4:])
    assert caught.value.code == REASON_UNKNOWN_MESSAGE_TYPE
    with pytest.raises(ProtocolError) as caught:
        parse_envelope(encode_frame({**hello, "extra_hook": True})[4:])
    assert caught.value.code == REASON_UNKNOWN_FIELD
    payload = dict(hello)
    payload["payload"] = {**hello["payload"], "admin": True}
    with pytest.raises(ProtocolError) as caught:
        parse_envelope(encode_frame(payload)[4:])
    assert caught.value.code == REASON_UNKNOWN_FIELD


def test_invalid_utf8_trailing_garbage_and_frame_limits():
    with pytest.raises(ProtocolError) as caught:
        decode_frame_payload(b"\xff\xfe")
    assert caught.value.code == REASON_INVALID_UTF8
    with pytest.raises(ProtocolError) as caught:
        decode_frame_payload(b'{"a":1}{"b":2}')
    assert caught.value.code == REASON_TRAILING_GARBAGE
    exact = {"k": "x" * 100}
    frame = encode_frame(exact)
    assert len(frame) - 4 <= MAX_FRAME_BYTES
    with pytest.raises(ProtocolError) as caught:
        encode_frame({"k": "x" * (MAX_FRAME_BYTES + 8)})
    assert caught.value.code == REASON_OVERSIZED_FRAME


def test_output_quota_is_enforced(supervisor, monkeypatch):
    import app.plugin_test_worker_supervisor as sup_mod
    monkeypatch.setattr(sup_mod, "MAX_TOTAL_OUTPUT_BYTES", 16)
    sup, start = supervisor
    session = start()
    outcome = sup.run_test_job(session, _spec(OPERATION_PING))
    assert outcome.accepted is False
    assert outcome.reason_code == REASON_OUTPUT_QUOTA_EXCEEDED


def test_process_and_pipe_cleanup_and_repeated_start_stop(supervisor):
    sup, start = supervisor
    pids = []
    for _ in range(3):
        session = start()
        pids.append(session.pid)
        outcome = sup.run_test_job(session, _spec(OPERATION_PING))
        assert outcome.accepted is True
        stdin = session.owned.stdin
        sup.shutdown_test_worker(session)
        time.sleep(0.05)
        assert session.owned.poll() is not None
        with pytest.raises((ValueError, OSError)):
            stdin.write(b"x")
    for pid in pids:
        assert not Path(f"/proc/{pid}").exists()
    assert current_owned_worker_pids() == ()


def test_retry_uses_new_attempt_and_late_timeout_result_rejected():
    from tests.test_plugin_runtime_foundation_phase1 import make_job
    first = make_job(lifecycle_state=ExecutionLifecycleState.TIMED_OUT)
    second = begin_retry(first)
    assert second.execution_attempt_id != first.execution_attempt_id
    assert second.job_id == first.job_id
    rejected = evaluate_late_result(
        ExecutionResultEnvelope.parse({
            "job_id": first.job_id,
            "execution_attempt_id": first.execution_attempt_id,
            "produced_at": utcnow(),
            "status": "SUCCEEDED",
        }),
        expected_job_id=second.job_id,
        expected_attempt_id=second.execution_attempt_id,
        current_lifecycle=ExecutionLifecycleState.RUNNING,
    )
    assert rejected.accepted is False
    assert rejected.reason_code == REASON_STALE_EXECUTION_ATTEMPT


def test_worker_has_no_child_process(supervisor):
    sup, start = supervisor
    session = start()
    sup.run_test_job(session, _spec(OPERATION_PING))
    assert _child_pids(session.pid) == []
    denied = sup.run_test_job(session, _spec(OPERATION_ATTEMPT_SUBPROCESS_FOR_TEST))
    assert denied.accepted is False
    assert denied.reason_code == "SUBPROCESS_PROHIBITED"
    assert _child_pids(session.pid) == []


def test_no_network_vault_provider_or_plugin_package_loading(supervisor):
    def boom(*_args, **_kwargs):
        raise AssertionError("forbidden side effect")

    with patch("socket.create_connection", boom), patch("httpx.Client.request", boom), \
            patch("app.credential_vault.credential_vault.resolve", boom):
        sup, start = supervisor
        session = start()
        outcome = sup.run_test_job(session, _spec(OPERATION_PING))
        assert outcome.accepted is True
    source = (REPO_ROOT / "app" / "plugin_test_worker.py").read_text()
    assert "examples/plugins" not in source
    assert "import subprocess" not in source
    assert "plugin_catalog" not in source
    assert HOST_TEST_WORKER_MODULE == "app.plugin_test_worker"
    assert HOST_TEST_WORKER_ARGV == ("-I", "-S", "-u")
    from app.plugin_worker_process import host_test_worker_argv, host_test_worker_bootstrap_path
    argv = host_test_worker_argv()
    assert argv[:3] == ("-I", "-S", "-u")
    assert argv[3] == str(host_test_worker_bootstrap_path())


def test_spawn_spec_is_frozen_not_a_command_runner():
    import inspect
    from app.plugin_worker_process import spawn_host_test_worker
    signature = inspect.signature(spawn_host_test_worker)
    assert list(signature.parameters) == []
    from app.plugin_test_worker_supervisor import HostTestWorkerSupervisor
    assert not hasattr(HostTestWorkerSupervisor, "run_command")
    assert not hasattr(HostTestWorkerSupervisor, "spawn")
    assert not hasattr(HostTestWorkerSupervisor, "execute_path")
    assert not hasattr(HostTestWorkerSupervisor, "invoke_module")


def test_production_startup_does_not_import_or_spawn_test_worker():
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    script = (
        "import sys\n"
        "import app.main\n"
        "assert 'app.plugin_test_worker_supervisor' not in sys.modules\n"
        "assert 'app.plugin_test_worker' not in sys.modules\n"
        "assert 'app.plugin_test_worker_bootstrap' not in sys.modules\n"
        "assert 'app.plugin_worker_windows_sandbox' not in sys.modules\n"
        "assert 'app.plugin_worker_windows_api' not in sys.modules\n"
        "from app.api import plugin_runtime_status\n"
        "status = plugin_runtime_status()\n"
        "assert status['execution_supported'] is False\n"
        "assert status['sandbox'] == 'NOT_CONFIGURED'\n"
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


def test_execution_supported_remains_false():
    from app.api import plugin_runtime_status
    from app.release_readiness import build_release_readiness
    from app.config import settings
    status = plugin_runtime_status()
    assert status["execution_supported"] is False
    gate = phase1_production_gate()
    assert gate.execution_supported is False
    assert gate.os_sandbox_ready is False
    assert gate.worker_runtime_ready is False


def test_missing_job_identity_on_job_start_is_rejected():
    envelope = build_envelope(
        MESSAGE_JOB_START,
        {"operation": OPERATION_PING},
        job_id=None,
        execution_attempt_id=None,
    )
    with pytest.raises(ProtocolError) as caught:
        parse_envelope(encode_frame(envelope)[4:])
    assert caught.value.code in {"MISSING_JOB_IDENTITY", "MALFORMED_FRAME"}


def test_handshake_envelope_roundtrip():
    nonce = new_session_nonce()
    hello = build_envelope(MESSAGE_HELLO, {"worker_identity": HOST_TEST_WORKER_IDENTITY, "session_nonce": nonce})
    parsed = parse_envelope(encode_frame(hello)[4:])
    assert parsed["protocol_version"] == PLUGIN_WORKER_PROTOCOL_VERSION
    assert parsed["payload"]["session_nonce"] == nonce
    ready = build_envelope(MESSAGE_READY, {"worker_identity": HOST_TEST_WORKER_IDENTITY, "session_nonce": nonce})
    validate_handshake(hello=parsed, ready=parse_envelope(encode_frame(ready)[4:]))
