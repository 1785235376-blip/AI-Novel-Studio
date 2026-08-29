"""Host-owned Test Worker supervisor prototype (Phase 2A).

Narrow API: start_test_worker / run_test_job / cancel_test_job /
shutdown_test_worker. Not a command runner, not a plugin executor, not a
Capability Broker. Production startup must not import or activate this module.

Spawning this worker does not set execution_supported=true. Third-party plugin
code execution remains disabled.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from queue import Empty, Queue
from typing import Any, IO, Literal

from app.plugin_capability_policy import REASON_ACCEPTED, begin_retry, evaluate_late_result
from app.plugin_runtime_contracts import ExecutionLifecycleState, ExecutionResultEnvelope, PluginExecutionJob, utcnow
from app.plugin_worker_process import (
    OwnedWorkerProcess,
    drain_stderr_bounded,
    owned_alive_pids,
    spawn_host_test_worker,
    terminate_owned_worker,
)
from app.plugin_worker_protocol import (
    HOST_TEST_WORKER_IDENTITY,
    MAX_FRAME_BYTES,
    MAX_STDERR_BYTES,
    MAX_TOTAL_OUTPUT_BYTES,
    MESSAGE_CANCEL,
    MESSAGE_HELLO,
    MESSAGE_JOB_ERROR,
    MESSAGE_JOB_RESULT,
    MESSAGE_JOB_START,
    MESSAGE_READY,
    MESSAGE_SHUTDOWN,
    OPERATION_ECHO_SAFE,
    OPERATION_SLEEP,
    ProtocolError,
    REASON_CANCELLED,
    REASON_HANDSHAKE_MALFORMED,
    REASON_HANDSHAKE_TIMEOUT,
    REASON_MALFORMED_FRAME,
    REASON_OUTPUT_QUOTA_EXCEEDED,
    REASON_OVERSIZED_FRAME,
    REASON_PROTOCOL_VERSION_MISMATCH,
    REASON_TRUNCATED_FRAME,
    REASON_WORKER_CRASH,
    REASON_WORKER_TIMEOUT,
    WORKER_OPERATIONS,
    build_envelope,
    encode_frame,
    new_session_nonce,
    parse_envelope,
    validate_handshake,
)

WorkerSessionState = Literal[
    "CREATED",
    "HANDSHAKING",
    "READY",
    "RUNNING",
    "SHUTDOWN",
]


@dataclass
class HostTestJobSpec:
    job_id: str
    execution_attempt_id: str
    operation: str
    echo_payload: str | None = None
    sleep_ms: int | None = None
    wall_timeout_ms: int = 2_000
    cancel_after_ms: int | None = None

    def __post_init__(self) -> None:
        if self.operation not in WORKER_OPERATIONS:
            raise ValueError("UNKNOWN_OPERATION")


@dataclass
class HostTestJobOutcome:
    accepted: bool
    reason_code: str
    lifecycle_state: ExecutionLifecycleState
    job_id: str
    execution_attempt_id: str
    result_payload: dict[str, Any] | None = None
    stderr_byte_count: int = 0
    worker_exit_status: int | None = None


@dataclass
class WorkerSession:
    owned: OwnedWorkerProcess
    session_nonce: str
    state: WorkerSessionState = "CREATED"
    job_id: str | None = None
    execution_attempt_id: str | None = None
    lifecycle: ExecutionLifecycleState = ExecutionLifecycleState.CREATED
    stderr: bytearray = field(default_factory=bytearray)
    output_bytes: int = 0
    _events: Queue = field(default_factory=Queue)
    _closed: bool = False
    _lock: threading.Lock = field(default_factory=threading.Lock)

    @property
    def pid(self) -> int:
        return self.owned.pid


class HostTestWorkerSupervisor:
    """Prototype supervisor. Host-owned test worker only."""

    handshake_timeout_s: float = 2.0

    def start_test_worker(self) -> WorkerSession:
        owned = spawn_host_test_worker()
        session = WorkerSession(owned=owned, session_nonce=new_session_nonce(), state="HANDSHAKING")
        threading.Thread(target=self._read_stdout, args=(session,), name=f"test-worker-stdout-{owned.pid}", daemon=True).start()
        threading.Thread(
            target=drain_stderr_bounded,
            args=(owned.stderr, session.stderr),
            kwargs={"limit": MAX_STDERR_BYTES},
            name=f"test-worker-stderr-{owned.pid}",
            daemon=True,
        ).start()
        try:
            self._handshake(session)
        except Exception:
            self.shutdown_test_worker(session)
            raise
        return session

    def run_test_job(self, session: WorkerSession, spec: HostTestJobSpec) -> HostTestJobOutcome:
        self._require_ready(session)
        with session._lock:
            session.job_id = spec.job_id
            session.execution_attempt_id = spec.execution_attempt_id
            session.lifecycle = ExecutionLifecycleState.RUNNING
            session.state = "RUNNING"
            session.output_bytes = 0
        payload: dict[str, Any] = {"operation": spec.operation}
        if spec.operation == OPERATION_ECHO_SAFE and spec.echo_payload is not None:
            payload["echo_payload"] = spec.echo_payload
        if spec.operation == OPERATION_SLEEP and spec.sleep_ms is not None:
            payload["sleep_ms"] = spec.sleep_ms
        self._send(session, MESSAGE_JOB_START, payload, job_id=spec.job_id, execution_attempt_id=spec.execution_attempt_id)
        if spec.cancel_after_ms is not None:
            self._wait_then_cancel(session, spec.cancel_after_ms)
        return self._await_job(session, spec, wall_timeout_ms=spec.wall_timeout_ms)

    def cancel_test_job(self, session: WorkerSession) -> None:
        job_id = session.job_id
        attempt_id = session.execution_attempt_id
        if not job_id or not attempt_id:
            raise ValueError("MISSING_JOB_IDENTITY")
        with session._lock:
            session.lifecycle = ExecutionLifecycleState.CANCEL_REQUESTED
        try:
            self._send(session, MESSAGE_CANCEL, {}, job_id=job_id, execution_attempt_id=attempt_id)
        except OSError:
            return

    def shutdown_test_worker(self, session: WorkerSession) -> None:
        with session._lock:
            if session._closed:
                return
            session._closed = True
        try:
            if session.owned.poll() is None:
                try:
                    self._send(session, MESSAGE_SHUTDOWN, {})
                    session.owned.wait(timeout=0.3)
                except Exception:
                    pass
        finally:
            terminate_owned_worker(session.owned)
            with session._lock:
                session.state = "SHUTDOWN"

    def retry_test_job(self, job: PluginExecutionJob) -> PluginExecutionJob:
        return begin_retry(job)

    def _wait_then_cancel(self, session: WorkerSession, cancel_after_ms: int) -> None:
        deadline = time.monotonic() + (cancel_after_ms / 1000.0)
        while time.monotonic() < deadline:
            if session.owned.poll() is not None:
                return
            if not session._events.empty():
                return
            time.sleep(0.01)
        if session.owned.poll() is None and session._events.empty():
            self.cancel_test_job(session)

    def _handshake(self, session: WorkerSession) -> None:
        hello = build_envelope(
            MESSAGE_HELLO,
            {"worker_identity": HOST_TEST_WORKER_IDENTITY, "session_nonce": session.session_nonce},
        )
        self._write(session, encode_frame(hello))
        event = self._wait_event(session, timeout_s=self.handshake_timeout_s)
        if event is None:
            raise ProtocolError(REASON_HANDSHAKE_TIMEOUT)
        kind, payload = event
        if kind != "frame":
            raise ProtocolError(self._event_reason(kind))
        try:
            ready = parse_envelope(payload)
        except ProtocolError as exc:
            if exc.code == REASON_PROTOCOL_VERSION_MISMATCH:
                raise
            raise ProtocolError(REASON_HANDSHAKE_MALFORMED) from None
        if ready["message_type"] != MESSAGE_READY:
            raise ProtocolError(REASON_HANDSHAKE_MALFORMED)
        validate_handshake(hello=hello, ready=ready)
        with session._lock:
            session.state = "READY"
            session.lifecycle = ExecutionLifecycleState.READY

    def _await_job(self, session: WorkerSession, spec: HostTestJobSpec, *, wall_timeout_ms: int) -> HostTestJobOutcome:
        deadline = time.monotonic() + (wall_timeout_ms / 1000.0)
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return self._on_timeout(session)
            event = self._wait_event(session, timeout_s=max(0.01, remaining))
            if event is None:
                if session.owned.poll() is not None:
                    return self._on_crash(session)
                continue
            kind, payload = event
            if kind == "eof":
                return self._on_crash(session)
            if kind in {"oversize", "truncated", "malformed"}:
                return self._fail(session, self._event_reason(kind), kill=True)
            if kind != "frame":
                return self._fail(session, self._event_reason(kind), kill=True)
            session.output_bytes += len(payload)
            if session.output_bytes > MAX_TOTAL_OUTPUT_BYTES:
                return self._fail(session, REASON_OUTPUT_QUOTA_EXCEEDED, kill=True)
            try:
                message = parse_envelope(payload)
            except ProtocolError as exc:
                return self._fail(session, exc.code, kill=True)
            outcome = self._handle_worker_message(session, spec, message)
            if outcome is not None:
                return outcome

    def _handle_worker_message(
        self,
        session: WorkerSession,
        spec: HostTestJobSpec,
        message: dict[str, Any],
    ) -> HostTestJobOutcome | None:
        message_type = message["message_type"]
        if message_type not in {MESSAGE_JOB_RESULT, MESSAGE_JOB_ERROR}:
            return self._fail(session, REASON_MALFORMED_FRAME, kill=True)
        status: str = "SUCCEEDED" if message_type == MESSAGE_JOB_RESULT else "FAILED"
        envelope = ExecutionResultEnvelope(
            job_id=message["job_id"],
            execution_attempt_id=message["execution_attempt_id"],
            produced_at=utcnow(),
            status=status,  # type: ignore[arg-type]
        )
        lifecycle_for_eval = (
            ExecutionLifecycleState.RUNNING
            if session.lifecycle in {ExecutionLifecycleState.RUNNING, ExecutionLifecycleState.CANCEL_REQUESTED}
            else session.lifecycle
        )
        decision = evaluate_late_result(
            envelope,
            expected_job_id=spec.job_id,
            expected_attempt_id=spec.execution_attempt_id,
            current_lifecycle=lifecycle_for_eval,
        )
        if not decision.accepted:
            return self._fail(session, decision.reason_code, kill=False)
        if message_type == MESSAGE_JOB_RESULT:
            if session.lifecycle is ExecutionLifecycleState.CANCEL_REQUESTED:
                return self._finish(session, ExecutionLifecycleState.CANCELLED, REASON_CANCELLED, accepted=False)
            return self._finish(
                session,
                ExecutionLifecycleState.SUCCEEDED,
                REASON_ACCEPTED,
                accepted=True,
                result=message.get("payload"),
            )
        reason = str((message.get("payload") or {}).get("reason_code") or REASON_WORKER_CRASH)
        if reason == REASON_CANCELLED or session.lifecycle is ExecutionLifecycleState.CANCEL_REQUESTED:
            return self._finish(session, ExecutionLifecycleState.CANCELLED, REASON_CANCELLED, accepted=False)
        return self._finish(session, ExecutionLifecycleState.FAILED, reason, accepted=False)

    def _on_timeout(self, session: WorkerSession) -> HostTestJobOutcome:
        with session._lock:
            session.lifecycle = ExecutionLifecycleState.TIMED_OUT
        self._kill(session)
        return self._outcome(session, accepted=False, reason=REASON_WORKER_TIMEOUT)

    def _on_crash(self, session: WorkerSession) -> HostTestJobOutcome:
        exit_status = session.owned.poll()
        with session._lock:
            session.lifecycle = ExecutionLifecycleState.FAILED
        self._kill(session)
        outcome = self._outcome(session, accepted=False, reason=REASON_WORKER_CRASH)
        outcome.worker_exit_status = exit_status
        return outcome

    def _fail(self, session: WorkerSession, reason: str, *, kill: bool) -> HostTestJobOutcome:
        with session._lock:
            if session.lifecycle is ExecutionLifecycleState.RUNNING:
                session.lifecycle = ExecutionLifecycleState.FAILED
        if kill:
            self._kill(session)
        elif session.owned.poll() is None:
            with session._lock:
                session.state = "READY"
        return self._outcome(session, accepted=False, reason=reason)

    def _finish(
        self,
        session: WorkerSession,
        lifecycle: ExecutionLifecycleState,
        reason: str,
        *,
        accepted: bool,
        result: dict[str, Any] | None = None,
    ) -> HostTestJobOutcome:
        with session._lock:
            session.lifecycle = lifecycle
            if session.owned.poll() is None and not session._closed:
                session.state = "READY"
        return self._outcome(session, accepted=accepted, reason=reason, result=result)

    def _kill(self, session: WorkerSession) -> None:
        terminate_owned_worker(session.owned)
        with session._lock:
            session._closed = True
            session.state = "SHUTDOWN"

    def _require_ready(self, session: WorkerSession) -> None:
        if session.state != "READY" or session.owned.poll() is not None:
            raise ProtocolError(REASON_HANDSHAKE_MALFORMED)

    def _send(
        self,
        session: WorkerSession,
        message_type: str,
        payload: dict[str, Any],
        *,
        job_id: str | None = None,
        execution_attempt_id: str | None = None,
    ) -> None:
        envelope = build_envelope(message_type, payload, job_id=job_id, execution_attempt_id=execution_attempt_id)
        self._write(session, encode_frame(envelope))

    def _write(self, session: WorkerSession, data: bytes) -> None:
        session.owned.stdin.write(data)
        session.owned.stdin.flush()

    def _wait_event(self, session: WorkerSession, *, timeout_s: float) -> tuple[str, Any] | None:
        try:
            return session._events.get(timeout=timeout_s)
        except Empty:
            return None

    def _read_stdout(self, session: WorkerSession) -> None:
        stdout = session.owned.stdout
        try:
            while True:
                header = _read_exact(stdout, 4)
                if header is None:
                    session._events.put(("eof", None))
                    return
                length = int.from_bytes(header, "big")
                if length == 0 or length > MAX_FRAME_BYTES:
                    session._events.put(("oversize", length))
                    return
                payload = _read_exact(stdout, length)
                if payload is None:
                    session._events.put(("truncated", None))
                    return
                session._events.put(("frame", payload))
        except (OSError, ValueError):
            session._events.put(("eof", None))

    def _event_reason(self, kind: str) -> str:
        if kind == "oversize":
            return REASON_OVERSIZED_FRAME
        if kind == "truncated":
            return REASON_TRUNCATED_FRAME
        if kind == "malformed":
            return REASON_MALFORMED_FRAME
        if kind == "timeout":
            return REASON_HANDSHAKE_TIMEOUT
        return REASON_WORKER_CRASH

    def _outcome(
        self,
        session: WorkerSession,
        *,
        accepted: bool,
        reason: str,
        result: dict[str, Any] | None = None,
    ) -> HostTestJobOutcome:
        return HostTestJobOutcome(
            accepted=accepted,
            reason_code=reason,
            lifecycle_state=session.lifecycle,
            job_id=session.job_id or "",
            execution_attempt_id=session.execution_attempt_id or "",
            result_payload=result,
            stderr_byte_count=len(session.stderr),
            worker_exit_status=session.owned.poll(),
        )


def _read_exact(stream: IO[bytes], nbytes: int) -> bytes | None:
    buf = bytearray()
    while len(buf) < nbytes:
        try:
            chunk = stream.read(nbytes - len(buf))
        except (OSError, ValueError):
            return None
        if not chunk:
            return None
        buf.extend(chunk)
    return bytes(buf)


def current_owned_worker_pids() -> tuple[int, ...]:
    return owned_alive_pids()
