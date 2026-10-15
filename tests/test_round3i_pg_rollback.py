"""R3-I — real PostgreSQL SQL-layer failure and rollback (PG-ROLLBACK-A/B).

This fails the ACTUAL `UPDATE experimental_scope_documents` statement inside
`ExperimentalStore.transaction()` with a PostgreSQL trigger, rather than raising from Python
business code. The trigger is scoped to one scope_key and dropped in a finally.

After the failure everything is re-read through a BRAND NEW connection, and then the SAME
request_id is retried to prove the operation converges on exactly one legitimate commit.
"""
from __future__ import annotations

import os

import pytest

from r3i_authorized_shared import build_authorized, chain, make_env

pytestmark = pytest.mark.postgres_backend_only

TRIGGER = "r3i_fail_scope_update"
FUNCTION = "r3i_fail_scope_update_fn"
MARKER = "INJECTED_PG_UPDATE_FAILURE"


@pytest.fixture(scope="module")
def env():
    if os.environ.get("PROJECT_ROOT") is None:
        pytest.skip("requires the isolated runner")
    return make_env("postgres")()


@pytest.fixture
def authorized(env):
    return build_authorized(env)


def _scope(e):
    return {"mode": "collaboration", "novel_id": e.nid, "workspace_id": e.workspace,
            "storyline_id": e.storyline, "branch_id": e.branch}


def _fresh(env):
    """A brand-new PostgreSQL connection, independent of the one that wrote."""
    from app.creative.service import CreativeService
    from app.experimental.store import ExperimentalStore

    store = ExperimentalStore(env.data_path, "postgres",
                              os.environ["TEST_POSTGRES_DATABASE_URL"])
    assert store.backend == "postgres"
    return store, CreativeService(store, env.novels, env.deps.chapter_service)


def _install_trigger(store, scope_key):
    # No bind parameters inside DDL: PostgreSQL cannot infer a type for them in a function body
    # (IndeterminateDatatype). The scope key is inlined as a proper SQL literal instead.
    from psycopg import sql as _sql

    with store._connect() as connection:
        connection.execute(_sql.SQL("""
            CREATE OR REPLACE FUNCTION {}() RETURNS trigger AS $$
            BEGIN
              IF NEW.scope_key = {} AND OLD.document IS DISTINCT FROM NEW.document THEN
                RAISE EXCEPTION {};
              END IF;
              RETURN NEW;
            END;
            $$ LANGUAGE plpgsql
        """).format(_sql.Identifier(FUNCTION), _sql.Literal(scope_key), _sql.Literal(MARKER)))
        connection.execute(_sql.SQL(
            "CREATE TRIGGER {} BEFORE UPDATE ON experimental_scope_documents "
            "FOR EACH ROW EXECUTE FUNCTION {}()").format(
                _sql.Identifier(TRIGGER), _sql.Identifier(FUNCTION)))
        connection.commit()


def _remove_trigger(store):
    from psycopg import sql as _sql

    with store._connect() as connection:
        connection.execute(_sql.SQL("DROP TRIGGER IF EXISTS {} ON experimental_scope_documents")
                           .format(_sql.Identifier(TRIGGER)))
        connection.execute(_sql.SQL("DROP FUNCTION IF EXISTS {}()").format(_sql.Identifier(FUNCTION)))
        connection.commit()


def _db_revision(store, scope_key):
    with store._connect() as connection:
        row = connection.execute(
            "SELECT revision FROM experimental_scope_documents WHERE scope_key = %s",
            (scope_key,)).fetchone()
    return row[0] if row else None


