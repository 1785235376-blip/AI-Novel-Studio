from copy import deepcopy,copy
import pytest
from test_taskcenter_mixed_external import rig,export_rig,mixed_rig,get,files,shared_scope
from app.experimental.imports import JOBS


def import_write(e,fn):
    with e.store.transaction(e.rig.nid,e.rig.scope) as document:fn(document['collections'][JOBS])


def export_write(e,fn):
    with e.source._mutation():
        rows=e.source._read();fn(rows);e.source._write(rows)


def token(e,params=None):
    r=get(e,params);assert r.status_code==200,r.text
    return r.json()['next_cursor']


def test_request_order_and_duplicates_do_not_change_original_order_or_token(mixed_rig):
    e=mixed_rig;t=token(e)
    expected=get(e,{'cursor':t})
    actual=get(e,{'cursor':t,'authority':['exports','semantic_import','exports']})
    assert actual.status_code==200,actual.text
    assert actual.json()==expected.json()


def test_actual_reader_registry_order_change_invalidates_then_controls_fresh_page(mixed_rig,monkeypatch):
    e=mixed_rig;t=token(e);svc=e.api.workspace_tools_service
    monkeypatch.setattr(svc,'task_readers',tuple(reversed(svc.task_readers)))
    r=get(e,{'cursor':t});assert r.status_code==409,r.text
    r=get(e);assert r.status_code==200,r.text
    assert all(row['authority']=='exports' for row in r.json()['items'])


@pytest.mark.parametrize('source',['import','export'])
def test_same_id_in_both_sources_keeps_distinct_nonce_authority(mixed_rig,source):
    e=mixed_rig;collision=e.imports[0];rows=e.source._read();row=rows.pop(e.ids[0]);row['id']=collision;rows[collision]=row;e.source._write(rows)
    r=get(e,{'limit':100});assert r.status_code==200,r.text
    assert {(x['authority'],x['id']) for x in r.json()['items'] if x['id']==collision}=={('semantic_import',collision),('exports',collision)}
    t=token(e)
    if source=='import':import_write(e,lambda rows:rows[collision].update(prompt='private-selected'))
    else:export_write(e,lambda rows:rows[collision].update(snapshot={'private':'private-selected'}))
    r=get(e,{'cursor':t});assert r.status_code==409,r.text
    assert 'private-selected' not in r.text


@pytest.mark.parametrize('source',['import','export'])
def test_original_private_selected_aba_restarts(mixed_rig,source):
    e=mixed_rig;t=token(e)
    if source=='import':
        rid=e.imports[0];original=e.store.read(e.rig.nid,e.rig.scope)['collections'][JOBS][rid]
        import_write(e,lambda rows:rows[rid].update(prompt='private-aba'))
        import_write(e,lambda rows:rows.__setitem__(rid,original))
    else:
        rid=e.ids[0];original=e.source._read()[rid]
        export_write(e,lambda rows:rows[rid].update(snapshot={'private':'private-aba'}))
        export_write(e,lambda rows:rows.__setitem__(rid,original))
    r=get(e,{'cursor':t});assert r.status_code==409,r.text


@pytest.mark.parametrize('source',['import','export'])
def test_query_unmatched_private_changes_do_not_bind(mixed_rig,source):
    e=mixed_rig
    import_write(e,lambda rows:[rows[rid].update(status='FAILED') for rid in e.imports[:2]])
    export_write(e,lambda rows:[rows[rid].update(status='failed') for rid in e.ids[:2]])
    t=token(e,{'failed_only':'true'})
    if source=='import':import_write(e,lambda rows:rows[e.imports[2]].update(prompt='private-hidden'))
    else:export_write(e,lambda rows:rows[e.ids[2]].update(snapshot={'private':'private-hidden'}))
    r=get(e,{'failed_only':'true','cursor':t});assert r.status_code==200,r.text
    assert r.json()['observed_total']==4 and 'private-hidden' not in r.text


