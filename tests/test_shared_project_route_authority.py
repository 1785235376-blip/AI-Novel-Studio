"""R1 original-route regressions, real File/PG identity and packaged sessions.

No policy/permission/session method is stubbed. Runtime/flag/role tests use the
production app with both mounted API prefixes. Baseline reproducer evidence and
all historical assertions remain separate and unchanged.
"""
from contextlib import contextmanager
from dataclasses import replace
from uuid import uuid4

import pytest

from app.actor_context import SessionContext
from app.authorization import AuthorizationScope, DomainRole, DomainRoleAssignment, ModalityDomain, PermissionAssignment, ScopeKind
from app.collaboration import Workspace
from app.experimental.flags import FLAGS
from app.identity import IdentityStatus, User, WorkspaceMembership
from app.packaging.bootstrap_api import PackagedBootstrapRegistry
from app.packaging.local_session_bootstrap import LocalSessionBootstrap, TrustedLocalIdentity
from app.packaging.runtime_identity import RuntimeIdentity
from app.services.v1_capability_service import ResearchRecordIn
from test_r3_mounted_contracts import checked, mounted, prefix, scoped


@pytest.fixture(params=["packaged", "collaboration"])
def mode(request):
    return request.param


@pytest.fixture(params=["off", "on", "v1"])
def flags(request):
    return request.param


@pytest.fixture
def authority(mounted, monkeypatch, mode, flags):
    e = scoped(mounted, monkeypatch)
    e.mode = mode
    config = replace(e.config, enable_collaboration_runtime=True,
                     enable_packaged_runtime=mode == "packaged")
    monkeypatch.setattr(e.api, "settings", config)
    monkeypatch.setattr(e.main, "settings", config)
    monkeypatch.setenv("EXPERIMENTAL_FEATURES", "" if flags == "off" else ",".join(FLAGS))
    monkeypatch.setenv("V1_ACCEPTANCE_MODE", "true" if flags == "v1" else "false")
    e.novels.update(e.nid, {"long_term_summary": "SYNTHETIC_PRIVATE_SUMMARY"})
    e.actors, e.grants = {}, {}
    for role in ("owner", "member", "reader", "nonmember", "revoked", "cross_workspace"):
        uid = role + "-" + uuid4().hex
        workspace = e.workspace
        if role == "cross_workspace":
            workspace = "other-" + uuid4().hex
            e.scopes.create_workspace(Workspace(workspace, "Synthetic other workspace"))
        e.identity.create_user(User(uid, uid))
        if role != "nonmember":
            e.identity.add_membership(WorkspaceMembership("m-" + uid, uid, workspace))
        if role == "cross_workspace":
            # Membership in both workspaces still cannot override the session's
            # currently selected workspace boundary.
            e.identity.add_membership(WorkspaceMembership("target-m-" + uid, uid, e.workspace))
        scope = AuthorizationScope(ScopeKind.WORKSPACE, e.workspace) if role == "owner" else AuthorizationScope(ScopeKind.PROJECT, e.workspace, e.nid)
        gid = "grant-" + uuid4().hex
        if role == "reader":
            e.authorization.assign_permission(PermissionAssignment(gid, uid, "domain.read", ModalityDomain.NOVEL, scope, e.lead))
        else:
            e.authorization.assign_role(DomainRoleAssignment(gid, uid,
                DomainRole.ADMIN if role == "owner" else DomainRole.DOMAIN_LEAD,
                ModalityDomain.NOVEL, scope, e.lead))
        if role == "revoked":
            e.identity.set_membership_status(uid, workspace, IdentityStatus.INACTIVE)
        e.actors[role] = (uid, workspace)
        e.grants[role] = gid

    def headers(role):
        uid, workspace = e.actors[role]
        if mode == "packaged":
            manager = LocalSessionBootstrap(runtime=RuntimeIdentity.create(), sessions=e.sessions,
                trusted_identity=TrustedLocalIdentity(uid, workspace), expected_origin="http://127.0.0.1:4173")
            token = manager.exchange(bootstrap_secret=manager.take_launcher_secret(),
                runtime_instance_id=manager.runtime.runtime_instance_id,
                origin=manager.expected_origin, remote_host="127.0.0.1").session_token
            registry = PackagedBootstrapRegistry(expected_origin=manager.expected_origin)
            registry.configure(manager)
            monkeypatch.setattr(e.main, "packaged_bootstrap_registry", registry)
            import app.dependencies as dependencies
            monkeypatch.setattr(dependencies, "packaged_bootstrap_registry", registry)
        else:
            token = "session-" + uuid4().hex
            e.sessions.register(token, SessionContext("s-" + uid, "c-" + uid, uid, workspace))
        return {"X-Session-Token": token}
    e.actor_headers = headers
    return e


