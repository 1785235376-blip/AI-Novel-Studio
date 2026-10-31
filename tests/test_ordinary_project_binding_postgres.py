"""Offline protocol tests, not evidence of live PostgreSQL concurrency.

These exercise the original PostgreSQL generation repository with real ORM
models and PostgreSQL SQL compilation. The small fake records transaction and
statement ordering; it does not simulate PostgreSQL locks or foreign keys.
"""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from sqlalchemy.dialects import postgresql

from app.repositories.generation_repository import GenerationProjectIdentityError
from app.repositories.postgres.generation import PostgresGenerationRepository
from app.repositories.postgres.models import GenerationJobModel, NovelModel


FIELD = "ordinary_project_binding"
PROJECT = "ordinary-project"


class _Rows:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self.rows


class _Session:
    def __init__(self, database):
        self.owner = deepcopy(database.owner)
        self.rows = deepcopy(database.rows)
        self.calls = []
        self.statements = []
        self.active = True

    def _statement(self, statement):
        assert self.active, "repository operation escaped its session"
        compiled = statement.compile(dialect=postgresql.dialect())
        self.statements.append(compiled)
        return statement.column_descriptions[0]["entity"], compiled.params

    def scalar(self, statement):
        entity, params = self._statement(statement)
        if entity is NovelModel:
            self.calls.append("owner")
            assert set(params) == {"slug_1"}
            return self.owner if self.owner and self.owner.slug == params["slug_1"] else None
        assert entity is GenerationJobModel
        assert set(params) == {"id_1"}
        self.calls.append("job")
        return self.rows.get(params["id_1"])

    def scalars(self, statement):
        entity, params = self._statement(statement)
        assert entity is GenerationJobModel and not params
        self.calls.append("all")
        return _Rows(sorted(self.rows.values(), key=lambda row: row.created_at))

    def get(self, entity, identifier):
        assert self.active and entity is GenerationJobModel
        self.calls.append("get")
        return self.rows.get(identifier)

    def add(self, row):
        assert self.active and isinstance(row, GenerationJobModel)
        assert row.id not in self.rows
        self.calls.append("add")
        # A real session obtains this mapped default during INSERT.
        row.created_at = datetime.now(timezone.utc)
        self.rows[row.id] = row

    def flush(self):
        assert self.active
        self.calls.append("flush")


class _Database:
    def __init__(self):
        self.owner = NovelModel(id=uuid4(), slug=PROJECT, title="Original owner")
        self.rows = {}
        self.sessions = []

    @contextmanager
    def session(self):
        session = _Session(self)
        self.sessions.append(session)
        try:
            yield session
        except BaseException:
            session.calls.append("rollback")
            raise
        else:
            session.calls.append("commit")
            self.rows = deepcopy(session.rows)
        finally:
            session.active = False


def _item(database, *, operation="continue", collaborative=False):
    item = {
        "id": str(uuid4()),
        "novel_id": PROJECT,
        "chapter_id": None,
        "operation": operation,
        "actor_id": None,
        "workspace_id": None,
        "scope": None,
        "scope_type": None,
        "scope_id": None,
        "experimental_origin": None,
        "status": "QUEUED",
        "request": {"instruction": "Keep the original request", "parameters": {"temperature": 0.2}},
        "output": "",
        "unrelated_metadata": {"labels": ["passive", "ordinary"]},
    }
    if collaborative:
        item.update({
            "actor_id": "ordinary-author",
            "workspace_id": "ordinary-workspace",
            "scope": {
                "kind": "BRANCH", "workspace_id": "ordinary-workspace",
                "project_id": PROJECT, "storyline_id": "ordinary-storyline",
                "branch_id": "ordinary-branch",
            },
            "scope_type": "BRANCH",
            "scope_id": "ordinary-branch",
            "experimental_origin": "branch_manuscript",
        })
    item[FIELD] = {
        "schema_version": 1,
        "project_incarnation": "postgres:" + str(database.owner.id),
        "job_id": item["id"],
        "project_id": PROJECT,
        **{key: deepcopy(item[key]) for key in (
            "chapter_id", "operation", "actor_id", "workspace_id", "scope", "scope_type", "scope_id",
            "experimental_origin",
        )},
    }
    return item


def _saved(database, item):
    return deepcopy(database.rows[UUID(item["id"])].request["_repository_payload"])


