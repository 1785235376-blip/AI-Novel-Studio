"""Original saved Graph -> one card task -> original immutable AudioJob.

These tests require the shared template_ref admission contract to be integrated.
They use real File/PostgreSQL owners and short synthetic CPU WAV processing.
No model, provider, alternate template store, or workflow run is created.
"""
from copy import deepcopy

import pytest

from app.creative.graph_models import MediaNodeParameters
from app.creative.production_execution_models import MediaCommand
from app.experimental.common import StaleSourceError
from test_studio_canvas_audio_return import audio_canvas
from test_v2_audio_wav_controls import preview, queue, run, get
from test_v2_independent_workspace import rig


def template_ref(row):
    trim = next(node for node in row['definition']['nodes'] if node['id'] == 'trim')
    return {'contract': 'studio-canvas-audio-template/1', 'graph_id': row['id'],
        'graph_version': row['version'], 'definition_digest': row['definition_digest'],
        'execution_digest': row['execution_digest'], 'node_id': trim['id'],
        'parameters': {key: trim['parameters']['parameters'][key] for key in ('in_ms', 'out_ms')}}


@pytest.fixture
def task_template(audio_canvas):
    e = audio_canvas
    value = {'schema_version': 3, 'title': 'Owned saved audio workflow', 'nodes': [
        {'id': 'source', 'definition_id': 'asset_reference', 'parameters': {
            'asset_id': e.source['id'], 'version': e.source['version'],
            'digest': e.source['sha256'], 'kind': 'audio'}},
        {'id': 'trim', 'definition_id': 'media_generate', 'parameters': {
            'operation_id': 'm8.audio.trim', 'parameters': {'in_ms': 100, 'out_ms': 900}}}],
        'edges': [{'id': 'source_trim', 'source_node_id': 'source', 'source_port': 'asset',
            'target_node_id': 'trim', 'target_port': 'source'}]}
    e.template = e.graph.create(e.nid, e.scope, e.actor,
        {'request_id': 'saved-audio-task-template', 'definition': value})
    e.command['template_ref'] = template_ref(e.template)
    e.command['parameters'] = {'in_ms': 100, 'out_ms': 900}
    return e


def save_template(e, **changes):
    value = deepcopy(e.template['definition'])
    value['nodes'][1]['parameters']['parameters'].update(changes)
    return e.graph.save(e.nid, e.scope, e.actor, e.template['id'],
        {'expected_version': e.template['version'], 'definition': value})


def test_original_graph_pin_task_override_and_queued_snapshot_survive_template_change(task_template):
    e = task_template
    before = deepcopy(e.template)
    # Both interval and envelope overrides belong to this card task alone.
    e.command['parameters'] = {'in_ms': 300, 'out_ms': 700, 'gain_db': -6,
        'fade_in_ms': 25, 'fade_out_ms': 30}
    captured = preview(e)
    assert captured['command']['template_ref'] == template_ref(before)
    assert captured['execution_recipe']['parameters'] == e.command['parameters']
    queued = queue(e)
    original = deepcopy(queued['command'])
    assert e.graph.get(e.nid, e.scope, e.actor, e.template['id']) == before
    changed = save_template(e, in_ms=500, out_ms=800)
    assert changed['version'] == before['version'] + 1
    assert get(e, queued)['command'] == original
    # The already admitted request is rechecked against its original full snapshot.
    rechecked = preview(e)['command']
    # Original preview has known null defaults; Job.view omits them. Compare
    # every effective parameter and all provenance/source fields exactly.
    rechecked['parameters'] = {k: v for k, v in rechecked['parameters'].items() if v is not None}
    assert rechecked == original
    assert queue(e) == queued
    fresh = deepcopy(e.command)
    fresh['request_id'] = 'new-task-old-template-pin'
    with pytest.raises((ValueError, StaleSourceError, FileNotFoundError)):
        preview(e, fresh)
    # Dispatch consumes the original AudioJob and never substitutes current template values.
    candidate = run(e, queued)
    assert candidate['status'] == 'AWAITING_REVIEW'
    assert candidate['command'] == original
    assert candidate['media_measurement']['duration_ms'] == 400
    assert candidate['execution_recipe']['parameters'] == original['parameters']
    assert not e.raw_store.read(e.nid, e.scope)['collections'].get(e.graph.RUNS)


