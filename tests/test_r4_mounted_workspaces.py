"""R4 real app composition, actual File/PG storage and trusted session guards."""
import copy
import json
from app.actor_context import SessionContext
import pytest
from test_r3_mounted_contracts import mounted, prefix, scoped, checked


@pytest.fixture
def workspace(mounted, monkeypatch):
    e = mounted
    for service in (e.experimental.workspace_tools_service, e.experimental.local_ai_inspection_service, e.experimental.writing_focus_service):
        for key, value in (('store', e.store), ('novels', e.novels), ('chapters', e.chapters)):
            monkeypatch.setattr(service, key, value)
    monkeypatch.setattr(e.experimental.workspace_tools_service, '_indexes', __import__('collections').OrderedDict())
    monkeypatch.setattr(e.experimental.local_ai_inspection_service, 'discovery_snapshot', lambda: {'runtimes': [], 'candidates': [], 'registrations': []})
    return e


def test_mounted_registry_off_and_acceptance_gates(workspace, monkeypatch):
    e = workspace
    result = checked(e.client.get(e.prefix + '/experimental/capabilities'))
    assert len(result['items']) == 40
    paths = ['/workspace/resume', '/workspace/search', '/workspace/tasks', '/local-ai/workflow-inspections']
    for config in ('', '*', ','.join(__import__('app.experimental.flags', fromlist=['FLAGS']).FLAGS)):
        monkeypatch.setenv('EXPERIMENTAL_FEATURES', config)
        monkeypatch.setenv('V1_ACCEPTANCE_MODE', 'true' if config not in ('', '*') else 'false')
        for path in paths:
            assert e.client.get(e.base + path).status_code == 404
        assert e.client.post(e.base + '/workspace/diagnostics/preview', json={}).status_code == 404


def test_mounted_resume_search_source_version_and_export(workspace):
    e = workspace
    before = copy.deepcopy(e.chapters.get(e.chapter['id']))
    saved = checked(e.client.put(e.base + '/workspace/resume', json={
        'chapter_id': before['id'], 'chapter_version': before['version'],
        'anchor': {'offset': 4, 'scroll': 50}, 'stopping_note': '明天校对合成章节',
    }))['item']
    assert checked(e.client.get(e.base + '/workspace/resume'))['item']['id'] == saved['id']
    target = checked(e.client.post(e.base + '/workspace/resume/resolve', json={'expected_version': saved['version']}))
    assert target['id'] == before['id'] and target['coordinate'] == 'EDITOR_TEXT_CODEPOINT'
    search = checked(e.client.get(e.base + '/workspace/search', params={'q': 'Alice'}))
    row = next(item for item in search['items'] if item['kind'] == 'chapter')
    e.chapters.save(before['id'], {'content': '变更后的合成章节，Alice', 'version': before['version']})
    assert checked(e.client.get(e.base + '/workspace/resume'))['availability'] == 'STALE'
    assert e.client.post(e.base + '/workspace/resume/resolve', json={'expected_version': saved['version']}).status_code == 409
    assert e.client.post(e.base + '/workspace/search/resolve', json={'kind': row['kind'], 'id': row['id'], 'revision': row['revision'], 'offset': row['offset']}).status_code == 409
    opened = checked(e.client.post(e.base + '/workspace/resume/resolve', json={'expected_version': saved['version'], 'open_current': True}))
    assert opened['anchor'] == {'offset': 0, 'scroll': 0}
    preview = checked(e.client.post(e.base + '/workspace/diagnostics/preview', json={}))
    exported = checked(e.client.post(e.base + '/workspace/diagnostics/export', json={'preview_digest': preview['preview_digest']}))
    assert exported == preview and exported['uploaded'] is False
    assert '明天' not in json.dumps(exported, ensure_ascii=False)
    assert e.client.post(e.base + '/workspace/diagnostics/export', json={'preview_digest': '0' * 64}).status_code == 409


def test_mounted_workspace_actor_separation_and_current_revocation(workspace, monkeypatch):
    e = scoped(workspace, monkeypatch)
    result = checked(e.client.put(e.base + '/workspace/resume', headers=e.headers,
        json={'stopping_note': 'Only lead note'}))
    assert result['item']['stopping_note'] == 'Only lead note'
    assert checked(e.client.get(e.base + '/workspace/resume', headers=e.viewer_headers))['item'] is None
    assert e.client.put(e.base + '/workspace/resume', headers=e.viewer_headers, json={'stopping_note': 'deny'}).status_code == 403
    search = checked(e.client.get(e.base + '/workspace/search', headers=e.headers))
    assert search['branch_sources_available'] is False and search['items'] == []
    e.authorization.revoke_role(e.role, e.lead)
    for path in ('/workspace/resume', '/workspace/search', '/workspace/tasks'):
        assert e.client.get(e.base + path, headers=e.headers).status_code == 403


def test_mounted_inspector_requires_real_host_session_and_project_guard(workspace, monkeypatch):
    e = workspace
    path = e.base + '/local-ai/workflow-inspections'
    assert e.client.get(path).status_code == 401
    token = 'synthetic-r4-host-session'
    e.sessions.register(token, SessionContext('r4-session', 'r4-client', 'r4-host', 'r4-workspace'))
    response = e.client.get(path, headers={'X-Session-Token': token})
    assert response.status_code == 200, response.text
    assert response.headers['cache-control'] == 'no-store'
    e.sessions.revoke(token)
    assert e.client.get(path, headers={'X-Session-Token': token}).status_code == 401


