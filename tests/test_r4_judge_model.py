"""A03 production-composed registered route, no paid/real-model calls.

Production routers and author/executor/broker/review authorities are unchanged
in these tests. File and marked real-PG cases share the same contracts.
"""
import copy
import json
from concurrent.futures import ThreadPoolExecutor

import pytest
from test_r3_mounted_contracts import mounted, prefix, checked, scoped
from test_r4_broker_mounted import broker_app, route, wait_ledger
from app.experimental.narrative_judge_model import parse_opinions, MAX_OUTPUT_BYTES


def started(e):
    return checked(e.client.post(e.base + '/narrative-judge/runs', headers=e.headers, json={
        'chapter_ids': [e.chapter['id']], 'expected_versions': {e.chapter['id']: e.chapter['version']}}), 201)


def action(e, row, name, **extra):
    return checked(e.client.post(e.base + f'/narrative-judge/runs/{row["id"]}/model/{name}', headers=e.headers,
        json={'expected_version': row['version'], **extra}))


def ready(e):
    row = started(e)
    return action(e, row, 'preview', route_id=route(e)['route_id'])


def dispatched(e, row):
    return action(e, row, 'dispatch', reviewed_preview_digest=row['model_preview']['preview_digest'])


def refresh(e, row):
    wait_ledger(e, row['model_execution']['reservation_id'])
    return action(e, row, 'refresh')


def test_shipped_registered_judge_exact_payload_original_job_and_review(broker_app, monkeypatch):
    from app.runtime import runtime
    from app.author_request import request_payload
    e = broker_app; before = copy.deepcopy(e.chapters.get(e.chapter['id'])); captured = []
    adapter = runtime.provider_registry.resolve('mock'); original = adapter.stream_text
    def stream(request):
        captured.append(request_payload(request)); yield from original(request)
    monkeypatch.setattr(adapter, 'stream_text', stream)
    catalog = checked(e.client.get(e.base + '/narrative-judge/model/catalog', headers=e.headers))
    assert any(r['provider_id'] == 'mock' and r['synthetic'] for r in catalog['routes'])
    row = ready(e); preview = row['model_preview']
    assert not captured and not e.manager.jobs
    assert preview['request']['context'] == {} and preview['truncation'] == 'NONE'
    assert preview['actor'] == 'local-author' and preview['sources'][e.chapter['id']]['version'] == before['version']
    assert preview['rubric']['version'] == 1 and preview['independence'] == 'UNVERIFIED'
    assert json.loads(preview['author']['instruction'].split('NARRATIVE_JUDGE_REQUEST_V1\n', 1)[1])['chapters'][0]['content'] == before['content']
    assert preview['broker']['chosen']['price']['reserve_microusd'] == 0
    run = dispatched(e, row); result = refresh(e, run)
    assert captured == [preview['request']]
    assert len(e.manager.jobs) == 1
    assert result['model_execution']['status'] == 'COMPLETED'
    assert result['model_execution']['accounting']['status'] == 'SETTLED'
    assert result['model_execution']['accounting']['actual_microusd'] == 0
    assert result['model_execution']['applied'] is False
    job = e.manager.get(run['model_execution']['job_id'])
    assert job.experimental_origin == 'narrative_judge_model' and job.generation_max_output_bytes == MAX_OUTPUT_BYTES
    findings = [f for f in result['findings'] if f['origin'] == 'MODEL_ASSESSMENT']
    assert len(findings) == 1 and findings[0]['model']['synthetic']
    assert findings[0]['quality_verification'] == 'SYNTHETIC_PROTOCOL_ONLY'
    proof = findings[0]['evidence'][0]
    assert before['content'][proof['start']:proof['end']] == proof['quote']
    assert e.chapters.get(e.chapter['id']) == before
    replay = dispatched(e, row)
    assert replay['model_execution']['job_id'] == job.id and len(e.manager.jobs) == 1
    assert e.client.post(e.prefix + f'/generation/{job.id}/accept', headers=e.headers, json={}).status_code in {409, 422}
    reviewed = checked(e.client.post(e.base + f'/narrative-judge/findings/{findings[0]["id"]}/review', headers=e.headers,
        json={'expected_version': 1, 'action': 'ignore', 'reason': 'Synthetic protocol opinion; preserve the prose.'}))
    assert reviewed['decision'] == 'IGNORED' and e.chapters.get(e.chapter['id']) == before
    reopened = action(e, result, 'refresh')
    assert len(reopened['findings']) == len(result['findings'])


