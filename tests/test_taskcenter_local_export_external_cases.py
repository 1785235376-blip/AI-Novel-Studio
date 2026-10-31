from copy import deepcopy
import json
import pytest
from fastapi import HTTPException
from test_taskcenter_local_export_external import rig,export_rig,get,files,shared_scope


def update(e,fn):
    with e.source._mutation():
        rows=e.source._read();fn(rows);e.source._write(rows)


def token(e,params=None):
    response=get(e,params);assert response.status_code==200,response.text
    return response.json()['next_cursor']


@pytest.mark.parametrize('kind',['private_aba','row_recreate','document_recreate','project_recreate'])
def test_selected_original_changes_restart(export_rig,kind):
    e=export_rig;t=token(e);rid=e.ids[0];original=deepcopy(e.source._read()[rid])
    if kind=='private_aba':
        update(e,lambda rows:rows[rid].update(snapshot={'private':'private-secret-snapshot'}))
        update(e,lambda rows:rows.__setitem__(rid,original))
    elif kind=='row_recreate':
        update(e,lambda rows:rows.pop(rid));update(e,lambda rows:rows.__setitem__(rid,original))
    elif kind=='document_recreate':
        rows=e.source._read();e.source.path.unlink();e.source._write(rows)
    else:
        marker=e.rig.root/'novels'/e.rig.nid/'creative_project_v2.json';marker.unlink();e.rig.workspace.creative.store.incarnation(e.rig.nid)
    response=get(e,{'cursor':t});assert response.status_code==409,response.text
    assert 'private-secret' not in response.text


@pytest.mark.parametrize('kind',['unmatched','foreign','wrong_local_actor'])
def test_unmatched_and_hidden_nonce_updates_do_not_invalidate(export_rig,kind):
    e=export_rig
    update(e,lambda rows:[rows[rid].update(status='failed') for rid in e.ids[:2]])
    if kind!='unmatched':
        row=deepcopy(e.source._read()[e.ids[2]]);row['id']='hidden-original';
        if kind=='foreign':row['novel_id']='other-project';row['permission_context']={'mode':'local','novel_id':'other-project'}
        else:row['permission_context']={**row['permission_context'],'actor_id':'local-author'}
        update(e,lambda rows:rows.__setitem__(row['id'],row));target=row['id']
    else:target=e.ids[2]
    t=token(e,{'failed_only':'true'})
    update(e,lambda rows:rows[target].update(snapshot={'private':'must-not-bind-hidden'}))
    response=get(e,{'failed_only':'true','cursor':t});assert response.status_code==200,response.text
    assert response.json()['observed_total']==2 and 'must-not-bind-hidden' not in response.text


def test_empty_bound_document_is_valid_without_provisioning(export_rig):
    e=export_rig;e.source._write({});before=files(e.rig.root);r=get(e)
    assert r.status_code==200,r.text
    assert r.json()['items']==[] and r.json()['next_cursor'] is None
    assert r.json()['observed_total']==0 and r.json()['source_truncated'] is False
    assert files(e.rig.root)==before


@pytest.mark.parametrize('kind',['legacy','missing'])
def test_missing_or_legacy_source_rejected_zero_write(export_rig,kind):
    e=export_rig
    if kind=='legacy':e.source.path.write_text(json.dumps(e.source._read()))
    else:e.source.path.unlink()
    before=files(e.rig.root);r=get(e);assert r.status_code==501,r.text
    assert files(e.rig.root)==before


@pytest.mark.parametrize('params',[{'authority':['exports','semantic_import']},{'authority':['exports','agent_team']}])
def test_mixed_source_stays_unsupported(export_rig,params):
    r=get(export_rig,params);assert r.status_code==501,r.text


def test_collaboration_exports_stays_unsupported(export_rig):
    e=export_rig;_,headers=shared_scope(e.rig);r=get(e,headers=headers);assert r.status_code==501,r.text


def test_original_reader_denial_never_uses_captured_rows_as_permission(export_rig,monkeypatch):
    e=export_rig;t=token(e)
    def deny(*a,**kw):raise HTTPException(403,{'code':'SYNTHETIC_ORIGINAL_EXPORT_DENIAL'})
    monkeypatch.setattr(e.source,'list',deny);r=get(e)
    # Original aggregate omits denied-source rows; unchanged local cursor
    # converts the projection mismatch to unsupported/restart, never success.
    assert r.status_code==501,r.text
    assert 'items' not in r.json()
    assert get(e,{'cursor':t}).status_code==409


def test_source_root_switch_after_original_reader_restarts(export_rig,monkeypatch,tmp_path):
    e=export_rig;t=token(e);original=e.source.list
    def changed(*a,**kw):
        result=original(*a,**kw);monkeypatch.setattr(e.source,'path',tmp_path/'other-owner'/'export_jobs.json');return result
    monkeypatch.setattr(e.source,'list',changed);r=get(e,{'cursor':t});assert r.status_code==409,r.text


def test_original_hundred_row_window_and_overflow_remain_bounded(export_rig):
    e=export_rig;template=e.source._read()[e.ids[0]]
    rows={}
    for i in range(101):
        rid=f'window-{i:03}';rows[rid]={**deepcopy(template),'id':rid,'created_at':f'2026-01-01T00:00:{i:03}Z'}
    e.source._write(rows)
    r=get(e,{'limit':100});assert r.status_code==200,r.text
    assert len(r.json()['items'])==100 and r.json()['observed_total']==100
    assert r.json()['source_truncated'] is True and r.json()['next_cursor'] is None
    r=get(e,{'q':'never-matches-anything'});assert r.status_code==200,r.text
    assert r.json()['items']==[] and r.json()['source_truncated'] is True


def test_hidden_tail_private_change_stable_but_window_reentry_restarts(export_rig):
    e=export_rig;template=e.source._read()[e.ids[0]]
    e.source._write({f'tail-{i:03}':{**deepcopy(template),'id':f'tail-{i:03}','created_at':f'2026-{i:03}'} for i in range(101)})
    t=token(e)
    update(e,lambda rows:rows['tail-000'].update(snapshot={'private':'hidden-tail-private'}))
    r=get(e,{'cursor':t});assert r.status_code==200,r.text
    update(e,lambda rows:rows['tail-000'].update(created_at='9999-newly-visible'))
    r=get(e,{'cursor':t});assert r.status_code==409,r.text


def test_original_scope_fence_hides_all_rows_and_overflow(export_rig):
    e=export_rig;template=e.source._read()[e.ids[0]]
    e.source._write({f'fenced-{i:03}':{**deepcopy(template),'id':f'fenced-{i:03}','branch_id':'foreign-branch'} for i in range(101)})
    r=get(e);assert r.status_code==200,r.text
    assert r.json()['items']==[] and r.json()['observed_total']==0 and r.json()['source_truncated'] is False
