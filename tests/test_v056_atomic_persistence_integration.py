from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from uuid import uuid4

import psycopg
import pytest
from dotenv import load_dotenv

from app.application.persistence import FileAtomicChapterAuditPort, PostgresAtomicChapterAuditPort
from app.config import Settings
from app.document import markdown_to_document
from app.repositories.chapter_repository import VersionConflict
from app.repositories.factory import create_repository_bundle
from app.repositories.file.scope import FileAuthorizationRepository
from app.services import ChapterService, NovelService


def _audit(event_id: str, actor_id: str, expected: int) -> dict:
    return {
        "id": event_id,
        "actor_id": actor_id,
        "action": "CHAPTER_UPDATED",
        "target_type": "Chapter",
        "target_id": "target",
        "scope": {
            "kind": "BRANCH", "workspace_id": "workspace",
            "project_id": "project", "storyline_id": "storyline", "branch_id": "branch",
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "metadata": {"expected_version": expected, "result_version": expected + 1,
                     "reason": "MANUAL_SAVE", "session_id": "client-a"},
    }


def test_file_atomic_success_conflict_and_audit_failure_compensation(tmp_path, monkeypatch):
    bundle = create_repository_bundle(Settings(storage_backend="file", novel_data=tmp_path), tmp_path)
    service = ChapterService(bundle.chapters)
    novel_id = NovelService(bundle.novels, bundle.chapters).create({"title": "Atomic file"})["id"]
    chapter_id = service.create(novel_id, {"title": "One", "content": "initial"})["id"]
    authorization = FileAuthorizationRepository(tmp_path)
    port = FileAtomicChapterAuditPort(bundle.chapters, authorization)
    original = service.get(chapter_id)

    winner = port.save_chapter_with_audit(
        chapter_id, markdown_to_document("winner"), original["version"],
        "MANUAL_SAVE", "actor-a", _audit("audit-file-win", "actor-a", original["version"]),
    )
    assert winner["version"] == original["version"] + 1
    assert authorization.list_audit_events()[0]["actor_id"] == "actor-a"
    with pytest.raises(VersionConflict):
        port.save_chapter_with_audit(
            chapter_id, markdown_to_document("loser"), original["version"],
            "MANUAL_SAVE", "actor-b", _audit("audit-file-lose", "actor-b", original["version"]),
        )
    assert service.get(chapter_id)["content"] == winner["content"]

    before = service.get(chapter_id)
    before_history = service.history(chapter_id)
    monkeypatch.setattr(authorization, "append_audit_event", lambda event: (_ for _ in ()).throw(RuntimeError("audit failed")))
    with pytest.raises(RuntimeError, match="audit failed"):
        port.save_chapter_with_audit(
            chapter_id, markdown_to_document("must roll back"), before["version"],
            "MANUAL_SAVE", "actor-a", _audit("audit-file-fail", "actor-a", before["version"]),
        )
    assert service.get(chapter_id) == before
    assert service.history(chapter_id) == before_history


def test_file_atomic_updates_to_different_chapters_do_not_lose_shared_audit(tmp_path):
    bundle = create_repository_bundle(Settings(storage_backend="file", novel_data=tmp_path), tmp_path)
    service = ChapterService(bundle.chapters)
    novel_id = NovelService(bundle.novels, bundle.chapters).create({"title": "Parallel audit"})["id"]
    chapters = [service.get(service.create(novel_id, {"title": f"Chapter {index}", "content": "initial"})["id"])
                for index in range(1, 9)]
    authorization = FileAuthorizationRepository(tmp_path)
    port = FileAtomicChapterAuditPort(bundle.chapters, authorization)

    def save(index):
        chapter = chapters[index]
        return port.save_chapter_with_audit(
            chapter["id"], markdown_to_document(f"client-{index}"), chapter["version"],
            "MANUAL_SAVE", f"actor-{index}", _audit(f"audit-parallel-{index}", f"actor-{index}", chapter["version"]),
        )

    with ThreadPoolExecutor(max_workers=len(chapters)) as pool:
        results = list(pool.map(save, range(len(chapters))))
    assert all(item["version"] == 2 for item in results)
    assert {event["id"] for event in authorization.list_audit_events()} == {
        f"audit-parallel-{index}" for index in range(len(chapters))}


def _postgres_url() -> str:
    load_dotenv()
    url = os.getenv("TEST_POSTGRES_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not url:
        pytest.fail("real PostgreSQL URL is required for V0.5.6 integration verification")
    return url


@pytest.mark.postgres_backend_only
def test_real_postgres_two_clients_one_winner_and_transaction_failure_rolls_back():
    url = _postgres_url()
    raw_url = url.replace("postgresql+psycopg://", "postgresql://")
    first_bundle = create_repository_bundle(Settings(storage_backend="postgres", database_url=url))
    second_bundle = create_repository_bundle(Settings(storage_backend="postgres", database_url=url))
    first = ChapterService(first_bundle.chapters)
    novel_id = NovelService(first_bundle.novels, first_bundle.chapters).create(
        {"title": f"V056 atomic {uuid4()}"}
    )["id"]
    chapter_id = first.create(novel_id, {"title": "Race", "content": "initial"})["id"]
    actor_a, actor_b = f"actor-a-{uuid4()}", f"actor-b-{uuid4()}"
    now = datetime.now(timezone.utc)
    with psycopg.connect(raw_url) as connection:
        connection.cursor().executemany(
            "INSERT INTO users(id,display_name,status,created_at,updated_at) VALUES (%s,%s,'ACTIVE',%s,%s)",
            [(actor_a, actor_a, now, now), (actor_b, actor_b, now, now)],
        )
        connection.commit()
    try:
        version = first.get(chapter_id)["version"]
        ports = (PostgresAtomicChapterAuditPort(first_bundle.chapters),
                 PostgresAtomicChapterAuditPort(second_bundle.chapters))

        def save(index: int):
            actor = (actor_a, actor_b)[index]
            try:
                value = ports[index].save_chapter_with_audit(
                    chapter_id, markdown_to_document(f"client-{index}"), version,
                    "MANUAL_SAVE", actor, _audit(f"audit-pg-{uuid4()}", actor, version),
                )
                return "saved", value
            except VersionConflict as error:
                return "conflict", error.as_dict()

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(save, (0, 1)))
        assert sorted(item[0] for item in outcomes) == ["conflict", "saved"]
        winner = first.get(chapter_id)
        assert winner["version"] == version + 1
        assert "client-" in winner["content"]
        assert [row["version"] for row in first.history(chapter_id)] == [version]

        # Duplicate audit PK fails after the conditional UPDATE; the surrounding
        # database transaction must restore both chapter and immutable history.
        duplicate_id = f"duplicate-{uuid4()}"
        duplicate = _audit(duplicate_id, actor_a, winner["version"])
        with psycopg.connect(raw_url) as connection:
            connection.execute(
                "INSERT INTO authorization_audit_events(id,payload) VALUES (%s,%s::jsonb)",
                (duplicate_id, __import__("json").dumps(duplicate)),
            )
            connection.commit()
        before_history = first.history(chapter_id)
        with pytest.raises(Exception):
            ports[0].save_chapter_with_audit(
                chapter_id, markdown_to_document("must roll back"), winner["version"],
                "MANUAL_SAVE", actor_a, duplicate,
            )
        assert first.get(chapter_id) == winner
        assert first.history(chapter_id) == before_history
    finally:
        with psycopg.connect(raw_url) as connection:
            connection.execute("DELETE FROM authorization_audit_events WHERE id LIKE 'audit-pg-%' OR id LIKE 'duplicate-%'")
            connection.execute("DELETE FROM users WHERE id IN (%s,%s)", (actor_a, actor_b))
            connection.commit()
        first.delete(chapter_id)
        NovelService(first_bundle.novels, first_bundle.chapters).delete(novel_id)
