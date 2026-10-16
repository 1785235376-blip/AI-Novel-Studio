"""Finite image-only Graph transforms over the original asset and job owners.

Reference nodes carry versioned assets, never pixels, paths or new registries.
Weights describe normalized pixel initialization, not a learned identity adapter.
Only the original media review can publish a generated asset.
"""
from copy import deepcopy

from .graph_models import (GraphImageAsset, ImagePromptParameters, ImagePromptPort, ImageStyleParameters,
    ImageReferenceParameters, validate_output_ports)


def execute_image_local(node, ports):
    """Deterministic transforms; the caller holds the original asset phase."""
    kind = node["definition_id"]
    if kind == "image_reference":
        parameters = ImageReferenceParameters.model_validate(node["parameters"])
        if not parameters.bindings or set(ports) != {binding.port for binding in parameters.bindings}:
            raise ValueError("CREATIVE_GRAPH_IMAGE_REFERENCE_BINDING_REQUIRED")
        output = {"references": [{"asset": GraphImageAsset.model_validate(ports[binding.port]).model_dump(),
            **{key: value for key, value in binding.model_dump().items() if key != "port"}}
            for binding in parameters.bindings]}
    elif kind == "image_prompt":
        parameters = ImagePromptParameters.model_validate(node["parameters"])
        if set(ports) - {"text", "references"}:
            raise ValueError("CREATIVE_GRAPH_IMAGE_PROMPT_INPUT_INVALID")
        text = ports.get("text", "")
        if not isinstance(text, str) or len(text) > 8000 or (parameters.prompt.strip() and text.strip()):
            raise ValueError("CREATIVE_GRAPH_IMAGE_PROMPT_AMBIGUOUS")
        output = {"prompt": {"prompt": parameters.prompt if parameters.prompt.strip() else text,
            "references": deepcopy(ports.get("references", []))}}
    elif kind == "image_style":
        if set(ports) != {"prompt"}:
            raise ValueError("CREATIVE_GRAPH_IMAGE_PROMPT_REQUIRED")
        prompt = ImagePromptPort.model_validate(ports["prompt"]).model_dump()
        style = ImageStyleParameters.model_validate(node["parameters"])
        instructions = [label + ": " + text.strip() for label, text in
            (("Style", style.style), ("Atmosphere", style.atmosphere), ("Color palette", style.color_palette)) if text.strip()]
        prompt["prompt"] += ("\n" + "\n".join(instructions)) if instructions else ""
        output = {"prompt": prompt}
    else:
        raise ValueError("CREATIVE_GRAPH_IMAGE_LOCAL_NODE_REQUIRED")
    return validate_output_ports(kind, output, schema_version=4)


def image_command_fields(node, ports):
    """Construct source DTOs from resolved typed ports, never caller metadata."""
    if node["definition_id"] == "image_upscale":
        if set(ports) != {"source"}:
            raise ValueError("CREATIVE_GRAPH_IMAGE_SOURCE_REQUIRED")
        source = GraphImageAsset.model_validate(ports["source"])
        snapshot = {"kind": "ASSET", "id": source.asset_id, "version": source.version,
            "digest": source.digest, "asset_kind": "image"}
        return {"prompt": "", "source_snapshots": [snapshot], "image_source": snapshot}
    if set(ports) - {"prompt", "source", "mask"} or "prompt" not in ports:
        raise ValueError("CREATIVE_GRAPH_IMAGE_PROMPT_REQUIRED")
    prompt = ImagePromptPort.model_validate(ports["prompt"])
    base = GraphImageAsset.model_validate(ports["source"]).model_dump() if "source" in ports else None
    mask = GraphImageAsset.model_validate(ports["mask"]).model_dump() if "mask" in ports else None
    references = [value.model_dump() for value in prompt.references]
    operation = node["parameters"]["operation_id"]
    if operation == "m5.image.t2i" and (base or mask or references):
        raise ValueError("CREATIVE_GRAPH_IMAGE_T2I_UNUSED_REFERENCE")
    if operation == "m5.image.reference" and (base or mask or not references):
        raise ValueError("CREATIVE_GRAPH_IMAGE_REFERENCE_INPUT_REQUIRED")
    if operation == "m5.image.i2i" and (not base or mask or len(references) > 4):
        raise ValueError("CREATIVE_GRAPH_IMAGE_SOURCE_REQUIRED")
    if operation == "m5.image.inpaint" and (not base or not mask or references):
        raise ValueError("CREATIVE_GRAPH_IMAGE_INPAINT_INPUT_REQUIRED")
    if base and mask and base["asset_id"] == mask["asset_id"]:
        raise ValueError("CREATIVE_GRAPH_IMAGE_MASK_SOURCE_ALIAS")

    def snapshot(asset):
        return {"kind": "ASSET", "id": asset["asset_id"], "version": asset["version"],
            "digest": asset["digest"], "asset_kind": "image"}

    source = snapshot(base) if base else None
    mask_source = snapshot(mask) if mask else None
    weighted = [{"source": snapshot(reference["asset"]), **{key: value for key, value in reference.items() if key != "asset"}}
        for reference in references]
    sources, seen = [], {}
    for value in ([source] if source else []) + [reference["source"] for reference in weighted] + ([mask_source] if mask_source else []):
        if value["id"] in seen:
            if seen[value["id"]] != value:
                raise ValueError("CREATIVE_GRAPH_IMAGE_SOURCE_VERSION_CONFLICT")
            raise ValueError("CREATIVE_GRAPH_IMAGE_REFERENCE_DUPLICATE")
        seen[value["id"]] = value
        sources.append(value)
    sources.extend(value.model_dump(exclude_none=True, exclude={"reference_only"}) for value in prompt.document_sources or [])
    result = {"prompt": prompt.prompt, "source_snapshots": sources}
    if source:
        result["image_source"] = source
    if weighted:
        result["image_references"] = weighted
    if mask_source:
        result["mask_source"] = mask_source
    return result


