"""Reconstructed independent samples / intentional review / original Writer Room contracts."""
from copy import deepcopy
from types import SimpleNamespace
import json
import pytest
from fastapi import HTTPException
from app.experimental.common import StaleSourceError
from app.experimental.inbox import ReviewBinding, UnifiedReviewInbox
from app.experimental.narrative_judge import NarrativeJudgeService
from app.experimental.store import ExperimentalStore
from app.experimental.style_analysis import StyleAnalysisService, METHOD
from app.experimental.ux import ReadContext
from app.experimental.writer_room import WriterRoomService
from app.services.v1_capability_service import CapabilityVersionConflict
from test_r3_planning import planning_env
from test_r4_style_judge import env, profile, analysis, run, duplicate

def decide(e,finding,action,reason='Intentional refrain'):
    return e.judge.review(e.nid,e.scope,'local-author',finding['id'],{'expected_version':finding['version'],'action':action,'reason':reason})
def edit_outside_evidence(e):
    chapter=e.chapters[e.order[0]]; chapter['content']='An unrelated opening.\n\n'+chapter['content']; chapter['version']+=1

def test_samples_have_independent_sentence_boundaries_absolute_unicode_anchors_and_retry_identity(env):
    e=env; first,second=e.order[:2]
    e.chapters[first]['content']='😀 Heading\n\nFirst unfinished sample'; e.chapters[second]['content']='Second unfinished sample'
    p=profile(e,chapter_ids=[first,second]); selected=[{'chapter_id':first,'expected_version':1,'start':11},{'chapter_id':second,'expected_version':1}]
    result=analysis(e,p,samples=selected)
    assert result['method_version']==METHOD and result['metric_kind']=='DETERMINISTIC_METRIC'
    assert result['metrics']['sentence_count']==2 and result['metrics']['characters']==len('First unfinished sampleSecond unfinished sample')
    assert result['sample_metrics'][0]['paragraphs']==[{'paragraph':2,'start':11,'end':34,'quote':'First unfinished sample','partial_paragraph':False}]
    assert result['metrics']['frequent_units'][0]=={'unit':'sample','count':2}
    assert result['model_opinion_state']=='NOT_REQUESTED' and not result['model_assessments']
    assert 'SENSORY_MEANING_RATIO' in result['unmeasured'] and not result['model_called']
    assert analysis(e,p,samples=selected)['id']==result['id']
    restarted=StyleAnalysisService(ExperimentalStore(e.root,e.backend,e.url),e.novels,e.chapter_service,e.creation)
    assert len(restarted.analyses(e.nid,e.scope))==1 and restarted.analyses(e.nid,e.scope)[0]['sample_metrics']==result['sample_metrics']
    edit_outside_evidence(e); redacted=restarted.analyses(e.nid,e.scope)[0]
    assert redacted['stale'] and 'sample_metrics' not in redacted and 'First unfinished' not in json.dumps(redacted)
def test_ranges_cannot_hide_conflicting_versions_and_partial_paragraphs_are_explicit(env):
    e=env; p=profile(e); cid=e.order[0]
    with pytest.raises(StaleSourceError,match='disagree'):
        analysis(e,p,samples=[{'chapter_id':cid,'expected_version':2,'start':0,'end':3},{'chapter_id':cid,'expected_version':1,'start':4,'end':8}])
    assert e.style.analyses(e.nid,e.scope)==[]
    result=analysis(e,p,samples=[{'chapter_id':cid,'expected_version':1,'start':2,'end':8}])
    assert result['sample_metrics'][0]['paragraphs'][0]['partial_paragraph']
    assert result['sample_metrics'][0]['paragraphs'][0]['quote']==e.chapters[cid]['content'][2:8]
