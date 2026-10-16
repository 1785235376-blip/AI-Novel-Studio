"""Reconstructed production-mounted continuation contracts, real File / hosted PG."""
import pytest
from test_r3_mounted_contracts import mounted,prefix,checked,scoped
from test_r4_style_judge_mounted import style_judge

def evidence_run(e):
    c=e.chapters.save(e.chapter['id'],{'version':e.chapter['version'],'content':'An intentional refrain.\n\nAn intentional refrain.'})
    result=checked(e.client.post(e.base+'/narrative-judge/runs',json={'chapter_ids':[c['id']],'expected_versions':{c['id']:c['version']}}),201)
    return c,result,result['findings'][0]
def test_mounted_intentional_and_revision_task_use_single_existing_authorities(style_judge):
    e=style_judge; chapter,run,finding=evidence_run(e); base=e.base+'/narrative-judge/findings/'+finding['id']
    catalog=e.client.get(base+'/revision-task'); assert catalog.headers['cache-control']=='no-store'; assert checked(catalog)['members'][0]['id']=='local-author'
    body={'expected_version':1,'title':'Review refrain','description':'Keep manuscript unchanged pending review.','assignee':'local-author','reviewer':'local-author'}
    task=checked(e.client.post(base+'/revision-task',json=body),201)['task']
    assert checked(e.client.post(base+'/revision-task',json=body),201)['task']['id']==task['id']
    room=checked(e.client.get(e.base+'/writer-room')); assert len(room['items'])==1 and room['items'][0]['id']==task['id'] and room['items'][0]['review_target']['id']==finding['id']
    marked=checked(e.client.post(base+'/review',json={'expected_version':1,'action':'intentional','reason':'Refrain is deliberate.'})); assert marked['decision']=='INTENTIONAL'
    retained=checked(e.client.get(e.base+'/writer-room'))['items']; assert len(retained)==1 and retained[0]['id']==task['id'] and retained[0]['source_state']=='STALE'
    assert checked(e.client.get(e.base+'/review-inbox?domain=narrative_judge'))['items']==[]
    current=e.chapters.save(chapter['id'],{'version':chapter['version'],'content':'Unrelated lead.\n\n'+chapter['content']})
    fresh=checked(e.client.post(e.base+'/narrative-judge/runs',json={'chapter_ids':[current['id']],'expected_versions':{current['id']:current['version']}}),201)
    assert fresh['findings'][0]['decision']=='INTENTIONAL' and fresh['findings'][0]['intentional_reused'] and e.chapters.get(current['id'])['content']==current['content']
def test_mounted_additional_task_flag_v1_and_conflict_redaction(style_judge,monkeypatch):
    e=style_judge; _,_,finding=evidence_run(e); base=e.base+'/narrative-judge/findings/'+finding['id']
    checked(e.client.post(base+'/review',json={'expected_version':1,'action':'accept','reason':'SOURCE_PRIVATE_REASON'}))
    conflict=e.client.post(base+'/review',json={'expected_version':1,'action':'intentional','reason':'old token'})
    assert conflict.status_code==409 and 'SOURCE_PRIVATE_REASON' not in conflict.text and 'An intentional refrain' not in conflict.text
    assert set(conflict.json()['detail']['current'])=={'id','version','status'}
    monkeypatch.setenv('EXPERIMENTAL_FEATURES','narrative_quality_judge_v2,advanced_planning_v2,world_character_engines_v2,unified_review_inbox')
    assert e.client.get(base+'/revision-task').status_code==404
    monkeypatch.setenv('EXPERIMENTAL_FEATURES','narrative_quality_judge_v2,advanced_planning_v2,world_character_engines_v2,unified_review_inbox,writer_room_v2'); monkeypatch.setenv('V1_ACCEPTANCE_MODE','true')
    assert e.client.get(base+'/revision-task').status_code==404
    assert e.client.post(base+'/review',json={'expected_version':2,'action':'intentional','reason':'No'}).status_code==404
def test_mounted_revision_task_rechecks_current_permission_and_does_not_disclose(style_judge,monkeypatch):
    e=scoped(style_judge,monkeypatch); base=e.base+'/narrative-judge/findings/unknown/revision-task'
    assert e.client.get(base,headers=e.viewer_headers).status_code==403
    assert e.client.post(base,headers=e.viewer_headers,json={'expected_version':1,'title':'No','description':'No','assignee':'stranger','reviewer':'stranger'}).status_code==403
    def revoked(*args): e.sessions.revoke(e.lead); return {'private':'REVOKED_TASK_CONTENT'}
    monkeypatch.setattr(e.experimental.narrative_judge_service,'revision_task_catalog',revoked)
    result=e.client.get(base,headers=e.headers); assert result.status_code in {401,403} and 'REVOKED_TASK_CONTENT' not in result.text
