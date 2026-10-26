"""Real loopback HTTP and process restart on unchanged application assembly.

The only synthetic component is a local Automatic1111 HTTP provider returning
a deterministic PNG. No owner, authorization function or app service is patched.
"""
from contextlib import contextmanager
import base64
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
from threading import Event, Thread
import time

import httpx
from PIL import Image
import pytest

pytestmark = pytest.mark.file_backend_only


def unused_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


@contextmanager
def original_application(root, run, config, log_name):
    port = unused_port()
    env = os.environ.copy()
    for key in tuple(env):
        if key.endswith("_API_KEY") or key in {"DATABASE_URL", "TEST_POSTGRES_DATABASE_URL", "E2E_DATABASE_URL"}:
            env.pop(key, None)
    for folder in ("home", "xdg", "data", "tmp", "appdata", "localappdata"):
        (run / folder).mkdir(parents=True, exist_ok=True)
    env.update(PROJECT_ROOT=str(root), PYTHONPATH=str(root), HOME=str(run / "home"),
        USERPROFILE=str(run / "home"), APPDATA=str(run / "appdata"), LOCALAPPDATA=str(run / "localappdata"),
        XDG_CONFIG_HOME=str(run / "xdg/config"), XDG_DATA_HOME=str(run / "xdg/data"), XDG_CACHE_HOME=str(run / "xdg/cache"),
        NOVEL_DATA_PATH=str(run / "data"), TMPDIR=str(run / "tmp"), TMP=str(run / "tmp"), TEMP=str(run / "tmp"),
        STORAGE_BACKEND="file", MOCK_PROVIDER="true", ENABLE_CLOUD="false", ENABLE_PACKAGED_RUNTIME="false",
        ENABLE_COLLABORATION_RUNTIME="false", ENABLE_EXPERIMENTAL_FILE_KEYED_GENERATION="false",
        CREDENTIAL_VAULT_BACKEND="memory", CREATION_PROFILE="LOCAL_ONLY", ASSET_PROVIDER_CONFIG_PATH=str(config),
        EXPERIMENTAL_FEATURES="narrative_production_v2,asset_lineage_v2,ai_execution_v2,model_broker_v2,author_context_inspector_v2",
        COLLABORATION_DEV_SESSIONS_JSON=json.dumps([{"token": "synthetic-studio-host", "session_id": "process-session",
            "client_id": "process-client", "actor_id": "local-author", "workspace_id": "process-workspace"}]))
    log_path = run / log_name
    with log_path.open("w", encoding="utf-8") as log:
        process = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1",
            "--port", str(port), "--no-proxy-headers", "--log-level", "warning"], cwd=root, env=env,
            stdout=log, stderr=subprocess.STDOUT)
        try:
            with httpx.Client(base_url=f"http://127.0.0.1:{port}", trust_env=False, timeout=30,
                              headers={"X-Session-Token": "synthetic-studio-host"}) as client:
                deadline = time.monotonic() + 35
                while True:
                    assert process.poll() is None, log_path.read_text(encoding="utf-8")
                    try:
                        if client.get("/health").status_code == 200:
                            break
                    except httpx.TransportError:
                        pass
                    assert time.monotonic() < deadline, "Original application did not become ready"
                    Event().wait(0.05)  # Startup readiness only; never used to arrange a race.
                yield client
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)


def checked(response, status=200):
    assert response.status_code == status, response.text
    return response.json()


@pytest.mark.parametrize("prefix", ["/api", "/api/v1"])
def test_original_http_assembly_candidate_adoption_survives_process_restart(tmp_path, prefix):
    root = Path(__file__).resolve().parents[1]
    run = tmp_path / "original-process"
    run.mkdir()
    image = BytesIO()
    Image.new("RGB", (64, 64), (30, 90, 160)).save(image, format="PNG")
    encoded = base64.b64encode(image.getvalue()).decode()
    calls = []

    class MockProvider(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            payload = json.dumps([{"title": "synthetic.safetensors"}]).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def do_POST(self):
            assert self.path == "/sdapi/v1/txt2img"
            calls.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
            payload = json.dumps({"images": [encoded]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    server = ThreadingHTTPServer(("127.0.0.1", 0), MockProvider)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    config = run / "providers.json"
    config.write_text(json.dumps({"automatic1111": {"endpoint": f"http://127.0.0.1:{server.server_port}",
        "default_model": "synthetic.safetensors", "api_style": "automatic1111", "local": True,
        "enabled": True, "requires_credential": False}}), encoding="utf-8")
    try:
        with original_application(root, run, config, "first-process.log") as client:
            novel = checked(client.post(prefix + "/novels", json={"title": "Synthetic process reopen"}), 201)
            nid = novel["id"]
            base = f"{prefix}/projects/{nid}/studio"
            creative = f"{prefix}/novels/{nid}/experimental/creative"
            checked(client.post(base + "/activate"))
            document = checked(client.post(creative + "/documents", json={"mode": "STORYBOARD", "title": "Synthetic board",
                "source_independent": True, "scenes": [{"id": "scene-one", "sequence": 1, "heading": "Courtyard"}],
                "shots": [{"id": "shot-one", "number": 1, "scene_id": "scene-one", "frame_prompt": "A blue courtyard"}]}), 201)
            doc_url = creative + "/documents/" + document["id"]
            board = checked(client.get(doc_url + "/storyboard"))
            shot = board["shots"][0]
            pin = {"expected_version": board["document_snapshot"]["version"], "shot_version": shot["shot_version"], "shot_digest": shot["shot_digest"]}
            prepared = checked(client.post(doc_url + "/shots/shot-one/image-request", json={**pin, "request_id": "process-shot-one",
                "provider": {"operation_id": "m5.image.t2i", "provider_id": "automatic1111", "model_id": "synthetic.safetensors"},
                "parameters": {"width": 64, "height": 64, "steps": 1, "seed": 42}}))
            preview = checked(client.post(base + "/production/preview", json=prepared["command"]))
            creation = {"command": prepared["command"], "reviewed_preview_digest": preview["preview_digest"]}
            row = checked(client.post(base + "/production/jobs", json=creation), 201)
            assert calls == []
            assert checked(client.post(base + "/production/jobs", json=creation), 201)["id"] == row["id"]
            job_url = base + "/production/jobs/image/" + row["id"]
            action = {"expected_version": row["version"], "expected_request_digest": row["request_digest"]}
            row = checked(client.post(job_url + "/execute", json=action))
            assert row["status"] == "AWAITING_REVIEW" and len(calls) == 1
            assert checked(client.get(doc_url + "/storyboard"))["shots"][0]["image_asset"] is None
            row = checked(client.post(job_url + "/review", json={"expected_version": row["version"],
                "expected_request_digest": row["request_digest"], "reviewed_output_digest": row["output_candidate"]["digest"]}))
            asset = {"asset_id": row["output_candidate"]["id"], "version": row["approved_asset_version"],
                "digest": row["output_candidate"]["digest"], "kind": "image"}
            bound = checked(client.post(doc_url + "/shots/shot-one/image-binding", json={**pin, "asset": asset}))
            assert bound["shots"][0]["image_asset"] == asset
        with original_application(root, run, config, "reopened-process.log") as client:
            assert checked(client.get(doc_url + "/storyboard")) == bound
            alias_prefix = "/api/v1" if prefix == "/api" else "/api"
            alias = alias_prefix + doc_url[len(prefix):]
            assert checked(client.get(alias + "/storyboard")) == bound
            assert checked(client.get(job_url))["status"] == "APPROVED"
            assert len(calls) == 1
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
