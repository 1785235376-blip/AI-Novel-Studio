from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.agents import AgentRunner
from app.compare_context_backends import differences
from app.config import Settings
from app.lore.context_view import LoreContextBuilder
from app.repositories.factory import create_repository_bundle
from app.repositories.postgres.models import CharacterModel, NovelModel
from app.repositories.postgres.session import Database
from app.services import ChapterService, ContextService, LoreService, MemoryService, NovelService
from app.storage import atomic_write


def prepare_memory(bundle, novel_id: str, chapter_id: str, *, privacy: str = "CLOUD_ALLOWED"):
    lore = LoreService(bundle.lore)
    evidence = lore.create_evidence(
        {
            "id": str(uuid.uuid4()),
            "novel_id": novel_id,
            "source_type": "CHAPTER_VERSION",
            "source_id": f"{chapter_id}:v1",
            "chapter_id": chapter_id,
            "chapter_version": 1,
            "excerpt": "Hero enters.",
            "locator": {"kind": "DOCUMENT_RANGE"},
            "content_hash": hashlib.sha256(b"Hero enters.").hexdigest(),
            "privacy": privacy,
        }
    )
    proposal = lore.create_proposal(
        {
            "id": str(uuid.uuid4()),
            "novel_id": novel_id,
            "proposal_type": "CHARACTER_MEMORY",
            "payload": {"candidate": True},
            "status": "PENDING",
        },
        [{"evidence_id": evidence["id"], "relevance": "PRIMARY"}],
    )
    return lore, MemoryService(bundle.lore), proposal


def setup_context(tmp_path):
    bundle = create_repository_bundle(data_root=tmp_path)
    novels = NovelService(bundle.novels, bundle.chapters)
    chapters = ChapterService(bundle.chapters)
    novel_id = novels.create({"id": "context-lore", "title": "Context Lore"})["id"]
    chapter = chapters.create(novel_id, {"title": "One", "content": "Hero enters."})
    atomic_write(
        tmp_path / "novels" / novel_id / "characters" / "characters.json",
        json.dumps([{"id": "hero", "name": "Hero"}]),
    )
    lore, memory, proposal = prepare_memory(bundle, novel_id, chapter["id"])
    memory.approve_character_memory(
        proposal["id"],
        {
            "character_id": "hero",
            "memory_type": "EXPERIENCE",
            "content": {"event": "crossed the storm"},
            "valid_from_chapter": 1,
        },
        "tester",
        memory_id="context-memory",
        business_id="context-memory",
    )
    return bundle, novel_id, chapter, lore


@pytest.mark.file_backend_only
def test_feature_flag_off_is_v048_compatible(tmp_path):
    bundle, novel_id, _, lore = setup_context(tmp_path)
    plain = ContextService(bundle.novels, bundle.chapters).build(novel_id, 1, "Hero", False)
    disabled = ContextService(bundle.novels, bundle.chapters, lore, False).build(
        novel_id, 1, "Hero", False
    )
    assert disabled == plain
    assert "lore_memory" not in disabled


@pytest.mark.file_backend_only
def test_enabled_context_adds_only_approved_active_memory(tmp_path):
    bundle, novel_id, chapter, lore = setup_context(tmp_path)
    _, _, pending = prepare_memory(bundle, novel_id, chapter["id"])
    _, _, rejected = prepare_memory(bundle, novel_id, chapter["id"])
    lore.reject_proposal(rejected["id"], "tester")

    context = ContextService(bundle.novels, bundle.chapters, lore, True).build(
        novel_id, 1, "Hero", False
    )
    view = context["lore_memory"]
    assert [item["id"] for item in view["short_memory"]] == ["context-memory"]
    assert view["medium_memory"] == []
    assert view["long_memory"] == []
    assert pending["id"] not in json.dumps(view)
    assert rejected["id"] not in json.dumps(view)


@pytest.mark.file_backend_only
def test_cloud_context_excludes_local_only_memory(tmp_path):
    bundle = create_repository_bundle(data_root=tmp_path)
    novels = NovelService(bundle.novels, bundle.chapters)
    chapters = ChapterService(bundle.chapters)
    novel_id = novels.create({"id": "private-lore", "title": "Private Lore"})["id"]
    chapter = chapters.create(novel_id, {"title": "One", "content": "Hero enters."})
    atomic_write(
        tmp_path / "novels" / novel_id / "characters" / "characters.json",
        json.dumps([{"id": "hero", "name": "Hero"}]),
    )
    lore, memory, proposal = prepare_memory(
        bundle, novel_id, chapter["id"], privacy="LOCAL_ONLY"
    )
    memory.approve_character_memory(
        proposal["id"],
        {"character_id": "hero", "memory_type": "EXPERIENCE", "content": {"private": True}},
        "tester",
        memory_id="private-memory",
        business_id="private-memory",
    )

    envelope = ContextService(bundle.novels, bundle.chapters, lore, True).build_envelope(
        novel_id, 1, "Hero", True
    )
    assert envelope.lore_memory.short_memory == []
    assert envelope.privacy_decisions == [
        {"memory_id": "private-memory", "decision": "OMITTED_LOCAL_ONLY"}
    ]


