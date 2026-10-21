"""Input-only audio drafts on the original Timeline CAS/history owner.

Owned synthetic WAVs only. Cold File reopen re-creates real services in a new
Python process; no saved proof, provider/model, parallel queue or storage owner.
"""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
from threading import Barrier
from types import SimpleNamespace
import wave

import pytest

from app.creative.production_execution import TIMELINES, digest
from app.experimental.common import StaleSourceError
from app.services.audiobook_service import AudiobookError
from app.services.v1_capability_service import CapabilityVersionConflict
from app.services.studio_timeline_render import normalize_studio_timeline
from test_creative_canvas_views_additive import owner, reference
from test_studio_canvas_audio_envelope import envelope_canvas, return_body, RATE, AMPLITUDE
from test_studio_canvas_audio_template_effects import effect_template, pin, LOCAL, save_template, no_jobs, no_native
from test_studio_canvas_audio_derived_recovery import failed_audio, derived_command, rows
from test_studio_canvas_audio_return import audio_canvas, change_origin
from test_v2_audio_wav_controls import production, preview, queue, run, get, review
from test_v2_independent_workspace import rig, reopened, services
from test_r3_mounted_contracts import checked, mounted, prefix
from test_v2_independent_workspace_api import client
from test_v2_audio_wav_controls_api import audio_client

REJECTED = (ValueError, StaleSourceError, FileNotFoundError, AudiobookError, CapabilityVersionConflict)


def inputs(e, *, request='saved-unqueued-audio', command=None):
    command = command or e.command
    return {'contract': 'studio-canvas-audio-draft/1', 'request_id': request,
        'parameters': deepcopy(command['parameters']),
        'source_snapshots': [{k: v for k, v in s.items() if k != 'reference_only'} for s in command['source_snapshots']],
        'canvas_return': deepcopy(command['canvas_return']), 'license_note': command.get('license_note', ''),
        **{k: deepcopy(command[k]) for k in ('template_ref', 'derived_from') if k in command}}


def timeline(value):
    p = value['parameters']
    return normalize_studio_timeline({'schema_version': 3, 'media_kind': 'AUDIO',
        'duration_ms': p['out_ms'] - p['in_ms'], 'tracks': [{
            'id': 'canvas-audio-track', 'kind': 'AUDIO', 'role': 'DIALOGUE', 'order': 0,
            'muted': False, 'gain_db': 0, 'clips': [{'id': 'canvas-audio-clip',
                'source_snapshot': deepcopy(value['source_snapshots'][0]), 'start_ms': 0,
                'in_ms': p['in_ms'], 'out_ms': p['out_ms'], 'speed_num': 1, 'speed_den': 1,
                'muted': False, 'gain_db': p.get('gain_db', 0),
                'fade_in_ms': p.get('fade_in_ms', 0), 'fade_out_ms': p.get('fade_out_ms', 0)}]}]})


def body(value, version=0):
    return {'title': 'Owned unqueued audio input', 'timeline': timeline(value),
            'expected_version': version, 'canvas_audio_draft': deepcopy(value)}


def save(e, value, row=None, guard=lambda: None):
    return e.production.timeline_save(e.nid, e.scope, e.actor, row['id'] if row else None,
                                      body(value, row['version'] if row else 0), guard)


def read(e, row, guard=lambda: None):
    return e.production.timeline_get(e.nid, e.scope, e.actor, row['id'], guard)


def command(value):
    # Rebuild only the original MediaCommand input, never authorization/preview.
    return {'operation_id': 'm8.audio.trim', 'request_id': value['request_id'],
        'provider_id': None, 'model_id': None, 'prompt': '', 'allow_cloud': False,
        'parameters': deepcopy(value['parameters']), 'source_snapshots': deepcopy(value['source_snapshots']),
        'canvas_return': deepcopy(value['canvas_return']), 'license_note': value.get('license_note', ''),
        **{k: deepcopy(value[k]) for k in ('template_ref', 'derived_from') if k in value}}