def test_judge_invalid_quote_discards_all_model_opinions_preserves_rules(broker_app, monkeypatch):
    from app.runtime import runtime
    e = broker_app
    bad = {'opinions': [{'category': 'PACING', 'explanation': 'test', 'suggestion': 'test', 'boundary': 'test',
        'evidence': [{'chapter_id': e.chapter['id'], 'chapter_version': e.chapter['version'], 'paragraph': 1, 'start': 0, 'end': 8, 'quote': 'invented'}]}]}
    monkeypatch.setattr(runtime.providers['mock'], 'stream', lambda *args, **kwargs: iter([json.dumps(bad)]))
    row = ready(e); rules = row['findings']; result = refresh(e, dispatched(e, row))
    assert result['model_execution']['status'] == 'FAILED'
    assert result['model_execution']['failure_code'] == 'JUDGE_OUTPUT_INVALID_OR_UNSUPPORTED_EVIDENCE'
    assert result['findings'] == rules


@pytest.mark.parametrize('output', ['```json\n{"opinions":[]}\n```', '{"opinions":[],"opinions":[]}', '{"opinions":[],"score":99}', '{"opinions":NaN}', '{"opinions":"none"}', '[]'])
def test_strict_bounded_judge_parser(output):
    with pytest.raises(ValueError): parse_opinions(output, {})


def test_judge_output_schema_rejects_coercion_and_limit():
    output = {'opinions': [{'category': 'PACING', 'explanation': 'test', 'suggestion': 'test', 'boundary': 'test',
        'evidence': [{'chapter_id': 'c', 'chapter_version': '1', 'paragraph': 1, 'start': 0, 'end': 1, 'quote': 'x'}]}]}
    with pytest.raises(ValueError): parse_opinions(json.dumps(output), {'c': {'version': 1, 'content': 'x'}})
    with pytest.raises(ValueError, match='LIMIT'): parse_opinions(' ' * (MAX_OUTPUT_BYTES + 1), {})
    assert parse_opinions('{"opinions":[]}', {}) == []


def test_judge_uncertain_admission_keeps_original_reservation_and_no_replay(broker_app, monkeypatch):
    e = broker_app; row = ready(e)
    monkeypatch.setattr(e.manager, 'start_prepared', lambda job: (_ for _ in ()).throw(ValueError('synthetic uncertain admission')))
    response = e.client.post(e.base + f'/narrative-judge/runs/{row["id"]}/model/dispatch', headers=e.headers,
        json={'expected_version': row['version'], 'reviewed_preview_digest': row['model_preview']['preview_digest']})
    assert response.status_code == 422
    current = checked(e.client.get(e.base + f'/narrative-judge/runs/{row["id"]}', headers=e.headers))
    assert current['model_execution']['status'] == 'UNKNOWN'
    replay = dispatched(e, row)
    assert replay['model_execution'] == current['model_execution'] and not e.manager.jobs
    refreshed = action(e, replay, 'refresh')
    assert refreshed['model_execution']['receipt_state'] == 'UNKNOWN_NO_AUTOMATIC_REPLAY'
    assert refreshed['model_execution']['accounting']['status'] == 'RESERVED'


def test_judge_parallel_dispatch_creates_one_original_job(broker_app):
    e = broker_app; row = ready(e)
    def send(_):
        return e.client.post(e.base + f'/narrative-judge/runs/{row["id"]}/model/dispatch', headers=e.headers,
            json={'expected_version': row['version'], 'reviewed_preview_digest': row['model_preview']['preview_digest']})
    with ThreadPoolExecutor(max_workers=2) as pool: results = list(pool.map(send, range(2)))
    assert all(r.status_code in {200, 409} for r in results) and any(r.status_code == 200 for r in results)
    assert len(e.manager.jobs) == 1 and len(e.broker.ledger(e.nid, e.scope, 'local-author')) == 1


