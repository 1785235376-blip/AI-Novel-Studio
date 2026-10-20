"""B07 line B: RENPY_8_5_4_PROJECT_V1 complete-project export contracts.

Directed, actually executed tests for the Ren'Py 8.5.4 runnable-project target:
the frozen adapter schema, the generated project structure, a local trusted-subset
parser plus bounded state-machine simulation of the generated Ren'Py script
checked against the authority play() witness, escaping/injection safety, absence
of python/IO/engine/media bytes, compatibility blocking, and the service end-to-end
deterministic ZIP with manifest/receipt hashes.

Honesty: no Ren'Py engine is installed on this host, so these tests never claim
target-runtime execution. Generated .rpy text is validated against the documented
Ren'Py 8.5.4 grammar by the local parser/simulator, which is
GENERATED_ARTIFACT_VALIDATED, not TARGET_RUNTIME_EXECUTED.
"""
from __future__ import annotations

import base64
import builtins
import hashlib
import io
import json
import re
from copy import deepcopy

import pytest

import app.experimental.interactive_export_contract as contract
import app.experimental.interactive_renpy_export as renpy_target
from app.experimental.interactive_story import (
    InteractiveStoryService,
    StorySpec,
    analyze,
    compile_story,
    digest,
    interpret,
    parse_condition,
    play,
    renpy_expression,
)
from app.experimental.interactive_targets.renpy import (
    FORMAT_VERSION as RENPY_FORMAT_VERSION,
    NO_CHOICE_MESSAGE,
    SCREENS_RPY,
    STEP_CAP_MESSAGE,
    WITNESS_SCHEMA,
    projection,
)
from app.experimental.planning import PlanningService
from app.experimental.story_graph import StoryGraphService
from app.services.asset_library_service import AssetLibraryService
from test_r4_revision_intelligence import revision_env

TARGET = renpy_target.TARGET_ID
TARGET_SLUG = 'renpy-8-5-4-project-v1'
LEGACY_RENPY = 'RENPY_8_5_4_TEXT_MENU_SUBSET'
EXPECTED_PROJECT_FILES = {
    'README.txt',
    'acceptance/witness.json',
    'game/options.rpy',
    'game/screens.rpy',
    'game/script.rpy',
}
ALLOWED_SUFFIXES = {'.rpy', '.txt', '.json'}
RESERVED_INJECTED = {'manifest.json', 'source-receipt.json'}
FORBIDDEN_SCRIPT_PATTERNS = (
    r'python\s*:',
    r'\bimport\s',
    r'\beval\s*\(',
    r'\bexec\s*\(',
    r'\bopen\s*\(',
    r'__',
    r'\bos\.',
    r'\bsys\.',
    r'subprocess',
    r'requests',
    r'urllib',
    r'pathlib',
    r'renpy\.loader',
    r'renpy\.open',
    r'file\s*\(',
    r'[A-Za-z]:[\\/]',
    r'https?://',
)


# ---------------------------------------------------------------------------
# fixtures for the service integration surface
# ---------------------------------------------------------------------------
@pytest.fixture
def renpy_env(revision_env):
    e = revision_env
    e.planning = PlanningService(e.store, e.novels, e.chapters)
    e.story_graph = StoryGraphService(e.store, e.novels, e.chapters)
    e.assets = AssetLibraryService(e.store.root)
    e.service = InteractiveStoryService(e.store, e.novels, e.chapters, e.planning, e.story_graph, e.assets)
    e.novels.upsert_character(e.nid, 'alice', {'name': 'Alice'})
    e.graph = e.planning.create_graph(e.nid, e.scope, 'author', {
        'title': 'Synthetic Ren' + chr(39) + 'Py choice tree',
        'links': {'chapter_ids': [e.cid], 'character_ids': ['alice']},
    })
    e.nodes = [e.graph['root_node_id']]
    for title in ['Harbour', 'Mountain']:
        e.nodes.append(e.planning.create_node(e.nid, e.scope, 'author', {
            'graph_id': e.graph['id'], 'parent_id': e.nodes[0], 'level': 'VOLUME', 'title': title,
        })['id'])
    return e


def service_spec(e):
    return {
        'title': 'Synthetic Ren' + chr(39) + 'Py adaptation [title]',
        'graph_id': e.graph['id'], 'graph_version': 1, 'entry_node_id': e.nodes[0],
        'max_steps': 4,
        'variables': [
            {'name': 'courage', 'type': 'int', 'initial': 0, 'minimum': 0, 'maximum': 3},
            {'name': 'trusted', 'type': 'bool', 'initial': True},
        ],
        'nodes': [
            {'node_id': e.nodes[0], 'node_version': 1, 'title': 'Gate', 'character_id': 'alice',
             'dialogue': 'Choose {b}now{/b} [blink] 100%',
             'choices': [
                 {'id': 'harbour', 'label': 'To harbour "quoted"', 'target': e.nodes[1],
                  'condition': 'trusted and courage < 3', 'assignments': {'courage': 2}},
                 {'id': 'mountain', 'label': 'To mountain', 'target': e.nodes[2],
                  'condition': 'not (courage > 3)', 'assignments': {'trusted': False}},
             ]},
            {'node_id': e.nodes[1], 'node_version': 1, 'title': 'Harbour', 'dialogue': 'Home',
             'ending': 'Harbour ending'},
            {'node_id': e.nodes[2], 'node_version': 1, 'title': 'Mountain', 'dialogue': 'Beyond',
             'ending': 'Mountain ending'},
        ],
    }


def create_approved(e, spec=None):
    row = e.service.create_story(e.nid, e.scope, 'author', {'spec': deepcopy(spec or service_spec(e))})
    row = e.service.review(e.nid, e.scope, 'author', row['id'], {
        'expected_version': row['version'], 'action': 'submit'})
    receipt = e.service.review_preview(e.nid, e.scope, 'author', row['id'], {'expected_version': row['version']})
    return e.service.review(e.nid, e.scope, 'author', row['id'], {
        'expected_version': row['version'], 'action': 'approve', 'preview_digest': receipt['preview_digest']})


def export_target_row(targets):
    return next(target for target in targets['targets'] if target['target_id'] == TARGET)


def export_zip(e, row):
    value = {'expected_version': row['version']}
    preview = e.service.export_preview(e.nid, e.scope, 'author', row['id'], {**value, 'target_id': TARGET})
    exported = e.service.export(e.nid, e.scope, 'author', row['id'], {
        **value, 'target_id': TARGET, 'preview_digest': preview['preview_digest']})
    content = base64.b64decode(exported['content_base64'])
    assert hashlib.sha256(content).hexdigest() == exported['sha256']
    prefix = 'interactive-' + TARGET_SLUG + '-' + row['id'] + '/'
    return preview, exported, content, contract.read_zip_safely(content, prefix)


# ---------------------------------------------------------------------------
# direct adapter snapshots and builds (no service round trip)
# ---------------------------------------------------------------------------
def direct_snapshot(spec, *, characters=None, media_manifest=None, analysis=None,
                    story_id='story-1', revision=2):
    spec = StorySpec.model_validate(spec).model_dump()
    analysis = deepcopy(analysis or analyze(spec))
    return {
        'story_id': story_id, 'revision': revision, 'status': 'APPROVED', 'title': spec['title'],
        'spec': spec, 'spec_digest': digest(spec), 'source_digest': 'b' * 64,
        'review_receipt': 'c' * 64, 'characters': dict(characters or {}),
        'witness': deepcopy(analysis['endings']), 'media_manifest': deepcopy(media_manifest or []),
        'analysis': analysis,
    }


def build_bundle(spec, *, options=None, **snapshot_kwargs):
    options = options or {'include_witness': True, 'target_options': {}}
    return contract.build_export_bundle(TARGET, direct_snapshot(spec, **snapshot_kwargs), options)


def payload_of(bundle):
    return {path: content for path, content in bundle.files.items() if path not in RESERVED_INJECTED}


