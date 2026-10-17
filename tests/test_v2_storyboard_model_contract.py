"""Explicit storyboard analysis with mock transport; live model quality NOT_RUN."""
from copy import deepcopy
import json
from threading import Event
from types import SimpleNamespace

import pytest

from app.creative.storyboard_model import STORYBOARD_CONTRACT, STORYBOARD_STRATEGY
from app.creative.proposals import digest
from test_v2_creative_workflows import (creative_model, broker_app, mounted, prefix, scoped,
    checked, route, model_action, model_settle, review_body, wait_ledger)
from test_v2_storyboard_workspace import board_value, content


def pair(e):
    value = board_value(source_independent=False, source_chapter_ids=[e.chapter['id']])
    value['shots'][0].update(sound='Rain', environment='Stone doorway', action='Wait', lens='35mm')
    src = checked(e.client.post(e.creative_base + '/documents', headers=e.headers, json=value), 201)
    row = checked(e.client.post(e.creative_base + '/director-proposals', headers=e.headers,
        json={'source_document_id': src['id'], 'expected_source_version': src['version']}), 201)
    return src, row


def output(src, row):
    notes = deepcopy(row['director_notes'])
    for note, association in zip(notes, row['provenance']['source_shots']):
        note.update(source_shot_id=association['source_shot_id'], duration_seconds=8,
            planning=dict(rationale='Hold tension', sequence_reason='Continue the action',
                duration_reason='Estimated reaction beat', uncertainty='Axis unknown',
                evidence=[], assumptions=['Camera room is speculative'], alternatives=[]))
    return dict(source_contract=STORYBOARD_CONTRACT, source_document_id=src['id'],
        source_version=src['version'], source_digest=row['source_digest'], director_notes=notes)


def preview(e, row):
    return model_action(e, row, 'storyboard-preview', route_id=route(e)['route_id'], source_contract=STORYBOARD_CONTRACT)


def dispatch(e, row):
    return model_action(e, row, 'storyboard-dispatch', source_contract=STORYBOARD_CONTRACT,
        reviewed_preview_digest=row['model_preview']['preview_digest'])


def transport(monkeypatch, payload):
    from app.runtime import runtime
    calls = []
    def stream(prompt, model, **kwargs):
        calls.append(prompt)
        yield payload if isinstance(payload, str) else json.dumps(payload)
    monkeypatch.setattr(runtime.providers['mock'], 'stream', stream)
    return calls


