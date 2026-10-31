"""HTTP-level lower-canvas run over a real localhost fake ComfyUI server.

This exercises the mounted application routes, middleware allowlist, project
session authority, the configured-provider transport, synchronous /prompt →
/history → /view execution, and real asset writeback. No model/GPU is used.
"""
from __future__ import annotations

import json
import subprocess
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from test_studio_asset_query import rig, shared_scope  # noqa: F401  (pytest fixtures)

pytestmark = pytest.mark.file_backend_only

OBJECT_INFO = {
    "LoadImage": {"input": {"required": {"image": [["server.png", "other.png"]]}},
                  "output": ["IMAGE"], "output_name": ["IMAGE"], "category": "image",
                  "display_name": "Load Image"},
    "MockOutput": {"input": {"optional": {"images": ["IMAGE"]}}, "output": [], "output_node": True,
                   "category": "test", "display_name": "Mock Output"},
}


def png_bytes() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (8, 8), (10, 20, 30)).save(buffer, format="PNG")
    return buffer.getvalue()


class FakeComfyHandler(BaseHTTPRequestHandler):
    media_bytes = png_bytes()
    media_type = "image/png"
    prompts: list[dict] = []
    uploads: list[dict] = []

    def log_message(self, *_args):
        pass

    def _json(self, value, status=200):
        body = json.dumps(value).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/object_info":
            return self._json(OBJECT_INFO)
        if self.path.startswith("/history/"):
            return self._json({"p1": {"status": {"status_str": "success"},
                "outputs": {"node1": {"images": [{"filename": "mock.png", "subfolder": "", "type": "output"}]}}}})
        if self.path.startswith("/view"):
            self.send_response(200)
            self.send_header("Content-Type", self.media_type)
            self.send_header("Content-Length", str(len(self.media_bytes)))
            self.end_headers()
            self.wfile.write(self.media_bytes)
            return
        self._json({"error": "not found"}, 404)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        if self.path == "/upload/image":
            self.uploads.append({"length": len(body), "content_type": self.headers.get("Content-Type", "")})
            return self._json({"name": "uploaded.png", "subfolder": "", "type": "input"})
        if self.path != "/prompt":
            return self._json({"error": "not found"}, 404)
        payload = json.loads(body)
        self.prompts.append(payload)
        prompt = payload.get("prompt")
        if not isinstance(prompt, dict) or prompt.get("node1", {}).get("class_type") != "MockOutput":
            return self._json({"error": "bad prompt"}, 400)
        self._json({"prompt_id": "p1"})


@pytest.fixture
def fake_comfy():
    FakeComfyHandler.prompts = []
    FakeComfyHandler.uploads = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), FakeComfyHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=5)


def mp4_bytes() -> bytes:
    import shutil
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        pytest.skip("ffmpeg not available")
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "result.mp4"
        completed = subprocess.run([ffmpeg, "-y", "-f", "lavfi", "-i", "color=c=black:s=2x2:d=0.2",
            "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(path)],
            capture_output=True, timeout=60)
        if completed.returncode != 0 or not path.exists():
            pytest.skip("ffmpeg could not encode a synthetic mp4")
        return path.read_bytes()


@pytest.fixture
def fake_comfy_video():
    class VideoHandler(FakeComfyHandler):
        media_bytes = mp4_bytes()
        media_type = "video/mp4"
    FakeComfyHandler.prompts = []
    FakeComfyHandler.uploads = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), VideoHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=5)


