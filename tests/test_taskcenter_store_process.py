"""Synthetic POSIX process probes; not power-loss or backup-replay guarantees."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

import pytest

from app.creative.project_store import CreativeProjectStore
from app.experimental.store import ExperimentalStore

pytestmark = [pytest.mark.file_backend_only, pytest.mark.skipif(os.name != 'posix', reason='POSIX SIGKILL probe')]
SCOPE = {'mode': 'local', 'novel_id': 'book'}
JOBS = 'semantic_import_jobs'


def setup_store(root):
    (root / 'novels' / 'book').mkdir(parents=True)
    store = ExperimentalStore(root)
    CreativeProjectStore(store).incarnation('book')
    with store.transaction('book', SCOPE) as doc:
        doc['collections'][JOBS] = {'job': {'id': 'job', 'novel_id': 'book', 'scope': SCOPE, 'version': 1, 'status': 'QUEUED'}}
    return store


def wait_file(path, process):
    deadline = time.monotonic() + 15
    while not path.exists() and time.monotonic() < deadline:
        if process.poll() is not None:
            raise AssertionError(process.communicate())
        time.sleep(.02)
    assert path.exists(), 'child failed to reach injected commit boundary'


@pytest.mark.parametrize('boundary', ['before_replace', 'after_replace'])
def test_killed_commit_keeps_business_and_evidence_paired(tmp_path, boundary):
    store = setup_store(tmp_path)
    before = store.capture_committed_collection('book', SCOPE)
    ready = tmp_path / 'boundary-ready'
    code = r'''
import sys,time
from pathlib import Path
from app.experimental.store import ExperimentalStore
from app import storage
root, boundary = Path(sys.argv[1]), sys.argv[2]
original = storage.os.replace
def intercepted(source, destination):
    if boundary == 'after_replace': original(source, destination)
    (root/'boundary-ready').write_text('ready')
    time.sleep(60)
    if boundary == 'before_replace': original(source, destination)
storage.os.replace = intercepted
store = ExperimentalStore(root)
with store.transaction('book', {'mode':'local','novel_id':'book'}) as doc:
    doc['collections']['semantic_import_jobs']['job']['status'] = 'RUNNING'
'''
    child = subprocess.Popen([sys.executable, '-c', code, str(tmp_path), boundary], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        wait_file(ready, child)
        child.kill()
        child.communicate(timeout=10)
        assert child.returncode == -signal.SIGKILL
    finally:
        if child.poll() is None:
            child.kill(); child.communicate(timeout=10)
    observed = ExperimentalStore(tmp_path).capture_committed_collection('book', SCOPE)
    assert observed['project_identity'] == before['project_identity']
    assert observed['document_incarnation'] == before['document_incarnation']
    if boundary == 'before_replace':
        assert observed == before
    else:
        assert observed['rows'][0]['status'] == 'RUNNING'
        assert observed['row_lifecycles']['job'] != before['row_lifecycles']['job']


def test_two_process_original_lock_serializes_updates(tmp_path):
    store = setup_store(tmp_path)
    before = store.capture_committed_collection('book', SCOPE)
    code = r'''
import json,sys
from app.experimental.store import ExperimentalStore
store=ExperimentalStore(sys.argv[1]); scope={'mode':'local','novel_id':'book'}
for _ in range(8):
    with store.transaction('book',scope) as doc:
        doc['collections']['semantic_import_jobs']['job']['version'] += 1
print('done')
'''
    children = [subprocess.Popen([sys.executable, '-c', code, str(tmp_path)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for _ in range(2)]
    try:
        for child in children:
            stdout, stderr = child.communicate(timeout=30)
            assert child.returncode == 0, stderr
            assert stdout.strip() == 'done'
    finally:
        for child in children:
            if child.poll() is None:
                child.kill(); child.communicate(timeout=10)
    observed = store.capture_committed_collection('book', SCOPE)
    assert observed['rows'][0]['version'] == 17
    assert observed['row_lifecycles']['job'] != before['row_lifecycles']['job']
