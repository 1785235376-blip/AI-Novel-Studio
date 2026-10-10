from __future__ import annotations
import copy
import os
import threading
import uuid
from types import SimpleNamespace
import pytest
from app.experimental.common import DomainService, StaleSourceError
from app.experimental.flags import FLAGS, LEGACY_FLAGS, enabled_flags, require_flag
from app.experimental.store import ExperimentalStore
from app.services.v1_capability_service import CapabilityVersionConflict
from fastapi import HTTPException


def test_flags_are_default_off_and_v1_mode_overrides(monkeypatch):
    monkeypatch.delenv('EXPERIMENTAL_FEATURES', raising=False)
    monkeypatch.delenv('V1_ACCEPTANCE_MODE', raising=False)
    assert not enabled_flags()
    with pytest.raises(HTTPException) as exc:
        require_flag('advanced_planning_v2')
    assert exc.value.status_code == 404
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', '*,all,unknown,experimental.advanced_planning_v2')
    assert enabled_flags() == {'advanced_planning_v2'}
    monkeypatch.setenv('V1_ACCEPTANCE_MODE', 'true')
    assert not enabled_flags()
    assert len(LEGACY_FLAGS) == 9
    assert set(LEGACY_FLAGS).issubset(FLAGS)


@pytest.fixture(params=['file', pytest.param('postgres', marks=pytest.mark.postgres_backend_only)])
def store(request, tmp_path):
    url = os.getenv('TEST_POSTGRES_DATABASE_URL', '')
    if request.param == 'postgres' and not url:
        pytest.fail('real PostgreSQL fixture requires TEST_POSTGRES_DATABASE_URL')
    return ExperimentalStore(tmp_path, request.param, url)


def test_atomic_restart_conflict_and_scope_isolation(store):
    nid = f'r3-{uuid.uuid4()}'
    scope = {'mode': 'local', 'novel_id': nid}
    chapters = {'chapter': {'id': 'chapter', 'novel_id': nid, 'version': 1, 'content': 'source'}}
    novels = SimpleNamespace(get=lambda n: {'id': n})
    chapter_service = SimpleNamespace(get=lambda cid: chapters[cid])
    service = DomainService(store, novels, chapter_service)
    sources = service.sources(nid, ['chapter'])
    row = service.create(nid, scope, 'author', 'plans', {'title': 'Original', 'sources': sources})
    restored = DomainService(ExperimentalStore(store.root, store.backend, store.database_url), novels, chapter_service)
    assert restored.get(nid, scope, 'plans', row['id']) == row
    other = {'mode': 'collaboration', 'novel_id': nid, 'workspace_id': 'w', 'storyline_id': 's', 'branch_id': 'b'}
    assert restored.list(nid, other, 'plans') == []
    with pytest.raises(FileNotFoundError):
        restored.get(nid, other, 'plans', row['id'])
    updated = restored.mutate(nid, scope, 'editor', 'plans', row['id'], 1, lambda r: r.update(title='Reviewed'))
    assert updated['version'] == 2 and updated['history'][0]['title'] == 'Original'
    assert updated['created_by'] == 'author' and updated['updated_by'] == 'editor'
    with pytest.raises(CapabilityVersionConflict):
        service.mutate(nid, scope, 'old', 'plans', row['id'], 1, lambda r: r.update(title='Bad'))
    with pytest.raises(RuntimeError):
        with store.transaction(nid, scope) as doc:
            doc['collections']['plans'][row['id']]['title'] = 'Rollback'
            doc['collections']['other'] = {'a': {'value': 1}}
            raise RuntimeError('simulated crash gap')
    assert restored.get(nid, scope, 'plans', row['id'])['title'] == 'Reviewed'
    assert 'other' not in store.read(nid, scope)['collections']
    chapters['chapter']['content'] = 'changed without version bump'
    with pytest.raises(StaleSourceError):
        service.assert_sources(nid, sources)


def test_concurrent_compare_and_swap_only_one_winner(store):
    nid = f'r3-{uuid.uuid4()}'
    scope = {'mode': 'local', 'novel_id': nid}
    service = DomainService(store, SimpleNamespace(get=lambda n: {}), None)
    row = service.create(nid, scope, 'author', 'items', {'count': 0})
    barrier = threading.Barrier(2)
    results = []
    def contender():
        other = DomainService(ExperimentalStore(store.root, store.backend, store.database_url), service.novels, None)
        barrier.wait()
        try:
            other.mutate(nid, scope, 'author', 'items', row['id'], 1, lambda r: r.update(count=r['count']+1))
            results.append('success')
        except CapabilityVersionConflict:
            results.append('conflict')
    workers = [threading.Thread(target=contender) for _ in range(2)]
    for worker in workers: worker.start()
    for worker in workers: worker.join(10)
    assert sorted(results) == ['conflict', 'success']
    assert service.get(nid, scope, 'items', row['id'])['count'] == 1


