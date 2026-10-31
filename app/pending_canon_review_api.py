"""Original pending Canon remains PROJECT-scoped, even with branch headers."""
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from .experimental.flags import require_flag
from .services.pending_canon_review_service import CanonDecisionIn, CanonPreviewIn
from .services.finding_review_service import FindingReviewConflict


class CancelRecoveryIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expected_version: int = Field(ge=1)


def create_pending_canon_review_router(service, authorize_project):
    router = APIRouter()
    def context(nid, token, permission):
        require_flag('finding_review_v1')
        return authorize_project(nid, token, permission)
    def call(fn, *args):
        try: return fn(*args)
        except FindingReviewConflict as exc: raise HTTPException(409, {'code': exc.code, 'current': exc.current}) from exc
        except (FileNotFoundError, KeyError) as exc: raise HTTPException(404, {'code': 'CANON_NOT_FOUND'}) from exc
        except OSError as exc: raise HTTPException(503, {'code': 'CANON_RECOVERY_REQUIRED', 'message': 'Commit interrupted; refresh and recover the existing receipt.'}) from exc
        except (ValueError, TypeError) as exc: raise HTTPException(422, {'code': 'CANON_REVIEW_INVALID', 'message': str(exc)}) from exc

    @router.get('/projects/{project_id}/pending-canon/review')
    def list_pending(project_id: str, x_session_token: str | None = Header(None)):
        actor = context(project_id, x_session_token, 'domain.read')
        result = call(service.list, project_id)
        if context(project_id, x_session_token, 'domain.read') != actor: raise HTTPException(403, {'code': 'CANON_ACTOR_CHANGED'})
        return result

    @router.post('/projects/{project_id}/pending-canon/{pending_id}/preview')
    def preview(project_id: str, pending_id: str, body: CanonPreviewIn, x_session_token: str | None = Header(None)):
        actor = context(project_id, x_session_token, 'domain.read')
        result = call(service.preview, project_id, pending_id, body)
        if context(project_id, x_session_token, 'domain.read') != actor: raise HTTPException(403, {'code': 'CANON_ACTOR_CHANGED'})
        return result

    @router.post('/projects/{project_id}/pending-canon/{pending_id}/review')
    def review(project_id: str, pending_id: str, body: CanonDecisionIn, x_session_token: str | None = Header(None)):
        actor = context(project_id, x_session_token, 'domain.review')
        def check():
            if context(project_id, x_session_token, 'domain.review') != actor: raise HTTPException(403, {'code': 'CANON_ACTOR_CHANGED'})
        result = call(service.review, project_id, pending_id, actor, body, check)
        check()
        return result

    @router.post('/projects/{project_id}/pending-canon/{pending_id}/recover')
    def recover(project_id: str, pending_id: str, body: CancelRecoveryIn, x_session_token: str | None = Header(None)):
        actor = context(project_id, x_session_token, 'domain.review')
        def check():
            if context(project_id, x_session_token, 'domain.review') != actor: raise HTTPException(403, {'code': 'CANON_ACTOR_CHANGED'})
        result = call(service.recover, project_id, pending_id, body.expected_version, check)
        check()
        return result

    @router.post('/projects/{project_id}/pending-canon/{pending_id}/cancel-recovery')
    def cancel(project_id: str, pending_id: str, body: CancelRecoveryIn, x_session_token: str | None = Header(None)):
        actor = context(project_id, x_session_token, 'domain.review')
        def check():
            if context(project_id, x_session_token, 'domain.review') != actor: raise HTTPException(403, {'code': 'CANON_ACTOR_CHANGED'})
        result = call(service.cancel_recovery, project_id, pending_id, actor, body.expected_version, check)
        check()
        return result
    return router
