"""Original-owner Character/Location/Relationship revisions on File and real PG."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json

import pytest
from app.repositories.chapter_repository import VersionConflict
from app.repositories.factory import create_repository_bundle
from app.repositories.story_record_versions import META, PATHS
from app.repositories.structured_cas import record_digest
from app.services.novel_service import NovelService
from test_surface_story_record_versions import env

KINDS = ['characters', 'locations', 'relationships']


def payload(kind, label='Initial'):
    if kind == 'characters':return {'name': label, 'goal': 'Original goal', 'privacy_level': 'LOCAL_ONLY'}
    if kind == 'locations':return {'name': label, 'description': 'Original description', 'privacy_level': 'LOCAL_ONLY'}
    return {'source_character_id': 'a', 'target_character_id': 'b', 'relationship_type': 'FRIEND', 'description': label, 'privacy_level': 'LOCAL_ONLY'}


def seed(e):
    for rid in ['a', 'b']:e.service.upsert_character(e.nid, rid, {'name': rid, 'privacy_level': 'LOCAL_ONLY'})


def old_method(e,kind):
    return getattr(e.service, {'characters':'upsert_character','locations':'upsert_location','relationships':'upsert_relationship'}[kind])


def inject_extension(e,kind,rid,*,sparse=False):
    if e.backend == 'file':
        from app.repository import read_json
        from app.storage import atomic_write
        path=e.root/'novels'/e.nid/PATHS[kind];rows=read_json(path,[])
        row=next(row for row in rows if row['id']==rid)
        row['import_extension']={'nested':['retained',{'value':7}]}
        if sparse:
            for key in ['goal','personality','rules','atmosphere','description','certainty']:row.pop(key,None)
        atomic_write(path,json.dumps(rows,ensure_ascii=False))
    else:
        from app.repositories.postgres.common import novel_or_raise
        with e.bundle.novels.database.session() as session:
            novel=novel_or_raise(session,e.nid)
            model,_=e.bundle.novels._story_model(session,novel,kind,rid)
            column='payload' if kind=='relationships' else 'facts';stored=dict(getattr(model,column) or {})
            stored['import_extension']={'nested':['retained',{'value':7}]}
            if sparse:
                for key in ['goal','personality','rules','atmosphere','description','certainty']:stored.pop(key,None)
            setattr(model,column,stored)


@pytest.mark.parametrize('kind',KINDS)
def test_original_owner_exact_identity_two_writers_restart_restore_and_old_client(env,kind):
    e=env;seed(e);rid='原始 Exact Identity'
    first=e.service.save_story_record(e.nid,kind,rid,payload(kind),None,0)
    assert first['record']['id']==rid and first['version']==1
    assert first['scope']=={'kind':'PROJECT','novel_id':e.nid,'branch_id':None}
    assert first['navigation']=={'module':'Story','kind':kind,'record_id':rid,'novel_id':e.nid}
    public=next(row for row in e.service.data_set(e.nid,kind) if row['id']==rid)
    assert first['record']==public and first['digest']==record_digest(public) and META not in public
    def write(label):
        try:return e.service.save_story_record(e.nid,kind,rid,payload(kind,label),first['digest'],1)
        except VersionConflict:return None
    with ThreadPoolExecutor(2) as pool:results=list(pool.map(write,['Writer A','Writer B']))
    assert sum(row is not None for row in results)==1
    won=next(row for row in results if row)
    assert won['version']==2 and won['history'][0]['record']==first['record']
    with pytest.raises(VersionConflict):e.service.save_story_record(e.nid,kind,rid,{},first['digest'],1,action='RESTORE',restore_version=1)
    restored=e.service.save_story_record(e.nid,kind,rid,{},won['digest'],2,action='RESTORE',restore_version=1)
    assert restored['record']==first['record'] and restored['version']==3
    bundle=create_repository_bundle(e.settings,data_root=e.root)
    try:
        restarted=NovelService(bundle.novels,bundle.chapters)
        assert restarted.story_record(e.nid,kind,rid)==e.service.story_record(e.nid,kind,rid)
        old_method(e,kind)(e.nid,rid,payload(kind,'Legacy after versions'))
        current=restarted.story_record(e.nid,kind,rid)
        assert current['version']==4 and current['action']=='LEGACY_SAVE'
        assert current['history'][-1]['record']==restored['record']
        assert len([row for row in restarted.data_set(e.nid,kind) if row['id']==rid])==1
        with pytest.raises(VersionConflict):restarted.save_story_record(e.nid,kind,rid,payload(kind,'Stale'),restored['digest'],3)
    finally:
        if e.backend=='postgres':bundle.novels.database.engine.dispose()


@pytest.mark.parametrize('kind',KINDS)
def test_opaque_extension_sparse_snapshots_feedback_and_restore_are_exact(env,kind):
    e=env;seed(e);old_method(e,kind)(e.nid,'old',payload(kind))
    inject_extension(e,kind,'old',sparse=True)
    original=e.service.story_record(e.nid,kind,'old')
    assert original['version']==0 and original['record']['import_extension']['nested'][1]=={'value':7}
    with pytest.raises(ValueError):e.service.save_story_record(e.nid,kind,'old',{**payload(kind),'import_extension':{}},original['digest'],0)
    with pytest.raises(ValueError):e.service.save_story_record(e.nid,kind,'old',{**payload(kind),META:{}},original['digest'],0)
    feedback=e.service.save_story_record(e.nid,kind,'old',{},original['digest'],0,action='FEEDBACK',feedback={'decision':'INTENTIONAL','note':'Human evidence','evidence':'Synthetic'})
    assert feedback['record']==original['record'] and feedback['digest']==original['digest']
    with pytest.raises(VersionConflict):e.service.save_story_record(e.nid,kind,'old',{},feedback['digest'],1,action='FEEDBACK',feedback={'decision':'DISMISSED'})
    with pytest.raises(VersionConflict):e.service.save_story_record(e.nid,kind,'old',payload(kind,'Wrong version'),original['digest'],0)
    saved=e.service.save_story_record(e.nid,kind,'old',payload(kind,'Changed'),feedback['digest'],1)
    assert saved['record']['import_extension']==original['record']['import_extension'] and saved['feedback_stale']
    restored=e.service.save_story_record(e.nid,kind,'old',{},saved['digest'],2,action='RESTORE',restore_version=0)
    assert restored['record']==original['record'] and restored['digest']==original['digest']
    old_method(e,kind)(e.nid,'old',payload(kind,'Old client retained extensions'))
    assert e.service.story_record(e.nid,kind,'old')['record']['import_extension']==original['record']['import_extension']


@pytest.mark.parametrize('kind',KINDS)
def test_create_race_bounded_history_denial_and_cancel_are_non_destructive(env,kind):
    e=env;seed(e)
    def create(label):
        try:return e.service.save_story_record(e.nid,kind,'new',payload(kind,label),None,0)
        except VersionConflict:return None
    with ThreadPoolExecutor(2) as pool:results=list(pool.map(create,['A','B']))
    assert sum(row is not None for row in results)==1
    current=e.service.story_record(e.nid,kind,'new')
    before=deepcopy(current)
    # Local Cancel has no server write; independent reads retain exact current state.
    assert e.service.story_record(e.nid,kind,'new')==before
    calls=[]
    def deny_at_commit():
        calls.append(1)
        if len(calls)>1:raise PermissionError('revoked at commit')
    with pytest.raises(PermissionError):e.service.save_story_record(e.nid,kind,'new',payload(kind,'Denied'),current['digest'],1,check=deny_at_commit)
    assert e.service.story_record(e.nid,kind,'new')==before
    for i in range(23):current=e.service.save_story_record(e.nid,kind,'new',payload(kind,str(i)),current['digest'],current['version'])
    assert current['version']==24 and len(current['history'])==20 and current['history'][0]['version']==4
    with pytest.raises(FileNotFoundError):e.service.save_story_record(e.nid,kind,'new',{},current['digest'],24,action='RESTORE',restore_version=1)


def test_relationship_source_lineage_stale_refresh_restore_foreign_missing_and_race(env,monkeypatch):
    e=env;seed(e)
    event=e.service.save_story_record(e.nid,'timeline','event',{'title':'Origin'},None,0)
    data={**payload('relationships'),'valid_from_event_id':'event'}
    row=e.service.save_story_record(e.nid,'relationships','relation',data,None,0)
    assert {(x['kind'],x['id']) for x in row['source_versions']}=={('characters','a'),('characters','b'),('timeline','event')}
    e.service.upsert_character(e.nid,'a',{'name':'Changed source'})
    stale=e.service.story_record(e.nid,'relationships','relation')
    assert stale['source_state']=='STALE' and stale['stale_sources']==['a']
    with pytest.raises(VersionConflict):e.service.save_story_record(e.nid,'relationships','relation',data,row['digest'],1)
    with pytest.raises(VersionConflict):e.service.save_story_record(e.nid,'relationships','relation',{},row['digest'],1,action='FEEDBACK',feedback={'decision':'INTENTIONAL'})
    refreshed=e.service.save_story_record(e.nid,'relationships','relation',data,row['digest'],1,refresh_sources=True)
    assert refreshed['source_state']=='CURRENT'
    restored=e.service.save_story_record(e.nid,'relationships','relation',{},refreshed['digest'],2,action='RESTORE',restore_version=1)
    assert restored['source_state']=='STALE' and restored['source_versions']==row['source_versions']
    for field in ['source_character_id','target_character_id','valid_from_event_id','valid_to_event_id']:
        with pytest.raises(FileNotFoundError):e.service.save_story_record(e.nid,'relationships','missing',{**data,field:'missing'},None,0)
    original=e.bundle.novels.compare_and_swap_record
    def race(*args,**kwargs):
        e.service.upsert_character(e.nid,'b',{'name':'Changed during prepare'})
        return original(*args,**kwargs)
    monkeypatch.setattr(e.bundle.novels,'compare_and_swap_record',race)
    with pytest.raises(VersionConflict):e.service.save_story_record(e.nid,'relationships','relation',data,restored['digest'],3,refresh_sources=True)
    assert e.service.story_record(e.nid,'relationships','relation')['version']==3


def test_character_location_lineage_is_exact_and_free_text_is_not_guessed(env):
    e=env
    location=e.service.save_story_record(e.nid,'locations','port',payload('locations'),None,0)
    row=e.service.save_story_record(e.nid,'characters','hero',{**payload('characters'),'current_location':'port'},None,0)
    assert row['source_versions']==[{'kind':'locations','id':'port','digest':location['digest']}]
    e.service.upsert_location(e.nid,'port',{'name':'Changed port'})
    assert e.service.story_record(e.nid,'characters','hero')['source_state']=='STALE'
    free=e.service.save_story_record(e.nid,'characters','free',{**payload('characters'),'current_location':'Somewhere in the mountains'},None,0)
    assert free['source_state']=='UNLINKED'


@pytest.mark.parametrize('kind',KINDS)
def test_digest_only_cas_preserves_extensions_and_private_history_never_enters_context(env,kind):
    e=env;seed(e)
    first=e.service.save_story_record(e.nid,kind,'record',payload(kind),None,0)
    inject_extension(e,kind,'record')
    original=e.service.story_record(e.nid,kind,'record')
    result=e.bundle.novels.compare_and_swap_record(e.nid,kind,'record',payload(kind,'Digest client'),original['digest'])
    assert result['import_extension']==original['record']['import_extension']
    assert META not in result
    assert e.service.story_record(e.nid,kind,'record')['version']==2
    public=next(row for row in e.service.data_set(e.nid,kind) if row['id']=='record')
    assert public==result
    sources=e.bundle.novels.get_context_sources(e.nid)
    assert META not in json.dumps(sources)


def test_original_sparse_legacy_defaults_stay_compatible(env):
    e=env
    location=e.service.upsert_location(e.nid,'legacy-place',{'name':'Place'})
    assert location['status']==('ACTIVE' if e.backend=='file' else '')
    relationship=e.service.upsert_relationship(e.nid,'legacy-pair',{'source_character_id':'a','target_character_id':'b','relationship_type':'FRIEND'})
    if e.backend=='file':
        assert not {'status','description','certainty'}.intersection(relationship)
    else:
        assert relationship['status']=='' and relationship['description']=='' and relationship['certainty']==''


@pytest.mark.parametrize('kind',KINDS)
def test_unknown_import_privacy_stays_fail_closed_until_explicit_policy_change(env,kind):
    e=env;seed(e)
    data={key:value for key,value in payload(kind).items() if key!='privacy_level'}
    first=e.service.save_story_record(e.nid,kind,'unknown',data,None,0)
    assert first['record']['privacy_level']=='LOCAL_ONLY' and first['record']['privacy_status']=='UNKNOWN'
    next_row=e.service.save_story_record(e.nid,kind,'unknown',data,first['digest'],1)
    assert next_row['record']['privacy_status']=='UNKNOWN'
    explicit=e.service.save_story_record(e.nid,kind,'unknown',{**data,'privacy_level':'REDACT_BEFORE_CLOUD'},next_row['digest'],2)
    assert explicit['record']['privacy_level']=='REDACT_BEFORE_CLOUD' and 'privacy_status' not in explicit['record']
    restored=e.service.save_story_record(e.nid,kind,'unknown',{},explicit['digest'],3,action='RESTORE',restore_version=1)
    assert restored['record']==first['record']


def test_actual_foreign_relationship_source_is_not_rebound_to_another_project(env):
    e=env;seed(e)
    other=e.service.create({'id':e.nid+'-other','title':'Foreign source owner'})
    try:
        e.service.upsert_character(other['id'],'foreign-only',{'name':'Foreign'})
        with pytest.raises(FileNotFoundError):e.service.save_story_record(e.nid,'relationships','foreign',{**payload('relationships'),'source_character_id':'foreign-only'},None,0)
        assert not e.service.data_set(e.nid,'relationships')
    finally:e.service.delete(other['id'])


@pytest.mark.parametrize('kind',KINDS)
def test_versioned_partial_save_preserves_other_original_fields(env,kind):
    e=env;seed(e)
    first=e.service.save_story_record(e.nid,kind,'partial',payload(kind),None,0)
    field='description' if kind=='relationships' else 'name'
    second=e.service.save_story_record(e.nid,kind,'partial',{field:'Only edited field'},first['digest'],1)
    assert second['record']=={**first['record'],field:'Only edited field'}
    if kind=='relationships':assert second['source_versions']==first['source_versions']


def test_character_nullable_age_can_be_cleared_without_resetting_other_fields(env):
    e=env
    first=e.service.save_story_record(e.nid,'characters','age',{**payload('characters'),'age':31},None,0)
    second=e.service.save_story_record(e.nid,'characters','age',{'name':'New name'},first['digest'],1)
    assert second['record']['age']==31
    cleared=e.service.save_story_record(e.nid,'characters','age',{'name':'New name','age':None},second['digest'],2)
    assert cleared['record']['age'] is None and cleared['record']['goal']=='Original goal'
