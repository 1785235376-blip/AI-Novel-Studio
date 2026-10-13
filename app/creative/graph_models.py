"""Finite M2-A graph contracts. Definitions describe trusted code, never load it."""
from __future__ import annotations

import re

from copy import deepcopy
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ..experimental.store import canonical
from ..services.v1_capability_service import V1CapabilityService, WorkflowRunIn
from .production_contracts import Name
from .production_execution_models import GraphMediaOperation, MediaParameters

MAX_NODES = 16
MAX_MEDIA_NODES = 24
MAX_MEDIA_GENERATORS = 4
MAX_MEDIA_HISTORY = 80
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


class MediaNodeParameters(Strict):
    """Configuration only; the runtime constructs the original MediaCommand."""
    operation_id: GraphMediaOperation
    provider_id: Name | None = None
    model_id: Name | None = None
    prompt: str = Field(default="", max_length=16000)
    parameters: MediaParameters = Field(default_factory=MediaParameters)
    allow_cloud: bool = False
    license_note: str = Field(default="", max_length=2000)

    @model_validator(mode="after")
    def closed_operation(self):
        parameters = self.parameters.model_dump(exclude_none=True)
        allowed = {
            "m5.image.t2i": {"width", "height", "steps", "seed", "negative_prompt", "size", "quality"},
            "m5.image.i2i": {"width", "height", "steps", "seed", "negative_prompt", "size", "quality"},
            "m7.video.t2v": {"width", "height", "seed", "negative_prompt", "duration_seconds", "frame_rate"},
            "m7.video.i2v": {"width", "height", "seed", "negative_prompt", "duration_seconds", "frame_rate"},
            "m7.video.v2v": {"width", "height", "seed", "negative_prompt", "duration_seconds", "frame_rate"},
            "m8.audio.speech": {"voice_id", "speech_rate"},
            "m8.audio.music": {"duration_seconds", "seed"},
            "m8.audio.effects": {"duration_seconds", "seed"},
            "m8.audio.trim": {"in_ms", "out_ms"},
        }[self.operation_id]
        if set(parameters) - allowed:
            raise ValueError("STUDIO_OPERATION_PARAMETER_UNSUPPORTED")
        if (self.parameters.width is None) != (self.parameters.height is None):
            raise ValueError("STUDIO_OPERATION_DIMENSIONS_PAIR_REQUIRED")
        if self.operation_id.startswith("m5.") and any(parameters.get(key, 64) % 8 for key in ("width", "height")):
            raise ValueError("STUDIO_IMAGE_DIMENSIONS_INVALID")
        if self.operation_id == "m8.audio.trim":
            if self.provider_id is not None or self.model_id is not None or self.allow_cloud or self.prompt:
                raise ValueError("STUDIO_AUDIO_TRIM_LOCAL_ONLY")
            start, end = self.parameters.in_ms, self.parameters.out_ms
            if start is None or end is None or not 0 < end - start <= 120000:
                raise ValueError("STUDIO_AUDIO_TRIM_INPUT_REQUIRED")
        elif not self.provider_id or not self.model_id or self.provider_id == "auto":
            raise ValueError("STUDIO_EXPLICIT_PROVIDER_MODEL_PROMPT_REQUIRED")
        return self


class MediaCandidatePort(Strict):
    owner: Literal["image", "video", "audio", "timeline"]
    job_id: str = Field(min_length=1, max_length=240)
    job_version: int = Field(ge=1)
    request_digest: Digest
    asset: AssetParameters

    @model_validator(mode="after")
    def original_output_kind(self):
        if self.asset.kind != ("video" if self.owner == "timeline" else self.owner):
            raise ValueError("CREATIVE_GRAPH_MEDIA_CANDIDATE_KIND_INVALID")
        return self


class TimelineSnapshotParameters(Strict):
    id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,239}$")
    version: int = Field(ge=1, le=2**53 - 1)
    digest: Digest


class TimelineSourceBinding(Strict):
    port: Literal["source_1", "source_2", "source_3", "source_4", "source_5", "source_6", "source_7", "source_8"]
    clip_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,239}$")


