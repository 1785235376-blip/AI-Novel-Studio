from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

import pytest

from app.plugin_trust_contracts import (
    ALLOWED_DIGEST_ALGORITHMS,
    EXECUTION_SUPPORTED,
    PLUGIN_DIGEST_MALFORMED,
    PLUGIN_SIGNATURE_POLICY_VERSION,
    PLUGIN_TRUST_COMMAND_FORBIDDEN,
    PLUGIN_TRUST_CONTRACT_INVALID,
    PLUGIN_TRUST_SECRET_FIELD_FORBIDDEN,
    PLUGIN_TRUST_UNKNOWN_FIELD,
    PluginPublisherIdentity,
    PluginRevocationRecord,
    PluginSignatureDescriptor,
    PluginTrustContractError,
    PluginTrustDecision,
    PluginTrustEvaluationInput,
    PluginTrustState,
    PluginVerificationEvidence,
    PublisherIdentityKind,
    RevocationSubjectType,
    VerificationOutcome,
    VerificationProvenance,
    dump_without_secrets,
    inspect_forbidden_payload,
    parse_digest,
)


REPO = Path(__file__).resolve().parents[1]
CONTRACTS = REPO / "app" / "plugin_trust_contracts.py"
FIXED_TIME = "2026-08-30T16:00:00Z"


def digest(label: str) -> str:
    return "sha256:" + hashlib.sha256(label.encode("utf-8")).hexdigest()


def make_publisher(**overrides) -> dict:
    payload = {
        "publisher_id": "official-studio",
        "display_name": "Official Studio",
        "identity_kind": "official",
        "identity_version": "1.0.0",
    }
    payload.update(overrides)
    return payload


def make_signature(**overrides) -> dict:
    payload = {
        "signature_scheme": "ed25519-detached-v1",
        "key_id": "kid-official-root-1",
        "signature_version": "1.0.0",
        "signed_manifest_digest": digest("manifest"),
        "signed_package_digest": digest("package"),
        "created_at": FIXED_TIME,
    }
    payload.update(overrides)
    return payload


def make_evidence(**overrides) -> dict:
    payload = {
        "plugin_id": "story-workflow-pack",
        "plugin_version": "1.0.0",
        "publisher_id": "official-studio",
        "key_id": "kid-official-root-1",
        "scheme": "ed25519-detached-v1",
        "manifest_digest": digest("manifest"),
        "package_digest": digest("package"),
        "outcome": "MATCH",
        "verified_at": FIXED_TIME,
        "policy_version": PLUGIN_SIGNATURE_POLICY_VERSION,
        "evidence_version": "1",
    }
    payload.update(overrides)
    return payload


def make_provenance(**overrides) -> dict:
    payload = {
        "evaluator": "plugin_signature_policy",
        "policy_version": PLUGIN_SIGNATURE_POLICY_VERSION,
        "verification_scheme": "ed25519-detached-v1",
        "manifest_digest": digest("manifest"),
        "package_digest": digest("package"),
        "signature_metadata_present": True,
        "evidence_present": True,
    }
    payload.update(overrides)
    return payload


def make_decision(**overrides) -> dict:
    payload = {
        "plugin_id": "story-workflow-pack",
        "plugin_version": "1.0.0",
        "publisher_id": "official-studio",
        "trust_state": "UNVERIFIED",
        "reason_code": "SIGNATURE_MISSING",
        "verification_provenance": make_provenance(
            verification_scheme="none",
            signature_metadata_present=False,
            evidence_present=False,
            manifest_digest=None,
            package_digest=None,
        ),
        "signature_metadata_present": False,
        "execution_supported": False,
        "sandbox_ready": False,
        "broker_ready": False,
        "worker_ready": False,
        "evaluated_at": FIXED_TIME,
        "policy_version": PLUGIN_SIGNATURE_POLICY_VERSION,
    }
    payload.update(overrides)
    return payload


def test_trust_states_are_closed_and_do_not_collapse_unverified_invalid():
    values = {item.value for item in PluginTrustState}
    assert values == {
        "UNVERIFIED", "VERIFIED", "REVOKED", "INVALID",
        "UNSUPPORTED", "EXPIRED", "UNKNOWN",
    }
    assert PluginTrustState.UNVERIFIED is not PluginTrustState.INVALID
    assert PluginTrustState.UNVERIFIED.value != PluginTrustState.INVALID.value


def test_publisher_identity_round_trip_has_no_secrets():
    identity = PluginPublisherIdentity.parse(make_publisher())
    dumped = dump_without_secrets(identity)
    restored = PluginPublisherIdentity.parse(json.loads(identity.canonical_json()))
    assert restored.public_dump() == dumped
    assert identity.publisher_id == "official-studio"
    assert identity.identity_kind is PublisherIdentityKind.OFFICIAL
    blob = json.dumps(dumped).casefold()
    assert "private" not in blob
    assert "api_key" not in blob
    assert "signature" not in blob


