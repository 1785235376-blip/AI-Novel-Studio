"""Mounted M1 routes through real original identity/scope/File/PostgreSQL owners."""
import base64
import copy
import hashlib
import json
from uuid import uuid4

import pytest

from test_r3_mounted_contracts import checked, mounted, prefix, scoped
from test_v2_independent_workspace import png_bytes


@pytest.fixture
def client(mounted, monkeypatch):
    from app.creative.service import CreativeService
    e = mounted
    creative = CreativeService(e.store, e.novels, e.chapters)
    e.studio = e.experimental.independent_workspace_service
    for name, value in (("creative", creative), ("store", creative.store), ("novels", e.novels),
                        ("assets", e.assets), ("lineage", e.experimental.production_lineage_service)):
        monkeypatch.setattr(e.studio, name, value)
    monkeypatch.setenv("EXPERIMENTAL_FEATURES", "narrative_production_v2")
    e.studio_base = e.prefix + f"/projects/{e.nid}/studio"
    return e


def upload_body(key="one"):
    return {"filename": "synthetic-external.png", "kind": "image",
            "content_base64": base64.b64encode(png_bytes()).decode(), "idempotency_key": key}


def test_blank_project_real_import_annotation_reopen_export_without_chapter(client):
    e = client
    created = checked(e.client.post(e.prefix + "/experimental/projects", json={
        "title": "Independent image project", "id": "v2-neutral-" + uuid4().hex}), 201)
    nid = created["id"]
    base = e.prefix + f"/projects/{nid}/studio"
    try:
        assert created["studio_ready"] and not created["requires_scope_selection"]
        assert checked(e.client.get(e.prefix + f"/novels/{nid}/chapters")) == []
        project = checked(e.client.get(base))
        assert project["project"] == {"id": nid, "title": created["title"], "entry_kind": "NEUTRAL_STUDIO"}
        assert project["capabilities"]["model_required"] is False
        assert project["capabilities"]["chapter_required"] is False
        assert project["capabilities"]["can_mutate"] is True
        row = checked(e.client.post(base + "/assets", json=upload_body()), 201)
        assert row["version"] == 1 and row["provenance"]["origin"] == "UNDECLARED"
        declared = checked(e.client.put(base + f"/assets/{row['id']}/lineage", json={
            "expected_version": 1, "origin": "EXTERNAL_IMPORT", "license": {"label": "Synthetic fixture"}}))
        assert declared["version"] == 2 and declared["provenance"]["origin"] == "EXTERNAL_IMPORT"
        assert declared["provenance"]["parents"] == declared["provenance"]["sources"] == []
        # A newly constructed service reads original persisted metadata, not a
        # TestClient cache or a second asset registry.
        from app.creative.workspace import IndependentWorkspaceService
        from app.creative.service import CreativeService
        from app.experimental.store import ExperimentalStore
        reopened = IndependentWorkspaceService(CreativeService(ExperimentalStore(e.root, e.backend, e.url),
            e.novels, e.chapters), e.assets, e.experimental.production_lineage_service)
        assert reopened.asset(nid, {"mode": "local", "novel_id": nid}, row["id"]) == declared
        response = e.client.get(base + f"/assets/{row['id']}/download")
        assert response.status_code == 200
        assert response.content == png_bytes()
        assert response.headers["x-asset-sha256"] == hashlib.sha256(png_bytes()).hexdigest()
        assert response.headers["x-asset-version"] == "2"
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["x-content-type-options"] == "nosniff"
        assert "filename*=UTF-8''synthetic-external.png" in response.headers["content-disposition"]
        assert checked(e.client.get(e.prefix + f"/novels/{nid}/chapters")) == []
        assert checked(e.client.get(base + "/assets"))["items"] == [declared]
        assert not any(key.startswith("_") for key in declared)
    finally:
        if e.backend == "postgres":
            with e.store._connect() as connection:
                connection.execute("DELETE FROM experimental_scope_documents WHERE novel_id = %s", (nid,))
        e.novels.delete(nid)


