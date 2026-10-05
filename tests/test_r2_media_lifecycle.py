"""Synthetic test media is generated here; no voice recording or licensed clip.

The sine/solid-color fixture generators are dedicated to CC0-1.0. These tests
verify file processing/contracts and do not claim real model validation.
"""
import base64
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
import json
from pathlib import Path
import shutil
import socket
import struct
import subprocess
import threading
import wave
import zlib

import pytest

from app.asset_providers import AssetGenerationRequest, AssetGenerationResult, AssetProviderRegistry, Automatic1111ImageProvider, OpenAICompatibleImageProvider, VideoGenerationResult
from app.audio_production_store import AudioProductionStore
from app.audio_providers import AudioGenerationResult, HttpAudioProvider, AudioGenerationRequest
from app.media_files import MediaValidationError, concatenate_wav, fetch_media_bytes, inspect_image, inspect_media, media_destination
from app.net_safety import OutboundURLRejected
from app.services.asset_library_service import AssetLibraryService
from app.services.audiobook_service import AudiobookService, AudiobookError
from app.services.image_job_service import ImageJobService
from app.services.screenplay_service import ScreenplayService


def wav_bytes(samples=800):
    output=BytesIO()
    with wave.open(output,'wb') as audio:
        audio.setnchannels(1);audio.setsampwidth(2);audio.setframerate(8000)
        audio.writeframes(b'\x00\x00'*samples)
    return output.getvalue()


def png_bytes():
    def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',2,2,8,2,0,0,0))+chunk(b'IDAT',zlib.compress((b'\x00'+b'\x11\x22\x33'*2)*2))+chunk(b'IEND',b'')


def audio_setup(tmp_path):
    store=AudioProductionStore(tmp_path/'audio');assets=AssetLibraryService(tmp_path)
    service=AudiobookService(store,assets)
    chapter={'id':'chapter-a','novel_id':'novel-a','content':'First sentence.','version':7,'privacy_level':'CLOUD_ALLOWED'}
    config={'provider_id':'synthetic','model_id':'fixture','voice':'CC0 silence','emotion':'neutral'}
    job=service.queue('novel-a',chapter,config,[{'text':'First sentence.','start_ms':0,'end_ms':1000}])
    return service,store,assets,chapter,job


class FixtureVoice:
    local=True
    def __init__(self, data=None):self.data=data or wav_bytes();self.requests=[]
    def generate(self,request):
        self.requests.append(request)
        return AudioGenerationResult('synthetic','fixture','data:audio/wav;base64,'+base64.b64encode(self.data).decode())


def test_wav_decodes_measures_concatenates_and_rejects_truncation():
    raw=wav_bytes();assert inspect_media(raw,'audio')['duration_ms']==100
    combined,manifest=concatenate_wav([raw,raw],pause_ms=250)
    assert inspect_media(combined,'audio')['duration_ms']==450
    assert [item['start_ms'] for item in manifest]==[0,350]
    with pytest.raises(MediaValidationError):inspect_media(raw[:-2],'audio')
    with pytest.raises(MediaValidationError):inspect_media(b'<html>error</html>','video')


def test_media_private_access_requires_exact_server_owned_provider_origin(monkeypatch):
    monkeypatch.setattr(socket,'getaddrinfo',lambda *args,**kwargs:[(2,1,6,'',('127.0.0.1',8188))])
    with pytest.raises(OutboundURLRejected):media_destination('http://localhost:8188/output.mp4')
    assert media_destination('http://localhost:8188/output.mp4','http://localhost:8188/v1')[2]=='127.0.0.1'
    with pytest.raises(OutboundURLRejected):media_destination('http://localhost:8189/output.mp4','http://localhost:8188/v1')
    with pytest.raises(OutboundURLRejected):media_destination('http://other:8188/output.mp4','http://localhost:8188/v1')
    monkeypatch.setattr(socket,'getaddrinfo',lambda *args,**kwargs:[(2,1,6,'',('169.254.169.254',80))])
    with pytest.raises(OutboundURLRejected):media_destination('http://metadata/latest','http://metadata')