def test_corrupt_file_fails_closed(tmp_path):
    store = ExperimentalStore(tmp_path)
    scope = {'mode': 'local', 'novel_id': 'n'}
    path = store.path('n', scope)
    path.parent.mkdir(parents=True)
    path.write_text('{broken')
    with pytest.raises(ValueError):
        with store.transaction('n', scope):
            pass
    assert path.read_text() == '{broken'


def test_scope_rejects_incomplete_or_cross_project(tmp_path):
    store = ExperimentalStore(tmp_path)
    for scope in ({'mode': 'local', 'novel_id': 'other'}, {'mode': 'collaboration', 'novel_id': 'n'}, {'mode': 'all', 'novel_id': 'n'}):
        with pytest.raises(ValueError):
            store.read('n', scope)


def test_packaged_migration_is_additive_and_opt_in(monkeypatch):
    from pathlib import Path
    from app.packaging.postgres_migrations import load_packaged_migrations, PackagedPostgresMigrationRunner
    root = Path(__file__).resolve().parents[1] / 'database' / 'migrations'
    before = load_packaged_migrations(root)
    after = load_packaged_migrations(root, include_experimental=True)
    assert after[:-1] == before
    assert after[-1].migration_id == '0003_experimental_scope_documents'
    assert 'DROP TABLE' not in '\n'.join(line for line in after[-1].sql.splitlines() if not line.startswith('--'))
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'advanced_planning_v2')
    monkeypatch.delenv('V1_ACCEPTANCE_MODE', raising=False)
    assert len(PackagedPostgresMigrationRunner(migrations_path=root, execute_sql=lambda sql: None).migrations) == len(before) + 1
    monkeypatch.setenv('V1_ACCEPTANCE_MODE', 'true')
    assert PackagedPostgresMigrationRunner(migrations_path=root, execute_sql=lambda sql: None).migrations == before


def test_corrupt_collection_cannot_escape_scope(tmp_path):
    scope = {'mode': 'local', 'novel_id': 'n'}
    store = ExperimentalStore(tmp_path)
    with store.transaction('n', scope) as doc:
        doc['collections']['records'] = {'foreign': {'id':'foreign', 'novel_id':'other', 'scope':scope}}
    service = DomainService(store, SimpleNamespace(get=lambda nid: {}), None)
    with pytest.raises(ValueError, match='scope metadata'):
        service.list('n', scope, 'records')


def test_real_process_restart_and_abrupt_transaction_exit(store):
    import json
    import subprocess
    import sys
    nid = f'r3-process-{uuid.uuid4()}'
    scope = {'mode':'local', 'novel_id':nid}
    service = DomainService(store, SimpleNamespace(get=lambda nid: {}), None)
    record = service.create(nid, scope, 'author', 'restart', {'title':'Durable source'})
    environment = dict(os.environ, R3_TEST_DATABASE_URL=store.database_url)
    script = '''import json,os,sys
from app.experimental.store import ExperimentalStore
root,backend,nid,rid,mode=sys.argv[1:]
scope={'mode':'local','novel_id':nid}
store=ExperimentalStore(root,backend,os.environ.get('R3_TEST_DATABASE_URL',''))
if mode=='crash':
    with store.transaction(nid,scope) as doc:
        doc['collections']['restart'][rid]['title']='Uncommitted crash'
        os._exit(71)
else:
    print(json.dumps(store.read(nid,scope)['collections']['restart'][rid]))
'''
    args = [sys.executable, '-c', script, str(store.root), store.backend, nid, record['id']]
    fresh = subprocess.run(args+['read'], env=environment, capture_output=True, text=True, timeout=20)
    assert fresh.returncode == 0, fresh.stderr
    assert json.loads(fresh.stdout) == record
    crashed = subprocess.run(args+['crash'], env=environment, capture_output=True, text=True, timeout=20)
    assert crashed.returncode == 71, crashed.stderr
    again = subprocess.run(args+['read'], env=environment, capture_output=True, text=True, timeout=20)
    assert again.returncode == 0, again.stderr
    assert json.loads(again.stdout)['title'] == 'Durable source'
