"""Strict request-admission receipts referencing only the original Job owner.

RESERVED means the request is fenced against automatic redispatch. It does not
mean that the original Job exists, started, or completed. Full v2 receipts keep
exactly their earlier shape; neither kind is a replacement Job state machine.
"""
import re
from uuid import UUID

_OWNER = re.compile(r"(?:file|postgres):[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}")
_RESERVED_KEYS = {"schema_version", "admission_state", "project_incarnation", "request_digest", "job_id"}
_RESULT_KEYS = {"job_id", "status", "events_url", "base_chapter_version"}


def validate_receipt(value):
    """Return the admission phase, or reject without adopting/changing data."""
    if (not isinstance(value, dict) or type(value.get("schema_version")) is not int
            or not isinstance(value.get("project_incarnation"), str)
            or not _OWNER.fullmatch(value["project_incarnation"])):
        raise ValueError("IDEMPOTENCY_RECORD_UNVERIFIED")
    if value["schema_version"] == 2:
        result = value.get("result")
        # Preserve the complete v2 validation contract, including legacy IDs.
        if (set(value) != {"schema_version", "project_incarnation", "request_digest", "result"}
                or not isinstance(result, dict) or set(result) != _RESULT_KEYS
                or not isinstance(result.get("job_id"), str) or not result["job_id"]
                or not isinstance(result.get("status"), str)
                or result.get("events_url") != f"/api/generation/{result['job_id']}/events"
                or type(result.get("base_chapter_version")) is not int
                or result["base_chapter_version"] < 1):
            raise ValueError("IDEMPOTENCY_RECORD_UNVERIFIED")
        return "RECORDED"
    if (value["schema_version"] != 3 or set(value) != _RESERVED_KEYS
            or value["admission_state"] != "RESERVED"
            or not isinstance(value["request_digest"], str)
            or not re.fullmatch(r"[a-f0-9]{64}", value["request_digest"])
            or not isinstance(value["job_id"], str)):
        raise ValueError("IDEMPOTENCY_RECORD_UNVERIFIED")
    try:
        identity = UUID(value["job_id"])
        if identity.version != 4 or str(identity) != value["job_id"]:
            raise ValueError("noncanonical original Job ID")
    except ValueError as exc:
        raise ValueError("IDEMPOTENCY_RECORD_UNVERIFIED") from exc
    return "RESERVED"


def reservation(project_incarnation, request_digest, job_id):
    value = {"schema_version": 3, "admission_state": "RESERVED",
             "project_incarnation": project_incarnation,
             "request_digest": request_digest, "job_id": job_id}
    validate_receipt(value)
    return value
