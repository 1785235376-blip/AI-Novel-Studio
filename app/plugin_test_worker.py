"""Host-owned Test Worker process (Phase 2A).

Fixed operations only. Not a plugin, not extensible, not a command runner.
Does not read the database, vault, providers, plugin packages, or network.
Does not eval/exec/import user modules. Child processes are prohibited.

Run only via the frozen supervisor spawn: `python -u -m app.plugin_test_worker`.
"""

from __future__ import annotations

import os
import queue
import sys
import threading
import time
from typing import Any, Callable

from app.plugin_worker_protocol import (
    HOST_TEST_WORKER_IDENTITY,
    MAX_FRAME_BYTES,
    MESSAGE_CANCEL,
    MESSAGE_HELLO,
    MESSAGE_JOB_ERROR,
    MESSAGE_JOB_RESULT,
    MESSAGE_JOB_START,
    MESSAGE_READY,
    MESSAGE_SHUTDOWN,
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
    REASON_HANDSHAKE_MALFORMED,
    REASON_PROTOCOL_VERSION_MISMATCH,
    REASON_SUBPROCESS_PROHIBITED,
    REASON_UNKNOWN_OPERATION,
    build_envelope,
    encode_frame,
    parse_envelope,
)

_CANCEL = threading.Event()
_CURRENT_JOB: dict[str, str] | None = None
_LOCK = threading.Lock()
_INCOMING: queue.Queue[tuple[str, Any]] = queue.Queue()


def _write_raw(data: bytes) -> None:
    sys.stdout.buffer.write(data)
    sys.stdout.buffer.flush()


def _write_envelope(message_type: str, payload: dict[str, Any] | None = None, **ids: str | None) -> None:
    envelope = build_envelope(
        message_type,
        payload,
        job_id=ids.get("job_id"),
        execution_attempt_id=ids.get("execution_attempt_id"),
    )
    _write_raw(encode_frame(envelope))


def _read_exact(nbytes: int) -> bytes | None:
    buf = bytearray()
    while len(buf) < nbytes:
        chunk = sys.stdin.buffer.read(nbytes - len(buf))
        if not chunk:
            return None
        buf.extend(chunk)
    return bytes(buf)


def _read_frame() -> bytes | None:
    header = _read_exact(4)
    if header is None:
        return None
    length = int.from_bytes(header, "big")
    if length == 0 or length > MAX_FRAME_BYTES:
        sys.exit(3)
    payload = _read_exact(length)
    if payload is None:
        return None
    return payload


def _handshake() -> None:
    raw = _read_frame()
    if raw is None:
        sys.exit(2)
    try:
        hello = parse_envelope(raw)
    except ProtocolError as exc:
        if exc.code == REASON_PROTOCOL_VERSION_MISMATCH:
            sys.exit(4)
        sys.exit(2)
    if hello["message_type"] != MESSAGE_HELLO:
        sys.exit(2)
    payload = hello["payload"]
    if payload.get("worker_identity") != HOST_TEST_WORKER_IDENTITY:
        sys.exit(2)
    nonce = payload.get("session_nonce")
    if not isinstance(nonce, str):
        sys.exit(2)
    _write_envelope(
        MESSAGE_READY,
        {
            "worker_identity": HOST_TEST_WORKER_IDENTITY,
            "session_nonce": nonce,
        },
    )


def _reader_loop() -> None:
    while True:
        raw = _read_frame()
        if raw is None:
            _INCOMING.put(("eof", None))
            return
        try:
            message = parse_envelope(raw)
        except ProtocolError as exc:
            _INCOMING.put(("error", exc))
            return
        if message["message_type"] == MESSAGE_CANCEL:
            with _LOCK:
                current = _CURRENT_JOB
            if (
                current
                and current["job_id"] == message["job_id"]
                and current["execution_attempt_id"] == message["execution_attempt_id"]
            ):
                _CANCEL.set()
            _INCOMING.put(("cancel", message))
            continue
        _INCOMING.put(("msg", message))


def _job_ids(message: dict[str, Any]) -> dict[str, str]:
    return {
        "job_id": message["job_id"],
        "execution_attempt_id": message["execution_attempt_id"],
    }


def _handle_ping(message: dict[str, Any]) -> None:
    _write_envelope(
        MESSAGE_JOB_RESULT,
        {"operation": OPERATION_PING, "output": {"pong": True, "protocol_version": PLUGIN_WORKER_PROTOCOL_VERSION}},
        **_job_ids(message),
    )