def test_mock_once_exact_context_refresh_review_and_file_restart(creative_model, monkeypatch):
    from app.creative.service import CreativeService
    from app.experimental.store import ExperimentalStore
    e = creative_model
    src, row = pair(e)
    from test_v2_storyboard_workspace import configured, bind, approve
    from test_v2_independent_workspace import import_asset, asset_files
    environment = SimpleNamespace(service=e.studio, nid=e.nid, scope=e.scope, actor='local-author',
        root=e.root, assets=e.assets)
    configured(environment, monkeypatch)
    asset = import_asset(environment, filename='model-source.png')
    bind(e.creative, environment, src['id'], 'shot-1', asset)
    approve(e.creative, environment, src['id'])
    src = e.creative.get(e.nid, e.scope, src['id'])
    row = checked(e.client.post(e.creative_base + '/director-proposals', headers=e.headers,
        json={'source_document_id': src['id'], 'expected_source_version': src['version']}), 201)
    files_before = asset_files(environment)
    from app.experimental.store import canonical
    source_bytes = canonical(e.store.read(e.nid, e.scope)['collections'][e.creative.COLLECTION][src['id']]).encode()
    original = deepcopy(src)
    chapter = deepcopy(e.chapters.get(e.chapter['id']))
    calls = transport(monkeypatch, output(src, row))
    ready = preview(e, row)
    p = ready['model_preview']
    data = json.loads(p['author']['instruction'].split('\n', 1)[1])
    assert data['storyboard'] == {key: src[key] for key in ('title', 'scenes', 'shots')}
    assert data['source_digest'] == row['source_digest']
    assert data['source_document_id'] == src['id'] and data['source_version'] == src['version']
    assert data['source_mapping'] == p['source_mapping']
    assert p['source_strategy'] == STORYBOARD_STRATEGY and p['token_fit_guaranteed'] is False
    assert p['author']['request_scope']['source_mode'] == 'NONE' and not calls
    running = dispatch(e, ready)
    admitted_jobs = set(e.manager.jobs)
    assert admitted_jobs == {running['model_execution']['job_id']}
    for action, extra in [('preview', {'route_id': 'unresolved'}),
                          ('dispatch', {'reviewed_preview_digest': p['preview_digest']})]:
        response = e.client.post(e.creative_base + f'/director-proposals/{row["id"]}/{action}',
            headers=e.headers, json={'expected_version': running['version'], **extra})
        assert response.status_code == 422 and 'CREATIVE_MODEL_SCREENPLAY_SOURCE_REQUIRED' in response.text
        assert set(e.manager.jobs) == admitted_jobs and len(calls) <= 1
    assert dispatch(e, ready)['model_execution']['job_id'] == running['model_execution']['job_id']
    candidates = model_settle(e, running)
    assert candidates['status'] == 'NEEDS_REVIEW' and len(calls) == 1
    assert set(e.manager.jobs) == admitted_jobs
    assert candidates['provenance']['source_shots'] == row['provenance']['source_shots']
    assert candidates['provenance']['source_mode'] == 'STORYBOARD'
    assert candidates['provenance']['raw_output_digest'] and candidates['provenance']['job_id']
    assert candidates['director_notes'][0]['duration_seconds'] == 8
    human = review_body(candidates)
    human['director_notes'] = deepcopy(human['director_notes'])
    human['director_notes'][0]['note'] = 'Human revision'
    accepted = checked(e.client.post(e.creative_base + f'/director-proposals/{row["id"]}/review', headers=e.headers, json=human))
    assert accepted['document']['status'] == 'DRAFT'
    assert e.creative.get(e.nid, e.scope, src['id']) == original
    assert e.chapters.get(e.chapter['id']) == chapter
    reopened = CreativeService(ExperimentalStore(e.store.root), e.novels, e.chapters)
    assert reopened.get(e.nid, e.scope, src['id']) == original
    assert reopened.get(e.nid, e.scope, accepted['document']['id']) == accepted['document']
    assert asset_files(environment) == files_before
    assert canonical(e.store.read(e.nid, e.scope)['collections'][e.creative.COLLECTION][src['id']]).encode() == source_bytes


@pytest.mark.parametrize('mutation', ['execution-contract', 'missing-preview-contract',
    'preview-mapping', 'preview-order', 'preview-digest', 'source-camera', 'source-note-id'])
def test_completed_candidate_contract_tampering_rejected(creative_model, monkeypatch, mutation):
    e = creative_model
    src, row = pair(e)
    calls = transport(monkeypatch, output(src, row))
    candidates = model_settle(e, dispatch(e, preview(e, row)))
    assert candidates['status'] == 'NEEDS_REVIEW' and len(calls) == 1
    coordinator = e.creative.proposals.generation
    ctx = SimpleNamespace(novel_id=e.nid, scope=e.scope)
    coordinator.validate_result(ctx, candidates)
    tampered = deepcopy(candidates)
    if mutation == 'execution-contract':
        tampered['model_execution']['source_contract'] = 'UNKNOWN'
    elif mutation == 'missing-preview-contract':
        tampered['model_preview'].pop('source_contract')
    elif mutation == 'preview-mapping':
        tampered['model_preview']['source_mapping'][0]['note_id'] = 'invented'
    elif mutation == 'preview-order':
        tampered['model_preview']['source_mapping'].reverse()
    elif mutation == 'preview-digest':
        tampered['model_preview']['preview_digest'] = '0' * 64
    elif mutation == 'source-camera':
        tampered['provenance']['source_shots'][0]['source_shot']['camera'] = 'Tampered camera'
    elif mutation == 'source-note-id':
        tampered['provenance']['source_shots'][0]['note_id'] = 'invented'
    with pytest.raises(ValueError):
        coordinator.validate_result(ctx, tampered)
    assert len(calls) == 1
    assert e.creative.get(e.nid, e.scope, src['id']) == src


