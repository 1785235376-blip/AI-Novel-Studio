"""Emit the real Phase7 production-workflow projection used by the frontend contract test.

The fixture is source-bound evidence: it is produced by the landed service from a
real File-backed project (activated neutral studio, one saved intent revision, one
really imported image), so ``frontend/src/production/productionWorkflowRealProjection.test.ts``
validates a real payload instead of a hand-written one.

Deterministic except for ``generated_at`` and ``project_start.incarnation``, which
are the owner's own runtime values. The isolated root lives under the gitignored
``.runtime/`` profile, so nothing tracked is written except the fixture itself.

Usage:
    python scripts/emit_phase7_workflow_fixture.py [--out <path>]
"""
from __future__ import annotations

import argparse
import base64
from pathlib import Path
import shutil
import struct
import sys
import zlib

ROOT = Path(__file__).resolve().parents[1]
PROJECT_ID = "phase7-fixture-project"
DEFAULT_OUT = ROOT / "frontend" / "src" / "production" / "fixtures" / "productionWorkflowProjection.real.json"


def png_bytes(color=b"\x11\x22\x33"):
    """A complete CRC-correct 2 x 2 RGB PNG, decoded by the real image validator."""
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", 2, 2, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress((b"\x00" + color * 2) * 2))
            + chunk(b"IEND", b""))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args(argv)
    target = Path(args.out)
    if not target.is_absolute():
        target = ROOT / target
    data_root = ROOT / ".runtime" / "phase7-fixture" / "isolated"
    shutil.rmtree(data_root, ignore_errors=True)
    data_root.mkdir(parents=True, exist_ok=True)

    from app.config import Settings
    from app.creative.production_workflow import ProductionWorkflowService
    from app.creative.service import CreativeService
    from app.creative.workspace import IndependentWorkspaceService
    from app.experimental.media import MediaService
    from app.experimental.production_lineage import ProductionLineageService
    from app.experimental.store import ExperimentalStore
    from app.repositories.factory import create_repository_bundle
    from app.services import NovelService, ChapterService
    from app.services.asset_library_service import AssetLibraryService

    bundle = create_repository_bundle(
        Settings(storage_backend="file", database_url="", novel_data=data_root,
                 enable_cloud=False, mock_provider=True), data_root=data_root)
    novels, chapters = NovelService(bundle.novels, bundle.chapters), ChapterService(bundle.chapters)
    store = ExperimentalStore(data_root, "file", "")
    assets = AssetLibraryService(data_root)
    creative = CreativeService(store, novels, chapters)
    media = MediaService(store, novels, chapters, assets)
    lineage = ProductionLineageService(store, novels, chapters, assets, media)
    workspace = IndependentWorkspaceService(creative, assets, lineage)
    workflow = ProductionWorkflowService(workspace, creative)

    novels.create({"id": PROJECT_ID, "title": "Phase7 fixture project"})
    scope = {"mode": "local", "novel_id": PROJECT_ID}
    actor = "phase7-fixture-author"
    workspace.activate(PROJECT_ID, scope, actor)
    # Opening the neutral studio already saves the preference row at version 1, so
    # the client submits the version it just read; a null expectation fails closed.
    saved = workflow.projection(PROJECT_ID, scope)["creative_intent"]["version"]
    workflow.update_intent(PROJECT_ID, scope, actor, {
        "expected_version": saved, "preset": "editing",
        "values": [{"intent_id": "ai_short_film", "label": "短片", "selected": True},
                   {"intent_id": "custom", "label": "实验短片", "selected": True}]})
    workspace.import_asset(PROJECT_ID, scope, actor, {
        "filename": "external.png", "kind": "image",
        "content_base64": base64.b64encode(png_bytes()).decode("ascii"),
        "idempotency_key": "phase7-fixture-image"})

    projection = workflow.projection(PROJECT_ID, scope)
    import json
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(projection, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"WROTE {target.relative_to(ROOT).as_posix()}")
    print("modules:", [(row["id"], row["status"], row["asset_count"]) for row in projection["modules"]])
    print("intent:", projection["creative_intent"]["version"], projection["creative_intent"]["preset"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