def unescape(value):
    """Apply the authority's displayed-text escapes in reverse (Ren'Py display)."""
    return value.replace('[[', '[').replace('{{', '{').replace(chr(0x3016) * 2, chr(0x3016)).replace('%%', '%')


def say_text(statement):
    return statement['what']


# ---------------------------------------------------------------------------
# trusted-subset parser for the generated Ren'Py script
# ---------------------------------------------------------------------------
_JSON = json.JSONDecoder()


def decode_renpy_literal(text, position):
    value, end = _JSON.raw_decode(text, position)
    assert isinstance(value, str), 'generated scripts must only use string literals here'
    return value, end


def _parse_say(text):
    first, end = decode_renpy_literal(text, 0)
    rest = text[end:]
    if not rest.strip():
        return {'kind': 'say', 'who': None, 'what': first}
    assert rest.startswith(' '), 'say statement must be one or two literals: ' + text
    second, end2 = decode_renpy_literal(text, end + 1)
    assert not text[end2:].strip(), 'unexpected trailing say text: ' + text
    return {'kind': 'say', 'who': first, 'what': second}


def _parse_scalar(token):
    token = token.strip()
    if token == 'True':
        return True
    if token == 'False':
        return False
    assert re.fullmatch(r'-?\d+', token), token
    return int(token)


def _parse_python_line(text):
    incr = re.fullmatch(r'(ans_[a-z0-9_]+) \+= 1', text)
    if incr:
        return {'kind': 'incr', 'name': incr.group(1)}
    assign = re.fullmatch(r'(ans_[a-z0-9_]+) = (-?\d+|True|False)', text)
    assert assign, 'unsupported generated python line: ' + text
    return {'kind': 'assign', 'name': assign.group(1), 'value': _parse_scalar(assign.group(2))}


def _line_indent(line):
    return len(line) - len(line.lstrip(' '))


def _parse_block(lines, i, indent):
    statements = []
    while i < len(lines):
        raw = lines[i]
        stripped = raw.strip()
        if not stripped or stripped.startswith('#'):
            i += 1
            continue
        actual = _line_indent(raw)
        if actual < indent:
            break
        assert actual == indent, 'unexpected indent at line %d: %r' % (i + 1, raw)
        text = raw[indent:]
        if text.startswith('$ '):
            statements.append(_parse_python_line(text[2:]))
            i += 1
        elif text == 'return':
            statements.append({'kind': 'return'})
            i += 1
            while i < len(lines):
                follower = lines[i]
                if not follower.strip() or follower.strip().startswith('#'):
                    i += 1
                    continue
                assert _line_indent(follower) < indent, 'statement after return at line %d: %r' % (i + 1, follower)
                break
            break
        elif text.startswith('jump '):
            statements.append({'kind': 'jump', 'label': text[len('jump '):].strip()})
            i += 1
        elif text == 'menu:':
            items = []
            i += 1
            while i < len(lines):
                raw_item = lines[i]
                stripped_item = raw_item.strip()
                if not stripped_item or stripped_item.startswith('#'):
                    i += 1
                    continue
                if _line_indent(raw_item) < indent + 4:
                    break
                assert _line_indent(raw_item) == indent + 4, 'menu item indent at line %d' % (i + 1)
                caption, condition = _parse_menu_item(raw_item[indent + 4:])
                body, i = _parse_block(lines, i + 1, indent + 8)
                items.append({'caption': caption, 'condition': condition, 'body': body})
            statements.append({'kind': 'menu', 'items': items})
        elif text.startswith('if '):
            condition = _parse_if_condition(text)
            body, i = _parse_block(lines, i + 1, indent + 4)
            assert len(body) == 2 and body[1] == {'kind': 'return'}, 'guard body must be one say plus return'
            assert body[0]['kind'] == 'say' and body[0]['who'] is None
            if condition['kind'] == 'step_cap':
                statements.append({'kind': 'step_cap', 'limit': condition['limit'],
                                   'message': body[0]['what'], 'body': body})
            else:
                statements.append({'kind': 'no_choice_guard', 'condition': condition['condition'],
                                   'message': body[0]['what'], 'body': body})
        else:
            assert text.startswith('"'), 'unsupported generated script statement: ' + text
            statements.append(_parse_say(text))
            i += 1
    return statements, i


def _parse_if_condition(text):
    step = re.fullmatch(r'if ans_steps >= (\d+):', text)
    if step:
        return {'kind': 'step_cap', 'limit': int(step.group(1))}
    guard = re.fullmatch(r'if not \((.+)\):', text)
    assert guard, 'unsupported generated if statement: ' + text
    return {'kind': 'no_choice_guard', 'condition': guard.group(1)}


def _parse_menu_item(text):
    caption, end = decode_renpy_literal(text, 0)
    rest = text[end:]
    assert rest.startswith(' if ') and rest.endswith(':'), 'unsupported menu item: ' + text
    return caption, rest[len(' if '):-1]


def parse_script(text):
    lines = text.split('\n')
    parsed = {'defaults': [], 'labels': {}, 'first_label_line': None}
    i = 0
    while i < len(lines):
        raw = lines[i]
        stripped = raw.strip()
        if not stripped or stripped.startswith('#'):
            i += 1
            continue
        assert not raw.startswith(' '), 'unexpected indented top-level line %d: %r' % (i + 1, raw)
        if raw.startswith('default '):
            name, separator, value = raw[len('default '):].partition(' = ')
            assert separator, raw
            assert re.fullmatch(r'ans_[a-z0-9_]+', name), name
            parsed['defaults'].append({'name': name, 'value': _parse_scalar(value), 'line': i + 1})
            i += 1
        elif raw.startswith('label '):
            assert raw.endswith(':'), raw
            name = raw[len('label '):-1]
            assert re.fullmatch(r'(start|ans_[a-z0-9_]+)', name), name
            assert name not in parsed['labels'], 'duplicate label ' + name
            if parsed['first_label_line'] is None:
                parsed['first_label_line'] = i + 1
            statements, i = _parse_block(lines, i + 1, 4)
            parsed['labels'][name] = statements
        else:
            raise AssertionError('unexpected top-level script line %d: %r' % (i + 1, raw))
    assert parsed['first_label_line'] is not None, 'generated script must define labels'
    for default in parsed['defaults']:
        assert default['line'] < parsed['first_label_line'], 'default declared after a label: ' + default['name']
    return parsed


# ---------------------------------------------------------------------------
# bounded simulator of the generated script plus authority-state comparison
# ---------------------------------------------------------------------------
def _evaluate(expression, values):
    return interpret(parse_condition(expression), values)


def label_to_node(project):
    return {label: node_id for node_id, label in project['labels'].items()}


def normalize(spec):
    return StorySpec.model_validate(spec).model_dump()