@pytest.mark.parametrize('stage', ['before', 'after'])
def test_legacy_board_rejected_even_after_opt_in_preview(creative_model, monkeypatch, stage):
    e = creative_model
    _, row = pair(e)
    if stage == 'after':
        row = preview(e, row)
    before = deepcopy(e.store.read(e.nid, e.scope))
    def forbidden(*args, **kwargs):
        pytest.fail('legacy request reached model owner')
    monkeypatch.setattr(e.broker, 'current_route', forbidden)
    monkeypatch.setattr(e.creative.proposals.generation.preparer, 'prepare_author', forbidden)
    for action, extra in [('preview', {'route_id': 'unresolved'}), ('dispatch', {'reviewed_preview_digest': 'a' * 64})]:
        response = e.client.post(e.creative_base + f'/director-proposals/{row["id"]}/{action}', headers=e.headers,
            json={'expected_version': row['version'], **extra})
        assert response.status_code == 422 and 'CREATIVE_MODEL_SCREENPLAY_SOURCE_REQUIRED' in response.text
    assert e.store.read(e.nid, e.scope) == before


@pytest.mark.parametrize('contract', [None, 'UNKNOWN'])
@pytest.mark.parametrize('action', ['storyboard-preview', 'storyboard-dispatch'])
def test_explicit_contract_required(creative_model, action, contract):
    e = creative_model
    _, row = pair(e)
    extra = {'route_id': 'unresolved'} if action.endswith('preview') else {'reviewed_preview_digest': 'a' * 64}
    for contract_field in ({}, {'source_contract': contract}):
        response = e.client.post(e.creative_base + f'/director-proposals/{row["id"]}/{action}', headers=e.headers,
            json={'expected_version': row['version'], **extra, **contract_field})
        assert response.status_code == 422
    assert not e.manager.jobs


def test_preview_digest_tamper_rejected_before_prepare(creative_model, monkeypatch):
    e = creative_model
    _, row = pair(e)
    row = preview(e, row)
    with e.creative.store.transaction(e.nid, e.scope) as state:
        stored = state['collections'][e.creative.proposals.COLLECTION][row['id']]
        stored['model_preview']['request']['parameters']['temperature'] = 0.99
    def forbidden(*args, **kwargs):
        pytest.fail('tampered preview reached prepare')
    monkeypatch.setattr(e.creative.proposals.generation.preparer, 'prepare_author', forbidden)
    response = e.client.post(e.creative_base + f'/director-proposals/{row["id"]}/storyboard-dispatch', headers=e.headers,
        json={'expected_version': row['version'], 'source_contract': STORYBOARD_CONTRACT,
              'reviewed_preview_digest': row['model_preview']['preview_digest']})
    assert response.status_code == 422 and 'EXACT_PREVIEW_REQUIRED' in response.text


@pytest.mark.parametrize('mutation', ['missing', 'extra', 'duplicate', 'reorder', 'crossed', 'new-id', 'no-planning', 'extra-field', 'source'])
def test_output_mapping_and_envelope_fail_closed(creative_model, mutation):
    e = creative_model
    src, row = pair(e)
    value = output(src, row)
    row = preview(e, row)
    notes = value['director_notes']
    if mutation == 'missing': notes.pop()
    elif mutation == 'extra': notes.append(deepcopy(notes[0]))
    elif mutation == 'duplicate': notes[1] = deepcopy(notes[0])
    elif mutation == 'reorder': notes.reverse()
    elif mutation == 'crossed': notes[0]['source_shot_id'] = notes[1]['source_shot_id']
    elif mutation == 'new-id': notes[0]['id'] = 'invented'
    elif mutation == 'no-planning': notes[0].pop('planning')
    elif mutation == 'extra-field': notes[0]['execute'] = 'tool'
    elif mutation == 'source': value['source_version'] += 1
    with pytest.raises(ValueError):
        e.creative.proposals.generation._parse(SimpleNamespace(novel_id=e.nid, scope=e.scope), row, json.dumps(value))


