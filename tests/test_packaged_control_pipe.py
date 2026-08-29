import io
import json
import time

import pytest

from app.credential_vault import CredentialVault
from app.packaging import control_pipe
from app.packaging.control_pipe import (
    CREDENTIAL_PROTOCOL,
    PROTOCOL,
    PackagedControlReader,
    credential_store,
    encode_ping,
)


def wait_for_ping(reader, expected=1):
    deadline = time.monotonic() + 1
    while time.monotonic() < deadline and reader.ping_count < expected:
        time.sleep(0.01)
    return reader.ping_count


@pytest.fixture
def isolated_process_credential_store(monkeypatch):
    """Inject a test-owned memory vault into the control-pipe module only.

    Does not change production default vault selection and does not touch
    real keyring or Windows Credential Manager.
    """
    vault = CredentialVault(backend="memory")
    original_values = dict(credential_store._values)
    monkeypatch.setattr(control_pipe, "credential_vault", vault)
    credential_store._values.clear()
    try:
        yield vault
    finally:
        credential_store._values.clear()
        credential_store._values.update(original_values)


def test_runtime_bound_ping_is_accepted_without_response_or_logging():
    stream = io.BytesIO(encode_ping("runtime-a"))
    reader = PackagedControlReader("runtime-a", stream)
    reader.start()
    assert wait_for_ping(reader) == 1


def test_wrong_runtime_is_rejected():
    stream = io.BytesIO(encode_ping("runtime-b"))
    reader = PackagedControlReader("runtime-a", stream)
    reader.start()
    time.sleep(0.05)
    assert reader.ping_count == 0


def test_malformed_unknown_and_oversized_frames_are_ignored():
    unknown = {"protocol": PROTOCOL, "type": "execute", "runtime_instance_id": "runtime-a"}
    stream = io.BytesIO(b"not-json\n" + json.dumps(unknown).encode() + b"\n" + b"x" * 5000 + b"\n" + encode_ping("runtime-a"))
    reader = PackagedControlReader("runtime-a", stream)
    reader.start()
    assert wait_for_ping(reader) == 1


def test_eof_is_safe_and_nonpackaged_mode_does_not_start_reader(monkeypatch):
    reader = PackagedControlReader("runtime-a", io.BytesIO(b""))
    reader.start()
    time.sleep(0.02)
    assert reader.ping_count == 0
    monkeypatch.setenv("PACKAGED_WINDOWS_MODE", "false")
    from app.packaging import control_pipe
    assert control_pipe.start_packaged_control_reader() is None


def test_packaged_reader_uses_authoritative_runtime_environment(monkeypatch):
    from app.packaging import control_pipe
    started = []
    monkeypatch.setenv("PACKAGED_WINDOWS_MODE", "true")
    monkeypatch.setenv("PACKAGED_RUNTIME_INSTANCE_ID", "runtime-formal")
    monkeypatch.setattr(control_pipe.PackagedControlReader, "start", lambda self: started.append(self.runtime_instance_id))
    reader = control_pipe.start_packaged_control_reader()
    assert reader is not None
    assert reader.runtime_instance_id == "runtime-formal"
    assert started == ["runtime-formal"]


def test_packaged_reader_fails_closed_without_authoritative_runtime_environment(monkeypatch):
    from app.packaging import control_pipe
    monkeypatch.setenv("PACKAGED_WINDOWS_MODE", "true")
    monkeypatch.delenv("PACKAGED_RUNTIME_INSTANCE_ID", raising=False)
    monkeypatch.setenv("RUNTIME_INSTANCE_ID", "legacy-name-must-not-start-reader")
    assert control_pipe.start_packaged_control_reader() is None


def test_reader_start_status_reports_invocation_and_missing_env(monkeypatch):
    from app.packaging import control_pipe
    monkeypatch.setenv("PACKAGED_WINDOWS_MODE", "true")
    monkeypatch.delenv("PACKAGED_RUNTIME_INSTANCE_ID", raising=False)
    assert control_pipe.start_packaged_control_reader() is None
    status = control_pipe.get_packaged_control_reader_status()
    assert status["invoked"] is True
    assert status["runtime_env_present"] is False
    assert status["stdin_available"] is False
    assert status["start_result"] == "MISSING_RUNTIME_INSTANCE_ID"


def test_reader_start_status_reports_started(monkeypatch):
    from app.packaging import control_pipe
    monkeypatch.setenv("PACKAGED_WINDOWS_MODE", "true")
    monkeypatch.setenv("PACKAGED_RUNTIME_INSTANCE_ID", "runtime-status")
    monkeypatch.setattr(control_pipe, "sys", type("S", (), {"stdin": type("I", (), {"buffer": io.BytesIO()})()})())
    reader = control_pipe.start_packaged_control_reader()
    status = control_pipe.get_packaged_control_reader_status()
    assert reader is not None
    assert status["invoked"] is True
    assert status["runtime_env_present"] is True
    assert status["stdin_available"] is True
    assert status["start_result"] == "STARTED"


def test_reader_accepts_all_supported_provider_credentials_and_clear_is_scoped(
    isolated_process_credential_store,
):
    providers = ("deepseek", "openai", "claude", "gemini", "ddshub", "custom")
    frames = []
    for provider in providers:
        frames.append(json.dumps({
            "protocol": CREDENTIAL_PROTOCOL,
            "type": "SET_PROVIDER_CREDENTIAL",
            "runtime_instance_id": "runtime-a",
            "provider": provider,
            "credential": "TEST_ONLY_" + provider,
        }, separators=(",", ":")).encode() + b"\n")
    reader = PackagedControlReader("runtime-a", io.BytesIO(b"".join(frames)))
    reader._read()
    try:
        for provider in providers:
            assert credential_store.resolve(provider) == "TEST_ONLY_" + provider
        clear = json.dumps({
            "protocol": CREDENTIAL_PROTOCOL,
            "type": "CLEAR_PROVIDER_CREDENTIAL",
            "runtime_instance_id": "runtime-a",
            "provider": "ddshub",
        }, separators=(",", ":")).encode() + b"\n"
        PackagedControlReader("runtime-a", io.BytesIO(clear))._read()
        assert credential_store.resolve("ddshub") is None
        assert credential_store.resolve("openai") == "TEST_ONLY_openai"
    finally:
        for provider in providers:
            credential_store.clear(provider)
