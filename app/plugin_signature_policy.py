"""Pure, side-effect-free plugin trust policy.

This evaluator maps already-parsed Host-owned facts onto a fail-closed
PluginTrustDecision. It does not access a filesystem, network, database,
Credential Vault, Provider, Windows API, or subprocess. It does not
implement cryptographic signature verification.

TRUST != AUTHORIZATION
SIGNATURE != EXECUTION
VERIFIED != SANDBOX READY

`execution_supported` remains false even when trust_state is VERIFIED.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from app.plugin_trust_contracts import (
    EXECUTION_SUPPORTED,
    PLUGIN_SIGNATURE_POLICY_VERSION,
    PluginSignatureDescriptor,
    PluginTrustDecision,
    PluginTrustEvaluationInput,
    PluginTrustState,
    PluginVerificationEvidence,
    RevocationSubjectType,
    VerificationOutcome,
    VerificationProvenance,
)


# Scheme identifier only. This module does not implement Ed25519 (or any) crypto.
SUPPORTED_SIGNATURE_SCHEMES = frozenset({"ed25519-detached-v1"})

REASON_SIGNATURE_MISSING = "SIGNATURE_MISSING"
REASON_SIGNATURE_SCHEME_UNSUPPORTED = "SIGNATURE_SCHEME_UNSUPPORTED"
REASON_DIGEST_MISMATCH = "DIGEST_MISMATCH"
REASON_SIGNATURE_MISMATCH = "SIGNATURE_MISMATCH"
REASON_PUBLISHER_UNKNOWN = "PUBLISHER_UNKNOWN"
REASON_PUBLISHER_REVOKED = "PUBLISHER_REVOKED"
REASON_KEY_REVOKED = "KEY_REVOKED"
REASON_PACKAGE_REVOKED = "PACKAGE_REVOKED"
REASON_EVIDENCE_PLUGIN_ID_MISMATCH = "EVIDENCE_PLUGIN_ID_MISMATCH"
REASON_EVIDENCE_PLUGIN_VERSION_MISMATCH = "EVIDENCE_PLUGIN_VERSION_MISMATCH"
REASON_EVIDENCE_PUBLISHER_MISMATCH = "EVIDENCE_PUBLISHER_MISMATCH"
REASON_EVIDENCE_KEY_MISMATCH = "EVIDENCE_KEY_MISMATCH"
REASON_EVIDENCE_SCHEME_MISMATCH = "EVIDENCE_SCHEME_MISMATCH"
REASON_EVIDENCE_MISSING = "EVIDENCE_MISSING"
REASON_EVIDENCE_EXPIRED = "EVIDENCE_EXPIRED"
REASON_VERIFICATION_EVIDENCE_VALID = "VERIFICATION_EVIDENCE_VALID"


def _parse_iso(value: str) -> datetime:
    text = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _not_before(left: str, right: str) -> bool:
    return _parse_iso(left) <= _parse_iso(right)


def _package_subject_ids(
    plugin_id: str,
    plugin_version: str,
    signature: PluginSignatureDescriptor | None,
    evidence: PluginVerificationEvidence | None,
) -> frozenset[str]:
    subjects = {plugin_id, f"{plugin_id}@{plugin_version}"}
    if signature is not None:
        subjects.add(signature.signed_package_digest)
    if evidence is not None:
        subjects.add(evidence.package_digest)
    return frozenset(subjects)


def _active_revocation_reason(inp: PluginTrustEvaluationInput) -> str | None:
    publisher_id = inp.publisher.publisher_id if inp.publisher is not None else None
    key_id = inp.signature.key_id if inp.signature is not None else (
        inp.evidence.key_id if inp.evidence is not None else None
    )
    package_ids = _package_subject_ids(inp.plugin_id, inp.plugin_version, inp.signature, inp.evidence)

    package_hit = False
    key_hit = False
    publisher_hit = False
    for record in inp.revocations:
        if not _not_before(record.effective_at, inp.evaluated_at):
            continue
        if record.subject_type is RevocationSubjectType.PACKAGE and record.subject_id in package_ids:
            package_hit = True
        elif record.subject_type is RevocationSubjectType.KEY and key_id is not None and record.subject_id == key_id:
            key_hit = True
        elif (
            record.subject_type is RevocationSubjectType.PUBLISHER
            and publisher_id is not None
            and record.subject_id == publisher_id
        ):
            publisher_hit = True
    if package_hit:
        return REASON_PACKAGE_REVOKED
    if key_hit:
        return REASON_KEY_REVOKED
    if publisher_hit:
        return REASON_PUBLISHER_REVOKED
    return None


def _publisher_is_known(inp: PluginTrustEvaluationInput) -> bool:
    if inp.publisher is None:
        return False
    return inp.publisher.publisher_id in inp.known_publisher_ids


def _provenance(
    *,
    scheme: str,
    signature: PluginSignatureDescriptor | None,
    evidence: PluginVerificationEvidence | None,
) -> VerificationProvenance:
    manifest = None
    package = None
    if evidence is not None:
        manifest = evidence.manifest_digest
        package = evidence.package_digest
    elif signature is not None:
        manifest = signature.signed_manifest_digest
        package = signature.signed_package_digest
    return VerificationProvenance(
        evaluator="plugin_signature_policy",
        policy_version=PLUGIN_SIGNATURE_POLICY_VERSION,
        verification_scheme=scheme,
        manifest_digest=manifest,
        package_digest=package,
        signature_metadata_present=signature is not None,
        evidence_present=evidence is not None,
    )


def _decision(
    inp: PluginTrustEvaluationInput,
    *,
    trust_state: PluginTrustState,
    reason_code: str,
    scheme: str,
    verified_manifest_digest: str | None = None,
    verified_package_digest: str | None = None,
) -> PluginTrustDecision:
    return PluginTrustDecision(
        plugin_id=inp.plugin_id,
        plugin_version=inp.plugin_version,
        publisher_id=inp.publisher.publisher_id if inp.publisher is not None else None,
        trust_state=trust_state,
        reason_code=reason_code,
        verification_provenance=_provenance(
            scheme=scheme,
            signature=inp.signature,
            evidence=inp.evidence,
        ),
        verified_manifest_digest=verified_manifest_digest,
        verified_package_digest=verified_package_digest,
        signature_metadata_present=inp.signature is not None,
        execution_supported=EXECUTION_SUPPORTED,
        sandbox_ready=False,
        broker_ready=False,
        worker_ready=False,
        evaluated_at=inp.evaluated_at,
        policy_version=PLUGIN_SIGNATURE_POLICY_VERSION,
    )


def _evidence_binding_reason(
    inp: PluginTrustEvaluationInput,
    evidence: PluginVerificationEvidence,
    signature: PluginSignatureDescriptor,
) -> str | None:
    if evidence.plugin_id != inp.plugin_id:
        return REASON_EVIDENCE_PLUGIN_ID_MISMATCH
    if evidence.plugin_version != inp.plugin_version:
        return REASON_EVIDENCE_PLUGIN_VERSION_MISMATCH
    if inp.publisher is None or evidence.publisher_id != inp.publisher.publisher_id:
        return REASON_EVIDENCE_PUBLISHER_MISMATCH
    if evidence.key_id != signature.key_id:
        return REASON_EVIDENCE_KEY_MISMATCH
    if evidence.scheme != signature.signature_scheme:
        return REASON_EVIDENCE_SCHEME_MISMATCH
    if (
        evidence.manifest_digest != signature.signed_manifest_digest
        or evidence.package_digest != signature.signed_package_digest
    ):
        return REASON_DIGEST_MISMATCH
    return None


def evaluate_plugin_trust(
    payload: PluginTrustEvaluationInput | dict[str, Any],
) -> PluginTrustDecision:
    """Fail-closed trust decision. Never authorizes plugin execution."""
    inp = payload if isinstance(payload, PluginTrustEvaluationInput) else PluginTrustEvaluationInput.parse(payload)
    scheme = inp.signature.signature_scheme if inp.signature is not None else "none"

    revoked = _active_revocation_reason(inp)
    if revoked is not None:
        return _decision(inp, trust_state=PluginTrustState.REVOKED, reason_code=revoked, scheme=scheme)

    if inp.signature is None:
        return _decision(
            inp,
            trust_state=PluginTrustState.UNVERIFIED,
            reason_code=REASON_SIGNATURE_MISSING,
            scheme="none",
        )

    if inp.signature.signature_scheme not in SUPPORTED_SIGNATURE_SCHEMES:
        return _decision(
            inp,
            trust_state=PluginTrustState.UNSUPPORTED,
            reason_code=REASON_SIGNATURE_SCHEME_UNSUPPORTED,
            scheme=inp.signature.signature_scheme,
        )

    if not _publisher_is_known(inp):
        return _decision(
            inp,
            trust_state=PluginTrustState.UNKNOWN,
            reason_code=REASON_PUBLISHER_UNKNOWN,
            scheme=inp.signature.signature_scheme,
        )

    if inp.evidence is None:
        return _decision(
            inp,
            trust_state=PluginTrustState.UNVERIFIED,
            reason_code=REASON_EVIDENCE_MISSING,
            scheme=inp.signature.signature_scheme,
        )

    binding = _evidence_binding_reason(inp, inp.evidence, inp.signature)
    if binding is not None:
        return _decision(inp, trust_state=PluginTrustState.INVALID, reason_code=binding, scheme=inp.signature.signature_scheme)

    if inp.evidence.outcome is VerificationOutcome.MISMATCH:
        return _decision(
            inp,
            trust_state=PluginTrustState.INVALID,
            reason_code=REASON_SIGNATURE_MISMATCH,
            scheme=inp.signature.signature_scheme,
        )

    if inp.evidence.expires_at is not None and not _not_before(inp.evaluated_at, inp.evidence.expires_at):
        return _decision(
            inp,
            trust_state=PluginTrustState.EXPIRED,
            reason_code=REASON_EVIDENCE_EXPIRED,
            scheme=inp.signature.signature_scheme,
        )

    if inp.evidence.scheme not in SUPPORTED_SIGNATURE_SCHEMES:
        return _decision(
            inp,
            trust_state=PluginTrustState.UNSUPPORTED,
            reason_code=REASON_SIGNATURE_SCHEME_UNSUPPORTED,
            scheme=inp.evidence.scheme,
        )

    return _decision(
        inp,
        trust_state=PluginTrustState.VERIFIED,
        reason_code=REASON_VERIFICATION_EVIDENCE_VALID,
        scheme=inp.signature.signature_scheme,
        verified_manifest_digest=inp.evidence.manifest_digest,
        verified_package_digest=inp.evidence.package_digest,
    )


def trust_does_not_authorize_execution(decision: PluginTrustDecision) -> Literal[False]:
    """VERIFIED trust is not an execution grant. Always false in this phase."""
    if decision.execution_supported is not False:
        raise RuntimeError("execution_supported must remain false")
    if decision.sandbox_ready or decision.broker_ready or decision.worker_ready:
        raise RuntimeError("trust must not claim runtime readiness")
    return False
