"""Original production composition, both API prefixes and actual File/opt-in PG.

All provider text is shipped synthetic protocol or explicitly captured synthetic
transport. This suite establishes admission/review safety, not language quality.
"""
import copy
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from test_r3_mounted_contracts import mounted, prefix, checked, scoped
from test_r4_broker_mounted import broker_app, route, wait_ledger


@pytest.fixture
def translation(broker_app):
    e = broker_app
    e.path = e.base + '/language-editions'
    e.translation = e.experimental.multilingual_editions_service.translation_coordinator
    # Use exact rich-text body paragraphs, without the created heading.
    chapter = checked(e.client.put(e.prefix + '/chapters/' + e.chapter['id'], json={
        'version': e.chapter['version'], 'document': {'type': 'doc', 'content': [
            {'type': 'paragraph', 'content': [{'type': 'text', 'text': '阿青🙂é走向港口。'}]},
            {'type': 'paragraph', 'content': [{'type': 'text', 'text': 'EXCLUDED_OTHER_PARAGRAPH'}]}]}}))
    e.chapter = chapter
    e.edition = checked(e.client.post(e.path, headers=e.headers, json={'title': 'Synthetic Arabic', 'source_language': 'zh-Hant', 'target_language': 'ar',
        'style_note': 'SYNTHETIC_PRIVATE_STYLE', 'chapters': [{'chapter_id': chapter['id'], 'chapter_version': chapter['version']}]}), 201)
    return e


def preview(e, edition=None, **extra):
    row = edition or e.edition
    return checked(e.client.post(e.path + f'/{row["id"]}/segments/{row["segments"][0]["id"]}/translation-preview', headers=e.headers,
        json={'expected_version': row['version'], 'route_id': route(e)['route_id'], 'allow_synthetic': True, **extra}), 201)


def action(e, row, name, **extra):
    return checked(e.client.post(e.path + f'/{row["edition_id"]}/translations/{row["id"]}/{name}', headers=e.headers,
        json={'expected_version': row['version'], **extra}))


def dispatch(e, row): return action(e, row, 'dispatch', reviewed_preview_digest=row['preview']['preview_digest'])
def settle(e, row):
    wait_ledger(e, row['execution']['reservation_id'])
    return action(e, row, 'refresh')

def current(e, row):
    return next(r for r in checked(e.client.get(e.path + f'/{row["edition_id"]}/translations', headers=e.headers))['items'] if r['id'] == row['id'])

def adopt(e, row, version=None):
    return action(e, row, 'adopt', expected_edition_version=version or row['edition_version'], candidate_digest=row['candidate']['digest'])


