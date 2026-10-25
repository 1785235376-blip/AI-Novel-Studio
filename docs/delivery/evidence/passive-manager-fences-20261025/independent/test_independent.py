from copy import deepcopy
from types import SimpleNamespace
from uuid import uuid4
import json
import pytest
from app.jobs import JobManager, generation_content_available
from app.creative.project_store import CreativeProjectStore
from app.repositories.factory import create_repository_bundle
from app.services import GenerationService, ChapterService
from app.services.generation_project_binding import FIELD, IDENTITY_FIELDS

@pytest.fixture
def env(tmp_path):
    bundle=create_repository_bundle(data_root=tmp_path)
    novels=bundle.novels.backend
    novels.create_novel(dict(id='ordinary-owner',title='Independent original'))
    novels.create_chapter('ordinary-owner',dict(title='One',content='Independent original source'))
    owner=CreativeProjectStore(SimpleNamespace(backend='file',root=tmp_path)).incarnation('ordinary-owner')
    row=dict(id=str(uuid4()),novel_id='ordinary-owner',chapter_id='ordinary-owner:1',operation='continue',actor_id=None,workspace_id=None,scope=None,scope_type=None,scope_id=None,experimental_origin=None,status='COMPLETED',output='PRIVATE DRAFT',instruction='Continue',profile='LOCAL_ONLY',source='Independent original source')
    row[FIELD]=dict(schema_version=1,project_incarnation=owner,job_id=row['id'],project_id=row['novel_id'],**{k:deepcopy(row[k]) for k in IDENTITY_FIELDS})
    bundle.generations.save(row)
    def manager(chapters=None):
        return JobManager(generations=GenerationService(bundle.generations),chapters=chapters or ChapterService(bundle.chapters),contexts=object(),canon=object(),memory_extractor=object(),collaboration_updates=object())
    return SimpleNamespace(bundle=bundle,novels=novels,row=row,manager=manager,root=tmp_path)

def replace_owner(e):
    e.novels.delete_novel('ordinary-owner')
    e.novels.create_novel(dict(id='ordinary-owner',title='Replacement'))
    e.novels.create_chapter('ordinary-owner',dict(title='One',content='Replacement source'))
    CreativeProjectStore(SimpleNamespace(backend='file',root=e.root)).incarnation('ordinary-owner')

def test_cached_content_after_owner_replacement(env):
    manager=env.manager(); job=manager.get(env.row['id'])
    assert generation_content_available(job)
    replace_owner(env)
    assert not generation_content_available(job)
    with pytest.raises(KeyError): manager.get(job.id)

def test_missing_durable_row_cannot_serve_cached(env):
    manager=env.manager(); job=manager.get(env.row['id'])
    env.bundle.generations._job_path(job.id).unlink()
    assert not generation_content_available(job)
    with pytest.raises(KeyError): manager.get(job.id)

def test_private_record_detached_from_public(env):
    manager=env.manager(); job=manager.get(env.row['id'])
    assert FIELD not in job.public()
    row=job.record(); assert row[FIELD]==env.row[FIELD]
    row[FIELD]['project_id']='mutated-copy'
    assert job.record()[FIELD]==env.row[FIELD]

@pytest.mark.parametrize('change',['null','remove','identity','binding_identity'])
def test_cached_binding_mutation_never_demotes(env,change):
    manager=env.manager(); job=manager.get(env.row['id'])
    if change=='null': setattr(job,FIELD,None)
    elif change=='remove': delattr(job,FIELD)
    elif change=='identity': job.novel_id='different'
    else: getattr(job,FIELD)['chapter_id']='ordinary-owner:2'
    assert not generation_content_available(job)
    with pytest.raises((KeyError,ValueError)): manager.get(job.id)

@pytest.mark.parametrize('action',['accept','reject','cancel','start_prepared'])
def test_bound_mutations_have_no_side_effect(env,action):
    manager=env.manager(); job=manager.get(env.row['id']); before=env.bundle.generations._job_path(job.id).read_bytes()
    with pytest.raises(Exception): getattr(manager,action)(job if action=='start_prepared' else job.id)
    assert job.status=='COMPLETED'
    assert not job.cancelled.is_set()
    assert env.bundle.generations._job_path(job.id).read_bytes()==before

def test_mismatched_chapter_store_cannot_serve(env,tmp_path):
    other=create_repository_bundle(data_root=tmp_path/'other')
    manager=env.manager(ChapterService(other.chapters))
    with pytest.raises(KeyError): manager.get(env.row['id'])

def test_event_replacement_after_first_yield(env):
    manager=env.manager(); job=manager.get(env.row['id']); job.status='RUNNING'
    stream=manager.events(job.id); assert 'PRIVATE DRAFT' in next(stream)
    replace_owner(env); job.output+='DO NOT DISCLOSE'; job.status='COMPLETED'
    assert list(stream)==[]

def test_diff_refuses_after_cached_owner_replacement(env):
    manager=env.manager(); manager.get(env.row['id']); replace_owner(env)
    with pytest.raises(Exception): manager.diff(env.row['id'])