def exact_saved(row, value):
    saved = row['canvas_audio_draft']
    assert {k: saved[k] for k in value} == value
    assert set(saved) == set(value) | {'timeline_snapshot'}
    assert saved['timeline_snapshot'] == {'id': row['id'], 'version': row['version'], 'digest': row['timeline_digest']}
    assert row['canvas_audio_draft_digest'] == digest(saved)
    assert row['timeline'] == timeline(value)
    assert not {'proof', 'authorization', 'preview_digest', 'reviewed_preview_digest', 'confirmation'}.intersection(saved)
    return saved


def test_baseline_legacy_audio_timeline_has_no_draft_metadata_and_never_queues(envelope_canvas, monkeypatch):
    e = envelope_canvas; value = inputs(e)
    no_native(monkeypatch)
    request = body(value); request.pop('canvas_audio_draft')
    row = e.production.timeline_save(e.nid, e.scope, e.actor, None, request, lambda: None)
    assert row['timeline'] == timeline(value)
    assert not {'canvas_audio_draft', 'canvas_audio_draft_digest', 'canvas_video_draft'}.intersection(row)
    assert read(e, row) == row
    no_jobs(e)


def test_save_plain_and_effect_template_inputs_reopen_without_any_job_or_proof(effect_template, monkeypatch):
    e = effect_template; e.command['parameters'] = deepcopy(LOCAL)
    before = deepcopy(e.store.read(e.nid, e.scope)); value = inputs(e)
    no_native(monkeypatch)
    row = save(e, value); saved = exact_saved(row, value)
    doc = e.store.read(e.nid, e.scope)
    assert set(doc['collections']) == set(before['collections']) | {TIMELINES}
    assert len(doc['collections'][TIMELINES]) == len(before['collections'].get(TIMELINES, {})) + 1
    assert doc['collections'][TIMELINES][row['id']]['canvas_audio_draft'] == saved
    no_jobs(e)
    e.service = reopened(e); e.store = e.service.store; e.production = production(e); e.graph = owner(e); e.graph.configure_media(e.production)
    listed = next(item for item in e.production.timeline_list(e.nid, e.scope, e.actor, lambda: None)['items'] if item['id'] == row['id'])
    assert listed == read(e, row) == row
    assert saved['template_ref'] == pin(e.template) and saved['parameters'] == LOCAL
    assert saved['parameters'] != saved['template_ref']['parameters']
    no_jobs(e)


def test_plain_input_optional_effects_stay_omitted(envelope_canvas, monkeypatch):
    e = envelope_canvas; no_native(monkeypatch)
    value = inputs(e); row = save(e, value)
    exact_saved(row, value)
    assert row['canvas_audio_draft']['parameters'] == {'in_ms': 200, 'out_ms': 1200}
    assert 'template_ref' not in row['canvas_audio_draft'] and 'derived_from' not in row['canvas_audio_draft']
    no_jobs(e)


