import json,socket
import pytest
from test_file_local_bound_review import bound
from test_passive_generation_manager_binding import source
from test_memory_agent_contract import memory_settings

@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def denied(*args,**kwargs):raise AssertionError('network prohibited')
    monkeypatch.setattr(socket.socket,'connect',denied)
    monkeypatch.setattr(socket,'create_connection',denied)

@pytest.mark.parametrize('memory_result',['valid','invalid'])
def test_manual_accept_original_memory_receipt_and_relations(bound,memory_result):
    cid=bound.row['novel_id']+':2'
    output={'proposals':[{'proposal_type':'EVENT','payload':{'description':'RETAINED_DRAFT'},'confidence':.9,'evidence':[{'chapter_id':cid,'chapter_version':1,'excerpt':'RETAINED_DRAFT','locator':{'kind':'DOCUMENT_RANGE','from':0,'to':14}}]}]}
    bound.memory.runtime.provider.text=json.dumps(output) if memory_result=='valid' else 'invalid JSON'
    accepted=bound.review_manager.accept(bound.row['id'])
    assert accepted['chapter']['id']==cid and accepted['pending_canon']
    assert bound.memory_finished.wait(10)
    assert bound.persistence.get(bound.row['id'])['status']=='ACCEPTED'
    receipts=[r for r in bound.bundle.generations.load_all() if r.get('operation')=='MEMORY_EXTRACTION']
    assert len(receipts)==1
    receipt=receipts[0]
    assert receipt['memory_project_binding']['project_incarnation']==bound.incarnation
    assert receipt['chapter_id']==cid and len(bound.memory.runtime.provider.calls)==1
    proposals=bound.bundle.lore.list_proposals(bound.row['novel_id'])
    if memory_result=='invalid':
        assert receipt['status']=='FAILED' and proposals==[]
        assert bound.bundle.lore.list_evidence(bound.row['novel_id'])==[]
    else:
        assert receipt['status']=='COMPLETED' and len(proposals)==1
        assert proposals[0]['generation_job_id']==receipt['id'] and proposals[0]['status']=='PENDING'
        relations=bound.bundle.lore.list_proposal_evidence(proposals[0]['id'])
        assert len(relations)==1
        assert bound.bundle.lore.get_evidence(relations[0]['evidence_id'])['excerpt']=='RETAINED_DRAFT'
        assert receipt['result']['proposal_ids']==[proposals[0]['id']]
