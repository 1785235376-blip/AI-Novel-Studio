"""Mounted synthetic speech requests on original trusted Host/File/PG owners.

WAV fixture transport only; real models and browser acceptance NOT_RUN.
"""
from types import SimpleNamespace
import pytest
from app.audio_production_store import AudioProductionStore
from app.audio_providers import HttpAudioProvider
from test_r3_mounted_contracts import mounted, prefix, checked, scoped
from test_v2_independent_workspace_api import client
from test_v2_discovered_image_production_api import image_client, action
from test_v2_storyboard_workspace_api import storyboard_client, get_storyboard, approve_board, shot_action
from test_v2_storyboard_workspace import board_value
from test_v2_independent_workspace import wav_bytes


@pytest.fixture
def speech_client(storyboard_client,monkeypatch):
    from app import audio_providers
    e=storyboard_client; e.speech_calls=[]
    class Wire:
        def post(self,url,**kwargs):
            e.speech_calls.append((url,kwargs))
            return SimpleNamespace(headers={'content-type':'audio/wav'},content=wav_bytes(),raise_for_status=lambda:None)
    provider=HttpAudioProvider(Wire(),'http://127.0.0.1:9876/v1',local=True)
    monkeypatch.setattr(audio_providers,'provider_catalog',lambda:[{'provider_id':'fixture-speech','default_model':'fixture-tts','endpoint':provider.endpoint,'local':True,'capabilities':['TTS']}])
    monkeypatch.setattr(audio_providers,'resolve_provider',lambda *args:('fixture-speech','fixture-tts',provider))
    monkeypatch.setattr(e.production,'audio_store',AudioProductionStore(e.root/'speech-audio'))
    value=board_value();value['shots'][0]['dialogue']=[{'speaker':'Synthetic','text':'Exact authored speech.'}]
    row=checked(e.client.post(e.creative_base+'/documents',headers=e.headers,json=value),201)
    e.board_id=row['id'];e.board_path=e.creative_base+'/documents/'+row['id']
    e.view=approve_board(e,get_storyboard(e))
    e.body={**shot_action(e.view),'document_digest':e.view['document_snapshot']['digest'],'dialogue_index':0,
        'request_id':'mounted-speech','provider':{'operation_id':'m8.audio.speech','provider_id':'fixture-speech','model_id':'fixture-tts'},
        'voice_id':'explicit-voice','speech_rate':1.0}
    return e


def prepare(e,**kwargs):
    return e.client.post(e.board_path+'/shots/shot-1/audio-request',headers=e.headers,json={**e.body,**kwargs})


def test_mounted_explicit_speech_original_audio_review(speech_client):
    e=speech_client
    prepared=checked(prepare(e));assert not e.speech_calls
    assert checked(e.client.get(e.base+'/jobs',headers=e.headers))['items']==[]
    command=prepared['command']; preview=checked(e.client.post(e.base+'/preview',headers=e.headers,json=command))
    job=checked(e.client.post(e.base+'/jobs',headers=e.headers,json={'command':command,'reviewed_preview_digest':preview['preview_digest']}),201)
    path=e.base+'/jobs/audio/'+job['id']
    ready=checked(e.client.post(path+'/execute',headers=e.headers,json=action(job)))
    assert ready['status']=='AWAITING_REVIEW',ready
    aid=ready['output_candidate']['id']
    assert e.client.get(e.studio_base+'/assets/'+aid,headers=e.headers).status_code==404
    reviewed=checked(e.client.post(path+'/review',headers=e.headers,json={**action(ready),'reviewed_output_digest':ready['output_candidate']['digest']}))
    assert reviewed['status']=='APPROVED' and reviewed['command']['storyboard_speech']==prepared['shot_pin']
    assert checked(e.client.get(e.studio_base+'/assets/'+aid,headers=e.headers))['kind']=='audio'
    # Optional cross-layer evidence contains synthetic authored text and WAV only.
    import os,json
    from pathlib import Path
    if os.getenv('STORYBOARD_SPEECH_CAPTURE'):
        target=Path(os.environ['STORYBOARD_SPEECH_CAPTURE']).resolve()
        assert target.is_relative_to(Path(__file__).resolve().parents[1]/'.runtime')
        target.mkdir(parents=True,exist_ok=True)
        (target/(e.backend+'-'+e.prefix.strip('/').replace('/','-')+'.json')).write_text(
            json.dumps({'fixture':'SYNTHETIC_WAV_TRANSPORT_ONLY','prepared':prepared,'queued':job,'ready':ready,'approved':reviewed},indent=2)+'\n')
    assert len(e.speech_calls)==1 and get_storyboard(e)==e.view
    assert checked(e.client.get(e.base+'/timelines',headers=e.headers))['items']==[]


