"""Level ② observation: passive, bounded, and fail-closed at `READY`.

These tests pin `app/model_center/runtime_observation.py`, which fills the level-②
gap recorded in `PHASE10_RELEASE_HARDENING_REPORT.md` §5.2: discovery observed
levels ①③④ and refused ⑤, but never observed whether a runtime process exists.

Two properties matter more than any individual assertion:

* **observation alone can never reach level 5** — the exhaustive test below walks
  every combination of observable evidence and asserts `READY` is never produced;
* **nothing is launched** — the real code path is driven with `subprocess.Popen`
  poisoned, and the module source is checked for any child-process API.

The scan report is deliberately untouched: `tests/test_v2_discovery_runtime_levels.py`
asserts it carries no process fact, so level ② lives on this separate surface.
"""
from __future__ import annotations

import itertools
import socket
from pathlib import Path

import pytest

from app.model_center import runtime_observation as ro


def owner(pid: int = 4242, image: str = "ollama.exe", verified: bool = True):
    return {"pid": pid, "image_name": image, "identity_verified": verified,
            "bind_address": "127.0.0.1", "state": 2}


# --- the ladder ------------------------------------------------------------

def test_absent_runtime_is_not_reported_as_discovered():
    """No evidence must not be dressed up as the level-1 status."""
    result = ro.observe_runtime(
        "absent", listener_probe=lambda *a, **k: False, owner_probe=lambda *a, **k: None
    )
    assert result.status == "NOT_OBSERVED" and result.level == 0
    assert "NO_EVIDENCE_OBSERVED" in result.notes
    assert "RUNTIME_EXISTENCE_NOT_OBSERVED" in result.notes
    assert result.is_ready is False


def test_artifact_only_is_level_one_and_not_ready():
    result = ro.observe_runtime(
        "file-only", artifact_present=True,
        listener_probe=lambda *a, **k: False, owner_probe=lambda *a, **k: None,
    )
    assert result.status == "DISCOVERED" and result.level == 1
    assert "ARTIFACT_PRESENT" in result.notes and "INFERENCE_NOT_OBSERVED" in result.notes
    assert result.is_ready is False


def test_managed_handle_alive_is_level_two_without_any_listener():
    """The app only truly knows a process exists when it owns the handle."""
    result = ro.observe_runtime(
        "managed", managed_process_alive=True,
        listener_probe=lambda *a, **k: False, owner_probe=lambda *a, **k: None,
    )
    assert result.status == "RUNTIME_AVAILABLE" and result.level == 2
    assert "MANAGED_PROCESS_ALIVE" in result.notes
    assert result.listener_present is False


def test_listener_identifies_an_external_runtime_at_level_two():
    result = ro.observe_runtime(
        "external", port=11434,
        listener_probe=lambda *a, **k: True, owner_probe=lambda *a, **k: owner(),
    )
    assert result.status == "RUNTIME_AVAILABLE" and result.level == 2
    assert result.listener_owner["pid"] == 4242
    assert "LOOPBACK_LISTENER_PRESENT" in result.notes
    assert "LISTENER_OWNER_IDENTIFIED" in result.notes


def test_unverifiable_owner_is_recorded_as_unverified_not_as_proof():
    result = ro.observe_runtime(
        "external", port=11434,
        listener_probe=lambda *a, **k: True,
        owner_probe=lambda *a, **k: owner(verified=False, image=None),
    )
    assert result.listener_owner["identity_verified"] is False
    assert "LISTENER_OWNER_UNVERIFIED" in result.notes


def test_protocol_answer_is_reachable_and_not_ready():
    """A TCP handshake is level ②, an answered protocol probe is level ③."""
    result = ro.observe_runtime("reachable", port=11434, http_reachable=True,
                                owner_probe=lambda *a, **k: owner())
    assert result.status == "REACHABLE" and result.level == 3
    assert result.listener_present is True
    assert "PROTOCOL_ANSWERED_IMPLIES_LISTENER" in result.notes
    assert result.is_ready is False


def test_recognized_model_is_capability_unknown_and_not_ready():
    result = ro.observe_runtime("recognized", port=11434, http_reachable=True,
                                model_recognized=True, owner_probe=lambda *a, **k: owner())
    assert result.status == "CAPABILITY_UNKNOWN" and result.level == 4
    assert result.is_ready is False
    assert "MODEL_RECOGNIZED" in result.notes


def test_recognition_without_reachability_does_not_claim_level_four():
    """Model recognition is meaningless without an answered endpoint."""
    result = ro.observe_runtime(
        "contradiction", model_recognized=True,
        listener_probe=lambda *a, **k: False, owner_probe=lambda *a, **k: None,
    )
    assert result.level <= 1


@pytest.mark.parametrize("artifact,managed,listener,reachable,recognized", list(
    itertools.product([False, True], repeat=5)
))
def test_observation_alone_can_never_produce_ready(artifact, managed, listener, reachable, recognized):
    """Exhaustive: no combination of observable evidence yields READY."""
    result = ro.observe_runtime(
        "matrix",
        artifact_present=artifact,
        managed_process_alive=managed,
        http_reachable=reachable,
        model_recognized=recognized,
        listener_probe=lambda *a, **k: listener,
        owner_probe=lambda *a, **k: owner(),
    )
    assert result.status != "READY"
    assert result.level <= ro.OBSERVABLE_LEVELS
    assert result.inference_verified is False