def test_media_download_pins_dns_and_rejects_redirects_and_oversize(monkeypatch):
    import app.media_files as media
    monkeypatch.setattr(socket,'getaddrinfo',lambda *args,**kwargs:[(2,1,6,'',('93.184.216.34',443))])
    calls=[]
    class Response:
        status=200
        def getheader(self,key,default=None):return {'Content-Length':'3'}.get(key,default)
        def read(self,n):
            if getattr(self,'read_done',False):return b''
            self.read_done=True;return b'abc'
    class Connection:
        response=Response()
        def __init__(self,*args,**kwargs):calls.append((args,kwargs));self.sock=None
        def request(self,*args,**kwargs):
            assert self._create_connection(('different.example',80),1)==('93.184.216.34',443)
            calls.append((args,kwargs))
        def getresponse(self):return self.response
        def close(self):pass
    monkeypatch.setattr(media.http.client,'HTTPSConnection',Connection)
    monkeypatch.setattr(socket,'create_connection',lambda target,*args:target)
    assert fetch_media_bytes('https://public.example/file',3)==b'abc'
    assert calls[0][0][0]=='public.example'
    with pytest.raises(OutboundURLRejected):fetch_media_bytes('https://public.example/file',2)
    Connection.response.status=302
    with pytest.raises(OutboundURLRejected):fetch_media_bytes('https://public.example/file',100)


def test_audio_snapshot_real_bytes_manifest_restart_and_exact_once(tmp_path):
    service,store,assets,chapter,job=audio_setup(tmp_path);provider=FixtureVoice()
    chapter['content']='Later edited text.'
    result=service.execute('novel-a',job['id'],chapter,lambda _:('synthetic','fixture',provider))
    assert provider.requests[0].prompt=='First sentence.' and '[emotion:' not in provider.requests[0].prompt
    assert result['status']=='SUCCEEDED' and result['duration_ms']==100
    persisted=AudioProductionStore(store.root).load('novel-a')
    assert persisted['jobs'][0]['source_version']==7 and len(persisted['generations'])==1
    assert assets.content(result['asset_id'])==wav_bytes()
    output,manifest=service.export_chapter('novel-a','chapter-a',[job['id']])
    assert output==wav_bytes() and manifest['segments'][0]['job_id']==job['id']
    with pytest.raises(AudiobookError):service.execute('novel-a',job['id'],chapter,lambda _:('synthetic','fixture',provider))
    assert len(store.load('novel-a')['generations'])==1


@pytest.mark.parametrize('failure',[False,True])
def test_audio_cancel_retry_fences_late_success_and_valueerror(tmp_path,failure):
    service,store,assets,chapter,job=audio_setup(tmp_path)
    started,release=threading.Event(),threading.Event()
    class BlockingVoice(FixtureVoice):
        def generate(self,request):
            started.set();assert release.wait(5)
            if failure:raise ValueError('late provider failure')
            return super().generate(request)
    with ThreadPoolExecutor() as pool:
        future=pool.submit(service.execute,'novel-a',job['id'],chapter,lambda _:('synthetic','fixture',BlockingVoice()))
        assert started.wait(5)
        service.transition('novel-a',job['id'],'CANCELLED')
        service.transition('novel-a',job['id'],'QUEUED')
        release.set();assert future.result()['status']=='QUEUED'
    assert store.load('novel-a')['generations']==[] and assets.list('novel-a')==[]


def test_audio_remote_privacy_and_corrupt_media_fail_closed(tmp_path):
    service,store,assets,chapter,job=audio_setup(tmp_path)
    provider=FixtureVoice();provider.local=False;chapter['privacy_level']='LOCAL_ONLY'
    with pytest.raises(AudiobookError,match='隐私'):service.execute('novel-a',job['id'],chapter,lambda _:('cloud','fixture',provider))
    assert not provider.requests and not assets.list('novel-a')
    service.transition('novel-a',job['id'],'QUEUED')
    with pytest.raises(AudiobookError):service.execute('novel-a',job['id'],chapter,lambda _:('local','fixture',FixtureVoice(b'not audio')))
    assert not assets.list('novel-a')


def test_audio_store_branch_partition_and_corruption_do_not_erase(tmp_path):
    store=AudioProductionStore(tmp_path);a=store.for_branch('branch-a');b=store.for_branch('branch-b')
    a.save('novel-a',{'jobs':[{'id':'job-a'}]});assert b.load('novel-a')['jobs']==[]
    path=a._path('novel-a');path.write_text('{broken')
    with pytest.raises(ValueError):a.mutate('novel-a',lambda state:state['jobs'].clear())
    assert path.read_text()=='{broken'


