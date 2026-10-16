"""Additive reconciliation scenarios and their minimal independent fixture support."""

from __future__ import annotations

import os

from types import SimpleNamespace

from uuid import uuid4

import pytest

from app.config import Settings

from app.experimental.store import ExperimentalStore

from app.repositories.factory import create_repository_bundle

from app.services import NovelService, ChapterService

from app.services.asset_library_service import AssetLibraryService

from app.services.screenplay_service import ScreenplayService

TEST_URL = os.getenv("TEST_POSTGRES_DATABASE_URL", "")

@pytest.fixture(params=[pytest.param("file", marks=pytest.mark.file_backend_only),
                        pytest.param("postgres", marks=[pytest.mark.postgres_backend_only,
                            pytest.mark.skipif(not TEST_URL, reason="NOT_RUN: disposable PostgreSQL endpoint not configured")])])
def rig(request, tmp_path):
    backend = request.param
    config = Settings(storage_backend=backend, database_url=TEST_URL if backend == "postgres" else "", novel_data=tmp_path)
    bundle = create_repository_bundle(config, data_root=tmp_path)
    novels, chapters = NovelService(bundle.novels, bundle.chapters), ChapterService(bundle.chapters)
    nid = novels.create({"id": "r3-media-" + uuid4().hex, "title": "Synthetic R3 media"})["id"]
    chapter = chapters.create(nid, {"title": "Chapter", "content": 'Alice: “Hello.”\nThen a voice answered: “Unknown speaker.”'})
    chapter = chapters.get(chapter["id"])
    novels.upsert_character(nid, "alice", {"name": "Alice", "personality": "Careful"})
    scope = {"mode": "local", "novel_id": nid}
    store = ExperimentalStore(tmp_path, backend, TEST_URL if backend == "postgres" else "")
    assets = AssetLibraryService(tmp_path)
    screenplays = ScreenplayService(bundle.novels, bundle.chapters)
    yield SimpleNamespace(nid=nid, scope=scope, actor="local-author", store=store, assets=assets, novels=novels, chapters=chapters,
                          chapter=chapter, screenplays=screenplays, root=tmp_path, bundle=bundle, backend=backend)
    if backend == "postgres":
        try:
            with store._connect() as connection:
                connection.execute("DELETE FROM experimental_scope_documents WHERE novel_id = %s", (nid,))
            novels.delete(nid)
        finally:
            bundle.novels.database.engine.dispose()
