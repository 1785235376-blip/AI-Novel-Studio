"""Local Audience slice. Same suite supports File and externally provisioned actual PG."""
from copy import deepcopy
import json

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from test_r4_style_judge import env as judge_env
from test_r3_planning import planning_env
from app.experimental.audience_review import AudienceReview
from app.experimental.narrative_judge import NarrativeJudgeService
from app.experimental.narrative_judge_api import create_narrative_judge_router
from app.experimental.store import ExperimentalStore
from app.experimental.common import StaleSourceError
from app.services.v1_capability_service import CapabilityVersionConflict
from app.source_privacy import content_digest, review_source_privacy


@pytest.fixture
def env(judge_env):
    e = judge_env
    if e.backend == 'file':
        (e.root / 'novels' / e.nid).mkdir(parents=True)
        yield e
    else:
        # Actual PG owner UUID, not a mock incarnation or a file-only substitute.
        from app.config import Settings
        from app.repositories.factory import create_repository_bundle
        from app.services import NovelService
        bundle = create_repository_bundle(Settings(storage_backend='postgres', database_url=e.url, novel_data=e.root), data_root=e.root)
        owner = NovelService(bundle.novels, bundle.chapters)
        owner.create({'id': e.nid, 'title': 'Audience synthetic owner'})
        e.real_owner = owner
        try: yield e
        finally:
            owner.delete(e.nid)
            bundle.novels.database.engine.dispose()


def body(e, observations=True):
    cid=e.order[0]
    e.chapters[cid]['content']='甲🙂 乙。\nSecond paragraph.'
    proof={'chapter_id':cid,'chapter_version':1,'paragraph':1,'start':0,'end':5,'quote':'甲🙂 乙。'}
    source = AudienceReview(e.judge).prepare_source(e.nid,e.scope,cid,1)
    return {'chapter_id':cid,'expected_version':1,'expected_source_digest':source['source_digest'],
        'profiles':[{'name':'New reader','genre_experience':'NOVICE','target_age_group':'GENERAL','language_habit':'Chinese prose','reading_speed':120},
                    {'name':'Longtime reader','genre_experience':'EXPERIENCED','target_age_group':'ADULTS','language_habit':'Bilingual prose','reading_speed':240}],
        'comparison':'DIFFERENT_ADVICE' if observations else 'NOT_ASSESSED',
        'observations':[{'profile_index':i,'evidence':proof,'observation':f'Author observation {i}', 'suggestion':f'Author advice {i}'} for i in (0,1)] if observations else []}


def create(e, data=None, guard=lambda:None):
    return AudienceReview(e.judge).create(e.nid,e.scope,'author',data or body(e),guard)


def test_exact_profiles_arithmetic_original_review_owner_restart_and_no_models(env):
    e=env;data=body(e);before=deepcopy(e.chapters)
    e.judge.adapters={'bad':object()}
    row=create(e,data)
    assert not row['model_called'] and row['verification']=='AUTHOR_ENTERED_AND_LOCAL_ARITHMETIC'
    assert row['audience']['chapter_version']==1
    expected=sum(not c.isspace() for c in e.chapters[e.order[0]]['content'])
    assert row['audience']['measurements'][0]['estimated_seconds']==expected/2
    assert row['audience']['measurements'][1]['estimated_seconds']==expected/4
    assert all(f['origin']=='AUTHOR_ENTERED' for f in row['findings'])
    assert row['findings'][0]['evidence'][0]['end']==5  # Unicode, not UTF-16
    assert len(e.creation._rows('review_threads'))==2
    assert not e.judge.runs(e.nid,e.scope) and not e.judge.list_review_items(e.nid,e.scope)
    first=row['findings'][0]
    reviewed=e.judge.review(e.nid,e.scope,'author',first['id'],{'expected_version':1,'action':'accept','reason':'Author chooses this advice'})
    assert reviewed['decision']=='ACCEPTED' and reviewed['review_history'][-1]['reason']=='Author chooses this advice'
    assert e.chapters==before
    restarted=NarrativeJudgeService(ExperimentalStore(e.root,e.backend,e.url),e.novels,e.chapter_service,e.creation,e.world)
    history=AudienceReview(restarted).comparisons(e.nid,e.scope)
    assert history[0]['findings'][0]['decision']=='ACCEPTED'
    assert create(e,data)['id']==row['id'] and len(e.creation._rows('review_threads'))==2


