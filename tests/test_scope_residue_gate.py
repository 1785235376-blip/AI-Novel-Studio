"""The File scope owner refuses known-shaped interrupted writes before yield.

Temporary names are suspicion only: never prove project ownership or cleanup.
"""
import hashlib
import base64
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest

from app.creative.project_store import CreativeProjectStore
from app.experimental.store import ExperimentalStore
from app.services.asset_library_service import AssetLibraryService
from app.repositories.file.mutation_coordinator import workspace_mutation
from test_studio_asset_query import rig
from test_studio_workspace_identity_history_contract import audio_history


SCOPE = {"mode": "local", "novel_id": "synthetic"}
NID = "synthetic"


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_original(root):
    (root / 'novels' / NID).mkdir(parents=True, exist_ok=True)
    store = ExperimentalStore(root)
    creative = CreativeProjectStore(store)
    creative.incarnation(NID)
    with store.transaction(NID, SCOPE) as state:
        state['collections']['synthetic'] = {'before': {'value': 'original'}}
    return store, creative


def _crash_after_temp_fsync(root):
    child = r'''
import os
from pathlib import Path
from app.experimental.store import ExperimentalStore
root = Path(os.environ['SCOPE_RESIDUE_ROOT'])
scope = {'mode': 'local', 'novel_id': 'synthetic'}
store = ExperimentalStore(root)
def terminate_after_fsync(source, destination):
    os._exit(73)
os.replace = terminate_after_fsync
with store.transaction('synthetic', scope) as state:
    state['collections']['synthetic']['during'] = {'value': 'interrupted'}
'''
    env = os.environ.copy()
    env.update(SCOPE_RESIDUE_ROOT=str(root), PYTHONUTF8='1')
    run = subprocess.run([sys.executable, '-c', child], env=env, capture_output=True, timeout=30)
    assert run.returncode == 73, (run.returncode, run.stderr)


@pytest.mark.skipif(os.name != 'nt', reason='Windows name-filtered residue fence')
def test_interrupted_temp_blocks_write_before_callback_but_preserves_read(tmp_path):
    store, _ = _write_original(tmp_path)
    _crash_after_temp_fsync(tmp_path)
    path = store.path(NID, SCOPE)
    leftovers = list(path.parent.glob(path.name + '.*.tmp'))
    assert len(leftovers) == 1
    original, residue = _sha(path), _sha(leftovers[0])
    reopened = ExperimentalStore(tmp_path)
    assert reopened.read(NID, SCOPE)['collections']['synthetic'] == {'before': {'value': 'original'}}
    reached = []
    with pytest.raises(ValueError, match='EXPERIMENTAL_SCOPE_UNRECONCILED'):
        with reopened.transaction(NID, SCOPE) as state:
            reached.append('possible cross-owner effect')
            state['collections']['synthetic']['later'] = {'value': 'should not commit'}
    assert reached == []
    assert (_sha(path), _sha(leftovers[0])) == (original, residue)


def test_source_observation_retains_old_document_without_writing(tmp_path):
    store, creative = _write_original(tmp_path)
    _crash_after_temp_fsync(tmp_path)
    path = store.path(NID, SCOPE)
    leftovers = list(path.parent.glob(path.name + '.*.tmp'))
    before = (_sha(path), _sha(leftovers[0]))
    with creative.source_lease(NID, SCOPE, _observation=True) as view:
        assert view['collections']['synthetic'] == {'before': {'value': 'original'}}
    assert (_sha(path), _sha(leftovers[0])) == before


def test_observed_view_is_detached_after_lease(tmp_path):
    store, creative = _write_original(tmp_path)
    _crash_after_temp_fsync(tmp_path)
    with creative.source_lease(NID, SCOPE, _observation=True) as view:
        saved = view
    saved['collections']['synthetic']['after_return'] = {'value': 'detached'}
    assert 'after_return' not in store.read(NID, SCOPE)['collections']['synthetic']


def test_explicit_observation_does_not_initialize_missing_project_marker(tmp_path):
    store, creative = _write_original(tmp_path)
    marker = tmp_path / 'novels' / NID / 'creative_project_v2.json'
    marker.unlink()  # synthetic fixture only
    scope_before = _sha(store.path(NID, SCOPE))
    with pytest.raises(FileNotFoundError):
        with creative.source_lease(NID, SCOPE, _observation=True):
            pytest.fail('must not provision missing owner')
    assert not marker.exists()
    assert _sha(store.path(NID, SCOPE)) == scope_before