def test_exact_saved_segment_approved_terms_capture_original_job_and_draft_only_adoption(translation, monkeypatch):
    from app.runtime import runtime
    e = translation; original = copy.deepcopy(e.chapters.get(e.chapter['id'])); calls = []
    path = e.path + '/' + e.edition['id']
    e.edition = checked(e.client.post(path + '/rules', headers=e.headers, json={'expected_version': e.edition['version'],
        'source_term': '阿青', 'source_aliases': ['青儿'], 'preferred': 'تشينغ', 'target_aliases': ['Qing'], 'forbidden': ['WrongName'], 'strategy': 'transliteration'}))
    e.edition = checked(e.client.post(path + f'/rules/{e.edition["rules"][0]["id"]}/review', headers=e.headers,
        json={'expected_version': e.edition['version'], 'action': 'approve'}))
    e.edition = checked(e.client.post(path + '/rules', headers=e.headers, json={'expected_version': e.edition['version'], 'source_term': 'UNAPPROVED_SECRET', 'preferred': 'UNAPPROVED_TARGET'}))
    def stream(request, *args, **kwargs):
        calls.append(request); yield 'تشينغ وصل إلى الميناء 🙂é'
    monkeypatch.setattr(runtime.providers['mock'], 'stream', stream)
    adapter = runtime.provider_registry.resolve('mock'); transport = []; original_stream = adapter.stream_text
    def captured(request):
        transport.append(request); yield from original_stream(request)
    monkeypatch.setattr(adapter, 'stream_text', captured)
    row = preview(e); p = row['preview']
    assert p['request']['context'] == {} and p['execution_available']
    assert '阿青🙂é走向港口。' in p['request']['prompt']
    assert 'SYNTHETIC_PRIVATE_STYLE' in p['request']['prompt'] and 'تشينغ' in p['request']['prompt'] and '青儿' in p['request']['prompt']
    assert 'UNAPPROVED_SECRET' not in str(p['request']) and 'EXCLUDED_OTHER_PARAGRAPH' not in str(p['request'])
    assert not e.manager.jobs and not calls
    run = dispatch(e, row); same = dispatch(e, row)
    assert same['execution']['job_id'] == run['execution']['job_id'] and len(e.manager.jobs) == 1
    candidate = settle(e, run)
    assert candidate['status'] == 'CANDIDATE' and candidate['candidate']['text'] == 'تشينغ وصل إلى الميناء 🙂é'
    assert calls[0] == p['request']['prompt'] and len(calls) == 1
    from app.author_request import request_payload
    assert request_payload(transport[0]) == p['request'] and len(transport) == 1
    assert candidate['execution']['accounting']['status'] == 'SETTLED'
    job = e.manager.get(run['execution']['job_id'])
    assert job.experimental_origin == 'multilingual_translation'
    assert e.client.post(e.prefix + f'/generation/{job.id}/accept', headers=e.headers, json={}).status_code in {409, 422}
    adopted = adopt(e, candidate)
    assert adopted['version'] == e.edition['version'] + 1 and adopted['segments'][0]['status'] == 'DRAFT'
    assert adopted['segments'][0]['target_text'] == candidate['candidate']['text'] and adopted['segments'][1]['target_text'] == ''
    assert adopted['segments'][0]['translation_provenance']['job_id'] == job.id
    assert e.chapters.get(e.chapter['id']) == original
    assert current(e, run)['status'] == 'ADOPTED'
    sid = adopted['segments'][0]['id']; segment_path = path + f'/segments/{sid}'
    adopted = checked(e.client.post(segment_path + '/review', headers=e.headers, json={'expected_version': adopted['version'], 'action': 'submit'}))
    receipt = checked(e.client.post(segment_path + '/preview', headers=e.headers, json={'expected_version': adopted['version']}))
    reviewed = checked(e.client.post(segment_path + '/review', headers=e.headers, json={'expected_version': adopted['version'], 'action': 'accept', 'preview_digest': receipt['preview_digest']}))
    assert reviewed['segments'][0]['status'] == 'ACCEPTED' and not reviewed['checks']['can_export']
    assert e.chapters.get(e.chapter['id']) == original


def test_manual_cas_change_withholds_candidate_and_never_overwrites(translation):
    e = translation; row = settle(e, dispatch(e, preview(e)))
    original = copy.deepcopy(e.chapters.get(e.chapter['id']))
    edited = checked(e.client.put(e.path + f'/{e.edition["id"]}/segments/{e.edition["segments"][0]["id"]}', headers=e.headers,
        json={'expected_version': e.edition['version'], 'text': 'Manual newer Arabic 🙂'}))
    assert current(e, row)['content_withheld'] and current(e, row)['candidate'] is None
    response = e.client.post(e.path + f'/{e.edition["id"]}/translations/{row["id"]}/adopt', headers=e.headers,
        json={'expected_version': row['version'], 'expected_edition_version': edited['version'], 'candidate_digest': row['candidate']['digest']})
    assert response.status_code == 409 and 'Manual newer Arabic' not in response.text
    assert checked(e.client.get(e.path + '/' + e.edition['id'], headers=e.headers))['segments'][0]['target_text'] == 'Manual newer Arabic 🙂'
    assert e.chapters.get(e.chapter['id']) == original


def test_changed_source_blocks_dispatch_and_hides_exact_preview(translation):
    e = translation; row = preview(e)
    checked(e.client.put(e.prefix + '/chapters/' + e.chapter['id'], json={'version': e.chapter['version'], 'content': 'New source'}))
    response = e.client.post(e.path + f'/{e.edition["id"]}/translations/{row["id"]}/dispatch', headers=e.headers,
        json={'expected_version': row['version'], 'reviewed_preview_digest': row['preview']['preview_digest']})
    assert response.status_code == 409 and not e.manager.jobs
    assert current(e, row)['preview'] is None


