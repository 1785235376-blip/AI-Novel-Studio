"""B02 original author + broker + JobManager + Workflow; synthetic protocol only.

The imported mounted fixtures parametrize real File and opted-in PostgreSQL,
with both API prefixes. No paid provider, model download or real manuscript.
"""
import copy
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from test_r3_mounted_contracts import mounted, prefix, checked, scoped
from test_r4_broker_mounted import broker_app, route, wait_ledger
from app.experimental.declarative_agents import default_definition, WorkflowAuthoring


def saved(e, **changes):
    value = default_definition(); value['agent'].update(model_route=route(e)['route_id'], role_prompt='Role: synthetic coastal planner. Tools remain denied.', timeout_seconds=120, **changes)
    value['nodes'][0]['type'] = 'agent_task'
    return checked(e.client.post(e.base + '/declarative-agents/definitions', headers=e.headers, json={'definition': value}), 201)


def created(e, d=None, selected=False):
    d = d or saved(e)
    return checked(e.client.post(e.base + f'/declarative-agents/definitions/{d["id"]}/runs', headers=e.headers,
        json={'expected_version': d['version'], 'reviewed_definition_digest': d['definition_digest'],
            'request_id': 'synthetic-' + d['id'], 'input': {} if selected else {'source_text': 'SYNTHETIC_INPUT_123'},
            **({'chapter_ids': [e.chapter['id']], 'source_version': e.chapter['version']} if selected else
               {'anchor_chapter_id': e.chapter['id'], 'anchor_chapter_version': e.chapter['version']})}), 201)


def action(e, row, name, **extra):
    return checked(e.client.post(e.base + f'/declarative-agents/runs/{row["id"]}/{name}', headers=e.headers,
        json={'expected_version': row['version'], **extra}))


def ready(e, **changes):
    row = created(e, saved(e, **changes)); row = action(e, row, 'execute')
    assert row['status'] == 'WAITING_APPROVAL' and row['current_node_id'] == 'prepare'
    return action(e, row, 'model/preview')


def dispatch(e, row):
    return action(e, row, 'model/dispatch', reviewed_preview_digest=row['model_preview']['preview_digest'])


def settle(e, row):
    wait_ledger(e, row['model_execution']['reservation_id'])
    return action(e, row, 'model/refresh')


def test_original_model_node_exact_no_manuscript_receipt_and_manual_draft_review(broker_app):
    e = broker_app; original = copy.deepcopy(e.chapters.get(e.chapter['id']))
    row = ready(e); preview = row['model_preview']
    assert preview['source_strategy'] == 'NO_MANUSCRIPT'
    assert preview['contract']['reviewed_preview_digest'] == preview['preview_digest']
    assert preview['contract']['author_request_digest'] == preview['author']['preview_digest']
    assert preview['contract']['automatic_retry'] is False
    assert preview['request']['context'] == {}
    assert 'SYNTHETIC_INPUT_123' in preview['request']['prompt']
    assert 'synthetic coastal planner' in preview['request']['prompt']
    assert e.chapter['content'] not in preview['request']['prompt']
    assert preview['broker']['chosen']['synthetic'] and preview['broker']['chosen']['price']['reserve_microusd'] == 0
    assert not e.manager.jobs
    assert e.client.post(e.base + f'/declarative-agents/runs/{row["id"]}/approve', headers=e.headers, json={'expected_version': row['version']}).status_code == 422
    running = dispatch(e, row)
    assert len(e.manager.jobs) == 1
    assert e.manager.get(running['model_execution']['job_id']).experimental_origin == 'declarative_agent'
    again = dispatch(e, row)
    assert again['model_execution']['job_id'] == running['model_execution']['job_id'] and len(e.manager.jobs) == 1
    waiting = settle(e, running)
    assert waiting['status'] == 'WAITING_APPROVAL' and waiting['current_node_id'] == 'review'
    assert waiting['node_states']['prepare']['output']['result']['draft']
    assert waiting['model_execution']['accounting']['status'] == 'SETTLED'
    complete = action(e, waiting, 'approve')
    assert complete['status'] == 'SUCCEEDED' and complete['model_called'] and not complete['applied']
    assert complete['agent_output']['draft'] == e.manager.get(running['model_execution']['job_id']).output
    assert complete['node_states']['artifact']['output']['content'][0]['provenance']['method'] == 'ORIGINAL_AUTHOR_EXECUTOR'
    assert e.chapters.get(e.chapter['id']) == original
    job_id = complete['model_execution']['job_id']
    response = e.client.post(e.prefix + '/generation/' + job_id + '/accept', headers=e.headers, json={})
    assert response.status_code in {409, 422}
    assert e.chapters.get(e.chapter['id']) == original


