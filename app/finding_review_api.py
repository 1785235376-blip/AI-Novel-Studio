"""Additive source-bound review routes; legacy resolve routes remain compatible."""
from fastapi import APIRouter, Header, HTTPException
from .experimental.flags import require_flag
from .services.finding_review_service import FindingCheckIn, FindingDecisionIn, FindingReviewConflict


def create_finding_review_router(service, authorize):
    router = APIRouter()

    def context(nid, token, branch, permission):
        require_flag('finding_review_v1')
        return authorize(nid, token, branch, permission)

    def call(fn, *args, **kwargs):
        try: return fn(*args, **kwargs)
        except FindingReviewConflict as exc:
            raise HTTPException(409, {'code': exc.code, 'current': exc.current}) from exc
        except (FileNotFoundError, KeyError) as exc:
            raise HTTPException(404, {'code': 'FINDING_NOT_FOUND'}) from exc
        except (ValueError, TypeError) as exc:
            raise HTTPException(422, {'code': 'FINDING_INVALID', 'message': str(exc)}) from exc

    @router.get('/projects/{project_id}/{kind}/review-findings')
    def list_findings(project_id: str, kind: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope = context(project_id, x_session_token, x_branch_id, 'domain.read')
        result = call(service.list, project_id, scope, kind)
        if context(project_id, x_session_token, x_branch_id, 'domain.read') != (actor, scope): raise HTTPException(403, {'code': 'FINDING_SCOPE_CHANGED'})
        return result

    @router.post('/projects/{project_id}/{kind}/review-checks')
    def check_findings(project_id: str, kind: str, body: FindingCheckIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope = context(project_id, x_session_token, x_branch_id, 'domain.write')
        def check():
            current = context(project_id, x_session_token, x_branch_id, 'domain.write')
            if current != (actor, scope): raise HTTPException(403, {'code': 'FINDING_SCOPE_CHANGED'})
        result = call(service.check, project_id, scope, actor, kind, body, check)
        check()
        return result

    @router.get('/projects/{project_id}/{kind}/review-findings/{finding_id}')
    def detail(project_id: str, kind: str, finding_id: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope = context(project_id, x_session_token, x_branch_id, 'domain.read')
        result = call(service.get, project_id, scope, kind, finding_id)
        if context(project_id, x_session_token, x_branch_id, 'domain.read') != (actor, scope): raise HTTPException(403, {'code': 'FINDING_SCOPE_CHANGED'})
        return result

    @router.get('/projects/{project_id}/{kind}/review-findings/{finding_id}/history')
    def history(project_id: str, kind: str, finding_id: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope = context(project_id, x_session_token, x_branch_id, 'domain.read')
        row = call(service.get, project_id, scope, kind, finding_id)
        if context(project_id, x_session_token, x_branch_id, 'domain.read') != (actor, scope): raise HTTPException(403, {'code': 'FINDING_SCOPE_CHANGED'})
        return {'items': row['review_history'], 'version': row['review_version']}

    @router.get('/projects/{project_id}/{kind}/review-findings/{finding_id}/evidence')
    def evidence(project_id: str, kind: str, finding_id: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope = context(project_id, x_session_token, x_branch_id, 'domain.read')
        result = call(service.evidence, project_id, scope, kind, finding_id)
        if context(project_id, x_session_token, x_branch_id, 'domain.read') != (actor, scope): raise HTTPException(403, {'code': 'FINDING_SCOPE_CHANGED'})
        return result

    @router.post('/projects/{project_id}/{kind}/review-findings/{finding_id}/review')
    def review(project_id: str, kind: str, finding_id: str, body: FindingDecisionIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope = context(project_id, x_session_token, x_branch_id, 'domain.review')
        def check():
            current = context(project_id, x_session_token, x_branch_id, 'domain.review')
            if current != (actor, scope): raise HTTPException(403, {'code': 'FINDING_SCOPE_CHANGED'})
        result = call(service.review, project_id, scope, actor, kind, finding_id, body, check)
        check()
        return result

    return router
