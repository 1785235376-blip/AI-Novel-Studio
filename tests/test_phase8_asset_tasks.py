from fastapi.testclient import TestClient
from app.main import app
def test_asset_task_queue():
 c=TestClient(app); n=c.post('/api/novels',json={'title':'任务'}).json(); nid=n['id']; c.post(f'/api/novels/{nid}/chapters',json={'title':'一','content':'a'}); s=c.post(f'/api/novels/{nid}/screenplays',json={}).json(); u=f"/api/novels/{nid}/screenplays/{s['id']}"; c.post(u+'/approve'); c.post(u+'/shots'); c.post(u+'/shots/approve'); c.post(u+'/storyboard'); c.post(u+'/storyboard/approve'); c.post(u+'/assets'); c.post(u+'/assets/approve'); queued=c.post(u+'/asset-tasks').json(); task=queued['asset_tasks'][0]; updated=c.put(u+f"/asset-tasks/{task['id']}",json={'status':'RUNNING','provider_id':'local','model_id':'image-v1'}).json(); assert updated['asset_tasks'][0]['status']=='RUNNING'
 assert c.put(u+f"/asset-tasks/{task['id']}",json={'status':'PENDING'}).status_code==400
 assert c.post(u+'/asset-tasks').json()['asset_tasks'][0]['id']==task['id']
 assert updated['asset_tasks'][0]['attempts']==1
 assert [x['status'] for x in updated['asset_tasks'][0]['history']][-1]=='RUNNING'
