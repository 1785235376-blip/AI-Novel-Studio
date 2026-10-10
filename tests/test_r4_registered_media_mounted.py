"""Production composition for original local-image routes; no external calls."""
import base64
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from app.experimental.media import MediaWorkflowRequest, MockImageWorkflowAdapter
from app.model_center.discovery_bridge import LocalImageAdapter
from test_r4_broker_mounted import broker_app
from test_r3_mounted_contracts import mounted, prefix, checked


def test_mounted_registered_media_quote_job_manifest_and_default_off(broker_app, monkeypatch):
    e = broker_app
    media, broker = e.experimental.media_service, e.experimental.model_broker_service
    assert media.registry.original_registry is not None
    assert e.experimental.model_benchmark_service.media is media
    assert media.broker is broker
    candidate = {'id': 'mounted-image', 'provider_id': 'mounted-local-image', 'model_name': 'fixture.ckpt',
        'display_name': 'Mounted injected checkpoint', 'runtime_type': 'AUTOMATIC1111',
        'runtime_config': {'endpoint': 'http://127.0.0.1:7860', 'type': 'AUTOMATIC1111'}, 'enabled_at': 'one',
        'enabled': True, 'enable_eligible': True, 'verified_capabilities': ['IMAGE'], 'evidence': {'sha256': 'a' * 64}}
    original = LocalImageAdapter(SimpleNamespace(guard=lambda _: candidate,
        service=SimpleNamespace(check_model_dispatch=lambda _: None)), candidate)
    png = MockImageWorkflowAdapter().generate(MediaWorkflowRequest('fixture', 'cover_generation', 'mock', {}, 1, {}, 'fixture'))[0].content
    calls = []
    class Reply:
        def raise_for_status(self): pass
        def json(self): return {'images': [base64.b64encode(png).decode()]}
    class Transport:
        def post(self, url, **kwargs): calls.append(kwargs['json']); return Reply()
    original.delegate.transport = Transport()
    monkeypatch.setattr(media.registry.original_registry, '_providers', {candidate['provider_id']: original})
    # The real production registry projection and broker composition are intact.
    definitions = checked(e.client.get(e.base + '/media/adapters'))['items']
    adapter_id = next(row['adapter_id'] for row in definitions if row['adapter_id'].startswith('registered-image:'))
    routes = checked(e.client.get(e.base + '/model-broker/status', headers=e.headers))['candidates']
    route = next(row for row in routes if row.get('adapter_id') == adapter_id)
    now = datetime.now(timezone.utc)
    checked(e.client.put(e.base + '/model-broker/price', headers=e.headers, json={'route_id': route['route_id'],
        'route_fingerprint': route['fingerprint'], 'reserve_microusd': 0, 'source': 'Injected fixture estimate',
        'as_of': now.isoformat(), 'expires_at': (now + timedelta(days=1)).isoformat(), 'expected_version': 0}))
    brief = checked(e.client.post(e.base + '/media/cover-briefs', json={'title': 'Mounted cover', 'chapter_ids': [e.chapter['id']]}), 201)
    task = checked(e.client.post(e.base + '/media/tasks', json={'brief_id': brief['id'], 'expected_brief_version': 1,
        'adapter_id': adapter_id, 'candidate_count': 1, 'parameters': {'seed': 7}}), 201)
    assert not calls
    assert e.client.post(e.base + f"/media/tasks/{task['id']}/execute", json={'expected_version': 1}).status_code == 422
    quote = checked(e.client.post(e.base + f"/media/tasks/{task['id']}/preflight", json={'expected_version': 1}))
    assert quote['ready']
    task = checked(e.client.post(e.base + f"/media/tasks/{task['id']}/execute", json={'expected_version': 1,
        'broker_decision_id': quote['broker_decision_id'], 'broker_decision_version': quote['broker_decision_version']}))
    assert task['status'] == 'SUCCEEDED' and len(calls) == 1 and calls[0]['seed'] == 7
    assert checked(e.client.get(e.base + '/media/proposals'))['items'][0]['status'] == 'PENDING_REVIEW'
    manifest = checked(e.client.post(e.base + '/production/manifests', json={'task_id': task['id'], 'expected_task_version': task['version']}), 201)
    assert manifest['environment']['model_digest'] == 'a' * 64 and manifest['seed']['value'] == 7
    assert not manifest['environment']['deterministic']
    for flags, mode in [('', 'false'), ('*', 'false'), ('cover_storyboard_generation,media_adapter_registry', 'true')]:
        monkeypatch.setenv('EXPERIMENTAL_FEATURES', flags); monkeypatch.setenv('V1_ACCEPTANCE_MODE', mode)
        assert e.client.get(e.base + '/media/adapters').status_code == 404
        assert e.client.post(e.base + f"/media/tasks/{task['id']}/preflight", json={'expected_version': task['version']}).status_code == 404
    assert len(calls) == 1