def _closed_timeline_operations(operations):
    """Bound edit syntax before the original owner validates its real base.

    This grants no edit/render authority. Contextual track/clip membership,
    ranges, overlap, source compatibility and final timeline normalization
    still belong to apply_timeline_edits on the exact owned snapshot.
    """
    fields = {
        "canvas.update": {"op", "changes"}, "track.insert": {"op", "track"},
        "track.remove": {"op", "track_id", "remove_clips"}, "track.update": {"op", "track_id", "changes"},
        "track.reorder": {"op", "track_ids"}, "clip.insert": {"op", "track_id", "clip"},
        "clip.update": {"op", "clip_id", "changes"}, "clip.remove": {"op", "clip_id", "ripple"},
        "clip.move": {"op", "clip_id", "track_id", "start_ms"},
        "clip.duplicate": {"op", "clip_id", "new_clip_id", "track_id", "start_ms"},
        "clip.split": {"op", "clip_id", "at_ms", "new_clip_id"},
        "clip.trim": {"op", "clip_id", "in_ms", "out_ms", "ripple"},
        "clip.slip": {"op", "clip_id", "offset_ms"}, "caption.insert": {"op", "caption"},
        "caption.update": {"op", "index", "caption"}, "caption.remove": {"op", "index"},
    }
    clip_fields = {"source_snapshot", "start_ms", "in_ms", "out_ms", "x", "y", "width", "height",
        "speed_num", "speed_den", "opacity", "gain_db", "muted", "include_audio", "fade_in_ms", "fade_out_ms", "crop", "transition_out"}
    for operation in operations:
        kind = operation.get("op")
        if not isinstance(kind, str) or kind not in fields or set(operation) != fields[kind]:
            raise ValueError("STUDIO_TIMELINE_EDIT_FIELDS_INVALID")
        nested = None
        if kind.endswith(".update") and kind != "caption.update":
            nested = operation["changes"]
            allowed = {"duration_ms", "width", "height", "fps", "schema_version"} if kind == "canvas.update" else (
                {"muted", "gain_db", "role", "locked"} if kind == "track.update" else clip_fields)
            if not isinstance(nested, dict) or not nested or set(nested) - allowed:
                raise ValueError("STUDIO_TIMELINE_EDIT_FIELDS_INVALID")
        elif kind == "track.insert":
            nested = operation["track"]
            required = {"id", "kind", "order", "clips"}
            if not isinstance(nested, dict) or required - set(nested) or set(nested) - required - {"muted", "gain_db", "role", "locked"}:
                raise ValueError("STUDIO_TIMELINE_EDIT_FIELDS_INVALID")
            if nested["clips"] != []:
                raise ValueError("STUDIO_TIMELINE_EDIT_INSERT_EMPTY_TRACK_REQUIRED")
        elif kind == "clip.insert":
            nested = operation["clip"]
            required = {"id", "source_snapshot", "start_ms", "in_ms", "out_ms"}
            if not isinstance(nested, dict) or required - set(nested) or set(nested) - clip_fields - {"id"}:
                raise ValueError("STUDIO_TIMELINE_EDIT_FIELDS_INVALID")
        elif kind in {"caption.insert", "caption.update"}:
            nested = operation["caption"]
            if not isinstance(nested, dict) or set(nested) != {"start_ms", "end_ms", "text"}:
                raise ValueError("STUDIO_TIMELINE_EDIT_FIELDS_INVALID")
        if isinstance(nested, dict) and "source_snapshot" in nested:
            snapshot = nested["source_snapshot"]
            if (not isinstance(snapshot, dict) or set(snapshot) != {"kind", "id", "version", "digest", "asset_kind"}
                    or snapshot["kind"] != "ASSET"):
                raise ValueError("STUDIO_TIMELINE_SOURCE_INVALID")
            AssetParameters.model_validate({"asset_id": snapshot["id"], "version": snapshot["version"],
                "digest": snapshot["digest"], "kind": snapshot["asset_kind"]})
        if isinstance(nested, dict) and "locked" in nested and type(nested["locked"]) is not bool:
            raise ValueError("STUDIO_TIMELINE_EDIT_BOOLEAN_INVALID")
        if isinstance(nested, dict) and "crop" in nested:
            crop = nested["crop"]
            if not (crop is None and kind == "clip.update") and (not isinstance(crop, dict) or set(crop) != {"x", "y", "width", "height"}
                    or any(type(crop[key]) is not int for key in crop)
                    or not 0 <= crop["x"] <= 32767 or not 0 <= crop["y"] <= 32767
                    or not 1 <= crop["width"] <= 32768 or not 1 <= crop["height"] <= 32768):
                raise ValueError("STUDIO_TIMELINE_CROP_INVALID")
        if isinstance(nested, dict) and "transition_out" in nested:
            transition = nested["transition_out"]
            if not (transition is None and kind == "clip.update") and (
                    not isinstance(transition, dict) or set(transition) != {"kind", "to_clip_id", "duration_ms"}
                    or transition["kind"] != "CROSS_DISSOLVE"
                    or not isinstance(transition["to_clip_id"], str)
                    or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,239}", transition["to_clip_id"])
                    or type(transition["duration_ms"]) is not int or not 1 <= transition["duration_ms"] <= 10_000):
                raise ValueError("STUDIO_TIMELINE_TRANSITION_INVALID")
    if len(canonical(operations).encode("utf-8")) > 128_000:
        raise ValueError("STUDIO_TIMELINE_EDIT_BYTES_LIMIT")


