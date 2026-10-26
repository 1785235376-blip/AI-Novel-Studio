"""Opt-in query contract for TaskCenter's existing safe bounded projection.

This module is not a task, project, permission, or lifecycle owner. It does not
read task stores, persist query state, or execute an action. The caller must
authorize before parsing and retain the original per-reader scope fences.

The authority catalogue documents the baseline's composition, not visibility.
Runtime acceptance is additionally checked against the actual reader registry
by the service. Cursor support is limited to an explicitly injected File/local semantic-import
adapter with original committed lifecycle evidence. Other modes fail closed.
"""
from __future__ import annotations

from dataclasses import dataclass
from fastapi import HTTPException


AUTHORITIES = (
    "author_generation", "workflows", "semantic_import", "media", "agent_team",
    "audiobook", "voice_direction", "agents", "exports", "images",
    "review_inbox", "audio_tts", "motion", "subtitle_processing", "adaptation",
    "research_analysis", "visual_identity",
)
MAX_AUTHORITY_VALUES = 64
MAX_CURSOR_LENGTH = 512
_INVALID = "TASKCENTER_QUERY_INVALID"


def normalize_authorities(value):
    """Validate direct service arguments; resolve names against its registry.

    None preserves the original all-reader behavior. Only a nonempty list or
    tuple of exact names in the fixed baseline catalogue is accepted. Duplicate selections
    are harmless and canonicalized; their order never changes registry order.
    A selected name must also exist in the real registry; the service performs
    that additional check. New reader authorities require a catalogue update.
    """
    if value is None:
        return None
    if type(value) not in (list, tuple) or not 1 <= len(value) <= MAX_AUTHORITY_VALUES:
        raise ValueError(_INVALID)
    if any(type(item) is not str or item not in AUTHORITIES for item in value):
        raise ValueError(_INVALID)
    return tuple(sorted(set(value)))


def _values(params, name):
    getter = getattr(params, "getlist", None)
    if callable(getter):
        return getter(name)
    value = params[name]
    return list(value) if type(value) in (list, tuple) else [value]


def _last(params, name):
    values = _values(params, name)
    if not values:
        raise ValueError(_INVALID)
    return values[-1]


@dataclass(frozen=True)
class TaskCenterQuery:
    """New parameters only; legacy limit/offset remain TaskPageQuery's owner."""

    authorities: tuple[str, ...] | None = None
    page_mode: str | None = None
    cursor: str | None = None

    def __post_init__(self):
        object.__setattr__(self, "authorities", normalize_authorities(self.authorities))
        if self.page_mode is not None and (
            type(self.page_mode) is not str or self.page_mode not in ("offset", "cursor")
        ):
            raise ValueError(_INVALID)
        if self.cursor is not None and (
            self.page_mode != "cursor" or type(self.cursor) is not str
            or not 1 <= len(self.cursor) <= MAX_CURSOR_LENGTH
        ):
            raise ValueError(_INVALID)

    @property
    def opt_in(self):
        """Only the new selector or explicit mode opts into new metadata."""
        return self.authorities is not None or self.page_mode is not None

    @classmethod
    def from_query_params(cls, params):
        """Parse after original access checks, with fixed non-echoing errors.

        authority is repeated form/explode OR, not a comma-separated string.
        Other new scalar parameters follow the original last-value convention.
        An isolated cursor remains an ignored unknown parameter, preserving
        the pre-existing route contract. Cursor mode rejects offset even at 0.
        """
        authorities = normalize_authorities(_values(params, "authority")) if "authority" in params else None
        page_mode = _last(params, "page_mode") if "page_mode" in params else None
        cursor = None
        if page_mode == "cursor":
            if "offset" in params:
                raise ValueError(_INVALID)
            if "cursor" in params:
                cursor = _last(params, "cursor")
        return cls(authorities=authorities, page_mode=page_mode, cursor=cursor)

    @classmethod
    def openapi_parameters(cls):
        """Static support catalogue; never a request's denied-reader report."""
        return [
            {
                "name": "authority", "in": "query", "required": False,
                "style": "form", "explode": True,
                "schema": {
                    "type": "array", "minItems": 1, "maxItems": MAX_AUTHORITY_VALUES,
                    "items": {"type": "string", "enum": list(AUTHORITIES)},
                },
                "description": (
                    "Exact reader authority names, repeated for OR. Duplicate values are deduplicated. "
                    "Case-sensitive; empty, unknown, whitespace-padded and comma-separated values are invalid. "
                    "The static catalogue is not a report of authorized or available readers. "
                    "The service also requires the selected authority in its actual reader registry."
                ),
            },
            {
                "name": "page_mode", "in": "query", "required": False,
                "schema": {"type": "string", "enum": ["offset", "cursor"]},
                "description": (
                    "Explicit opt-in query mode; repeated values use the last value. "
                    "Omitted preserves legacy behavior. offset preserves existing bounded response paging. "
                    "cursor supports two exclusive non-packaged File modes: explicit local semantic_import or exports "
                    "without session/branch headers, or collaboration source-free agent_team with original "
                    "session, membership, topology and grant evidence. Existing project/source lifecycle "
                    "evidence is required. Only the local semantic_import+exports pair supports mixed selection (200+100 original windows). Other mixed sources and modes return TASKCENTER_CURSOR_UNSUPPORTED; "
                    "it cannot be mixed with an explicit offset, including offset=0."
                ),
            },
            {
                "name": "cursor", "in": "query", "required": False,
                "schema": {"type": "string", "minLength": 1, "maxLength": MAX_CURSOR_LENGTH},
                "description": (
                    "Only recognized when page_mode=cursor; otherwise ignored for legacy compatibility. "
                    "Repeated values use the last value. Tokens expire, may be evicted and are process-local; "
                    "a changed observation requires a restart, not an automatic retry or offset fallback. "
                    "Empty or oversized values in cursor mode return the fixed query validation error."
                ),
            },
        ]