def test_cold_file_reopen_then_fresh_preview_native_job_review_and_exact_card_history(effect_template, tmp_path):
    e = effect_template
    if e.backend != 'file': pytest.skip('cold process acceptance is specifically File; PG requires separate host acceptance')
    e.command['parameters'] = deepcopy(LOCAL)
    value = inputs(e); row = save(e, value); exact_saved(row, value); no_jobs(e)
    request = tmp_path / 'cold-reopen.json'; response = tmp_path / 'cold-result.json'; log = tmp_path / 'cold-process.log'
    request.write_text(json.dumps({'root': str(e.root), 'nid': e.nid, 'scope': e.scope, 'actor': e.actor,
        'row_id': row['id'], 'expected_row': row, 'source': e.source, 'expected_input': value,
        'parent_pid': os.getpid(), 'response': str(response)}), encoding='utf-8')
    env = dict(os.environ, PYTHONPATH=os.pathsep.join([str(Path.cwd()), str(Path.cwd() / 'tests')]),
               EXPERIMENTAL_FEATURES='narrative_production_v2,asset_lineage_v2')
    with log.open('wb') as output:
        result = subprocess.run([sys.executable, '-B', str(Path(__file__).resolve()), '--cold-audio-draft', str(request)],
            cwd=Path.cwd(), env=env, stdout=output, stderr=subprocess.STDOUT, timeout=60)
    assert result.returncode == 0, log.read_text(encoding='utf-8', errors='replace')
    evidence = json.loads(response.read_text(encoding='utf-8'))
    assert evidence['pid'] != os.getpid() and evidence['real_cpu_ffmpeg'] and not evidence['model_inference']
    assert evidence['draft_read'] == row and evidence['queued']['command']['template_ref'] == value['template_ref']
    assert evidence['cpu']['frames'] == RATE and evidence['cpu']['maximum_absolute_lsb_error'] <= 1.1
    assert evidence['approved']['status'] == 'APPROVED'
    assert evidence['returned']['version'] == 2 and evidence['restored']['version'] == 3
    capture = os.environ.get('STUDIO_AUDIO_SAVED_DRAFT_CAPTURE_DIR')
    if capture:
        target = Path(capture); target.mkdir(parents=True, exist_ok=True)
        (target / 'native-cold-audio-draft.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding='utf-8')
        (target / 'cold-process.log').write_bytes(log.read_bytes())


def test_original_cas_history_preserves_metadata_and_conflicts_never_overwrite(effect_template, monkeypatch):
    e = effect_template; value = inputs(e); no_native(monkeypatch)
    first = save(e, value); newer = deepcopy(value); newer['parameters']['gain_db'] = -3
    second = save(e, newer, first)
    assert second['id'] == first['id'] and second['version'] == first['version'] + 1
    exact_saved(second, newer)
    raw = e.store.read(e.nid, e.scope)['collections'][TIMELINES][first['id']]
    assert raw['history'][0]['canvas_audio_draft'] == first['canvas_audio_draft']
    before = deepcopy(e.store.read(e.nid, e.scope))
    with pytest.raises(REJECTED): save(e, value, first)
    assert e.store.read(e.nid, e.scope) == before and read(e, second) == second
    no_jobs(e)



def test_generic_timeline_edit_keeps_saved_input_historical_until_explicit_audio_cas_save(effect_template,monkeypatch):
    e=effect_template;value=inputs(e);first=save(e,value);no_native(monkeypatch)
    changed_timeline=deepcopy(first['timeline']);changed_timeline['tracks'][0]['clips'][0]['gain_db']=-2
    generic=e.production.timeline_save(e.nid,e.scope,e.actor,first['id'],{
        'title':first['title'],'timeline':changed_timeline,'expected_version':first['version']},lambda:None)
    assert generic['version']==first['version']+1
    assert generic['canvas_audio_draft']==first['canvas_audio_draft']
    assert generic['canvas_audio_draft']['timeline_snapshot']['version']!=generic['version']
    assert generic['canvas_audio_draft']['timeline_snapshot']['digest']!=generic['timeline_digest']
    assert read(e,generic)==generic
    # Only an explicit audio-draft CAS save captures a new current input binding.
    captured=save(e,value,generic);exact_saved(captured,value)
    assert captured['version']==generic['version']+1
    no_jobs(e)

def test_concurrent_cas_only_one_audio_draft_writer_wins(effect_template, monkeypatch):
    e = effect_template; value = inputs(e); first = save(e, value); no_native(monkeypatch)
    gate = Barrier(2)
    def update(gain):
        changed = deepcopy(value); changed['parameters']['gain_db'] = gain; gate.wait(timeout=10)
        try: return save(e, changed, first)
        except REJECTED: return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(update, [-3, -4]))
    assert sum(result is not None for result in results) == 1
    current = read(e, first); assert current['version'] == 2
    assert current['canvas_audio_draft']['parameters']['gain_db'] in {-3, -4}
    no_jobs(e)


