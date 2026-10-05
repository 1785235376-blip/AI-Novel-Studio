"""Captured free synthetic author transport proves preview/request correspondence."""
import copy
import json
from types import SimpleNamespace as S

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.author_request import request_digest, request_payload
from app.experimental.author_context_api import create_author_context_router
from app.experimental.flags import require_flag
from app.idempotency import IdempotencyStore
from app.jobs import JobManager
from app.model_runtime import GenerationEvent, TextGenerationResponse
from app.router import Route
from app.services.context_service import ContextService
from app.source_privacy import content_digest, review_source_privacy


@pytest.fixture
def rig(monkeypatch, tmp_path, request):
    import app.api as legacy
    import app.jobs as jobs
    import app.experimental.author_context_api as api
    from app.config import settings
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'author_context_inspector_v2')
    monkeypatch.delenv('V1_ACCEPTANCE_MODE', raising=False)
    original_data = settings.novel_data
    object.__setattr__(settings, 'novel_data', tmp_path / 'data')
    request.addfinalizer(lambda: object.__setattr__(settings, 'novel_data', original_data))
    monkeypatch.setattr(legacy, '_idempotency_store', IdempotencyStore(tmp_path / 'idempotency.json'))
    chapter = {'id': 'n:1', 'novel_id': 'n', 'number': 1, 'version': 1, 'content': 'Saved synthetic chapter selection.'}
    sources = {'novel': {'title': 'Synthetic'}, 'characters': [], 'secrets': [], 'locations': [], 'summaries': [], 'story_state': {}}
    manager = JobManager.__new__(JobManager)
    manager.chapters = S(get=lambda _: copy.deepcopy(chapter))
    manager.contexts = ContextService(S(get_context_sources=lambda _: copy.deepcopy(sources)), manager.chapters, enable_lore_context=False, enable_narrative_context=False, enable_context_pack_v2=False)
    manager.snapshot_required = False
    manager._emit = lambda job, chunk='': setattr(job, 'output', job.output + chunk)
    manager._persist = lambda job: None
    state = S(cloud=False, permitted=True, sent=[], created=[], before_send=lambda: None, extra_style='')
    class Node:
        def stream(self, value):
            state.before_send()
            value.request.dispatch_guard()
            state.sent.append(copy.deepcopy(request_payload(value.request)))
            yield GenerationEvent('generation.delta', None, delta='synthetic draft')
            yield GenerationEvent('generation.completed', None, response=TextGenerationResponse('synthetic draft', 'stop', 'fixture', 'model'))
    runtime = S(is_remote_text_provider=lambda _: state.cloud, router=lambda *_: S(routes={'writer': [Route('fixture', 'model')]}),
                packaged_author_route_ready=lambda _: True, prepare_text_route=lambda *_: Node())
    monkeypatch.setattr(jobs, 'runtime', runtime); monkeypatch.setattr(api, 'runtime', runtime)
    monkeypatch.setattr(jobs, 'runtime_log', S(write=lambda **_: None)); monkeypatch.setattr(jobs, 'deterministic_review', lambda *_: [])
    def start_prepared(job):
        assert job.status == 'PREPARED'
        state.created.append(job); manager._run(job); return job
    manager.start_prepared = start_prepared
    def authorize(nid, token, branch, permission):
        if not state.permitted or token != 'session' or nid != 'n' or branch:
            raise HTTPException(403, {'code': 'FORBIDDEN'})
        return 'actor', {'mode': 'local', 'novel_id': nid}
    def generation_context(*_): return None, None
    def generation_payload(body, *_): return {**body.model_dump(), 'style': state.extra_style or body.style}
    app = FastAPI(); router = create_author_context_router(manager, authorize, require_flag, generation_context, generation_payload)
    app.include_router(router, prefix='/api'); app.include_router(router, prefix='/api/v1')
    return S(client=TestClient(app), manager=manager, chapter=chapter, sources=sources, state=state, headers={'X-Session-Token': 'session'},
             body={'novel_id': 'n', 'chapter_id': 'n:1', 'chapter_version': 1, 'operation': 'continue', 'provider_id': 'fixture', 'model_id': 'model', 'instruction': 'Concise', 'style': 'calm', 'source': 'selection', 'selected_text': 'selection'})


