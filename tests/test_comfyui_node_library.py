"""Read-only ComfyUI node-library bridge: bounded parsing, provider fetch fences."""
from __future__ import annotations

import json

import pytest

from app.creative.comfy_node_mapping import (mapping_definitions, node_mapping_index,
    validate_node_mappings, ComfyNodeMappingError)
from app.creative.comfy_node_library import (
    MAX_INPUTS_PER_NODE,
    MAX_OUTPUTS_PER_NODE,
    MAX_RESPONSE_BYTES,
    ComfyNodeLibraryError,
    load_comfyui_node_library,
    parse_comfyui_object_info,
)


def object_info():
    return {
        "KSampler": {
            "input": {
                "required": {
                    "model": ["MODEL"],
                    "seed": ["INT", {"default": 42, "min": 0, "max": 100}],
                    "steps": ["INT", {"default": 20}],
                    "sampler_name": [[
                        "euler", "dpmpp_2m", "  euler  ", "x" * 500,
                    ]],
                },
                "optional": {
                    "denoise": ["FLOAT", {"default": 1.0}],
                    "source_image": ["IMAGE"],
                    "broken": [],
                },
            },
            "output": ["LATENT"],
            "output_name": ["samples"],
            "output_is_list": [False],
            "category": "sampling",
            "display_name": "KSampler",
            "description": "Sample a latent\nwith a model",
            "output_node": False,
        },
        "SaveImage": {
            "input": {"required": {"images": ["IMAGE"], "filename_prefix": ["STRING", {"default": "ComfyUI"}]}},
            "output": [],
            "output_name": [],
            "category": "image",
            "display_name": "Save Image",
            "description": "Save images",
            "output_node": True,
        },
        "BadNode": "not-a-node-object",
        "": {"category": "empty-name"},
    }


class FakeResponse:
    def __init__(self, payload=None, *, status=200, raw=None):
        self.status_code = status
        self.content = raw if raw is not None else json.dumps(payload).encode("utf-8")


class FakeTransport:
    def __init__(self, response):
        self.response = response
        self.calls = []
        self.max_response_bytes = None
        self.max_wire_bytes = None

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def configure_comfy(tmp_path, monkeypatch, *, provider_id="localcomfy", **overrides):
    config = {
        "endpoint": "http://127.0.0.1:8188",
        "default_model": "",
        "api_style": "comfyui",
        "local": True,
        "enabled": True,
        "requires_credential": False,
        "display_name": "Local ComfyUI",
    }
    config.update(overrides)
    path = tmp_path / "providers.json"
    path.write_text(json.dumps({provider_id: config}), encoding="utf-8")
    monkeypatch.setenv("ASSET_PROVIDER_CONFIG_PATH", str(path))
    return path


def test_parse_object_info_normalizes_bounded_node_library():
    result = parse_comfyui_object_info(object_info())
    assert result["contract"] == "studio-comfyui-node-library/1"
    assert result["node_count"] == 2 and result["ignored_nodes"] == 2
    assert [node["node_class"] for node in result["nodes"]] == ["SaveImage", "KSampler"]
    sampler = next(node for node in result["nodes"] if node["node_class"] == "KSampler")
    assert sampler["definition_id"].startswith("comfyui.KSampler.")
    assert sampler["category"] == "sampling" and sampler["description"] == "Sample a latent with a model"
    assert sampler["outputs"] == [{"index": 0, "type": "LATENT", "name": "samples", "is_list": False}]
    assert sampler["studio_type_hints"] == ["MODEL", "INT", "CHOICE", "FLOAT", "IMAGE", "LATENT"]
    inputs = {row["name"]: row for row in sampler["inputs"]}
    assert inputs["model"] == {"name": "model", "type": "MODEL", "required": True, "has_default": False}
    assert inputs["seed"]["default"] == 42 and inputs["seed"]["has_default"] is True
    assert inputs["sampler_name"]["choices"][:2] == ["euler", "dpmpp_2m"]
    assert all(len(choice) <= 80 for choice in inputs["sampler_name"]["choices"])
    assert inputs["source_image"]["required"] is False
    assert inputs["denoise"]["default"] == 1.0
    assert "broken" not in inputs  # empty type specs are ignored instead of guessing
    save = next(node for node in result["nodes"] if node["node_class"] == "SaveImage")
    assert save["output_node"] is True and save["outputs"] == []


