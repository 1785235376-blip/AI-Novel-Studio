from __future__ import annotations

import base64
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.asset_lifecycle_api import create_asset_lifecycle_router
from app.services.asset_library_service import AssetIdempotencyConflict, AssetIntegrityError, AssetLibraryService
from app.services.v1_capability_service import AssetDerivativeIn, CapabilityVersionConflict, V1CapabilityService, VisualMemoryIn


def upload(service, data=b"fixture-image-bytes", **kwargs):
    return service.create("n1", "reference.png", base64.b64encode(data).decode(), "image/png", **kwargs)


class Novels:
    def get(self, nid):
        if nid not in {"n1", "n2"}:
            raise FileNotFoundError(nid)
        return {"id": nid}

    def data_set(self, nid, dataset):
        return [{"id": "hero"}]


@pytest.fixture
def services(tmp_path):
    assets = AssetLibraryService(tmp_path)
    memories = V1CapabilityService(tmp_path, Novels(), None, assets)
    return assets, memories


def reference(memories, asset, **kwargs):
    body = VisualMemoryIn(entity_type="CHARACTER", entity_id="hero", asset_id=asset["id"],
                          appearance={"eyes": "green"}, notes="银色长发 silver hair", evidence_ids=["user-reference"])
    return memories.create_visual_memory("n1", body, **kwargs)


@pytest.mark.parametrize("identifier", ["../escape", "/tmp/escape", "a/b", "a\\b", "..", ".", "a\x00b", ""])
def test_path_identifiers_rejected(services, identifier):
    assets, _ = services
    for operation in (assets.get, assets.content, assets.delete, assets.restore):
        with pytest.raises(ValueError, match="asset_id"):
            operation(identifier)


def test_content_verifies_digest_and_length(services):
    assets, _ = services
    item = upload(assets, b"1234")
    assets._bin_path(item["id"]).write_bytes(b"5678")
    with pytest.raises(AssetIntegrityError, match="digest"):
        assets.content(item["id"])
    assets._bin_path(item["id"]).write_bytes(b"longer")
    with pytest.raises(AssetIntegrityError, match="size"):
        assets.content(item["id"])


def test_symlink_assets_are_never_followed(services, tmp_path):
    assets, _ = services
    item = upload(assets)
    target = tmp_path / "unrelated"
    target.write_text("private")
    assets._bin_path(item["id"]).unlink()
    (assets.root / (item["id"] + ".bin")).symlink_to(target)
    with pytest.raises(AssetIntegrityError, match="regular file"):
        assets.content(item["id"])


def test_idempotency_binds_payload_and_deletion(services):
    assets, _ = services
    first = upload(assets, idempotency_key="key")
    assert upload(assets, idempotency_key="key")["id"] == first["id"]
    with pytest.raises(AssetIdempotencyConflict):
        upload(assets, b"changed", idempotency_key="key")
    assets.delete(first["id"])
    with pytest.raises(AssetIdempotencyConflict, match="deleted"):
        upload(assets, idempotency_key="key")


def test_scoped_idempotency_isolated_and_concurrent(services):
    assets, _ = services
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(lambda _: upload(assets, idempotency_key="key", branch_id="b1"), range(12)))
    assert len({item["id"] for item in results}) == 1
    other = upload(assets, idempotency_key="key", branch_id="b2")
    assert other["id"] != results[0]["id"]
    assert len(assets.list("n1", branch_id="b1")) == 1
    with pytest.raises(FileNotFoundError):
        assets.get(other["id"], branch_id="b1")
    legacy = upload(assets)
    with pytest.raises(FileNotFoundError):
        assets.get(legacy["id"], branch_id="b1")


def test_delete_recover_and_restart_preserve_original(services, tmp_path):
    assets, _ = services
    item = upload(assets)
    removed = assets.delete(item["id"])
    assert removed["recoverable"]
    assert assets._bin_path(item["id"]).exists()
    assert not assets.list("n1")
    with pytest.raises(FileNotFoundError):
        assets.get(item["id"])
    restarted = AssetLibraryService(tmp_path)
    restored = restarted.restore(item["id"])
    assert restored["sha256"] == item["sha256"]
    assert restored["version"] == 3
    assert restarted.content(item["id"]) == b"fixture-image-bytes"