def url(action, prefix='/api'): return prefix + '/novels/n/experimental/author-context/' + action


def preview(rig, body=None):
    result = rig.client.post(url('preview'), json=body or rig.body, headers=rig.headers)
    assert result.status_code == 200, result.text
    return result.json()


def generate(rig, value, body=None, headers=None):
    return rig.client.post(url('generate'), json={**(body or rig.body), 'preview_digest': value['preview_digest']}, headers=headers or rig.headers)


def test_preview_matches_exact_captured_adapter_request_and_no_early_model_call(rig):
    value = preview(rig)
    assert not rig.state.sent and not rig.state.created
    assert value['source_strategy'] == 'EXACT_SAVED_SELECTION'
    assert value['token_count'] is None and value['token_count_state'] == 'UNKNOWN'
    result = generate(rig, value)
    assert result.status_code == 202, result.text
    assert result.json()['status'] == 'COMPLETED'
    assert rig.state.sent == [value['request']]
    assert 'calm' in value['request']['prompt'] and 'selection' in value['request']['prompt']
    assert rig.state.created[0].public()['expected_request_digest'] == value['preview_digest']
    assert 'request_authorization' not in rig.state.created[0].public()


@pytest.mark.parametrize('change', ['instruction', 'style', 'provider_id', 'model_id', 'source', 'chapter_version'])
def test_changed_user_inputs_cannot_reuse_old_preview(rig, change):
    value = preview(rig)
    body = dict(rig.body)
    if change == 'chapter_version': body[change] = 2
    elif change == 'source': body.update(source='Saved', selected_text='Saved')
    else: body[change] += ' changed'
    result = generate(rig, value, body)
    assert result.status_code == 409 and not rig.state.sent and not rig.state.created


@pytest.mark.parametrize('change', ['chapter', 'context', 'approved_style', 'permission', 'locality'])
def test_current_source_context_approval_permission_locality_changes_block(rig, change):
    value = preview(rig)
    if change == 'chapter': rig.chapter['version'] = 2
    elif change == 'context': rig.sources['novel']['title'] = 'Changed project'
    elif change == 'approved_style': rig.state.extra_style = 'new approved style'
    elif change == 'permission': rig.state.permitted = False
    elif change == 'locality': rig.state.cloud = True
    assert generate(rig, value).status_code in {403, 409}
    assert rig.state.sent == []


@pytest.mark.parametrize('change', ['chapter', 'context', 'permission', 'approved_style', 'flag', 'cancel'])
def test_last_transport_guard_blocks_late_changes(rig, monkeypatch, change):
    value = preview(rig)
    def mutate():
        if change == 'chapter': rig.chapter['content'] = 'Different same-version source'
        elif change == 'context': rig.sources['novel']['title'] = 'Late context change'
        elif change == 'permission': rig.state.permitted = False
        elif change == 'approved_style': rig.state.extra_style = 'Late changed approval'
        elif change == 'flag': monkeypatch.setenv('V1_ACCEPTANCE_MODE', 'true')
        elif change == 'cancel': rig.state.created[-1].cancelled.set()
    rig.state.before_send = mutate
    result = generate(rig, value)
    assert result.status_code == 202
    assert result.json()['status'] in {'FAILED', 'CANCELLED'}
    assert rig.state.sent == []


def test_unsaved_selection_and_stale_chapter_and_extra_fields_fail_closed(rig):
    for update, status in [({'source': 'unsaved text', 'selected_text': 'unsaved text'}, 409), ({'source': 'selection', 'selected_text': 'Saved'}, 422), ({'chapter_version': 2}, 409), ({'operation': 'rewrite', 'source': '', 'selected_text': ''}, 422), ({'unknown': 'private'}, 422), ({'style': 'PRIVATE\nCONTROL'}, 422)]:
        result = rig.client.post(url('preview'), json={**rig.body, **update}, headers=rig.headers)
        assert result.status_code == status
    assert not rig.state.sent


