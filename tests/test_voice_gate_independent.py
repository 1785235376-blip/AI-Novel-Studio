"""Independent voice route closure checks, File/Mock with isolated store."""
import pytest

from app.audio_production_store import AudioProductionStore
from test_audio_history_status_readonly import snapshot
from test_studio_asset_query import rig, shared_scope

pytestmark = pytest.mark.file_backend_only


@pytest.fixture
def env(rig, monkeypatch):
    from app import api, audio_production_store as audio_module
    from app.experimental import api as experimental_api
    for name, value in (('store', rig.workspace.store.store), ('novels', rig.novels),
                        ('chapters', rig.workspace.creative.chapters), ('assets', rig.assets)):
        monkeypatch.setattr(experimental_api.audiobook_service, name, value)
    monkeypatch.setattr(api, 'asset_library_service', rig.assets)
    monkeypatch.setattr(audio_module, 'audio_production_store', AudioProductionStore(rig.root / 'isolated-voice'))
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'narrative_production_v2,asset_lineage_v2,audiobook_v2,voice_direction_v2')
    return rig


def run(env, alias, op, headers=None):
    prefix = f"/api{'/v1' if alias else ''}/novels/{env.nid}/experimental/voice-direction"
    if op == 'queue':
        return env.client.post(prefix + '/plans/missing/queue', headers=headers,
            json={'expected_version': 1, 'segment_ids': ['synthetic'], 'approve_selected': True})
    return env.client.post(prefix + '/jobs/missing/execute', headers=headers)


@pytest.mark.parametrize('alias', [False, True])
@pytest.mark.parametrize('operation', ['queue', 'execute'])
def test_uninitialized_closed_before_any_files_and_executor(env, monkeypatch, alias, operation):
    def forbid(*args, **kwargs):
        pytest.fail('executor factory reached before closed gate')
    monkeypatch.setattr(AudioProductionStore, 'for_branch', forbid)
    before = snapshot(env.root)
    response = run(env, alias, operation)
    assert response.status_code == 422, response.text
    assert response.json()['detail']['message'] == 'AUDIO_CAPACITY_WRITE_UNAVAILABLE'
    assert snapshot(env.root) == before


@pytest.mark.parametrize('alias', [False, True])
@pytest.mark.parametrize('operation', ['queue', 'execute'])
def test_missing_voice_feature_is_rejected_before_gate(env, monkeypatch, alias, operation):
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'narrative_production_v2,asset_lineage_v2,audiobook_v2')
    before = snapshot(env.root)
    response = run(env, alias, operation)
    assert response.status_code == 404, response.text
    assert 'AUDIO_CAPACITY_WRITE_UNAVAILABLE' not in response.text
    assert snapshot(env.root) == before


@pytest.mark.parametrize('alias', [False, True])
@pytest.mark.parametrize('operation', ['queue', 'execute'])
def test_collaboration_authority_precedes_closed_gate(env, alias, operation):
    _, headers = shared_scope(env)
    before = snapshot(env.root)
    response = run(env, alias, operation, headers={**headers, 'X-Session-Token': 'token-no-grants'})
    assert response.status_code == 403, response.text
    assert 'AUDIO_CAPACITY_WRITE_UNAVAILABLE' not in response.text
    assert snapshot(env.root) == before


@pytest.mark.parametrize('alias', [False, True])
def test_empty_voice_job_list_remains_readable(env, alias):
    prefix = f"/api{'/v1' if alias else ''}/novels/{env.nid}/experimental/voice-direction"
    before = snapshot(env.root)
    response = env.client.get(prefix + '/jobs')
    assert response.status_code == 200, response.text
    assert response.json() == {'items': []}
    assert snapshot(env.root) == before
