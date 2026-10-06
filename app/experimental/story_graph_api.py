"""Authorized author editing and fail-closed character projections."""
from fastapi import APIRouter, Header, HTTPException, Response
from pydantic import Field

from .common import api_call
from .planning import StrictModel
from .story_graph import StoryRecordIn, StoryRecordEditIn


class VersionIn(StrictModel):
    expected_version: int = Field(ge=1)


class ContextIn(StrictModel):
    character_id: str = Field(min_length=1, max_length=160)
    chapter_id: str = Field(min_length=1, max_length=160)
    world_time: int | None = None
    calendar: str = Field(default='story', min_length=1, max_length=80)


def create_story_graph_router(service, authorize, require_flag):
    router = APIRouter(prefix='/novels/{nid}/experimental/story-graph', tags=['experimental-story-graph'])

    def access(nid, token, branch, permission='domain.read', mind=False):
        require_flag('temporal_story_graph_v2')
        if mind: require_flag('character_mind_v2')
        return authorize(nid, token, branch, permission)

    def enabled_kind(kind):
        if kind == 'KNOWLEDGE_EVENT':
            try: require_flag('character_mind_v2')
            except HTTPException as exc:
                if exc.status_code == 404: return False
                raise
        return True

    def record(nid, scope, rid):
        row = api_call(service.record, nid, scope, rid)
        if not enabled_kind(row['kind']): raise HTTPException(404, {'code': 'EXPERIMENTAL_NOT_FOUND'})
        return row

    @router.get('/catalog')
    def catalog(nid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        _, scope = access(nid, x_session_token, x_branch_id, 'domain.write')
        return api_call(service.catalog, nid, scope)

    @router.get('/records')
    def records(nid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        _, scope = access(nid, x_session_token, x_branch_id, 'domain.write')
        return {'items': [row for row in api_call(service.records, nid, scope) if enabled_kind(row['kind'])]}

    @router.post('/records', status_code=201)
    def create(nid: str, body: StoryRecordIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope = access(nid, x_session_token, x_branch_id, 'domain.write', body.kind == 'KNOWLEDGE_EVENT')
        return api_call(service.create_record, nid, scope, actor, body)

    @router.get('/records/{rid}')
    def read(nid: str, rid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        _, scope = access(nid, x_session_token, x_branch_id, 'domain.write')
        return record(nid, scope, rid)

    @router.put('/records/{rid}')
    def edit(nid: str, rid: str, body: StoryRecordEditIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope = access(nid, x_session_token, x_branch_id, 'domain.write', body.kind == 'KNOWLEDGE_EVENT')
        record(nid, scope, rid)
        return api_call(service.edit_record, nid, scope, actor, rid, body)

    @router.get('/records/{rid}/history')
    def history(nid: str, rid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        _, scope = access(nid, x_session_token, x_branch_id, 'domain.write')
        return {'items': record(nid, scope, rid)['history']}

    @router.get('/records/{rid}/impact')
    def impact(nid: str, rid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        _, scope = access(nid, x_session_token, x_branch_id, 'domain.write')
        record(nid, scope, rid)
        # Impact can name knowledge-event IDs; require its flag when any such
        # records would otherwise appear, rather than disclose hidden counts.
        result = api_call(service.impact, nid, scope, rid)
        result['items'] = [row for row in result['items'] if enabled_kind(row['kind'])]
        result['affected_count'] = len(result['items'])
        return result

    @router.post('/records/{rid}/{action}')
    def action(nid: str, rid: str, action: str, body: VersionIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope = access(nid, x_session_token, x_branch_id, 'domain.write' if action == 'recompute' else 'domain.review')
        record(nid, scope, rid)
        if action == 'recompute':
            result = api_call(service.recompute, nid, scope, actor, rid, body.expected_version)
            # Graph-only users can refresh their graph. Never disclose IDs or
            # counts of the disabled knowledge extension in the result.
            result['recomputed_ids'] = [key for key in result['recomputed_ids']
                if enabled_kind(api_call(service.record, nid, scope, key)['kind'])]
            result['count'] = len(result['recomputed_ids'])
            return result
        return api_call(service.review, nid, scope, actor, rid, action, body.expected_version)

    @router.get('/query')
    def query(nid: str, response: Response, chapter_id: str, character_id: str | None = None, world_time: int | None = None,
              calendar: str = 'story', x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        _, scope = access(nid, x_session_token, x_branch_id, 'domain.read' if character_id else 'domain.write', bool(character_id))
        response.headers['Cache-Control'] = 'no-store'
        return api_call(service.graph, nid, scope, chapter_id, character_id, world_time, calendar)

    @router.post('/character-context')
    def context(nid: str, body: ContextIn, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        _, scope = access(nid, x_session_token, x_branch_id, mind=True)
        response.headers['Cache-Control'] = 'no-store'
        return api_call(service.character_context, nid, scope, body.character_id, body.chapter_id, body.world_time, body.calendar)

    return router
