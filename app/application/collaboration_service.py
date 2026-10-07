from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from ..actor_context import ActorContext
from ..authorization import AuthorizationScope, ModalityDomain
from ..repositories.chapter_repository import VersionConflict
from .audit_service import AuditService


class AtomicChapterAuditPort(Protocol):
    """Persistence boundary: CAS mutation and success audit commit together or not at all."""

    def save_chapter_with_audit(
        self, chapter_id: str, document: dict[str, Any], expected_version: int,
        source: str, operator: str, audit_event: dict[str, Any],
    ) -> dict[str, Any]: ...

    def create_chapter_with_audit(
        self, project_id: str, title: str, operator: str, audit_event_factory,
    ) -> dict[str, Any]: ...
    def set_chapter_archived_with_audit(self, chapter_id: str, expected_version: int, archived: bool, audit_event: dict[str, Any]) -> dict[str, Any]: ...


@dataclass(frozen=True, slots=True)
class ConflictResponse:
    status_code: int
    body: dict[str, Any]


def version_conflict_response(error: VersionConflict) -> ConflictResponse:
    """Transport-neutral, content-free contract for Root's HTTP 409 integration."""
    return ConflictResponse(status_code=409, body={"error": error.as_dict()})


class CollaborationApplicationService:
    """Membership- and permission-aware boundary for collaborative chapter writes."""

    def __init__(self, membership_authorization, atomic_updates: AtomicChapterAuditPort, audit: AuditService):
        self.authorization = membership_authorization
        self.atomic_updates = atomic_updates
        self.audit = audit

    def _branch_context(self, actor, scope, chapter_id=None):
        owner = getattr(self, "branch_manuscripts", None)
        if owner is None or not scope.branch_id: return None
        from ..experimental.flags import enabled_flags, require_flag
        from ..services.branch_manuscript_service import experimental_scope
        from ..experimental.ux import ReadContext
        def check():
            require_flag("branch_manuscript_v1")
            self.authorization.require(actor, "domain.write", ModalityDomain.NOVEL, scope)
        check()
        return owner, ReadContext(scope.project_id, experimental_scope(scope), actor.actor_id, None, scope.branch_id), check

    def create_chapter(self, *, actor: ActorContext, scope: AuthorizationScope,
                       title: str) -> dict[str, Any]:
        self.authorization.require(actor, "domain.write", ModalityDomain.NOVEL, scope)
        if not scope.project_id:
            raise ValueError("project scope is required")
        branch = self._branch_context(actor, scope)
        if branch:
            owner, ctx, check = branch
            return owner.create(ctx, {"title": title, "content": ""}, check)

        def event_for(created: dict[str, Any]) -> dict[str, Any]:
            return self.audit.build(
                actor, "CHAPTER_CREATED", "Chapter", created["id"], scope,
                {"result_version": created["version"]},
            )

        return self.atomic_updates.create_chapter_with_audit(
            scope.project_id, title, actor.actor_id, event_for,
        )

    def update_chapter(
        self,
        *, actor: ActorContext, scope: AuthorizationScope, chapter_id: str,
        document: dict[str, Any], expected_version: int, reason: str = "MANUAL_SAVE",
    ) -> dict[str, Any]:
        # This must precede construction/invocation of every mutation.
        self.authorization.require(actor, "domain.write", ModalityDomain.NOVEL, scope)
        allowed_reasons = {
            "MANUAL_SAVE", "AI_ACCEPT", "RESTORE", "CHAPTER_SWITCH", "EXPLICIT_CHECKPOINT",
        }
        if reason not in allowed_reasons:
            raise ValueError("unsupported chapter update reason")
        branch = self._branch_context(actor, scope, chapter_id)
        if branch:
            owner, ctx, check = branch
            return owner.save(ctx, chapter_id, document, expected_version, check, reason)
        success = self.audit.build(
            actor, "CHAPTER_UPDATED", "Chapter", chapter_id, scope,
            {"expected_version": expected_version, "result_version": expected_version + 1, "reason": reason},
        )
        try:
            return self.atomic_updates.save_chapter_with_audit(
                chapter_id, document, expected_version, reason, actor.actor_id, success,
            )
        except VersionConflict as error:
            # A failed CAS has no content mutation. Conflict observability is deliberately
            # independent and contains versions/ids only.
            conflict = self.audit.build(
                actor, "CHAPTER_UPDATE_CONFLICT", "Chapter", chapter_id, scope,
                {"expected_version": error.expected_version, "actual_version": error.actual_version,
                 "conflict_type": error.conflict_type, "reason": reason},
            )
            # A conflict has no mutation to roll back. Its observability event
            # is best-effort and must never mask the authoritative CAS result.
            try:
                self.audit.append(conflict)
            except Exception:
                pass
            raise

    def set_chapter_archived(self, *, actor: ActorContext, scope: AuthorizationScope,
                             chapter_id: str, expected_version: int, archived: bool) -> dict[str, Any]:
        self.authorization.require(actor, "domain.write", ModalityDomain.NOVEL, scope)
        branch = self._branch_context(actor, scope, chapter_id)
        if branch:
            owner, ctx, check = branch
            return owner.archive(ctx, chapter_id, archived, expected_version, check)
        action = "CHAPTER_ARCHIVED" if archived else "CHAPTER_RESTORED"
        event = self.audit.build(actor, action, "Chapter", chapter_id, scope, {"expected_version": expected_version})
        return self.atomic_updates.set_chapter_archived_with_audit(chapter_id, expected_version, archived, event)
