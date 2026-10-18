"""Camera exchange against original File/PostgreSQL Asset and project owners.

Real generated GLB bytes are imported, reopened, inspected and exported. No
fake persistence, decoded camera result, browser, DCC, renderer or provider is
substituted. Select the original rig's file_backend_only marker for File runs.
"""
from __future__ import annotations

import base64
import hashlib
import json
from types import SimpleNamespace

import pytest

from test_v2_independent_workspace import branch_scope, reopened, rig
from test_v2_static_glb_inspection import glb, triangle_document
from test_v2_static_glb_owner import body as import_body


def source_camera_document():
    document = triangle_document()
    document["cameras"] = [{"name": "Source perspective camera", "type": "perspective",
                            "perspective": {"yfov": 0.7, "znear": 0.1}}]
    document["nodes"].extend([
        {"name": "Source camera node", "camera": 0, "translation": [1, 2, 3]},
        {"name": "Source camera parent", "children": [1], "translation": [4, 5, 6]},
    ])
    document["scenes"][0]["nodes"] = [0, 2]
    return document


def source_asset(rig):
    return rig.service.import_model_reference(
        rig.nid, rig.scope, rig.actor, import_body(glb(source_camera_document()), "camera-source"))


def export_body(asset):
    return {"contract": "studio-static-glb-camera-export/1", "source_version": asset["version"],
            "source_sha256": asset["sha256"], "scene_index": 0, "node_index": 1,
            "camera_index": 0, "profile": "GLTF_2_CAMERA_ONLY"}


def files(rig):
    return {str(path.relative_to(rig.root)): path.read_bytes()
            for path in rig.root.rglob("*") if path.is_file()}


def inspect(rig, asset, service=None, guard=lambda: None):
    return (service or rig.service).inspect_model_reference(
        rig.nid, rig.scope, asset["id"], guard, camera_inspection=True)


def export(rig, asset, service=None, guard=lambda: None, **changes):
    return (service or rig.service).export_model_camera(
        rig.nid, rig.scope, asset["id"], {**export_body(asset), **changes}, guard)


def private_response(response, status):
    assert response.status_code == status, response.text
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    for marker in ("PRIVATE-FIXTURE-VALUE", "Source camera node", "Source perspective camera",
                   "content_base64", "world_matrix", "camera_inspection", "_owner_actor_id"):
        assert marker not in response.text


@pytest.fixture
def camera_http(rig):
    from fastapi import FastAPI, HTTPException
    from fastapi.testclient import TestClient
    from app.creative.workspace_api import create_independent_workspace_router
    from app.experimental.flags import require_flag

    source = source_asset(rig)
    state = SimpleNamespace(allowed=True, calls=[])

    def authorize(nid, token, branch, permission):
        state.calls.append((nid, token, branch, permission))
        if (nid != rig.nid or token != "fixture-session" or branch is not None
                or permission != "domain.read" or not state.allowed):
            raise HTTPException(403, {"code": "DENIED"})
        return rig.actor, rig.scope

    app = FastAPI()
    app.include_router(create_independent_workspace_router(
        rig.service, authorize, require_flag, create_project=lambda *args: None,
        workspace_writer=lambda token: rig.actor), prefix="/api")
    with TestClient(app) as client:
        yield SimpleNamespace(client=client, source=source, state=state,
                              headers={"X-Session-Token": "fixture-session"},
                              path=f"/api/projects/{rig.nid}/studio/assets/{source['id']}/model-reference")


