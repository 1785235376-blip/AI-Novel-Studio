"""M5 v1 receipt fence: original owners, legitimate post-owner-entry seam."""
from contextlib import contextmanager
import json
from pathlib import Path
import pytest
from test_file_local_bound_review import bound, source, memory_settings
from test_bound_memory_project_owner import setup
from test_bound_review_port_blockers import replace_memory_owner
from test_passive_generation_manager_binding import _replace_owner


def project_files(root,nid):
    return {str(p.relative_to(root)):p.read_bytes() for p in (root/'novels'/nid).rglob('*') if p.is_file()}

@pytest.mark.parametrize('terminal',['ACCEPTING','ACCEPTED'])
def test_manual_receipt_after_owner_entry_replacement_does_not_write(bound,monkeypatch,terminal):
    repo=bound.bundle.generations;jid=bound.row['id'];original=repo._graph_owner
    before=[];replacement={};seen=[];old_path=repo._job_path(jid)
    @contextmanager
    def seam(item,binding):
        with original(item,binding):
            if item['id']==jid and item['status']==terminal and not seen:
                before.append(old_path.read_bytes());seen.append(True)
                _replace_owner(bound)
                replacement.update(project_files(bound.root,bound.row['novel_id']))
            yield
    monkeypatch.setattr(repo,'_graph_owner',seam)
    try:bound.review_manager.accept(jid)
    except Exception:pass
    assert seen, 'terminal seam was not reached'
    assert project_files(bound.root,bound.row['novel_id'])==replacement
    actual=old_path.read_bytes()
    assert actual==before[0], f"stale manual receipt written: {json.loads(actual)['status']}"

@pytest.mark.parametrize('terminal',['GENERATING','COMPLETED'])
def test_memory_receipt_after_owner_entry_replacement_does_not_write(tmp_path,memory_settings,monkeypatch,terminal):
    agent,bundle,nid,cid,version,owner,binding=setup(tmp_path)
    repo=bundle.generations;jid=binding['job_id'];original=repo._graph_owner
    path=repo._job_path(jid);before=[];replacement={};seen=[]
    @contextmanager
    def seam(item,current):
        with original(item,current):
            if item['id']==jid and item['status']==terminal and not seen:
                before.append(path.read_bytes() if path.exists() else None);seen.append(True)
                replace_memory_owner(tmp_path,bundle,nid)
                replacement.update(project_files(tmp_path,nid))
            yield
    monkeypatch.setattr(repo,'_graph_owner',seam)
    try:agent.extract(nid,cid,version,project_incarnation=binding['project_incarnation'])
    except Exception:pass
    assert seen,'terminal seam was not reached'
    assert project_files(tmp_path,nid)==replacement
    actual=path.read_bytes() if path.exists() else None
    assert actual==before[0], f"stale memory receipt written: {json.loads(actual)['status'] if actual else None}"


def test_manual_root_rotation_after_entry_preserves_receipt_and_lock_root(bound,monkeypatch):
    repo=bound.bundle.generations;jid=bound.row['id'];old_root=repo.root;path=repo._job_path(jid)
    foreign=bound.root/'foreign'/'runtime'/'jobs';foreign.mkdir(parents=True)
    original=repo._graph_owner;seen=[];before=[];foreign_locks=[]
    import app.repositories.file.mutation_coordinator as coordinator
    original_lock=coordinator.workspace_mutation
    @contextmanager
    def locks(root,key):
        if seen and Path(root).resolve()==foreign.resolve():foreign_locks.append(key)
        with original_lock(root,key):yield
    @contextmanager
    def seam(item,binding):
        with original(item,binding):
            if item['id']==jid and item['status']=='ACCEPTED' and not seen:
                seen.append(True);before.append(path.read_bytes());repo.root=foreign
            yield
    monkeypatch.setattr(coordinator,'workspace_mutation',locks)
    monkeypatch.setattr(repo,'_graph_owner',seam)
    try:
        try:bound.review_manager.accept(jid)
        except Exception:pass
        assert seen
        assert path.read_bytes()==before[0]
        assert not list(foreign.glob('*.json'))
        assert not foreign_locks,foreign_locks
    finally:repo.root=old_root

@pytest.mark.parametrize('rotation',['lore_facade','generation_root'])
def test_memory_port_rotation_after_entry_preserves_receipt(tmp_path,memory_settings,monkeypatch,rotation):
    from app.services import LoreService
    agent,bundle,nid,cid,version,owner,binding=setup(tmp_path)
    repo=bundle.generations;jid=binding['job_id'];old_root=repo.root;path=repo._job_path(jid)
    original=repo._graph_owner;seen=[];before=[];foreign=tmp_path/'foreign'/'runtime'/'jobs';foreign.mkdir(parents=True)
    @contextmanager
    def seam(item,current):
        with original(item,current):
            if item['id']==jid and item['status']=='COMPLETED' and not seen:
                seen.append(True);before.append(path.read_bytes())
                if rotation=='lore_facade':agent.lore=LoreService(bundle.lore)
                else:repo.root=foreign
            yield
    monkeypatch.setattr(repo,'_graph_owner',seam)
    try:
        try:agent.extract(nid,cid,version,project_incarnation=binding['project_incarnation'])
        except Exception:pass
        assert seen
        assert path.read_bytes()==before[0]
        assert not list(foreign.glob('*.json'))
    finally:repo.root=old_root


def test_final_fence_runs_under_original_owner_and_leaf_for_manual_and_memory(bound,monkeypatch):
    repo=bound.bundle.generations;original=repo._check_expected_save_owner;observed=[]
    import app.repositories.file.mutation_coordinator as coordinator
    def check(item,binding,expected_root,file_memory):
        if expected_root is not None or file_memory is not None:
            depths=dict(getattr(coordinator._thread_state,'depths',{}))
            assert any(key[0]==str(bound.root.resolve()) and key[1].startswith('project-lifecycle:') for key in depths),depths
            assert any(key[0]==str(repo.root.resolve()) and key[1].startswith('generation-write:') for key in depths),depths
            observed.append((item['operation'],item['status']))
        return original(item,binding,expected_root,file_memory)
    monkeypatch.setattr(repo,'_check_expected_save_owner',check)
    result=bound.review_manager.accept(bound.row['id'])
    assert result['chapter'] and result['pending_canon']
    assert bound.memory_finished.wait(10)
    assert ('continue','ACCEPTED') in observed
    assert ('MEMORY_EXTRACTION','COMPLETED') in observed
