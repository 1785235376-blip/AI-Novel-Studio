"""Additive JSON compatibility; reads never migrate old artifacts."""
import copy
from app.experimental.story_graph import StoryGraphService
from app.experimental.style_analysis import StyleAnalysisService,METHOD
from app.experimental.store import ExperimentalStore
from app.experimental.revision_intelligence import RevisionIntelligenceService
from test_r3_planning import planning_env
from test_r4_story_graph import env as graph_env,relation,learn
from test_r4_style_judge import env as style_env,profile,analysis,duplicate
from test_r4_revision_intelligence import revision_env,proposal


def test_pre_continuation_scene_less_graph_mind_reopen_without_rewrite(graph_env):
    e=graph_env;r=relation(e)
    with e.store.transaction(e.nid,e.scope) as state:
        row=state['collections']['world_records'][r['id']]
        for version in [row,*row['history']]:version['data'].pop('scene_id',None)
        for canon in state['collections'].get('world_canon',{}).values():canon['data'].pop('scene_id',None)
    k=learn(e,e.graph.record(e.nid,e.scope,r['id']))
    with e.store.transaction(e.nid,e.scope) as state:
        row=state['collections']['world_records'][k['id']]
        for version in [row,*row['history']]:version['data'].pop('scene_id',None)
    before=e.store.read(e.nid,e.scope)
    reopened=StoryGraphService(ExperimentalStore(e.root,e.backend,e.url),e.novels,e.chapter_service)
    result=reopened.character_context(e.nid,e.scope,'alice',e.order[3])
    assert result['secrets'][0]['text']==r['data']['statement']
    assert 'scene_id' not in result and 'relationships' not in result
    assert reopened.record(e.nid,e.scope,k['id'])['history']==before['collections']['world_records'][k['id']]['history']
    assert e.store.read(e.nid,e.scope)==before and before['schema_version']==1


def test_existing_revision_proposals_and_history_need_no_comparison_migration(revision_env):
    e=revision_env;old=proposal(e);before=e.store.read(e.nid,e.scope)
    assert e.service.COMPARISONS not in before['collections']
    reopened=RevisionIntelligenceService(ExperimentalStore(e.store.root,e.backend,e.store.database_url),e.novels,e.chapters)
    assert reopened.proposal(e.nid,e.scope,old['id'])=={**old,'stale':False}
    assert reopened.comparisons(e.nid,e.scope)=={'items':[]}
    assert reopened.version_catalog(e.nid,e.scope,e.cid)['current_version']==e.chapter['version']
    assert e.store.read(e.nid,e.scope)==before and before['schema_version']==1


def test_old_style_method_and_opinion_fields_remain_unchanged_and_new_run_is_separate(style_env):
    e=style_env;p=profile(e);old=analysis(e,p)
    with e.store.transaction(e.nid,e.scope) as state:
        row=state['collections'][e.style.ANALYSES][old['id']];row['method_version']='unicode-style-statistics-v1'
        for key in ('sample_metrics','metric_kind','model_opinion_state','unmeasured'):row.pop(key,None)
        assert row['model_assessments']==[]
    before=e.store.read(e.nid,e.scope)
    reopened=StyleAnalysisService(ExperimentalStore(e.root,e.backend,e.url),e.novels,e.chapter_service,e.creation)
    loaded=reopened.analyses(e.nid,e.scope)[0]
    assert loaded['method_version']=='unicode-style-statistics-v1' and 'sample_metrics' not in loaded
    assert e.store.read(e.nid,e.scope)==before
    with e.store.transaction(e.nid,e.scope) as state:
        row=state['collections'][e.style.ANALYSES].pop(old['id']);row['id']='legacy-style-receipt';state['collections'][e.style.ANALYSES][row['id']]=row
    new=analysis(e,p)
    assert new['method_version']==METHOD and new['id']!='legacy-style-receipt'
    assert len(e.style.analyses(e.nid,e.scope))==2


def test_old_judge_thread_gains_key_only_on_explicit_fresh_review(style_env):
    e=style_env;result=duplicate(e);finding=result['findings'][0];rows=e.creation._rows('review_threads')
    legacy=next(row for row in rows if row['id']==finding['id']);legacy['narrative_judge'].pop('issue_key',None)
    e.creation.store._write('review_threads',rows);before=copy.deepcopy(e.creation._rows('review_threads'))
    assert e.judge.run(e.nid,e.scope,result['id'])['findings'][0]['decision']=='PENDING'
    assert e.creation._rows('review_threads')==before
    reviewed=e.judge.review(e.nid,e.scope,'author',finding['id'],{'expected_version':finding['version'],'action':'intentional','reason':'Explicit upgrade of this review'})
    assert reviewed['id']==finding['id'] and reviewed['decision']=='INTENTIONAL'
    persisted=next(row for row in e.creation._rows('review_threads') if row['id']==finding['id'])
    assert persisted['narrative_judge']['issue_key'] and persisted['history'][:-1]==legacy['history']
