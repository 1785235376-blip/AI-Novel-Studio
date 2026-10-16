"""Original registered-local execution, historical evidence and review-only output."""
import copy
import json
from concurrent.futures import ThreadPoolExecutor
import pytest
from app.experimental.revision_intelligence_model import parse_version_opinions,MAX_OUTPUT_BYTES
from app.experimental.ux import ReadContext
from app.services.v1_capability_service import CapabilityVersionConflict
from test_r3_mounted_contracts import mounted,prefix,scoped,checked
from test_r4_broker_mounted import broker_app,route,wait_ledger


def started(e):
    before=e.chapters.get(e.chapter['id'])
    after=e.chapters.save(before['id'],{'version':before['version'],'content':'A new synthetic assertion.\n\nA changed fictional tone.'})
    body={'chapter_id':before['id'],'current_version':after['version'],'before_version':before['version'],'after_version':after['version']}
    base=e.base+'/revisions';preview=checked(e.client.post(base+'/comparisons/preview',headers=e.headers,json=body))
    return checked(e.client.post(base+'/comparisons',headers=e.headers,json={'comparison':body,'preview_digest':preview['preview_digest'],'title':'Registered model historical comparison'}),201)


def action(e,row,name,**extra):
    return checked(e.client.post(e.base+f'/revisions/comparisons/{row["id"]}/model/{name}',headers=e.headers,json={'expected_version':row['version'],**extra}))
def ready(e):return action(e,started(e),'preview',route_id=route(e)['route_id'])
def dispatch(e,row):return action(e,row,'dispatch',reviewed_preview_digest=row['model_preview']['preview_digest'])
def refresh(e,row):
    wait_ledger(e,row['model_execution']['reservation_id']);return action(e,row,'refresh')


def test_real_original_job_compares_exact_history_and_stays_review_only(broker_app,monkeypatch):
    from app.runtime import runtime
    from app.author_request import request_payload
    e=broker_app;captured=[];provider=runtime.provider_registry.resolve('mock');original=provider.stream_text
    def stream(request):captured.append(request_payload(request));yield from original(request)
    monkeypatch.setattr(provider,'stream_text',stream)
    catalog=checked(e.client.get(e.base+'/revisions/comparisons-model/catalog',headers=e.headers))
    assert catalog['rubric']['id']=='original-version-semantic-comparison-v1'
    row=ready(e);before=e.chapters.get(e.chapter['id']);snapshot=copy.deepcopy(e.chapters.history(e.chapter['id']))
    preview=row['model_preview'];assert preview['execution_available'] and preview['request']['context']=={}
    request=json.loads(preview['author']['instruction'].split('REVISION_COMPARISON_OPINIONS_V1\n',1)[1])
    assert request['versions']['before']['text']==row['before_text'] and request['versions']['after']['text']==row['after_text']
    assert not e.manager.jobs and captured==[]
    running=dispatch(e,row);result=refresh(e,running)
    assert captured==[preview['request']] and len(e.manager.jobs)==1
    assert result['model_execution']['status']=='COMPLETED' and result['model_execution']['accounting']['status']=='SETTLED'
    opinion=result['model_assessments'][0]
    assert opinion['source']=='EXECUTED_MODEL_ASSESSMENT' and opinion['interpretation']=='MODEL_DERIVED'
    assert opinion['provenance_verification']=='ORIGINAL_REGISTERED_LOCAL_JOB'
    assert opinion['quality_verification']=='SYNTHETIC_PROTOCOL_ONLY' and opinion['model']['synthetic']
    assert result['before_text'][opinion['before_start']:opinion['before_start']+len(opinion['before_quote'])]==opinion['before_quote']
    job=e.manager.get(running['model_execution']['job_id']);assert job.experimental_origin=='revision_comparison_model'
    assert e.client.post(e.prefix+f'/generation/{job.id}/accept',headers=e.headers,json={}).status_code in {409,422}
    accepted=checked(e.client.post(e.base+f'/revisions/comparisons/{row["id"]}/model/opinions/{opinion["id"]}/accept',headers=e.headers,json={'expected_version':result['version']}))
    assert accepted['model_assessments'][0]['decision']=='ACCEPTED_INTERPRETATION'
    assert e.chapters.get(e.chapter['id'])==before and e.chapters.history(e.chapter['id'])==snapshot
    assert dispatch(e,row)['model_execution']['job_id']==job.id and len(e.manager.jobs)==1


