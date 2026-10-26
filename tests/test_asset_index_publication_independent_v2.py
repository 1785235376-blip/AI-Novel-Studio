"""Independent fsync interruption checks after production freeze 13700f24.

Real File source ownership, mounted query, SQLite staging and recovery remain
intact. Only the explicit final staging fsync is made to report an I/O error.
"""
import errno
from contextlib import closing
import os
import sqlite3

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


@pytest.mark.skipif(os.name != 'nt', reason='Windows native ChangeTime boundary')
def test_same_size_source_edit_with_restored_mtime_changes_filtered_results(rig):
    row = rig.seed('before.png')
    endpoint = f'/api/projects/{rig.nid}/studio/assets'
    initial = rig.client.get(endpoint, params={'q': 'before', 'limit': 10})
    assert initial.status_code == 200 and initial.json()['total'] == 1
    path = rig.assets.root / (row['id'] + '.json')
    prior = path.stat()
    content = path.read_bytes()
    replacement = content.replace(b'"before.png"', b'"afters.png"')
    assert replacement != content and len(replacement) == len(content)
    path.write_bytes(replacement)
    os.utime(path, ns=(prior.st_atime_ns, prior.st_mtime_ns))
    assert path.stat().st_size == prior.st_size
    assert path.stat().st_mtime_ns == prior.st_mtime_ns
    current = rig.client.get(endpoint, params={'q': 'afters', 'limit': 10})
    assert current.status_code == 200, current.text
    assert [item['id'] for item in current.json()['items']] == [row['id']]
    assert current.json()['total'] == 1
    assert rig.client.get(endpoint, params={'q': 'before', 'limit': 10}).json()['total'] == 0


@pytest.mark.skipif(os.name != 'nt', reason='Windows native ChangeTime boundary')
def test_warm_index_same_size_sql_corruption_with_restored_mtime_rebuilds(rig):
    row = rig.seed('needle.png')
    endpoint = f'/api/projects/{rig.nid}/studio/assets'
    initial = rig.client.get(endpoint, params={'q': 'needle', 'limit': 10})
    assert initial.status_code == 200 and initial.json()['total'] == 1
    index = rig.workspace.query_index
    prior = index.path.stat()
    original_sources = source_bytes(rig)
    with closing(sqlite3.connect(index.path)) as connection:
        with connection:
            connection.execute('UPDATE sources SET filename_folded=? WHERE asset_id=?',
                               ('hidden.png', row['id']))
    os.utime(index.path, ns=(prior.st_atime_ns, prior.st_mtime_ns))
    assert index.path.stat().st_size == prior.st_size
    assert index.path.stat().st_mtime_ns == prior.st_mtime_ns
    recovered = rig.client.get(endpoint, params={'q': 'needle', 'limit': 10})
    assert recovered.status_code == 200, recovered.text
    assert [item['id'] for item in recovered.json()['items']] == [row['id']]
    assert recovered.json()['total'] == 1
    assert source_bytes(rig) == original_sources


@pytest.mark.skipif(os.name != 'nt', reason='Windows native ChangeTime boundary')
@pytest.mark.parametrize('failure', ['attributes', 'missing-api', 'open-handle', 'reparse-attribute'])
def test_native_failure_refuses_warm_cache_and_releases_handle(rig, monkeypatch, failure):
    import app.services.asset_query_index as owner
    row = rig.seed('native-attributes.png')
    assert query(rig).status_code == 200
    index = rig.workspace.query_index
    before = index.path.read_bytes()
    dll, basic_type = owner._windows_signature_api()
    failed = []

    class FailedAttributes:
        def __getattr__(self, name):
            return getattr(dll, name)

        def GetFileInformationByHandleEx(self, *args):
            failed.append(True)
            if failure == 'reparse-attribute':
                import ctypes
                result = dll.GetFileInformationByHandleEx(*args)
                assert result
                # Auxiliary native-result injection: actual symlink creation
                # is checked separately and may be unavailable on the host.
                ctypes.cast(args[2], ctypes.POINTER(basic_type)).contents.attributes |= 0x400
                return result
            return False

        def CreateFileW(self, *args):
            if failure == 'open-handle':
                import ctypes
                failed.append(True)
                return ctypes.c_void_p(-1).value
            return dll.CreateFileW(*args)

    def failing_api():
        if failure == 'missing-api':
            failed.append(True)
            raise AttributeError('independent native API unavailable')
        return FailedAttributes(), basic_type

    with monkeypatch.context() as fault:
        fault.setattr(owner, '_windows_signature_api', failing_api)
        for _ in range(3):
            denied = query(rig)
            assert denied.status_code == 503, denied.text
            assert denied.json()['code'] == 'ASSET_QUERY_INDEX_UNAVAILABLE'
            assert row['id'] not in denied.text and 'items' not in denied.json()
    assert len(failed) == 3 and index.path.read_bytes() == before
    # A leaked FILE_SHARE_READ-only handle would prevent this real metadata
    # update/atomic replace, so recovery checks disposal as well as response.
    with rig.workspace._asset_scope(rig.nid, rig.scope):
        current = rig.assets.get(row['id'])
        current['filename'] = 'native-attributes-after-fault.png'
        rig.assets._write_meta(current)
    recovered = query(rig)
    assert recovered.status_code == 200, recovered.text
    assert recovered.json()['items'][0]['filename'] == current['filename']


@pytest.mark.skipif(os.name != 'nt', reason='Windows reparse-point boundary')
def test_actual_reparse_metadata_entry_is_rejected_without_reading_target(rig):
    row = rig.seed('ordinary-metadata.png')
    assert query(rig).status_code == 200
    external = rig.root / 'independent-reparse-target.json'
    external.write_bytes(b'INDEPENDENT_TARGET_BYTES_MUST_NOT_BECOME_QUERY_CONTENT')
    link = rig.assets.root / 'independent-reparse.json'
    try:
        link.symlink_to(external)
    except OSError as error:
        if getattr(error, 'winerror', None) == 1314:
            pytest.skip('Host does not permit creation of a real Windows symlink')
        raise
    assert link.is_symlink()
    denied = query(rig)
    assert denied.status_code == 503, denied.text
    assert denied.json()['code'] == 'ASSET_QUERY_INDEX_UNAVAILABLE'
    assert row['id'] not in denied.text and external.read_text() not in denied.text
    assert 'items' not in denied.json()
    link.unlink()
    assert query(rig).status_code == 200
