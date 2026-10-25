"""Strict passive identity for future ordinary keyed generation records.

This is repository data, not execution/review authority. No API accepts or stamps
it yet. Missing means legacy; presence (even null) must validate without fallback.
"""
from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, model_validator

FIELD = "ordinary_project_binding"
Identifier = Annotated[str, Field(min_length=1, max_length=240)]
SPECIALIZED_FIELDS = ("graph_binding", "adaptation_binding", "creative_director_binding",
                      "director_image_binding", "research_ocr_binding", "research_ocr_output_evidence",
                      "_creative_director_terminal_evidence", "director_image_terminal_v3")
IDENTITY_FIELDS = ("chapter_id", "operation", "actor_id", "workspace_id", "scope", "scope_type", "scope_id", "experimental_origin")


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class OrdinaryScope(_Strict):
    kind: Literal["WORKSPACE", "PROJECT", "STORYLINE", "BRANCH"]
    workspace_id: Identifier
    project_id: Identifier | None
    storyline_id: Identifier | None
    branch_id: Identifier | None

    @model_validator(mode="after")
    def _shape(self):
        from ..authorization import AuthorizationScope, ScopeKind
        AuthorizationScope(ScopeKind(self.kind), self.workspace_id, self.project_id,
                           self.storyline_id, self.branch_id)
        return self


class OrdinaryProjectBinding(_Strict):
    schema_version: Literal[1]
    project_incarnation: Identifier
    job_id: Identifier
    project_id: Identifier
    chapter_id: Identifier | None
    operation: Literal["continue", "rewrite", "polish", "brainstorm", "review"]
    experimental_origin: Literal["branch_manuscript"] | None
    actor_id: Identifier | None
    workspace_id: Identifier | None
    scope: OrdinaryScope | None
    scope_type: Literal["WORKSPACE", "PROJECT", "STORYLINE", "BRANCH"] | None
    scope_id: Identifier | None

    @model_validator(mode="after")
    def _identity(self):
        backend, value = self.project_incarnation.split(":", 1)
        identity = UUID(value)
        if (backend not in {"file", "postgres"} or str(identity) != value
                or (backend == "file" and identity.version != 4)
                or str(UUID(self.job_id)) != self.job_id):
            raise ValueError("invalid canonical identity")
        if (self.experimental_origin == "branch_manuscript") != (self.scope is not None and self.scope.kind == "BRANCH"):
            raise ValueError("different ordinary branch origin")
        if self.scope is None:
            if any(value is not None for value in (self.actor_id, self.workspace_id, self.scope_type, self.scope_id)):
                raise ValueError("unexpected local authority identity")
        else:
            scope = self.scope
            if (self.actor_id is None or self.workspace_id != scope.workspace_id
                    or (scope.project_id is not None and scope.project_id != self.project_id)
                    or self.scope_type != scope.kind
                    or self.scope_id != {"WORKSPACE": scope.workspace_id, "PROJECT": scope.project_id,
                                         "STORYLINE": scope.storyline_id, "BRANCH": scope.branch_id}[scope.kind]):
                raise ValueError("different scope identity")
        return self


def ordinary_job_binding(item):
    """Validate exact durable shape, including required explicit nullable fields."""
    value = item[FIELD]
    if not isinstance(value, dict) or type(value.get("schema_version")) is not int:
        raise ValueError("invalid ordinary binding schema")
    binding = OrdinaryProjectBinding.model_validate(value).model_dump()
    if (any(key in item for key in SPECIALIZED_FIELDS)
            or item.get("id") != binding["job_id"] or item.get("novel_id") != binding["project_id"]
            or any(key not in item or item[key] != binding[key] for key in IDENTITY_FIELDS)):
        raise ValueError("different ordinary job identity")
    return binding
