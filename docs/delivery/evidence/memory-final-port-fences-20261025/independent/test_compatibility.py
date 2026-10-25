import json
import socket
from threading import Thread, Event
import pytest
from test_bound_memory_project_owner import setup, record
from test_memory_agent_contract import memory_settings, runner, valid_output
from app.lore.memory_project_binding import FIELD

@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def denied(*a, **kw): raise AssertionError('network prohibited in independent review')
    monkeypatch.setattr(socket.socket, 'connect', denied)
    monkeypatch.setattr(socket, 'create_connection', denied)

def test_failed_same_owner_retry_has_complete_relations(tmp_path, memory_settings, monkeypatch):
    agent,bundle,nid,cid,v,owner,binding=setup(tmp_path)
    original=bundle.lore.link_evidence
    def fail(item, **kwargs): raise OSError('synthetic one-time relation write failure')
    monkeypatch.setattr(bundle.lore,'link_evidence',fail)
    with pytest.raises(OSError): agent.extract(nid,cid,v,project_incarnation=binding['project_incarnation'])
    assert bundle.generations.get(binding['job_id'])['status']=='FAILED'
    assert len(bundle.lore.list_proposals(nid))==1
    monkeypatch.setattr(bundle.lore,'link_evidence',original)
    ids=agent.extract(nid,cid,v,project_incarnation=binding['project_incarnation'])
    assert bundle.generations.get(binding['job_id'])['status']=='COMPLETED'
    assert len(bundle.lore.list_proposal_evidence(ids[0]))==1, 'COMPLETED after retry with missing evidence relation'

def test_bound_does_not_adopt_legacy_proposal_receipt(tmp_path,memory_settings):
    agent,bundle,nid,cid,v,owner,binding=setup(tmp_path)
    legacy=agent.extract(nid,cid,v,job_id='legacy-existing')
    ids=agent.extract(nid,cid,v,project_incarnation=binding['project_incarnation'])
    assert bundle.generations.get(binding['job_id'])['status']=='COMPLETED'
    assert bundle.lore.get_proposal(ids[0])['generation_job_id']==binding['job_id'], 'bound receipt points to legacy proposal provenance'

def test_error_record_original_lease(tmp_path,memory_settings,monkeypatch):
    agent,bundle,nid,cid,v,owner,binding=setup(tmp_path)
    agent.runtime.provider.text='invalid JSON'
    at,release,deleted=Event(),Event(),Event(); errors=[]
    original=bundle.generations.save
    def save(item, **kwargs):
        if item['status']=='FAILED':
            at.set(); assert release.wait(5)
        return original(item, **kwargs)
    monkeypatch.setattr(bundle.generations,'save',save)
    def work():
        try: agent.extract(nid,cid,v,project_incarnation=binding['project_incarnation'])
        except Exception as exc: errors.append(exc)
    def delete():
        bundle.novels.delete(nid);deleted.set()
    t=Thread(target=work);t.start();assert at.wait(5)
    d=Thread(target=delete);d.start()
    try: assert not deleted.wait(.15)
    finally: release.set()
    t.join(5);d.join(5)
    assert not t.is_alive() and not d.is_alive() and errors
    assert json.loads(bundle.generations._job_path(binding['job_id']).read_text())['status']=='FAILED'
    with pytest.raises(KeyError):bundle.generations.get(binding['job_id'])

def test_source_recheck_and_terminal_share_original_lease(tmp_path,memory_settings,monkeypatch):
    agent,bundle,nid,cid,v,owner,binding=setup(tmp_path)
    at,release,deleted=Event(),Event(),Event(); errors=[]; seen=[]
    original=agent._input
    def input(*args):
        result=original(*args);seen.append(result)
        if len(seen)==2: at.set();assert release.wait(5)
        return result
    monkeypatch.setattr(agent,'_input',input)
    def work():
        try: agent.extract(nid,cid,v,project_incarnation=binding['project_incarnation'])
        except Exception as exc:errors.append(exc)
    def delete():bundle.novels.delete(nid);deleted.set()
    t=Thread(target=work);t.start();assert at.wait(5)
    d=Thread(target=delete);d.start()
    try:assert not deleted.wait(.15)
    finally:release.set()
    t.join(5);d.join(5)
    assert not errors and not t.is_alive() and not d.is_alive()
    durable=json.loads(bundle.generations._job_path(binding['job_id']).read_text())
    assert durable['status']=='COMPLETED' and durable[FIELD]==binding
    assert not (tmp_path/'novels'/nid).exists()

