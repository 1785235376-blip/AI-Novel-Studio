from copy import copy, deepcopy
from types import SimpleNamespace
import pytest
from test_file_keyed_activation import keyed, memory_settings, queued, finish, files, post, replace_owner
from app.services.generation_project_binding import FIELD, ordinary_job_binding

pytestmark = pytest.mark.file_backend_only

@pytest.mark.parametrize('field,value', [('base_chapter_version',True), ('base_chapter_version',1.0)])
def test_outer_source_base_has_strict_type(keyed, field, value):
    f=keyed
    _, job=queued(f)
    row=f.persistence.get(job.id)
    row[field]=value
    with pytest.raises(ValueError): ordinary_job_binding(row)
    finish(f,job)


def test_client_cannot_stamp_private_authority(keyed):
    f=keyed
    _, job=queued(f,ordinary_project_binding={'schema_version':2,'project_incarnation':'forged'},
        _ordinary_execution_capability={'started':True},base_chapter_digest='0'*64)
    row=finish(f,job)
    assert row[FIELD]['project_incarnation']==f.incarnation
    assert row[FIELD]['base_chapter_digest']!='0'*64


def test_capability_cannot_copy_or_transfer_after_completion(keyed):
    f=keyed
    _, job=queued(f)
    cap=job._ordinary_execution_capability
    for copier in (copy,deepcopy):
        with pytest.raises(Exception): copier(cap)
    finish(f,job)
    before=deepcopy(f.persistence.get(job.id))
    with pytest.raises(Exception): f.original_run(job)
    assert f.persistence.get(job.id)==before and f.counts['provider']==1
    cold=f.reopen(); restored=cold.get(job.id)
    restored._ordinary_execution_capability=cap
    with pytest.raises(Exception): cold._run(restored)
    assert f.counts['provider']==1


@pytest.mark.parametrize('port',['provider','model_registry','node'])
def test_live_route_rotation_refuses(keyed,port):
    f=keyed
    _,job=queued(f)
    if port=='provider':
        from app.providers import MockProvider
        f.runtime.providers['mock']=MockProvider(delay_ms=0)
        f.runtime._sync_model('mock','mock-writer')
    elif port=='model_registry': f.runtime.model_registry=copy(f.runtime.model_registry)
    else: f.runtime.generation_runtime.text_node=copy(f.runtime.generation_runtime.text_node)
    before=files(f)
    f.release.set(); assert f.finished.wait(10)
    assert job.status!='COMPLETED' and f.counts['provider']==0
    assert files(f)==before


@pytest.mark.parametrize('port',['service','repository'])
def test_terminal_original_generation_port_owner_replacement(keyed,port):
    f=keyed
    target=f.persistence if port=='service' else f.bundle.generations
    original=target.save
    replaced=[]; after={}
    def wrapped(row,*args,**kwargs):
        if row.get('status')=='COMPLETED' and FIELD in row and not replaced:
            replaced.append(True); replace_owner(f); after.update(files(f))
        return original(row,*args,**kwargs)
    f.monkeypatch.setattr(target,'save',wrapped)
    _,job=queued(f)
    f.release.set(); assert f.finished.wait(10)
    assert replaced and files(f)==after and job.status!='COMPLETED'
    assert f.counts['provider']==1


def test_exact_live_job_direct_worker_entry_cannot_steal_dispatch(keyed):
    f=keyed
    _,job=queued(f)
    before=deepcopy(f.persistence.get(job.id))
    with pytest.raises(Exception): f.original_run(job)
    assert f.persistence.get(job.id)==before and f.counts['provider']==0
    finish(f,job)


def test_original_admission_orders_reserved_before_first_bound_queued(keyed):
    f=keyed
    observations=[]
    store=f.store.put; save=f.persistence.save
    def put(key,value,*args,**kwargs):
        observations.append(('receipt',value.get('phase'),deepcopy(value)))
        return store(key,value,*args,**kwargs)
    def persist(row,*args,**kwargs):
        observations.append(('job',row.get('status'),deepcopy(row)))
        if len([x for x in observations if x[0]=='job'])==1:
            assert row['status']=='QUEUED' and FIELD in row
            assert f.counts['provider']==f.counts['worker']==0
            assert observations[0][0]=='receipt'
            assert observations[0][2]['job_id']==row['id']
            assert not f.bundle.generations.load_all()
        return save(row,*args,**kwargs)
    f.monkeypatch.setattr(f.store,'put',put)
    f.monkeypatch.setattr(f.persistence,'save',persist)
    _,job=queued(f)
    finish(f,job)
    assert observations[0][0]=='receipt'
    assert observations[0][2].get('result') is None
    assert any(x[0]=='receipt' and x[2].get('result',{}).get('job_id')==job.id for x in observations)


