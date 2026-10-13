"""Typed read adapters over original Creative documents, never a second owner.

Graph nodes do not create, accept or apply Director/Storyboard suggestions.
The user saves or reviews the original document first, then binds an exact
snapshot. All reads, dispatches and publication callbacks recheck that snapshot.
"""
from .graph_models import (PlanningNodeParameters, DirectorPlanPort, StoryboardDataPort,
    StoryboardPromptParameters, validate_output_ports)
from .service import document_digest
from ..experimental.common import StaleSourceError

PLANNING_REFERENCES = {"director_plan", "storyboard_plan"}
PLANNING_LOCAL = PLANNING_REFERENCES | {"storyboard_prompt", "storyboard_shot"}


def read_document(service, nid, scope, node, guard, state=None):
    expected = PlanningNodeParameters.model_validate(node["parameters"]).document_snapshot
    document = state if state is not None else service.store.read(nid, scope)
    creative = service.workspace.creative
    row = document["collections"].get(creative.COLLECTION, {}).get(expected.id)
    guard()
    if not isinstance(row, dict) or row.get("status") == "ARCHIVED":
        raise FileNotFoundError(expected.id)
    # Match CreativeService._raw's record check without acquiring a new lease.
    if type(row.get("version")) is not int or row["version"] < 1:
        raise ValueError("CREATIVE_DOCUMENT_CORRUPT")
    creative.assert_current(nid, scope, row)
    mode = "DIRECTOR" if node["definition_id"] == "director_plan" else "STORYBOARD"
    if row.get("mode") != mode:
        raise ValueError("CREATIVE_GRAPH_PLANNING_DOCUMENT_MODE_INVALID")
    if row.get("version") != expected.version or document_digest(row) != expected.digest:
        raise StaleSourceError("CREATIVE_GRAPH_PLANNING_DOCUMENT_CHANGED")
    guard()
    return row


def current_documents(service, nid, scope, nodes, guard, state=None):
    for node in nodes:
        if node["definition_id"] in PLANNING_REFERENCES:
            read_document(service, nid, scope, node, guard, state)
    guard()


def preflight_planning(service, nid, scope, nodes, incoming, order, guard, state=None, *, schema_version=4, actor=None):
    """Check selected shot, exact Director ancestry and bounded typed output.

    Only passive planning nodes are evaluated. No provider, asset mutation,
    proposal acceptance or job admission can happen during this preview.
    """
    outputs, issues = {}, []
    for node_id in order:
        node = nodes[node_id]
        if schema_version == 5 and node["definition_id"] == "video_generate":
            shot_edge = next((edge for edge in incoming[node_id] if edge["target_port"] == "shot"), None)
            shot = outputs.get(shot_edge["source_node_id"], {}).get("shot") if shot_edge else None
            if shot_edge and (shot is None or not shot["approved"]):
                issues.append({"code": "STUDIO_STORYBOARD_APPROVAL_REQUIRED", "node_id": node_id})
            if shot is not None:
                duration = node["parameters"]["parameters"].get("duration_seconds")
                if duration is not None and duration != shot["shot"]["duration_seconds"]:
                    issues.append({"code": "CREATIVE_GRAPH_VIDEO_SHOT_DURATION_CONFLICT", "node_id": node_id})
                if (node["parameters"]["operation_id"] == "m7.video.i2v" and shot["image_asset"] is None
                        and not any(edge["target_port"] == "source" for edge in incoming[node_id])):
                    issues.append({"code": "CREATIVE_GRAPH_VIDEO_SOURCE_REQUIRED", "node_id": node_id})
            continue
        if node["definition_id"] not in PLANNING_LOCAL:
            continue
        inputs = {edge["target_port"]: outputs.get(edge["source_node_id"], {}).get(edge["source_port"])
            for edge in incoming[node_id]}
        try:
            outputs[node_id] = execute_planning_local(service, nid, scope, node, inputs, guard, state,
                schema_version=schema_version, actor=actor)
        except (ValueError, FileNotFoundError):
            guard()
            issues.append({"code": "CREATIVE_GRAPH_PLANNING_INPUT_CHANGED_OR_INVALID", "node_id": node_id})
    guard()
    return issues


def execute_planning_local(service, nid, scope, node, ports, guard, state=None, *, schema_version=4, actor=None, check_images=True):
    kind = node["definition_id"]
    if kind == "storyboard_shot":
        if schema_version != 5:
            raise ValueError("CREATIVE_GRAPH_VIDEO_SCHEMA_REQUIRED")
        from .graph_video_nodes import execute_shot
        return execute_shot(service, nid, scope, node, ports, guard, state, actor=actor, check_images=check_images)
    if kind in PLANNING_REFERENCES:
        if set(ports) - ({"direction"} if kind == "storyboard_plan" else set()):
            raise ValueError("CREATIVE_GRAPH_PLANNING_INPUT_INVALID")
        row = read_document(service, nid, scope, node, guard, state)
        # Use only the strict author's payload; server paths/history/permissions
        # never enter a node output. The complete original row is digest-bound.
        from .models import CreativeProductionDocumentIn
        content = CreativeProductionDocumentIn.model_validate({key: row[key]
            for key in CreativeProductionDocumentIn.model_fields if key in row}).model_dump()
        if "direction" in ports:
            direction = DirectorPlanPort.model_validate(ports["direction"]).document_snapshot
            if row.get("source_documents", {}).get(direction.id) != {
                    "version": direction.version, "digest": direction.digest}:
                raise StaleSourceError("CREATIVE_GRAPH_STORYBOARD_DIRECTOR_BINDING_REQUIRED")
        output = {"direction" if kind == "director_plan" else "storyboard": {
            "document_snapshot": node["parameters"]["document_snapshot"], "content": content}}
    elif kind == "storyboard_prompt":
        if set(ports) != {"storyboard"}:
            raise ValueError("CREATIVE_GRAPH_STORYBOARD_INPUT_REQUIRED")
        data = StoryboardDataPort.model_validate(ports["storyboard"])
        parameters = StoryboardPromptParameters.model_validate(node["parameters"])
        shot = next((shot for shot in data.content.shots if shot.id == parameters.shot_id), None)
        if shot is None:
            raise ValueError("CREATIVE_GRAPH_STORYBOARD_SHOT_REQUIRED")
        scene = next((scene for scene in data.content.scenes if scene.id == shot.scene_id), None)
        parts = [value for value in [shot.frame_prompt, scene.heading if scene else ""] if value.strip()]
        for name in ("shot_size", "camera_angle", "camera_motion", "composition", "lens", "lighting",
                "environment", "color", "action", "emotion", "sound", "sound_effect"):
            text = getattr(shot, name, None)
            if text and text.strip():
                parts.append(name + ": " + text.strip())
        if getattr(shot, "characters", None):
            parts.append("characters: " + ", ".join(shot.characters))
        goal = getattr(data.content, "visual_target", None)
        if goal is not None:
            for name in ("style", "atmosphere", "color", "rhythm"):
                text = getattr(goal, name, "")
                if text.strip():
                    parts.append(name + ": " + text.strip())
        source = data.document_snapshot
        output = {"prompt": {"prompt": "\n".join(parts), "references": [], "document_sources": [{
            "kind": "CREATIVE_DOCUMENT", "id": source.id, "version": source.version, "digest": source.digest}]}}
    else:
        raise ValueError("CREATIVE_GRAPH_PLANNING_NODE_REQUIRED")
    guard()
    return validate_output_ports(kind, output, schema_version=schema_version)
