"""Schema-5 projections; original Creative, VideoJob and Asset owners execute.

No provider command or URL is accepted here. A shot is exact original history
evidence, and every resolved command still passes MediaCommand validation.
"""
from copy import deepcopy

from .graph_models import (AssetParameters, StoryboardDataPort, StoryboardShotParameters,
    StoryboardShotPort, VideoNodeParameters, validate_output_ports)
from ..experimental.common import StaleSourceError


def execute_shot(service, nid, scope, node, ports, guard, state=None, *, actor, check_images=True):
    if set(ports) != {"storyboard"}:
        raise ValueError("CREATIVE_GRAPH_STORYBOARD_INPUT_REQUIRED")
    data = StoryboardDataPort.model_validate(ports["storyboard"])
    selected = StoryboardShotParameters.model_validate(node["parameters"])
    from .graph_planning_nodes import read_document
    from .storyboard import storyboard_receipt
    row = read_document(service, nid, scope, {"definition_id": "storyboard_plan",
        "parameters": {"document_snapshot": data.document_snapshot.model_dump()}}, guard, state)
    receipt = storyboard_receipt(row)
    item = next((item for item in receipt["shots"] if item["shot_id"] == selected.shot_id), None)
    if item is None or (item["shot_version"], item["shot_digest"]) != (selected.shot_version, selected.shot_digest):
        raise StaleSourceError("CREATIVE_GRAPH_STORYBOARD_SHOT_CHANGED")
    image = item["image_asset"]
    if image is not None and check_images:
        service.asset_inputs.read(nid, scope, actor, image, guard)
    output = {"shot": {**selected.model_dump(), "document_snapshot": data.document_snapshot.model_dump(),
        "shot": deepcopy(item["shot"]), "image_asset": deepcopy(image), "approved": receipt["approved"]}}
    guard()
    return validate_output_ports("storyboard_shot", output, schema_version=5)


def video_command_fields(node, ports):
    parameters = VideoNodeParameters.model_validate(node["parameters"])
    if set(ports) - {"text", "shot", "source", "reference"}:
        raise ValueError("CREATIVE_GRAPH_VIDEO_INPUT_INVALID")
    values = parameters.model_dump()
    purpose = values.pop("reference_purpose", None)
    bind_shot = values.pop("bind_shot", None)
    prompt = values["prompt"]
    text = ports.get("text")
    if text is not None:
        if not isinstance(text, str) or not text.strip() or len(text) > 8000:
            raise ValueError("CREATIVE_GRAPH_VIDEO_TEXT_INVALID")
        prompt += ("\n\n" if prompt else "") + "GRAPH_SOURCE_TEXT\n" + text
    sources = []
    shot = StoryboardShotPort.model_validate(ports["shot"]) if "shot" in ports else None
    if bind_shot and shot is None:
        raise ValueError("CREATIVE_GRAPH_VIDEO_SHOT_BINDING_INPUT_REQUIRED")
    if shot is not None:
        if not shot.approved:
            raise ValueError("STUDIO_STORYBOARD_APPROVAL_REQUIRED")
        authored = [shot.shot.frame_prompt]
        for key in ("shot_size", "camera_angle", "camera_motion", "lens", "composition", "action",
                "emotion", "lighting", "environment", "color", "sound", "sound_effect", "video_generation_hint"):
            value = getattr(shot.shot, key, None)
            if value and value.strip():
                authored.append(key + ": " + value.strip())
        if shot.shot.characters:
            authored.append("characters: " + ", ".join(shot.shot.characters))
        prompt += ("\n\n" if prompt else "") + "STORYBOARD_SHOT\n" + "\n".join(authored)
        duration = values["parameters"].get("duration_seconds")
        if duration is not None and duration != shot.shot.duration_seconds:
            raise ValueError("CREATIVE_GRAPH_VIDEO_SHOT_DURATION_CONFLICT")
        values["parameters"]["duration_seconds"] = shot.shot.duration_seconds
        pin = shot.document_snapshot
        sources.append({"kind": "CREATIVE_DOCUMENT", "id": pin.id, "version": pin.version, "digest": pin.digest})
        # Explicit opt-in preserves already-published schema5 command identities.
        # This pin is original history evidence; MediaCommand's owner validates
        # current approval and later publication/review keep the original fences.
        if bind_shot:
            values["storyboard_shot"] = {"document_snapshot": pin.model_dump(),
                "shot_id": shot.shot_id, "shot_version": shot.shot_version, "shot_digest": shot.shot_digest}
    source = AssetParameters.model_validate(ports["source"]) if "source" in ports else None
    reference = AssetParameters.model_validate(ports["reference"]) if "reference" in ports else None
    if reference is not None:
        if source is not None or parameters.operation_id != "m7.video.v2v" or reference.kind != "video" or purpose is None:
            raise ValueError("CREATIVE_GRAPH_VIDEO_REFERENCE_INVALID")
        source = reference
    elif purpose is not None:
        raise ValueError("CREATIVE_GRAPH_VIDEO_REFERENCE_REQUIRED")
    if source is None and parameters.operation_id == "m7.video.i2v" and shot is not None and shot.image_asset is not None:
        source = shot.image_asset
    required = {"m7.video.i2v": "image", "m7.video.v2v": "video"}.get(parameters.operation_id)
    if required is None and source is not None or required is not None and (source is None or source.kind != required):
        raise ValueError("CREATIVE_GRAPH_VIDEO_SOURCE_KIND_INVALID")
    if parameters.operation_id == "m7.video.i2v" and shot is not None and shot.image_asset is not None and source != shot.image_asset:
        raise StaleSourceError("CREATIVE_GRAPH_VIDEO_SHOT_IMAGE_CONFLICT")
    if source is not None:
        snapshot = {"kind": "ASSET", "id": source.asset_id, "version": source.version,
            "digest": source.digest, "asset_kind": source.kind}
        sources.append(snapshot)
        if reference is not None:
            values["video_reference"] = {"source": snapshot, "purpose": purpose}
    values.update(prompt=prompt, source_snapshots=sources)
    return values