def test_judge_stale_and_final_feature_revocation_prevent_sends(broker_app, monkeypatch):
    from app.runtime import runtime
    e = broker_app; row = ready(e); calls = []
    original = e.broker.guard_dispatch
    def revoke(*args, **kwargs):
        result = original(*args, **kwargs); monkeypatch.setenv('V1_ACCEPTANCE_MODE', 'true'); return result
    monkeypatch.setattr(e.broker, 'guard_dispatch', revoke)
    monkeypatch.setattr(runtime.providers['mock'], 'stream', lambda *args, **kwargs: (calls.append('unexpected') or iter(['bad'])))
    response = e.client.post(e.base + f'/narrative-judge/runs/{row["id"]}/model/dispatch', headers=e.headers,
        json={'expected_version': row['version'], 'reviewed_preview_digest': row['model_preview']['preview_digest']})
    assert response.status_code in {200, 404}
    for job in list(e.manager.jobs.values()):
        import time
        end = time.monotonic() + 5
        while job.status not in e.manager.terminal and time.monotonic() < end: time.sleep(.01)
    assert calls == []
    monkeypatch.setenv('V1_ACCEPTANCE_MODE', 'false')
    checked(e.client.put(e.prefix + f'/chapters/{e.chapter["id"]}', json={'version': e.chapter['version'], 'content': 'New synthetic chapter'}))
    stale = checked(e.client.get(e.base + f'/narrative-judge/runs/{row["id"]}', headers=e.headers))
    assert stale['stale'] and stale['model_preview'] is None and stale['findings'] == []
    assert e.chapter['content'] not in json.dumps(stale, ensure_ascii=False)


def test_judge_current_authority_flags_and_no_runtime_rules_still_work(broker_app, monkeypatch):
    e = broker_app; row = ready(e)
    path = e.base + f'/narrative-judge/runs/{row["id"]}/model/dispatch'
    payload = {'expected_version': row['version'], 'reviewed_preview_digest': row['model_preview']['preview_digest']}
    assert e.client.post(path, json=payload).status_code == 401
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'narrative_quality_judge_v2,world_character_engines_v2,advanced_planning_v2,unified_review_inbox')
    assert e.client.get(e.base + '/narrative-judge/catalog', headers=e.headers).status_code == 200
    assert e.client.post(path, headers=e.headers, json=payload).status_code == 404
    assert not e.manager.jobs
    monkeypatch.setenv('V1_ACCEPTANCE_MODE', 'true')
    assert e.client.get(e.base + '/narrative-judge/catalog', headers=e.headers).status_code == 404


def test_judge_cancel_discards_late_output_and_restart_cannot_republish(broker_app, monkeypatch):
    from threading import Event
    from app.runtime import runtime
    from app.jobs import JobManager
    e = broker_app; begun = Event(); release = Event()
    def stream(*args, **kwargs):
        begun.set(); assert release.wait(5); yield '{"opinions":[]}'
    monkeypatch.setattr(runtime.providers['mock'], 'stream', stream)
    row = dispatched(e, ready(e))
    try:
        assert begun.wait(5)
        cancelled = action(e, row, 'cancel')
        assert cancelled['model_execution']['status'] == 'CANCELLED'
    finally: release.set()
    result = refresh(e, cancelled)
    assert result['model_execution']['status'] == 'CANCELLED'
    assert e.manager.get(row['model_execution']['job_id']).output == ''
    restarted = JobManager(generations=e.manager.persistence, chapters=e.chapters, contexts=e.manager.contexts, canon=e.canon, snapshot_required=False)
    monkeypatch.setattr(e.experimental.narrative_judge_service.model_coordinator, 'manager', restarted)
    assert dispatched(e, row)['model_execution']['job_id'] == row['model_execution']['job_id']


def test_judge_source_version_and_budget_changed_since_preview(broker_app):
    e = broker_app; row = ready(e)
    checked(e.client.put(e.base + '/model-broker/budget', headers=e.headers, json={'expected_version': 0, 'limit_microusd': 0, 'max_inflight': 1, 'require_known_estimate': True}))
    response = e.client.post(e.base + f'/narrative-judge/runs/{row["id"]}/model/dispatch', headers=e.headers,
        json={'expected_version': row['version'], 'reviewed_preview_digest': row['model_preview']['preview_digest']})
    assert response.status_code == 409 and not e.manager.jobs
    assert not e.broker.ledger(e.nid, e.scope, 'local-author')


def test_judge_model_unselected_context_and_branch_never_fall_back(broker_app, monkeypatch):
    e = scoped(broker_app, monkeypatch)
    assert e.client.get(e.base + '/narrative-judge/catalog', headers=e.headers).json()['chapters'] == []
    response = e.client.post(e.base + '/narrative-judge/runs', headers=e.headers,
        json={'chapter_ids': [e.chapter['id']], 'expected_versions': {e.chapter['id']: e.chapter['version']}})
    assert response.status_code == 404 and not e.manager.jobs