def test_parse_object_info_enforces_node_limit_and_rejects_non_object():
    payload = {f"Node{i}": object_info()["SaveImage"] for i in range(5)}
    result = parse_comfyui_object_info(payload, max_nodes=2)
    assert result["node_count"] == 2
    assert result["truncated"] is True and result["ignored_nodes"] == 3
    with pytest.raises(ComfyNodeLibraryError) as raised:
        parse_comfyui_object_info([])
    assert raised.value.code == "COMFYUI_NODE_LIBRARY_INVALID"


def test_input_and_output_bounds_are_applied():
    required = {f"i{i}": ["INT"] for i in range(MAX_INPUTS_PER_NODE + 10)}
    outputs = ["IMAGE"] * (MAX_OUTPUTS_PER_NODE + 5)
    result = parse_comfyui_object_info({
        "Big": {"input": {"required": required}, "output": outputs,
                "output_name": [f"o{i}" for i in range(len(outputs))]},
    })
    node = result["nodes"][0]
    assert len(node["inputs"]) == MAX_INPUTS_PER_NODE
    assert len(node["outputs"]) == MAX_OUTPUTS_PER_NODE


def test_load_fetches_only_configured_comfyui_provider_read_only(tmp_path, monkeypatch):
    configure_comfy(tmp_path, monkeypatch)
    transport = FakeTransport(FakeResponse(object_info()))
    calls = []

    def guard():
        calls.append(True)

    result = load_comfyui_node_library(guard=guard,
        transport_factory=lambda endpoint: transport)

    assert transport.calls and transport.calls[0][0] == "http://127.0.0.1:8188/object_info"
    assert transport.calls[0][1]["timeout"] == 10 and transport.calls[0][1]["dispatch_guard"] is guard
    assert transport.max_response_bytes == MAX_RESPONSE_BYTES
    assert result["provider_id"] == "localcomfy"
    assert result["endpoint_origin"] == "http://127.0.0.1:8188"
    assert result["compatibility"]["execution"] == "NOT_CONNECTED"
    assert result["compatibility"]["studio_executable"] is False
    assert result["compatibility"]["requires_explicit_workflow_mapping"] is True
    assert result["limits"]["cache"] == "NONE_LIVE_READ_ONLY"
    assert result["node_count"] == 2
    assert len(calls) >= 3  # start, before fetch, after fetch/parse


def test_load_rejects_missing_disabled_and_foreign_providers(tmp_path, monkeypatch):
    monkeypatch.setenv("ASSET_PROVIDER_CONFIG_PATH", str(tmp_path / "missing.json"))
    with pytest.raises(ComfyNodeLibraryError) as missing:
        load_comfyui_node_library()
    assert missing.value.code == "COMFYUI_PROVIDER_NOT_CONFIGURED" and missing.value.status == 409

    configure_comfy(tmp_path, monkeypatch, enabled=False)
    with pytest.raises(ComfyNodeLibraryError) as disabled:
        load_comfyui_node_library(transport_factory=lambda endpoint: FakeTransport(FakeResponse(object_info())))
    assert disabled.value.code == "COMFYUI_PROVIDER_DISABLED"

    monkeypatch.setenv("ASSET_PROVIDER_CONFIG_PATH", str(tmp_path / "foreign.json"))
    (tmp_path / "foreign.json").write_text(json.dumps({
        "openai": {"endpoint": "https://api.example.test/v1", "api_style": "openai", "enabled": True},
    }), encoding="utf-8")
    with pytest.raises(ComfyNodeLibraryError) as foreign:
        load_comfyui_node_library(transport_factory=lambda endpoint: FakeTransport(FakeResponse(object_info())))
    assert foreign.value.code == "COMFYUI_PROVIDER_NOT_CONFIGURED"