def simulate(project, spec, parsed, choices):
    """Run the generated trusted subset and snapshot every entered node."""
    spec = normalize(spec)
    nodes = {node['node_id']: node for node in spec['nodes']}
    mapping = label_to_node(project)
    generated_names = project['names']
    values = {generated_names[variable['name']]: variable['initial'] for variable in spec['variables']}
    values['ans_steps'] = 0

    def menu_of(label):
        return next((statement for statement in parsed['labels'][label] if statement['kind'] == 'menu'), None)

    def enabled_ids(label):
        node = nodes[mapping[label]]
        menu = menu_of(label)
        if menu is None:
            return []
        return [node['choices'][index]['id'] for index, item in enumerate(menu['items'])
                if _evaluate(item['condition'], values)]

    def run_choice_body(body):
        for statement in body:
            if statement['kind'] == 'incr':
                values['ans_steps'] += 1
            elif statement['kind'] == 'assign':
                values[statement['name']] = statement['value']
            elif statement['kind'] == 'jump':
                return statement['label']
            else:
                raise AssertionError('unexpected menu body statement ' + statement['kind'])
        raise AssertionError('a generated menu choice must always jump')

    next_label = None
    for statement in parsed['labels']['start']:
        if statement['kind'] == 'assign':
            values[statement['name']] = statement['value']
        elif statement['kind'] == 'jump':
            next_label = statement['label']
        else:
            raise AssertionError('unexpected start statement ' + statement['kind'])
    assert next_label is not None, 'start must jump to the entry node'
    label = next_label
    snapshots = []
    taken = 0
    while True:
        node_id = mapping[label]
        node = nodes[node_id]
        if node['ending']:
            status = 'ENDING'
        elif values['ans_steps'] >= spec['max_steps']:
            status = 'STEP_CAP_REACHED'
        elif enabled_ids(label):
            status = 'PLAYING'
        else:
            status = 'NO_EXIT'
        snapshots.append({
            'label': label, 'node_id': node_id, 'steps': values['ans_steps'],
            'variables': {name: values[generated] for name, generated in generated_names.items()},
            'enabled_choice_ids': enabled_ids(label), 'status': status,
        })
        if node['ending']:
            return snapshots
        menu = menu_of(label)
        assert menu is not None, 'non-ending node without a generated menu'
        if taken >= len(choices):
            return snapshots
        choice_id = choices[taken]
        taken += 1
        index = next((position for position, choice in enumerate(node['choices']) if choice['id'] == choice_id), None)
        assert index is not None, 'unknown choice id ' + choice_id
        item = menu['items'][index]
        assert _evaluate(item['condition'], values), 'witness selected a disabled choice'
        for statement in parsed['labels'][label]:
            if statement is menu:
                break
            if statement['kind'] == 'step_cap':
                assert values['ans_steps'] < statement['limit'], 'step-cap guard should have stopped playback'
        label = run_choice_body(item['body'])


def expected_states(spec, choices):
    spec = StorySpec.model_validate(spec).model_dump()
    states = []
    for index in range(len(choices) + 1):
        played = play(spec, list(choices[:index]))
        states.append({
            'node_id': played['node']['node_id'],
            'steps': played['steps'],
            'variables': played['variables'],
            'enabled_choice_ids': [choice['id'] for choice in played['choices'] if choice['enabled']],
            'status': played['status'],
        })
    return states


def assert_states_match(spec, snapshots, choices):
    expected = expected_states(spec, choices)
    assert len(snapshots) == len(expected), (len(snapshots), len(expected))
    for actual, wanted in zip(snapshots, expected):
        for key in ('node_id', 'steps', 'variables', 'enabled_choice_ids', 'status'):
            assert actual[key] == wanted[key], (key, actual, wanted)


def generate_bundle(spec):
    return build_bundle(spec)


# ---------------------------------------------------------------------------
# synthetic authoritative specs used by the direct adapter tests
# ---------------------------------------------------------------------------
def branching_spec():
    return {
        'title': 'Ren' + chr(39) + 'Py project bridge',
        'graph_id': 'graph-1', 'graph_version': 1, 'entry_node_id': 'n1', 'max_steps': 4,
        'variables': [
            {'name': 'courage', 'type': 'int', 'initial': 0, 'minimum': 0, 'maximum': 3},
            {'name': 'trusted', 'type': 'bool', 'initial': True},
        ],
        'nodes': [
            {'node_id': 'n1', 'node_version': 1, 'title': 'Gate', 'character_id': 'alice',
             'dialogue': 'Choose now',
             'choices': [
                 {'id': 'harbour', 'label': 'To harbour', 'target': 'n2',
                  'condition': 'trusted and courage < 3', 'assignments': {'courage': 2}},
                 {'id': 'mountain', 'label': 'To mountain', 'target': 'n3',
                  'condition': 'not (courage > 3)', 'assignments': {'trusted': False}},
             ]},
            {'node_id': 'n2', 'node_version': 1, 'title': 'Harbour', 'dialogue': 'Home',
             'ending': 'Harbour ending'},
            {'node_id': 'n3', 'node_version': 1, 'title': 'Mountain', 'dialogue': 'Beyond',
             'ending': 'Mountain ending'},
        ],
    }


NASTY_SPEAKER = ('Ali' + chr(39) + 'ce " [x] {y} ' + chr(0x3016) + 'z %')
NASTY_DIALOGUE = ('Choose "quoted" \\ backslash [blink] {b}bold{/b} ' + chr(0x3016) + 'ruby' +
                  chr(0x3017) + ' 100% %s %(name)s\t' + chr(0x5217) + '\n' + chr(0x7B2C) +
                  chr(0x4E8C) + chr(0x884C) + ' \U0001F642 e' + chr(0x301) + ':')
NASTY_ENDING = 'Ending {i}with{/i} [brackets] ' + chr(0x3016) + 'ruby 50% "quote"'


def rich_spec():
    return {
        'title': 'Ren' + chr(39) + 'Py [title] {x} ' + chr(0x3016) + 'ruby 10%',
        'graph_id': 'graph-esc', 'graph_version': 1, 'entry_node_id': 'n1', 'max_steps': 4,
        'variables': [{'name': 'value', 'type': 'int', 'initial': 0, 'minimum': -3, 'maximum': 3}],
        'nodes': [
            {'node_id': 'n1', 'node_version': 1, 'title': 'Escapes [1] {2}', 'character_id': 'alice',
             'dialogue': NASTY_DIALOGUE,
             'choices': [
                 {'id': 'go', 'label': 'Go' + chr(39) + ' "now" [x] {y} 50%',
                  'target': 'n2', 'condition': 'value > -2 and value <= 3', 'assignments': {'value': -1}},
                 {'id': 'wait', 'label': 'Wait', 'target': 'n2',
                  'condition': 'value >= 0', 'assignments': {'value': 3}},
             ]},
            {'node_id': 'n2', 'node_version': 1, 'title': 'End', 'dialogue': 'Bye [x] {y}',
             'ending': NASTY_ENDING},
        ],
    }


def loop_spec(max_steps=8):
    return {
        'title': 'Ren' + chr(39) + 'Py loop bridge',
        'graph_id': 'graph-loop', 'graph_version': 1, 'entry_node_id': 'n0', 'max_steps': max_steps,
        'variables': [{'name': 'flag', 'type': 'bool', 'initial': False}],
        'nodes': [
            {'node_id': 'n0', 'node_version': 1, 'title': 'Crossroads', 'dialogue': 'Again?',
             'choices': [
                 {'id': 'flip', 'label': 'Walk on', 'target': 'n1',
                  'condition': 'True', 'assignments': {'flag': True}},
                 {'id': 'end', 'label': 'Finish', 'target': 'done',
                  'condition': 'flag', 'assignments': {}},
             ]},
            {'node_id': 'n1', 'node_version': 1, 'title': 'Path', 'dialogue': 'Turn back or end',
             'choices': [
                 {'id': 'return', 'label': 'Turn back', 'target': 'n0',
                  'condition': 'True', 'assignments': {'flag': False}},
                 {'id': 'end', 'label': 'Finish now', 'target': 'done',
                  'condition': 'flag', 'assignments': {}},
             ]},
            {'node_id': 'done', 'node_version': 1, 'title': 'Done', 'ending': 'Loop ending'},
        ],
    }


def dead_end_spec():
    return {
        'title': 'Dead end bridge', 'graph_id': 'graph-dead', 'graph_version': 1,
        'entry_node_id': 'n1', 'max_steps': 4,
        'variables': [{'name': 'trusted', 'type': 'bool', 'initial': False}],
        'nodes': [
            {'node_id': 'n1', 'node_version': 1, 'title': 'Gate',
             'choices': [{'id': 'go', 'label': 'Go', 'target': 'n2',
                          'condition': 'trusted', 'assignments': {}}]},
            {'node_id': 'n2', 'node_version': 1, 'title': 'End', 'ending': 'Done'},
        ],
    }


