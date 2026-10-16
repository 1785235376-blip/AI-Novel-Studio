"""Reconstructed registered-local Style contracts; rerun after restoration."""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
import json
from threading import Event
import pytest
from test_r3_mounted_contracts import mounted, prefix, checked, scoped
from test_r4_broker_mounted import broker_app, route, wait_ledger
from app.experimental.style_analysis_model import parse_style_opinions, MAX_OUTPUT_BYTES, MARKER

def analysis(e, *, start=0, end=None):
    c=e.chapters.get(e.chapter['id'])
    profile=checked(e.client.post(e.base+'/style-analysis/profiles',headers=e.headers,json={'title':'Synthetic style','instructions':'Use concrete verbs.','rules':['Preserve deliberate repetitions.'],'chapter_ids':[c['id']]}),201)
    return checked(e.client.post(e.base+'/style-analysis/analyses',headers=e.headers,json={'style_id':profile['id'],'expected_style_version':profile['version'],'language':'en','samples':[{'chapter_id':c['id'],'expected_version':c['version'],'start':start,'end':end}]}),201)
def action(e,row,name,**extra):
    return checked(e.client.post(e.base+f'/style-analysis/analyses/{row["id"]}/model/{name}',headers=e.headers,json={'expected_version':row['version'],**extra}))
def ready(e,**selection):
    return action(e,analysis(e,**selection),'preview',route_id=route(e)['route_id'])
def dispatch(e,row):
    return action(e,row,'dispatch',reviewed_preview_digest=row['model_preview']['preview_digest'])
def finish(e,row):
    wait_ledger(e,row['model_execution']['reservation_id']); return action(e,row,'refresh')

def test_shipped_style_contract_exact_ranges_original_job_review_and_immutable_metrics(broker_app,monkeypatch):
    from app.runtime import runtime
    from app.author_request import request_payload
    e=broker_app; original=deepcopy(e.chapters.get(e.chapter['id'])); calls=[]
    adapter=runtime.provider_registry.resolve('mock'); stream=adapter.stream_text
    def capture(request): calls.append(request_payload(request)); yield from stream(request)
    monkeypatch.setattr(adapter,'stream_text',capture)
    catalog=checked(e.client.get(e.base+'/style-analysis/model/catalog',headers=e.headers))
    assert catalog['rubric']['categories']==['NARRATIVE_DISTANCE','EMOTIONAL_TONE','RHYTHM','HUMOR','IMAGERY']
    row=ready(e,start=12,end=24); preview=row['model_preview']; metrics=deepcopy(row['metrics'])
    profile_before=e.creation.get_record(e.nid,e.scope,row['style_id'])
    assert calls==[] and not e.manager.jobs and preview['request']['context']=={}
    exact=json.loads(preview['author']['instruction'].split(MARKER)[1])
    assert exact['samples'][0]['fragments'][0]['quote']==original['content'][12:24]
    assert original['content'] not in json.dumps(preview) and 'The city gate opened' not in json.dumps(preview)
    assert preview['source_strategy']=='EXACT_SELECTED_STYLE_RANGES' and preview['broker']['chosen']['price']['reserve_microusd']==0
    result=finish(e,dispatch(e,row)); assert calls==[preview['request']]
    assert result['model_execution']['status']=='COMPLETED' and result['model_opinion_state']=='AVAILABLE'
    assert result['model_execution']['accounting']['actual_microusd']==0
    opinion=result['model_assessments'][0]
    assert opinion['origin']=='MODEL_DERIVED' and opinion['quality_verification']=='SYNTHETIC_PROTOCOL_ONLY'
    proof=opinion['evidence'][0]
    assert 12<=proof['start']<proof['end']<=24 and original['content'][proof['start']:proof['end']]==proof['quote']
    job=e.manager.get(result['model_execution']['job_id'])
    assert job.experimental_origin=='style_analysis_model' and len(e.manager.jobs)==1
    assert e.client.post(e.prefix+f'/generation/{job.id}/accept',headers=e.headers,json={}).status_code in {409,422}
    assert dispatch(e,row)['model_execution']['job_id']==job.id and len(e.manager.jobs)==1
    reviewed=checked(e.client.post(e.base+f'/style-analysis/analyses/{row["id"]}/opinions/{opinion["id"]}/review',headers=e.headers,json={'expected_version':result['version'],'action':'ignore','reason':'Synthetic protocol only; keep source and profile.'}))
    assert reviewed['model_assessments'][0]['decision']=='IGNORED' and reviewed['metrics']==metrics
    assert e.chapters.get(e.chapter['id'])==original and e.creation.get_record(e.nid,e.scope,row['style_id'])==profile_before
    again=action(e,reviewed,'refresh'); assert again['version']==reviewed['version'] and len(again['model_assessments'])==1

