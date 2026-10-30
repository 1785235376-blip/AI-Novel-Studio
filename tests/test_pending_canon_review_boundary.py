"""Independent approval/authority boundary for the finding-review Canon routes.

The new ``/api/projects/{project_id}/pending-canon/...`` review surface commits
Canon facts from a human decision. This file binds the current behavior to the
mounted route contract so the following cannot silently regress:

* project ``domain.review`` authority (read-only and cross-project sessions are
  refused before any pending row is read or written);
* session revocation between preview and commit;
* preview/version staleness and operation-id replay;
* project deletion + same-identifier recreation, where the old pending record
  must not be adopted by the new project.

Synthetic File fixtures only. Real PostgreSQL, browser and packaged Host
contexts remain NOT_RUN for this slice.
"""
from __future__ import annotations

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

REVIEW_FLAG = "finding_review_v1"


@pytest.fixture
def rig(tmp_path, monkeypatch):
    from app import api
    from app.actor_context import SessionContext
    from app.authorization import (
        AuthorizationScope, ModalityDomain, PermissionAssignment, ScopeKind,
    )
    from app.collaboration import Workspace
    from app.config import Settings
    from app.identity import User, WorkspaceMembership
    from app.pending_canon_review_api import create_pending_canon_review_router
    from app.repositories.factory import create_repository_bundle
    from app.services.authorization_service import AuthorizationService
    from app.services.canon_service import CanonService
    from app.services.chapter_service import ChapterService
    from app.services.collaboration_scope_service import CollaborationScopeService
    from app.services.identity_service import IdentityService
    from app.services.membership_authorization_service import MembershipAuthorizationService
    from app.services.novel_service import NovelService
    from app.services.pending_canon_review_service import PendingCanonReviewService
    from app.trusted_sessions import TrustedSessionResolver

    monkeypatch.setenv("EXPERIMENTAL_FEATURES", REVIEW_FLAG)
    bundle = create_repository_bundle(
        Settings(storage_backend="file", novel_data=tmp_path, enable_cloud=False,
                 mock_provider=True),
        data_root=tmp_path,
    )
    novels = NovelService(bundle.novels, bundle.chapters)
    chapters = ChapterService(bundle.chapters)
    canon = CanonService(bundle.canon)
    scopes = CollaborationScopeService(bundle.scope, bundle.novels)
    identities = IdentityService(bundle.identity, scopes)
    grants = AuthorizationService(bundle.authorization, scopes)
    membership = MembershipAuthorizationService(identities, grants)
    sessions = TrustedSessionResolver()
    service = PendingCanonReviewService(canon, chapters, novels)

    object.__setattr__(api.settings, "enable_collaboration_runtime", True)
    for name, value in (("novel_service", novels), ("collaboration_scope_service", scopes),
                        ("trusted_session_resolver", sessions),
                        ("membership_authorization_service", membership)):
        monkeypatch.setattr(api, name, value)

    scopes.create_workspace(Workspace("ws", "Synthetic workspace"))

    def project(nid=None):
        from uuid import uuid4
        created = novels.create({"title": "Synthetic Canon project " + uuid4().hex[:8],
                                 **({"id": nid} if nid else {})})
        scopes.link_project("ws", created["id"])
        return created["id"]

    for user in ("reviewer", "reader", "stale"):
        identities.create_user(User(user, user))
        identities.add_membership(WorkspaceMembership("member-" + user, user, "ws"))
        sessions.register("token-" + user, SessionContext("session-" + user, "client", user, "ws"))

    nid = project()

    def grant(user, permission, project_id):
        grants.assign_permission(PermissionAssignment(
            f"perm:{user}:{permission}:{project_id}", user, permission,
            ModalityDomain.NOVEL,
            AuthorizationScope(ScopeKind.PROJECT, "ws", project_id), "fixture"))

    grant("reviewer", "domain.review", nid)
    grant("reviewer", "domain.read", nid)
    grant("reader", "domain.read", nid)
    grant("stale", "domain.read", nid)

    def add_pending(pending_id, project_id=nid, fact="Synthetic fact"):
        chapter = chapters.create(project_id, {"title": "Chapter " + pending_id,
                                               "content": "Synthetic source prose."})
        chapter_id = chapter["id"]
        canon.save_pending({"id": pending_id, "novel_id": project_id, "chapter_id": chapter_id,
                            "proposals": [{"fact": fact, "source_evidence": None}]})
        return chapter_id

    app = FastAPI()
    app.include_router(create_pending_canon_review_router(service, api._pending_canon_review_authorize),
                       prefix="/api")
    client = TestClient(app)
    yield {
        "client": client, "nid": nid, "project": project, "add_pending": add_pending,
        "canon": canon, "chapters": chapters, "sessions": sessions, "grant": grant,
    }
    client.close()


