"""R3-I — PG-INCARNATION: SAME-ID recreation, AUTHORIZATION isolation, and cross-workspace atomicity.

CORRECTED. The previous version asserted `status_code >= 400` on three reads that carried NO
`X-Branch-ID`, so `_workbench_authorize()` answered 400 BRANCH_SCOPE_REQUIRED and the assertions
proved nothing about isolation. Those results are treated as UNPROVEN, not PASS. Every isolation
request here carries a real session token AND a real branch id, and the codes are distinguished:
400 BRANCH_SCOPE_REQUIRED (unproven), 403 PROJECT_SCOPE_FORBIDDEN (refused), 404 (invisible),
200 (visible). A request refused merely for lacking scope is never counted as isolation.

The discriminating question is NOT "is the new UUID different" but "can the OLD actor, holding only
the OLD branch role, actually act on the NEW project now that the public id is identical again".
"""
from __future__ import annotations

import os

import pytest

from r3i_authorized_shared import build_authorized, chain, make_env

pytestmark = pytest.mark.postgres_backend_only

CREATIVE = "/api/novels/{nid}/experimental/creative"
STUDIO = "/api/projects/{nid}/studio"


@pytest.fixture(scope="module")
def env():
    assert os.environ.get("PROJECT_ROOT"), "requires the isolated runner"
    return make_env("postgres")()


@pytest.fixture
def authorized(env):
    return build_authorized(env)


def _query(sql: str, params: tuple):
    import psycopg
    with psycopg.connect(os.environ["TEST_POSTGRES_DATABASE_URL"], connect_timeout=5) as conn:
        return conn.execute(sql, params).fetchone()


def _novel_row(slug: str):
    return _query("SELECT id::text, slug FROM novels WHERE slug = %s", (slug,))


def _binding(project_id: str):
    row = _query("SELECT workspace_id FROM project_workspaces WHERE project_id = %s", (project_id,))
    return row[0] if row else None


def _reason(response) -> str:
    try:
        body = response.json()
    except Exception:  # noqa: BLE001
        return ""
    detail = body.get("detail") if isinstance(body, dict) else None
    if isinstance(detail, dict):
        return str(detail.get("code") or "")
    return str(body.get("code") or "")


def _forbidden(response):
    assert response.status_code == 403, (response.status_code, response.text[:300])
    assert _reason(response) == "PROJECT_SCOPE_FORBIDDEN", response.text[:300]