def test_style_parser_exact_whitespace_unicode_and_range_boundaries():
    source='Hidden.\n  😀 gentle rain.\nHidden again.'; chapters={'c':{'id':'c','version':2,'content':source}}
    start,end=source.index('  😀'),source.index('\nHidden again'); samples=[{'chapter_id':'c','expected_version':2,'start':start,'end':end}]
    opinion={'category':'IMAGERY','interpretation':'A fallible opinion.','boundary':'Only this excerpt.','evidence':[{'chapter_id':'c','chapter_version':2,'paragraph':2,'start':start,'end':end,'quote':source[start:end]}]}
    assert parse_style_opinions(json.dumps({'opinions':[opinion]}),chapters,samples)[0]['evidence'][0]['quote'].startswith('  😀')
    for change in ({'start':0,'end':7,'paragraph':1,'quote':'Hidden.'},{'chapter_version':3},{'quote':'invented'},{'chapter_id':'unselected'}):
        bad=deepcopy(opinion); bad['evidence'][0].update(change)
        with pytest.raises(ValueError): parse_style_opinions(json.dumps({'opinions':[opinion,bad]}),chapters,samples)

def test_style_created_chapter_uses_saved_markdown_coordinates_and_preserves_exact_document(broker_app):
    """Creation adds a heading; both API prefixes and backends use GET anchors."""
    e = broker_app
    selected = '  雨水敲着窗沿，她停下来听了一会儿。'
    content = f'EXCLUDED_PRIVATE_OPENING\n{selected}\nEXCLUDED_PRIVATE_ENDING'
    created = checked(e.client.post(e.prefix + f'/novels/{e.nid}/chapters', headers=e.headers,
        json={'title': '合成😀雨声', 'content': content}), 201)
    chapter = checked(e.client.get(e.prefix + f'/chapters/{created["id"]}', headers=e.headers))
    assert isinstance(chapter['version'], int) and chapter['version'] >= 1
    assert chapter['content'] == '# 合成😀雨声\n\n' + content + '\n\n'
    start = chapter['content'].index(selected)
    end = start + len(selected)
    assert start != content.index(selected) and chapter['content'][start:end] == selected
    profile = checked(e.client.post(e.base + '/style-analysis/profiles', headers=e.headers,
        json={'title': 'Saved source coordinates', 'instructions': '保留具体动作与停顿。',
              'chapter_ids': [chapter['id']]}), 201)
    row = checked(e.client.post(e.base + '/style-analysis/analyses', headers=e.headers,
        json={'style_id': profile['id'], 'expected_style_version': profile['version'], 'language': 'zh',
              'samples': [{'chapter_id': chapter['id'], 'expected_version': chapter['version'],
                           'start': start, 'end': end}]}), 201)
    previewed = action(e, row, 'preview', route_id=route(e)['route_id'])
    preview = previewed['model_preview']
    exact = json.loads(preview['author']['instruction'].split(MARKER)[1])
    assert exact['samples'] == [{'chapter_id': chapter['id'], 'chapter_version': chapter['version'],
        'start': start, 'end': end,
        'fragments': [{'paragraph': 3, 'start': start, 'end': end, 'quote': selected}]}]
    assert preview['request']['context'] == {}
    assert 'EXCLUDED_PRIVATE_OPENING' not in json.dumps(preview)
    assert 'EXCLUDED_PRIVATE_ENDING' not in json.dumps(preview)
    result = finish(e, dispatch(e, previewed))
    assert result['model_execution']['status'] == 'COMPLETED'
    assert result['model_assessments'][0]['evidence'][0]['quote'] == selected
    assert result['metrics'] == row['metrics']
    assert checked(e.client.get(e.prefix + f'/chapters/{chapter["id"]}', headers=e.headers)) == chapter
@pytest.mark.parametrize('text',['[]','{"opinions":[],"score":99}','{"opinions":[],"opinions":[]}','{"opinions":NaN}','```json\n{"opinions":[]}\n```','{"opinions":"none"}'])
def test_style_strict_output_rejects_scores_duplicates_fences_and_coercion(text):
    with pytest.raises(ValueError): parse_style_opinions(text,{},[])
    assert parse_style_opinions('{"opinions":[]}',{},[])==[]