def state_explosion_spec():
    variables = [{'name': 'v' + str(index), 'type': 'bool', 'initial': False} for index in range(13)]
    nodes = []
    for index in range(13):
        nodes.append({'node_id': 'n' + str(index), 'node_version': 1, 'title': 'Node ' + str(index),
                      'choices': [
                          {'id': 'yes', 'label': 'Yes', 'target': 'n' + str((index + 1) % 13),
                           'assignments': {'v' + str(index): True}},
                          {'id': 'no', 'label': 'No', 'target': 'n' + str((index + 1) % 13),
                           'assignments': {'v' + str(index): False}},
                          {'id': 'end', 'label': 'End', 'target': 'ending'},
                      ]})
    nodes.append({'node_id': 'ending', 'node_version': 1, 'title': 'End', 'ending': 'Done'})
    return {'title': 'Bounded Ren project', 'graph_id': 'graph-bounded', 'graph_version': 1,
            'entry_node_id': 'n0', 'nodes': nodes, 'variables': variables, 'max_steps': 128}


def step_limited_spec():
    variables = [{'name': 'v' + str(index), 'type': 'bool', 'initial': False} for index in range(13)]
    nodes = [{'node_id': 'n' + str(index), 'node_version': 1, 'title': 'Node ' + str(index),
              'choices': [{'id': 'go', 'label': 'Go', 'target': 'n' + str((index + 1) % 13),
                           'assignments': {'v' + str(index): True}}]}
             for index in range(13)]
    nodes[0]['choices'].append({'id': 'end', 'label': 'End', 'target': 'ending',
                                'condition': 'v0', 'assignments': {}})
    nodes.append({'node_id': 'ending', 'node_version': 1, 'title': 'End', 'ending': 'Done'})
    return {'title': 'Step limited Ren project', 'graph_id': 'graph-step', 'graph_version': 1,
            'entry_node_id': 'n0', 'nodes': nodes, 'variables': variables, 'max_steps': 8}


# ---------------------------------------------------------------------------
# descriptor, registry and honest evidence levels
# ---------------------------------------------------------------------------
def test_descriptor_is_the_frozen_runnable_project_surface():
    descriptor = contract.describe_target(TARGET)
    assert descriptor.target_id == TARGET
    assert descriptor.kind == 'RUNNABLE_PROJECT'
    assert descriptor.format_version == RENPY_FORMAT_VERSION == 'renpy-8-5-4-project-1'
    assert descriptor.adapter_revision == 1
    assert set(descriptor.capabilities) == set(contract.CAPABILITY_KEYS) and len(contract.CAPABILITY_KEYS) == 13
    assert descriptor.engine is not None
    assert descriptor.engine.name == 'Ren' + chr(39) + 'Py'
    assert descriptor.engine.minimum_version == '8.5.4'
    assert descriptor.engine.env_override == 'POEMSEED_RENPY_BIN'
    assert descriptor.engine.gui is True
    assert 'renpy.exe' in descriptor.engine.executables
    assert 'Ren' + chr(39) + 'Py 8.5.4' in descriptor.launch_instructions
    for level, status in descriptor.evidence.items():
        assert level in contract.EVIDENCE_LEVELS
        assert status in contract.EVIDENCE_STATUSES
    for key in ('conditions', 'bool_variables', 'int_variables', 'assignment', 'dialogue', 'choices',
                'endings', 'loops', 'step_cap', 'save', 'restore', 'unicode'):
        assert descriptor.capabilities[key].supported is True, key
    assert descriptor.capabilities['media'].supported is False
    assert TARGET in contract.available_target_ids()
    assert LEGACY_RENPY in contract.available_target_ids()
    assert TARGET in {item['target_id'] for item in contract.all_target_descriptors()}
    document = contract.contract_document()
    assert document['adapter_contract']['may_install_or_launch_engine'] is False
    assert document['adapter_contract']['may_read_arbitrary_files'] is False


def test_evidence_levels_are_honest_for_this_host():
    descriptor = contract.describe_target(TARGET)
    evidence = contract.evidence_for(TARGET)
    probe = contract.probe_engine(descriptor.engine)
    assert probe['status'] in {'READY', 'NOT_INSTALLED', 'UNSUPPORTED_VERSION', 'PROBE_FAILED'}
    assert probe['declared']['minimum_version'] == '8.5.4'
    assert evidence['SOURCE_IMPLEMENTED'] == 'PASS'
    assert evidence['FIXTURE_TESTED'] == 'PASS'
    assert evidence['GENERATED_ARTIFACT_VALIDATED'] == 'PASS'
    if probe['status'] != 'READY':
        assert evidence['TARGET_RUNTIME_EXECUTED'] == 'BLOCKED_ENVIRONMENT'
        assert evidence['SAVE_RESTORE_VERIFIED'] == 'BLOCKED_ENVIRONMENT'
        assert InteractiveStoryService._runtime_claim(evidence) == 'BLOCKED_ENVIRONMENT'
    assert evidence['WINDOWS_USABILITY_VERIFIED'] in {'NOT_RUN', 'PASS', 'PARTIAL'}
    for level, status in evidence.items():
        assert level in contract.EVIDENCE_LEVELS
        assert status in contract.EVIDENCE_STATUSES


# ---------------------------------------------------------------------------
# generated project structure and payload safety
# ---------------------------------------------------------------------------
def test_project_payload_is_complete_safe_and_runtime_free():
    spec = branching_spec()
    bundle = build_bundle(spec, characters={'alice': 'Alice'})
    files = payload_of(bundle)
    assert set(files) == EXPECTED_PROJECT_FILES
    assert bundle.kind == 'RUNNABLE_PROJECT'
    assert bundle.target_format_version == RENPY_FORMAT_VERSION
    assert bundle.adapter_revision == 1
    total = 0
    for path, content in files.items():
        assert contract.safe_bundle_path(path) == path
        assert path.isascii() and len(path) <= contract.MAX_PATH_LENGTH
        assert len(content) <= contract.MAX_FILE_BYTES
        assert path.lower() not in RESERVED_INJECTED
        assert path.rsplit('.', 1)[-1].lower() in {suffix[1:] for suffix in ALLOWED_SUFFIXES}
        text = content.decode('utf-8')
        assert text
        total += len(content)
    assert total <= contract.MAX_TOTAL_BYTES
    joined = b''.join(files.values())
    assert b'PK\x03\x04' not in joined
    assert b'\x00' not in joined
    engine_or_media_suffixes = ('.exe', '.dll', '.png', '.jpg', '.jpeg', '.wav', '.mp3', '.ogg', '.ttf', '.otf')
    assert not any(path.lower().endswith(engine_or_media_suffixes) for path in files)
    manifest = bundle.manifest
    receipt = bundle.receipt
    assert manifest['target_kind'] == 'RUNNABLE_PROJECT'
    assert manifest['target_id'] == TARGET and receipt['target_id'] == TARGET
    assert receipt['capabilities_supported'] and receipt['capabilities_unsupported'] == ['media']
    assert 'MEDIA_REFERENCES_NOT_EMBEDDED_OR_PLAYED' in receipt['losses']
    extra = manifest['extra']['renpy_project']
    assert extra['witness_count'] == len(analyze(normalize(spec))['endings']) > 1
    assert extra['engine_bundled'] is False
    assert extra['media_bytes_packaged'] is False
    assert extra['engine_minimum_version'] == '8.5.4'
    assert extra['script_path'] == 'game/script.rpy'
    assert extra['witness_path'] == 'acceptance/witness.json'


def test_build_is_pure_deterministic_and_never_opens_files(monkeypatch):
    spec = branching_spec()
    snapshot = direct_snapshot(spec, characters={'alice': 'Alice'})
    options = {'include_witness': True, 'story_filename': 'story', 'target_options': {}}
    opened = []

    def forbidden_open(*args, **kwargs):
        opened.append(args)
        raise AssertionError('adapter performed file IO: %r' % (args,))

    monkeypatch.setattr(builtins, 'open', forbidden_open)
    monkeypatch.setattr(io, 'open', forbidden_open)
    first = renpy_target.build(deepcopy(snapshot), deepcopy(options))
    second = renpy_target.build(deepcopy(snapshot), deepcopy(options))
    assert opened == []
    assert first == second
    assert set(first['files']) == EXPECTED_PROJECT_FILES
    assert first['manifest_extra'] == second['manifest_extra']