def test_damaged_deleted_asset_cannot_be_restored(services):
    assets, _ = services
    item = upload(assets)
    assets.delete(item["id"])
    assets._bin_path(item["id"]).write_bytes(b"bad")
    with pytest.raises(AssetIntegrityError):
        assets.restore(item["id"])
    assert assets.get(item["id"], include_deleted=True)["deleted_at"]


def test_approved_reference_index_is_persisted_lexical_with_provenance(services, tmp_path):
    assets, memories = services
    asset = upload(assets)
    memory = reference(memories, asset)
    assert memories.search_visual_memory("n1", "silver")["items"] == []
    approved = memories.approve_visual_memory("n1", memory["id"], 1, actor_id="author-a")
    found = memories.search_visual_memory("n1", "silver")
    assert found["retrieval_mode"] == "LEXICAL_METADATA"
    assert found["embeddings_available"] is False and found["inference_performed"] is False
    assert found["items"][0]["id"] == memory["id"]
    assert found["items"][0]["provenance"]["asset_sha256"] == asset["sha256"]
    assert found["items"][0]["version"] == approved["version"] == 2
    assert memories.search_visual_memory("n1", "长发")["items"][0]["id"] == memory["id"]
    index_files = list((tmp_path / "v1_capabilities" / "visual_memory_indexes").glob("*.json"))
    assert len(index_files) == 1
    assert json.loads(index_files[0].read_text())["postings"]["silver"][memory["id"]] > 0
    restarted = V1CapabilityService(tmp_path, Novels(), None, AssetLibraryService(tmp_path))
    assert restarted.search_visual_memory("n1", "silver")["source_fingerprint"] == found["source_fingerprint"]
    assert restarted.search_visual_memory("n2", "silver")["items"] == []


def test_approval_version_and_edit_invalidate_index(services):
    assets, memories = services
    asset = upload(assets)
    memory = reference(memories, asset)
    memories.approve_visual_memory("n1", memory["id"], 1)
    with pytest.raises(CapabilityVersionConflict):
        memories.approve_visual_memory("n1", memory["id"], 1)
    updated = memories.update_visual_memory("n1", memory["id"], VisualMemoryIn(
        entity_type="CHARACTER", entity_id="hero", asset_id=asset["id"], notes="black hair"), 2)
    assert updated["approval_status"] == "DRAFT"
    assert memories.search_visual_memory("n1", "silver")["items"] == []


def test_missing_tampered_deleted_and_restored_assets_fail_closed(services):
    assets, memories = services
    item = upload(assets)
    memory = reference(memories, item)
    memories.approve_visual_memory("n1", memory["id"], 1)
    assets.delete(item["id"])
    result = memories.search_visual_memory("n1", "silver")
    assert result["items"] == [] and result["excluded"][0]["reason"] == "ASSET_MISSING_OR_INVALID"
    assets.restore(item["id"])
    result = memories.search_visual_memory("n1", "silver")
    assert result["items"] == [] and result["excluded"][0]["reason"] == "APPROVAL_STALE"
    memories.approve_visual_memory("n1", memory["id"], 2)
    assert len(memories.search_visual_memory("n1", "silver")["items"]) == 1
    assets._bin_path(item["id"]).write_bytes(b"x" * item["size"])
    assert memories.search_visual_memory("n1", "silver")["items"] == []
    assets._bin_path(item["id"]).unlink()
    assert memories.search_visual_memory("n1", "silver")["items"] == []


def test_index_cache_tampering_rebuilds_from_authority(services, tmp_path):
    assets, memories = services
    item = upload(assets)
    memory = reference(memories, item)
    memories.approve_visual_memory("n1", memory["id"], 1)
    memories.search_visual_memory("n1", "silver")
    path = next((tmp_path / "v1_capabilities" / "visual_memory_indexes").glob("*.json"))
    cached = json.loads(path.read_text())
    cached["postings"]["private"] = {memory["id"]: 100}
    path.write_text(json.dumps(cached))
    assert memories.search_visual_memory("n1", "private")["items"] == []
    path.write_text("broken")
    assert memories.search_visual_memory("n1", "silver")["items"]