def test_load_rejects_bad_endpoint_without_calling_transport(tmp_path, monkeypatch):
    configure_comfy(tmp_path, monkeypatch, endpoint="http://user:pass@127.0.0.1:8188")
    called = []

    def factory(endpoint):
        called.append(endpoint)
        return FakeTransport(FakeResponse(object_info()))

    with pytest.raises(ComfyNodeLibraryError) as raised:
        load_comfyui_node_library(transport_factory=factory)
    assert raised.value.code == "COMFYUI_ENDPOINT_REJECTED"
    assert called == []


@pytest.mark.parametrize(("response", "code"), [
    (FakeResponse(raw=b"not-json"), "COMFYUI_NODE_LIBRARY_INVALID"),
    (FakeResponse(raw=b""), "COMFYUI_NODE_LIBRARY_INVALID"),
    (FakeResponse(raw=b"{}"), None),
    (FakeResponse(payload={}, status=500), "COMFYUI_NODE_LIBRARY_UNAVAILABLE"),
    (FakeResponse(payload={"Node": {"input": {}, "output": []}}, status=403), "COMFYUI_NODE_LIBRARY_UNAVAILABLE"),
    (RuntimeError("offline"), "COMFYUI_NODE_LIBRARY_UNAVAILABLE"),
])
def test_load_failures_are_explicit(tmp_path, monkeypatch, response, code):
    configure_comfy(tmp_path, monkeypatch)
    transport = FakeTransport(response)
    if code is None:
        result = load_comfyui_node_library(transport_factory=lambda endpoint: transport)
        assert result["node_count"] == 0 and result["nodes"] == []
        return
    with pytest.raises(ComfyNodeLibraryError) as raised:
        load_comfyui_node_library(transport_factory=lambda endpoint: transport)
    assert raised.value.code == code


def test_load_rejects_oversized_object_info(tmp_path, monkeypatch):
    configure_comfy(tmp_path, monkeypatch)
    transport = FakeTransport(FakeResponse(raw=b"{" + b" " * (MAX_RESPONSE_BYTES + 1) + b"}"))
    with pytest.raises(ComfyNodeLibraryError) as raised:
        load_comfyui_node_library(transport_factory=lambda endpoint: transport)
    assert raised.value.code == "COMFYUI_NODE_LIBRARY_TOO_LARGE"


def test_graph_router_registers_read_only_comfy_node_library_path():
    from app.creative.graph_api import create_creative_graph_router

    from types import SimpleNamespace

    class DummyService:
        GRAPHS = "graphs"
        workspace = SimpleNamespace(lineage=SimpleNamespace(change_impact=None))

    router = create_creative_graph_router(DummyService(), lambda *args, **kwargs: None)
    routes = {(route.path, frozenset(getattr(route, "methods", ()) or ()))
              for route in router.routes if getattr(route, "path", None)}
    assert any(path.endswith("/studio/graphs/comfyui-node-library") and methods == frozenset({"GET"})
               for path, methods in routes)


def _all_recipe_classes():
    from app.services.studio_image_provider_recipes import RECIPES
    classes = []
    for recipe in RECIPES:
        for node in recipe["required_nodes"]:
            if node not in classes:
                classes.append(node)
    return classes


def _object_info_for(classes):
    return {node: {"input": {}, "output": ["IMAGE"], "category": "test",
                   "display_name": node} for node in classes}


