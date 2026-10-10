"""M1 independent studios over real original File/PostgreSQL project owners.

Run with scripts/run_v2_checks.py and an owned --basetemp. PostgreSQL cases
require a real dedicated TEST_POSTGRES_DATABASE_URL; no Session replacement,
provider invocation, model download, or fabricated decoded-media result is used.
"""
from __future__ import annotations

import base64
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
from threading import Barrier, Event
from types import SimpleNamespace
from urllib.parse import unquote, urlparse
from uuid import uuid4
import wave
import zlib

import pytest


TEST_URL = os.getenv("TEST_POSTGRES_DATABASE_URL", "")
FLAGS = "narrative_production_v2,asset_lineage_v2"
RESERVED = {"_required_features", "_owner_actor_id", "_origin_provenance", "_project_binding"}


def png_bytes(color=b"\x11\x22\x33"):
    """A complete CRC-correct 2 x 2 RGB PNG, decoded by the real validator."""
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", 2, 2, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress((b"\x00" + color * 2) * 2))
            + chunk(b"IEND", b""))


def wav_bytes():
    output = io.BytesIO()
    with wave.open(output, "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(8000)
        writer.writeframes(b"\x00\x00" * 800)
    return output.getvalue()


@pytest.fixture
def decoders():
    # Missing decoders must be reported as a failed acceptance prerequisite,
    # never converted into a passing fake media contract or silent skip.
    for executable in ("ffmpeg", "ffprobe"):
        assert shutil.which(executable), f"real M1 media tests require {executable}"


@pytest.fixture
def media_bytes(request, tmp_path, decoders):
    kind = request.param
    if kind == "image":
        return kind, "external.png", "image/png", png_bytes()
    if kind == "audio":
        return kind, "external.wav", "audio/wav", wav_bytes()
    clip = tmp_path / "external.mp4"
    subprocess.run([
        shutil.which("ffmpeg"), "-nostdin", "-v", "error", "-threads", "1",
        "-f", "lavfi", "-i", "color=c=blue:s=32x32:r=10:d=0.3",
        "-c:v", "mpeg4", "-threads", "1", "-y", str(clip),
    ], check=True, capture_output=True, timeout=20)
    return kind, clip.name, "video/mp4", clip.read_bytes()


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


def reopened(rig):
    return services(rig.root, rig.backend, rig.url, rig.novels, rig.chapters)


def upload(data=None, *, filename="external.png", kind="image", key=None):
    return {"filename": filename, "kind": kind, "content_base64": base64.b64encode(data if data is not None else png_bytes()).decode(),
            "idempotency_key": key or uuid4().hex}


def import_asset(rig, *, service=None, scope=None, **kw):
    return (service or rig.service).import_asset(rig.nid, scope or rig.scope, rig.actor, upload(**kw))


def declaration(version, parents=(), **kw):
    return {"expected_version": version,
            "origin": "DERIVED_PROCESSING" if parents else "EXTERNAL_IMPORT",
            "parent_asset_ids": list(parents),
            "license": {"label": "Author-owned fixture", "source": "Local test fixture", "note": "Author declaration only"},
            **kw}


def branch_scope(rig, branch="branch-a"):
    return {"mode": "collaboration", "novel_id": rig.nid, "workspace_id": "workspace-a",
            "storyline_id": "storyline-a", "branch_id": branch}


def stored_asset(rig, aid):
    return json.loads((rig.assets.root / f"{aid}.json").read_text(encoding="utf-8"))


def asset_files(rig):
    return {path.name: path.read_bytes() for path in rig.assets.root.iterdir() if path.is_file()}


def assert_public(value):
    if isinstance(value, dict):
        assert not RESERVED.intersection(value), value
        for child in value.values():
            assert_public(child)
    elif isinstance(value, list):
        for child in value:
            assert_public(child)


def test_blank_original_owner_defaults_have_zero_chapters_and_no_hidden_jobs(rig):
    from app.creative.workspace import PREFERENCES
    view = rig.service.project(rig.nid, rig.scope)
    assert view["project"] == {"id": rig.nid, "title": "Blank independent studio", "entry_kind": "LEGACY"}
    assert view["preferences"] == {"version": 0, "intents": [], "preset": "BLANK", "custom_intent": ""}
    assert view["capabilities"]["chapter_required"] is False
    assert view["capabilities"]["model_required"] is False
    assert view["capabilities"]["intent_is_permission"] is False
    assert set(view["capabilities"]["asset_kinds"]) == {"image", "video", "audio"}
    assert rig.chapters.list(rig.nid) == []
    assert rig.service.creative.list(rig.nid, rig.scope) == []
    assert rig.service.list_assets(rig.nid, rig.scope) == {"items": []}
    collections = rig.raw_store.read(rig.nid, rig.scope)["collections"]
    assert not collections.get(PREFERENCES)
    for name in ("media_tasks", "media_proposals", "creative_director_proposals_v2"):
        assert not collections.get(name)


@pytest.mark.parametrize("media_bytes", ["image", "video", "audio"], indirect=True)
def test_real_external_media_owner_provenance_restart_and_original_byte_export(rig, media_bytes):
    from app.media_files import inspect_image, inspect_media
    activated = rig.service.activate(rig.nid, rig.scope, rig.actor)
    assert activated["project"]["entry_kind"] == "NEUTRAL_STUDIO"
    assert activated["preferences"] == {"version": 1, "intents": [], "preset": "BLANK", "custom_intent": ""}
    assert rig.chapters.list(rig.nid) == []
    kind, filename, mime, data = media_bytes
    measured = inspect_image(data) if kind == "image" else inspect_media(data, kind)
    assert measured["media_type"] == mime
    body = upload(data, filename=filename, kind=kind, key="roundtrip")
    row = rig.service.import_asset(rig.nid, rig.scope, rig.actor, body)
    digest = hashlib.sha256(data).hexdigest()
    assert row["version"] == 1 and row["sha256"] == digest
    assert row["media_type"] == mime and row["kind"] == kind and row["size"] == len(data)
    assert row["provenance"]["integrity"] == "VERIFIED"
    assert_public(row)
    raw = stored_asset(rig, row["id"])
    assert raw["_project_binding"] == {"novel_id": rig.nid, "branch_id": None,
                                       "incarnation": rig.store.incarnation(rig.nid),
                                       "scope_key": rig.store.key(rig.nid, rig.scope)}
    assert raw["_required_features"] == ["narrative_production_v2"]
    assert (rig.assets.root / f"{row['id']}.bin").read_bytes() == data
    assert not rig.raw_store.read(rig.nid, rig.scope)["collections"].get("assets")
    annotated = rig.service.annotate(rig.nid, rig.scope, rig.actor, row["id"], declaration(row["version"]))
    assert annotated["version"] == row["version"] + 1
    assert annotated["provenance"]["origin"] == "EXTERNAL_IMPORT"
    assert annotated["provenance"]["license_verification"] == "AUTHOR_DECLARATION_NOT_LEGAL_VERIFICATION"
    assert annotated["provenance"]["producer"]["declared_by"] == rig.actor
    second = reopened(rig)
    assert second.asset(rig.nid, rig.scope, row["id"]) == annotated
    assert second.list_assets(rig.nid, rig.scope) == {"items": [annotated]}
    meta, content = second.download(rig.nid, rig.scope, row["id"])
    assert content == data and hashlib.sha256(content).hexdigest() == digest
    assert meta["sha256"] == digest and meta["version"] == annotated["version"]
    assert_public(meta)
    assert rig.chapters.list(rig.nid) == []


def test_explicit_activation_is_scoped_idempotent_and_not_an_intent_side_effect(rig, decoders):
    from app.creative.workspace import PREFERENCES
    image = import_asset(rig)
    before_assets = asset_files(rig)
    before_owner = rig.novels.get(rig.nid)
    capabilities = rig.service.project(rig.nid, rig.scope)["capabilities"]
    first = rig.service.activate(rig.nid, rig.scope, rig.actor)
    saved = rig.raw_store.read(rig.nid, rig.scope)
    assert first["project"]["entry_kind"] == "NEUTRAL_STUDIO"
    assert first["preferences"]["version"] == 1
    assert first["capabilities"] == capabilities
    assert reopened(rig).activate(rig.nid, rig.scope, "another-actor") == first
    assert rig.raw_store.read(rig.nid, rig.scope) == saved
    assert rig.novels.get(rig.nid) == before_owner
    assert asset_files(rig) == before_assets
    assert rig.chapters.list(rig.nid) == []
    assert rig.service.asset(rig.nid, rig.scope, image["id"])["sha256"] == image["sha256"]
    preferences = rig.service.preferences(rig.nid, rig.scope, rig.actor,
                                          {"expected_version": 1, "preset": "TEXT", "intents": ["NOVEL_WRITING"]})
    assert preferences["version"] == 2
    assert rig.service.project(rig.nid, rig.scope)["project"]["entry_kind"] == "NEUTRAL_STUDIO"
    branch = branch_scope(rig)
    assert rig.service.project(rig.nid, branch)["project"]["entry_kind"] == "LEGACY"
    assert rig.service.project(rig.nid, branch)["preferences"]["version"] == 0
    row = next(iter(rig.store.read(rig.nid, rig.scope)["collections"][PREFERENCES].values()))
    assert row["entry_kind"] == row["history"][0]["entry_kind"] == "NEUTRAL_STUDIO"


def test_activation_of_existing_preferences_records_history_without_resetting_them(rig):
    from app.creative.workspace import PREFERENCES
    original = rig.service.preferences(rig.nid, rig.scope, rig.actor,
                                       {"expected_version": 0, "preset": "AUDIO", "intents": ["CUSTOM"], "custom_intent": "Field recordings"})
    assert rig.service.project(rig.nid, rig.scope)["project"]["entry_kind"] == "LEGACY"
    activated = rig.service.activate(rig.nid, rig.scope, "studio-editor")
    assert activated["preferences"] == {**original, "version": 2}
    assert activated["project"]["entry_kind"] == "NEUTRAL_STUDIO"
    row = next(iter(rig.store.read(rig.nid, rig.scope)["collections"][PREFERENCES].values()))
    assert len(row["history"]) == 1 and row["history"][0]["version"] == 1
    assert row["history"][0].get("entry_kind", "LEGACY") == "LEGACY"
    assert row["created_by"] == rig.actor and row["updated_by"] == "studio-editor"


def test_activation_guard_rollback_and_recreate_restore_default_entry_kind(rig):
    calls = []
    def revoked():
        calls.append(None)
        if len(calls) == 2:
            raise PermissionError("activation permission revoked")
    before = rig.raw_store.read(rig.nid, rig.scope)
    with pytest.raises(PermissionError):
        rig.service.activate(rig.nid, rig.scope, rig.actor, revoked)
    assert rig.raw_store.read(rig.nid, rig.scope) == before
    rig.service.activate(rig.nid, rig.scope, rig.actor)
    identity = rig.store.incarnation(rig.nid)
    rig.novels.delete(rig.nid)
    rig.create_project("Recreated blank project", nid=rig.nid)
    view = reopened(rig).project(rig.nid, rig.scope)
    assert view["project"]["entry_kind"] == "LEGACY"
    assert view["preferences"]["version"] == 0
    assert rig.store.incarnation(rig.nid) != identity
    assert rig.chapters.list(rig.nid) == []


def test_fresh_python_process_reopens_real_asset_and_preference_owners(rig, decoders):
    row = import_asset(rig)
    prefs = rig.service.preferences(rig.nid, rig.scope, rig.actor,
                                   {"expected_version": 0, "preset": "IMAGE", "intents": ["IMAGE_DESIGN"]})
    script = """
import base64,json,os,sys
from pathlib import Path
from app.config import Settings
from app.repositories.factory import create_repository_bundle
from app.services import NovelService,ChapterService
from app.services.asset_library_service import AssetLibraryService
from app.experimental.store import ExperimentalStore
from app.experimental.media import MediaService
from app.experimental.production_lineage import ProductionLineageService
from app.creative.service import CreativeService
from app.creative.workspace import IndependentWorkspaceService
root=Path(sys.argv[1]); backend=sys.argv[2]; nid=sys.argv[3]; aid=sys.argv[4]
url=os.getenv('M1_TEST_DATABASE_URL','')
bundle=create_repository_bundle(Settings(storage_backend=backend,database_url=url,novel_data=root),data_root=root)
novels=NovelService(bundle.novels,bundle.chapters); chapters=ChapterService(bundle.chapters)
store=ExperimentalStore(root,backend,url); assets=AssetLibraryService(root)
creative=CreativeService(store,novels,chapters)
media=MediaService(store,novels,chapters,assets)
lineage=ProductionLineageService(store,novels,chapters,assets,media)
workspace=IndependentWorkspaceService(creative,assets,lineage)
scope={'mode':'local','novel_id':nid}
meta,data=workspace.download(nid,scope,aid)
print(json.dumps({'asset':workspace.asset(nid,scope,aid),'bytes':base64.b64encode(data).decode(),
                  'preferences':workspace.project(nid,scope)['preferences'],'chapters':chapters.list(nid)}))
if backend=='postgres': bundle.novels.database.engine.dispose()
"""
    result = subprocess.run([sys.executable, "-B", "-X", "utf8", "-c", script,
                             str(rig.root), rig.backend, rig.nid, row["id"]],
                            cwd=Path(__file__).resolve().parents[1],
                            env={**os.environ, "M1_TEST_DATABASE_URL": rig.url, "EXPERIMENTAL_FEATURES": FLAGS},
                            capture_output=True, text=True, encoding="utf-8", timeout=45, check=False)
    assert result.returncode == 0, result.stderr
    actual = json.loads(result.stdout)
    assert actual["asset"] == row and actual["preferences"] == prefs
    assert base64.b64decode(actual["bytes"]) == png_bytes() and actual["chapters"] == []


def test_preference_cas_history_and_real_postgres_jsonb_or_file_persistence(rig):
    from app.creative.project_store import BINDING
    from app.creative.workspace import PREFERENCES
    from app.services.v1_capability_service import CapabilityVersionConflict
    one = rig.service.preferences(rig.nid, rig.scope, rig.actor,
                                  {"expected_version": 0, "intents": ["AI_SHORT_FILM", "IMAGE_DESIGN"], "preset": "MIXED"})
    second = reopened(rig)
    two = second.preferences(rig.nid, rig.scope, "editor",
                             {"expected_version": 1, "intents": ["CUSTOM"], "preset": "AUDIO", "custom_intent": "Sound experiment"})
    with pytest.raises(CapabilityVersionConflict):
        rig.service.preferences(rig.nid, rig.scope, rig.actor, {"expected_version": 1, "preset": "TEXT"})
    assert second.project(rig.nid, rig.scope)["preferences"] == two
    assert one["version"] == 1 and two["version"] == 2
    if rig.backend == "postgres":
        with rig.store._connect() as connection:
            saved, revision = connection.execute(
                "SELECT document, revision FROM experimental_scope_documents WHERE scope_key = %s",
                (rig.store.key(rig.nid, rig.scope),)).fetchone()
            owner_id = connection.execute("SELECT id FROM novels WHERE slug = %s", (rig.nid,)).fetchone()[0]
        # The actual owner inserts revision 1 and advances once per changed
        # document transaction; two preference writes therefore persist 3.
        assert revision == 3
        expected_binding = "postgres:" + str(owner_id)
    else:
        saved = json.loads(rig.raw_store.path(rig.nid, rig.scope).read_text(encoding="utf-8"))
        expected_binding = rig.store.incarnation(rig.nid)
    rows = list(saved["collections"][PREFERENCES].values())
    assert len(rows) == 1
    row = rows[0]
    assert row[BINDING] == expected_binding and row["scope"] == rig.scope
    assert row["created_by"] == rig.actor and row["updated_by"] == "editor"
    assert [item["version"] for item in row["history"]] == [1]
    assert row["history"][0]["intents"] == one["intents"]
    assert BINDING not in one and BINDING not in two


@pytest.mark.parametrize("preset", ["BLANK", "TEXT", "IMAGE", "VIDEO", "AUDIO", "EDITING", "MIXED"])
def test_intents_and_presets_neither_mutate_chapters_assets_nor_restrict_types(rig, decoders, preset):
    chapter = rig.chapters.create(rig.nid, {"title": "Existing unrelated chapter", "content": "Leave this manuscript alone."})
    chapter_before = rig.chapters.get(chapter["id"])
    image = import_asset(rig)
    old_files = asset_files(rig)
    capabilities = rig.service.project(rig.nid, rig.scope)["capabilities"]
    rig.service.preferences(rig.nid, rig.scope, rig.actor,
                            {"expected_version": 0, "preset": preset, "intents": ["NOVEL_WRITING", "COMMERCIAL_CG", "PODCAST_VOICE"]})
    assert rig.chapters.get(chapter["id"]) == chapter_before
    assert asset_files(rig) == old_files
    assert rig.service.asset(rig.nid, rig.scope, image["id"]) == image
    assert rig.service.project(rig.nid, rig.scope)["capabilities"] == capabilities
    assert rig.service.project(rig.nid, rig.scope)["project"]["entry_kind"] == "LEGACY"
    audio = import_asset(rig, data=wav_bytes(), filename="audio.wav", kind="audio")
    assert audio["kind"] == "audio"
    assert rig.chapters.get(chapter["id"]) == chapter_before


@pytest.mark.parametrize("bad", [
    {"intents": ["IMAGE_DESIGN", "IMAGE_DESIGN"]}, {"intents": ["ADMIN"]},
    {"preset": "EXECUTE"}, {"custom_intent": "x" * 241}, {"chapter_ids": ["invented"]},
    {"project_incarnation": "forged"}, {"entry_kind": "NEUTRAL_STUDIO"},
    {"expected_version": True}, {"expected_version": "0"},
])
def test_invalid_preferences_do_not_write_or_grant_capabilities(rig, bad):
    before = rig.raw_store.read(rig.nid, rig.scope)
    with pytest.raises(ValueError):
        rig.service.preferences(rig.nid, rig.scope, rig.actor, {"expected_version": 0, **bad})
    assert rig.raw_store.read(rig.nid, rig.scope) == before
    assert rig.chapters.list(rig.nid) == []


def test_preference_guard_rollback_and_history_capacity(rig, monkeypatch):
    calls = []
    def revoked():
        calls.append(None)
        if len(calls) == 2:
            raise PermissionError("authority revoked")
    before = rig.raw_store.read(rig.nid, rig.scope)
    with pytest.raises(PermissionError):
        rig.service.preferences(rig.nid, rig.scope, rig.actor, {"expected_version": 0, "preset": "TEXT"}, guard=revoked)
    assert rig.raw_store.read(rig.nid, rig.scope) == before
    rig.service.preferences(rig.nid, rig.scope, rig.actor, {"expected_version": 0, "preset": "IMAGE"})
    monkeypatch.setattr(rig.service, "MAX_PREFERENCE_HISTORY", 1)
    rig.service.preferences(rig.nid, rig.scope, rig.actor, {"expected_version": 1, "preset": "VIDEO"})
    before = rig.raw_store.read(rig.nid, rig.scope)
    with pytest.raises(ValueError, match="HISTORY_LIMIT"):
        rig.service.preferences(rig.nid, rig.scope, rig.actor, {"expected_version": 2, "preset": "MIXED"})
    assert rig.raw_store.read(rig.nid, rig.scope) == before


def test_independent_preference_writers_commit_exactly_one_initial_revision(rig):
    from app.creative.workspace import PREFERENCES
    from app.services.v1_capability_service import CapabilityVersionConflict
    barrier = Barrier(2)
    def write(preset):
        service = reopened(rig)
        barrier.wait(timeout=10)
        try:
            return service.preferences(rig.nid, rig.scope, preset, {"expected_version": 0, "preset": preset})
        except CapabilityVersionConflict:
            return "CONFLICT"
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(write, ("IMAGE", "VIDEO")))
    assert results.count("CONFLICT") == 1
    winner = next(row for row in results if row != "CONFLICT")
    assert winner["version"] == 1
    assert rig.service.project(rig.nid, rig.scope)["preferences"] == winner
    assert len(rig.store.read(rig.nid, rig.scope)["collections"][PREFERENCES]) == 1