class TimelineNodeParameters(Strict):
    timeline_snapshot: TimelineSnapshotParameters
    edit_operations: list[dict] = Field(default_factory=list, max_length=40)
    source_bindings: list[TimelineSourceBinding] = Field(default_factory=list, max_length=8)
    export_profile: dict

    @model_validator(mode="after")
    def closed_original_configuration(self):
        from ..services.studio_timeline_export import normalize_export_profile
        self.export_profile = normalize_export_profile(self.export_profile)
        _closed_timeline_operations(self.edit_operations)
        if (len({binding.port for binding in self.source_bindings}) != len(self.source_bindings)
                or len({binding.clip_id for binding in self.source_bindings}) != len(self.source_bindings)):
            raise ValueError("CREATIVE_GRAPH_TIMELINE_SOURCE_BINDING_DUPLICATE")
        if len(self.edit_operations) + len(self.source_bindings) > 40:
            raise ValueError("STUDIO_TIMELINE_EDIT_OPERATION_LIMIT")
        return self


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
DEFINITIONS["media_generate"] = {"inputs": [port("text", "TEXT"), port("draft", "DRAFT"), port("source", "ASSET_REF")],
    "outputs": [port("candidate", "MEDIA_CANDIDATE")], "parameters": MediaNodeParameters}
DEFINITIONS["media_review"] = {"inputs": [port("candidate", "MEDIA_CANDIDATE", True)],
    "outputs": [port("asset", "ASSET_REF")], "parameters": EmptyParameters}
DEFINITIONS["timeline_export"] = {"inputs": [port(f"source_{index}", "ASSET_REF") for index in range(1, 9)],
    "outputs": [port("candidate", "MEDIA_CANDIDATE")], "parameters": TimelineNodeParameters}


def definition_for(definition_id, *, schema_version=None):
    """Only schema 3 exposes a completed original human review's draft.

    The frozen schema 1/2 catalog and their edge/output validators still use
    the original empty human-review output contract.
    """
    definition = DEFINITIONS[definition_id]
    if definition_id == "human_review" and schema_version == 3:
        return {**definition, "outputs": [port("reviewed_draft", "DRAFT")]}
    return definition

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


class MediaNodeInstance(NodeInstance):
    definition_id: Literal["text_input", "text_reference", "draft_prepare", "manual_transform",
        "director_note", "human_review", "asset_reference", "text_generate", "media_generate", "media_review", "timeline_export"]


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
            out = next((p for p in definition_for(source.definition_id, schema_version=self.schema_version)["outputs"] if p["id"] == edge.source_port), None)
            inp = next((p for p in definition_for(target.definition_id, schema_version=self.schema_version)["inputs"] if p["id"] == edge.target_port), None)
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


class GraphMediaInput(GraphInput):
    # New schema owns the additive limits; old schemas and their catalogs stay fixed.
    schema_version: Literal[3]
    nodes: list[MediaNodeInstance] = Field(default_factory=list, max_length=MAX_MEDIA_NODES)

    @model_validator(mode="after")
    def media_capacity(self):
        if sum(node.definition_id in {"media_generate", "timeline_export"} for node in self.nodes) > MAX_MEDIA_GENERATORS:
            raise ValueError("CREATIVE_GRAPH_MEDIA_NODE_CAPACITY")
        return self


def parse_graph(value):
    schema = value.get("schema_version", 1) if isinstance(value, dict) else value.schema_version
    model = GraphMediaInput if schema == 3 else GraphModelInput if schema == 2 else GraphInput
    return model.model_validate(value)


class GraphCreate(Strict):
    request_id: RequestId
    expected_version: Literal[0] = 0
    definition: GraphInput | GraphModelInput | GraphMediaInput

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
    definition: GraphInput | GraphModelInput | GraphMediaInput


class GraphPreflight(Strict):
    expected_version: int = Field(ge=1)
    target_node_ids: list[Id] = Field(default_factory=list, max_length=MAX_NODES)


