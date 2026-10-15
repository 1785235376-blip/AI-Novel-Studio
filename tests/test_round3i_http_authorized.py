"""R3-I — REAL collaboration-authorized HTTP adoption (A), read-only refusal (B), /api/v1 (C).

Run with:  python scripts/run_v2_checks.py --collaboration-runtime r3i-auth-file -- \
             python -m pytest tests/test_round3i_http_authorized.py -q -rs

The fixture reuses the application's OWN service graph from `app.dependencies`, so the session
resolver, scope service, identity service and authorization service used to build the fixtures
are the very same objects the HTTP routes use. It does NOT build a second bundle, scope service
or resolver, and it does not patch them.

CORRECTED ORDERING: `CollaborationScopeService.create_storyline` raises
"project does not belong to workspace" when `project_workspace(item.project_id) != workspace_id`.
The project must therefore be created FIRST (over real HTTP, by the initializing user), and the
storyline and branches created afterwards with the REAL project id.
"""
from __future__ import annotations

import hashlib
import os
from types import SimpleNamespace
from uuid import uuid4

import pytest

pytestmark = pytest.mark.file_backend_only


@pytest.fixture(scope="module")
def env():
    if os.environ.get("PROJECT_ROOT") is None:
        pytest.skip("requires the isolated runner")
    from fastapi.testclient import TestClient

    from app import dependencies as deps
    import app.api as api
    import app.main as main

    # Collaboration must genuinely be on, and the app and its API layer must share ONE graph.
    assert getattr(main.settings, "enable_collaboration_runtime", False) is True, \
        "run with --collaboration-runtime so ENABLE_COLLABORATION_RUNTIME is exported first"
    assert api.trusted_session_resolver is deps.trusted_session_resolver, \
        "app.api and app.dependencies use different session resolvers"

    return SimpleNamespace(
        client=TestClient(main.app, raise_server_exceptions=False),
        main=main, api=api, deps=deps,
        novels=deps.novel_service,
        scopes=deps.collaboration_scope_service,
        identity=deps.identity_service,
        authorization=deps.authorization_service,
        membership=deps.membership_authorization_service,
        sessions=deps.trusted_session_resolver,
        data_path=os.environ.get("NOVEL_DATA_PATH"),
    )


@pytest.fixture
def authorized(env):
    from app.actor_context import SessionContext
    from app.authorization import (AuthorizationScope, DomainRole, DomainRoleAssignment,
                                   ModalityDomain, PermissionAssignment, ScopeKind)
    from app.collaboration import Branch, Storyline, Workspace
    from app.identity import User, WorkspaceMembership

    suffix = uuid4().hex[:10]
    workspace, storyline = f"w-{suffix}", f"s-{suffix}"
    branch, other = f"b-{suffix}", f"x-{suffix}"
    init_user, writer, reader = f"init-{suffix}", f"writer-{suffix}", f"reader-{suffix}"
    client = env.client

    # 1. workspace
    env.scopes.create_workspace(Workspace(workspace, "R3-I authorized"))
    # 2-5. identities, memberships and real sessions on the SAME resolver the routes use.
    for user in (init_user, writer, reader):
        env.identity.create_user(User(user, user))
        env.identity.add_membership(WorkspaceMembership("m-" + user, user, workspace))
        env.sessions.register(user, SessionContext("session-" + user, "client-" + user,
                                                   user, workspace))
    # 4. the initializer holds a WORKSPACE-scope NOVEL lead, which is what lets it create the
    #    project. The business writer deliberately does NOT get a workspace-wide grant, or the
    #    cross-branch refusal test would be a false positive.
    env.authorization.assign_role(DomainRoleAssignment(
        "init-" + suffix, init_user, DomainRole.DOMAIN_LEAD, ModalityDomain.NOVEL,
        AuthorizationScope(ScopeKind.WORKSPACE, workspace, None, None, None), init_user))

    # 6-7. create the project over REAL HTTP as the initializing user.
    init_headers = {"X-Session-Token": init_user}
    project = client.post("/api/experimental/projects", headers=init_headers,
                          json={"title": "R3-I auth " + suffix})
    assert project.status_code == 201, (project.status_code, project.text[:400])
    nid = project.json()["id"]

    # 8-9. prove the binding instead of assuming it.
    assert env.novels.get(nid) is not None, "the project must exist in the app's own novel service"
    bound = env.scopes.repository.project_workspace(nid)
    assert bound == workspace, f"project bound to {bound!r}, expected {workspace!r}"

    # 10-11. NOW the storyline and branches, with the real project id.
    env.scopes.create_storyline(Storyline(storyline, workspace, nid, "Main"))
    for bid in (branch, other):
        env.scopes.create_branch(Branch(bid, workspace, nid, storyline, bid))

    # 13-14. branch-scoped grants only.
    auth_scope = AuthorizationScope(ScopeKind.BRANCH, workspace, nid, storyline, branch)
    env.authorization.assign_role(DomainRoleAssignment(
        "w-" + suffix, writer, DomainRole.DOMAIN_LEAD, ModalityDomain.NOVEL, auth_scope, init_user))
    env.authorization.assign_permission(PermissionAssignment(
        "r-" + suffix, reader, "domain.read", ModalityDomain.NOVEL, auth_scope, init_user))

    env.nid, env.workspace, env.storyline = nid, workspace, storyline
    env.branch, env.other = branch, other
    env.init_user, env.writer, env.reader = init_user, writer, reader
    env.init_headers = init_headers
    env.headers = {"X-Session-Token": writer, "X-Branch-ID": branch}
    env.reader_headers = {"X-Session-Token": reader, "X-Branch-ID": branch}
    env.wrong_branch_headers = {"X-Session-Token": writer, "X-Branch-ID": other}
    return env