def test_lower_canvas_run_over_http_with_real_asset_writeback(rig, monkeypatch, tmp_path, fake_comfy):
    from app.authorization import AuthorizationScope, ModalityDomain, PermissionAssignment, ScopeKind

    scope, headers = shared_scope(rig)
    grant_scope = AuthorizationScope(ScopeKind.PROJECT, "query-workspace", rig.nid)
    rig.grants.assign_permission(PermissionAssignment("e2e-write", "reader", "domain.write",
        ModalityDomain.NOVEL, grant_scope, "fixture"))
    path = tmp_path / "asset-providers.json"
    path.write_text(json.dumps({"comfy": {"endpoint": fake_comfy, "api_style": "comfyui",
        "enabled": True, "local": True, "default_model": "", "requires_credential": False}}), encoding="utf-8")
    monkeypatch.setenv("ASSET_PROVIDER_CONFIG_PATH", str(path))
    base = f"/api/projects/{rig.nid}/studio/lower-canvas/image"

    draft = {"nodes": [{"id": "node1", "t": "MockOutput", "x": 0, "y": 0, "title": "output"}], "edges": []}
    saved = rig.client.put(base, headers=headers, json={"expected_version": 0, "graph": draft})
    assert saved.status_code == 200, saved.text
    assert saved.json()["version"] == 1

    info = rig.client.get("/api/comfy/object_info", headers=headers)
    assert info.status_code == 200, info.text
    assert "MockOutput" in info.json()

    quote_response = rig.client.post(f"{base}/runs/preflight", headers=headers,
        json={"expected_version": 1})
    assert quote_response.status_code == 200, quote_response.text
    quote = quote_response.json()
    assert quote["node_count"] == 1 and quote["output_nodes"] == ["node1"]
    assert quote["execution"] == "NOT_DISPATCHED"

    run_response = rig.client.post(f"{base}/runs", headers=headers,
        json={"expected_version": 1, "quote_id": quote["quote_id"], "quote_digest": quote["quote_digest"]})
    assert run_response.status_code == 200, run_response.text
    run = run_response.json()
    assert run["status"] == "COMPLETED", run
    assert run["error"] is None and len(run["assets"]) == 1
    assert FakeComfyHandler.prompts and FakeComfyHandler.prompts[0]["prompt"]["node1"]["class_type"] == "MockOutput"

    fetched = rig.client.get(f"{base}/runs/{run['id']}", headers=headers)
    assert fetched.status_code == 200, fetched.text
    assert fetched.json()["status"] == "COMPLETED"

    asset_id = run["assets"][0]["id"]
    download = rig.client.get(f"/api/projects/{rig.nid}/studio/assets/{asset_id}/download", headers=headers)
    assert download.status_code == 200, download.text
    assert download.content == FakeComfyHandler.media_bytes
    assets = rig.client.get(f"/api/projects/{rig.nid}/studio/assets", headers=headers)
    assert assets.status_code == 200, assets.text
    assert any(row["id"] == asset_id for row in assets.json()["items"])


def test_lower_canvas_and_node_library_routes_are_admitted():
    from app.creative.workspace_api import is_independent_studio_route
    root = "/api/projects/n/studio"
    assert is_independent_studio_route("GET", root + "/lower-canvas/image")
    assert is_independent_studio_route("GET", root + "/lower-canvas/image/runs/lcr_x")
    assert is_independent_studio_route("PUT", root + "/lower-canvas/image")
    assert is_independent_studio_route("POST", root + "/lower-canvas/image/runs/preflight")
    assert is_independent_studio_route("POST", root + "/lower-canvas/image/runs")
    assert is_independent_studio_route("GET", root + "/assets")
    assert is_independent_studio_route("GET", root + "/assets/aid/download")


