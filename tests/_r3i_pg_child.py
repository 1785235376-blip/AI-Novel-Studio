"""R3-I PostgreSQL cross-process child worker.

Runs in its OWN Python process with its OWN database connection and its OWN service graph, so
the parent test exercises real cross-process contention rather than two threads sharing one
object. All inputs arrive as one JSON argv. Output is written as JSON so the parent can assert
on the real outcome.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from types import SimpleNamespace


def main() -> int:
    args = json.loads(sys.argv[1])
    out = Path(args["out"])
    barrier = Path(args["barrier"])
    tag = args["tag"]
    root = Path(args["root"])
    url = args["url"]
    sys.path.insert(0, args["repo"])

    os.environ.setdefault("EXPERIMENTAL_FEATURES", "narrative_production_v2,asset_lineage_v2")
    os.environ.setdefault("STORAGE_BACKEND", "postgres")
    os.environ.setdefault("DATABASE_URL", url)

    from app.config import Settings
    from app.creative.bible_workspace import BibleWorkspaceService
    from app.creative.prompt_adoption import PromptAdoptionService
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

    # A genuinely separate store and connection for this process.
    store = ExperimentalStore(root, "postgres", url)
    if store.backend != "postgres":
        raise SystemExit(f"child refused: backend is {store.backend!r}")
    with store._connect() as connection:
        identity = connection.execute(
            "SELECT current_database(), inet_server_port(), pg_backend_pid()").fetchone()
    bundle = create_repository_bundle(
        Settings(storage_backend="postgres", database_url=url, novel_data=root,
                 enable_cloud=False, mock_provider=True), data_root=root)
    novels = NovelService(bundle.novels, bundle.chapters)
    chapters = ChapterService(bundle.chapters)
    creative = CreativeService(store, novels, chapters)
    assets = AssetLibraryService(root)
    workspace = IndependentWorkspaceService(creative, assets, ProductionLineageService(
        store, novels, chapters, assets, MediaService(store, novels, chapters, assets)))
    bible = BibleWorkspaceService(workspace, WorldService(store, novels, chapters))
    library = PromptWorkspaceService(workspace, bible)
    adoption = PromptAdoptionService(workspace, library)

    request = SimpleNamespace(**args["request"])
    nid, scope = args["nid"], args["scope"]

    # Deterministic rendezvous: announce readiness, then wait for EVERY child to be ready.
    barrier.mkdir(parents=True, exist_ok=True)
    (barrier / f"ready-{tag}").write_text("1", encoding="utf-8")
    expected = args["peers"]
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        if len(list(barrier.glob("ready-*"))) >= expected:
            break
        time.sleep(0.02)
    else:
        raise SystemExit("child timed out waiting for peers at the rendezvous")

    payload = {"tag": tag, "pid": os.getpid(), "database": identity[0], "port": identity[1],
               "backend_pid": identity[2], "backend": store.backend}
    try:
        result = adoption.adopt_atomic(nid, scope, args["actor"], args["document_id"],
                                       args["shot_id"], request)
        payload["outcome"] = "ok"
        payload["result"] = result
    except Exception as exc:  # noqa: BLE001
        payload["outcome"] = "error"
        payload["error_type"] = type(exc).__name__
        payload["error"] = str(exc)
        payload["error_module"] = type(exc).__module__
    out.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
