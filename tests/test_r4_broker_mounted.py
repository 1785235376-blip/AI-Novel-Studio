"""Mounted A06/A07 with production routers, File/real PG and existing authority."""
import copy
import time
from app.actor_context import SessionContext
from app.services.context_service import ContextService
from app.services.generation_service import GenerationService
from test_r3_mounted_contracts import mounted, prefix, scoped, checked
import pytest


@pytest.fixture
def broker_app(mounted, monkeypatch):
    e = mounted
    e.broker = e.experimental.model_broker_service
    e.bench = e.experimental.model_benchmark_service
    for service in (e.broker, e.bench):
        for name, value in (('store', e.store), ('novels', e.novels), ('chapters', e.chapters)):
            monkeypatch.setattr(service, name, value)
    e.sessions.register('broker-host', SessionContext('broker-host-session', 'broker-test-client', 'broker-test-actor', 'broker-test-workspace'))
    e.headers = {'X-Session-Token': 'broker-host'}
    e.manager = e.api.jobs
    context = ContextService(e.bundle.novels, e.bundle.chapters, e.lore,
        enable_lore_context=False, enable_narrative_context=False, enable_context_pack_v2=False)
    for key, value in (('chapters', e.chapters), ('contexts', context), ('persistence', GenerationService(e.bundle.generations)),
                       ('snapshot_required', False), ('jobs', {})):
        monkeypatch.setattr(e.manager, key, value)
    yield e
    for job in list(e.manager.jobs.values()):
        if job.status not in e.manager.terminal: e.manager.cancel(job.id)
    deadline = time.monotonic() + 5
    while any(job.status not in e.manager.terminal or (job.dispatch_hooks_required and job.terminal_hook_status is None) for job in e.manager.jobs.values()) and time.monotonic() < deadline:
        time.sleep(.01)


def route(e):
    value = checked(e.client.get(e.base + '/model-broker/status', headers=e.headers))
    return next(r for r in value['candidates'] if r['provider_id'] == 'mock')


def quote(e):
    return checked(e.client.post(e.base + '/model-broker/preview', headers=e.headers, json={
        'chapter_ids': [e.chapter['id']], 'policy': 'CUSTOM', 'preferred_route': route(e)['route_id'], 'allow_synthetic': True}))


def author_body(e):
    return {'novel_id': e.nid, 'chapter_id': e.chapter['id'], 'chapter_version': e.chapter['version'],
            'operation': 'continue', 'instruction': 'Synthetic mounted broker request', 'provider_id': 'mock', 'model_id': 'mock-writer', 'profile': 'LOCAL_ONLY'}


def wait_ledger(e, reservation_id):
    deadline = time.monotonic() + 5
    while True:
        row = checked(e.client.get(e.base + '/model-broker/jobs/' + reservation_id, headers=e.headers))
        if row['ledger']['status'] not in {'RESERVED', 'DISPATCHED'}: return row
        if time.monotonic() > deadline: pytest.fail(f'Broker job did not settle: {row["ledger"]["status"]}')
        time.sleep(.01)


def test_mounted_broker_exact_author_receipt_existing_executor_and_idempotent_ledger(broker_app):
    e = broker_app; original = copy.deepcopy(e.chapters.get(e.chapter['id']))
    selected = quote(e); assert selected['chosen']['provider_id'] == 'mock'
    body = author_body(e)
    preview = checked(e.client.post(e.base + '/author-context/preview', headers=e.headers, json=body))
    value = {'preview_id': selected['id'], 'expected_version': selected['version'], 'request_id': 'mounted-author-one',
             'author': {**body, 'preview_digest': preview['preview_digest']}}
    generated = checked(e.client.post(e.base + '/model-broker/generate', headers=e.headers, json=value), 202)
    result = wait_ledger(e, generated['reservation_id'])
    assert result['job']['status'] == 'COMPLETED' and result['job']['output']
    assert result['ledger']['status'] == 'SETTLED' and result['ledger']['actual_microusd'] == 0
    assert result['job']['id'] in e.manager.jobs
    assert result['job']['dispatch_hooks_required'] is True
    assert not any(key in result['job'] for key in ('before_dispatch', 'on_terminal', 'request_authorization'))
    again = checked(e.client.post(e.base + '/model-broker/generate', headers=e.headers, json=value), 202)
    assert again['job_id'] == generated['job_id'] and len(e.manager.jobs) == 1
    assert e.chapters.get(e.chapter['id']) == original
    assert e.client.get(e.base + '/model-broker/status', headers=e.headers).headers['cache-control'] == 'no-store'


