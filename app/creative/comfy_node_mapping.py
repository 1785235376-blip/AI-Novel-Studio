"""Closed, reviewed ComfyUI-node mappings for Studio's existing execution adapters.

This module is the second phase of the node-library bridge: it does not execute
arbitrary ComfyUI graphs. It declares which *existing* Studio definitions already
own a bounded ComfyUI adapter and which ComfyUI classes that adapter's recipe
requires. The mapping endpoint validates a provider's advertised ``/object_info``
against those classes; actual execution remains the existing Studio image/upscale
provider path, behind its normal permissions, review, cost and recovery contracts.
"""
from __future__ import annotations

CONTRACT = "studio-comfyui-node-mapping/1"
PASSTHROUGH_EXECUTION = False


class ComfyNodeMappingError(ValueError):
    def __init__(self, code: str, *, status: int = 409, detail: str = ""):
        super().__init__(code)
        self.code = code
        self.status = int(status)
        self.detail = str(detail)[:240]


def mapping_definitions() -> tuple[dict, ...]:
    """Closed mapping table derived from the existing fixed image recipes.

    Recipe ids, required classes and Studio definition ownership are existing
    contracts; this table only makes them visible to the node-library UI.
    """
    from ..services.studio_image_provider_recipes import RECIPES

    result: list[dict] = []
    for recipe in RECIPES:
        upscale = str(recipe.get("family", "")).upper() == "IMAGE_UPSCALE"
        mapping_id = f"studio.{recipe['id']}.existing-adapter"
        result.append({
            "mapping_id": mapping_id,
            "recipe_id": str(recipe["id"]),
            "studio_definition_id": "image_upscale" if upscale else "image_generate",
            "studio_execution": "EXISTING_PROVIDER_RECIPE",
            "comfyui_required_classes": tuple(str(item) for item in recipe["required_nodes"]),
            "executable_graph_passthrough": PASSTHROUGH_EXECUTION,
            "note": "Existing Studio provider recipe only; ComfyUI classes are prerequisites, not arbitrary graph execution.",
        })
    return tuple(result)


def node_mapping_index() -> dict[str, tuple[str, ...]]:
    index: dict[str, list[str]] = {}
    for mapping in mapping_definitions():
        for node_class in mapping["comfyui_required_classes"]:
            index.setdefault(node_class, []).append(mapping["mapping_id"])
    return {key: tuple(value) for key, value in sorted(index.items())}


def annotate_node_library(library: dict) -> dict:
    """Attach read-only mapping ids to node-library descriptors (mutates a fresh copy)."""
    index = node_mapping_index()
    for node in library.get("nodes", []):
        if isinstance(node, dict):
            node["studio_mappings"] = list(index.get(str(node.get("node_class")), ()))
    library["mapping_contract"] = CONTRACT
    library["mapping_execution"] = "EXISTING_STUDIO_ADAPTER_ONLY"
    return library


def validate_node_mappings(library: dict, *, mapping_id: str | None = None) -> dict:
    """Compare the library's advertised node classes with the closed mappings."""
    if not isinstance(library, dict) or library.get("contract") != "studio-comfyui-node-library/1":
        raise ComfyNodeMappingError("COMFYUI_NODE_LIBRARY_INVALID", status=502)
    definitions = mapping_definitions()
    if mapping_id is not None:
        selected = tuple(item for item in definitions if item["mapping_id"] == mapping_id)
        if not selected:
            raise ComfyNodeMappingError("COMFYUI_NODE_MAPPING_UNKNOWN", status=409)
        definitions = selected
    nodes = library.get("nodes")
    if not isinstance(nodes, list):
        raise ComfyNodeMappingError("COMFYUI_NODE_LIBRARY_INVALID", status=502)
    advertised = {str(node.get("node_class")) for node in nodes if isinstance(node, dict)}
    rows = []
    for mapping in definitions:
        missing = [node_class for node_class in mapping["comfyui_required_classes"]
                   if node_class not in advertised]
        rows.append({
            "mapping_id": mapping["mapping_id"],
            "recipe_id": mapping["recipe_id"],
            "studio_definition_id": mapping["studio_definition_id"],
            "studio_execution": mapping["studio_execution"],
            "status": "COMPATIBLE" if not missing else "MISSING_CLASSES",
            "missing_classes": missing,
            "required_classes": list(mapping["comfyui_required_classes"]),
            "executable_graph_passthrough": bool(mapping["executable_graph_passthrough"]),
            "note": mapping["note"],
        })
    return {
        "contract": CONTRACT,
        "provider_id": library.get("provider_id"),
        "endpoint_origin": library.get("endpoint_origin"),
        "observed_at": library.get("observed_at"),
        "node_count": int(library.get("node_count") or 0),
        "mapping_count": len(rows),
        "mappings": rows,
        "compatibility": {
            "contract": "studio-comfyui-node-compatibility/1",
            "execution": "EXISTING_STUDIO_ADAPTER_ONLY",
            "studio_executable": False,
            "executable_graph_passthrough": PASSTHROUGH_EXECUTION,
            "requires_existing_provider_recipe": True,
            "arbitrary_comfyui_graph_execution": "NOT_IMPLEMENTED",
        },
        "limits": {
            "mapping_source": "CLOSED_STUDIO_RECIPES",
            "validation": "CLASS_PRESENCE_ONLY",
            "real_comfyui_execution": "NOT_RUN",
        },
    }
