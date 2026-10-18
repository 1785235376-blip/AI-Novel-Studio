"""Synthetic speech transport only; original File/PG owners and real WAV decoding.

No real speech model, browser, paid compute or movie acceptance is claimed.
"""
from copy import deepcopy
from types import SimpleNamespace
import pytest
from app.creative.production_execution_models import MediaCommand
from app.experimental.common import StaleSourceError
from test_v2_independent_workspace import rig, wav_bytes, reopened
from test_v2_storyboard_workspace import board_value, content, approve
from test_v2_storyboard_video_pipeline import shot_action
from test_v2_audio_wav_controls import production, queue, action


def setup(e, monkeypatch):
    from app import audio_providers
    from app.audio_providers import HttpAudioProvider
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'narrative_production_v2,asset_lineage_v2,ai_execution_v2,model_broker_v2,author_context_inspector_v2')
    e.service.activate(e.nid, e.scope, e.actor)
    e.production = production(e)
    calls = []
    class Wire:
        def post(self, url, **kwargs):
            calls.append((url, kwargs))
            return SimpleNamespace(headers={'content-type': 'audio/wav'}, content=wav_bytes(), raise_for_status=lambda: None)
    provider = HttpAudioProvider(Wire(), 'http://127.0.0.1:9876/v1', local=True)
    monkeypatch.setattr(audio_providers, 'provider_catalog', lambda: [{'provider_id':'fixture-speech','default_model':'fixture-tts','endpoint':provider.endpoint,'local':True,'capabilities':['TTS']}])
    monkeypatch.setattr(audio_providers, 'resolve_provider', lambda *args: ('fixture-speech','fixture-tts',provider))
    e.service.creative.configure_storyboard_production(e.production)
    value = board_value()
    value['shots'][0]['dialogue'] = [{'speaker':'A','text':'First synthetic line.'},{'speaker':'B','text':' Second exact line. '}]
    row = e.service.creative.create(e.nid,e.scope,e.actor,value)
    view = approve(e.service.creative,e,row['id'])
    e.board, e.board_view, e.calls = row, view, calls
    e.synthetic_provider = provider
    e.body = {**shot_action(view),'document_digest':view['document_snapshot']['digest'],'dialogue_index':1,
        'request_id':'fixture-speech-request','provider':{'operation_id':'m8.audio.speech','provider_id':'fixture-speech','model_id':'fixture-tts'},
        'voice_id':'explicit-fixture-voice','speech_rate':1.25}
    return e


@pytest.fixture
def speech(rig, monkeypatch):
    return setup(rig, monkeypatch)


def prepare(e, body=None):
    return e.service.creative.storyboards.audio_request(e.nid,e.scope,e.actor,e.board['id'],'shot-1',body or e.body)


def edit(e):
    row=e.service.creative.get(e.nid,e.scope,e.board['id']); value=content(row)
    value['shots'][0]['dialogue'][1]['text']='Changed source'
    e.service.creative.update(e.nid,e.scope,e.actor,row['id'],row['version'],value)


def test_original_speech_private_review_asset_and_reopen(speech):
    e=speech; before=e.raw_store.read(e.nid,e.scope); prepared=prepare(e)
    assert e.raw_store.read(e.nid,e.scope)==before and not e.calls
    assert prepared['command']['prompt']==' Second exact line. '
    assert prepared['automatic_dispatch'] is prepared['model_called'] is False
    job=queue(e, prepared['command'])
    ready=e.production.execute(e.nid,e.scope,e.actor,'audio',job['id'],action(job),lambda:None)
    assert ready['status']=='AWAITING_REVIEW', str(ready)
    assert len(e.calls)==1 and e.calls[0][1]['json']['input']==' Second exact line. '
    with pytest.raises(FileNotFoundError): e.service.asset(e.nid,e.scope,ready['output_candidate']['id'])
    approved=e.production.review(e.nid,e.scope,e.actor,'audio',job['id'],action(ready,True),lambda:None)
    assert approved['status']=='APPROVED'
    aid=approved['output_candidate']['id']
    assert reopened(e).asset(e.nid,e.scope,aid)['kind']=='audio'
    with e.service._asset_scope(e.nid,e.scope):
        assert e.assets.get(aid,branch_id=e.scope.get('branch_id'))['_studio_result_origin']['storyboard_speech']==prepared['shot_pin']
    assert e.service.creative.storyboards.get(e.nid,e.scope,e.actor,e.board['id'])==e.board_view


@pytest.mark.parametrize('field,value',[('dialogue_index',0),('dialogue_index',199),('prompt','forged'),('shot_digest','0'*64),('shot_version',2),('document_digest','0'*64)])
def test_forged_command_rejected_at_preview(speech,field,value):
    e=speech; command=prepare(e)['command']
    if field=='prompt': command[field]=value
    elif field=='document_digest': command['storyboard_speech']['document_snapshot']['digest']=value
    else: command['storyboard_speech'][field]=value
    with pytest.raises((ValueError,StaleSourceError)):
        e.production.preview(e.nid,e.scope,e.actor,command,lambda:None)
    assert not e.calls


