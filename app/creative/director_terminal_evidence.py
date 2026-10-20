"""Passive historical evidence, never fresh execution/review/adoption authority.

Authority and bounds were sampled at the named pre-commit checkpoint, not at
physical replacement. Participating File owners are coordinated; neither
hostile filesystem tampering nor power-loss durability is promised. No second
text copy is retained. Future consumers must separately validate matching text
and fresh authority; this foundation deliberately provides no such consumer.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from .director_binding import CreativeDirectorSourceBinding, creative_director_job_binding

FIELD = "_creative_director_terminal_evidence"
CONTRACT = "CREATIVE_DIRECTOR_TERMINAL_HISTORY_V1"


@dataclass(frozen=True, slots=True)
class _PublicationAcknowledgment:
    """Transient original-repository return value, never serialized authority."""
    capability: object
    repository: object
    job: object
    evidence_digest: str


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class _Admission(_Strict):
    proposal_id: str = Field(min_length=1)
    proposal_version: int = Field(ge=1)
    preview_id: str = Field(min_length=1)
    preview_version: int = Field(ge=1)
    preview_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    output_contract: str | None


class _Parameters(_Strict):
    max_output_tokens: int = Field(ge=1, le=2048)
    temperature: float = Field(ge=0, le=2, allow_inf_nan=False)


class _Route(_Strict):
    route_id: str = Field(min_length=1)
    fingerprint: str = Field(min_length=1)
    binding_hash: str = Field(min_length=1)
    provider_id: str = Field(min_length=1)
    model_id: str = Field(min_length=1)
    parameters: _Parameters
    execution_mode: str = Field(min_length=1)
    synthetic: bool


class _Accounting(_Strict):
    reservation_id: str = Field(min_length=1)
    version: int = Field(ge=1)
    digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    status: Literal["SETTLED"]
    job_status: Literal["COMPLETED"]
    dispatched: Literal[True]
    actual_microusd: Literal[0]


class TerminalEvidence(_Strict):
    contract: Literal["CREATIVE_DIRECTOR_TERMINAL_HISTORY_V1"]
    schema_version: Literal[1]
    semantics: Literal["AUTHORITY_AND_BOUNDS_SAMPLED_PRE_COMMIT"]
    consumer_authority: Literal[False]
    checkpoint_at: str
    job_id: str
    operation: Literal["creative_director_text"]
    origin: Literal["creative_director_source_model"]
    source_binding: CreativeDirectorSourceBinding
    request_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    output_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    output_bytes: int = Field(ge=1, le=128000)
    maximum_output_bytes: int = Field(ge=256, le=128000)
    generation_deadline: str
    admission: _Admission
    route: _Route
    accounting: _Accounting


def validate_evidence(value, item):
    """Bind history to immutable identity, never to mutable current output/status."""
    try:
        evidence = TerminalEvidence.model_validate(value).model_dump()
        binding = creative_director_job_binding(item)
        checkpoint = datetime.fromisoformat(evidence["checkpoint_at"])
        deadline = datetime.fromisoformat(evidence["generation_deadline"])
        if (str(UUID(evidence["job_id"])) != evidence["job_id"]
                or evidence["job_id"] != item["id"]
                or evidence["source_binding"] != binding
                or evidence["request_digest"] != item.get("expected_request_digest")
                or evidence["admission"]["preview_digest"] != binding["reviewed_preview_digest"]
                or checkpoint.tzinfo is None or deadline.tzinfo is None or checkpoint >= deadline
                or evidence["output_bytes"] > evidence["maximum_output_bytes"]
                or type(value["accounting"]["actual_microusd"]) is not int
                or type(value["schema_version"]) is not int
                or value["consumer_authority"] is not False
                or value["accounting"]["dispatched"] is not True):
            raise ValueError("invalid historical identity")
        return evidence
    except (ValueError, TypeError, KeyError, AttributeError):
        raise ValueError("CREATIVE_DIRECTOR_TERMINAL_EVIDENCE_INVALID") from None


def preserve_evidence(previous, item):
    """Generic saves cannot mint, replace or explicitly erase historical evidence."""
    exists = isinstance(previous, dict) and FIELD in previous
    if not exists:
        if FIELD in item:
            raise ValueError("CREATIVE_DIRECTOR_TERMINAL_EVIDENCE_OWNER_REQUIRED")
        return item
    evidence = validate_evidence(previous[FIELD], previous)
    validate_evidence(evidence, item)
    if FIELD in item:
        validate_evidence(item[FIELD], item)
        if digest(item[FIELD]) != digest(previous[FIELD]):
            raise ValueError("CREATIVE_DIRECTOR_TERMINAL_EVIDENCE_IMMUTABLE")
    result = dict(item)
    result[FIELD] = deepcopy(previous[FIELD])
    return result


# Parsed candidates live only in the original proposal. This private receipt
# records explicit fresh-authorized publication, never an execution capability.
PENDING_FIELD = "_creative_director_pending_review"
PENDING_CONTRACT = "CREATIVE_DIRECTOR_PENDING_REVIEW_V1"


class PendingReview(_Strict):
    contract: Literal["CREATIVE_DIRECTOR_PENDING_REVIEW_V1"]
    schema_version: Literal[1]
    proposal_id: str = Field(min_length=1)
    admitted_version: int = Field(ge=1)
    published_version: int = Field(ge=2)
    terminal_evidence_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    output_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    published_by: str = Field(min_length=1)
    published_at: str
    provenance: dict
    adoption: dict | None = None


def validate_pending(value):
    try:
        pending = PendingReview.model_validate(value).model_dump(exclude_unset=True)
        if "adoption" in pending:
            from .director_lifecycle import validate_adoption
            pending["adoption"] = validate_adoption(pending["adoption"])
        if (type(value["schema_version"]) is not int
                or pending["published_version"] != pending["admitted_version"] + 1
                or datetime.fromisoformat(pending["published_at"]).tzinfo is None
                or digest(pending) != digest(value)):
            raise ValueError("invalid pending identity")
        return pending
    except (ValueError, TypeError, KeyError, AttributeError):
        raise ValueError("CREATIVE_DIRECTOR_PENDING_REVIEW_INVALID") from None
