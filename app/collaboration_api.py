from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query
from sqlalchemy import text

from .authorization import AuthorizationScope, ModalityDomain, ScopeKind
from .collaboration_contracts import (
    ActorView, AuditPage, AuditView, ChapterCreateRequest, ChapterList, ChapterSummary, ChapterView, CollaborationBootstrap, GenerationSnapshotLink,
    MemberList, MemberView, PermissionSummary, RevisionDetail, RevisionList,
    RevisionSummary, ScopeView, SnapshotDetail, SnapshotList, SnapshotSummary, StoryDatabaseView,
)
from .model_runtime import ModelRuntimeError
from .visual_workflow import VisualTextWorkflowAdapter, VisualTextWorkflowView
from .runtime_diagnostics import TextRuntimeDiagnosticsAdapter, TextRuntimeDiagnosticsView


CAPABILITIES = ("domain.read", "domain.write", "proposal.create", "proposal.review")


def _error(status: int, code: str, detail: str | None = None) -> HTTPException:
    return HTTPException(status, {"code": code, "detail": detail})


class CollaborationReadService:
    def __init__(self, *, sessions, membership_authorization, identity, authorization,
                 scopes, chapters, generations, lore_repository, novels=None, collaboration_application=None,
                 visual_workflows: VisualTextWorkflowAdapter | None = None,
                 runtime_diagnostics: TextRuntimeDiagnosticsAdapter | None = None):
        self.sessions = sessions
        self.membership_authorization = membership_authorization
        self.identity = identity
        self.authorization = authorization
        self.scopes = scopes
        self.chapters = chapters
        self.generations = generations
        self.lore_repository = lore_repository
        self.novels = novels
        self.collaboration_application = collaboration_application
        self.visual_workflows = visual_workflows
        self.runtime_diagnostics = runtime_diagnostics

    def context(self, token: str | None, workspace_id: str, project_id: str,
                storyline_id: str, branch_id: str, permission: str = "domain.read"):
        if not token:
            raise _error(401, "SESSION_REQUIRED")
        try:
            actor = self.sessions.resolve(token)
        except KeyError:
            raise _error(401, "INVALID_SESSION")
        scope = AuthorizationScope(ScopeKind.BRANCH, workspace_id, project_id, storyline_id, branch_id)
        try:
            self.scopes.validate_scope(__import__("app.collaboration", fromlist=["CollaborationScope"]).CollaborationScope(
                workspace_id, project_id, storyline_id, branch_id
            ))
            self.membership_authorization.require(actor, permission, ModalityDomain.NOVEL, scope)
        except (KeyError, ValueError):
            raise _error(404, "SCOPE_NOT_FOUND")
        except PermissionError as exc:
            raise _error(403, "FORBIDDEN", str(exc))
        return actor, scope

    def create_chapter(self, actor, scope, title: str) -> dict[str, Any]:
        if self.collaboration_application is None:
            raise _error(501, "COLLABORATION_MUTATION_NOT_CONFIGURED")
        return self.collaboration_application.create_chapter(
            actor=actor, scope=scope, title=title,
        )

    def story_database(self, project_id: str, resource: str) -> list[dict[str, Any]]:
        if self.novels is None:
            raise _error(501, "STORY_DATABASE_NOT_CONFIGURED")
        if resource == "secrets":
            return self.novels.get_public_secrets(project_id)
        return self.novels.get_data_set(project_id, resource)

    def capabilities(self, actor, scope) -> dict[str, bool]:
        return {permission: self.membership_authorization.is_allowed(
            actor, permission, ModalityDomain.NOVEL, scope
        ) for permission in CAPABILITIES}

    def snapshots(self, chapter_id: str) -> list[dict[str, Any]]:
        repository = self.lore_repository
        if hasattr(repository, "backend"):
            novel_id = chapter_id.rsplit(":", 1)[0]
            root = Path(repository.backend.novels) / novel_id / "lore" / "context_snapshots"
            return [json.loads(path.read_text(encoding="utf-8")) for path in sorted(root.glob("*.json"))]
        database = getattr(repository, "database", None)
        if database is None:
            return []
        slug, number = chapter_id.rsplit(":", 1)
        with database.session() as session:
            rows = session.execute(text(
                "SELECT s.snapshot FROM chapter_context_snapshots s "
                "JOIN chapters c ON c.id=s.chapter_id JOIN novels n ON n.id=c.novel_id "
                "WHERE n.slug=:slug AND c.chapter_number=:number ORDER BY s.created_at DESC"
            ), {"slug": slug, "number": int(number)}).all()
        return [dict(row[0]) for row in rows]

    def visual_text_workflow(self, provider_id: str, model_id: str) -> VisualTextWorkflowView:
        if self.visual_workflows is None:
            raise _error(501, "VISUAL_WORKFLOW_NOT_CONFIGURED")
        try:
            return self.visual_workflows.compose(provider_id, model_id)
        except ModelRuntimeError as exc:
            raise _error(404, exc.code.value, exc.safe_message)

    def text_runtime_diagnostics(self, provider_id: str, model_id: str) -> TextRuntimeDiagnosticsView:
        if self.runtime_diagnostics is None:
            raise _error(501, "TEXT_RUNTIME_DIAGNOSTICS_NOT_CONFIGURED")
        try:
            return self.runtime_diagnostics.diagnose(provider_id, model_id)
        except ModelRuntimeError as exc:
            raise _error(404, exc.code.value, exc.safe_message)


