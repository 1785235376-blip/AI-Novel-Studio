"""Versioned, bounded IPC for the Host-owned Test Worker (Phase 2A).

Length-prefixed JSON frames over inherited stdin/stdout. Fail-closed:
unknown fields, unknown types, version mismatch, oversized/truncated/
malformed frames, and trailing garbage are rejected. This module is
stdlib-only so the worker process does not import the rest of the host.

This is not a plugin API. It is not a generic RPC bus.
"""

from __future__ import annotations

import json
import re
import struct
import uuid
from typing import Any, Mapping

PLUGIN_WORKER_PROTOCOL_VERSION = "1"
HOST_TEST_WORKER_IDENTITY = "host.test_worker"

MAX_FRAME_BYTES = 64 * 1024
MAX_JSON_DEPTH = 8
MAX_JSON_KEYS = 32
MAX_JSON_LIST = 32
MAX_STDERR_BYTES = 8 * 1024
MAX_TOTAL_OUTPUT_BYTES = 64 * 1024
MAX_ECHO_CHARS = 1024
HEADER_STRUCT = struct.Struct(">I")

MESSAGE_HELLO = "HELLO"
MESSAGE_READY = "READY"
MESSAGE_JOB_START = "JOB_START"
MESSAGE_JOB_RESULT = "JOB_RESULT"
MESSAGE_JOB_ERROR = "JOB_ERROR"
MESSAGE_CANCEL = "CANCEL"
MESSAGE_SHUTDOWN = "SHUTDOWN"

MESSAGE_TYPES = frozenset({
    MESSAGE_HELLO,
    MESSAGE_READY,
    MESSAGE_JOB_START,
    MESSAGE_JOB_RESULT,
    MESSAGE_JOB_ERROR,
    MESSAGE_CANCEL,
    MESSAGE_SHUTDOWN,
})

ENVELOPE_FIELDS = frozenset({
    "protocol_version",
    "message_type",
    "job_id",
    "execution_attempt_id",
    "message_id",
    "payload",
})

OPERATION_PING = "PING"
OPERATION_ECHO_SAFE = "ECHO_SAFE"
OPERATION_SLEEP = "SLEEP"
OPERATION_RETURN_FIXED_RESULT = "RETURN_FIXED_RESULT"
OPERATION_CRASH_FOR_TEST = "CRASH_FOR_TEST"
OPERATION_EMIT_MALFORMED_FRAME_FOR_TEST = "EMIT_MALFORMED_FRAME_FOR_TEST"
OPERATION_EMIT_OVERSIZED_FRAME_FOR_TEST = "EMIT_OVERSIZED_FRAME_FOR_TEST"
OPERATION_EMIT_TRUNCATED_FRAME_FOR_TEST = "EMIT_TRUNCATED_FRAME_FOR_TEST"
OPERATION_ATTEMPT_SUBPROCESS_FOR_TEST = "ATTEMPT_SUBPROCESS_FOR_TEST"
OPERATION_PROBE_ALLOWED_READ = "PROBE_ALLOWED_READ"
OPERATION_PROBE_ALLOWED_WRITE = "PROBE_ALLOWED_WRITE"
OPERATION_PROBE_FORBIDDEN_HOST_READ = "PROBE_FORBIDDEN_HOST_READ"
OPERATION_PROBE_FORBIDDEN_HOST_WRITE = "PROBE_FORBIDDEN_HOST_WRITE"
OPERATION_PROBE_NETWORK = "PROBE_NETWORK"
OPERATION_PROBE_CHILD_PROCESS = "PROBE_CHILD_PROCESS"
OPERATION_PROBE_TOKEN_IDENTITY = "PROBE_TOKEN_IDENTITY"

