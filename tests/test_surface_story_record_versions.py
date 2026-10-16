"""Original Timeline/Foreshadowing owner, including real PostgreSQL opt-in."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import os
from types import SimpleNamespace
from uuid import uuid4

import pytest
from app.config import Settings
from app.repositories.factory import create_repository_bundle
from app.repositories.chapter_repository import VersionConflict
from app.repositories.structured_cas import record_digest
from app.repositories.story_record_versions import META
from app.services.novel_service import NovelService


@pytest.fixture(params=[pytest.param('file',marks=pytest.mark.file_backend_only),pytest.param('postgres',marks=pytest.mark.postgres_backend_only)])
def env(tmp_path,request):
    backend=request.param;url=os.getenv('TEST_POSTGRES_DATABASE_URL','') if backend=='postgres' else ''
    if backend=='postgres' and not url:pytest.fail('real PostgreSQL story records require TEST_POSTGRES_DATABASE_URL')
    settings=Settings(storage_backend=backend,database_url=url,novel_data=tmp_path)
    bundle=create_repository_bundle(settings,data_root=tmp_path)
    service=NovelService(bundle.novels,bundle.chapters);nid='story-version-'+uuid4().hex
    service.create({'id':nid,'title':'Story fixture'})
    chapter=bundle.chapters.create(nid,{'title':'Source','content':'Before'});chapter=bundle.chapters.get(chapter['id'])
    yield SimpleNamespace(service=service,bundle=bundle,nid=nid,chapter=chapter,settings=settings,root=tmp_path,backend=backend)
    if backend=='postgres':service.delete(nid);bundle.novels.database.engine.dispose()


def create(e,kind='timeline',rid='event'):
    payload={'title':'First','privacy_level':'LOCAL_ONLY'}
    if kind=='timeline':payload.update(chapter_id=e.chapter['id'],location='unresolved-old-slug',status='PLANNED')
    else:payload.update(planted_chapter=e.chapter['number'],status='OPEN')
    return e.service.save_story_record(e.nid,kind,rid,payload,None,0)


@pytest.mark.parametrize('kind',['timeline','foreshadowing'])
def test_cas_public_digest_two_writers_history_restore_restart_and_legacy(env,kind):
    e=env;row=create(e,kind)
    public=e.service.data_set(e.nid,kind)[0]
    assert row['record']==public and row['digest']==record_digest(public) and META not in public
    if kind=='timeline':assert public['location']=='unresolved-old-slug' and public['status']=='PLANNED'
    def write(title):
        try:return e.service.save_story_record(e.nid,kind,'event',{'title':title},row['digest'],row['version'])
        except VersionConflict:return None
    with ThreadPoolExecutor(2) as pool:results=list(pool.map(write,['A','B']))
    assert sum(result is not None for result in results)==1
    won=next(result for result in results if result)
    assert won['version']==2 and won['history'][0]['record']==row['record']
    with pytest.raises(VersionConflict):e.service.save_story_record(e.nid,kind,'event',{},row['digest'],1,action='RESTORE',restore_version=1)
    restored=e.service.save_story_record(e.nid,kind,'event',{},won['digest'],2,action='RESTORE',restore_version=1)
    assert restored['record']==row['record'] and restored['version']==3
    replacement=create_repository_bundle(e.settings,data_root=e.root)
    restarted=NovelService(replacement.novels,replacement.chapters)
    assert restarted.story_record(e.nid,kind,'event')['history']==restored['history']
    old_method=restarted.upsert_timeline_event if kind=='timeline' else restarted.upsert_foreshadowing
    old_method(e.nid,'event',{'title':'Legacy after opt-in'})
    current=restarted.story_record(e.nid,kind,'event')
    assert current['version']==4 and current['history'][-1]['record']==restored['record']
    with pytest.raises(VersionConflict):e.service.save_story_record(e.nid,kind,'event',{'title':'No lost overwrite'},restored['digest'],3)
    if e.backend=='postgres':replacement.novels.database.engine.dispose()


def test_bounded_history_source_feedback_terminal_restore_and_revocation(env):
    e=env;row=create(e);assert e.service.story_record(e.nid,'timeline','event')['source_state']=='CURRENT'
    feedback=e.service.save_story_record(e.nid,'timeline','event',{},row['digest'],1,action='FEEDBACK',feedback={'decision':'INTENTIONAL','note':'Deliberate','evidence':'Author review'})
    assert feedback['record']==row['record'] and feedback['digest']==row['digest']
    assert feedback['feedback']['source_versions'][0]['id']==e.chapter['id']
    with pytest.raises(VersionConflict):e.service.save_story_record(e.nid,'timeline','event',{},row['digest'],2,action='FEEDBACK',feedback={'decision':'DISMISSED'})
    e.bundle.chapters.rename(e.chapter['id'],'Changed source',e.chapter['version'])
    stale=e.service.story_record(e.nid,'timeline','event');assert stale['source_state']=='STALE' and stale['feedback_stale']
    with pytest.raises(VersionConflict):e.service.save_story_record(e.nid,'timeline','event',{'title':'Unreviewed'},stale['digest'],2)
    def revoked():raise PermissionError('revoked before commit')
    with pytest.raises(PermissionError):e.service.save_story_record(e.nid,'timeline','event',{'title':'No'},stale['digest'],2,refresh_sources=True,check=revoked)
    assert e.service.story_record(e.nid,'timeline','event')['version']==2
    current=stale
    for number in range(25):
        current=e.service.save_story_record(e.nid,'timeline','event',{'title':str(number)},current['digest'],current['version'],refresh_sources=True)
    assert len(current['history'])==20 and current['history'][0]['version']==7
    with pytest.raises(FileNotFoundError):e.service.save_story_record(e.nid,'timeline','event',{},current['digest'],current['version'],action='RESTORE',restore_version=0)


@pytest.mark.parametrize('kind',['timeline','foreshadowing'])
def test_existing_extension_preserved_client_extension_rejected_and_old_shape(env,kind):
    e=env;method=e.service.upsert_timeline_event if kind=='timeline' else e.service.upsert_foreshadowing
    method(e.nid,'old',{'title':'Old'})
    assert e.service.story_record(e.nid,kind,'old')['version']==0
    if e.backend=='file':
        from app.repository import read_json
        from app.storage import atomic_write
        import json
        path=e.root/'novels'/e.nid/('timeline/events.json' if kind=='timeline' else 'foreshadowing.json')
        rows=read_json(path,[]);rows[0]['import_extension']={'keep':'opaque'};atomic_write(path,json.dumps(rows))
    else:
        from sqlalchemy import select
        from app.repositories.postgres.models import TimelineModel,ForeshadowingModel
        cls=TimelineModel if kind=='timeline' else ForeshadowingModel
        with e.bundle.novels.database.session() as session:
            model=session.scalar(select(cls).where(cls.details['_source_id'].astext=='old'))
            model.details={**model.details,'import_extension':{'keep':'opaque'}}
    current=e.service.story_record(e.nid,kind,'old')
    with pytest.raises(ValueError):e.service.save_story_record(e.nid,kind,'old',{'title':'No','import_extension':{}},current['digest'],0)
    saved=e.service.save_story_record(e.nid,kind,'old',{'title':'Safe'},current['digest'],0)
    assert saved['record']['import_extension']=={'keep':'opaque'}
    assert saved['history'][0]['record']==current['record']
    assert META not in e.service.data_set(e.nid,kind)[0]


def test_original_context_excludes_private_history(env):
    from app.context import build_context_from_sources
    e=env;row=create(e,'foreshadowing')
    e.service.save_story_record(e.nid,'foreshadowing','event',{'title':'Current'},row['digest'],1)
    sources=e.bundle.novels.get_context_sources(e.nid)
    assert META not in sources['foreshadowing'][0]
    direct={**sources,'foreshadowing':[{**sources['foreshadowing'][0],META:{'history':[{'record':{'title':'Private'}}]}}]}
    assert META not in build_context_from_sources(direct,e.nid,1,'')['active_foreshadowing'][0]


def test_create_race_non_ascii_exact_identity_and_changed_source_before_commit(env,monkeypatch):
    e=env
    def create_once(title):
        try:return e.service.save_story_record(e.nid,'timeline','原始事件',{'title':title,'chapter_id':e.chapter['id']},None,0)
        except VersionConflict:return None
    with ThreadPoolExecutor(2) as pool:results=list(pool.map(create_once,['First','Second']))
    assert sum(result is not None for result in results)==1
    current=e.service.story_record(e.nid,'timeline','原始事件');assert current['record']['id']=='原始事件'
    original=e.bundle.novels.compare_and_swap_record
    def change_before_commit(*args,**kwargs):
        e.bundle.chapters.rename(e.chapter['id'],'Changed while preparing',e.chapter['version'])
        return original(*args,**kwargs)
    monkeypatch.setattr(e.bundle.novels,'compare_and_swap_record',change_before_commit)
    with pytest.raises(VersionConflict):e.service.save_story_record(e.nid,'timeline','原始事件',{'title':'Stale source','chapter_id':e.chapter['id']},current['digest'],1)
    assert e.service.story_record(e.nid,'timeline','原始事件')['version']==1


def test_source_tombstone_does_not_rebind_or_restore_deleted_chapter(env):
    e=env;row=create(e);source_id=row['source_versions'][0]['id']
    e.bundle.chapters.delete(source_id)
    next_chapter=e.bundle.chapters.create(e.nid,{'title':'Another chapter','content':'Other'})
    assert next_chapter['id']!=source_id
    stale=e.service.story_record(e.nid,'timeline','event')
    assert stale['source_state']=='STALE' and stale['source_versions'][0]['id']==source_id
    with pytest.raises(FileNotFoundError):e.service.save_story_record(e.nid,'timeline','event',{'title':'Cannot guess a source','chapter_id':source_id},row['digest'],1,refresh_sources=True)
    assert e.service.story_record(e.nid,'timeline','event')['version']==1


@pytest.mark.parametrize('kind',['timeline','foreshadowing'])
def test_sparse_legacy_snapshot_feedback_and_restore_keep_exact_public_shape(env,kind):
    e=env;method=e.service.upsert_timeline_event if kind=='timeline' else e.service.upsert_foreshadowing
    method(e.nid,'sparse',{'title':'Sparse original','privacy_level':'LOCAL_ONLY'})
    omitted={'description','characters','chapter_id','events'}|({'status'} if kind=='timeline' else set())
    if e.backend=='file':
        from app.repository import read_json
        from app.storage import atomic_write
        import json
        path=e.root/'novels'/e.nid/('timeline/events.json' if kind=='timeline' else 'foreshadowing.json')
        rows=read_json(path,[])
        rows[0]={key:value for key,value in rows[0].items() if key not in omitted}
        rows[0]['import_extension']={'keep':'sparse opaque original'}
        atomic_write(path,json.dumps(rows))
    else:
        from sqlalchemy import select
        from app.repositories.postgres.models import TimelineModel,ForeshadowingModel
        cls=TimelineModel if kind=='timeline' else ForeshadowingModel
        with e.bundle.novels.database.session() as session:
            model=session.scalar(select(cls).where(cls.details['_source_id'].astext=='sparse'))
            model.details={**{key:value for key,value in model.details.items() if key not in omitted},'import_extension':{'keep':'sparse opaque original'}}
    original=e.service.story_record(e.nid,kind,'sparse')
    assert not omitted.intersection(original['record'])
    feedback=e.service.save_story_record(e.nid,kind,'sparse',{},original['digest'],0,action='FEEDBACK',feedback={'decision':'ACKNOWLEDGED','note':'Sparse review','evidence':''})
    assert feedback['record']==original['record'] and feedback['digest']==original['digest']
    changed=e.service.save_story_record(e.nid,kind,'sparse',{'title':'Expanded row','description':'New'},feedback['digest'],1)
    restored=e.service.save_story_record(e.nid,kind,'sparse',{},changed['digest'],2,action='RESTORE',restore_version=0)
    assert restored['record']==original['record'] and restored['digest']==original['digest']
    assert e.service.data_set(e.nid,kind)[0]==original['record']


@pytest.mark.parametrize('kind',['timeline','foreshadowing'])
def test_legacy_client_updates_existing_exact_non_slug_identity_instead_of_creating_a_duplicate(env,kind):
    e=env;rid='原始事件 Exact Identity';original=create(e,kind,rid)
    method=e.service.upsert_timeline_event if kind=='timeline' else e.service.upsert_foreshadowing
    result=method(e.nid,rid,{'title':'Older client edit'})
    assert result['id']==rid and len(e.service.data_set(e.nid,kind))==1
    current=e.service.story_record(e.nid,kind,rid)
    assert current['version']==2 and current['history'][0]['record']==original['record']
    with pytest.raises(VersionConflict):e.service.save_story_record(e.nid,kind,rid,{'title':'Stale versioned client'},original['digest'],1)