def test_style_output_bound():
    with pytest.raises(ValueError,match='LIMIT'): parse_style_opinions('x'*(MAX_OUTPUT_BYTES+1),{},[])
def test_style_invalid_model_output_preserves_deterministic_metrics(broker_app,monkeypatch):
    from app.runtime import runtime
    e=broker_app; row=ready(e); metrics=deepcopy(row['metrics'])
    monkeypatch.setattr(runtime.providers['mock'],'stream',lambda *a,**k:iter(['{"opinions":[],"score":0.98}']))
    result=finish(e,dispatch(e,row))
    assert result['model_execution']['status']=='FAILED' and result['model_execution']['failure_code']=='STYLE_OPINION_OUTPUT_INVALID_OR_UNSUPPORTED_EVIDENCE'
    assert result['model_assessments']==[] and result['metrics']==metrics
@pytest.mark.parametrize('change',['text','profile','privacy'])
def test_style_source_profile_and_privacy_drift_redact_and_prevent_dispatch(broker_app,change):
    from app.source_privacy import content_digest,review_source_privacy
    e=broker_app; row=ready(e); path=e.base+f'/style-analysis/analyses/{row["id"]}'
    if change=='text': e.chapters.save(e.chapter['id'],{'version':e.chapter['version'],'content':'New current source.'})
    elif change=='profile': e.experimental.style_analysis_service.save_profile(e.nid,e.scope,'local-author',{'title':'Changed','instructions':'Different instruction.','chapter_ids':[e.chapter['id']],'expected_version':row['style_version']},row['style_id'])
    else:
        c=e.chapters.get(e.chapter['id']); review_source_privacy(c,None,'local-author','CLOUD_ALLOWED',c['version'],content_digest(c),e.store.root)
    stale=checked(e.client.get(path,headers=e.headers))
    assert stale['stale'] and stale['model_preview'] is None and stale['model_assessments']==[]
    assert e.chapter['content'] not in json.dumps(stale) and 'metrics' not in stale
    result=e.client.post(path+'/model/dispatch',headers=e.headers,json={'expected_version':row['version'],'reviewed_preview_digest':row['model_preview']['preview_digest']})
    assert result.status_code==409 and not e.manager.jobs

def test_style_authority_flag_and_v1_revocation_stop_before_final_send(broker_app,monkeypatch):
    from app.runtime import runtime
    e=broker_app; row=ready(e); calls=[]; original=e.broker.guard_dispatch
    def revoke(*args,**kwargs):
        value=original(*args,**kwargs); monkeypatch.setenv('V1_ACCEPTANCE_MODE','true'); return value
    monkeypatch.setattr(e.broker,'guard_dispatch',revoke)
    monkeypatch.setattr(runtime.providers['mock'],'stream',lambda *a,**k:(calls.append(True) or iter(['bad'])))
    result=e.client.post(e.base+f'/style-analysis/analyses/{row["id"]}/model/dispatch',headers=e.headers,json={'expected_version':row['version'],'reviewed_preview_digest':row['model_preview']['preview_digest']})
    assert result.status_code in {200,404}
    for job in list(e.manager.jobs.values()):
        import time
        until=time.monotonic()+5
        while job.status not in e.manager.terminal and time.monotonic()<until: time.sleep(.01)
    assert not calls and e.client.get(e.base+'/style-analysis/model/catalog',headers=e.headers).status_code==404

def test_style_parallel_sends_only_one_job_and_admission_unknown_never_replays(broker_app,monkeypatch):
    e=broker_app; row=ready(e)
    monkeypatch.setattr(e.manager,'start_prepared',lambda job:(_ for _ in ()).throw(ValueError('Uncertain admission')))
    def send(_): return e.client.post(e.base+f'/style-analysis/analyses/{row["id"]}/model/dispatch',headers=e.headers,json={'expected_version':row['version'],'reviewed_preview_digest':row['model_preview']['preview_digest']})
    with ThreadPoolExecutor(max_workers=2) as pool: results=list(pool.map(send,range(2)))
    assert all(r.status_code in {200,409,422} for r in results)
    current=checked(e.client.get(e.base+f'/style-analysis/analyses/{row["id"]}',headers=e.headers))
    assert current['model_execution']['status']=='UNKNOWN' and dispatch(e,row)['model_execution']['job_id']==current['model_execution']['job_id']
    assert len(e.broker.ledger(e.nid,e.scope,'local-author'))==1 and not e.manager.jobs