def test_lost_admission_recovers_same_identity_and_blocks_blind_replacement(translation, monkeypatch):
    e = translation; row = preview(e)
    monkeypatch.setattr(e.manager, 'start_prepared', lambda job: (_ for _ in ()).throw(ValueError('SYNTHETIC_LOST_ADMISSION')))
    response = e.client.post(e.path + f'/{e.edition["id"]}/translations/{row["id"]}/dispatch', headers=e.headers,
        json={'expected_version': row['version'], 'reviewed_preview_digest': row['preview']['preview_digest']})
    assert response.status_code == 422
    recovered = current(e, row); assert recovered['status'] == 'UNKNOWN'
    assert dispatch(e, row)['execution']['job_id'] == recovered['execution']['job_id']
    fresh = preview(e)
    response = e.client.post(e.path + f'/{e.edition["id"]}/translations/{fresh["id"]}/dispatch', headers=e.headers,
        json={'expected_version': fresh['version'], 'reviewed_preview_digest': fresh['preview']['preview_digest']})
    assert response.status_code == 422 and 'REQUIRES_RECOVERY' in response.text
    assert len(e.broker.ledger(e.nid, e.scope, 'local-author')) == 1 and not e.manager.jobs
    result = action(e, recovered, 'refresh')
    assert result['status'] == 'UNKNOWN' and result['execution']['accounting']['status'] == 'RESERVED'


def test_parallel_dispatch_one_job_one_ledger(translation):
    e = translation; row = preview(e)
    url = e.path + f'/{e.edition["id"]}/translations/{row["id"]}/dispatch'
    payload = {'expected_version': row['version'], 'reviewed_preview_digest': row['preview']['preview_digest']}
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: e.client.post(url, headers=e.headers, json=payload), range(2)))
    assert all(r.status_code in {200, 409} for r in results) and any(r.status_code == 200 for r in results)
    assert len(e.manager.jobs) == 1 and len(e.broker.ledger(e.nid, e.scope, 'local-author')) == 1
    assert settle(e, current(e, row))['status'] == 'CANDIDATE'


def test_cancel_late_output_and_source_revocation(translation, monkeypatch):
    from app.runtime import runtime
    e = translation; started, release = Event(), Event()
    def stream(*args, **kwargs): started.set(); assert release.wait(5); yield 'Synthetic late Arabic'
    monkeypatch.setattr(runtime.providers['mock'], 'stream', stream)
    run = dispatch(e, preview(e))
    try:
        assert started.wait(5)
        cancelled = action(e, run, 'cancel')
    finally: release.set()
    row = settle(e, cancelled)
    assert row['status'] == 'CANCELLED' and row['candidate'] is None
    assert e.manager.get(row['execution']['job_id']).output == ''
    assert checked(e.client.get(e.path + '/' + e.edition['id'], headers=e.headers))['segments'][0]['target_text'] == ''


def test_oversized_and_restarted_results_never_become_candidates(translation, monkeypatch):
    from app.runtime import runtime
    from app.jobs import JobManager
    e = translation
    monkeypatch.setattr(runtime.providers['mock'], 'stream', lambda *a, **k: iter(['合' * 7000]))
    run = dispatch(e, preview(e)); result = settle(e, run)
    assert result['status'] == 'FAILED' and result['candidate'] is None
    assert e.manager.get(run['execution']['job_id']).output == ''
    monkeypatch.setattr(runtime.providers['mock'], 'stream', lambda *a, **k: iter(['Synthetic candidate']))
    run = dispatch(e, preview(e)); wait_ledger(e, run['execution']['reservation_id'])
    restarted = JobManager(generations=e.manager.persistence, chapters=e.chapters, contexts=e.manager.contexts, canon=e.canon, snapshot_required=False)
    monkeypatch.setattr(e.translation, 'manager', restarted)
    result = action(e, run, 'refresh')
    assert result['status'] == 'UNKNOWN' and result['candidate'] is None
    assert result['execution']['receipt_state'] == 'UNKNOWN_NO_AUTOMATIC_REPLAY'
    assert dispatch(e, run)['execution']['job_id'] == run['execution']['job_id']


def test_missing_host_flags_and_synthetic_opt_in_fail_closed(translation, monkeypatch):
    e = translation
    assert e.client.get(e.path + '/translation/routes').status_code == 401
    row = preview(e, allow_synthetic=False)
    assert row['status'] == 'BLOCKED' and not row['preview']['execution_available']
    assert row['preview']['request'] is None and not e.manager.jobs
    for flags, acceptance in [('', 'false'), ('*', 'false'), ('multilingual_editions_v2', 'false'), ('multilingual_editions_v2,model_broker_v2,author_context_inspector_v2', 'true')]:
        monkeypatch.setenv('EXPERIMENTAL_FEATURES', flags); monkeypatch.setenv('V1_ACCEPTANCE_MODE', acceptance)
        assert e.client.get(e.path + '/translation/routes', headers=e.headers).status_code == 404
    assert not e.manager.jobs