def test_signature_descriptor_presence_is_not_verification():
    descriptor = PluginSignatureDescriptor.parse(make_signature())
    assert descriptor.metadata_present is True
    dumped = descriptor.public_dump()
    assert "signed_manifest_digest" in dumped
    assert "signed_package_digest" in dumped
    assert "trust_state" not in dumped
    assert dumped.get("verified") is None
    assert "signature_bytes" not in dumped
    assert "raw_signature" not in dumped
    assert EXECUTION_SUPPORTED is False


def test_digest_canonicalizes_sha256_and_rejects_malformed_or_weak():
    hex64 = "a" * 64
    assert parse_digest(f"SHA256:{hex64.upper()}") == f"sha256:{hex64}"
    assert parse_digest(f"sha256:{hex64.upper()}") == f"sha256:{hex64}"
    with pytest.raises(PluginTrustContractError) as caught:
        parse_digest(hex64)
    assert caught.value.code == PLUGIN_DIGEST_MALFORMED
    for bad in (
        "",
        "sha256:",
        "sha256:abcd",
        "sha256:" + "g" * 64,
        "md5:" + "a" * 32,
        "sha1:" + "b" * 40,
        "sha512:" + "c" * 128,
        "none:00",
        "sha256:aa:bb",
        "sha256:/etc/passwd",
    ):
        with pytest.raises(PluginTrustContractError) as item:
            parse_digest(bad)
        assert item.value.code == PLUGIN_DIGEST_MALFORMED
    assert ALLOWED_DIGEST_ALGORITHMS == frozenset({"sha256"})


@pytest.mark.parametrize("field", ["signed_manifest_digest", "signed_package_digest"])
def test_malformed_digest_on_signature_descriptor_is_rejected(field):
    payload = make_signature(**{field: "md5:" + "ab" * 16})
    with pytest.raises(PluginTrustContractError) as caught:
        PluginSignatureDescriptor.parse(payload)
    assert caught.value.code == PLUGIN_DIGEST_MALFORMED


def test_raw_signature_and_private_key_fields_are_rejected():
    with pytest.raises(PluginTrustContractError) as caught:
        PluginSignatureDescriptor.parse({**make_signature(), "signature_bytes": "aabb"})
    assert caught.value.code == PLUGIN_TRUST_SECRET_FIELD_FORBIDDEN
    with pytest.raises(PluginTrustContractError) as secret:
        PluginPublisherIdentity.parse({**make_publisher(), "private_key": "-----BEGIN"})
    assert secret.value.code == PLUGIN_TRUST_SECRET_FIELD_FORBIDDEN
    with pytest.raises(PluginTrustContractError) as command:
        PluginTrustEvaluationInput.parse({
            "plugin_id": "story-workflow-pack",
            "plugin_version": "1.0.0",
            "evaluated_at": FIXED_TIME,
            "command": "python evil.py",
        })
    assert command.value.code == PLUGIN_TRUST_COMMAND_FORBIDDEN


def test_unknown_fields_are_rejected():
    with pytest.raises(PluginTrustContractError) as caught:
        PluginPublisherIdentity.parse({**make_publisher(), "extra": True})
    assert caught.value.code == PLUGIN_TRUST_UNKNOWN_FIELD


def test_revocation_contract_covers_publisher_key_and_package():
    publisher = PluginRevocationRecord.parse({
        "subject_type": "publisher",
        "subject_id": "official-studio",
        "effective_at": FIXED_TIME,
        "reason_code": "PUBLISHER_COMPROMISED",
        "source": "host_policy",
        "record_version": "1",
    })
    key = PluginRevocationRecord.parse({
        "subject_type": "key",
        "subject_id": "kid-official-root-1",
        "effective_at": FIXED_TIME,
        "reason_code": "KEY_COMPROMISED",
        "source": "operator_pin",
        "record_version": "1",
    })
    package = PluginRevocationRecord.parse({
        "subject_type": "package",
        "subject_id": "story-workflow-pack@1.0.0",
        "effective_at": FIXED_TIME,
        "reason_code": "PACKAGE_MALICIOUS",
        "source": "host_policy",
        "record_version": "1",
    })
    by_digest = PluginRevocationRecord.parse({
        "subject_type": "package",
        "subject_id": digest("package"),
        "effective_at": FIXED_TIME,
        "reason_code": "PACKAGE_MALICIOUS",
        "source": "host_policy",
        "record_version": "1",
    })
    assert publisher.subject_type is RevocationSubjectType.PUBLISHER
    assert key.subject_type is RevocationSubjectType.KEY
    assert package.subject_type is RevocationSubjectType.PACKAGE
    assert by_digest.subject_id.startswith("sha256:")


