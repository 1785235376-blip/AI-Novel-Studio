"""Inert Research OCR records in original real File/PostgreSQL job stores."""
from copy import deepcopy
from uuid import uuid4
import pytest
from fastapi import HTTPException
from app.jobs import Job, JobManager, generation_content_available, require_whole_generation_acceptance
from app.experimental.research_ocr_binding import ResearchOCRJobBinding
from app.repositories.generation_repository import GenerationProjectIdentityError
from app.services.generation_service import GenerationService
from test_v2_independent_workspace import rig


class ForbiddenOwner:
    def __getattr__(self,name):raise AssertionError('Passive OCR accessed live owner: '+name)


def record(e,status='COMPLETED'):
    binding=ResearchOCRJobBinding.model_validate(dict(contract='RESEARCH_OCR_JOB_V1',source_kind='IMAGE',
        project_id=e.nid,project_incarnation=e.store.incarnation(e.nid),actor_id=e.actor,scope=deepcopy(e.scope),
        source_id='research-image',source_version=1,source_digest='a'*64,media_type='image/png',
        language='eng',route_digest='b'*64,reviewed_preview_digest='c'*64)).model_dump()
    return Job(id=str(uuid4()),operation='research_ocr',novel_id=e.nid,chapter_id=None,
        instruction='',profile='LOCAL_ONLY',status=status,actor_id=e.actor,scope=deepcopy(e.scope),
        experimental_origin='research_ocr_model',research_ocr_binding=binding,expected_request_digest='d'*64).public()


def reopen(e):
    owner=ForbiddenOwner()
    return JobManager(GenerationService(e.bundle.generations),owner,owner,owner,
        memory_extractor=owner,snapshot_required=True,collaboration_updates=owner)


def test_original_store_roundtrip_is_passive_and_detached(rig):
    e=rig; item=record(e); e.bundle.generations.save(item)
    assert e.bundle.generations.get(item['id'])==item
    manager=reopen(e); job=manager.get(item['id'])
    assert not generation_content_available(job)
    changed=job.public(); changed['research_ocr_binding']['scope']['novel_id']='other'
    assert job.research_ocr_binding==item['research_ocr_binding']
    for operation in [lambda:manager.start_prepared(job),lambda:manager._start_prepared_validated(job),
                      lambda:manager._run(job)]:
        with pytest.raises(ValueError,match='RESEARCH_OCR_EXECUTION_UNAVAILABLE'):operation()
    for operation in [lambda:manager.accept(job.id),lambda:manager.diff(job.id),
                      lambda:require_whole_generation_acceptance(job)]:
        with pytest.raises(HTTPException):operation()
    assert e.bundle.generations.get(item['id'])==item and e.chapters.list(e.nid)==[]


@pytest.mark.parametrize('status',['PREPARED','QUEUED','GENERATING','RUNNING','SETTLING'])
def test_restart_never_replays_or_publishes_uncertain_output(rig,status):
    e=rig;item=record(e,status);item['output']='Unproven native output';e.bundle.generations.save(item)
    job=reopen(e).get(item['id'])
    assert job.status=='FAILED' and job.output=='' and not generation_content_available(job)
    assert job.request_authorization is None and job.on_terminal is None
    assert e.bundle.generations.get(item['id'])['output']==''
    assert reopen(e).get(item['id']).public()==job.public()


@pytest.mark.parametrize('field,value',[('actor_id','other'),('scope',None),('novel_id','other'),
    ('operation','writer'),('experimental_origin','creative_graph_model'),('chapter_id','fake'),
    ('research_ocr_binding',None),('graph_binding',{}),('creative_director_binding',None),
    ('expected_request_digest','changed'),('profile','AUTO')])
def test_malformed_and_mixed_records_cannot_enter_original_store(rig,field,value):
    e=rig;item=record(e);item[field]=value
    with pytest.raises(GenerationProjectIdentityError):e.bundle.generations.save(item)
    assert item['id'] not in {row['id'] for row in e.bundle.generations.load_all()}


def test_complete_identity_removal_cannot_downgrade_existing_record(rig):
    e=rig;item=record(e);e.bundle.generations.save(item);changed=deepcopy(item)
    changed.pop('research_ocr_binding');changed.pop('expected_request_digest')
    changed.update(operation='writer',experimental_origin=None,scope=None,actor_id=None)
    with pytest.raises(GenerationProjectIdentityError):e.bundle.generations.save(changed)
    assert e.bundle.generations.get(item['id'])==item


def test_bound_source_and_route_cannot_be_reassigned(rig):
    e=rig;item=record(e);e.bundle.generations.save(item)
    for field,value in [('source_id','other'),('source_version',2),('route_digest','f'*64)]:
        changed=deepcopy(item);changed['research_ocr_binding'][field]=value
        with pytest.raises(GenerationProjectIdentityError):e.bundle.generations.save(changed)
    assert e.bundle.generations.get(item['id'])==item


def test_reused_public_project_cannot_inherit_ocr_job(rig):
    e=rig;item=record(e);e.bundle.generations.save(item);old=item['research_ocr_binding']['project_incarnation']
    e.novels.delete(e.nid);e.create_project(nid=e.nid)
    assert e.store.incarnation(e.nid)!=old
    with pytest.raises(GenerationProjectIdentityError):e.bundle.generations.save(dict(item,output='late'))
    with pytest.raises(KeyError):e.bundle.generations.get(item['id'])
    assert item['id'] not in reopen(e).jobs
    fresh=record(e);e.bundle.generations.save(fresh)
    assert e.bundle.generations.get(fresh['id'])==fresh


@pytest.mark.parametrize('marker',[{'operation':'research_ocr'},{'research_ocr_binding':None},
    {'experimental_origin':'research_ocr_model'}])
def test_ordinary_author_preparation_rejects_each_reserved_marker(rig,marker):
    e=rig;manager=reopen(e)
    operation=marker.get('operation','writer')
    with pytest.raises(ValueError,match='RESEARCH_OCR_EXECUTION_UNAVAILABLE'):
        manager.prepare_job(operation,{'novel_id':e.nid,'chapter_id':'must-not-read',**marker})
