"""Explicit original-Asset clay reference save, File and real PostgreSQL."""
import copy,json
import pytest
from test_v2_independent_workspace import rig,reopened
from test_v2_static_glb_owner import upload
from test_v2_static_glb_clay_owner import body as export_body


def prepared(e):
    source=upload(e);view=e.service.export_model_clay(e.nid,e.scope,source['id'],export_body(source))
    request={**export_body(source),'contract':'studio-static-glb-clay-asset/1','reviewed_png_sha256':view['clay_export']['png_sha256'],'confirm_reference':True,'idempotency_key':'saved-clay'}
    return source,view,request


def save(e,source,request,**kwargs):return e.service.save_model_clay_reference(e.nid,e.scope,e.actor,source['id'],request,kwargs.get('guard',lambda:None))

def files(e):return {p.name:p.read_bytes() for p in e.assets.root.iterdir() if p.is_file()}


def test_reviewed_pixels_save_once_with_first_commit_lineage_and_reopen(rig,monkeypatch):
    e=rig;source,view,request=prepared(e);seen=[];original=e.assets._write_meta
    def written(row):
        if '_model_reference_origin' in row:
            assert row['source_asset_ids']==[source['id']] and row['parameters']['asset_lineage_v2']['parents']=={source['id']:{'version':1,'digest':source['sha256']}}
            seen.append(row['id'])
        return original(row)
    monkeypatch.setattr(e.assets,'_write_meta',written)
    result=save(e,source,request);asset=result['asset'];assert seen==[asset['id']]
    assert asset['kind']=='image' and asset['sha256']==view['clay_export']['png_sha256']
    assert asset['provenance']['origin']=='MANUAL_EDIT' and asset['provenance']['integrity']=='VERIFIED'
    assert asset['model_reference']['diagnostic_only'] is True and not result['receipt']['model_called']
    assert '_model_reference_origin' not in json.dumps(result)
    service=reopened(e);assert service.asset(e.nid,e.scope,asset['id'])==asset
    import base64
    assert service.download(e.nid,e.scope,asset['id'])[1]==base64.b64decode(view['content_base64'])
    replay=service.save_model_clay_reference(e.nid,e.scope,e.actor,source['id'],request,lambda:None)
    assert replay['asset']==asset and replay['receipt']['replayed'] and not replay['receipt']['asset_created']
    assert len(service.list_assets(e.nid,e.scope)['items'])==2 and e.chapters.list(e.nid)==[]


@pytest.mark.parametrize('change',['hash','source','actor','confirmation'])
def test_changed_review_or_identity_never_creates_duplicate(rig,change):
    e=rig;source,view,request=prepared(e);save(e,source,request);before=files(e);actor=e.actor
    if change=='hash':request['reviewed_png_sha256']='0'*64
    elif change=='source':request['source_version']+=1
    elif change=='actor':actor='different-author'
    else:request['confirm_reference']=False
    with pytest.raises(ValueError):e.service.save_model_clay_reference(e.nid,e.scope,actor,source['id'],request,lambda:None)
    assert files(e)==before


def test_metadata_cannot_forge_provider_or_rebind_lineage_and_annotation_retains_pin(rig):
    e=rig;source,view,request=prepared(e);result=save(e,source,request);asset=result['asset'];before=files(e)
    with e.service._asset_scope(e.nid,e.scope):
        with pytest.raises(ValueError):e.assets.update_metadata(asset['id'],{'source_asset_ids':[]},expected_version=1)
        with pytest.raises(ValueError):e.assets.update_metadata(asset['id'],{'provider_id':'fake-model'},expected_version=1)
    assert files(e)==before
    changed=e.service.annotate(e.nid,e.scope,e.actor,asset['id'],{'expected_version':1,'origin':'MANUAL_EDIT','parent_asset_ids':[source['id']],'license':{'label':'Author claim'},'operation':'Human reference description'})
    assert changed['version']==2 and changed['model_reference']==asset['model_reference']
    assert save(e,source,request)['asset']==changed


def test_revoke_during_render_and_final_guard_failure_leave_no_new_asset(rig,monkeypatch):
    import app.creative.model_reference_depth as renderer
    e=rig;source,view,request=prepared(e);original=renderer.render_clay;allowed=True;before=files(e)
    def revoked(*args,**kwargs):
        nonlocal allowed
        result=original(*args,**kwargs);allowed=False;return result
    monkeypatch.setattr(renderer,'render_clay',revoked)
    def guard():
        if not allowed:raise PermissionError('revoked')
    with pytest.raises(PermissionError):save(e,source,request,guard=guard)
    assert files(e)==before


def test_original_route_needs_write_authority_not_only_read(rig):
    from fastapi import FastAPI,HTTPException
    from fastapi.testclient import TestClient
    from app.creative.workspace_api import create_independent_workspace_router,is_independent_studio_route
    from app.experimental.flags import require_flag
    e=rig;source,view,request=prepared(e);permissions=[]
    def authorize(nid,token,branch,permission):
        permissions.append(permission)
        if token!='writer' and permission=='domain.write':raise HTTPException(403,{'code':'DENIED'})
        return e.actor,e.scope
    app=FastAPI();app.include_router(create_independent_workspace_router(e.service,authorize,require_flag,create_project=lambda *a:None,workspace_writer=lambda t:e.actor),prefix='/api')
    path=f'/api/projects/{e.nid}/studio/assets/{source["id"]}/model-reference/clay-save'
    assert is_independent_studio_route('POST',path)
    with TestClient(app) as client:
        assert client.post(path,json=request,headers={'X-Session-Token':'reader'}).status_code==403
        response=client.post(path,json=request,headers={'X-Session-Token':'writer'});assert response.status_code==201,response.text
        assert response.json()['asset']['kind']=='image'
    assert set(permissions)=={'domain.write'}