def _assert_owner_lock(statement):
    sql = str(statement)
    assert "FROM novels" in sql
    assert "WHERE novels.slug =" in sql
    assert sql.endswith("FOR KEY SHARE")
    assert statement.params == {"slug_1": PROJECT}


@pytest.mark.parametrize("operation", ["continue", "rewrite", "polish", "brainstorm", "review"])
@pytest.mark.parametrize("collaborative", [False, True], ids=["local", "branch"])
def test_original_postgres_roundtrip_preserves_binding_and_nullable_identity(operation, collaborative):
    database = _Database()
    repository = PostgresGenerationRepository(database)
    item = _item(database, operation=operation, collaborative=collaborative)
    original = deepcopy(item)

    repository.save(item)

    assert item == original
    row = database.rows[UUID(item["id"])]
    assert row.novel_id == database.owner.id
    assert row.chapter_id is None
    assert row.operation == operation
    assert row.request == {**original["request"], "_repository_payload": original}
    assert repository.get(item["id"]) == original
    assert repository.load_all() == [original]


def test_owner_key_share_and_generation_row_update_lock_share_the_save_session():
    database = _Database()
    repository = PostgresGenerationRepository(database)
    item = _item(database)

    repository.save(item)

    assert len(database.sessions) == 1
    session = database.sessions[0]
    assert session.calls == ["owner", "job", "add", "flush", "commit"]
    assert not session.active
    _assert_owner_lock(session.statements[0])
    assert str(session.statements[1]).endswith("FOR UPDATE")
    assert "FROM generation_jobs" in str(session.statements[1])
    assert session.statements[1].params == {"id_1": UUID(item["id"])}

    updated = deepcopy(item)
    updated.update({"status": "RUNNING", "output": "A partial ordinary result"})
    repository.save(updated)

    update_session = database.sessions[1]
    assert update_session.calls == ["owner", "job", "flush", "commit"]
    _assert_owner_lock(update_session.statements[0])
    assert str(update_session.statements[1]).endswith("FOR UPDATE")
    assert _saved(database, item) == updated


def test_get_and_load_validate_the_original_owner_inside_their_read_session():
    database = _Database()
    repository = PostgresGenerationRepository(database)
    item = _item(database)
    repository.save(item)

    assert repository.get(item["id"]) == item
    get_session = database.sessions[-1]
    assert get_session.calls == ["get", "owner", "commit"]
    _assert_owner_lock(get_session.statements[0])

    assert repository.load_all() == [item]
    load_session = database.sessions[-1]
    assert load_session.calls == ["all", "owner", "commit"]
    assert "ORDER BY generation_jobs.created_at" in str(load_session.statements[0])
    _assert_owner_lock(load_session.statements[1])


def test_status_result_and_repository_projection_update_without_rebinding():
    database = _Database()
    repository = PostgresGenerationRepository(database)
    item = _item(database, collaborative=True)
    repository.save(item)
    updated = deepcopy(item)
    updated.update({
        "status": "COMPLETED", "output": "Original generated prose",
        "result": {"text": "Original generated prose"},
        "provider": "existing-provider", "model": "existing-model",
        "context_snapshot_id": str(uuid4()), "retry_count": 1,
    })

    repository.save(updated)

    assert _saved(database, item) == updated
    assert repository.get(item["id"]) == updated
    assert repository.load_all() == [updated]
    assert updated[FIELD] == item[FIELD]


@pytest.mark.parametrize("owner_change", ["missing", "replacement", "file_backend"])
def test_save_rejects_missing_replaced_or_wrong_backend_owner_before_job_lookup(owner_change):
    database = _Database()
    repository = PostgresGenerationRepository(database)
    item = _item(database)
    repository.save(item)
    original = _saved(database, item)
    stale = deepcopy(item)
    stale["status"] = "COMPLETED"
    if owner_change == "missing":
        database.owner = None
    elif owner_change == "replacement":
        database.owner.id = uuid4()
    else:
        stale[FIELD]["project_incarnation"] = "file:" + str(database.owner.id)

    with pytest.raises(GenerationProjectIdentityError, match="PROJECT_OWNER_CHANGED"):
        repository.save(stale)

    assert database.sessions[-1].calls == ["owner", "rollback"]
    assert _saved(database, item) == original


