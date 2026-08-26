from fastapi.testclient import TestClient
from app.main import app
def test_asset_execution_requires_route_and_is_not_repeatable():
 c=TestClient(app); n=c.post('/api/novels',json={'title':'任务保护'}).json(); nid=n['id']; c.post(f'/api/novels/{nid}/chapters',json={'title':'一','content':'a'}); s=c.post(f'/api/novels/{nid}/screenplays',json={}).json(); u=f"/api/novels/{nid}/screenplays/{s['id']}"; c.post(u+'/approve'); c.post(u+'/shots'); c.post(u+'/shots/approve'); c.post(u+'/storyboard'); c.post(u+'/storyboard/approve'); c.post(u+'/assets'); c.post(u+'/assets/approve'); t=c.post(u+'/asset-tasks').json()['asset_tasks'][0]; c.put(u+f"/asset-tasks/{t['id']}",json={'status':'RUNNING'}); assert c.post(u+f"/asset-tasks/{t['id']}/execute").status_code==400