def test_intentional_survives_unrelated_edit_restart_and_has_no_repeated_inbox_nudge(env):
    e=env; original=duplicate(e); finding=original['findings'][0]
    reviewed=decide(e,finding,'intentional','PRIVATE_OLD_REASON referencing another chapter')
    assert reviewed['decision']=='INTENTIONAL' and reviewed['status']=='RESOLVED' and e.judge.list_review_items(e.nid,e.scope)==[]
    edit_outside_evidence(e); fresh=run(e,chapter_ids=e.order[:1]); carried=fresh['findings'][0]
    assert fresh['id']!=original['id'] and carried['decision']=='INTENTIONAL'
    assert carried['intentional_reused'] and 'PRIVATE_OLD_REASON' not in json.dumps(fresh)
    assert carried['evidence'][0]['paragraph']==2 and carried['evidence'][0]['chapter_version']==2
    restarted=NarrativeJudgeService(ExperimentalStore(e.root,e.backend,e.url),e.novels,e.chapter_service,e.creation,e.world)
    assert restarted.run(e.nid,e.scope,fresh['id'])['findings'][0]['decision']=='INTENTIONAL'
    assert restarted.list_review_items(e.nid,e.scope)==[] and restarted.run(e.nid,e.scope,original['id'])['stale']
def test_changed_evidence_new_occurrence_and_ignore_do_not_silently_suppress(env):
    e=env; original=duplicate(e); decide(e,original['findings'][0],'intentional'); chapter=e.chapters[e.order[0]]
    chapter['content']+='\n\nThe lantern stood beside the door.'; chapter['version']+=1
    fresh=run(e,chapter_ids=e.order[:1]); assert [item['decision'] for item in fresh['findings']]==['INTENTIONAL','PENDING']
    assert decide(e,fresh['findings'][1],'ignore')['decision']=='IGNORED'
    edit_outside_evidence(e); assert [item['decision'] for item in run(e,chapter_ids=e.order[:1])['findings']]==['INTENTIONAL','PENDING']
    chapter['content']=chapter['content'].replace('door.','window.'); chapter['version']+=1
    assert all(item['decision']=='PENDING' for item in run(e,chapter_ids=e.order[:1])['findings'])
def test_intentional_reopen_propagates_exact_group_cas_and_clean_conflict_payload(env):
    e=env; first=duplicate(e); first_finding=first['findings'][0]; second=run(e,chapter_ids=e.order[:2]); second_finding=second['findings'][0]
    decide(e,first_finding,'intentional'); carried=e.judge.run(e.nid,e.scope,second['id'])['findings'][0]
    assert carried['decision']=='INTENTIONAL' and carried['version']==2
    with pytest.raises(CapabilityVersionConflict) as conflict: decide(e,second_finding,'reopen')
    assert set(conflict.value.current)=={'id','version','status'}
    decide(e,carried,'reopen','Reconsider exact evidence'); reopened=e.judge.run(e.nid,e.scope,first['id'])['findings'][0]
    assert reopened['decision']=='PENDING' and reopened['version']==3
    accepted=decide(e,reopened,'accept'); assert accepted['decision']=='ACCEPTED' and accepted['status']=='RESOLVED'
    assert len(e.judge.list_review_items(e.nid,e.scope))==2
def test_intentional_permissions_staleness_and_branch_isolation(env):
    e=env; finding=duplicate(e)['findings'][0]; before=deepcopy(e.creation._rows('review_threads'))
    def deny(): raise HTTPException(403,'REVOKED')
    with pytest.raises(HTTPException): e.judge.review(e.nid,e.scope,'local-author',finding['id'],{'expected_version':1,'action':'intentional','reason':'No'},reauthorize=deny)
    assert e.creation._rows('review_threads')==before
    with pytest.raises(FileNotFoundError): e.judge.review(e.nid,{**e.scope,'branch_id':'other'},'local-author',finding['id'],{'expected_version':1,'action':'intentional','reason':'No'})
    edit_outside_evidence(e)
    with pytest.raises(StaleSourceError): decide(e,finding,'intentional')
    assert e.creation._rows('review_threads')==before