def static_capabilities():
    """Implementation support only; never task visibility, counts, or costs."""
    return {
        "authority_filter": {"supported": True, "operator": "OR"},
        "cursor": {
            "supported": True,
            "mode": "FILE_TWO_EXCLUSIVE_MODES",
            "conditions": ["ACTUAL_FILE_OWNERS", "NON_PACKAGED",
                           "LOCAL_SEMANTIC_IMPORT_OR_EXPORTS_OR_COLLABORATION_SOURCE_FREE_AGENT_TEAM",
                           "EXISTING_PROJECT_SOURCE_AND_AUTHORITY_LIFECYCLES", "ONLY_LOCAL_SEMANTIC_IMPORT_EXPORTS_MIXED_PAIR"],
        },
        "cross_owner_atomic_snapshot": False,
        "full_history_query": False,
        "cost": "UNKNOWN",
    }


def add_query_metadata(result, query):
    """Preserve old envelopes, including old offset mode, unless opted in.

    The service retains ownership of observed_total, safe items, pagination and
    source_truncated. An empty/final page or an unavailable-free projection is
    never evidence of complete history or the absence of hidden tasks.
    """
    if not query.opt_in:
        return result
    extended = {**result, "capabilities": static_capabilities()}
    extended.setdefault("coverage", {
        "scope": "BOUNDED_AUTHORIZED_PROJECTION",
        "completeness": "NOT_ASSERTED",
    })
    return extended


def cursor_not_supported():
    """Fail closed without issuing tokens or echoing private input."""
    raise HTTPException(
        501,
        {"code": "TASKCENTER_CURSOR_UNSUPPORTED", "message": "TASKCENTER_CURSOR_UNSUPPORTED"},
    )


def openapi_responses():
    """Static narrow support and fixed errors, never per-request visibility."""
    coverage = {"scope": "BOUNDED_AUTHORIZED_PROJECTION", "completeness": "NOT_ASSERTED"}
    legacy = {"items": [], "unavailable": [], "truncated": False,
              "executor": False, "refresh": "MANUAL", "automatic_retries": False}
    selected = {**legacy, "observed_total": 0, "source_truncated": False,
                "coverage": coverage, "capabilities": static_capabilities()}
    offset = {**selected, "limit": 50, "offset": 0, "has_more": False, "next_offset": None}
    cursor = {**selected, "page_mode": "cursor", "limit": 50,
              "has_more": False, "next_cursor": None}
    unsupported = {"code": "TASKCENTER_CURSOR_UNSUPPORTED",
                   "message": "TASKCENTER_CURSOR_UNSUPPORTED"}
    return {
        200: {
            "description": (
                "Legacy envelopes remain unchanged without authority/page_mode. "
                "authority alone retains the 500-item cap and adds bounded observed_total. "
                "page_mode=offset activates existing 50/0 defaults; limit stays at most 100. "
                "cursor requires the documented File exclusive local semantic_import/exports or collaboration source-free agent_team conditions and emits "
                "next_cursor/has_more without offset fallback. An empty or final page never "
                "establishes complete history."
            ),
            "content": {"application/json": {"examples": {
                "legacy": {"value": legacy},
                "authority_only_empty": {"value": selected},
                "explicit_offset_empty": {"value": offset},
                "supported_cursor_empty": {"value": cursor},
            }}},
        },
        409: {
            "description": "TASKCENTER_CURSOR_RESTART_REQUIRED. Observation changed, expired, was evicted or belongs to another binding/process.",
            "content": {"application/json": {"example": {"detail": {
                "code": "TASKCENTER_CURSOR_RESTART_REQUIRED", "message": "TASKCENTER_CURSOR_RESTART_REQUIRED"}}}},
        },
        422: {
            "description": "Fixed non-echoing invalid opt-in query or token shape.",
            "content": {"application/json": {"example": {"detail": {
                "code": "EXPERIMENTAL_INVALID", "message": "TASKCENTER_QUERY_INVALID"}}}},
        },
        501: {
            "description": (
                "TASKCENTER_CURSOR_UNSUPPORTED after original authorization. "
                "The request does not satisfy the narrow File exclusive local semantic_import/exports or collaboration source-free agent_team conditions, "
                "or an initial observation lacks reliable existing original lifecycle binding."
            ),
            "content": {"application/json": {"example": {"detail": unsupported}}},
        },
    }
