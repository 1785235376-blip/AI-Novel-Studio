"""Real app router/storage integration; only model transport is a free test double."""
import json
import time
from types import SimpleNamespace as S

from app.actor_context import SessionContext
from app.author_request import request_payload
from app.model_runtime import GenerationEvent, TextGenerationResponse
from app.router import Route
from app.services.context_service import ContextService
from app.services.generation_service import GenerationService
from test_r3_mounted_contracts import mounted, prefix, checked


def test_mounted_workflow_inspection_saved_summary_is_real_and_redacted(mounted, monkeypatch):
    e = mounted
    service = e.experimental.local_ai_inspection_service
    for name, value in [('store', e.store), ('novels', e.novels), ('chapters', e.chapters)]: monkeypatch.setattr(service, name, value)
    monkeypatch.setattr(service, 'discovery_snapshot', lambda: {'scan': None, 'registrations': [], 'workflow_adapters': []})
    token = 'synthetic-host-inspection'
    e.sessions.register(token, SessionContext('session', 'client', 'actor', 'workspace'))
    headers = {'X-Session-Token': token}
    path = e.base + '/local-ai/workflow-inspections'
    body = {'workflow_json': json.dumps({'private-node': {'class_type': 'PythonExecHTTP', 'inputs': {'prompt': 'PRIVATE_PROMPT_CANARY', 'api_key': 'PRIVATE_KEY', 'path': '/private/folder'}}})}
    result = checked(e.client.post(path + '/inspect', json=body, headers=headers))
    assert result['execution_policy'] == 'DENY_ALL' and result['runnable'] is False
    assert 'PRIVATE_PROMPT_CANARY' not in json.dumps(result)
    assert checked(e.client.get(path + '/reports', headers=headers))['items'] == []
    saved = checked(e.client.post(path + '/reports', json=body, headers=headers), 201)
    assert saved['version'] == 1 and saved['privacy_level'] == 'LOCAL_ONLY'
    reopened = checked(e.client.get(path + '/reports', headers=headers))['items']
    assert reopened[0]['id'] == saved['id']
    assert reopened[0]['summary'] == result['export_summary']
    assert 'PRIVATE_KEY' not in json.dumps(e.store.read(e.nid, e.scope))
    assert 'private-node' not in json.dumps(e.store.read(e.nid, e.scope))
    e.sessions.revoke(token)
    assert e.client.get(path + '/reports', headers=headers).status_code == 401


def test_mounted_author_preview_real_job_persistence_matches_captured_transport(mounted, monkeypatch):
    import app.jobs as jobs_module
    import app.experimental.author_context_api as author_api
    e = mounted
    manager = e.api.jobs
    for name, value in [('chapters', e.chapters), ('contexts', ContextService(e.bundle.novels, e.bundle.chapters, enable_lore_context=False, enable_narrative_context=False, enable_context_pack_v2=False)), ('persistence', GenerationService(e.bundle.generations)), ('snapshot_required', False), ('jobs', {})]:
        monkeypatch.setattr(manager, name, value)
    sent = []
    class Node:
        def stream(self, value):
            value.request.dispatch_guard(); sent.append(request_payload(value.request))
            yield GenerationEvent('generation.delta', None, delta='Synthetic adapter output')
            yield GenerationEvent('generation.completed', None, response=TextGenerationResponse('Synthetic adapter output', 'stop', 'fixture', 'model'))
    runtime = S(is_remote_text_provider=lambda _: False, router=lambda *_: S(routes={'writer': [Route('fixture', 'model')]}),
                packaged_author_route_ready=lambda _: True, prepare_text_route=lambda *_: Node())
    monkeypatch.setattr(jobs_module, 'runtime', runtime); monkeypatch.setattr(author_api, 'runtime', runtime)
    body = {'novel_id': e.nid, 'chapter_id': e.chapter['id'], 'chapter_version': e.chapter['version'], 'operation': 'continue', 'provider_id': 'fixture', 'model_id': 'model', 'profile': 'LOCAL_ONLY'}
    preview = checked(e.client.post(e.base + '/author-context/preview', json=body))
    assert not sent
    result = checked(e.client.post(e.base + '/author-context/generate', json={**body, 'preview_digest': preview['preview_digest']}, headers={'Idempotency-Key': e.nid}), 202)
    for _ in range(200):
        job = manager.get(result['job_id'])
        if job.status in manager.terminal: break
        time.sleep(.01)
    assert job.status == 'COMPLETED', job.error
    assert sent == [preview['request']]
    stored = manager.persistence.get(job.id)
    assert stored['expected_request_digest'] == preview['preview_digest'] and stored['base_chapter_digest']
    assert 'request_authorization' not in stored
    assert e.chapters.get(e.chapter['id'])['content'] == e.chapter['content']
    repeated = checked(e.client.post(e.base + '/author-context/generate', json={**body, 'preview_digest': preview['preview_digest']}, headers={'Idempotency-Key': e.nid}), 202)
    assert repeated['job_id'] == job.id and len(sent) == 1
    # An interrupted reviewed job must never retry through the old unbound path.
    job.status = 'FAILED'
    assert e.client.post(e.prefix + f'/generation/{job.id}/retry').status_code == 409