@pytest.mark.parametrize('mutation', ['null', 'proof', 'preview', 'confirmation', 'extra', 'source-marker'])
def test_draft_never_accepts_reusable_authority_or_extra_fields(envelope_canvas, monkeypatch, mutation):
    e = envelope_canvas; value = inputs(e); request = body(value)
    if mutation == 'null': request['canvas_audio_draft'] = None
    elif mutation == 'source-marker': request['canvas_audio_draft']['source_snapshots'][0]['reference_only'] = True
    elif mutation == 'extra': request['canvas_audio_draft']['automatic_execute'] = True
    else: request['canvas_audio_draft'][mutation if mutation != 'preview' else 'reviewed_preview_digest'] = 'a' * 64
    no_native(monkeypatch); before = deepcopy(e.store.read(e.nid, e.scope))
    with pytest.raises(REJECTED): e.production.timeline_save(e.nid, e.scope, e.actor, None, request, lambda: None)
    assert e.store.read(e.nid, e.scope) == before; no_jobs(e)


@pytest.mark.parametrize('bad', [{'sample_rate':48000},{'channels':2},{'output_format':'FLAC'}, {'gain_db':True},
    {'gain_db':None},{'fade_in_ms':0.5},{'fade_out_ms':1001},{'fade_in_ms':501,'fade_out_ms':500}])
def test_draft_parameters_are_closed_and_invalid_values_are_never_silently_dropped(envelope_canvas, monkeypatch, bad):
    e = envelope_canvas; value = inputs(e); request = body(value)
    request['canvas_audio_draft']['parameters'].update(bad)
    no_native(monkeypatch); before = deepcopy(e.store.read(e.nid, e.scope))
    with pytest.raises(REJECTED): e.production.timeline_save(e.nid, e.scope, e.actor, None, request, lambda: None)
    assert e.store.read(e.nid, e.scope) == before; no_jobs(e)


def test_metadata_must_compile_to_exact_saved_audio_timeline(envelope_canvas, monkeypatch):
    e = envelope_canvas; value = inputs(e); request = body(value)
    request['canvas_audio_draft']['parameters']['out_ms'] -= 100
    no_native(monkeypatch); before = deepcopy(e.store.read(e.nid, e.scope))
    with pytest.raises(REJECTED): e.production.timeline_save(e.nid, e.scope, e.actor, None, request, lambda: None)
    assert e.store.read(e.nid, e.scope) == before; no_jobs(e)


@pytest.mark.parametrize('field', ['request_id', 'source_snapshots', 'canvas_return', 'template_ref'])
def test_cas_update_cannot_rebind_saved_draft_identity_or_template(effect_template, monkeypatch, field):
    e = effect_template; value = inputs(e); row = save(e, value); changed = deepcopy(value)
    if field == 'request_id': changed[field] += '-other'
    elif field == 'source_snapshots': changed[field][0]['version'] += 1
    elif field == 'canvas_return': changed[field]['card_id'] = 'other-audio'
    else: changed[field]['parameters']['gain_db'] += 1
    no_native(monkeypatch); before = deepcopy(e.store.read(e.nid, e.scope))
    with pytest.raises(REJECTED): save(e, changed, row)
    assert e.store.read(e.nid, e.scope) == before and read(e, row) == row; no_jobs(e)


@pytest.mark.parametrize('change', ['source-pin', 'source-deleted', 'version', 'deleted-card', 'template-version'])
def test_reopen_rechecks_current_source_target_and_template(effect_template, monkeypatch, change):
    e = effect_template; row = save(e, inputs(e))
    if change == 'template-version': save_template(e, gain_db=-3)
    else: change_origin(e, change)
    no_native(monkeypatch)
    with pytest.raises(REJECTED): read(e, row)
    no_jobs(e)


