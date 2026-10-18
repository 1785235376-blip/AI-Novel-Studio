import json
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.bailian_text_preset import BAILIAN_REGION_URLS,bailian_preset_catalog
from app.model_center.api import create_model_center_router


def test_public_preset_catalog_is_constants_only_without_environment_or_owner_access(monkeypatch):
    def forbidden(*a,**kw):raise AssertionError('Catalog must not inspect current configuration or execute')
    monkeypatch.setattr('os.getenv',forbidden)
    catalog=bailian_preset_catalog()
    assert {r['id']:r['base_url'] for r in catalog['regions']}==dict(BAILIAN_REGION_URLS)
    for key in ('current_configuration_included','credential_value_included','configuration_applied','network_called','model_called','enable_thinking'):assert catalog[key] is False
    catalog['regions'][0]['base_url']='changed'
    assert bailian_preset_catalog()['regions'][0]['base_url']==BAILIAN_REGION_URLS['cn-beijing']


def test_original_model_center_get_does_not_need_or_invoke_runtime_control(tmp_path):
    class NoService:
        def __getattr__(self,key):raise AssertionError('Must not access runtime owner for constant hints')
    def forbidden(*a,**kw):raise AssertionError('No authority expansion or runtime control')
    app=FastAPI();app.include_router(create_model_center_router(NoService(),mutation_authorization=forbidden))
    with TestClient(app) as client:
        response=client.get('/api/model-center/provider-presets/bailian-text');assert response.status_code==200
        assert response.json()==bailian_preset_catalog()
        assert client.post('/api/model-center/provider-presets/bailian-text').status_code==405
        (tmp_path/'bailian-preset-wire.json').write_text(json.dumps(response.json(),ensure_ascii=False,indent=2)+'\n')


import pytest

@pytest.mark.parametrize('prefix',['/api','/api/v1'])
def test_actual_application_preserves_collaboration_and_packaged_session_gates(prefix):
    from app.main import app
    from app.config import settings
    from app.dependencies import trusted_session_resolver
    from app.actor_context import SessionContext
    old=(settings.enable_collaboration_runtime,settings.enable_packaged_runtime)
    token='synthetic-bailian-catalog-session'
    trusted_session_resolver.register(token,SessionContext('bailian-catalog','fixture-client','fixture-author','fixture-workspace'))
    try:
        object.__setattr__(settings,'enable_collaboration_runtime',True);object.__setattr__(settings,'enable_packaged_runtime',False)
        with TestClient(app) as client:
            path=prefix+'/model-center/provider-presets/bailian-text'
            assert client.get(path).status_code==401
            response=client.get(path,headers={'X-Session-Token':token});assert response.status_code==200,response.text
            assert response.json()==bailian_preset_catalog()
            assert client.post(path,headers={'X-Session-Token':token}).status_code==501
            assert client.get(path+'/extra',headers={'X-Session-Token':token}).status_code==501
            object.__setattr__(settings,'enable_packaged_runtime',True)
            assert client.get(path).status_code==401
            assert client.get(path,headers={'X-Session-Token':token}).status_code==401
    finally:
        trusted_session_resolver.revoke(token)
        object.__setattr__(settings,'enable_collaboration_runtime',old[0]);object.__setattr__(settings,'enable_packaged_runtime',old[1])