def test_idempotency_reuses_original_identity_and_rejects_changed_upload(rig, decoders):
    from app.services.asset_library_service import AssetIdempotencyConflict
    body = upload(key="retry-external")
    row = rig.service.import_asset(rig.nid, rig.scope, rig.actor, body)
    before = asset_files(rig)
    assert reopened(rig).import_asset(rig.nid, rig.scope, rig.actor, body) == row
    assert asset_files(rig) == before
    for changed in (upload(png_bytes(b"\xff\x00\x00"), key="retry-external"),
                    {**body, "filename": "renamed.png"}):
        with pytest.raises(AssetIdempotencyConflict):
            rig.service.import_asset(rig.nid, rig.scope, rig.actor, changed)
        assert asset_files(rig) == before
    assert len(rig.service.list_assets(rig.nid, rig.scope)["items"]) == 1


def test_simultaneous_idempotent_imports_share_one_binary_and_owner_record(rig, decoders):
    barrier, body = Barrier(2), upload(key="concurrent-retry")
    def create(_):
        service = reopened(rig)
        barrier.wait(timeout=10)
        return service.import_asset(rig.nid, rig.scope, rig.actor, body)
    with ThreadPoolExecutor(max_workers=2) as pool:
        rows = list(pool.map(create, range(2)))
    assert rows[0] == rows[1]
    assert set(asset_files(rig)) == {rows[0]["id"] + ".json", rows[0]["id"] + ".bin"}


