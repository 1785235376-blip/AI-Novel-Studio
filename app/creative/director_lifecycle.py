"""Strict passive private lifecycle receipts; no execution or storage owner.

These objects are not public endpoints and never restore execution authority.
Only the original coordinator can bind them to current original-owner data.
"""
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from .director_terminal_evidence import digest

Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Identifier = Annotated[str, Field(min_length=1, max_length=240)]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class DocumentReceipt(_Strict):
    document_id: Identifier
    version: int = Field(ge=1)
    digest: Digest
    mode: Literal["DIRECTOR"] = "DIRECTOR"
    status: Literal["DRAFT"] = "DRAFT"


class AdoptionReceipt(_Strict):
    contract: Literal["CREATIVE_DIRECTOR_ADOPTED_DRAFT_V1"]
    proposal_id: Identifier
    reviewed_version: int = Field(ge=1)
    approved_version: int = Field(ge=2)
    reviewed_by: Identifier
    review_action_digest: Digest
    candidate_output_digest: Digest
    reviewed_output_digest: Digest
    source_document_id: Identifier
    source_version: int = Field(ge=1)
    source_digest: Digest
    job_id: Identifier
    request_digest: Digest
    terminal_evidence_digest: Digest
    document: DocumentReceipt


class CancelInput(_Strict):
    expected_version: int = Field(ge=1)
    job_id: Identifier
    request_digest: Digest
    reviewed_preview_digest: Digest


class StatusReceipt(_Strict):
    contract: Literal["CREATIVE_DIRECTOR_STATUS_V1"] = "CREATIVE_DIRECTOR_STATUS_V1"
    proposal_id: Identifier
    version: int = Field(ge=1)
    phase: Literal["PREVIEW", "ADMITTED", "RUNNING", "SETTLING", "COMPLETED", "FAILED", "CANCELLED",
                   "UNKNOWN", "PENDING_REVIEW", "ADOPTED_DRAFT"]
    job_id: Identifier | None = None
    request_digest: Digest | None = None
    reviewed_preview_digest: Digest
    cancellation_requested: bool = False
    cancellation_confirmed: bool = False
    dispatch_state: Literal["NOT_DISPATCHED", "DISPATCHED"] = "NOT_DISPATCHED"
    settlement_state: Literal["NOT_APPLICABLE", "RESERVED", "DISPATCHED", "RELEASED", "SETTLED", "UNKNOWN_UPSTREAM"] = "NOT_APPLICABLE"
    upstream_cancellation_guaranteed: Literal[False] = False
    terminal_evidence_digest: Digest | None = None
    adoption: AdoptionReceipt | None = None
    automatic_retry: Literal[False] = False


def review_action_digest(body):
    # Omitted visual_target preserves the authored goal; explicit null clears
    # it. Hash the normalized schema AND explicit fields to retain that choice.
    return digest({"body": body.model_dump(), "fields": sorted(body.model_fields_set)})


def validate_adoption(value):
    try:
        receipt = AdoptionReceipt.model_validate(value).model_dump()
        if (receipt["approved_version"] != receipt["reviewed_version"] + 1
                or digest(receipt) != digest(value)):
            raise ValueError("different exact receipt")
        return receipt
    except (ValueError, TypeError, KeyError, AttributeError):
        raise ValueError("CREATIVE_DIRECTOR_ADOPTION_RECEIPT_INVALID") from None
