"""Bounded lower-canvas run preflight: prompt conversion + quote, no dispatch."""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from app.creative.lower_canvas_api import (
    LowerCanvasSave,
    create_lower_canvas_router,
    save_lower_canvas,
)
from app.creative.lower_canvas_runs import (
    LowerCanvasRunError,
    build_comfy_prompt,
    preflight_lower_canvas_run,
)


def object_info():
    return {
        "CheckpointLoaderSimple": {"input": {"required": {"ckpt_name": [["model.safetensors", "other.safetensors"]]}},
            "output": ["MODEL", "CLIP", "VAE"], "output_name": ["MODEL", "CLIP", "VAE"], "category": "loaders"},
        "CLIPTextEncode": {"input": {"required": {"text": ["STRING", {"multiline": True}], "clip": ["CLIP"]}},
            "output": ["CONDITIONING"], "category": "conditioning"},
        "EmptyLatentImage": {"input": {"required": {"width": ["INT", {"default": 512}], "height": ["INT", {"default": 512}],
            "batch_size": ["INT", {"default": 1}]}}, "output": ["LATENT"], "category": "latent"},
        "KSampler": {"input": {"required": {"model": ["MODEL"], "seed": ["INT", {"default": 0}], "steps": ["INT", {"default": 20}],
            "cfg": ["FLOAT", {"default": 7.0}], "sampler_name": [["euler", "dpmpp_2m"]],
            "scheduler": [["normal", "karras"]], "positive": ["CONDITIONING"], "negative": ["CONDITIONING"],
            "latent_image": ["LATENT"], "denoise": ["FLOAT", {"default": 1.0}]}}, "output": ["LATENT"], "category": "sampling"},
        "VAEDecode": {"input": {"required": {"samples": ["LATENT"], "vae": ["VAE"]}}, "output": ["IMAGE"], "category": "latent"},
        "SaveImage": {"input": {"required": {"images": ["IMAGE"], "filename_prefix": ["STRING", {"default": "ComfyUI"}]}},
            "output": [], "output_node": True, "category": "image"},
    }


def valid_graph():
    return {
        "nodes": [
            {"id": "ckpt", "t": "CheckpointLoaderSimple", "x": 0, "y": 0, "title": "ckpt",
             "params": {"ckpt_name": "model.safetensors"}},
            {"id": "pos", "t": "CLIPTextEncode", "x": 0, "y": 0, "title": "pos", "params": {"text": "a cat"}},
            {"id": "neg", "t": "CLIPTextEncode", "x": 0, "y": 0, "title": "neg", "params": {"text": "blurry"}},
            {"id": "latent", "t": "EmptyLatentImage", "x": 0, "y": 0, "title": "latent",
             "params": {"width": 512, "height": 512, "batch_size": 1}},
            {"id": "sampler", "t": "KSampler", "x": 0, "y": 0, "title": "sample",
             "params": {"seed": 7, "steps": 20, "cfg": 7.0, "sampler_name": "euler", "scheduler": "normal", "denoise": 1.0}},
            {"id": "decode", "t": "VAEDecode", "x": 0, "y": 0, "title": "decode"},
            {"id": "save", "t": "SaveImage", "x": 0, "y": 0, "title": "save", "params": {"filename_prefix": "out"}},
        ],
        "edges": [
            {"id": "e1", "a": "ckpt", "as": 1, "b": "pos", "bs": 0},
            {"id": "e2", "a": "ckpt", "as": 1, "b": "neg", "bs": 0},
            {"id": "e3", "a": "ckpt", "as": 0, "b": "sampler", "bs": 0},
            {"id": "e4", "a": "pos", "as": 0, "b": "sampler", "bs": 1},
            {"id": "e5", "a": "neg", "as": 0, "b": "sampler", "bs": 2},
            {"id": "e6", "a": "latent", "as": 0, "b": "sampler", "bs": 3},
            {"id": "e7", "a": "sampler", "as": 0, "b": "decode", "bs": 0},
            {"id": "e8", "a": "ckpt", "as": 2, "b": "decode", "bs": 1},
            {"id": "e9", "a": "decode", "as": 0, "b": "save", "bs": 0},
        ],
    }


class FakeResponse:
    def __init__(self, payload):
        self.status_code = 200
        self.content = json.dumps(payload).encode("utf-8")


class FakeTransport:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []
        self.max_response_bytes = None
        self.max_wire_bytes = None

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return FakeResponse(self.payload)


def configure_comfy(tmp_path, monkeypatch, *, local=True):
    path = tmp_path / "providers.json"
    path.write_text(json.dumps({"comfy": {"endpoint": "http://127.0.0.1:8188", "api_style": "comfyui",
        "enabled": True, "local": local, "default_model": "", "requires_credential": False}}), encoding="utf-8")
    monkeypatch.setenv("ASSET_PROVIDER_CONFIG_PATH", str(path))


def save_draft(service, graph=None):
    nid, scope = "novel-run", {"mode": "local", "novel_id": "novel-run"}
    save_lower_canvas(service, nid, scope, "author", "image",
        LowerCanvasSave.model_validate({"expected_version": 0, "graph": graph or valid_graph()}))
    return nid, scope


def test_build_prompt_converts_ports_widgets_and_output_nodes():
    built = build_comfy_prompt(valid_graph(), object_info())
    assert built["contract"] == "studio-lower-canvas-prompt/1"
    assert built["node_count"] == 7 and built["edge_count"] == 9
    assert built["output_nodes"] == ["save"]
    prompt = built["prompt"]
    assert prompt["ckpt"] == {"class_type": "CheckpointLoaderSimple",
        "inputs": {"ckpt_name": "model.safetensors"}}
    assert prompt["sampler"] == {"class_type": "KSampler", "inputs": {
        "seed": 7, "steps": 20, "cfg": 7.0, "sampler_name": "euler", "scheduler": "normal", "denoise": 1.0,
        "model": ["ckpt", 0], "positive": ["pos", 0], "negative": ["neg", 0], "latent_image": ["latent", 0]}}
    assert prompt["save"]["inputs"] == {"filename_prefix": "out", "images": ["decode", 0]}
    assert len(built["prompt_digest"]) == 64