def test_agent_adapter_only_exposes_lore_to_writer():
    class Registry:
        def prompt(self, name):
            return name

    runner = AgentRunner(Registry())
    context = {"chapter": 1, "lore_memory": {"short_memory": [{"id": "m"}]}}
    assert "lore_memory" in runner.build_prompt("writer", context, "write")
    assert "lore_memory" not in runner.build_prompt("editor", context, "edit")


def test_file_and_postgres_lore_context_match(tmp_path):
    url = os.getenv("TEST_POSTGRES_DATABASE_URL", "")
    if not url or not Database(url).health_check():
        pytest.skip("real PostgreSQL unavailable")

    file_bundle = create_repository_bundle(
        Settings(storage_backend="file", novel_data=tmp_path), tmp_path
    )
    postgres_bundle = create_repository_bundle(
        Settings(storage_backend="postgres", database_url=url)
    )
    shared_novel_id = f"lore-context-match-{uuid.uuid4().hex[:8]}"
    shared_evidence_id = f"context-match-evidence-{uuid.uuid4().hex[:8]}"
    shared_proposal_id = f"context-match-proposal-{uuid.uuid4().hex[:8]}"
    shared_memory_id = f"context-match-memory-{uuid.uuid4().hex[:8]}"
    stamp = datetime(2026, 8, 9, tzinfo=timezone.utc)
    for bundle in (file_bundle, postgres_bundle):
        novels = NovelService(bundle.novels, bundle.chapters)
        chapters = ChapterService(bundle.chapters)
        novel_id = novels.create({"id": shared_novel_id, "title": "Lore Context Match"})["id"]
        chapter = chapters.create(novel_id, {"title": "One", "content": "Hero enters."})
        if bundle is file_bundle:
            atomic_write(
                tmp_path / "novels" / novel_id / "characters" / "characters.json",
                json.dumps([{"id": "hero", "name": "Hero"}]),
            )
        else:
            with bundle.novels.database.session() as session:
                novel = session.scalar(select(NovelModel).where(NovelModel.slug == novel_id))
                session.add(CharacterModel(novel_id=novel.id, slug="hero", name="Hero", facts={}))

        lore = LoreService(bundle.lore)
        evidence = lore.create_evidence(
            {
                "id": shared_evidence_id,
                "novel_id": novel_id,
                "source_type": "CHAPTER_VERSION",
                "source_id": f"{chapter['id']}:v1",
                "chapter_id": chapter["id"],
                "chapter_version": 1,
                "excerpt": "Hero enters.",
                "locator": {"kind": "DOCUMENT_RANGE"},
                "content_hash": hashlib.sha256(b"Hero enters.").hexdigest(),
                "privacy": "CLOUD_ALLOWED",
                "created_at": stamp,
                "updated_at": stamp,
            }
        )
        proposal = lore.create_proposal(
            {
                "id": shared_proposal_id,
                "novel_id": novel_id,
                "proposal_type": "CHARACTER_MEMORY",
                "payload": {"candidate": True},
                "status": "PENDING",
                "created_at": stamp,
                "updated_at": stamp,
            },
            [{"evidence_id": evidence["id"], "relevance": "PRIMARY", "created_at": stamp}],
        )
        bundle.lore.approve_proposal_with_memory(
            proposal["id"],
            {"candidate": True},
            "tester",
            {
                "id": shared_memory_id,
                "business_id": shared_memory_id,
                "character_id": "hero",
                "memory_type": "EXPERIENCE",
                "content": {"event": "crossed the storm"},
                "status": "ACTIVE",
                "valid_from_chapter": 1,
                "created_at": stamp,
                "updated_at": stamp,
            },
        )

    base = {
        "novel_id": shared_novel_id,
        "volume": 1,
        "characters": [{"id": "hero", "name": "Hero"}],
    }
    file_view = LoreContextBuilder(LoreService(file_bundle.lore)).build(base, 1).lore_memory
    postgres_view = LoreContextBuilder(LoreService(postgres_bundle.lore)).build(base, 1).lore_memory
    assert file_view.model_dump(mode="json") == postgres_view.model_dump(mode="json")


