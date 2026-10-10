"""Wire validation and deterministic hashing; trust inputs are local-only.

No function opens evidence locators, files, URLs, products, models or plugins.
Canonical hashing uses UTF-8, sorted JSON object keys, compact separators, UTC
RFC3339 timestamps, and no NaN/infinity. This is the V1 profile, not generic JCS.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Iterable, Literal, Mapping, TypeVar
from urllib.parse import urlsplit

from pydantic import BaseModel, ValidationError

from .models import (
    CAPABILITIES,
    PROTOCOL_NAME,
    PROTOCOL_VERSION,
    AppContextCapsule,
    Authority,
    ContextEvidence,
    DiagnosticCapsule,
    ErrorCode,
    InteropError,
    Privacy,
    WireModel,
)

MAX_MESSAGE_BYTES = 1024 * 1024
T = TypeVar("T", bound=WireModel)


class ProtocolViolation(ValueError):
    """Typed, bounded public failure. Never include the offending payload."""

    def __init__(self, code: ErrorCode, message: str, *, retryable: bool = False):
        self.code = code
        self.message = message
        self.retryable = retryable
        super().__init__(message)

    def as_error(self, request_id: str | None = None) -> InteropError:
        return InteropError(
            request_id=request_id, code=self.code, message=self.message, retryable=self.retryable
        )


def _json_default(value: object) -> object:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Timestamp must have an offset")
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    raise TypeError(f"Unsupported canonical JSON type: {type(value).__name__}")


def canonical_json(value: object) -> str:
    return json.dumps(
        value,
        default=_json_default,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def canonical_hash(value: object, *, exclude: Iterable[str] = ()) -> str:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    if exclude:
        if not isinstance(value, Mapping):
            raise TypeError("Hash exclusions require a JSON object")
        excluded = set(exclude)
        value = {key: item for key, item in value.items() if key not in excluded}
    return sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _duplicate_safe(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def parse_wire(model_type: type[T], payload: bytes | str | Mapping[str, Any]) -> T:
    """Validate untrusted input, including version, size and duplicate JSON keys.

    Mapping input is only a convenience at framework boundaries. Models retain
    frozen tuple arrays; JSON decoding does not coerce strings to numbers/bools.
    """
    try:
        raw = canonical_json(payload) if isinstance(payload, Mapping) else payload
        if not isinstance(raw, (str, bytes)):
            raise ValueError("Message must be a JSON object")
        if len(raw.encode("utf-8") if isinstance(raw, str) else raw) > MAX_MESSAGE_BYTES:
            raise ValueError("Message exceeds the V1 byte bound")
        decoded = json.loads(
            raw,
            object_pairs_hook=_duplicate_safe,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Non-finite JSON number")),
        )
        if not isinstance(decoded, dict):
            raise ValueError("Message must be a JSON object")
        if "protocol_name" in model_type.model_fields:
            if "protocol_name" not in decoded or "protocol_version" not in decoded:
                raise ValueError("Protocol identity fields are required on the wire")
            if (
                decoded["protocol_name"] != PROTOCOL_NAME
                or decoded["protocol_version"] != PROTOCOL_VERSION
            ):
                raise ProtocolViolation(
                    "PROTOCOL_INCOMPATIBLE", "No compatible Local Interop protocol version"
                )
        return model_type.model_validate_json(raw, context={"wire": True})
    except ProtocolViolation:
        raise
    except (ValidationError, ValueError, TypeError, UnicodeError, RecursionError) as error:
        raise ProtocolViolation(
            "INVALID_MESSAGE", "Malformed or invalid Local Interop message"
        ) from error


def _create_hashed(model_type: type[T], hash_field: str, fields: Mapping[str, Any]) -> T:
    values = dict(fields)
    values[hash_field] = "0" * 64
    # Only the trusted factory bypasses the first checksum comparison. All field,
    # consent, privacy and temporal invariants are still checked in this pass.
    hydrated = model_type.model_validate_json(
        canonical_json(values), context={"_allow_unsealed": True}
    )
    sealed = hydrated.model_dump(mode="json")
    sealed[hash_field] = canonical_hash(sealed, exclude=(hash_field,))
    return model_type.model_validate_json(canonical_json(sealed))


def create_capsule(**fields: Any) -> AppContextCapsule:
    return _create_hashed(AppContextCapsule, "capsule_hash", fields)


def create_diagnostic(**fields: Any) -> DiagnosticCapsule:
    return _create_hashed(DiagnosticCapsule, "content_hash", fields)


def validate_capsule(
    capsule: AppContextCapsule,
    *,
    now: datetime | None = None,
    source_version: str | None = None,
    project_version: str | None = None,
    chapter_version: int | None = None,
) -> None:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("Validation clock must have a timezone")
    if capsule.expires_at <= now or capsule.created_at > now:
        raise ProtocolViolation("CONTEXT_STALE", "Context is expired or not yet valid")
    if source_version is not None and capsule.source_version != source_version:
        raise ProtocolViolation("SOURCE_CHANGED", "Context source version changed")
    if project_version is not None and capsule.project_version != project_version:
        raise ProtocolViolation("SOURCE_CHANGED", "Project version changed")
    if chapter_version is not None and capsule.chapter_version != chapter_version:
        raise ProtocolViolation("SOURCE_CHANGED", "Chapter version changed")
    if canonical_hash(capsule, exclude=("capsule_hash",)) != capsule.capsule_hash:
        raise ProtocolViolation("SOURCE_CHANGED", "Context checksum does not match")


def strictest_privacy(*values: Privacy) -> Privacy:
    ranks = {"CONSENTED_CLOUD": 0, "REDACTION_REQUIRED": 1, "LOCAL_ONLY": 2}
    if not values:
        return "LOCAL_ONLY"
    if any(value not in ranks for value in values):
        raise ProtocolViolation("INVALID_MESSAGE", "Unknown privacy class")
    return max(values, key=ranks.__getitem__)


def validate_derived_privacy(derived: Privacy, sources: Iterable[Privacy]) -> None:
    if strictest_privacy(derived, *tuple(sources)) != derived:
        raise ProtocolViolation(
            "CONTEXT_NOT_AUTHORIZED", "Derived content cannot weaken source privacy"
        )


def require_capabilities(required: Iterable[str], available: Iterable[str]) -> None:
    required_set = set(required)
    if not required_set.issubset(CAPABILITIES) or not required_set.issubset(available):
        raise ProtocolViolation(
            "CAPABILITY_NOT_SUPPORTED", "A required capability is not supported"
        )


@dataclass(frozen=True, slots=True)
class TrustedSourceProvenance:
    """LOCAL-ONLY trust record obtained by a host from its own actual state.

    Never create this from request JSON, caller-supplied authority, an LLM result,
    or an evidence locator. Source_id/version/hash must bind the real observation.
    """

    source_id: str
    source_version: str
    content_hash: str
    authority: Authority
    privacy: Privacy
    origin: Literal["HOST_STATE", "USER_CONFIRMED", "LLM"]


def validate_evidence_authority(
    evidence: ContextEvidence, provenance: TrustedSourceProvenance
) -> None:
    if not isinstance(provenance, TrustedSourceProvenance):
        raise ProtocolViolation("PERMISSION_DENIED", "Trusted host source provenance is required")
    if (evidence.source_id, evidence.source_version, evidence.content_hash) != (
        provenance.source_id,
        provenance.source_version,
        provenance.content_hash,
    ):
        raise ProtocolViolation(
            "SOURCE_CHANGED", "Evidence does not match the trusted source snapshot"
        )
    if provenance.origin not in ("HOST_STATE", "USER_CONFIRMED", "LLM"):
        raise ProtocolViolation("PERMISSION_DENIED", "Unrecognized evidence provenance")
    if provenance.origin == "LLM" and (
        evidence.authority != "ADVISORY" or provenance.authority != "ADVISORY"
    ):
        raise ProtocolViolation("PERMISSION_DENIED", "Model text cannot claim elevated authority")
    if evidence.authority != provenance.authority:
        raise ProtocolViolation(
            "PERMISSION_DENIED", "Evidence authority does not match trusted provenance"
        )
    validate_derived_privacy(evidence.privacy, (provenance.privacy,))


def assert_local_endpoint(url: str) -> None:
    """Only a literal 127.0.0.1 HTTP origin is allowed; never resolve DNS."""
    try:
        if not isinstance(url, str) or any(ord(char) < 33 or ord(char) > 126 for char in url):
            raise ValueError("Origin must contain only printable ASCII without whitespace")
        parts = urlsplit(url)
        invalid = (
            parts.scheme != "http"
            or parts.hostname != "127.0.0.1"
            or parts.username is not None
            or parts.password is not None
            or parts.query
            or parts.fragment
            or parts.path not in ("", "/")
            or parts.port is None
            or not 1 <= parts.port <= 65535
            or parts.netloc != f"127.0.0.1:{parts.port}"
        )
    except (TypeError, ValueError):
        invalid = True
    if invalid:
        raise ProtocolViolation(
            "TRANSPORT_ERROR",
            "Only an explicit 127.0.0.1 HTTP origin without URL credentials is allowed",
        )
