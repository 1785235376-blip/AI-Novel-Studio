"""Passive runtime observation: the missing level ②, without launching anything.

Why this module exists
----------------------
`app/model_center/discovery.py` observes level ① (a file exists), level ③ (the
endpoint answers our protocol) and level ④ (a model is recognisable), and it
refuses level ⑤ by design. Level ② — *does a runtime process actually exist* —
was never observed: `RuntimeInstance.process_alive` lives on the lifecycle object
that discovery never consults, so `DISCOVERED` only ever meant "the endpoint did
not answer". That gap was recorded in `PHASE10_RELEASE_HARDENING_REPORT.md` §5.2
and pinned by `tests/test_v2_discovery_runtime_levels.py`, which asserts the scan
report carries **no** process fact.

Consequences of that pin, and the reason this is a separate surface:

* This module must **not** add keys to the scan report. It returns its own
  immutable `RuntimeObservation`; nothing here mutates discovery state.
* Observation only. No launch, no install, no download, no repair, no write, and
  no child process of any kind. Every channel below is passive: a bounded TCP
  connect, the app's own managed process handle, and — on Windows — a read of the
  OS TCP table through `ctypes` (a syscall, not a subprocess).

The ladder (monotonic, and `READY` is unreachable by observation alone)
----------------------------------------------------------------------
===== ==================== ==================================================
level status               evidence that is actually required
===== ==================== ==================================================
0     NOT_OBSERVED         no evidence at all. Reported honestly instead of
                           calling an absent runtime "DISCOVERED".
1     DISCOVERED           a model artifact / configured file is known to exist
2     RUNTIME_AVAILABLE    a managed process handle is alive, **or** something
                           owns the configured loopback port
3     REACHABLE            the endpoint answered our protocol probe, not merely
                           accepted a connection
4     CAPABILITY_UNKNOWN   a model was recognised, but its capability is not
                           verified (the honest name: verified, but unknown)
5     READY                **real inference was verified elsewhere**. Observation
                           can never produce this level, so "level 1 is not
                           level 5" holds by construction rather than by review.
===== ==================== ==================================================
"""
from __future__ import annotations

import socket
import struct
import sys
from dataclasses import dataclass, field
from typing import Any, Callable

#: Ordered observation statuses: index == level. `NOT_OBSERVED` was added to the
#: five named statuses so that "nothing was observed" cannot be reported as the
#: level-1 status `DISCOVERED`, which would be an overstatement.
OBSERVATION_STATUSES: tuple[str, ...] = (
    "NOT_OBSERVED",
    "DISCOVERED",
    "RUNTIME_AVAILABLE",
    "REACHABLE",
    "CAPABILITY_UNKNOWN",
    "READY",
)

#: Levels 1-4 are observable. Level 5 is never produced by observation.
OBSERVABLE_LEVELS = 4

#: Bounded, conservative defaults: observation must never stall a scan.
DEFAULT_LISTENER_TIMEOUT = 0.25


@dataclass(frozen=True)
class RuntimeObservation:
    """What was *observed* about one runtime, with the evidence kept separate."""

    runtime_id: str
    status: str
    level: int
    artifact_present: bool = False
    managed_process_alive: bool | None = None
    listener_present: bool | None = None
    listener_owner: dict[str, Any] | None = None
    http_reachable: bool = False
    model_recognized: bool = False
    inference_verified: bool = False
    notes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_ready(self) -> bool:
        return self.status == "READY"

    def as_dict(self) -> dict[str, Any]:
        return {
            "runtime_id": self.runtime_id,
            "status": self.status,
            "level": self.level,
            "artifact_present": self.artifact_present,
            "managed_process_alive": self.managed_process_alive,
            "listener_present": self.listener_present,
            "listener_owner": self.listener_owner,
            "http_reachable": self.http_reachable,
            "model_recognized": self.model_recognized,
            "inference_verified": self.inference_verified,
            "observable_levels": OBSERVABLE_LEVELS,
            "notes": list(self.notes),
        }


def _status_for_level(level: int) -> str:
    if not 0 <= level < len(OBSERVATION_STATUSES):
        raise ValueError("RUNTIME_OBSERVATION_LEVEL_INVALID")
    return OBSERVATION_STATUSES[level]


def loopback_listener_present(host: str, port: int | None, *,
                             timeout: float = DEFAULT_LISTENER_TIMEOUT) -> bool | None:
    """Is *anything* accepting TCP connections on this loopback port?

    A completed TCP handshake is level ② evidence: some process is bound and
    listening. It is deliberately **not** level ③ — a listener that speaks a
    different protocol, or hangs before answering, is still only "available".

    Returns ``None`` when the question does not apply (no port configured).
    """
    if not port:
        return None
    try:
        with socket.create_connection((host, int(port)), timeout=timeout):
            return True
    except (OSError, ValueError):
        return False


