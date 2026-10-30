"""Independent real File process controls; only synthetic test data."""
import base64
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest

from app.experimental.store import ExperimentalStore
from test_studio_asset_query import rig
from test_studio_workspace_identity_history_contract import audio_history

pytestmark = [pytest.mark.file_backend_only, pytest.mark.skipif(os.name != 'nt', reason='Windows scope fence')]


def crash_scope(root, nid):
    code = r'''
import os
from pathlib import Path
from app.experimental.store import ExperimentalStore
nid = os.environ['SYNTHETIC_NID']
scope = {'mode': 'local', 'novel_id': nid}
def die(*_): os._exit(74)
os.replace = die
with ExperimentalStore(Path(os.environ['SYNTHETIC_ROOT'])).transaction(nid, scope) as state:
    state['collections']['synthetic']['interrupted'] = {'value': 'never committed'}
'''
    env = os.environ.copy()
    env.update(SYNTHETIC_ROOT=str(root), SYNTHETIC_NID=nid, PYTHONUTF8='1')
    run = subprocess.run([sys.executable, '-c', code], env=env, capture_output=True, timeout=30)
    assert run.returncode == 74, (run.returncode, run.stderr)
    return env


@pytest.mark.parametrize('lease', ['transaction', 'source_lease'])
@pytest.mark.parametrize('alias', ['', '/v1'])
def test_new_process_after_crash_blocks_real_asset_create_but_preserves_http_download(audio_history, lease, alias):
    e = audio_history
    store = e.rig.workspace.store.store
    with store.transaction(e.rig.nid, e.rig.scope) as doc:
        doc['collections']['synthetic'] = {'committed': {'value': 'preserved'}}
    env = crash_scope(e.rig.root, e.rig.nid)
    path = store.path(e.rig.nid, e.rig.scope)
    residue = list(path.parent.glob(path.name + '.*.tmp'))
    assert len(residue) == 1
    before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in [path, residue[0]]}
    asset_files = {p.name for p in e.rig.assets.root.iterdir() if p.suffix in ('.bin', '.json')}
    code = r'''
import base64, os, sys
from pathlib import Path
from app.creative.project_store import CreativeProjectStore
from app.experimental.store import ExperimentalStore
from app.services.asset_library_service import AssetLibraryService
root, nid = Path(os.environ['SYNTHETIC_ROOT']), os.environ['SYNTHETIC_NID']
scope = {'mode': 'local', 'novel_id': nid}
store = ExperimentalStore(root)
owner = CreativeProjectStore(store)
try:
    cm = store.transaction(nid, scope) if os.environ['SYNTHETIC_LEASE'] == 'transaction' else owner.source_lease(nid, scope)
    with cm:
        AssetLibraryService(root).create(nid, 'never-created.bin', base64.b64encode(b'synthetic').decode(),
                                         'application/octet-stream', 'file')
except ValueError as exc:
    if str(exc) != 'EXPERIMENTAL_SCOPE_UNRECONCILED': raise
    print('BLOCKED_BEFORE_ASSET_CREATE')
    sys.exit(0)
raise AssertionError('asset write was not fenced')
'''
    env['SYNTHETIC_LEASE'] = lease
    run = subprocess.run([sys.executable, '-c', code], env=env, capture_output=True, timeout=30)
    assert run.returncode == 0, (run.returncode, run.stdout, run.stderr)
    assert run.stdout.decode('utf-8').strip() == 'BLOCKED_BEFORE_ASSET_CREATE'
    assert {p.name for p in e.rig.assets.root.iterdir() if p.suffix in ('.bin', '.json')} == asset_files
    assert {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in [path, residue[0]]} == before
    assert ExperimentalStore(e.rig.root).read(e.rig.nid, e.rig.scope)['collections']['synthetic'] == {'committed': {'value': 'preserved'}}
    url = f'/api{alias}/projects/{e.rig.nid}/studio/assets/{e.asset["id"]}'
    assert e.client.get(url, headers=e.headers).status_code == 200
    downloaded = e.client.get(url + '/download', headers=e.headers)
    assert downloaded.status_code == 200 and downloaded.content == e.content


def test_active_scope_writer_serializes_real_source_lease_and_asset_create(tmp_path):
    nid = 'synthetic'
    scope = {'mode': 'local', 'novel_id': nid}
    (tmp_path / 'novels' / nid).mkdir(parents=True)
    store = ExperimentalStore(tmp_path)
    with store.transaction(nid, scope) as doc:
        doc['collections']['synthetic'] = {'before': {}}
    ready, release = tmp_path / 'synthetic-ready', tmp_path / 'synthetic-release'
    env = os.environ.copy()
    env.update(SYNTHETIC_ROOT=str(tmp_path), SYNTHETIC_NID=nid, SYNTHETIC_READY=str(ready),
               SYNTHETIC_RELEASE=str(release), PYTHONUTF8='1')
    first_code = r'''
import os, time
from pathlib import Path
from app.experimental.store import ExperimentalStore
root, nid = Path(os.environ['SYNTHETIC_ROOT']), os.environ['SYNTHETIC_NID']
original = os.replace
def wait(source, dest):
    Path(os.environ['SYNTHETIC_READY']).write_text('ready', encoding='utf-8')
    deadline = time.monotonic() + 15
    while not Path(os.environ['SYNTHETIC_RELEASE']).exists():
        if time.monotonic() > deadline: raise RuntimeError('fixture timeout')
        time.sleep(.02)
    return original(source, dest)
os.replace = wait
with ExperimentalStore(root).transaction(nid, {'mode':'local', 'novel_id':nid}) as doc:
    doc['collections']['synthetic']['first'] = {'value':'committed'}
'''
    second_code = r'''
import base64, os
from pathlib import Path
from app.creative.project_store import CreativeProjectStore
from app.experimental.store import ExperimentalStore
from app.services.asset_library_service import AssetLibraryService
root, nid = Path(os.environ['SYNTHETIC_ROOT']), os.environ['SYNTHETIC_NID']
scope = {'mode':'local', 'novel_id':nid}
with CreativeProjectStore(ExperimentalStore(root)).source_lease(nid, scope):
    AssetLibraryService(root).create(nid, 'synthetic.bin', base64.b64encode(b'synthetic').decode(),
                                     'application/octet-stream', 'file')
'''
    first = subprocess.Popen([sys.executable, '-c', first_code], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    second = None
    try:
        deadline = time.monotonic() + 15
        while not ready.exists():
            assert first.poll() is None and time.monotonic() < deadline
            time.sleep(.02)
        second = subprocess.Popen([sys.executable, '-c', second_code], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        time.sleep(.3)
        assert second.poll() is None
        release.write_text('release', encoding='utf-8')
        out1, err1 = first.communicate(timeout=20)
        out2, err2 = second.communicate(timeout=20)
        assert first.returncode == second.returncode == 0, (out1, err1, out2, err2)
    finally:
        if first.poll() is None: first.kill(); first.wait(timeout=10)
        if second is not None and second.poll() is None: second.kill(); second.wait(timeout=10)
    assert store.read(nid, scope)['collections']['synthetic']['first'] == {'value': 'committed'}
    assert len(list((tmp_path / 'assets').glob('*.bin'))) == 1
