"""Audiobook-owned writes close while shared scope capacity is unverified."""
import pytest
from uuid import uuid4

from app.experimental.common import new_row
from test_audio_history_status_readonly import snapshot
from test_studio_asset_query import rig, shared_scope

pytestmark = pytest.mark.file_backend_only


def seed(rig, monkeypatch):
    from app.experimental import api as experimental_api
    project = rig.workspace.store
    current = project.incarnation(rig.nid)
    chapter = rig.workspace.creative.chapters.create(rig.nid, {'title': 'Synthetic', 'content': 'Synthetic narration.'})
    profile = new_row(rig.nid, rig.scope, 'synthetic', {'display_name': 'Synthetic', 'provider_id': 'local',
        'model_id': 'local', 'voice_id': 'synthetic', 'license_note': 'synthetic', 'status': 'ACTIVE'})
    with project.store.transaction(rig.nid, rig.scope) as doc:
        doc['collections']['creative_documents_v2'] = {
            'current': {'project_incarnation': current},
            'old': {'project_incarnation': 'file:' + str(uuid4())},
        }
        doc['collections']['audio_v2_profiles'] = {profile['id']: profile}
    mounted = experimental_api.audiobook_service
    for name, value in (('store', project.store), ('novels', rig.novels),
                        ('chapters', rig.workspace.creative.chapters), ('assets', rig.assets)):
        monkeypatch.setattr(mounted, name, value)
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'narrative_production_v2,asset_lineage_v2,audiobook_v2')
    return project, profile, chapter


@pytest.mark.parametrize('alias', [False, True])
@pytest.mark.parametrize('kind', ['profile', 'mapping', 'plan'])
def test_mounted_audio_write_is_closed_and_reads_and_other_domain_remain(rig, monkeypatch, alias, kind):
    project, profile, chapter = seed(rig, monkeypatch)
    prefix = f"/api{'/v1' if alias else ''}/novels/{rig.nid}/experimental/audiobook"
    choices = {
        'profile': ('profiles', {'display_name': 'Another', 'provider_id': 'local', 'model_id': 'local',
                                 'voice_id': 'synthetic', 'license_note': 'synthetic'}),
        'mapping': ('mappings', {'character_id': '__narrator__', 'profile_id': profile['id']}),
        'plan': ('plans', {'chapter_id': chapter['id'], 'title': 'Synthetic plan'}),
    }
    before = snapshot(rig.root)
    path, body = choices[kind]
    response = rig.client.post(f'{prefix}/{path}', json=body)
    assert response.status_code == 422, response.text
    assert response.json()['detail']['message'] == 'AUDIO_CAPACITY_WRITE_UNAVAILABLE'
    listed = rig.client.get(prefix + '/profiles')
    assert listed.status_code == 200, listed.text
    assert any(item['id'] == profile['id'] for item in listed.json()['items'])
    assert snapshot(rig.root) == before
    with project.store.transaction(rig.nid, rig.scope) as document:
        document['collections']['other_synthetic_domain'] = {'allowed': {'text': 'synthetic'}}
    assert project.store.read(rig.nid, rig.scope)['collections']['other_synthetic_domain']['allowed']['text'] == 'synthetic'


@pytest.mark.parametrize('alias', [False, True])
def test_missing_write_authority_still_wins(rig, monkeypatch, alias):
    from app.experimental import api as experimental_api
    scope, headers = shared_scope(rig)
    mounted = experimental_api.audiobook_service
    for name, value in (('store', rig.workspace.store.store), ('novels', rig.novels),
                        ('chapters', rig.workspace.creative.chapters), ('assets', rig.assets)):
        monkeypatch.setattr(mounted, name, value)
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'narrative_production_v2,asset_lineage_v2,audiobook_v2')
    prefix = f"/api{'/v1' if alias else ''}/novels/{rig.nid}/experimental/audiobook"
    before = snapshot(rig.root)
    body = {'display_name': 'Synthetic', 'provider_id': 'local', 'model_id': 'local',
            'voice_id': 'synthetic', 'license_note': 'synthetic'}
    response = rig.client.post(prefix + '/profiles', json=body,
                               headers={**headers, 'X-Session-Token': 'token-no-grants'})
    assert response.status_code == 403, response.text
    assert snapshot(rig.root) == before


@pytest.mark.parametrize('name', ['create_profile', 'map_voice', 'create_plan', 'update_segment',
    'bind_audio', 'add_track', 'remove_track', 'review', 'mix', 'edit_direction', 'lock', 'reorder',
    'create', 'mutate'])
def test_direct_audio_services_close_before_reads_or_side_effects(rig, monkeypatch, name):
    from app.experimental import api as experimental_api
    seed(rig, monkeypatch)
    service = experimental_api.audiobook_service
    args = {
        'create_profile': [{}], 'map_voice': [{}], 'create_plan': [{}],
        'update_segment': ['plan', 'segment', {}], 'bind_audio': ['plan', 'segment', {}],
        'add_track': ['plan', {}], 'remove_track': ['plan', 'track', 1],
        'review': ['plan', 'approve', 1], 'mix': ['plan', 1],
        'edit_direction': ['plan', 'segment', {}], 'lock': ['plan', 'segment', {}],
        'reorder': ['plan', {}], 'create': [service.PLANS, {}],
        'mutate': [service.PLANS, 'plan', 1, lambda row: pytest.fail('mutation callback reached')],
    }
    before = snapshot(rig.root)
    with pytest.raises(ValueError, match='AUDIO_CAPACITY_WRITE_UNAVAILABLE'):
        getattr(service, name)(rig.nid, rig.scope, 'synthetic-actor', *args[name])
    assert snapshot(rig.root) == before
