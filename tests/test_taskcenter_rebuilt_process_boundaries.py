"""Fresh POSIX process evidence for each original single-file commit boundary.

Not a multi-file crash-atomicity, power-loss, Windows, or backup-replay test.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import select
import signal
import subprocess
import sys

import pytest

from app.experimental.store import ExperimentalStore, TEAM_COLLECTION, TEAM_LIFECYCLE
from app.creative.project_store import CreativeProjectStore
from app.repositories.file.identity import FileIdentityRepository
from app.repositories.file.scope import FileScopeRepository, FileAuthorizationRepository

pytestmark = [pytest.mark.file_backend_only, pytest.mark.skipif(os.name != 'posix', reason='POSIX process boundary probes')]
KINDS = ['identity', 'scope', 'grants', 'team']
SCOPE = {'mode':'collaboration','novel_id':'book','workspace_id':'w','storyline_id':'s','branch_id':'b'}


def repository(root, kind):
    if kind == 'identity': return FileIdentityRepository(root)
    if kind == 'scope': return FileScopeRepository(root)
    if kind == 'grants': return FileAuthorizationRepository(root)
    return ExperimentalStore(root)


def target(root, kind):
    r = repository(root, kind)
    return r.path('book', SCOPE) if kind == 'team' else r.path


def append(root, kind, name):
    r = repository(root, kind)
    if kind == 'identity': r.save_user({'id':name, 'status':'ACTIVE'})
    elif kind == 'scope': r.create('branches', {'id':name,'workspace_id':'w','project_id':'book','storyline_id':'s'})
    elif kind == 'grants': r.save_permission_assignment({'id':name,'principal_id':'u','permission':'domain.read','domain':'NOVEL','scope':{'kind':'WORKSPACE','workspace_id':'w'}})
    else:
        with r.transaction('book', SCOPE) as doc:
            doc['collections'].setdefault(TEAM_COLLECTION, {})[name] = {'id':name, 'status':'QUEUED'}


def seed(root, kind):
    root.mkdir(parents=True, exist_ok=True)
    if kind == 'team':
        (root/'novels/book').mkdir(parents=True)
        CreativeProjectStore(ExperimentalStore(root)).incarnation('book')
    append(root, kind, 'seed')


def paired_rows(root, kind):
    """Original reader validates persisted evidence before inspecting pairing."""
    r = repository(root, kind)
    if kind == 'team':
        observation = r.capture_committed_collection('book', SCOPE, TEAM_COLLECTION)
        return {x['id'] for x in observation['rows']}, observation['row_lifecycles']
    doc = r._read()
    if kind == 'identity': return {x['id'] for x in doc['users']}, doc['_identity_lifecycle_v1']['users']
    key, rows = ('_scope_lifecycle_v1','branches') if kind == 'scope' else ('_grant_lifecycle_v1','permission_assignments')
    return {x['id'] for x in doc[rows]}, doc[key]['rows'][rows]


CHILD = r'''
import sys, os
from pathlib import Path
from test_taskcenter_rebuilt_process_boundaries import append, target
from app import storage
from app.repositories.file import mutation_coordinator
root, kind, name, mode = Path(sys.argv[1]),sys.argv[2],sys.argv[3],sys.argv[4]
path = target(root,kind).resolve()
original_replace = storage.os.replace
original_lock = mutation_coordinator._lock_file

def replace(src,dst):
    if Path(dst).resolve() != path: return original_replace(src,dst)
    if mode == 'after': original_replace(src,dst)
    print('COMMIT_READY',flush=True)
    if mode in ('before','after','hold'): sys.stdin.readline()
    if mode != 'after': original_replace(src,dst)

def lock(handle):
    if mode == 'contend': print('LOCK_ATTEMPT',flush=True)
    return original_lock(handle)
storage.os.replace=replace
mutation_coordinator._lock_file=lock
append(root,kind,name)
print('DONE',flush=True)
'''


def child(root, kind, name, mode):
    env = os.environ.copy()
    env['PYTHONPATH'] = str(Path(__file__).parent) + os.pathsep + str(Path(__file__).parents[1])
    return subprocess.Popen([sys.executable,'-u','-c',CHILD,str(root),kind,name,mode],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=env)


def line(proc, expected):
    readable,_,_ = select.select([proc.stdout], [], [], 40)
    assert readable, ('child boundary timeout',proc.poll())
    value = proc.stdout.readline().strip()
    assert value == expected, (value,proc.poll(), proc.stderr.read() if proc.poll() is not None else '')


def cleanup(proc):
    if proc.poll() is None: proc.kill()
    proc.communicate(timeout=40)


@pytest.mark.parametrize('kind',KINDS)
@pytest.mark.parametrize('boundary',['before','after'])
def test_kill_at_replace_pairs_business_and_lifecycle(tmp_path,kind,boundary):
    seed(tmp_path,kind); path=target(tmp_path,kind); before=path.read_bytes(); ids,meta=paired_rows(tmp_path,kind)
    proc=child(tmp_path,kind,'new',boundary)
    try:
        line(proc,'COMMIT_READY'); proc.kill(); proc.communicate(timeout=40)
        assert proc.returncode == -signal.SIGKILL
    finally: cleanup(proc)
    actual,evidence=paired_rows(tmp_path,kind)
    assert actual == set(evidence)
    assert evidence['seed'] == meta['seed']
    if boundary=='before':
        assert path.read_bytes()==before
        assert actual==ids
    else:
        assert actual==ids|{'new'} and path.read_bytes()!=before
        assert evidence['new'] != evidence['seed']
    append(tmp_path,kind,'reopened')
    assert paired_rows(tmp_path,kind)[0] == actual|{'reopened'}


@pytest.mark.parametrize('kind',KINDS)
@pytest.mark.parametrize('fault',['fsync','replace'])
def test_write_failure_preserves_exact_bytes_and_next_commit(tmp_path,kind,fault,monkeypatch):
    seed(tmp_path,kind);path=target(tmp_path,kind);before=path.read_bytes(); observed=paired_rows(tmp_path,kind)
    from app import storage
    def fail(*a,**k): raise OSError('synthetic commit failure')
    with monkeypatch.context() as m:
        m.setattr(storage.os,fault,fail)
        with pytest.raises(OSError,match='synthetic commit failure'): append(tmp_path,kind,'failed')
    assert path.read_bytes()==before
    assert paired_rows(tmp_path,kind)==observed
    append(tmp_path,kind,'recovered')
    ids,meta=paired_rows(tmp_path,kind)
    assert ids==set(meta)=={'seed','recovered'}


@pytest.mark.parametrize('kind',KINDS)
def test_real_process_lock_serializes_complete_commits(tmp_path,kind):
    seed(tmp_path,kind)
    first=child(tmp_path,kind,'first','hold');second=None
    try:
        line(first,'COMMIT_READY')
        second=child(tmp_path,kind,'second','contend')
        line(second,'LOCK_ATTEMPT')
        # First holds the actual original owner lock at replace. No second
        # commit may pass it, and disk still contains the original whole file.
        assert {x for x in json.loads(target(tmp_path,kind).read_text())}  # readable JSON
        assert second.poll() is None
        first.stdin.write('\n');first.stdin.flush()
        out,err=first.communicate(timeout=40)
        assert first.returncode==0,(out,err)
        out,err=second.communicate(timeout=40)
        assert second.returncode==0,(out,err)
        assert 'COMMIT_READY' in out and 'DONE' in out
    finally:
        cleanup(first)
        if second is not None:cleanup(second)
    ids,meta=paired_rows(tmp_path,kind)
    assert ids==set(meta)=={'seed','first','second'}
    assert len(set(meta.values()))==3
