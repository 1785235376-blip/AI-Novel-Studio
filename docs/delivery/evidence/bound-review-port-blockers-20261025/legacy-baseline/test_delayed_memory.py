"""Baseline-only scheduling observations; original worker, accept, enqueue and writes."""
import json
import time
from threading import Event
from pathlib import Path
import pytest
from app import jobs as jobs_module
from app.lore import memory_agent as memory_module
from app.agents import AgentRegistry, AgentRunner
from app.config import Settings
from app.providers import MockProvider
from app.runtime import Runtime
from app.stable_identity import StableIdentityStore
from app.repositories.factory import create_repository_bundle
from app.services import NovelService, ChapterService, CanonService, ContextService, GenerationService, LoreService
from app.services.generation_idempotency_authority import GenerationIdempotencyAuthority
from app.lore.memory_agent import MemoryAgentRunner
from app.jobs import JobManager
from test_memory_agent_contract import Runtime as MemoryRuntime

@pytest.mark.parametrize('gate', ['before_extract', 'before_evidence_write'])
def test_delayed_memory_crosses_replacement_owner(tmp_path, monkeypatch, gate):
    config=Settings(storage_backend='file', novel_data=tmp_path, mock_provider=True, enable_cloud=False, enable_collaboration_runtime=False, enable_packaged_runtime=False)
    monkeypatch.setattr(jobs_module,'settings',config)
    monkeypatch.setattr(memory_module,'settings',config)
    bundle=create_repository_bundle(config,tmp_path)
    novels=NovelService(bundle.novels,bundle.chapters); chapters=ChapterService(bundle.chapters)
    nid=novels.create({'id':'delayed-book','title':'Original owner'})['id']
    cid=chapters.create(nid,{'title':'One','content':'Original opening.'})['id']
    authority=GenerationIdempotencyAuthority(novels,chapters)
    old_owner=authority.capture_new(nid)
    runtime=Runtime(StableIdentityStore(tmp_path/'runtime'/'identities.json'))
    runtime.providers['mock']=MockProvider(delay_ms=0)
    runtime._sync_model('mock','mock-writer')
    monkeypatch.setattr(jobs_module,'runtime',runtime)
    lore=LoreService(bundle.lore)
    memory_runtime=MemoryRuntime('{}')
    memory=MemoryAgentRunner(bundle.novels,bundle.chapters,lore,GenerationService(bundle.generations),AgentRunner(AgentRegistry()),memory_runtime)
    entered, release, finished=Event(),Event(),Event()
    errors=[]
    original_quiet=memory._quiet_extract
    def quiet(*args):
        try:
            if gate=='before_extract':
                entered.set(); assert release.wait(15)
            original_quiet(*args)
        finally: finished.set()
    monkeypatch.setattr(memory,'_quiet_extract',quiet)
    original_evidence=lore.create_evidence
    def write_evidence(item):
        entered.set(); assert release.wait(15)
        return original_evidence(item)
    if gate=='before_evidence_write': monkeypatch.setattr(lore,'create_evidence',write_evidence)
    manager=JobManager(generations=GenerationService(bundle.generations), chapters=chapters, contexts=ContextService(bundle.novels,bundle.chapters,lore), canon=CanonService(bundle.canon), memory_extractor=memory, snapshot_required=False)
    job=manager.create('continue',{'novel_id':nid,'chapter_id':cid,'instruction':'Continue','profile':'LOCAL_ONLY','provider_id':'mock','model_id':'mock-writer'})
    deadline=time.monotonic()+15
    while job.status not in manager.terminal and time.monotonic()<deadline: time.sleep(.01)
    assert job.status=='COMPLETED',job.public()
    quote=job.output.strip().splitlines()[0]
    memory_runtime.provider.text=json.dumps({'proposals':[{'proposal_type':'EVENT','payload':{'event':'Synthetic offline extracted event'},'confidence':.9,'evidence':[{'chapter_id':nid+':2','chapter_version':1,'excerpt':quote,'locator':{'kind':'DOCUMENT_RANGE','from':1,'to':len(quote)}}]}]})
    adopted=manager.accept(job.id)
    assert job.status=='ACCEPTED'
    assert adopted['pending_canon']['status']=='PENDING'
    assert bundle.canon.get_pending(adopted['pending_canon']['id'])['status']=='PENDING'
    assert entered.wait(15)
    records=[r for r in bundle.generations.load_all() if r.get('operation')=='MEMORY_EXTRACTION']
    assert len(records)==1
    memory_id=records[0]['id']
    accepted=chapters.get(nid+':2')
    assert accepted['version']==1
    novels.delete(nid)
    novels.create({'id':nid,'title':'Replacement owner'})
    chapters.create(nid,{'title':'One','content':'Replacement opening.'})
    replacement_content=accepted['content'] if gate=='before_extract' else 'Entirely different replacement chapter.'
    chapters.create(nid,{'title':adopted['chapter']['title'],'content':replacement_content})
    new_owner=authority.capture_new(nid)
    assert new_owner!=old_owner
    assert bundle.lore.list_proposals(nid)==[]
    assert bundle.lore.list_evidence(nid)==[]
    release.set(); assert finished.wait(15)
    record=bundle.generations.get(memory_id)
    proposals=bundle.lore.list_proposals(nid); evidence=bundle.lore.list_evidence(nid)
    print(json.dumps({'gate':gate,'adoption':job.status,'old_owner':old_owner,'new_owner':new_owner,'memory_status':record['status'],'binding_present':'ordinary_project_binding' in record,'replacement_proposals':len(proposals),'replacement_evidence':len(evidence),'memory_calls':len(memory_runtime.provider.calls),'record':record},ensure_ascii=False))
    assert record['status']=='COMPLETED',record
    assert len(proposals)==len(evidence)==1
    assert proposals[0]['generation_job_id']==memory_id and proposals[0]['status']=='PENDING'
    assert bundle.lore.list_memories(nid)==[]
    if gate=='before_evidence_write':
        assert evidence[0]['excerpt'] not in chapters.get(nid+':2')['content']
