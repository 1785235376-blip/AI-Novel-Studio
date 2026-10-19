"""Synthetic-only final dispatch boundaries and mounted Local AI authority."""
from types import SimpleNamespace as S
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from app.model_runtime import (ModelRegistry,ProviderRegistry,ProviderDescriptor,ModelDescriptor,Modality,
    TextGenerationRequest,TextModelNode,TextModelNodeInput,TextGenerationResponse)

@pytest.mark.parametrize('stream',[False,True])
def test_normalized_node_rechecks_guard_after_registry_resolution(stream):
    permitted=[True];sent=[]
    class Provider:
        def generate_text(self,request):
            sent.append(request);return TextGenerationResponse('draft','stop','fixture','fixture')
        def stream_text(self,request):
            sent.append(request);return iter(())
    providers=ProviderRegistry();models=ModelRegistry()
    providers.register(ProviderDescriptor('fixture','Fixture','local',frozenset({Modality.TEXT}),True,True),Provider())
    models.register(ModelDescriptor('fixture','fixture','Fixture',Modality.TEXT,frozenset({'generate','stream'}),streaming=True))
    original=providers.resolve
    def resolve(pid):
        value=original(pid);permitted[0]=False;return value
    providers.resolve=resolve
    def guard():
        if not permitted[0]:raise ValueError('revoked before dispatch')
    request=TextGenerationRequest('fixture','fixture','synthetic only',dispatch_guard=guard)
    node=TextModelNode(providers,models)
    with pytest.raises(ValueError,match='revoked'):
        list(node.stream(TextModelNodeInput(request))) if stream else node.execute(TextModelNodeInput(request))
    assert sent==[]

@pytest.mark.parametrize('consent',[False,None,'true',1])
def test_manual_remote_input_has_no_implicit_consent(monkeypatch,consent):
    import app.api as api
    monkeypatch.setattr(api,'settings',S(enable_cloud=True,enable_collaboration_runtime=False))
    with pytest.raises(HTTPException) as error:
        api._assert_manual_media_egress({'prompt':'Synthetic private prompt','allow_cloud_prompt':consent},S(local=False))
    assert error.value.status_code==403


def test_manual_project_restriction_cannot_be_waived(monkeypatch):
    import app.api as api
    monkeypatch.setattr(api,'settings',S(enable_cloud=True,enable_collaboration_runtime=False))
    monkeypatch.setattr(api,'_authorize_media_novel',lambda *args:None)
    repository=S(get_context_sources=lambda _: {'novel':{'privacy_level':'LOCAL_ONLY'}})
    monkeypatch.setattr(api,'novel_service',S(novels=repository))
    with pytest.raises(ValueError):
        api._assert_manual_media_egress({'novel_id':'synthetic','prompt':'prompt','allow_cloud_prompt':True},S(local=False))


def test_manual_local_input_needs_no_cloud_permission(monkeypatch):
    import app.api as api
    monkeypatch.setattr(api,'settings',S(enable_cloud=False,enable_collaboration_runtime=False))
    api._assert_manual_media_egress({'prompt':'Synthetic local prompt','allow_cloud_prompt':False},S(local=True))

@pytest.mark.parametrize('prefix',['/api','/api/v1'])
def test_real_app_discovery_mount_requires_session_and_exposes_no_paths(prefix,monkeypatch):
    import app.main as main
    monkeypatch.setattr(main,'settings',S(enable_collaboration_runtime=False,enable_packaged_runtime=False))
    client=TestClient(main.app)
    response=client.get(prefix+'/model-center/local-ai')
    assert response.status_code==401
    assert 'roots' not in response.text and 'runtimes' not in response.text
    monkeypatch.setattr(main.trusted_session_resolver,'resolve',lambda token: S(actor_id='synthetic'))
    response=client.get(prefix+'/model-center/local-ai',headers={'X-Session-Token':'synthetic-test-session'})
    assert response.status_code==200,response.text
    assert 'registrations' in response.json()
