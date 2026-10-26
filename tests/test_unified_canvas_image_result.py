"""Original File/HTTP Canvas result adoption with synthetic local provider bytes.

Original owner implementations, graph invoker, authorization functions and
approval transitions remain in use. The process fixture returns one generated
PNG through original A1111; collaboration uses fresh temporary owner instances.
"""
from contextlib import ExitStack, contextmanager
from copy import deepcopy
from hashlib import sha256
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path
from threading import Thread
from types import SimpleNamespace
import base64
import json

import pytest
from PIL import Image

from test_studio_process_reopen_v2 import original_application
from test_studio_asset_query import rig, shared_scope


pytestmark = pytest.mark.file_backend_only


def record(e, label, response, status=200):
    try:
        body = response.json()
    except ValueError:
        body = {"byte_count": len(response.content), "sha256": sha256(response.content).hexdigest()}
    e.receipts.append({"label": label, "method": response.request.method,
                       "url": str(response.request.url), "status": response.status_code, "body": body})
    (e.run / "http-receipts.json").write_text(json.dumps(e.receipts, indent=2), encoding="utf-8")
    assert response.status_code == status, f"{label}: {response.status_code}: {response.text}"
    return body


@contextmanager
def synthetic_provider(run):
    image = BytesIO()
    Image.new("RGB", (64, 64), (37, 107, 173)).save(image, format="PNG")
    png = image.getvalue()
    calls = []
    encoded = base64.b64encode(png).decode("ascii")

    class Provider(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def reply(self, value):
            body = json.dumps(value).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            self.reply([{"title": "synthetic.safetensors"}])

        def do_POST(self):
            assert self.path == "/sdapi/v1/txt2img"
            calls.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
            (run / "provider-calls.json").write_text(json.dumps(calls, indent=2), encoding="utf-8")
            self.reply({"images": [encoded]})

    server = ThreadingHTTPServer(("127.0.0.1", 0), Provider)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    config = run / "providers.json"
    config.write_text(json.dumps({"automatic1111": {
        "endpoint": f"http://127.0.0.1:{server.server_port}",
        "default_model": "synthetic.safetensors", "api_style": "automatic1111",
        "local": True, "enabled": True, "requires_credential": False}}), encoding="utf-8")
    try:
        yield config, png, calls
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def prepare_approved_node(e, client, *, existing_nid=None, scope=None):
    e.client = client
    if existing_nid is None:
        project = record(e, "novel.create", client.post(e.prefix + "/novels",
            json={"title": "Synthetic original canvas image adoption"}), 201)
        e.nid = project["id"]
    else:
        e.nid = existing_nid
    e.base = f"{e.prefix}/projects/{e.nid}/studio"
    record(e, "studio.activate", client.post(e.base + "/activate"))
    overview = record(e, "studio.overview", client.get(e.base))
    e.incarnation = overview["project"]["incarnation"]
    e.target = record(e, "canvas.create", client.post(e.base + "/canvas-views", json={
        "request_id": "original-node-empty-target", "expected_version": 0,
        "definition": {"schema_version": 1, "title": "Original explicit image node", "cards": [],
                       "viewport": {"x": 0, "y": 0, "zoom": 1}}}), 201)
    e.canvas_url = e.base + "/canvas-views/" + e.target["id"]
    prompt = "Synthetic image node: one blue square, no model inference"
    e.binding = {"contract": "studio-canvas-image-node/1", "project_id": e.nid,
        "scope": deepcopy(scope or {"mode": "local", "novel_id": e.nid}), "incarnation": e.incarnation,
        "canvas_id": e.target["id"], "canvas_version": e.target["version"],
        "canvas_digest": e.target["definition_digest"], "node_id": "generation-node-one",
        "title": "Original explicit image node", "position": {"x": 48, "y": 80},
        "prompt_digest": sha256(prompt.encode("utf-8")).hexdigest()}
    command = {"operation_id": "m5.image.t2i", "request_id": "original-node-generation",
        "provider_id": "automatic1111", "model_id": "synthetic.safetensors", "prompt": prompt,
        "parameters": {"width": 64, "height": 64, "steps": 1, "seed": 42},
        "source_snapshots": [], "allow_cloud": False,
        "license_note": "Self-created synthetic PNG; local Mock provider only",
        "canvas_image_node": e.binding}
    preview = record(e, "production.preview", client.post(e.base + "/production/preview", json=command))
    assert preview["automatic_dispatch"] is False and e.calls == []
    queued = record(e, "production.create", client.post(e.base + "/production/jobs", json={
        "command": command, "reviewed_preview_digest": preview["preview_digest"]}), 201)
    assert queued["status"] == "QUEUED" and e.calls == []
    e.job_url = e.base + "/production/jobs/image/" + queued["id"]
    candidate = record(e, "production.execute", client.post(e.job_url + "/execute", json={
        "expected_version": queued["version"], "expected_request_digest": queued["request_digest"]}))
    assert candidate["status"] == "AWAITING_REVIEW" and len(e.calls) == 1
    binary = client.get(e.job_url + "/candidate")
    record(e, "production.candidate", binary)
    assert binary.content == e.png
    assert sha256(e.png).hexdigest() == candidate["output_candidate"]["digest"]
    e.job = record(e, "production.review", client.post(e.job_url + "/review", json={
        "expected_version": candidate["version"], "expected_request_digest": candidate["request_digest"],
        "reviewed_output_digest": candidate["output_candidate"]["digest"]}))
    assert e.job["status"] == "APPROVED" and len(e.calls) == 1
    e.pin = {"asset_id": e.job["output_candidate"]["id"], "version": e.job["approved_asset_version"],
             "digest": e.job["output_candidate"]["digest"], "kind": "image"}
    e.asset_url = e.base + "/assets/" + e.pin["asset_id"]
    e.asset = record(e, "asset.formal", client.get(e.asset_url))
    assert (e.asset["id"], e.asset["version"], e.asset["sha256"]) == (
        e.pin["asset_id"], e.pin["version"], e.pin["digest"])
    e.body = {"confirmed": True, "expected_incarnation": e.incarnation,
        "expected_version": e.target["version"], "expected_definition_digest": e.target["definition_digest"],
        "job_id": e.job["id"], "job_version": e.job["version"],
        "job_request_digest": e.job["request_digest"], "asset": e.pin}


@pytest.fixture(params=["/api", "/api/v1"])
def approved_node(tmp_path, request):
    root = Path(__file__).resolve().parents[1]
    run = tmp_path / "original-canvas-process"
    run.mkdir()
    e = SimpleNamespace(root=root, run=run, prefix=request.param, receipts=[])
    with synthetic_provider(run) as (config, png, calls):
        e.config, e.png, e.calls = config, png, calls
        with ExitStack() as app_stack:
            client = app_stack.enter_context(original_application(root, run, config, "first-process.log"))
            e.stop_application = app_stack.close
            prepare_approved_node(e, client)
            yield e


def snapshot(e, label):
    return {"canvas": record(e, label + ".canvas", e.client.get(e.canvas_url)),
            "history": record(e, label + ".history", e.client.get(e.canvas_url + "/history")),
            "job": record(e, label + ".job", e.client.get(e.job_url)),
            "asset": record(e, label + ".asset", e.client.get(e.asset_url))}


def test_original_approved_image_first_backfill_and_reopen(approved_node):
    e = approved_node
    before = snapshot(e, "before")
    response = e.client.post(e.canvas_url + "/image-node-result", json=e.body)
    # Capture refusal evidence before the positive assertion, including unchanged
    # original durable owners. A baseline403 remains a real failing acceptance.
    if response.status_code != 200:
        record(e, "image-node-result.rejected", response, response.status_code)
        assert snapshot(e, "after-refusal") == before
        assert len(e.calls) == 1
    saved = record(e, "image-node-result.accepted", response)
    assert saved["version"] == e.target["version"] + 1
    assert saved["definition"]["cards"] == [{"id": e.binding["node_id"],
        "position": e.binding["position"], "asset": e.pin}]
    assert saved["definition"]["image_node_origin"] == {
        "contract": "studio-canvas-image-node-result/1", "target": e.binding,
        "job_id": e.job["id"], "job_version": e.job["version"],
        "job_request_digest": e.job["request_digest"], "asset": e.pin}
    after = snapshot(e, "after")
    replay = record(e, "image-node-result.exact-replay",
        e.client.post(e.canvas_url + "/image-node-result", json=e.body))
    assert replay == saved and snapshot(e, "after-replay") == after
    # End the original child process before opening the same durable state.
    e.stop_application()
    with original_application(e.root, e.run, e.config, "reopened-process.log") as reopened:
        assert record(e, "reopen.canvas", reopened.get(e.canvas_url)) == saved
        assert record(e, "reopen.job", reopened.get(e.job_url)) == e.job
        assert record(e, "reopen.asset", reopened.get(e.asset_url)) == e.asset
        alias = "/api/v1" if e.prefix == "/api" else "/api"
        assert record(e, "reopen.alias", reopened.get(alias + e.canvas_url[len(e.prefix):])) == saved
    assert len(e.calls) == 1


@pytest.mark.parametrize("field", ["expected_version", "expected_definition_digest", "expected_incarnation",
    "job_version", "job_request_digest", "asset_id", "asset_version", "asset_digest"])
def test_original_approved_image_rejects_changed_source_pin(approved_node, field):
    e = approved_node
    body = deepcopy(e.body)
    if field == "asset_id":
        body["asset"]["asset_id"] = "another-original-asset"
    elif field == "asset_version":
        body["asset"]["version"] += 1
    elif field == "asset_digest":
        body["asset"]["digest"] = "f" * 64
    elif field in {"expected_version", "job_version"}:
        body[field] += 1
    elif field == "expected_incarnation":
        body[field] = "file:00000000-0000-4000-8000-000000000000"
    else:
        body[field] = "f" * 64
    before = snapshot(e, "before-negative")
    record(e, "image-node-result.changed-" + field,
        e.client.post(e.canvas_url + "/image-node-result", json=body), 409)
    assert snapshot(e, "after-negative") == before
    assert len(e.calls) == 1


@pytest.fixture
def shared_approved_node(rig, monkeypatch):
    """Actual packaged Host plus collaboration authorities on temporary owners.

    Only owner instances are installed into the already mounted original app.
    Session issuance, middleware, HTTP executor/review and graph guards are real.
    """
    import httpx
    from app import dependencies, main
    from app.asset_providers import AssetProviderRegistry, Automatic1111ImageProvider
    from app.audio_production_store import AudioProductionStore
    from app.authorization import AuthorizationScope, ModalityDomain, PermissionAssignment, ScopeKind
    from app.creative.graph import CreativeGraphService
    from app.creative.production_execution import ProductionExecutionService
    from app.experimental import api as experimental_api
    from app.model_center.discovery_bridge import _LocalImageTransport
    from app.packaging.bootstrap_api import PackagedBootstrapRegistry
    from app.packaging.local_session_bootstrap import LocalSessionBootstrap, TrustedLocalIdentity
    from app.packaging.runtime_identity import RuntimeIdentity
    from app.services.image_job_service import ImageJobService
    from app.services.video_assembly_service import VideoAssemblyService
    from test_studio_backend_integration_v2 import NoCalls

    scope, _ = shared_scope(rig)
    monkeypatch.setenv("EXPERIMENTAL_FEATURES", "narrative_production_v2,asset_lineage_v2,ai_execution_v2,model_broker_v2,author_context_inspector_v2")
    object.__setattr__(rig.settings, "enable_packaged_runtime", True)
    grant_scope = AuthorizationScope(ScopeKind.PROJECT, "query-workspace", rig.nid)
    for permission in ("write", "review"):
        rig.grants.assign_permission(PermissionAssignment("node-" + permission, "reader", "domain." + permission,
            ModalityDomain.NOVEL, grant_scope, "fixture"))
    runtime = RuntimeIdentity.create()
    origin = "http://127.0.0.1:41831"
    manager = LocalSessionBootstrap(runtime=runtime, sessions=rig.sessions,
        trusted_identity=TrustedLocalIdentity("reader", "query-workspace"), expected_origin=origin)
    registry_owner = PackagedBootstrapRegistry()
    registry_owner.configure(manager)
    monkeypatch.setattr(main, "packaged_bootstrap_registry", registry_owner)
    monkeypatch.setattr(dependencies, "packaged_bootstrap_registry", registry_owner)
    issued = manager.exchange(bootstrap_secret=manager.take_launcher_secret(),
        runtime_instance_id=runtime.runtime_instance_id, origin=origin, remote_host="127.0.0.1")
    rig.client.headers.update({"X-Session-Token": issued.session_token, "X-Branch-Id": scope["branch_id"]})
    run = rig.root / "shared-original-canvas"
    run.mkdir()
    e = SimpleNamespace(root=rig.root, run=run, prefix="/api", rig=rig, scope=scope,
                        token=issued.session_token, receipts=[])
    with synthetic_provider(run) as (config, png, calls):
        e.config, e.png, e.calls = config, png, calls
        monkeypatch.setenv("ASSET_PROVIDER_CONFIG_PATH", str(config))
        provider_config = json.loads(config.read_text(encoding="utf-8"))["automatic1111"]
        providers = AssetProviderRegistry()
        transport = _LocalImageTransport(provider_config["endpoint"], configured=True, trust_env=False)
        adapter = Automatic1111ImageProvider(transport, provider_config["endpoint"])
        adapter.default_model = provider_config["default_model"]
        providers.register("automatic1111", adapter)
        production = ProductionExecutionService(rig.workspace, ImageJobService(rig.root / "shared-image-jobs"),
            providers, VideoAssemblyService(rig.root, rig.assets), {}, {},
            AudioProductionStore(rig.root / "shared-audio"), NoCalls(), httpx)
        graph = CreativeGraphService(rig.workspace.store, rig.workspace)
        graph.configure_media(production)
        for mounted, fresh in ((experimental_api.creative_graph_service, graph),
                               (experimental_api.studio_production_service, production)):
            for name, value in fresh.__dict__.items():
                monkeypatch.setattr(mounted, name, value, raising=False)
        e.production, e.graph = production, graph
        prepare_approved_node(e, rig.client, existing_nid=rig.nid, scope=scope)
        try:
            yield e
        finally:
            registry_owner.clear()


def shared_owner_bytes(e):
    from app.experimental.store import canonical
    jobs = e.production.image_jobs.for_actor("reader")._path(e.nid, e.scope["branch_id"])
    return (canonical(e.graph.store.read(e.nid, e.scope)), jobs.read_bytes(),
            e.rig.assets._meta_path(e.pin["asset_id"]).read_bytes(),
            e.rig.assets._bin_path(e.pin["asset_id"]).read_bytes())


def test_shared_approved_image_control_uses_real_host_and_project_authority(shared_approved_node):
    e = shared_approved_node
    saved = record(e, "shared.image-node-result.accepted",
        e.client.post(e.canvas_url + "/image-node-result", json=e.body))
    assert saved["definition"]["image_node_origin"]["asset"] == e.pin
    assert saved["scope"] == e.scope and len(e.calls) == 1


@pytest.mark.parametrize("retirement", ["read", "write", "session"])
@pytest.mark.parametrize("timing", ["before", "commit"])
def test_shared_approved_image_revocation_preserves_original_owners(shared_approved_node, monkeypatch, retirement, timing):
    from app.creative import canvas_views
    e = shared_approved_node
    before = shared_owner_bytes(e)
    retired = []

    def revoke():
        assert not retired
        if retirement == "session":
            e.rig.sessions.revoke(e.token)
        else:
            e.rig.grants.revoke_permission("query-read" if retirement == "read" else "node-write", "fixture")
        retired.append(retirement)

    if timing == "before":
        revoke()
    else:
        original_change = canvas_views.change_row

        def retire_after_original_change(row, *args, **kwargs):
            result = original_change(row, *args, **kwargs)
            assert row["id"] == e.target["id"] and row["definition"].get("image_node_origin")
            revoke()
            return result

        monkeypatch.setattr(canvas_views, "change_row", retire_after_original_change)
    record(e, f"shared.{timing}.{retirement}.refused",
        e.client.post(e.canvas_url + "/image-node-result", json=e.body),
        401 if retirement == "session" else 403)
    assert retired == [retirement]
    assert shared_owner_bytes(e) == before
    assert len(e.calls) == 1


@pytest.mark.parametrize("identity", ["missing-token", "unknown-token", "wrong-branch"])
def test_shared_approved_image_rejects_wrong_request_identity(shared_approved_node, identity):
    e = shared_approved_node
    before = shared_owner_bytes(e)
    # Explicitly edit a prepared request so missing really means no header;
    # ordinary per-request headers would merge the client's valid default.
    request = e.client.build_request("POST", e.canvas_url + "/image-node-result", json=e.body)
    if identity == "missing-token":
        del request.headers["X-Session-Token"]
    elif identity == "unknown-token":
        request.headers["X-Session-Token"] = "synthetic-unissued-session"
    else:
        request.headers["X-Branch-Id"] = "query-branch-b"
    record(e, "shared." + identity, e.client.send(request), 404 if identity == "wrong-branch" else 401)
    assert shared_owner_bytes(e) == before and len(e.calls) == 1
