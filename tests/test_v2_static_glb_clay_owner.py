import json
import pytest
from test_v2_independent_workspace import rig,reopened
from test_v2_static_glb_owner import upload
pytestmark=[pytest.mark.file_backend_only,pytest.mark.parametrize('rig',['file'],indirect=True)]


def body(asset):return {'contract':'studio-static-glb-clay-export/1','source_version':asset['version'],'source_sha256':asset['sha256'],'yaw':0.,'pitch':0.}


def test_clay_original_file_readonly_pin_and_capture(rig):
    asset=upload(rig);before={str(p):p.read_bytes() for p in rig.root.rglob('*') if p.is_file()}
    result=reopened(rig).export_model_clay(rig.nid,rig.scope,asset['id'],body(asset))
    assert result['asset_snapshot']['digest']==asset['sha256'] and result['clay_export']['asset_created'] is False
    assert before=={str(p):p.read_bytes() for p in rig.root.rglob('*') if p.is_file()}
    (rig.root/'clay-wire.json').write_text(json.dumps({'asset':asset,'result':result},indent=2)+'\n')
    with pytest.raises(ValueError):rig.service.export_model_clay(rig.nid,rig.scope,asset['id'],{**body(asset),'source_version':2})


def test_clay_discards_result_after_source_retirement(rig,monkeypatch):
    import app.creative.model_reference_depth as module
    asset=upload(rig);original=module.render_clay
    def retired(*args,**kw):
        result=original(*args,**kw);rig.service.lifecycle(rig.nid,rig.scope,asset['id'],asset['version']);return result
    monkeypatch.setattr(module,'render_clay',retired)
    with pytest.raises((ValueError,FileNotFoundError)):rig.service.export_model_clay(rig.nid,rig.scope,asset['id'],body(asset))


def test_clay_exact_router_read_authority_and_contract(rig):
    from fastapi import FastAPI,HTTPException
    from fastapi.testclient import TestClient
    from app.creative.workspace_api import create_independent_workspace_router,is_independent_studio_route
    from app.experimental.flags import require_flag
    asset=upload(rig);allowed=[True]
    def authorize(nid,token,branch,permission):
        if not allowed[0] or nid!=rig.nid or token!='fixture-session' or branch is not None or permission!='domain.read':raise HTTPException(403,{'code':'DENIED'})
        return rig.actor,rig.scope
    app=FastAPI();app.include_router(create_independent_workspace_router(rig.service,authorize,require_flag,create_project=lambda *a:None,workspace_writer=lambda t:rig.actor),prefix='/api')
    path=f'/api/projects/{rig.nid}/studio/assets/{asset["id"]}/model-reference/clay-export'
    assert is_independent_studio_route('POST',path) and not is_independent_studio_route('GET',path)
    with TestClient(app) as client:
        response=client.post(path,headers={'X-Session-Token':'fixture-session'},json=body(asset));assert response.status_code==200,response.text
        assert response.json()['clay_export']['materials_rendered'] is False
        assert client.post(path,headers={'X-Session-Token':'fixture-session'},json={**body(asset),'contract':'studio-static-glb-depth-export/1'}).status_code==422
        allowed[0]=False;assert client.post(path,headers={'X-Session-Token':'fixture-session'},json=body(asset)).status_code==403
