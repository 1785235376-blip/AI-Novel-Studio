"""Backward-compatible shared seams; V1/off does not capture new evidence."""
import base64

import pytest
from app.experimental.media import MediaService
from app.services.asset_library_service import AssetLibraryService
from app.services.v1_capability_service import CapabilityVersionConflict
from test_r3_media_support import rig


def test_asset_compare_and_swap_and_reserved_provenance(tmp_path):
    assets = AssetLibraryService(tmp_path)
    a = assets.create('synthetic-project', 'a.bin', base64.b64encode(b'fixture').decode())
    with pytest.raises(CapabilityVersionConflict):
        assets.update_metadata(a['id'], {'provider_id': 'test'}, expected_version=2)
    for data in ({'origin': 'ORIGINAL_INPUT'}, None):
        with pytest.raises(ValueError, match='scoped versioned annotation'):
            assets.update_metadata(a['id'], {'parameters': {'asset_lineage_v2': data}})
    assert assets.get(a['id'])['version'] == 1


def test_media_evidence_is_opt_in_and_rechecks_capture_flag(rig):
    enabled = [False]
    media = MediaService(rig.store, rig.novels, rig.chapters, rig.assets, rig.screenplays,
                         production_capture_enabled=lambda: enabled[0])
    brief = media.create_cover(rig.nid, rig.scope, rig.actor, {'title': 'Synthetic fixture'})
    body = {'brief_id': brief['id'], 'expected_brief_version': 1, 'adapter_id': 'mock-image-v1'}
    legacy = media.queue(rig.nid, rig.scope, rig.actor, body)
    assert 'queued_environment' not in legacy
    completed = media.execute(rig.nid, rig.scope, rig.actor, legacy['id'], 1)
    assert 'observed_environment' not in completed
    enabled[0] = True
    task = media.queue(rig.nid, rig.scope, rig.actor, body)
    assert task['queued_environment']['verification'] == 'SYNTHETIC_PROTOCOL_ONLY'
    enabled[0] = False
    with pytest.raises(ValueError, match='CAPTURE_DISABLED'):
        media.execute(rig.nid, rig.scope, rig.actor, task['id'], 1)
    assert media.get(rig.nid, rig.scope, media.TASKS, task['id'])['status'] == 'FAILED'
    assert len(media.proposals(rig.nid, rig.scope)) == 2


def test_off_projections_retain_internal_evidence_and_legacy_fields(rig, monkeypatch):
    assets = rig.assets
    parent = assets.create(rig.nid, 'parent.bin', base64.b64encode(b'parent').decode())
    child = assets.create(rig.nid, 'child.bin', base64.b64encode(b'child').decode())
    assets.annotate_lineage(child['id'], {'origin': 'DERIVED_PROCESSING', 'license': {'label': 'declaration'}},
        [parent['id']], branch_id=None, expected_version=1)
    stored = assets.get(child['id'])
    for acceptance in ('false', 'true'):
        monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'asset_lineage_v2' if acceptance == 'true' else '')
        monkeypatch.setenv('V1_ACCEPTANCE_MODE', acceptance)
        public = assets.public({'items': [stored], 'source_asset': stored})
        assert 'asset_lineage_v2' not in str(public)
        assert public['items'][0]['source_asset_ids'] == [parent['id']]
        assert 'asset_lineage_v2' in assets.get(child['id'])['parameters']
    enabled = [True]
    media = MediaService(rig.store, rig.novels, rig.chapters, assets, rig.screenplays, production_capture_enabled=lambda: enabled[0])
    brief = media.create_cover(rig.nid, rig.scope, rig.actor, {'title': 'Private original'})
    task = media.queue(rig.nid, rig.scope, rig.actor, {'brief_id': brief['id'], 'expected_brief_version': 1, 'adapter_id': 'mock-image-v1'})
    completed = media.execute(rig.nid, rig.scope, rig.actor, task['id'], 1)
    enabled[0] = False
    public = media.tasks(rig.nid, rig.scope)[0]
    assert 'environment' not in str(public)
    assert 'queued_environment' in media.get(rig.nid, rig.scope, media.TASKS, task['id'])
    assert completed['status'] == public['status'] == 'SUCCEEDED' and public['brief_snapshot']['title'] == 'Private original'