def preflight_image_nodes(nodes, incoming, order, source_kind):
    """Static wiring checks; these never confer asset or model authority."""
    issues = []
    for node_id in order:
        node = nodes[node_id]
        kind = node["definition_id"]
        edges = {edge["target_port"]: edge for edge in incoming[node_id]}
        code = None
        if kind == "image_reference":
            bindings = {binding["port"] for binding in node["parameters"]["bindings"]}
            if not bindings or set(edges) != bindings:
                code = "CREATIVE_GRAPH_IMAGE_REFERENCE_BINDING_REQUIRED"
            elif any(source_kind(edge) != "image" for edge in edges.values()):
                code = "CREATIVE_GRAPH_IMAGE_SOURCE_KIND_INVALID"
        elif kind == "image_prompt":
            if "text" in edges and node["parameters"]["prompt"].strip():
                code = "CREATIVE_GRAPH_IMAGE_PROMPT_AMBIGUOUS"
            elif "text" not in edges and not node["parameters"]["prompt"].strip():
                code = "CREATIVE_GRAPH_IMAGE_PROMPT_REQUIRED"
        elif kind == "image_upscale":
            if set(edges) != {"source"} or source_kind(edges["source"]) != "image":
                code = "CREATIVE_GRAPH_IMAGE_SOURCE_REQUIRED"
        elif kind == "image_generate":
            operation = node["parameters"]["operation_id"]
            prompt_edge = edges.get("prompt")
            prompt_node = nodes[prompt_edge["source_node_id"]] if prompt_edge else None
            while prompt_node and prompt_node["definition_id"] == "image_style":
                upstream = next((edge for edge in incoming[prompt_node["id"]] if edge["target_port"] == "prompt"), None)
                prompt_node = nodes[upstream["source_node_id"]] if upstream else None
            has_refs = bool(prompt_node and any(edge["target_port"] == "references"
                for edge in incoming[prompt_node["id"]]))
            if any(source_kind(edge) != "image" for port, edge in edges.items() if port in {"source", "mask"}):
                code = "CREATIVE_GRAPH_IMAGE_SOURCE_KIND_INVALID"
            elif operation == "m5.image.t2i" and (has_refs or set(edges) & {"source", "mask"}):
                code = "CREATIVE_GRAPH_IMAGE_T2I_UNUSED_REFERENCE"
            elif operation == "m5.image.reference" and (not has_refs or set(edges) & {"source", "mask"}):
                code = "CREATIVE_GRAPH_IMAGE_REFERENCE_INPUT_REQUIRED"
            elif operation == "m5.image.i2i" and ("source" not in edges or "mask" in edges):
                code = "CREATIVE_GRAPH_IMAGE_SOURCE_REQUIRED"
            elif operation == "m5.image.i2i" and has_refs:
                ref_edge = next(edge for edge in incoming[prompt_node["id"]] if edge["target_port"] == "references")
                reference = nodes[ref_edge["source_node_id"]]
                if len(reference["parameters"]["bindings"]) > 4:
                    code = "CREATIVE_GRAPH_IMAGE_REFERENCE_LIMIT"
            elif operation == "m5.image.inpaint" and (has_refs or not {"source", "mask"} <= set(edges)):
                code = "CREATIVE_GRAPH_IMAGE_INPAINT_INPUT_REQUIRED"
            elif operation == "m5.image.inpaint" and edges["source"]["source_node_id"] == edges["mask"]["source_node_id"]:
                code = "CREATIVE_GRAPH_IMAGE_MASK_SOURCE_ALIAS"
        if code:
            issues.append({"code": code, "node_id": node_id})
    return issues