def test_http_audio_accepts_real_binary_and_does_not_speak_emotion_tags():
    class Response:
        headers={'content-type':'audio/wav'};content=wav_bytes()
        def raise_for_status(self):pass
    class Transport:
        def post(self,*args,**kwargs):self.payload=kwargs['json'];return Response()
    transport=Transport();provider=HttpAudioProvider(transport,'http://127.0.0.1:8001',local=True)
    result=provider.generate(AudioGenerationRequest('local','tts','TTS','Real words','task',parameters={'emotion':'neutral','speed':1.25,'response_format':'wav'}))
    assert result.audio_uri.startswith('data:audio/wav;base64,') and transport.payload['input']=='Real words'
    assert transport.payload['speed']==1.25 and 'emotion' not in transport.payload
    with pytest.raises(ValueError,match='UNSUPPORTED'):provider.generate(AudioGenerationRequest('local','tts','TTS','Words','task',parameters={'emotion':'angry'}))


def test_image_parameters_reach_adapter_and_unknown_parameters_fail():
    class Response:
        def raise_for_status(self):pass
        def json(self):return {'images':['abc']}
    class Transport:
        def post(self,*args,**kwargs):self.payload=kwargs['json'];return Response()
    transport=Transport();provider=Automatic1111ImageProvider(transport,'http://127.0.0.1:7860')
    provider.generate(AssetGenerationRequest('a1111','model','prompt','task',{'seed':3,'steps':12,'width':512,'height':768}))
    assert transport.payload['seed']==3 and transport.payload['width']==512
    with pytest.raises(ValueError):provider.generate(AssetGenerationRequest('a1111','model','prompt','task',{'width':777}))


def test_image_review_queue_restarts_scopes_and_accepts_only_decoded_results(tmp_path):
    if not shutil.which('ffmpeg'):pytest.skip('ffmpeg required for real image validation')
    registry=AssetProviderRegistry()
    class Provider:
        local=True  # Recording-only fixture; no external provider.
        def generate(self,request):return AssetGenerationResult('fixture','fixture','data:image/png;base64,'+base64.b64encode(png_bytes()).decode())
    registry.register('fixture',Provider());service=ImageJobService(tmp_path);assets=AssetLibraryService(tmp_path)
    job=service.create('novel-a','branch-a',{'provider_id':'fixture','model_id':'fixture','prompt':'CC0 synthetic swatch','parameters':{}},'key')
    assert service.list('novel-a','branch-b')==[]
    complete=service.execute('novel-a','branch-a',job['id'],registry)
    assert complete['status']=='SUCCEEDED' and complete['approval_status']=='PENDING' and not assets.list('novel-a')
    restored=ImageJobService(tmp_path);assert restored.list('novel-a','branch-a')[0]['id']==job['id']
    asset=restored.accept('novel-a','branch-a',job['id'],assets,registry)
    assert inspect_image(assets.content(asset['id'],branch_id='branch-a'))['width']==2
    assert restored.accept('novel-a','branch-a',job['id'],assets,registry)['id']==asset['id']


def test_video_late_submission_cannot_resurrect_cancelled_task():
    from test_phase1_video_runtime import Repo,task,approve_synthetic_motion
    repo=Repo(task());started,release=threading.Event(),threading.Event()
    class Provider:
        local=True  # Recording-only fixture; no external provider.
        def generate(self,request):started.set();assert release.wait(5);return VideoGenerationResult('video','model','https://cdn.example/late.mp4','remote-late','SUCCEEDED')
        def cancel(self,remote):self.cancelled=remote
    provider=Provider();service=ScreenplayService(repo,object(),video_providers={'video':provider})
    approve_synthetic_motion(service,'novel-a')
    with ThreadPoolExecutor() as pool:
        future=pool.submit(service.execute_motion_task,'novel-a','screenplay-1','motion-1',reauthorize=lambda:None);assert started.wait(5)
        service.cancel_motion_task('novel-a','screenplay-1','motion-1');release.set();future.result()
    final=repo.rows[0]['motion_tasks'][0]
    assert final['status']=='CANCELLED' and not final.get('result') and provider.cancelled=='remote-late'


