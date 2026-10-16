"""Additive reconciliation scenarios and their minimal independent fixture support."""

from __future__ import annotations

import base64

import os

from pathlib import Path

import shutil

import struct

from types import SimpleNamespace

from urllib.parse import unquote, urlparse

from uuid import uuid4

import zlib

import pytest

TEST_URL = os.getenv("TEST_POSTGRES_DATABASE_URL", "")

FLAGS = "narrative_production_v2,asset_lineage_v2"

def png_bytes(color=b"\x11\x22\x33"):
    """A complete CRC-correct 2 x 2 RGB PNG, decoded by the real validator."""
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", 2, 2, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress((b"\x00" + color * 2) * 2))
            + chunk(b"IEND", b""))

@pytest.fixture
def decoders():
    # Missing decoders must be reported as a failed acceptance prerequisite,
    # never converted into a passing fake media contract or silent skip.
    for executable in ("ffmpeg", "ffprobe"):
        assert shutil.which(executable), f"real M1 media tests require {executable}"

def services(root, backend, url, novels, chapters):
    from app.creative.service import CreativeService
    from app.creative.workspace import IndependentWorkspaceService
    from app.experimental.media import MediaService
    from app.experimental.production_lineage import ProductionLineageService
    from app.experimental.store import ExperimentalStore
    from app.services.asset_library_service import AssetLibraryService
    raw_store = ExperimentalStore(root, backend, url)
    assets = AssetLibraryService(root)
    creative = CreativeService(raw_store, novels, chapters)
    media = MediaService(raw_store, novels, chapters, assets)
    lineage = ProductionLineageService(raw_store, novels, chapters, assets, media)
    return IndependentWorkspaceService(creative, assets, lineage)

@pytest.fixture(params=[
    pytest.param("file", marks=pytest.mark.file_backend_only),
    pytest.param("postgres", marks=pytest.mark.postgres_backend_only),
])
def rig(request, tmp_path, monkeypatch):
    from app.config import Settings
    from app.repositories.factory import create_repository_bundle
    from app.services import NovelService, ChapterService
    root = Path(__file__).resolve().parents[1]
    assert Path(os.environ["PROJECT_ROOT"]).resolve() == root
    for key in ("LOCALAPPDATA", "NOVEL_DATA_PATH"):
        assert Path(os.environ[key]).resolve().is_relative_to(root / ".runtime")
    assert tmp_path.resolve().is_relative_to(root / ".runtime")
    backend = request.param
    url = TEST_URL if backend == "postgres" else ""
    if backend == "postgres" and not url:
        pytest.fail("M1 PostgreSQL cases require a real TEST_POSTGRES_DATABASE_URL")
    monkeypatch.setenv("EXPERIMENTAL_FEATURES", FLAGS)
    monkeypatch.delenv("V1_ACCEPTANCE_MODE", raising=False)
    bundle = create_repository_bundle(
        Settings(storage_backend=backend, database_url=url, novel_data=tmp_path,
                 enable_cloud=False, mock_provider=True), data_root=tmp_path)
    novels, chapters = NovelService(bundle.novels, bundle.chapters), ChapterService(bundle.chapters)
    project_ids = set()

    def create_project(title="Blank independent studio", nid=None):
        row = novels.create({"id": nid or "v2-independent-" + uuid4().hex, "title": title})
        project_ids.add(row["id"])
        return row["id"]

    nid = create_project()
    service = services(tmp_path, backend, url, novels, chapters)
    assert chapters.list(nid) == []
    if backend == "postgres":
        assert bundle.novels.database.engine.dialect.name == "postgresql"
        with service.store._connect() as connection:
            database, server = connection.execute("SELECT current_database(), version()").fetchone()
            expected_database = unquote(urlparse(url).path.removeprefix("/"))
            assert expected_database and database == expected_database and "PostgreSQL" in server
            owner = connection.execute("SELECT id FROM novels WHERE slug = %s", (nid,)).fetchone()
            assert owner is not None
            assert connection.execute("SELECT count(*) FROM chapters WHERE novel_id = %s", (owner[0],)).fetchone()[0] == 0
    yield SimpleNamespace(nid=nid, scope={"mode": "local", "novel_id": nid}, actor="local-studio-author",
                          root=tmp_path, backend=backend, url=url, novels=novels, chapters=chapters,
                          service=service, assets=service.assets, store=service.store,
                          raw_store=service.store.store, bundle=bundle, create_project=create_project)
    if backend == "postgres":
        try:
            with service.store._connect() as connection:
                for project_id in project_ids:
                    connection.execute("DELETE FROM experimental_scope_documents WHERE novel_id = %s", (project_id,))
            for project_id in project_ids:
                try:
                    novels.delete(project_id)
                except FileNotFoundError:
                    pass
        finally:
            bundle.novels.database.engine.dispose()

def upload(data=None, *, filename="external.png", kind="image", key=None):
    return {"filename": filename, "kind": kind, "content_base64": base64.b64encode(data if data is not None else png_bytes()).decode(),
            "idempotency_key": key or uuid4().hex}

def import_asset(rig, *, service=None, scope=None, **kw):
    return (service or rig.service).import_asset(rig.nid, scope or rig.scope, rig.actor, upload(**kw))
