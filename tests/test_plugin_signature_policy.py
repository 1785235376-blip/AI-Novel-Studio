from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from app.plugin_signature_policy import (
    EXECUTION_SUPPORTED,
    REASON_DIGEST_MISMATCH,
    REASON_EVIDENCE_MISSING,
    REASON_EVIDENCE_PLUGIN_ID_MISMATCH,
    REASON_EVIDENCE_PLUGIN_VERSION_MISMATCH,
    REASON_EVIDENCE_EXPIRED,
    REASON_EVIDENCE_VERSION_UNSUPPORTED,
    REASON_POLICY_VERSION_UNSUPPORTED,
    REASON_KEY_REVOKED,
    REASON_PACKAGE_REVOKED,
    REASON_PUBLISHER_REVOKED,
    REASON_PUBLISHER_UNKNOWN,
    REASON_SIGNATURE_MISMATCH,
    REASON_SIGNATURE_MISSING,
    REASON_SIGNATURE_SCHEME_UNSUPPORTED,
    REASON_VERIFICATION_EVIDENCE_VALID,
    SUPPORTED_SIGNATURE_SCHEMES,
    evaluate_plugin_trust,
    trust_does_not_authorize_execution,
)
from app.plugin_trust_contracts import (
    PLUGIN_DIGEST_MALFORMED,
    PLUGIN_SIGNATURE_POLICY_VERSION,
    PLUGIN_TRUST_CONTRACT_INVALID,
    SUPPORTED_EVIDENCE_VERSIONS,
    SUPPORTED_POLICY_VERSIONS,
    PluginTrustContractError,
    PluginTrustDecision,
    PluginTrustEvaluationInput,
    PluginTrustState,
    dump_without_secrets,
)


REPO = Path(__file__).resolve().parents[1]
POLICY = REPO / "app" / "plugin_signature_policy.py"
FIXED_TIME = "2026-08-30T16:00:00Z"
EXPIRED_TIME = "2026-08-01T00:00:00Z"
FUTURE_TIME = "2026-12-01T00:00:00Z"


def digest(label: str) -> str:
    return "sha256:" + hashlib.sha256(label.encode("utf-8")).hexdigest()


def publisher(**overrides) -> dict:
    payload = {
        "publisher_id": "official-studio",
        "display_name": "Official Studio",
        "identity_kind": "official",
        "identity_version": "1.0.0",
    }
    payload.update(overrides)
    return payload


def signature(**overrides) -> dict:
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


def evidence(**overrides) -> dict:
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


def revocation(subject_type: str, subject_id: str, reason_code: str) -> dict:
    return {
        "subject_type": subject_type,
        "subject_id": subject_id,
        "effective_at": "2026-01-01T00:00:00Z",
        "reason_code": reason_code,
        "source": "host_policy",
        "record_version": "1",
    }


def base_input(**overrides) -> dict:
    payload = {
        "plugin_id": "story-workflow-pack",
        "plugin_version": "1.0.0",
        "evaluated_at": FIXED_TIME,
        "publisher": publisher(),
        "signature": signature(),
        "evidence": evidence(),
        "revocations": [],
        "known_publisher_ids": ["official-studio"],
    }
    payload.update(overrides)
    return payload


def decide(**overrides) -> PluginTrustDecision:
    return evaluate_plugin_trust(base_input(**overrides))


def test_missing_signature_is_unverified_not_invalid():
    decision = decide(signature=None, evidence=None)
    assert decision.trust_state is PluginTrustState.UNVERIFIED
    assert decision.reason_code == REASON_SIGNATURE_MISSING
    assert decision.signature_metadata_present is False
    assert decision.verified_manifest_digest is None
    assert decision.execution_supported is False


def test_signature_metadata_without_evidence_stays_unverified():
    decision = decide(evidence=None)
    assert decision.trust_state is PluginTrustState.UNVERIFIED
    assert decision.reason_code == REASON_EVIDENCE_MISSING
    assert decision.signature_metadata_present is True
    assert decision.trust_state is not PluginTrustState.VERIFIED
    assert decision.trust_state is not PluginTrustState.INVALID


def test_unsupported_signature_scheme():
    decision = decide(
        signature=signature(signature_scheme="rsa-pkcs1v15-v1"),
        evidence=evidence(scheme="rsa-pkcs1v15-v1"),
    )
    assert decision.trust_state is PluginTrustState.UNSUPPORTED
    assert decision.reason_code == REASON_SIGNATURE_SCHEME_UNSUPPORTED
    assert "ed25519-detached-v1" in SUPPORTED_SIGNATURE_SCHEMES


def test_malformed_digest_is_rejected_before_policy():
    with pytest.raises(PluginTrustContractError) as caught:
        evaluate_plugin_trust(base_input(signature=signature(signed_manifest_digest="sha1:" + "ab" * 20)))
    assert caught.value.code == PLUGIN_DIGEST_MALFORMED


def test_wrong_digest_is_invalid():
    decision = decide(evidence=evidence(manifest_digest=digest("other-manifest")))
    assert decision.trust_state is PluginTrustState.INVALID
    assert decision.reason_code == REASON_DIGEST_MISMATCH
    assert decision.verified_manifest_digest is None