WORKER_OPERATIONS = frozenset({
    OPERATION_PING,
    OPERATION_ECHO_SAFE,
    OPERATION_SLEEP,
    OPERATION_RETURN_FIXED_RESULT,
    OPERATION_CRASH_FOR_TEST,
    OPERATION_EMIT_MALFORMED_FRAME_FOR_TEST,
    OPERATION_EMIT_OVERSIZED_FRAME_FOR_TEST,
    OPERATION_EMIT_TRUNCATED_FRAME_FOR_TEST,
    OPERATION_ATTEMPT_SUBPROCESS_FOR_TEST,
    OPERATION_PROBE_ALLOWED_READ,
    OPERATION_PROBE_ALLOWED_WRITE,
    OPERATION_PROBE_FORBIDDEN_HOST_READ,
    OPERATION_PROBE_FORBIDDEN_HOST_WRITE,
    OPERATION_PROBE_NETWORK,
    OPERATION_PROBE_CHILD_PROCESS,
    OPERATION_PROBE_TOKEN_IDENTITY,
})

PAYLOAD_KEYS: dict[str, frozenset[str]] = {
    MESSAGE_HELLO: frozenset({"worker_identity", "session_nonce"}),
    MESSAGE_READY: frozenset({"worker_identity", "session_nonce"}),
    MESSAGE_JOB_START: frozenset({"operation", "echo_payload", "sleep_ms"}),
    MESSAGE_JOB_RESULT: frozenset({"operation", "output"}),
    MESSAGE_JOB_ERROR: frozenset({"reason_code", "exit_status"}),
    MESSAGE_CANCEL: frozenset(),
    MESSAGE_SHUTDOWN: frozenset(),
}

MESSAGES_WITHOUT_JOB = frozenset({MESSAGE_HELLO, MESSAGE_READY, MESSAGE_SHUTDOWN})

UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
NONCE_RE = re.compile(r"^[0-9a-f]{32}$")
REASON_RE = re.compile(r"^[A-Z][A-Z0-9_]{2,78}$")
ECHO_RE = re.compile(r"^[A-Za-z0-9._\- ]{0,1024}$")

REASON_PROTOCOL_VERSION_MISMATCH = "PROTOCOL_VERSION_MISMATCH"
REASON_MALFORMED_FRAME = "MALFORMED_FRAME"
REASON_OVERSIZED_FRAME = "OVERSIZED_FRAME"
REASON_TRUNCATED_FRAME = "TRUNCATED_FRAME"
REASON_UNKNOWN_MESSAGE_TYPE = "UNKNOWN_MESSAGE_TYPE"
REASON_UNKNOWN_FIELD = "UNKNOWN_FIELD"
REASON_INVALID_UTF8 = "INVALID_UTF8"
REASON_TRAILING_GARBAGE = "TRAILING_GARBAGE"
REASON_HANDSHAKE_TIMEOUT = "HANDSHAKE_TIMEOUT"
REASON_HANDSHAKE_MALFORMED = "HANDSHAKE_MALFORMED"
REASON_WORKER_CRASH = "WORKER_CRASH"
REASON_WORKER_TIMEOUT = "WORKER_TIMEOUT"
REASON_OUTPUT_QUOTA_EXCEEDED = "OUTPUT_QUOTA_EXCEEDED"
REASON_SUBPROCESS_PROHIBITED = "SUBPROCESS_PROHIBITED"
REASON_WORKER_IDENTITY_MISMATCH = "WORKER_IDENTITY_MISMATCH"
REASON_SESSION_NONCE_MISMATCH = "SESSION_NONCE_MISMATCH"
REASON_MISSING_JOB_IDENTITY = "MISSING_JOB_IDENTITY"
REASON_UNKNOWN_OPERATION = "UNKNOWN_OPERATION"
REASON_CANCELLED = "CANCELLED"
REASON_INVALID_JSON = "INVALID_JSON"
REASON_INVALID_JSON_STRUCTURE = "INVALID_JSON_STRUCTURE"


class ProtocolError(ValueError):
    def __init__(self, code: str, message: str | None = None):
        self.code = code
        super().__init__(message or code)


def new_message_id() -> str:
    return str(uuid.uuid4())


def new_session_nonce() -> str:
    return uuid.uuid4().hex