def test_style_cancellation_fences_late_output_even_after_source_change(broker_app,monkeypatch):
    from app.runtime import runtime
    e=broker_app; begun,release=Event(),Event()
    def stream(*args,**kwargs): begun.set(); assert release.wait(5); yield '{"opinions":[]}'
    monkeypatch.setattr(runtime.providers['mock'],'stream',stream); row=dispatch(e,ready(e))
    try:
        assert begun.wait(5); e.chapters.save(e.chapter['id'],{'version':e.chapter['version'],'content':'Changed source during request.'})
        cancelled=action(e,row,'cancel'); assert cancelled['stale'] and cancelled['model_execution']['status']=='CANCELLED'
    finally: release.set()
    wait_ledger(e,row['model_execution']['reservation_id'])
    assert e.manager.get(row['model_execution']['job_id']).output=='' and cancelled['model_assessments']==[]

def test_style_restart_uses_original_job_without_admitting_untrusted_persisted_output(broker_app,monkeypatch):
    from uuid import uuid4
    from unittest.mock import Mock
    from app.jobs import Job, JobManager
    e=broker_app
    def persisted():
        rows=e.manager.persistence.load_all()
        assert len(rows)==len({item['id'] for item in rows})
        return deepcopy({item['id']:item for item in rows})
    # PG load_all is database-wide; File uses this fixture's directory. Keep
    # every pre-existing record and deliberately exercise unrelated hydration
    # on both backends, without calling an unconfigured provider.
    prior=persisted()
    unrelated=Job(str(uuid4()),'continue',e.nid,e.chapter['id'],'Unrelated terminal fixture','LOCAL_ONLY',
        requested_provider='deepseek',requested_model='deepseek-chat',status='FAILED',
        error_code='TEXT_PROVIDER_NOT_CONFIGURED',error='Synthetic persisted failure fixture')
    e.manager.persistence.save(unrelated.public())
    unrelated_saved=deepcopy(e.manager.persistence.get(unrelated.id))
    preview=ready(e); row=dispatch(e,preview); wait_ledger(e,row['model_execution']['reservation_id'])
    jid=row['model_execution']['job_id']; original=e.manager.get(jid)
    # Settlement commits its ledger before publishing the final job receipt.
    # Its original condition protects both writes; capture only that completed
    # publication, rather than racing the final persisted updated_at.
    with original.condition:
        assert original.status=='COMPLETED' and original.terminal_hook_status=='COMPLETED'
        original_public=deepcopy(original.public())
        saved=persisted()
    assert set(saved)==set(prior)|{unrelated.id,jid}
    assert saved=={**prior,unrelated.id:unrelated_saved,jid:saved[jid]}
    ledger=deepcopy(e.broker.ledger(e.nid,e.scope,'local-author'))
    assert len(ledger)==1 and ledger[0]['job_id']==jid
    restarted=JobManager(generations=e.manager.persistence,chapters=e.chapters,contexts=e.manager.contexts,canon=e.canon,snapshot_required=False)
    assert persisted()==saved
    assert restarted.get(jid).public()==original_public
    assert restarted.get(jid).request_authorization is None
    assert restarted.get(unrelated.id).public()==unrelated.public()
    assert {job.id for job in restarted.jobs.values() if job.novel_id==e.nid and job.experimental_origin=='style_analysis_model'}=={jid}
    hydrated={key:deepcopy(job.public()) for key,job in restarted.jobs.items()}
    assert set(hydrated)<=set(saved)
    coordinator=e.experimental.style_analysis_service.model_coordinator
    monkeypatch.setattr(coordinator,'manager',restarted)
    prepare=Mock(side_effect=AssertionError('Restart must not prepare another author job'))
    start=Mock(side_effect=AssertionError('Restart must not dispatch a provider job'))
    monkeypatch.setattr(coordinator.preparer,'prepare_author',prepare)
    monkeypatch.setattr(restarted,'start_prepared',start)
    current=action(e,row,'refresh')
    assert current['model_execution']['status']=='UNKNOWN' and current['model_assessments']==[]
    assert current['model_execution']['receipt_state']=='UNKNOWN_NO_AUTOMATIC_REPLAY'
    assert dispatch(e,preview)['model_execution']['job_id']==jid
    prepare.assert_not_called(); start.assert_not_called()
    assert {key:job.public() for key,job in restarted.jobs.items()}==hydrated
    assert persisted()==saved and e.broker.ledger(e.nid,e.scope,'local-author')==ledger