@pytest.mark.parametrize('empty',['import','export','both'])
def test_bound_empty_one_or_both_sources(mixed_rig,empty):
    e=mixed_rig
    if empty in {'import','both'}:import_write(e,lambda rows:rows.clear())
    if empty in {'export','both'}:e.source._write({})
    before=files(e.rig.root);r=get(e,{'limit':100});assert r.status_code==200,r.text
    assert r.json()['observed_total']==(0 if empty=='both' else 3)
    assert r.json()['next_cursor'] is None and files(e.rig.root)==before


def test_original_200_plus_100_caps_not_global_sort_or_500(mixed_rig):
    e=mixed_rig;raw=e.store.read(e.rig.nid,e.rig.scope)['collections'][JOBS][e.imports[0]]
    import_write(e,lambda rows:(rows.clear(),rows.update({f'i-{i:03}':{**deepcopy(raw),'id':f'i-{i:03}'} for i in range(201)})))
    raw=e.source._read()[e.ids[0]];e.source._write({f'e-{i:03}':{**deepcopy(raw),'id':f'e-{i:03}'} for i in range(101)})
    seen=[];r=get(e,{'limit':100})
    while True:
        assert r.status_code==200,r.text;seen+=r.json()['items']
        assert r.json()['observed_total']==300 and r.json()['source_truncated'] is True
        t=r.json()['next_cursor']
        if t is None:break
        r=get(e,{'limit':100,'cursor':t})
    assert [x['authority'] for x in seen]==['semantic_import']*200+['exports']*100
    assert len({(x['authority'],x['id']) for x in seen})==300


@pytest.mark.parametrize('source',['import','export'])
def test_actual_source_singleton_swap_same_root_restarts(mixed_rig,monkeypatch,source):
    e=mixed_rig;t=token(e)
    if source=='import':monkeypatch.setattr(e.api,'import_service',copy(e.importer))
    else:monkeypatch.setattr(e.legacy,'export_job_service',copy(e.source))
    r=get(e,{'cursor':t});assert r.status_code==409,r.text


@pytest.mark.parametrize('source',['import','export'])
def test_source_document_replacement_mid_original_reader_restarts(mixed_rig,monkeypatch,source):
    e=mixed_rig;t=token(e);original=e.source.list
    def changed(*a,**kw):
        result=original(*a,**kw)
        if source=='export':
            rows=e.source._read();e.source.path.unlink();e.source._write(rows)
        else:
            path=e.store.path(e.rig.nid,e.rig.scope);document=e.store.read(e.rig.nid,e.rig.scope);document.pop('_taskcenter_source_lifecycle_v1',None)
            # Original new-document writer recreates content after physical retirement.
            from app.experimental.store import LIFECYCLE
            document.pop(LIFECYCLE,None);path.unlink()
            with e.store.transaction(e.rig.nid,e.rig.scope) as d:d['collections']=document['collections']
        return result
    monkeypatch.setattr(e.source,'list',changed);r=get(e,{'cursor':t});assert r.status_code==409,r.text


@pytest.mark.parametrize('params',[{'authority':['semantic_import','exports','agent_team']},{'authority':['exports','media']}])
def test_other_mixed_remains_unsupported(mixed_rig,params):
    r=get(mixed_rig,params);assert r.status_code==501,r.text


def test_collaboration_mode_never_relabels_local_mixed(mixed_rig):
    e=mixed_rig;_,headers=shared_scope(e.rig);r=get(e,headers=headers);assert r.status_code==501,r.text


@pytest.mark.parametrize('empty',['import','export'])
def test_empty_source_incarnation_still_binds_continuation(mixed_rig,empty):
    e=mixed_rig
    if empty=='import':import_write(e,lambda rows:rows.clear())
    else:e.source._write({})
    t=token(e)
    if empty=='import':
        e.store.path(e.rig.nid,e.rig.scope).unlink()
        with e.store.transaction(e.rig.nid,e.rig.scope) as d:d['collections'][JOBS]={}
    else:e.source.path.unlink();e.source._write({})
    r=get(e,{'cursor':t});assert r.status_code==409,r.text
