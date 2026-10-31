"""Synthetic mixed File document: candidate mutations remain closed."""
import copy
from uuid import uuid4
import pytest

from app.experimental.audiobook import AudiobookV2Service
from test_audio_history_status_readonly import snapshot
from test_audio_shared_replacement_plan_independent import candidate
from test_studio_asset_query import rig


def mixed(rig, state):
    project = rig.workspace.store
    current = project.incarnation(rig.nid)
    row = candidate()
    row.update(novel_id=rig.nid, scope=copy.deepcopy(rig.scope), status=state)
    if state == 'APPROVING':
        row.update(promotion_token='synthetic-token', promotion_started_at='synthetic-time',
                   promotion_actor='synthetic-actor')
    with project.store.transaction(rig.nid, rig.scope) as doc:
        doc['collections']['creative_documents_v2'] = {
            'current': {'project_incarnation': current},
            'old': {'project_incarnation': 'file:' + str(uuid4())},
        }
        doc['collections']['audio_v2_mix_proposals'] = {row['id']: row}
    service = AudiobookV2Service(project.store, rig.novels, rig.workspace.creative.chapters,
                                 assets=rig.assets)
    return service, row


@pytest.mark.parametrize('state,action', [('PENDING_REVIEW', 'approve'),
                                         ('PENDING_REVIEW', 'reject'),
                                         ('REJECTED', 'reopen'),
                                         ('APPROVING', 'approve')])
def test_unverified_candidate_cannot_mutate_or_publish(rig, monkeypatch, state, action):
    service, row = mixed(rig, state)
    monkeypatch.setattr(service, '_mix_plan', lambda *args: {'id': 'plan', 'version': 1, 'sources': {}})
    def must_not_publish(*args, **kwargs):
        raise AssertionError('asset publication was reached')
    monkeypatch.setattr(service.assets, 'create', must_not_publish)
    assert service.get(rig.nid, rig.scope, service.MIXES, row['id'])['id'] == row['id']
    before = snapshot(rig.root)
    with pytest.raises(ValueError, match='AUDIO_CAPACITY_WRITE_UNAVAILABLE'):
        service.review(rig.nid, rig.scope, 'synthetic-actor', row['id'], action, row['version'])
    assert snapshot(rig.root) == before


def test_direct_promotion_is_closed_before_asset_owner(rig, monkeypatch):
    service, row = mixed(rig, 'APPROVING')
    monkeypatch.setattr(service.assets, 'create', lambda *a, **kw: pytest.fail('publication reached'))
    before = snapshot(rig.root)
    with pytest.raises(ValueError, match='AUDIO_CAPACITY_WRITE_UNAVAILABLE'):
        service._approve_mix(rig.nid, rig.scope, 'synthetic-actor', row['id'], row['version'])
    assert snapshot(rig.root) == before


def test_mix_is_closed_before_mixer_or_document_write(rig):
    service, _ = mixed(rig, 'PENDING_REVIEW')
    class Mixer:
        local = True
        adapter_id = 'synthetic'
        def mix(self, request):
            pytest.fail('mixer reached')
    service.mixer = Mixer()
    before = snapshot(rig.root)
    with pytest.raises(ValueError, match='AUDIO_CAPACITY_WRITE_UNAVAILABLE'):
        service.mix(rig.nid, rig.scope, 'synthetic-actor', 'synthetic-plan', 1)
    assert snapshot(rig.root) == before


@pytest.mark.parametrize('alias', [False, True])
def test_mounted_candidate_review_is_closed_and_listing_remains_readable(rig, monkeypatch, alias):
    from app.experimental import api as experimental_api
    service, row = mixed(rig, 'PENDING_REVIEW')
    mounted = experimental_api.audiobook_service
    for name in ('store', 'novels', 'chapters', 'assets'):
        monkeypatch.setattr(mounted, name, getattr(service, name))
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'narrative_production_v2,asset_lineage_v2,audiobook_v2')
    prefix = f"/api{'/v1' if alias else ''}/novels/{rig.nid}/experimental/audiobook/mixes"
    before = snapshot(rig.root)
    listed = rig.client.get(prefix)
    assert listed.status_code == 200, listed.text
    assert row['id'] in [item['id'] for item in listed.json()['items']]
    response = rig.client.post(prefix + '/' + row['id'] + '/approve', json={'expected_version': row['version']})
    assert response.status_code == 422, response.text
    assert response.json()['detail']['message'] == 'AUDIO_CAPACITY_WRITE_UNAVAILABLE'
    assert snapshot(rig.root) == before