@pytest.mark.parametrize("bad", [
    {"content_base64": "%%%"}, {"content_base64": ""}, {"filename": "   "},
    {"kind": "executable"}, {"idempotency_key": ""}, {"novel_id": "forged"},
    {"branch_id": "forged"}, {"_project_binding": {"incarnation": "forged"}},
    {"_required_features": []}, {"source_asset_ids": ["forged"]}, {"version": 99},
    {"media_type": "image/png"}, {"source_job_id": "forged"},
])
def test_import_rejects_untrusted_metadata_and_invalid_inputs_without_writes(rig, bad):
    before = asset_files(rig)
    with pytest.raises(ValueError):
        rig.service.import_asset(rig.nid, rig.scope, rig.actor, {**upload(), **bad})
    assert asset_files(rig) == before
    assert rig.chapters.list(rig.nid) == []


@pytest.mark.parametrize("kind,data", [
    ("image", b"opaque text with a png filename"), ("image", b"\x89PNG\r\n\x1a\n"),
    ("video", b"\x00\x00\x00\x18ftypmp42"), ("video", png_bytes()),
    ("audio", b"RIFF\x00\x00\x00\x00WAVEtruncated"),
])
def test_actual_decoder_rejects_malformed_or_mislabeled_media_without_artifacts(rig, decoders, kind, data):
    from app.media_files import MediaValidationError
    with pytest.raises(MediaValidationError):
        import_asset(rig, data=data, filename="misleading.png", kind=kind)
    assert asset_files(rig) == {}
    assert rig.service.list_assets(rig.nid, rig.scope) == {"items": []}