def _review(client, nid, pending_id, token, *, expected_version=1, preview_digest=None,
            action="approve", operation_id="op-1", reason="reviewed", chapter_id=None):
    body = {
        "expected_version": expected_version, "preview_digest": preview_digest,
        "action": action, "reason": reason, "operation_id": operation_id, "confirmed": True,
    }
    if chapter_id is not None:
        body["chapter_id"] = chapter_id
    headers = {"X-Session-Token": token} if token else {}
    return client.post(f"/api/projects/{nid}/pending-canon/{pending_id}/review", json=body,
                       headers=headers)


def _preview(client, nid, pending_id, token, chapter_id=None):
    headers = {"X-Session-Token": token} if token else {}
    body = {"chapter_id": chapter_id} if chapter_id else {}
    return client.post(f"/api/projects/{nid}/pending-canon/{pending_id}/preview", json=body,
                       headers=headers)


def _pending_row(rig, nid, pending_id):
    path = rig["canon"].repository.backend.novels / nid / "pending_canon" / f"{pending_id}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _canon_facts(rig, nid):
    return rig["canon"].list(nid)


def test_review_requires_project_review_authority_and_session(rig):
    pending = "pending-authority"
    rig["add_pending"](pending)
    preview = _preview(rig["client"], rig["nid"], pending, "token-reviewer")
    assert preview.status_code == 200, preview.text
    digest = preview.json()["preview_digest"]

    anonymous = _review(rig["client"], rig["nid"], pending, None, preview_digest=digest)
    assert anonymous.status_code == 401
    assert anonymous.json()["detail"]["code"] == "SESSION_REQUIRED"

    read_only = _review(rig["client"], rig["nid"], pending, "token-reader", preview_digest=digest)
    assert read_only.status_code == 403
    assert read_only.json()["detail"]["code"] == "PROJECT_SCOPE_FORBIDDEN"
    assert _pending_row(rig, rig["nid"], pending)["status"] == "PENDING"
    assert _canon_facts(rig, rig["nid"]) == []


def test_cross_project_review_is_refused_before_reading_pending(rig):
    other = rig["project"]()
    pending = "pending-cross"
    rig["add_pending"](pending, project_id=other)
    denied = _review(rig["client"], other, pending, "token-reviewer", preview_digest="0" * 64)
    assert denied.status_code == 403
    assert denied.json()["detail"]["code"] == "PROJECT_SCOPE_FORBIDDEN"
    assert _pending_row(rig, other, pending)["status"] == "PENDING"


def test_revoked_session_cannot_commit_a_previewed_decision(rig):
    pending = "pending-revoke"
    rig["add_pending"](pending)
    # "stale" can preview (domain.read) but has no review grant yet.
    preview = _preview(rig["client"], rig["nid"], pending, "token-stale")
    assert preview.status_code == 200, preview.text
    digest = preview.json()["preview_digest"]
    rig["grant"]("stale", "domain.review", rig["nid"])
    allowed = _preview(rig["client"], rig["nid"], pending, "token-stale")
    assert allowed.status_code == 200, allowed.text
    digest = allowed.json()["preview_digest"]
    rig["sessions"].revoke("token-stale")
    revoked = _review(rig["client"], rig["nid"], pending, "token-stale", preview_digest=digest)
    assert revoked.status_code == 401
    assert revoked.json()["detail"]["code"] == "INVALID_SESSION"
    assert _pending_row(rig, rig["nid"], pending)["status"] == "PENDING"
    assert _canon_facts(rig, rig["nid"]) == []