@pytest.mark.parametrize('bad', ['{"source_contract":"x","source_contract":"y"}', '{"director_notes":', 'x' * 128001])
def test_malformed_json_and_bound(creative_model, bad):
    e = creative_model
    _, row = pair(e)
    row = preview(e, row)
    with pytest.raises(ValueError):
        e.creative.proposals.generation._parse(SimpleNamespace(novel_id=e.nid, scope=e.scope), row, bad)


def test_capability_read_and_missing_anchor_fail_before_preparer(creative_model, monkeypatch):
    e = creative_model
    result = checked(e.client.get(e.creative_base + '/director-proposals/model-capabilities', headers=e.headers))
    assert result['storyboard_source_contract'] == STORYBOARD_CONTRACT and result['live_model_quality'] == 'NOT_RUN'
    assert e.client.get(e.creative_base + '/director-proposals/model-capabilities').status_code == 401
    src = checked(e.client.post(e.creative_base + '/documents', headers=e.headers, json=board_value()), 201)
    row = checked(e.client.post(e.creative_base + '/director-proposals', headers=e.headers,
        json={'source_document_id': src['id'], 'expected_source_version': 1}), 201)
    def forbidden(*args, **kwargs): pytest.fail('unanchored source reached preparer')
    monkeypatch.setattr(e.creative.proposals.generation.preparer, 'prepare_preview', forbidden)
    response = e.client.post(e.creative_base + f'/director-proposals/{row["id"]}/storyboard-preview', headers=e.headers,
        json={'expected_version': 1, 'route_id': route(e)['route_id'], 'source_contract': STORYBOARD_CONTRACT})
    assert response.status_code == 422 and 'SOURCE_CHAPTER_ANCHOR_REQUIRED' in response.text


def test_restart_live_authority_fail_closed_without_replay(creative_model, monkeypatch):
    from app.jobs import JobManager
    e = creative_model
    src, row = pair(e)
    calls = transport(monkeypatch, output(src, row))
    row = preview(e, row)
    running = dispatch(e, row)
    wait_ledger(e, running['model_execution']['reservation_id'])
    restarted = JobManager(generations=e.manager.persistence, chapters=e.chapters,
        contexts=e.manager.contexts, canon=e.canon, snapshot_required=False)
    monkeypatch.setattr(e.creative.proposals.generation, 'manager', restarted)
    result = model_action(e, running, 'refresh')
    assert result['status'] == 'MODEL_UNAVAILABLE' and not result['director_notes']
    assert result['model_execution']['status'] == 'UNKNOWN' and len(calls) == 1
    assert len(e.broker.ledger(e.nid, e.scope, 'local-author')) == 1


def test_cancel_late_output_never_adopted(creative_model, monkeypatch):
    from app.runtime import runtime
    e = creative_model
    src, row = pair(e)
    value = output(src, row)
    row = preview(e, row)
    entered, release = Event(), Event()
    def delayed(*args, **kwargs):
        entered.set()
        assert release.wait(10)
        yield json.dumps(value)
    monkeypatch.setattr(runtime.providers['mock'], 'stream', delayed)
    try:
        running = dispatch(e, row)
        assert entered.wait(5)
        cancelled = model_action(e, running, 'cancel')
    finally:
        release.set()
    wait_ledger(e, running['model_execution']['reservation_id'])
    assert cancelled['status'] == 'CANCELLED' and not cancelled['director_notes']
    response = e.client.post(e.creative_base + f'/director-proposals/{row["id"]}/refresh', headers=e.headers,
        json={'expected_version': cancelled['version']})
    assert response.status_code == 422
    assert e.creative.get(e.nid, e.scope, src['id']) == src


