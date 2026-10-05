"""Synthetic zero-egress regression cases for the retired/legacy dispatch paths.

All providers and transports below are in-process spies. No real manuscript,
credentials, network requests, or model-validation claim is involved.
"""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace
import threading

import pytest

from app.asset_providers import AssetGenerationResult,AssetProviderRegistry,VideoGenerationResult
from app.model_runtime import (ModelRuntimeError,RuntimeErrorCode,ProviderDescriptor,ModelDescriptor,
                              ModelRegistry,ProviderRegistry,GenerationRuntime,Modality)
from app.model_center.discovery_bridge import LocalTextAdapter
from app.services.screenplay_service import ScreenplayService
from app.workflow import NovelWorkflow
from test_memory_agent_contract import runner,valid_output


def test_quality_memory_profile_cannot_inherit_a_cloud_route(tmp_path):
    agent,bundle,nid,cid,version=runner(tmp_path,valid_output())
    agent.extract(nid,cid,version,profile='QUALITY',job_id='local-memory')
    job=bundle.generations.get('local-memory')
    assert job['request']['profile']=='LOCAL_ONLY'
    assert job['provider']=='mock' and job['execution_mode']=='mock_standin'
    assert len(agent.runtime.provider.requests)==1


@pytest.mark.parametrize('kind',['remote','cloud','local'])
def test_memory_rejects_cloud_and_unverified_local_labels(tmp_path,kind):
    agent,bundle,nid,cid,version=runner(tmp_path,valid_output())
    class Spy:
        endpoint='https://synthetic-cloud.invalid'
        calls=0
        def generate_text(self,request):self.calls+=1;raise AssertionError('no outbound call allowed')
    spy=Spy();registry=agent.runtime.provider_registry
    registry.register(ProviderDescriptor('mock','Unverified',kind,frozenset({Modality.TEXT}),True,True),spy,replace=True)
    with pytest.raises(ModelRuntimeError) as caught:
        agent.extract(nid,cid,version,profile='QUALITY',job_id='blocked-memory')
    assert caught.value.code is RuntimeErrorCode.TEXT_PROVIDER_NOT_CONFIGURED and spy.calls==0
    assert bundle.generations.get('blocked-memory')['status']=='NOT_CONFIGURED'


def test_memory_rechecks_registered_adapter_after_preparation(tmp_path):
    agent,bundle,nid,cid,version=runner(tmp_path,valid_output())
    original=agent.runtime.prepare_text_route
    def replaced(*args):
        descriptor=agent.runtime.provider_registry.descriptors()[0]
        agent.runtime.provider_registry.register(replace(descriptor,provider_type='remote'),object(),replace=True)
        return original(*args)
    agent.runtime.prepare_text_route=replaced
    with pytest.raises(ModelRuntimeError):agent.extract(nid,cid,version,profile='QUALITY')
    assert agent.runtime.provider.requests==[] and bundle.lore.list_proposals(nid)==[]


@pytest.mark.parametrize('packaged,mock_enabled',[(True,True),(False,False)])
def test_memory_never_silently_uses_development_mock(tmp_path,packaged,mock_enabled):
    from app.config import settings
    agent,bundle,nid,cid,version=runner(tmp_path,valid_output())
    object.__setattr__(settings,'enable_packaged_runtime',packaged)
    object.__setattr__(settings,'mock_provider',mock_enabled)
    with pytest.raises(ModelRuntimeError) as caught:agent.extract(nid,cid,version,job_id='no-silent-mock')
    assert caught.value.code is RuntimeErrorCode.TEXT_PROVIDER_NOT_CONFIGURED
    assert agent.runtime.provider.requests==[]
    assert bundle.generations.get('no-silent-mock')['status']=='NOT_CONFIGURED'