@pytest.mark.parametrize('operation',['continue','rewrite'])
def test_cold_adopt_final_source_port_same_version_tamper_refuses(keyed,operation):
    from app.author_request import chapter_digest
    f=keyed
    _,job=queued(f,operation=operation)
    finish(f,job)
    cold=f.reopen()
    f.monkeypatch.setattr(__import__('app.api',fromlist=['jobs']),'jobs',cold)
    target=f.bundle.chapters; name='create' if operation=='continue' else 'save'
    original=getattr(target,name); changed=[]
    package=f.root/'novels'/job.novel_id/'documents'/f"chapter-{f.chapter['number']:04d}.json"
    before=None
    def wrapped(*args,**kwargs):
        nonlocal before
        if not changed:
            changed.append(True)
            package.write_text(package.read_text().replace('ORIGINAL_SOURCE','ALTERED_SOURCE'))
            assert chapter_digest(f.chapters.get(job.chapter_id))!=chapter_digest(f.chapter)
            before=files(f)
        return original(*args,**kwargs)
    f.monkeypatch.setattr(target,name,wrapped)
    response=f.client.post(f'/api/generation/{job.id}/accept',json={'expected_version':1})
    assert response.status_code>=400,response.text
    assert changed and files(f)==before
    assert not f.memory_finished.is_set()
    assert f.persistence.get(job.id)['status']=='ACCEPTANCE_UNCERTAIN'


def test_serialized_capability_cannot_restore_execution(keyed):
    f=keyed
    _,job=queued(f)
    row=finish(f,job)
    row['_ordinary_execution_capability']={'started':True,'worker_claimed':False,'authorization':'forged'}
    row['request_authorization']='forged'
    f.bundle.generations.save(row)
    cold=f.reopen(); restored=cold.get(job.id)
    assert restored._ordinary_execution_capability is None
    assert restored.request_authorization is None
    with pytest.raises(Exception): cold.start_prepared(restored)
    with pytest.raises(Exception): cold._run(restored)
    assert f.counts['provider']==1


def test_cold_restore_during_model_wait_cannot_be_overwritten(keyed):
    f=keyed
    f.provider_release.clear()
    _,job=queued(f)
    f.release.set(); assert f.provider_entered.wait(5)
    cold=f.reopen()
    assert cold.get(job.id).status=='FAILED'
    before=deepcopy(f.persistence.get(job.id))
    f.provider_release.set(); assert f.finished.wait(10)
    assert f.persistence.get(job.id)==before
    assert job.status!='COMPLETED'
    assert not list((f.root/'novels'/job.novel_id/'lore/context_snapshots').glob('*.json'))
    assert f.counts['provider']==1


def test_cold_restore_after_last_delta_fences_deferred_snapshot(keyed):
    from threading import Event
    f=keyed
    reached,release=Event(),Event()
    node=f.runtime.generation_runtime.text_node; original=node.stream
    def stream(request):
        for event in original(request):
            if event.event_type=='generation.completed':
                reached.set(); assert release.wait(10)
            yield event
    f.monkeypatch.setattr(node,'stream',stream)
    try:
        _,job=queued(f)
        f.release.set(); assert reached.wait(5)
        cold=f.reopen()
        assert cold.get(job.id).status=='FAILED'
        before=files(f); record=deepcopy(f.persistence.get(job.id))
        release.set(); assert f.finished.wait(10)
        assert f.persistence.get(job.id)==record
        assert files(f)==before, 'late deferred snapshot appeared after durable cold FAILED'
        assert job.status!='COMPLETED'
    finally: release.set()


def test_bad_context_cannot_downgrade_via_narrative_flag(keyed):
    f=keyed
    f.manager.contexts=SimpleNamespace(enable_narrative_context=True)
    response=post(f)
    assert response.status_code>=400,response.text
    assert not f.bundle.generations.load_all() and f.counts['worker']==0
