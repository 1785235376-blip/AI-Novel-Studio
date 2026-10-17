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


def validate_creative_director_source(documents, binding, *, actor_id, scope):
    """Validate a real current saved source using its original owners and locks.

    Hold scope before project. Missing-source exceptions roll back the original
    PostgreSQL scope transaction, including its possible INSERT ON CONFLICT.
    An existing File marker is checked before any Creative owner can provision it.
    The detached return is evidence only, with no authority beyond this read.
    """
    from ..experimental.store import canonical
    from ..file_project_lifecycle import project_operation
    from .project_store import BINDING, _read_marker

    binding = CreativeDirectorBinding.model_validate(binding)
    nid, wanted_scope = binding.project_id, binding.scope.model_dump()
    if actor_id != binding.actor_id or scope != wanted_scope:
        raise ValueError("CREATIVE_DIRECTOR_SOURCE_AUTHORITY_MISMATCH")
    store = documents.store
    if nid in getattr(store._local, "owners", {}):
        raise ValueError("CREATIVE_DIRECTOR_SOURCE_LOCK_ORDER_INVALID")
    with store.store.transaction(nid, wanted_scope) as raw:
        before = canonical(raw)
        try:
            row = raw["collections"].get(documents.COLLECTION, {}).get(binding.source_document_id)
            # Eligibility precedes original source validation, so an unsupported
            # chapter/ancestry source cannot trigger an implicit owner read.
            if (not isinstance(row, dict) or row.get("mode") != "STORYBOARD"
                    or row.get("source_independent") is not True
                    or row.get("source_chapter_ids") != []
                    or row.get("source_evidence") != {} or row.get("source_documents") != {}
                    or row.get("source_privacy") != {}):
                raise ValueError("CREATIVE_DIRECTOR_INDEPENDENT_STORYBOARD_REQUIRED")
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
                source = documents.get(nid, wanted_scope, binding.source_document_id)
                if (source.get("id") != binding.source_document_id
                        or source.get("project_incarnation") != binding.project_incarnation
                        or type(source.get("version")) is not int or source["version"] != binding.source_version
                        or documents.document_digest(source) != binding.source_digest):
                    raise ValueError("CREATIVE_DIRECTOR_SOURCE_CHANGED")
                return deepcopy(source)
        finally:
            if canonical(raw) != before:
                raise ValueError("CREATIVE_DIRECTOR_SOURCE_MUTATION_DENIED")
