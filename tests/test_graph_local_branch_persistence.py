"""Exercise an actual local branched graph and its original File owner.

This deliberately does not claim binary media dispatch or provider acceptance.
"""
import pytest

from app.config import Settings
from app.creative.graph import CreativeGraphService
from app.creative.service import CreativeService
from app.creative.workspace import IndependentWorkspaceService
from app.experimental.media import MediaService
from app.experimental.production_lineage import ProductionLineageService
from app.experimental.store import ExperimentalStore
from app.repositories.factory import create_repository_bundle
from app.services import ChapterService, NovelService
from app.services.asset_library_service import AssetLibraryService

pytestmark = pytest.mark.file_backend_only


def test_branched_local_graph_executes_and_reopens_file_owner(tmp_path, monkeypatch):
    monkeypatch.setenv("EXPERIMENTAL_FEATURES", "narrative_production_v2,asset_lineage_v2")
    bundle = create_repository_bundle(Settings(storage_backend="file", novel_data=tmp_path,
        enable_cloud=False, mock_provider=True), data_root=tmp_path)
    novels = NovelService(bundle.novels, bundle.chapters)
    chapters = ChapterService(bundle.chapters)
    store = ExperimentalStore(tmp_path, "file", "")
    assets = AssetLibraryService(tmp_path)
    creative = CreativeService(store, novels, chapters)
    media = MediaService(store, novels, chapters, assets)
    workspace = IndependentWorkspaceService(creative, assets,
        ProductionLineageService(store, novels, chapters, assets, media))
    graph = CreativeGraphService(workspace.store, workspace)
    nid = novels.create({"id": "graph-local-synthetic", "title": "Synthetic"})["id"]
    scope, actor = {"mode": "local", "novel_id": nid}, "local-author"
    nodes = [
        {"id": "source", "definition_id": "text_input", "parameters": {"text": "A real input"}},
        {"id": "reference", "definition_id": "text_reference"},
        {"id": "note", "definition_id": "director_note", "parameters": {"note": "A real direction"}},
        {"id": "draft", "definition_id": "draft_prepare"},
        {"id": "review", "definition_id": "human_review"},
    ]
    edges = [
        {"id": "a", "source_node_id": "source", "source_port": "text", "target_node_id": "reference", "target_port": "text"},
        {"id": "b", "source_node_id": "reference", "source_port": "text", "target_node_id": "draft", "target_port": "text"},
        {"id": "c", "source_node_id": "note", "source_port": "direction", "target_node_id": "draft", "target_port": "direction"},
        {"id": "d", "source_node_id": "draft", "source_port": "draft", "target_node_id": "review", "target_port": "draft"},
    ]
    saved = graph.create(nid, scope, actor, {"request_id": "branch-create", "definition": {
        "title": "Branched local graph", "nodes": nodes, "edges": edges}})
    plan = graph.preflight(nid, scope, actor, saved["id"], {"expected_version": saved["version"]})
    assert plan["executable"] and set(plan["execution_order"]) == {node["id"] for node in nodes}
    order = plan["execution_order"]
    assert order.index("source") < order.index("reference") < order.index("draft") < order.index("review")
    assert order.index("note") < order.index("draft")
    queued = graph.create_run(nid, scope, actor, saved["id"], {
        "expected_graph_version": saved["version"], "reviewed_preflight_digest": plan["preflight_digest"],
        "request_id": "branch-run"})
    result = graph.action(nid, scope, actor, queued["id"], "execute", {"expected_version": queued["version"]})
    assert result["status"] == "WAITING_APPROVAL"
    stored = workspace.store.read(nid, scope)["collections"][graph.RUNS][queued["id"]]
    assert stored["typed_outputs"]["source"]["text"] == "A real input"
    assert stored["typed_outputs"]["reference"]["text"] == "A real input"
    draft = stored["typed_outputs"]["draft"]["draft"]
    assert draft["text"] == "A real input" and draft["direction"]["note"] == "A real direction"
    assert workspace.store.path(nid, scope).is_file()
    fresh_store = ExperimentalStore(tmp_path, "file", "")
    fresh_creative = CreativeService(fresh_store, novels, chapters)
    fresh_media = MediaService(fresh_store, novels, chapters, assets)
    fresh_workspace = IndependentWorkspaceService(fresh_creative, assets,
        ProductionLineageService(fresh_store, novels, chapters, assets, fresh_media))
    fresh_graph = CreativeGraphService(fresh_workspace.store, fresh_workspace)
    reopened = fresh_graph.get_run(nid, scope, actor, queued["id"])
    assert reopened["status"] == result["status"] and reopened["version"] == result["version"]
    assert reopened["review"]["draft"] == draft
    approved = fresh_graph.action(nid, scope, actor, queued["id"], "approve", {
        "expected_version": reopened["version"], "node_id": "review",
        "reviewed_output_digest": reopened["review"]["output_digest"]})
    assert approved["status"] == "SUCCEEDED" and approved["reviewed"]
    assert fresh_graph.get_run(nid, scope, actor, queued["id"])["status"] == "SUCCEEDED"
