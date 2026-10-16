"""R3-I — PostgreSQL CROSS-PROCESS acceptance (PG-A and PG-B).

Two genuinely independent operating-system processes, each with its own database connection and
its own Creative/Prompt/Asset service graph. Threads sharing one service instance would NOT be
equivalent to this and are not used here.

Synchronisation is a file rendezvous: every child announces readiness and waits until all peers
have announced, so the submissions contend by construction rather than by a guessed delay.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest

from app.creative.prompt_authoring_models import PromptCreateIn

TEST_URL = os.getenv("TEST_POSTGRES_DATABASE_URL", "")
REPO = str(Path(__file__).resolve().parents[1])
CHILD = str(Path(__file__).resolve().parent / "_r3i_pg_child.py")

pytestmark = pytest.mark.postgres_backend_only

TEXT_A = "PG 子进程 A 的正文 🙂"
TEXT_B = "PG 子进程 B 的正文 ✨"


@pytest.fixture
def pg(tmp_path, monkeypatch):
    if os.environ.get("PROJECT_ROOT") is None:
        pytest.skip("requires the isolated runner")
    if not TEST_URL:
        pytest.skip("TEST_POSTGRES_DATABASE_URL not set")
    from app.config import Settings
    from app.creative.bible_workspace import BibleWorkspaceService
    from app.creative.prompt_authoring import PromptAuthoringService
    from app.creative.prompt_workspace import PromptWorkspaceService
    from app.creative.service import CreativeService
    from app.creative.workspace import IndependentWorkspaceService
    from app.experimental.media import MediaService
    from app.experimental.production_lineage import ProductionLineageService
    from app.experimental.store import ExperimentalStore
    from app.experimental.world import WorldService
    from app.repositories.factory import create_repository_bundle
    from app.services import ChapterService, NovelService
    from app.services.asset_library_service import AssetLibraryService

    monkeypatch.setenv("EXPERIMENTAL_FEATURES", "narrative_production_v2,asset_lineage_v2")
    monkeypatch.delenv("V1_ACCEPTANCE_MODE", raising=False)
    root = tmp_path
    bundle = create_repository_bundle(
        Settings(storage_backend="postgres", database_url=TEST_URL, novel_data=root,
                 enable_cloud=False, mock_provider=True), data_root=root)
    novels = NovelService(bundle.novels, bundle.chapters)
    chapters = ChapterService(bundle.chapters)
    store = ExperimentalStore(root, "postgres", TEST_URL)
    assert store.backend == "postgres", "the parent must also be on real PostgreSQL"
    with store._connect() as connection:
        parent_db = connection.execute("SELECT current_database()").fetchone()[0]
    creative = CreativeService(store, novels, chapters)
    assets = AssetLibraryService(root)
    workspace = IndependentWorkspaceService(creative, assets, ProductionLineageService(
        store, novels, chapters, assets, MediaService(store, novels, chapters, assets)))
    bible = BibleWorkspaceService(workspace, WorldService(store, novels, chapters))
    library = PromptWorkspaceService(workspace, bible)
    authoring = PromptAuthoringService(workspace, bible)
    nid = "pgx-" + uuid4().hex
    novels.create({"id": nid, "title": "PG 跨进程"})
    from types import SimpleNamespace
    return SimpleNamespace(nid=nid, scope={"mode": "local", "novel_id": nid}, root=root,
                           url=TEST_URL, creative=creative, library=library,
                           authoring=authoring, actor="author-a", parent_db=parent_db,
                           store=store, workspace=workspace)


def _storyboard(pg):
    screenplay = pg.creative.create(pg.nid, pg.scope, pg.actor, {
        "mode": "SCREENPLAY", "title": "剧本", "source_independent": True,
        "scenes": [{"id": "scene-1", "sequence": 1, "heading": "内景 房间 日", "action": "站住"}]})
    board = pg.creative.derive(pg.nid, pg.scope, pg.actor, screenplay["id"], {
        "expected_version": screenplay["version"], "mode": "STORYBOARD",
        "title": "分镜", "shot_policy": "SCENE"})
    return board, board["shots"][0]["id"]


def _prompt(pg, text):
    receipt = pg.authoring.create(pg.nid, pg.scope, pg.actor, PromptCreateIn.model_validate(
        dict(text=text, purpose="IMAGE", origin="MANUAL", request_id="r-" + uuid4().hex)))
    pg.authoring.approve(pg.nid, pg.scope, pg.actor, receipt["family_id"],
                         receipt["asset_id"], receipt["asset_version"])
    body = pg.library.revision_body(pg.nid, pg.scope, receipt["family_id"],
                                    receipt["asset_id"], pg.actor)
    return receipt, body


def _request(pg, board, receipt, body, shot_id, request_id=None):
    return {
        "shot_id": shot_id, "family_id": receipt["family_id"], "asset_id": receipt["asset_id"],
        "revision": receipt["revision"], "expected_digest": body["digest"],
        "expected_version": board["version"],
        "expected_digest_target": pg.creative.document_digest(board),
        "request_id": request_id or ("pg-" + uuid4().hex),
    }


def _spawn_both(pg, tmp_path, requests):
    """Start one child per request, let them rendezvous, then collect their JSON outcomes."""
    barrier = tmp_path / "barrier"
    procs, outs = [], []
    for index, (tag, request) in enumerate(requests):
        out = tmp_path / f"out-{tag}.json"
        outs.append(out)
        args = {"repo": REPO, "root": str(pg.root), "url": pg.url, "nid": pg.nid,
                "scope": pg.scope, "actor": pg.actor, "document_id": request.pop("_document_id"),
                "shot_id": request["shot_id"], "request": request, "out": str(out),
                "barrier": str(barrier), "tag": tag, "peers": len(requests)}
        procs.append(subprocess.Popen([sys.executable, CHILD, json.dumps(args)],
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE))
    results = []
    for proc, out in zip(procs, outs):
        stdout, stderr = proc.communicate(timeout=180)
        assert proc.returncode == 0, (
            f"child exited {proc.returncode}\nstdout={stdout.decode(errors='replace')[-800:]}"
            f"\nstderr={stderr.decode(errors='replace')[-800:]}")
        assert out.exists(), "the child produced no outcome file"
        results.append(json.loads(out.read_text(encoding="utf-8")))
    return results


def _live(pg, document_id):
    """Read the committed state back from PostgreSQL through a brand-new store connection."""
    from app.creative.service import CreativeService
    from app.experimental.store import ExperimentalStore
    fresh = ExperimentalStore(pg.root, "postgres", pg.url)
    assert fresh.backend == "postgres"
    service = CreativeService(fresh, pg.creative.novels, pg.creative.chapters)
    return service.get(pg.nid, pg.scope, document_id)


# ------------------------------------------------------------------ PG-A --
def test_PG_A_two_processes_two_prompts_one_shot(pg, tmp_path):
    board, shot_id = _storyboard(pg)
    r1, b1 = _prompt(pg, TEXT_A)
    r2, b2 = _prompt(pg, TEXT_B)
    q1 = _request(pg, board, r1, b1, shot_id); q1["_document_id"] = board["id"]
    q2 = _request(pg, board, r2, b2, shot_id); q2["_document_id"] = board["id"]

    results = _spawn_both(pg, tmp_path, [("a", q1), ("b", q2)])

    # Each child really was a separate process on a separate PostgreSQL connection.
    assert len({r["pid"] for r in results}) == 2, "the children were not separate processes"
    assert len({r["backend_pid"] for r in results}) == 2, "not separate database connections"
    assert all(r["backend"] == "postgres" for r in results)
    assert all(r["database"] == pg.parent_db for r in results), \
        "a child connected to a different database than the parent"

    winners = [r for r in results if r["outcome"] == "ok"]
    losers = [r for r in results if r["outcome"] == "error"]
    assert len(winners) == 1, f"exactly one process may write, got {results}"
    assert len(losers) == 1
    # The loser must fail for a DEFINED reason, not an arbitrary error.
    assert losers[0]["error_module"].endswith("v1_capability_service") or \
        losers[0]["error"].startswith("PROMPT_ADOPTION"), \
        f"undefined loser failure: {losers[0]}"

    live = _live(pg, board["id"])
    assert live["version"] == board["version"] + 1, "PostgreSQL must gain exactly one version"
    shot = next(item for item in live["shots"] if item["id"] == shot_id)
    win_req = q1 if winners[0]["tag"] == "a" else q2
    assert shot["frame_prompt"] == (TEXT_A if winners[0]["tag"] == "a" else TEXT_B)
    proofs = live.get("prompt_adoptions") or []
    assert [p for p in proofs if p.get("request_id") == win_req["request_id"]]
    lose_req = q2 if winners[0]["tag"] == "a" else q1
    assert not [p for p in proofs if p.get("request_id") == lose_req["request_id"]], \
        "the losing process left a proof behind"


# ------------------------------------------------------------------ PG-B --
def test_PG_B_two_processes_same_request_id(pg, tmp_path):
    board, shot_id = _storyboard(pg)
    receipt, body = _prompt(pg, TEXT_A)
    shared = _request(pg, board, receipt, body, shot_id)      # ONE request identity
    q1 = dict(shared); q1["_document_id"] = board["id"]
    q2 = dict(shared); q2["_document_id"] = board["id"]

    results = _spawn_both(pg, tmp_path, [("a", q1), ("b", q2)])
    assert len({r["pid"] for r in results}) == 2
    assert all(r["backend"] == "postgres" for r in results)

    live = _live(pg, board["id"])
    assert live["version"] == board["version"] + 1, \
        "two identical request ids must produce exactly one revision"
    proofs = [p for p in (live.get("prompt_adoptions") or [])
              if p.get("request_id") == shared["request_id"]]
    assert len(proofs) == 1, "exactly one proof may exist for one request identity"

    successes = [r for r in results if r["outcome"] == "ok"]
    assert successes, "at least one process must settle successfully"
    for entry in successes:
        assert entry["result"]["version"] == live["version"], \
            "every success must describe the same committed version"
    if len(successes) == 2:
        flags = sorted(e["result"]["replayed"] for e in successes)
        assert flags == [False, True], \
            "a second identical success must be reported as a replay, not a new commit"

    # Reopening through a brand-new connection still shows exactly one valid revision.
    assert _live(pg, board["id"])["version"] == live["version"]
