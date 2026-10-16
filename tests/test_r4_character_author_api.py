"""Shared strict author coordinator and character preview/generation parity."""
import json

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.experimental.author_context_api import AuthorPreviewInput, create_author_context_router, create_author_preparer
from app.experimental.flags import require_flag
from test_r3_planning import planning_env
from test_r4_story_graph import env, relation, learn
from test_r4_character_author_context import binding
from test_r4_character_author_dispatch import dispatch


@pytest.fixture
def author_api(dispatch, monkeypatch):
    import app.jobs as jobs_module
    import app.experimental.author_context_api as api_module
    e = dispatch
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'world_character_engines_v2,temporal_story_graph_v2,character_mind_v2,author_context_inspector_v2')
    monkeypatch.setattr(api_module, 'runtime', jobs_module.runtime)
    e.started = []; e.permitted = True
    def authorize(nid, token, branch, permission):
        if not e.permitted or nid != e.nid or token != 'session' or branch: raise HTTPException(403)
        return 'local-author', e.scope
    def ordinary_payload(*_): pytest.fail('Character coordinator must not derive ordinary style or plan context')
    preparer = create_author_preparer(e.manager, authorize, require_flag, lambda *_: (None, None), ordinary_payload, story_graph=e.graph)
    def start(value):
        assert value.status == 'PREPARED'
        e.started.append(value); e.manager._run(value); return value
    e.manager.start_prepared = start
    app = FastAPI(); app.include_router(create_author_context_router(e.manager, authorize, require_flag, lambda *_: (None, None), ordinary_payload, preparer=preparer))
    e.client = TestClient(app); e.preparer = preparer
    e.base = f'/novels/{e.nid}/experimental/author-context'
    e.body = {'novel_id': e.nid, 'chapter_id': e.order[3], 'chapter_version': 1, 'operation': 'continue',
        'character_id': 'alice', 'provider_id': e.candidate['provider_id'], 'model_id': e.candidate['id'],
        'instruction': 'Use only what this fictional character knows.', 'profile': 'LOCAL_ONLY'}
    e.headers = {'X-Session-Token': 'session'}
    return e


def preview(e, **change):
    result = e.client.post(e.base + '/preview', json={**e.body, **change}, headers=e.headers)
    assert result.status_code == 200, result.text
    return result.json()


def test_character_preview_and_final_serialized_request_match_with_no_source_or_plan(author_api):
    e = author_api; secret = 'NARRATOR_SECRET_NOT_KNOWN_TO_ALICE'
    e.chapters[e.order[3]]['content'] = secret
    r = relation(e, secret); learn(e, r, character='bob')
    e.body.update(source=secret, selected_text='even an unsaved selection must be omitted', style=secret,
        style_profile_id='private-style-do-not-read', plot_plan_id='private-plan-do-not-read')
    p = preview(e)
    assert p['source_strategy'] == 'CHARACTER_KNOWLEDGE_ONLY' and p['source_characters'] == 0
    assert p['creation_records'] == [] and p['truncation'] == 'NONE'
    assert secret not in json.dumps(p) and 'private-plan-do-not-read' not in json.dumps(p)
    assert not e.wire.calls and not e.started
    response = e.client.post(e.base + '/generate', json={**e.body, 'preview_digest': p['preview_digest']}, headers=e.headers)
    assert response.status_code == 202, response.text
    assert response.json()['status'] == 'COMPLETED'
    assert e.adapter_requests == [p['request']]
    assert e.wire.generations[0][2]['prompt'] == p['request']['prompt']
    assert e.started[0].character_viewpoint == p['character_viewpoint']
    assert 'character_context_resolver' not in e.started[0].public()


def test_preparer_is_nonpersisting_exact_receipt_callable_for_broker(author_api):
    e = author_api; p = preview(e)
    body = AuthorPreviewInput.model_validate({**e.body, 'preview_digest': p['preview_digest']})
    value = e.preparer.prepare_author(e.nid, body, 'session', None)
    assert value.status == 'PREPARED' and value.expected_request_digest == p['preview_digest']
    assert callable(value.request_authorization) and callable(value.character_context_resolver)
    assert not e.started and not e.wire.calls
    bad = body.model_copy(update={'preview_digest': '0' * 64})
    with pytest.raises(HTTPException) as exc: e.preparer(e.nid, bad, 'session', None)
    assert exc.value.status_code == 409 and not e.wire.calls


@pytest.mark.parametrize('change', ['character', 'time', 'learn', 'instruction', 'permission'])
def test_character_receipt_rejects_new_viewpoint_or_current_authority(author_api, change):
    e = author_api; r = relation(e); p = preview(e); body = dict(e.body)
    if change == 'character': body['character_id'] = 'bob'
    elif change == 'time': body['world_time'] = 1
    elif change == 'learn': learn(e, r)
    elif change == 'instruction': body['instruction'] = 'Different explicit instruction'
    else: e.permitted = False
    result = e.client.post(e.base + '/generate', json={**body, 'preview_digest': p['preview_digest']}, headers=e.headers)
    assert result.status_code in {403, 409} and not e.started and not e.wire.calls


@pytest.mark.parametrize('change,status', [({'operation': 'rewrite'}, 422), ({'operation': 'polish'}, 422),
    ({'operation': 'review'}, 422), ({'profile': 'HYBRID'}, 403), ({'character_id': None, 'world_time': 1}, 422)])
def test_character_api_does_not_silently_downgrade_unsupported_input(author_api, change, status):
    e = author_api
    response = e.client.post(e.base + '/preview', json={**e.body, **change}, headers=e.headers)
    assert response.status_code == status and not e.wire.calls