def test_mounted_broker_current_source_revocation_and_flag_dependencies(broker_app, monkeypatch):
    e = broker_app; selected = quote(e); body = author_body(e)
    preview = checked(e.client.post(e.base + '/author-context/preview', headers=e.headers, json=body))
    changed = checked(e.client.put(e.prefix + f'/chapters/{e.chapter["id"]}', json={'version': e.chapter['version'], 'content': 'New synthetic revision'}))
    assert changed['version'] > e.chapter['version']
    value = {'preview_id': selected['id'], 'expected_version': 1, 'request_id': 'stale-mounted', 'author': {**body, 'preview_digest': preview['preview_digest']}}
    assert e.client.post(e.base + '/model-broker/generate', headers=e.headers, json=value).status_code == 409
    assert not e.manager.jobs
    for flags, acceptance in [('', 'false'), ('*', 'false'), ('model_broker_v2,model_benchmark_v2', 'false'), ('author_context_inspector_v2,model_broker_v2,model_benchmark_v2', 'true')]:
        monkeypatch.setenv('EXPERIMENTAL_FEATURES', flags); monkeypatch.setenv('V1_ACCEPTANCE_MODE', acceptance)
        for path in ('/model-broker/status', '/model-benchmarks/status', '/model-broker/history'):
            assert e.client.get(e.base + path, headers=e.headers).status_code == 404


def test_mounted_benchmark_persistence_current_evidence_and_cas(broker_app):
    e = broker_app
    definition = {'title': 'Mounted synthetic set', 'cases': [{'title': 'Chinese', 'kind': 'CHINESE_CONTINUATION', 'prompt': '用中文继续合成故事。', 'rule': 'NONEMPTY'}]}
    test_set = checked(e.client.post(e.base + '/model-benchmarks/sets', headers=e.headers, json=definition), 201)
    run = checked(e.client.post(e.base + '/model-benchmarks/runs', headers=e.headers, json={'set_id': test_set['id'], 'expected_set_version': 1, 'route_id': route(e)['route_id'], 'request_id': 'mounted-bench'}), 201)
    assert run['status'] == 'READY'
    run = checked(e.client.post(e.base + f'/model-benchmarks/runs/{run["id"]}/step', headers=e.headers, json={'expected_version': 1}))
    assert run['status'] == 'COMPLETED'
    evidence = checked(e.client.get(e.base + '/model-benchmarks/status', headers=e.headers))['evidence'][0]
    assert evidence['evidence_state'] == 'CURRENT' and evidence['metrics']['sample_count'] == 1
    assert evidence['tokens_per_second'] is None and evidence['gpu_memory_bytes'] is None
    checked(e.client.put(e.base + f'/model-benchmarks/sets/{test_set["id"]}', headers=e.headers, json={**definition, 'title': 'Changed test set', 'expected_version': 1}))
    assert e.client.put(e.base + f'/model-benchmarks/sets/{test_set["id"]}', headers=e.headers, json={**definition, 'expected_version': 1}).status_code == 409
    assert checked(e.client.get(e.base + '/model-benchmarks/status', headers=e.headers))['evidence'][0]['evidence_state'] == 'HISTORICAL'


def test_mounted_host_and_current_membership_are_both_required(broker_app, monkeypatch):
    e = broker_app
    assert e.client.get(e.base + '/model-broker/status').status_code == 401
    e = scoped(e, monkeypatch)
    checked(e.client.get(e.base + '/model-broker/status', headers=e.headers))
    assert e.client.post(e.base + '/model-broker/preview', headers=e.viewer_headers, json={}).status_code == 403
    assert e.client.post(e.base + '/model-benchmarks/sets', headers=e.viewer_headers, json={'title': 'No write', 'cases': [{'title': 'x', 'kind': 'SHORT_REVIEW', 'prompt': 'x'}]}).status_code == 403
    e.authorization.revoke_role(e.role, e.lead)
    assert e.client.get(e.base + '/model-broker/status', headers=e.headers).status_code == 403
    assert e.client.get(e.base + '/model-benchmarks/status', headers=e.headers).status_code == 403