@pytest.mark.parametrize('change',['version','text','privacy','hidden','secret','archive','delete'])
def test_changed_or_unavailable_sources_redact_all_profile_text_and_block_review(env,change):
    e=env;row=create(e);cid=e.order[0]
    if change=='version':e.chapters[cid]['version']+=1
    elif change=='text':e.chapters[cid]['content']='changed without version'
    elif change=='privacy':
        c=e.chapters[cid];review_source_privacy(c,None,'author','CLOUD_ALLOWED',c['version'],content_digest(c),e.root)
    elif change=='hidden':e.chapters[cid]['hidden']=True
    elif change=='secret':e.chapters[cid]['secret']=True
    elif change=='archive':e.chapters[cid]['archived_at']='now'
    else:del e.chapters[cid];e.order.remove(cid)
    result=AudienceReview(e.judge).comparisons(e.nid,e.scope)[0]
    assert result['stale'] and not result['findings'] and 'audience' not in result
    assert 'Author observation' not in json.dumps(result)
    with pytest.raises(StaleSourceError):
        e.judge.review(e.nid,e.scope,'author',row['findings'][0]['id'],{'expected_version':1,'action':'accept','reason':'No stale review'})


@pytest.mark.parametrize('change',['quote','paragraph','version','foreign','blank','speed','extra','missing_other','same_profiles'])
def test_invalid_input_cannot_write(env,change):
    e=env;data=body(e)
    if change=='quote':data['observations'][0]['evidence']['quote']='fake'
    elif change=='paragraph':data['observations'][0]['evidence']['paragraph']=2
    elif change=='version':data['expected_version']=2
    elif change=='foreign':data['observations'][0]['evidence']['chapter_id']=e.order[1]
    elif change=='blank':data['profiles'][0]['language_habit']='   '
    elif change=='speed':data['profiles'][0]['reading_speed']=True
    elif change=='extra':data['profiles'][0]['real_child_name']='Do not collect'
    elif change=='missing_other':data['observations']=data['observations'][:1]
    else:data['profiles'][1]=deepcopy(data['profiles'][0])
    with pytest.raises((ValueError,StaleSourceError)):create(e,data)
    assert not e.creation._rows('review_threads')
    assert not e.store.read(e.nid,e.scope)['collections'].get(e.judge.RUNS)


def test_profile_and_source_versions_do_not_share_decision_or_receipt(env):
    e=env;data=body(e);first=create(e,data)
    e.judge.review(e.nid,e.scope,'author',first['findings'][0]['id'],{'expected_version':1,'action':'intentional','reason':'For this profile only'})
    current=AudienceReview(e.judge).comparisons(e.nid,e.scope)[0]
    assert current['findings'][1]['decision']=='PENDING'
    data['profiles'][0]['reading_speed']=121
    second=create(e,data)
    assert second['id']!=first['id'] and second['findings'][0]['decision']=='PENDING'
    e.chapters[e.order[0]]['version']=2;data['expected_version']=2
    for observation in data['observations']:observation['evidence']['chapter_version']=2
    data['expected_source_digest']=AudienceReview(e.judge).source(e.nid,e.scope,e.order[0],2)['source_digest']
    third=create(e,data)
    assert third['id']!=second['id'] and third['findings'][0]['decision']=='PENDING'
    assert len(AudienceReview(e.judge).comparisons(e.nid,e.scope))==3


def test_write_failure_retry_deduplicates_and_revocation_rolls_back(env,monkeypatch):
    e=env;data=body(e)
    def denied():raise RuntimeError('revoked')
    with pytest.raises(RuntimeError,match='revoked'):create(e,data,denied)
    assert not e.creation._rows('review_threads')
    write=e.creation.store._write
    def fail(*args):raise OSError('disk unavailable')
    monkeypatch.setattr(e.creation.store,'_write',fail)
    with pytest.raises(OSError):create(e,data)
    assert not e.store.read(e.nid,e.scope)['collections'].get(e.judge.RUNS)
    monkeypatch.setattr(e.creation.store,'_write',write)
    row=create(e,data);create(e,data)
    assert len(e.creation._rows('review_threads'))==2
    f=row['findings'][0]
    e.judge.review(e.nid,e.scope,'author',f['id'],{'expected_version':1,'action':'ignore','reason':'Rejected by author'})
    with pytest.raises(CapabilityVersionConflict):e.judge.review(e.nid,e.scope,'author',f['id'],{'expected_version':1,'action':'accept','reason':'stale'})