@pytest.mark.parametrize(("mutate", "code"), [
    (lambda g: g.update(nodes=[]), "LOWER_CANVAS_GRAPH_EMPTY"),
    (lambda g: g["nodes"][0].update(t="MissingNode"), "LOWER_CANVAS_NODE_CLASS_UNKNOWN"),
    (lambda g: g["edges"].append({"id": "x", "a": "ckpt", "as": 0, "b": "save", "bs": 9}),
     "LOWER_CANVAS_LINK_SLOT_INVALID"),
    (lambda g: g["edges"].append({"id": "x", "a": "ckpt", "as": 0, "b": "pos", "bs": 0}),
     "LOWER_CANVAS_INPUT_MULTI_LINKED"),
    (lambda g: g["nodes"][4]["params"].update(seed="7"), "LOWER_CANVAS_PARAM_INVALID"),
    (lambda g: g["nodes"][4]["params"].update(nope=1), "LOWER_CANVAS_PARAM_UNKNOWN"),
    (lambda g: g["edges"].append({"id": "dup", "a": "ckpt", "as": 0, "b": "sampler", "bs": 0}),
     "LOWER_CANVAS_INPUT_MULTI_LINKED"),
])
def test_build_prompt_rejects_invalid_graphs(mutate, code):
    graph = valid_graph()
    mutate(graph)
    with pytest.raises(LowerCanvasRunError) as raised:
        build_comfy_prompt(graph, object_info())
    assert raised.value.code == code


def test_build_prompt_rejects_cycles():
    graph = valid_graph()
    # CLIPTextEncode has no CONDITIONING input, so use two nodes that do: add cycle via duplicate KSampler edges is
    # already multi-linked; instead build a minimal graph of two VAEDecode nodes whose inputs are mutually linked.
    graph = {"nodes": [{"id": "a", "t": "VAEDecode", "x": 0, "y": 0, "title": "a"},
                       {"id": "b", "t": "VAEDecode", "x": 0, "y": 0, "title": "b"},
                       {"id": "out", "t": "SaveImage", "x": 0, "y": 0, "title": "out"}],
             "edges": [{"id": "e2", "a": "a", "as": 0, "b": "b", "bs": 0},
                       {"id": "e3", "a": "b", "as": 0, "b": "a", "bs": 1}]}
    with pytest.raises(LowerCanvasRunError) as raised:
        build_comfy_prompt(graph, object_info())
    assert raised.value.code == "LOWER_CANVAS_GRAPH_HAS_CYCLE"


def test_preflight_requires_version_local_provider_and_returns_quote(tmp_path, monkeypatch):
    from app.experimental.store import ExperimentalStore
    configure_comfy(tmp_path, monkeypatch)
    service = SimpleNamespace(store=ExperimentalStore(tmp_path / "data"))
    nid, scope = save_draft(service)
    transport = FakeTransport(object_info())

    quote = preflight_lower_canvas_run(service, nid, scope, "author", "image", expected_version=1,
        provider_id="comfy", transport_factory=lambda endpoint: transport)
    assert quote["contract"] == "studio-lower-canvas-run-quote/1"
    assert quote["draft_version"] == 1 and quote["provider_id"] == "comfy"
    assert quote["node_count"] == 7 and quote["edge_count"] == 9
    assert quote["output_nodes"] == ["save"]
    assert quote["price"] == {"currency": "USD", "amount_micros": 0, "reason": "LOCAL_COMFYUI_NO_BILLING"}
    assert quote["confirmation_required"] is True
    assert quote["execution"] == "NOT_DISPATCHED" and quote["dispatch_contract"] == "NOT_IMPLEMENTED"
    assert len(quote["quote_digest"]) == 64 and quote["quote_id"].startswith("lcq_")
    assert transport.calls and transport.calls[0][0] == "http://127.0.0.1:8188/object_info"

    with pytest.raises(LowerCanvasRunError) as conflict:
        preflight_lower_canvas_run(service, nid, scope, "author", "image", expected_version=0,
            provider_id="comfy", transport_factory=lambda endpoint: transport)
    assert conflict.value.code == "LOWER_CANVAS_VERSION_CONFLICT"


def test_preflight_rejects_non_local_provider(tmp_path, monkeypatch):
    from app.experimental.store import ExperimentalStore
    configure_comfy(tmp_path, monkeypatch, local=False)
    service = SimpleNamespace(store=ExperimentalStore(tmp_path / "data2"))
    nid, scope = save_draft(service)
    with pytest.raises(LowerCanvasRunError) as raised:
        preflight_lower_canvas_run(service, nid, scope, "author", "image", expected_version=1,
            provider_id="comfy", transport_factory=lambda endpoint: FakeTransport(object_info()))
    assert raised.value.code == "LOWER_CANVAS_RUN_LOCAL_PROVIDER_REQUIRED"


def test_preflight_router_registers_route():
    router = create_lower_canvas_router(SimpleNamespace(), lambda *args, **kwargs: None)
    routes = {(route.path, frozenset(getattr(route, "methods", ()) or ()))
              for route in router.routes if getattr(route, "path", None)}
    assert ("/projects/{nid}/studio/lower-canvas/{kind}/runs/preflight", frozenset({"POST"})) in routes
