"""Real File/HTTP VTT import through original timeline and revision owners."""
import base64
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace
import pytest
from app.actor_context import SessionContext
from app.audio_production_store import AudioProductionStore
from app.asset_providers import AssetProviderRegistry
from app.creative.production_execution import ProductionExecutionService
from app.experimental import api as experimental_api
from app.services.image_job_service import ImageJobService
from app.services.video_assembly_service import VideoAssemblyService
from test_studio_asset_query import rig
from test_studio_workspace_identity_history_contract import NoExternalCalls

pytestmark = pytest.mark.file_backend_only

def checked(r, status=200):
    assert r.status_code == status, r.text
    return r.json()

def files(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file()}

@pytest.fixture
def case(rig, monkeypatch, tmp_path):
    p = ProductionExecutionService(rig.workspace, ImageJobService(rig.root/'image'), AssetProviderRegistry(),
        VideoAssemblyService(rig.root/'video', rig.assets), {}, {}, AudioProductionStore(rig.root/'audio'),
        NoExternalCalls(), NoExternalCalls())
    for name, value in p.__dict__.items():
        monkeypatch.setattr(experimental_api.studio_production_service, name, value, raising=False)
    token = 'otio-runtime-host'
    rig.sessions.register(token, SessionContext('otio-session','otio-client','otio-actor','otio-workspace'))
    headers = {'X-Session-Token': token}
    checked(rig.client.post(f'/api/projects/{rig.nid}/studio/activate', headers=headers))
    media = tmp_path/'synthetic.mp4'
    subprocess.run(['ffmpeg','-nostdin','-v','error','-f','lavfi','-i','color=c=blue:s=64x64:r=25:d=2',
        '-an','-c:v','mpeg4','-threads','1','-y',str(media)], check=True, timeout=20)
    with rig.workspace._asset_scope(rig.nid,rig.scope):
        asset = rig.assets.create(rig.nid,'synthetic.mp4',base64.b64encode(media.read_bytes()).decode(),
            'video/mp4','video',required_features=('narrative_production_v2',))
    source = {'kind':'ASSET','asset_kind':'video','id':asset['id'],'version':asset['version'],'digest':asset['sha256']}
    definition = {'schema_version':2,'duration_ms':1000,'width':640,'height':360,'fps':25,
        'tracks':[{'id':'v1','kind':'VIDEO','order':0,'clips':[{'id':'clip1','source_snapshot':source,
        'start_ms':0,'in_ms':400,'out_ms':1400,'include_audio':False}]}],
        'captions':[{'start_ms':0,'end_ms':500,'text':'Synthetic OTIO caption'}]}
    created = checked(rig.client.post(f'/api/projects/{rig.nid}/studio/production/timelines',headers=headers,
        json={'expected_version':0,'title':'Synthetic OTIO transfer','timeline':definition}),201)
    return SimpleNamespace(rig=rig,p=p,headers=headers,row=created,asset=asset)


@pytest.mark.parametrize('prefix', ['/api', '/api/v1'])
def test_external_vtt_preview_commit_replay_history_restore(case, prefix):
    from test_studio_vtt_literal_rebuild_20261029 import vtt
    e = case
    url = f'{prefix}/projects/{e.rig.nid}/studio/production/timelines/{e.row["id"]}'
    request = {'expected_version': e.row['version'], 'reviewed_timeline_digest': e.row['timeline_digest'],
               'direction': 'IMPORT', 'format': 'VTT', 'content': vtt('caf&eacute; &#65; &copy;')}
    before = files(e.rig.root)
    preview = checked(e.rig.client.post(url+'/transfer-preview', headers=e.headers, json=request))
    assert files(e.rig.root) == before
    assert preview['timeline']['captions'][0]['text'] == 'café A ©'
    assert preview['model_called'] is False and preview['external_media_access'] is False
    commit = {**request, 'request_id': 'vtt-external-import', 'reviewed_preview_digest': preview['preview_digest'],
              'acknowledge_losses': True}
    applied = checked(e.rig.client.post(url+'/transfer-import', headers=e.headers, json=commit))
    assert applied['version'] == 2
    assert applied['timeline']['tracks'] == e.row['timeline']['tracks']
    assert applied['timeline']['captions'][0]['text'] == 'café A ©'
    after = files(e.rig.root)
    assert checked(e.rig.client.post(url+'/transfer-import', headers=e.headers, json=commit)) == applied
    assert files(e.rig.root) == after
    history = checked(e.rig.client.get(url+'/history', headers=e.headers))
    assert history['current_version'] == 2 and len(history['items']) == 1
    restored = checked(e.rig.client.post(url+'/restore', headers=e.headers, json={
        'expected_version': 2, 'reviewed_timeline_digest': applied['timeline_digest'],
        'restore_version': 1, 'restore_digest': e.row['timeline_digest']}))
    assert restored['version'] == 3 and restored['timeline'] == e.row['timeline']

@pytest.mark.parametrize('text', ['&#60;b&#62;', '&#1;'])
def test_external_vtt_forbidden_decoded_text_is_read_only(case, text):
    from test_studio_vtt_literal_rebuild_20261029 import vtt
    e = case
    url = f'/api/projects/{e.rig.nid}/studio/production/timelines/{e.row["id"]}/transfer-preview'
    before = files(e.rig.root)
    result = e.rig.client.post(url, headers=e.headers, json={
        'expected_version': e.row['version'], 'reviewed_timeline_digest': e.row['timeline_digest'],
        'direction': 'IMPORT', 'format': 'VTT', 'content': vtt(text)})
    assert result.status_code == 422, result.text
    assert files(e.rig.root) == before