def test_inference_does_not_block_deletion_and_stale_failure_not_written(tmp_path,memory_settings,monkeypatch):
    from test_bound_review_port_blockers import replace_memory_owner,project_bytes
    agent,bundle,nid,cid,v,owner,binding=setup(tmp_path)
    at,release=Event(),Event(); errors=[]
    original=agent.runtime.provider._text
    def text(prompt):at.set();assert release.wait(5);return original(prompt)
    monkeypatch.setattr(agent.runtime.provider,'_text',text)
    def work():
        try:agent.extract(nid,cid,v,project_incarnation=binding['project_incarnation'])
        except Exception as exc:errors.append(exc)
    t=Thread(target=work);t.start();assert at.wait(5)
    before=bundle.generations._job_path(binding['job_id']).read_bytes()
    replace_memory_owner(tmp_path,bundle,nid)
    replacement=project_bytes(tmp_path,nid)
    release.set();t.join(5)
    assert not t.is_alive() and errors
    assert bundle.generations._job_path(binding['job_id']).read_bytes()==before
    assert project_bytes(tmp_path,nid)==replacement

def test_failed_retry_enqueue_uses_same_owner_identity(tmp_path,memory_settings,monkeypatch):
    import app.lore.memory_agent as module
    agent,bundle,nid,cid,v,owner,binding=setup(tmp_path)
    agent.runtime.provider.text='invalid'
    with pytest.raises(Exception):agent.extract(nid,cid,v,project_incarnation=binding['project_incarnation'])
    agent.runtime.provider.text=json.dumps(valid_output());pending=[]
    class Delayed(Thread):
        def start(self):pending.append(self)
    monkeypatch.setattr(module.threading,'Thread',Delayed)
    jid=agent.enqueue(nid,cid,v,project_incarnation=binding['project_incarnation'])
    assert jid==binding['job_id'] and len(pending)==1
    pending[0].run()
    assert bundle.generations.get(jid)['status']=='COMPLETED'
    assert agent.enqueue(nid,cid,v,project_incarnation=binding['project_incarnation'])==jid and len(pending)==1

def test_postgres_explicit_bound_refusal_before_database(tmp_path):
    from app.repositories.postgres.generation import PostgresGenerationRepository
    from app.repositories.generation_repository import GenerationProjectIdentityError
    *_,binding=setup(tmp_path)
    class NoDatabase:
        def session(self):raise AssertionError('PG must not be touched')
    with pytest.raises(GenerationProjectIdentityError,match='MEMORY_POSTGRES_UNSUPPORTED'):
        PostgresGenerationRepository(NoDatabase()).save(record(binding))

def test_runtime_observers_run_after_owner_lease(tmp_path,memory_settings):
    from app.runtime_events import runtime_events
    from app.file_project_lifecycle import project_operation
    agent,bundle,nid,cid,v,owner,binding=setup(tmp_path)
    observations=[]; workers=[]
    def callback(change):
        if change.module!='TASK' or change.entity_id!=binding['job_id']:return
        acquired=Event()
        def acquire():
            with project_operation(tmp_path,nid):acquired.set()
        worker=Thread(target=acquire);workers.append(worker);worker.start()
        observations.append(acquired.wait(1))
    unsubscribe=runtime_events.subscribe(callback)
    try:agent.extract(nid,cid,v,project_incarnation=binding['project_incarnation'])
    finally:unsubscribe()
    for worker in workers:worker.join(5)
    assert len(observations)==2 and all(observations), 'observer ran while original project lock held'

@pytest.mark.parametrize('change',['remove','null','mixed','bool'])
def test_invalid_update_keeps_original_row(tmp_path,change):
    from app.repositories.generation_repository import GenerationProjectIdentityError
    agent,bundle,nid,cid,v,owner,binding=setup(tmp_path)
    row=record(binding);bundle.generations.save(row)
    before=bundle.generations._job_path(binding['job_id']).read_bytes()
    if change=='remove':row.pop(FIELD)
    elif change=='null':row[FIELD]=None
    elif change=='mixed':row['ordinary_project_binding']=None
    else:row[FIELD]['chapter_version']=True
    with pytest.raises(GenerationProjectIdentityError):bundle.generations.save(row)
    assert bundle.generations._job_path(binding['job_id']).read_bytes()==before

@pytest.mark.parametrize('stage',['queued','adapter'])
def test_replaced_owner_refuses_before_model(tmp_path,memory_settings,monkeypatch,stage):
    import app.lore.memory_agent as module
    from test_bound_review_port_blockers import replace_memory_owner,project_bytes
    agent,bundle,nid,cid,v,owner,binding=setup(tmp_path);pending=[]
    if stage=='queued':
        class Delayed(Thread):
            def start(self):pending.append(self)
        monkeypatch.setattr(module.threading,'Thread',Delayed)
        agent.enqueue(nid,cid,v,project_incarnation=binding['project_incarnation'])
        replace_memory_owner(tmp_path,bundle,nid);before=project_bytes(tmp_path,nid)
        pending[0].run()
    else:
        original=agent.runtime.prepare_text_route
        snapshot=[]
        def prepare(*args):
            result=original(*args);replace_memory_owner(tmp_path,bundle,nid)
            snapshot.append(project_bytes(tmp_path,nid));return result
        monkeypatch.setattr(agent.runtime,'prepare_text_route',prepare)
        with pytest.raises(Exception):agent.extract(nid,cid,v,project_incarnation=binding['project_incarnation'])
        before=snapshot[0]
    assert agent.runtime.provider.calls==[]
    assert project_bytes(tmp_path,nid)==before

