from __future__ import annotations

import json
import os
import pytest
from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from dotenv import load_dotenv

from app.actor_context import ActorContext, SessionContext
from app.collaboration_api import CollaborationReadService, create_collaboration_router
from app.config import Settings
from app.repositories.factory import create_repository_bundle
from app.services import ChapterService, NovelService
from app.services.context_snapshot_service import ContextSnapshotService


class Sessions:
    def resolve(self, token):
        if token != "trusted": raise KeyError(token)
        return ActorContext("alice", "w", SessionContext("session", "client", "alice", "w"))


class MembershipAuthorization:
    def require(self, actor, permission, domain, scope):
        if actor.actor_id != "alice": raise PermissionError("denied")
    def is_allowed(self, actor, permission, domain, scope):
        return permission in {"domain.read", "domain.write"}


class IdentityRepository:
    def list_memberships(self, workspace_id=None):
        return [{"id": "membership", "user_id": "alice", "workspace_id": "w", "status": "ACTIVE"}]
    def get_user(self, user_id):
        return {"id": user_id, "display_name": "Alice", "status": "ACTIVE"}


class AuthorizationRepository:
    def list_audit_events(self, scope=None):
        return [{"id": "audit", "actor_id": "alice", "action": "CHAPTER_UPDATED",
                 "target_type": "Chapter", "target_id": "novel:1", "timestamp": "2026-01-01T00:00:00+00:00",
                 "metadata": {"expected_version": 1}}]


class Scopes:
    def validate_scope(self, scope): return scope


class Chapters:
    def get(self, chapter_id):
        return {"id": chapter_id, "novel_id": chapter_id.rsplit(":", 1)[0], "version": 2}
    def history(self, chapter_id):
        return [{"version": 1, "document": {"content": [{"text": "history"}]},
                 "timestamp": "2026-01-01T00:00:00+00:00", "source": "MANUAL_SAVE", "operator": "alice"}]


class Generations:
    def get(self, generation_id):
        return {"id": generation_id, "novel_id": "project", "context_snapshot_id": "snapshot"}


def client(tmp_path, authorization=None):
    snapshot_root = tmp_path / "novels" / "project" / "lore" / "context_snapshots"
    snapshot_root.mkdir(parents=True)
    (snapshot_root / "snapshot.json").write_text(json.dumps({
        "id": "snapshot", "chapter_version_id": "project:1:v1", "context_pack_hash": "hash",
        "prompt_version": "prompt", "model": "model", "context_mode": "V2", "generation_id": "generation",
        "created_at": "2026-01-01T00:00:00+00:00", "actor_id": "alice", "session_id": "session",
        "scope_type": "BRANCH", "scope_id": "branch", "ordering": ["safe-id"], "budget": {"used_tokens": 10},
        "context": {"secret": "must never be returned", "privacy": "LOCAL_ONLY"},
    }), encoding="utf-8")
    service = CollaborationReadService(
        sessions=Sessions(), membership_authorization=authorization or MembershipAuthorization(),
        identity=SimpleNamespace(repository=IdentityRepository()),
        authorization=SimpleNamespace(repository=AuthorizationRepository()), scopes=Scopes(), chapters=Chapters(),
        generations=Generations(), lore_repository=SimpleNamespace(backend=SimpleNamespace(novels=tmp_path / "novels")),
    )
    app = FastAPI(); app.include_router(create_collaboration_router(service)); return TestClient(app)


BASE = "/api/collaboration/workspaces/w/projects/project/storylines/story/branches/branch"
HEADERS = {"X-Session-Token": "trusted"}