@pytest.mark.parametrize('change', ['actor','project','incarnation'])
def test_saved_input_read_and_write_do_not_cross_owner_scope_or_incarnation(effect_template, monkeypatch, change):
    e = effect_template; value = inputs(e); row = save(e, value)
    nid, scope, actor = e.nid, deepcopy(e.scope), e.actor
    if change == 'actor': actor = 'other-author'
    elif change == 'project':
        nid = e.create_project('Other audio draft owner'); scope = {'mode':'local','novel_id':nid};e.service.activate(nid,scope,actor)
    else:
        e.novels.delete(nid);e.create_project('Recreated audio project',nid);e.service.activate(nid,scope,actor)
    no_native(monkeypatch)
    with pytest.raises(REJECTED): e.production.timeline_get(nid,scope,actor,row['id'],lambda:None)
    with pytest.raises(REJECTED): e.production.timeline_save(nid,scope,actor,row['id'],body(value,row['version']),lambda:None)


def test_any_already_admitted_request_cannot_be_resumed_or_overwritten(effect_template, monkeypatch):
    e = effect_template; value = inputs(e); row = save(e, value); queued = queue(e, command(value))
    no_native(monkeypatch)
    with pytest.raises(REJECTED): read(e, row)
    with pytest.raises(REJECTED): save(e, value, row)
    assert get(e, queued) == queued and len(rows(e)) == 1


def test_saved_failed_derivation_rechecks_parent_and_preserves_original_record(failed_audio, monkeypatch):
    e = failed_audio; original = deepcopy(e.failed)
    derived = derived_command(e,request='saved-failed-audio-draft')
    value = inputs(e,request=derived['request_id'],command=derived)
    no_native(monkeypatch); row = save(e,value); exact_saved(row,value)
    assert read(e,row) == row and get(e,e.failed) == original and len(rows(e)) == 1
    audio=e.production._audio(e.scope,e.actor)
    def unknown(state):
        parent=audio.service.find(state,e.failed['id']);parent['status']='UNKNOWN';parent['dispatch_state']='OUTCOME_UNKNOWN';parent['version']+=1;audio._receipt(parent)
    audio.store.mutate(e.nid,unknown)
    with pytest.raises(REJECTED):read(e,row)
    with pytest.raises(REJECTED):save(e,value,row)
    current=get(e,e.failed);assert current['status']=='UNKNOWN' and current['automatic_replay'] is False
    # A completely fresh request with the UNKNOWN row's *current* version and
    # receipt must also fail, isolating status from old-version rejection.
    unknown_command=derived_command(e,current,request='current-unknown-cannot-derive')
    fresh=inputs(e,request=unknown_command['request_id'],command=unknown_command)
    with pytest.raises(REJECTED):save(e,fresh)
    assert get(e,current)==current and len(rows(e))==1


def test_final_denied_guard_rolls_back_saved_inputs_without_creating_job(effect_template, monkeypatch):
    e=effect_template;value=inputs(e);before=deepcopy(e.store.read(e.nid,e.scope));no_native(monkeypatch)
    def denied():
        document=e.store.read(e.nid,e.scope)
        if len(document['collections'].get(TIMELINES,{})) > len(before['collections'].get(TIMELINES,{})):
            raise PermissionError('synthetic final audio draft authority retirement')
    with pytest.raises(PermissionError):save(e,value,guard=denied)
    assert e.store.read(e.nid,e.scope)==before;no_jobs(e)


def test_corrupt_saved_metadata_digest_is_never_adopted(effect_template, monkeypatch):
    e=effect_template;row=save(e,inputs(e));no_native(monkeypatch)
    with e.store.transaction(e.nid,e.scope) as document:
        document['collections'][TIMELINES][row['id']]['canvas_audio_draft_digest']='f'*64
    with pytest.raises(REJECTED):read(e,row)
    no_jobs(e)