def test_memory_registered_loopback_adapter_uses_normalized_node(tmp_path):
    import json
    from test_local_ai_discovery import service,scan,approve_license
    from test_local_ai_discovery_egress import OllamaWire
    from app.model_center.discovery_bridge import LocalDiscoveryBridge
    agent,bundle,nid,cid,version=runner(tmp_path,valid_output())
    runtime=SimpleNamespace(provider_registry=ProviderRegistry(),model_registry=ModelRegistry())
    svc=service(tmp_path);wire=OllamaWire('fixture');wire.response_text=json.dumps(valid_output());svc.client=wire.client()
    svc.route_bridge=LocalDiscoveryBridge(svc,runtime,AssetProviderRegistry())
    candidate=scan(svc)['candidates'][0];svc.validate(candidate['id']);svc.register(candidate['id']);approve_license(svc,candidate['id']);svc.enable(candidate['id'])
    adapter=runtime.provider_registry.resolve(candidate['provider_id']);adapter.client=wire.client()
    generation=GenerationRuntime(runtime.provider_registry,runtime.model_registry)
    runtime.prepare_text_route=lambda *args:generation.text_node
    agent.runtime=runtime
    assert len(agent.extract(nid,cid,version,profile='QUALITY'))==1
    assert len(wire.generations)==1 and wire.generations[0][1]=='/api/generate'


def test_legacy_live_workflow_fails_before_read_write_or_router(tmp_path):
    class Spy:
        calls=0
        def generate(self,*args):self.calls+=1;raise AssertionError('disabled')
    spy=Spy()
    with pytest.raises(RuntimeError,match='LEGACY_WORKFLOW_DISABLED'):
        NovelWorkflow(tmp_path,spy).run('missing-project',1,'synthetic','QUALITY')
    assert spy.calls==0 and list(tmp_path.iterdir())==[]


class Repo:
    def __init__(self,kind='motion'):
        self.row={'id':'screenplay','novel_id':'novel','branch_id':'branch-a','actor_id':'actor-a',
                  'status':'APPROVED','asset_status':'APPROVED','edit_version':0}
        if kind=='motion':
            self.row['motion_tasks']=[{'id':'task','status':'PENDING','provider_id':'provider','model_id':'model',
                'prompt':'Synthetic camera move','start_frame':'https://synthetic.invalid/start.png',
                'end_frame':'https://synthetic.invalid/end.png','constraints':{},'privacy_level':'LOCAL_ONLY'}]
        else:
            self.row['asset_tasks']=[{'id':'task','status':'RUNNING','provider_id':'provider','model_id':'model',
                                      'asset_id':'requirement','attempts':1,'history':[]}]
            self.row['asset_requirements']=[{'id':'requirement','description':'Synthetic swatch'}]
    def get_context_sources(self,novel_id):return deepcopy(getattr(self,'sources',{}))
    def list_screenplays(self,novel_id):return [deepcopy(self.row)]
    def save_screenplay(self,novel_id,screenplay,*,expected_version=None):
        self.row=deepcopy(screenplay);return deepcopy(self.row)


class MediaSpy:
    endpoint='http://127.0.0.1:8189'
    def __init__(self,kind='motion'):self.calls=[];self.kind=kind
    def generate(self,request):
        self.calls.append(request)
        if self.kind=='motion':return VideoGenerationResult('provider','model',remote_task_id='synthetic-remote',status='RUNNING')
        return AssetGenerationResult('provider','model','data:image/png;base64,synthetic-contract-only')


def motion_setup(cloud=False):
    repo=Repo();provider=MediaSpy()
    if cloud:provider.endpoint='https://synthetic-provider.invalid'
    service=ScreenplayService(repo,object(),video_providers={'provider':provider})
    if cloud:
        review=service.motion_privacy('novel','screenplay','task')
        service.update_motion_privacy('novel','screenplay','task','CLOUD_ALLOWED',review['prompt_sha256'],review['request_sha256'])
    return repo,provider,service


def run_motion(service,callback=lambda:None):
    try:return service.execute_motion_task('novel','screenplay','task',reauthorize=callback)
    except (ValueError,PermissionError):return None


