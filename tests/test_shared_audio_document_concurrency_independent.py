"""Original File scope transaction evidence; no quota admission is implemented."""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest

from app.experimental.audio_shared_document_measurement import plan_file_scope_replacement
from app.experimental.store import ExperimentalStore, canonical
from test_audio_shared_replacement_plan_independent import candidate
from test_studio_asset_query import rig

pytestmark = pytest.mark.file_backend_only
NAME = 'audio_v2_mix_proposals'
ROOT = Path(__file__).resolve().parents[1]


def encoded(value):
    return canonical(value).encode('utf-8')


def row_for(rig):
    row = candidate()
    row.update(novel_id=rig.nid, scope=copy.deepcopy(rig.scope))
    return row


def test_external_change_during_original_transaction_rejects_stale_candidate(rig, tmp_path):
    """A simulated uncoordinated writer cannot be overwritten by the scope owner."""
    store = rig.workspace.store.store
    rig.workspace.store.incarnation(rig.nid)
    with store.transaction(rig.nid, rig.scope) as doc:
        doc['collections']['unrelated_synthetic'] = {'body': {'text': '旧文本☃'}}
    path = store.path(rig.nid, rig.scope)
    before = path.read_bytes()
    replacement = store.read(rig.nid, rig.scope)
    row = row_for(rig)
    replacement['collections'][NAME] = {row['id']: row}
    plan = plan_file_scope_replacement(before, encoded(replacement), rig.nid, rig.scope)
    external = tmp_path / 'external-write.json'
    child = r'''
import json, sys
from pathlib import Path
from app.experimental.store import canonical
from app.storage import atomic_write
path, evidence = map(Path, sys.argv[1:])
doc = json.loads(path.read_text(encoding='utf-8'))
doc['collections']['unrelated_synthetic']['body']['text'] = '外部更新雪'
payload = canonical(doc)
atomic_write(path, payload)
evidence.write_text(payload, encoding='utf-8')
'''
    with pytest.raises(ValueError, match='EXPERIMENTAL_SCOPE_CONCURRENT_WRITE'):
        with store.transaction(rig.nid, rig.scope) as doc:
            doc['collections'][NAME] = {row['id']: row}
            result = subprocess.run([sys.executable, '-c', child, str(path), str(external)],
                cwd=ROOT, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=20)
            assert result.returncode == 0, result.stdout + result.stderr
    current = path.read_bytes()
    assert current == external.read_bytes()
    assert hashlib.sha256(current).hexdigest() != plan['previous_sha256']
    after = ExperimentalStore(rig.root, 'file', '').read(rig.nid, rig.scope)
    assert after['collections']['unrelated_synthetic']['body']['text'] == '外部更新雪'
    assert NAME not in after['collections']


def test_two_file_owner_processes_serialize_and_preserve_both_updates(rig, tmp_path):
    """Cooperating writers share the original scope lock across processes."""
    store = rig.workspace.store.store
    rig.workspace.store.incarnation(rig.nid)
    with store.transaction(rig.nid, rig.scope) as doc:
        doc['collections']['unrelated_synthetic'] = {'body': {'text': '初始'}}
    before = store.path(rig.nid, rig.scope).read_bytes()
    row = row_for(rig)
    marker = tmp_path / 'child-attempt.txt'
    inside = tmp_path / 'child-inside.txt'
    child = r'''
from pathlib import Path
import sys
from app.experimental.store import ExperimentalStore
root, nid, marker, inside = sys.argv[1:]
scope = {'mode':'local', 'novel_id':nid}
store = ExperimentalStore(Path(root), 'file', '')
Path(marker).write_text('ready', encoding='utf-8')
with store.transaction(nid, scope) as doc:
    Path(inside).write_text('inside', encoding='utf-8')
    doc['collections']['unrelated_synthetic']['body']['text'] = '另一个进程'
'''
    process = None
    try:
        with store.transaction(rig.nid, rig.scope) as doc:
            doc['collections'][NAME] = {row['id']: row}
            process = subprocess.Popen([sys.executable, '-u', '-c', child, str(rig.root), rig.nid, str(marker), str(inside)],
                cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace')
            deadline = time.monotonic() + 15
            while not marker.exists() and time.monotonic() < deadline:
                assert process.poll() is None, process.communicate()
                time.sleep(.025)
            assert marker.exists(), 'child did not reach original scope transaction'
            # During the parent's transaction, no cooperating child can publish.
            blocked_until = time.monotonic() + .5
            while time.monotonic() < blocked_until:
                assert process.poll() is None
                assert not inside.exists(), 'child entered the scope during the parent transaction'
                time.sleep(.025)
            assert store.path(rig.nid, rig.scope).read_bytes() == before
        stdout, stderr = process.communicate(timeout=20)
        assert process.returncode == 0, stdout + stderr
        assert inside.exists()
    finally:
        if process is not None and process.poll() is None:
            process.kill()
            process.communicate(timeout=10)
    reopened = ExperimentalStore(rig.root, 'file', '').read(rig.nid, rig.scope)
    assert reopened['collections'][NAME][row['id']]['content_sha256'] == row['content_sha256']
    assert reopened['collections']['unrelated_synthetic']['body']['text'] == '另一个进程'