@pytest.mark.parametrize("owner_change", ["missing", "replacement", "foreign_row_owner"])
def test_get_hides_stale_owner_and_load_omits_it_without_rebinding(owner_change):
    database = _Database()
    repository = PostgresGenerationRepository(database)
    item = _item(database)
    repository.save(item)
    legacy = {"id": "legacy-without-project", "status": "QUEUED", "request": {"legacy": True}}
    repository.save(legacy)
    if owner_change == "missing":
        database.owner = None
    elif owner_change == "replacement":
        database.owner.id = uuid4()
    else:
        database.rows[UUID(item["id"])].novel_id = uuid4()
    original = _saved(database, item)

    with pytest.raises(KeyError) as error:
        repository.get(item["id"])

    assert error.value.args == (item["id"],)
    assert repository.load_all() == [legacy]
    assert _saved(database, item) == original
    assert all("flush" not in session.calls for session in database.sessions[-2:])


def test_save_rejects_generation_row_foreign_key_owner_mismatch():
    database = _Database()
    repository = PostgresGenerationRepository(database)
    item = _item(database)
    repository.save(item)
    foreign_owner = uuid4()
    database.rows[UUID(item["id"])].novel_id = foreign_owner
    original = _saved(database, item)

    with pytest.raises(GenerationProjectIdentityError, match="BINDING_CHANGED"):
        repository.save({**item, "status": "COMPLETED"})

    assert database.sessions[-1].calls == ["owner", "job", "rollback"]
    assert database.rows[UUID(item["id"])].novel_id == foreign_owner
    assert _saved(database, item) == original


def test_previously_unbound_row_cannot_be_upgraded_to_ordinary_binding():
    database = _Database()
    repository = PostgresGenerationRepository(database)
    bound = _item(database)
    legacy = deepcopy(bound)
    legacy.pop(FIELD)
    repository.save(legacy)

    with pytest.raises(GenerationProjectIdentityError, match="BINDING_CHANGED"):
        repository.save(bound)

    assert database.sessions[-1].calls == ["owner", "job", "rollback"]
    assert _saved(database, legacy) == legacy
    assert repository.get(legacy["id"]) == legacy


@pytest.mark.parametrize("downgrade", ["removed", "null"])
def test_bound_row_cannot_be_downgraded_or_nullified(downgrade):
    database = _Database()
    repository = PostgresGenerationRepository(database)
    item = _item(database)
    repository.save(item)
    downgraded = deepcopy(item)
    if downgrade == "removed":
        downgraded.pop(FIELD)
    else:
        downgraded[FIELD] = None

    with pytest.raises(GenerationProjectIdentityError):
        repository.save(downgraded)

    assert "flush" not in database.sessions[-1].calls
    assert database.sessions[-1].calls[-1] == "rollback"
    assert _saved(database, item) == item


@pytest.mark.parametrize("identity_change", ["operation", "actor", "branch", "replacement_owner"])
def test_valid_but_changed_binding_cannot_rewrite_existing_row(identity_change):
    database = _Database()
    repository = PostgresGenerationRepository(database)
    item = _item(database, collaborative=True)
    repository.save(item)
    changed = deepcopy(item)
    if identity_change == "operation":
        changed["operation"] = changed[FIELD]["operation"] = "polish"
    elif identity_change == "actor":
        changed["actor_id"] = changed[FIELD]["actor_id"] = "another-author"
    elif identity_change == "branch":
        changed["scope"]["branch_id"] = changed[FIELD]["scope"]["branch_id"] = "another-branch"
        changed["scope_id"] = changed[FIELD]["scope_id"] = "another-branch"
    else:
        database.owner.id = uuid4()
        changed[FIELD]["project_incarnation"] = "postgres:" + str(database.owner.id)

    with pytest.raises(GenerationProjectIdentityError, match="BINDING_CHANGED"):
        repository.save(changed)

    assert database.sessions[-1].calls == ["owner", "job", "rollback"]
    assert _saved(database, item) == item


@pytest.mark.parametrize("specialized_field", [
    "graph_binding", "adaptation_binding", "creative_director_binding",
    "director_image_binding", "research_ocr_binding",
])
def test_specialized_field_presence_even_null_cannot_fall_through_to_ordinary_save(specialized_field):
    database = _Database()
    repository = PostgresGenerationRepository(database)
    item = _item(database)
    item[specialized_field] = None

    with pytest.raises(GenerationProjectIdentityError, match="ORDINARY_BINDING_INVALID"):
        repository.save(item)

    assert database.sessions[-1].calls == ["rollback"]
    assert not database.rows


