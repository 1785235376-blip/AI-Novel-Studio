"""Original version A/B comparison is evidence-bound review metadata."""
import copy
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from app.experimental.common import StaleSourceError
from app.experimental.revision_intelligence import RevisionIntelligenceService
from app.experimental.revision_intelligence_api import create_revision_intelligence_router
from app.experimental.store import ExperimentalStore
from app.services.v1_capability_service import CapabilityVersionConflict
from test_r4_revision_intelligence import revision_env, paragraph, document


def pair(e):
    before=e.chapters.get(e.cid)
    after=e.chapters.save(e.cid, {'version':before['version'],'document':document(paragraph('新的事实。'),paragraph('人物已经信任对方。'))})
    return {'chapter_id':e.cid,'current_version':after['version'],'before_version':before['version'],'after_version':after['version']}


def save(e,value=None,changes=None):
    value=value or pair(e);preview=e.service.compare_versions(e.nid,e.scope,value)
    row=e.service.save_comparison(e.nid,e.scope,'author',{'comparison':value,'preview_digest':preview['preview_digest'],'title':'Synthetic version comparison','changes':changes or []})
    return row,preview


def test_compare_reuses_original_history_persists_only_pins_and_restarts(revision_env):
    e=revision_env;value=pair(e);before=copy.deepcopy(e.chapters.get(e.cid));history=e.chapters.history(e.cid)
    catalog=e.service.version_catalog(e.nid,e.scope,e.cid)
    assert {value['before_version'],value['after_version']}.issubset({r['version'] for r in catalog['items']})
    row,preview=save(e,value)
    assert preview['before_text'].startswith('甲🙂') and preview['after_text'].startswith('新的事实')
    assert preview['model_called'] is False and preview['semantic_execution']=='NOT_REQUESTED'
    raw=e.service.get(e.nid,e.scope,e.service.COMPARISONS,row['id'])
    assert not {'document','before_text','after_text','diff'} & set(raw)
    restarted=RevisionIntelligenceService(ExperimentalStore(e.store.root,e.backend,e.store.database_url),e.novels,e.chapters)
    assert restarted.comparison(e.nid,e.scope,row['id'])==row
    assert e.chapters.get(e.cid)==before and e.chapters.history(e.cid)==history


@pytest.mark.parametrize('kind',['FACT_ADDED','FACT_REMOVED','CHARACTER_STATE_CHANGED','RELATIONSHIP_CHANGED','CANON_CHANGED','EMOTIONAL_TONE_CHANGED','PLOT_INTENT_CHANGED'])
def test_seven_semantic_categories_have_exact_evidence_and_honest_model_label(revision_env,kind):
    e=revision_env;value=pair(e)
    change={'kind':kind,'explanation':'Synthetic interpretation, not a probability','before_quote':'甲🙂e\u0301。' if kind!='FACT_ADDED' else '', 'after_quote':'新的事实。' if kind!='FACT_REMOVED' else '', 'source':'IMPORTED_MODEL_ASSESSMENT','model_identity':'declared-fixture-model'}
    row,_=save(e,value,[change]);opinion=row['changes'][0]
    assert opinion['interpretation']=='MODEL_DERIVED' and opinion['provenance_verification']=='DECLARED_NOT_VERIFIED'
    assert opinion['evidence_verification']=='EXACT_QUOTE_ONLY_NOT_SEMANTIC_TRUTH'
    assert not row['model_called'] and not row['manuscript_modified']


@pytest.mark.parametrize('bad',[{'after_start':1},{'after_quote':'forged'},{'before_quote':'unexpected'},{'model_identity':None}])
def test_bad_offsets_quotes_or_missing_model_identity_cannot_persist(revision_env,bad):
    e=revision_env;value=pair(e)
    change={'kind':'FACT_ADDED','explanation':'Synthetic','after_quote':'新的事实。','source':'IMPORTED_MODEL_ASSESSMENT','model_identity':'fixture',**bad}
    with pytest.raises(ValueError):save(e,value,[change])
    assert not e.service.comparisons(e.nid,e.scope)['items']


def test_compare_edit_review_conflict_history_and_archive_are_metadata_only(revision_env):
    e=revision_env;row,_=save(e);chapter=e.chapters.get(e.cid)
    changed=e.service.edit_comparison(e.nid,e.scope,'author',row['id'],{'expected_version':1,'title':'Reviewed title','changes':[]})
    assert changed['version']==2 and changed['history'][0]['title']==row['title']
    with pytest.raises(CapabilityVersionConflict):e.service.edit_comparison(e.nid,e.scope,'author',row['id'],{'expected_version':1,'title':'late','changes':[]})
    for action,status in [('acknowledge','ACKNOWLEDGED'),('archive','ARCHIVED'),('reopen','REVIEW')]:
        changed=e.service.review_comparison(e.nid,e.scope,'reviewer',row['id'],{'expected_version':changed['version'],'action':action});assert changed['status']==status
    assert len(changed['history'])==4 and e.chapters.get(e.cid)==chapter


