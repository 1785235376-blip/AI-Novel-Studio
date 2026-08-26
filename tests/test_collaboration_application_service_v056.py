from __future__ import annotations

import json

import pytest

from app.actor_context import ActorContext, SessionContext
from app.application.audit_service import AuditService
from app.application.collaboration_service import CollaborationApplicationService, version_conflict_response
from app.authorization import AuthorizationScope, ScopeKind
from app.repositories.chapter_repository import VersionConflict


def actor():
    session = SessionContext("session-a", "client-a", "user-a", "workspace-a", "corr-a")
    return ActorContext("user-a", "workspace-a", session)


def scope():
    return AuthorizationScope(ScopeKind.BRANCH, "workspace-a", "project-a", "story-a", "branch-a")


class Authorization:
    def __init__(self, allowed=True, calls=None): self.allowed, self.calls = allowed, calls if calls is not None else []
    def require(self, actor_value, permission, domain, scope_value):
        self.calls.append(("authorize", actor_value.actor_id, permission, scope_value.branch_id))
        if not self.allowed: raise PermissionError("denied")


class AuditRepository:
    def __init__(self, calls): self.calls, self.events = calls, []
    def append_audit_event(self, event): self.calls.append(("append", event["action"])); self.events.append(event); return event


class AtomicUpdates:
    def __init__(self, calls, conflict=False): self.calls, self.conflict = calls, conflict
    def save_chapter_with_audit(self, chapter_id, document, expected_version, source, operator, audit_event):
        self.calls.append(("atomic", chapter_id, expected_version, audit_event))
        if self.conflict:
            raise VersionConflict({"id": chapter_id, "version": 8, "document": {"secret": "latest"}}, resource_id=chapter_id, expected_version=expected_version)
        return {"id": chapter_id, "version": expected_version + 1}


def service(allowed=True, conflict=False):
    calls = []
    repository = AuditRepository(calls)
    return CollaborationApplicationService(Authorization(allowed, calls), AtomicUpdates(calls, conflict), AuditService(repository)), calls, repository


def test_authorization_precedes_atomic_mutation_and_actor_scope_propagate():
    target, calls, _ = service()
    result = target.update_chapter(actor=actor(), scope=scope(), chapter_id="novel:1", document={"content": ["private"]}, expected_version=4)
    assert result["version"] == 5
    assert [call[0] for call in calls] == ["authorize", "atomic"]
    event = calls[1][3]
    assert event["actor_id"] == "user-a" and event["scope"]["branch_id"] == "branch-a"
    assert event["metadata"]["session_id"] == "session-a" and event["metadata"]["correlation_id"] == "corr-a"


def test_non_member_or_unauthorized_actor_is_rejected_before_mutation_or_audit():
    target, calls, repository = service(allowed=False)
    with pytest.raises(PermissionError):
        target.update_chapter(actor=actor(), scope=scope(), chapter_id="novel:1", document={"content": []}, expected_version=1)
    assert [call[0] for call in calls] == ["authorize"]
    assert repository.events == []


def test_conflict_is_audited_without_document_and_maps_to_409():
    target, calls, repository = service(conflict=True)
    with pytest.raises(VersionConflict) as caught:
        target.update_chapter(actor=actor(), scope=scope(), chapter_id="novel:1", document={"prompt": "do not log"}, expected_version=7)
    response = version_conflict_response(caught.value)
    assert response.status_code == 409
    assert response.body == {"error": {"resource_id": "novel:1", "expected_version": 7, "actual_version": 8, "type": "VERSION_CONFLICT"}}
    event = repository.events[0]
    encoded = json.dumps(event).casefold()
    assert event["action"] == "CHAPTER_UPDATE_CONFLICT"
    assert all(term not in encoded for term in ("do not log", "latest", "prompt", "secret", "local_only"))


def test_success_audit_metadata_never_contains_sensitive_payload():
    target, calls, _ = service()
    target.update_chapter(actor=actor(), scope=scope(), chapter_id="novel:1", document={"content": "novel", "secret": "x"}, expected_version=2)
    encoded = json.dumps(calls[1][3]).casefold()
    assert all(term not in encoded for term in ('"content"', '"secret"', '"prompt"', '"local_only"'))


def test_admin_path_remains_version_aware():
    target, calls, _ = service()
    target.update_chapter(actor=actor(), scope=scope(), chapter_id="novel:1", document={}, expected_version=12)
    assert calls[1][2] == 12


def test_free_form_reason_cannot_be_used_to_smuggle_sensitive_text_into_audit():
    target, calls, _ = service()
    with pytest.raises(ValueError, match="unsupported chapter update reason"):
        target.update_chapter(actor=actor(), scope=scope(), chapter_id="novel:1", document={}, expected_version=1, reason="secret chapter prose")
    assert [call[0] for call in calls] == ["authorize"]