@pytest.mark.parametrize('field,value',[('dialogue_index',True),('dialogue_index',-1),('dialogue_index',2),('voice_id',''),('speech_rate',None),('speech_rate',3),('document_digest','0'*64),('prompt','forged')])
def test_preparation_rejects_invalid_or_missing_explicit_choices(speech,field,value):
    with pytest.raises((ValueError,StaleSourceError)):
        prepare(speech,{**speech.body,field:value})
    assert not speech.calls


@pytest.mark.parametrize('stage',['preview','create','execute','review'])
def test_source_change_fails_closed(speech,stage):
    e=speech; command=prepare(e)['command']; preview=e.production.preview(e.nid,e.scope,e.actor,command,lambda:None)[0]
    if stage in ('execute','review'): job=queue(e,command)
    if stage=='review': job=e.production.execute(e.nid,e.scope,e.actor,'audio',job['id'],action(job),lambda:None)
    edit(e)
    if stage=='execute':
        try: result=e.production.execute(e.nid,e.scope,e.actor,'audio',job['id'],action(job),lambda:None)
        except (ValueError,StaleSourceError): pass
        else: assert result['status']!='AWAITING_REVIEW'
    else:
        with pytest.raises((ValueError,StaleSourceError)):
            if stage=='preview': e.production.preview(e.nid,e.scope,e.actor,command,lambda:None)
            elif stage=='create': e.production.create(e.nid,e.scope,e.actor,{'command':command,'reviewed_preview_digest':preview['preview_digest']},lambda:None)
            else: e.production.review(e.nid,e.scope,e.actor,'audio',job['id'],action(job,True),lambda:None)
    assert len(e.calls)==(1 if stage=='review' else 0)


def test_absent_speech_preserves_legacy_and_video_boundary():
    value={'operation_id':'m8.audio.speech','request_id':'legacy','provider_id':'p','model_id':'m','prompt':'legacy'}
    assert 'storyboard_speech' not in MediaCommand.model_validate(value).model_dump()
    assert MediaCommand.model_validate(value).model_dump()==MediaCommand.model_validate({**value,'storyboard_speech':None}).model_dump()


@pytest.mark.parametrize('target',['context','body','command','digest','graph'])
def test_original_audio_owner_rejects_mismatched_speech_binding(speech,target):
    from app.services.studio_audio_execution import _binding, _body
    from app.services.audiobook_service import AudiobookError
    e=speech; command=prepare(e)['command']; _,context,parsed=e.production.preview(e.nid,e.scope,e.actor,command,lambda:None)
    context['command']=parsed.model_dump()
    payload=parsed.model_dump(exclude={'request_id','allow_cloud','license_note'})
    payload['parameters']=parsed.parameters.model_dump(exclude_none=True);payload['source_snapshots']=context['sources']
    body=_body(payload)
    if target=='context': context['storyboard_speech']['dialogue_index']=0
    elif target=='body': body['storyboard_speech']['dialogue_index']=0
    elif target=='command': context['command']['prompt']='forged'
    elif target=='graph': context['graph_binding']={}
    else: context['request_digest']='0'*64
    with pytest.raises((ValueError,AudiobookError)): _binding(context,body)


@pytest.mark.parametrize('stage',['execute','review'])
def test_wrong_actor_cannot_consume_original_speech_job(speech,stage):
    from app.services.audiobook_service import AudiobookError
    e=speech;job=queue(e,prepare(e)['command'])
    if stage=='review':job=e.production.execute(e.nid,e.scope,e.actor,'audio',job['id'],action(job),lambda:None)
    with pytest.raises((FileNotFoundError,AudiobookError)):
        if stage=='execute':e.production.execute(e.nid,e.scope,'another-actor','audio',job['id'],action(job),lambda:None)
        else:e.production.review(e.nid,e.scope,'another-actor','audio',job['id'],action(job,True),lambda:None)


def test_revoked_authority_and_wrong_document_do_not_prepare(speech):
    e=speech
    def denied():raise PermissionError('synthetic permission revoked')
    with pytest.raises(PermissionError):
        e.service.creative.storyboards.audio_request(e.nid,e.scope,e.actor,e.board['id'],'shot-1',e.body,denied)
    with pytest.raises(FileNotFoundError):
        e.service.creative.storyboards.audio_request(e.nid,e.scope,e.actor,'foreign-document','shot-1',e.body)
    assert not e.calls