def test_legacy_screenplay_request_bytes_and_schemas_golden():
    """Frozen pre-change functions generate the same complete author request/schema."""
    from pathlib import Path
    import textwrap
    from app.creative import generation
    from app.creative.models import DirectorModelPreview, DirectorModelDispatch, DirectorModelOutput
    from test_v2_director_model_planning import coordinator
    fixture = Path(__file__).parent / 'fixtures' / 'storyboard_model'
    namespace = dict(vars(generation))
    exec(textwrap.dedent((fixture / 'screenplay_author_golden.txt').read_text()), namespace)
    exec((fixture / 'screenplay_schema_golden.txt').read_text(), namespace)
    owner, ctx, _ = coordinator()
    for goal in (None, {'style': 'Restrained', 'rhythm': 'Hold then cut', 'genre': 'Mystery'}):
        row = {'title': 'Candidate'}
        if goal is not None: row['visual_target'] = goal
        route_value = {'provider_id': 'mock', 'model_id': 'fake-local'}
        assert owner._author(ctx, row, route_value).model_dump(mode='json') == namespace['_author'](owner, ctx, row, route_value).model_dump(mode='json')
    for production in (False, True):
        for planning in (False, True):
            assert generation.director_output_schema(production=production, planning=planning) == namespace['director_output_schema'](production=production, planning=planning)
    for schema, body in ((DirectorModelPreview, {'expected_version': 1, 'route_id': 'mock'}),
                         (DirectorModelDispatch, {'expected_version': 1, 'reviewed_preview_digest': 'a' * 64})):
        assert 'source_contract' not in schema.model_json_schema()['properties']
        with pytest.raises(ValueError): schema.model_validate({**body, 'source_contract': STORYBOARD_CONTRACT})
    assert 'source_contract' not in DirectorModelOutput.model_json_schema()['properties']


def test_chapter_count_and_full_instruction_bounds_fail_without_prepare(creative_model, monkeypatch):
    e = creative_model
    src, row = pair(e)
    coordinator = e.creative.proposals.generation
    ctx = SimpleNamespace(novel_id=e.nid, scope=e.scope)
    selected = route(e)
    too_many = deepcopy(src)
    too_many['source_chapter_ids'] = [f'chapter-{i}' for i in range(21)]
    with monkeypatch.context() as patch:
        patch.setattr(coordinator.proposals, '_current', lambda *args: too_many)
        with pytest.raises(ValueError, match='SOURCE_CHAPTER_LIMIT'):
            coordinator._author(ctx, row, selected, source_contract=STORYBOARD_CONTRACT)
    large = deepcopy(src)
    large['scenes'][0]['action'] = 'UNTRUSTED' * 3000
    with monkeypatch.context() as patch:
        patch.setattr(coordinator.proposals, '_current', lambda *args: large)
        with pytest.raises(ValueError, match='INPUT_LIMIT'):
            coordinator._author(ctx, row, selected, source_contract=STORYBOARD_CONTRACT)


def test_screenplay_and_adaptation_reject_storyboard_contract(creative_model, monkeypatch):
    from test_v2_creative_workflows import model_ready
    from app.creative.models import DirectorModelDispatch
    e = creative_model
    _, row, calls = model_ready(e, monkeypatch)
    response = e.client.post(e.creative_base + f'/director-proposals/{row["id"]}/storyboard-preview', headers=e.headers,
        json={'expected_version': row['version'], 'route_id': route(e)['route_id'], 'source_contract': STORYBOARD_CONTRACT})
    assert response.status_code == 422 and 'SOURCE_CONTRACT_MISMATCH' in response.text
    # The adaptation dispatcher uses this exact unchanged shared schema.
    with pytest.raises(ValueError):
        DirectorModelDispatch.model_validate({'expected_version': 1, 'reviewed_preview_digest': 'a' * 64,
                                              'source_contract': STORYBOARD_CONTRACT})
    assert not calls


