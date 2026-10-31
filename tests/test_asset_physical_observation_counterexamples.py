"""Independent, synthetic canonical-file observation checks."""
import pytest

from app.repositories.file.mutation_coordinator import existing_coordination_only
from test_audio_history_status_readonly import snapshot
from test_studio_workspace_identity_history_contract import audio_history
from test_studio_asset_query import rig

pytestmark = pytest.mark.file_backend_only


def test_existing_coordination_observes_one_file_only_and_is_read_only(audio_history):
    e = audio_history
    extra = e.rig.assets.root / 'synthetic-residual.tmp'
    extra.write_bytes(b'unknown owner')
    before = snapshot(e.rig.root)
    with existing_coordination_only(), e.rig.workspace.store.existing_owner_only():
        with e.rig.workspace._asset_scope(e.rig.nid, e.rig.scope):
            result = e.rig.assets.physical_asset_observation(e.asset['id'])
    assert result['content_file_length_bytes'] == len(e.content)
    assert result['allocated_storage_bytes'] == 'UNKNOWN'
    assert 'verified_physical_bytes' not in result
    assert result['status'] == 'PARTIAL' and result['quota_admission'] == 'NOT_AVAILABLE'
    assert 'TEMPORARIES' in result['unaccounted']
    assert snapshot(e.rig.root) == before


@pytest.mark.parametrize('changed', ['content', 'metadata'])
def test_change_during_verified_read_rejects_stale_observation(audio_history, monkeypatch, changed):
    e = audio_history
    original = e.rig.assets._verified_content
    path = (e.rig.assets._bin_path(e.asset['id']) if changed == 'content'
            else e.rig.assets._meta_path(e.asset['id']))
    def mutate_after_verification(*args, **kwargs):
        data = original(*args, **kwargs)
        path.write_bytes(path.read_bytes() + b' ')
        return data
    monkeypatch.setattr(e.rig.assets, '_verified_content', mutate_after_verification)
    with existing_coordination_only(), e.rig.workspace.store.existing_owner_only():
        with e.rig.workspace._asset_scope(e.rig.nid, e.rig.scope):
            with pytest.raises(ValueError, match='physical observation unavailable'):
                e.rig.assets.physical_asset_observation(e.asset['id'])


def test_other_project_binding_cannot_observe_known_asset(audio_history):
    e = audio_history
    other = e.rig.project()
    e.rig.workspace.store.incarnation(other)
    before = snapshot(e.rig.root)
    with existing_coordination_only(), e.rig.workspace.store.existing_owner_only():
        with e.rig.workspace._asset_scope(other, {'mode': 'local', 'novel_id': other}):
            with pytest.raises(FileNotFoundError):
                e.rig.assets.physical_asset_observation(e.asset['id'])
    assert snapshot(e.rig.root) == before


def test_requires_existing_only_for_scoped_observation(audio_history):
    e = audio_history
    with e.rig.workspace._asset_scope(e.rig.nid, e.rig.scope):
        with pytest.raises(ValueError, match='ASSET_OBSERVATION_EXISTING_ONLY_REQUIRED'):
            e.rig.assets.physical_asset_observation(e.asset['id'])