def test_mounted_original_timeline_save_get_refuses_saved_proof_and_cas_conflict_without_job(audio_client, monkeypatch):
    e=audio_client
    monkeypatch.setenv('EXPERIMENTAL_FEATURES','narrative_production_v2,asset_lineage_v2,ai_execution_v2,model_broker_v2,author_context_inspector_v2')
    from app.creative.canvas_views import CreativeCanvasViews
    from app.creative.graph_asset_inputs import GraphAssetInputs
    graphs=e.experimental.creative_graph_service
    # Match original audio-only Timeline mounted fixture: this adapter captures
    # workspace/store at construction and must use the disposable original owner.
    monkeypatch.setattr(e.production,'timeline_inputs',GraphAssetInputs(e.production))
    monkeypatch.setattr(graphs,'store',e.studio.store);monkeypatch.setattr(graphs,'workspace',e.studio)
    monkeypatch.setattr(graphs,'asset_inputs',GraphAssetInputs(graphs));monkeypatch.setattr(graphs,'canvas_views',CreativeCanvasViews(graphs));graphs.configure_media(e.production)
    canvas=checked(e.client.post(e.studio_base+'/canvas-views',headers=e.headers,json={
        'request_id':'api-audio-draft-card','definition':{'title':'Owned unqueued audio card','cards':[
            {'id':'origin-audio','position':{'x':44,'y':66},'asset':reference(e.source)}]}}),201)
    source={k:v for k,v in e.command['source_snapshots'][0].items() if k!='reference_only'}
    value={'contract':'studio-canvas-audio-draft/1','request_id':'api-saved-unqueued-audio',
        'parameters':{'in_ms':100,'out_ms':800,'gain_db':-3.5,'fade_in_ms':50,'fade_out_ms':100},
        'source_snapshots':[source],'license_note':'Owned synthetic audio input',
        'canvas_return':{'contract':'studio-canvas-return/1','project_id':e.nid,'scope':e.scope,
            'incarnation':e.studio.store.incarnation(e.nid),'canvas_id':canvas['id'],'canvas_version':canvas['version'],
            'canvas_digest':canvas['definition_digest'],'card_id':'origin-audio','source':source}}
    no_native(monkeypatch)
    response=e.client.post(e.base+'/timelines',headers=e.headers,json=body(value))
    row=checked(response,201);exact_saved(row,value)
    assert response.headers['cache-control']=='no-store'
    assert checked(e.client.get(e.base+'/timelines/'+row['id'],headers=e.headers))==row
    assert checked(e.client.get(e.base+'/jobs',headers=e.headers))['items']==[]
    bad=body(value,row['version']);bad['canvas_audio_draft']['proof']={'confirmed':True}
    rejected=e.client.put(e.base+'/timelines/'+row['id'],headers=e.headers,json=bad)
    assert rejected.status_code==422,rejected.text
    changed=deepcopy(value);changed['parameters']['gain_db']=-2
    saved=checked(e.client.put(e.base+'/timelines/'+row['id'],headers=e.headers,json=body(changed,row['version'])))
    assert saved['version']==row['version']+1;exact_saved(saved,changed)
    conflict=e.client.put(e.base+'/timelines/'+row['id'],headers=e.headers,json=body(value,row['version']))
    assert conflict.status_code in {409,422},conflict.text
    assert checked(e.client.get(e.base+'/timelines/'+row['id'],headers=e.headers))==saved
    assert checked(e.client.get(e.base+'/jobs',headers=e.headers))['items']==[]

