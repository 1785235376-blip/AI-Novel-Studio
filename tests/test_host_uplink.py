import json

from app.packaging.host_uplink import (
    CREDENTIAL_PREFIX,
    PREFIX,
    PROTOCOL,
    encode_backend_credential,
    encode_host_ping,
    parse_host_credential,
    parse_host_ping,
)


def test_accepts_only_current_runtime_ping():
    assert parse_host_ping(encode_host_ping("runtime-a"), "runtime-a")
    assert not parse_host_ping(encode_host_ping("runtime-a"), "runtime-b")


def test_normal_output_and_wrong_prefix_are_not_control():
    assert not parse_host_ping("DESKTOP_SESSION_READY", "runtime-a")
    assert not parse_host_ping("{}", "runtime-a")


def test_malformed_unknown_missing_and_oversized_frames_are_rejected():
    assert not parse_host_ping(PREFIX + "not-json", "runtime-a")
    assert not parse_host_ping(PREFIX + json.dumps({"protocol": "wrong", "type": "PING", "runtime_instance_id": "runtime-a"}), "runtime-a")
    assert not parse_host_ping(PREFIX + json.dumps({"protocol": PROTOCOL, "type": "EXECUTE", "runtime_instance_id": "runtime-a"}), "runtime-a")
    assert not parse_host_ping(PREFIX + json.dumps({"protocol": PROTOCOL, "type": "PING"}), "runtime-a")
    assert not parse_host_ping(PREFIX + "x" * 3000, "runtime-a")


def test_credential_frames_preserve_each_supported_provider_without_exposing_secrets():
    providers = ("deepseek", "openai", "claude", "gemini", "ddshub", "custom")
    for provider in providers:
        value = {
            "protocol": "packaged-host-credential/v1",
            "type": "SET_PROVIDER_CREDENTIAL",
            "runtime_instance_id": "runtime-a",
            "provider": provider,
            "credential": "TEST_ONLY_" + provider,
        }
        parsed = parse_host_credential(
            CREDENTIAL_PREFIX + json.dumps(value, separators=(",", ":")), "runtime-a"
        )
        assert parsed == value
        forwarded = encode_backend_credential(parsed).decode()
        assert '"provider":"' + provider + '"' in forwarded
        assert "TEST_ONLY_" + provider in forwarded


def test_credential_allow_list_rejects_unknown_provider():
    value = {
        "protocol": "packaged-host-credential/v1",
        "type": "CLEAR_PROVIDER_CREDENTIAL",
        "runtime_instance_id": "runtime-a",
        "provider": "unknown",
    }
    assert parse_host_credential(
        CREDENTIAL_PREFIX + json.dumps(value, separators=(",", ":")), "runtime-a"
    ) is None