@pytest.mark.parametrize('change', ['version', 'definition-digest', 'execution-digest', 'graph-id',
    'node-id', 'parameter-snapshot', 'contract', 'extra', 'null', 'without-card'])
def test_new_admission_rejects_bad_template_binding_without_creating_audiojob(task_template, change):
    e = task_template
    value = deepcopy(e.command)
    ref = value['template_ref']
    if change == 'version': ref['graph_version'] += 1
    elif change == 'definition-digest': ref['definition_digest'] = 'f' * 64
    elif change == 'execution-digest': ref['execution_digest'] = 'e' * 64
    elif change == 'graph-id': ref['graph_id'] = 'missing-original-graph'
    elif change == 'node-id': ref['node_id'] = 'source'
    elif change == 'parameter-snapshot': ref['parameters']['in_ms'] += 1
    elif change == 'contract': ref['contract'] = 'invented-template/1'
    elif change == 'extra': ref['provider_id'] = 'unsupported'
    elif change == 'null': value['template_ref'] = None
    elif change == 'without-card': value.pop('canvas_return')
    with pytest.raises((ValueError, StaleSourceError, FileNotFoundError)):
        preview(e, value)
    audio = e.production._audio(e.scope, e.actor)
    assert audio.list(e.nid, e.production._base(e.nid, e.scope, e.actor, lambda: None), lambda: None) == []


def test_reading_new_template_version_does_not_mutate_the_original_queued_task(task_template):
    e = task_template
    queued = queue(e)
    changed = save_template(e, in_ms=250, out_ms=750)
    new = deepcopy(e.command)
    new['request_id'] = 'explicit-new-version-task'
    new['template_ref'] = template_ref(changed)
    new['parameters'] = {'in_ms': 250, 'out_ms': 750}
    next_job = queue(e, new)
    assert next_job['id'] != queued['id']
    assert next_job['command']['template_ref']['graph_version'] == changed['version']
    assert get(e, queued)['command']['template_ref'] == template_ref(e.template)
    assert get(e, queued)['command']['parameters'] == {'in_ms': 100, 'out_ms': 900}


def test_same_queued_request_cannot_replace_its_recorded_template_snapshot(task_template):
    e = task_template
    queued = queue(e)
    changed = save_template(e, in_ms=250, out_ms=750)
    replacement = deepcopy(e.command)
    replacement['template_ref'] = template_ref(changed)
    with pytest.raises((ValueError, StaleSourceError, FileNotFoundError)):
        queue(e, replacement)
    assert get(e, queued) == queued


def test_disabled_current_template_node_is_not_an_admissible_task_template(task_template):
    e = task_template
    definition = deepcopy(e.template['definition'])
    definition['nodes'][1]['enabled'] = False
    changed = e.graph.save(e.nid, e.scope, e.actor, e.template['id'],
        {'expected_version': e.template['version'], 'definition': definition})
    e.command['template_ref'] = template_ref(changed)
    with pytest.raises((ValueError, StaleSourceError, FileNotFoundError)):
        preview(e)


@pytest.mark.parametrize('parameters', [{'sample_rate': 44100}, {'channels': 1}, {'target_peak_dbfs': -6}])
def test_graph_template_does_not_gain_task_only_envelope_support(parameters):
    with pytest.raises(ValueError):
        MediaNodeParameters.model_validate({'operation_id': 'm8.audio.trim',
            'parameters': {'in_ms': 100, 'out_ms': 900, **parameters}})


def test_omitted_template_reference_remains_compatible_with_the_original_card_contract(task_template):
    e = task_template
    e.command.pop('template_ref')
    checked = MediaCommand.model_validate(e.command)
    assert 'template_ref' not in checked.model_dump(exclude_unset=True)
    queued = queue(e)
    assert 'template_ref' not in queued['command']