def test_model_selected_saved_chapter_retains_current_version_fence(broker_app):
    e = broker_app; row = created(e, selected=True); row = action(e, row, 'execute'); row = action(e, row, 'model/preview')
    assert row['model_preview']['source_strategy'] == 'EXACT_SAVED_SELECTION'
    assert row['input']['source_text'] in row['model_preview']['request']['prompt']
    checked(e.client.put(e.prefix + f'/chapters/{e.chapter["id"]}', json={'version': e.chapter['version'], 'content': 'Changed synthetic source'}))
    response = e.client.post(e.base + f'/declarative-agents/runs/{row["id"]}/model/dispatch', headers=e.headers,
        json={'expected_version': row['version'], 'reviewed_preview_digest': row['model_preview']['preview_digest']})
    assert response.status_code == 409 and not e.manager.jobs
    current = checked(e.client.get(e.base + f'/declarative-agents/runs/{row["id"]}', headers=e.headers))
    assert current['stale'] and current['model_preview'] is None and current['input'] == {}


def test_model_admission_uncertain_never_replays_or_releases_hold(broker_app, monkeypatch):
    e = broker_app; row = ready(e)
    monkeypatch.setattr(e.manager, 'start_prepared', lambda job: (_ for _ in ()).throw(ValueError('synthetic lost admission response')))
    response = e.client.post(e.base + f'/declarative-agents/runs/{row["id"]}/model/dispatch', headers=e.headers,
        json={'expected_version': row['version'], 'reviewed_preview_digest': row['model_preview']['preview_digest']})
    assert response.status_code == 422
    current = checked(e.client.get(e.base + f'/declarative-agents/runs/{row["id"]}', headers=e.headers))
    assert current['model_execution']['status'] == 'UNKNOWN'
    assert current['model_execution']['receipt_state'] == 'UNKNOWN_NO_AUTOMATIC_REPLAY'
    again = dispatch(e, row)
    assert again['model_execution'] == current['model_execution'] and not e.manager.jobs
    refreshed = action(e, current, 'model/refresh')
    assert refreshed['model_execution']['accounting']['status'] == 'RESERVED'
    cancelled = action(e, refreshed, 'cancel')
    assert e.client.post(e.base + f'/declarative-agents/runs/{row["id"]}/retry', headers=e.headers, json={'expected_version': cancelled['version']}).status_code == 422


def test_model_preview_and_dispatch_require_current_host_and_flag(broker_app, monkeypatch):
    e = broker_app; row = ready(e)
    path = e.base + f'/declarative-agents/runs/{row["id"]}/model/dispatch'
    body = {'expected_version': row['version'], 'reviewed_preview_digest': row['model_preview']['preview_digest']}
    assert e.client.post(path, json=body).status_code == 401
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', '')
    assert e.client.post(path, headers=e.headers, json=body).status_code == 404
    assert not e.manager.jobs


def test_original_ready_branch_dag_executes_both_branches_before_review(broker_app):
    e = broker_app; value = default_definition(); value['agent']['allowed_tools'] += ['knowledge_candidates']
    value['nodes'].insert(1, {'id': 'branch', 'type': 'knowledge_candidates', 'name': 'Candidates'})
    value['nodes'].insert(2, {'id': 'other', 'type': 'checkpoint', 'name': 'Checkpoint'})
    value['edges'] = [{'source': 'prepare', 'target': 'branch'}, {'source': 'prepare', 'target': 'other'},
        {'source': 'branch', 'target': 'review'}, {'source': 'other', 'target': 'review'}, {'source': 'review', 'target': 'artifact'}]
    d = checked(e.client.post(e.base + '/declarative-agents/definitions', headers=e.headers, json={'definition': value}), 201)
    row = checked(e.client.post(e.base + f'/declarative-agents/definitions/{d["id"]}/runs', headers=e.headers, json={
        'expected_version': d['version'], 'reviewed_definition_digest': d['definition_digest'], 'request_id': 'branch', 'input': {'source_text': 'Synthetic branch one\nSynthetic branch two'}}), 201)
    waiting = action(e, row, 'execute')
    assert all(waiting['node_states'][key]['status'] == 'SUCCEEDED' for key in ('prepare', 'branch', 'other'))
    assert waiting['node_states']['artifact']['status'] == 'PENDING'
    complete = action(e, waiting, 'approve')
    assert complete['status'] == 'SUCCEEDED' and len(complete['node_states']['artifact']['output']['content']) == 2
    bypass = copy.deepcopy(value); bypass['edges'].append({'source': 'branch', 'target': 'artifact'})
    with pytest.raises(ValueError, match='review gate'): WorkflowAuthoring.model_validate(bypass)