def test_restart_never_restores_callbacks(env):
    row=deepcopy(env.row); row.update(status='RUNNING',before_dispatch='forged',on_terminal='forged',request_authorization='forged')
    env.bundle.generations.save(row)
    manager=env.manager(); job=manager.get(row['id'])
    assert not callable(job.before_dispatch) and not callable(job.on_terminal) and not callable(job.request_authorization)
    assert job.status not in {'RUNNING','QUEUED','GENERATING','PREPARED'}
    assert FIELD not in job.public()

def test_diff_cannot_read_foreign_root_source(env,tmp_path):
    row=deepcopy(env.row); row['source']=''; env.bundle.generations.save(row)
    other=create_repository_bundle(data_root=tmp_path/'foreign')
    other.novels.backend.create_novel(dict(id='ordinary-owner',title='Foreign'))
    other.novels.backend.create_chapter('ordinary-owner',dict(title='One',content='FOREIGN PRIVATE CONTENT'))
    manager=env.manager(ChapterService(other.chapters))
    with pytest.raises(Exception): manager.diff(row['id'])

def test_persistence_swap_never_reauthorizes_removed_original(env):
    manager=env.manager(); job=manager.get(env.row['id'])
    env.bundle.generations._job_path(job.id).unlink()
    class Substitute:
        def get(self,jid): return deepcopy(env.row)
    manager.persistence=Substitute()
    assert not generation_content_available(job)
    with pytest.raises(KeyError): manager.get(job.id)

def test_diff_rechecks_owner_after_source_resolution(env,monkeypatch):
    row=deepcopy(env.row); row['source']=''; env.bundle.generations.save(row)
    manager=env.manager(); original_get=manager.chapters.get
    def replacing_get(cid):
        replace_owner(env)
        return original_get(cid)
    monkeypatch.setattr(manager.chapters,'get',replacing_get)
    with pytest.raises(Exception): manager.diff(row['id'])

def test_original_service_wrapper_cannot_be_swapped_for_forged_read(env):
    manager=env.manager(); job=manager.get(env.row['id'])
    env.bundle.generations._job_path(job.id).unlink()
    class Substitute:
        repository=env.bundle.generations
        def get(self,jid): return deepcopy(env.row)
    manager.persistence=Substitute()
    assert not generation_content_available(job)

def test_mismatched_restore_does_not_write_recovery(env,tmp_path):
    row=deepcopy(env.row); row['status']='RUNNING'; env.bundle.generations.save(row)
    before=env.bundle.generations._job_path(row['id']).read_bytes()
    other=create_repository_bundle(data_root=tmp_path/'other')
    manager=env.manager(ChapterService(other.chapters))
    assert env.bundle.generations._job_path(row['id']).read_bytes()==before
    with pytest.raises(KeyError): manager.get(row['id'])

def test_bound_direct_worker_refuses_before_callbacks(env):
    manager=env.manager(); job=manager.get(env.row['id']); calls=[]
    job.before_dispatch=lambda: calls.append('dispatch')
    job.on_terminal=lambda *a,**k: calls.append('terminal')
    before=job.record()
    with pytest.raises(Exception): manager._run(job)
    assert calls==[] and job.record()==before

@pytest.mark.parametrize('change',['owner','database'])
def test_original_postgres_manager_read_protocol(env,change):
    # Existing offline protocol harness; real ORM/SQL compilation, NOT a live DB.
    import sys
    from pathlib import Path
    sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tests'))
    from test_ordinary_project_binding_postgres import _Database, _item
    from app.repositories.postgres.generation import PostgresGenerationRepository
    from app.repositories.postgres.chapter import PostgresChapterRepository
    database=_Database(); repository=PostgresGenerationRepository(database)
    row=_item(database); row.update(status='COMPLETED',output='PG PRIVATE',instruction='Continue',profile='LOCAL_ONLY',source='PG SOURCE')
    repository.save(row)
    chapters=PostgresChapterRepository(database)
    manager=JobManager(generations=GenerationService(repository),chapters=ChapterService(chapters),contexts=object(),canon=object(),memory_extractor=object(),collaboration_updates=object())
    job=manager.get(row['id']); assert generation_content_available(job)
    assert all(not s.active for s in database.sessions)
    assert FIELD not in job.public()
    if change=='owner': database.owner.id=uuid4()
    else: chapters.database=_Database()
    assert not generation_content_available(job)
    with pytest.raises(KeyError): manager.get(job.id)
    assert all(not s.active for s in database.sessions)

@pytest.mark.parametrize('kind',['graph','adaptation','director','ocr','image'])
def test_specialized_manager_record_persist_projection_unchanged(env,kind):
    import sys
    from pathlib import Path
    sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tests'))
    from test_ordinary_project_binding import test_original_specialized_file_contracts_remain_exact
    owner=SimpleNamespace(item=env.row,repository=env.bundle.generations,root=env.root)
    test_original_specialized_file_contracts_remain_exact(owner,kind)
    row=next(r for r in env.bundle.generations.load_all() if r['id']!=env.row['id'])
    row.update(id=str(uuid4()),instruction='Synthetic specialized',status='COMPLETED')
    from app.jobs import Job
    row=Job(**{k:v for k,v in row.items() if k in Job.__dataclass_fields__}).public()
    env.bundle.generations.save(row)
    manager=env.manager(); job=manager.get(row['id'])
    public=job.public()
    assert FIELD not in public and job.record()==public
    manager._persist(job)
    assert env.bundle.generations.get(job.id)==public
