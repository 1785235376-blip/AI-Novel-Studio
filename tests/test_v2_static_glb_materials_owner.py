import json
import pytest
from test_v2_independent_workspace import rig,reopened
from test_v2_static_glb_owner import upload,body
from test_v2_static_glb_materials import document
from test_v2_static_glb_inspection import glb
pytestmark=[pytest.mark.file_backend_only,pytest.mark.parametrize('rig',['file'],indirect=True)]


def test_real_file_material_inspection_is_readonly_and_reopenable(rig):
    asset=upload(rig,body(glb(document())));before={str(p):p.read_bytes() for p in rig.root.rglob('*') if p.is_file()}
    result=reopened(rig).inspect_model_reference(rig.nid,rig.scope,asset['id'],material_inspection=True)
    assert result['asset_snapshot']['digest']==asset['sha256'] and result['material_inspection']['materials'][0]['name']=='Paint'
    assert before=={str(p):p.read_bytes() for p in rig.root.rglob('*') if p.is_file()}
    (rig.root/'materials-wire.json').write_text(json.dumps({'asset':asset,'result':result},indent=2)+'\n')
    rig.service.lifecycle(rig.nid,rig.scope,asset['id'],asset['version'])
    with pytest.raises((ValueError,FileNotFoundError)):reopened(rig).inspect_model_reference(rig.nid,rig.scope,asset['id'],material_inspection=True)


def test_material_route_is_original_authorized_read(rig):
    from fastapi import FastAPI,HTTPException
    from fastapi.testclient import TestClient
    from app.creative.workspace_api import create_independent_workspace_router,is_independent_studio_route
    from app.experimental.flags import require_flag
    asset=upload(rig,body(glb(document())));allowed=[True]
    def authorize(nid,token,branch,permission):
        if not allowed[0] or nid!=rig.nid or token!='fixture-session' or branch is not None or permission!='domain.read':raise HTTPException(403,{'code':'DENIED'})
        return rig.actor,rig.scope
    app=FastAPI();app.include_router(create_independent_workspace_router(rig.service,authorize,require_flag,create_project=lambda *a:None,workspace_writer=lambda t:rig.actor),prefix='/api')
    path=f'/api/projects/{rig.nid}/studio/assets/{asset["id"]}/model-reference/materials'
    assert is_independent_studio_route('GET',path) and not is_independent_studio_route('POST',path)
    with TestClient(app) as client:
        response=client.get(path,headers={'X-Session-Token':'fixture-session'});assert response.status_code==200,response.text
        assert response.json()['material_inspection']['materials_rendered'] is False
        allowed[0]=False;assert client.get(path,headers={'X-Session-Token':'fixture-session'}).status_code==403
