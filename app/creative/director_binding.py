"""Passive independent-storyboard evidence, never execution or review authority.

There is deliberately no preparer, provider, coordinator, or dispatch here.
The preview digest records data; it is not consent or a reusable capability.
"""
from __future__ import annotations

from contextlib import ExitStack
from copy import deepcopy
import re
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

CREATIVE_DIRECTOR_OPERATION = "creative_director_text"
CREATIVE_DIRECTOR_ORIGIN = "creative_director_source_model"
Identifier = Annotated[str, Field(min_length=1, max_length=240)]
Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class _Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class CreativeDirectorLocalScope(_Frozen):
    mode: Literal["local"]
    novel_id: Identifier


class CreativeDirectorCollaborationScope(_Frozen):
    mode: Literal["collaboration"]
    novel_id: Identifier
    workspace_id: Identifier
    storyline_id: Identifier
    branch_id: Identifier


class CreativeDirectorBinding(_Frozen):
    contract: Literal["CREATIVE_DIRECTOR_SOURCE_V1"]
    source_kind: Literal["STORYBOARD"]
    project_id: Identifier
    project_incarnation: Identifier
    actor_id: Identifier
    scope: Annotated[CreativeDirectorLocalScope | CreativeDirectorCollaborationScope,
                     Field(discriminator="mode")]
    source_document_id: Identifier
    source_version: int = Field(ge=1, le=2**53 - 1)
    source_digest: Digest
    reviewed_preview_digest: Digest

    @model_validator(mode="after")
    def _identity(self):
        try:
            backend, value = self.project_incarnation.split(":", 1)
            identity = UUID(value)
            if (backend not in {"file", "postgres"} or str(identity) != value
                    or (backend == "file" and identity.version != 4)
                    or self.scope.novel_id != self.project_id):
                raise ValueError("invalid identity")
        except (ValueError, AttributeError):
            raise ValueError("CREATIVE_DIRECTOR_BINDING_IDENTITY_INVALID") from None
        return self


def is_creative_director_job(value):
    """Every discriminator independently fences even incomplete/mixed records."""
    get = value.get if isinstance(value, dict) else lambda key, default=None: getattr(value, key, default)
    return (("creative_director_binding" in value if isinstance(value, dict)
             else get("creative_director_binding") is not None)
            or get("operation") == CREATIVE_DIRECTOR_OPERATION
            or get("experimental_origin") == CREATIVE_DIRECTOR_ORIGIN)


def creative_director_job_binding(item, *, require_request_digest=True):
    """Validate passive identity and digest syntax, not payload equality/consent."""
    try:
        binding = CreativeDirectorBinding.model_validate(item.get("creative_director_binding"))
        if (item.get("operation") != CREATIVE_DIRECTOR_OPERATION
                or item.get("experimental_origin") != CREATIVE_DIRECTOR_ORIGIN
                or item.get("chapter_id") is not None
                or item.get("graph_binding") is not None or item.get("adaptation_binding") is not None
                or item.get("novel_id") != binding.project_id
                or item.get("actor_id") != binding.actor_id
                or item.get("scope") != binding.scope.model_dump()
                or item.get("profile") != "LOCAL_ONLY"
                or str(UUID(item["id"])) != item["id"]):
            raise ValueError("invalid job identity")
        if require_request_digest and (not isinstance(item.get("expected_request_digest"), str)
                or re.fullmatch(r"[0-9a-f]{64}", item["expected_request_digest"]) is None):
            raise ValueError("invalid passive request digest")
    except (ValueError, TypeError, KeyError, AttributeError):
        raise ValueError("GENERATION_CREATIVE_DIRECTOR_BINDING_INVALID") from None
    return binding.model_dump()


def _source_authority(documents, binding, actor_id, scope):
    binding = CreativeDirectorBinding.model_validate(binding)
    if actor_id != binding.actor_id or scope != binding.scope.model_dump():
        raise ValueError("CREATIVE_DIRECTOR_SOURCE_AUTHORITY_MISMATCH")
    return binding


from contextlib import contextmanager


@contextmanager
def _creative_director_owner_lease(documents, binding):
    """Original owner, scope first, with no missing-marker provisioning."""
    from ..file_project_lifecycle import project_operation
    from .project_store import BINDING, _read_marker
    binding = CreativeDirectorBinding.model_validate(binding)
    store, nid = documents.store, binding.project_id
    key = store.store.key(nid, binding.scope.model_dump())
    if key not in getattr(store.store._local, "active", {}):
        raise ValueError("CREATIVE_DIRECTOR_SOURCE_LOCK_ORDER_INVALID")
    with ExitStack() as owners:
        if store.backend == "file":
            owners.enter_context(project_operation(store.root, nid))
            try:
                marker = _read_marker(store.root / "novels" / nid / "creative_project_v2.json")
                if (not isinstance(marker, dict) or set(marker) != {"schema_version", BINDING}
                        or type(marker["schema_version"]) is not int or marker["schema_version"] != 1
                        or not isinstance(marker[BINDING], str)):
                    raise ValueError("invalid original marker")
                identity = UUID(marker[BINDING])
                if (identity.version != 4 or str(identity) != marker[BINDING]
                        or "file:" + str(identity) != binding.project_incarnation):
                    raise ValueError("different original owner")
            except (OSError, ValueError, TypeError, KeyError):
                raise ValueError("CREATIVE_DIRECTOR_SOURCE_OWNER_CHANGED") from None
        identity = owners.enter_context(store.owner_lease(nid))
        if identity != binding.project_incarnation:
            raise ValueError("CREATIVE_DIRECTOR_SOURCE_OWNER_CHANGED")
        yield identity


