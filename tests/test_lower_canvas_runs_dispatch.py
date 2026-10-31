"""Synchronous lower-canvas dispatch against a fake local ComfyUI (no network)."""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from app.creative.lower_canvas_api import create_lower_canvas_router
from app.creative.lower_canvas_runs import (
    LowerCanvasRunError,
    dispatch_lower_canvas_run,
    get_lower_canvas_run,
)
from test_lower_canvas_runs_preflight import (
    configure_comfy,
    object_info,
    save_draft,
)

PNG = b"\x89PNG\r\n\x1a\n" + b"fake-bounded-image-bytes"


class Resp:
    def __init__(self, payload=None, *, status=200, content=None):
        self.status_code = status
        self._payload = payload
        self.content = content if content is not None else b""

    def json(self):
        return self._payload


class FakeComfy:
    def __init__(self, history_status="success"):
        self.history_status = history_status
        self.get_calls = []
        self.post_calls = []

    def get(self, url, **kwargs):
        self.get_calls.append((url, kwargs))
        if url.endswith("/object_info"):
            return Resp(object_info(), content=json.dumps(object_info()).encode("utf-8"))
        if "/history/" in url:
            if self.history_status == "failed":
                return Resp({"p1": {"status": {"status_str": "error"}, "outputs": {}}})
            return Resp({"p1": {"status": {"status_str": "success"},
                "outputs": {"save": {"images": [{"filename": "out.png", "subfolder": "", "type": "output"}]}}}})
        if url.endswith("/view"):
            return Resp(content=PNG)
        return Resp({}, status=404)

    def post(self, url, **kwargs):
        self.post_calls.append((url, kwargs))
        if url.endswith("/prompt"):
            return Resp({"prompt_id": "p1"})
        return Resp({}, status=404)


def dispatch_fixture(tmp_path, monkeypatch, fake, writer=None):
    from app.experimental.store import ExperimentalStore
    configure_comfy(tmp_path, monkeypatch)
    service = SimpleNamespace(store=ExperimentalStore(tmp_path / "data"))
    nid, scope = save_draft(service)
    preflight = __import__("app.creative.lower_canvas_runs", fromlist=["preflight_lower_canvas_run"]).preflight_lower_canvas_run
    quote = preflight(service, nid, scope, "author", "image", expected_version=1,
                      provider_id="comfy", transport_factory=lambda endpoint: fake)
    result = dispatch_lower_canvas_run(service, nid, scope, "author", "image",
        expected_version=1, quote_id=quote["quote_id"], quote_digest=quote["quote_digest"], provider_id="comfy",
        transport_factory=lambda endpoint: fake, asset_writer=writer or (lambda image: {
            "id": "asset-" + image["sha256"][:8], "filename": image["filename"],
            "media_type": image["media_type"], "sha256": image["sha256"], "size": image["size"]}),
        poll_interval=0)
    return service, nid, scope, quote, result


def test_dispatch_persists_one_run_and_writes_assets(tmp_path, monkeypatch):
    fake = FakeComfy()
    service, nid, scope, quote, result = dispatch_fixture(tmp_path, monkeypatch, fake)
    assert result["contract"] == "studio-lower-canvas-run/1"
    assert result["status"] == "COMPLETED" and result["error"] is None
    assert result["quote_digest"] == quote["quote_digest"]
    assert result["assets"][0]["id"].startswith("asset-") and result["assets"][0]["size"] == len(PNG)
    assert [call[0] for call in fake.post_calls] == ["http://127.0.0.1:8188/prompt"]
    stored = get_lower_canvas_run(service, nid, scope, "image", result["id"])
    assert stored["status"] == "COMPLETED" and stored["assets"] == result["assets"]

    # The same quote digest is idempotent: no second /prompt submit.
    again = dispatch_lower_canvas_run(service, nid, scope, "author", "image",
        expected_version=1, quote_id=quote["quote_id"], quote_digest=quote["quote_digest"], provider_id="comfy",
        transport_factory=lambda endpoint: fake, asset_writer=lambda image: {"id": "never"})
    assert again["id"] == result["id"] and again["status"] == "COMPLETED"
    assert len(fake.post_calls) == 1


def test_dispatch_reports_failed_comfyui_run_without_fake_assets(tmp_path, monkeypatch):
    fake = FakeComfy(history_status="failed")
    written = []
    service, nid, scope, quote, result = dispatch_fixture(
        tmp_path, monkeypatch, fake, writer=lambda image: written.append(image) or {"id": "x"})
    assert result["status"] == "FAILED"
    assert result["error"]["code"] == "LOWER_CANVAS_COMFYUI_EXECUTION_FAILED"
    assert result["assets"] == [] and written == []
    stored = get_lower_canvas_run(service, nid, scope, "image", result["id"])
    assert stored["status"] == "FAILED"


def test_dispatch_rejects_stale_quote_before_touching_comfyui(tmp_path, monkeypatch):
    from app.experimental.store import ExperimentalStore
    configure_comfy(tmp_path, monkeypatch)
    service = SimpleNamespace(store=ExperimentalStore(tmp_path / "data"))
    nid, scope = save_draft(service)
    fake = FakeComfy()
    with pytest.raises(LowerCanvasRunError) as raised:
        dispatch_lower_canvas_run(service, nid, scope, "author", "image",
            expected_version=1, quote_id="lcq_" + "0" * 24, quote_digest="0" * 64, provider_id="comfy",
            transport_factory=lambda endpoint: fake)
    assert raised.value.code == "LOWER_CANVAS_RUN_QUOTE_STALE"
    assert fake.post_calls == []


def test_dispatch_and_get_routes_registered():
    router = create_lower_canvas_router(SimpleNamespace(), lambda *args, **kwargs: None)
    routes = {(route.path, frozenset(getattr(route, "methods", ()) or ()))
              for route in router.routes if getattr(route, "path", None)}
    assert ("/projects/{nid}/studio/lower-canvas/{kind}/runs", frozenset({"POST"})) in routes
    assert ("/projects/{nid}/studio/lower-canvas/{kind}/runs/{run_id}", frozenset({"GET"})) in routes