def test_bootstrap_members_permissions_audit_and_revision_contracts(tmp_path):
    api = client(tmp_path)
    bootstrap = api.get(f"{BASE}/bootstrap", headers=HEADERS)
    assert bootstrap.status_code == 200
    assert bootstrap.json()["actor"] == {"actor_id": "alice", "session_id": "session", "client_id": "client"}
    assert bootstrap.json()["capabilities"]["domain.read"] is True
    assert api.get(f"{BASE}/members", headers=HEADERS).json()["items"][0]["display_name"] == "Alice"
    assert api.get(f"{BASE}/permissions", headers=HEADERS).json()["capabilities"]["proposal.review"] is False
    assert api.get(f"{BASE}/audit?action=CHAPTER_UPDATED&limit=1", headers=HEADERS).json()["total"] == 1
    revisions = api.get(f"{BASE}/chapters/project:1/revisions", headers=HEADERS).json()
    assert revisions["current_version"] == 2 and "document" not in revisions["items"][0]
    assert api.get(f"{BASE}/chapters/project:1/revisions/1", headers=HEADERS).json()["document"]


def test_snapshot_default_detail_is_metadata_only_and_generation_link_is_visible(tmp_path):
    api = client(tmp_path)
    listing = api.get(f"{BASE}/chapters/project:1/snapshots", headers=HEADERS)
    detail = api.get(f"{BASE}/chapters/project:1/snapshots/snapshot", headers=HEADERS)
    assert listing.status_code == detail.status_code == 200
    encoded = json.dumps(detail.json()).casefold()
    assert "context" not in detail.json()
    assert "must never be returned" not in encoded and "local_only" not in encoded
    link = api.get(f"{BASE}/generations/generation/snapshot", headers=HEADERS)
    assert link.json() == {"generation_id": "generation", "context_snapshot_id": "snapshot"}


def test_every_endpoint_requires_trusted_session_and_explicit_scope(tmp_path):
    api = client(tmp_path)
    assert api.get(f"{BASE}/bootstrap").status_code == 401
    assert api.get(f"{BASE}/bootstrap", headers={"X-Session-Token": "forged"}).status_code == 401
    assert api.get(f"{BASE}/chapters/other:1/revisions", headers=HEADERS).status_code == 403


@pytest.mark.postgres_backend_only
def test_real_postgres_snapshot_metadata_and_generation_link_are_api_visible():
    load_dotenv()
    url = os.getenv("TEST_POSTGRES_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not url:
        raise AssertionError("real PostgreSQL is required for V0.5.7 contract verification")
    bundle = create_repository_bundle(Settings(storage_backend="postgres", database_url=url))
    novels, chapters = NovelService(bundle.novels, bundle.chapters), ChapterService(bundle.chapters)
    novel_id = novels.create({"title": f"V057 contract {uuid4()}"})["id"]
    chapter_id = chapters.create(novel_id, {"title": "One", "content": "body"})["id"]
    snapshot = ContextSnapshotService(bundle.lore).create(
        chapter_id, 1, {"canon": [], "private_payload": "not returned"}, "prompt", "model",
        session_id="session", scope_type="BRANCH", scope_id="branch",
    )
    generation_id = str(uuid4())
    bundle.generations.save({"id": generation_id, "novel_id": novel_id, "chapter_id": chapter_id,
                             "operation": "continue", "status": "COMPLETED", "context_snapshot_id": snapshot["id"]})
    service = CollaborationReadService(
        sessions=Sessions(), membership_authorization=MembershipAuthorization(),
        identity=SimpleNamespace(repository=IdentityRepository()),
        authorization=SimpleNamespace(repository=AuthorizationRepository()), scopes=Scopes(),
        chapters=bundle.chapters, generations=bundle.generations, lore_repository=bundle.lore,
    )
    app = FastAPI(); app.include_router(create_collaboration_router(service)); api = TestClient(app)
    base = f"/api/collaboration/workspaces/w/projects/{novel_id}/storylines/story/branches/branch"
    try:
        detail = api.get(f"{base}/chapters/{chapter_id}/snapshots/{snapshot['id']}", headers=HEADERS)
        assert detail.status_code == 200
        assert detail.json()["context_pack_hash"] == snapshot["context_pack_hash"]
        assert "private_payload" not in json.dumps(detail.json())
        link = api.get(f"{base}/generations/{generation_id}/snapshot", headers=HEADERS)
        assert link.json()["context_snapshot_id"] == snapshot["id"]
    finally:
        novels.delete(novel_id)