def _bounded_json(value: Any, *, depth: int = 0) -> None:
    if depth > MAX_JSON_DEPTH:
        raise ProtocolError(REASON_INVALID_JSON_STRUCTURE)
    if isinstance(value, dict):
        if len(value) > MAX_JSON_KEYS:
            raise ProtocolError(REASON_INVALID_JSON_STRUCTURE)
        for key, item in value.items():
            if not isinstance(key, str):
                raise ProtocolError(REASON_INVALID_JSON_STRUCTURE)
            _bounded_json(item, depth=depth + 1)
        return
    if isinstance(value, list):
        if len(value) > MAX_JSON_LIST:
            raise ProtocolError(REASON_INVALID_JSON_STRUCTURE)
        for item in value:
            _bounded_json(item, depth=depth + 1)
        return
    if value is None or isinstance(value, (str, int, float, bool)):
        if isinstance(value, bool):
            return
        if isinstance(value, int) and not isinstance(value, bool) and abs(value) > 10**12:
            raise ProtocolError(REASON_INVALID_JSON_STRUCTURE)
        return
    raise ProtocolError(REASON_INVALID_JSON_STRUCTURE)


def encode_frame(message: Mapping[str, Any]) -> bytes:
    payload = json.dumps(message, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
    if len(payload) > MAX_FRAME_BYTES:
        raise ProtocolError(REASON_OVERSIZED_FRAME)
    return HEADER_STRUCT.pack(len(payload)) + payload


def decode_frame_payload(payload: bytes) -> dict[str, Any]:
    if len(payload) > MAX_FRAME_BYTES:
        raise ProtocolError(REASON_OVERSIZED_FRAME)
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ProtocolError(REASON_INVALID_UTF8) from exc
    try:
        obj, index = json.JSONDecoder().raw_decode(text)
    except json.JSONDecodeError as exc:
        raise ProtocolError(REASON_INVALID_JSON) from exc
    if index != len(text):
        raise ProtocolError(REASON_TRAILING_GARBAGE)
    if not isinstance(obj, dict):
        raise ProtocolError(REASON_MALFORMED_FRAME)
    _bounded_json(obj)
    return obj


def parse_envelope(payload: bytes) -> dict[str, Any]:
    obj = decode_frame_payload(payload)
    unknown = set(obj) - ENVELOPE_FIELDS
    if unknown:
        raise ProtocolError(REASON_UNKNOWN_FIELD)
    missing = ENVELOPE_FIELDS - set(obj)
    if missing:
        raise ProtocolError(REASON_MALFORMED_FRAME)
    version = obj["protocol_version"]
    if version != PLUGIN_WORKER_PROTOCOL_VERSION:
        raise ProtocolError(REASON_PROTOCOL_VERSION_MISMATCH)
    message_type = obj["message_type"]
    if not isinstance(message_type, str) or message_type not in MESSAGE_TYPES:
        raise ProtocolError(REASON_UNKNOWN_MESSAGE_TYPE)
    message_id = obj["message_id"]
    if not isinstance(message_id, str) or not UUID_RE.fullmatch(message_id):
        raise ProtocolError(REASON_MALFORMED_FRAME)
    job_id = obj["job_id"]
    attempt_id = obj["execution_attempt_id"]
    if message_type in MESSAGES_WITHOUT_JOB:
        if job_id is not None or attempt_id is not None:
            raise ProtocolError(REASON_MALFORMED_FRAME)
    else:
        if not isinstance(job_id, str) or not UUID_RE.fullmatch(job_id):
            raise ProtocolError(REASON_MISSING_JOB_IDENTITY)
        if not isinstance(attempt_id, str) or not UUID_RE.fullmatch(attempt_id):
            raise ProtocolError(REASON_MISSING_JOB_IDENTITY)
    body = obj["payload"]
    if not isinstance(body, dict):
        raise ProtocolError(REASON_MALFORMED_FRAME)
    allowed = PAYLOAD_KEYS[message_type]
    extra = set(body) - allowed
    if extra:
        raise ProtocolError(REASON_UNKNOWN_FIELD)
    _validate_payload(message_type, body)
    return obj


def _validate_payload(message_type: str, body: dict[str, Any]) -> None:
    if message_type in {MESSAGE_HELLO, MESSAGE_READY}:
        identity = body.get("worker_identity")
        nonce = body.get("session_nonce")
        if identity != HOST_TEST_WORKER_IDENTITY:
            raise ProtocolError(REASON_WORKER_IDENTITY_MISMATCH)
        if not isinstance(nonce, str) or not NONCE_RE.fullmatch(nonce):
            raise ProtocolError(REASON_HANDSHAKE_MALFORMED)
        return
    if message_type == MESSAGE_JOB_START:
        operation = body.get("operation")
        if operation not in WORKER_OPERATIONS:
            raise ProtocolError(REASON_UNKNOWN_OPERATION)
        if "echo_payload" in body and body["echo_payload"] is not None:
            echo = body["echo_payload"]
            if not isinstance(echo, str) or len(echo) > MAX_ECHO_CHARS or not ECHO_RE.fullmatch(echo):
                raise ProtocolError(REASON_MALFORMED_FRAME)
        if "sleep_ms" in body and body["sleep_ms"] is not None:
            sleep_ms = body["sleep_ms"]
            if not isinstance(sleep_ms, int) or isinstance(sleep_ms, bool) or sleep_ms < 0 or sleep_ms > 10_000:
                raise ProtocolError(REASON_MALFORMED_FRAME)
        return
    if message_type == MESSAGE_JOB_RESULT:
        operation = body.get("operation")
        if operation not in WORKER_OPERATIONS:
            raise ProtocolError(REASON_UNKNOWN_OPERATION)
        if "output" in body:
            _bounded_json(body["output"])
        return
    if message_type == MESSAGE_JOB_ERROR:
        reason = body.get("reason_code")
        if not isinstance(reason, str) or not REASON_RE.fullmatch(reason):
            raise ProtocolError(REASON_MALFORMED_FRAME)
        if "exit_status" in body and body["exit_status"] is not None:
            status = body["exit_status"]
            if not isinstance(status, int) or isinstance(status, bool) or status < 0 or status > 255:
                raise ProtocolError(REASON_MALFORMED_FRAME)
        return


def build_envelope(
    message_type: str,
    payload: dict[str, Any] | None = None,
    *,
    job_id: str | None = None,
    execution_attempt_id: str | None = None,
    message_id: str | None = None,
    protocol_version: str = PLUGIN_WORKER_PROTOCOL_VERSION,
) -> dict[str, Any]:
    return {
        "protocol_version": protocol_version,
        "message_type": message_type,
        "job_id": job_id,
        "execution_attempt_id": execution_attempt_id,
        "message_id": message_id or new_message_id(),
        "payload": payload or {},
    }


def validate_handshake(*, hello: Mapping[str, Any], ready: Mapping[str, Any]) -> None:
    if hello.get("protocol_version") != PLUGIN_WORKER_PROTOCOL_VERSION:
        raise ProtocolError(REASON_PROTOCOL_VERSION_MISMATCH)
    if ready.get("protocol_version") != hello.get("protocol_version"):
        raise ProtocolError(REASON_PROTOCOL_VERSION_MISMATCH)
    if hello.get("message_type") != MESSAGE_HELLO or ready.get("message_type") != MESSAGE_READY:
        raise ProtocolError(REASON_HANDSHAKE_MALFORMED)
    hello_payload = hello.get("payload") or {}
    ready_payload = ready.get("payload") or {}
    if hello_payload.get("worker_identity") != HOST_TEST_WORKER_IDENTITY:
        raise ProtocolError(REASON_WORKER_IDENTITY_MISMATCH)
    if ready_payload.get("worker_identity") != HOST_TEST_WORKER_IDENTITY:
        raise ProtocolError(REASON_WORKER_IDENTITY_MISMATCH)
    if hello_payload.get("session_nonce") != ready_payload.get("session_nonce"):
        raise ProtocolError(REASON_SESSION_NONCE_MISMATCH)
