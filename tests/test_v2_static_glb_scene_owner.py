"""Original real File pin/read owner for scene geometry; no writes on inspect."""
import pytest
from test_v2_independent_workspace import rig,reopened
from test_v2_static_glb_owner import upload
pytestmark=[pytest.mark.file_backend_only,pytest.mark.parametrize('rig',['file'],indirect=True)]

def test_scene_original_owner_exact_pin_and_reopen_read_only(rig):
    asset=upload(rig);service=reopened(rig)
    before={str(p):p.read_bytes() for p in rig.root.rglob('*') if p.is_file()}
    result=service.inspect_model_reference(rig.nid,rig.scope,asset['id'],scene_preview=True)
    assert result['asset_snapshot']['digest']==asset['sha256']
    assert result['scene_preview']['bounds']['min']==[99,0,0]
    assert 'mesh_preview' not in result
    assert before=={str(p):p.read_bytes() for p in rig.root.rglob('*') if p.is_file()}
    with pytest.raises(ValueError):service.inspect_model_reference(rig.nid,rig.scope,asset['id'],scene_preview=True,mesh_preview=True)


def test_scene_route_uses_original_read_authority_and_private_codes(rig):
    from fastapi import FastAPI,HTTPException
    from fastapi.testclient import TestClient
    from app.creative.workspace_api import create_independent_workspace_router,is_independent_studio_route
    from app.experimental.flags import require_flag
    asset=upload(rig);allowed=[True]
    def authorize(nid,token,branch,permission):
        if nid!=rig.nid or token!='fixture-session' or branch is not None or permission!='domain.read' or not allowed[0]:raise HTTPException(403,{'code':'DENIED'})
        return rig.actor,rig.scope
    app=FastAPI();app.include_router(create_independent_workspace_router(rig.service,authorize,require_flag,create_project=lambda *args:None,workspace_writer=lambda token:rig.actor),prefix='/api')
    path=f'/api/projects/{rig.nid}/studio/assets/{asset["id"]}/model-reference/scene-preview'
    assert is_independent_studio_route('GET',path) and not is_independent_studio_route('POST',path)
    with TestClient(app) as client:
        response=client.get(path,headers={'X-Session-Token':'fixture-session'})
        assert response.status_code==200,response.text
        assert response.json()['scene_preview']['bounds']['min']==[99,0,0]
        allowed[0]=False;assert client.get(path,headers={'X-Session-Token':'fixture-session'}).status_code==403