def test_real_owner_reopen_camera_inspection_export_exact_and_readonly(rig):
    asset = source_asset(rig)
    service = reopened(rig)
    assert service.list_assets(rig.nid, rig.scope) == {"items": [asset]}
    assert rig.chapters.list(rig.nid) == []
    before = files(rig)
    inspected = inspect(rig, asset, service)
    result = export(rig, asset, service)
    snapshot = {"id": asset["id"], "kind": "ASSET", "asset_kind": "model",
                "version": 1, "digest": hashlib.sha256(glb(source_camera_document())).hexdigest()}
    assert asset["sha256"] == snapshot["digest"]
    assert inspected["asset_snapshot"] == result["asset_snapshot"] == snapshot
    cameras = inspected["camera_inspection"]
    assert cameras["contract"] == "studio-static-glb-cameras/1"
    assert cameras["scene_index"] == 0 and cameras["scene_selection"] == "DECLARED_DEFAULT"
    assert cameras["camera_definition_count"] == 1 and len(cameras["instances"]) == 1
    camera = cameras["instances"][0]
    matrix = [1., 0., 0., 0., 0., 1., 0., 0., 0., 0., 1., 0., 5., 7., 9., 1.]
    assert camera == {"node_index": 1, "camera_index": 0, "node_name": "Source camera node",
                      "camera_name": "Source perspective camera", "world_matrix": matrix,
                      "projection": {"type": "perspective", "yfov": 0.7, "znear": 0.1,
                                     "aspectRatio": None, "zfar": None}}
    data = base64.b64decode(result["content_base64"], validate=True)
    document = json.loads(data)
    assert document == {
        "asset": {"version": "2.0", "generator": "Studio static camera exchange/1"},
        "scene": 0, "scenes": [{"nodes": [0]}],
        "nodes": [{"camera": 0, "name": "Source camera node", "matrix": matrix}],
        "cameras": [{"type": "perspective", "name": "Source perspective camera",
                     "perspective": {"yfov": 0.7, "znear": 0.1}}],
        "extras": {"studio_camera_source": {
            "contract": "studio-static-glb-camera-source/1", "asset_id": asset["id"],
            "version": asset["version"], "sha256": asset["sha256"], "scene_index": 0,
            "scene_selection": "DECLARED_DEFAULT", "node_index": 1, "camera_index": 0}},
    }
    assert "aspectRatio" not in document["cameras"][0]["perspective"]
    assert "zfar" not in document["cameras"][0]["perspective"]
    assert not {"buffers", "bufferViews", "accessors", "meshes", "images", "animations"} & document.keys()
    expected_bytes = (json.dumps(document, sort_keys=True, separators=(",", ":"),
                                 ensure_ascii=True, allow_nan=False) + "\n").encode("utf-8")
    assert data == expected_bytes
    proof = result["camera_export"]
    assert proof == {
        "contract": "studio-static-glb-camera-export/1", "profile": "GLTF_2_CAMERA_ONLY",
        "scene_index": 0, "scene_selection": "DECLARED_DEFAULT", "camera": camera,
        "coordinate_system": "GLTF_RH_Y_UP_METERS", "matrix_layout": "COLUMN_MAJOR",
        "byte_count": len(data), "sha256": hashlib.sha256(data).hexdigest(),
        "animation_applied": False, "model_called": False, "asset_created": False,
        "blender_import_acceptance": "NOT_RUN", "unreal_import_acceptance": "NOT_RUN",
    }
    assert export(rig, asset, service) == result
    assert service.download(rig.nid, rig.scope, asset["id"])[1] == glb(source_camera_document())
    assert service.list_assets(rig.nid, rig.scope) == {"items": [asset]}
    assert files(rig) == before
    # Reusable genuine service-wire evidence, emitted only after read-only checks.
    (rig.root / "camera-wire.json").write_text(json.dumps({
        "asset": asset, "inspection": inspected, "request": export_body(asset), "result": result,
        "source_glb_base64": base64.b64encode(glb(source_camera_document())).decode("ascii"),
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


@pytest.mark.parametrize("changes", [{"source_version": 2}, {"source_sha256": "0" * 64}])
def test_stale_source_pin_rejected_before_parser(rig, monkeypatch, changes):
    from app.experimental.common import StaleSourceError
    import app.creative.model_reference_glb as parser
    asset = source_asset(rig)
    before = files(rig)
    def forbidden(*args, **kwargs):
        raise AssertionError("stale source must not enter parser")
    monkeypatch.setattr(parser, "inspect_static_glb", forbidden)
    with pytest.raises(StaleSourceError, match="MODEL_REFERENCE_SOURCE_CHANGED"):
        export(rig, asset, **changes)
    assert files(rig) == before


@pytest.mark.parametrize("method", ["inspect", "export"])
@pytest.mark.parametrize("exclusion", ["project", "branch", "private-owner"])
def test_wrong_project_branch_and_private_owner_are_excluded(rig, method, exclusion):
    asset = source_asset(rig)
    nid, scope = rig.nid, rig.scope
    if exclusion == "project":
        nid = rig.create_project("Other camera owner")
        scope = {"mode": "local", "novel_id": nid}
    elif exclusion == "branch":
        scope = branch_scope(rig)
    else:
        raw = rig.assets._load(asset["id"])
        raw["_owner_actor_id"] = rig.actor
        rig.assets._write_meta(raw)
    before = files(rig)
    service = reopened(rig)
    with pytest.raises((FileNotFoundError, ValueError)):
        if method == "inspect":
            service.inspect_model_reference(nid, scope, asset["id"], camera_inspection=True)
        else:
            service.export_model_camera(nid, scope, asset["id"], export_body(asset))
    assert files(rig) == before
    if exclusion != "project":
        assert service.list_assets(nid, scope) == {"items": []}
        assert files(rig) == before


@pytest.mark.file_backend_only
@pytest.mark.parametrize("rig", ["file"], indirect=True)
@pytest.mark.parametrize("surface", ["service-inspect", "service-export", "route-inspect", "route-export"])
def test_missing_file_owner_marker_is_never_provisioned_by_camera_reads(rig, camera_http, surface):
    h = camera_http
    marker = rig.root / "novels" / rig.nid / "creative_project_v2.json"
    assert marker.is_file()
    marker.unlink()
    before = files(rig)
    if surface.startswith("service-"):
        operation = inspect if surface == "service-inspect" else export
        with pytest.raises(FileNotFoundError):
            operation(rig, h.source, reopened(rig))
    elif surface == "route-inspect":
        private_response(h.client.get(h.path + "/cameras", headers=h.headers), 404)
    else:
        private_response(h.client.post(h.path + "/camera-export", headers=h.headers,
                                       json=export_body(h.source)), 404)
    assert not marker.exists()
    assert files(rig) == before


def test_deleted_asset_and_recreated_project_never_reuse_camera_source(rig):
    asset = source_asset(rig)
    incarnation = rig.store.incarnation(rig.nid)
    rig.service.lifecycle(rig.nid, rig.scope, asset["id"], asset["version"])
    for operation in (inspect, export):
        with pytest.raises((FileNotFoundError, ValueError)):
            operation(rig, asset, reopened(rig))
    rig.novels.delete(rig.nid)
    rig.create_project("Recreated camera owner", rig.nid)
    assert rig.store.incarnation(rig.nid) != incarnation
    for operation in (inspect, export):
        with pytest.raises((FileNotFoundError, ValueError)):
            operation(rig, asset, reopened(rig))
    fresh = source_asset(rig)
    assert fresh["id"] != asset["id"]
    assert export(rig, fresh)["asset_snapshot"]["id"] == fresh["id"]


@pytest.mark.parametrize("stage", ["inspection-parser", "export-parser", "export-serializer"])
@pytest.mark.parametrize("change", ["revocation", "version", "digest", "kind", "media-type",
                                     "private-owner", "required-feature", "deleted", "recreated"])
def test_fresh_authority_source_and_privacy_are_rechecked_after_work(rig, monkeypatch, stage, change):
    import app.creative.model_reference_cameras as serializer
    import app.creative.model_reference_glb as parser
    asset = source_asset(rig)
    state = {"allowed": True, "calls": 0}

    def guard():
        if not state["allowed"]:
            raise PermissionError("camera authority revoked")

    def mutate():
        state["calls"] += 1
        if change == "revocation":
            state["allowed"] = False
        elif change == "deleted":
            rig.service.lifecycle(rig.nid, rig.scope, asset["id"], asset["version"])
        elif change == "recreated":
            rig.novels.delete(rig.nid)
            rig.create_project("Changed camera incarnation", rig.nid)
        else:
            raw = rig.assets._load(asset["id"])
            field, value = {
                "version": ("version", asset["version"] + 1), "digest": ("sha256", "0" * 64),
                "kind": ("kind", "image"), "media-type": ("media_type", "image/png"),
                "private-owner": ("_owner_actor_id", rig.actor),
                "required-feature": ("_required_features", ["private_camera_fixture_feature"]),
            }[change]
            raw[field] = value
            rig.assets._write_meta(raw)

    module, name = ((serializer, "export_camera") if stage == "export-serializer"
                    else (parser, "inspect_static_glb"))
    original = getattr(module, name)
    def changed(*args, **kwargs):
        result = original(*args, **kwargs)
        mutate()
        return result
    monkeypatch.setattr(module, name, changed)
    operation = inspect if stage == "inspection-parser" else export
    with pytest.raises((PermissionError, FileNotFoundError, ValueError)):
        operation(rig, asset, guard=guard)
    assert state["calls"] == 1
    assert len(list(rig.assets.root.glob("*.bin"))) == 1


@pytest.mark.parametrize("operation", [inspect, export], ids=["inspect", "export"])
def test_missing_nofollow_stays_fail_closed_without_ordinary_read_fallback(rig, monkeypatch, operation):
    import app.creative.model_reference_glb as parser
    import app.services.asset_library_service as owner
    asset = source_asset(rig)
    before = files(rig)
    def forbidden(*args, **kwargs):
        raise AssertionError("unsafe bounded read must not reach parser")
    monkeypatch.setattr(parser, "inspect_static_glb", forbidden)
    monkeypatch.delattr(owner.os, "O_NOFOLLOW", raising=False)
    with pytest.raises(ValueError, match="ASSET_BOUNDED_READ_UNSUPPORTED"):
        operation(rig, asset)
    assert files(rig) == before


def test_real_routes_use_read_authority_and_return_exact_private_wire(rig, camera_http):
    h = camera_http
    before = files(rig)
    inspected = h.client.get(h.path + "/cameras", headers=h.headers)
    assert inspected.status_code == 200, inspected.text
    assert inspected.json() == inspect(rig, h.source)
    response = h.client.post(h.path + "/camera-export", headers=h.headers, json=export_body(h.source))
    assert response.status_code == 200, response.text
    assert response.json() == export(rig, h.source)
    for success in (inspected, response):
        assert success.headers["cache-control"] == "no-store"
        assert success.headers["x-content-type-options"] == "nosniff"
    assert h.state.calls and {call[3] for call in h.state.calls} == {"domain.read"}
    assert files(rig) == before


@pytest.mark.parametrize("suffix,method", [("/cameras", "GET"), ("/camera-export", "POST")])
@pytest.mark.parametrize("denial", ["missing-token", "wrong-branch", "wrong-project", "revoked", "private-owner"])
def test_routes_keep_denials_private(rig, camera_http, suffix, method, denial):
    h = camera_http
    headers, path = dict(h.headers), h.path + suffix
    if denial == "missing-token":
        headers = {}
    elif denial == "wrong-branch":
        headers["X-Branch-ID"] = "PRIVATE-FIXTURE-VALUE"
    elif denial == "wrong-project":
        path = path.replace(rig.nid, "PRIVATE-FIXTURE-VALUE")
    elif denial == "revoked":
        h.state.allowed = False
    else:
        raw = rig.assets._load(h.source["id"])
        raw["_owner_actor_id"] = rig.actor
        rig.assets._write_meta(raw)
    kwargs = {"json": export_body(h.source)} if method == "POST" else {}
    response = h.client.request(method, path, headers=headers, **kwargs)
    private_response(response, 404 if denial == "private-owner" else 403)


@pytest.mark.parametrize("stage", ["inspection-parser", "export-parser", "export-serializer"])
@pytest.mark.parametrize("change,status", [("revocation", 403), ("version", 409), ("private-owner", 404),
                                           ("deleted", 404), ("recreated", 403)])
def test_routes_discard_work_when_authority_source_or_privacy_changes(rig, camera_http, monkeypatch, stage, change, status):
    import app.creative.model_reference_cameras as serializer
    import app.creative.model_reference_glb as parser
    h = camera_http
    module, name = ((serializer, "export_camera") if stage == "export-serializer"
                    else (parser, "inspect_static_glb"))
    original = getattr(module, name)
    calls = []
    fresh_assets = []

    def changed(*args, **kwargs):
        result = original(*args, **kwargs)
        if module is parser and kwargs.get("include_cameras") is not True:
            return result  # A concurrent original import still uses the real base parser.
        calls.append(None)
        if change == "revocation":
            h.state.allowed = False
        elif change == "deleted":
            rig.service.lifecycle(rig.nid, rig.scope, h.source["id"], h.source["version"])
        elif change == "recreated":
            rig.novels.delete(rig.nid)
            rig.create_project("Recreated while camera work completed", rig.nid)
            # A distinct real service represents another original owner writer;
            # it does not inherit this read request's observation-only context.
            writer = reopened(rig)
            fresh_assets.append(writer.import_model_reference(
                rig.nid, rig.scope, rig.actor, import_body(glb(source_camera_document()), "fresh-camera-owner")))
        else:
            raw = rig.assets._load(h.source["id"])
            if change == "version":
                raw["version"] += 1
            else:
                raw["_owner_actor_id"] = rig.actor
            rig.assets._write_meta(raw)
        return result

    monkeypatch.setattr(module, name, changed)
    if stage == "inspection-parser":
        response = h.client.get(h.path + "/cameras", headers=h.headers)
    else:
        response = h.client.post(h.path + "/camera-export", headers=h.headers, json=export_body(h.source))
    private_response(response, status)
    assert h.source["id"] not in response.text and h.source["sha256"] not in response.text
    assert len(calls) == 1
    if change == "recreated":
        monkeypatch.setattr(module, name, original)
        fresh = fresh_assets[0]
        assert fresh["id"] != h.source["id"]
        path = h.path.replace(h.source["id"], fresh["id"])
        inspected = h.client.get(path + "/cameras", headers=h.headers)
        assert inspected.status_code == 200, inspected.text
        result = h.client.post(path + "/camera-export", headers=h.headers, json=export_body(fresh))
        assert result.status_code == 200, result.text
        assert inspected.json()["asset_snapshot"] == result.json()["asset_snapshot"]
        assert result.json()["asset_snapshot"]["id"] == fresh["id"]
        assert result.json()["asset_snapshot"]["digest"] == fresh["sha256"]


@pytest.mark.parametrize("field,value", [
    ("source_version", True), ("source_version", "1"), ("source_version", 1.0),
    ("source_version", 0), ("source_version", 2**53),
    ("source_sha256", "PRIVATE-FIXTURE-VALUE"), ("source_sha256", "A" * 64),
    ("scene_index", False), ("scene_index", "0"), ("scene_index", 0.0), ("scene_index", -1), ("scene_index", 64),
    ("node_index", True), ("node_index", "1"), ("node_index", 1.0), ("node_index", -1), ("node_index", 256),
    ("camera_index", False), ("camera_index", "0"), ("camera_index", 0.0), ("camera_index", -1), ("camera_index", 64),
    ("profile", "BLENDER"), ("contract", "PRIVATE-FIXTURE-VALUE"), ("unexpected", "PRIVATE-FIXTURE-VALUE"),
])
def test_export_request_is_closed_strict_and_never_echoes_input(rig, camera_http, field, value):
    h = camera_http
    before = files(rig)
    response = h.client.post(h.path + "/camera-export", headers=h.headers,
                             json={**export_body(h.source), field: value})
    private_response(response, 422)
    assert response.json() == {"detail": {"code": "MODEL_REFERENCE_CAMERA_REQUEST_INVALID"}}
    assert files(rig) == before


@pytest.mark.parametrize("field", ["contract", "source_version", "source_sha256", "scene_index",
                                   "node_index", "camera_index", "profile"])
def test_export_request_requires_every_source_and_selection_field(rig, camera_http, field):
    h = camera_http
    value = export_body(h.source)
    value.pop(field)
    before = files(rig)
    response = h.client.post(h.path + "/camera-export", headers=h.headers, json=value)
    private_response(response, 422)
    assert response.json() == {"detail": {"code": "MODEL_REFERENCE_CAMERA_REQUEST_INVALID"}}
    assert files(rig) == before


@pytest.mark.parametrize("payload", ["duplicate", "nested-duplicate", "nan", "infinity", "list", "null", "bad-utf8", "malformed"])
def test_export_request_json_rejects_ambiguous_or_nonobject_input(rig, camera_http, payload):
    h = camera_http
    value = json.dumps(export_body(h.source), separators=(",", ":"))
    bodies = {
        "duplicate": value[:-1] + ',"node_index":1}',
        "nested-duplicate": value[:-1] + ',"extra":{"PRIVATE-FIXTURE-VALUE":0,"PRIVATE-FIXTURE-VALUE":1}}',
        "nan": value.replace('"node_index":1', '"node_index":NaN'),
        "infinity": value.replace('"node_index":1', '"node_index":Infinity'),
        "list": "[]", "null": "null", "bad-utf8": b"\xffPRIVATE-FIXTURE-VALUE",
        "malformed": '{"PRIVATE-FIXTURE-VALUE":',
    }
    before = files(rig)
    response = h.client.post(h.path + "/camera-export", headers={**h.headers, "Content-Type": "application/json"},
                             content=bodies[payload])
    private_response(response, 422)
    assert response.json() == {"detail": {"code": "MODEL_REFERENCE_CAMERA_REQUEST_INVALID"}}
    assert files(rig) == before


def test_export_request_body_limit_counts_stream_not_declared_length(rig, camera_http):
    from app.creative.workspace_api import ModelCameraExportRoute
    h = camera_http
    value = json.dumps(export_body(h.source)).encode("utf-8")
    before = files(rig)
    bounded = value + b" " * (ModelCameraExportRoute.MAX_BODY - len(value))
    response = h.client.post(h.path + "/camera-export", headers={**h.headers, "Content-Type": "application/json"}, content=bounded)
    assert response.status_code == 200, response.text
    chunks = iter((b"PRIVATE-FIXTURE-VALUE", b" " * ModelCameraExportRoute.MAX_BODY))
    response = h.client.post(h.path + "/camera-export", headers={**h.headers, "Content-Length": "1"}, content=chunks)
    private_response(response, 413)
    assert response.json() == {"detail": {"code": "MODEL_REFERENCE_CAMERA_REQUEST_LIMIT"}}
    assert files(rig) == before


def test_route_stale_pin_and_invalid_selection_return_no_camera_bytes(rig, camera_http):
    h = camera_http
    for changes, status in (({"source_version": 2}, 409), ({"source_sha256": "0" * 64}, 409),
                            ({"scene_index": 1}, 422), ({"node_index": 0}, 422), ({"camera_index": 1}, 422)):
        response = h.client.post(h.path + "/camera-export", headers=h.headers,
                                 json={**export_body(h.source), **changes})
        private_response(response, status)


def test_camera_route_admission_is_exact_and_does_not_add_execution_or_dcc_import():
    from app.creative.workspace_api import is_independent_studio_route
    root = "/api/projects/project/studio/assets/asset/model-reference"
    assert is_independent_studio_route("GET", root + "/cameras")
    assert is_independent_studio_route("POST", root + "/camera-export")
    for method, suffix in [
        ("POST", "/cameras"), ("PUT", "/cameras"), ("DELETE", "/cameras"),
        ("GET", "/camera-export"), ("PUT", "/camera-export"), ("DELETE", "/camera-export"),
        ("POST", "/camera-export/execute"), ("GET", "/cameras/download"),
        ("POST", "/camera-import"), ("POST", "/camera-save"), ("POST", "/cameras/execute"),
        ("POST", "/camera-export/blender"), ("POST", "/camera-export/unreal"),
        ("GET", "/cameras/"), ("POST", "/camera-export/"),
    ]:
        assert not is_independent_studio_route(method, root + suffix), (method, suffix)