def test_import_measures_mime_from_bytes_and_sanitizes_filename(rig, decoders):
    row = import_asset(rig, filename="../../private\\external.txt\r\n")
    assert row["filename"] == "external.txt"
    assert row["media_type"] == "image/png"
    assert rig.service.download(rig.nid, rig.scope, row["id"])[1] == png_bytes()
    assert all(path.parent == rig.assets.root for path in rig.assets.root.glob("*.*") if path.is_file())


def test_missing_real_media_validator_fails_closed_but_pcm_audio_remains_decoded(rig, monkeypatch):
    import app.media_files as module
    from app.media_files import MediaValidationError
    monkeypatch.setattr(module.shutil, "which", lambda _name: None)
    with pytest.raises(MediaValidationError, match="MEDIA_VALIDATOR_NOT_CONFIGURED"):
        import_asset(rig)
    assert asset_files(rig) == {}
    row = import_asset(rig, data=wav_bytes(), filename="audio.wav", kind="audio")
    assert row["media_type"] == "audio/wav"
    assert rig.service.download(rig.nid, rig.scope, row["id"])[1] == wav_bytes()


def test_decoded_size_limit_is_checked_before_decode_or_persistence(rig, monkeypatch):
    monkeypatch.setattr(rig.assets, "MAX_BYTES", len(png_bytes()) - 1)
    with pytest.raises(ValueError, match="SIZE_INVALID"):
        import_asset(rig)
    assert asset_files(rig) == {}