def test_build_rejects_unsupported_options_filename_and_missing_speaker():
    snapshot = direct_snapshot(branching_spec(), characters={'alice': 'Alice'})
    base = {'include_witness': True, 'story_filename': 'story', 'target_options': {}}
    with pytest.raises(ValueError):
        renpy_target.build(deepcopy(snapshot), {**base, 'target_options': {'any_option': True}})
    with pytest.raises(ValueError):
        renpy_target.build(deepcopy(snapshot), {**base, 'story_filename': '../evil'})
    with pytest.raises(ValueError):
        renpy_target.build(deepcopy(snapshot), {**base, 'story_filename': 'bad name'})
    missing = direct_snapshot(branching_spec(), characters={})
    with pytest.raises(ValueError):
        renpy_target.build(deepcopy(missing), dict(base))
    report = contract.compatibility_report(TARGET, missing)
    assert report['can_export'] is False
    assert any(issue['code'] == 'RENPY_SPEAKER_UNAVAILABLE' for issue in report['issues'])


def test_story_filename_option_maps_to_renpy_script_convention():
    spec = branching_spec()
    default_bundle = build_bundle(spec, characters={'alice': 'Alice'})
    assert 'game/script.rpy' in default_bundle.files
    custom = build_bundle(spec, characters={'alice': 'Alice'},
                          options={'include_witness': True, 'story_filename': 'main', 'target_options': {}})
    assert 'game/main.rpy' in custom.files and 'game/script.rpy' not in custom.files
    assert custom.manifest['extra']['renpy_project']['script_path'] == 'game/main.rpy'
    witness = json.loads(custom.files['acceptance/witness.json'])
    assert witness['project']['script'] == 'game/main.rpy'
    without_witness = build_bundle(spec, characters={'alice': 'Alice'},
                                   options={'include_witness': False, 'story_filename': 'story',
                                            'target_options': {}})
    assert 'acceptance/witness.json' not in without_witness.files
    assert without_witness.manifest['extra']['renpy_project']['witness_path'] is None


# ---------------------------------------------------------------------------
# generated Ren'Py script: trusted subset structure and authority equivalence
# ---------------------------------------------------------------------------
def test_generated_script_is_trusted_subset_with_resolved_labels_and_defaults():
    spec = branching_spec()
    project = projection(spec)
    bundle = build_bundle(spec, characters={'alice': 'Alice'})
    parsed = parse_script(bundle.files['game/script.rpy'].decode('utf-8'))
    expected_labels = {'start', *project['labels'].values()}
    assert set(parsed['labels']) == expected_labels
    assert len(parsed['labels']) == len(spec['nodes']) + 1
    expected_defaults = [{'name': 'ans_steps', 'value': 0}]
    for variable in project['spec']['variables']:
        expected_defaults.append({'name': project['names'][variable['name']], 'value': variable['initial']})
    assert [{'name': d['name'], 'value': d['value']} for d in parsed['defaults']] == expected_defaults
    every_label = set(parsed['labels'])
    for statements in parsed['labels'].values():
        for statement in statements:
            if statement['kind'] == 'jump':
                assert statement['label'] in every_label
            for item in statement.get('items') or []:
                jumps = [body['label'] for body in item['body'] if body['kind'] == 'jump']
                assert jumps and jumps[0] in every_label
    start = parsed['labels']['start']
    assert start[0] == {'kind': 'assign', 'name': 'ans_steps', 'value': 0}
    assert [statement['name'] for statement in start[:-1]] == ['ans_steps', *project['names'].values()]
    assert start[-1] == {'kind': 'jump', 'label': project['labels'][spec['entry_node_id']]}
    # every non-ending label guards the step cap, guards the empty menu, then menus.
    for node_id, label in project['labels'].items():
        statements = parsed['labels'][label]
        node = project['nodes'][node_id]
        if node['ending']:
            assert [statement['kind'] for statement in statements][-2:] == ['say', 'return']
            continue
        kinds = [statement['kind'] for statement in statements]
        assert kinds.count('step_cap') == 1 and kinds.count('no_choice_guard') == 1 and kinds.count('menu') == 1
        assert kinds.index('step_cap') < kinds.index('no_choice_guard') < kinds.index('menu')
        menu = statements[kinds.index('menu')]
        assert len(menu['items']) == len(node['choices'])
    for label, statements in parsed['labels'].items():
        if label == 'start':
            continue
        for statement in statements:
            assert statement['kind'] in {'say', 'return', 'jump', 'menu', 'assign', 'incr',
                                         'step_cap', 'no_choice_guard'}


def test_generated_script_menu_conditions_assignments_and_bounds_match_authority():
    spec = rich_spec()
    project = projection(spec)
    nodes, compiled, issues = compile_story(project['spec'])
    assert issues == []
    bundle = build_bundle(spec, characters={'alice': NASTY_SPEAKER})
    parsed = parse_script(bundle.files['game/script.rpy'].decode('utf-8'))
    variables = {variable['name']: variable for variable in project['spec']['variables']}
    for node_id, label in project['labels'].items():
        node = nodes[node_id]
        if node['ending']:
            continue
        statements = parsed['labels'][label]
        step_cap = next(statement for statement in statements if statement['kind'] == 'step_cap')
        assert step_cap['limit'] == spec['max_steps']
        assert unescape(step_cap['message']) == STEP_CAP_MESSAGE
        no_choice = next(statement for statement in statements if statement['kind'] == 'no_choice_guard')
        assert unescape(no_choice['message']) == NO_CHOICE_MESSAGE
        menu = next(statement for statement in statements if statement['kind'] == 'menu')
        expected_conditions = [renpy_expression(compiled[(node_id, choice['id'])], project['names'])
                               for choice in node['choices']]
        assert [item['condition'] for item in menu['items']] == expected_conditions
        assert no_choice['condition'] == ' or '.join(expected_conditions)
        assert [unescape(item['caption']) for item in menu['items']] == [choice['label'] for choice in node['choices']]
        for item, choice in zip(menu['items'], node['choices']):
            kinds = [statement['kind'] for statement in item['body']]
            assert kinds[0] == 'incr' and kinds[-1] == 'jump'
            assignments = item['body'][1:-1]
            assert all(statement['kind'] == 'assign' for statement in assignments)
            expected_assignments = [(project['names'][name], value) for name, value in choice['assignments'].items()]
            assert [(statement['name'], statement['value']) for statement in assignments] == expected_assignments
            assert item['body'][-1] == {'kind': 'jump', 'label': project['labels'][choice['target']]}
            for name, value in choice['assignments'].items():
                variable = variables[name]
                assert type(value) is (bool if variable['type'] == 'bool' else int)
                if variable['type'] == 'int':
                    assert variable['minimum'] <= value <= variable['maximum']
            # menu conditions are exactly the authority compile_story trees, not re-derived text
            assert _evaluate(item['condition'], {'ans_var_0': 0}) == \
                interpret(compiled[(node_id, choice['id'])], {'value': 0})


def test_generated_project_contains_no_python_imports_io_network_or_absolute_paths():
    bundle = build_bundle(rich_spec(), characters={'alice': NASTY_SPEAKER})
    for path in ('game/script.rpy', 'game/options.rpy', 'game/screens.rpy'):
        text = bundle.files[path].decode('utf-8')
        for pattern in FORBIDDEN_SCRIPT_PATTERNS:
            assert not re.search(pattern, text), (path, pattern)
        assert not re.search(r'^\s*(python|init\s+python)\b', text, re.M)
        assert not re.search(r'^\s*[A-Za-z_][A-Za-z0-9_]*\s*=\s*', text, re.M) or path == 'game/options.rpy'
    options = bundle.files['game/options.rpy'].decode('utf-8')
    for line in options.splitlines():
        if line.startswith('define '):
            assert re.fullmatch(r'define [A-Za-z_.]+ = (?:"(?:[^"\\]|\\.)*"|True|False)', line), line
    assert 'define config.name = ' in options


