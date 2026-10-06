"""Public Local Interop 1.0 contract and semantic validator tests.

These use synthetic data only. They do not claim real desktop integration.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path

import jsonschema
import pytest
from pydantic import ValidationError

import local_interop_protocol as p
from local_interop_protocol.generate_contracts import SCHEMAS, generate

NOW = datetime(2026, 10, 6, 5, 0, tzinfo=timezone.utc)
ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "contracts/local-interop/v1"


def evidence(**updates):
    values = dict(
        source_id="task-state-1",
        source_version="37",
        locator="task:task-1",
        content_hash=p.canonical_hash({"task_status": "FAILED"}),
        timestamp=NOW,
        authority="AUTHORITATIVE",
        privacy="LOCAL_ONLY",
    )
    values.update(updates)
    return p.ContextEvidence(**values)


def capsule(**updates):
    values = dict(
        capsule_id="capsule-1",
        source_version="37",
        product_id=p.STUDIO_PRODUCT_ID,
        product_version="0.7.0",
        instance_id="studio-instance-1",
        project_id="project-1",
        project_version="project-version-37",
        chapter_id="chapter-1",
        chapter_version=37,
        module="editor",
        surface="task-center",
        task_id="task-1",
        task_type="generation",
        task_status="FAILED",
        runtime_id="runtime-1",
        runtime_status="READY",
        model_id="model-1",
        created_at=NOW,
        expires_at=NOW + timedelta(minutes=5),
        evidence=(evidence(),),
    )
    values.update(updates)
    return p.create_capsule(**values)


def diagnostic(**updates):
    values = dict(
        diagnostic_id="diagnostic-1",
        source_version="37",
        software_id=p.STUDIO_PRODUCT_ID,
        software_version="0.7.0",
        feature="task-center",
        error_code="SYNTHETIC_ERROR",
        task_state="FAILED",
        runtime="runtime-1",
        model="model-1",
        created_at=NOW,
        expires_at=NOW + timedelta(minutes=5),
        evidence=(evidence(),),
    )
    values.update(updates)
    return p.create_diagnostic(**values)


def product():
    return p.ProductDescriptor(
        product_id=p.TUTOR_PRODUCT_ID,
        display_name="Synthetic Tutor (MOCK_ONLY)",
        product_version="0.1.0",
        instance_id="tutor-instance-1",
        product_role="AI_TUTOR",
        capabilities=tuple(p.CAPABILITIES),
    )


def samples():
    state = capsule()
    condition = p.VerificationCondition(
        field="runtime_status", expected_value="READY", source_id="runtime-state-1"
    )
    guidance = p.TutorGuidance(
        request_id="request-1",
        session_id="session-1",
        guidance_id="guidance-1",
        summary="Review the failure",
        diagnosis="A synthetic task reported FAILED.",
        steps=(p.GuidanceStep(step_id="step-1", instruction="Review the task in Studio."),),
        verification_condition=condition,
        created_at=NOW,
    )
    result = p.VerifierResult(
        request_id="request-1",
        session_id="session-1",
        result_id="result-1",
        status="VERIFIED",
        reason="Trusted synthetic state was observed.",
        evidence=(evidence(),),
        created_at=NOW,
    )
    session = p.SessionDescriptor(
        session_id="session-1",
        product_id=p.TUTOR_PRODUCT_ID,
        instance_id="tutor-instance-1",
        peer_product_id=p.STUDIO_PRODUCT_ID,
        peer_instance_id="studio-instance-1",
        user_identity="opaque-user-1",
        capabilities=tuple(p.CAPABILITIES),
        nonce="n" * 32,
        created_at=NOW,
        expires_at=NOW + timedelta(hours=1),
        transport="LOOPBACK_HTTP",
    )
    hello = p.HandshakeHello(product=product(), transport="LOOPBACK_HTTP", session_nonce="n" * 32)
    values = {
        "handshake": hello,
        "product": product(),
        "capability": p.CapabilityDescriptor(capability="project.context.read"),
        "context-capsule": state,
        "context-evidence": evidence(),
        "event": p.InteropEvent(
            event_id="event-1",
            session_id="session-1",
            sequence=1,
            event_type="TASK_FAILED",
            created_at=NOW,
            context=state,
        ),
        "diagnostic": diagnostic(),
        "handoff": p.HandoffRequest(
            request_id="request-1",
            session_id="session-1",
            target=p.HandoffTarget(
                action="OPEN_PROJECT",
                target_product_id=p.STUDIO_PRODUCT_ID,
                project_id="project-1",
                source_version="37",
            ),
            user_gesture_id="gesture-1",
        ),
        "model-registry": p.ModelRegistry(
            models=(
                p.SharedModelDescriptor(
                    runtime_id="runtime-1",
                    model_id="model-1",
                    family="synthetic",
                    modality=("TEXT",),
                    runtime_type="synthetic",
                    local=True,
                ),
            ),
            created_at=NOW,
        ),
        "tutor-request": p.TutorRequest(
            request_id="request-1",
            session_id="session-1",
            context=state,
            question="Why did the synthetic task fail?",
        ),
        "tutor-response": guidance,
        "verifier-request": p.VerifierRequest(
            request_id="request-1",
            session_id="session-1",
            guidance_id="guidance-1",
            condition=condition,
            context=state,
        ),
        "verifier-result": result,
        "case-candidate": p.CaseCandidate(
            candidate_id="case-1",
            problem="Synthetic task failure",
            environment=p.CaseEnvironment(
                product_id=p.STUDIO_PRODUCT_ID, product_version="0.7.0", module="task-center"
            ),
            diagnosis="Synthetic diagnosis",
            guidance=guidance,
            result="Verified synthetic observation",
            verification=result,
            software_id=p.STUDIO_PRODUCT_ID,
            software_version="0.7.0",
            evidence=(evidence(),),
            created_at=NOW,
        ),
        "error": p.InteropError(code="CAPABILITY_NOT_SUPPORTED", message="Capability unavailable"),
        "hello-result": p.HelloResult(
            hello_id="hello-1", product=product(), session_nonce="n" * 32
        ),
        "capability-negotiation": p.CapabilityNegotiation(
            hello_id="hello-1",
            requested_capabilities=("tutor.guidance.request",),
            granted_capabilities=("tutor.guidance.request",),
        ),
        "session": session,
        "session-open-request": p.SessionOpenRequest(
            hello_id="hello-1", session_nonce="n" * 32, user_identity="opaque-user-1"
        ),
        "session-open-result": p.SessionOpenResult(session=session, session_token="t" * 43),
        "task-requirement": p.TaskRequirement(
            task_type="generation", required_modality=("TEXT",), estimated_context=4096
        ),
        "handoff-result": p.HandoffResult(
            request_id="request-1", session_id="session-1", status="OPENED"
        ),
        "discovery": p.DiscoveryRecord(
            product_id=p.STUDIO_PRODUCT_ID,
            instance_id="studio-instance-1",
            product_version="0.7.0",
            capabilities=("project.context.read",),
        ),
        "heartbeat": p.Heartbeat(session_id="session-1", sequence=1, created_at=NOW),
        "cancel-request": p.CancelRequest(request_id="request-1", session_id="session-1"),
        "cancel-result": p.CancelResult(request_id="request-1", session_id="session-1"),
        "transport-request": p.TransportRequest(operation="HELLO", payload=hello),
        "transport-response": p.TransportResponse(operation="TUTOR", payload=guidance),
    }
    assert set(values) == set(SCHEMAS)
    return values


@pytest.mark.parametrize("slug", sorted(SCHEMAS))
def test_generated_schema_and_dto_accept_same_valid_sample(slug):
    model = samples()[slug]
    data = model.model_dump(mode="json")
    schema = json.loads((CONTRACTS / f"{slug}.schema.json").read_text())
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker()).validate(
        data
    )
    assert p.parse_wire(SCHEMAS[slug], data) == model


@pytest.mark.parametrize("slug", sorted(SCHEMAS))
def test_unknown_fields_rejected_by_schema_and_dto(slug):
    data = samples()[slug].model_dump(mode="json")
    data["unexpected_field"] = "not accepted"
    schema = json.loads((CONTRACTS / f"{slug}.schema.json").read_text())
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(schema).validate(data)
    with pytest.raises(p.ProtocolViolation, match="invalid Local Interop"):
        p.parse_wire(SCHEMAS[slug], data)


@pytest.mark.parametrize("slug", sorted(SCHEMAS))
def test_all_object_shapes_forbid_unknown_properties(slug):
    schema = json.loads((CONTRACTS / f"{slug}.schema.json").read_text())
    for node in (schema, *schema.get("$defs", {}).values()):
        if node.get("type") == "object":
            assert node["additionalProperties"] is False


@pytest.mark.parametrize("bad", ["2.0", "0.9", 1.0, None])
def test_unsupported_protocol_explicit_typed_error(bad):
    data = samples()["handshake"].model_dump(mode="json")
    data["protocol_version"] = bad
    with pytest.raises(p.ProtocolViolation) as caught:
        p.parse_wire(p.HandshakeHello, data)
    assert caught.value.code == "PROTOCOL_INCOMPATIBLE"


@pytest.mark.parametrize("field", ["protocol_name", "protocol_version"])
def test_protocol_fields_required_on_wire(field):
    data = samples()["handshake"].model_dump(mode="json")
    del data[field]
    with pytest.raises(p.ProtocolViolation):
        p.parse_wire(p.HandshakeHello, data)
    data = samples()["handshake"].model_dump(mode="json")
    del data["product"][field]
    with pytest.raises(p.ProtocolViolation):
        p.parse_wire(p.HandshakeHello, data)


@pytest.mark.parametrize(
    "value", ["", "../../private", "/home/private", "C:\\private", "with spaces", "x" * 129, 123]
)
def test_invalid_opaque_identifier(value):
    with pytest.raises((ValidationError, ValueError)):
        capsule(capsule_id=value)


@pytest.mark.parametrize("value", ["", "g" * 64, "a" * 63, "A" * 64, 123])
def test_invalid_hash(value):
    with pytest.raises(ValidationError):
        evidence(content_hash=value)


@pytest.mark.parametrize(
    "field,value",
    [
        ("authority", "SYSTEM"),
        ("privacy", "CLOUD_ALLOWED"),
        ("privacy", "PUBLIC"),
        ("authority", 1),
    ],
)
def test_invalid_authority_and_privacy(field, value):
    with pytest.raises(ValidationError):
        evidence(**{field: value})


def test_context_default_has_no_content_and_is_deeply_immutable():
    item = capsule()
    assert item.content.level == "NONE" and item.content.text is None
    assert isinstance(item.evidence, tuple)
    with pytest.raises(ValidationError):
        item.task_status = "COMPLETED"
    with pytest.raises(ValidationError):
        item.evidence[0].authority = "ADVISORY"


def test_content_requires_explicit_per_request_consent_and_matching_selection_hash():
    with pytest.raises(ValidationError):
        p.ContextContent(level="SELECTED_TEXT", text="Synthetic selected text")
    with pytest.raises(ValidationError):
        p.ContextContent(level="NONE", text="Synthetic selected text", consent_id="consent-1")
    content = p.ContextContent(
        level="SELECTED_TEXT", text="Synthetic selected text", consent_id="consent-1"
    )
    with pytest.raises(ValidationError):
        capsule(content=content)
    with pytest.raises(ValidationError):
        capsule(content=content, selection_id="selection-1", selection_hash="a" * 64)
    selected = capsule(
        content=content, selection_id="selection-1", selection_hash=p.canonical_hash(content.text)
    )
    assert selected.content.text == "Synthetic selected text"


def test_capsule_hash_covers_state_version_privacy_and_content():
    item = capsule()
    for field, value in (
        ("task_status", "COMPLETED"),
        ("source_version", "38"),
        ("privacy_scope", "CONSENTED_CLOUD"),
        ("project_version", "changed"),
    ):
        changed = item.model_dump(mode="json")
        changed[field] = value
        with pytest.raises(p.ProtocolViolation):
            p.parse_wire(p.AppContextCapsule, changed)


def test_canonical_hash_is_order_independent_and_hydrated():
    assert p.canonical_hash({"b": 1, "a": 2}) == p.canonical_hash({"a": 2, "b": 1})
    item = capsule()
    assert item.capsule_hash == p.canonical_hash(item, exclude=("capsule_hash",))
    assert item.capsule_hash == capsule().capsule_hash
    assert (
        p.parse_wire(p.AppContextCapsule, item.model_dump_json()).capsule_hash == item.capsule_hash
    )


@pytest.mark.parametrize(
    "change",
    [{"source_version": "38"}, {"project_version": "project-version-38"}, {"chapter_version": 38}],
)
def test_stale_source_versions_fail(change):
    with pytest.raises(p.ProtocolViolation) as caught:
        p.validate_capsule(capsule(), now=NOW + timedelta(seconds=1), **change)
    assert caught.value.code == "SOURCE_CHANGED"


def test_expired_or_future_capsule_fails():
    for now in (NOW - timedelta(seconds=1), NOW + timedelta(minutes=5)):
        with pytest.raises(p.ProtocolViolation) as caught:
            p.validate_capsule(capsule(), now=now)
        assert caught.value.code == "CONTEXT_STALE"
    p.validate_capsule(
        capsule(), now=NOW + timedelta(seconds=1), source_version="37", chapter_version=37
    )


@pytest.mark.parametrize(
    "required,available",
    [
        (["model.execute"], ["model.execute"]),
        (["project.context.read"], []),
        (["unrecognized.capability"], ["unrecognized.capability"]),
    ],
)
def test_missing_or_forbidden_capability_is_explicit(required, available):
    with pytest.raises(p.ProtocolViolation) as caught:
        p.require_capabilities(required, available)
    assert caught.value.code == "CAPABILITY_NOT_SUPPORTED"


def test_future_advertisement_does_not_grant_future_capability():
    advertised = product().model_dump(mode="json")
    advertised["capabilities"].append("future.safe.metadata")
    assert "future.safe.metadata" in p.parse_wire(p.ProductDescriptor, advertised).capabilities
    with pytest.raises(ValidationError):
        p.CapabilityNegotiation(
            hello_id="hello-1",
            requested_capabilities=("future.safe.metadata",),
            granted_capabilities=("future.safe.metadata",),
        )
    with pytest.raises(ValidationError):
        p.CapabilityNegotiation(
            hello_id="hello-1",
            requested_capabilities=(),
            granted_capabilities=("project.context.read",),
        )


def test_authority_comes_from_host_provenance_not_a_wire_claim():
    item = evidence()
    trusted = p.TrustedSourceProvenance(
        source_id=item.source_id,
        source_version=item.source_version,
        content_hash=item.content_hash,
        authority="AUTHORITATIVE",
        privacy="LOCAL_ONLY",
        origin="HOST_STATE",
    )
    p.validate_evidence_authority(item, trusted)
    forged = p.TrustedSourceProvenance(
        source_id=item.source_id,
        source_version=item.source_version,
        content_hash=item.content_hash,
        authority="AUTHORITATIVE",
        privacy="LOCAL_ONLY",
        origin="LLM",
    )
    with pytest.raises(p.ProtocolViolation) as caught:
        p.validate_evidence_authority(item, forged)
    assert caught.value.code == "PERMISSION_DENIED"
    with pytest.raises(p.ProtocolViolation):
        p.validate_evidence_authority(item, {"origin": "HOST_STATE"})
    changed = p.TrustedSourceProvenance(
        source_id=item.source_id,
        source_version="38",
        content_hash=item.content_hash,
        authority="AUTHORITATIVE",
        privacy="LOCAL_ONLY",
        origin="HOST_STATE",
    )
    with pytest.raises(p.ProtocolViolation) as caught:
        p.validate_evidence_authority(item, changed)
    assert caught.value.code == "SOURCE_CHANGED"


def test_privacy_strictest_inheritance_and_no_implicit_summary_upgrade():
    assert p.strictest_privacy() == "LOCAL_ONLY"
    assert p.strictest_privacy("CONSENTED_CLOUD", "REDACTION_REQUIRED") == "REDACTION_REQUIRED"
    assert p.strictest_privacy("REDACTION_REQUIRED", "LOCAL_ONLY") == "LOCAL_ONLY"
    with pytest.raises(p.ProtocolViolation):
        p.validate_derived_privacy("CONSENTED_CLOUD", ("LOCAL_ONLY",))
    with pytest.raises(ValidationError):
        capsule(privacy_scope="CONSENTED_CLOUD")
    with pytest.raises(ValidationError):
        diagnostic(privacy_scope="REDACTION_REQUIRED")
    with pytest.raises(ValidationError):
        p.TutorRequest(
            request_id="request-1",
            session_id="session-1",
            context=capsule(),
            task_requirement=p.TaskRequirement(
                task_type="generation",
                required_modality=("TEXT",),
                estimated_context=1,
                privacy="CONSENTED_CLOUD",
            ),
        )


def test_advice_cannot_claim_authoritative_or_verified_success():
    guidance = samples()["tutor-response"].model_dump(mode="json")
    guidance["authority"] = "AUTHORITATIVE"
    with pytest.raises(p.ProtocolViolation):
        p.parse_wire(p.TutorGuidance, guidance)
    with pytest.raises(ValidationError):
        p.VerifierResult(
            request_id="request-1",
            session_id="session-1",
            result_id="result-1",
            status="VERIFIED",
            reason="An LLM said it succeeded",
            evidence=(evidence(authority="ADVISORY"),),
            created_at=NOW,
        )
    assert capsule().task_status == "FAILED"


@pytest.mark.parametrize(
    "secret",
    [
        "api_key=synthetic-value",
        "Bearer abcdefghijklmnopqrstuvwxyz",
        "sk-abcdefghijklmnop0123456789",
        "postgresql://user:password@localhost/database",
    ],
)
def test_no_credential_shaped_text_is_transferred(secret):
    with pytest.raises(ValidationError):
        p.ContextContent(level="SELECTED_TEXT", text=secret, consent_id="consent-1")
    with pytest.raises(ValidationError):
        p.TutorRequest(
            request_id="request-1", session_id="session-1", context=capsule(), question=secret
        )


@pytest.mark.parametrize(
    "field",
    [
        "api_key",
        "provider_secret",
        "oauth_token",
        "vault_secret",
        "cookie",
        "session_token",
        "raw_prompt",
        "raw_manuscript",
        "local_full_path",
        "raw_screenshot",
        "logs",
    ],
)
def test_diagnostic_has_no_arbitrary_content_or_secret_fields(field):
    data = diagnostic().model_dump(mode="json")
    data[field] = "synthetic forbidden data"
    with pytest.raises(p.ProtocolViolation):
        p.parse_wire(p.DiagnosticCapsule, data)


def test_diagnostic_preview_can_remove_all_metadata():
    item = p.create_diagnostic(
        diagnostic_id="diagnostic-1",
        source_version="37",
        created_at=NOW,
        expires_at=NOW + timedelta(minutes=1),
    )
    assert item.software_id is None and item.feature is None and item.evidence == ()


@pytest.mark.parametrize(
    "locator",
    [
        "/home/person/private.txt",
        "C:\\Users\\person\\private.txt",
        "file:///private",
        "https://example.com/private",
        "../private",
        "task:../../private",
    ],
)
def test_locator_cannot_be_file_path_or_network_locator(locator):
    with pytest.raises(ValidationError):
        evidence(locator=locator)


def test_event_never_carries_selection_content():
    selected = capsule(
        content=p.ContextContent(
            level="SELECTED_TEXT", text="Synthetic selection", consent_id="consent-1"
        ),
        selection_id="selection-1",
        selection_hash=p.canonical_hash("Synthetic selection"),
    )
    with pytest.raises(ValidationError):
        p.InteropEvent(
            event_id="event-1",
            session_id="session-1",
            sequence=1,
            event_type="TASK_UPDATED",
            created_at=NOW,
            context=selected,
        )


@pytest.mark.parametrize(
    "target",
    [
        {
            "action": "OPEN_PROJECT",
            "target_product_id": p.STUDIO_PRODUCT_ID,
            "project_id": "project-1",
        },
        {
            "action": "OPEN_FEATURE",
            "target_product_id": p.STUDIO_PRODUCT_ID,
            "feature": "model-center",
            "project_id": "project-1",
        },
        {
            "action": "RUN_MODEL",
            "target_product_id": p.STUDIO_PRODUCT_ID,
            "feature": "model-center",
        },
        {
            "action": "OPEN_FEATURE",
            "target_product_id": "invalid product",
            "feature": "model-center",
        },
    ],
)
def test_malformed_handoff_is_rejected(target):
    with pytest.raises(ValidationError):
        p.HandoffTarget(**target)


def test_handoff_requires_gesture_identifier_but_host_must_verify_it():
    with pytest.raises(ValidationError):
        p.HandoffRequest(
            request_id="request-1",
            session_id="session-1",
            target=p.HandoffTarget(
                action="OPEN_FEATURE", target_product_id=p.STUDIO_PRODUCT_ID, feature="model-center"
            ),
        )


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://0.0.0.0:8080",
        "http://192.168.1.2:8080",
        "http://localhost:8080",
        "https://127.0.0.1:8080",
        "http://127.0.0.1:8080?token=private",
        "http://user:secret@127.0.0.1:8080",
        "http://127.0.0.1:8080#token",
        "http://127.0.0.1:8080/redirect",
        "http://[::1]:8080",
        "http://2130706433:8080",
    ],
)
def test_non_loopback_or_credential_url_is_rejected(endpoint):
    with pytest.raises(p.ProtocolViolation) as caught:
        p.assert_local_endpoint(endpoint)
    assert caught.value.code == "TRANSPORT_ERROR"


def test_literal_loopback_endpoint_is_accepted():
    p.assert_local_endpoint("http://127.0.0.1:8080")
    p.assert_local_endpoint("http://127.0.0.1:8080/")


@pytest.mark.parametrize(
    "payload",
    [
        '{"protocol_name":"PoemSeed Local Interop","protocol_version":"1.0",'
        '"code":"TIMEOUT","code":"CANCELLED","message":"message"}',
        '{"protocol_name":"PoemSeed Local Interop","protocol_version":"1.0",'
        '"code":"TIMEOUT","message":NaN}',
        "[]",
        "{broken",
        b"\xff",
    ],
)
def test_duplicate_nonfinite_and_malformed_json_fail_closed(payload):
    with pytest.raises(p.ProtocolViolation):
        p.parse_wire(p.InteropError, payload)


def test_bounded_message_and_strict_numeric_types():
    with pytest.raises(p.ProtocolViolation):
        p.parse_wire(p.InteropError, "x" * (p.MAX_MESSAGE_BYTES + 1))
    for value in (True, "1", 1.0, -1):
        with pytest.raises(ValidationError):
            p.Heartbeat(session_id="session-1", sequence=value, created_at=NOW)
    with pytest.raises((ValidationError, ValueError)):
        capsule(created_at=NOW.replace(tzinfo=None))


def test_transport_operation_must_match_strict_payload_type():
    with pytest.raises(ValidationError):
        p.TransportRequest(operation="VERIFY", payload=samples()["handshake"])
    with pytest.raises(ValidationError):
        p.TransportResponse(operation="VERIFY", payload=samples()["tutor-response"])
    error = p.TransportResponse(
        operation="VERIFY",
        payload=p.InteropError(code="VERIFIER_UNAVAILABLE", message="Unavailable"),
    )
    assert error.payload.code == "VERIFIER_UNAVAILABLE"


def test_contract_manifest_matches_bytes_and_regeneration(tmp_path):
    manifest = json.loads((CONTRACTS / "parity-manifest.json").read_text())
    assert manifest["protocol_version"] == p.PROTOCOL_VERSION
    for name, expected in manifest["files"].items():
        assert sha256((ROOT / name).read_bytes()).hexdigest() == expected, name
    # Generator output matches checked-in schemas/interfaces, independently of mtime.
    generate(tmp_path)
    generated = tmp_path / "contracts/local-interop/v1"
    for name in [
        *map(lambda slug: f"{slug}.schema.json", SCHEMAS),
        "common.schema.json",
        "protocol.ts",
        "protocol.rs",
    ]:
        assert (generated / name).read_bytes() == (CONTRACTS / name).read_bytes(), name


@pytest.mark.parametrize("sanitized", [1, 0, False, "true"])
def test_diagnostic_sanitized_literal_does_not_coerce(sanitized):
    with pytest.raises(ValidationError):
        diagnostic(sanitized=sanitized)


@pytest.mark.parametrize(
    "origin", [" http://127.0.0.1:8080", "http://127.0.0.1:08080", "http://127.0.0.1:8080/\r\n"]
)
def test_ambiguous_loopback_origin_is_rejected(origin):
    with pytest.raises(p.ProtocolViolation):
        p.assert_local_endpoint(origin)


def test_evidence_cannot_be_future_dated_or_duplicated():
    with pytest.raises(ValidationError):
        capsule(evidence=(evidence(timestamp=NOW + timedelta(seconds=1)),))
    with pytest.raises(ValidationError):
        capsule(evidence=(evidence(), evidence()))


def test_schema_rejects_cross_field_handoff_and_privacy_violations():
    handoff = samples()["handoff"].model_dump(mode="json")
    handoff["target"]["feature"] = "model-center"
    schema = json.loads((CONTRACTS / "handoff.schema.json").read_text())
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(schema).validate(handoff)
    diagnostic_data = diagnostic().model_dump(mode="json")
    diagnostic_data["privacy_scope"] = "CONSENTED_CLOUD"
    schema = json.loads((CONTRACTS / "diagnostic.schema.json").read_text())
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(schema).validate(diagnostic_data)
    result = samples()["verifier-result"].model_dump(mode="json")
    result["evidence"] = []
    schema = json.loads((CONTRACTS / "verifier-result.schema.json").read_text())
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(schema).validate(result)