@pytest.mark.parametrize("quota", ["MAX_ASSETS", "MAX_PROJECT_BYTES"])
def test_project_quota_counts_trash_allows_retries_and_does_not_touch_other_owners(rig, decoders, monkeypatch, quota):
    from app.services.asset_library_service import AssetIdempotencyConflict
    other = rig.create_project("Unrelated asset owner")
    other_scope = {"mode": "local", "novel_id": other}
    unrelated = rig.service.import_asset(other, other_scope, rig.actor, upload(key="unrelated"))
    body = upload(key="quota-retry")
    first = rig.service.import_asset(rig.nid, rig.scope, rig.actor, body)
    monkeypatch.setattr(rig.service, quota, 1 if quota == "MAX_ASSETS" else len(png_bytes()))
    assert rig.service.import_asset(rig.nid, rig.scope, rig.actor, body) == first
    before = asset_files(rig)
    with pytest.raises(ValueError, match="PROJECT_ASSET_QUOTA"):
        import_asset(rig)
    assert asset_files(rig) == before
    deleted = rig.service.lifecycle(rig.nid, rig.scope, first["id"], first["version"])
    assert deleted["deleted_at"]
    with pytest.raises(ValueError, match="PROJECT_ASSET_QUOTA"):
        import_asset(rig)
    with pytest.raises(AssetIdempotencyConflict, match="deleted"):
        rig.service.import_asset(rig.nid, rig.scope, rig.actor, body)
    assert rig.service.download(other, other_scope, unrelated["id"])[1] == png_bytes()


def test_independent_import_services_cannot_race_past_owner_quota(rig, decoders, monkeypatch):
    from app.creative.workspace import IndependentWorkspaceService
    monkeypatch.setattr(IndependentWorkspaceService, "MAX_ASSETS", 1)
    barrier = Barrier(2)
    def create(index):
        service = reopened(rig)
        barrier.wait(timeout=10)
        try:
            return service.import_asset(rig.nid, rig.scope, rig.actor, upload(key=f"quota-{index}"))
        except ValueError as exc:
            assert str(exc) == "CREATIVE_PROJECT_ASSET_QUOTA"
            return "QUOTA"
    with ThreadPoolExecutor(max_workers=2) as pool:
        rows = list(pool.map(create, range(2)))
    assert rows.count("QUOTA") == 1
    assert len(rig.service.list_assets(rig.nid, rig.scope)["items"]) == 1
    assert len(asset_files(rig)) == 2


def test_lineage_versions_history_and_bytes_remain_owned_by_existing_asset_service(rig, decoders):
    from app.services.v1_capability_service import CapabilityVersionConflict
    source, child = import_asset(rig), import_asset(rig)
    declared = rig.service.annotate(rig.nid, rig.scope, rig.actor, source["id"], declaration(1))
    revised = rig.service.annotate(rig.nid, rig.scope, "reviewer", source["id"],
                                   declaration(2, license={"label": "CC0", "source": "Author declaration", "note": "Revised statement"}))
    assert revised["version"] == 3
    evidence = stored_asset(rig, source["id"])["parameters"]["asset_lineage_v2"]
    assert evidence["output_digest"] == source["sha256"]
    assert evidence["history"][0]["asset_version"] == declared["version"]
    assert evidence["history"][0]["license"]["label"] == "Author-owned fixture"
    assert revised["provenance"]["declaration_history_versions"] == [2]
    with pytest.raises(CapabilityVersionConflict):
        rig.service.annotate(rig.nid, rig.scope, rig.actor, source["id"], declaration(2))
    derived = rig.service.annotate(rig.nid, rig.scope, rig.actor, child["id"], declaration(1, [source["id"]]))
    assert derived["source_asset_ids"] == [source["id"]]
    assert derived["provenance"]["parents"][0] == {
        "id": source["id"], "label": source["filename"], "version": revised["version"],
        "digest": source["sha256"], "state": "CURRENT"}
    assert rig.service.download(rig.nid, rig.scope, source["id"])[1] == png_bytes()
    assert rig.service.download(rig.nid, rig.scope, child["id"])[1] == png_bytes()
    assert_public(derived)


def test_lineage_rejects_cycles_parent_erasure_wrong_project_and_wrong_branch(rig, decoders):
    source, child = import_asset(rig), import_asset(rig)
    derived = rig.service.annotate(rig.nid, rig.scope, rig.actor, child["id"], declaration(1, [source["id"]]))
    before = asset_files(rig)
    with pytest.raises(ValueError, match="cycle"):
        rig.service.annotate(rig.nid, rig.scope, rig.actor, source["id"], declaration(1, [child["id"]]))
    with pytest.raises(ValueError, match="REMOVAL"):
        rig.service.annotate(rig.nid, rig.scope, rig.actor, child["id"], declaration(derived["version"]))
    assert asset_files(rig) == before
    branch = import_asset(rig, scope=branch_scope(rig))
    other_id = rig.create_project("Other lineage owner")
    other = rig.service.import_asset(other_id, {"mode": "local", "novel_id": other_id}, rig.actor, upload())
    for parent in (branch, other):
        before = asset_files(rig)
        with pytest.raises(FileNotFoundError):
            rig.service.annotate(rig.nid, rig.scope, rig.actor, source["id"], declaration(1, [parent["id"]]))
        assert asset_files(rig) == before


def test_asset_cas_soft_delete_restore_storage_and_dependency_guard(rig, decoders):
    from app.services.v1_capability_service import CapabilityVersionConflict
    source, child = import_asset(rig), import_asset(rig)
    child = rig.service.annotate(rig.nid, rig.scope, rig.actor, child["id"], declaration(1, [source["id"]]))
    before = asset_files(rig)
    with pytest.raises(ValueError, match="ASSET_IN_USE"):
        rig.service.lifecycle(rig.nid, rig.scope, source["id"], 1)
    assert asset_files(rig) == before
    child_deleted = rig.service.lifecycle(rig.nid, rig.scope, child["id"], child["version"])
    assert child_deleted["version"] == child["version"] + 1
    source_deleted = rig.service.lifecycle(rig.nid, rig.scope, source["id"], 1)
    assert source_deleted["version"] == 2
    assert rig.service.list_assets(rig.nid, rig.scope) == {"items": []}
    assert len(rig.service.list_assets(rig.nid, rig.scope, include_deleted=True)["items"]) == 2
    for operation in (lambda: rig.service.asset(rig.nid, rig.scope, source["id"]),
                      lambda: rig.service.download(rig.nid, rig.scope, source["id"])):
        with pytest.raises(FileNotFoundError):
            operation()
    with pytest.raises(CapabilityVersionConflict):
        rig.service.lifecycle(rig.nid, rig.scope, source["id"], 1, restore=True)
    storage = rig.service.storage(rig.nid, rig.scope)
    assert storage["assets"] == {"count": 0, "bytes": 0}
    assert storage["trash"] == {"count": 2, "bytes": len(png_bytes()) * 2}
    assert storage["physical_cleanup_available"] is False
    assert storage["model_storage"] == "EXTERNAL_READ_ONLY"
    assert storage["cache_storage"] == "SEPARATE_OWNER"
    assert storage["export_storage"] == "CLIENT_SELECTED_DOWNLOAD"
    for row in (source, child):
        assert (rig.assets.root / f"{row['id']}.bin").read_bytes() == png_bytes()
    restored = rig.service.lifecycle(rig.nid, rig.scope, source["id"], 2, restore=True)
    assert restored["version"] == 3 and restored["deleted_at"] is None
    child_restored = rig.service.lifecycle(rig.nid, rig.scope, child["id"], child_deleted["version"], restore=True)
    assert child_restored["provenance"]["parents"][0]["state"] == "STALE"
    assert rig.service.download(rig.nid, rig.scope, source["id"])[1] == png_bytes()