def test_user_text_and_menu_labels_are_escaped_into_single_literals():
    spec = rich_spec()
    project = projection(spec)
    script = build_bundle(spec, characters={'alice': NASTY_SPEAKER}).files['game/script.rpy'].decode('utf-8')
    parsed = parse_script(script)
    node_id = 'n1'
    says = [statement for statement in parsed['labels'][project['labels'][node_id]] if statement['kind'] == 'say']
    assert len(says) == 1
    assert says[0]['who'] is not None and unescape(says[0]['who']) == NASTY_SPEAKER
    assert unescape(says[0]['what']) == NASTY_DIALOGUE
    raw_line = next(line for line in script.splitlines() if 'ruby' in line and 'Choose' in line)
    assert '\n' not in raw_line and '\\n' in raw_line and '\\t' in raw_line
    assert raw_line.count(chr(0x5217) + '\n' + chr(0x7B2C)) == 0
    menu = next(statement for statement in parsed['labels'][project['labels'][node_id]]
                if statement['kind'] == 'menu')
    assert [unescape(item['caption']) for item in menu['items']] == \
        [choice['label'] for choice in project['nodes'][node_id]['choices']]
    ending_label = project['labels']['n2']
    ending_says = [statement for statement in parsed['labels'][ending_label] if statement['kind'] == 'say']
    assert unescape(ending_says[-1]['what']) == NASTY_ENDING
    options = build_bundle(spec, characters={'alice': NASTY_SPEAKER}).files['game/options.rpy'].decode('utf-8')
    name_value = re.search(r'^define config.name = (.+)$', options, re.M).group(1)
    assert unescape(json.loads(name_value)) == spec['title']
    assert '\n' not in name_value


def test_adversarial_text_cannot_inject_script_statements():
    injected = (chr(10) + "label injected:" + chr(10) + "    $ dangerous()" + chr(10) + chr(34) +
                chr(10) + "label injected2:" + chr(10) + "    python:" + chr(10) +
                "        import os" + chr(10) + chr(34) + " [x] {y} " + chr(0x3016) + "r %")
    spec = branching_spec()
    spec['nodes'][0]['dialogue'] = injected
    spec['nodes'][1]['ending'] = ('End' + chr(10) + 'label injected3:' + chr(10) +
                                  "    $ dangerous()")
    bundle = build_bundle(spec, characters={'alice': 'Alice' + chr(10) + 'label injected4:'})
    script = bundle.files['game/script.rpy'].decode('utf-8')
    parsed = parse_script(script)
    assert len(parsed['labels']) == len(spec['nodes']) + 1
    expected_labels = projection(spec)['labels']
    top_level_labels = [line[len("label "):-1] for line in script.splitlines()
                        if line.startswith("label ")]
    assert top_level_labels == ['start', *expected_labels.values()]
    assert not any(line.lstrip().startswith('$ dangerous') for line in script.splitlines())
    says = [statement for statement in parsed['labels'][expected_labels['n1']]
            if statement['kind'] == 'say']
    assert len(says) == 1 and says[0]['who'] is not None
    assert 'label injected:' in unescape(says[0]['what'])
    assert 'python:' in unescape(says[0]['what'])

def test_options_and_screens_are_minimal_self_authored_project_files():
    spec = branching_spec()
    bundle = build_bundle(spec, characters={'alice': 'Alice'})
    files = payload_of(bundle)
    options = files['game/options.rpy'].decode('utf-8')
    assert 'define config.name = ' in options
    assert 'define config.version = ' in options
    assert 'define build.name = ' in options
    assert 'define config.save_directory = ' in options
    assert 'define config.old_substitutions = True' in options
    assert 'gui/' not in options and '.png' not in options and 'add gui.' not in options
    assert 'launcher template file is copied' in options
    screens = files['game/screens.rpy'].decode('utf-8')
    assert screens == SCREENS_RPY.decode('utf-8')
    assert re.findall(r'^screen (\w+)', screens, re.M) == ['say', 'choice', 'main_menu']
    for required in ('id "window"', 'id "who"', 'id "what"', 'tag menu',
                     'action Start()', 'action Quit(confirm=False)'):
        assert required in screens
    assert 'gui/' not in screens and '.png' not in screens and 'use navigation' not in screens
    assert 'python:' not in screens


def test_readme_documents_extraction_launcher_flow_limits_and_evidence():
    spec = branching_spec()
    readme = build_bundle(spec, characters={'alice': 'Alice'}).files['README.txt'].decode('utf-8')
    for phrase in (
        'Ren' + chr(39) + 'Py 8.5.4',
        'NEW EMPTY directory',
        'Do NOT extract over',
        'launcher',
        'Projects Directory',
        'Launch Project',
        'does NOT contain',
        'engine',
        'Save compatibility across re-exported story revisions is NOT guaranteed',
        'acceptance/witness.json',
        'BLOCKED_ENVIRONMENT',
        'TARGET_RUNTIME_EXECUTED=BLOCKED_ENVIRONMENT',
        'replayable',
    ):
        assert phrase in readme, phrase


def test_ending_nodes_display_the_approved_ending_text_then_return():
    spec = branching_spec()
    project = projection(spec)
    parsed = parse_script(build_bundle(spec, characters={'alice': 'Alice'}).files['game/script.rpy'].decode('utf-8'))
    for node_id, node in project['nodes'].items():
        if not node['ending']:
            continue
        statements = parsed['labels'][project['labels'][node_id]]
        assert statements[-1] == {'kind': 'return'}
        assert statements[-2]['kind'] == 'say'
        assert unescape(statements[-2]['what']) == node['ending']
        if node['dialogue']:
            assert statements[-3]['kind'] == 'say'
            assert unescape(statements[-3]['what']) == node['dialogue']
        assert not any(statement['kind'] in {'menu', 'jump', 'step_cap', 'no_choice_guard'}
                       for statement in statements)


def test_loop_cycle_is_generated_and_replay_resets_state():
    spec = normalize(loop_spec())
    analysis = analyze(spec)
    assert analysis['can_review'] is True and analysis['analysis_complete'] is True
    assert analysis['step_limit_reached'] is False
    project = projection(spec)
    parsed = parse_script(build_bundle(spec).files['game/script.rpy'].decode('utf-8'))
    path = ['flip', 'return', 'flip', 'end']
    snapshots = simulate(project, spec, parsed, path)
    assert len(snapshots) == len(path) + 1
    assert snapshots[0]['label'] == project['labels'][spec['entry_node_id']]
    assert snapshots[0]['variables'] == {'flag': False}
    assert snapshots[2]['label'] == snapshots[0]['label'] and snapshots[2]['variables'] == {'flag': False}
    assert snapshots[-1]['status'] == 'ENDING'
    assert_states_match(spec, snapshots, path)
    replay = simulate(project, spec, parsed, path)
    assert replay == snapshots
    assert parsed['labels']['start'][0] == {'kind': 'assign', 'name': 'ans_steps', 'value': 0}
    declared = {default['name']: default['value'] for default in parsed['defaults']}
    assert declared == {'ans_steps': 0, 'ans_var_0': False}


def enumerate_paths(spec, limit=64):
    spec = StorySpec.model_validate(spec).model_dump()
    paths, seen, queue = [], set(), [()]
    while queue and len(paths) < limit:
        path = queue.pop(0)
        state = play(spec, list(path))
        key = (state['node']['node_id'], tuple(sorted(state['variables'].items())))
        if key in seen:
            continue
        seen.add(key)
        if state['status'] == 'ENDING':
            paths.append(list(path))
            continue
        for choice in state['choices']:
            if choice['enabled'] and len(path) < spec['max_steps']:
                queue.append(path + (choice['id'],))
    return paths


def test_simulated_generated_script_matches_authority_for_every_reachable_path():
    for spec in (branching_spec(), rich_spec(), loop_spec()):
        project = projection(spec)
        parsed = parse_script(build_bundle(
            spec, characters={'alice': NASTY_SPEAKER},
        ).files['game/script.rpy'].decode('utf-8'))
        paths = enumerate_paths(spec)
        assert paths, 'fixture must have reachable ending paths'
        for path in paths:
            snapshots = simulate(project, spec, parsed, path)
            assert_states_match(spec, snapshots, path)