def _cold_file(request_path):
    payload=json.loads(Path(request_path).read_text(encoding='utf-8'))
    from app.config import Settings
    from app.repositories.factory import create_repository_bundle
    from app.services import NovelService, ChapterService
    root=Path(payload['root'])
    bundle=create_repository_bundle(Settings(storage_backend='file',database_url='',novel_data=root,enable_cloud=False,mock_provider=True),data_root=root)
    e=SimpleNamespace(root=root,backend='file',url='',nid=payload['nid'],scope=payload['scope'],actor=payload['actor'],
        novels=NovelService(bundle.novels,bundle.chapters),chapters=ChapterService(bundle.chapters),source=payload['source'])
    e.service=services(root,'file','',e.novels,e.chapters);e.store=e.service.store;e.assets=e.service.assets
    e.production=production(e);e.graph=owner(e);e.graph.configure_media(e.production)
    value=payload['expected_input'];row=e.production.timeline_get(e.nid,e.scope,e.actor,payload['row_id'],lambda:None)
    assert os.getpid()!=payload['parent_pid'] and row==payload['expected_row'];exact_saved(row,value);no_jobs(e)
    e.canvas=e.graph.canvas_views.get(e.nid,e.scope,e.actor,value['canvas_return']['canvas_id'])
    original_canvas=deepcopy(e.canvas);candidate_command=command(value)
    captured=preview(e,candidate_command)
    assert captured['automatic_dispatch'] is False and captured['provider'] is None
    assert captured['execution_recipe']['parameters']==value['parameters']
    with pytest.raises(REJECTED):e.production.create(e.nid,e.scope,e.actor,{'command':candidate_command,'reviewed_preview_digest':'f'*64},lambda:None)
    no_jobs(e)
    queued=queue(e,candidate_command);assert queued['status']=='QUEUED' and queued['output_candidate'] is None
    assert e.graph.canvas_views.get(e.nid,e.scope,e.actor,e.canvas['id'])==original_canvas
    result=run(e,queued);assert result['status']=='AWAITING_REVIEW',result
    meta,data=e.production.candidate(e.nid,e.scope,e.actor,'audio',result['id'],lambda:None)
    with wave.open(io.BytesIO(data),'rb') as stream:
        assert(stream.getframerate(),stream.getnchannels(),stream.getsampwidth(),stream.getnframes())==(RATE,2,2,RATE)
        pcm=stream.readframes(stream.getnframes())
    samples=struct.unpack('<'+'h'*(len(pcm)//2),pcm)
    assert samples[0::2]==samples[1::2]
    p=value['parameters'];plateau=AMPLITUDE*10**(p['gain_db']/20)
    maximum=max(abs(sample-plateau*min(1,(index*1000/RATE)/p['fade_in_ms'])*min(1,(1000-index*1000/RATE)/p['fade_out_ms'])) for index,sample in enumerate(samples[0::2]))
    assert maximum<=1.1
    sha=hashlib.sha256(data).hexdigest();assert sha==meta['sha256']==result['output_candidate']['digest']==result['media_measurement']['output_sha256']
    with pytest.raises(FileNotFoundError):e.service.asset(e.nid,e.scope,result['output_candidate']['id'])
    approved=review(e,result);assert approved['status']=='APPROVED'
    formal=e.service.asset(e.nid,e.scope,approved['output_candidate']['id'])
    returned=e.graph.canvas_views.save(e.nid,e.scope,e.actor,e.canvas['id'],return_body(e,formal))
    assert returned['version']==2 and returned['definition']['cards'][0]['asset']==reference(formal)
    assert returned['definition']['cards'][0]['position']==original_canvas['definition']['cards'][0]['position']
    assert returned['definition']['cards'][1:]==original_canvas['definition']['cards'][1:]
    history=e.graph.canvas_views.history(e.nid,e.scope,e.actor,e.canvas['id'])
    restored=e.graph.canvas_views.restore(e.nid,e.scope,e.actor,e.canvas['id'],{'expected_version':returned['version'],
        'expected_definition_digest':returned['definition_digest'],'expected_incarnation':history['incarnation'],
        'restore_version':original_canvas['version'],'restore_definition_digest':original_canvas['definition_digest']})
    assert restored['version']==3 and restored['definition']==original_canvas['definition']
    evidence={'contract':'synthetic-cold-saved-audio-draft/1','real_cpu_ffmpeg':True,'model_inference':False,
        'pid':os.getpid(),'parent_pid':payload['parent_pid'],'draft_read':row,'command':candidate_command,'preview':captured,
        'queued':queued,'executed':result,'approved':approved,'returned':returned,'history':history,'restored':restored,
        'cpu':{'frames':len(samples)//2,'sample_rate':RATE,'channels':2,'maximum_absolute_lsb_error':maximum,
            'output_sha256':sha,'pcm_sha256':hashlib.sha256(pcm).hexdigest()},
        'candidate_wav_base64':base64.b64encode(data).decode('ascii')}
    Path(payload['response']).write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__' and len(sys.argv)==3 and sys.argv[1]=='--cold-audio-draft':
    _cold_file(sys.argv[2])