@pytest.mark.parametrize('change',['cancel','branch','actor','attempt','token','prompt','provider','privacy','parameters','registration','project-policy','source-policy','screenplay-policy'])
def test_motion_final_fence_catches_mutation_during_frame_preparation(monkeypatch,change):
    import app.media_frames as frames
    repo,provider,service=motion_setup(cloud=True)
    original=frames.resolve_motion_frame;changed=False
    def prepare(*args,**kwargs):
        nonlocal changed
        result=original(*args,**kwargs)
        if not changed:
            changed=True;task=repo.row['motion_tasks'][0]
            if change=='cancel':task['status']='CANCELLED'
            elif change=='branch':repo.row['branch_id']='branch-b'
            elif change=='actor':repo.row['actor_id']='actor-b'
            elif change=='attempt':task['attempts']+=1
            elif change=='token':task['execution_token']='new-attempt'
            elif change=='prompt':task['prompt']='changed synthetic prompt'
            elif change=='provider':task['provider_id']='other'
            elif change=='privacy':task['privacy_level']='LOCAL_ONLY'
            elif change=='parameters':task['constraints']={'camera_motion':'new text not reviewed'}
            elif change=='registration':service.video_providers['provider']=MediaSpy()
            elif change=='project-policy':repo.sources={'novel':{'privacy_level':'LOCAL_ONLY'}}
            elif change=='source-policy':repo.sources={'characters':[{'id':'synthetic-secret-character'}]}
            elif change=='screenplay-policy':repo.row['privacy_level']='LOCAL_ONLY'
        return result
    monkeypatch.setattr(frames,'resolve_motion_frame',prepare)
    run_motion(service)
    assert provider.calls==[] and not repo.row['motion_tasks'][0].get('result')
    if change=='cancel':assert repo.row['motion_tasks'][0]['status']=='CANCELLED'


def test_motion_callback_revocation_and_missing_callback_cannot_dispatch():
    for callback in (None,lambda:(_ for _ in ()).throw(PermissionError('membership revoked'))):
        repo,provider,service=motion_setup()
        run_motion(service,callback)
        assert provider.calls==[] and repo.row['motion_tasks'][0]['status']=='FAILED'


def test_motion_reapproval_requires_exact_frames_parameters_and_route():
    repo,provider,service=motion_setup(cloud=True)
    review=service.motion_privacy('novel','screenplay','task')
    service.update_motion_frames('novel','screenplay','task',constraints={'camera_motion':'new synthetic constraint'})
    with pytest.raises(ValueError,match='request changed'):
        service.update_motion_privacy('novel','screenplay','task','CLOUD_ALLOWED',review['prompt_sha256'],review['request_sha256'])
    with pytest.raises(ValueError,match='REVIEW_REQUIRED'):
        service.execute_motion_task('novel','screenplay','task',reauthorize=lambda:None)
    assert provider.calls==[]


def asset_setup(cloud=False):
    repo=Repo('asset');provider=MediaSpy('asset')
    if cloud:provider.endpoint='https://synthetic-provider.invalid'
    registry=AssetProviderRegistry();registry.register('provider',provider)
    return repo,provider,ScreenplayService(repo,object(),asset_providers=registry)


@pytest.mark.parametrize('change',['cancel','branch','actor','attempt','token','description','provider','registration','endpoint','membership'])
def test_asset_final_fence_catches_preparation_or_permission_drift(change):
    repo,provider,service=asset_setup()
    def changed():
        task=repo.row['asset_tasks'][0]
        if change=='cancel':task['status']='CANCELLED'
        elif change=='branch':repo.row['branch_id']='branch-b'
        elif change=='actor':repo.row['actor_id']='actor-b'
        elif change=='attempt':task['attempts']+=1
        elif change=='token':task['execution_token']='new-attempt'
        elif change=='description':repo.row['asset_requirements'][0]['description']='changed synthetic source'
        elif change=='provider':task['provider_id']='other'
        elif change=='registration':service.asset_providers.register('provider',MediaSpy('asset'))
        elif change=='endpoint':provider.endpoint='https://synthetic-provider.invalid'
        elif change=='membership':raise PermissionError('membership revoked')
    service.execute_asset_task('novel','screenplay','task',reauthorize=changed)
    assert provider.calls==[] and not repo.row['asset_tasks'][0].get('asset_uri')
    if change=='cancel':assert repo.row['asset_tasks'][0]['status']=='CANCELLED'


def test_approved_screenplay_does_not_authorize_remote_asset_description():
    repo,provider,service=asset_setup(cloud=True)
    task=service.execute_asset_task('novel','screenplay','task',reauthorize=lambda:None)['asset_tasks'][0]
    assert task['status']=='FAILED' and task['error']=='IMAGE_CLOUD_PROMPT_REVIEW_REQUIRED'
    assert provider.calls==[]


