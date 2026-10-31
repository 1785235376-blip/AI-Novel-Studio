"""Lower-canvas draft API + ComfyUI object_info proxy (synthetic, no network)."""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.creative.comfy_node_library import ComfyNodeLibraryError
from app.creative.lower_canvas_api import (
    LowerCanvasSave,
    LowerCanvasVersionConflict,
    create_lower_canvas_router,
    read_lower_canvas,
    save_lower_canvas,
)


def scope(nid="novel-lower"):
    return {"mode": "local", "novel_id": nid}


def graph(nodes=None, edges=None):
    return {
        "nodes": nodes if nodes is not None else [
            {"id": "n1", "t": "CheckpointLoaderSimple", "x": 10, "y": 20, "title": "Load"},
            {"id": "n2", "t": "KSampler", "x": 300, "y": 20, "title": "Sample"},
        ],
        "edges": edges if edges is not None else [
            {"id": "e1", "a": "n1", "as": 0, "b": "n2", "bs": 0},
        ],
    }


@pytest.fixture
def service(tmp_path):
    from app.experimental.store import ExperimentalStore
    return SimpleNamespace(store=ExperimentalStore(tmp_path / "data"))


def save_body(**overrides):
    values = {"expected_version": 0, "graph": graph()}
    values.update(overrides)
    return LowerCanvasSave.model_validate(values)


def test_lower_canvas_roundtrip_preserves_aliases_and_versions(service):
    nid, sc = "novel-lower", scope()
    empty = read_lower_canvas(service, nid, sc, "image")
    assert empty == {**empty, "kind": "image", "version": 0,
                     "graph": {"nodes": [], "edges": []}, "execution": "NOT_IMPLEMENTED"}

    saved = save_lower_canvas(service, nid, sc, "local-author", "image", save_body())
    assert saved["version"] == 1 and saved["updated_by"] == "local-author"
    assert saved["graph"] == graph() and saved["graph"]["edges"][0]["as"] == 0
    assert saved["execution"] == "NOT_IMPLEMENTED"

    read = read_lower_canvas(service, nid, sc, "image")
    assert read["version"] == 1 and read["graph"] == graph()

    # image and video are independent rows.
    assert read_lower_canvas(service, nid, sc, "video")["version"] == 0


def test_lower_canvas_optimistic_conflict(service):
    nid, sc = "novel-lower", scope()
    save_lower_canvas(service, nid, sc, "a", "image", save_body())
    with pytest.raises(LowerCanvasVersionConflict) as raised:
        save_lower_canvas(service, nid, sc, "a", "image", save_body())
    assert raised.value.current_version == 1


@pytest.mark.parametrize(("body", "code"), [
    ({"expected_version": 0, "graph": {"nodes": [{"id": "x", "t": "A", "x": 0, "y": 0, "title": ""},
                                                  {"id": "x", "t": "B", "x": 0, "y": 0, "title": ""}],
                                      "edges": []}}, "LOWER_CANVAS_NODE_ID_DUPLICATE"),
    ({"expected_version": 0, "graph": {"nodes": [{"id": "x", "t": "A", "x": 0, "y": 0, "title": ""}],
                                      "edges": [{"id": "e", "a": "x", "as": 0, "b": "missing", "bs": 0}]}},
     "LOWER_CANVAS_EDGE_ENDPOINT_MISSING"),
    ({"expected_version": 0, "graph": {"nodes": [{"id": "x", "t": "A", "x": 0, "y": 0, "title": ""}],
                                      "edges": [{"id": "e", "a": "x", "as": 0, "b": "x", "bs": 0}]}},
     "LOWER_CANVAS_EDGE_SELF_LOOP"),
])
def test_lower_canvas_rejects_invalid_graphs(service, body, code):
    with pytest.raises(HTTPException) as raised:
        save_lower_canvas(service, "novel-lower", scope(), "a", "image",
            LowerCanvasSave.model_validate(body))
    assert raised.value.status_code == 400
    assert raised.value.detail["code"] == code


def test_lower_canvas_rejects_unknown_kind(service):
    with pytest.raises(HTTPException) as raised:
        read_lower_canvas(service, "novel-lower", scope(), "audio")
    assert raised.value.status_code == 404
    assert raised.value.detail["code"] == "LOWER_CANVAS_KIND_INVALID"


def test_lower_canvas_router_registers_get_and_put():
    calls = []
    router = create_lower_canvas_router(SimpleNamespace(), lambda *args: calls.append(args))
    routes = {(route.path, frozenset(getattr(route, "methods", ()) or ()))
              for route in router.routes if getattr(route, "path", None)}
    assert ("/projects/{nid}/studio/lower-canvas/{kind}", frozenset({"GET"})) in routes
    assert ("/projects/{nid}/studio/lower-canvas/{kind}", frozenset({"PUT"})) in routes


def test_object_info_proxy_passthrough_headers_whitelist_and_meta(monkeypatch):
    from app import api as api_module

    payload = {"KSampler": {"input": {"required": {}}, "output": ["LATENT"]},
               "SaveImage": {"input": {"required": {}}, "output": []},
               "Other": {"input": {}, "output": []}}

    def fake_fetch(**kwargs):
        return {"provider_id": "localcomfy", "available_providers": ["localcomfy"],
                "endpoint_origin": "http://127.0.0.1:8188",
                "observed_at": "2026-10-31T00:00:00+00:00",
                "source_version": "a" * 64, "payload": payload, "raw_bytes": 123}

    monkeypatch.setattr("app.creative.comfy_node_library.fetch_comfyui_object_info", fake_fetch)
    response = api_module.comfy_object_info(provider_id=None, nodes="KSampler,SaveImage,Missing")
    assert response.status_code == 200
    body = json.loads(response.body)
    assert list(body) == ["KSampler", "SaveImage"]
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-comfy-source-version"] == "a" * 64
    assert response.headers["x-comfy-fetched-at"] == "2026-10-31T00:00:00+00:00"
    assert response.headers["x-comfy-provider-id"] == "localcomfy"

    meta = json.loads(api_module.comfy_object_info(provider_id=None, nodes=None, meta=True).body)
    assert meta["object_info"] == payload and meta["node_count"] == 3
    assert meta["execution"] == "NOT_IMPLEMENTED" and meta["source_version"] == "a" * 64


def test_object_info_proxy_maps_provider_failure_to_503(monkeypatch):
    from app import api as api_module

    def unavailable(**kwargs):
        raise ComfyNodeLibraryError("COMFYUI_NODE_LIBRARY_UNAVAILABLE", status=503)

    monkeypatch.setattr("app.creative.comfy_node_library.fetch_comfyui_object_info", unavailable)
    with pytest.raises(HTTPException) as raised:
        api_module.comfy_object_info(provider_id=None, nodes=None)
    assert raised.value.status_code == 503
    assert raised.value.detail["code"] == "comfy_unavailable"


def test_global_comfy_object_info_route_is_mounted_and_fails_closed(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app

    monkeypatch.setenv("ASSET_PROVIDER_CONFIG_PATH", str(tmp_path / "missing-providers.json"))
    response = TestClient(app).get("/api/comfy/object_info")
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "comfy_unavailable"

