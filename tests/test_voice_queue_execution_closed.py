"""Voice writes must close before queue or executor effects, on real File owners."""
import hashlib
import pytest

from app.audio_production_store import AudioProductionStore
from app.experimental.common import new_row
from app.source_privacy import content_digest
from test_audio_history_status_readonly import snapshot
from test_studio_asset_query import rig, shared_scope

pytestmark = pytest.mark.file_backend_only


def prepared(rig, monkeypatch):
    from app import api, audio_production_store as audio_module
    from app.experimental import api as experimental_api
    project = rig.workspace.store
    created = rig.workspace.creative.chapters.create(rig.nid, {'title': 'Synthetic', 'content': 'Synthetic narration.'})
    chapter = rig.workspace.creative.chapters.get(created['id'])
    profile = new_row(rig.nid, rig.scope, 'local-author', {'display_name': 'Synthetic', 'provider_id': 'local',
        'model_id': 'local', 'voice_id': 'synthetic', 'license_note': 'synthetic', 'status': 'ACTIVE'})
    text = chapter['content']
    segment = {'id': 'synthetic-segment', 'text': text, 'source_start': 0, 'source_end': len(text),
        'source_text_digest': hashlib.sha256(text.encode()).hexdigest(), 'kind': 'NARRATION',
        'character_id': '__narrator__', 'profile_id': profile['id'], 'profile_version': profile['version'],
        'attribution_status': 'NARRATION', 'duration_ms': None, 'audio_asset_id': None,
        'direction': {'text_reviewed': True, 'voice_authorized': True, 'reviewed_text': text,
            'emotion': 'neutral', 'speech_rate': 1, 'pause_ms': 0, 'pronunciation_rules': []}}
    plan = new_row(rig.nid, rig.scope, 'local-author', {'chapter_id': chapter['id'], 'title': 'Synthetic',
        'status': 'APPROVED', 'voice_direction': True, 'segments': [segment], 'tracks': [],
        'sources': {chapter['id']: {'version': chapter['version'], 'digest': content_digest(chapter)}},
        'character_snapshots': {}, 'timing_status': 'UNMEASURED'})
    with project.store.transaction(rig.nid, rig.scope) as doc:
        doc['collections']['audio_v2_plans'] = {plan['id']: plan}
        doc['collections']['audio_v2_profiles'] = {profile['id']: profile}
    mounted = experimental_api.audiobook_service
    for name, value in (('store', project.store), ('novels', rig.novels),
                        ('chapters', rig.workspace.creative.chapters), ('assets', rig.assets)):
        monkeypatch.setattr(mounted, name, value)
    monkeypatch.setattr(api, 'asset_library_service', rig.assets)
    monkeypatch.setattr(audio_module, 'audio_production_store', AudioProductionStore(rig.root / 'voice-production'))
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'narrative_production_v2,asset_lineage_v2,audiobook_v2,voice_direction_v2')
    return mounted, chapter, plan, segment, profile


@pytest.mark.parametrize('alias', [False, True])
def test_voice_queue_denied_before_actual_queue_write_and_jobs_remain_readable(rig, monkeypatch, alias):
    _, _, plan, segment, _ = prepared(rig, monkeypatch)
    base = f"/api{'/v1' if alias else ''}/novels/{rig.nid}/experimental/voice-direction"
    before = snapshot(rig.root)
    response = rig.client.post(base + f"/plans/{plan['id']}/queue",
        json={'expected_version': plan['version'], 'segment_ids': [segment['id']], 'approve_selected': True})
    assert response.status_code == 422, response.text
    assert response.json()['detail']['message'] == 'AUDIO_CAPACITY_WRITE_UNAVAILABLE'
    listed = rig.client.get(base + '/jobs')
    assert listed.status_code == 200 and listed.json()['items'] == []
    assert snapshot(rig.root) == before


@pytest.mark.parametrize('alias', [False, True])
def test_voice_queue_denied_authority_first(rig, monkeypatch, alias):
    from app.experimental import api as experimental_api
    _, headers = shared_scope(rig)
    mounted = experimental_api.audiobook_service
    for name, value in (('store', rig.workspace.store.store), ('novels', rig.novels),
                        ('chapters', rig.workspace.creative.chapters), ('assets', rig.assets)):
        monkeypatch.setattr(mounted, name, value)
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'narrative_production_v2,asset_lineage_v2,audiobook_v2,voice_direction_v2')
    base = f"/api{'/v1' if alias else ''}/novels/{rig.nid}/experimental/voice-direction"
    before = snapshot(rig.root)
    response = rig.client.post(base + '/plans/synthetic/queue',
        headers={**headers, 'X-Session-Token': 'token-no-grants'},
        json={'expected_version': 1, 'segment_ids': ['synthetic'], 'approve_selected': True})
    assert response.status_code == 403, response.text
    assert snapshot(rig.root) == before


