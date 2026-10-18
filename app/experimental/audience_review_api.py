"""Audience routes mounted only beneath the original narrative review router."""
from fastapi import Header, Response
from .common import api_call
from .planning import StrictModel
from pydantic import Field


class PrepareSourceIn(StrictModel):
    expected_version: int = Field(ge=1)
from .audience_review import AudienceReview, AudienceComparisonIn


def mount_audience_review(router, service, access):
    audience = AudienceReview(service)

    @router.get('/audience/catalog')
    def catalog(nid: str, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        _, scope, guard = access(nid, x_session_token, x_branch_id, response)
        result = api_call(audience.catalog, nid, scope); guard(); return result

    @router.get('/audience/source/{chapter_id}')
    def source(nid: str, chapter_id: str, expected_version: int, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        _, scope, guard = access(nid, x_session_token, x_branch_id, response)
        result = api_call(audience.source, nid, scope, chapter_id, expected_version, guard); guard(); return result

    @router.post('/audience/source/{chapter_id}/prepare')
    def prepare_source(nid: str, chapter_id: str, body: PrepareSourceIn, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        _, scope, guard = access(nid, x_session_token, x_branch_id, response)
        result = api_call(audience.prepare_source, nid, scope, chapter_id, body.expected_version, guard); guard(); return result

    @router.get('/audience/comparisons')
    def comparisons(nid: str, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        _, scope, guard = access(nid, x_session_token, x_branch_id, response)
        result = {'items': api_call(audience.comparisons, nid, scope)}; guard(); return result

    @router.post('/audience/comparisons', status_code=201)
    def create(nid: str, body: AudienceComparisonIn, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope, guard = access(nid, x_session_token, x_branch_id, response)
        result = api_call(audience.create, nid, scope, actor, body, guard); guard(); return result