@pytest.mark.parametrize('fault,status',[('missing',401),('forged',401),('origin',403),('forwarded',403)])
def test_speech_preserves_trusted_host(speech_client,fault,status):
    e=speech_client
    headers={} if fault=='missing' else {'X-Session-Token':'forged'} if fault=='forged' else {**e.headers,**({'Origin':'https://untrusted.invalid'} if fault=='origin' else {'Forwarded':'for=127.0.0.1'})}
    response=e.client.post(e.board_path+'/shots/shot-1/audio-request',headers=headers,json=e.body)
    assert response.status_code==status,response.text
    assert not e.speech_calls and get_storyboard(e)==e.view


@pytest.mark.parametrize('field,value',[('document_digest','0'*64),('dialogue_index',9),('voice_id',None),('speech_rate',None),('prompt','forged')])
def test_speech_exact_request_contract(speech_client,field,value):
    e=speech_client;response=prepare(e,**{field:value})
    assert response.status_code in (409,422),response.text
    assert not e.speech_calls


def test_wrong_collaboration_scope_cannot_prepare_or_consume(speech_client,monkeypatch):
    e=speech_client;command=checked(prepare(e))['command']
    p=checked(e.client.post(e.base+'/preview',headers=e.headers,json=command))
    job=checked(e.client.post(e.base+'/jobs',headers=e.headers,json={'command':command,'reviewed_preview_digest':p['preview_digest']}),201)
    try:
        e=scoped(e,monkeypatch)
        for headers in (e.headers,e.viewer_headers,{**e.headers,'X-Branch-ID':e.other_branch}):
            for path,body in ((e.board_path+'/shots/shot-1/audio-request',e.body),
                              (e.base+'/jobs/audio/'+job['id']+'/execute',action(job))):
                response=e.client.post(path,headers=headers,json=body)
                assert response.status_code==403,response.text
        assert not e.speech_calls
    finally:
        if e.backend == 'postgres' and hasattr(e, 'workspace'):
            with e.store._connect() as connection:
                for table in ('domain_role_assignments', 'permission_assignments', 'authorization_audit_events'):
                    connection.execute(f"DELETE FROM {table} WHERE payload->'scope'->>'workspace_id'=%s AND payload->'scope'->>'project_id'=%s", (e.workspace, e.nid))
                connection.execute('DELETE FROM workspace_memberships WHERE workspace_id=%s AND user_id IN (%s,%s)', (e.workspace, e.lead, e.viewer))
                for table in ('storyline_branches', 'storylines'):
                    connection.execute(f"DELETE FROM {table} WHERE payload->>'workspace_id'=%s AND payload->>'project_id'=%s", (e.workspace, e.nid))
                connection.execute('DELETE FROM project_workspaces WHERE project_id=%s AND workspace_id=%s', (e.nid, e.workspace))
                connection.execute("UPDATE novels SET workspace_id='default-workspace' WHERE slug=%s AND workspace_id=%s", (e.nid, e.workspace))
                connection.execute('DELETE FROM workspaces WHERE id=%s', (e.workspace,))
                connection.execute('DELETE FROM users WHERE id IN (%s,%s)', (e.lead, e.viewer))