@pytest.mark.skipif(os.name != 'nt', reason='Windows name-filtered residue fence')
def test_observation_flag_is_not_a_general_cross_owner_capability(tmp_path):
    store, creative = _write_original(tmp_path)
    assets = AssetLibraryService(tmp_path)
    # Existing-only coordination does not turn this into a general write
    # capability when all original locks already exist and are warmed.
    with workspace_mutation(assets.root, 'asset-library'):
        pass
    _crash_after_temp_fsync(tmp_path)
    # Deliberate misuse demonstrates the limitation of the internal flag: it
    # must be reserved for statically audited production paths that do not
    # invoke other owners. This is not a claim that those paths did so.
    with creative.source_lease(NID, SCOPE, _observation=True):
        assets.create(NID, 'synthetic.bin', base64.b64encode(b'owned synthetic').decode(),
                      'application/octet-stream', 'file')
    assert len(list(assets.root.glob('*.bin'))) == 1
    assert len(list(assets.root.glob('*.json'))) == 1


@pytest.mark.skipif(os.name != 'nt', reason='Windows name-filtered residue fence')
def test_default_source_lease_blocks_real_cross_owner_write(tmp_path):
    store, creative = _write_original(tmp_path)
    assets = AssetLibraryService(tmp_path)
    _crash_after_temp_fsync(tmp_path)
    path = store.path(NID, SCOPE)
    leftovers = list(path.parent.glob(path.name + '.*.tmp'))
    before = (_sha(path), _sha(leftovers[0]))
    with pytest.raises(ValueError, match='EXPERIMENTAL_SCOPE_UNRECONCILED'):
        with creative.source_lease(NID, SCOPE):
            assets.create(NID, 'synthetic.bin', base64.b64encode(b'owned synthetic').decode(),
                          'application/octet-stream', 'file')
    assert not list(assets.root.glob('*.bin'))
    assert not list(assets.root.glob('*.json'))
    assert (_sha(path), _sha(leftovers[0])) == before


def test_observation_cannot_modify_scope_even_without_residue(tmp_path):
    store, _ = _write_original(tmp_path)
    before = _sha(store.path(NID, SCOPE))
    with pytest.raises(ValueError, match='EXPERIMENTAL_SCOPE_OBSERVATION_MUTATION'):
        with store.transaction(NID, SCOPE, _observation=True) as state:
            state['collections']['synthetic']['tampered'] = {'value': 1}
    assert _sha(store.path(NID, SCOPE)) == before


def test_normal_callback_failure_leaves_no_scope_temp(tmp_path):
    store, _ = _write_original(tmp_path)
    before = _sha(store.path(NID, SCOPE))
    with pytest.raises(RuntimeError, match='ordinary'):
        with store.transaction(NID, SCOPE) as state:
            state['collections']['synthetic']['later'] = {'value': 'rollback'}
            raise RuntimeError('ordinary')
    path = store.path(NID, SCOPE)
    assert _sha(path) == before
    assert not list(path.parent.glob(path.name + '.*.tmp'))


@pytest.mark.skipif(os.name != 'nt', reason='Windows name-filtered residue fence')
def test_new_suspected_residue_during_callback_prevents_scope_commit(tmp_path):
    store, _ = _write_original(tmp_path)
    path = store.path(NID, SCOPE)
    residue = path.parent / (path.name + '.new-unknown.tmp')
    original = _sha(path)
    with pytest.raises(ValueError, match='EXPERIMENTAL_SCOPE_UNRECONCILED'):
        with store.transaction(NID, SCOPE) as state:
            state['collections']['synthetic']['late'] = {'value': 'uncommitted'}
            # Fault injection models an uncooperative actor, not an original
            # cooperating writer; never infer project ownership from its name.
            residue.write_bytes(b'unowned synthetic bytes')
    assert _sha(path) == original
    assert residue.read_bytes() == b'unowned synthetic bytes'


@pytest.mark.skipif(os.name != 'nt', reason='Windows name-filtered residue fence')
def test_native_query_failure_refuses_before_callback(tmp_path, monkeypatch):
    import ctypes
    store, _ = _write_original(tmp_path)

    class Function:
        def __init__(self, callback): self.callback = callback
        def __call__(self, *args): return self.callback(*args)
    def denied(*_):
        ctypes.set_last_error(5)  # deterministic fault injection: access denied
        return ctypes.c_void_p(-1).value
    class Kernel:
        FindFirstFileW = Function(denied)
        FindClose = Function(lambda *_: 1)
        GetDriveTypeW = Function(lambda *_: 3)
    monkeypatch.setattr(ctypes, 'WinDLL', lambda *_, **__: Kernel())
    touched = []
    with pytest.raises(ValueError, match='EXPERIMENTAL_SCOPE_UNRECONCILED'):
        with store.transaction(NID, SCOPE):
            touched.append(True)
    assert touched == []