def test_video_actual_fixture_decodes_before_asset_import(tmp_path,monkeypatch):
    if not shutil.which('ffmpeg'):pytest.skip('ffmpeg required for real video validation')
    from test_phase1_video_runtime import Repo,task
    clip=tmp_path/'cc0-fixture.mp4'
    subprocess.run(['ffmpeg','-nostdin','-v','error','-f','lavfi','-i','color=c=blue:s=32x32:r=10:d=0.3','-c:v','mpeg4','-y',str(clip)],check=True,timeout=20)
    raw=clip.read_bytes();assert inspect_media(raw,'video')['duration_ms']==300
    repo=Repo(task(status='SUCCEEDED',asset_import={'url':'https://example.test/clip.mp4','filename':'clip.mp4'}));service=ScreenplayService(repo,object());assets=AssetLibraryService(tmp_path)
    monkeypatch.setattr('app.media_files.fetch_media_bytes',lambda *args,**kwargs:raw)
    result=service.download_motion_asset('novel-a','screenplay-1','motion-1',assets)
    assert result['import_status']=='COMPLETED' and result['duration_ms']==300
    assert assets.content(result['asset']['id'])==raw
    repo=Repo(task(status='SUCCEEDED',asset_import={'url':'https://example.test/bad.mp4','filename':'bad.mp4'}));service=ScreenplayService(repo,object())
    monkeypatch.setattr('app.media_files.fetch_media_bytes',lambda *args,**kwargs:b'<html>Provider outage</html>')
    assert service.download_motion_asset('novel-a','screenplay-1','motion-1',assets)['import_status']=='FAILED'
    assert len(assets.list('novel-a'))==1


def test_local_video_assembly_preserves_order_trim_lineage_and_scopes(tmp_path):
    if not shutil.which('ffmpeg'):pytest.skip('ffmpeg required for real video assembly')
    from app.services.video_assembly_service import VideoAssemblyService
    assets=AssetLibraryService(tmp_path);source=tmp_path/'source.mp4'
    subprocess.run(['ffmpeg','-nostdin','-v','error','-f','lavfi','-i','color=c=red:s=32x32:r=24:d=1','-c:v','mpeg4','-y',str(source)],check=True,timeout=20)
    asset=assets.create('novel-a','cc0-solid-red.mp4',base64.b64encode(source.read_bytes()).decode(),'video/mp4','video',branch_id='branch-a')
    service=VideoAssemblyService(tmp_path,assets)
    job=service.create('novel-a','branch-a','actor-a','screenplay-a',[{'asset_id':asset['id'],'start_ms':500,'end_ms':750},{'asset_id':asset['id'],'start_ms':0,'end_ms':250}])
    assert job['status']=='SUCCEEDED' and job['audio_policy']=='VIDEO_ONLY'
    assert [clip['start_ms'] for clip in job['clips']]==[500,0]
    assert abs(job['duration_ms']-500)<50
    assert assets.get(job['asset_id'],branch_id='branch-a')['source_asset_ids']==[asset['id']]
    assert service.list('novel-a','branch-a','actor-b')==[]
    assert VideoAssemblyService(tmp_path,assets).list('novel-a','branch-a','actor-a')[0]['id']==job['id']
    with pytest.raises(ValueError):service.create('novel-a','branch-a','actor-a','screenplay-a',[{'asset_id':asset['id'],'start_ms':0,'end_ms':1001}])


def test_motion_local_frame_resolution_checks_real_assets_and_never_fakes_shots(tmp_path):
    if not shutil.which('ffmpeg'):pytest.skip('ffmpeg required for frame decoding')
    from app.media_frames import resolve_motion_frame
    assets=AssetLibraryService(tmp_path)
    asset=assets.create('novel-a','synthetic.png',base64.b64encode(png_bytes()).decode(),'image/png','image',branch_id='branch-a')
    screenplay={'branch_id':'branch-a','shots':[{'id':'shot-a','frame_asset_id':asset['id']},{'id':'shot-empty'}]}
    provider=type('Local',(),{'endpoint':'http://127.0.0.1:8189'})()
    uri,source=resolve_motion_frame('shot:shot-a',screenplay,'novel-a',provider,assets)
    assert uri.startswith('data:image/png;base64,') and source['asset_sha256']==asset['sha256'] and source['content_verified']
    with pytest.raises(ValueError,match='no rendered'):resolve_motion_frame('shot:shot-empty',screenplay,'novel-a',provider,assets)
    with pytest.raises(ValueError,match='this project'):resolve_motion_frame('asset:'+asset['id'],screenplay,'novel-b',provider,assets)
    with pytest.raises(ValueError,match='PRIVACY'):resolve_motion_frame('asset:'+asset['id'],screenplay,'novel-a',type('Cloud',(),{'endpoint':'https://provider.example'})(),assets)


