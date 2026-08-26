import base64
from uuid import uuid4
from fastapi.testclient import TestClient
from app.main import app
from concurrent.futures import ThreadPoolExecutor

def test_asset_upload_list_metadata_and_download():
    client=TestClient(app); novel=client.post('/api/novels',json={'title':f'asset-test-{uuid4()}'}).json(); nid=novel['id']
    raw=b'asset-bytes'; encoded=base64.b64encode(raw).decode()
    response=client.post(f'/api/novels/{nid}/assets',headers={'Idempotency-Key':'asset-1'},json={'novel_id':nid,'filename':'cover.png','content_base64':encoded,'media_type':'image/png'})
    assert response.status_code==200; asset=response.json(); assert asset['size']==len(raw) and len(asset['sha256'])==64
    repeated=client.post(f'/api/novels/{nid}/assets',headers={'Idempotency-Key':'asset-1'},json={'novel_id':nid,'filename':'cover.png','content_base64':encoded,'media_type':'image/png'})
    assert repeated.json()['id']==asset['id']
    assert client.get(f'/api/novels/{nid}/assets').json()[0]['id']==asset['id']
    downloaded=client.get(f"/api/assets/{asset['id']}/download")
    assert downloaded.status_code==200 and downloaded.content==raw and downloaded.headers['x-asset-sha256']==asset['sha256']
    assert client.delete(f"/api/assets/{asset['id']}").json()['deleted'] is True
    assert client.get(f"/api/assets/{asset['id']}").status_code==404

def test_concurrent_asset_upload_with_same_key_is_single_resource():
    client=TestClient(app); nid=client.post('/api/novels',json={'title':f'asset-race-{uuid4()}'}).json()['id']
    payload={'novel_id':nid,'filename':'race.png','content_base64':base64.b64encode(b'race').decode(),'media_type':'image/png'}
    def submit(_): return TestClient(app).post(f'/api/novels/{nid}/assets',headers={'Idempotency-Key':'race-key'},json=payload).json()['id']
    with ThreadPoolExecutor(max_workers=4) as pool: ids=list(pool.map(submit,range(4)))
    assert len(set(ids))==1 and len(client.get(f'/api/novels/{nid}/assets').json())==1