def test_ready_requires_verified_inference_and_reachability():
    result = ro.observe_runtime("ready", port=11434, http_reachable=True,
                                model_recognized=True, inference_verified=True,
                                owner_probe=lambda *a, **k: owner())
    assert result.status == "READY" and result.level == 5 and result.is_ready is True
    assert "INFERENCE_VERIFIED" in result.notes


def test_verified_inference_without_reachability_is_refused():
    with pytest.raises(ValueError, match="RUNTIME_OBSERVATION_INFERENCE_WITHOUT_REACHABILITY"):
        ro.observe_runtime("bogus", inference_verified=True, http_reachable=False)


# --- observation is passive ------------------------------------------------

def test_observation_never_launches_a_process(monkeypatch):
    """Drive the real code path with Popen poisoned."""
    import subprocess

    def refuse(*args, **kwargs):  # pragma: no cover - must never run
        raise AssertionError("runtime observation must never launch a process")

    monkeypatch.setattr(subprocess, "Popen", refuse)
    # A closed loopback port drives the real default listener probe.
    probe = socket.socket()
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()

    result = ro.observe_runtime("passive", port=port)
    assert result.status in {"NOT_OBSERVED", "RUNTIME_AVAILABLE"}


def test_module_contains_no_child_process_or_launch_api():
    """Scan for real API usage; the module's prose may name what it refuses to do."""
    source = Path(ro.__file__).read_text(encoding="utf-8")
    for forbidden in ("import subprocess", "subprocess.Popen", "subprocess.run",
                      "subprocess.check_output", "os.system", "os.popen", "shell=True"):
        assert forbidden not in source, f"observation layer must not reference {forbidden}"


# --- pure owner-table decoding ---------------------------------------------

def _row(state: int, addr: bytes, port: int, remote_addr: bytes = b"\0\0\0\0",
         remote_port: int = 0, pid: int = 0) -> bytes:
    def net_port(value: int) -> int:
        return ((value & 0xFF) << 8) | ((value >> 8) & 0xFF)
    return b"".join(struct_pack_dword(v) for v in (
        state, struct_unpack_dword(addr), net_port(port),
        struct_unpack_dword(remote_addr), net_port(remote_port), pid,
    ))


def struct_pack_dword(value: int) -> bytes:
    import struct
    return struct.pack("<I", value & 0xFFFFFFFF)


def struct_unpack_dword(value: bytes) -> int:
    import struct
    return struct.unpack("<I", value)[0]


def test_owner_table_decoder_finds_the_matching_port_only():
    import struct

    other = _row(2, socket.inet_aton("127.0.0.1"), 1234, pid=111)
    match = _row(2, socket.inet_aton("127.0.0.1"), 11434, pid=222)
    wildcard = _row(2, socket.inet_aton("0.0.0.0"), 11434, pid=333)
    table = struct.pack("<I", 3) + other + match + wildcard

    owners = ro._decode_owner_table(table, 11434)
    assert [item["pid"] for item in owners] == [222, 333]
    assert owners[0]["bind_address"] == "127.0.0.1"
    assert owners[1]["bind_address"] == "0.0.0.0"
    assert ro._decode_owner_table(table, 9999) == []


def test_owner_table_decoder_tolerates_truncated_and_empty_buffers():
    assert ro._decode_owner_table(b"", 80) == []
    assert ro._decode_owner_table(b"\x01\x00\x00\x00", 80) == []      # claims 1 row, none present
    assert ro._decode_owner_table(b"\xff\xff\xff\xff" + b"\x00" * 8, 80) == []


def test_owner_probe_returns_none_when_unavailable_never_raises():
    """Unavailable must be None ("unidentified"), never False ("absent")."""
    assert ro.windows_listener_owner("127.0.0.1", None) is None
    assert isinstance(ro.loopback_listener_present("127.0.0.1", None), type(None))


# --- the three capability layers must not be conflated ---------------------

def test_capability_layers_are_distinct_vocabularies():
    assert "ASR" not in ro.CAPABILITY_LAYERS["MODEL_CAPABILITY"]
    assert "ASR" in ro.CAPABILITY_LAYERS["GRAPH_NODE_BINDING"]
    assert ro.CAPABILITY_LAYERS["TASK_CAPABILITY"] == (
        "TEXT_GENERATION IMAGE_GENERATION VIDEO_GENERATION"
    )


def test_task_vocabulary_maps_down_to_model_vocabulary():
    assert ro.model_capability_for_task("IMAGE_GENERATION") == "IMAGE"
    assert ro.model_capability_for_task("TEXT_GENERATION") == "TEXT"
    assert ro.model_capability_for_task("VIDEO_GENERATION") == "VIDEO"
    with pytest.raises(ValueError, match="TASK_CAPABILITY_UNKNOWN"):
        ro.model_capability_for_task("ASR")


def test_observation_payload_is_json_shaped_and_declares_its_ceiling():
    result = ro.observe_runtime("payload", artifact_present=True,
                                listener_probe=lambda *a, **k: False,
                                owner_probe=lambda *a, **k: None)
    payload = result.as_dict()
    assert payload["status"] == "DISCOVERED" and payload["level"] == 1
    assert payload["observable_levels"] == 4
    assert payload["inference_verified"] is False
    assert isinstance(payload["notes"], list)
