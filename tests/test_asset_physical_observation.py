"""Partial canonical-file diagnostics use the real scoped Asset owner."""
import os

import pytest

from test_audio_history_status_readonly import snapshot
from test_studio_asset_query import rig
from test_studio_workspace_identity_history_contract import audio_history

pytestmark = pytest.mark.file_backend_only


def observe(e, asset_id=None):
    with e.rig.workspace._asset_scope(e.rig.nid, e.rig.scope):
        return e.rig.assets.physical_asset_observation(asset_id or e.asset['id'])


def test_canonical_actual_bytes_and_unattributed_temporary_are_distinct(audio_history):
    e = audio_history
    # A name is not a durable operation receipt: never claim this file belongs
    # to the asset, even if it resembles that asset's original create temporary.
    temporary = e.rig.assets.root / (e.asset['id'] + '.synthetic.tmp')
    temporary.write_bytes(b'failure residue')
    before = snapshot(e.rig.root)
    result = observe(e)
    meta_size = e.rig.assets._meta_path(e.asset['id']).stat().st_size
    assert result == {'status': 'PARTIAL', 'scope': 'AUTHORIZED_ASSET_CANONICAL_FILES_ONLY',
        'content_bytes': len(e.content), 'metadata_bytes': meta_size,
        'verified_physical_bytes': len(e.content) + meta_size,
        'logical_content_bytes': len(e.content),
        'unaccounted': 'TEMPORARIES_RESIDUALS_OTHER_OBJECTS_AND_SHARED_STORAGE',
        'quota_admission': 'NOT_AVAILABLE'}
    assert snapshot(e.rig.root) == before
    assert temporary.read_bytes() == b'failure residue'


def test_equal_content_in_distinct_assets_counts_both_physical_files(audio_history):
    e = audio_history
    import base64
    with e.rig.workspace._asset_scope(e.rig.nid, e.rig.scope):
        second = e.rig.assets.create(e.rig.nid, 'same.wav', base64.b64encode(e.content).decode(),
            'audio/wav', 'audio', required_features=('narrative_production_v2',))
    first_obs, second_obs = observe(e), observe(e, second['id'])
    assert e.asset['sha256'] == second['sha256']
    assert e.rig.assets._bin_path(e.asset['id']).stat().st_ino != e.rig.assets._bin_path(second['id']).stat().st_ino
    assert first_obs['content_bytes'] + second_obs['content_bytes'] == 2 * len(e.content)
    assert first_obs['quota_admission'] == second_obs['quota_admission'] == 'NOT_AVAILABLE'


@pytest.mark.parametrize('damage', ['missing', 'corrupt'])
def test_missing_or_corrupt_content_never_returns_physical_total(audio_history, damage):
    e = audio_history
    path = e.rig.assets._bin_path(e.asset['id'])
    if damage == 'missing':
        path.unlink()
    else:
        path.write_bytes(b'x' * len(e.content))
    before = snapshot(e.rig.root)
    with pytest.raises((FileNotFoundError, ValueError)):
        observe(e)
    assert snapshot(e.rig.root) == before


def test_private_asset_and_other_incarnation_are_not_observable(audio_history):
    e = audio_history
    private = e.rig.seed('private.wav', 'audio', owner='different-actor')
    with pytest.raises(FileNotFoundError):
        observe(e, private['id'])
    other = e.rig.project()
    with e.rig.workspace._asset_scope(other, {'mode': 'local', 'novel_id': other}):
        with pytest.raises(FileNotFoundError):
            e.rig.assets.physical_asset_observation(e.asset['id'])


def test_call_requires_existing_scope(audio_history):
    with pytest.raises(ValueError, match='ASSET_PROJECT_BINDING_REQUIRED'):
        audio_history.rig.assets.physical_asset_observation(audio_history.asset['id'])


def test_unproven_shared_physical_file_is_rejected(audio_history):
    e = audio_history
    # A second link cannot prove same-asset exclusive ownership; do not
    # discount it or count it as if it were an independent verified object.
    other_link = e.rig.assets.root / 'synthetic-extra-hardlink.bin'
    os.link(e.rig.assets._bin_path(e.asset['id']), other_link)
    before = snapshot(e.rig.root)
    with pytest.raises(ValueError, match='physical observation unavailable'):
        observe(e)
    assert snapshot(e.rig.root) == before


def test_recreated_project_cannot_observe_old_incarnation(audio_history):
    e = audio_history
    e.rig.novels.delete(e.rig.nid)
    e.rig.project(e.rig.nid)
    with pytest.raises(FileNotFoundError):
        observe(e)
