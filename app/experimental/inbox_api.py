from typing import Literal
from fastapi import APIRouter, Header, Query, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from .common import api_call
from .inbox import ReviewContext


class ReviewActionIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expected_version: int = Field(ge=1)


class BatchItem(ReviewActionIn):
    domain: str = Field(min_length=1, max_length=80)
    id: str = Field(min_length=1, max_length=240)
    action: Literal['approve', 'reject', 'reopen']


class BatchIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    items: list[BatchItem] = Field(min_length=1, max_length=50)


def create_inbox_router(service, authorize, require_flag):
    router = APIRouter()
    prefix = '/novels/{nid}/experimental/review-inbox'

    def context(nid, token, branch, permission):
        require_flag('unified_review_inbox')
        actor, scope = authorize(nid, token, branch, permission)
        return ReviewContext(nid, scope, actor, token, branch)

    @router.get(prefix)
    def inbox(nid: str, domain: str | None = None, status: str | None = None,
              search: str | None = Query(None, max_length=400), stale: bool | None = None,
              x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx = context(nid, x_session_token, x_branch_id, 'domain.read')
        result = api_call(service.list, ctx, domain=domain, status=status, search=search, stale=stale)
        if context(nid, x_session_token, x_branch_id, 'domain.read') != ctx:
            raise HTTPException(403, {'code': 'REVIEW_AUTHORITY_CHANGED'})
        return result

    @router.post(prefix + '/batch')
    def batch(nid: str, body: BatchIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx = context(nid, x_session_token, x_branch_id, 'domain.review')
        def reauthorize():
            current = context(nid, x_session_token, x_branch_id, 'domain.review')
            if current != ctx:
                raise ValueError('review authority changed')
        return api_call(service.batch, ctx, body.items, reauthorize)

    @router.post(prefix + '/{domain}/{item_id}/{action}')
    def review(nid: str, domain: str, item_id: str, action: Literal['approve', 'reject', 'reopen'],
               body: ReviewActionIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx = context(nid, x_session_token, x_branch_id, 'domain.review')
        return api_call(service.review, ctx, domain, item_id, action, body.expected_version)

    return router