def test_model_forgeries_rejected_without_touching_imported_or_manual_notes(broker_app,monkeypatch):
    from app.runtime import runtime
    e=broker_app;row=ready(e)
    bad={'opinions':[{'kind':'FACT_ADDED','explanation':'Invalid evidence','before_version':row['comparison']['before_version'],'after_version':row['comparison']['after_version'],'after_quote':'fabricated','after_start':0}]}
    monkeypatch.setattr(runtime.providers['mock'],'stream',lambda *args,**kwargs:iter([json.dumps(bad)]))
    result=refresh(e,dispatch(e,row))
    assert result['model_execution']['status']=='FAILED'
    assert result['model_execution']['failure_code']=='REVISION_MODEL_OUTPUT_INVALID_OR_UNSUPPORTED_EVIDENCE'
    assert not result['model_assessments'] and result['changes']==row['changes']


@pytest.mark.parametrize('text',['```json\n{"opinions":[]}\n```','{"opinions":[],"score":90}','{"opinions":[],"opinions":[]}','{"opinions":NaN}','[]'])
def test_semantic_parser_never_accepts_markdown_extra_keys_duplicate_or_nonfinite(text):
    with pytest.raises(ValueError):parse_version_opinions(text,{},{})


def test_semantic_parser_versions_offsets_and_output_bounds():
    capture={'versions':{'before':{'version':1},'after':{'version':2}}};texts={'before':'Old','after':'New'}
    item={'kind':'PLOT_INTENT_CHANGED','explanation':'Test','before_version':1,'after_version':2,'before_quote':'Old','after_quote':'New'}
    assert parse_version_opinions(json.dumps({'opinions':[item]}),texts,capture)[0]['after_version']==2
    for update in ({'after_version':3},{'after_start':1},{'kind':'LITERARY_SCORE'},{'before_version':'1'}):
        with pytest.raises(ValueError):parse_version_opinions(json.dumps({'opinions':[{**item,**update}]}),texts,capture)
    with pytest.raises(ValueError):parse_version_opinions('x'*(MAX_OUTPUT_BYTES+1),texts,capture)


def test_uncertain_dispatch_and_restart_never_repeat_original_job(broker_app,monkeypatch):
    e=broker_app;row=ready(e)
    monkeypatch.setattr(e.manager,'start_prepared',lambda job:(_ for _ in ()).throw(ValueError('uncertain admission')))
    response=e.client.post(e.base+f'/revisions/comparisons/{row["id"]}/model/dispatch',headers=e.headers,json={'expected_version':row['version'],'reviewed_preview_digest':row['model_preview']['preview_digest']})
    assert response.status_code==422
    current=dispatch(e,row);assert current['model_execution']['status']=='UNKNOWN' and not e.manager.jobs
    restarted=action(e,current,'refresh')
    assert restarted['model_execution']['receipt_state']=='UNKNOWN_NO_AUTOMATIC_REPLAY'
    assert restarted['model_execution']['accounting']['status']=='RESERVED'
    assert len(e.broker.ledger(e.nid,e.scope,'local-author'))==1


def test_cancel_wins_over_late_model_result_and_stale_originals_still_cancellable(broker_app,monkeypatch):
    e=broker_app;row=ready(e);monkeypatch.setattr(e.manager,'start_prepared',lambda job:None)
    queued=dispatch(e,row);cancelled=action(e,queued,'cancel');assert cancelled['model_execution']['status']=='CANCELLED'
    service=e.experimental.revision_intelligence_service;ctx=ReadContext(e.nid,{'mode':'local','novel_id':e.nid},'local-author','broker-host')
    with pytest.raises(CapabilityVersionConflict):service.record_model_result(ctx,queued,{**queued['model_execution'],'status':'COMPLETED'},[],lambda:None)
    result=action(e,cancelled,'refresh')
    assert result['model_execution']['status']=='CANCELLED' and not result.get('model_assessments')


def test_parallel_dispatch_is_one_original_job_and_one_reservation(broker_app):
    e=broker_app;row=ready(e)
    def send(_):return e.client.post(e.base+f'/revisions/comparisons/{row["id"]}/model/dispatch',headers=e.headers,json={'expected_version':row['version'],'reviewed_preview_digest':row['model_preview']['preview_digest']})
    with ThreadPoolExecutor(max_workers=2) as pool:responses=list(pool.map(send,range(2)))
    assert all(r.status_code in {200,409} for r in responses) and any(r.status_code==200 for r in responses)
    assert len(e.manager.jobs)==len(e.broker.ledger(e.nid,e.scope,'local-author'))==1


