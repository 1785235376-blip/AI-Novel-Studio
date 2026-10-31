import json,socket
import pytest
from test_bound_memory_project_owner import setup
from test_memory_agent_contract import runner,valid_output,memory_settings
from test_bound_review_port_blockers import replace_memory_owner

@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def denied(*a,**kw):raise AssertionError('network disabled')
    monkeypatch.setattr(socket.socket,'connect',denied)
    monkeypatch.setattr(socket,'create_connection',denied)

@pytest.mark.parametrize('port',['service_evidence','repository_evidence','repository_proposal'])
def test_same_thread_owner_replacement_counterexample(tmp_path,memory_settings,monkeypatch,port):
    agent,bundle,nid,cid,v,owner,binding=setup(tmp_path)
    target,name={'service_evidence':(agent.lore,'create_evidence'),'repository_evidence':(bundle.lore,'create_evidence'),'repository_proposal':(bundle.lore,'create_proposal')}[port]
    original=getattr(target,name);replaced=[]
    def replace_then_write(item, **kwargs):
        replace_memory_owner(tmp_path,bundle,nid)
        replaced.append(owner.incarnation(nid))
        return original(item, **kwargs)
    monkeypatch.setattr(target,name,replace_then_write)
    with pytest.raises((ValueError,FileNotFoundError)) as caught:
        agent.extract(nid,cid,v,project_incarnation=binding['project_incarnation'])
    assert replaced and replaced[0]!=binding['project_incarnation']
    rows=bundle.lore.list_proposals(nid) if port=='repository_proposal' else bundle.lore.list_evidence(nid)
    print('REFUSED',port,'replacement durable count',len(rows),'error',type(caught.value).__name__,str(caught.value))
    assert len(rows)==0,'replacement contamination remains'
    assert len(agent.runtime.provider.calls)==1
    raw=json.loads(bundle.generations._job_path(binding['job_id']).read_text())
    assert raw['status']=='GENERATING'

@pytest.mark.parametrize('rotation',['facade_same_root','backend_same_root','facade_other_root'])
def test_final_port_rotation_counterexample(tmp_path,memory_settings,monkeypatch,rotation):
    from app.repositories.factory import create_repository_bundle
    from app.config import Settings
    agent,bundle,nid,cid,v,owner,binding=setup(tmp_path)
    if rotation=='facade_other_root':
        other,other_bundle,*_=runner(tmp_path/'other',valid_output())
    else:
        other_bundle=create_repository_bundle(Settings(storage_backend='file',novel_data=tmp_path),tmp_path)
    original=agent.lore.create_evidence
    def rotate_then_write(item, **kwargs):
        if rotation=='backend_same_root':bundle.lore.backend=other_bundle.lore.backend
        else:agent.lore.repository=other_bundle.lore
        return original(item, **kwargs)
    monkeypatch.setattr(agent.lore,'create_evidence',rotate_then_write)
    with pytest.raises(ValueError,match='STORE_MISMATCH'):
        agent.extract(nid,cid,v,project_incarnation=binding['project_incarnation'])
    raw=bundle.generations.get(binding['job_id'])
    assert raw['status']=='GENERATING'
    assert len(other_bundle.lore.list_evidence(nid))==len(other_bundle.lore.list_proposals(nid))==0
    print('REFUSED',rotation,'no evidence/proposal writes, receipt remains GENERATING')
    if rotation=='facade_other_root':
        assert bundle.lore.list_evidence(nid)==[] and bundle.lore.list_proposals(nid)==[]