# (suffix, collaboration admitted). Its restrictive original allowlist stays put.
READS = (
    ("", False), ("/chapters", False), ("/chapters/archived", True),
    ("/overview", True), ("/writing-goal", False), ("/research", True),
    ("/character-evolution", True), ("/lore/evidence", True),
    ("/lore/proposals", True), ("/characters", False), ("/outline", False),
)


@pytest.mark.parametrize("role", ["owner", "member", "reader", "nonmember", "revoked", "cross_workspace"])
def test_original_project_reads_require_current_project_authority(authority, role):
    e = authority
    headers = e.actor_headers(role)
    permitted = role in {"owner", "member", "reader"}
    for suffix, admitted in READS:
        response = e.client.get(e.prefix + f"/novels/{e.nid}" + suffix, headers=headers)
        expected = 501 if e.mode == "collaboration" and not admitted else 200 if permitted else 403
        assert response.status_code == expected, (role, suffix, response.text)
        if expected != 200:
            assert "SYNTHETIC_PRIVATE_SUMMARY" not in response.text
            assert e.chapter["content"] not in response.text
            assert '"counts"' not in response.text
    response = e.client.get(e.prefix + "/research", params={"novel_id": e.nid}, headers=headers)
    assert response.status_code == (200 if permitted else 403), response.text


@pytest.mark.parametrize("role", ["owner", "member", "reader", "nonmember", "revoked", "cross_workspace"])
def test_original_writes_fail_without_changes_and_preserve_valid_writers(authority, role):
    e = authority
    headers = e.actor_headers(role)
    writable = role in {"owner", "member"}
    before = e.novels.get(e.nid)
    research_before = e.capabilities.list_research(e.nid)
    response = e.client.post(e.prefix + f"/novels/{e.nid}/research", headers=headers,
                            json={"title": "Synthetic write", "notes": "Synthetic research"})
    assert response.status_code == (201 if writable else 403), response.text
    if not writable:
        assert e.capabilities.list_research(e.nid) == research_before
    response = e.client.put(e.prefix + f"/novels/{e.nid}/writing-goal", headers=headers,
                            json={"target_words": 4321, "target_chapters": 7})
    expected = 501 if e.mode == "collaboration" else 200 if writable else 403
    assert response.status_code == expected, response.text
    if expected == 200:
        assert e.novels.writing_goal(e.nid)["target_words"] == 4321
        assert e.novels.writing_goal(e.nid)["target_chapters"] == 7
    else:
        assert e.novels.get(e.nid) == before


@pytest.mark.parametrize("revocation", ["membership", "grant", "session"])
def test_revalidation_is_current_and_never_leaks_counts(authority, revocation):
    e = authority
    headers = e.actor_headers("reader")
    path = e.prefix + f"/novels/{e.nid}/overview"
    assert checked(e.client.get(path, headers=headers))["novel"]["id"] == e.nid
    uid, workspace = e.actors["reader"]
    if revocation == "membership":
        e.identity.set_membership_status(uid, workspace, IdentityStatus.INACTIVE)
    elif revocation == "grant":
        e.authorization.revoke_permission(e.grants["reader"], e.lead)
    else:
        e.sessions.revoke(headers["X-Session-Token"])
    response = e.client.get(path, headers=headers)
    assert response.status_code == (401 if revocation == "session" else 403), response.text
    assert '"counts"' not in response.text
    assert "SYNTHETIC_PRIVATE_SUMMARY" not in response.text


def test_branch_sources_are_never_substituted_with_project_manuscript(authority):
    e = authority
    headers = {**e.actor_headers("owner"), "X-Branch-ID": e.branch}
    for suffix, admitted in READS:
        response = e.client.get(e.prefix + f"/novels/{e.nid}" + suffix, headers=headers)
        assert response.status_code == (501 if e.mode == "collaboration" and not admitted else 409), response.text
        assert "SYNTHETIC_PRIVATE_SUMMARY" not in response.text
        assert e.chapter["content"] not in response.text
    headers["X-Branch-ID"] = "missing-branch"
    assert e.client.get(e.prefix + f"/novels/{e.nid}/overview", headers=headers).status_code == 403


@contextmanager
def other_project(e, *, workspace=None):
    nid = "hidden-" + uuid4().hex
    e.novels.create({"id": nid, "title": "SYNTHETIC_HIDDEN_PROJECT"})
    if workspace:
        e.scopes.link_project(workspace, nid)
    try:
        yield nid
    finally:
        e.novels.delete(nid)