def test_mounted_focus_notes_reference_pin_and_explicit_planning_copy(workspace):
    e = workspace
    base = e.base + '/writing-focus'
    original = copy.deepcopy(e.chapters.get(e.chapter['id']))
    reference = next(row for row in checked(e.client.get(base + '/references'))['items'] if row['kind'] == 'chapter')
    pref = checked(e.client.put(base + '/preferences', json={'expected_version': 0,
        'preferences': {'font_size': 20, 'paragraph_focus': True},
        'pins': [{k: reference[k] for k in ('kind', 'id', 'revision')}]}))
    assert pref['version'] == 1
    assert checked(e.client.get(base + '/pins'))['items'][0]['state'] == 'READY'
    note = checked(e.client.post(base + '/notes', json={'capture_id': 'synthetic-note-one',
        'title': '灵感标题', 'text': '我自己记录的合成灵感，不是 Canon。',
        'chapter_id': original['id'], 'chapter_version': original['version']}), 201)
    assert note['included_in_ai_context'] is False and note['canon'] is False
    graph = checked(e.client.post(e.base + '/planning/graphs', json={'title': 'Synthetic proposal target'}), 201)
    request = {'expected_version': note['version'], 'node_id': graph['root_node_id'], 'expected_node_version': 1, 'field': 'goal'}
    preview = checked(e.client.post(base + f"/notes/{note['id']}/planning/preview", json=request))
    assert preview['status_after_copy'] == 'REVIEW'
    result = checked(e.client.post(base + f"/notes/{note['id']}/planning/copy", json={**request, 'preview_digest': preview['preview_digest']}), 201)
    assert result['status'] == 'REVIEW'
    assert e.chapters.get(original['id']) == original
    current_graph = checked(e.client.get(e.base + '/planning/graphs/' + graph['id']))
    assert next(node for node in current_graph['nodes'] if node['id'] == graph['root_node_id'])['fields']['goal'] == ''


def test_mounted_author_preview_matches_real_adapter_boundary_and_persists(workspace, monkeypatch):
    import time
    from types import SimpleNamespace
    from app.author_request import request_payload
    from app.idempotency import IdempotencyStore
    from app.model_runtime import GenerationEvent, TextGenerationResponse
    from app.router import Route
    from app.services.context_service import ContextService
    from app.services.generation_service import GenerationService
    import app.jobs as jobs_module
    import app.experimental.author_context_api as author_api
    e = workspace
    manager = e.api.jobs
    monkeypatch.setattr(manager, 'chapters', e.chapters)
    monkeypatch.setattr(manager, 'contexts', ContextService(e.bundle.novels, e.bundle.chapters, e.lore,
        enable_lore_context=False, enable_narrative_context=False, enable_context_pack_v2=False))
    monkeypatch.setattr(manager, 'persistence', GenerationService(e.bundle.generations))
    monkeypatch.setattr(manager, 'snapshot_required', False)
    monkeypatch.setattr(manager, 'jobs', {})
    monkeypatch.setattr(e.api, '_idempotency_store', IdempotencyStore(e.root / 'author-idempotency.json'))
    captured = []
    class CaptureTransport:
        def stream(self, value):
            value.request.dispatch_guard()
            captured.append(copy.deepcopy(request_payload(value.request)))
            yield GenerationEvent('generation.delta', None, delta='Synthetic adapter output')
            yield GenerationEvent('generation.completed', None,
                response=TextGenerationResponse('Synthetic adapter output', 'stop', 'fixture', 'model'))
    runtime = SimpleNamespace(is_remote_text_provider=lambda _: False,
        router=lambda *_: SimpleNamespace(routes={'writer': [Route('fixture', 'model')]}),
        packaged_author_route_ready=lambda _: True, prepare_text_route=lambda *_: CaptureTransport())
    monkeypatch.setattr(jobs_module, 'runtime', runtime)
    monkeypatch.setattr(author_api, 'runtime', runtime)
    monkeypatch.setattr(jobs_module, 'runtime_log', SimpleNamespace(write=lambda **_: None))
    monkeypatch.setattr(jobs_module, 'deterministic_review', lambda *_: [])
    payload = {'novel_id': e.nid, 'chapter_id': e.chapter['id'], 'chapter_version': e.chapter['version'],
        'operation': 'continue', 'instruction': 'Synthetic request', 'profile': 'LOCAL_ONLY',
        'provider_id': 'fixture', 'model_id': 'model'}
    preview = checked(e.client.post(e.base + '/author-context/preview', json=payload))
    assert captured == []
    headers = {'Idempotency-Key': 'synthetic-stable-preview-submit'}
    response = checked(e.client.post(e.base + '/author-context/generate', headers=headers,
        json={**payload, 'preview_digest': preview['preview_digest']}), 202)
    deadline = time.monotonic() + 5
    while manager.get(response['job_id']).status not in {'COMPLETED', 'FAILED'} and time.monotonic() < deadline:
        time.sleep(.01)
    job = manager.get(response['job_id'])
    assert job.status == 'COMPLETED', job.error
    assert captured == [preview['request']]
    repeated = checked(e.client.post(e.base + '/author-context/generate', headers=headers,
        json={**payload, 'preview_digest': preview['preview_digest']}), 202)
    assert repeated['job_id'] == job.id and len(captured) == 1
    assert manager.persistence.get(job.id)['expected_request_digest'] == preview['preview_digest']
    assert e.client.post(e.prefix + f'/generation/{job.id}/retry').status_code == 409
    assert e.chapters.get(e.chapter['id'])['version'] == e.chapter['version']
