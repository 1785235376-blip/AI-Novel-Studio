"""Original File decision storage + SYNTHETIC read ports; not owner API acceptance."""
from copy import deepcopy

import pytest

from app.experimental.change_impact import ChangeImpactService
from app.experimental.common import StaleSourceError
from app.experimental.store import ExperimentalStore
from app.experimental.storyboard_impact_adapter import observe_storyboard
from test_dif02_storyboard_impact_adapter import ports
from test_r3_media_support import rig
from test_r4_change_impact import impact
from test_r3_mounted_contracts import mounted, prefix


def enable_modern(service):
    old = service.enabled
    service.enabled = lambda name: name == 'narrative_production_v2' or old(name)


def selected(observation, r):
    view = observation.view(r.nid, r.scope, r.actor, 'board')
    return {'source': {'kind': 'CREATIVE_STORYBOARD', 'id': 'board'},
        'selected': [{'key': row['key'], 'expected_version': row['version'], 'choice': 'REBUILD'} for row in view['items']]}


def test_missing_request_local_observation_cannot_use_legacy_asset_or_create_records(rig, impact, monkeypatch):
    r, service = rig, impact; enable_modern(service)
    monkeypatch.setattr(service.production, '_asset', lambda *a, **k: pytest.fail('Modern IDs cannot become legacy asset reads'))
    body = {'source': {'kind': 'CREATIVE_STORYBOARD', 'id': 'board'},
        'selected': [{'key': 'CREATIVE_GRAPH_NODE:untrusted', 'expected_version': 1, 'choice': 'KEEP'}]}
    before = deepcopy(r.store.read(r.nid, r.scope))
    for method, value in ((service.impact, {'source': body['source']}),
                          (service.preview_decisions, body),
                          (service.save_decisions, {**body, 'preview_digest': 'a' * 64, 'request_id': 'unwired'}),
                          (service.decisions, {'source': body['source']})):
        with pytest.raises(FileNotFoundError, match='READ_OWNER_UNAVAILABLE'):
            if method == service.impact: method(r.nid, r.scope, value)
            else: method(r.nid, r.scope, r.actor, value)
    assert r.store.read(r.nid, r.scope) == before


def test_file_intent_checkpoint_reopen_is_only_persistence_harness_not_owner_authorization(rig, impact):
    r, service = rig, impact; enable_modern(service)
    state, readers = ports(r.nid, r.scope, r.actor, targets=2)
    before = deepcopy(r.store.read(r.nid, r.scope))
    with observe_storyboard(r.nid, r.scope, r.actor, 'board', readers) as observation:
        body = selected(observation, r)
        preview = service.preview_decisions(r.nid, r.scope, r.actor, body, observation=observation)
        assert r.store.read(r.nid, r.scope) == before
        request = {**body, 'preview_digest': preview['preview_digest'], 'request_id': 'guarded-intent'}
        saved = service.save_decisions(r.nid, r.scope, r.actor, request, observation=observation)
        assert saved['current'] and saved['decision_only'] and not saved['automatic_execution']
        assert service.save_decisions(r.nid, r.scope, r.actor, request, observation=observation) == saved
        assert len(state.opened) == 3  # No list/get was repeated inside the DIF transaction.
    after = deepcopy(r.store.read(r.nid, r.scope)); records = after['collections'].pop(service.DECISIONS)
    assert len(records) == 1 and after == before
    fresh = ChangeImpactService(ExperimentalStore(r.root, r.backend, r.store.database_url), r.novels, r.chapters,
        service.graph, service.production, service.planning, service.audiobook, enabled=service.enabled)
    with observe_storyboard(r.nid, r.scope, r.actor, 'board', readers) as observation:
        assert fresh.decisions(r.nid, r.scope, r.actor, {'source': body['source']}, observation=observation) == {'items': [saved]}
    with pytest.raises(PermissionError, match='LEASE_CLOSED'):
        fresh.decisions(r.nid, r.scope, r.actor, {'source': body['source']}, observation=observation)


