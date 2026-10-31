"""HTTP idempotency contracts with real File owners and trusted authority.

Only the job dispatcher is a controlled double: these tests count dispatches,
not model executions. Cache entries are always produced by the production route.
"""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
import hashlib
import json
from threading import Barrier, Lock, Thread
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app import api
from app.actor_context import SessionContext
from app.authorization import AuthorizationScope, DomainRole, DomainRoleAssignment, ModalityDomain, ScopeKind
from app.collaboration import Branch, Storyline, Workspace
from app.config import Settings
from app.experimental.store import ExperimentalStore
from app.idempotency import IdempotencyStore
from app.identity import IdentityStatus, User, WorkspaceMembership
from app.main import app
from app.repositories.factory import create_repository_bundle
from app.services import ChapterService, NovelService
from app.services.authorization_service import AuthorizationService
from app.services.branch_manuscript_service import BranchManuscriptService
from app.services.collaboration_scope_service import CollaborationScopeService
from app.services.identity_service import IdentityService
from app.services.membership_authorization_service import MembershipAuthorizationService
from app.trusted_sessions import TrustedSessionResolver


class CountingDispatcher:
    """Replace dispatch only, without stubbing source or authorization checks."""

    def __init__(self):
        self.calls = []
        self.prepare_calls = []
        self.prepared = []
        self.items = {}
        self.failures_remaining = 0
        self.delay = 0
        self.on_get = None
        self.on_create = None
        self.lock = Lock()

    def prepare_job(self, operation, payload, actor=None, scope=None, request_authorization=None):
        if request_authorization is not None:
            request_authorization()
        with self.lock:
            self.prepare_calls.append((operation, dict(payload), actor, scope))
            if self.failures_remaining:
                self.failures_remaining -= 1
                raise RuntimeError("controlled preparation failure")
        item = SimpleNamespace(
            id=str(uuid4()), status="PREPARED", base_chapter_version=1,
            novel_id=payload["novel_id"], chapter_id=payload["chapter_id"],
            actor_id=actor.actor_id if actor else None,
            workspace_id=actor.workspace_id if actor else None,
            scope=asdict(scope) if scope else None,
            request_authorization=request_authorization,
            dispatch_call=(operation, dict(payload), actor, scope),
        )
        self.prepared.append(item)
        return item

    def start_prepared(self, item):
        import time

        if item.request_authorization is not None:
            item.request_authorization()
        with self.lock:
            self.calls.append(item.dispatch_call)
        # Delay outside this counter lock, so it cannot supply idempotency itself.
        if self.delay:
            time.sleep(self.delay)
        item.status = "QUEUED"
        with self.lock:
            self.items[item.id] = item
        callback, self.on_create = self.on_create, None
        if callback is not None:
            callback()
        return item

    def create(self, operation, payload, actor=None, scope=None, request_authorization=None):
        return self.start_prepared(self.prepare_job(
            operation, payload, actor, scope, request_authorization))

    def get(self, job_id):
        callback, self.on_get = self.on_get, None
        if callback is not None:
            callback()
        return self.items[job_id]


def _payload(chapter):
    return {"novel_id": chapter["novel_id"], "chapter_id": chapter["id"], "instruction": "继续"}


def _rows(store):
    return json.loads(store.path.read_text()) if store.path.exists() else {}


def _cache_key(payload, key, operation="continue", actor="local-author", workspace="local", branch=None):
    authority = [payload["novel_id"], payload["chapter_id"], actor, workspace, branch]
    scope_hash = hashlib.sha256(json.dumps(authority).encode()).hexdigest()
    return f"generate:{operation}:{scope_hash}:{key}"