def test_historical_pair_survives_new_current_version_but_not_removed_history(revision_env,monkeypatch):
    e=revision_env;row,_=save(e);current=e.chapters.get(e.cid)
    e.chapters.save(e.cid,{'version':current['version'],'document':document(paragraph('Later current version'))})
    assert not e.service.comparison(e.nid,e.scope,row['id'])['stale']
    history=e.chapters.history
    monkeypatch.setattr(e.chapters,'history',lambda cid:[r for r in history(cid) if r['version']!=row['comparison']['before_version']])
    stale=e.service.comparison(e.nid,e.scope,row['id'])
    assert stale['stale'] and not stale['changes'] and not stale['history']
    assert 'before_text' not in stale and 'title' not in stale


def test_source_privacy_change_redacts_comparison_and_prevents_old_adoption(revision_env):
    from app.source_privacy import review_source_privacy,content_digest
    e=revision_env;row,_=save(e);current=e.chapters.get(e.cid)
    review_source_privacy(current,None,'author','CLOUD_ALLOWED',current['version'],content_digest(current),e.store.root)
    assert e.service.comparison(e.nid,e.scope,row['id'])['stale']
    with pytest.raises(StaleSourceError):e.service.review_comparison(e.nid,e.scope,'author',row['id'],{'expected_version':1,'action':'acknowledge'})


def test_save_preview_fences_current_version_digest_and_scope(revision_env):
    e=revision_env;value=pair(e);preview=e.service.compare_versions(e.nid,e.scope,value)
    with pytest.raises(StaleSourceError):e.service.save_comparison(e.nid,e.scope,'author',{'comparison':value,'preview_digest':'0'*64,'title':'Forged'})
    e.chapters.save(e.cid,{'version':value['current_version'],'document':document(paragraph('New current'))})
    with pytest.raises(StaleSourceError):e.service.save_comparison(e.nid,e.scope,'author',{'comparison':value,'preview_digest':preview['preview_digest'],'title':'Late'})
    with pytest.raises(ValueError,match='branch-isolated'):e.service.compare_versions(e.nid,{**e.scope,'branch_id':'other'},{**value,'current_version':value['current_version']+1})
    with pytest.raises(FileNotFoundError):e.service.compare_versions('foreign',{'mode':'local','novel_id':'foreign'},value)


def test_comparison_routes_flags_authority_and_revoke_before_commit(revision_env,monkeypatch):
    e=revision_env;value=pair(e);controls={'enabled':True,'revoked':False}
    def flag(_):
        if not controls['enabled']:raise HTTPException(404)
    def auth(nid,token,branch,permission):
        if controls['revoked'] or token!='author':raise HTTPException(403)
        return 'author',e.scope
    app=FastAPI();app.include_router(create_revision_intelligence_router(e.service,auth,flag))
    client=TestClient(app);base=f'/novels/{e.nid}/experimental/revisions';headers={'X-Session-Token':'author'}
    assert client.get(base+'/original-versions',params={'chapter_id':e.cid}).status_code==403
    controls['enabled']=False;assert client.post(base+'/comparisons/preview',headers=headers,json=value).status_code==404
    controls['enabled']=True;preview=client.post(base+'/comparisons/preview',headers=headers,json=value)
    assert preview.status_code==200 and preview.headers['cache-control']=='no-store'
    captured=e.store.read(e.nid,e.scope);original=e.service._semantic_changes
    def revoke(*args):
        result=original(*args);controls['revoked']=True;return result
    monkeypatch.setattr(e.service,'_semantic_changes',revoke)
    result=client.post(base+'/comparisons',headers=headers,json={'comparison':value,'preview_digest':preview.json()['preview_digest'],'title':'Denied'})
    assert result.status_code==403 and e.store.read(e.nid,e.scope)==captured


def test_malformed_history_and_unsupported_document_never_fake_comparison(revision_env,monkeypatch):
    e=revision_env;value=pair(e);original=e.chapters.history
    monkeypatch.setattr(e.chapters,'history',lambda cid:original(cid)+[original(cid)[0]])
    with pytest.raises(ValueError,match='ambiguous'):e.service.compare_versions(e.nid,e.scope,value)
