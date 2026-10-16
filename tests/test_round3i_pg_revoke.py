"""R3-I — PG-REVOKE-BEFORE-COMMIT, corrected.

THE PREVIOUS VERSION WAS A FALSE POSITIVE and is replaced. It revoked on the second call to the
route's guard, but `GraphAssetInputs.phase()` calls `guard()` twice BEFORE any business logic runs,
so the revocation happened before the in-memory revision existed. It therefore could not show
that a COMPLETED in-memory revision rolls back.

This version hooks `app.creative.service.change_row`, the function `revise_in_state` uses to apply
the real in-memory mutation. The hook:
  1. runs the ORIGINAL change_row, so the mutation genuinely happens;
  2. asserts, from the in-memory row, that the version advanced, the target shot text changed and
     the request's proof is present;
  3. only then revokes the writer's branch role through the real AuthorizationService;
  4. returns the original result, so `revise_in_state`'s own post-write `reauthorize()` runs and
     refuses the write.
The request goes through the real TestClient POST, so it is the ROUTE's own guard that refuses -
no substitute guard is written, and no production code is changed to suit the test.
"""
from __future__ import annotations

import os
from uuid import uuid4

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


def test_PG_REVOKE_BEFORE_COMMIT_after_a_completed_in_memory_revision(env, authorized, monkeypatch):
    import app.creative.prompt_adoption_api as adopt_api
    import app.creative.service as creative_service
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

    original_change_row = creative_service.change_row
    observed = {"hook_calls": 0}

    def hooked_change_row(row, actor, expected_version, mutator):
        result = original_change_row(row, actor, expected_version, mutator)
        # Only the target storyboard, and only once.
        if row.get("id") != flow["board"]["id"] or observed["hook_calls"]:
            return result
        observed["hook_calls"] += 1
        # 4/5/6. the IN-MEMORY mutation is already applied at this point.
        observed["in_memory_version"] = row.get("version")
        shot = next((i for i in (row.get("shots") or []) if i.get("id") == flow["shot_id"]), {})
        observed["in_memory_shot"] = shot.get("frame_prompt")
        observed["in_memory_proofs"] = [
            p.get("request_id") for p in (row.get("prompt_adoptions") or [])
            if p.get("request_id") == flow["dto"]["request_id"]]
        # 7. now revoke, while the transaction is still open and uncommitted.
        e.authorization.revoke_role(e.writer_role, e.init_user)
        observed["revoked"] = True
        observed["allowed_after_revoke"] = e.authorization.is_allowed(
            e.writer, "domain.write", ModalityDomain.NOVEL, e.auth_scope)
        return result

    monkeypatch.setattr(creative_service, "change_row", hooked_change_row)
    adopt_api.PROMPT_ADOPTION_WRITE_ENABLED = True
    response = None
    try:
        response = e.client.post(flow["adopt_url"], headers=e.headers, json=flow["dto"])
    finally:
        adopt_api.PROMPT_ADOPTION_WRITE_ENABLED = False
        monkeypatch.setattr(creative_service, "change_row", original_change_row)

    # 1. the hook really ran
    assert observed["hook_calls"] == 1, "the change_row hook did not run exactly once"
    # 2. the in-memory revision really was complete before the revocation
    assert observed["in_memory_version"] == before_version + 1, observed["in_memory_version"]
    assert observed["in_memory_shot"] == flow["source"]["value"], observed["in_memory_shot"]
    assert observed["in_memory_proofs"] == [flow["dto"]["request_id"]], observed["in_memory_proofs"]
    # 3/4. the revocation is real and the business authorization check refused the write
    assert observed["revoked"] is True
    assert observed["allowed_after_revoke"] is False
    assert response is not None
    assert response.status_code == 403, (response.status_code, response.text[:300])
    assert "PROJECT_SCOPE_FORBIDDEN" in response.text, response.text[:300]

    # Persisted state through a NEW connection: full rollback.
    after_store, after_service = _fresh(env)
    after_doc = after_service.get(e.nid, scope, flow["board"]["id"])
    after_shot = next(i for i in after_doc["shots"] if i["id"] == flow["shot_id"])
    assert after_doc["version"] == before_version, "the completed in-memory revision must roll back"
    assert after_shot["frame_prompt"] == before_shot["frame_prompt"]
    assert [p for p in (after_doc.get("prompt_adoptions") or [])
            if p.get("request_id") == flow["dto"]["request_id"]] == [], "no proof may survive"
    assert _db_revision(after_store, scope_key) == before_revision, \
        "the database row revision must not advance"

    with after_store._connect() as connection:
        waiting = connection.execute(
            "SELECT count(*) FROM pg_stat_activity WHERE datname = current_database() "
            "AND wait_event_type = 'Lock'").fetchone()[0]
    assert waiting == 0, f"{waiting} sessions are still waiting on a lock"

    # ---------------- recovery: restore a legal role, replay the SAME request ----------------
    from app.authorization import DomainRole, DomainRoleAssignment

    e.authorization.assign_role(DomainRoleAssignment(
        "restored-" + uuid4().hex[:10], e.writer, DomainRole.DOMAIN_LEAD, ModalityDomain.NOVEL,
        e.auth_scope, e.init_user))
    assert e.authorization.is_allowed(e.writer, "domain.write", ModalityDomain.NOVEL,
                                      e.auth_scope) is True

    adopt_api.PROMPT_ADOPTION_WRITE_ENABLED = True
    try:
        ok = e.client.post(flow["adopt_url"], headers=e.headers, json=flow["dto"])
    finally:
        adopt_api.PROMPT_ADOPTION_WRITE_ENABLED = False
    assert ok.status_code == 200, (ok.status_code, ok.text[:400])
    result = ok.json()
    assert result["committed"] is True
    assert result["replayed"] is False, "a genuine first commit, not a replay"
    assert result["version"] == before_version + 1

    final_store, final_service = _fresh(env)
    final_doc = final_service.get(e.nid, scope, flow["board"]["id"])
    final_shot = next(i for i in final_doc["shots"] if i["id"] == flow["shot_id"])
    proofs = [p for p in (final_doc.get("prompt_adoptions") or [])
              if p.get("request_id") == flow["dto"]["request_id"]]
    assert final_shot["frame_prompt"] == flow["source"]["value"]
    assert len(proofs) == 1 and proofs[0]["digest"] == flow["source"]["digest"]
    assert _db_revision(final_store, scope_key) == before_revision + 1

    adopt_api.PROMPT_ADOPTION_WRITE_ENABLED = True
    try:
        again = e.client.post(flow["adopt_url"], headers=e.headers, json=flow["dto"])
    finally:
        adopt_api.PROMPT_ADOPTION_WRITE_ENABLED = False
    assert again.json()["replayed"] is True
    assert again.json()["version"] == final_doc["version"]