def test_route_revocation_after_completion_hides_and_blocks_candidate(translation, monkeypatch):
    e = translation; row = settle(e, dispatch(e, preview(e)))
    original = e.broker.current_route
    monkeypatch.setattr(e.broker, 'current_route', lambda rid: {**original(rid), 'available': False})
    hidden = current(e, row); assert hidden['content_withheld'] and hidden['candidate'] is None
    response = e.client.post(e.path + f'/{e.edition["id"]}/translations/{row["id"]}/adopt', headers=e.headers,
        json={'expected_version': row['version'], 'expected_edition_version': row['edition_version'], 'candidate_digest': row['candidate']['digest']})
    assert response.status_code == 409


def test_unknown_nonzero_or_cloud_price_routes_never_prepare_or_send(translation, monkeypatch):
    e = translation
    original_price = e.broker._price
    for price in [None, {'reserve_microusd': 5, 'currency': 'USD'}, {'reserve_microusd': 0, 'currency': 'USD', 'input_per_million_microusd': None, 'output_per_million_microusd': None}]:
        monkeypatch.setattr(e.broker, '_price', lambda *args, value=price: value)
        row = preview(e)
        assert row['status'] == 'BLOCKED' and row['preview']['request'] is None
    monkeypatch.setattr(e.broker, '_price', original_price)
    original_candidates = e.broker.candidates
    monkeypatch.setattr(e.broker, 'candidates', lambda: [{**r, 'cloud': True} for r in original_candidates()])
    row = preview(e)
    assert row['status'] == 'BLOCKED' and row['preview']['request'] is None and not e.manager.jobs


def test_last_hop_feature_revocation_prevents_send(translation, monkeypatch):
    import time
    from app.runtime import runtime
    e = translation; calls = []; row = preview(e)
    original = e.broker.guard_dispatch
    monkeypatch.setattr(runtime.providers['mock'], 'stream', lambda *a, **k: (calls.append('send') or iter(['Must not run'])))
    def revoked(*args, **kwargs):
        monkeypatch.setenv('EXPERIMENTAL_FEATURES', '')
        return original(*args, **kwargs)
    monkeypatch.setattr(e.broker, 'guard_dispatch', revoked)
    response = e.client.post(e.path + f'/{e.edition["id"]}/translations/{row["id"]}/dispatch', headers=e.headers,
        json={'expected_version': row['version'], 'reviewed_preview_digest': row['preview']['preview_digest']})
    assert response.status_code in {200, 404}
    stored = e.store.read(e.nid, e.scope)['collections'][e.translation.RUNS][row['id']]
    job = e.manager.get(stored['execution']['job_id'])
    deadline = time.monotonic() + 5
    while (job.status not in e.manager.terminal or job.terminal_hook_status is None) and time.monotonic() < deadline: time.sleep(.01)
    assert not calls and not job.output and job.status == 'FAILED'
    ledger = e.broker.get(e.nid, e.scope, e.broker.LEDGER, stored['execution']['reservation_id'])
    assert ledger['status'] == 'RELEASED' and not ledger['dispatched']


def test_late_source_change_and_changed_deadline_discard_output(translation):
    e = translation; run = dispatch(e, preview(e)); wait_ledger(e, run['execution']['reservation_id'])
    with e.store.transaction(e.nid, e.scope) as state:
        state['collections'][e.translation.RUNS][run['id']]['execution']['deadline'] = '2000-01-01T00:00:00+00:00'
    result = action(e, run, 'refresh'); assert result['status'] == 'FAILED' and result['candidate'] is None
    run = dispatch(e, preview(e)); wait_ledger(e, run['execution']['reservation_id'])
    checked(e.client.put(e.prefix + '/chapters/' + e.chapter['id'], json={'version': e.chapter['version'], 'content': 'Source changed after inference'}))
    result = action(e, run, 'refresh')
    assert result['status'] == 'FAILED' and result['content_withheld'] and result['candidate'] is None
    assert not e.store.read(e.nid, e.scope)['collections'][e.experimental.multilingual_editions_service.COLLECTION][e.edition['id']]['segments'][0]['target_text']


def test_current_branch_actor_authority_not_base_source_fallback(translation, monkeypatch):
    e = scoped(translation, monkeypatch)
    assert e.client.get(e.path + '/translation/routes', headers=e.viewer_headers).status_code == 403
    assert e.client.get(e.path + '/' + e.edition['id'] + '/translations', headers=e.headers).status_code == 404
    e.authorization.revoke_role(e.role, e.lead)
    assert e.client.get(e.path + '/translation/routes', headers=e.headers).status_code == 403