@pytest.mark.parametrize("expected", [True, "1", 0, -1, 1.0])
def test_asset_lifecycle_requires_a_genuine_positive_integer_revision(rig, decoders, expected):
    from app.creative.workspace_models import AssetVersion
    row = import_asset(rig)
    before = asset_files(rig)
    with pytest.raises(ValueError):
        AssetVersion.model_validate({"expected_version": expected})
    with pytest.raises(ValueError):
        rig.service.lifecycle(rig.nid, rig.scope, row["id"], expected)
    assert asset_files(rig) == before


def test_two_service_asset_annotation_delete_race_has_exactly_one_cas_winner(rig, decoders):
    from app.services.v1_capability_service import CapabilityVersionConflict
    row, barrier = import_asset(rig), Barrier(2)
    def write(action):
        service = reopened(rig)
        barrier.wait(timeout=10)
        try:
            if action == "delete":
                return service.lifecycle(rig.nid, rig.scope, row["id"], 1)
            return service.annotate(rig.nid, rig.scope, rig.actor, row["id"], declaration(1))
        except (CapabilityVersionConflict, FileNotFoundError):
            return "CONFLICT"
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(write, ("annotate", "delete")))
    assert results.count("CONFLICT") == 1
    winner = next(result for result in results if result != "CONFLICT")
    assert winner["version"] == 2
    assert rig.service.asset(rig.nid, rig.scope, row["id"], include_deleted=True) == winner
    assert (rig.assets.root / f"{row['id']}.bin").read_bytes() == png_bytes()


def test_wrong_scope_project_and_exact_branch_never_fall_back_to_mainline(rig, decoders):
    local = import_asset(rig, key="same-key")
    branch = branch_scope(rig)
    branch_row = import_asset(rig, scope=branch, key="same-key")
    assert branch_row["id"] != local["id"]
    assert [row["id"] for row in rig.service.list_assets(rig.nid, rig.scope)["items"]] == [local["id"]]
    assert [row["id"] for row in rig.service.list_assets(rig.nid, branch)["items"]] == [branch_row["id"]]
    assert rig.service.list_assets(rig.nid, branch_scope(rig, "other-branch")) == {"items": []}
    for changed_scope in ({**branch, "workspace_id": "other-workspace"},
                          {**branch, "storyline_id": "other-storyline"},
                          {**branch, "mode": "local"}):
        assert rig.service.list_assets(rig.nid, changed_scope) == {"items": []}
        for operation in (lambda: rig.service.asset(rig.nid, changed_scope, branch_row["id"]),
                          lambda: rig.service.download(rig.nid, changed_scope, branch_row["id"])):
            with pytest.raises(FileNotFoundError):
                operation()
    other = rig.create_project("Another project")
    for nid, scope, aid in ((rig.nid, rig.scope, branch_row["id"]), (rig.nid, branch, local["id"]),
                            (other, {"mode": "local", "novel_id": other}, local["id"])):
        for operation in (lambda: rig.service.asset(nid, scope, aid),
                          lambda: rig.service.download(nid, scope, aid),
                          lambda: rig.service.lifecycle(nid, scope, aid, 1)):
            with pytest.raises(FileNotFoundError):
                operation()
    for scope in ({"mode": "local", "novel_id": other}, {"mode": "collaboration", "novel_id": rig.nid}):
        with pytest.raises(ValueError):
            rig.service.list_assets(rig.nid, scope)


def test_legacy_unbound_assets_stay_legacy_without_silent_adoption(rig, decoders):
    plain = rig.assets.create(rig.nid, "opaque.bin", base64.b64encode(b"legacy opaque bytes").decode(),
                              "application/octet-stream", "file", "shared-key")
    branch_plain = rig.assets.create(rig.nid, "legacy.png", base64.b64encode(png_bytes()).decode(),
                                     "image/png", "image", "branch-key", branch_id="legacy-branch")
    assert rig.service.list_assets(rig.nid, rig.scope) == {"items": []}
    with pytest.raises(FileNotFoundError):
        rig.service.asset(rig.nid, rig.scope, plain["id"])
    bound = import_asset(rig, key="shared-key")
    assert bound["id"] != plain["id"]
    assert rig.assets.content(plain["id"]) == b"legacy opaque bytes"
    assert rig.assets.get(branch_plain["id"]) == branch_plain  # historical None wildcard is preserved
    assert {row["id"] for row in rig.assets.list(rig.nid)} == {plain["id"], branch_plain["id"]}
    for operation in (lambda: rig.assets.get(bound["id"]), lambda: rig.assets.content(bound["id"]),
                      lambda: rig.assets.delete(bound["id"]), lambda: rig.assets.restore(bound["id"])):
        with pytest.raises(FileNotFoundError):
            operation()
    assert "_project_binding" not in stored_asset(rig, plain["id"])


