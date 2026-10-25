"""Offline manager/repository protocol tests, not live PostgreSQL evidence.

The original PostgreSQL repositories and Database.session implementation run
against a recording session factory. Real ORM rows and PostgreSQL compilation
check protocol ordering only: this does not emulate locks, foreign keys, SQL
execution, isolation, or concurrent PostgreSQL connections.
"""
from __future__ import annotations

from contextlib import nullcontext
from copy import deepcopy
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.engine import make_url

from app.jobs import JobManager, generation_content_available
from app.repositories.generation_repository import GenerationProjectIdentityError
from app.repositories.postgres.chapter import PostgresChapterRepository
from app.repositories.postgres.generation import PostgresGenerationRepository
from app.repositories.postgres.models import NovelModel
from app.repositories.postgres.session import Database
from app.services import ChapterService, GenerationService
from app.services.generation_project_binding import FIELD, IDENTITY_FIELDS
from test_ordinary_project_binding_postgres import (
    PROJECT, _Session, _assert_owner_lock, _item, _saved,
)


class _ProtocolSession(_Session):
    def __init__(self, database):
        assert database.active_sessions == 0, "nested repository session"
        super().__init__(database)
        self.database = database
        database.active_sessions += 1
        database.sessions.append(self)

    def commit(self):
        assert self.active
        self.calls.append("commit")
        self.database.rows = deepcopy(self.rows)

    def rollback(self):
        assert self.active
        self.calls.append("rollback")

    def close(self):
        assert self.active
        self.calls.append("close")
        self.active = False
        self.database.active_sessions -= 1


def _database():
    # Keep Database.session itself original. No engine, driver, socket, or live
    # server is created; the URL exists solely for same-URL mismatch coverage.
    database = Database.__new__(Database)
    database.engine = SimpleNamespace(url=make_url("postgresql+psycopg://offline/protocol"))
    database.owner = NovelModel(id=uuid4(), slug=PROJECT, title="Original owner")
    database.rows = {}
    database.sessions = []
    database.active_sessions = 0
    database.session_factory = lambda: _ProtocolSession(database)
    return database


class _NoSideEffects:
    def __getattr__(self, name):
        raise AssertionError(f"passive manager reached downstream service: {name}")


def _manager(database, *, chapter_database=None):
    return JobManager(
        generations=GenerationService(PostgresGenerationRepository(database)),
        chapters=ChapterService(PostgresChapterRepository(chapter_database or database)),
        contexts=_NoSideEffects(), canon=_NoSideEffects(),
        memory_extractor=_NoSideEffects(), collaboration_updates=_NoSideEffects(),
        snapshot_required=False,
    )


def _seed(database, *, operation="continue", collaborative=False, status="COMPLETED"):
    item = _item(database, operation=operation, collaborative=collaborative)
    item.update(
        instruction="Preserve this request", profile="LOCAL", source="Original source",
        status=status, output="A passive generated draft", variant_group_id="passive-group",
        variant_index=2,
    )
    PostgresGenerationRepository(database).save(item)
    database.sessions.clear()
    return item


def _assert_no_writes(database):
    assert database.active_sessions == 0
    assert all(not session.active for session in database.sessions)
    assert all("flush" not in session.calls and "add" not in session.calls
               for session in database.sessions)


def _invalidate(database, item, change):
    row = database.rows[UUID(item["id"])]
    payload = row.request["_repository_payload"]
    if change == "missing_row":
        del database.rows[row.id]
    elif change == "missing_owner":
        database.owner = None
    elif change == "replaced_owner":
        database.owner.id = uuid4()
    elif change == "foreign_row_owner":
        row.novel_id = uuid4()
    elif change == "missing_binding":
        del payload[FIELD]
    elif change == "null_binding":
        payload[FIELD] = None
    elif change == "changed_binding":
        row.operation = payload["operation"] = payload[FIELD]["operation"] = "polish"
    elif change == "row_operation":
        row.operation = "polish"
    else:
        raise AssertionError(change)