def test_mapping_table_is_closed_and_derived_from_existing_recipes():
    from app.services.studio_image_provider_recipes import RECIPES

    definitions = mapping_definitions()
    assert len(definitions) == len(RECIPES)
    by_recipe = {row["id"]: row for row in RECIPES}
    for mapping in definitions:
        recipe = by_recipe[mapping["recipe_id"]]
        assert mapping["comfyui_required_classes"] == tuple(recipe["required_nodes"])
        assert mapping["studio_execution"] == "EXISTING_PROVIDER_RECIPE"
        assert mapping["executable_graph_passthrough"] is False
        assert mapping["studio_definition_id"] in {"image_generate", "image_upscale"}
    index = node_mapping_index()
    assert index["KSampler"] and all(mid.startswith("studio.comfy-") for mid in index["KSampler"])
    assert index["LoadImage"]  # upscale recipe owns the upload class


def test_mapping_validation_compatible_missing_and_unknown(tmp_path, monkeypatch):
    configure_comfy(tmp_path, monkeypatch)
    classes = _all_recipe_classes()
    transport = FakeTransport(FakeResponse(_object_info_for(classes)))
    library = load_comfyui_node_library(transport_factory=lambda endpoint: transport)
    result = validate_node_mappings(library)
    assert result["contract"] == "studio-comfyui-node-mapping/1"
    assert result["mapping_count"] == 4
    assert {row["status"] for row in result["mappings"]} == {"COMPATIBLE"}
    assert all(row["executable_graph_passthrough"] is False for row in result["mappings"])
    assert result["compatibility"]["execution"] == "EXISTING_STUDIO_ADAPTER_ONLY"

    missing = load_comfyui_node_library(transport_factory=lambda endpoint: FakeTransport(
        FakeResponse(_object_info_for([node for node in classes if node != "KSampler"]))))
    result = validate_node_mappings(missing)
    by_id = {row["mapping_id"]: row for row in result["mappings"]}
    assert by_id["studio.comfy-sd-checkpoint-v1.existing-adapter"]["status"] == "MISSING_CLASSES"
    assert "KSampler" in by_id["studio.comfy-sd-checkpoint-v1.existing-adapter"]["missing_classes"]
    assert by_id["studio.comfy-upscale-model-v1.existing-adapter"]["status"] == "COMPATIBLE"

    one = validate_node_mappings(library, mapping_id="studio.comfy-upscale-model-v1.existing-adapter")
    assert one["mapping_count"] == 1
    assert one["mappings"][0]["studio_definition_id"] == "image_upscale"

    with pytest.raises(ComfyNodeMappingError) as unknown:
        validate_node_mappings(library, mapping_id="studio.not-a-mapping")
    assert unknown.value.code == "COMFYUI_NODE_MAPPING_UNKNOWN"


def test_node_library_annotates_closed_mapping_ids(tmp_path, monkeypatch):
    configure_comfy(tmp_path, monkeypatch)
    transport = FakeTransport(FakeResponse(_object_info_for(["KSampler", "SaveImage", "UnknownNode"])))
    library = load_comfyui_node_library(transport_factory=lambda endpoint: transport)
    assert library["mapping_contract"] == "studio-comfyui-node-mapping/1"
    assert library["mapping_execution"] == "EXISTING_STUDIO_ADAPTER_ONLY"
    nodes = {node["node_class"]: node for node in library["nodes"]}
    assert nodes["KSampler"]["studio_mappings"]
    assert all(mid.startswith("studio.comfy-") for mid in nodes["KSampler"]["studio_mappings"])
    assert nodes["UnknownNode"]["studio_mappings"] == []


def test_graph_router_registers_comfy_mapping_path():
    from app.creative.graph_api import create_creative_graph_router
    from types import SimpleNamespace

    class DummyService:
        GRAPHS = "graphs"
        workspace = SimpleNamespace(lineage=SimpleNamespace(change_impact=None))

    router = create_creative_graph_router(DummyService(), lambda *args, **kwargs: None)
    routes = {(route.path, frozenset(getattr(route, "methods", ()) or ()))
              for route in router.routes if getattr(route, "path", None)}
    assert any(path.endswith("/studio/graphs/comfyui-node-mapping") and methods == frozenset({"GET"})
               for path, methods in routes)
