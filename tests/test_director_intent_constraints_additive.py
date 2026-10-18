"""Authored advisory intent on original File/PostgreSQL owners; no model call."""
from copy import deepcopy
import hashlib
import json

import pytest

from app.creative.models import DirectorVisualTarget
from app.creative.director_intent import project_director_intent
from test_v2_independent_workspace import rig
from test_v2_storyboard_director_proposal_loop import source_value, review_body

FIELDS = ('target_audience', 'target_platform', 'production_budget_constraints')
LEGACY = dict(style='Quiet', atmosphere='', reference_works=[], color='', rhythm='')
TARGET = dict(LEGACY, target_audience='First-time viewers', target_platform='Local screening',
              production_budget_constraints='Use existing sets; no paid cloud calls')


def test_legacy_serialization_and_five_response_schemas_keep_exact_identity():
    from app.creative.generation import director_output_schema
    from app.creative.storyboard_model import DirectorStoryboardModelOutput
    from app.creative.screenplay_model import DirectorScreenplaySceneOutput
    assert DirectorVisualTarget.model_validate(LEGACY).model_dump() == LEGACY
    for blank in ['', '   ', '\n\t']:
        assert DirectorVisualTarget.model_validate(dict(LEGACY, **dict.fromkeys(FIELDS, blank))).model_dump() == LEGACY
    assert DirectorVisualTarget.model_validate(dict(LEGACY, **dict.fromkeys(FIELDS))).model_dump() == LEGACY
    schemas = [director_output_schema(), director_output_schema(production=True),
               director_output_schema(production=True, planning=True),
               DirectorStoryboardModelOutput.model_json_schema(), DirectorScreenplaySceneOutput.model_json_schema()]
    # Independently captured immediately before this additive context extension.
    pins = ['b582b2a9e4ec8839103f1557e7002e326a17ad3090824cd62fc422b40fa1199d',
            '139e1174af3be3a717a99ba312b3df04bdb197897d2b02fef31f14a63c97d659',
            '78402bc5eff3e3cb81834c5d4cc0ccc5e33d630b059054ae9185a54852b73ca8',
            '674333af0f67d90f8d7af6284093b80b1ea591439b41c8281dcf835b826cae23',
            '7263335febb5d68396dcf63e4830265a7af7a6f1bf9b8687e288bdbdd084c241']
    assert [hashlib.sha256(json.dumps(s, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
            for s in schemas] == pins


@pytest.mark.parametrize('key', FIELDS)
@pytest.mark.parametrize('value', [True, 25, {}, [], 'x' * 2001])
def test_context_is_closed_bounded_authored_text(key, value):
    with pytest.raises(ValueError):
        DirectorVisualTarget.model_validate({**LEGACY, key: value}, strict=True)


def test_unicode_context_and_unknown_costs_are_preserved_without_authority():
    value = DirectorVisualTarget.model_validate({**TARGET, 'target_audience': '🎬' * 2000}).model_dump()
    assert value['target_audience'] == '🎬' * 2000
    source = {'visual_target': value}
    before = deepcopy(source)
    projected = project_director_intent(source)
    assert len(projected['fields']) == 7
    constraints = projected['production_constraints']
    assert constraints['cost_status'] == constraints['feasibility_status'] == 'UNKNOWN'
    assert constraints['execution_authority'] is False and constraints['advisory_only'] is True
    assert all(row['authored'] and row['source'] == 'visual_target.' + row['field'] for row in constraints['fields'])
    assert source == before
    assert all(not row['authored'] for row in project_director_intent({})['production_constraints']['fields'])
    with pytest.raises(ValueError):
        DirectorVisualTarget.model_validate({**TARGET, 'execution_authority': True})


def test_original_owner_proposal_prompt_review_edit_reopen_and_stale_bindings(rig):
    from app.creative.service import CreativeService, document_digest
    from app.creative.models import CreativeProductionDocumentIn
    from app.creative.storyboard_model import _storyboard_prompt_data as storyboard_prompt_data
    from app.creative.screenplay_model import screenplay_prompt_data
    from app.creative.proposals import director_output_digest
    from app.experimental.store import ExperimentalStore
    from app.experimental.common import StaleSourceError
    creative = rig.service.creative
    source = creative.create(rig.nid, rig.scope, rig.actor, source_value())
    proposal = creative.proposals.create(rig.nid, rig.scope, rig.actor, {
        'source_document_id': source['id'], 'expected_source_version': source['version'], 'visual_target': TARGET})
    assert proposal['visual_target'] == TARGET
    assert proposal['status'] == 'NEEDS_REVIEW' and proposal['provenance']['model_called'] is False
    assert storyboard_prompt_data(proposal, source)['visual_target'] == TARGET
    # Same full authored context reaches the independent screenplay model contract.
    screenplay = creative.create(rig.nid, rig.scope, rig.actor, {
        'mode': 'SCREENPLAY', 'source_independent': True, 'title': 'Authored screenplay',
        'scenes': [{'id': 'scene-a', 'sequence': 1, 'heading': 'ROOM', 'action': 'A visitor waits.'}]})
    sp = creative.proposals.create(rig.nid, rig.scope, rig.actor, {
        'source_document_id': screenplay['id'], 'expected_source_version': 1, 'visual_target': TARGET})
    assert screenplay_prompt_data(sp, screenplay)['visual_target'] == TARGET
    for key in FIELDS:
        changed = {**TARGET, key: TARGET[key] + ' edited'}
        assert director_output_digest(proposal['director_notes'], changed) != proposal['output_digest']
        assert storyboard_prompt_data({**proposal, 'visual_target': changed}, source) != storyboard_prompt_data(proposal, source)
    before = creative.get(rig.nid, rig.scope, source['id'])
    adopted = creative.proposals.review(rig.nid, rig.scope, rig.actor, proposal['id'], review_body(proposal))
    draft = adopted['document']
    assert draft['status'] == 'DRAFT' and draft['visual_target'] == TARGET
    assert creative.get(rig.nid, rig.scope, source['id']) == before
    board = creative.derive(rig.nid, rig.scope, rig.actor, draft['id'], {
        'expected_version': draft['version'], 'mode': 'STORYBOARD', 'shot_policy': 'DIRECTOR_NOTES'})
    assert board['visual_target'] == TARGET
    changed = {k: deepcopy(draft[k]) for k in CreativeProductionDocumentIn.model_fields if k in draft}
    changed['visual_target']['production_budget_constraints'] = 'Only existing assets'
    updated = creative.update(rig.nid, rig.scope, rig.actor, draft['id'], draft['version'], changed)
    reopened = CreativeService(ExperimentalStore(rig.root, rig.backend, rig.url), rig.novels, rig.chapters)
    assert reopened.get(rig.nid, rig.scope, draft['id'])['visual_target'] == changed['visual_target']
    assert document_digest(updated) != document_digest(draft)
    assert updated['source_documents'] == draft['source_documents'] and updated['status'] == 'DRAFT'
    with pytest.raises(StaleSourceError): reopened.export(rig.nid, rig.scope, board['id'])

    cleared = {k: deepcopy(updated[k]) for k in CreativeProductionDocumentIn.model_fields if k in updated}
    cleared['visual_target'].update(dict.fromkeys(FIELDS, '  '))
    emptied = reopened.update(rig.nid, rig.scope, rig.actor, updated['id'], updated['version'], cleared)
    assert emptied['visual_target'] == LEGACY
    assert reopened.get(rig.nid, rig.scope, updated['id'])['visual_target'] == LEGACY


from creative_director_execution_fixture import lifecycle


@pytest.mark.file_backend_only
def test_original_preview_pins_constraints_and_rejects_changed_intent_before_dispatch(lifecycle):
    from creative_director_execution_fixture import preview, dispatch
    e = lifecycle
    e.row = e.documents.proposals.create(e.nid, e.scope, e.actor, {
        'source_document_id': e.source['id'], 'expected_source_version': e.source['version'], 'visual_target': TARGET})
    prepared = preview(e)
    captured = prepared['model_preview']
    assert captured['visual_target'] == TARGET
    assert json.loads(captured['prompt'].split('\n', 1)[1])['visual_target'] == TARGET
    assert captured['model_called'] is False and not e.requests and not e.manager.jobs
    # A changed authored target cannot reuse the already-reviewed exact preview.
    with e.raw.transaction(e.nid, e.scope) as state:
        state['collections'][e.documents.proposals.COLLECTION][e.row['id']]['visual_target']['target_platform'] = 'Changed destination'
    with pytest.raises(ValueError):
        dispatch(e, prepared)
    assert not e.requests and not e.manager.jobs
