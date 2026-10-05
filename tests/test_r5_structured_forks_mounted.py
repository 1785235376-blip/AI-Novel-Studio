"""Mounted B09 structured source/selection/permission routes and original CAS."""
import pytest
from app.experimental.planning import digest
from test_r5_project_forks_mounted import forks
from test_r3_mounted_contracts import mounted, prefix, checked


@pytest.fixture
def structures(forks):
    e = forks; e.sbase = e.fbase + '/structured'
    e.novels.upsert_character(e.nid, 'hero', {'name': 'Synthetic hero', 'privacy_level': 'LOCAL_ONLY'})
    yield e
    for row in e.store.read(e.nid, e.scope)['collections'].get('project_structured_forks_v1', {}).values():
        try: e.novels.delete(row['target_id'])
        except FileNotFoundError: pass


def create(e):
    sources = checked(e.client.get(e.sbase + '/catalog'))['records']
    selected = [r for r in sources if r['key'] == 'characters:hero']
    pre = checked(e.client.post(e.sbase + '/preflight', json={'title': 'Synthetic structured copy', 'records': [
        {k:r[k] for k in ('kind','record_id','source_digest')} | {'license':'Synthetic author-owned','allow_local_copy':True} for r in selected]}))
    row = checked(e.client.post(e.sbase + f"/{pre['id']}/create", json={'expected_version':pre['version'],'preview_digest':pre['preview_digest'],'confirmed':True}))
    rid = row['id_map']['characters:hero'].split(':', 1)[1]
    current = next(r for r in e.novels.data_set(row['target_id'],'characters') if r['id'] == rid)
    e.novels.compare_and_swap_record(row['target_id'],'characters',rid,{k:v for k,v in current.items() if k not in {'id','privacy_status'}} | {'name':'Synthetic changed'},digest(current))
    return row


def test_mounted_structured_selection_compare_cas_and_recovery(structures, monkeypatch):
    e = structures; row = create(e); writer = e.novels.compare_and_swap_record; writes = []
    def track(*args, **kwargs): writes.append(args); return writer(*args, **kwargs)
    monkeypatch.setattr(e.novels,'compare_and_swap_record',track)
    comparison = checked(e.client.post(e.sbase + f"/{row['id']}/compare",json={'expected_version':row['version']}))
    assert comparison['can_apply'] and comparison['write_count'] == 1 and not writes
    done = checked(e.client.post(e.sbase + f"/{row['id']}/apply",json={'expected_version':row['version'],'preview_digest':comparison['preview_digest'],'confirmed':True}))
    assert done['status'] == 'COMPLETED' and len(writes) == 1 and len(writes[0][-1]) == 64
    recovery = checked(e.client.post(e.sbase + f"/merges/{done['id']}/recovery",json={'expected_version':done['version']}))
    restored = checked(e.client.post(e.sbase + f"/merges/{done['id']}/restore",json={'expected_version':done['version'],'preview_digest':recovery['preview_digest'],'confirmed':True}))
    assert restored['status'] == 'RESTORED' and len(writes) == 2


def test_mounted_structured_source_digest_and_current_session_recheck(structures):
    e = structures; row = create(e)
    comparison = checked(e.client.post(e.sbase + f"/{row['id']}/compare",json={'expected_version':row['version']}))
    body = {'expected_version':row['version'],'preview_digest':comparison['preview_digest'],'confirmed':True}
    e.sessions.revoke('fork-host')
    denied = e.client.post(e.sbase + f"/{row['id']}/apply",json=body)
    assert denied.status_code == 401 and 'Synthetic' not in denied.text
    assert next(r for r in e.novels.data_set(e.nid,'characters') if r['id']=='hero')['name'] == 'Synthetic hero'


@pytest.mark.parametrize('flags,v1',[('',False),('project_forks_v2',False),('*',False),('all',True)])
def test_mounted_structured_default_off_dependencies_and_v1(structures,monkeypatch,flags,v1):
    e = structures; monkeypatch.setenv('EXPERIMENTAL_FEATURES',flags); monkeypatch.setenv('V1_ACCEPTANCE_MODE',str(v1))
    assert e.client.get(e.sbase + '/catalog').status_code == 404
    assert e.client.get(e.sbase + '/records').status_code == 404
    assert e.client.post(e.sbase + '/preflight',json={}).status_code == 404


def test_mounted_structured_revocation_between_original_writes_preserves_partial_journal(structures, monkeypatch):
    e = structures; e.novels.upsert_character(e.nid, 'second', {'name':'Synthetic second','privacy_level':'LOCAL_ONLY'})
    sources = checked(e.client.get(e.sbase + '/catalog'))['records']; selected = [r for r in sources if r['key'] in {'characters:hero','characters:second'}]
    pre = checked(e.client.post(e.sbase + '/preflight',json={'title':'Two synthetic structures','records':[{k:r[k] for k in ('kind','record_id','source_digest')} | {'license':'Mine','allow_local_copy':True} for r in selected]}))
    row = checked(e.client.post(e.sbase + f"/{pre['id']}/create",json={'expected_version':pre['version'],'preview_digest':pre['preview_digest'],'confirmed':True}))
    for key in row['id_map'].values():
        rid = key.split(':',1)[1]; current = next(r for r in e.novels.data_set(row['target_id'],'characters') if r['id']==rid)
        e.novels.compare_and_swap_record(row['target_id'],'characters',rid,{k:v for k,v in current.items() if k not in {'id','privacy_status'}} | {'name':'Fork changed'},digest(current))
    preview = checked(e.client.post(e.sbase + f"/{row['id']}/compare",json={'expected_version':row['version']}))
    original = e.novels.compare_and_swap_record; calls = []
    def revoke(*args, **kwargs):
        result = original(*args, **kwargs); calls.append(args[2]); e.sessions.revoke('fork-host'); return result
    monkeypatch.setattr(e.novels,'compare_and_swap_record',revoke)
    response = e.client.post(e.sbase + f"/{row['id']}/apply",json={'expected_version':row['version'],'preview_digest':preview['preview_digest'],'confirmed':True})
    assert response.status_code == 401 and len(calls)==1
    plan = next(iter(e.store.read(e.nid,e.scope)['collections']['project_structured_merges_v1'].values()))
    assert plan['status']=='RECOVERY_REQUIRED' and len(plan['journal'])==1
    actual = [r['name'] for r in e.novels.data_set(e.nid,'characters') if r['id'] in {'hero','second'}]
    assert actual.count('Fork changed') == 1
