"""Original File/broker preview with unchanged V1 public transport boundary."""
import json
import pytest
from creative_director_execution_fixture import lifecycle, raw_proposal
from app.creative.screenplay_model import SCREENPLAY_CONTRACT

pytestmark = pytest.mark.file_backend_only


def screenplay(e):
    e.source = e.documents.create(e.nid, e.scope, e.actor, {
        'mode': 'SCREENPLAY', 'source_independent': True, 'title': 'Independent screenplay',
        'scenes': [{'id': 'scene-a', 'sequence': 4, 'heading': 'ROOM', 'action': 'A visitor waits.'}]})
    e.row = e.documents.proposals.create(e.nid, e.scope, e.actor,
        {'source_document_id': e.source['id'], 'expected_source_version': e.source['version']})
    return e


def preview(e, **kw):
    return e.coordinator._preview_independent_screenplay(e.ctx, e.row['id'], {
        'expected_version': e.row['version'], 'route_id': e.route['route_id'],
        'allow_synthetic': False, 'max_output_tokens': 512, 'temperature': 0.0},
        e.guard, host_authority=e.authority, **kw)


def test_explicit_original_preview_binds_scene_ids_before_notes_clear(lifecycle):
    e = screenplay(lifecycle); note = e.row['director_notes'][0]
    result = preview(e); stored = raw_proposal(e); p = stored['model_preview']
    assert result['id'] == stored['id'] and p['model_called'] is False
    assert stored['director_notes'] == []
    assert p['source_binding']['contract'] == 'CREATIVE_DIRECTOR_SCREENPLAY_SOURCE_V2'
    assert p['source_binding']['source_kind'] == 'SCREENPLAY'
    assert p['source_mapping'] == [{'note_id': note['id'], 'scene_id': 'scene-a', 'source_sequence': 4, 'number': 1}]
    data = json.loads(p['prompt'].removeprefix(SCREENPLAY_CONTRACT+'\n'))
    assert data['source_mapping'] == p['source_mapping']
    assert data['screenplay']['scenes'] == e.source['scenes']
    assert not e.manager.jobs
    # No accidental activation of old dispatcher or public proposal projection.
    with pytest.raises(ValueError):
        e.coordinator._require_independent_transport_v1(e.ctx, e.row['id'])
    public = e.documents.proposals.get(e.nid,e.scope,e.actor,e.row['id'])
    assert public['status'] == 'MODEL_UNAVAILABLE'
    assert public['model_preview'] is None and public['model_execution'] is None
    assert public['director_notes'] == [] and 'provenance' not in public
    assert p['execution_available'] is True
    assert not e.manager.jobs


def test_new_preview_does_not_accept_storyboard_or_bypass_host(lifecycle):
    e = lifecycle
    with pytest.raises(ValueError): preview(e)
    assert raw_proposal(e)['model_preview'] is None
    e = screenplay(e)
    from types import SimpleNamespace
    with pytest.raises(ValueError):
        e.coordinator._preview_independent_screenplay(e.ctx,e.row['id'], {
            'expected_version': e.row['version'], 'route_id': e.route['route_id'],
            'allow_synthetic': False, 'max_output_tokens': 512, 'temperature': 0.0},
            e.guard,host_authority=SimpleNamespace(principal='forged',guard=lambda:None))
    assert raw_proposal(e)['model_preview'] is None
    assert not e.manager.jobs