def create_collaboration_router(
    service: CollaborationReadService, *, prefix: str = "/api/collaboration",
) -> APIRouter:
    router = APIRouter(prefix=prefix, tags=["collaboration"])

    def authorized(token, w, p, s, b):
        return service.context(token, w, p, s, b)

    @router.get("/workspaces/{w}/projects/{p}/storylines/{s}/branches/{b}/bootstrap", response_model=CollaborationBootstrap)
    def bootstrap(w: str, p: str, s: str, b: str, x_session_token: str | None = Header(None)):
        actor, scope = authorized(x_session_token, w, p, s, b)
        return CollaborationBootstrap(actor=ActorView(actor_id=actor.actor_id, session_id=actor.session_id, client_id=actor.client_id),
            scope=ScopeView(workspace_id=w, project_id=p, storyline_id=s, branch_id=b), capabilities=service.capabilities(actor, scope))

    @router.get("/workspaces/{w}/projects/{p}/storylines/{s}/branches/{b}/visual-text-workflow", response_model=VisualTextWorkflowView)
    def visual_text_workflow(w: str, p: str, s: str, b: str, provider_id: str = Query(...), model_id: str = Query(...), x_session_token: str | None = Header(None)):
        authorized(x_session_token, w, p, s, b)
        return service.visual_text_workflow(provider_id, model_id)

    @router.get("/workspaces/{w}/projects/{p}/storylines/{s}/branches/{b}/text-runtime-diagnostics", response_model=TextRuntimeDiagnosticsView)
    def text_runtime_diagnostics(w: str, p: str, s: str, b: str, provider_id: str = Query(...), model_id: str = Query(...), x_session_token: str | None = Header(None)):
        authorized(x_session_token, w, p, s, b)
        return service.text_runtime_diagnostics(provider_id, model_id)

    @router.get("/workspaces/{w}/projects/{p}/storylines/{s}/branches/{b}/members", response_model=MemberList)
    def members(w: str, p: str, s: str, b: str, x_session_token: str | None = Header(None)):
        authorized(x_session_token, w, p, s, b)
        items = []
        for membership in service.identity.repository.list_memberships(workspace_id=w):
            user = service.identity.repository.get_user(membership["user_id"])
            items.append(MemberView(user_id=user["id"], display_name=user["display_name"],
                                    status=membership["status"], membership_id=membership["id"]))
        return MemberList(items=items)

    @router.get("/workspaces/{w}/projects/{p}/storylines/{s}/branches/{b}/permissions", response_model=PermissionSummary)
    def permissions(w: str, p: str, s: str, b: str, x_session_token: str | None = Header(None)):
        actor, scope = authorized(x_session_token, w, p, s, b)
        return PermissionSummary(actor_id=actor.actor_id, domain="NOVEL", capabilities=service.capabilities(actor, scope))

    @router.get("/workspaces/{w}/projects/{p}/storylines/{s}/branches/{b}/chapters", response_model=ChapterList)
    def chapter_list(w: str, p: str, s: str, b: str, x_session_token: str | None = Header(None)):
        authorized(x_session_token, w, p, s, b)
        return ChapterList(items=[ChapterSummary(**row) for row in service.chapters.list(p)])

    @router.post("/workspaces/{w}/projects/{p}/storylines/{s}/branches/{b}/chapters", response_model=ChapterView, status_code=201)
    def chapter_create(w: str, p: str, s: str, b: str, body: ChapterCreateRequest,
                       x_session_token: str | None = Header(None)):
        actor, scope = service.context(x_session_token, w, p, s, b, "domain.write")
        try:
            return service.create_chapter(actor, scope, body.title)
        except FileNotFoundError:
            raise _error(404, "PROJECT_NOT_FOUND")
        except FileExistsError as exc:
            raise _error(409, "CHAPTER_ALREADY_EXISTS", str(exc))

    @router.get("/workspaces/{w}/projects/{p}/storylines/{s}/branches/{b}/story-database/{resource}", response_model=StoryDatabaseView)
    def story_database(w: str, p: str, s: str, b: str, resource: str,
                       x_session_token: str | None = Header(None)):
        authorized(x_session_token, w, p, s, b)
        if resource not in {"characters", "locations", "canon", "foreshadowing", "timeline", "secrets"}:
            raise _error(404, "STORY_DATABASE_RESOURCE_NOT_FOUND")
        try:
            return StoryDatabaseView(resource=resource, items=service.story_database(p, resource))
        except (FileNotFoundError, KeyError):
            raise _error(404, "PROJECT_NOT_FOUND")

    @router.get("/workspaces/{w}/projects/{p}/storylines/{s}/branches/{b}/audit", response_model=AuditPage)
    def audit(w: str, p: str, s: str, b: str, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200),
              action: str | None = None, actor_id: str | None = None, x_session_token: str | None = Header(None)):
        _, scope = authorized(x_session_token, w, p, s, b)
        rows = service.authorization.repository.list_audit_events(scope)
        rows = [row for row in rows if (action is None or row["action"] == action) and (actor_id is None or row["actor_id"] == actor_id)]
        rows.sort(key=lambda row: (row.get("timestamp", ""), row["id"]), reverse=True)
        return AuditPage(items=[AuditView(**row) for row in rows[offset:offset + limit]], offset=offset, limit=limit, total=len(rows))

    @router.get("/workspaces/{w}/projects/{p}/storylines/{s}/branches/{b}/chapters/{chapter_id}/revisions", response_model=RevisionList)
    def revisions(w: str, p: str, s: str, b: str, chapter_id: str, x_session_token: str | None = Header(None)):
        authorized(x_session_token, w, p, s, b)
        current = service.chapters.get(chapter_id)
        if current["novel_id"] != p: raise _error(403, "RESOURCE_OUTSIDE_SCOPE")
        rows = service.chapters.history(chapter_id)
        return RevisionList(chapter_id=chapter_id, current_version=current["version"], items=[RevisionSummary(**row) for row in rows])

    @router.get("/workspaces/{w}/projects/{p}/storylines/{s}/branches/{b}/chapters/{chapter_id}/revisions/{version}", response_model=RevisionDetail)
    def revision_detail(w: str, p: str, s: str, b: str, chapter_id: str, version: int, x_session_token: str | None = Header(None)):
        authorized(x_session_token, w, p, s, b)
        current = service.chapters.get(chapter_id)
        if current["novel_id"] != p: raise _error(403, "RESOURCE_OUTSIDE_SCOPE")
        row = next((item for item in service.chapters.history(chapter_id) if item["version"] == version), None)
        if row is None: raise _error(404, "REVISION_NOT_FOUND")
        return RevisionDetail(**row)

    @router.get("/workspaces/{w}/projects/{p}/storylines/{s}/branches/{b}/chapters/{chapter_id}/snapshots", response_model=SnapshotList)
    def snapshots(w: str, p: str, s: str, b: str, chapter_id: str, x_session_token: str | None = Header(None)):
        authorized(x_session_token, w, p, s, b)
        if service.chapters.get(chapter_id)["novel_id"] != p: raise _error(403, "RESOURCE_OUTSIDE_SCOPE")
        return SnapshotList(items=[SnapshotSummary(**row) for row in service.snapshots(chapter_id)])

    @router.get("/workspaces/{w}/projects/{p}/storylines/{s}/branches/{b}/chapters/{chapter_id}/snapshots/{snapshot_id}", response_model=SnapshotDetail)
    def snapshot_detail(w: str, p: str, s: str, b: str, chapter_id: str, snapshot_id: str, x_session_token: str | None = Header(None)):
        authorized(x_session_token, w, p, s, b)
        if service.chapters.get(chapter_id)["novel_id"] != p: raise _error(403, "RESOURCE_OUTSIDE_SCOPE")
        row = next((item for item in service.snapshots(chapter_id) if item["id"] == snapshot_id), None)
        if row is None: raise _error(404, "SNAPSHOT_NOT_FOUND")
        # SnapshotDetail intentionally excludes the stored context payload.
        return SnapshotDetail(**row)

    @router.get("/workspaces/{w}/projects/{p}/storylines/{s}/branches/{b}/generations/{generation_id}/snapshot", response_model=GenerationSnapshotLink)
    def generation_snapshot(w: str, p: str, s: str, b: str, generation_id: str, x_session_token: str | None = Header(None)):
        authorized(x_session_token, w, p, s, b)
        try: job = service.generations.get(generation_id)
        except KeyError: raise _error(404, "GENERATION_NOT_FOUND")
        if job.get("novel_id") not in (None, p): raise _error(403, "RESOURCE_OUTSIDE_SCOPE")
        return GenerationSnapshotLink(generation_id=generation_id, context_snapshot_id=job.get("context_snapshot_id"))

    return router
