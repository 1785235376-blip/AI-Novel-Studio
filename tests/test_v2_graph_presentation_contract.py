"""Pure annotation serialization; no lifecycle, permission or execution calls."""
import json
from copy import deepcopy

import pytest
from pydantic import ValidationError

from app.creative.graph_models import GraphCreate, GraphSave, parse_graph, MAX_NODES, MAX_MEDIA_NODES, MAX_EDGES
from app.creative.graph import execution_definition, digest


@pytest.mark.parametrize('schema', [1, 2, 3, 4, 5])
def test_optional_presentation_preserves_legacy_canonical_values(schema):
    legacy = {'schema_version': schema, 'title': 'Legacy', 'nodes': [], 'edges': [],
              'viewport': {'x': 0.0, 'y': 0.0, 'zoom': 1.0}}
    parsed = parse_graph(legacy)
    assert parsed.model_dump() == legacy
    assert json.loads(parsed.model_dump_json()) == legacy
    assert GraphCreate.model_validate({'request_id': 'legacy', 'definition': legacy}).model_dump()['definition'] == legacy
    assert GraphSave.model_validate({'expected_version': 1, 'definition': legacy}).model_dump()['definition'] == legacy
    annotated = {**legacy, 'presentation': {'comment': '🎬' * 2000}}
    assert parse_graph(annotated).model_dump() == annotated
    assert digest(execution_definition(annotated)) == digest(execution_definition(legacy))
    assert digest(annotated) != digest(legacy)
    assert parse_graph({**legacy, 'presentation': None}).model_dump() == legacy


@pytest.mark.parametrize('presentation', [{'comment': 'x' * 2001}, {'comment': 1}, {'comment': 'a', 'groups': []}, {}, {'comment': 'a', 'allow_cloud': True}])
def test_annotation_is_bounded_strict_plain_data(presentation):
    with pytest.raises(ValidationError):
        parse_graph({'title': 'Graph', 'presentation': presentation})


def test_annotation_does_not_relax_graph_validation_or_budgets():
    assert (MAX_NODES, MAX_MEDIA_NODES, MAX_EDGES) == (16, 24, 40)
    graph = {'title': 'Graph', 'presentation': {'comment': 'x' * 2000}, 'nodes': [
        {'id': 'text', 'definition_id': 'text_input', 'parameters': {'text': 'original'}}]}
    original = deepcopy(graph)
    assert parse_graph(graph).model_dump()['presentation'] == graph['presentation']
    assert graph == original
    for patch in ({'nodes': graph['nodes'] * 17}, {'unexpected': True},
                  {'edges': [{'id': 'edge', 'source_node_id': 'text', 'source_port': 'text', 'target_node_id': 'missing', 'target_port': 'text'}]},
                  {'nodes': [{'id': 'visual', 'definition_id': 'visual_group'}]}):
        with pytest.raises(ValidationError):
            parse_graph({**graph, **patch})


@pytest.mark.parametrize('schema', [1, 2, 3, 4, 5])
def test_groups_roundtrip_without_changing_annotation_or_execution(schema):
    old = parse_graph({'schema_version': schema, 'title': 'Graph', 'nodes': [
        {'id': 'text', 'definition_id': 'text_input', 'parameters': {'text': 'original'}}],
        'presentation': {'comment': '  🎬\n'}}).model_dump()
    grouped = deepcopy(old)
    grouped['presentation']['groups'] = [{'id': 'group_1', 'name': '🎬' * 80, 'node_ids': ['text']}]
    assert parse_graph(grouped).model_dump() == grouped
    assert GraphSave.model_validate({'expected_version': 1, 'definition': grouped}).model_dump()['definition'] == grouped
    assert digest(execution_definition(grouped)) == digest(execution_definition(old))
    del grouped['presentation']['groups']
    assert digest(parse_graph(grouped).model_dump()) == digest(old)


@pytest.mark.parametrize('groups', [None, [], {}, [None],
    [{'id': 'g', 'name': '', 'node_ids': ['text']}],
    [{'id': 'g', 'name': ' ', 'node_ids': ['text']}],
    [{'id': 'g', 'name': '🎬' * 81, 'node_ids': ['text']}],
    [{'id': 'g', 'name': 1, 'node_ids': ['text']}],
    [{'id': '1g', 'name': 'Name', 'node_ids': ['text']}],
    [{'id': 'g', 'name': 'Name', 'node_ids': []}],
    [{'id': 'g', 'name': 'Name', 'node_ids': ['missing']}],
    [{'id': 'g', 'name': 'Name', 'node_ids': ['text', 'text']}],
    [{'id': 'g', 'name': 'Name', 'node_ids': ['text'], 'collapsed': True}],
    [{'id': 'g', 'name': 'Name', 'node_ids': ['text']}, {'id': 'other', 'name': 'Other', 'node_ids': ['text']}],
    [{'id': 'g', 'name': 'Name', 'node_ids': ['text']}, {'id': 'g', 'name': 'Other', 'node_ids': ['other']}],
    [{'id': 'g', 'name': 'Name', 'node_ids': ['text']}] * 25,
])
def test_groups_reject_malformed_dangling_duplicate_or_overlapping_membership(groups):
    with pytest.raises(ValidationError):
        parse_graph({'title': 'Graph', 'nodes': [
            {'id': 'text', 'definition_id': 'text_input'}, {'id': 'other', 'definition_id': 'text_input'}],
            'presentation': {'groups': groups}})


VIEW = {'show_grid': False, 'snap': True, 'grid_step': 32, 'show_minimap': False}


@pytest.mark.parametrize('schema', [1, 2, 3, 4, 5])
def test_view_preferences_roundtrip_preserve_legacy_execution(schema):
    old = parse_graph({'schema_version': schema, 'title': 'Graph'}).model_dump()
    updated = {**old, 'presentation': {'view': VIEW, 'comment': '🎬' * 2000}}
    assert parse_graph(updated).model_dump() == updated
    assert GraphSave.model_validate({'expected_version': 1, 'definition': updated}).model_dump()['definition'] == updated
    assert digest(execution_definition(updated)) == digest(execution_definition(old))
    assert digest(updated) != digest(old)
    assert parse_graph(old).model_dump() == old


@pytest.mark.parametrize('view', [None, {}, {**VIEW, 'unknown': True}, {**VIEW, 'show_grid': 1},
    {**VIEW, 'snap': 'true'}, {**VIEW, 'show_minimap': None}, {**VIEW, 'grid_step': True},
    {**VIEW, 'grid_step': 24.0}, {**VIEW, 'grid_step': float('nan')},
    {**VIEW, 'grid_step': float('inf')}, {**VIEW, 'grid_step': -1}, {**VIEW, 'grid_step': 48},
    {**VIEW, 'grid_step': '２４'}])
def test_view_preferences_are_strict_bounded_complete(view):
    with pytest.raises(ValidationError):
        parse_graph({'title': 'Graph', 'presentation': {'view': view}})