def test_source_tail_is_actual_2000_saved_characters(rig):
    rig.chapter['content'] = 'prefix-not-sent-' + 'x' * 2000
    body = {**rig.body, 'source': '', 'selected_text': ''}
    value = preview(rig, body)
    assert value['source_characters'] == 2000
    assert value['source_strategy'] == 'LAST_2000_SAVED_CHARACTERS'
    assert 'prefix-not-sent' not in value['request']['prompt']
    assert generate(rig, value, body).status_code == 202
    assert rig.state.sent == [value['request']]


def test_cloud_request_omits_private_derived_summary_and_source_identifiers(rig):
    rig.state.cloud = True
    rig.body['profile'] = 'QUALITY'
    rig.sources['summaries'] = [{'id': 'PRIVATE_SOURCE_ID', 'text': 'PRIVATE_DERIVED_CANARY', 'privacy_level': 'LOCAL_ONLY'}]
    review_source_privacy(rig.chapter, None, 'synthetic', 'CLOUD_ALLOWED', 1, content_digest(rig.chapter))
    value = preview(rig)
    encoded = json.dumps(value)
    assert 'PRIVATE_SOURCE_ID' not in encoded and 'PRIVATE_DERIVED_CANARY' not in encoded
    assert value['privacy_omissions'] == [{'reason': 'SOURCE_PRIVACY_POLICY'}]
    assert generate(rig, value).status_code == 202
    assert rig.state.sent == [value['request']]
    assert 'PRIVATE_DERIVED_CANARY' not in json.dumps(rig.state.sent)


def test_cloud_consent_revoked_at_transport_prevents_any_request(rig):
    rig.state.cloud = True; rig.body['profile'] = 'QUALITY'
    review_source_privacy(rig.chapter, None, 'synthetic', 'CLOUD_ALLOWED', 1, content_digest(rig.chapter))
    value = preview(rig)
    rig.state.before_send = lambda: review_source_privacy(rig.chapter, None, 'synthetic', 'LOCAL_ONLY', 1, content_digest(rig.chapter))
    assert generate(rig, value).json()['status'] == 'FAILED'
    assert not rig.state.sent


def test_preview_digests_are_stable_across_transient_job_ids(rig):
    first, second = preview(rig), preview(rig)
    assert first['preview_digest'] == second['preview_digest']
    assert rig.state.created == []


def test_idempotency_returns_original_job_and_rejects_changed_payload(rig):
    headers = {**rig.headers, 'Idempotency-Key': 'same-attempt'}
    value = preview(rig)
    first = generate(rig, value, headers=headers)
    second = generate(rig, value, headers=headers)
    assert first.json() == second.json() and len(rig.state.created) == 1
    changed = {**rig.body, 'instruction': 'new instruction'}
    new = preview(rig, changed)
    rejected = generate(rig, new, changed, headers=headers)
    assert rejected.status_code == 409 and rejected.json()['detail']['code'] == 'IDEMPOTENCY_REQUEST_MISMATCH'
    assert len(rig.state.created) == 1


@pytest.mark.parametrize('prefix', ['/api', '/api/v1'])
def test_flags_permissions_missing_receipt_and_redacted_validation(rig, monkeypatch, prefix):
    assert rig.client.post(url('preview', prefix), json=rig.body).status_code == 403
    assert rig.client.post(url('generate', prefix), json=rig.body, headers=rig.headers).status_code == 409
    invalid = rig.client.post(url('preview', prefix), json={**rig.body, 'source': {'key': 'SECRET'}}, headers=rig.headers)
    assert invalid.status_code == 422 and 'SECRET' not in invalid.text
    monkeypatch.setenv('V1_ACCEPTANCE_MODE', 'true')
    rig.manager.contexts.for_chapter = lambda *_: pytest.fail('disabled flag must not build context')
    assert rig.client.post(url('preview', prefix), json=rig.body, headers=rig.headers).status_code == 404
    assert rig.client.post(url('generate', prefix), json=rig.body, headers=rig.headers).status_code == 404


