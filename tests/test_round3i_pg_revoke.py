"""R3-I — PG-REVOKE-BEFORE-COMMIT: revoke authorization INSIDE the transaction, before the
PostgreSQL commit, and prove the whole thing rolls back.

`revise_in_state` calls `reauthorize()` once before the write and once after it (following
assert_current and assert_capacity), and BOTH run inside `ExperimentalStore.transaction` before
the commit. This test revokes the writer's real branch role on the SECOND call and then runs the
REAL authorization check, so the guard itself refuses the write and the transaction rolls back.

This is deliberately NOT the already-passing post-commit test, where the commit had already
happened and the response merely became a 403. Here nothing may persist at all.
"""
from __future__ import annotations

import os

import pytest

from r3i_authorized_shared import build_authorized, chain, make_env

pytestmark = pytest.mark.postgres_backend_only


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
    from app.creative.service import CreativeService
    from app.experimental.store import ExperimentalStore

    store = ExperimentalStore(env.data_path, "postgres",
                              os.environ["TEST_POSTGRES_DATABASE_URL"])
    assert store.backend == "postgres"
    return store, CreativeService(store, env.novels, env.deps.chapter_service)


def _db_revision(store, scope_key):
    with store._connect() as connection:
        row = connection.execute(
            "SELECT revision FROM experimental_scope_documents WHERE scope_key = %s",
            (scope_key,)).fetchone()
    return row[0] if row else None


def test_PG_REVOKE_BEFORE_COMMIT_rolls_the_whole_transaction_back(env, authorized):
    from types import SimpleNamespace

    import app.creative.prompt_adoption_api as adopt_api
    import app.experimental.api as exp_api
    from app.authorization import ModalityDomain

    e = authorized
    flow = chain(e, "/api", e.headers)
    scope = _scope(e)
    inner = getattr(exp_api.studio_prompt_adoption_service.workspace.creative.store, "store",
                    exp_api.studio_prompt_adoption_service.workspace.creative.store)
    scope_key = inner.key(e.nid, scope)

    before_store, before_service = _fresh(env)
    before_doc = before_service.get(e.nid, scope, flow["board"]["id"])
    before_version = before_doc["version"]
    before_shot = next(i for i in before_doc["shots"] if i["id"] == flow["shot_id"])
    before_revision = _db_revision(before_store, scope_key)

    calls = {"n": 0}
    observed = {}

    def guard():
        """Runs inside the transaction. On the SECOND call the in-memory revision is complete
        and the commit has not happened yet, so this is the pre-commit authorization boundary."""
        calls["n"] += 1
        if calls["n"] >= 2 and "revoked" not in observed:
            # A REAL authorization change through the real service, not a flag.
            e.authorization.revoke_role(e.writer_role, e.init_user)
            observed["revoked"] = True
            observed["allowed_after_revoke"] = e.authorization.is_allowed(
                e.writer, "domain.write", ModalityDomain.NOVEL, e.auth_scope)
        # The ORIGINAL permission guard continues to run: the real check must now refuse.
        e.authorization.require(e.writer, "domain.write", ModalityDomain.NOVEL, e.auth_scope)

    request = SimpleNamespace(**flow["dto"])
    adopt_api.PROMPT_ADOPTION_WRITE_ENABLED = True
    raised = None
    try:
        try:
            exp_api.studio_prompt_adoption_service.adopt_atomic(
                e.nid, scope, e.writer, flow["board"]["id"], flow["shot_id"], request, guard)
        except BaseException as exc:  # noqa: BLE001
            raised = exc
    finally:
        adopt_api.PROMPT_ADOPTION_WRITE_ENABLED = False

    # 4. the revocation really took effect, and it happened before the commit
    assert observed.get("revoked") is True, "the guard never reached the pre-commit boundary"
    assert observed["allowed_after_revoke"] is False, "the revocation did not remove permission"
    assert calls["n"] >= 2, "the guard did not run after the in-memory revision"

    # 5. the write was refused
    assert raised is not None, "the adoption reported success after the pre-commit revocation"

    # 6/7. through a NEW connection: full rollback, nothing persisted
    after_store, after_service = _fresh(env)
    after_doc = after_service.get(e.nid, scope, flow["board"]["id"])
    after_shot = next(i for i in after_doc["shots"] if i["id"] == flow["shot_id"])
    assert after_doc["version"] == before_version, "a pre-commit revocation must not commit"
    assert after_shot["frame_prompt"] == before_shot["frame_prompt"], "the shot must be unchanged"
    assert [p for p in (after_doc.get("prompt_adoptions") or [])
            if p.get("request_id") == flow["dto"]["request_id"]] == [], \
        "no proof may survive a pre-commit revocation"
    assert _db_revision(after_store, scope_key) == before_revision, \
        "the database row revision must not advance"

    with after_store._connect() as connection:
        waiting = connection.execute(
            "SELECT count(*) FROM pg_stat_activity WHERE datname = current_database() "
            "AND wait_event_type = 'Lock'").fetchone()[0]
    assert waiting == 0, f"{waiting} sessions are still waiting on a lock (possible deadlock)"

    # Recovery: restore a legal role under a NEW id, then the SAME request_id must converge on
    # exactly one legitimate commit.
    from app.authorization import DomainRole, DomainRoleAssignment

    e.authorization.assign_role(DomainRoleAssignment(
        "restored-" + os.urandom(5).hex(), e.writer, DomainRole.DOMAIN_LEAD,
        ModalityDomain.NOVEL, e.auth_scope, e.init_user))
    assert e.authorization.is_allowed(e.writer, "domain.write", ModalityDomain.NOVEL,
                                      e.auth_scope) is True

    adopt_api.PROMPT_ADOPTION_WRITE_ENABLED = True
    try:
        result = exp_api.studio_prompt_adoption_service.adopt_atomic(
            e.nid, scope, e.writer, flow["board"]["id"], flow["shot_id"], request)
    finally:
        adopt_api.PROMPT_ADOPTION_WRITE_ENABLED = False
    assert result["committed"] is True
    assert result["replayed"] is False, "this must be a genuine first commit, not a replay"
    assert result["version"] == before_version + 1

    final_store, final_service = _fresh(env)
    final_doc = final_service.get(e.nid, scope, flow["board"]["id"])
    final_shot = next(i for i in final_doc["shots"] if i["id"] == flow["shot_id"])
    proofs = [p for p in (final_doc.get("prompt_adoptions") or [])
              if p.get("request_id") == flow["dto"]["request_id"]]
    assert final_shot["frame_prompt"] == flow["source"]["value"]
    assert len(proofs) == 1 and proofs[0]["digest"] == flow["source"]["digest"]
    assert _db_revision(final_store, scope_key) == before_revision + 1