def test_judge_restart_without_live_authority_does_not_publish_or_replay(broker_app, monkeypatch):
    from app.jobs import JobManager
    e = broker_app; preview = ready(e); row = dispatched(e, preview)
    wait_ledger(e, row['model_execution']['reservation_id'])
    restarted = JobManager(generations=e.manager.persistence, chapters=e.chapters, contexts=e.manager.contexts, canon=e.canon, snapshot_required=False)
    monkeypatch.setattr(e.experimental.narrative_judge_service.model_coordinator, 'manager', restarted)
    current = action(e, row, 'refresh')
    assert current['model_execution']['status'] == 'UNKNOWN'
    assert current['model_execution']['receipt_state'] == 'UNKNOWN_NO_AUTOMATIC_REPLAY'
    assert not any(f['origin'] == 'MODEL_ASSESSMENT' for f in current['findings'])
    again = dispatched(e, preview)
    assert again['model_execution']['job_id'] == row['model_execution']['job_id'] and len(restarted.jobs) == 1


def test_judge_large_stream_is_discarded_before_model_review(broker_app, monkeypatch):
    from app.runtime import runtime
    e = broker_app
    monkeypatch.setattr(runtime.providers['mock'], 'stream', lambda *a, **k: iter(['x' * (MAX_OUTPUT_BYTES + 1)]))
    row = dispatched(e, ready(e)); result = refresh(e, row)
    assert result['model_execution']['status'] == 'FAILED'
    assert result['model_execution']['failure_code'] == 'GENERATION_OUTPUT_LIMIT'
    assert e.manager.get(row['model_execution']['job_id']).output == ''
    assert not any(f['origin'] == 'MODEL_ASSESSMENT' for f in result['findings'])


def test_judge_selected_evidence_omits_unselected_chapter_and_rejects_late_source(broker_app):
    e = broker_app
    other = checked(e.client.post(e.prefix + f'/novels/{e.nid}/chapters', json={'title': 'Hidden from selection', 'content': 'UNSELECTED_SYNTHETIC_SECRET_MARKER'}), 201)
    row = ready(e)
    assert 'UNSELECTED_SYNTHETIC_SECRET_MARKER' not in json.dumps(row['model_preview'], ensure_ascii=False)
    assert other['id'] not in row['model_preview']['sources']
    checked(e.client.put(e.prefix + f'/chapters/{e.chapter["id"]}', json={'version': e.chapter['version'], 'content': 'Changed selected saved source'}))
    response = e.client.post(e.base + f'/narrative-judge/runs/{row["id"]}/model/dispatch', headers=e.headers,
        json={'expected_version': row['version'], 'reviewed_preview_digest': row['model_preview']['preview_digest']})
    assert response.status_code == 409 and not e.manager.jobs


def test_judge_disabled_registered_route_is_not_sent(broker_app):
    from dataclasses import replace
    from app.runtime import runtime
    e = broker_app; row = ready(e)
    model = next(m for m in runtime.model_registry.descriptors() if m.provider_id == 'mock')
    runtime.model_registry.register(replace(model, enabled=False), replace=True)
    try:
        response = e.client.post(e.base + f'/narrative-judge/runs/{row["id"]}/model/dispatch', headers=e.headers,
            json={'expected_version': row['version'], 'reviewed_preview_digest': row['model_preview']['preview_digest']})
        assert response.status_code in {409, 422} and not e.manager.jobs
    finally: runtime.model_registry.register(model, replace=True)


def test_judge_current_actor_and_stale_conflict_never_leak_old_prompt(broker_app, monkeypatch):
    e = broker_app; row = ready(e)
    # Current owner authority is bound in addition to the visible run/source.
    coordinator = e.experimental.narrative_judge_service.model_coordinator
    from app.experimental.ux import ReadContext
    with pytest.raises(ValueError, match='ACTOR'):
        coordinator._row(ReadContext(e.nid, e.scope, 'another-actor', 'broker-host', None), row['id'], lambda: None)
    running = dispatched(e, row)
    wait_ledger(e, running['model_execution']['reservation_id'])
    checked(e.client.put(e.prefix + f'/chapters/{e.chapter["id"]}', json={'version': e.chapter['version'], 'content': 'Changed selected saved source'}))
    response = e.client.post(e.base + f'/narrative-judge/runs/{row["id"]}/model/cancel', headers=e.headers, json={'expected_version': 1})
    assert response.status_code == 409
    assert 'model_preview' not in response.text and 'instruction' not in response.text
    cancelled = action(e, running, 'cancel')
    assert cancelled['stale'] and cancelled['model_preview'] is None and cancelled['model_execution']['status'] == 'CANCELLED'