def test_old_preview_rejects_changed_graph_and_old_incarnation_is_not_reopened(rig, impact):
    r, service = rig, impact; enable_modern(service)
    state, readers = ports(r.nid, r.scope, r.actor)
    with observe_storyboard(r.nid, r.scope, r.actor, 'board', readers) as observation:
        body = selected(observation, r)
        preview = service.preview_decisions(r.nid, r.scope, r.actor, body, observation=observation)
    request = {**body, 'preview_digest': preview['preview_digest'], 'request_id': 'old-preview'}
    state.graphs[0]['version'] = 2
    before = deepcopy(r.store.read(r.nid, r.scope))
    with observe_storyboard(r.nid, r.scope, r.actor, 'board', readers) as observation:
        body['selected'][0]['expected_version'] = 2
        with pytest.raises(StaleSourceError):
            service.save_decisions(r.nid, r.scope, r.actor, {**request, 'selected': body['selected']}, observation=observation)
        assert r.store.read(r.nid, r.scope) == before
        preview = service.preview_decisions(r.nid, r.scope, r.actor, body, observation=observation)
        service.save_decisions(r.nid, r.scope, r.actor,
            {**body, 'preview_digest': preview['preview_digest'], 'request_id': 'current-preview'}, observation=observation)
    state.epoch = 'recreated-project'
    with observe_storyboard(r.nid, r.scope, r.actor, 'board', readers) as observation:
        assert service.decisions(r.nid, r.scope, r.actor, {'source': body['source']}, observation=observation) == {'items': []}


def test_retained_guard_revocation_at_original_write_rolls_back_checkpoint(rig, impact, monkeypatch):
    import app.experimental.change_impact as module
    r, service = rig, impact; enable_modern(service)
    state, readers = ports(r.nid, r.scope, r.actor)
    before = deepcopy(r.store.read(r.nid, r.scope))
    original = module.new_row
    def revoke_after_row_created(*args, **kwargs):
        row = original(*args, **kwargs)
        state.denied = True
        return row
    with pytest.raises(PermissionError):
        with observe_storyboard(r.nid, r.scope, r.actor, 'board', readers) as observation:
            body = selected(observation, r)
            preview = service.preview_decisions(r.nid, r.scope, r.actor, body, observation=observation)
            monkeypatch.setattr(module, 'new_row', revoke_after_row_created)
            service.save_decisions(r.nid, r.scope, r.actor,
                {**body, 'preview_digest': preview['preview_digest'], 'request_id': 'revoke-during-write'}, observation=observation)
    assert r.store.read(r.nid, r.scope) == before and not state.active


def test_original_mounted_file_route_fails_closed_while_modern_owner_ports_are_unwired(mounted, monkeypatch):
    e = mounted
    monkeypatch.setattr(e.experimental.change_impact_service, '_storyboard_reader_factory', None)
    monkeypatch.setattr(e.experimental.change_impact_service, '_graph_reader_factory', None)
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'change_impact_v2,temporal_story_graph_v2,world_character_engines_v2,asset_lineage_v2,narrative_production_v2')
    body = {'source': {'kind': 'CREATIVE_STORYBOARD', 'id': 'board'},
        'selected': [{'key': 'CREATIVE_GRAPH_NODE:untrusted', 'expected_version': 1, 'choice': 'REBUILD'}]}
    before = deepcopy(e.experimental.change_impact_service.store.read(e.nid, e.scope))
    base = e.base + '/change-impact'
    for suffix, value in (('/query', {'source': body['source']}), ('/decisions/preview', body),
                          ('/decisions', {**body, 'preview_digest': 'a' * 64, 'request_id': 'no-modern-grant'})):
        response = e.client.post(base + suffix, json=value)
        assert response.status_code == 404 and 'untrusted' not in response.text
    response = e.client.get(base + '/decisions', params={'source_kind': 'CREATIVE_STORYBOARD', 'source_id': 'board'})
    assert response.status_code == 404
    assert e.experimental.change_impact_service.store.read(e.nid, e.scope) == before
