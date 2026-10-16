"""Known generation-origin OFF/V1 regression repairs, not provider testing."""
import copy
import json

import pytest

from app.jobs import Job, generation_required_features, mark_generation_origin
from test_r3_mounted_contracts import mounted, prefix, checked
from test_r4_broker_mounted import broker_app, quote, author_body, wait_ledger


def complete_broker(e):
    selected = quote(e); body = author_body(e)
    preview = checked(e.client.post(e.base + '/author-context/preview', headers=e.headers, json=body))
    result = checked(e.client.post(e.base + '/model-broker/generate', headers=e.headers, json={
        'preview_id': selected['id'], 'expected_version': selected['version'], 'request_id': 'origin-repair',
        'author': {**body, 'preview_digest': preview['preview_digest']}}), 202)
    state = wait_ledger(e, result['reservation_id'])
    return result, state


@pytest.mark.parametrize('origin', ['broker', 'older_broker', 'older_preview', 'older_character'])
@pytest.mark.parametrize('off', ['disabled', 'v1'])
def test_all_generation_content_routes_obey_current_origin_flags(broker_app, monkeypatch, origin, off):
    e = broker_app; created, _ = complete_broker(e)
    value = e.manager.get(created['job_id'])
    if origin.startswith('older_'):
        value.experimental_origin = None; value.required_experimental_features = []
        if origin != 'older_broker': value.dispatch_hooks_required = False
        if origin == 'older_character': value.character_viewpoint = {'character_id': 'alice', 'chapter_id': e.chapter['id']}
    value.variant_group_id = 'origin-group'
    e.manager._persist(value)
    if origin.startswith('older_'):
        value = Job(**e.manager.persistence.get(value.id))
        e.manager.jobs[value.id] = value
    before = copy.deepcopy(e.chapters.list(e.nid))
    if off == 'disabled': monkeypatch.setenv('EXPERIMENTAL_FEATURES', '')
    else: monkeypatch.setenv('V1_ACCEPTANCE_MODE', 'true')
    base = e.prefix + '/generation/' + value.id
    for path in (base, base + '/events', e.prefix + '/generation-groups/origin-group'):
        response = e.client.get(path, headers=e.headers)
        assert response.status_code == 404, response.text
        assert value.output not in response.text
    for action in ('accept', 'reject', 'retry'):
        response = e.client.post(base + '/' + action, headers=e.headers,
            json={'content': 'Must not be accepted', 'expected_version': e.chapter['version']} if action == 'accept' else None)
        assert response.status_code == 404, response.text
    with pytest.raises(Exception) as exc: e.manager.diff(value.id)
    assert getattr(exc.value, 'status_code', None) == 404
    assert e.chapters.list(e.nid) == before and value.status == 'COMPLETED'
    cancelled = checked(e.client.post(base + '/cancel', headers=e.headers))
    assert cancelled == {'id': value.id, 'status': 'COMPLETED', 'cancellation_requested': True, 'content_available': False}
    assert value.cancelled.is_set()


def test_disabling_only_broker_or_mind_retains_specific_origin_fences(broker_app, monkeypatch):
    e = broker_app; created, _ = complete_broker(e); value = e.manager.get(created['job_id'])
    assert value.experimental_origin == 'model_broker'
    assert set(value.required_experimental_features) >= {'model_broker_v2', 'author_context_inspector_v2'}
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'author_context_inspector_v2')
    assert e.client.get(e.prefix + '/generation/' + value.id, headers=e.headers).status_code == 404
    # An older character receipt cannot be downgraded to ordinary U08 just
    # because its new origin stamp is absent after a software upgrade.
    value.experimental_origin = None; value.required_experimental_features = []; value.dispatch_hooks_required = False
    value.character_viewpoint = {'character_id': 'alice', 'chapter_id': e.chapter['id']}
    assert 'character_mind_v2' in generation_required_features(value)
    assert e.client.get(e.prefix + '/generation/' + value.id, headers=e.headers).status_code == 404