def test_parallel_model_admissions_keep_exactly_one_job_and_one_reservation(broker_app):
    e = broker_app; row = ready(e)
    path = e.base + f'/declarative-agents/runs/{row["id"]}/model/dispatch'
    payload = {'expected_version': row['version'], 'reviewed_preview_digest': row['model_preview']['preview_digest']}
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: e.client.post(path, headers=e.headers, json=payload), range(2)))
    assert all(r.status_code in {200, 409} for r in responses)
    assert any(r.status_code == 200 for r in responses)
    assert len(e.manager.jobs) == 1
    assert len(e.broker.ledger(e.nid, e.scope, 'local-author')) == 1
    current = checked(e.client.get(e.base + f'/declarative-agents/runs/{row["id"]}', headers=e.headers))
    settled = settle(e, current)
    assert settled['status'] == 'WAITING_APPROVAL'


def test_model_late_source_change_withholds_output_and_review(broker_app):
    e = broker_app; running = dispatch(e, ready(e)); wait_ledger(e, running['model_execution']['reservation_id'])
    checked(e.client.put(e.prefix + f'/chapters/{e.chapter["id"]}', json={'version': e.chapter['version'], 'content': 'New anchor revision'}))
    response = e.client.post(e.base + f'/declarative-agents/runs/{running["id"]}/model/refresh', headers=e.headers, json={'expected_version': running['version']})
    assert response.status_code == 409
    current = checked(e.client.get(e.base + f'/declarative-agents/runs/{running["id"]}', headers=e.headers))
    assert current['stale'] and not current['input'] and current['model_preview'] is None
    assert all(v['output'] is None for v in current['node_states'].values())
    assert current['agent_output'] is None


def test_model_budget_change_after_exact_preview_blocks_original_dispatch(broker_app):
    e = broker_app; row = ready(e)
    checked(e.client.put(e.base + '/model-broker/budget', headers=e.headers, json={'expected_version': 0, 'limit_microusd': 0, 'max_inflight': 1, 'require_known_estimate': True}))
    response = e.client.post(e.base + f'/declarative-agents/runs/{row["id"]}/model/dispatch', headers=e.headers,
        json={'expected_version': row['version'], 'reviewed_preview_digest': row['model_preview']['preview_digest']})
    assert response.status_code == 409 and not e.manager.jobs
    assert not e.broker.ledger(e.nid, e.scope, 'local-author')


def test_model_bound_stream_discards_oversized_output_before_workflow_review(broker_app, monkeypatch):
    from app.runtime import runtime
    e = broker_app
    monkeypatch.setattr(runtime.providers['mock'], 'stream', lambda *args, **kwargs: iter(['潮' * 80, '潮' * 6]))
    running = dispatch(e, ready(e, max_output_bytes=256))
    job = e.manager.get(running['model_execution']['job_id'])
    result = settle(e, running)
    assert job.status == 'FAILED' and job.error_code == 'GENERATION_OUTPUT_LIMIT' and job.output == ''
    assert result['status'] == 'FAILED' and result['agent_output'] is None
    assert result['node_states']['artifact']['output'] is None
    assert result['model_execution']['accounting']['status'] == 'SETTLED'


def test_cancel_inflight_original_job_discards_late_output_and_never_retries(broker_app, monkeypatch):
    from threading import Event
    from app.runtime import runtime
    e = broker_app; started = Event(); release = Event()
    def stream(*args, **kwargs):
        started.set(); assert release.wait(5); yield 'Synthetic late output'
    monkeypatch.setattr(runtime.providers['mock'], 'stream', stream)
    running = dispatch(e, ready(e))
    try:
        assert started.wait(5)
        cancelled = action(e, running, 'cancel')
        assert cancelled['status'] == 'CANCELLED'
        assert e.manager.get(running['model_execution']['job_id']).cancelled.is_set()
    finally: release.set()
    wait_ledger(e, running['model_execution']['reservation_id'])
    assert e.manager.get(running['model_execution']['job_id']).output == ''
    refreshed = action(e, cancelled, 'model/refresh')
    assert refreshed['status'] == 'CANCELLED' and refreshed['agent_output'] is None