def test_global_lists_filter_before_counts_and_pagination(authority):
    e = authority
    headers = e.actor_headers("reader")
    with other_project(e, workspace=e.workspace) as hidden:
        own = e.capabilities.evaluate_release_gate(e.nid, {})
        denied = e.capabilities.evaluate_release_gate(hidden, {})
        # Last journal row is unauthorized. Pagination must happen after ACLs.
        e.capabilities._audit("VISIBLE", "Synthetic", "visible", e.nid)
        e.capabilities._audit("SYNTHETIC_HIDDEN_ACTION", "Synthetic", "hidden", hidden)
        gates = checked(e.client.get(e.prefix + "/release-gates", headers=headers))
        assert [r["id"] for r in gates["items"]] == [own["id"]]
        assert gates["total"] == 1
        audit = checked(e.client.get(e.prefix + "/audit?limit=1", headers=headers))
        assert audit["total"] == 2
        assert len(audit["items"]) == 1 and audit["items"][0]["action"] == "VISIBLE"
        assert e.client.get(e.prefix + f"/release-gates/{denied['id']}", headers=headers).status_code == 403
        for path in ("/release-gates", "/audit"):
            response = e.client.get(e.prefix + path, params={"novel_id": hidden}, headers=headers)
            assert response.status_code == 403, response.text
            assert "SYNTHETIC_HIDDEN" not in response.text
        if e.mode == "packaged":
            projects = checked(e.client.get(e.prefix + "/novels", headers=headers))
            assert [r["id"] for r in projects] == [e.nid]
            assert checked(e.client.get("/novels", headers=headers)) == [{"id": e.nid}]
        else:
            assert e.client.get(e.prefix + "/novels", headers=headers).status_code == 501


def test_record_ids_cannot_bypass_review_permission(authority):
    e = authority
    pid = "pending-" + uuid4().hex
    e.canon.save_pending({"id": pid, "novel_id": e.nid, "chapter": 1,
                          "status": "PENDING", "proposals": [{"fact_key": "synthetic", "value": "Synthetic"}]})
    for role in ("reader", "nonmember", "revoked", "cross_workspace"):
        headers = e.actor_headers(role)
        for action in ("approve", "reject"):
            response = e.client.post(e.prefix + f"/pending-canon/{pid}/{action}", headers=headers)
            assert response.status_code == (501 if e.mode == "collaboration" else 403), response.text
            assert e.canon.repository.get_pending(pid)["status"] == "PENDING"
    headers = e.actor_headers("member")
    response = e.client.post(e.prefix + f"/pending-canon/{pid}/reject", headers=headers)
    assert response.status_code == (501 if e.mode == "collaboration" else 200), response.text
    if e.mode == "packaged":
        assert e.canon.repository.get_pending(pid)["status"] == "REJECTED"


def test_top_level_context_and_creation_require_authority(authority):
    e = authority
    headers = e.actor_headers("nonmember")
    response = e.client.post("/context-packs", headers=headers, json={"novel_id": e.nid, "chapter": 1, "instruction": "Synthetic"})
    assert response.status_code == (501 if e.mode == "collaboration" else 403), response.text
    before = e.novels.list()
    response = e.client.post(e.prefix + "/novels", headers=headers,
                            json={"id": "denied-" + uuid4().hex, "title": "Denied"})
    assert response.status_code == (501 if e.mode == "collaboration" else 403), response.text
    assert e.novels.list() == before
    response = e.client.post(e.prefix + "/novels/import", headers=headers,
                            json={"format": "txt", "content": "Synthetic import", "confirm": True})
    assert response.status_code == (501 if e.mode == "collaboration" else 403), response.text
    assert e.novels.list() == before


def test_local_noncollaboration_original_semantics_are_preserved(mounted):
    e = mounted
    assert checked(e.client.get(e.prefix + f"/novels/{e.nid}"))["id"] == e.nid
    assert checked(e.client.get(e.prefix + f"/novels/{e.nid}/chapters"))[0]["id"] == e.chapter["id"]
    result = checked(e.client.put(e.prefix + f"/novels/{e.nid}/writing-goal",
                                 json={"target_words": 4321, "target_chapters": 7}))
    assert result["target_words"] == 4321
    assert result["current_chapters"] == 1
    record = checked(e.client.post(e.prefix + f"/novels/{e.nid}/research",
                                  json={"title": "Local original research"}), 201)
    assert checked(e.client.get(e.prefix + f"/novels/{e.nid}/research/{record['id']}"))["id"] == record["id"]