def test_unknown_publisher():
    decision = decide(known_publisher_ids=[])
    assert decision.trust_state is PluginTrustState.UNKNOWN
    assert decision.reason_code == REASON_PUBLISHER_UNKNOWN
    missing = decide(publisher=None, known_publisher_ids=["official-studio"])
    assert missing.trust_state is PluginTrustState.UNKNOWN
    assert missing.reason_code == REASON_PUBLISHER_UNKNOWN


def test_revoked_publisher():
    decision = decide(revocations=[revocation("publisher", "official-studio", "PUBLISHER_COMPROMISED")])
    assert decision.trust_state is PluginTrustState.REVOKED
    assert decision.reason_code == REASON_PUBLISHER_REVOKED


def test_revoked_key():
    decision = decide(revocations=[revocation("key", "kid-official-root-1", "KEY_COMPROMISED")])
    assert decision.trust_state is PluginTrustState.REVOKED
    assert decision.reason_code == REASON_KEY_REVOKED


def test_revoked_package_by_id_version_and_digest():
    by_coord = decide(revocations=[revocation("package", "story-workflow-pack@1.0.0", "PACKAGE_MALICIOUS")])
    assert by_coord.trust_state is PluginTrustState.REVOKED
    assert by_coord.reason_code == REASON_PACKAGE_REVOKED
    by_id = decide(revocations=[revocation("package", "story-workflow-pack", "PACKAGE_MALICIOUS")])
    assert by_id.reason_code == REASON_PACKAGE_REVOKED
    by_digest = decide(revocations=[revocation("package", digest("package"), "PACKAGE_MALICIOUS")])
    assert by_digest.reason_code == REASON_PACKAGE_REVOKED


def test_revocation_wins_over_valid_evidence():
    decision = decide(revocations=[revocation("package", "story-workflow-pack@1.0.0", "PACKAGE_MALICIOUS")])
    assert decision.trust_state is PluginTrustState.REVOKED
    assert decision.reason_code != REASON_VERIFICATION_EVIDENCE_VALID


def test_future_dated_revocation_is_not_yet_active():
    later = {
        **revocation("package", "story-workflow-pack@1.0.0", "PACKAGE_MALICIOUS"),
        "effective_at": FUTURE_TIME,
    }
    decision = decide(revocations=[later])
    assert decision.trust_state is PluginTrustState.VERIFIED


def test_valid_verification_evidence_is_verified_but_not_executable():
    decision = decide()
    assert decision.trust_state is PluginTrustState.VERIFIED
    assert decision.reason_code == REASON_VERIFICATION_EVIDENCE_VALID
    assert decision.verified_manifest_digest == digest("manifest")
    assert decision.verified_package_digest == digest("package")
    assert decision.execution_supported is False
    assert decision.sandbox_ready is False
    assert decision.broker_ready is False
    assert decision.worker_ready is False
    assert trust_does_not_authorize_execution(decision) is False
    assert EXECUTION_SUPPORTED is False
    dumped = dump_without_secrets(decision)
    assert dumped["execution_supported"] is False
    assert "signature_bytes" not in json.dumps(dumped)


def test_evidence_bound_to_wrong_plugin_id():
    decision = decide(evidence=evidence(plugin_id="other-plugin-pack"))
    assert decision.trust_state is PluginTrustState.INVALID
    assert decision.reason_code == REASON_EVIDENCE_PLUGIN_ID_MISMATCH


def test_evidence_bound_to_wrong_plugin_version():
    decision = decide(evidence=evidence(plugin_version="9.9.9"))
    assert decision.trust_state is PluginTrustState.INVALID
    assert decision.reason_code == REASON_EVIDENCE_PLUGIN_VERSION_MISMATCH


def test_signature_mismatch_outcome_is_invalid():
    decision = decide(evidence=evidence(outcome="MISMATCH"))
    assert decision.trust_state is PluginTrustState.INVALID
    assert decision.reason_code == REASON_SIGNATURE_MISMATCH


def test_expired_evidence_is_expired_not_verified():
    decision = decide(evidence=evidence(
        verified_at="2026-07-01T00:00:00Z",
        expires_at=EXPIRED_TIME,
    ))
    assert decision.trust_state is PluginTrustState.EXPIRED
    assert decision.reason_code == REASON_EVIDENCE_EXPIRED
    assert decision.verified_manifest_digest is None


def test_unknown_evidence_version_never_verified():
    decision = decide(evidence=evidence(evidence_version="999"))
    assert decision.trust_state is PluginTrustState.UNSUPPORTED
    assert decision.reason_code == REASON_EVIDENCE_VERSION_UNSUPPORTED
    assert decision.trust_state is not PluginTrustState.VERIFIED
    assert decision.verified_manifest_digest is None
    assert decision.execution_supported is False
    assert "999" not in SUPPORTED_EVIDENCE_VERSIONS