@pytest.mark.parametrize('cloud', [False, True])
def test_multiline_hardbreak_emoji_editor_selection_is_exact_saved_source(rig, cloud):
    from app.document import document_to_markdown
    rig.chapter['document'] = {'type': 'doc', 'content': [
        {'type': 'paragraph', 'content': [{'type': 'text', 'text': 'First 😀'}, {'type': 'hardBreak'}, {'type': 'text', 'text': 'line'}]},
        {'type': 'paragraph', 'content': [{'type': 'text', 'text': 'Second 文'}]},
    ]}
    rig.chapter['content'] = document_to_markdown(rig.chapter['document'])
    body = {**rig.body, 'source': '😀\nline\nSecond 文', 'selected_text': '😀\nline\nSecond 文', 'operation': 'rewrite'}
    if cloud:
        rig.state.cloud = True; body['profile'] = 'QUALITY'
        review_source_privacy(rig.chapter, None, 'synthetic', 'CLOUD_ALLOWED', 1, content_digest(rig.chapter))
    value = preview(rig, body)
    assert value['request']['prompt'].endswith('SOURCE:\n😀\nline\nSecond 文')
    assert generate(rig, value, body).json()['status'] == 'COMPLETED'
    assert rig.state.sent == [value['request']]


def test_unsynchronized_document_cannot_add_private_text_to_reviewed_content(rig):
    rig.chapter['document'] = {'type': 'doc', 'content': [{'type': 'paragraph', 'content': [{'type': 'text', 'text': 'SECRET UNSAVED'}]}]}
    response = rig.client.post(url('preview'), json={**rig.body, 'source': 'SECRET UNSAVED', 'selected_text': 'SECRET UNSAVED'}, headers=rig.headers)
    assert response.status_code == 409 and not rig.state.sent


def test_real_local_adapter_serialization_sends_exact_preview_prompt(rig, tmp_path, monkeypatch):
    """Production node + discovery adapter + urllib serialization, synthetic wire."""
    import app.jobs as jobs_module
    from app.model_runtime import TextModelNode
    from test_local_ai_discovery_egress import enabled
    service, registered, candidate, adapter, wire = enabled(tmp_path / 'local-adapter')
    monkeypatch.setattr(jobs_module.runtime, 'prepare_text_route', lambda *_: TextModelNode(registered.provider_registry, registered.model_registry))
    body = {**rig.body, 'provider_id': candidate['provider_id'], 'model_id': candidate['id']}
    value = preview(rig, body)
    assert wire.calls == []  # Preview does not even probe the runtime.
    response = generate(rig, value, body)
    assert response.json()['status'] == 'COMPLETED', response.text
    assert len(wire.generations) == 1
    sent = wire.generations[0][2]
    assert sent['prompt'] == value['request']['prompt']
    assert sent['model'] == wire.tag['name']  # Existing registered upstream alias.
    assert sent['stream'] is False  # Existing discovery adapter buffers final output.


def test_local_metadata_wait_cannot_bypass_late_preview_revocation(rig, tmp_path, monkeypatch):
    import app.jobs as jobs_module
    from app.model_runtime import TextModelNode
    from test_local_ai_discovery_egress import enabled
    service, registered, candidate, adapter, wire = enabled(tmp_path / 'local-adapter')
    monkeypatch.setattr(jobs_module.runtime, 'prepare_text_route', lambda *_: TextModelNode(registered.provider_registry, registered.model_registry))
    body = {**rig.body, 'provider_id': candidate['provider_id'], 'model_id': candidate['id']}
    value = preview(rig, body)
    wire.on_show = lambda: setattr(rig.state, 'permitted', False)
    assert generate(rig, value, body).json()['status'] == 'FAILED'
    assert not wire.generations