def test_stale_board_and_human_association_change_fail_closed(creative_model, monkeypatch):
    e = creative_model
    src, row = pair(e)
    calls = transport(monkeypatch, output(src, row))
    row = preview(e, row)
    ready = model_settle(e, dispatch(e, row))
    human = review_body(ready)
    human['director_notes'] = deepcopy(human['director_notes'])
    human['director_notes'].reverse()
    response = e.client.post(e.creative_base + f'/director-proposals/{row["id"]}/review', headers=e.headers, json=human)
    assert response.status_code == 422 and 'ASSOCIATION_REQUIRED' in response.text
    updated = content(src)
    updated['title'] += ' changed'
    e.creative.update(e.nid, e.scope, 'local-author', src['id'], src['version'], updated)
    response = e.client.post(e.creative_base + f'/director-proposals/{row["id"]}/refresh', headers=e.headers,
        json={'expected_version': ready['version']})
    assert response.status_code == 409 and len(calls) == 1


def test_exact_instruction_boundary_whole_route_no_truncation(creative_model, monkeypatch):
    e = creative_model
    src, row = pair(e)
    coordinator = e.creative.proposals.generation
    ctx = SimpleNamespace(novel_id=e.nid, scope=e.scope)
    selected = route(e)
    original_length = len(coordinator._author(ctx, row, selected, source_contract=STORYBOARD_CONTRACT).instruction)
    assert original_length < 20000
    padding = 20000 - original_length
    assert padding < 16000
    value = content(src)
    value['scenes'][0]['action'] += 'x' * padding
    current = e.creative.update(e.nid, e.scope, 'local-author', src['id'], src['version'], value)
    row = e.creative.proposals.create(e.nid, e.scope, 'local-author', {
        'source_document_id': src['id'], 'expected_source_version': current['version']})
    assert len(coordinator._author(ctx, row, selected, source_contract=STORYBOARD_CONTRACT).instruction) == 20000
    accepted = preview(e, row)
    assert len(accepted['model_preview']['author']['instruction']) == 20000
    value['scenes'][0]['action'] += 'x'
    current = e.creative.update(e.nid, e.scope, 'local-author', src['id'], current['version'], value)
    row = e.creative.proposals.create(e.nid, e.scope, 'local-author', {
        'source_document_id': src['id'], 'expected_source_version': current['version']})
    before = deepcopy(e.store.read(e.nid, e.scope))
    def forbidden(*args, **kwargs): pytest.fail('oversize request reached preparation or broker preview')
    monkeypatch.setattr(coordinator.preparer, 'prepare_preview', forbidden)
    monkeypatch.setattr(e.broker, 'preview', forbidden)
    response = e.client.post(e.creative_base + f'/director-proposals/{row["id"]}/storyboard-preview', headers=e.headers,
        json={'expected_version': row['version'], 'route_id': selected['route_id'], 'source_contract': STORYBOARD_CONTRACT})
    assert response.status_code == 422 and 'INPUT_LIMIT' in response.text
    assert e.store.read(e.nid, e.scope) == before


def test_twenty_chapters_supported_twenty_one_rejects_before_prepare(creative_model, monkeypatch):
    e = creative_model
    ids = [e.chapter['id']] + [e.chapters.create(e.nid, {'title': f'Anchor {i}', 'content': 'Authored anchor'})['id'] for i in range(20)]
    selected = route(e)
    for size in (20, 21):
        src = e.creative.create(e.nid, e.scope, 'local-author',
            board_value(source_independent=False, source_chapter_ids=ids[:size]))
        row = e.creative.proposals.create(e.nid, e.scope, 'local-author',
            {'source_document_id': src['id'], 'expected_source_version': src['version']})
        if size == 20:
            assert preview(e, row)['model_preview']['execution_available']
        else:
            def forbidden(*args, **kwargs): pytest.fail('21 anchors reached preparation or broker preview')
            monkeypatch.setattr(e.creative.proposals.generation.preparer, 'prepare_preview', forbidden)
            monkeypatch.setattr(e.broker, 'preview', forbidden)
            response = e.client.post(e.creative_base + f'/director-proposals/{row["id"]}/storyboard-preview', headers=e.headers,
                json={'expected_version': row['version'], 'route_id': selected['route_id'], 'source_contract': STORYBOARD_CONTRACT})
            assert response.status_code == 422 and 'SOURCE_CHAPTER_LIMIT' in response.text