def test_source_bounds_and_readonly_estimates(env):
    e=env;data=body(e,False);row=create(e,data)
    assert not row['findings'] and row['audience']['comparison']=='NOT_ASSESSED'
    source=AudienceReview(e.judge).source(e.nid,e.scope,e.order[0],1)
    assert source['paragraphs'][0]=={'paragraph':1,'start':0,'end':5,'quote':'甲🙂 乙。'}
    e.chapters[e.order[0]]['content']='x'*2001
    source=AudienceReview(e.judge).source(e.nid,e.scope,e.order[0],1)
    assert source['paragraphs']==[] and source['unsupported_paragraphs']==1


def test_mounted_gates_no_store_no_model_and_original_review_endpoint(env):
    e=env;data=body(e);permissions={'enabled':True,'review':True,'write':True}
    def flag(_):
        if not permissions['enabled']:raise HTTPException(404,'disabled')
    def authorize(nid,token,branch,permission):
        if token!='author' or nid!=e.nid or branch or not permissions['write'] or permission=='domain.review' and not permissions['review']:raise HTTPException(403,'denied')
        return 'author',e.scope
    app=FastAPI();app.include_router(create_narrative_judge_router(e.judge,authorize,flag))
    client=TestClient(app);base=f'/novels/{e.nid}/experimental/narrative-judge';headers={'x-session-token':'author'}
    response=client.post(base+'/audience/comparisons',headers=headers,json=data)
    assert response.status_code==201 and response.headers['cache-control']=='no-store',response.text
    row=response.json();rid=row['id'];fid=row['findings'][0]['id']
    assert client.get(base+'/audience/comparisons',headers=headers).json()['items'][0]['id']==rid
    assert client.get(base+'/audience/catalog',headers=headers).status_code==200
    assert client.get(base+f'/audience/source/{e.order[0]}?expected_version=1',headers=headers).status_code==200
    for suffix,body_ in [('preview',{'expected_version':1,'route_id':'any'}),('dispatch',{'expected_version':1,'reviewed_preview_digest':'a'*64}),('refresh',{'expected_version':1}),('cancel',{'expected_version':1})]:
        response=client.post(base+f'/runs/{rid}/model/{suffix}',headers=headers,json=body_)
        assert response.status_code==409 and response.json()['detail']['code']=='AUDIENCE_AUTHOR_COMPARISON_NO_MODEL'
    review={'expected_version':1,'action':'accept','reason':'Human choice'}
    permissions['review']=False
    assert client.post(base+f'/findings/{fid}/review',headers=headers,json=review).status_code==403
    permissions['review']=True
    assert client.post(base+f'/findings/{fid}/review',headers=headers,json=review).json()['decision']=='ACCEPTED'
    permissions['enabled']=False
    assert client.get(base+'/audience/comparisons',headers=headers).status_code==404


def test_history_capacity_and_blank_reason_preserve_original_decision(env):
    e=env;row=create(e);f=row['findings'][0]
    with pytest.raises(ValueError):
        e.judge.review(e.nid,e.scope,'author',f['id'],{'expected_version':1,'action':'accept','reason':'   '})
    rows=e.creation._rows('review_threads');thread=next(r for r in rows if r['id']==f['id'])
    thread['history']=[{'action':'EXISTING','actor_id':'author','at':'before'}]*100
    e.creation.store._write('review_threads',rows)
    with pytest.raises(ValueError,match='AUDIENCE_HISTORY_LIMIT'):
        e.judge.review(e.nid,e.scope,'author',f['id'],{'expected_version':1,'action':'accept','reason':'cannot discard history'})
    result=AudienceReview(e.judge).comparisons(e.nid,e.scope)[0]['findings'][0]
    assert result['decision']=='PENDING' and len(result['review_history'])==100


