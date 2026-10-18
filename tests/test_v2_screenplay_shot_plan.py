"""Opt-in bounded shot planning. Synthetic wire data; no real model/quality claim."""
from copy import deepcopy
import json
import pytest
from test_v2_independent_workspace import rig
from test_v2_screenplay_scene_contract import setup
from app.creative.screenplay_model import (SHOT_PLAN_CONTRACT, screenplay_allowed_slots,
    screenplay_shot_plan_prompt_data, screenplay_selected_mapping, parse_screenplay_shot_plan_output)
from app.creative.service import document_digest

# Use the original fixture's File/PG parameters; PG covers source/proposal/parser only.
# Job/transport lifecycle coverage remains in the explicitly File-only module.


def shot_output(source, row, indexes=(0, 1, 2, 3)):
    slots = screenplay_allowed_slots(row, source)
    notes = []
    for number, index in enumerate(indexes, 1):
        slot = slots[index]
        scene = next(s for s in source['scenes'] if s['id'] == slot['scene_id'])
        notes.append({'id': slot['note_id'], 'scene_id': slot['scene_id'], 'number': number,
            'note': ['Establish the wait', 'Focus on the reaction', 'Hold the gesture', 'Reveal the doorway'][min(number-1, 3)],
            'duration_seconds': 4 + number, 'planning': {'rationale': 'Synthetic dramatic rationale',
            'sequence_reason': 'Reaction follows establishing detail', 'duration_reason': 'Tentative beat estimate',
            'uncertainty': 'Not tested against performance or geometry', 'assumptions': [],
            'alternatives': [{'choice': 'Hold wide', 'tradeoff': 'Less reaction detail'}],
            'evidence': [{'scene_id': scene['id'], 'field': 'action', 'excerpt': scene['action']}]}})
    return {'source_contract': SHOT_PLAN_CONTRACT, 'source_document_id': source['id'],
        'source_version': source['version'], 'source_digest': row['source_digest'], 'director_notes': notes}


def parse(source, row, value):
    return parse_screenplay_shot_plan_output(row, source, json.dumps(value),
        frozen_mapping=screenplay_allowed_slots(row, source))


def test_model_selects_three_plus_one_and_can_skip_slots(rig):
    _, source, row = setup(rig)
    prompt = screenplay_shot_plan_prompt_data(row, source)
    assert 'source_mapping' not in prompt and len(prompt['allowed_source_mapping']) == 6
    notes = parse(source, row, shot_output(source, row))
    assert [n['scene_id'] for n in notes] == ['s1', 's1', 's1', 's2']
    assert [n['number'] for n in notes] == [1, 2, 3, 4]
    selected = screenplay_selected_mapping(row, source, notes, frozen_mapping=prompt['allowed_source_mapping'])
    assert len(selected) == 4 and sum(n['duration_seconds'] for n in notes) == 26
    skipped = parse(source, row, shot_output(source, row, (0, 2, 5)))
    assert [n['number'] for n in skipped] == [1, 2, 3]
    assert len(parse(source, row, shot_output(source, row, tuple(range(6))))) == 6


@pytest.mark.parametrize('change', ['foreign_id', 'duplicate_id', 'foreign_scene', 'cross_scene',
    'missing_scene', 'reorder', 'number_gap', 'bool_number', 'four_in_scene', 'over_total',
    'zero_duration', 'long_duration', 'float_duration', 'missing_duration', 'missing_rationale',
    'missing_sequence_reason', 'missing_duration_reason', 'bad_excerpt', 'cross_evidence',
    'no_evidence_no_assumptions', 'missing_planning', 'wrong_version', 'wrong_digest'])
def test_invalid_shot_plan_fails_closed(rig, change):
    _, source, row = setup(rig); value = shot_output(source, row); notes = value['director_notes']; first = notes[0]
    if change == 'foreign_id': first['id'] = 'invented'
    if change == 'duplicate_id': notes[1]['id'] = first['id']
    if change == 'foreign_scene': first['scene_id'] = 'invented'
    if change == 'cross_scene': first['scene_id'] = 's2'
    if change == 'missing_scene': notes.pop()
    if change == 'reorder': notes[0], notes[1] = notes[1], notes[0]
    if change == 'number_gap': first['number'] = 5
    if change == 'bool_number': first['number'] = True
    if change == 'four_in_scene': notes[-1]['scene_id'] = 's1'
    if change == 'over_total': notes.extend(deepcopy(notes))
    if change == 'zero_duration': first['duration_seconds'] = 0
    if change == 'long_duration': first['duration_seconds'] = 601
    if change == 'float_duration': first['duration_seconds'] = 1.5
    if change == 'missing_duration': del first['duration_seconds']
    if change.startswith('missing_') and change[8:] in first['planning']: del first['planning'][change[8:]]
    if change == 'bad_excerpt': first['planning']['evidence'][0]['excerpt'] = 'Not authored'
    if change == 'cross_evidence': first['planning']['evidence'][0]['scene_id'] = 's2'
    if change == 'no_evidence_no_assumptions': first['planning']['evidence'] = []
    if change == 'missing_planning': del first['planning']
    if change == 'wrong_version': value['source_version'] += 1
    if change == 'wrong_digest': value['source_digest'] = '0'*64
    with pytest.raises(ValueError): parse(source, row, value)


def test_speculation_and_incomplete_json_and_frozen_slots(rig):
    _, source, row = setup(rig); value = shot_output(source, row)
    value['director_notes'][0]['planning'].update(evidence=[], assumptions=['Speculative reaction shot'])
    assert parse(source, row, value)
    slots = screenplay_allowed_slots(row, source); slots[0]['slot'] = True
    with pytest.raises(ValueError, match='ALLOWED_SLOTS_CHANGED'):
        parse_screenplay_shot_plan_output(row, source, json.dumps(value), frozen_mapping=slots)
    with pytest.raises(ValueError):
        parse_screenplay_shot_plan_output(row, source, json.dumps(value)[:-2], frozen_mapping=screenplay_allowed_slots(row, source))
    with pytest.raises(ValueError, match='ALLOWED_SLOTS_REQUIRED'):
        parse_screenplay_shot_plan_output(row, source, json.dumps(value), frozen_mapping=None)


@pytest.mark.parametrize('count', [0, 3])
def test_no_implicit_scene_split_or_truncation(rig, count):
    _, source, row = setup(rig)
    source['scenes'] = [{'id': f's{i}', 'sequence': i+1, 'heading': 'ROOM', 'action': 'Wait.'} for i in range(count)]
    row['source_digest'] = document_digest(source)
    with pytest.raises(ValueError): screenplay_shot_plan_prompt_data(row, source)
