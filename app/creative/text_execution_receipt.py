"""Bounded, passive text-execution evidence. This module grants no authority.

The original Job, broker decision/ledger, graph and asset remain the owners.
Neither a receipt nor its request data can prepare, authorize or replay a job.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta
from hashlib import sha256
import json
import re

from ..experimental.store import canonical

CONTRACT = "creative-graph-text-execution/1"
PRIVATE_FIELD = "_text_execution_receipt"
MAX_BYTES = 64_000


def _fail():
    raise ValueError("TEXT_EXECUTION_RECEIPT_INVALID")


def _keys(value, keys):
    if not isinstance(value, dict) or set(value) != set(keys.split()):
        _fail()


def _text(value, limit=240):
    if (not isinstance(value, str) or not value.strip() or len(value) > limit
            or any(ord(char) < 32 or ord(char) == 127 for char in value)):
        _fail()


def _digest(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-f0-9]{64}", value):
        _fail()


def request_payload(preview, node):
    """Expected data of the existing bounded TextModelNode contract, not a request."""
    return {"provider_id": preview["route"]["provider_id"], "model_id": preview["route"]["model_id"],
        "prompt": preview["prompt"], "system_instruction": None, "context": {},
        "parameters": {"temperature": 0.0, "max_output_tokens": node["parameters"]["max_output_tokens"],
                       "stop_sequences": []},
        "structured_output_schema": None, "metadata": {"purpose": "creative_graph_model"}}


def model_evidence(identity):
    return {"kind": "SYNTHETIC_PROTOCOL" if identity.get("synthetic") else "MODEL_CENTER_METADATA",
        "model_fingerprint": identity.get("model_version"), "runtime_fingerprint": identity.get("runtime_hash"),
        "runtime_version": identity.get("runtime_version")}


def receipt_payload(preview, node, chosen, origin, *, execution_mode, request_digest, settlement_id):
    """One passive shape for admission sizing and verified terminal evidence.

    This builds data only. Callers must retain the original owner checks; a
    sizing payload is never persisted or exposed as a completed execution.
    """
    payload = request_payload(preview, node)
    identity = chosen.get("identity") or {}
    return {"schema_version": 1, "contract": CONTRACT,
        "prompt": payload["prompt"], "prompt_sha256": sha256(payload["prompt"].encode()).hexdigest(),
        "provider_id": chosen["provider_id"], "model_id": chosen["model_id"],
        "route_id": chosen["route_id"], "route_fingerprint": chosen["fingerprint"],
        "route_identity": deepcopy(identity), "model_evidence": model_evidence(identity),
        "parameters": payload["parameters"], "execution_mode": execution_mode,
        "request_digest": request_digest, "workflow": deepcopy(origin),
        "terminal": {"status": "COMPLETED", "settlement_id": settlement_id, "settled_at": origin["produced_at"]},
        "quality_verification": "NOT_RUN"}


def validate_receipt(value, *, source, provider_id, model_id, parameters):
    """Structural and digest checks at the existing asset-owner boundary.

    Source/job/route/ledger authorization must additionally be checked by the
    graph coordinator immediately before commit and before every projection.
    """
    _keys(value, "schema_version contract prompt prompt_sha256 provider_id model_id route_id route_fingerprint "
        "model_evidence parameters execution_mode request_digest workflow terminal quality_verification route_identity")
    if (type(value["schema_version"]) is not int or value["schema_version"] != 1
            or value["contract"] != CONTRACT or value["quality_verification"] != "NOT_RUN"
            or value["workflow"] != source or value["provider_id"] != provider_id or value["model_id"] != model_id):
        _fail()
    for name in ("provider_id", "model_id"):
        _text(value[name])
    for name in ("prompt_sha256", "route_id", "route_fingerprint", "request_digest"):
        _digest(value[name])
    prompt = value["prompt"]
    try:
        if (not isinstance(prompt, str) or not prompt.strip() or not 0 < len(prompt.encode()) <= 32_000
                or sha256(prompt.encode()).hexdigest() != value["prompt_sha256"]):
            _fail()
        encoded = json.dumps(value, ensure_ascii=False, allow_nan=False).encode()
        if len(encoded) > MAX_BYTES:
            _fail()
    except (TypeError, UnicodeError):
        _fail()
    params = value["parameters"]
    _keys(params, "temperature max_output_tokens stop_sequences")
    if (type(params["temperature"]) not in {int, float} or params["temperature"] != 0
            or type(params["max_output_tokens"]) is not int or not 1 <= params["max_output_tokens"] <= 2048
            or params["stop_sequences"] != [] or params["max_output_tokens"] != parameters.get("max_output_tokens")
            or params["temperature"] != parameters.get("temperature")):
        _fail()
    identity = value["route_identity"]
    if (not isinstance(identity, dict) or len(canonical(identity).encode()) > 16_000
            or sha256(canonical(identity).encode()).hexdigest() != value["route_fingerprint"]
            or identity.get("provider_id") != provider_id or identity.get("model_id") != model_id
            or identity.get("cloud") is not False or type(identity.get("synthetic")) is not bool
            or identity["synthetic"] != parameters.get("synthetic")
            or value["route_id"] != sha256(canonical([provider_id, model_id]).encode()).hexdigest()):
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
    terminal = value["terminal"]
    _keys(terminal, "status settlement_id settled_at")
    if terminal["status"] != "COMPLETED" or terminal["settled_at"] != source["produced_at"]:
        _fail()
    _text(terminal["settlement_id"])
    try:
        stamp = datetime.fromisoformat(terminal["settled_at"])
        if stamp.tzinfo is None or stamp.utcoffset() != timedelta(0):
            _fail()
    except (ValueError, TypeError, OverflowError):
        _fail()
    return deepcopy(value)


def public_receipt(value):
    """Only the current actor-scoped graph projection may expose this prompt."""
    return {key: deepcopy(item) for key, item in value.items() if key != "route_identity"}
