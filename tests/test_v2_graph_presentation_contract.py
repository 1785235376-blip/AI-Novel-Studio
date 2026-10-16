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