def test_revocation_source_cannot_be_url_or_path():
    for source in ("https://evil.example/crl", "http://ocsp", "../crl", "C:\\crl"):
        with pytest.raises(PluginTrustContractError) as caught:
            PluginRevocationRecord.parse({
                "subject_type": "publisher",
                "subject_id": "official-studio",
                "effective_at": FIXED_TIME,
                "reason_code": "PUBLISHER_COMPROMISED",
                "source": source,
                "record_version": "1",
            })
        assert caught.value.code == PLUGIN_TRUST_CONTRACT_INVALID


def test_decision_verified_requires_digests_and_cannot_enable_execution():
    verified = PluginTrustDecision.parse({
        **make_decision(),
        "trust_state": "VERIFIED",
        "reason_code": "VERIFICATION_EVIDENCE_VALID",
        "verified_manifest_digest": digest("manifest"),
        "verified_package_digest": digest("package"),
        "signature_metadata_present": True,
        "verification_provenance": make_provenance(),
    })
    assert verified.trust_state is PluginTrustState.VERIFIED
    assert verified.execution_supported is False
    assert verified.sandbox_ready is False
    assert verified.broker_ready is False
    assert verified.worker_ready is False
    dumped = dump_without_secrets(verified)
    assert "signature_bytes" not in dumped
    assert dumped["execution_supported"] is False

    with pytest.raises(PluginTrustContractError):
        PluginTrustDecision.parse({
            **make_decision(),
            "trust_state": "VERIFIED",
            "reason_code": "VERIFICATION_EVIDENCE_VALID",
            "signature_metadata_present": True,
            "verification_provenance": make_provenance(),
        })
    with pytest.raises(PluginTrustContractError):
        PluginTrustDecision.parse({
            **make_decision(),
            "verified_manifest_digest": digest("manifest"),
        })


def test_unverified_and_invalid_decisions_are_distinct_serializations():
    unverified = PluginTrustDecision.parse(make_decision())
    invalid = PluginTrustDecision.parse({
        **make_decision(),
        "trust_state": "INVALID",
        "reason_code": "SIGNATURE_MISMATCH",
        "signature_metadata_present": True,
        "verification_provenance": make_provenance(evidence_present=False),
    })
    assert unverified.trust_state is PluginTrustState.UNVERIFIED
    assert invalid.trust_state is PluginTrustState.INVALID
    assert unverified.public_dump() != invalid.public_dump()


def test_evaluation_input_round_trip():
    payload = {
        "plugin_id": "story-workflow-pack",
        "plugin_version": "1.0.0",
        "evaluated_at": FIXED_TIME,
        "publisher": make_publisher(),
        "signature": make_signature(),
        "evidence": make_evidence(),
        "revocations": [],
        "known_publisher_ids": ["official-studio"],
    }
    parsed = PluginTrustEvaluationInput.parse(payload)
    restored = PluginTrustEvaluationInput.parse(json.loads(parsed.canonical_json()))
    assert restored.plugin_id == "story-workflow-pack"
    assert restored.signature is not None
    assert restored.evidence.outcome is VerificationOutcome.MATCH
    assert restored.known_publisher_ids == ("official-studio",)


def test_provenance_answers_what_digest_policy_and_scheme():
    provenance = VerificationProvenance.parse(make_provenance())
    dumped = provenance.public_dump()
    assert dumped["evaluator"] == "plugin_signature_policy"
    assert dumped["policy_version"] == PLUGIN_SIGNATURE_POLICY_VERSION
    assert dumped["verification_scheme"] == "ed25519-detached-v1"
    assert dumped["manifest_digest"].startswith("sha256:")
    assert dumped["package_digest"].startswith("sha256:")
    assert "private_key" not in dumped
    assert "log" not in dumped


def test_inspect_forbidden_payload_finds_nested_secrets():
    assert inspect_forbidden_payload({"nested": {"api_key": "x"}}) == PLUGIN_TRUST_SECRET_FIELD_FORBIDDEN
    assert inspect_forbidden_payload({"ok": 1}) is None


def test_contracts_module_does_not_import_io_or_crypto_backends():
    tree = ast.parse(CONTRACTS.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
            imported.add(node.module)
    forbidden = {
        "os", "socket", "subprocess", "pathlib", "httpx", "urllib", "requests",
        "sqlite3", "sqlalchemy", "psycopg", "keyring", "ssl", "ctypes",
        "hashlib", "hmac", "nacl", "cryptography",
    }
    assert not (imported & forbidden)
    assert "app.plugin_contracts" in imported