def _validate_creative_director_source_locked(documents, binding, *, actor_id, scope):
    """Read the actual original active scope and matching owner, never a supplied view.

    This internal seam composes with original broker transactions. Its mutation
    bracket covers only validation; surrounding admission/ledger writes belong
    to their original transaction owners and are not forbidden.
    """
    from ..experimental.store import canonical
    binding = _source_authority(documents, binding, actor_id, scope)
    store, nid = documents.store, binding.project_id
    key = store.store.key(nid, scope)
    active = getattr(store.store._local, "active", {})
    raw = active.get(key)
    if (not isinstance(raw, dict) or raw.get("novel_id") != nid or raw.get("scope") != scope
            or getattr(store._local, "owners", {}).get(nid) != binding.project_incarnation):
        raise ValueError("CREATIVE_DIRECTOR_SOURCE_LOCK_ORDER_INVALID")
    view = getattr(store._local, "active", {}).get(key)
    before, view_before = canonical(raw), canonical(view)
    try:
        row = raw["collections"].get(documents.COLLECTION, {}).get(binding.source_document_id)
        if (not isinstance(row, dict) or row.get("mode") != "STORYBOARD"
                or row.get("source_independent") is not True
                or row.get("source_chapter_ids") != [] or row.get("source_evidence") != {}
                or row.get("source_documents") != {} or row.get("source_privacy") != {}):
            raise ValueError("CREATIVE_DIRECTOR_INDEPENDENT_STORYBOARD_REQUIRED")
        if view is not None and (not isinstance(view, dict) or view.get("novel_id") != nid
                or view.get("scope") != scope
                or view.get("collections", {}).get(documents.COLLECTION, {}).get(binding.source_document_id) != row):
            raise ValueError("CREATIVE_DIRECTOR_SOURCE_CHANGED")
        source = documents.get(nid, scope, binding.source_document_id)
        if (source.get("id") != binding.source_document_id
                or source.get("project_incarnation") != binding.project_incarnation
                or type(source.get("version")) is not int or source["version"] != binding.source_version
                or documents.document_digest(source) != binding.source_digest):
            raise ValueError("CREATIVE_DIRECTOR_SOURCE_CHANGED")
        return deepcopy(source)
    finally:
        if (active.get(key) is not raw or getattr(store.store._local, "active", None) is not active
                or getattr(store._local, "active", {}).get(key) is not view
                or getattr(store._local, "owners", {}).get(nid) != binding.project_incarnation
                or canonical(raw) != before or canonical(view) != view_before):
            raise ValueError("CREATIVE_DIRECTOR_SOURCE_MUTATION_DENIED")


def validate_creative_director_source(documents, binding, *, actor_id, scope):
    """Passive standalone validation; nested transactions remain forbidden."""
    binding = _source_authority(documents, binding, actor_id, scope)
    store, nid = documents.store, binding.project_id
    if nid in getattr(store._local, "owners", {}):
        raise ValueError("CREATIVE_DIRECTOR_SOURCE_LOCK_ORDER_INVALID")
    with store.store.transaction(nid, scope):
        # Check unsupported sources before entering an owner that could read it.
        raw = store.store._local.active[store.store.key(nid, scope)]
        row = raw["collections"].get(documents.COLLECTION, {}).get(binding.source_document_id)
        if (not isinstance(row, dict) or row.get("mode") != "STORYBOARD"
                or row.get("source_independent") is not True or row.get("source_chapter_ids") != []
                or row.get("source_evidence") != {} or row.get("source_documents") != {}
                or row.get("source_privacy") != {}):
            raise ValueError("CREATIVE_DIRECTOR_INDEPENDENT_STORYBOARD_REQUIRED")
        with _creative_director_owner_lease(documents, binding):
            return _validate_creative_director_source_locked(documents, binding, actor_id=actor_id, scope=scope)


CREATIVE_DIRECTOR_INTERNAL_CONTRACT = "CREATIVE_DIRECTOR_INTERNAL_EXECUTION_V1"


def _has_internal_director_record(row):
    """Bounded structural scan of model fields/history, never authored prose.

    Old snapshots retain the marker even if a current model field is removed.
    Malformed/over-depth persisted history fails closed rather than truncating.
    """
    stack, seen = [(row, 0, False)], 0
    while stack:
        value, depth, model_field = stack.pop()
        seen += 1
        if seen > 20000 or depth > 32:
            return True
        if model_field:
            if isinstance(value, list):
                if len(value) > 20000: return True
                stack.extend((item, depth + 1, True) for item in value if isinstance(item, (dict, list)))
                continue
            if not isinstance(value, dict): return True
            contract = value.get("contract")
            if contract is not None and not isinstance(contract, str): return True
            if contract in (CREATIVE_DIRECTOR_INTERNAL_CONTRACT, "CREATIVE_DIRECTOR_SOURCE_V1"):
                return True
            stack.extend((item, depth + 1, True) for item in value.values() if isinstance(item, (dict, list)))
        else:
            if not isinstance(value, dict): return True
            for key in ("model_preview", "model_execution"):
                child = value.get(key)
                if child is not None:
                    if not isinstance(child, dict): return True
                    stack.append((child, depth + 1, True))
            history = value.get("history", [])
            if not isinstance(history, list) or len(history) > 100: return True
            stack.extend((item, depth + 1, False) for item in history)
    return False


def _deny_internal_director_record(row):
    if _has_internal_director_record(row):
        raise ValueError("CREATIVE_DIRECTOR_EXECUTION_UNAVAILABLE")