@pytest.mark.parametrize("operation", ["continue", "rewrite", "polish", "brainstorm", "review"])
def test_original_postgres_manager_restores_bound_passive_record_without_writes(operation):
    database = _database()
    item = _seed(database, operation=operation)
    payload = database.rows[UUID(item["id"])].request["_repository_payload"]
    # Durable data cannot deserialize execution or content-serving authority.
    for field in ("request_authorization", "before_dispatch", "on_terminal",
                  "prepared_text_invocation", "_ordinary_read_verifier"):
        payload[field] = "untrusted serialized hook"

    manager = _manager(database)

    assert type(manager.persistence.repository) is PostgresGenerationRepository
    assert type(manager.chapters.repository) is PostgresChapterRepository
    assert manager.persistence.repository.database is manager.chapters.repository.database is database
    job = manager.jobs[item["id"]]
    assert job.status == "COMPLETED" and job.output == item["output"]
    assert FIELD not in job.public()
    assert job.record()[FIELD] == item[FIELD]
    assert all(key in job.record() and job.record()[key] == item[key] for key in IDENTITY_FIELDS)
    assert job.experimental_origin is None
    assert job.request_authorization is job.before_dispatch is job.on_terminal is None
    assert job.prepared_text_invocation is None
    assert job._ordinary_read_verifier.__self__ is manager
    assert job._ordinary_read_verifier.__func__ is JobManager._ordinary_record_available
    assert len(database.sessions) == 2
    assert database.sessions[0].calls == ["all", "owner", "commit", "close"]
    assert database.sessions[1].calls == ["get", "owner", "commit", "close"]
    _assert_no_writes(database)

    private = job.record()
    private[FIELD]["operation"] = "polish"
    private["issues"].append("caller-owned mutation")
    assert job.ordinary_project_binding == item[FIELD] and job.issues == []
    assert _saved(database, item) == payload


@pytest.mark.parametrize("read", ["get", "content", "variants"])
def test_manager_reads_use_one_original_read_session_without_nested_connection(read):
    database = _database()
    item = _seed(database)
    manager = _manager(database)
    job = manager.jobs[item["id"]]
    database.sessions.clear()

    if read == "get":
        assert manager.get(job.id) is job
    elif read == "content":
        assert generation_content_available(job)
    else:
        assert manager.variants("passive-group") == [job]

    assert len(database.sessions) == 1
    session = database.sessions[0]
    assert session.calls == ["get", "owner", "commit", "close"]
    _assert_owner_lock(session.statements[0])
    _assert_no_writes(database)


@pytest.mark.parametrize("change", [
    "missing_row", "missing_owner", "replaced_owner", "foreign_row_owner",
    "missing_binding", "null_binding", "changed_binding", "row_operation",
])
def test_original_row_and_owner_changes_fence_cached_reads_and_content(change):
    database = _database()
    item = _seed(database)
    manager = _manager(database)
    job = manager.jobs[item["id"]]
    original = job.record()
    _invalidate(database, item, change)
    database.sessions.clear()

    with pytest.raises(KeyError) as error:
        manager.get(job.id)
    assert error.value.args == (job.id,)
    assert generation_content_available(job) is False
    assert manager.variants("passive-group") == []
    with pytest.raises(KeyError):
        next(manager.events(job.id))
    with pytest.raises(KeyError):
        manager.diff(job.id)

    assert manager.jobs[job.id] is job and job.record() == original
    _assert_no_writes(database)


@pytest.mark.parametrize("change", ["missing_owner", "replaced_owner", "foreign_row_owner", "null_binding", "row_operation"])
def test_stale_or_malformed_bound_rows_are_not_restored(change):
    database = _database()
    item = _seed(database)
    _invalidate(database, item, change)

    manager = _manager(database)

    assert item["id"] not in manager.jobs
    _assert_no_writes(database)


def test_same_url_different_database_object_cannot_restore_bound_rows():
    database = _database()
    other = _database()
    item = _seed(database)
    assert database.engine.url == other.engine.url
    assert database is not other

    manager = _manager(database, chapter_database=other)

    assert item["id"] not in manager.jobs
    assert len(database.sessions) == 1
    assert other.sessions == []
    _assert_no_writes(database)


@pytest.mark.parametrize("change", ["chapter_database", "generation_repository"])
def test_recomposed_manager_hides_cached_bound_job_and_rejects_persist_without_sql(change):
    database = _database()
    item = _seed(database)
    manager = _manager(database)
    job = manager.jobs[item["id"]]
    original = _saved(database, item)
    other = _database()
    if change == "chapter_database":
        manager.chapters = ChapterService(PostgresChapterRepository(other))
    else:
        manager.persistence = GenerationService(PostgresGenerationRepository(database))
    database.sessions.clear()

    with pytest.raises(KeyError):
        manager.get(job.id)
    assert generation_content_available(job) is False
    with pytest.raises(GenerationProjectIdentityError, match="ORDINARY_STORE_MISMATCH"):
        manager._persist(job)

    assert database.sessions == other.sessions == []
    assert _saved(database, item) == original