def _assert_cache(store, payload, key, result, **authority):
    normalized = api.GenerateIn(**payload).model_dump(exclude={"count"})
    digest = hashlib.sha256(json.dumps(normalized, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    marker = json.loads((store.path.parent / "novels" / payload["novel_id"] / "creative_project_v2.json").read_text())
    assert store.get(_cache_key(payload, key, **authority)) == {
        "schema_version": 2, "project_incarnation": "file:" + marker["project_incarnation"],
        "request_digest": digest, "result": result,
    }


def _post(fixture, key=None, *, payload=None, operation="continue", headers=None):
    request_headers = dict(headers or {})
    if key is not None:
        request_headers["Idempotency-Key"] = key
    return fixture.client.post(f"/api/generate/{operation}", headers=request_headers,
                               json=fixture.payload if payload is None else payload)


def _accepted(response):
    assert response.status_code == 202, response.text
    body = response.json()
    assert body == {
        "job_id": body["job_id"], "status": "QUEUED",
        "events_url": f"/api/generation/{body['job_id']}/events", "base_chapter_version": 1,
    }
    return body


@pytest.fixture
def generation(tmp_path, monkeypatch):
    import app.main as main_module

    config = Settings(storage_backend="file", novel_data=tmp_path, mock_provider=True,
                      enable_collaboration_runtime=False, enable_packaged_runtime=False)
    bundle = create_repository_bundle(config, tmp_path)
    novels = NovelService(bundle.novels, bundle.chapters)
    chapters = ChapterService(bundle.chapters)
    novel = novels.create({"id": "idempotency-book", "title": "Idempotency contracts"})
    chapter = chapters.create(novel["id"], {"title": "One", "content": "Original source"})
    dispatcher = CountingDispatcher()
    store = IdempotencyStore(tmp_path / "idempotency.json")
    monkeypatch.setattr(api, "settings", config)
    monkeypatch.setattr(main_module, "settings", config)
    monkeypatch.setattr(api, "novel_service", novels)
    monkeypatch.setattr(api, "chapter_service", chapters)
    monkeypatch.setattr(api, "jobs", dispatcher)
    monkeypatch.setattr(api, "_idempotency_store", store)
    return SimpleNamespace(
        client=TestClient(app, raise_server_exceptions=False), bundle=bundle,
        novels=novels, chapters=chapters, chapter=chapter, payload=_payload(chapter),
        dispatcher=dispatcher, store=store, root=tmp_path,
    )


@pytest.fixture
def collaboration_generation(generation, monkeypatch):
    """Use real File scope, memberships, roles, sessions and branch manuscript owner."""
    import app.main as main_module

    fixture = generation
    monkeypatch.setenv("EXPERIMENTAL_FEATURES", "branch_manuscript_v1")
    monkeypatch.delenv("V1_ACCEPTANCE_MODE", raising=False)
    scopes = CollaborationScopeService(fixture.bundle.scope, fixture.bundle.novels)
    scopes.create_workspace(Workspace("workspace", "Workspace"))
    scopes.link_project("workspace", fixture.payload["novel_id"])
    scopes.create_storyline(Storyline("story", "workspace", fixture.payload["novel_id"], "Story"))
    for branch in ("branch-a", "branch-b"):
        scopes.create_branch(Branch(branch, "workspace", fixture.payload["novel_id"], "story", branch))
    identity = IdentityService(fixture.bundle.identity, scopes)
    authorization = AuthorizationService(fixture.bundle.authorization, scopes)
    sessions = TrustedSessionResolver()
    for user in ("alice", "bob"):
        identity.create_user(User(user, user.title()))
        identity.add_membership(WorkspaceMembership(f"membership-{user}", user, "workspace"))
        sessions.register(f"opaque-{user}", SessionContext(f"session-{user}", f"client-{user}", user, "workspace"))
        for branch in ("branch-a", "branch-b"):
            scope = AuthorizationScope(ScopeKind.BRANCH, "workspace", fixture.payload["novel_id"], "story", branch)
            authorization.assign_role(DomainRoleAssignment(
                f"role-{user}-{branch}", user, DomainRole.DOMAIN_LEAD, ModalityDomain.NOVEL, scope, "fixture-admin",
            ))
    branches = BranchManuscriptService(ExperimentalStore(fixture.root, "file"),
                                       fixture.novels, fixture.chapters, scopes)
    fixture.chapters.branch_authority = branches.for_scope
    fixture.novels.branch_authority = branches.for_scope
    branch_scopes = {
        branch: AuthorizationScope(ScopeKind.BRANCH, "workspace", fixture.payload["novel_id"], "story", branch)
        for branch in ("branch-a", "branch-b")
    }
    branch_chapters = {
        branch: branches.for_scope(scope).create(fixture.payload["novel_id"], {"title": branch, "content": f"Source {branch}"})
        for branch, scope in branch_scopes.items()
    }
    config = Settings(storage_backend="file", novel_data=fixture.root, mock_provider=True,
                      enable_collaboration_runtime=True, enable_packaged_runtime=False)
    monkeypatch.setattr(api, "settings", config)
    monkeypatch.setattr(main_module, "settings", config)
    monkeypatch.setattr(api, "trusted_session_resolver", sessions)
    monkeypatch.setattr(main_module, "trusted_session_resolver", sessions)
    monkeypatch.setattr(api, "collaboration_scope_service", scopes)
    monkeypatch.setattr(api, "membership_authorization_service", MembershipAuthorizationService(identity, authorization))
    fixture.client.headers.update({"X-Session-Token": "opaque-alice", "X-Branch-Id": "branch-a"})
    fixture.payload = _payload(branch_chapters["branch-a"])
    fixture.branch_chapters, fixture.branch_scopes = branch_chapters, branch_scopes
    fixture.branches, fixture.sessions = branches, sessions
    fixture.identity, fixture.authorization = identity, authorization
    return fixture


def test_generation_replay_returns_cached_result_without_creating(generation):
    first = _accepted(_post(generation, "replay-key"))
    _assert_cache(generation.store, generation.payload, "replay-key", first)
    assert _accepted(_post(generation, "replay-key")) == first
    assert len(generation.dispatcher.calls) == 1


def test_generation_replay_contract_is_stable_across_repeats(generation, monkeypatch):
    first = _accepted(_post(generation, "replay-stable"))
    # Reopen the actual persisted store: no fabricated preseed or in-memory replay.
    reopened = IdempotencyStore(generation.store.path)
    monkeypatch.setattr(api, "_idempotency_store", reopened)
    for _ in range(20):
        assert _accepted(_post(generation, "replay-stable")) == first
    _assert_cache(reopened, generation.payload, "replay-stable", first)
    assert len(generation.dispatcher.calls) == 1


def test_generation_without_idempotency_key_creates_independently(generation):
    first = _accepted(_post(generation))
    second = _accepted(_post(generation))
    assert first["job_id"] != second["job_id"]
    assert len(generation.dispatcher.calls) == 2
    assert _rows(generation.store) == {}


def test_generation_distinct_keys_create_once_each(generation):
    first = _accepted(_post(generation, "k1"))
    second = _accepted(_post(generation, "k2"))
    assert first["job_id"] != second["job_id"]
    assert _accepted(_post(generation, "k1")) == first
    assert _accepted(_post(generation, "k2")) == second
    assert len(generation.dispatcher.calls) == 2


def test_generation_idempotency_is_namespaced_by_operation(generation):
    first = _accepted(_post(generation, "same", operation="continue"))
    second = _accepted(_post(generation, "same", operation="rewrite"))
    assert first["job_id"] != second["job_id"]
    assert _accepted(_post(generation, "same", operation="continue")) == first
    assert _accepted(_post(generation, "same", operation="rewrite")) == second
    assert [call[0] for call in generation.dispatcher.calls] == ["continue", "rewrite"]
    _assert_cache(generation.store, generation.payload, "same", first)
    _assert_cache(generation.store, generation.payload, "same", second, operation="rewrite")


def test_generation_prepare_failure_is_not_cached_and_releases_lock(generation):
    generation.dispatcher.failures_remaining = 1
    failed = _post(generation, "err-key")
    assert failed.status_code == 500
    assert "job_id" not in failed.text
    assert generation.dispatcher.items == {}
    assert _rows(generation.store) == {}
    box = {}

    def retry():
        box["response"] = _post(generation, "err-key")

    worker = Thread(target=retry, daemon=True)
    worker.start()
    worker.join(5)
    assert not worker.is_alive(), "Failed dispatch stranded the idempotency lock"
    second = _accepted(box["response"])
    assert second["job_id"] == generation.dispatcher.prepared[-1].id
    assert _accepted(_post(generation, "err-key")) == second
    _assert_cache(generation.store, generation.payload, "err-key", second)
    assert len(generation.dispatcher.prepare_calls) == 2
    assert len(generation.dispatcher.calls) == 1
    assert set(generation.dispatcher.items) == {second["job_id"]}


def test_generation_fresh_store_concurrent_submission_survives_repeated_races(generation, monkeypatch):
    generation.dispatcher.delay = 0.005
    for round_id in range(100):
        store = IdempotencyStore(generation.root / f"round-{round_id}.json")
        monkeypatch.setattr(api, "_idempotency_store", store)
        start = Barrier(3)
        before = len(generation.dispatcher.calls)

        def submit(_):
            start.wait(timeout=5)
            return _accepted(_post(generation, f"fresh-{round_id}"))

        with ThreadPoolExecutor(max_workers=3) as pool:
            bodies = list(pool.map(submit, range(3)))
        assert all(body == bodies[0] for body in bodies)
        assert len(generation.dispatcher.calls) == before + 1
        _assert_cache(store, generation.payload, f"fresh-{round_id}", bodies[0])


def test_generation_same_key_changed_payload_is_rejected_without_overwriting_cache(generation):
    first = _accepted(_post(generation, "immutable-request"))
    before = generation.store.path.read_bytes()
    conflict = _post(generation, "immutable-request", payload={**generation.payload, "instruction": "改写"})
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "IDEMPOTENCY_REQUEST_MISMATCH"
    assert "job_id" not in conflict.json()
    assert generation.store.path.read_bytes() == before
    assert _accepted(_post(generation, "immutable-request")) == first
    assert len(generation.dispatcher.calls) == 1


def test_generation_same_key_is_isolated_between_real_projects(generation):
    first = _accepted(_post(generation, "same-project-key"))
    other = generation.novels.create({"id": "other-book", "title": "Other"})
    chapter = generation.chapters.create(other["id"], {"title": "Other chapter", "content": "Other source"})
    payload = _payload(chapter)
    second = _accepted(_post(generation, "same-project-key", payload=payload))
    assert first["job_id"] != second["job_id"]
    assert _accepted(_post(generation, "same-project-key")) == first
    assert _accepted(_post(generation, "same-project-key", payload=payload)) == second
    _assert_cache(generation.store, generation.payload, "same-project-key", first)
    _assert_cache(generation.store, payload, "same-project-key", second)
    assert len(generation.dispatcher.calls) == 2


def test_generation_same_key_is_isolated_by_trusted_actor_and_branch(collaboration_generation):
    fixture = collaboration_generation
    first = _accepted(_post(fixture, "same"))
    bob_headers = {"X-Session-Token": "opaque-bob"}
    second = _accepted(_post(fixture, "same", headers=bob_headers))
    branch_b_payload = _payload(fixture.branch_chapters["branch-b"])
    third = _accepted(_post(fixture, "same", payload=branch_b_payload, headers={"X-Branch-Id": "branch-b"}))
    assert len({first["job_id"], second["job_id"], third["job_id"]}) == 3
    assert _accepted(_post(fixture, "same")) == first
    assert _accepted(_post(fixture, "same", headers=bob_headers)) == second
    assert _accepted(_post(fixture, "same", payload=branch_b_payload, headers={"X-Branch-Id": "branch-b"})) == third
    for payload, actor, branch, result in ((fixture.payload, "alice", "branch-a", first),
                                          (fixture.payload, "bob", "branch-a", second),
                                          (branch_b_payload, "alice", "branch-b", third)):
        _assert_cache(fixture.store, payload, "same", result, actor=actor, workspace="workspace", branch=branch)
    assert [(call[2].actor_id, call[3].branch_id) for call in fixture.dispatcher.calls] == [
        ("alice", "branch-a"), ("bob", "branch-a"), ("alice", "branch-b"),
    ]
    # A different valid scope cannot resolve the old branch's source or cache.
    denied = _post(fixture, "same", headers={"X-Branch-Id": "branch-b"})
    assert denied.status_code == 404
    assert denied.json()["code"] == "CHAPTER_NOT_FOUND"
    assert len(fixture.dispatcher.calls) == 3


@pytest.mark.parametrize(("revocation", "status", "code"), [
    ("membership", 403, "FORBIDDEN"),
    ("role", 403, "FORBIDDEN"),
    ("session", 401, "INVALID_SESSION"),
    ("source", 404, "CHAPTER_NOT_FOUND"),
    ("feature", 404, "EXPERIMENTAL_FEATURE_DISABLED"),
])
def test_generation_cached_result_rechecks_current_authority_and_source(collaboration_generation, monkeypatch, revocation, status, code):
    fixture = collaboration_generation
    first = _accepted(_post(fixture, "revoke-after-cache"))
    assert _accepted(_post(fixture, "revoke-after-cache")) == first
    before = fixture.store.path.read_bytes()
    if revocation == "membership":
        fixture.identity.set_membership_status("alice", "workspace", IdentityStatus.INACTIVE)
    elif revocation == "role":
        fixture.authorization.revoke_role("role-alice-branch-a", "fixture-admin")
    elif revocation == "session":
        fixture.sessions.revoke("opaque-alice")
    elif revocation == "source":
        repository = fixture.branches.repository(fixture.branch_scopes["branch-a"])
        archived = repository.set_archived(fixture.payload["chapter_id"], True, 1, "alice")
        repository.delete(fixture.payload["chapter_id"], archived["version"], "alice")
    else:
        monkeypatch.setenv("EXPERIMENTAL_FEATURES", "")
    denied = _post(fixture, "revoke-after-cache")
    assert denied.status_code == status, denied.text
    assert denied.json()["detail"]["code"] == code
    assert "job_id" not in denied.json()
    assert first["job_id"] not in denied.text
    assert len(fixture.dispatcher.calls) == 1
    assert fixture.store.path.read_bytes() == before


@pytest.mark.parametrize("revocation", ["membership", "role"])
def test_generation_cached_replay_rechecks_revocation_after_request_validation(collaboration_generation, revocation):
    fixture = collaboration_generation
    first = _accepted(_post(fixture, "revoke-during-replay"))
    before = fixture.store.path.read_bytes()

    def revoke():
        if revocation == "membership":
            fixture.identity.set_membership_status("alice", "workspace", IdentityStatus.INACTIVE)
        else:
            fixture.authorization.revoke_role("role-alice-branch-a", "fixture-admin")

    # This is inside the allowed dispatcher double. Source lookup, the cache
    # lock and both authorization boundaries remain production implementations.
    fixture.dispatcher.on_get = revoke
    denied = _post(fixture, "revoke-during-replay")
    assert denied.status_code == 403
    assert denied.json()["detail"]["code"] == "FORBIDDEN"
    assert "job_id" not in denied.json()
    assert first["job_id"] not in denied.text
    assert len(fixture.dispatcher.calls) == 1
    assert fixture.store.path.read_bytes() == before


def test_generation_cached_result_does_not_survive_local_source_deletion(generation):
    first = _accepted(_post(generation, "deleted-source"))
    generation.chapters.delete(generation.payload["chapter_id"])
    denied = _post(generation, "deleted-source")
    assert denied.status_code == 404
    assert "job_id" not in denied.json()
    assert first["job_id"] not in denied.text
    assert len(generation.dispatcher.calls) == 1


def test_generation_request_cannot_use_another_projects_chapter(generation):
    _accepted(_post(generation, "project-owner"))
    other = generation.novels.create({"id": "wrong-owner", "title": "Wrong owner"})
    denied = _post(generation, "project-owner", payload={**generation.payload, "novel_id": other["id"]})
    assert denied.status_code == 404
    assert denied.json()["code"] == "CHAPTER_OUTSIDE_PROJECT"
    assert len(generation.dispatcher.calls) == 1


def test_generation_cached_result_rejects_recreated_project_incarnation(generation):
    first = _accepted(_post(generation, "recreated-project"))
    before = generation.store.path.read_bytes()
    project_id = generation.payload["novel_id"]
    assert generation.client.delete(f"/api/novels/{project_id}").status_code == 204
    created = generation.client.post("/api/novels", json={"id": project_id, "title": "New owner"})
    assert created.status_code == 201
    chapter = generation.client.post(f"/api/novels/{project_id}/chapters",
                                     json={"title": "New chapter", "content": "New owner's source"})
    assert chapter.status_code == 201
    payload = _payload(chapter.json())
    assert payload == generation.payload, "Exercise the legitimate whole-project ID reuse path"
    denied = _post(generation, "recreated-project", payload=payload)
    assert denied.status_code == 409
    assert denied.json()["code"] == "IDEMPOTENCY_OWNER_CHANGED"
    assert first["job_id"] not in denied.text
    assert len(generation.dispatcher.calls) == 1
    assert generation.store.path.read_bytes() == before


def test_generation_cached_result_rechecks_source_deleted_during_replay(collaboration_generation):
    fixture = collaboration_generation
    first = _accepted(_post(fixture, "source-deleted-during-replay"))
    before = fixture.store.path.read_bytes()

    def delete_source():
        repository = fixture.branches.repository(fixture.branch_scopes["branch-a"])
        archived = repository.set_archived(fixture.payload["chapter_id"], True, 1, "alice")
        repository.delete(fixture.payload["chapter_id"], archived["version"], "alice")

    fixture.dispatcher.on_get = delete_source
    denied = _post(fixture, "source-deleted-during-replay")
    assert denied.status_code == 404
    assert denied.json()["code"] == "CHAPTER_NOT_FOUND"
    assert first["job_id"] not in denied.text
    assert len(fixture.dispatcher.calls) == 1
    assert fixture.store.path.read_bytes() == before


@pytest.mark.parametrize("legacy_kind", ["scoped", "unscoped", "expired-scoped", "expired-unscoped", "invalid-result"])
def test_generation_retained_legacy_receipt_never_becomes_an_automatic_miss(generation, legacy_kind):
    from datetime import datetime, timedelta, timezone

    first = _accepted(_post(generation, "legacy-request"))
    current_key = _cache_key(generation.payload, "legacy-request")
    rows = _rows(generation.store)
    row = rows[current_key]
    if "expired" in legacy_kind:
        row["created_at"] = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
    if legacy_kind == "invalid-result":
        row["value"]["result"] = {"job_id": "incomplete"}
    else:
        row["value"] = {"request_digest": row["value"]["request_digest"], "result": first}
        if "unscoped" in legacy_kind:
            row["value"] = first
            rows = {"generate:continue:legacy-request": row}
    generation.store.path.write_text(json.dumps(rows))
    marker = generation.root / "novels" / generation.payload["novel_id"] / "creative_project_v2.json"
    marker.unlink()
    before = generation.store.path.read_bytes()
    denied = _post(generation, "legacy-request")
    assert denied.status_code == 409
    assert denied.json()["code"] == "IDEMPOTENCY_RECORD_UNVERIFIED"
    assert len(generation.dispatcher.calls) == 1
    assert generation.store.path.read_bytes() == before
    assert not marker.exists(), "Legacy replay must not provision a replacement identity"


def test_generation_expired_bound_receipt_requires_an_explicit_new_key(generation):
    from datetime import datetime, timedelta, timezone

    _accepted(_post(generation, "expired-request"))
    rows = _rows(generation.store)
    rows[_cache_key(generation.payload, "expired-request")]["created_at"] = (
        datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
    generation.store.path.write_text(json.dumps(rows))
    before = generation.store.path.read_bytes()
    denied = _post(generation, "expired-request")
    assert denied.status_code == 409
    assert denied.json()["code"] == "IDEMPOTENCY_KEY_EXPIRED"
    assert len(generation.dispatcher.calls) == 1
    assert generation.store.path.read_bytes() == before
    _accepted(_post(generation, "explicit-new-request"))
    assert len(generation.dispatcher.calls) == 2
    assert _rows(generation.store)[_cache_key(generation.payload, "expired-request")] == rows[_cache_key(generation.payload, "expired-request")]


@pytest.mark.parametrize("marker_state", ["missing", "corrupt"])
def test_generation_replay_never_replaces_missing_or_corrupt_owner_marker(generation, marker_state):
    _accepted(_post(generation, "owner-marker"))
    marker = generation.root / "novels" / generation.payload["novel_id"] / "creative_project_v2.json"
    if marker_state == "missing":
        marker.unlink()
    else:
        marker.write_text('{"schema_version": 1, "project_incarnation": "invalid"}')
    before_marker = marker.read_bytes() if marker.exists() else None
    before_cache = generation.store.path.read_bytes()
    denied = _post(generation, "owner-marker")
    assert denied.status_code == 409
    assert denied.json()["code"] == "IDEMPOTENCY_OWNER_CHANGED"
    assert str(generation.root) not in denied.text
    assert (marker.read_bytes() if marker.exists() else None) == before_marker
    assert generation.store.path.read_bytes() == before_cache
    assert len(generation.dispatcher.calls) == 1


@pytest.mark.parametrize("corrupt", ['{broken json', '[]', '{"unused": 1, "generate:continue:broken": null}'])
def test_generation_corrupt_retained_cache_fails_closed_without_overwriting(generation, corrupt):
    generation.store.path.write_text(corrupt)
    before = generation.store.path.read_bytes()
    denied = _post(generation, "broken")
    assert denied.status_code == 409
    assert denied.json()["code"] == "IDEMPOTENCY_RECORD_UNVERIFIED"
    assert generation.dispatcher.calls == []
    assert generation.store.path.read_bytes() == before


def test_generation_keyed_request_rejects_different_repository_roots(generation, monkeypatch):
    other_root = generation.root / "different-owner"
    bundle = create_repository_bundle(Settings(storage_backend="file", novel_data=other_root), other_root)
    novels = NovelService(bundle.novels, bundle.chapters)
    chapters = ChapterService(bundle.chapters)
    novels.create({"id": generation.payload["novel_id"], "title": "Different File owner"})
    created = chapters.create(generation.payload["novel_id"], {"title": "One", "content": "Different owner"})
    assert created["id"] == generation.payload["chapter_id"]
    monkeypatch.setattr(api, "chapter_service", chapters)
    denied = _post(generation, "wrong-root")
    assert denied.status_code == 409
    assert denied.json()["code"] == "IDEMPOTENCY_OWNER_UNVERIFIED"
    assert str(generation.root) not in denied.text
    assert generation.dispatcher.calls == []
    assert _rows(generation.store) == {}
    assert not list(generation.root.rglob("creative_project_v2.json"))


def test_generation_authority_rejects_registered_branch_store_from_another_root(collaboration_generation):
    from app.services.generation_idempotency_authority import GenerationIdempotencyAuthority, GenerationOwnerUnverified

    fixture = collaboration_generation
    fixture.branches.store = ExperimentalStore(fixture.root / "wrong-root", "file")
    with pytest.raises(GenerationOwnerUnverified, match="generation branch root differs"):
        GenerationIdempotencyAuthority(fixture.novels, fixture.chapters)
    assert fixture.dispatcher.calls == []


@pytest.mark.parametrize("change", ["source", "project"])
def test_generation_successful_dispatch_retains_receipt_if_final_source_or_owner_check_fails(collaboration_generation, change):
    # Both branch source retirement and its parent project retirement must
    # retain an already-produced dispatch receipt without returning success.
    fixture = collaboration_generation
    if change == "source":
        def mutate():
            repository = fixture.branches.repository(fixture.branch_scopes["branch-a"])
            archived = repository.set_archived(fixture.payload["chapter_id"], True, 1, "alice")
            repository.delete(fixture.payload["chapter_id"], archived["version"], "alice")
        expected_status, expected_code = 404, "CHAPTER_NOT_FOUND"
    else:
        # The branch's project retirement removes its scope. This must reject
        # after dispatch but retain the original owner's dispatch receipt.
        def mutate():
            fixture.novels.delete(fixture.payload["novel_id"])
            fixture.novels.create({"id": fixture.payload["novel_id"], "title": "Recreated project"})
        expected_status, expected_code = 401, "INVALID_SESSION"
    fixture.dispatcher.on_create = mutate
    denied = _post(fixture, "late-rejection")
    assert denied.status_code == expected_status, denied.text
    assert denied.json()["detail"]["code"] == expected_code
    assert "job_id" not in denied.json()
    assert len(fixture.dispatcher.calls) == 1
    rows = _rows(fixture.store)
    assert len(rows) == 1
    receipt = next(iter(rows.values()))["value"]
    assert receipt["schema_version"] == 2
    assert receipt["project_incarnation"].startswith("file:")
    assert receipt["result"]["job_id"] == fixture.dispatcher.prepared[0].id
    before = fixture.store.path.read_bytes()
    assert _post(fixture, "late-rejection").status_code == expected_status
    assert len(fixture.dispatcher.calls) == 1
    assert fixture.store.path.read_bytes() == before


@pytest.mark.parametrize("moment", ["before", "during"])
def test_generation_keyed_replay_rejects_archived_branch_source(collaboration_generation, moment):
    fixture = collaboration_generation
    _accepted(_post(fixture, "archived-source"))

    def archive():
        fixture.branches.repository(fixture.branch_scopes["branch-a"]).set_archived(
            fixture.payload["chapter_id"], True, 1, "alice")

    if moment == "before":
        archive()
    else:
        fixture.dispatcher.on_get = archive
    denied = _post(fixture, "archived-source")
    assert denied.status_code == 404
    assert denied.json()["code"] == "CHAPTER_NOT_FOUND"
    assert len(fixture.dispatcher.calls) == 1


def test_generation_keyed_replay_rechecks_feature_disabled_during_lookup(collaboration_generation, monkeypatch):
    fixture = collaboration_generation
    _accepted(_post(fixture, "feature-during-replay"))
    fixture.dispatcher.on_get = lambda: monkeypatch.setenv("EXPERIMENTAL_FEATURES", "")
    denied = _post(fixture, "feature-during-replay")
    assert denied.status_code == 404
    assert denied.json()["code"] == "EXPERIMENTAL_FEATURE_DISABLED"
    assert len(fixture.dispatcher.calls) == 1


def test_generation_without_key_and_variants_do_not_create_idempotency_owner_marker(generation):
    _accepted(_post(generation))
    variants = generation.client.post("/api/generate/continue/variants", json={**generation.payload, "count": 3})
    assert variants.status_code == 202, variants.text
    assert len(variants.json()["variants"]) == 3
    assert len(generation.dispatcher.calls) == 4
    assert _rows(generation.store) == {}
    assert not (generation.root / "novels" / generation.payload["novel_id"] / "creative_project_v2.json").exists()


def test_idempotency_non_generation_get_keeps_its_original_ttl_contract(tmp_path):
    from datetime import datetime, timedelta, timezone

    store = IdempotencyStore(tmp_path / "ordinary-idempotency.json")
    store.put("other-operation", {"answer": "old"})
    rows = _rows(store)
    rows["other-operation"]["created_at"] = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
    store.path.write_text(json.dumps(rows))
    assert store.retained("other-operation") == rows["other-operation"]
    assert store.get("other-operation") is None
    assert _rows(store) == {}


@pytest.mark.parametrize("failure", [None, "query", "body"])
def test_generation_postgres_owner_adapter_uses_original_engine_protocol_without_connecting_to_postgres(failure):
    """Protocol-only test: a real PostgreSQL service is deliberately NOT RUN."""
    from contextlib import contextmanager
    from app.creative.project_store import CreativeProjectStore
    from app.services.generation_idempotency_authority import _DatabaseOwnerAdapter

    calls = []
    owner_uuid = "12345678-1234-4234-8234-123456789abc"

    class Connection:
        @contextmanager
        def begin(self):
            calls.append("begin")
            try:
                yield
            except Exception:
                calls.append("rollback")
                raise
            else:
                calls.append("commit")

        def exec_driver_sql(self, sql, parameters):
            calls.append((sql, parameters))
            if failure == "query":
                raise RuntimeError("controlled driver failure")
            return SimpleNamespace(fetchone=lambda: (owner_uuid,))

    connection = Connection()

    class Engine:
        @contextmanager
        def connect(self):
            calls.append("connect")
            try:
                yield connection
            finally:
                calls.append("close")

    engine = Engine()
    adapter = _DatabaseOwnerAdapter(SimpleNamespace(engine=engine))
    assert adapter.database.engine is engine
    owner = CreativeProjectStore(adapter)

    def read():
        with owner.owner_lease("actual-project") as incarnation:
            assert incarnation == "postgres:" + owner_uuid
            if failure == "body":
                raise RuntimeError("controlled caller failure")

    if failure is None:
        read()
    else:
        with pytest.raises(RuntimeError, match="controlled"):
            read()
    assert calls == ["connect", "begin", ("SELECT id FROM novels WHERE slug = %s FOR KEY SHARE", ("actual-project",)),
                     "commit" if failure is None else "rollback", "close"]


def test_generation_late_local_project_recreation_keeps_original_receipt_and_requires_new_key(generation):
    project_id = generation.payload["novel_id"]

    def recreate():
        generation.novels.delete(project_id)
        generation.novels.create({"id": project_id, "title": "Replacement owner"})
        chapter = generation.chapters.create(project_id, {"title": "Replacement", "content": "Replacement source"})
        assert chapter["id"] == generation.payload["chapter_id"]

    generation.dispatcher.on_create = recreate
    denied = _post(generation, "late-local-owner")
    assert denied.status_code == 409
    assert denied.json()["code"] == "IDEMPOTENCY_OWNER_CHANGED"
    assert len(generation.dispatcher.calls) == 1
    key = _cache_key(generation.payload, "late-local-owner")
    old_receipt = _rows(generation.store)[key]
    assert old_receipt["value"]["result"]["job_id"] == generation.dispatcher.prepared[0].id
    assert _post(generation, "late-local-owner").status_code == 409
    assert len(generation.dispatcher.calls) == 1
    second = _accepted(_post(generation, "explicit-new-owner-request"))
    assert second["job_id"] == generation.dispatcher.prepared[-1].id
    assert _rows(generation.store)[key] == old_receipt
    new_receipt = _rows(generation.store)[_cache_key(generation.payload, "explicit-new-owner-request")]
    assert new_receipt["value"]["project_incarnation"] != old_receipt["value"]["project_incarnation"]


def test_generation_owner_uses_actual_repository_not_decoy_settings_root(generation, monkeypatch):
    from dataclasses import replace

    decoy = generation.root / "settings-decoy"
    monkeypatch.setattr(api, "settings", replace(api.settings, novel_data=decoy))
    _accepted(_post(generation, "actual-owner"))
    marker = generation.root / "novels" / generation.payload["novel_id"] / "creative_project_v2.json"
    assert marker.is_file()
    assert not decoy.exists()
    assert len(generation.dispatcher.calls) == 1


@pytest.mark.parametrize("configuration", [
    "matching-driver", "database", "host", "port", "query", "user",
    "chapter-database", "branch-novels-database", "branch-mainline-database",
])
def test_generation_postgres_owner_binding_configuration_without_a_database_connection(configuration):
    """Offline configuration contract only; real PostgreSQL remains NOT RUN."""
    from sqlalchemy.engine import make_url
    from app.repositories.postgres.session import Database
    from app.services.generation_idempotency_authority import GenerationIdempotencyAuthority, GenerationOwnerUnverified

    actual_url = make_url("postgresql+psycopg://fixture@db.invalid:5432/original?application_name=contracts")
    database = Database.__new__(Database)
    database.engine = SimpleNamespace(url=actual_url)  # No connect method: no connection can be made.
    other_database = Database.__new__(Database)
    other_database.engine = SimpleNamespace(url=actual_url)
    novels = SimpleNamespace(novels=SimpleNamespace(database=database))
    chapters = SimpleNamespace(repository=SimpleNamespace(database=database))
    branch_url = actual_url.set(drivername="postgresql")
    changes = {
        "database": {"database": "different"}, "host": {"host": "different.invalid"},
        "port": {"port": 6543}, "query": {"query": {"application_name": "different"}},
        "user": {"username": "different"},
    }
    if configuration in changes:
        branch_url = branch_url.set(**changes[configuration])

    class BranchOwner:
        def __init__(self):
            self.store = SimpleNamespace(backend="postgres", database_url=str(branch_url))
            self.novels, self.mainline = novels, chapters

        def for_scope(self, scope):
            raise AssertionError("Binding validation must not read a source or connect")

    branch = BranchOwner()
    chapters.branch_authority = branch.for_scope
    if configuration == "chapter-database":
        chapters.repository = SimpleNamespace(database=other_database)
    elif configuration == "branch-novels-database":
        branch.novels = SimpleNamespace(novels=SimpleNamespace(database=other_database))
    elif configuration == "branch-mainline-database":
        branch.mainline = SimpleNamespace(repository=SimpleNamespace(database=other_database))
    if configuration == "matching-driver":
        authority = GenerationIdempotencyAuthority(novels, chapters)
        assert authority.database is database
        assert authority.owner.store.database.engine is database.engine
    else:
        with pytest.raises(GenerationOwnerUnverified):
            GenerationIdempotencyAuthority(novels, chapters)