def _same_name_novel_views(bundle, prefix: str, tmp_path=None):
    views = {}
    stamp = datetime(2026, 8, 12, 9, 0, tzinfo=timezone.utc)
    for key in ("alpha", "beta"):
        marker = f"{key.upper()}_ONLY_{prefix}"
        evidence_marker = f"{key.upper()}_EVIDENCE_{prefix}"
        novel_id = f"{prefix}-{key}"
        novels = NovelService(bundle.novels, bundle.chapters)
        chapters = ChapterService(bundle.chapters)
        novel_id = novels.create({"id": novel_id, "title": f"Lore {key}"})["id"]
        chapter = chapters.create(novel_id, {"title": "One", "content": evidence_marker})
        if tmp_path is not None:
            atomic_write(
                tmp_path / "novels" / novel_id / "characters" / "characters.json",
                json.dumps([{"id": "same-name-character", "name": "林远"}]),
            )
        else:
            with bundle.novels.database.session() as session:
                novel = session.scalar(select(NovelModel).where(NovelModel.slug == novel_id))
                session.add(CharacterModel(
                    novel_id=novel.id, slug="same-name-character", name="林远", facts={}
                ))
        lore = LoreService(bundle.lore)
        evidence = lore.create_evidence({
            "id": f"{prefix}-{key}-evidence", "novel_id": novel_id,
            "source_type": "CHAPTER_VERSION", "source_id": f"{chapter['id']}:v1",
            "chapter_id": chapter["id"], "chapter_version": 1, "excerpt": evidence_marker,
            "locator": {"kind": "DOCUMENT_RANGE"},
            "content_hash": hashlib.sha256(evidence_marker.encode()).hexdigest(),
            "privacy": "CLOUD_ALLOWED",
        })
        proposal = lore.create_proposal({
            "id": f"{prefix}-{key}-proposal", "novel_id": novel_id,
            "proposal_type": "CHARACTER_MEMORY", "payload": {"candidate": True},
            "status": "PENDING",
        }, [{"evidence_id": evidence["id"], "relevance": "PRIMARY"}])
        bundle.lore.approve_proposal_with_memory(proposal["id"], {}, "tester", {
            "id": f"{prefix}-{key}-memory", "business_id": f"{prefix}-{key}-memory",
            "character_id": "same-name-character", "memory_type": "EXPERIENCE",
            "content": {"marker": marker}, "status": "ACTIVE", "valid_from_chapter": 1,
            "created_at": stamp, "updated_at": stamp,
        })
    for key in ("alpha", "beta"):
        novel_id = f"{prefix}-{key}"
        views[key] = LoreContextBuilder(LoreService(bundle.lore)).build({
            "novel_id": novel_id, "volume": 1,
            "characters": [{"id": "same-name-character", "name": "林远"}],
        }, 1).lore_memory.model_dump(mode="json")
    return views


def test_same_name_character_lore_isolated_by_novel_in_file_and_postgres(tmp_path):
    url = os.getenv("TEST_POSTGRES_DATABASE_URL", "")
    if not url or not Database(url).health_check():
        pytest.skip("real PostgreSQL unavailable")
    run_id = uuid.uuid4().hex[:10]
    file_views = _same_name_novel_views(
        create_repository_bundle(Settings(storage_backend="file", novel_data=tmp_path), tmp_path),
        f"lore-isolation-{run_id}", tmp_path,
    )
    postgres_views = _same_name_novel_views(
        create_repository_bundle(Settings(storage_backend="postgres", database_url=url)),
        f"lore-isolation-{run_id}",
    )
    for views in (file_views, postgres_views):
        alpha = json.dumps(views["alpha"], ensure_ascii=False)
        beta = json.dumps(views["beta"], ensure_ascii=False)
        assert f"ALPHA_ONLY_lore-isolation-{run_id}" in alpha
        assert f"ALPHA_EVIDENCE_lore-isolation-{run_id}" in alpha
        assert f"BETA_ONLY_lore-isolation-{run_id}" not in alpha
        assert f"BETA_EVIDENCE_lore-isolation-{run_id}" not in alpha
        assert f"BETA_ONLY_lore-isolation-{run_id}" in beta
        assert f"BETA_EVIDENCE_lore-isolation-{run_id}" in beta
        assert f"ALPHA_ONLY_lore-isolation-{run_id}" not in beta
        assert f"ALPHA_EVIDENCE_lore-isolation-{run_id}" not in beta
    assert file_views == postgres_views, differences(file_views, postgres_views)


def test_lore_memory_view_parity_comparator_detects_semantic_difference():
    same = {"short_memory": [], "medium_memory": [], "long_memory": [],
            "evidence_summary": [{"evidence_id": "alpha"}], "memory_version": {}}
    changed = {**same, "evidence_summary": [{"evidence_id": "beta"}]}
    assert differences(same, same) == []
    assert differences(same, changed) == [
        {"path": "evidence_summary[0].evidence_id", "file": "alpha", "postgres": "beta"}
    ]