@pytest.mark.skipif(os.name != 'nt', reason='Windows name-filtered residue fence')
def test_unknown_or_remote_drive_is_not_treated_as_same_host(tmp_path, monkeypatch):
    import ctypes
    store, _ = _write_original(tmp_path)

    class Function:
        def __init__(self, callback): self.callback = callback
        def __call__(self, *args): return self.callback(*args)
    def should_not_query(*_):
        raise AssertionError('remote drive must not be scanned')
    class Kernel:
        FindFirstFileW = Function(should_not_query)
        FindClose = Function(lambda *_: 1)
        GetDriveTypeW = Function(lambda *_: 4)  # injected remote-drive result
    monkeypatch.setattr(ctypes, 'WinDLL', lambda *_, **__: Kernel())
    with pytest.raises(ValueError, match='EXPERIMENTAL_SCOPE_UNRECONCILED'):
        with store.transaction(NID, SCOPE):
            raise AssertionError('must not reach the write callback')


def test_foreign_scope_residue_does_not_claim_or_expose_other_content(tmp_path):
    store, _ = _write_original(tmp_path)
    path = store.path(NID, SCOPE)
    other = path.parent / ('f' * 64 + '.json.fake.tmp')
    other.write_bytes(b'unowned synthetic data')
    before = _sha(other)
    with store.transaction(NID, SCOPE) as state:
        state['collections']['synthetic']['safe'] = {'value': 'different scope'}
    assert _sha(other) == before


@pytest.mark.parametrize('alias', ['', '/v1'])
def test_http_asset_get_and_download_remain_available(audio_history, alias):
    e = audio_history
    path = e.rig.workspace.store.path(e.rig.nid, e.rig.scope)
    path.parent.mkdir(parents=True, exist_ok=True)
    residue = path.parent / (path.name + '.synthetic.tmp')
    residue.write_bytes(b'unverified synthetic interruption')
    before = _sha(residue)
    url = f'/api{alias}/projects/{e.rig.nid}/studio/assets/{e.asset["id"]}'
    result = e.client.get(url, headers=e.headers)
    download = e.client.get(url + '/download', headers=e.headers)
    assert result.status_code == 200, result.text
    assert download.status_code == 200 and download.content == e.content
    assert _sha(residue) == before


def test_cooperating_writer_waits_for_live_temp_then_succeeds(tmp_path):
    store, _ = _write_original(tmp_path)
    ready, release = tmp_path / 'ready', tmp_path / 'release'
    code1 = r'''
import os, time
from pathlib import Path
from app.experimental.store import ExperimentalStore
root = Path(os.environ['SCOPE_RESIDUE_ROOT'])
scope = {'mode':'local', 'novel_id':'synthetic'}
ready, release = Path(os.environ['SCOPE_READY']), Path(os.environ['SCOPE_RELEASE'])
original = os.replace
def hold_after_fsync(source, destination):
    ready.write_text('ready', encoding='utf-8')
    deadline = time.monotonic() + 15
    while not release.exists():
        if time.monotonic() >= deadline: raise RuntimeError('timed out')
        time.sleep(.02)
    return original(source, destination)
os.replace = hold_after_fsync
with ExperimentalStore(root).transaction('synthetic', scope) as state:
    state['collections']['synthetic']['first'] = {'value': 'first'}
'''
    code2 = r'''
import os
from pathlib import Path
from app.experimental.store import ExperimentalStore
root = Path(os.environ['SCOPE_RESIDUE_ROOT'])
scope = {'mode':'local', 'novel_id':'synthetic'}
with ExperimentalStore(root).transaction('synthetic', scope) as state:
    state['collections']['synthetic']['second'] = {'value': 'second'}
'''
    env = os.environ.copy()
    env.update(SCOPE_RESIDUE_ROOT=str(tmp_path), SCOPE_READY=str(ready),
               SCOPE_RELEASE=str(release), PYTHONUTF8='1')
    first = subprocess.Popen([sys.executable, '-c', code1], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    second = None
    try:
        deadline = time.monotonic() + 15
        while not ready.exists():
            assert first.poll() is None and time.monotonic() < deadline
            time.sleep(.02)
        path = store.path(NID, SCOPE)
        assert list(path.parent.glob(path.name + '.*.tmp'))
        second = subprocess.Popen([sys.executable, '-c', code2], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        time.sleep(.4)
        assert second.poll() is None
        release.write_text('release', encoding='utf-8')
        out1, err1 = first.communicate(timeout=20)
        out2, err2 = second.communicate(timeout=20)
        assert first.returncode == second.returncode == 0, (out1, err1, out2, err2)
    finally:
        if first.poll() is None:
            first.kill()
            first.wait(timeout=10)
        if second is not None and second.poll() is None:
            second.kill()
            second.wait(timeout=10)
    rows = store.read(NID, SCOPE)['collections']['synthetic']
    assert rows['first']['value'] == 'first' and rows['second']['value'] == 'second'
    assert not list(path.parent.glob(path.name + '.*.tmp'))
