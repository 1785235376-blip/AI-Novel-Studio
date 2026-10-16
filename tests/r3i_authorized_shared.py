"""Shared helpers for the R3-I authorized HTTP tests (File and PostgreSQL).

Test-utility code only: it builds synthetic collaboration identities with the APPLICATION'S OWN
services and drives the real HTTP routes. It creates no second repository bundle, no second
authorization service and no fake router.
"""
from __future__ import annotations

import hashlib
from types import SimpleNamespace
from uuid import uuid4

import pytest


def make_env(backend_marker: str = "file"):
    """Return a module-scoped fixture body that asserts the REAL runtime identity."""

    def _env():
        import os

        from fastapi.testclient import TestClient

        from app import dependencies as deps
        import app.api as api
        import app.main as main

        assert getattr(main.settings, "enable_collaboration_runtime", False) is True, \
            "run with --collaboration-runtime so the flag is exported before app.main import"
        assert api.trusted_session_resolver is deps.trusted_session_resolver, \
            "app.api and app.dependencies use different session resolvers"

        expected = "postgres" if backend_marker == "postgres" else "file"
        assert getattr(main.settings, "storage_backend", None) == expected, \
            f"settings.storage_backend is {getattr(main.settings, 'storage_backend', None)!r}, " \
            f"expected {expected!r}"

        return SimpleNamespace(
            client=TestClient(main.app, raise_server_exceptions=False),
            main=main, api=api, deps=deps,
            novels=deps.novel_service,
            scopes=deps.collaboration_scope_service,
            identity=deps.identity_service,
            authorization=deps.authorization_service,
            membership=deps.membership_authorization_service,
            sessions=deps.trusted_session_resolver,
            expected_backend=expected,
            data_path=os.environ.get("NOVEL_DATA_PATH"),
        )

    return _env


def build_authorized(env):
    """Create workspace, identities, project-over-HTTP, storyline, branches and grants."""
    from app.actor_context import SessionContext
    from app.authorization import (AuthorizationScope, DomainRole, DomainRoleAssignment,
                                   ModalityDomain, PermissionAssignment, ScopeKind)
    from app.collaboration import Branch, Storyline, Workspace
    from app.identity import User, WorkspaceMembership

    suffix = uuid4().hex[:10]
    workspace, storyline = f"w-{suffix}", f"s-{suffix}"
    branch, other = f"b-{suffix}", f"x-{suffix}"
    init_user, writer, reader = f"init-{suffix}", f"writer-{suffix}", f"reader-{suffix}"

    env.scopes.create_workspace(Workspace(workspace, "R3-I authorized"))
    for user in (init_user, writer, reader):
        env.identity.create_user(User(user, user))
        env.identity.add_membership(WorkspaceMembership("m-" + user, user, workspace))
        env.sessions.register(user, SessionContext("session-" + user, "client-" + user,
                                                   user, workspace))
    env.authorization.assign_role(DomainRoleAssignment(
        "init-" + suffix, init_user, DomainRole.DOMAIN_LEAD, ModalityDomain.NOVEL,
        AuthorizationScope(ScopeKind.WORKSPACE, workspace, None, None, None), init_user))

    init_headers = {"X-Session-Token": init_user}
    project = env.client.post("/api/experimental/projects", headers=init_headers,
                              json={"title": "R3-I auth " + suffix})
    assert project.status_code == 201, (project.status_code, project.text[:400])
    nid = project.json()["id"]
    assert env.novels.get(nid) is not None
    bound = env.scopes.repository.project_workspace(nid)
    assert bound == workspace, f"project bound to {bound!r}, expected {workspace!r}"

    env.scopes.create_storyline(Storyline(storyline, workspace, nid, "Main"))
    for bid in (branch, other):
        env.scopes.create_branch(Branch(bid, workspace, nid, storyline, bid))

    auth_scope = AuthorizationScope(ScopeKind.BRANCH, workspace, nid, storyline, branch)
    env.writer_role = "w-" + suffix
    env.auth_scope = auth_scope
    env.authorization.assign_role(DomainRoleAssignment(
        env.writer_role, writer, DomainRole.DOMAIN_LEAD, ModalityDomain.NOVEL, auth_scope,
        init_user))
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


def chain(e, prefix, headers):
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


def full_adoption_assertions(e, flow, expect_actor, *, prefix_label=""):
    """Run the adoption, read back, replay - and assert every contract detail."""
    c = flow["client"]
    result = flow["result"]
    proof = result["adoption"]
    assert result["committed"] is True
    assert result["version"] == flow["target"]["version"] + 1, f"{prefix_label} version must be +1"
    assert proof["adopted_by"] == expect_actor, f"{prefix_label} adopted_by {proof['adopted_by']!r}"
    assert proof["asset_id"] == flow["prompt"]["asset_id"]
    assert proof["revision"] == 1
    assert proof["digest"] == flow["source"]["digest"]
    assert proof["result_version"] == result["version"]

    live = c.get(f"{flow['creative']}/documents/{flow['board']['id']}",
                 headers=flow["headers"]).json()
    shot = next(i for i in live["shots"] if i["id"] == flow["shot_id"])
    assert shot["frame_prompt"] == flow["source"]["value"], f"{prefix_label} text must be verbatim"
    assert hashlib.sha256(shot["frame_prompt"].encode()).hexdigest() == proof["digest"]

    projection = c.get(flow["read_url"], headers=flow["headers"]).json()
    entry = next(a for a in projection["adoptions"]
                 if a["request_id"] == flow["dto"]["request_id"])
    assert entry["still_applied"] is True, f"{prefix_label} still_applied must be True"
    assert projection["version"] == result["version"]

    replay = c.post(flow["adopt_url"], headers=flow["headers"], json=flow["dto"])
    assert replay.status_code == 200, (replay.status_code, replay.text[:300])
    assert replay.json()["replayed"] is True
    assert replay.json()["version"] == result["version"]
    after = c.get(flow["read_url"], headers=flow["headers"]).json()
    assert after["version"] == result["version"], "a replay must not add a revision"
    assert len([a for a in after["adoptions"]
                if a["request_id"] == flow["dto"]["request_id"]]) == 1
    return {"live": live, "projection": projection, "replay": replay.json()}