def test_memory_branch_and_foreign_asset_isolation(services):
    assets, memories = services
    item = upload(assets, branch_id="b1")
    row = reference(memories, item, branch_id="b1")
    with pytest.raises(FileNotFoundError):
        memories.approve_visual_memory("n1", row["id"], 1, branch_id="b2")
    memories.approve_visual_memory("n1", row["id"], 1, branch_id="b1")
    assert memories.search_visual_memory("n1", "silver", branch_id="b2")["items"] == []
    foreign = assets.create("n2", "foreign.png", base64.b64encode(b"x").decode(), "image/png")
    with pytest.raises(FileNotFoundError):
        reference(memories, foreign)


def test_derivatives_are_verified_acyclic_and_references_retained(services):
    assets, memories = services
    a, b, c = (upload(assets, value) for value in (b"a", b"b", b"c"))
    memory = reference(memories, a)
    memories.create_asset_derivative(a["id"], AssetDerivativeIn(derivative_asset_id=b["id"], derivative_type="CROP"))
    memories.create_asset_derivative(b["id"], AssetDerivativeIn(derivative_asset_id=c["id"], derivative_type="CROP"))
    with pytest.raises(ValueError, match="cycle"):
        memories.create_asset_derivative(c["id"], AssetDerivativeIn(derivative_asset_id=a["id"], derivative_type="CROP"))
    assert memories.list_asset_derivatives(a["id"])["items"][0]["integrity_status"] == "VERIFIED"
    assets.delete(b["id"])
    assert memories.list_asset_derivatives(a["id"])["items"][0]["integrity_status"] == "MISSING_OR_INVALID"
    assets.delete(a["id"])
    refs = memories.asset_references(a["id"], include_deleted=True)
    assert refs["total"] == 2
    assert any(item["id"] == memory["id"] for item in refs["items"])


def test_router_local_loop_create_approve_search_restore(services):
    assets, memories = services
    app = FastAPI()
    app.include_router(create_asset_lifecycle_router(assets, memories), prefix="/api")
    client = TestClient(app)
    asset = upload(assets)
    prefix = "/api/novels/n1"
    created = client.post(prefix + "/visual-references", json={"entity_type": "STYLE", "entity_id": "noir", "asset_id": asset["id"], "notes": "silver"})
    assert created.status_code == 201
    row = created.json()
    assert client.get(prefix + "/visual-reference-search?query=silver").json()["items"] == []
    assert client.post(prefix + f"/visual-references/{row['id']}/approve", json={"expected_version": 1}).status_code == 200
    assert client.post(prefix + f"/visual-references/{row['id']}/approve", json={"expected_version": 1}).status_code == 409
    assert client.get(prefix + "/visual-reference-search?query=silver").json()["items"][0]["id"] == row["id"]
    assert client.get(prefix + f"/assets/{asset['id']}/references").json()["total"] == 1
    assets.delete(asset["id"])
    assert client.get(prefix + "/asset-trash").json()["items"][0]["id"] == asset["id"]
    assert client.post(f"/api/novels/n2/assets/{asset['id']}/restore").status_code == 404
    assert client.post(prefix + f"/assets/{asset['id']}/restore").status_code == 200


def test_multiple_service_instances_share_durable_idempotency_lock(services, tmp_path):
    assets, _ = services
    second = AssetLibraryService(tmp_path)
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda index: upload(assets if index % 2 else second, idempotency_key="shared"), range(20)))
    assert len({item["id"] for item in results}) == 1


def test_provenance_metadata_is_bounded_idempotent_and_scope_checked(services):
    assets, _ = services
    a, b = upload(assets, branch_id="b1"), upload(assets, branch_id="b1")
    data = {"source_job_id": "job", "parameters": {"seed": 9}, "source_asset_ids": [b["id"]]}
    changed = assets.update_metadata(a["id"], data, branch_id="b1")
    assert changed["version"] == 2
    assert assets.update_metadata(a["id"], data, branch_id="b1")["version"] == 2
    with pytest.raises(ValueError):
        assets.update_metadata(a["id"], {"sha256": "forged"})
    with pytest.raises(ValueError):
        assets.update_metadata(a["id"], {"source_asset_ids": [a["id"]]})
    foreign = upload(assets, branch_id="b2")
    with pytest.raises(FileNotFoundError):
        assets.update_metadata(a["id"], {"source_asset_ids": [foreign["id"]]}, branch_id="b1")


