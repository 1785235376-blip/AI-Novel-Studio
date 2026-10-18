"""Passive contract against genuine original File documents; no model execution."""
from copy import deepcopy
import json
import pytest
from test_v2_independent_workspace import rig
from app.creative.screenplay_model import (SCREENPLAY_CONTRACT, screenplay_source_mapping,
    screenplay_prompt_data, parse_screenplay_output)
from app.creative.service import document_digest

pytestmark = [pytest.mark.file_backend_only, pytest.mark.parametrize('rig', ['file'], indirect=True)]


def setup(rig):
    documents = rig.service.creative
    source = documents.create(rig.nid, rig.scope, rig.actor, {
        'mode': 'SCREENPLAY', 'source_independent': True, 'title': 'Independent authored scenes',
        'scenes': [{'id': 's2', 'sequence': 8, 'heading': 'HALL', 'action': 'The door opens.'},
                   {'id': 's1', 'sequence': 3, 'heading': 'ROOM', 'action': 'The visitor waits.'}]})
    row = documents.proposals.create(rig.nid, rig.scope, rig.actor,
        {'source_document_id': source['id'], 'expected_source_version': source['version']})
    return documents, source, row


def output(source, row):
    notes = []
    for n in row['director_notes']:
        scene = next(s for s in source['scenes'] if s['id'] == n['scene_id'])
        notes.append({**n, 'planning': {'rationale': 'Consider a reaction',
            'sequence_reason': 'Follow authored order', 'duration_reason': 'Tentative timing',
            'uncertainty': 'Geometry unknown', 'assumptions': ['Camera placement unverified'],
            'alternatives': [{'choice': 'Hold wide', 'tradeoff': 'Less detail'}],
            'evidence': [{'scene_id': scene['id'], 'field': 'action', 'excerpt': scene['action']}]}})
    return {'source_contract': SCREENPLAY_CONTRACT, 'source_document_id': source['id'],
        'source_version': source['version'], 'source_digest': row['source_digest'], 'director_notes': notes}


def test_original_file_source_exact_mapping_prompt_and_output_without_writes(rig):
    documents, source, row = setup(rig)
    before = {str(p): p.read_bytes() for p in rig.root.rglob('*') if p.is_file()}
    mapping = screenplay_source_mapping(row, source)
    assert [m['source_sequence'] for m in mapping] == [3, 8]
    assert [m['number'] for m in mapping] == [1, 2]
    prompt = screenplay_prompt_data(row, source)
    assert [s['id'] for s in prompt['screenplay']['scenes']] == ['s1', 's2']
    assert prompt['source_digest'] == documents.document_digest(source)
    assert 'source_shot_id' not in json.dumps(prompt)
    parsed = parse_screenplay_output(row, source, json.dumps(output(source, row)))
    assert [n['id'] for n in parsed] == [m['note_id'] for m in mapping]
    assert rig.chapters.list(rig.nid) == []
    assert before == {str(p): p.read_bytes() for p in rig.root.rglob('*') if p.is_file()}
    prompt['screenplay']['scenes'][0]['action'] = 'changed copy'
    assert source['scenes'][0]['action'] != 'changed copy'


@pytest.mark.parametrize('change', ['digest', 'version', 'owner', 'mode', 'chapter', 'sequence', 'note_id'])
def test_rejects_changed_source_or_association(rig, change):
    _, source, row = setup(rig)
    if change == 'digest': source['title'] += '!'
    if change == 'version': source['version'] += 1
    if change == 'owner': row['project_incarnation'] += '-other'
    if change == 'mode': source['mode'] = 'SCRIPT'
    if change == 'chapter': source['source_chapter_ids'] = ['fake']
    if change == 'sequence': row['director_notes'].reverse()
    if change == 'note_id': row['director_notes'][1]['id'] = row['director_notes'][0]['id']
    with pytest.raises(ValueError): screenplay_prompt_data(row, source)


@pytest.mark.parametrize('change', ['source', 'reorder', 'omit', 'id', 'cross_scene', 'false_evidence', 'missing_planning', 'shot_contract'])
def test_rejects_mismatched_output_without_normalizing_away_error(rig, change):
    _, source, row = setup(rig); value = output(source, row)
    if change == 'source': value['source_digest'] = '0' * 64
    if change == 'reorder': value['director_notes'].reverse()
    if change == 'omit': value['director_notes'].pop()
    if change == 'id': value['director_notes'][0]['id'] = 'invented'
    if change == 'cross_scene': value['director_notes'][0]['scene_id'] = 's2'
    if change == 'false_evidence': value['director_notes'][0]['planning']['evidence'][0]['excerpt'] = 'invented'
    if change == 'missing_planning': del value['director_notes'][0]['planning']
    if change == 'shot_contract': value['source_contract'] = 'STORYBOARD_SHOT_CONTEXT_V1'
    with pytest.raises(ValueError): parse_screenplay_output(row, source, json.dumps(value))


def test_bounds_duplicate_json_and_no_legacy_binding_widening(rig):
    _, source, row = setup(rig)
    with pytest.raises(ValueError, match='OUTPUT_LIMIT'):
        parse_screenplay_output(row, source, json.dumps(output(source, row)), max_output_bytes=10)
    with pytest.raises(ValueError, match='DUPLICATE_JSON_KEY'):
        parse_screenplay_output(row, source, '{"x":1,"x":2}')
    source['scenes'][0]['action'] = '界' * 32000
    source['scenes'][1]['action'] = '界' * 32000
    row['source_digest'] = document_digest(source)
    with pytest.raises(ValueError, match='PROMPT_LIMIT'): screenplay_prompt_data(row, source)
    from app.creative.director_binding import CreativeDirectorBinding
    assert CreativeDirectorBinding.model_fields['source_kind'].annotation.__args__ == ('STORYBOARD',)
