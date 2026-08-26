from fastapi.testclient import TestClient
from app.main import app

def test_errors_include_request_id_and_compatible_envelope():
    client=TestClient(app)
    response=client.get('/api/novels/missing-novel')
    assert response.status_code==404
    payload=response.json()
    assert payload['code'] and payload['message'] and payload['request_id']
    assert response.headers['x-request-id']==payload['request_id']

def test_client_request_id_is_echoed():
    client=TestClient(app)
    response=client.get('/health',headers={'X-Request-ID':'desktop-test-1'})
    assert response.status_code==200 and response.headers['x-request-id']=='desktop-test-1'