class GraphMediaPreflight(GraphPreflight):
    # Same wire fields; only a saved schema-3 definition grants this allowance.
    target_node_ids: list[Id] = Field(default_factory=list, max_length=MAX_MEDIA_NODES)


class GraphRunCreate(Strict):
    expected_graph_version: int = Field(ge=1)
    reviewed_preflight_digest: Digest
    target_node_ids: list[Id] = Field(default_factory=list, max_length=MAX_NODES)
    request_id: RequestId


class GraphMediaRunCreate(GraphRunCreate):
    target_node_ids: list[Id] = Field(default_factory=list, max_length=MAX_MEDIA_NODES)


def parse_graph_preflight(value, definition):
    model = GraphMediaPreflight if definition["schema_version"] == 3 else GraphPreflight
    # Pydantic can trust subclass instances without revalidating their fields.
    # Revalidate the wire fields against the authoritative saved definition.
    return model.model_validate(value.model_dump() if isinstance(value, GraphPreflight) else value)


def parse_graph_run_create(value, definition):
    model = GraphMediaRunCreate if definition["schema_version"] == 3 else GraphRunCreate
    return model.model_validate(value.model_dump() if isinstance(value, GraphRunCreate) else value)


class GraphAction(Strict):
    expected_version: int = Field(ge=1)
    node_id: Id | None = None
    reviewed_output_digest: Digest | None = None
    note: str = Field(default="", max_length=1_000)


def catalog_definitions(*, include_model=False, include_media=False):
    return [{"id": key, "version": 1, "inputs": deepcopy(value["inputs"]),
        "outputs": deepcopy(value["outputs"]), "parameters_schema": value["parameters"].model_json_schema(),
        "default_parameters": value["parameters"]().model_dump() if key not in {"asset_reference", "media_generate", "timeline_export"} else None,
        "executable": include_media or key != "asset_reference", "model_called": False,
        "blockers": ["CREATIVE_GRAPH_ATOMIC_INPUT_OWNER_ADAPTER_REQUIRED"] if key == "asset_reference" and not include_media else []}
        for key in DEFINITIONS
        for value in [definition_for(key, schema_version=3 if include_media else None)]
        if (include_model or key != "text_generate") and (include_media or key not in {"media_generate", "media_review", "timeline_export"})]


def history_limit(row):
    return MAX_MEDIA_HISTORY if row.get("graph_schema_version") == 3 or row.get("definition", {}).get("schema_version") == 3 else MAX_HISTORY


def validate_output_ports(definition_id, value, *, schema_version=None):
    """Finite output types also apply to persisted/cached local receipts."""
    expected = definition_for(definition_id, schema_version=schema_version)["outputs"]
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
            model_draft = definition_id == "text_generate" or (definition_id == "human_review"
                and schema_version == 3 and isinstance(item, dict) and item.get("origin") == "MODEL_PROPOSAL")
            draft = (ModelDraftPort if model_draft else DraftPort).model_validate(item)
            if ((definition_id == "draft_prepare" and (draft.origin != "USER_SUPPLIED" or draft.plan is None))
                    or (definition_id == "manual_transform" and (draft.origin != "MANUAL" or draft.plan is not None))):
                raise ValueError("CREATIVE_GRAPH_OUTPUT_SCHEMA_INVALID")
            result[port["id"]] = draft.model_dump(exclude_none=True)
        elif port["type"] == "ASSET_REF":
            if definition_id == "asset_reference" and schema_version != 3:
                raise ValueError("CREATIVE_GRAPH_ATOMIC_INPUT_OWNER_ADAPTER_REQUIRED")
            result[port["id"]] = AssetParameters.model_validate(item).model_dump()
        elif port["type"] == "MEDIA_CANDIDATE":
            candidate = MediaCandidatePort.model_validate(item)
            if candidate.owner == "timeline":
                if schema_version != 3 or definition_id != "timeline_export" or candidate.asset.kind != "video":
                    raise ValueError("CREATIVE_GRAPH_MEDIA_CANDIDATE_KIND_INVALID")
            elif definition_id == "timeline_export" or candidate.owner != candidate.asset.kind:
                raise ValueError("CREATIVE_GRAPH_MEDIA_CANDIDATE_KIND_INVALID")
            result[port["id"]] = candidate.model_dump()
        else:
            raise ValueError("CREATIVE_GRAPH_ATOMIC_INPUT_OWNER_ADAPTER_REQUIRED")
    if len(canonical(result).encode()) > MAX_OUTPUT_BYTES:
        raise ValueError("CREATIVE_GRAPH_OUTPUT_LIMIT")
    return result
