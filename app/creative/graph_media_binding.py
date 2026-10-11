"""Closed server-only provenance for original Graph-bound modality jobs."""
from __future__ import annotations

import hashlib
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from ..experimental.store import canonical


class GraphMediaBinding(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    contract: Literal["creative-graph-media-binding/1"]
    run_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,239}$")
    node_id: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
    graph_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,239}$")
    graph_version: int = Field(ge=1, le=2**53 - 1)
    graph_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    run_request_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    input_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    preview_run_version: int = Field(ge=1, le=2**53 - 1)
    command_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    attempt_digest: str = Field(pattern=r"^[a-f0-9]{64}$")


def make_graph_binding_digest(value, context):
    """Bind the original run snapshot to its server actor/scope/incarnation."""
    return hashlib.sha256(canonical({"binding": {key: item for key, item in value.items() if key != "attempt_digest"},
        "owner": {key: context[key] for key in ("actor", "scope_key", "incarnation")}}).encode("utf-8")).hexdigest()


def validate_graph_binding(value, context):
    if value is None:
        return None
    result = GraphMediaBinding.model_validate(value).model_dump()
    if result["attempt_digest"] != make_graph_binding_digest(result, context):
        raise ValueError("CREATIVE_GRAPH_MEDIA_BINDING_INVALID")
    return result