def test_PG_ROLLBACK_A_and_B_sql_update_failure_then_safe_retry(env, authorized):
    from types import SimpleNamespace

    import app.creative.prompt_adoption_api as adopt_api
    import app.experimental.api as exp_api
    from app.experimental.store import ExperimentalStore

    e = authorized
    flow = chain(e, "/api", e.headers)
    scope = _scope(e)
    store = exp_api.studio_prompt_adoption_service.workspace.creative.store
    inner = getattr(store, "store", store)
    scope_key = inner.key(e.nid, scope)

    writer_store, writer_service = _fresh(env)
    before_doc = writer_service.get(e.nid, scope, flow["board"]["id"])
    before_version = before_doc["version"]
    before_shot = next(i for i in before_doc["shots"] if i["id"] == flow["shot_id"])
    before_revision = _db_revision(writer_store, scope_key)
    assert before_revision is not None, "the scope row must exist before the attempt"

    request = SimpleNamespace(**flow["dto"])
    adopt_api.PROMPT_ADOPTION_WRITE_ENABLED = True
    _install_trigger(inner, scope_key)
    raised = None
    try:
        try:
            exp_api.studio_prompt_adoption_service.adopt_atomic(
                e.nid, scope, e.writer, flow["board"]["id"], flow["shot_id"], request)
        except BaseException as exc:  # noqa: BLE001
            raised = exc
    finally:
        _remove_trigger(inner)
        adopt_api.PROMPT_ADOPTION_WRITE_ENABLED = False

    # 9/10. no success reported, and the failure really came from the injected SQL trigger.
    assert raised is not None, "the adoption reported success despite a failed UPDATE"
    chain_text = "".join(str(a) for a in getattr(raised, "args", ())) + type(raised).__name__
    cause = getattr(raised, "__cause__", None) or getattr(raised, "__context__", None)
    while cause is not None and MARKER not in chain_text:
        chain_text += "".join(str(a) for a in getattr(cause, "args", ())) + type(cause).__name__
        cause = getattr(cause, "__cause__", None) or getattr(cause, "__context__", None)
    assert MARKER in chain_text, f"the failure was not the injected trigger: {raised!r}"

    # PERSISTED STATE, read through a NEW connection.
    after_store, after_service = _fresh(env)
    after_doc = after_service.get(e.nid, scope, flow["board"]["id"])
    after_shot = next(i for i in after_doc["shots"] if i["id"] == flow["shot_id"])
    assert after_doc["version"] == before_version, "a failed UPDATE must not add a version"
    assert after_shot["frame_prompt"] == before_shot["frame_prompt"], "the shot must be unchanged"
    proofs = [p for p in (after_doc.get("prompt_adoptions") or [])
              if p.get("request_id") == flow["dto"]["request_id"]]
    assert proofs == [], "no proof may survive a failed commit"
    assert _db_revision(after_store, scope_key) == before_revision, \
        "the database row revision must not advance on rollback"

    # No leaked locks/connections from the failed transaction.
    with after_store._connect() as connection:
        waiting = connection.execute(
            "SELECT count(*) FROM pg_stat_activity WHERE datname = current_database() "
            "AND wait_event_type = 'Lock'").fetchone()[0]
    assert waiting == 0, f"{waiting} sessions are still waiting on a lock"

    # ---------------- PG-ROLLBACK-B: the SAME request_id, after recovery -------------------
    adopt_api.PROMPT_ADOPTION_WRITE_ENABLED = True
    try:
        result = exp_api.studio_prompt_adoption_service.adopt_atomic(
            e.nid, scope, e.writer, flow["board"]["id"], flow["shot_id"], request)
    finally:
        adopt_api.PROMPT_ADOPTION_WRITE_ENABLED = False

    assert result["committed"] is True, "the retry must really commit, not fake a replay"
    assert result["replayed"] is False, "the first successful commit must not be reported as replay"
    assert result["version"] == before_version + 1, "exactly one increment"

    final_store, final_service = _fresh(env)
    final_doc = final_service.get(e.nid, scope, flow["board"]["id"])
    final_shot = next(i for i in final_doc["shots"] if i["id"] == flow["shot_id"])
    final_proofs = [p for p in (final_doc.get("prompt_adoptions") or [])
                    if p.get("request_id") == flow["dto"]["request_id"]]
    assert final_doc["version"] == before_version + 1
    assert final_shot["frame_prompt"] == flow["source"]["value"]
    assert len(final_proofs) == 1, "exactly one proof for the request id"
    assert final_proofs[0]["digest"] == flow["source"]["digest"]
    assert final_proofs[0]["result_version"] == final_doc["version"]
    assert _db_revision(final_store, scope_key) == before_revision + 1

    # A further replay adds nothing.
    adopt_api.PROMPT_ADOPTION_WRITE_ENABLED = True
    try:
        again = exp_api.studio_prompt_adoption_service.adopt_atomic(
            e.nid, scope, e.writer, flow["board"]["id"], flow["shot_id"], request)
    finally:
        adopt_api.PROMPT_ADOPTION_WRITE_ENABLED = False
    assert again["replayed"] is True
    assert again["version"] == final_doc["version"]
    check_store, check_service = _fresh(env)
    assert check_service.get(e.nid, scope, flow["board"]["id"])["version"] == final_doc["version"]