@pytest.mark.parametrize("field", [
    "chapter_id", "actor_id", "workspace_id", "scope", "scope_type", "scope_id", "experimental_origin",
])
@pytest.mark.parametrize("location", ["binding", "item"])
def test_missing_explicit_nullable_identity_is_rejected_before_sql(field, location):
    database = _Database()
    repository = PostgresGenerationRepository(database)
    item = _item(database)
    (item[FIELD] if location == "binding" else item).pop(field)

    with pytest.raises(GenerationProjectIdentityError, match="ORDINARY_BINDING_INVALID"):
        repository.save(item)

    assert database.sessions[-1].calls == ["rollback"]
    assert not database.rows


def test_postgres_owner_uuid_need_not_be_version_four():
    database = _Database()
    database.owner.id = UUID("945bfb01-f4b0-5003-8350-9e74d3c1bc9b")
    repository = PostgresGenerationRepository(database)
    item = _item(database)

    repository.save(item)

    assert repository.get(item["id"]) == item
    assert database.rows[UUID(item["id"])].novel_id == database.owner.id


@pytest.mark.parametrize("corruption", [
    "null", "binding_job_id", "row_job_id", "row_operation", "extra_field", "boolean_version", "scope_field",
])
def test_corrupt_persisted_binding_is_hidden_by_get_and_load(corruption):
    database = _Database()
    repository = PostgresGenerationRepository(database)
    item = _item(database, collaborative=True)
    repository.save(item)
    row = database.rows[UUID(item["id"])]
    payload = row.request["_repository_payload"]
    if corruption == "null":
        payload[FIELD] = None
    elif corruption == "binding_job_id":
        payload[FIELD]["job_id"] = str(uuid4())
    elif corruption == "row_job_id":
        payload["id"] = payload[FIELD]["job_id"] = str(uuid4())
    elif corruption == "row_operation":
        row.operation = "polish"
    elif corruption == "extra_field":
        payload[FIELD]["unexpected"] = "must not be ignored"
    elif corruption == "boolean_version":
        payload[FIELD]["schema_version"] = True
    else:
        payload[FIELD]["scope"].pop("storyline_id")
    corrupt_payload = deepcopy(payload)

    with pytest.raises(KeyError) as error:
        repository.get(item["id"])

    assert error.value.args == (item["id"],)
    assert repository.load_all() == []
    assert _saved(database, item) == corrupt_payload
    assert all("owner" not in session.calls and "flush" not in session.calls
               for session in database.sessions[-2:])


def test_saved_binding_is_detached_from_mutable_caller_objects_before_commit():
    database = _Database()
    repository = PostgresGenerationRepository(database)
    item = _item(database, collaborative=True)
    original = deepcopy(item)
    repository.save(item)
    # Inspect the actual row passed to the fake session, not its committed copy.
    # The fake's commit copy must not mask a shallow repository-payload alias.
    inserted_row = database.sessions[-1].rows[UUID(item["id"])]

    item[FIELD]["scope"]["branch_id"] = "caller-mutated-branch"
    item["scope"]["branch_id"] = "caller-mutated-branch"
    item["unrelated_metadata"]["labels"].append("caller mutation")

    assert inserted_row.request["_repository_payload"] == original


@pytest.mark.parametrize("same_owner", [True, False])
def test_ordinary_mainline_chapter_must_belong_to_locked_owner_in_same_session(monkeypatch, same_owner):
    from app.repositories.postgres.models import ChapterModel
    import app.repositories.postgres.generation as module
    database = _Database()
    repository = PostgresGenerationRepository(database)
    item = _item(database)
    item["chapter_id"] = item[FIELD]["chapter_id"] = PROJECT + ":1"
    chapter = ChapterModel(id=uuid4(), novel_id=database.owner.id if same_owner else uuid4(),
                           chapter_number=1, markdown_path="chapters/1.md")
    calls = []

    def resolve(session, chapter_id):
        assert session is database.sessions[-1] and session.active
        assert chapter_id == item["chapter_id"]
        assert session.calls == ["owner", "job"]
        calls.append(session)
        return database.owner, chapter

    monkeypatch.setattr(module, "chapter_or_raise", resolve)
    if same_owner:
        repository.save(item)
        assert database.rows[UUID(item["id"])].chapter_id == chapter.id
    else:
        with pytest.raises(GenerationProjectIdentityError, match="CHAPTER_OWNER_MISMATCH"):
            repository.save(item)
        assert database.rows == {}
        assert "flush" not in database.sessions[-1].calls
    assert len(calls) == 1 and len(database.sessions) == 1