def _handle_echo(message: dict[str, Any]) -> None:
    echo = message["payload"].get("echo_payload") or ""
    _write_envelope(
        MESSAGE_JOB_RESULT,
        {"operation": OPERATION_ECHO_SAFE, "output": {"echo": echo}},
        **_job_ids(message),
    )


def _handle_sleep(message: dict[str, Any]) -> None:
    sleep_ms = int(message["payload"].get("sleep_ms") or 0)
    deadline = time.monotonic() + (sleep_ms / 1000.0)
    while time.monotonic() < deadline:
        if _CANCEL.is_set():
            _write_envelope(
                MESSAGE_JOB_ERROR,
                {"reason_code": REASON_CANCELLED},
                **_job_ids(message),
            )
            return
        time.sleep(0.02)
    _write_envelope(
        MESSAGE_JOB_RESULT,
        {"operation": OPERATION_SLEEP, "output": {"slept_ms": sleep_ms}},
        **_job_ids(message),
    )


def _handle_fixed(message: dict[str, Any]) -> None:
    _write_envelope(
        MESSAGE_JOB_RESULT,
        {"operation": OPERATION_RETURN_FIXED_RESULT, "output": {"fixed": "host-test-worker"}},
        **_job_ids(message),
    )


def _handle_crash(_message: dict[str, Any]) -> None:
    os._exit(17)


def _handle_malformed(_message: dict[str, Any]) -> None:
    payload = b"not-json"
    _write_raw(len(payload).to_bytes(4, "big") + payload)


def _handle_oversized(_message: dict[str, Any]) -> None:
    _write_raw((MAX_FRAME_BYTES + 1).to_bytes(4, "big"))


def _handle_truncated(_message: dict[str, Any]) -> None:
    _write_raw((32).to_bytes(4, "big") + b"{")
    sys.stdout.buffer.flush()
    os._exit(0)


def _handle_subprocess(message: dict[str, Any]) -> None:
    _write_envelope(
        MESSAGE_JOB_ERROR,
        {"reason_code": REASON_SUBPROCESS_PROHIBITED},
        **_job_ids(message),
    )


_OPERATIONS: dict[str, Callable[[dict[str, Any]], None]] = {
    OPERATION_PING: _handle_ping,
    OPERATION_ECHO_SAFE: _handle_echo,
    OPERATION_SLEEP: _handle_sleep,
    OPERATION_RETURN_FIXED_RESULT: _handle_fixed,
    OPERATION_CRASH_FOR_TEST: _handle_crash,
    OPERATION_EMIT_MALFORMED_FRAME_FOR_TEST: _handle_malformed,
    OPERATION_EMIT_OVERSIZED_FRAME_FOR_TEST: _handle_oversized,
    OPERATION_EMIT_TRUNCATED_FRAME_FOR_TEST: _handle_truncated,
    OPERATION_ATTEMPT_SUBPROCESS_FOR_TEST: _handle_subprocess,
}


def _handle_job_start(message: dict[str, Any]) -> None:
    global _CURRENT_JOB
    operation = message["payload"].get("operation")
    handler = _OPERATIONS.get(operation) if isinstance(operation, str) else None
    if handler is None:
        _write_envelope(
            MESSAGE_JOB_ERROR,
            {"reason_code": REASON_UNKNOWN_OPERATION},
            **_job_ids(message),
        )
        return
    with _LOCK:
        _CURRENT_JOB = _job_ids(message)
        _CANCEL.clear()
    try:
        handler(message)
    finally:
        with _LOCK:
            _CURRENT_JOB = None


def main() -> int:
    _handshake()
    reader = threading.Thread(target=_reader_loop, name="host-test-worker-reader", daemon=True)
    reader.start()
    while True:
        kind, item = _INCOMING.get()
        if kind == "eof":
            return 0
        if kind == "error":
            exc = item
            if isinstance(exc, ProtocolError) and exc.code == REASON_PROTOCOL_VERSION_MISMATCH:
                return 4
            if isinstance(exc, ProtocolError) and exc.code == REASON_HANDSHAKE_MALFORMED:
                return 2
            return 3
        if kind == "cancel":
            continue
        message = item
        message_type = message["message_type"]
        if message_type == MESSAGE_SHUTDOWN:
            return 0
        if message_type == MESSAGE_JOB_START:
            _handle_job_start(message)
            continue
        if message_type == MESSAGE_HELLO:
            return 2
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