def test_scope_router_resolves_trusted_actor_and_denies_branch_mismatch(services, monkeypatch):
    from types import SimpleNamespace
    from app.actor_context import ActorContext, SessionContext
    import app.api as api_module
    import app.asset_lifecycle_api as domain_api
    import app.dependencies as dependencies

    assets, memories = services
    settings = SimpleNamespace(enable_collaboration_runtime=True)
    monkeypatch.setattr(api_module, "settings", settings)
    monkeypatch.setattr(domain_api, "settings", settings)

    class Sessions:
        def resolve(self, token):
            if token != "trusted":
                raise KeyError(token)
            return ActorContext("author", "w1", SessionContext("s1", "client", "author", "w1"))

    class Scopes:
        def get(self, collection, identifier):
            return {"id": identifier, "workspace_id": "w1" if identifier != "foreign" else "w2",
                    "project_id": "n1", "storyline_id": "story"}

        def project_workspace(self, nid):
            return "w1"

    class Membership:
        def require(self, actor, permission, domain, scope):
            if scope.branch_id == "read-only" and permission == "domain.write":
                raise PermissionError("write denied")

    sessions = Sessions()
    monkeypatch.setattr(api_module, "trusted_session_resolver", sessions)
    monkeypatch.setattr(dependencies, "trusted_session_resolver", sessions)
    monkeypatch.setattr(api_module, "collaboration_scope_service", SimpleNamespace(repository=Scopes(), validate_scope=lambda scope: scope))
    monkeypatch.setattr(api_module, "membership_authorization_service", Membership())
    app = FastAPI()
    app.include_router(create_asset_lifecycle_router(assets, memories), prefix="/api")
    client = TestClient(app)
    asset = upload(assets, branch_id="b1")
    body = {"entity_type": "STYLE", "entity_id": "noir", "asset_id": asset["id"], "notes": "silver"}
    path = "/api/novels/n1/visual-references"
    assert client.get(path).status_code == 401
    assert client.get(path, headers={"X-Session-Token": "trusted"}).status_code == 400
    assert client.get(path, headers={"X-Branch-Id": "b1"}).status_code == 401
    assert client.get(path, headers={"X-Branch-Id": "foreign", "X-Session-Token": "trusted"}).status_code == 403
    assert client.post(path, headers={"X-Branch-Id": "read-only", "X-Session-Token": "trusted"}, json=body).status_code == 403
    other_headers = {"X-Branch-Id": "b2", "X-Session-Token": "trusted"}
    assert client.post(path, headers=other_headers, json=body).status_code == 404
    headers = {"X-Branch-Id": "b1", "X-Session-Token": "trusted"}
    row = client.post(path, headers=headers, json=body).json()
    response = client.post(path + f"/{row['id']}/approve", headers=headers, json={"expected_version": 1})
    assert response.status_code == 200
    assert response.json()["approval"]["approved_by"] == "author"
    assert client.get(path, headers=other_headers).json()["items"] == []
    assert client.post(path + f"/{row['id']}/approve", headers=other_headers, json={"expected_version": 2}).status_code == 404


def test_source_lineage_cycle_and_usage_are_checked(services):
    assets, memories = services
    a, b = upload(assets, b"a"), upload(assets, b"b")
    assets.update_metadata(a["id"], {"source_asset_ids": [b["id"]]})
    with pytest.raises(ValueError, match="cycle"):
        assets.update_metadata(b["id"], {"source_asset_ids": [a["id"]]})
    refs = memories.asset_references(b["id"])
    assert refs["items"] == [{"collection": "assets", "id": a["id"], "field": "source_asset_ids", "version": 2, "status": "AVAILABLE"}]
