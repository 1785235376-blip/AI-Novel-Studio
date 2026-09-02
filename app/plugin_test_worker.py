"""Host-owned Test Worker process (Phase 2A).

Fixed operations only. Not a plugin, not extensible, not a command runner.
Does not read the database, vault, providers, plugin packages, or arbitrary
network. Does not eval/exec/import user modules. Generic child processes are
prohibited. Fixed sandbox probes (read/write/token/loopback/child) exist only
for Host-owned Phase 2B tests and never accept arbitrary paths, URLs, or
commands.

Run only via the frozen supervisor spawn:
`python -I -S -u <absolute-host-owned-bootstrap>`.
The bootstrap is `app/plugin_test_worker_bootstrap.py`. Do not launch this
module through inherited PYTHONPATH or `python -m`.
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
    OPERATION_PROBE_ALLOWED_READ,
    OPERATION_PROBE_ALLOWED_WRITE,
    OPERATION_PROBE_CHILD_PROCESS,
    OPERATION_PROBE_FORBIDDEN_HOST_READ,
    OPERATION_PROBE_FORBIDDEN_HOST_WRITE,
    OPERATION_PROBE_NETWORK,
    OPERATION_PROBE_TOKEN_IDENTITY,
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


def _sandbox_env(name: str) -> str:
    value = os.environ.get(name, "")
    return value if isinstance(value, str) else ""


def _result(message: dict[str, Any], operation: str, output: dict[str, Any]) -> None:
    _write_envelope(MESSAGE_JOB_RESULT, {"operation": operation, "output": output}, **_job_ids(message))


def _handle_probe_allowed_read(message: dict[str, Any]) -> None:
    path = os.path.join(_sandbox_env("ANS_SANDBOX_IN"), "input.txt")
    ok = False
    text = ""
    try:
        with open(path, "r", encoding="utf-8") as handle:
            text = handle.read(64)
        ok = text == "SANDBOX_INPUT_OK"
    except OSError:
        ok = False
        text = ""
    _result(message, OPERATION_PROBE_ALLOWED_READ, {"ok": ok, "matched": text == "SANDBOX_INPUT_OK"})


def _handle_probe_allowed_write(message: dict[str, Any]) -> None:
    out_path = os.path.join(_sandbox_env("ANS_SANDBOX_OUT"), "output.txt")
    in_path = os.path.join(_sandbox_env("ANS_SANDBOX_IN"), "should_fail.txt")
    tmp_path = os.path.join(_sandbox_env("ANS_SANDBOX_TMP"), "tmp.txt")
    out_ok = False
    in_denied = False
    tmp_ok = False
    try:
        with open(out_path, "w", encoding="utf-8") as handle:
            handle.write("SANDBOX_OUTPUT_OK")
        out_ok = True
    except OSError:
        out_ok = False
    try:
        with open(in_path, "w", encoding="utf-8") as handle:
            handle.write("SHOULD_NOT_LAND")
        in_denied = False
    except OSError:
        in_denied = True
    try:
        with open(tmp_path, "w", encoding="utf-8") as handle:
            handle.write("SANDBOX_TMP_OK")
        tmp_ok = True
    except OSError:
        tmp_ok = False
    _result(
        message,
        OPERATION_PROBE_ALLOWED_WRITE,
        {"output_ok": out_ok, "input_write_denied": in_denied, "tmp_ok": tmp_ok},
    )


def _handle_probe_forbidden_read(message: dict[str, Any]) -> None:
    path = _sandbox_env("ANS_PROBE_FORBIDDEN_READ")
    denied = True
    leaked = False
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = handle.read(4096)
        denied = False
        leaked = bool(data)
    except OSError:
        denied = True
        leaked = False
    _result(message, OPERATION_PROBE_FORBIDDEN_HOST_READ, {"denied": denied, "secret_leaked": leaked})


def _handle_probe_forbidden_write(message: dict[str, Any]) -> None:
    path = _sandbox_env("ANS_PROBE_FORBIDDEN_WRITE")
    denied = True
    try:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("PWNED")
        denied = False
    except OSError:
        denied = True
    _result(message, OPERATION_PROBE_FORBIDDEN_HOST_WRITE, {"denied": denied})


def _handle_probe_network(message: dict[str, Any]) -> None:
    denied = True
    raw = _sandbox_env("ANS_PROBE_LOOPBACK_PORT")
    try:
        port = int(raw)
        if 0 < port < 65536:
            import socket

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.4)
            try:
                sock.connect(("127.0.0.1", port))
                denied = False
            except OSError:
                denied = True
            finally:
                sock.close()
    except (ValueError, OSError):
        denied = True
    _result(message, OPERATION_PROBE_NETWORK, {"denied": denied, "loopback": True})


def _handle_probe_child(message: dict[str, Any]) -> None:
    denied = True
    try:
        pid = os.spawnv(os.P_NOWAIT, sys.executable, (sys.executable, "-c", "raise SystemExit(0)"))
        denied = False
        if isinstance(pid, int) and pid > 0:
            try:
                os.waitpid(pid, os.WNOHANG if hasattr(os, "WNOHANG") else 0)
            except OSError:
                pass
    except OSError:
        denied = True
    _result(message, OPERATION_PROBE_CHILD_PROCESS, {"denied": denied})


def _handle_probe_token(message: dict[str, Any]) -> None:
    is_appcontainer = False
    sid_present = False
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes

            advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            token = wintypes.HANDLE()
            TOKEN_QUERY = 0x0008
            if advapi32.OpenProcessToken(kernel32.GetCurrentProcess(), TOKEN_QUERY, ctypes.byref(token)):
                value = wintypes.DWORD()
                needed = wintypes.DWORD()
                TokenIsAppContainer = 19
                TokenAppContainerSid = 31
                if advapi32.GetTokenInformation(
                    token, TokenIsAppContainer, ctypes.byref(value), ctypes.sizeof(value), ctypes.byref(needed)
                ):
                    is_appcontainer = int(value.value) != 0
                needed = wintypes.DWORD(0)
                advapi32.GetTokenInformation(token, TokenAppContainerSid, None, 0, ctypes.byref(needed))
                if needed.value:
                    buf = ctypes.create_string_buffer(needed.value)
                    if advapi32.GetTokenInformation(token, TokenAppContainerSid, buf, needed, ctypes.byref(needed)):
                        sid_present = True
                kernel32.CloseHandle(token)
        except Exception:
            is_appcontainer = False
            sid_present = False
    _result(
        message,
        OPERATION_PROBE_TOKEN_IDENTITY,
        {"is_appcontainer": is_appcontainer, "appcontainer_sid_present": sid_present},
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
    OPERATION_PROBE_ALLOWED_READ: _handle_probe_allowed_read,
    OPERATION_PROBE_ALLOWED_WRITE: _handle_probe_allowed_write,
    OPERATION_PROBE_FORBIDDEN_HOST_READ: _handle_probe_forbidden_read,
    OPERATION_PROBE_FORBIDDEN_HOST_WRITE: _handle_probe_forbidden_write,
    OPERATION_PROBE_NETWORK: _handle_probe_network,
    OPERATION_PROBE_CHILD_PROCESS: _handle_probe_child,
    OPERATION_PROBE_TOKEN_IDENTITY: _handle_probe_token,
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