def _chain(e, prefix, headers):
    """The full real HTTP business chain. No service call replaces an HTTP call."""
    c, nid = e.client, e.nid
    creative = f"{prefix}/novels/{nid}/experimental/creative"
    studio = f"{prefix}/projects/{nid}/studio"

    screenplay = c.post(f"{creative}/documents", headers=headers, json={
        "mode": "SCREENPLAY", "title": "R3-I 授权剧本", "source_independent": True,
        "scenes": [{"id": "scene-1", "sequence": 1, "heading": "内景 房间 日",
                    "action": "人物走向窗边"}]})
    assert screenplay.status_code == 201, ("screenplay", screenplay.status_code, screenplay.text[:400])
    sp = screenplay.json()

    derived = c.post(f"{creative}/documents/{sp['id']}/derive", headers=headers, json={
        "expected_version": sp["version"], "mode": "STORYBOARD",
        "title": "R3-I 授权分镜", "shot_policy": "SCENE"})
    assert derived.status_code == 201, ("derive", derived.status_code, derived.text[:400])
    board = derived.json()
    shot_id = (board.get("shots") or [{}])[0].get("id")
    assert shot_id, "derive must return a real shot"

    prompt = c.post(f"{studio}/prompts", headers=headers, json={
        "text": "电影感中景，人物站在窗前，柔和侧光", "purpose": "IMAGE", "origin": "MANUAL",
        "request_id": "auth-prompt-" + uuid4().hex[:8]})
    assert prompt.status_code == 201, ("prompt", prompt.status_code, prompt.text[:400])
    p = prompt.json()
    approved = c.post(f"{studio}/prompts/{p['family_id']}/revisions/{p['asset_id']}/approve",
                      headers=headers, params={"expected_version": p["asset_version"]})
    assert approved.status_code == 200, ("approve", approved.status_code, approved.text[:400])

    body = c.get(f"{studio}/prompts/{p['family_id']}/revisions/{p['asset_id']}/body",
                 headers=headers)
    assert body.status_code == 200, ("body", body.status_code, body.text[:400])
    source = body.json()
    read = c.get(f"{studio}/documents/{board['id']}/prompt-adoption", headers=headers)
    assert read.status_code == 200, ("read", read.status_code, read.text[:400])
    target = read.json()

    dto = {"shot_id": shot_id, "family_id": p["family_id"], "asset_id": p["asset_id"],
           "revision": 1, "expected_digest": source["digest"],
           "expected_version": target["version"],
           "expected_digest_target": target["digest"],
           "request_id": "auth-adopt-" + uuid4().hex[:8]}
    return {"creative": creative, "studio": studio, "board": board, "shot_id": shot_id,
            "prompt": p, "source": source, "target": target, "dto": dto,
            "adopt_url": f"{studio}/documents/{board['id']}/shots/{shot_id}/prompt-adoption",
            "read_url": f"{studio}/documents/{board['id']}/prompt-adoption"}


def test_the_actor_is_a_real_collaboration_identity(authorized):
    e = authorized
    resolved = e.sessions.resolve(e.headers["X-Session-Token"])
    assert resolved.actor_id == e.writer
    assert resolved.actor_id != "local-author", "the request must not fall back to local-author"
    assert resolved.workspace_id == e.workspace
    assert e.identity.get_membership(e.writer, e.workspace) is not None


