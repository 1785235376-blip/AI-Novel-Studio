"""Independent fsync interruption checks after production freeze 13700f24.

Real File source ownership, mounted query, SQLite staging and recovery remain
intact. Only the explicit final staging fsync is made to report an I/O error.
"""
import errno
import os

import pytest

from test_studio_asset_query import rig

pytestmark = pytest.mark.file_backend_only


def query(rig):
    return rig.client.get(f'/api/projects/{rig.nid}/studio/assets', params={'limit': 10})


def source_bytes(rig):
    return {path.name: path.read_bytes() for path in rig.assets.root.iterdir()
            if path.is_file() and path.suffix in {'.json', '.bin'}}


@pytest.mark.parametrize('previous_publication', [False, True], ids=['first-build', 'replace-existing'])
def test_staging_fsync_failure_preserves_publication_and_recovers(rig, monkeypatch, previous_publication):
    from app.services.asset_query_index import FileAssetQueryIndex

    asset = rig.seed('before-interruption.png')
    index = rig.workspace.query_index
    if previous_publication:
        initial = query(rig)
        assert initial.status_code == 200, initial.text
        assert [row['id'] for row in initial.json()['items']] == [asset['id']]
        old_database = index.path.read_bytes()
        old_identity = index._index_identity()
        old_verified = index._verified_identity, index._verified_revision
        with rig.workspace._asset_scope(rig.nid, rig.scope):
            current = rig.assets.get(asset['id'])
            current['filename'] = 'after-interruption-different-length.png'
            rig.assets._write_meta(current)
    else:
        old_database = old_identity = None
        old_verified = index._verified_identity, index._verified_revision

    unchanged_sources = source_bytes(rig)
    sync_calls, phases, replacements = [], [], []
    original_replace = os.replace

    def fail_sync(fd):
        # This is the real open, populated SQLite staging file, not a fake
        # handle or a mocked database. Failure must prevent atomic publication.
        sync_calls.append(os.fstat(fd).st_size)
        raise OSError(errno.EIO, 'independent injected staged-index flush failure')

    def record_replace(source, target):
        replacements.append(str(target))
        return original_replace(source, target)

    with monkeypatch.context() as fault:
        fault.setattr(os, 'fsync', fail_sync)
        fault.setattr(os, 'replace', record_replace)
        fault.setattr(index, '_rebuild_checkpoint', phases.append)
        failed = query(rig)

    assert failed.status_code == 503, failed.text
    assert failed.json()['code'] == 'ASSET_QUERY_INDEX_UNAVAILABLE'
    assert 'items' not in failed.json() and 'total' not in failed.json()
    assert asset['id'] not in failed.text and 'independent injected' not in failed.text
    assert len(sync_calls) == 1 and sync_calls[0] > 0
    assert 'committed' in phases and 'published' not in phases
    assert str(index.path) not in replacements
    assert index._index_identity() == old_identity
    assert (index._verified_identity, index._verified_revision) == old_verified
    if previous_publication:
        assert index.path.read_bytes() == old_database
    else:
        assert not index.path.exists()
    assert not list(index.directory.glob('building-*'))
    assert source_bytes(rig) == unchanged_sources

    # Clearing the injected failure permits the unchanged original fsync and
    # atomic replace to publish; a fresh reader independently verifies the DB.
    recovered = query(rig)
    assert recovered.status_code == 200, recovered.text
    rows = recovered.json()['items']
    assert recovered.json()['total'] == 1 and [row['id'] for row in rows] == [asset['id']]
    expected_name = 'after-interruption-different-length.png' if previous_publication else asset['filename']
    assert rows[0]['filename'] == expected_name
    fresh = FileAssetQueryIndex(rig.assets.root)
    with rig.workspace._asset_scope(rig.nid, rig.scope):
        snapshot = fresh.snapshot(rig.assets._load)
        candidates = list(fresh.iter_candidates(snapshot, rig.nid, rig.assets._scope.binding))
        fresh.verify(snapshot)
    assert [row['id'] for row in candidates] == [asset['id']]
    assert candidates[0]['filename'] == expected_name
    assert source_bytes(rig) == unchanged_sources