def test_existing_stream_stops_before_any_disabled_content_is_yielded(broker_app, monkeypatch):
    e = broker_app; created, _ = complete_broker(e); value = e.manager.get(created['job_id'])
    value.status = 'GENERATING'; value.output = 'First authorized fragment'
    stream = e.manager.events(value.id)
    assert 'First authorized fragment' in next(stream)
    value.output += ' LATER_DISABLED_SECRET'
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', '')
    with pytest.raises(StopIteration): next(stream)
    value.status = 'COMPLETED'


def test_disabled_broker_recovery_is_authorized_and_never_returns_draft_content(broker_app, monkeypatch):
    e = broker_app; created, _ = complete_broker(e); value = e.manager.get(created['job_id'])
    monkeypatch.setenv('V1_ACCEPTANCE_MODE', 'true')
    base = e.base + '/model-broker/jobs/' + created['reservation_id']
    assert e.client.get(base).status_code == 401
    receipt = checked(e.client.get(base, headers=e.headers))
    assert receipt['recovery'] == 'FEATURE_DISABLED_CONTENT_HIDDEN'
    assert receipt['job'] == {'id': value.id, 'status': 'COMPLETED', 'content_available': False}
    assert value.output not in json.dumps(receipt)
    assert not set(receipt['ledger']) & {'route_id', 'provider_id', 'model_id', 'preview_id', 'price', 'history'}
    cancelled = checked(e.client.post(base + '/cancel', headers=e.headers, json={'expected_version': receipt['ledger']['version']}))
    assert cancelled['job']['content_available'] is False and value.output not in json.dumps(cancelled)


def test_origin_fields_are_server_bound_not_copied_from_generation_payload(broker_app, monkeypatch):
    e = broker_app
    prepared = e.manager.prepare_job('continue', {'novel_id': e.nid, 'chapter_id': e.chapter['id'], 'profile': 'LOCAL_ONLY',
        'experimental_origin': 'model_broker', 'required_experimental_features': ['model_broker_v2'], 'dispatch_hooks_required': True, 'execution_outcome': 'COMPLETED'})
    assert prepared.experimental_origin is None and prepared.required_experimental_features == []
    assert prepared.dispatch_hooks_required is False and prepared.execution_outcome is None and not generation_required_features(prepared)
    mark_generation_origin(prepared, 'author_context')
    restored = Job(**prepared.public())
    assert restored.experimental_origin == 'author_context'
    assert generation_required_features(restored) == {'author_context_inspector_v2'}
    assert not callable(restored.request_authorization)


def test_plain_v1_jobs_keep_legacy_read_diff_accept_with_all_experiments_off(broker_app, monkeypatch):
    e = broker_app; current = e.chapters.get(e.chapter['id'])
    plain = Job('ordinary-v1', 'continue', e.nid, current['id'], 'ordinary user instruction', 'LOCAL_ONLY',
        output='Ordinary V1 draft', status='COMPLETED', base_chapter_version=current['version'])
    e.manager.jobs[plain.id] = plain; e.manager._persist(plain)
    for key, value in (('memory_extractor', None), ('canon', e.canon), ('collaboration_updates', None)):
        monkeypatch.setattr(e.manager, key, value)
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', ''); monkeypatch.setenv('V1_ACCEPTANCE_MODE', 'true')
    response = checked(e.client.get(e.prefix + '/generation/' + plain.id, headers=e.headers))
    assert response['output'] == plain.output and 'experimental_origin' not in response
    result = checked(e.client.post(e.prefix + '/generation/' + plain.id + '/accept', headers=e.headers,
        json={'content': plain.output, 'expected_version': current['version']}))
    assert plain.status == 'ACCEPTED' and plain.output in result['chapter']['content']


def test_orphan_accounting_reconciliation_remains_available_when_generation_is_off(broker_app, monkeypatch):
    e = broker_app
    selected = quote(e)
    entry = e.broker.reserve(e.nid, e.scope, 'local-author', selected['id'], selected['version'], 'orphan-off', 'missing-executor')
    entry = e.broker.guard_dispatch(e.nid, e.scope, 'local-author', entry['id'], entry['job_id'])
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', '')
    before = checked(e.client.get(e.base + '/model-broker/jobs/' + entry['id'], headers=e.headers))
    assert before['orphan_reconciliation_available'] is True
    result = checked(e.client.post(e.base + '/model-broker/ledger/' + entry['id'] + '/reconcile', headers=e.headers,
        json={'expected_version': entry['version'], 'actual_microusd': 0, 'upstream_terminal_confirmed': True, 'original_executor_stopped_confirmed': True, 'evidence_note': 'Synthetic confirmed terminal invoice.'}))
    assert result['status'] == 'RECONCILED'
    assert not set(result) & {'price', 'history', 'provider_id', 'route_id', 'reconciliation_note'}