def test_source_change_flags_and_host_requirements_fence_preview_and_final_send(broker_app,monkeypatch):
    from app.runtime import runtime
    import time
    e=broker_app;row=ready(e);calls=[];before=e.broker.guard_dispatch
    assert e.client.get(e.base+'/revisions/comparisons-model/catalog').status_code==401
    def revoke(*args,**kwargs):
        result=before(*args,**kwargs);monkeypatch.setenv('V1_ACCEPTANCE_MODE','true');return result
    monkeypatch.setattr(e.broker,'guard_dispatch',revoke)
    monkeypatch.setattr(runtime.providers['mock'],'stream',lambda *args,**kwargs:(calls.append('unexpected') or iter(['bad'])))
    response=e.client.post(e.base+f'/revisions/comparisons/{row["id"]}/model/dispatch',headers=e.headers,json={'expected_version':row['version'],'reviewed_preview_digest':row['model_preview']['preview_digest']})
    assert response.status_code in {200,404}
    deadline=time.monotonic()+5
    while any(j.status not in e.manager.terminal for j in e.manager.jobs.values()) and time.monotonic()<deadline:time.sleep(.01)
    assert not calls
    monkeypatch.setenv('V1_ACCEPTANCE_MODE','false');monkeypatch.setenv('EXPERIMENTAL_FEATURES','revision_intelligence_v2')
    safe=checked(e.client.get(e.base+f'/revisions/comparisons/{row["id"]}',headers=e.headers))
    assert safe['model_unavailable'] and not safe.get('model_preview') and not safe.get('model_assessments')


def test_actual_membership_revocation_and_cross_branch_cannot_read_model_sources(broker_app,monkeypatch):
    row=started(broker_app);e=scoped(broker_app,monkeypatch)
    assert e.client.get(e.base+'/revisions/comparisons-model/catalog',headers=e.viewer_headers).status_code==403
    assert e.client.post(e.base+f'/revisions/comparisons/{row["id"]}/model/preview',headers=e.headers,json={'expected_version':1,'route_id':'any'}).status_code==404
    e.authorization.revoke_role(e.role,e.lead)
    assert e.client.get(e.base+'/revisions/comparisons-model/catalog',headers=e.headers).status_code==403


def test_current_source_changes_require_new_author_preview_for_same_historical_pair(broker_app):
    e=broker_app;row=ready(e);current=e.chapters.get(e.chapter['id'])
    e.chapters.save(current['id'],{'version':current['version'],'content':'Unrelated third original revision.'})
    result=e.client.post(e.base+f'/revisions/comparisons/{row["id"]}/model/dispatch',headers=e.headers,json={'expected_version':row['version'],'reviewed_preview_digest':row['model_preview']['preview_digest']})
    assert result.status_code in {409,422} and not e.manager.jobs
    newer=action(e,row,'preview',route_id=route(e)['route_id'])
    assert newer['model_preview']['author']['chapter_version']==current['version']+1 and newer['capture']==row['capture']
    assert refresh(e,dispatch(e,newer))['model_execution']['status']=='COMPLETED'


def test_deleted_original_evidence_redacts_model_preview_and_still_allows_cancel(broker_app,monkeypatch):
    e=broker_app;row=ready(e);monkeypatch.setattr(e.manager,'start_prepared',lambda job:None);queued=dispatch(e,row)
    original=e.chapters.history
    monkeypatch.setattr(e.chapters,'history',lambda cid:[item for item in original(cid) if item['version']!=row['comparison']['before_version']])
    stale=checked(e.client.get(e.base+f'/revisions/comparisons/{row["id"]}',headers=e.headers))
    assert stale['stale'] and stale['model_preview'] is None and stale['model_assessments']==[]
    assert 'before_text' not in stale and 'capture' not in stale
    cancelled=action(e,stale,'cancel');assert cancelled['model_execution']['status']=='CANCELLED' and cancelled['stale']


def test_model_input_limit_and_archive_of_active_job_are_honest(broker_app,monkeypatch):
    e=broker_app;row=ready(e);monkeypatch.setattr(e.manager,'start_prepared',lambda job:None);queued=dispatch(e,row)
    result=e.client.post(e.base+f'/revisions/comparisons/{row["id"]}/review',headers=e.headers,json={'expected_version':queued['version'],'action':'archive'})
    assert result.status_code==422
    assert action(e,queued,'cancel')['model_execution']['status']=='CANCELLED'
    current=e.chapters.get(e.chapter['id']);e.chapters.save(current['id'],{'version':current['version'],'content':'long original evidence. '*1000});row=started(e)
    result=e.client.post(e.base+f'/revisions/comparisons/{row["id"]}/model/preview',headers=e.headers,json={'expected_version':row['version'],'route_id':route(e)['route_id']})
    assert result.status_code==422 and 'INPUT_LIMIT' in result.text


def test_model_unicode_evidence_preserves_whitespace_instead_of_silently_normalizing():
    text=' 甲🙂e\u0301。 '
    item={'kind':'EMOTIONAL_TONE_CHANGED','explanation':'Unverified interpretation','before_version':1,'after_version':2,'before_quote':text,'before_start':0,'after_quote':text,'after_start':0}
    parsed=parse_version_opinions(json.dumps({'opinions':[item]}),{'before':text,'after':text},{'versions':{'before':{'version':1},'after':{'version':2}}})
    assert parsed[0]['before_quote']==text
