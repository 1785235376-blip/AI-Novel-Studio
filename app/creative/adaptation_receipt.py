"""Closed, passive adaptation archive evidence; no execution or write authority.

The original Job, proposal, Broker and asset service remain the owners. This
module deliberately does not import an owner, construct requests or invoke a
model. Admission uses the same encoders and validators as the asset boundary.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta
from hashlib import sha256
import json
import re

from ..experimental.store import canonical

ASSET_CONTRACT = "creative-adaptation-text-asset/1"
CONTRACT = "creative-adaptation-text-execution/1"
REVIEW_CONTRACT = "creative-adaptation-text-review/1"
PUBLICATION_CONTRACT = "creative-adaptation-terminal-publication/1"
PRIVATE_FIELD = "_text_execution_receipt"
FEATURES = frozenset(("narrative_production_v2", "model_broker_v2", "author_context_inspector_v2"))
MAX_OUTPUT_BYTES = 128_000
MAX_PROMPT_BYTES = 128_000
MAX_REQUEST_BYTES = 256_000
MAX_BYTES = 384_000
MAX_METADATA_BYTES = 400_000
MAX_VERSION = 2**53 - 1


def _fail(code="ADAPTATION_TEXT_EXECUTION_RECEIPT_INVALID"):
    raise ValueError(code)


def _keys(value, keys, code="ADAPTATION_TEXT_EXECUTION_RECEIPT_INVALID"):
    if not isinstance(value, dict) or set(value) != set(keys.split()):
        _fail(code)


def _text(value, limit=240):
    if (not isinstance(value, str) or not value.strip() or len(value) > limit
            or any(ord(char) < 32 or ord(char) == 127 for char in value)):
        _fail()


def _identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,239}", value):
        _fail()


def _chapter_identifier(value):
    # Chapter references are original Creative identifiers, not asset paths.
    # The original owner emits both novel:1 and novel:~UUID chapter tokens.
    _text(value)
    if "/" in value or "\\" in value or value in {".", ".."}:
        _fail()


def _digest(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-f0-9]{64}", value):
        _fail()


def _version(value):
    if type(value) is not int or not 1 <= value <= MAX_VERSION:
        _fail()


def _stamp(value):
    if not isinstance(value, str) or not 1 <= len(value) <= 64:
        _fail()
    try:
        stamp = datetime.fromisoformat(value)
        if stamp.tzinfo is None or stamp.utcoffset() != timedelta(0):
            _fail()
    except (ValueError, OverflowError):
        _fail()


def encode_receipt(value):
    """Actual logical-budget bytes (including JSON escapes), not char counts."""
    try:
        return json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, UnicodeError, RecursionError):
        _fail()


def validate_source(value):
    _keys(value, "schema_version contract proposal_id source_proposal_version chapter_id source_version "
        "source_digest selection_digest job_id output_digest preview_digest produced_at",
        "ADAPTATION_TEXT_SOURCE_RECEIPT_INVALID")
    if type(value["schema_version"]) is not int or value["schema_version"] != 1 or value["contract"] != ASSET_CONTRACT:
        _fail("ADAPTATION_TEXT_SOURCE_RECEIPT_INVALID")
    for key in ("proposal_id", "job_id"):
        _identifier(value[key])
    _chapter_identifier(value["chapter_id"])
    for key in ("source_proposal_version", "source_version"):
        _version(value[key])
    for key in ("source_digest", "selection_digest", "output_digest", "preview_digest"):
        _digest(value[key])
    _stamp(value["produced_at"])
    return deepcopy(value)


def validate_request(value, *, provider_id, model_id):
    _keys(value, "provider_id model_id prompt system_instruction context parameters structured_output_schema metadata")
    if (value["provider_id"] != provider_id or value["model_id"] != model_id
            or value["system_instruction"] is not None or value["structured_output_schema"] is not None
            or value["context"] != {} or value["metadata"] != {"purpose": "brainstorm"}):
        _fail()
    _text(provider_id)
    _text(model_id)
    params = value["parameters"]
    _keys(params, "temperature max_output_tokens stop_sequences")
    if params != {"temperature": None, "max_output_tokens": None, "stop_sequences": []}:
        _fail()
    prompt = value["prompt"]
    try:
        if not isinstance(prompt, str) or not prompt.strip() or not 0 < len(prompt.encode("utf-8")) <= MAX_PROMPT_BYTES:
            _fail("ADAPTATION_TEXT_PROMPT_LIMIT")
    except UnicodeError:
        _fail()
    if len(encode_receipt(value)) > MAX_REQUEST_BYTES:
        _fail("ADAPTATION_TEXT_REQUEST_LIMIT")
    return deepcopy(value)


def model_evidence(identity):
    return {"kind": "SYNTHETIC_PROTOCOL" if identity.get("synthetic") else "MODEL_CENTER_METADATA",
        "model_fingerprint": identity.get("model_version"), "runtime_fingerprint": identity.get("runtime_hash"),
        "runtime_version": identity.get("runtime_version")}


def asset_parameters(request, chosen):
    return {**deepcopy(request["parameters"]), "synthetic": chosen["identity"]["synthetic"],
        "quality_verification": "NOT_RUN"}


def receipt_payload(request, chosen, origin, *, execution_mode, request_digest, settlement_id, settlement_version,
                    generation_bounds, final_publication):
    """Build passive data for validated terminal evidence or admission sizing.

    A sizing payload is never persisted as evidence. Only the coordinator can
    establish the original owners and current actor/Host/source authority.
    """
    identity = chosen.get("identity") or {}
    return {"schema_version": 1, "contract": CONTRACT, "request": deepcopy(request),
        "request_payload_sha256": sha256(canonical(request).encode("utf-8")).hexdigest(),
        "prompt_sha256": sha256(request["prompt"].encode("utf-8")).hexdigest(),
        "provider_id": chosen["provider_id"], "model_id": chosen["model_id"],
        "route_id": chosen["route_id"], "route_fingerprint": chosen["fingerprint"],
        "route_identity": deepcopy(identity), "model_evidence": model_evidence(identity),
        "request_digest": request_digest, "execution_mode": execution_mode, "workflow": deepcopy(origin),
        "generation_bounds": deepcopy(generation_bounds),
        "terminal": {"status": "COMPLETED", "settlement_id": settlement_id, "settlement_version": settlement_version,
            "settled_at": origin["produced_at"],
            "final_publication": deepcopy(final_publication)}, "quality_verification": "NOT_RUN"}


def validate_publication(value, *, source, request_digest):
    _keys(value, "schema_version contract job_id request_digest output_digest")
    if (type(value["schema_version"]) is not int or value["schema_version"] != 1
            or value["contract"] != PUBLICATION_CONTRACT or value["job_id"] != source["job_id"]
            or value["request_digest"] != request_digest or value["output_digest"] != source["output_digest"]):
        _fail()
    _identifier(value["job_id"])
    _digest(value["request_digest"])
    _digest(value["output_digest"])
    return deepcopy(value)


def validate_receipt(value, *, source, provider_id, model_id, parameters):
    source = validate_source(source)
    _keys(value, "schema_version contract request request_payload_sha256 prompt_sha256 provider_id model_id "
        "route_id route_fingerprint route_identity model_evidence request_digest execution_mode workflow "
        "generation_bounds terminal quality_verification")
    if (type(value["schema_version"]) is not int or value["schema_version"] != 1
            or value["contract"] != CONTRACT or value["workflow"] != source
            or value["provider_id"] != provider_id or value["model_id"] != model_id
            or value["quality_verification"] != "NOT_RUN"):
        _fail()
    if len(encode_receipt(value)) > MAX_BYTES:
        _fail("ADAPTATION_TEXT_EXECUTION_RECEIPT_LIMIT")
    request = validate_request(value["request"], provider_id=provider_id, model_id=model_id)
    for key in ("request_payload_sha256", "prompt_sha256", "route_id", "route_fingerprint", "request_digest"):
        _digest(value[key])
    if (value["request_payload_sha256"] != sha256(canonical(request).encode("utf-8")).hexdigest()
            or value["prompt_sha256"] != sha256(request["prompt"].encode("utf-8")).hexdigest()):
        _fail()
    _keys(parameters, "temperature max_output_tokens stop_sequences synthetic quality_verification")
    if (any(parameters[key] != request["parameters"][key] for key in request["parameters"])
            or type(parameters["synthetic"]) is not bool or parameters["quality_verification"] != "NOT_RUN"):
        _fail()
    identity = value["route_identity"]
    if (not isinstance(identity, dict) or len(canonical(identity).encode("utf-8")) > 16_000
            or sha256(canonical(identity).encode("utf-8")).hexdigest() != value["route_fingerprint"]
            or identity.get("provider_id") != provider_id or identity.get("model_id") != model_id
            or identity.get("cloud") is not False or type(identity.get("synthetic")) is not bool
            or identity["synthetic"] != parameters["synthetic"]
            or value["route_id"] != sha256(canonical([provider_id, model_id]).encode("utf-8")).hexdigest()):
        _fail()
    evidence = value["model_evidence"]
    _keys(evidence, "kind model_fingerprint runtime_fingerprint runtime_version")
    if evidence != model_evidence(identity):
        _fail()
    if identity["synthetic"]:
        if (value["execution_mode"] != "mock_standin" or evidence["kind"] != "SYNTHETIC_PROTOCOL"
                or evidence["model_fingerprint"] != "synthetic-protocol-v1" or evidence["runtime_fingerprint"] is not None):
            _fail()
    else:
        if (value["execution_mode"] != "real" or evidence["kind"] != "MODEL_CENTER_METADATA"
                or identity.get("source_locality") != "LOCAL_VERIFIED" or identity.get("license_confirmed") is not True):
            _fail()
        _digest(evidence["model_fingerprint"])
        _digest(evidence["runtime_fingerprint"])
    if evidence["runtime_version"] is not None:
        _text(evidence["runtime_version"])
    bounds = value["generation_bounds"]
    _keys(bounds, "max_output_bytes deadline")
    if type(bounds["max_output_bytes"]) is not int or bounds["max_output_bytes"] != MAX_OUTPUT_BYTES:
        _fail()
    _stamp(bounds["deadline"])
    terminal = value["terminal"]
    _keys(terminal, "status settlement_id settlement_version settled_at final_publication")
    if terminal["status"] != "COMPLETED" or terminal["settled_at"] != source["produced_at"]:
        _fail()
    _text(terminal["settlement_id"])
    _version(terminal["settlement_version"])
    _stamp(terminal["settled_at"])
    validate_publication(terminal["final_publication"], source=source, request_digest=value["request_digest"])
    return deepcopy(value)


def validate_initial(initial, data, *, source_validator, metadata_encoder):
    """The original asset owner supplies its closed source-contract dispatcher."""
    _keys(initial, "_text_result_origin source_job_id provider_id model_id parameters _text_execution_receipt",
        "TEXT_RESULT_METADATA_INVALID")
    source = source_validator(initial["_text_result_origin"])
    if (source["contract"] != ASSET_CONTRACT or not isinstance(data, bytes) or not 0 < len(data) <= MAX_OUTPUT_BYTES
            or source["output_digest"] != sha256(data).hexdigest()):
        _fail("TEXT_RESULT_CONTENT_INVALID")
    try:
        if not data.decode("utf-8").strip() or b"\x00" in data:
            _fail("TEXT_RESULT_CONTENT_INVALID")
    except UnicodeError:
        _fail("TEXT_RESULT_CONTENT_INVALID")
    if initial["source_job_id"] != source["job_id"]:
        _fail("TEXT_RESULT_JOB_BINDING_INVALID")
    validate_receipt(initial[PRIVATE_FIELD], source=source, provider_id=initial["provider_id"],
        model_id=initial["model_id"], parameters=initial["parameters"])
    if len(metadata_encoder(initial)) > MAX_METADATA_BYTES:
        _fail("TEXT_RESULT_METADATA_LIMIT")
    return deepcopy(initial)


def validate_review(value, *, source, actor_id, output_digest):
    source = validate_source(source)
    _keys(value, "contract proposal_id proposal_version output_digest generated_output_digest reviewed_output_digest "
        "document_id document_version reviewed_by reviewed_at", "TEXT_RESULT_REVIEW_RECEIPT_INVALID")
    if (value["contract"] != REVIEW_CONTRACT or value["proposal_id"] != source["proposal_id"]
            or value["output_digest"] != source["output_digest"] or value["output_digest"] != output_digest
            or value["reviewed_by"] != actor_id or not actor_id
            or type(value["document_version"]) is not int or value["document_version"] != 1):
        _fail("TEXT_RESULT_REVIEW_BINDING_INVALID")
    _identifier(value["proposal_id"])
    _identifier(value["document_id"])
    # Actor identities are opaque original-owner metadata, never asset paths.
    _text(value["reviewed_by"])
    _version(value["proposal_version"])
    if value["proposal_version"] <= source["source_proposal_version"]:
        _fail("TEXT_RESULT_REVIEW_BINDING_INVALID")
    for key in ("output_digest", "generated_output_digest", "reviewed_output_digest"):
        _digest(value[key])
    _stamp(value["reviewed_at"])
    return deepcopy(value)


def public_receipt(value):
    """Only a freshly authorized actor/Host adaptation projection may use this."""
    return {key: deepcopy(item) for key, item in value.items() if key != "route_identity"}