def test_A_authorized_writer_adopts_over_api(authorized):
    e = authorized
    import app.creative.prompt_adoption_api as adopt_api

    chain = _chain(e, "/api", e.headers)
    c = e.client
    closed = c.post(chain["adopt_url"], headers=e.headers, json=chain["dto"])
    assert closed.status_code == 503, (closed.status_code, closed.text[:300])
    assert c.get(chain["read_url"], headers=e.headers).json()["version"] == chain["target"]["version"]

    adopt_api.PROMPT_ADOPTION_WRITE_ENABLED = True
    try:
        ok = c.post(chain["adopt_url"], headers=e.headers, json=chain["dto"])
        assert ok.status_code == 200, ("adopt", ok.status_code, ok.text[:400])
        result = ok.json()
        assert result["committed"] is True
        assert result["version"] == chain["target"]["version"] + 1
        proof = result["adoption"]
        assert proof["adopted_by"] == e.writer, f"proof adopted_by {proof['adopted_by']!r}"
        assert proof["asset_id"] == chain["prompt"]["asset_id"]
        assert proof["revision"] == 1
        assert proof["digest"] == chain["source"]["digest"]
        assert proof["result_version"] == result["version"]

        live = c.get(f"{chain['creative']}/documents/{chain['board']['id']}", headers=e.headers).json()
        shot = next(i for i in live["shots"] if i["id"] == chain["shot_id"])
        assert shot["frame_prompt"] == chain["source"]["value"]
        assert hashlib.sha256(shot["frame_prompt"].encode()).hexdigest() == proof["digest"]

        projection = c.get(chain["read_url"], headers=e.headers).json()
        assert projection["adoptions"][-1]["still_applied"] is True
        assert projection["version"] == result["version"]

        replay = c.post(chain["adopt_url"], headers=e.headers, json=chain["dto"])
        assert replay.status_code == 200, replay.text[:300]
        assert replay.json()["replayed"] is True
        assert replay.json()["version"] == result["version"]
        final = c.get(chain["read_url"], headers=e.headers).json()
        assert final["version"] == result["version"]
        assert len([a for a in final["adoptions"]
                    if a["request_id"] == chain["dto"]["request_id"]]) == 1
    finally:
        adopt_api.PROMPT_ADOPTION_WRITE_ENABLED = False
    assert adopt_api.PROMPT_ADOPTION_WRITE_ENABLED is False


def test_B_a_read_only_user_is_refused_by_the_authorization_layer(authorized):
    """The switch is ON, so a refusal here is authorization, not the feature being disabled."""
    e = authorized
    import app.creative.prompt_adoption_api as adopt_api

    chain = _chain(e, "/api", e.headers)
    adopt_api.PROMPT_ADOPTION_WRITE_ENABLED = True
    try:
        denied = e.client.post(chain["adopt_url"], headers=e.reader_headers, json=chain["dto"])
        assert denied.status_code == 403, ("read-only must be 403", denied.status_code,
                                           denied.text[:400])
        after = e.client.get(chain["read_url"], headers=e.headers).json()
        assert after["version"] == chain["target"]["version"], "a refused write must not commit"
        assert after["adoptions"] == []
        live = e.client.get(f"{chain['creative']}/documents/{chain['board']['id']}",
                            headers=e.headers).json()
        shot = next(i for i in live["shots"] if i["id"] == chain["shot_id"])
        assert shot["frame_prompt"] == "", "a refused write must not touch the shot"
        assert chain["source"]["value"] not in denied.text, "the refusal leaked the prompt text"
    finally:
        adopt_api.PROMPT_ADOPTION_WRITE_ENABLED = False


@pytest.mark.parametrize("case", ["no_session", "bad_session", "wrong_branch"])
def test_unauthorized_callers_are_refused_and_change_nothing(authorized, case):
    e = authorized
    import app.creative.prompt_adoption_api as adopt_api

    chain = _chain(e, "/api", e.headers)
    headers = {"no_session": {"X-Branch-ID": e.branch},
               "bad_session": {"X-Session-Token": "not-a-session", "X-Branch-ID": e.branch},
               "wrong_branch": e.wrong_branch_headers}[case]
    adopt_api.PROMPT_ADOPTION_WRITE_ENABLED = True
    try:
        response = e.client.post(chain["adopt_url"], headers=headers, json=chain["dto"])
        assert response.status_code >= 400, (case, response.status_code, response.text[:300])
        assert response.status_code != 200
        after = e.client.get(chain["read_url"], headers=e.headers).json()
        assert after["version"] == chain["target"]["version"], f"{case} wrote to the document"
        assert after["adoptions"] == []
        assert chain["source"]["value"] not in response.text
    finally:
        adopt_api.PROMPT_ADOPTION_WRITE_ENABLED = False


def test_C_authorized_writer_adopts_over_api_v1(authorized):
    e = authorized
    import app.creative.prompt_adoption_api as adopt_api

    chain = _chain(e, "/api/v1", e.headers)
    adopt_api.PROMPT_ADOPTION_WRITE_ENABLED = True
    try:
        ok = e.client.post(chain["adopt_url"], headers=e.headers, json=chain["dto"])
        assert ok.status_code == 200, (ok.status_code, ok.text[:400])
        result = ok.json()
        assert result["committed"] is True
        assert result["version"] == chain["target"]["version"] + 1
        proof = result["adoption"]
        assert proof["adopted_by"] == e.writer
        assert proof["digest"] == chain["source"]["digest"]
        live = e.client.get(f"{chain['creative']}/documents/{chain['board']['id']}",
                            headers=e.headers).json()
        shot = next(i for i in live["shots"] if i["id"] == chain["shot_id"])
        assert shot["frame_prompt"] == chain["source"]["value"]
        projection = e.client.get(chain["read_url"], headers=e.headers).json()
        assert projection["adoptions"][-1]["still_applied"] is True
        replay = e.client.post(chain["adopt_url"], headers=e.headers, json=chain["dto"])
        assert replay.json()["replayed"] is True
        assert replay.json()["version"] == result["version"]
    finally:
        adopt_api.PROMPT_ADOPTION_WRITE_ENABLED = False
