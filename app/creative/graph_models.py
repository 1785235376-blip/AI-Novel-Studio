"""Finite M2-A graph contracts. Definitions describe trusted code, never load it."""
from __future__ import annotations

from copy import deepcopy
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ..experimental.store import canonical
from ..services.v1_capability_service import V1CapabilityService, WorkflowRunIn

MAX_NODES = 16
MAX_EDGES = 40
MAX_DEFINITION_BYTES = 96_000
MAX_OUTPUT_BYTES = 64_000
MAX_GRAPHS = 25
MAX_RUNS = 100
MAX_HISTORY = 20
MAX_RECORD_BYTES = 2_000_000
MAX_SCOPE_BYTES = 8_000_000
# Reuse the original owner's default, never a caller-provided timeout override.
RUN_TIMEOUT_SECONDS = WorkflowRunIn.model_fields["timeout_seconds"].default
NODE_TIMEOUT_SECONDS = 5
Id = Annotated[str, Field(pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,63}$", strict=True)]
RequestId = Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$", strict=True)]
Digest = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$", strict=True)]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class Position(Strict):
    x: float = Field(default=0.0, ge=-100_000, le=100_000)
    y: float = Field(default=0.0, ge=-100_000, le=100_000)


class Viewport(Position):
    zoom: float = Field(default=1.0, ge=0.35, le=2.5)


class TextParameters(Strict):
    text: str = Field(default="", max_length=8_000)


class EmptyParameters(Strict):
    pass


class ManualParameters(Strict):
    result: str = Field(default="", max_length=8_000)


class DirectorParameters(Strict):
    note: str = Field(default="", max_length=4_000)


class ModelTextParameters(Strict):
    instruction: str = Field(default="", max_length=4_000)
    max_output_tokens: int = Field(default=512, ge=1, le=2048)


class ModelDraftPort(Strict):
    text: str = Field(min_length=1, max_length=8_000)
    origin: Literal["MODEL_PROPOSAL"]
    direction: DirectorParameters | None = None


class AssetParameters(Strict):
    asset_id: str = Field(min_length=1, max_length=240)
    version: int = Field(ge=1)
    digest: Digest
    kind: Literal["image", "video", "audio"]


class PlanItem(Strict):
    sequence: int = Field(ge=1, le=100)
    beat: str = Field(min_length=1, max_length=8_000)


class DraftPort(Strict):
    text: str = Field(min_length=1, max_length=8_000)
    origin: Literal["USER_SUPPLIED", "MANUAL"]
    plan: list[PlanItem] | None = Field(default=None, max_length=100)
    direction: DirectorParameters | None = None


def port(name, kind, required=False):
    return {"id": name, "type": kind, "required": required, "multiple": False}


DEFINITIONS = {
    "text_input": {"inputs": [], "outputs": [port("text", "TEXT")], "parameters": TextParameters},
    "text_reference": {"inputs": [port("text", "TEXT", True)], "outputs": [port("text", "TEXT")], "parameters": EmptyParameters},
    "draft_prepare": {"inputs": [port("text", "TEXT", True), port("direction", "DIRECTOR_NOTES")], "outputs": [port("draft", "DRAFT")], "parameters": EmptyParameters},
    "manual_transform": {"inputs": [port("text", "TEXT", True), port("direction", "DIRECTOR_NOTES")], "outputs": [port("draft", "DRAFT")], "parameters": ManualParameters},
    "director_note": {"inputs": [], "outputs": [port("direction", "DIRECTOR_NOTES")], "parameters": DirectorParameters},
    "human_review": {"inputs": [port("draft", "DRAFT", True)], "outputs": [], "parameters": EmptyParameters},
    "asset_reference": {"inputs": [], "outputs": [port("asset", "ASSET_REF")], "parameters": AssetParameters},
}
# Additive versioned model execution; the default seven-item catalog stays frozen.
DEFINITIONS["text_generate"] = {"inputs": [port("text", "TEXT", True), port("direction", "DIRECTOR_NOTES")],
    "outputs": [port("draft", "DRAFT")], "parameters": ModelTextParameters}

DefinitionId = Literal["text_input", "text_reference", "draft_prepare", "manual_transform", "director_note", "human_review", "asset_reference"]


class NodeInstance(Strict):
    id: Id
    definition_id: DefinitionId
    definition_version: Literal[1] = 1
    enabled: bool = True
    position: Position = Field(default_factory=Position)
    parameters: dict = Field(default_factory=dict)

    @field_validator("definition_version", mode="before")
    @classmethod
    def exact_version(cls, value):
        if type(value) is not int:
            raise ValueError("CREATIVE_GRAPH_DEFINITION_VERSION_INVALID")
        return value

    @model_validator(mode="after")
    def parameters_for_definition(self):
        if type(self.definition_version) is not int:
            raise ValueError("CREATIVE_GRAPH_DEFINITION_VERSION_INVALID")
        self.parameters = DEFINITIONS[self.definition_id]["parameters"].model_validate(self.parameters).model_dump()
        return self


class ModelNodeInstance(NodeInstance):
    definition_id: Literal["text_input", "text_reference", "draft_prepare", "manual_transform",
        "director_note", "human_review", "asset_reference", "text_generate"]


class TypedEdge(Strict):
    id: Id
    source_node_id: Id
    source_port: Id
    target_node_id: Id
    target_port: Id


class GraphInput(Strict):
    schema_version: Literal[1] = 1
    title: str = Field(min_length=1, max_length=160)
    nodes: list[NodeInstance] = Field(default_factory=list, max_length=MAX_NODES)
    edges: list[TypedEdge] = Field(default_factory=list, max_length=MAX_EDGES)
    viewport: Viewport = Field(default_factory=Viewport)

    @field_validator("schema_version", mode="before")
    @classmethod
    def exact_schema(cls, value):
        if type(value) is not int:
            raise ValueError("CREATIVE_GRAPH_SCHEMA_VERSION_INVALID")
        return value

    @model_validator(mode="after")
    def validate_graph(self):
        if type(self.schema_version) is not int or not self.title.strip():
            raise ValueError("CREATIVE_GRAPH_TITLE_OR_SCHEMA_INVALID")
        nodes = {node.id: node for node in self.nodes}
        if len(nodes) != len(self.nodes) or len({edge.id for edge in self.edges}) != len(self.edges):
            raise ValueError("CREATIVE_GRAPH_DUPLICATE_ID")
        seen, targets = set(), set()
        for edge in self.edges:
            if edge.source_node_id not in nodes or edge.target_node_id not in nodes:
                raise ValueError("CREATIVE_GRAPH_UNKNOWN_NODE")
            source, target = nodes[edge.source_node_id], nodes[edge.target_node_id]
            out = next((p for p in DEFINITIONS[source.definition_id]["outputs"] if p["id"] == edge.source_port), None)
            inp = next((p for p in DEFINITIONS[target.definition_id]["inputs"] if p["id"] == edge.target_port), None)
            if not out or not inp:
                raise ValueError("CREATIVE_GRAPH_UNKNOWN_PORT")
            if out["type"] != inp["type"]:
                raise ValueError("CREATIVE_GRAPH_PORT_TYPE_MISMATCH")
            key = (edge.source_node_id, edge.source_port, edge.target_node_id, edge.target_port)
            target_key = (edge.target_node_id, edge.target_port)
            if key in seen:
                raise ValueError("CREATIVE_GRAPH_DUPLICATE_EDGE")
            if target_key in targets:
                raise ValueError("CREATIVE_GRAPH_PORT_CARDINALITY")
            seen.add(key); targets.add(target_key)
        V1CapabilityService._workflow_order([{"id": node.id} for node in self.nodes],
            [{"source": edge.source_node_id, "target": edge.target_node_id} for edge in self.edges])
        if len(canonical(self.model_dump()).encode()) > MAX_DEFINITION_BYTES:
            raise ValueError("CREATIVE_GRAPH_DEFINITION_CAPACITY")
        return self


class GraphModelInput(GraphInput):
    # Explicit new schema: the original seven-definition GraphInput is frozen.
    schema_version: Literal[2]
    nodes: list[ModelNodeInstance] = Field(default_factory=list, max_length=MAX_NODES)


def parse_graph(value):
    schema = value.get("schema_version", 1) if isinstance(value, dict) else value.schema_version
    return (GraphModelInput if schema == 2 else GraphInput).model_validate(value)


class GraphCreate(Strict):
    request_id: RequestId
    expected_version: Literal[0] = 0
    definition: GraphInput | GraphModelInput

    @field_validator("expected_version", mode="before")
    @classmethod
    def exact_zero(cls, value):
        if type(value) is not int:
            raise ValueError("CREATIVE_GRAPH_EXPECTED_VERSION_INVALID")
        return value

    @model_validator(mode="after")
    def strict_zero(self):
        if type(self.expected_version) is not int:
            raise ValueError("CREATIVE_GRAPH_EXPECTED_VERSION_INVALID")
        return self


class GraphSave(Strict):
    expected_version: int = Field(ge=1)
    definition: GraphInput | GraphModelInput


class GraphPreflight(Strict):
    expected_version: int = Field(ge=1)
    target_node_ids: list[Id] = Field(default_factory=list, max_length=MAX_NODES)


class GraphRunCreate(Strict):
    expected_graph_version: int = Field(ge=1)
    reviewed_preflight_digest: Digest
    target_node_ids: list[Id] = Field(default_factory=list, max_length=MAX_NODES)
    request_id: RequestId


class GraphAction(Strict):
    expected_version: int = Field(ge=1)
    node_id: Id | None = None
    reviewed_output_digest: Digest | None = None
    note: str = Field(default="", max_length=1_000)


def catalog_definitions(*, include_model=False):
    return [{"id": key, "version": 1, "inputs": deepcopy(value["inputs"]),
        "outputs": deepcopy(value["outputs"]), "parameters_schema": value["parameters"].model_json_schema(),
        "default_parameters": value["parameters"]().model_dump() if key != "asset_reference" else None,
        "executable": key != "asset_reference", "model_called": False,
        "blockers": ["CREATIVE_GRAPH_ATOMIC_INPUT_OWNER_ADAPTER_REQUIRED"] if key == "asset_reference" else []}
        for key, value in DEFINITIONS.items() if include_model or key != "text_generate"]


def validate_output_ports(definition_id, value):
    """Finite output types also apply to persisted/cached local receipts."""
    expected = DEFINITIONS[definition_id]["outputs"]
    if not isinstance(value, dict) or set(value) != {port["id"] for port in expected}:
        raise ValueError("CREATIVE_GRAPH_OUTPUT_SCHEMA_INVALID")
    result = {}
    for port in expected:
        item = value[port["id"]]
        if port["type"] == "TEXT":
            if not isinstance(item, str) or len(item) > 8_000:
                raise ValueError("CREATIVE_GRAPH_OUTPUT_SCHEMA_INVALID")
            result[port["id"]] = item
        elif port["type"] == "DIRECTOR_NOTES":
            result[port["id"]] = DirectorParameters.model_validate(item).model_dump()
        elif port["type"] == "DRAFT":
            draft = (ModelDraftPort if definition_id == "text_generate" else DraftPort).model_validate(item)
            if ((definition_id == "draft_prepare" and (draft.origin != "USER_SUPPLIED" or draft.plan is None))
                    or (definition_id == "manual_transform" and (draft.origin != "MANUAL" or draft.plan is not None))):
                raise ValueError("CREATIVE_GRAPH_OUTPUT_SCHEMA_INVALID")
            result[port["id"]] = draft.model_dump(exclude_none=True)
        else:
            raise ValueError("CREATIVE_GRAPH_ATOMIC_INPUT_OWNER_ADAPTER_REQUIRED")
    if len(canonical(result).encode()) > MAX_OUTPUT_BYTES:
        raise ValueError("CREATIVE_GRAPH_OUTPUT_LIMIT")
    return result
