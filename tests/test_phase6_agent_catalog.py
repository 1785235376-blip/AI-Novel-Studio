from fastapi.testclient import TestClient

from app.main import app


def test_agent_catalog_has_six_bounded_roles():
    response=TestClient(app).get('/api/agents');assert response.status_code==200;body=response.json();agents=body['agents']
    assert body['catalog_version']=='1.0'
    assert [item['id'] for item in agents]==['planner','writer','editor','continuity','director','artist']
    assert all(item['tools'] and item['output_schema'] for item in agents)
    assert next(item for item in agents if item['id']=='continuity')['requires_approval'] is False
    assert next(item for item in agents if item['id']=='writer')['requires_approval'] is True


def test_agent_catalog_does_not_expose_credentials_or_prompt_text():
    body=TestClient(app).get('/api/agents').json();serialized=str(body).lower()
    assert 'api_key' not in serialized and 'sk-' not in serialized
    assert all('system_prompt' not in item for item in body['agents'])