def test_unknown_policy_version_never_verified():
    decision = decide(evidence=evidence(policy_version="trust.v999"))
    assert decision.trust_state is PluginTrustState.UNSUPPORTED
    assert decision.reason_code == REASON_POLICY_VERSION_UNSUPPORTED
    assert decision.trust_state is not PluginTrustState.VERIFIED
    assert decision.verified_manifest_digest is None
    assert decision.execution_supported is False
    assert "trust.v999" not in SUPPORTED_POLICY_VERSIONS


def test_supported_evidence_and_policy_version_can_verify():
    decision = decide(evidence=evidence(
        evidence_version="1",
        policy_version=PLUGIN_SIGNATURE_POLICY_VERSION,
    ))
    assert "1" in SUPPORTED_EVIDENCE_VERSIONS
    assert PLUGIN_SIGNATURE_POLICY_VERSION in SUPPORTED_POLICY_VERSIONS
    assert decision.trust_state is PluginTrustState.VERIFIED
    assert decision.reason_code == REASON_VERIFICATION_EVIDENCE_VALID
    assert decision.execution_supported is False


def test_verified_at_after_evaluated_at_never_verified():
    with pytest.raises(PluginTrustContractError) as caught:
        decide(evidence=evidence(verified_at="2026-08-30T17:00:00Z"))
    assert caught.value.code == PLUGIN_TRUST_CONTRACT_INVALID


def test_invalid_calendar_and_time_never_verified():
    with pytest.raises(PluginTrustContractError) as calendar:
        decide(evaluated_at="2026-99-99T99:99:99Z")
    assert calendar.value.code == PLUGIN_TRUST_CONTRACT_INVALID
    with pytest.raises(PluginTrustContractError) as clock:
        decide(evidence=evidence(verified_at="2026-08-30T25:61:61Z"))
    assert clock.value.code == PLUGIN_TRUST_CONTRACT_INVALID


def test_unsigned_revoked_package_is_revoked_not_unverified():
    decision = decide(
        signature=None,
        evidence=None,
        revocations=[revocation("package", "story-workflow-pack", "PACKAGE_MALICIOUS")],
    )
    assert decision.trust_state is PluginTrustState.REVOKED
    assert decision.reason_code == REASON_PACKAGE_REVOKED
    assert decision.trust_state is not PluginTrustState.UNVERIFIED


def test_decision_round_trip_and_typed_input():
    parsed_input = PluginTrustEvaluationInput.parse(base_input())
    decision = evaluate_plugin_trust(parsed_input)
    restored = PluginTrustDecision.parse(json.loads(decision.canonical_json()))
    assert restored.public_dump() == decision.public_dump()
    assert restored.verification_provenance.policy_version == PLUGIN_SIGNATURE_POLICY_VERSION
    assert restored.verification_provenance.verification_scheme == "ed25519-detached-v1"
    assert restored.verification_provenance.manifest_digest == digest("manifest")


def test_policy_and_contracts_have_no_subprocess_network_vault_or_provider_side_effects():
    def boom(*_args, **_kwargs):
        raise AssertionError("forbidden side effect")

    with patch("subprocess.Popen", boom), patch("subprocess.run", boom), \
            patch("os.system", boom), patch("socket.create_connection", boom), \
            patch("httpx.Client.request", boom), patch("httpx.Client.get", boom):
        with patch("app.credential_vault.credential_vault.resolve", boom):
            missing = evaluate_plugin_trust(base_input(signature=None, evidence=None))
            verified = evaluate_plugin_trust(base_input())
            revoked = evaluate_plugin_trust(base_input(
                revocations=[revocation("key", "kid-official-root-1", "KEY_COMPROMISED")],
            ))
            assert missing.trust_state is PluginTrustState.UNVERIFIED
            assert verified.trust_state is PluginTrustState.VERIFIED
            assert revoked.trust_state is PluginTrustState.REVOKED
            trust_does_not_authorize_execution(verified)


def test_policy_module_is_structurally_pure():
    source = POLICY.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
            imported.add(node.module)
    forbidden = {
        "os", "sys", "socket", "subprocess", "pathlib", "httpx", "urllib",
        "requests", "sqlite3", "sqlalchemy", "psycopg", "keyring", "ssl",
        "ctypes", "hashlib", "hmac", "nacl", "cryptography", "builtins",
    }
    assert not (imported & forbidden)
    assert "app.plugin_trust_contracts" in imported
    assert "app.credential_vault" not in imported
    assert "app.plugin_worker_process" not in imported
    assert "app.plugin_discovery" not in imported
    for token in ("hashlib", "hmac", "from cryptography", "nacl", "Popen", "urlopen"):
        assert token not in source
    assert "execution_supported" in source


def test_verified_does_not_imply_executable_capability():
    decision = decide()
    assert decision.trust_state is PluginTrustState.VERIFIED
    capabilities = {
        "execution_supported": decision.execution_supported,
        "sandbox_ready": decision.sandbox_ready,
        "broker_ready": decision.broker_ready,
        "worker_ready": decision.worker_ready,
    }
    assert capabilities == {
        "execution_supported": False,
        "sandbox_ready": False,
        "broker_ready": False,
        "worker_ready": False,
    }
    assert trust_does_not_authorize_execution(decision) is False