def room(e):
    inbox=UnifiedReviewInbox(); inbox.register(ReviewBinding('narrative_judge',lambda ctx:e.judge.list_review_items(ctx.novel_id,ctx.scope)))
    e.judge.writer_room=WriterRoomService(e.store,e.novels,e.chapter_service,sources=SimpleNamespace(chapter_reader=None),creation=e.creation,inbox=inbox,assets=None,membership=lambda:None)
    return ReadContext(e.nid,e.scope,'local-author')
def task_body(finding):
    return {'expected_version':finding['version'],'title':'Recheck refrain','description':'Compare exact quoted paragraphs.','assignee':'local-author','reviewer':'local-author'}
def test_revision_task_uses_only_existing_writer_room_authority_and_restart_recovery(env):
    e=env; finding=duplicate(e)['findings'][0]; ctx=room(e); before=deepcopy(e.chapters)
    catalog=e.judge.revision_task_catalog(ctx,finding['id'],lambda:None)
    assert catalog['existing_task'] is None and catalog['members'][0]['id']=='local-author'
    created=e.judge.create_revision_task(ctx,finding['id'],task_body(finding),lambda:None); retry=e.judge.create_revision_task(ctx,finding['id'],task_body(finding),lambda:None)
    assert created['task']['id']==retry['task']['id'] and not created['manuscript_changed']
    assert created['task']['review_target']=={'domain':'narrative_judge','id':finding['id'],'version':1}
    assert len(e.judge.writer_room._rows(ctx))==1 and e.chapters==before
    e.judge.writer_room.store=ExperimentalStore(e.root,e.backend,e.url)
    assert e.judge.revision_task_catalog(ctx,finding['id'],lambda:None)['existing_task']['id']==created['task']['id']
    assert e.creation._rows('review_threads')[0]['version']==1 and not any('judge_revision' in key for key in e.store.read(e.nid,e.scope)['collections'])
def test_revision_task_rejects_bad_member_stale_finding_and_last_write_revocation(env):
    e=env; finding=duplicate(e)['findings'][0]; ctx=room(e)
    with pytest.raises(HTTPException): e.judge.create_revision_task(ctx,finding['id'],{**task_body(finding),'assignee':'stranger'},lambda:None)
    calls=0
    def deny_at_commit():
        nonlocal calls
        calls+=1
        if calls>=3: raise HTTPException(403,'REVOKED')
    with pytest.raises(HTTPException): e.judge.create_revision_task(ctx,finding['id'],task_body(finding),deny_at_commit)
    assert e.judge.writer_room._rows(ctx)==[]
    decide(e,finding,'intentional')
    with pytest.raises(CapabilityVersionConflict): e.judge.create_revision_task(ctx,finding['id'],task_body(finding),lambda:None)
    with pytest.raises(ValueError,match='reopen'): e.judge.create_revision_task(ctx,finding['id'],task_body({**finding,'version':2}),lambda:None)
    assert not e.judge.writer_room._rows(ctx)
def test_original_review_item_resolves_intentional_without_reintroducing_inbox_nudge(env):
    e=env; finding=duplicate(e)['findings'][0]; decide(e,finding,'intentional')
    assert e.judge.list_review_items(e.nid,e.scope)==[] and e.judge.review_item(e.nid,e.scope,finding['id'])['decision']=='INTENTIONAL'
    with pytest.raises(FileNotFoundError): e.judge.review_item(e.nid,{**e.scope,'branch_id':'other'},finding['id'])
    edit_outside_evidence(e); redacted=e.judge.review_item(e.nid,e.scope,finding['id']); assert redacted['stale'] and 'The lantern' not in json.dumps(redacted)
def test_independent_sample_metric_budget_has_no_synthetic_separator_overflow(env):
    e=env; c1,c2=e.order[:2]; e.chapters[c1]['content']='a'*50000; e.chapters[c2]['content']='b'*50000
    result=analysis(e,profile(e,chapter_ids=[c1,c2]),samples=[{'chapter_id':c1,'expected_version':1},{'chapter_id':c2,'expected_version':1}])
    assert result['metrics']['characters']==100000 and result['metrics']['sentence_count']==2