@pytest.mark.parametrize('change', ['budget', 'price'])
def test_reviewed_budget_or_price_change_blocks_original_admission(translation, monkeypatch, change):
    e = translation; row = preview(e)
    if change == 'budget':
        checked(e.client.put(e.base + '/model-broker/budget', headers=e.headers, json={'expected_version': 0, 'limit_microusd': 0, 'max_inflight': 1, 'require_known_estimate': True}))
    else:
        original = e.broker._price
        monkeypatch.setattr(e.broker, '_price', lambda *args: {**original(*args), 'source': 'Changed exact price receipt'})
    response = e.client.post(e.path + f'/{e.edition["id"]}/translations/{row["id"]}/dispatch', headers=e.headers,
        json={'expected_version': row['version'], 'reviewed_preview_digest': row['preview']['preview_digest']})
    assert response.status_code == 409 and not e.manager.jobs
    assert not e.broker.ledger(e.nid, e.scope, 'local-author')
    recovered = current(e, row)
    assert recovered['status'] == 'UNKNOWN' and recovered['execution']['receipt_state'] == 'UNKNOWN_NO_AUTOMATIC_REPLAY'
    assert dispatch(e, row)['execution']['job_id'] == recovered['execution']['job_id']


def test_final_adoption_authority_failure_rolls_back_both_run_and_edition(translation):
    from app.experimental.ux import ReadContext
    from fastapi import HTTPException
    e = translation; row = settle(e, dispatch(e, preview(e)))
    before = e.store.read(e.nid, e.scope)
    checks = 0
    def guard():
        nonlocal checks
        checks += 1
        if checks == 3: raise HTTPException(403, {'code': 'SYNTHETIC_FINAL_REVOCATION'})
    with pytest.raises(HTTPException):
        e.translation.adopt(ReadContext(e.nid, e.scope, 'local-author', 'broker-host', None), e.edition['id'], row['id'],
            {'expected_version': row['version'], 'expected_edition_version': row['edition_version'], 'candidate_digest': row['candidate']['digest']}, guard)
    assert e.store.read(e.nid, e.scope) == before


def test_refresh_while_original_accounting_settles_retains_live_admission(translation, monkeypatch):
    e = translation; entered, release = Event(), Event(); original = e.broker.finalize
    def delayed(*args, **kwargs):
        entered.set(); assert release.wait(5)
        return original(*args, **kwargs)
    monkeypatch.setattr(e.broker, 'finalize', delayed)
    run = dispatch(e, preview(e))
    try:
        assert entered.wait(5)
        settling = action(e, run, 'refresh')
        assert settling['status'] == 'SETTLING' and settling['candidate'] is None
    finally: release.set()
    candidate = settle(e, settling)
    assert candidate['status'] == 'CANDIDATE'


def test_refresh_during_original_stream_keeps_current_admission(translation, monkeypatch):
    from app.runtime import runtime
    e = translation; entered, release = Event(), Event()
    def stream(*args, **kwargs):
        entered.set(); assert release.wait(5); yield 'Synthetic current translation'
    monkeypatch.setattr(runtime.providers['mock'], 'stream', stream)
    run = dispatch(e, preview(e))
    try:
        assert entered.wait(5)
        generating = action(e, run, 'refresh')
        assert generating['status'] == 'GENERATING' and generating['candidate'] is None
        assert callable(e.manager.get(generating['execution']['job_id']).request_authorization)
        e.manager.get(generating['execution']['job_id']).request_authorization()
    finally: release.set()
    assert settle(e, generating)['status'] == 'CANDIDATE'


def test_uncertain_terminal_accounting_retains_original_unknown_identity(translation, monkeypatch):
    import time
    e = translation
    monkeypatch.setattr(e.broker, 'finalize', lambda *a, **k: (_ for _ in ()).throw(ValueError('SYNTHETIC_SETTLEMENT_UNCERTAIN')))
    run = dispatch(e, preview(e)); job = e.manager.get(run['execution']['job_id'])
    deadline = time.monotonic() + 5
    while job.terminal_hook_status is None and time.monotonic() < deadline: time.sleep(.01)
    assert job.terminal_hook_status == 'FAILED_RECONCILIATION_REQUIRED'
    result = action(e, run, 'refresh')
    assert result['status'] == 'UNKNOWN' and result['candidate'] is None
    assert result['execution']['receipt_state'] == 'UNKNOWN_NO_AUTOMATIC_REPLAY'
    assert result['execution']['accounting']['status'] == 'DISPATCHED'
    assert dispatch(e, run)['execution']['job_id'] == job.id and len(e.manager.jobs) == 1
