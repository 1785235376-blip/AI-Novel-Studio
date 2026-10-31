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
    def fail(item): raise OSError('synthetic one-time relation write failure')
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
    def save(item):
        if item['status']=='FAILED':
            at.set(); assert release.wait(5)
        return original(item)
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