@pytest.mark.parametrize("prefix", ["/api", "/api/v1"])
def test_same_slug_recreation_hides_old_bound_assets_even_on_legacy_routes(rig, decoders, monkeypatch, prefix):
    import app.api as api
    from app.config import settings
    from app.main import app
    from fastapi.testclient import TestClient
    old = import_asset(rig, key="reused-after-recreate")
    old_identity = stored_asset(rig, old["id"])["_project_binding"]["incarnation"]
    rig.service.preferences(rig.nid, rig.scope, rig.actor, {"expected_version": 0, "preset": "VIDEO"})
    other = rig.create_project("Unrelated project")
    other_scope = {"mode": "local", "novel_id": other}
    other_asset = rig.service.import_asset(other, other_scope, rig.actor, upload())
    old_meta = stored_asset(rig, old["id"])
    rig.novels.delete(rig.nid)
    with pytest.raises(FileNotFoundError):
        rig.service.list_assets(rig.nid, rig.scope)
    rig.create_project("Recreated owner", nid=rig.nid)
    second = reopened(rig)
    assert second.project(rig.nid, rig.scope)["preferences"]["version"] == 0
    assert second.list_assets(rig.nid, rig.scope) == {"items": []}
    assert second.store.incarnation(rig.nid) != old_identity
    for operation in (lambda: second.asset(rig.nid, rig.scope, old["id"]),
                      lambda: second.download(rig.nid, rig.scope, old["id"]),
                      lambda: second.lifecycle(rig.nid, rig.scope, old["id"], 1, restore=True),
                      lambda: second.assets.get(old["id"], include_deleted=True),
                      lambda: second.assets.content(old["id"])):
        with pytest.raises(FileNotFoundError):
            operation()
    assert stored_asset(rig, old["id"]) == old_meta
    assert (rig.assets.root / f"{old['id']}.bin").read_bytes() == png_bytes()
    fresh = second.import_asset(rig.nid, rig.scope, rig.actor, upload(key="reused-after-recreate"))
    assert fresh["id"] != old["id"]
    assert second.download(other, other_scope, other_asset["id"])[1] == png_bytes()
    monkeypatch.setattr(api, "asset_library_service", second.assets)
    monkeypatch.setattr(api, "novel_service", rig.novels)
    from dataclasses import replace
    import app.main as main
    config = replace(settings, enable_collaboration_runtime=False, enable_packaged_runtime=False)
    monkeypatch.setattr(api, "settings", config)
    monkeypatch.setattr(main, "settings", config)
    client = TestClient(app)
    assert client.get(f"{prefix}/novels/{rig.nid}/assets").json() == []
    for suffix in ("", "/download"):
        response = client.get(f"{prefix}/assets/{old['id']}{suffix}", params={"novel_id": rig.nid})
        assert response.status_code == 404, response.text
        assert old["sha256"] not in response.text
    response = client.delete(f"{prefix}/assets/{old['id']}", params={"novel_id": rig.nid})
    assert response.status_code == 404, response.text
    assert second.asset(rig.nid, rig.scope, fresh["id"]) == fresh
    assert stored_asset(rig, old["id"]) == old_meta


def test_feature_revocation_hides_bound_assets_without_mutating_them(rig, decoders, monkeypatch):
    row = import_asset(rig)
    before = asset_files(rig)
    monkeypatch.setenv("EXPERIMENTAL_FEATURES", "")
    assert rig.service.list_assets(rig.nid, rig.scope) == {"items": []}
    with pytest.raises(FileNotFoundError):
        rig.service.download(rig.nid, rig.scope, row["id"])
    with pytest.raises(ValueError, match="feature unavailable"):
        import_asset(rig)
    assert asset_files(rig) == before
    monkeypatch.setenv("EXPERIMENTAL_FEATURES", FLAGS)
    assert rig.service.download(rig.nid, rig.scope, row["id"])[1] == png_bytes()


def test_corrupt_original_bytes_fail_export_and_restore_without_fictional_integrity(rig, decoders):
    from app.services.asset_library_service import AssetIntegrityError
    row = import_asset(rig)
    path = rig.assets.root / f"{row['id']}.bin"
    data = path.read_bytes()
    path.write_bytes(bytes([data[0] ^ 1]) + data[1:])
    assert rig.service.asset(rig.nid, rig.scope, row["id"])["provenance"]["integrity"] == "CONTENT_UNAVAILABLE"
    with pytest.raises(AssetIntegrityError, match="digest"):
        rig.service.download(rig.nid, rig.scope, row["id"])
    deleted = rig.service.lifecycle(rig.nid, rig.scope, row["id"], 1)
    with pytest.raises(AssetIntegrityError):
        rig.service.lifecycle(rig.nid, rig.scope, row["id"], deleted["version"], restore=True)
    assert rig.service.asset(rig.nid, rig.scope, row["id"], include_deleted=True)["deleted_at"]


def test_precommit_authority_failure_never_writes_and_releases_asset_scope(rig, decoders):
    calls = []
    def revoked():
        calls.append(None)
        if len(calls) == 2:
            raise PermissionError("authority revoked")
    with pytest.raises(PermissionError):
        rig.service.import_asset(rig.nid, rig.scope, rig.actor, upload(), guard=revoked)
    assert asset_files(rig) == {}
    assert getattr(rig.assets._scope, "binding", None) is None
    row = import_asset(rig)
    before = asset_files(rig)
    calls.clear()
    with pytest.raises(PermissionError):
        rig.service.annotate(rig.nid, rig.scope, rig.actor, row["id"], declaration(1), guard=revoked)
    assert asset_files(rig) == before
    assert getattr(rig.assets._scope, "binding", None) is None
    def denied():
        raise PermissionError("authority revoked")
    with pytest.raises(PermissionError):
        rig.service.lifecycle(rig.nid, rig.scope, row["id"], 1, guard=denied)
    assert asset_files(rig) == before
    assert getattr(rig.assets._scope, "binding", None) is None
    assert reopened(rig).download(rig.nid, rig.scope, row["id"])[1] == png_bytes()


def test_metadata_write_failure_removes_new_binary_and_releases_locks(rig, decoders, monkeypatch):
    good = import_asset(rig)
    before = asset_files(rig)
    original = rig.assets._write_meta
    def disk_full(_meta):
        raise OSError("synthetic metadata write failure")
    monkeypatch.setattr(rig.assets, "_write_meta", disk_full)
    with pytest.raises(OSError, match="metadata write failure"):
        import_asset(rig)
    assert asset_files(rig) == before
    assert getattr(rig.assets._scope, "binding", None) is None
    monkeypatch.setattr(rig.assets, "_write_meta", original)
    assert reopened(rig).download(rig.nid, rig.scope, good["id"])[1] == png_bytes()
    assert import_asset(rig)["id"] != good["id"]


