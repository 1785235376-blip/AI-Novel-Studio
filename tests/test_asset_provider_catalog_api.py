from fastapi.testclient import TestClient
from app.main import app
def test_asset_provider_catalog_never_exposes_secret():
 body=TestClient(app).get('/api/asset-providers').json(); rows={r['provider_id']:r for r in body['items']}
 assert rows['ddshub']['endpoint']=='https://www.ddshub.cc/v1'
 assert rows['ddshub']['default_model']=='gpt-image-2'
 assert all(r['secret'] is None for r in rows.values())