@pytest.mark.parametrize('alias', [False, True])
def test_existing_voice_execution_denied_before_executor_and_readable(rig, monkeypatch, alias):
    from app.experimental.voice_direction_api import create_runtime_executor
    from app.services.audiobook_service import AudiobookService
    service, chapter, plan, segment, profile = prepared(rig, monkeypatch)
    executor = create_runtime_executor(rig.scope, 'local-author')
    config = {'provider_id': 'local', 'model_id': 'local', 'voice': 'synthetic',
        'experimental_origin': 'voice_direction_v2', 'local_only': True, 'max_cost': 0,
        'direction_binding': {'plan_id': plan['id'], 'segment_id': segment['id'],
            'fingerprint': service.segment_fingerprint(segment), 'actor': 'local-author', 'scope': rig.scope}}
    job = executor.queue(rig.nid, chapter, config, [], source_chapter=chapter)
    calls = []
    def intercepted(*args, **kwargs):
        calls.append(True)
        return {'id': job['id'], 'status': 'SYNTHETIC_INTERCEPT'}
    monkeypatch.setattr(AudiobookService, 'execute', intercepted)
    base = f"/api{'/v1' if alias else ''}/novels/{rig.nid}/experimental/voice-direction"
    before = snapshot(rig.root)
    response = rig.client.post(base + f"/jobs/{job['id']}/execute")
    assert response.status_code == 422, response.text
    assert response.json()['detail']['message'] == 'AUDIO_CAPACITY_WRITE_UNAVAILABLE'
    assert not calls
    listed = rig.client.get(base + '/jobs')
    assert listed.status_code == 200, listed.text
    assert job['id'] in [item['id'] for item in listed.json()['items']]
    assert snapshot(rig.root) == before


@pytest.mark.parametrize('alias', [False, True])
@pytest.mark.parametrize('operation', ['queue', 'execute'])
def test_uninitialized_scope_does_not_create_marker_lock_or_executor(rig, monkeypatch, alias, operation):
    from app.experimental import api as experimental_api
    mounted = experimental_api.audiobook_service
    for name, value in (('store', rig.workspace.store.store), ('novels', rig.novels),
                        ('chapters', rig.workspace.creative.chapters), ('assets', rig.assets)):
        monkeypatch.setattr(mounted, name, value)
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'narrative_production_v2,asset_lineage_v2,audiobook_v2,voice_direction_v2')
    before = snapshot(rig.root)
    base = f"/api{'/v1' if alias else ''}/novels/{rig.nid}/experimental/voice-direction"
    if operation == 'queue':
        response = rig.client.post(base + '/plans/synthetic/queue',
            json={'expected_version': 1, 'segment_ids': ['synthetic'], 'approve_selected': True})
    else:
        response = rig.client.post(base + '/jobs/synthetic/execute')
    assert response.status_code == 422, response.text
    assert response.json()['detail']['message'] == 'AUDIO_CAPACITY_WRITE_UNAVAILABLE'
    assert snapshot(rig.root) == before


@pytest.mark.parametrize('operation', ['queue', 'execute'])
def test_direct_service_is_closed_before_executor_use(rig, monkeypatch, operation):
    service, _, plan, segment, _ = prepared(rig, monkeypatch)
    class NoExecutor:
        def __getattribute__(self, name):
            pytest.fail('executor touched: ' + name)
    before = snapshot(rig.root)
    with pytest.raises(ValueError, match='AUDIO_CAPACITY_WRITE_UNAVAILABLE'):
        if operation == 'queue':
            service.queue_selected(rig.nid, rig.scope, 'local-author', plan['id'],
                {'expected_version': plan['version'], 'segment_ids': [segment['id']], 'approve_selected': True},
                NoExecutor(), lambda: pytest.fail('reauthorization callback reached'))
        else:
            service.execute_local_job(rig.nid, rig.scope, 'local-author', 'synthetic', NoExecutor(),
                lambda _: pytest.fail('provider resolver reached'), lambda: pytest.fail('guard reached'))
    assert snapshot(rig.root) == before