def test_stale_expected_version_cannot_commit(rig):
    pending = "pending-stale-version"
    rig["add_pending"](pending)
    preview = _preview(rig["client"], rig["nid"], pending, "token-reviewer")
    digest = preview.json()["preview_digest"]
    denied = _review(rig["client"], rig["nid"], pending, "token-reviewer",
                     preview_digest=digest, expected_version=7)
    assert denied.status_code == 409
    assert denied.json()["detail"]["code"] == "CANON_VERSION_CONFLICT"
    assert _pending_row(rig, rig["nid"], pending)["status"] == "PENDING"
    assert _canon_facts(rig, rig["nid"]) == []


def test_stale_preview_digest_cannot_commit(rig):
    pending = "pending-stale-preview"
    rig["add_pending"](pending)
    preview = _preview(rig["client"], rig["nid"], pending, "token-reviewer")
    assert preview.status_code == 200, preview.text
    denied = _review(rig["client"], rig["nid"], pending, "token-reviewer",
                     preview_digest="0" * 64)
    assert denied.status_code == 409
    assert denied.json()["detail"]["code"] == "CANON_PREVIEW_STALE"
    assert _pending_row(rig, rig["nid"], pending)["status"] == "PENDING"
    assert _canon_facts(rig, rig["nid"]) == []


def test_operation_id_reuse_with_different_decision_is_refused(rig):
    pending = "pending-reuse-digest"
    rig["add_pending"](pending)
    digest = _preview(rig["client"], rig["nid"], pending, "token-reviewer").json()["preview_digest"]
    first = _review(rig["client"], rig["nid"], pending, "token-reviewer",
                    preview_digest=digest, operation_id="op-shared", reason="first")
    assert first.status_code == 200, first.text
    facts_after_first = len(_canon_facts(rig, rig["nid"]))
    replay = _review(rig["client"], rig["nid"], pending, "token-reviewer",
                     preview_digest=digest, operation_id="op-shared", reason="different")
    assert replay.status_code == 409
    assert replay.json()["detail"]["code"] == "CANON_OPERATION_REUSED"
    assert len(_canon_facts(rig, rig["nid"])) == facts_after_first


def test_successful_review_commits_once_and_replays_idempotently(rig):
    pending = "pending-success"
    rig["add_pending"](pending)
    preview = _preview(rig["client"], rig["nid"], pending, "token-reviewer")
    digest = preview.json()["preview_digest"]
    first = _review(rig["client"], rig["nid"], pending, "token-reviewer",
                    preview_digest=digest, operation_id="op-success")
    assert first.status_code == 200, first.text
    assert first.json()["status"] == "APPROVED"
    facts = _canon_facts(rig, rig["nid"])
    assert len(facts) == 1 and facts[0]["source"] == f"pending:{pending}"
    replay = _review(rig["client"], rig["nid"], pending, "token-reviewer",
                     preview_digest=digest, operation_id="op-success")
    assert replay.status_code == 200
    assert len(_canon_facts(rig, rig["nid"])) == 1


def test_deleted_and_recreated_project_does_not_adopt_old_pending(rig):
    nid = rig["nid"]
    pending = "pending-recreate"
    rig["add_pending"](pending)
    from app import api  # the same novel owner the route authority resolves through

    api.novel_service.delete(nid)
    recreated = api.novel_service.create({"id": nid, "title": "Synthetic Canon project"})
    assert recreated["id"] == nid
    # Original authority is retired by project deletion; a recreated project
    # must be re-linked and re-granted explicitly, exactly as the admin owner
    # does. The old pending record must still not be adopted.
    scopes = api.collaboration_scope_service
    scopes.link_project("ws", nid)
    rig["grant"]("reviewer", "domain.review", nid)
    rig["grant"]("reviewer", "domain.read", nid)
    denied = _review(rig["client"], nid, pending, "token-reviewer", preview_digest="0" * 64)
    assert denied.status_code == 404
    assert denied.json()["detail"]["code"] == "CANON_NOT_FOUND"
    assert _canon_facts(rig, nid) == []
    assert not (rig["canon"].repository.backend.novels / nid / "pending_canon" / f"{pending}.json").exists()