def test_persisted_settling_restores_failed_without_dispatch_or_releasing_ledger(broker_app, monkeypatch):
    from app.jobs import JobManager
    e = broker_app
    selected = quote(e)
    value = e.manager.prepare_job('continue', {'novel_id': e.nid, 'chapter_id': e.chapter['id'], 'profile': 'LOCAL_ONLY'})
    mark_generation_origin(value, 'model_broker')
    value.status = 'SETTLING'; value.dispatch_hooks_required = True; value.execution_outcome = 'COMPLETED'
    value.output = 'Completed draft, unconfirmed accounting'
    e.manager._persist(value)
    ledger = e.broker.reserve(e.nid, e.scope, 'local-author', selected['id'], selected['version'], 'settling-restart', value.id)
    ledger = e.broker.guard_dispatch(e.nid, e.scope, 'local-author', ledger['id'], value.id)
    restored_manager = JobManager(generations=e.manager.persistence, chapters=e.chapters, contexts=e.manager.contexts,
        canon=e.canon, memory_extractor=object(), snapshot_required=False)
    restored = restored_manager.get(value.id)
    assert restored.status == 'FAILED' and restored.execution_outcome == 'COMPLETED'
    assert restored.terminal_hook_status == 'MISSING_RECONCILIATION_REQUIRED'
    assert restored.error_code == 'GENERATION_SETTLEMENT_RECOVERY_REQUIRED'
    assert restored.output == value.output
    assert restored.before_dispatch is None and restored.on_terminal is None
    assert e.broker.get(e.nid, e.scope, e.broker.LEDGER, ledger['id']) == ledger
    with pytest.raises(ValueError): restored_manager.start_prepared(restored)
    monkeypatch.setattr(e.manager, 'jobs', restored_manager.jobs)
    response = checked(e.client.get(e.base + '/model-broker/jobs/' + ledger['id'], headers=e.headers))
    assert response['orphan_reconciliation_available'] is True
    assert response['ledger']['status'] == 'DISPATCHED'


def test_completion_receipt_stays_settling_until_accounting_is_confirmed(broker_app, monkeypatch):
    from threading import Event
    from concurrent.futures import ThreadPoolExecutor
    e = broker_app; entered = Event(); release = Event()
    original = e.broker.finalize
    def paused(*args, **kwargs):
        entered.set()
        assert release.wait(5)
        return original(*args, **kwargs)
    monkeypatch.setattr(e.broker, 'finalize', paused)
    for key, value in (('memory_extractor', None), ('canon', e.canon), ('collaboration_updates', None)):
        monkeypatch.setattr(e.manager, key, value)
    selected = quote(e); body = author_body(e)
    preview = checked(e.client.post(e.base + '/author-context/preview', headers=e.headers, json=body))
    result = checked(e.client.post(e.base + '/model-broker/generate', headers=e.headers, json={
        'preview_id': selected['id'], 'expected_version': selected['version'], 'request_id': 'pause-settlement',
        'author': {**body, 'preview_digest': preview['preview_digest']}}), 202)
    try:
        assert entered.wait(5)
        value = e.manager.get(result['job_id'])
        assert value.public()['status'] == 'SETTLING'
        current = checked(e.client.get(e.prefix + '/generation/' + value.id, headers=e.headers))
        assert current['status'] == 'SETTLING'
        with ThreadPoolExecutor(max_workers=1) as pool:
            accepted = pool.submit(e.client.post, e.prefix + '/generation/' + value.id + '/accept', headers=e.headers,
                json={'content': 'Reviewed output after accounting', 'expected_version': e.chapter['version']})
            release.set()
            assert accepted.result(timeout=5).status_code == 200
        assert value.status == 'ACCEPTED' and value.execution_outcome == 'COMPLETED'
        assert value.terminal_hook_status == 'COMPLETED'
    finally:
        release.set()