def test_lower_canvas_video_result_is_written_and_downloadable(rig, monkeypatch, tmp_path, fake_comfy_video):
    from app.authorization import AuthorizationScope, ModalityDomain, PermissionAssignment, ScopeKind

    scope, headers = shared_scope(rig)
    grant_scope = AuthorizationScope(ScopeKind.PROJECT, "query-workspace", rig.nid)
    rig.grants.assign_permission(PermissionAssignment("e2e-write-video", "reader", "domain.write",
        ModalityDomain.NOVEL, grant_scope, "fixture"))
    path = tmp_path / "asset-providers.json"
    path.write_text(json.dumps({"comfy": {"endpoint": fake_comfy_video, "api_style": "comfyui",
        "enabled": True, "local": True, "default_model": "", "requires_credential": False}}), encoding="utf-8")
    monkeypatch.setenv("ASSET_PROVIDER_CONFIG_PATH", str(path))
    base = f"/api/projects/{rig.nid}/studio/lower-canvas/image"
    draft = {"nodes": [{"id": "node1", "t": "MockOutput", "x": 0, "y": 0, "title": "output"}], "edges": []}
    assert rig.client.put(base, headers=headers, json={"expected_version": 0, "graph": draft}).status_code == 200
    quote = rig.client.post(f"{base}/runs/preflight", headers=headers, json={"expected_version": 1})
    assert quote.status_code == 200, quote.text
    quote = quote.json()
    run = rig.client.post(f"{base}/runs", headers=headers, json={"expected_version": 1,
        "quote_id": quote["quote_id"], "quote_digest": quote["quote_digest"]})
    assert run.status_code == 200, run.text
    run = run.json()
    assert run["status"] == "COMPLETED" and run["error"] is None
    assert run["assets"][0]["kind"] == "video"
    asset_id = run["assets"][0]["id"]
    download = rig.client.get(f"/api/projects/{rig.nid}/studio/assets/{asset_id}/download", headers=headers)
    assert download.status_code == 200, download.text
    assert download.headers["content-type"].startswith("video/")
    assert len(download.content) > 100


def test_lower_canvas_run_uploads_bound_studio_asset(rig, monkeypatch, tmp_path, fake_comfy):
    import base64
    from app.authorization import AuthorizationScope, ModalityDomain, PermissionAssignment, ScopeKind

    scope, headers = shared_scope(rig)
    grant_scope = AuthorizationScope(ScopeKind.PROJECT, "query-workspace", rig.nid)
    rig.grants.assign_permission(PermissionAssignment("e2e-write-asset", "reader", "domain.write",
        ModalityDomain.NOVEL, grant_scope, "fixture"))
    with rig.workspace._asset_scope(rig.nid, scope):
        asset = rig.workspace.assets.create(rig.nid, "studio-ref.png",
            base64.b64encode(png_bytes()).decode("ascii"), "image/png", "image",
            branch_id=scope["branch_id"])
    path = tmp_path / "asset-providers.json"
    path.write_text(json.dumps({"comfy": {"endpoint": fake_comfy, "api_style": "comfyui",
        "enabled": True, "local": True, "default_model": "", "requires_credential": False}}), encoding="utf-8")
    monkeypatch.setenv("ASSET_PROVIDER_CONFIG_PATH", str(path))
    base = f"/api/projects/{rig.nid}/studio/lower-canvas/image"
    draft = {"nodes": [
        {"id": "load1", "t": "LoadImage", "x": 0, "y": 0, "title": "load", "input_assets": {"image": asset["id"]}},
        {"id": "node1", "t": "MockOutput", "x": 200, "y": 0, "title": "out"}],
      "edges": [{"id": "e1", "a": "load1", "as": 0, "b": "node1", "bs": 0}]}
    assert rig.client.put(base, headers=headers, json={"expected_version": 0, "graph": draft}).status_code == 200
    quote = rig.client.post(f"{base}/runs/preflight", headers=headers, json={"expected_version": 1})
    assert quote.status_code == 200, quote.text
    quote = quote.json()
    assert quote["input_asset_count"] == 1
    run = rig.client.post(f"{base}/runs", headers=headers, json={"expected_version": 1,
        "quote_id": quote["quote_id"], "quote_digest": quote["quote_digest"]})
    assert run.status_code == 200, run.text
    run = run.json()
    assert run["status"] == "COMPLETED", run
    assert FakeComfyHandler.uploads and FakeComfyHandler.uploads[0]["length"] > 100
    prompt = FakeComfyHandler.prompts[-1]["prompt"]
    assert prompt["load1"]["inputs"]["image"] == "uploaded.png"
    assert prompt["load1"]["class_type"] == "LoadImage"