def test_cloud_video_prompt_requires_explicit_hash_bound_review():
    from test_phase1_video_runtime import Repo,task
    from app.asset_providers import VideoGenerationResult
    class Provider:
        local=True  # Recording-only fixture; no external provider.
        def __init__(self):self.calls=0
        def generate(self,request):self.calls+=1;return VideoGenerationResult('video','model',remote_task_id='remote',status='RUNNING')
    provider=Provider();repo=Repo(task(privacy_level='LOCAL_ONLY',cloud_approval_prompt_sha256=None));service=ScreenplayService(repo,object(),video_providers={'video':provider})
    with pytest.raises(ValueError,match='REVIEW_REQUIRED'):service.execute_motion_task('novel-a','screenplay-1','motion-1')
    assert provider.calls==0
    review=service.motion_privacy('novel-a','screenplay-1','motion-1')
    with pytest.raises(ValueError,match='changed'):service.update_motion_privacy('novel-a','screenplay-1','motion-1','CLOUD_ALLOWED','0'*64)
    service.update_motion_privacy('novel-a','screenplay-1','motion-1','CLOUD_ALLOWED',review['prompt_sha256'],review['request_sha256'])
    service.execute_motion_task('novel-a','screenplay-1','motion-1',reauthorize=lambda:None);assert provider.calls==1


def test_audio_cloud_uses_reviewed_source_and_rechecks_drift_before_dispatch(tmp_path,monkeypatch):
    from app.source_privacy import review_source_privacy,content_digest
    import app.source_privacy as privacy
    monkeypatch.setattr(privacy,'settings',type('Settings',(),{'data_path':lambda self:tmp_path})())
    service,store,assets,chapter,old_job=audio_setup(tmp_path)
    review_source_privacy(chapter,None,'author','CLOUD_ALLOWED',chapter['version'],content_digest(chapter),root=tmp_path)
    # Approval after queueing does not retroactively upgrade an unreviewed snapshot.
    cloud=FixtureVoice();cloud.local=False
    with pytest.raises(AudiobookError,match='隐私'):service.execute('novel-a',old_job['id'],chapter,lambda _:('cloud','fixture',cloud))
    job=service.queue('novel-a',chapter,{'provider_id':'cloud','voice':'licensed synthetic'},[])
    result=service.execute('novel-a',job['id'],chapter,lambda _:('cloud','fixture',cloud),check_project_policy=lambda:None)
    assert result['status']=='SUCCEEDED' and len(cloud.requests)==1
    next_job=service.queue('novel-a',chapter,{'provider_id':'cloud','voice':'licensed synthetic'},[])
    newer={**chapter,'content':'Changed secret','version':8}
    with pytest.raises(AudiobookError,match='版本'):service.execute('novel-a',next_job['id'],chapter,lambda _:('cloud','fixture',cloud),lambda:newer)
    assert len(cloud.requests)==1


def test_configured_ipv6_loopback_works_but_mapped_metadata_never_does(monkeypatch):
    monkeypatch.setattr(socket,'getaddrinfo',lambda *args,**kwargs:[(10,1,6,'',('::1',8188,0,0))])
    assert media_destination('http://localhost:8188/output','http://localhost:8188/v1')[2]=='::1'
    with pytest.raises(OutboundURLRejected):media_destination('http://localhost:8188/output')
    monkeypatch.setattr(socket,'getaddrinfo',lambda *args,**kwargs:[(10,1,6,'',('::ffff:169.254.169.254',8188,0,0))])
    with pytest.raises(OutboundURLRejected):media_destination('http://localhost:8188/output','http://localhost:8188/v1')


def test_cloud_provider_same_origin_does_not_gain_private_dns_access(monkeypatch):
    monkeypatch.setattr(socket,'getaddrinfo',lambda *args,**kwargs:[(2,1,6,'',('10.2.3.4',443))])
    with pytest.raises(OutboundURLRejected):media_destination('https://cloud.example/output.mp4','https://cloud.example/v1')