@pytest.mark.parametrize("acceptance", [False, True])
def test_every_new_route_default_off_and_v1_override_preserves_originals(client, monkeypatch, acceptance):
    e = client
    before = copy.deepcopy(e.chapters.get(e.chapter["id"]))
    monkeypatch.setenv("EXPERIMENTAL_FEATURES", "narrative_production_v2" if acceptance else "")
    monkeypatch.setenv("V1_ACCEPTANCE_MODE", "true" if acceptance else "")
    paths = [("GET", "", None), ("POST", "/activate", None), ("GET", "/preferences", None),
             ("PUT", "/preferences", {"expected_version": 0}), ("GET", "/assets", None),
             ("POST", "/assets", upload_body()), ("GET", "/assets/missing", None),
             ("PUT", "/assets/missing/lineage", {"expected_version": 1, "origin": "EXTERNAL_IMPORT"}),
             ("GET", "/assets/missing/download", None), ("DELETE", "/assets/missing?expected_version=1", None),
             ("POST", "/assets/missing/restore", {"expected_version": 1}), ("GET", "/storage", None),
             ("GET", "/references?kind=ASSET", None), ("GET", "/relationships", None),
             ("POST", "/assets/missing/relationships", {"expected_version": 1, "type": "REFERENCES",
                "target": {"kind": "ASSET", "id": "missing", "version": 1, "digest": "0" * 64}}),
             ("DELETE", "/assets/missing/relationships/missing?expected_version=1", None)]
    for method, suffix, body in paths:
        response = e.client.request(method, e.studio_base + suffix, json=body)
        assert response.status_code == 404, (method, suffix, response.text)
        assert response.json()["detail"]["code"] == "EXPERIMENTAL_FEATURE_DISABLED"
    assert e.client.post(e.prefix + "/experimental/projects", json={"title": "No create"}).status_code == 404
    assert e.chapters.get(e.chapter["id"]) == before


def test_activation_is_explicit_preferences_are_not_neutral_authority(client):
    e = client
    assert checked(e.client.get(e.studio_base))["project"]["entry_kind"] == "LEGACY"
    preferences = checked(e.client.put(e.studio_base + "/preferences", json={
        "expected_version": 0, "intents": ["IMAGE_DESIGN"], "preset": "IMAGE"}))
    assert preferences["version"] == 1
    assert checked(e.client.get(e.studio_base))["project"]["entry_kind"] == "LEGACY"
    assert e.client.put(e.studio_base + "/preferences", json={"expected_version": 1,
        "entry_kind": "NEUTRAL_STUDIO"}).status_code == 422
    activated = checked(e.client.post(e.studio_base + "/activate"))
    assert activated["project"]["entry_kind"] == "NEUTRAL_STUDIO"
    assert activated["preferences"]["version"] == 2
    assert checked(e.client.post(e.studio_base + "/activate")) == activated
    assert e.chapters.get(e.chapter["id"]) == e.chapter


def test_real_identity_branch_permissions_and_readonly_controls(client, monkeypatch):
    e = scoped(client, monkeypatch)
    for headers, status in (({}, 401), ({"X-Session-Token": "untrusted"}, 401),
                            ({"X-Session-Token": e.lead}, 400)):
        assert e.client.get(e.studio_base, headers=headers).status_code == status
    assert checked(e.client.get(e.studio_base, headers=e.viewer_headers))["capabilities"]["can_mutate"] is False
    for suffix, body in (("/activate", {}), ("/assets", upload_body())):
        assert e.client.post(e.studio_base + suffix, headers=e.viewer_headers, json=body).status_code == 403
    asset = checked(e.client.post(e.studio_base + "/assets", headers=e.headers, json=upload_body()), 201)
    assert checked(e.client.get(e.studio_base + f"/assets/{asset['id']}", headers=e.viewer_headers)) == asset
    denied = e.client.get(e.studio_base + f"/assets/{asset['id']}/download",
                          headers={**e.headers, "X-Branch-ID": e.other_branch})
    assert denied.status_code == 403 and png_bytes() not in denied.content
    assert e.client.delete(e.studio_base + f"/assets/{asset['id']}?expected_version=1",
                           headers=e.viewer_headers).status_code == 403
    e.authorization.revoke_role(e.role, e.lead)
    assert e.client.get(e.studio_base, headers=e.headers).status_code == 403
    e.sessions.revoke(e.lead)
    assert e.client.get(e.studio_base, headers=e.headers).status_code == 401


def test_collaboration_admission_is_exact_and_feature_gated(client, monkeypatch):
    e = scoped(client, monkeypatch)
    for method, path in (("GET", e.studio_base + "/unknown"), ("PATCH", e.studio_base + "/preferences"),
                         ("DELETE", e.studio_base), ("GET", e.prefix + "/experimental/projects")):
        response = e.client.request(method, path, headers=e.headers)
        assert response.status_code == 501
        assert response.json()["detail"]["code"] == "COLLABORATION_ROUTE_NOT_ENABLED"
    monkeypatch.setenv("V1_ACCEPTANCE_MODE", "true")
    assert e.client.get(e.studio_base, headers=e.headers).status_code == 501


def test_staged_decoding_rechecks_revocation_before_any_asset_commit(client, monkeypatch):
    import app.creative.workspace as module
    e = scoped(client, monkeypatch)
    decode = module.inspect_image
    def revoke_after_decode(data):
        result = decode(data)
        e.authorization.revoke_role(e.role, e.lead)
        return result
    monkeypatch.setattr(module, "inspect_image", revoke_after_decode)
    response = e.client.post(e.studio_base + "/assets", headers=e.headers, json=upload_body())
    assert response.status_code == 403
    assert list(e.assets.root.glob("*.json")) == list(e.assets.root.glob("*.bin")) == []