def test_commit_time_revocation_and_source_mutation_abort(env):
    e=env;data=body(e);calls=[]
    def revoke_late():
        calls.append(1)
        if len(calls)==2:raise RuntimeError('late authority loss')
    with pytest.raises(RuntimeError):create(e,data,revoke_late)
    assert not e.creation._rows('review_threads')
    assert not e.store.read(e.nid,e.scope)['collections'].get(e.judge.RUNS)
    def change_source():e.chapters[e.order[0]]['version']+=1
    with pytest.raises(StaleSourceError):create(e,data,change_source)
    assert not e.creation._rows('review_threads')


@pytest.mark.parametrize('change', ['unquoted_text', 'privacy'])
def test_preview_digest_rejects_same_version_drift_before_any_write(env, change):
    e=env;data=body(e);cid=e.order[0]
    if change=='unquoted_text':e.chapters[cid]['content'] += '\nUnseen added paragraph.'
    else:
        c=e.chapters[cid];review_source_privacy(c,None,'author','CLOUD_ALLOWED',c['version'],content_digest(c),e.root)
    with pytest.raises(StaleSourceError,match='AUDIENCE_SOURCE_PREVIEW_CHANGED'):create(e,data)
    assert not e.creation._rows('review_threads')


def test_recreated_original_owner_blocks_old_preview_history_and_review(env):
    e=env;data=body(e);row=create(e,data)
    if e.backend=='file':
        import shutil
        shutil.rmtree(e.root/'novels'/e.nid)
        (e.root/'novels'/e.nid).mkdir()
    else:
        e.real_owner.delete(e.nid)
        e.real_owner.create({'id':e.nid,'title':'New synthetic owner'})
    # Source observation never provisions a replacement File marker.
    if e.backend=='file':
        with pytest.raises(FileNotFoundError):AudienceReview(e.judge).source(e.nid,e.scope,e.order[0],1)
        assert not (e.root/'novels'/e.nid/'creative_project_v2.json').exists()
    AudienceReview(e.judge).prepare_source(e.nid,e.scope,e.order[0],1)
    with pytest.raises(StaleSourceError):create(e,data)
    result=AudienceReview(e.judge).comparisons(e.nid,e.scope)[0]
    assert result['stale'] and not result['findings'] and 'audience' not in result
    with pytest.raises(StaleSourceError):
        e.judge.review(e.nid,e.scope,'author',row['findings'][0]['id'],{'expected_version':1,'action':'accept','reason':'old owner'})
    old_threads=deepcopy(e.creation._rows('review_threads'))
    data['expected_source_digest']=AudienceReview(e.judge).source(e.nid,e.scope,e.order[0],1)['source_digest']
    new=create(e,data)
    reviewed=e.judge.review(e.nid,e.scope,'author',new['findings'][0]['id'],{'expected_version':1,'action':'intentional','reason':'Only new owner'})
    e.judge.review(e.nid,e.scope,'author',reviewed['id'],{'expected_version':reviewed['version'],'action':'reopen','reason':'Only new owner reopened'})
    current={thread['id']:thread for thread in e.creation._rows('review_threads')}
    assert all(current[thread['id']]==thread for thread in old_threads)



def test_source_read_does_not_initialize_original_owner(env):
    e=env
    if e.backend!='file':pytest.skip('PG identity is created by original novel owner')
    with pytest.raises(FileNotFoundError):AudienceReview(e.judge).source(e.nid,e.scope,e.order[0],1)
    assert not (e.root/'novels'/e.nid/'creative_project_v2.json').exists()
    result=AudienceReview(e.judge).prepare_source(e.nid,e.scope,e.order[0],1)
    assert len(result['source_digest'])==64
    assert (e.root/'novels'/e.nid/'creative_project_v2.json').is_file()


@pytest.mark.parametrize('field',['hidden','secret','is_archived'])
def test_source_read_rechecks_visibility_after_capture(env,field):
    e=env;body(e)
    def revoke_visibility():e.chapters[e.order[0]][field]=True
    with pytest.raises(StaleSourceError):
        AudienceReview(e.judge).source(e.nid,e.scope,e.order[0],1,revoke_visibility)