def test_restarted_original_job_loses_live_authority_and_cannot_be_admitted(broker_app, monkeypatch):
    from app.jobs import JobManager
    e = broker_app; running = dispatch(e, ready(e)); wait_ledger(e, running['model_execution']['reservation_id'])
    restarted = JobManager(generations=e.manager.persistence, chapters=e.chapters, contexts=e.manager.contexts, canon=e.canon, snapshot_required=False)
    coordinator = e.experimental.declarative_agents_service.model_coordinator
    monkeypatch.setattr(coordinator, 'manager', restarted)
    current = action(e, running, 'model/refresh')
    assert current['status'] == 'FAILED' and current['agent_output'] is None
    assert current['model_execution']['receipt_state'] == 'UNKNOWN_NO_AUTOMATIC_REPLAY'
    again = dispatch(e, running)
    assert again['model_execution']['job_id'] == running['model_execution']['job_id']
    assert len(restarted.jobs) == 1


def test_model_scope_never_falls_back_to_base_chapter_for_branch_anchor(broker_app, monkeypatch):
    e = scoped(broker_app, monkeypatch)
    d = saved(e)
    catalog = checked(e.client.get(e.base + '/declarative-agents/catalog', headers=e.headers))
    assert catalog['chapters'] == []  # Base manuscript is not a branch source.
    response = e.client.post(e.base + f'/declarative-agents/definitions/{d["id"]}/runs', headers=e.headers,
        json={'expected_version': 1, 'reviewed_definition_digest': d['definition_digest'], 'request_id': 'branch-anchor',
            'input': {'source_text': 'Synthetic manual instruction'}, 'anchor_chapter_id': e.chapter['id'], 'anchor_chapter_version': e.chapter['version']})
    assert response.status_code == 404 and not e.manager.jobs
    assert e.client.post(e.base + '/declarative-agents/definitions', headers=e.viewer_headers, json={'definition': d['definition']}).status_code == 403
    e.authorization.revoke_role(e.role, e.lead)
    assert e.client.get(e.base + '/declarative-agents/catalog', headers=e.headers).status_code == 403


def test_model_last_hop_feature_revocation_prevents_provider_send(broker_app, monkeypatch):
    from app.runtime import runtime
    e = broker_app; calls = []; original = e.broker.guard_dispatch
    monkeypatch.setattr(runtime.providers['mock'], 'stream', lambda *a, **k: (calls.append('send') or iter(['must not run'])))
    row = ready(e)
    def revoked(*args, **kwargs):
        monkeypatch.setenv('EXPERIMENTAL_FEATURES', '')
        return original(*args, **kwargs)
    monkeypatch.setattr(e.broker, 'guard_dispatch', revoked)
    response = e.client.post(e.base + f'/declarative-agents/runs/{row["id"]}/model/dispatch', headers=e.headers, json={'expected_version': row['version'], 'reviewed_preview_digest': row['model_preview']['preview_digest']})
    assert response.status_code in {200, 404}  # Revocation may race the final response fence.
    running = e.store.read(e.nid, e.scope)['collections'][e.experimental.declarative_agents_service.RUNS][row['id']]
    job = e.manager.get(running['model_execution']['job_id'])
    deadline = time.monotonic() + 5
    while (job.status not in e.manager.terminal or job.terminal_hook_status is None) and time.monotonic() < deadline: time.sleep(.01)
    assert job.status == 'FAILED' and not calls and not job.output
    ledger = e.broker.get(e.nid, e.scope, e.broker.LEDGER, running['model_execution']['reservation_id'])
    assert ledger['status'] == 'RELEASED' and not ledger['dispatched']


def test_model_expired_original_workflow_discards_completed_job_without_review(broker_app):
    e = broker_app; running = dispatch(e, ready(e)); wait_ledger(e, running['model_execution']['reservation_id'])
    from datetime import datetime, timedelta, timezone
    service = e.experimental.declarative_agents_service
    with e.store.transaction(e.nid, e.scope) as state:
        row = state['collections'][service.RUNS][running['id']]
        row['started_at'] = (datetime.now(timezone.utc) - timedelta(seconds=301)).isoformat()
    current = action(e, running, 'model/refresh')
    assert current['status'] == 'FAILED' and current['error']['code'] == 'WORKFLOW_TIMEOUT'
    assert current['agent_output'] is None and current['node_states']['artifact']['output'] is None