def test_acceptance_witness_matches_authority_play_and_manifest_extra():
    spec = normalize(branching_spec())
    analysis = analyze(spec)
    bundle = build_bundle(spec, characters={'alice': 'Alice'})
    witness = json.loads(bundle.files['acceptance/witness.json'])
    assert witness['schema'] == WITNESS_SCHEMA
    assert witness['target_id'] == TARGET
    assert witness['target_format_version'] == RENPY_FORMAT_VERSION
    assert witness['project']['engine_bundled'] is False
    assert witness['project']['script'] == 'game/script.rpy'
    assert witness['story']['spec_digest'] == bundle.manifest['story']['spec_digest']
    assert witness['story']['story_id'] == 'story-1' and witness['story']['revision'] == 2
    assert witness['witness_count'] == len(analysis['endings']) > 1
    assert witness['truncated'] is False
    assert witness['state_count'] == sum(len(item['choices']) + 1 for item in witness['witnesses'])
    for recorded in witness['witnesses']:
        assert recorded['choices'] in [ending['choices'] for ending in analysis['endings']]
        expected = expected_states(spec, recorded['choices'])
        assert len(recorded['states']) == len(expected)
        for actual, wanted in zip(recorded['states'], expected):
            assert actual['node_id'] == wanted['node_id']
            assert actual['steps'] == wanted['steps'] and actual['index'] == wanted['steps']
            assert actual['variables'] == wanted['variables']
            assert actual['enabled_choice_ids'] == wanted['enabled_choice_ids']
            assert actual['status'] == wanted['status']
        assert recorded['states'][-1]['status'] == 'ENDING'
        ending_nodes = {node['node_id']: node for node in spec['nodes']}
        assert recorded['ending'] == ending_nodes[recorded['ending_node_id']]['ending']
    extra = bundle.manifest['extra']['renpy_project']
    assert extra['witness_count'] == witness['witness_count']
    assert extra['witness_state_count'] == witness['state_count']
    assert extra['witness_truncated'] is False


# ---------------------------------------------------------------------------
# compatibility, media references and analysis limits
# ---------------------------------------------------------------------------
def test_compatibility_reports_media_as_reference_only_loss():
    media_manifest = [{
        'asset_id': 'asset-1', 'version': 1, 'sha256': 'a' * 64, 'kind': 'image',
        'missing': False, 'packaged': False, 'reason': 'TEXT_SUBSET_REFERENCE_ONLY',
    }]
    snapshot = direct_snapshot(branching_spec(), characters={'alice': 'Alice'},
                               media_manifest=media_manifest)
    report = contract.compatibility_report(TARGET, snapshot)
    assert report['target_id'] == TARGET
    assert report['can_export'] is True
    assert set(report['capabilities']) == set(contract.CAPABILITY_KEYS)
    media = report['capabilities']['media']
    assert media['supported'] is False and media['lossy'] is True
    assert '1 approved asset reference' in media['note']
    assert 'MEDIA_REFERENCES_NOT_EMBEDDED_OR_PLAYED' in report['losses']
    assert report['notes']
    bundle = contract.build_export_bundle(TARGET, deepcopy(snapshot),
                                          {'include_witness': True, 'target_options': {}})
    witness = json.loads(bundle.files['acceptance/witness.json'])
    assert witness['media_references'] == [{
        'asset_id': 'asset-1', 'kind': 'image', 'version': 1, 'missing': False, 'packaged': False,
    }]
    readme = bundle.files['README.txt'].decode('utf-8')
    assert 'asset-1' in readme
    assert bundle.manifest['story']['media_manifest_digest'] == contract.digest(media_manifest)
    assert not any('asset-1' in path for path in bundle.files)
    assert b'PNG' not in b''.join(payload_of(bundle).values())


def test_compatibility_blocks_incomplete_analysis_state_and_step_limits():
    dead = direct_snapshot(dead_end_spec())
    report = contract.compatibility_report(TARGET, dead)
    assert report['can_export'] is False
    codes = {issue['code'] for issue in report['issues']}
    assert 'CONDITIONAL_NO_EXIT' in codes
    assert 'NO_REACHABLE_ENDING_WITHIN_CAP' in codes
    with pytest.raises(ValueError):
        contract.build_export_bundle(TARGET, deepcopy(dead), {'include_witness': True, 'target_options': {}})
    forged = deepcopy(dead)
    forged['analysis'] = {
        'can_review': True, 'analysis_complete': True, 'issues': [], 'warnings': [], 'endings': [],
        'states_checked': 1, 'state_limit_reached': False, 'step_limit_reached': False, 'max_steps': 4,
    }
    with pytest.raises(ValueError):
        renpy_target.build(forged, {'include_witness': True, 'target_options': {}})
    explosion = contract.compatibility_report(TARGET, direct_snapshot(state_explosion_spec()))
    assert explosion['can_export'] is False
    assert 'STORY_ANALYSIS_STATE_LIMIT' in {issue['code'] for issue in explosion['issues']}
    step_limited = contract.compatibility_report(TARGET, direct_snapshot(step_limited_spec()))
    assert step_limited['can_export'] is False
    assert 'STORY_ANALYSIS_STEP_LIMIT' in {issue['code'] for issue in step_limited['issues']}


def test_witness_is_bounded_declared_and_never_claims_runtime_execution():
    from app.experimental.interactive_targets.renpy import witness as renpy_witness
    bundle = build_bundle(branching_spec(), characters={'alice': 'Alice'})
    witness = json.loads(bundle.files['acceptance/witness.json'])
    assert witness['state_limit'] == renpy_witness.WITNESS_STATE_LIMIT
    assert witness['byte_limit'] == renpy_witness.WITNESS_BYTE_LIMIT
    assert witness['truncated'] is False
    assert witness['coverage'] == 'ONE_WITNESS_PER_DISCOVERED_ENDING_WITH_PER_STEP_PLAY_STATES_NOT_ALL_PATHS'
    assert witness['expected_runtime_behavior'] and witness['how_to_use']
    descriptor_evidence = contract.evidence_for(TARGET)
    assert witness['runtime_evidence'] == {str(level): str(status)
                                           for level, status in sorted(descriptor_evidence.items())}
    assert witness['runtime_evidence']['TARGET_RUNTIME_EXECUTED'] in {'BLOCKED_ENVIRONMENT', 'PASS'}
    assert witness['project']['engine_minimum_version'] == '8.5.4'
    assert witness['schema'] == WITNESS_SCHEMA


# ---------------------------------------------------------------------------
# service-facing end-to-end: export-targets, preview, deterministic ZIP records
# ---------------------------------------------------------------------------
def test_service_export_targets_reports_runnable_renpy_project(renpy_env):
    e = renpy_env
    row = create_approved(e)
    value = {'expected_version': row['version']}
    targets = e.service.export_targets(e.nid, e.scope, 'author', row['id'], value)
    assert targets['schema'] == contract.TARGETS_SCHEMA
    assert targets['contract_version'] == contract.CONTRACT_VERSION
    target = export_target_row(targets)
    assert target['kind'] == 'RUNNABLE_PROJECT'
    assert target['format_version'] == RENPY_FORMAT_VERSION
    assert target['adapter_revision'] == 1
    assert target['export_ready'] is True
    assert target['compatibility']['can_export'] is True
    assert set(target['capabilities']) == set(contract.CAPABILITY_KEYS)
    assert target['runtime_claim'] == 'BLOCKED_ENVIRONMENT'
    assert target['engine_probe']['status'] in {'NOT_INSTALLED', 'READY', 'UNSUPPORTED_VERSION', 'PROBE_FAILED'}
    assert target['engine_probe']['declared']['minimum_version'] == '8.5.4'
    assert target['evidence']['TARGET_RUNTIME_EXECUTED'] in {'BLOCKED_ENVIRONMENT', 'PASS'}
    assert targets['can_export_any'] is True
    assert targets['witness']
    assert targets['story']['spec_digest'] == contract.digest(row['spec'])
    ids = {item['target_id'] for item in targets['targets']}
    assert {LEGACY_RENPY, 'GODOT_4_DATA_ADAPTER', 'INKJS_2_3_2_TYPED_TEXT_SUBSET', TARGET} <= ids
    legacy = next(item for item in targets['targets'] if item['target_id'] == LEGACY_RENPY)
    assert legacy['kind'] == 'LEGACY_FRAGMENT' and legacy['format_version'] == 'legacy-text-menu-1'


