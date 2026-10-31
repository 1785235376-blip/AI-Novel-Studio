"""Final original-port fences, including reentrant real lifecycle operations."""
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.repositories.file.lore import FileLoreRepository
from app.repositories.file.chapter import FileChapterRepository
from app.repository import FileRepository
from app.lore.file_memory_ports import _FileMemoryPorts
from test_bound_memory_project_owner import setup
from test_bound_review_port_blockers import replace_memory_owner, project_bytes
from test_memory_agent_contract import memory_settings, runner, valid_output

pytestmark = pytest.mark.file_backend_only


@pytest.mark.parametrize('seam', ['service_evidence','repository_evidence','repository_proposal',
                                  'repository_relation','terminal_receipt','source_chapter','source_snapshot'])
def test_final_original_port_refuses_reentrant_replacement(tmp_path, memory_settings, monkeypatch, seam):
    agent,bundle,nid,cid,version,owner,binding=setup(tmp_path)
    target,name={
        'service_evidence':(agent.lore,'create_evidence'),
        'repository_evidence':(bundle.lore,'create_evidence'),
        'repository_proposal':(bundle.lore,'create_proposal'),
        'repository_relation':(bundle.lore,'link_evidence'),
        'terminal_receipt':(bundle.generations,'save'),
        'source_chapter':(bundle.chapters,'get'),
        'source_snapshot':(bundle.lore,'get_latest_snapshot'),
    }[seam]
    original=getattr(target,name);replacement={};fired=[]
    def replace_then_original(*args,**kwargs):
        relevant=seam!='terminal_receipt' or args[0].get('status')=='COMPLETED'
        if relevant and not fired:
            fired.append(True)
            replace_memory_owner(tmp_path,bundle,nid)
            assert owner.incarnation(nid)!=binding['project_incarnation']
            replacement.update(project_bytes(tmp_path,nid))
        return original(*args,**kwargs)
    monkeypatch.setattr(target,name,replace_then_original)
    with pytest.raises((ValueError,FileNotFoundError)):
        agent.extract(nid,cid,version,project_incarnation=binding['project_incarnation'])
    assert fired==[True]
    assert project_bytes(tmp_path,nid)==replacement
    assert not list((tmp_path/'novels'/nid/'lore'/'evidence').glob('*.json'))
    assert not list((tmp_path/'novels'/nid/'lore'/'proposals').glob('*.json'))
    with pytest.raises(KeyError):bundle.generations.get(binding['job_id'])
    assert len(agent.runtime.provider.calls)==(0 if seam.startswith('source_') else 1)


@pytest.mark.parametrize('rotation', ['same_root_repository','same_root_backend','other_root_repository',
                                     'other_root_backend','chapter_repository','generation_service'])
def test_late_original_port_rotation_never_follows_replacement(tmp_path,memory_settings,monkeypatch,rotation):
    agent,bundle,nid,cid,version,owner,binding=setup(tmp_path)
    other,other_bundle,*_=runner(tmp_path/'other',valid_output())
    # Give the unrelated root a different genuine incarnation.
    from app.creative.project_store import CreativeProjectStore
    other_owner=CreativeProjectStore(SimpleNamespace(backend='file',root=tmp_path/'other'))
    assert other_owner.incarnation(nid)!=binding['project_incarnation']
    before_other={str(p.relative_to(tmp_path/'other')):p.read_bytes() for p in (tmp_path/'other').rglob('*') if p.is_file()}
    original=agent.lore.create_evidence;fired=[]
    def rotate_then_original(*args,**kwargs):
        fired.append(True)
        if rotation=='same_root_repository':agent.lore.repository=FileLoreRepository(bundle.lore.backend)
        elif rotation=='same_root_backend':bundle.lore.backend=FileRepository(tmp_path)
        elif rotation=='other_root_repository':agent.lore.repository=other_bundle.lore
        elif rotation=='other_root_backend':bundle.lore.backend=other_bundle.lore.backend
        elif rotation=='chapter_repository':agent.chapters=FileChapterRepository(bundle.chapters.backend)
        else:agent.generations=other.generations
        return original(*args,**kwargs)
    monkeypatch.setattr(agent.lore,'create_evidence',rotate_then_original)
    with pytest.raises(ValueError,match='STORE_MISMATCH'):
        agent.extract(nid,cid,version,project_incarnation=binding['project_incarnation'])
    assert fired==[True] and len(agent.runtime.provider.calls)==1
    assert before_other=={str(p.relative_to(tmp_path/'other')):p.read_bytes() for p in (tmp_path/'other').rglob('*') if p.is_file()}
    assert not list((tmp_path/'novels'/nid/'lore'/'evidence').glob('*.json'))
    assert not list((tmp_path/'novels'/nid/'lore'/'proposals').glob('*.json'))
    assert bundle.generations.get(binding['job_id'])['status']=='GENERATING'


def test_private_expectation_data_is_immutable_and_rejects_other_targets(tmp_path,memory_settings):
    from dataclasses import FrozenInstanceError
    agent,bundle,nid,cid,version,owner,binding=setup(tmp_path)
    expected=_FileMemoryPorts(agent,binding)
    with pytest.raises(FrozenInstanceError):expected.root=tmp_path/'other'
    with pytest.raises(TypeError):expected.binding['project_incarnation']='file:fake'
    with pytest.raises(ValueError):expected.check(FileLoreRepository(bundle.lore.backend))
    # No arbitrary callable is accepted by the final original service guard.
    with pytest.raises(ValueError,match='PORTS_REQUIRED'):
        agent.lore.create_evidence({},_file_memory=lambda:None)
