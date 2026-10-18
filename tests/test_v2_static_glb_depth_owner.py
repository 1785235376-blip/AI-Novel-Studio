import base64
import json
import pytest
from test_v2_independent_workspace import rig,reopened
from test_v2_static_glb_owner import upload
from test_v2_static_glb_depth import pixels
pytestmark=[pytest.mark.file_backend_only,pytest.mark.parametrize('rig',['file'],indirect=True)]


def body(asset):return {'contract':'studio-static-glb-depth-export/1','source_version':asset['version'],'source_sha256':asset['sha256'],'yaw':0.,'pitch':0.}


def test_real_file_source_depth_download_is_readonly_and_exact(rig):
    asset=upload(rig);service=reopened(rig);before={str(p):p.read_bytes() for p in rig.root.rglob('*') if p.is_file()}
    result=service.export_model_depth(rig.nid,rig.scope,asset['id'],body(asset))
    assert result['asset_snapshot']['digest']==asset['sha256'] and set(pixels(base64.b64decode(result['content_base64'])))=={0,255}
    assert before=={str(p):p.read_bytes() for p in rig.root.rglob('*') if p.is_file()}
    with pytest.raises(ValueError):service.export_model_depth(rig.nid,rig.scope,asset['id'],{**body(asset),'source_version':2})
    (rig.root/'depth-wire.json').write_text(json.dumps({'asset':asset,'result':result},ensure_ascii=False,indent=2)+'\n')


def test_final_source_recheck_discards_rendered_bytes_after_change(rig,monkeypatch):
    import app.creative.model_reference_depth as module
    asset=upload(rig);original=module.render_depth
    def changed(*args,**kw):
        result=original(*args,**kw);rig.service.lifecycle(rig.nid,rig.scope,asset['id'],asset['version']);return result
    monkeypatch.setattr(module,'render_depth',changed)
    with pytest.raises((ValueError,FileNotFoundError)):rig.service.export_model_depth(rig.nid,rig.scope,asset['id'],body(asset))


def test_depth_route_has_exact_read_authority_and_no_execution_route(rig):
    from fastapi import FastAPI,HTTPException
    from fastapi.testclient import TestClient
    from app.creative.workspace_api import create_independent_workspace_router,is_independent_studio_route
    from app.experimental.flags import require_flag
    asset=upload(rig);allowed=[True]
    def authorize(nid,token,branch,permission):
        if nid!=rig.nid or token!='fixture-session' or branch is not None or permission!='domain.read' or not allowed[0]:raise HTTPException(403,{'code':'DENIED'})
        return rig.actor,rig.scope
    app=FastAPI();app.include_router(create_independent_workspace_router(rig.service,authorize,require_flag,create_project=lambda *args:None,workspace_writer=lambda token:rig.actor),prefix='/api')
    path=f'/api/projects/{rig.nid}/studio/assets/{asset["id"]}/model-reference/depth-export'
    assert is_independent_studio_route('POST',path) and not is_independent_studio_route('GET',path)
    with TestClient(app) as client:
        response=client.post(path,headers={'X-Session-Token':'fixture-session'},json=body(asset));assert response.status_code==200,response.text
        assert response.json()['depth_export']['asset_created'] is False
        allowed[0]=False;assert client.post(path,headers={'X-Session-Token':'fixture-session'},json=body(asset)).status_code==403