def preflight_video(nodes, incoming, order, source_kind):
    issues = []
    for key in order:
        node = nodes[key]
        if node["definition_id"] != "video_generate":
            continue
        edges = {edge["target_port"]: edge for edge in incoming[key]}
        operation = node["parameters"]["operation_id"]
        code = None
        if node["parameters"].get("bind_shot") and "shot" not in edges:
            code = "CREATIVE_GRAPH_VIDEO_SHOT_BINDING_INPUT_REQUIRED"
        elif "source" in edges and "reference" in edges:
            code = "CREATIVE_GRAPH_VIDEO_SOURCE_EXCLUSIVE"
        elif "reference" in edges and (operation != "m7.video.v2v" or source_kind(edges["reference"]) != "video"
                or node["parameters"].get("reference_purpose") is None):
            code = "CREATIVE_GRAPH_VIDEO_REFERENCE_INVALID"
        elif "reference" not in edges and node["parameters"].get("reference_purpose") is not None:
            code = "CREATIVE_GRAPH_VIDEO_REFERENCE_REQUIRED"
        else:
            required = {"m7.video.i2v": "image", "m7.video.v2v": "video"}.get(operation)
            if "source" in edges and (required is None or source_kind(edges["source"]) != required):
                code = "CREATIVE_GRAPH_VIDEO_SOURCE_KIND_INVALID"
            elif required == "video" and not set(edges) & {"source", "reference"}:
                code = "CREATIVE_GRAPH_VIDEO_SOURCE_REQUIRED"
            elif required == "image" and not set(edges) & {"source", "shot"}:
                code = "CREATIVE_GRAPH_VIDEO_SOURCE_REQUIRED"
            elif not node["parameters"]["prompt"].strip() and not set(edges) & {"text", "shot"}:
                code = "CREATIVE_GRAPH_MEDIA_PROMPT_REQUIRED"
        if code:
            issues.append({"code": code, "node_id": key})
    return issues