def test_asset_without_final_authorizer_cannot_dispatch():
    repo,provider,service=asset_setup()
    task=service.execute_asset_task('novel','screenplay','task')['asset_tasks'][0]
    assert task['status']=='FAILED' and task['error']=='MEDIA_DISPATCH_AUTHORIZATION_REQUIRED'
    assert provider.calls==[]


def test_asset_local_success_and_duplicate_active_invocation():
    repo,provider,service=asset_setup();started,release=threading.Event(),threading.Event();generate=provider.generate
    def blocked(request):started.set();assert release.wait(5);return generate(request)
    provider.generate=blocked
    with ThreadPoolExecutor() as pool:
        future=pool.submit(service.execute_asset_task,'novel','screenplay','task',reauthorize=lambda:None)
        assert started.wait(5)
        with pytest.raises(ValueError,match='already executing'):
            service.execute_asset_task('novel','screenplay','task',reauthorize=lambda:None)
        release.set();result=future.result()
    assert result['asset_tasks'][0]['status']=='SUCCEEDED' and len(provider.calls)==1


def test_asset_late_success_does_not_resurrect_cancelled_retried_attempt():
    repo,provider,service=asset_setup();started,release=threading.Event(),threading.Event();generate=provider.generate
    def blocked(request):started.set();assert release.wait(5);return generate(request)
    provider.generate=blocked
    with ThreadPoolExecutor() as pool:
        future=pool.submit(service.execute_asset_task,'novel','screenplay','task',reauthorize=lambda:None)
        assert started.wait(5)
        service.update_asset_task('novel','screenplay','task',{'status':'CANCELLED'})
        service.retry_asset_task('novel','screenplay','task')
        service.update_asset_task('novel','screenplay','task',{'status':'RUNNING'})
        release.set();future.result()
    final=repo.row['asset_tasks'][0]
    assert final['status']=='RUNNING' and final['attempts']==2 and not final.get('asset_uri')


@pytest.mark.parametrize('change',['privacy','version','novel','shot-mapping'])
def test_motion_rechecks_frame_authority_after_final_permission_callback(monkeypatch,change):
    repo,provider,service=motion_setup(cloud=True)
    frame={'id':'frame','novel_id':'novel','branch_id':'branch-a','sha256':'synthetic-digest',
           'version':1,'privacy_level':'CLOUD_ALLOWED'}
    # The real decoder/resolver is covered by the media lifecycle suite. This
    # fixture isolates the last metadata-authority read at the send boundary.
    service.asset_library=SimpleNamespace(get=lambda *args,**kwargs:deepcopy(frame))
    monkeypatch.setattr('app.media_frames.resolve_motion_frame',lambda *args,**kwargs:
        ('data:image/png;base64,synthetic-contract-only',{'kind':'ASSET','asset_id':'frame','asset_sha256':'synthetic-digest','asset_version':1}))
    calls=0
    def permission():
        nonlocal calls
        calls+=1
        if calls==2:
            if change=='privacy':frame['privacy_level']='LOCAL_ONLY'
            elif change=='version':frame['version']=2
            elif change=='novel':frame['novel_id']='other-novel'
            else:repo.row['shots']=[{'id':'shot','frame_asset_id':'other-frame'}]
    run_motion(service,permission)
    assert provider.calls==[] and not repo.row['motion_tasks'][0].get('result')


def test_motion_review_does_not_survive_moving_task_to_another_branch():
    repo,provider,service=motion_setup(cloud=True)
    repo.row['branch_id']='other-branch'
    with pytest.raises(ValueError,match='REVIEW_REQUIRED'):
        service.execute_motion_task('novel','screenplay','task',reauthorize=lambda:None)
    assert provider.calls==[]


def test_motion_missing_model_remains_honestly_not_configured():
    repo,provider,service=motion_setup()
    repo.row['motion_tasks'][0]['model_id']=''
    result=service.execute_motion_task('novel','screenplay','task',reauthorize=lambda:None)['motion_tasks'][0]
    assert result['status']=='PENDING' and result['error']=='VIDEO_PROVIDER_NOT_CONFIGURED' and provider.calls==[]