# --- Windows owner identification (passive: reads the OS TCP table) ----------

_AF_INET = 2
_TCP_TABLE_OWNER_PID_LISTENER = 3
_ROW_SIZE = 24  # MIB_TCPROW_OWNER_PID: 6 x DWORD
_ERROR_INSUFFICIENT_BUFFER = 122
_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


def _decode_owner_table(data: bytes, port: int) -> list[dict[str, Any]]:
    """Pure decoder for a MIB_TCPTABLE_OWNER_PID buffer. Raises nothing on junk."""
    if len(data) < 4:
        return []
    (count,) = struct.unpack_from("<I", data, 0)
    owners: list[dict[str, Any]] = []
    for index in range(count):
        offset = 4 + index * _ROW_SIZE
        if offset + _ROW_SIZE > len(data):
            break
        state, local_addr, local_port, _remote_addr, _remote_port, pid = struct.unpack_from(
            "<IIIIII", data, offset
        )
        # dwLocalPort / dwLocalAddr are network byte order in the low words.
        decoded_port = ((local_port & 0xFF) << 8) | ((local_port >> 8) & 0xFF)
        if decoded_port != port:
            continue
        owners.append({
            "pid": int(pid),
            "state": int(state),
            "bind_address": socket.inet_ntoa(struct.pack("<I", local_addr)),
        })
    return owners


def windows_listener_owner(host: str, port: int | None) -> dict[str, Any] | None:
    """Identify the process that owns a listening loopback port, on Windows.

    Passive: `GetExtendedTcpTable` and `QueryFullProcessImageNameW` are syscalls
    in this process, so no child process is created. Returns ``None`` whenever the
    answer is unavailable (not Windows, no port, no listener, no permission) — the
    caller must treat ``None`` as "unidentified", never as "absent".
    """
    if sys.platform != "win32" or not port:
        return None
    try:
        import ctypes
        from ctypes import wintypes

        class MIB_TCPROW_OWNER_PID(ctypes.Structure):
            _fields_ = [
                ("dwState", wintypes.DWORD), ("dwLocalAddr", wintypes.DWORD),
                ("dwLocalPort", wintypes.DWORD), ("dwRemoteAddr", wintypes.DWORD),
                ("dwRemotePort", wintypes.DWORD), ("dwOwningPid", wintypes.DWORD),
            ]

        iphlpapi = ctypes.WinDLL("iphlpapi.dll")
        size = wintypes.DWORD(0)
        result = iphlpapi.GetExtendedTcpTable(
            None, ctypes.byref(size), False, _AF_INET, _TCP_TABLE_OWNER_PID_LISTENER, 0
        )
        if result not in (0, _ERROR_INSUFFICIENT_BUFFER) or size.value == 0:
            return None
        buffer = ctypes.create_string_buffer(size.value)
        result = iphlpapi.GetExtendedTcpTable(
            buffer, ctypes.byref(size), False, _AF_INET, _TCP_TABLE_OWNER_PID_LISTENER, 0
        )
        if result != 0:
            return None
        owners = _decode_owner_table(buffer.raw[: size.value], int(port))
        if not owners:
            return None
        owner = owners[0]
        kernel32 = ctypes.WinDLL("kernel32.dll")
        handle = kernel32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, owner["pid"])
        if not handle:
            return {**owner, "image_name": None, "identity_verified": False}
        try:
            name = ctypes.create_unicode_buffer(32768)
            length = wintypes.DWORD(len(name))
            if kernel32.QueryFullProcessImageNameW(handle, 0, name, ctypes.byref(length)):
                owner = {**owner, "image_name": name.value, "identity_verified": True}
            else:
                owner = {**owner, "image_name": None, "identity_verified": False}
        finally:
            kernel32.CloseHandle(handle)
        return owner
    except Exception:
        # Observation must never raise into a caller or a request handler.
        return None


