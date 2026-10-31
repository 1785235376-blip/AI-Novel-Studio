"""Independent File/Windows native default-stream observations, synthetic data."""
import base64
import os

import pytest

from app.creative.asset_usage_budget import UsageBudgetError, usage_read_budget
from app.services.asset_query_budget import AssetQueryReadBudget, asset_query_budget
from test_asset_physical_observation import observe
from test_studio_asset_query import rig
from test_studio_workspace_identity_history_contract import audio_history

pytestmark = [pytest.mark.file_backend_only, pytest.mark.skipif(os.name != 'nt', reason='Windows native handle')]


def test_both_content_reads_charge_existing_query_and_usage_budget(audio_history):
    e = audio_history
    with usage_read_budget(fresh=True) as usage, asset_query_budget() as query:
        result = observe(e)
        assert result['quota_admission'] == 'NOT_AVAILABLE'
        assert result['allocated_storage_bytes'] == 'UNKNOWN'
        assert usage.read_bytes >= 2 * len(e.content)
        assert query.content_reads == 2 and query.content_bytes == 2 * len(e.content)


def test_tight_outer_budget_is_not_refreshed_and_file_is_unchanged(audio_history):
    e = audio_history
    with usage_read_budget(fresh=True) as usage:
        usage.MAX_READ_BYTES = len(e.content)
        with pytest.raises(UsageBudgetError):
            observe(e)
        assert usage.reads >= 1
    assert e.rig.assets._bin_path(e.asset['id']).read_bytes() == e.content


def test_named_stream_never_becomes_a_known_total(audio_history):
    e = audio_history
    path = e.rig.assets._bin_path(e.asset['id'])
    try:
        with open(str(path) + ':synthetic-independent', 'xb') as stream:
            stream.write(b'synthetic additional stream')
    except OSError:
        pytest.skip('named streams unavailable on this volume')
    result = observe(e)
    assert type(result['content_default_stream_stored_bytes']) is int
    assert result['content_other_streams'] == 'UNKNOWN'
    assert result['metadata_stored_bytes'] == 'UNKNOWN'
    assert result['allocated_storage_bytes'] == 'UNKNOWN'
    assert result['quota_admission'] == 'NOT_AVAILABLE'


def test_equal_digest_on_distinct_physical_objects_is_not_deduplicated(audio_history):
    e = audio_history
    with e.rig.workspace._asset_scope(e.rig.nid, e.rig.scope):
        second = e.rig.assets.create(e.rig.nid, 'second-synthetic.wav', base64.b64encode(e.content).decode(),
                                      'audio/wav', 'audio')
    one, two = observe(e), observe(e, second['id'])
    assert e.asset['sha256'] == second['sha256']
    assert e.rig.assets._bin_path(e.asset['id']).stat().st_ino != e.rig.assets._bin_path(second['id']).stat().st_ino
    assert one['content_default_stream_stored_bytes'] > 0 and two['content_default_stream_stored_bytes'] > 0
    assert one['allocated_storage_bytes'] == two['allocated_storage_bytes'] == 'UNKNOWN'


def test_unlinked_metadata_is_not_proven_by_matching_content(audio_history):
    e = audio_history
    path = e.rig.assets._meta_path(e.asset['id'])
    original = path.read_bytes()
    path.write_bytes(original.replace(e.asset['sha256'].encode(), b'0' * 64))
    with pytest.raises(ValueError):
        observe(e)
    assert e.rig.assets._bin_path(e.asset['id']).read_bytes() == e.content


def test_native_handle_checks_real_revoked_session_before_observation(rig):
    from fastapi import HTTPException
    from app import api
    from app.services.asset_bounded_file_windows import open_windows_bounded_asset
    from test_studio_asset_query import shared_scope
    scope, headers = shared_scope(rig)
    asset = rig.seed('synthetic-private.wav', 'audio', scope_value=scope, owner='reader')
    token = headers['X-Session-Token']
    def guard():
        actor, selected = api._workbench_authorize(rig.nid, token, 'query-branch-a', 'domain.read')
        assert actor == 'reader' and selected == scope
    with open_windows_bounded_asset(rig.assets._bin_path(asset['id']), trusted_root=rig.assets.root,
            expected_size=asset['size'], max_bytes=rig.assets.MAX_BYTES,
            expected_sha256=asset['sha256'], guard=guard) as lease:
        assert lease.read_all() == b'synthetic fixture bytes'
        rig.sessions.revoke(token)
        with pytest.raises(HTTPException) as exc:
            lease.stored_bytes()
        assert exc.value.status_code in (401, 403)
