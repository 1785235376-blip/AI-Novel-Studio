"""V2 capability registry: read-only, deterministic, honest status boundaries."""
from __future__ import annotations

import hashlib
import json

import pytest

from app.config import settings
from test_studio_asset_query import rig

pytestmark = pytest.mark.file_backend_only

RUNTIME = "/studio/production-contracts/runtime"


def snapshot(root):
    return {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in root.rglob("*") if path.is_file()}


def registry(client, nid, prefix="api"):
    response = client.get(f"/{prefix}/projects/{nid}" + RUNTIME)
    assert response.status_code == 200, response.text
    return response.json()["capability_registry"]


def status(value, item_id):
    return next(item["status"] for item in value["items"] if item["id"] == item_id)


def test_registry_is_read_only_deterministic_and_authority_scoped(rig):
    rig.workspace.activate(rig.nid, rig.scope, "local-author")
    before = snapshot(rig.root)
    first = registry(rig.client, rig.nid)
    second = registry(rig.client, rig.nid)
    legacy = rig.client.get(f"/api/projects/{rig.nid}" + RUNTIME)
    alias = rig.client.get(f"/api/v1/projects/{rig.nid}" + RUNTIME)
    assert first == second
    assert legacy.json() == alias.json()
    assert snapshot(rig.root) == before
    value = legacy.json()
    assert value["contract"] == "studio-runtime-capabilities/1"
    assert value["capability_registry"]["contract"] == "v2-capability-registry/1"
    assert value["audio_asset_history"]["enabled"] is False
    assert value["project_capacity"]["admission_enabled"] is False


def test_default_statuses_never_claim_untested_or_blocked_capabilities(rig):
    rig.workspace.activate(rig.nid, rig.scope, "local-author")
    value = registry(rig.client, rig.nid)
    environments = {item["name"]: item["status"] for item in value["real_environments"]}
    assert environments["real_postgres"] == "NOT_RUN"
    assert environments["real_browser_e2e"] == "NOT_RUN"
    assert environments["real_model_gpu_provider"] == "NOT_RUN"
    assert environments["windows_packaged_desktop"] == "NOT_RUN"
    assert environments["hosted_ci"] == "NOT_RUN"
    assert environments["external_nle"] == "NOT_RUN"
    assert environments["publishing_review"] == "BLOCKED"
    assert environments["windows_acl_junction_probe"] == "BLOCKED"
    assert status(value, "audio_asset_history") == "UNAVAILABLE_BY_FLAG"
    assert status(value, "project_capacity_ledger") == "UNAVAILABLE_BY_FLAG"
    assert status(value, "studio_task_cost") == "PARTIAL"
    assert status(value, "audio_canvas_return") == "PRODUCT_DECISION"
    assert status(value, "f37_warm409_root_cause") == "UNKNOWN"
    assert status(value, "historical_product_branches") == "PRODUCT_DECISION"
    assert status(value, "real_provider_inference") == "NOT_RUN"
    assert status(value, "publishing_review") == "BLOCKED"


def test_flag_boundaries_reflect_in_registry_without_writes(rig):
    rig.workspace.activate(rig.nid, rig.scope, "local-author")
    previous_history = settings.enable_audio_asset_history
    previous_capacity = settings.enable_project_capacity_admission
    before = snapshot(rig.root)
    try:
        object.__setattr__(settings, "enable_audio_asset_history", True)
        object.__setattr__(settings, "enable_project_capacity_admission", True)
        value = registry(rig.client, rig.nid)
        assert status(value, "audio_asset_history") == "IMPLEMENTED_VERIFIED_SYNTHETIC"
        assert status(value, "project_capacity_ledger") == "PARTIAL"
        assert status(value, "real_provider_inference") == "NOT_RUN"
        assert snapshot(rig.root) == before
    finally:
        object.__setattr__(settings, "enable_audio_asset_history", previous_history)
        object.__setattr__(settings, "enable_project_capacity_admission", previous_capacity)


def test_registry_shape_and_evidence_are_bounded_and_unique(rig):
    rig.workspace.activate(rig.nid, rig.scope, "local-author")
    value = registry(rig.client, rig.nid)
    items = value["items"]
    ids = [item["id"] for item in items]
    assert len(ids) == len(set(ids))
    assert {"novel_chapter_bible", "video_execution", "graph_multi_node_recovery",
            "timeline_render_export", "export_formats", "taskcenter_query",
            "asset_query_budget", "postgres_backend"} <= set(ids)
    serialized = json.dumps(value, ensure_ascii=False)
    assert "D:\\" not in serialized and "/home/" not in serialized
    for item in items:
        assert item["status"] in {
            "IMPLEMENTED_VERIFIED_SYNTHETIC", "PARTIAL", "UNAVAILABLE_BY_FLAG",
            "NOT_IMPLEMENTED", "NOT_RUN", "NOT_VERIFIED", "BLOCKED",
            "PRODUCT_DECISION", "UNKNOWN"}
        assert item["verification"] in {
            "FILE_SYNTHETIC", "HTTP_SYNTHETIC", "WINDOWS_SYNTHETIC",
            "FILE_AND_HTTP_SYNTHETIC", "NOT_RUN", "NONE"}
        if item["status"] in {"PARTIAL", "NOT_RUN", "BLOCKED", "PRODUCT_DECISION", "UNKNOWN"}:
            assert item["limits"] or item["status"] != "PARTIAL"
    # Real environments are always explicit and never promoted by this read model.
    assert all(entry["status"] in {"NOT_RUN", "BLOCKED", "NOT_VERIFIED"}
               for entry in value["real_environments"])