def test_metadata_commit_then_error_keeps_committed_bytes_for_idempotent_recovery(rig, decoders, monkeypatch):
    original = rig.assets._write_meta
    body = upload(key="uncertain-write")
    def written_then_failed(meta):
        original(meta)
        raise OSError("synthetic error after metadata commit")
    monkeypatch.setattr(rig.assets, "_write_meta", written_then_failed)
    with pytest.raises(OSError, match="after metadata commit"):
        rig.service.import_asset(rig.nid, rig.scope, rig.actor, body)
    files = asset_files(rig)
    assert len(files) == 2 and not any(name.endswith(".tmp") for name in files)
    assert getattr(rig.assets._scope, "binding", None) is None
    monkeypatch.setattr(rig.assets, "_write_meta", original)
    recovered = reopened(rig).import_asset(rig.nid, rig.scope, rig.actor, body)
    assert set(files) == {recovered["id"] + ".bin", recovered["id"] + ".json"}
    assert asset_files(rig) == files
    assert rig.service.download(rig.nid, rig.scope, recovered["id"])[1] == png_bytes()


def test_project_scope_releases_on_identity_or_nested_context_failure(rig):
    @contextmanager
    def bad_identity():
        yield "forged-incarnation"
    with pytest.raises(ValueError, match="IDENTITY_INVALID"):
        with rig.assets.project_scope(rig.nid, None, bad_identity, scope_key=rig.store.key(rig.nid, rig.scope)):
            pytest.fail("bad incarnation entered asset scope")
    assert getattr(rig.assets._scope, "binding", None) is None
    with rig.assets.project_scope(rig.nid, None, lambda: rig.store.owner_lease(rig.nid),
                                  scope_key=rig.store.key(rig.nid, rig.scope)):
        with pytest.raises(ValueError, match="SCOPE_NESTED"):
            with rig.assets.project_scope(rig.nid, None, lambda: rig.store.owner_lease(rig.nid),
                                          scope_key=rig.store.key(rig.nid, rig.scope)):
                pytest.fail("nested asset scope accepted")
        assert rig.assets._scope.binding["novel_id"] == rig.nid
    assert getattr(rig.assets._scope, "binding", None) is None
    assert rig.service.list_assets(rig.nid, rig.scope) == {"items": []}


def test_asset_owner_lease_blocks_concurrent_original_project_delete_until_commit(rig, decoders, monkeypatch):
    entered, release, deleting, deleted = Event(), Event(), Event(), Event()
    original = rig.assets._write_meta
    def paused_write(meta):
        entered.set()
        assert release.wait(15), "test did not release the asset write"
        return original(meta)
    monkeypatch.setattr(rig.assets, "_write_meta", paused_write)
    def remove_owner():
        deleting.set()
        rig.novels.delete(rig.nid)
        deleted.set()
    with ThreadPoolExecutor(max_workers=2) as pool:
        importing = pool.submit(import_asset, rig)
        try:
            assert entered.wait(15), "import never reached real asset persistence"
            removing = pool.submit(remove_owner)
            assert deleting.wait(5)
            assert not deleted.wait(0.2), "original project was deleted inside the leased asset write"
        finally:
            release.set()
        row = importing.result(timeout=20)
        removing.result(timeout=20)
    assert deleted.is_set()
    assert (rig.assets.root / f"{row['id']}.bin").read_bytes() == png_bytes()
    assert getattr(rig.assets._scope, "binding", None) is None
    rig.create_project("New same-slug owner", nid=rig.nid)
    assert rig.service.list_assets(rig.nid, rig.scope) == {"items": []}
    with pytest.raises(FileNotFoundError):
        rig.service.download(rig.nid, rig.scope, row["id"])


def test_deleted_owner_cannot_leave_orphan_new_assets_or_borrow_recreated_owner(rig, decoders):
    old = import_asset(rig)
    before = asset_files(rig)
    rig.novels.delete(rig.nid)
    with pytest.raises(FileNotFoundError):
        import_asset(rig)
    assert asset_files(rig) == before
    assert getattr(rig.assets._scope, "binding", None) is None
    rig.create_project("New blank project", nid=rig.nid)
    assert rig.service.list_assets(rig.nid, rig.scope) == {"items": []}
    new = import_asset(rig)
    assert new["id"] != old["id"]
    assert stored_asset(rig, new["id"])["_project_binding"] != stored_asset(rig, old["id"])["_project_binding"]


def test_unbound_old_preferences_are_retained_without_adoption(rig):
    from app.creative.workspace import PREFERENCES
    from app.experimental.common import new_row
    old = new_row(rig.nid, rig.scope, "legacy", {"intents": ["ADVERTISEMENT"], "preset": "VIDEO", "custom_intent": ""})
    with rig.raw_store.transaction(rig.nid, rig.scope) as document:
        document["collections"][PREFERENCES] = {old["id"]: copy.deepcopy(old)}
    assert rig.service.project(rig.nid, rig.scope)["preferences"]["version"] == 0
    new = rig.service.preferences(rig.nid, rig.scope, rig.actor, {"expected_version": 0, "preset": "IMAGE"})
    raw = rig.raw_store.read(rig.nid, rig.scope)["collections"][PREFERENCES]
    assert raw[old["id"]] == old and len(raw) == 2
    assert new["version"] == 1
    assert reopened(rig).project(rig.nid, rig.scope)["preferences"] == new


@pytest.mark.parametrize("version", [True, False, 0, -1, "1", 1.0, None])
def test_new_studio_rejects_corrupt_original_asset_version_without_mutating_owner(rig, decoders, version):
    row = import_asset(rig)
    path = rig.assets.root / f"{row['id']}.json"
    metadata = json.loads(path.read_text())
    metadata["version"] = version
    path.write_text(json.dumps(metadata))
    before = asset_files(rig)
    for operation in (
        lambda: rig.service.asset(rig.nid, rig.scope, row["id"]),
        lambda: rig.service.download(rig.nid, rig.scope, row["id"]),
        lambda: rig.service.list_assets(rig.nid, rig.scope),
        lambda: rig.service.relationships.references(rig.nid, rig.scope, "ASSET"),
    ):
        with pytest.raises(ValueError, match="CREATIVE_ASSET_VERSION_INVALID"):
            operation()
        assert asset_files(rig) == before