@pytest.mark.parametrize('after_commit',[False,True])
def test_metadata_failure_preserves_exact_durable_boundary_and_retry(rig,monkeypatch,after_commit):
    e=rig;source,view,request=prepared(e);before=files(e);original=e.assets._write_meta
    def failed(row):
        if '_model_reference_origin' in row:
            if after_commit:original(row)
            raise OSError('synthetic acknowledgement failure')
        return original(row)
    monkeypatch.setattr(e.assets,'_write_meta',failed)
    with pytest.raises(OSError):save(e,source,request)
    if not after_commit:assert files(e)==before
    else:assert len(list(e.assets.root.glob('*.json')))==2 and len(list(e.assets.root.glob('*.bin')))==2
    monkeypatch.setattr(e.assets,'_write_meta',original)
    result=save(e,source,request)
    assert result['receipt']['replayed'] is after_commit
    assert len(e.service.list_assets(e.nid,e.scope)['items'])==2


def test_concurrent_same_key_converges_on_one_original_asset(rig):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    e=rig;source,view,request=prepared(e);other=reopened(e);gate=Barrier(2)
    def run(service):
        gate.wait(timeout=10)
        return service.save_model_clay_reference(e.nid,e.scope,e.actor,source['id'],request,lambda:None)
    with ThreadPoolExecutor(max_workers=2) as pool:
        a=pool.submit(run,e.service);b=pool.submit(run,other)
        one,two=a.result(timeout=20),b.result(timeout=20)
    assert one['asset']==two['asset']
    assert sorted([one['receipt']['replayed'],two['receipt']['replayed']])==[False,True]
    assert len(e.service.list_assets(e.nid,e.scope)['items'])==2


@pytest.mark.parametrize('change',['revision','delete','recreate'])
def test_source_drift_during_render_never_saves_reference(rig,monkeypatch,change):
    import app.creative.model_reference_depth as renderer
    e=rig;source,view,request=prepared(e);original=renderer.render_clay
    def changed(*a,**k):
        result=original(*a,**k)
        if change=='recreate':e.novels.delete(e.nid);e.create_project(nid=e.nid)
        else:
            with e.service._asset_scope(e.nid,e.scope):
                if change=='revision':e.assets.update_metadata(source['id'],{'scene_id':'changed'},expected_version=1)
                else:e.assets.delete(source['id'])
        return result
    monkeypatch.setattr(renderer,'render_clay',changed)
    with pytest.raises((ValueError,FileNotFoundError)):save(e,source,request)
    assert len(list(e.assets.root.glob('*.json')))==len(list(e.assets.root.glob('*.bin')))==1


def test_damaged_retry_receipt_never_falls_through_to_duplicate(rig,monkeypatch):
    import app.services.asset_library_service as owner
    e=rig;source,view,request=prepared(e);result=save(e,source,request)
    path=e.assets._meta_path(result['asset']['id']);row=json.loads(path.read_text());row['_model_reference_origin']['source']['version']=99;path.write_text(json.dumps(row));before=files(e)
    monkeypatch.setattr(owner.tempfile,'mkstemp',lambda *a,**k:(_ for _ in ()).throw(AssertionError('must not stage')))
    with pytest.raises(ValueError,match='MODEL_REFERENCE_RECEIPT_UNAVAILABLE'):save(e,source,request)
    assert files(e)==before


def test_original_quota_and_storage_admission_remain_authoritative(rig,monkeypatch):
    from app.creative.storage_admission import StudioStorageCapacityError
    e=rig;source,view,request=prepared(e);before=files(e)
    monkeypatch.setattr(e.service,'MAX_ASSETS',1)
    with pytest.raises(ValueError,match='CREATIVE_PROJECT_ASSET_QUOTA'):save(e,source,request)
    assert files(e)==before
    monkeypatch.setattr(e.service,'MAX_ASSETS',100)
    monkeypatch.setattr(e.service.storage_admission,'require',lambda *a:(_ for _ in ()).throw(StudioStorageCapacityError('CREATIVE_STORAGE_LOW_SPACE')))
    with pytest.raises(StudioStorageCapacityError):save(e,source,request)
    assert files(e)==before


@pytest.mark.parametrize("rig", [pytest.param("file", marks=pytest.mark.file_backend_only)], indirect=True)
def test_real_file_wire_for_client_decoder(rig):
    e=rig
    assert e.backend=="file"
    from pathlib import Path
    import os
    source,review,request=prepared(e);result=save(e,source,request)
    target=Path(os.environ['NOVEL_DATA_PATH']).parent/'clay-save-wire.json'
    target.write_text(json.dumps({'source':source,'review':review,'result':result},ensure_ascii=False,indent=2)+'\n')
    assert result['asset']['sha256']==review['clay_export']['png_sha256']