def test_review_rejects_changed_candidate_speech_provenance(speech,monkeypatch):
    e=speech;job=queue(e,prepare(e)['command'])
    ready=e.production.execute(e.nid,e.scope,e.actor,'audio',job['id'],action(job),lambda:None)
    aid=ready['output_candidate']['id']; original=e.assets.get
    def forged(asset_id,*args,**kwargs):
        row=original(asset_id,*args,**kwargs)
        if asset_id==aid:
            row=deepcopy(row);row['_studio_result_origin']['storyboard_speech']['dialogue_index']=0
        return row
    monkeypatch.setattr(e.assets,'get',forged)
    with pytest.raises(ValueError,match='STORYBOARD_SPEECH_CANDIDATE_CHANGED'):
        e.production.review(e.nid,e.scope,e.actor,'audio',job['id'],action(ready,True),lambda:None)
    with pytest.raises(FileNotFoundError): e.service.asset(e.nid,e.scope,aid)


@pytest.mark.parametrize('stage',['resolution','send','promotion'])
def test_late_authority_revocation_never_dispatches_or_promotes(speech,monkeypatch,stage):
    from app import audio_providers
    e=speech;job=queue(e,prepare(e)['command']);revoked=[False];reached=[]
    def guard():
        if revoked[0]:raise PermissionError('synthetic revoked authority at '+stage)
    if stage=='resolution':
        original=audio_providers.resolve_provider
        def revoke(*args):
            reached.append(stage);revoked[0]=True;return original(*args)
        monkeypatch.setattr(audio_providers,'resolve_provider',revoke)
    elif stage=='send':
        original=e.synthetic_provider.generate
        def revoke(request):
            reached.append(stage);revoked[0]=True;return original(request)
        monkeypatch.setattr(e.synthetic_provider,'generate',revoke)
    else:
        job=e.production.execute(e.nid,e.scope,e.actor,'audio',job['id'],action(job),guard)
        original=e.assets.promote_owned
        def revoke(*args,**kwargs):
            reached.append(stage);revoked[0]=True;return original(*args,**kwargs)
        monkeypatch.setattr(e.assets,'promote_owned',revoke)
    with pytest.raises(PermissionError):
        if stage=='promotion':e.production.review(e.nid,e.scope,e.actor,'audio',job['id'],action(job,True),guard)
        else:e.production.execute(e.nid,e.scope,e.actor,'audio',job['id'],action(job),guard)
    assert reached==[stage] and len(e.calls)==(1 if stage=='promotion' else 0)
    assert e.service.list_assets(e.nid,e.scope)['items']==[]


def test_recreated_project_cannot_read_or_execute_old_speech_job(speech,monkeypatch):
    from app.creative.graph_asset_inputs import GraphAssetInputs
    from app.services.audiobook_service import AudiobookError
    e=speech;job=queue(e,prepare(e)['command']);identity=e.store.incarnation(e.nid)
    e.novels.delete(e.nid);e.create_project('Recreated synthetic speech project',nid=e.nid)
    fresh=reopened(e);fresh.activate(e.nid,e.scope,e.actor)
    assert fresh.store.incarnation(e.nid)!=identity
    monkeypatch.setattr(e.production,'workspace',fresh);monkeypatch.setattr(e.production,'store',fresh.store)
    monkeypatch.setattr(e.production,'timeline_inputs',GraphAssetInputs(e.production))
    def private_read(*args,**kwargs):pytest.fail('stale incarnation read private source')
    monkeypatch.setattr(fresh.creative,'get',private_read)
    with pytest.raises((FileNotFoundError,AudiobookError)):
        e.production.execute(e.nid,e.scope,e.actor,'audio',job['id'],action(job),lambda:None)
    assert not e.calls


def test_wrong_actor_denied_before_private_source_read(speech,monkeypatch):
    from app.services.audiobook_service import AudiobookError
    e=speech;job=queue(e,prepare(e)['command'])
    def private_read(*args,**kwargs):pytest.fail('wrong actor read private source')
    monkeypatch.setattr(e.service.creative,'get',private_read)
    with pytest.raises((FileNotFoundError,AudiobookError)):
        e.production.execute(e.nid,e.scope,'foreign-actor','audio',job['id'],action(job),lambda:None)
    assert not e.calls


def test_baseline_ce3ac098_speech_and_video_canonical_omission_bytes():
    import hashlib,json
    from pathlib import Path
    from app.experimental.store import canonical
    fixture=json.loads((Path(__file__).parent/'fixtures/storyboard_speech_legacy_ce3ac098.json').read_text())
    assert fixture['source_commit']=='ce3ac098'
    for case in fixture['cases']:
        parsed=MediaCommand.model_validate(case['input'])
        encoded=canonical(parsed.model_dump())
        assert encoded==case['canonical_command']
        assert hashlib.sha256(encoded.encode()).hexdigest()==case['sha256']
        assert 'storyboard_speech' not in parsed.model_dump()