def observe_runtime(
    runtime_id: str,
    *,
    host: str = "127.0.0.1",
    port: int | None = None,
    artifact_present: bool = False,
    managed_process_alive: bool | None = None,
    http_reachable: bool = False,
    model_recognized: bool = False,
    inference_verified: bool = False,
    listener_probe: Callable[..., bool | None] = loopback_listener_present,
    owner_probe: Callable[..., dict[str, Any] | None] = windows_listener_owner,
) -> RuntimeObservation:
    """Compose passive evidence into one observation. Never starts anything.

    ``inference_verified`` is accepted only so an *external* caller that really ran
    inference can record it; nothing in this module can set it. With the default
    arguments the maximum reachable status is ``CAPABILITY_UNKNOWN``.
    """
    notes: list[str] = []

    if inference_verified and not http_reachable:
        # A verified inference implies a reachable endpoint; refusing the
        # contradiction keeps a caller from hand-building a level 5 claim.
        raise ValueError("RUNTIME_OBSERVATION_INFERENCE_WITHOUT_REACHABILITY")

    listener: bool | None = None
    if http_reachable:
        # An answered protocol probe subsumes the handshake: a listener existed.
        listener = True
        notes.append("PROTOCOL_ANSWERED_IMPLIES_LISTENER")
    else:
        listener = listener_probe(host, port)
        if listener is None:
            notes.append("LISTENER_NOT_APPLICABLE")
        elif listener:
            notes.append("LOOPBACK_LISTENER_PRESENT")
        else:
            notes.append("NO_LOOPBACK_LISTENER")

    managed = managed_process_alive
    if managed:
        notes.append("MANAGED_PROCESS_ALIVE")
    elif managed is False and listener:
        notes.append("MANAGED_HANDLE_GONE_BUT_LISTENER_PRESENT")

    owner: dict[str, Any] | None = None
    if listener:
        owner = owner_probe(host, port)
        if owner:
            notes.append("LISTENER_OWNER_IDENTIFIED" if owner.get("identity_verified")
                         else "LISTENER_OWNER_UNVERIFIED")
        else:
            notes.append("LISTENER_OWNER_UNIDENTIFIED")

    runtime_exists = bool(managed) or bool(listener)
    if not runtime_exists:
        notes.append("RUNTIME_EXISTENCE_NOT_OBSERVED")

    if artifact_present:
        notes.append("ARTIFACT_PRESENT")
    if http_reachable:
        notes.append("HTTP_REACHABLE")
    if model_recognized:
        notes.append("MODEL_RECOGNIZED")
    if inference_verified:
        notes.append("INFERENCE_VERIFIED")
    else:
        notes.append("INFERENCE_NOT_OBSERVED")

    level = 1 if artifact_present else 0
    if runtime_exists:
        level = max(level, 2)
    if http_reachable:
        level = max(level, 3)
    if model_recognized and http_reachable:
        level = max(level, 4)
    if inference_verified:
        level = 5
    if level == 0:
        notes.append("NO_EVIDENCE_OBSERVED")
    if level >= 5 and not inference_verified:  # defensive: cannot happen
        raise AssertionError("RUNTIME_OBSERVATION_READY_WITHOUT_INFERENCE")

    return RuntimeObservation(
        runtime_id=runtime_id,
        status=_status_for_level(level),
        level=level,
        artifact_present=artifact_present,
        managed_process_alive=managed,
        listener_present=listener,
        listener_owner=owner,
        http_reachable=http_reachable,
        model_recognized=model_recognized,
        inference_verified=inference_verified,
        notes=tuple(dict.fromkeys(notes)),
    )


# --- capability layers: model vs task vs graph node -------------------------
#
# These three are deliberately *different* vocabularies and must never be
# compared to each other. Phase10 verified the mappings; this table records them
# in one place so a reader cannot mistake one layer for another.

CAPABILITY_LAYERS: dict[str, str] = {
    # Model Center registry capability (`app/model_center/domain.py::Capability`)
    "MODEL_CAPABILITY": "TEXT IMAGE VIDEO VISION TTS AUDIO EMBEDDING RERANK RESTORATION INTERPOLATION",
    # Task-layer vocabulary (`app/model_provider_contracts.py::TaskType`)
    "TASK_CAPABILITY": "TEXT_GENERATION IMAGE_GENERATION VIDEO_GENERATION",
    # Graph node binding names (not capabilities at all)
    "GRAPH_NODE_BINDING": "ASR (Whisper node binding), and other node-local names",
}

#: Task vocabulary -> model registry vocabulary. The only sanctioned crossing.
TASK_TO_MODEL_CAPABILITY: dict[str, str] = {
    "TEXT_GENERATION": "TEXT",
    "IMAGE_GENERATION": "IMAGE",
    "VIDEO_GENERATION": "VIDEO",
}


def model_capability_for_task(task_type: str) -> str:
    """Translate a task-layer name down to the model registry vocabulary."""
    try:
        return TASK_TO_MODEL_CAPABILITY[task_type]
    except KeyError:
        raise ValueError("TASK_CAPABILITY_UNKNOWN") from None
