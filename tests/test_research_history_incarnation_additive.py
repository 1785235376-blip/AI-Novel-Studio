"""Real project reincarnation must not authorize old historical research text."""
import copy
import pytest

from app.experimental.research_library import ResearchLibraryService
from test_v2_creative_project_lifecycle import rig, TITLE
from test_r4_research_library import payload, citation


def test_same_public_id_and_author_cannot_read_previous_project_history(rig):
    e = rig
    service = ResearchLibraryService(e.store, e.novels, e.chapters, historical_inspection=True)
    row = service.import_file(e.nid, e.scope, e.actor,
                              payload('Private first-incarnation evidence.'), guard=lambda: None)
    service.replace_file(e.nid, e.scope, e.actor, row['id'],
                         {**payload('Current replacement.'), 'expected_version': 1}, guard=lambda: None)
    ref = citation(row)
    assert service.inspect_history(e.nid, e.scope, e.actor, row['id'], 2, ref)['text'] == 'Private first-incarnation evidence.'
    saved = copy.deepcopy(e.store.read(e.nid, e.scope))
    old_id = e.nid
    e.novels.delete(old_id)
    assert e.novels.create({'title': TITLE})['id'] == old_id
    assert e.store.read(e.nid, e.scope) == saved
    with pytest.raises(FileNotFoundError):
        service.inspect_history(e.nid, e.scope, e.actor, row['id'], 2, ref)
    assert e.store.read(e.nid, e.scope) == saved


@pytest.mark.parametrize('location', ['current', 'revision', 'both'])
def test_unbound_history_is_not_adopted_or_rewritten(rig, location):
    e = rig
    service = ResearchLibraryService(e.store, e.novels, e.chapters, historical_inspection=True)
    row = service.import_file(e.nid, e.scope, e.actor, payload(), guard=lambda: None)
    service.replace_file(e.nid, e.scope, e.actor, row['id'],
                         {**payload('Replacement'), 'expected_version': 1}, guard=lambda: None)
    with e.store.transaction(e.nid, e.scope) as state:
        source = state['collections']['research_sources'][row['id']]
        if location in {'current', 'both'}: source.pop('research_project_incarnation')
        if location in {'revision', 'both'}: source['history'][0].pop('research_project_incarnation')
    before = copy.deepcopy(e.store.read(e.nid, e.scope))
    with pytest.raises(FileNotFoundError):
        service.inspect_history(e.nid, e.scope, e.actor, row['id'], 2, citation(row))
    assert e.store.read(e.nid, e.scope) == before


def test_new_incarnation_can_create_and_inspect_its_own_history(rig):
    e = rig
    service = ResearchLibraryService(e.store, e.novels, e.chapters, historical_inspection=True)
    identities = []
    for index in range(2):
        row = service.import_file(e.nid, e.scope, e.actor, payload(f'Generation {index}'), guard=lambda: None)
        service.replace_file(e.nid, e.scope, e.actor, row['id'],
                             {**payload('Replacement'), 'expected_version': 1}, guard=lambda: None)
        assert service.inspect_history(e.nid, e.scope, e.actor, row['id'], 2, citation(row))['text'] == f'Generation {index}'
        identities.append(service.history_identity(e.nid))
        if index == 0:
            e.novels.delete(e.nid)
            assert e.novels.create({'title': TITLE})['id'] == e.nid
    assert identities[0] != identities[1]


def test_recreated_during_extraction_cannot_receive_old_import(rig, monkeypatch):
    import app.experimental.research_library as module
    e = rig
    service = ResearchLibraryService(e.store, e.novels, e.chapters, historical_inspection=True)
    original = module.extract_document
    before = copy.deepcopy(e.store.read(e.nid, e.scope))
    def extract(*args):
        value = original(*args)
        e.novels.delete(e.nid)
        assert e.novels.create({'title': TITLE})['id'] == e.nid
        return value
    monkeypatch.setattr(module, 'extract_document', extract)
    with pytest.raises(FileNotFoundError):
        service.import_file(e.nid, e.scope, e.actor, payload(), guard=lambda: None)
    assert e.store.read(e.nid, e.scope) == before