def test_explicit_original_route_policy_inventory():
    from app.api import router
    audited = []
    for route in router.routes:
        for dependency in getattr(route, "dependencies", []):
            policy = getattr(dependency.dependency, "shared_project_policy", None)
            if policy:
                audited.append((tuple(sorted(route.methods)), route.path, policy))
    # Machine-readable inventory ensures shared original paths cannot disappear
    # from this remediation just because one reproducer endpoint became green.
    assert len(audited) >= 115
    by_path = {path: policy for _, path, policy in audited}
    for path in ("/novels/{nid}", "/novels/{nid}/chapters", "/novels/{nid}/overview",
                 "/novels/{nid}/writing-goal", "/novels/{nid}/characters",
                 "/projects/{project_id}/narrative/state", "/research",
                 "/novels/{nid}/lore/evidence"):
        assert path in by_path
    assert by_path["/pending-canon/{pid}/approve"][0] == "domain.review"
    assert by_path["/pending-canon/{pid}/approve"][1] == "pending"
    assert by_path["/release-gates/{gate_id}"][1] == "release_gate"


@pytest.mark.parametrize("role", ["owner", "member", "reader", "nonmember", "revoked", "cross_workspace"])
def test_every_declared_original_route_policy_uses_real_authority(authority, role):
    """Per-registration positive/negative checks, additional to mounted HTTP.

    This directly evaluates the production dependency with real request inputs
    and original authorization/storage. It is not an end-to-end business-flow
    claim for every record mutation or an allow-all handler replacement.
    """
    import asyncio
    import base64
    import json
    from fastapi import HTTPException
    from starlette.requests import Request

    e = authority
    headers = e.actor_headers(role)
    pid = "policy-pending-" + uuid4().hex
    e.canon.save_pending({"id": pid, "novel_id": e.nid, "status": "PENDING", "proposals": []})
    gate = e.capabilities.evaluate_release_gate(e.nid, {})
    asset = e.assets.create(e.nid, "synthetic.txt", base64.b64encode(b"SYNTHETIC_ASSET").decode(), "text/plain", "file")
    tested = 0
    for route in e.api.router.routes:
        for entry in getattr(route, "dependencies", []):
            dependency = entry.dependency
            policy = getattr(dependency, "shared_project_policy", None)
            if policy is None:
                continue
            permission, record, scoped_policy, unavailable = policy
            params = {"nid": e.nid, "project_id": e.nid, "workspace_id": e.workspace,
                      "pid": pid, "gate_id": gate["id"], "asset_id": asset["id"]}
            if "{storyline_id}" in route.path:
                params["storyline_id"] = e.storyline
            if "{branch_id}" in route.path:
                params["branch_id"] = e.branch
            async def receive():
                return {"type": "http.request", "body": json.dumps({"novel_id": e.nid}).encode(), "more_body": False}
            request = Request({"type": "http", "method": next(iter(route.methods)),
                               "path": e.prefix + route.path, "path_params": params,
                               "query_string": ("novel_id=" + e.nid).encode(),
                               "headers": [(key.lower().encode(), value.encode()) for key, value in headers.items()]}, receive)
            allowed = role in {"owner", "member"} or role == "reader" and permission == "domain.read"
            expected = 403 if not allowed else 501 if unavailable else None
            try:
                asyncio.run(dependency(request))
            except HTTPException as exc:
                assert exc.status_code == expected, (role, route.path, policy, exc.detail)
            else:
                assert expected is None, (role, route.path, policy)
            tested += 1
    assert tested >= 115
    assert e.canon.repository.get_pending(pid)["status"] == "PENDING"


def test_supported_creation_links_new_project_to_authorized_workspace(authority):
    e = authority
    headers = e.actor_headers("owner")
    nid = "new-authorized-" + uuid4().hex
    response = e.client.post(e.prefix + "/novels", headers=headers, json={"id": nid, "title": nid})
    if e.mode == "collaboration":
        assert response.status_code == 501
        return
    try:
        assert checked(response, 201)["id"] == nid
        assert e.scopes.repository.project_workspace(nid) == e.workspace
        assert checked(e.client.get(e.prefix + f"/novels/{nid}", headers=headers))["id"] == nid
    finally:
        e.novels.delete(nid)


@pytest.mark.parametrize("credential", ["absent", "unknown", "revoked"])
def test_original_capability_reads_require_current_session(authority, credential):
    e = authority
    headers = e.actor_headers("owner")
    if credential == "absent":
        headers = {}
    elif credential == "unknown":
        headers = {"X-Session-Token": "synthetic-unknown"}
    else:
        e.sessions.revoke(headers["X-Session-Token"])
    response = e.client.get(e.prefix + f"/novels/{e.nid}/overview", headers=headers)
    assert response.status_code == 401
    assert '"counts"' not in response.text