def test_service_exports_complete_project_zip_with_bound_manifest_and_receipt(renpy_env):
    e = renpy_env
    row = create_approved(e)
    preview, exported, content, files = export_zip(e, row)
    assert preview['can_export'] is True
    assert preview['target_id'] == TARGET
    assert preview['selected_target']['target_id'] == TARGET
    assert exported['target_id'] == TARGET
    assert exported['target_format_version'] == RENPY_FORMAT_VERSION
    assert exported['adapter_revision'] == 1
    assert exported['runtime_claim'] == 'BLOCKED_ENVIRONMENT'
    assert exported['published'] is False
    assert hashlib.sha256(content).hexdigest() == exported['sha256']
    assert set(files) == EXPECTED_PROJECT_FILES | RESERVED_INJECTED
    manifest = json.loads(files['manifest.json'])
    receipt = json.loads(files['source-receipt.json'])
    payload = {path: value for path, value in files.items() if path not in RESERVED_INJECTED}
    assert manifest['schema'] == contract.MANIFEST_SCHEMA
    assert receipt['schema'] == contract.RECEIPT_SCHEMA
    assert manifest['contract_version'] == contract.CONTRACT_VERSION
    assert manifest['target_kind'] == 'RUNNABLE_PROJECT'
    assert manifest['target_id'] == TARGET and receipt['target_id'] == TARGET
    assert manifest['story']['spec_digest'] == contract.digest(row['spec'])
    assert receipt['spec_digest'] == manifest['story']['spec_digest']
    assert receipt['source_digest'] == manifest['story']['source_digest']
    assert receipt['manifest_sha256'] == hashlib.sha256(files['manifest.json']).hexdigest()
    assert manifest['payload_files_digest'] == contract.files_digest(payload)
    assert receipt['payload_files_digest'] == manifest['payload_files_digest']
    assert [entry['path'] for entry in manifest['files']] == sorted(payload)
    for entry in manifest['files']:
        assert entry['bytes'] == len(payload[entry['path']])
        assert entry['sha256'] == hashlib.sha256(payload[entry['path']]).hexdigest()
    assert manifest['runtime']['evidence'] == contract.evidence_for(TARGET)
    assert manifest['runtime']['evidence']['TARGET_RUNTIME_EXECUTED'] == 'BLOCKED_ENVIRONMENT'
    assert manifest['generation']['wall_clock_included'] is False
    assert manifest['generation']['deterministic'] is True
    extra = manifest['extra']['renpy_project']
    assert extra['engine_bundled'] is False and extra['media_bytes_packaged'] is False
    assert extra['script_path'] == 'game/script.rpy'
    assert extra['witness_path'] == 'acceptance/witness.json'
    assert receipt['capabilities_unsupported'] == ['media']
    assert receipt['story_id'] == row['id'] and receipt['story_revision'] == row['version']
    assert 'MEDIA_REFERENCES_NOT_EMBEDDED_OR_PLAYED' in receipt['losses']


def test_service_export_is_deterministic_across_calls(renpy_env):
    e = renpy_env
    row = create_approved(e)
    first_preview, first_exported, first_content, first_files = export_zip(e, row)
    second_preview, second_exported, second_content, second_files = export_zip(e, row)
    assert first_preview['preview_digest'] == second_preview['preview_digest']
    assert first_exported['sha256'] == second_exported['sha256']
    assert first_content == second_content
    assert first_files == second_files


def test_service_export_requires_approval_and_complete_analysis(renpy_env):
    e = renpy_env
    draft = e.service.create_story(e.nid, e.scope, 'author', {'spec': service_spec(e)})
    value = {'expected_version': draft['version']}
    preview = e.service.export_preview(e.nid, e.scope, 'author', draft['id'], {**value, 'target_id': TARGET})
    assert preview['can_export'] is False
    assert preview['target_id'] == TARGET
    assert preview['selected_target']['export_ready'] is False
    with pytest.raises(ValueError):
        e.service.export(e.nid, e.scope, 'author', draft['id'], {
            **value, 'target_id': TARGET, 'preview_digest': preview['preview_digest']})
    dead_spec = {
        'title': 'Incomplete analysis bridge', 'graph_id': e.graph['id'], 'graph_version': 1,
        'entry_node_id': e.nodes[0], 'max_steps': 4,
        'variables': [{'name': 'trusted', 'type': 'bool', 'initial': False}],
        'nodes': [
            {'node_id': e.nodes[0], 'node_version': 1, 'title': 'Gate',
             'choices': [{'id': 'go', 'label': 'Go', 'target': e.nodes[1],
                          'condition': 'trusted', 'assignments': {}}]},
            {'node_id': e.nodes[1], 'node_version': 1, 'title': 'End', 'ending': 'Done'},
        ],
    }
    pending = e.service.create_story(e.nid, e.scope, 'author', {'spec': dead_spec})
    pending = e.service.review(e.nid, e.scope, 'author', pending['id'], {
        'expected_version': pending['version'], 'action': 'submit'})
    receipt = e.service.review_preview(e.nid, e.scope, 'author', pending['id'],
                                       {'expected_version': pending['version']})
    with pytest.raises(ValueError):
        e.service.review(e.nid, e.scope, 'author', pending['id'], {
            'expected_version': pending['version'], 'action': 'approve',
            'preview_digest': receipt['preview_digest']})
    incomplete_preview = e.service.export_preview(e.nid, e.scope, 'author', pending['id'],
                                                  {'expected_version': pending['version'], 'target_id': TARGET})
    assert incomplete_preview['can_export'] is False


def test_service_exported_witness_matches_authority_play(renpy_env):
    e = renpy_env
    row = create_approved(e)
    _preview, _exported, _content, files = export_zip(e, row)
    witness = json.loads(files['acceptance/witness.json'])
    spec = row['spec']
    analysis = analyze(spec)
    assert witness['witness_count'] == len(analysis['endings'])
    for recorded in witness['witnesses']:
        expected = expected_states(spec, recorded['choices'])
        assert len(recorded['states']) == len(expected)
        for actual, wanted in zip(recorded['states'], expected):
            assert actual['node_id'] == wanted['node_id']
            assert actual['variables'] == wanted['variables']
            assert actual['enabled_choice_ids'] == wanted['enabled_choice_ids']
            assert actual['status'] == wanted['status']
    script = files['game/script.rpy'].decode('utf-8')
    parsed = parse_script(script)
    project = projection(spec)
    for recorded in witness['witnesses']:
        snapshots = simulate(project, spec, parsed, recorded['choices'])
        assert_states_match(spec, snapshots, recorded['choices'])


def test_service_legacy_multi_file_export_still_works(renpy_env):
    import zipfile
    e = renpy_env
    row = create_approved(e)
    value = {'expected_version': row['version']}
    preview = e.service.export_preview(e.nid, e.scope, 'author', row['id'], value)
    assert preview['can_export'] is True
    exported = e.service.export(e.nid, e.scope, 'author', row['id'], {
        **value, 'preview_digest': preview['preview_digest']})
    assert exported['target_runtime'] == 'NOT_RUN'
    with zipfile.ZipFile(io.BytesIO(base64.b64decode(exported['content_base64']))) as archive:
        names = archive.namelist()
    assert any(name.endswith('game/story.rpy') for name in names)
    assert any(name.endswith('ink/story.ink') for name in names)
    assert any(name.endswith('checksums.json') for name in names)
    assert all(name.startswith('interactive-story-' + row['id'] + '/') for name in names)