@pytest.mark.parametrize("private_error", [False, True])
def test_late_revoke_suppresses_asset_bytes_and_private_errors(client, monkeypatch, private_error):
    e = scoped(client, monkeypatch)
    row = checked(e.client.post(e.studio_base + "/assets", headers=e.headers, json=upload_body()), 201)
    original = e.studio.download
    def revoked(*args, **kwargs):
        result = original(*args, **kwargs)
        e.sessions.revoke(e.lead)
        if private_error:
            raise ValueError("synthetic-external.png private diagnostic")
        return result
    monkeypatch.setattr(e.studio, "download", revoked)
    response = e.client.get(e.studio_base + f"/assets/{row['id']}/download", headers=e.headers)
    assert response.status_code == 401
    assert png_bytes() not in response.content and "synthetic-external" not in response.text


def test_asset_cas_conflict_recoverable_deletion_and_stale_restore(client):
    e = client
    row = checked(e.client.post(e.studio_base + "/assets", json=upload_body()), 201)
    path = e.studio_base + f"/assets/{row['id']}"
    conflict = e.client.delete(path + "?expected_version=9")
    assert conflict.status_code == 409 and conflict.json()["detail"]["current"] == {"version": 1}
    removed = checked(e.client.delete(path + "?expected_version=1"))
    assert removed["version"] == 2 and removed["deleted_at"]
    assert e.client.get(path + "/download").status_code == 404
    assert checked(e.client.get(e.studio_base + "/assets"))["items"] == []
    assert checked(e.client.get(e.studio_base + "/assets?include_deleted=true"))["items"] == [removed]
    assert e.client.post(path + "/restore", json={"expected_version": 1}).status_code == 409
    restored = checked(e.client.post(path + "/restore", json={"expected_version": 2}))
    assert restored["version"] == 3 and restored["deleted_at"] is None
    assert e.client.get(path + "/download").content == png_bytes()


def test_bound_assets_are_never_visible_through_old_asset_or_lineage_routes(client, monkeypatch):
    e = client
    row = checked(e.client.post(e.studio_base + "/assets", json=upload_body()), 201)
    monkeypatch.setenv("EXPERIMENTAL_FEATURES", "narrative_production_v2,asset_lineage_v2")
    assert checked(e.client.get(e.prefix + f"/novels/{e.nid}/assets")) == []
    old = e.client.get(e.prefix + f"/assets/{row['id']}/download?novel_id={e.nid}")
    assert old.status_code == 404
    old_lineage = e.client.get(e.base + f"/production/assets/{row['id']}")
    assert old_lineage.status_code == 404
    assert checked(e.client.get(e.studio_base + f"/assets/{row['id']}"))["id"] == row["id"]


def test_late_same_slug_recreation_cannot_release_old_asset_response(client, monkeypatch):
    e = client
    row = checked(e.client.post(e.studio_base + "/assets", json=upload_body()), 201)
    original = e.studio.download
    def recreated(*args, **kwargs):
        result = original(*args, **kwargs)
        e.novels.delete(e.nid)
        assert e.novels.create({"id": e.nid, "title": "New owner, identical slug"})["id"] == e.nid
        return result
    monkeypatch.setattr(e.studio, "download", recreated)
    response = e.client.get(e.studio_base + f"/assets/{row['id']}/download")
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "CREATIVE_AUTHORITY_CHANGED"
    assert png_bytes() not in response.content
    assert checked(e.client.get(e.studio_base + "/assets"))["items"] == []
    assert e.client.get(e.prefix + f"/assets/{row['id']}/download?novel_id={e.nid}").status_code == 404


def test_missing_incarnation_metadata_never_falls_back_to_legacy_access(client):
    e = client
    row = checked(e.client.post(e.studio_base + "/assets", json=upload_body()), 201)
    path = e.assets.root / f"{row['id']}.json"
    metadata = json.loads(path.read_text(encoding="utf-8"))
    metadata.pop("_project_binding")
    path.write_text(json.dumps(metadata), encoding="utf-8")
    before = path.read_bytes()
    assert e.client.get(e.studio_base + f"/assets/{row['id']}").status_code == 404
    assert e.client.get(e.prefix + f"/assets/{row['id']}/download?novel_id={e.nid}").status_code == 404
    assert checked(e.client.get(e.prefix + f"/novels/{e.nid}/assets")) == []
    assert path.read_bytes() == before


@pytest.mark.parametrize("version", [True, "1", 1.2, 0])
def test_new_asset_revision_contracts_reject_coercion(client, version):
    e = client
    row = checked(e.client.post(e.studio_base + "/assets", json=upload_body()), 201)
    path = e.studio_base + f"/assets/{row['id']}"
    assert e.client.put(path + "/lineage", json={"expected_version": version, "origin": "EXTERNAL_IMPORT"}).status_code == 422
    assert e.client.post(path + "/restore", json={"expected_version": version}).status_code == 422
    assert checked(e.client.get(path))["version"] == 1