def test_style_missing_host_flag_and_branch_source_never_fall_back(broker_app,monkeypatch):
    e=broker_app; assert e.client.get(e.base+'/style-analysis/model/catalog').status_code==401
    monkeypatch.setenv('EXPERIMENTAL_FEATURES','style_dna_v2')
    assert e.client.get(e.base+'/style-analysis/catalog',headers=e.headers).status_code==200
    assert e.client.get(e.base+'/style-analysis/model/catalog',headers=e.headers).status_code==404
    e=scoped(e,monkeypatch); assert e.client.get(e.base+'/style-analysis/model/catalog',headers=e.viewer_headers).status_code==403

def test_style_input_bound_does_not_silently_truncate(broker_app):
    e=broker_app; e.chapter=e.chapters.save(e.chapter['id'],{'version':e.chapter['version'],'content':'a'*18001}); row=analysis(e)
    result=e.client.post(e.base+f'/style-analysis/analyses/{row["id"]}/model/preview',headers=e.headers,json={'expected_version':row['version'],'route_id':route(e)['route_id']})
    assert result.status_code==422 and 'INPUT_TOO_LARGE' in result.text and not e.manager.jobs
@pytest.mark.parametrize('change',['budget','registration'])
def test_style_budget_and_registered_route_changes_prevent_admission(broker_app,change):
    from dataclasses import replace
    from app.runtime import runtime
    e=broker_app; row=ready(e); model=next(m for m in runtime.model_registry.descriptors() if m.provider_id=='mock')
    if change=='budget': checked(e.client.put(e.base+'/model-broker/budget',headers=e.headers,json={'expected_version':0,'limit_microusd':0,'max_inflight':1,'require_known_estimate':True}))
    else: runtime.model_registry.register(replace(model,enabled=False),replace=True)
    try:
        result=e.client.post(e.base+f'/style-analysis/analyses/{row["id"]}/model/dispatch',headers=e.headers,json={'expected_version':row['version'],'reviewed_preview_digest':row['model_preview']['preview_digest']})
        assert result.status_code in {409,422} and not e.manager.jobs
    finally:
        if change=='registration': runtime.model_registry.register(model,replace=True)

def test_style_model_opinion_review_conflict_is_private_and_requires_current_source(broker_app):
    e=broker_app; result=finish(e,dispatch(e,ready(e))); opinion=result['model_assessments'][0]
    path=e.base+f'/style-analysis/analyses/{result["id"]}/opinions/{opinion["id"]}/review'
    first=checked(e.client.post(path,headers=e.headers,json={'expected_version':result['version'],'action':'review','reason':'PRIVATE_REASON'}))
    conflict=e.client.post(path,headers=e.headers,json={'expected_version':result['version'],'action':'ignore','reason':'stale'})
    assert conflict.status_code==409 and set(conflict.json()['detail']['current'])=={'id','version','status'}
    assert 'PRIVATE_REASON' not in conflict.text and 'model_preview' not in conflict.text
    e.chapters.save(e.chapter['id'],{'version':e.chapter['version'],'content':'New current source.'})
    assert e.client.post(path,headers=e.headers,json={'expected_version':first['version'],'action':'reopen','reason':'old source'}).status_code==409

def test_style_original_job_discards_oversize_stream_before_admitting_opinions(broker_app,monkeypatch):
    from app.runtime import runtime
    e=broker_app; row=ready(e); monkeypatch.setattr(runtime.providers['mock'],'stream',lambda *a,**k:iter(['x'*(MAX_OUTPUT_BYTES+1)]))
    result=finish(e,dispatch(e,row))
    assert result['model_execution']['status']=='FAILED' and result['model_execution']['failure_code']=='GENERATION_OUTPUT_LIMIT'
    assert result['model_assessments']==[] and e.manager.get(result['model_execution']['job_id']).output==''
def test_style_known_zero_is_stricter_than_an_estimate_of_zero():
    from app.experimental.style_analysis_model import known_zero
    assert known_zero({'reserve_microusd':0,'actual_known_zero':True})
    assert known_zero({'reserve_microusd':0,'input_per_million_microusd':0,'output_per_million_microusd':0})
    assert not known_zero({'reserve_microusd':0})
    assert not known_zero({'reserve_microusd':0,'input_per_million_microusd':1,'output_per_million_microusd':0})
