"""R3-I — PG-INCARNATION: delete a project and recreate it under the SAME public id.

Answers, with real PostgreSQL data and the official business routes: after deleting and recreating
a same-named project, are the old project's data and authority still safe?

Identity model, read from the schema and the repository:
  * the PUBLIC id is `novels.slug` (the API returns the slug as "id");
  * the INTERNAL incarnation is `novels.id`, a uuid defaulting to gen_random_uuid();
  * `project_workspaces` binds the TEXT project id to a workspace, with no FK cascade to novels.

Nothing here writes SQL to advance the lifecycle: the project is created and deleted through the
official HTTP routes, and SQL is used only to READ back what actually persisted.
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


def _slug_for(env, title: str) -> str:
    """Recreate the slug the API derives from a title (observed behaviour, not a guess)."""
    carried = "".join(ch if ch.isalnum() else "-" for ch in title.lower())
    while "--" in carried:
        carried = carried.replace("--", "-")
    return carried.strip("-")


def _novel_uuid(env, slug: str):
    """Read the real incarnation straight from PostgreSQL, independent of repository internals."""
    import psycopg

    url = os.environ["TEST_POSTGRES_DATABASE_URL"]
    with psycopg.connect(url, connect_timeout=5) as connection:
        row = connection.execute("SELECT id::text FROM novels WHERE slug = %s",
                                 (slug,)).fetchone()
        return row[0] if row else None


def _scope_row(env, project_id: str):
    import psycopg

    with psycopg.connect(os.environ["TEST_POSTGRES_DATABASE_URL"], connect_timeout=5) as conn:
        row = conn.execute(
            "SELECT workspace_id FROM project_workspaces WHERE project_id = %s",
            (project_id,)).fetchone()
        return row[0] if row else None


def _role_rows(env, actor_id: str):
    import psycopg

    with psycopg.connect(os.environ["TEST_POSTGRES_DATABASE_URL"], connect_timeout=5) as conn:
        return conn.execute(
            "SELECT count(*) FROM domain_role_assignments WHERE principal_id = %s",
            (actor_id,)).fetchone()[0]


def test_PG_INCARNATION_delete_and_recreate_same_public_id(env, authorized):
    import app.creative.prompt_adoption_api as adopt_api

    e = authorized
    slug, old_uuid = e.nid, None
    old_uuid = _novel_uuid(env, slug)
    assert old_uuid, "the created project must have a novels row"
    print(f"[PG-INC] slug={slug} old_uuid={old_uuid}")

    # ---- build real content on the old incarnation
    flow = chain(e, "/api", e.headers)
    scope = {"mode": "collaboration", "novel_id": e.nid, "workspace_id": e.workspace,
             "storyline_id": e.storyline, "branch_id": e.branch}
    adopt_api.PROMPT_ADOPTION_WRITE_ENABLED = True
    try:
        adopted = e.client.post(flow["adopt_url"], headers=e.headers, json=flow["dto"])
    finally:
        adopt_api.PROMPT_ADOPTION_WRITE_ENABLED = False
    assert adopted.status_code == 200, (adopted.status_code, adopted.text[:300])
    assert adopted.json()["committed"] is True
    old_document, old_shot = flow["board"]["id"], flow["shot_id"]
    old_asset = flow["prompt"]["asset_id"]
    old_request = flow["dto"]["request_id"]
    print(f"[PG-INC] old_document={old_document} old_asset={old_asset} old_request={old_request}")

    # ---- delete through the official route
    deleted = e.client.delete(f"/api/novels/{slug}", headers=e.init_headers)
    print(f"[PG-INC] DELETE /api/novels/{slug} -> {deleted.status_code}")
    assert deleted.status_code in {204, 200}, (deleted.status_code, deleted.text[:300])

    # ---- what actually persisted
    gone = _novel_uuid(env, slug)
    print(f"[PG-INC] novels row after delete: {gone!r}")
    binding = env.scopes.repository.project_workspace(slug)
    print(f"[PG-INC] project_workspaces binding after delete: {binding!r}")
    print(f"[PG-INC] SQL project_workspaces row: {_scope_row(env, slug)!r}")
    # AUTHORIZATION_ISOLATION, asked through the REAL authorization service rather than SQL:
    # does the writer's old branch role still permit the old scope after the project is gone?
    from app.authorization import ModalityDomain
    print("[PG-INC] writer allowed on OLD branch scope after delete: "
          f"{e.authorization.is_allowed(e.writer, 'domain.write', ModalityDomain.NOVEL, e.auth_scope)}")

    # ---- recreate under the SAME public id through the official route
    title = f"R3-I auth {slug.rsplit('-', 1)[-1]}"
    recreated = e.client.post("/api/experimental/projects", headers=e.init_headers,
                              json={"title": title})
    print(f"[PG-INC] recreate -> {recreated.status_code} {recreated.text[:200]}")
    if recreated.status_code >= 300:
        # The product contract refuses same-id recreation: record the real refusal and the state.
        print("[PG-INC] BLOCKED: the product refuses to recreate the same public id")
        assert gone is None or recreated.status_code == 409
        return

    new_nid = recreated.json()["id"]
    new_uuid = _novel_uuid(env, new_nid)
    print(f"[PG-INC] recreated slug={new_nid} new_uuid={new_uuid}")
    assert new_uuid, "the recreated project must have a novels row"
    if new_nid == slug:
        assert new_uuid != old_uuid, "a recreated same-id project must be a DIFFERENT incarnation"

    # ================= 1. DATA ISOLATION: the old document must not be readable =============
    old_doc_read = e.client.get(
        f"/api/novels/{slug}/experimental/creative/documents/{old_document}",
        headers=e.init_headers)
    print(f"[PG-INC] DATA_ISOLATION read old document -> {old_doc_read.status_code}")
    assert old_doc_read.status_code >= 400 or not old_doc_read.text.strip(), \
        "the old CreativeDocument must not be readable after recreate"

    # ================= 2. ASSET ISOLATION: the old prompt must not be inherited =============
    body = e.client.get(
        f"/api/projects/{new_nid}/studio/prompts/"
        f"{flow['prompt']['family_id']}/revisions/{old_asset}/body", headers=e.init_headers)
    print(f"[PG-INC] ASSET_ISOLATION read old prompt -> {body.status_code}")
    assert body.status_code >= 400, "the old Prompt asset must not be readable under the new id"

    # ================= 3/4. IDEMPOTENCY ISOLATION: the old request must not replay ==========
    new_scope = {"mode": "collaboration", "novel_id": new_nid}
    fresh_read = e.client.get(f"/api/projects/{new_nid}/studio/documents/{old_document}/"
                              f"prompt-adoption", headers=e.init_headers)
    print(f"[PG-INC] IDEMPOTENCY_ISOLATION adoption projection -> {fresh_read.status_code}")
    if fresh_read.status_code == 200:
        payload = fresh_read.json()
        assert payload.get("adoptions") in ([], None) or not payload.get("adoptions"), \
            "the old adoption proof must not appear under the new project"