def test_root_rotation_before_final_commit_fails_without_lore(tmp_path,memory_settings,monkeypatch):
    from app.repositories.generation_repository import GenerationProjectIdentityError
    agent,bundle,nid,cid,v,owner,binding=setup(tmp_path)
    original=agent.runtime.provider._text
    def text(prompt):
        bundle.generations.root=tmp_path/'wrong/runtime/jobs'
        return original(prompt)
    monkeypatch.setattr(agent.runtime.provider,'_text',text)
    with pytest.raises(GenerationProjectIdentityError,match='STORE_MISMATCH'):
        agent.extract(nid,cid,v,project_incarnation=binding['project_incarnation'])
    assert not (tmp_path/'wrong').exists()
    assert bundle.lore.list_proposals(nid)==[] and bundle.lore.list_evidence(nid)==[]

def test_bound_local_error_never_remote_fallback(tmp_path,memory_settings):
    from test_memory_agent_contract import Runtime,MemoryMockProvider,UnverifiedProvider
    from app.providers import ProviderError
    from app.model_runtime import ProviderDescriptor,ModelDescriptor,Modality,LegacyTextProviderAdapter,ModelRuntimeError
    from app.lore.memory_project_binding import create_binding
    from app.creative.project_store import CreativeProjectStore
    from types import SimpleNamespace
    class Fail(MemoryMockProvider):
        def _text(self,prompt):self.calls.append(prompt);raise ProviderError('synthetic failure')
    runtime=Runtime('',provider=Fail(''));remote=UnverifiedProvider()
    runtime.provider_registry.register(ProviderDescriptor('remote','Forbidden','remote',frozenset({Modality.TEXT}),True,True),LegacyTextProviderAdapter('remote',remote))
    runtime.model_registry.register(ModelDescriptor('remote-model','remote','Remote',Modality.TEXT,frozenset({'generate'})))
    agent,bundle,nid,cid,v=runner(tmp_path,valid_output(),runtime=runtime)
    owner=CreativeProjectStore(SimpleNamespace(backend='file',root=tmp_path));binding=create_binding(nid,cid,v,owner.incarnation(nid))
    with pytest.raises(ModelRuntimeError):agent.extract(nid,cid,v,project_incarnation=binding['project_incarnation'])
    assert len(runtime.provider.calls)==1 and remote.calls==[]
    assert bundle.generations.get(binding['job_id'])['status']=='FAILED'

def test_failed_old_owner_cannot_retry_into_replacement(tmp_path,memory_settings,monkeypatch):
    import app.lore.memory_agent as module
    from test_bound_review_port_blockers import replace_memory_owner,project_bytes
    agent,bundle,nid,cid,v,owner,binding=setup(tmp_path)
    agent.runtime.provider.text='invalid'
    with pytest.raises(Exception):agent.extract(nid,cid,v,project_incarnation=binding['project_incarnation'])
    old=bundle.generations._job_path(binding['job_id']).read_bytes()
    replacement,_,_=replace_memory_owner(tmp_path,bundle,nid);before=project_bytes(tmp_path,nid)
    with pytest.raises(Exception):agent.enqueue(nid,cid,v,project_incarnation=binding['project_incarnation'])
    assert bundle.generations._job_path(binding['job_id']).read_bytes()==old and project_bytes(tmp_path,nid)==before
    pending=[]
    class Delayed(Thread):
        def start(self):pending.append(self)
    monkeypatch.setattr(module.threading,'Thread',Delayed)
    new_id=replacement.enqueue(nid,cid,v,project_incarnation=owner.incarnation(nid))
    assert new_id!=binding['job_id']
    pending[0].run();assert bundle.generations.get(new_id)['status']=='COMPLETED'

def test_wrong_file_port_refused_before_dispatch(tmp_path,memory_settings):
    from app.repositories.generation_repository import GenerationProjectIdentityError
    agent,bundle,nid,cid,v,owner,binding=setup(tmp_path)
    other,*_=runner(tmp_path/'other',valid_output())
    agent.lore=other.lore
    with pytest.raises(GenerationProjectIdentityError,match='STORE_MISMATCH'):
        agent.extract(nid,cid,v,project_incarnation=binding['project_incarnation'])
    assert agent.runtime.provider.calls==[] and not bundle.generations._job_path(binding['job_id']).exists()

def test_legacy_delayed_counterexample_remains(tmp_path,memory_settings,monkeypatch):
    import app.lore.memory_agent as module
    from test_bound_review_port_blockers import replace_memory_owner
    agent,bundle,nid,cid,v,owner,binding=setup(tmp_path);pending=[]
    class Delayed(Thread):
        def start(self):pending.append(self)
    monkeypatch.setattr(module.threading,'Thread',Delayed)
    jid=agent.enqueue(nid,cid,v)
    replace_memory_owner(tmp_path,bundle,nid)
    pending[0].run()
    assert bundle.generations.get(jid)['status']=='COMPLETED'
    assert len(bundle.lore.list_proposals(nid))==1
    assert FIELD not in bundle.generations.get(jid)