def test_bound_postgres_branch_is_not_inferred_from_mainline_database_identity():
    database = _database()
    item = _seed(database, collaborative=True)

    manager = _manager(database)

    assert item["id"] not in manager.jobs
    assert len(database.sessions) == 1
    _assert_no_writes(database)


def test_bound_persist_retains_private_identity_in_one_original_save_session():
    database = _database()
    item = _seed(database)
    manager = _manager(database)
    job = manager.jobs[item["id"]]
    job.status = "FAILED"
    job.error = "Preserve passive recovery status"
    database.sessions.clear()

    manager._persist(job)

    assert len(database.sessions) == 1
    session = database.sessions[0]
    assert session.calls == ["owner", "job", "flush", "commit", "close"]
    _assert_owner_lock(session.statements[0])
    assert str(session.statements[1]).endswith("FOR UPDATE")
    assert session.statements[1].params == {"id_1": UUID(job.id)}
    assert database.active_sessions == 0
    assert _saved(database, item) == job.record()
    assert _saved(database, item)[FIELD] == item[FIELD]
    assert FIELD not in job.public()


@pytest.mark.parametrize("change", ["missing_owner", "replaced_owner", "foreign_row_owner", "changed_binding"])
def test_original_save_transaction_rejects_stale_bound_persist_without_writes(change):
    database = _database()
    item = _seed(database)
    manager = _manager(database)
    job = manager.jobs[item["id"]]
    _invalidate(database, item, change)
    original = _saved(database, item)
    database.sessions.clear()

    with pytest.raises(GenerationProjectIdentityError):
        manager._persist(job)

    assert len(database.sessions) == 1
    assert database.sessions[0].calls[-2:] == ["rollback", "close"]
    assert _saved(database, item) == original
    _assert_no_writes(database)


@pytest.mark.parametrize("operation", [
    "cancel", "accept", "reject", "start_prepared", "_start_prepared_validated",
    "_run", "_accept_claimed", "_accept_branch_claimed",
])
def test_passive_mutation_entrypoints_refuse_before_any_write_or_downstream_call(operation):
    database = _database()
    item = _seed(database)
    manager = _manager(database)
    job = manager.jobs[item["id"]]
    original = job.record()
    stored = _saved(database, item)
    database.sessions.clear()

    with pytest.raises(HTTPException) as error:
        if operation in {"cancel", "accept", "reject"}:
            getattr(manager, operation)(job.id)
        elif operation == "_accept_claimed":
            manager._accept_claimed(job, {}, 1)
        elif operation == "_accept_branch_claimed":
            manager._accept_branch_claimed(job, {}, 1, None, None, None)
        else:
            getattr(manager, operation)(job)

    assert error.value.status_code == 409
    assert error.value.detail == {"code": "GENERATION_ORDINARY_MUTATION_NOT_INTEGRATED"}
    assert job.record() == original and not job.cancelled.is_set()
    assert _saved(database, item) == stored
    _assert_no_writes(database)


@pytest.mark.parametrize("status", ["SETTLING", "RUNNING", "GENERATING", "QUEUED", "PREPARED"])
def test_existing_restart_recovery_preserves_binding_without_replaying_execution(monkeypatch, status):
    database = _database()
    item = _seed(database, status=status)
    # The existing process claim is outside this offline SQL protocol test.
    monkeypatch.setattr(JobManager, "_review_mutation", lambda self, jid: nullcontext())

    manager = _manager(database)

    job = manager.jobs[item["id"]]
    assert job.status == "FAILED"
    assert job.ordinary_project_binding == item[FIELD]
    assert job.request_authorization is job.before_dispatch is job.on_terminal is None
    assert job.prepared_text_invocation is None
    assert not job.cancelled.is_set()
    assert _saved(database, item)[FIELD] == item[FIELD]
    assert _saved(database, item)["status"] == "FAILED"
    assert len(database.sessions) == 4
    assert [session.calls for session in database.sessions[:3]] == [
        ["all", "owner", "commit", "close"],
        ["get", "owner", "commit", "close"],
        ["get", "owner", "commit", "close"],
    ]
    assert database.sessions[-1].calls == ["owner", "job", "flush", "commit", "close"]
    assert database.active_sessions == 0