def test_PG_INCARNATION_same_id_recreation_and_old_authority(env, authorized):
    import app.creative.prompt_adoption_api as adopt_api

    e = authorized
    slug = e.nid
    before = _novel_row(slug)
    assert before is not None, "the project must exist before the test"
    old_uuid = before[0]
    print(f"[PG-INC] slug={slug} old_uuid={old_uuid}")

    # ---- real content plus an adoption Proof on the old incarnation
    flow = chain(e, "/api", e.headers)
    adopt_api.PROMPT_ADOPTION_WRITE_ENABLED = True
    try:
        adopted = e.client.post(flow["adopt_url"], headers=e.headers, json=flow["dto"])
    finally:
        adopt_api.PROMPT_ADOPTION_WRITE_ENABLED = False
    assert adopted.status_code == 200, (adopted.status_code, adopted.text[:300])
    old_document = flow["board"]["id"]
    old_family, old_asset = flow["prompt"]["family_id"], flow["prompt"]["asset_id"]
    old_request = flow["dto"]["request_id"]

    # ---- delete through the official route, then PROVE the row is gone
    deleted = e.client.delete(f"/api/novels/{slug}", headers=e.init_headers)
    assert deleted.status_code == 204, (deleted.status_code, deleted.text[:200])
    gone = _novel_row(slug)
    print(f"[PG-INC] novels row after delete: {gone!r}")
    assert gone is None, "the deleted project's novels row must not survive"
    print(f"[PG-INC] project_workspaces after delete: {_binding(slug)!r}")
    assert _binding(slug) is None, "retirement must remove the old workspace binding"
    assert not [row for row in e.authorization.repository.list_role_assignments()
                if row["scope"].get("project_id") == slug]
    assert not [row for row in e.authorization.repository.list_permission_assignments()
                if row["scope"].get("project_id") == slug]
    assert e.scopes.repository.list("storylines", project_id=slug) == []
    assert e.scopes.repository.list("branches", project_id=slug) == []

    # ---- recreate under the SAME public id: must really succeed
    title = "R3-I auth " + slug.rsplit("-", 1)[-1]
    recreated = e.client.post("/api/experimental/projects", headers=e.init_headers,
                              json={"title": title})
    print(f"[PG-INC] recreate -> {recreated.status_code} {_reason(recreated)}")
    assert recreated.status_code == 201, (
        "SAME_ID_RECREATION must be explicit: expected 201, got "
        f"{recreated.status_code} {_reason(recreated)}")
    new_nid = recreated.json()["id"]
    assert new_nid == slug, f"expected the same public id {slug!r}, got {new_nid!r}"

    fresh = _novel_row(new_nid)
    assert fresh is not None, "the recreated project must have a novels row"
    new_uuid = fresh[0]
    print(f"[PG-INC] new_uuid={new_uuid} binding={_binding(new_nid)!r}")
    assert new_uuid != old_uuid, "SAME_ID_RECREATION must produce a new incarnation"

    # Positive control: explicitly authorize a new actor on the new incarnation,
    # while deliberately reusing the exact public storyline and branch IDs.
    from uuid import uuid4
    from app.actor_context import SessionContext
    from app.authorization import AuthorizationScope, DomainRole, DomainRoleAssignment, ModalityDomain, ScopeKind
    from app.collaboration import Branch, Storyline
    from app.identity import User, WorkspaceMembership
    actor = "new-incarnation-" + uuid4().hex
    e.scopes.create_storyline(Storyline(e.storyline, e.workspace, new_nid, "Fresh storyline"))
    e.scopes.create_branch(Branch(e.branch, e.workspace, new_nid, e.storyline, "Fresh branch"))
    e.identity.create_user(User(actor, actor))
    e.identity.add_membership(WorkspaceMembership("m-" + actor, actor, e.workspace))
    e.authorization.assign_role(DomainRoleAssignment(uuid4().hex, actor, DomainRole.DOMAIN_LEAD,
        ModalityDomain.NOVEL, AuthorizationScope(ScopeKind.PROJECT, e.workspace, new_nid), e.init_user))
    e.sessions.register(actor, SessionContext("session-" + actor, "client-" + actor, actor, e.workspace))
    fresh_headers = {"X-Session-Token": actor, "X-Branch-ID": e.branch}
    positive = e.client.post(CREATIVE.format(nid=new_nid) + "/documents", headers=fresh_headers,
        json={"mode": "SCREENPLAY", "title": "Legitimate new incarnation", "source_independent": True,
              "scenes": [{"id": "fresh-scene", "sequence": 1, "heading": "INT. ROOM - DAY", "action": "A visitor arrives."}]})
    assert positive.status_code == 201, (positive.status_code, positive.text[:300])
    positive_read = e.client.get(CREATIVE.format(nid=new_nid) + "/documents/" + positive.json()["id"], headers=fresh_headers)
    assert positive_read.status_code == 200 and positive_read.json() == positive.json()

    # ================= AUTHORIZATION_ISOLATION: the DISCRIMINATING test ====================
    old_headers = {"X-Session-Token": e.writer, "X-Branch-ID": e.branch}
    created = e.client.post(CREATIVE.format(nid=new_nid) + "/documents", headers=old_headers,
                            json={"mode": "SCREENPLAY", "title": "old writer probe",
                                  "source_independent": True,
                                  "scenes": [{"id": "s1", "sequence": 1, "heading": "H"}]})
    print(f"[PG-INC] AUTHORIZATION old writer creates in NEW project -> "
          f"{created.status_code} {_reason(created)}")
    _forbidden(created)

    # ================= DATA_ISOLATION (same headers, so scope is not the reason) ============
    old_doc = e.client.get(CREATIVE.format(nid=new_nid) + f"/documents/{old_document}",
                           headers=old_headers)
    print(f"[PG-INC] DATA old document via NEW project -> {old_doc.status_code} {_reason(old_doc)}")
    _forbidden(old_doc)

    # ================= IDEMPOTENCY_ISOLATION (request identity, not just a failing GET) =====
    projection = e.client.get(STUDIO.format(nid=new_nid) +
                              f"/documents/{old_document}/prompt-adoption", headers=old_headers)
    print(f"[PG-INC] IDEMPOTENCY projection -> {projection.status_code} {_reason(projection)}")
    _forbidden(projection)

    # ================= ASSET_ISOLATION =====================================================
    body = e.client.get(STUDIO.format(nid=new_nid) +
                        f"/prompts/{old_family}/revisions/{old_asset}/body", headers=old_headers)
    print(f"[PG-INC] ASSET old prompt via NEW project -> {body.status_code} {_reason(body)}")
    _forbidden(body)

    # Data/asset/request isolation also holds for the freshly authorized actor.
    assert e.client.get(CREATIVE.format(nid=new_nid) + f"/documents/{old_document}", headers=fresh_headers).status_code == 404
    assert e.client.get(STUDIO.format(nid=new_nid) + f"/prompts/{old_family}/revisions/{old_asset}/body", headers=fresh_headers).status_code == 404
    fresh_board = e.client.post(CREATIVE.format(nid=new_nid) + f"/documents/{positive.json()['id']}/derive",
        headers=fresh_headers, json={"expected_version": positive.json()["version"], "mode": "STORYBOARD",
                                    "title": "Fresh incarnation storyboard", "shot_policy": "SCENE"})
    assert fresh_board.status_code == 201, fresh_board.text[:300]
    new_projection = e.client.get(STUDIO.format(nid=new_nid) + f"/documents/{fresh_board.json()['id']}/prompt-adoption", headers=fresh_headers)
    assert new_projection.status_code == 200, new_projection.text[:300]
    assert not [row for row in new_projection.json().get("adoptions", []) if row.get("request_id") == old_request]

    print("[PG-INC] RESULT same_id_recreation=PASS data=PASS asset=PASS idempotency=PASS "
          "authorization=PASS")
