"""M5 v1 trusted drafts and real Mock memory; no new admission or dispatch."""
from contextlib import contextmanager
import json

import pytest

from test_file_local_bound_review import bound, source, memory_settings
from test_passive_generation_manager_binding import _replace_owner
from test_bound_memory_project_owner import setup
from test_bound_review_port_blockers import replace_memory_owner, project_bytes

pytestmark = pytest.mark.file_backend_only


@pytest.mark.parametrize('status,operation', [('ACCEPTING','accept'), ('ACCEPTED','accept'), ('REJECTED','reject')])
def test_manual_after_owner_entry_keeps_original_receipt(bound, monkeypatch, status, operation):
    repo=bound.bundle.generations
    original=repo._graph_owner
    seen={}
    @contextmanager
    def replace_after_entry(item,binding):
        with original(item,binding):
            if item.get('status')==status and not seen:
                seen['receipt']=repo._job_path(item['id']).read_bytes()
                _replace_owner(bound)
                seen['project']=project_bytes(bound.root,item['novel_id'])
            yield
    monkeypatch.setattr(repo,'_graph_owner',replace_after_entry)
    with pytest.raises((ValueError,KeyError,FileNotFoundError)):
        getattr(bound.review_manager,operation)(bound.row['id'])
    assert seen
    assert repo._job_path(bound.row['id']).read_bytes()==seen['receipt']
    assert project_bytes(bound.root,bound.row['novel_id'])==seen['project']


def test_memory_after_owner_entry_keeps_generating_receipt(tmp_path,memory_settings,monkeypatch):
    agent,bundle,nid,cid,version,owner,binding=setup(tmp_path)
    repo=bundle.generations
    original=repo._graph_owner
    seen={}
    @contextmanager
    def replace_after_entry(item,current):
        with original(item,current):
            if item.get('status')=='COMPLETED' and not seen:
                seen['receipt']=repo._job_path(item['id']).read_bytes()
                replace_memory_owner(tmp_path,bundle,nid)
                seen['project']=project_bytes(tmp_path,nid)
            yield
    monkeypatch.setattr(repo,'_graph_owner',replace_after_entry)
    with pytest.raises((ValueError,KeyError,FileNotFoundError)):
        agent.extract(nid,cid,version,project_incarnation=binding['project_incarnation'])
    assert len(agent.runtime.provider.calls)==1
    assert seen and json.loads(seen['receipt'])['status']=='GENERATING'
    assert repo._job_path(binding['job_id']).read_bytes()==seen['receipt']
    assert project_bytes(tmp_path,nid)==seen['project']


def test_manual_rotated_root_refuses_without_new_owner_lock(bound,monkeypatch):
    from app.repositories.file import mutation_coordinator
    repo=bound.bundle.generations
    original=repo._graph_owner
    old_root=repo.root
    other=bound.root/'other'/'runtime/jobs'
    other.mkdir(parents=True)
    seen=[]
    mutation=mutation_coordinator.workspace_mutation
    @contextmanager
    def observed(data,key):
        seen.append((str(data),key))
        with mutation(data,key):yield
    @contextmanager
    def rotate_after_entry(item,binding):
        with original(item,binding):
            if item.get('status')=='ACCEPTING':repo.root=other
            yield
    monkeypatch.setattr(mutation_coordinator,'workspace_mutation',observed)
    monkeypatch.setattr(repo,'_graph_owner',rotate_after_entry)
    before=repo._job_path(bound.row['id']).read_bytes()
    try:
        with pytest.raises(ValueError):bound.review_manager.accept(bound.row['id'])
        assert not list(other.glob('*.json'))
        assert (old_root/(bound.row['id']+'.json')).read_bytes()==before
        assert not any(data in {str(other),str(other.parent.parent)} for data,key in seen)
    finally:repo.root=old_root