def test_storyline_grant_is_used_at_its_declared_scope(authority):
    import asyncio
    from fastapi import HTTPException
    from starlette.requests import Request
    e = authority
    headers = e.actor_headers("reader")
    uid, workspace = e.actors["reader"]
    e.authorization.revoke_permission(e.grants["reader"], e.lead)
    scope = AuthorizationScope(ScopeKind.STORYLINE, workspace, e.nid, e.storyline)
    e.authorization.assign_permission(PermissionAssignment("story-read-" + uuid4().hex, uid,
        "domain.read", ModalityDomain.NOVEL, scope, e.lead))
    request = Request({"type": "http", "method": "GET", "path": e.prefix,
        "path_params": {"workspace_id": workspace, "project_id": e.nid, "storyline_id": e.storyline},
        "query_string": b"", "headers": [(b"x-session-token", headers["X-Session-Token"].encode())]})
    asyncio.run(e.api._shared_scope_read(request))
    with pytest.raises(HTTPException) as denied:
        e.api._require_shared_project(e.nid, headers["X-Session-Token"], "domain.read")
    assert denied.value.status_code == 403
    assert e.client.get(e.prefix + f"/novels/{e.nid}/overview", headers=headers).status_code == 403


@pytest.mark.parametrize("role", ["owner", "member", "reader", "branch_member"])
def test_existing_chapter_authority_cas_and_history_remain_valid(authority, monkeypatch, role):
    from app.application.audit_service import AuditService
    from app.application.collaboration_service import CollaborationApplicationService
    from app.application.persistence import create_atomic_chapter_audit_port

    e = authority
    e.actors["branch_member"] = (e.lead, e.workspace)
    service = CollaborationApplicationService(e.membership,
        create_atomic_chapter_audit_port(e.bundle.chapters, e.bundle.authorization),
        AuditService(e.bundle.authorization))
    monkeypatch.setattr(e.api, "collaboration_application_service", service)
    headers = {**e.actor_headers(role), "X-Branch-ID": e.branch}
    path = e.prefix + f"/chapters/{e.chapter['id']}"
    before = checked(e.client.get(path, headers=headers))
    response = e.client.put(path, headers=headers,
        json={"version": before["version"], "content": "SYNTHETIC_AUTHORIZED_CHAPTER_CHANGE"})
    if role == "reader":
        assert response.status_code == 403
        assert e.chapters.get(e.chapter["id"]) == before
    else:
        after = checked(response)
        assert after["version"] == before["version"] + 1
        assert "SYNTHETIC_AUTHORIZED_CHAPTER_CHANGE" in e.chapters.get(e.chapter["id"])["content"]
        stale = e.client.put(path, headers=headers,
            json={"version": before["version"], "content": "SYNTHETIC_STALE_CHANGE"})
        assert stale.status_code == 409
        assert "SYNTHETIC_STALE_CHANGE" not in e.chapters.get(e.chapter["id"])["content"]
    history = checked(e.client.get(path + "/history", headers=headers))
    assert isinstance(history, list)


def test_existing_chapter_routes_reject_arbitrary_and_foreign_branch_ownership(authority):
    from app.collaboration import Branch, Storyline

    e = authority
    headers = e.actor_headers("owner")
    before = e.chapters.get(e.chapter["id"])
    path = e.prefix + f"/chapters/{e.chapter['id']}"
    for same_workspace in (True, False):
        workspace = e.workspace
        if not same_workspace:
            workspace = "foreign-w-" + uuid4().hex
            e.scopes.create_workspace(Workspace(workspace, "Synthetic foreign workspace"))
        with other_project(e, workspace=workspace) as nid:
            sid, bid = "foreign-s-" + uuid4().hex, "foreign-b-" + uuid4().hex
            e.scopes.create_storyline(Storyline(sid, workspace, nid, "Synthetic foreign story"))
            e.scopes.create_branch(Branch(bid, workspace, nid, sid, "Synthetic foreign branch"))
            foreign = {**headers, "X-Branch-ID": bid}
            for suffix in ("", "/history"):
                response = e.client.get(path + suffix, headers=foreign)
                assert response.status_code == 403
                assert e.chapter["content"] not in response.text
            assert e.client.put(path, headers=foreign,
                json={"version": before["version"], "content": "DENIED"}).status_code == 403
            assert e.chapters.get(e.chapter["id"]) == before
    unknown = {**headers, "X-Branch-ID": "synthetic-unknown-branch"}
    assert e.client.get(path, headers=unknown).status_code == 401
    assert e.chapters.get(e.chapter["id"]) == before
