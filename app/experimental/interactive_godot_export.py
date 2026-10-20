"""B07 Godot 4 runnable runtime project export target (C line).

Target `GODOT_4_RUNTIME_PROJECT_V1` builds a complete, playable Godot 4 project from
an authorized, approved story snapshot. The GDScript runtime is a FIXED template that
is copied verbatim from `app/experimental/interactive_targets/godot/`; only
`project.godot` (project name) and the data files are story-specific. The runtime
interprets the bounded typed AST (bool/int literals and variables, eq/ne/lt/le/gt/ge,
and/or/not, bounded assignments, node transitions, choice availability, explicit step
cap) and never evaluates generated code, never uses `Expression`, never loads remote
resources and never opens arbitrary files.

This adapter is a restricted pure converter. It reads only its own module templates,
performs no external write, never installs or launches an engine and never executes
story code. It is engine-neutral from Python's point of view: real Godot execution is
performed by `scripts/verify_godot_interactive_runtime.py` and recorded as independent
evidence levels; generating the project is not running it.
"""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, model_validator

TARGET_ID = 'GODOT_4_RUNTIME_PROJECT_V1'
FORMAT_VERSION = 'godot-runtime-project-1'
ADAPTER_REVISION = 1
RUNTIME_STORY_SCHEMA = 'poemseed-godot-runtime-story/1'
RUNTIME_STORY_FORMAT = 'godot-runtime-story-1'
SAVE_SCHEMA = 'poemseed-godot-save/1'
CASES_SCHEMA = 'poemseed-godot-acceptance-cases/1'
RESULT_SCHEMA = 'poemseed-godot-runtime-result/1'
PROJECT_NAME_PREFIX = 'PoemSeed Story '
ACCEPTANCE_STDOUT_PREFIXES = (
    'POEMSEED_USERDIR ', 'POEMSEED_STORY ', 'POEMSEED_STATE ', 'POEMSEED_RESTORED ',
    'POEMSEED_SAVED ', 'POEMSEED_RESULT ', 'POEMSEED_DONE ', 'POEMSEED_ERROR ',
)
EXIT_OK = 0
EXIT_SAVE_REJECTED = 2
EXIT_FAILED = 3

TEMPLATE_DIR = 'interactive_targets/godot'
PROJECT_TEMPLATE = 'project.godot.tmpl'
PROJECT_NAME_TOKEN = '__POEMSEED_PROJECT_NAME__'
FIXED_TEMPLATE_FILES = (
    'main.gd',
    'main.tscn',
    'runtime/story_loader.gd',
    'runtime/story_runtime.gd',
    'runtime/save_store.gd',
    'runtime/acceptance_runner.gd',
)
# Documents the auditable runtime exactly: hash of every file copied verbatim from
# app/experimental/interactive_targets/godot/ into the delivered project.
# Kept in sync with the repository template; tests and the runtime verifier fail on drift.
PINNED_TEMPLATE_SHA256: dict[str, str] = {
    'main.gd': 'f43ebb34000d2278abc7a1a626ff621b90b23d06f63f32e673cc513c00b37170',
    'main.tscn': 'ac167bb92adbfb94de91e1011dd715e0d2bb4ccb1fc05486f04e33a6ac5438ca',
    'runtime/story_loader.gd': '5fbe936ef022488f72aeb16399ee84d3f5534c26ebca3c0fe0b0f7372e5ff159',
    'runtime/story_runtime.gd': '4d101c7c87f55ef84fd436f9ffb55b7b6a8b7ad13e4c20e487211bd595d56bb6',
    'runtime/save_store.gd': 'f69fe3ddfe26d7afa564975863b9cf150446b27dd9712bcc766d462f96ba58ea',
    'runtime/acceptance_runner.gd': '88d2ffd1125ef142d5e057418ec86ec86d08427183bf5b62882003ec443fdd62',
}

LOSSES = [
    'MEDIA_REFERENCES_RECORDED_NOT_PACKAGED_OR_PLAYED',
    'GODOT_RUNTIME_WINDOWS_GUI_USABILITY_NOT_VERIFIED_BY_HEADLESS_AUTOMATION',
    'NO_TARGET_CUSTOM_SCREENS_ANIMATION_OR_PLUGINS',
    'GODOT_RUNTIME_SAVE_FILES_ARE_LOCAL_JSON_UNDER_USER_DIR_ONLY',
    'GODOT_RUNTIME_FONT_GLYPH_COVERAGE_NOT_VERIFIED',
]
RUNTIME_REQUIREMENTS = [
    'Godot 4.0 or newer; verified locally with Godot 4.7.stable.official (headless console build).',
    'A local writable user:// directory for optional save files; no network access is required.',
]
CAPABILITIES = {
    'conditions': (True, False, 'Bounded bool/int comparison and and/or/not tree interpreted directly.'),
    'bool_variables': True,
    'int_variables': True,
    'assignment': (True, False, 'Bounded typed assignments are applied before the node transition.'),
    'dialogue': (True, False, 'Dialogue is shown with plain Labels; BBCode/HTML is never parsed.'),
    'choices': True,
    'endings': True,
    'loops': (True, False, 'Node transitions may revisit a node; the runtime enforces the explicit step cap.'),
    'step_cap': (True, False, 'The explicit max_steps from the reviewed story is enforced by the runtime.'),
    'save': (True, False, 'Save to a bounded local user:// JSON file.'),
    'restore': (True, False, 'Restore validates story/revision/digests and replays the saved path before continuing.'),
    'unicode': (True, True, 'UTF-8 text, CJK content and escaping are preserved and compared headlessly; GUI font glyph coverage is not verified.'),
    'media': (False, True, 'Approved asset references are recorded as IDs only; no media bytes are packaged or played.'),
}
EVIDENCE = {
    'SOURCE_IMPLEMENTED': 'PASS',
    'SCHEMA_VALIDATED': 'PASS',
    'FIXTURE_TESTED': 'PASS',
    # Achieved by scripts/verify_godot_interactive_runtime.py on a real Godot 4.7
    # headless run: see docs/v2/B07_GODOT_RUNTIME_EVIDENCE_20261020.json.
    # WINDOWS_USABILITY_VERIFIED is deliberately absent: headless automation is not
    # GUI usability acceptance.
    'GENERATED_ARTIFACT_VALIDATED': 'PASS',
    'TARGET_RUNTIME_EXECUTED': 'PASS',
    'SAVE_RESTORE_VERIFIED': 'PASS',
}

DESCRIPTOR = {
    'target_id': TARGET_ID,
    'display_name': 'Godot 4 runnable runtime project',
    'kind': 'RUNNABLE_PROJECT',
    'format_version': FORMAT_VERSION,
    'adapter_revision': ADAPTER_REVISION,
    'engine': {
        'name': 'Godot', 'minimum_version': '4.0',
        'executables': ['godot', 'godot.exe', 'Godot_v4.7-stable_win64_console.exe', 'Godot_v4.7-stable_win64.exe'],
        'version_args': ['--version'], 'env_override': 'POEMSEED_GODOT_BIN',
        'search_hints': ['D:/GameDev/Godot/Godot-4.7-stable/Godot_v4.7-stable_win64_console.exe'],
        'gui': False,
        'note': 'Headless acceptance uses the console build; GUI playability is not claimed by automation.',
    },
    'capabilities': CAPABILITIES,
    'losses': LOSSES,
    'runtime_requirements': RUNTIME_REQUIREMENTS,
    'launch_instructions': (
        'Extract the delivered folder, open it with Godot 4.x ("godot --path <folder>") and press Run. '
        'Headless acceptance: "godot --headless --path <folder> -- --witness-path <choice_id,...>"; '
        'add "--save user://slot.json", "--load user://slot.json" or "--result user://result.json" for controlled checks.'
    ),
    'integration_notes': [
        'The GDScript runtime is copied verbatim from app/experimental/interactive_targets/godot/; only data is story-specific.',
        'Old target GODOT_4_DATA_ADAPTER and its godot/story.json output are unchanged; this is an independent new target.',
        'Headless execution only proves TARGET_RUNTIME_EXECUTED and SAVE_RESTORE_VERIFIED; WINDOWS_USABILITY_VERIFIED stays NOT_RUN.',
    ],
    'evidence': EVIDENCE,
}


class Frozen(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=False, populate_by_name=True, serialize_by_alias=True)


Name = Annotated[str, Field(pattern=r'^[a-z][a-z0-9_]{0,31}$')]
Digest = Annotated[str, Field(pattern=r'^[a-f0-9]{64}$')]
Scalar = StrictBool | Annotated[StrictInt, Field(ge=-10000, le=10000)]


class RuntimeLiteral(Frozen):
    op: Literal['literal']
    value: Scalar


class RuntimeVariable(Frozen):
    op: Literal['var']
    name: Name


class RuntimeNot(Frozen):
    op: Literal['not']
    arg: 'RuntimeCondition'


class RuntimeBoolean(Frozen):
    op: Literal['and', 'or']
    args: list['RuntimeCondition'] = Field(min_length=2, max_length=64)


class RuntimeComparison(Frozen):
    op: Literal['eq', 'ne', 'lt', 'le', 'gt', 'ge']
    left: 'RuntimeCondition'
    right: 'RuntimeCondition'


RuntimeCondition = Annotated[
    RuntimeLiteral | RuntimeVariable | RuntimeNot | RuntimeBoolean | RuntimeComparison, Field(discriminator='op')]
for _runtime_condition_model in (RuntimeNot, RuntimeBoolean, RuntimeComparison):
    _runtime_condition_model.model_rebuild()


class RuntimeChoice(Frozen):
    id: Name
    label: str = Field(min_length=1, max_length=240)
    target: str = Field(min_length=1, max_length=160)
    condition: RuntimeCondition
    assignments: dict[Name, Scalar] = Field(default_factory=dict, max_length=16)


class RuntimeNode(Frozen):
    node_id: str = Field(min_length=1, max_length=160)
    title: str = Field(min_length=1, max_length=240)
    dialogue: str = Field(max_length=8000)
    speaker: str = Field(default='', max_length=2000)
    ending: str = Field(default='', max_length=240)
    choices: list[RuntimeChoice] = Field(default_factory=list, max_length=8)


class RuntimeWitness(Frozen):
    node_id: str = Field(min_length=1, max_length=160)
    ending: str = Field(default='', max_length=240)
    choices: list[Name] = Field(max_length=128)


class RuntimeVariableDef(Frozen):
    name: Name
    type: Literal['bool', 'int']
    initial: Scalar
    minimum: int = Field(default=0, ge=-10000, le=10000, strict=True)
    maximum: int = Field(default=100, ge=-10000, le=10000, strict=True)

    @model_validator(mode='after')
    def bounded(self):
        if self.minimum > self.maximum: raise ValueError('invalid variable bounds')
        if self.type == 'bool' and type(self.initial) is not bool: raise ValueError('boolean initial value required')
        if self.type == 'int' and (type(self.initial) is not int or not self.minimum <= self.initial <= self.maximum):
            raise ValueError('integer initial value outside bounds')
        return self


class RuntimeMediaReference(Frozen):
    asset_id: str = Field(min_length=1, max_length=160)
    kind: Literal['image', 'audio']
    node_id: str = Field(min_length=1, max_length=160)


class GodotRuntimeStory(Frozen):
    """Machine-checked schema of data/story.json shipped in the project."""

    schema_id: Literal['poemseed-godot-runtime-story/1'] = Field(alias='schema')
    format_version: Literal['godot-runtime-story-1']
    engine_target: Literal['GODOT_4_RUNTIME_PROJECT_V1']
    story_id: Annotated[str, Field(pattern=r'^[A-Za-z0-9_-]{1,80}$')]
    revision: int = Field(ge=1, le=1000000000, strict=True)
    title: str = Field(min_length=1, max_length=160)
    spec_digest: Digest
    source_digest: Digest
    review_receipt: Digest
    entry_node_id: str = Field(min_length=1, max_length=160)
    max_steps: int = Field(ge=1, le=128, strict=True)
    variables: list[RuntimeVariableDef] = Field(default_factory=list, max_length=16)
    nodes: list[RuntimeNode] = Field(min_length=1, max_length=100)
    witness: list[RuntimeWitness] = Field(default_factory=list, max_length=100)
    media_references: list[RuntimeMediaReference] = Field(default_factory=list, max_length=200)

    @model_validator(mode='after')
    def references(self):
        node_ids = [node.node_id for node in self.nodes]
        if len(set(node_ids)) != len(node_ids): raise ValueError('duplicate node ids')
        if self.entry_node_id not in node_ids: raise ValueError('entry node missing')
        names = [definition.name for definition in self.variables]
        if len(set(names)) != len(names): raise ValueError('duplicate variable names')
        variables = {definition.name: definition for definition in self.variables}
        for node in self.nodes:
            if node.ending and node.choices: raise ValueError('ending node cannot have choices')
            if len({choice.id for choice in node.choices}) != len(node.choices): raise ValueError('duplicate choice ids')
            for choice in node.choices:
                if choice.target not in node_ids: raise ValueError('choice target missing')
                if _expression_type(choice.condition.model_dump(), {name: definition.model_dump() for name, definition in variables.items()}) is not bool:
                    raise ValueError('choice condition is not boolean')
                for name, value in choice.assignments.items():
                    definition = variables.get(name)
                    if definition is None: raise ValueError('assignment variable missing')
                    if definition.type == 'bool' and type(value) is not bool: raise ValueError('assignment type mismatch')
                    if definition.type == 'int' and (type(value) is not int or not definition.minimum <= value <= definition.maximum):
                        raise ValueError('assignment out of bounds')
        for record in self.witness:
            if record.node_id not in node_ids: raise ValueError('witness node missing')
        for reference in self.media_references:
            if reference.node_id not in node_ids: raise ValueError('media reference node missing')
        return self


def _expression_type(tree, variables):
    op = tree['op']
    if op == 'literal': return type(tree['value'])
    if op == 'var':
        definition = variables.get(tree['name'])
        if definition is None: raise ValueError('UNDEFINED_VARIABLE')
        return bool if definition['type'] == 'bool' else int
    if op in {'and', 'or', 'not'}:
        args = tree['args'] if op != 'not' else [tree['arg']]
        if any(_expression_type(arg, variables) is not bool for arg in args): raise ValueError('CONDITION_TYPE_MISMATCH')
        return bool
    left, right = _expression_type(tree['left'], variables), _expression_type(tree['right'], variables)
    if left is not right or (op not in {'eq', 'ne'} and left is not int): raise ValueError('CONDITION_TYPE_MISMATCH')
    return bool


# ---------------------------------------------------------------------------
# fixed runtime template
# ---------------------------------------------------------------------------
def template_root():
    from pathlib import Path
    return Path(__file__).resolve().parent / TEMPLATE_DIR


def read_template(relative_path: str) -> bytes:
    """Read one file from this module's own audited template directory."""
    path = template_root() / relative_path
    data = path.read_bytes()
    expected = PINNED_TEMPLATE_SHA256.get(relative_path)
    if expected and hashlib.sha256(data).hexdigest() != expected:
        raise ValueError('GODOT_RUNTIME_TEMPLATE_HASH_MISMATCH:' + relative_path)
    return data


def template_hashes() -> dict[str, str]:
    return {relative: hashlib.sha256(read_template(relative)).hexdigest() for relative in FIXED_TEMPLATE_FILES}


def project_template() -> str:
    return read_template(PROJECT_TEMPLATE).decode('utf-8')


def _render_project_godot(story_id: str) -> bytes:
    name = PROJECT_NAME_PREFIX + story_id
    template = project_template()
    if template.count(PROJECT_NAME_TOKEN) != 1: raise ValueError('GODOT_RUNTIME_PROJECT_TEMPLATE_INVALID')
    if '"' in name or '\\' in name:
        raise ValueError('GODOT_RUNTIME_PROJECT_NAME_INVALID')
    return template.replace(PROJECT_NAME_TOKEN, name).encode('utf-8')


def _encode_json(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2).encode('utf-8')


# ---------------------------------------------------------------------------
# conversion
# ---------------------------------------------------------------------------
def _analysis_issue(issue) -> dict:
    if isinstance(issue, dict):
        return {'code': 'GODOT_RUNTIME_ANALYSIS:' + str(issue.get('code', 'UNKNOWN'))[:90],
                'node_id': issue.get('node_id'), 'choice_id': issue.get('choice_id'),
                'detail': str(issue.get('detail', ''))[:400]}
    return {'code': 'GODOT_RUNTIME_ANALYSIS:UNKNOWN'}


def _node_id_unsupported(node_id) -> bool:
    if not isinstance(node_id, str) or not 1 <= len(node_id) <= 160: return True
    return any(ord(character) < 32 or ord(character) == 127 for character in node_id)


def _validate(snapshot: dict):
    """Return (context, issues, notes, analysis) for an authorized snapshot."""
    from .interactive_story import StorySpec, analyze, play

    issues: list[dict] = []
    notes: list[str] = []
    try:
        spec = StorySpec.model_validate(snapshot.get('spec')).model_dump()
    except Exception as exc:
        return {}, [{'code': 'GODOT_RUNTIME_SPEC_INVALID', 'detail': type(exc).__name__}], notes, {}
    analysis = analyze(spec)
    for issue in analysis['issues']:
        issues.append(_analysis_issue(issue))
    context = {'spec': spec, 'analysis': analysis, 'characters': dict(snapshot.get('characters') or {})}
    for node in spec['nodes']:
        if _node_id_unsupported(node['node_id']):
            issues.append({'code': 'GODOT_RUNTIME_NODE_ID_UNSUPPORTED', 'node_id': node['node_id']})
        character_id = node.get('character_id')
        if character_id:
            name = context['characters'].get(character_id)
            if not isinstance(name, str) or not name:
                issues.append({'code': 'GODOT_RUNTIME_SPEAKER_UNAVAILABLE', 'node_id': node['node_id'],
                               'character_id': character_id})
        for choice in node['choices']:
            if _node_id_unsupported(choice['target']):
                issues.append({'code': 'GODOT_RUNTIME_TARGET_UNSUPPORTED', 'node_id': node['node_id'],
                               'choice_id': choice['id']})
    witness = snapshot.get('witness') or []
    if not witness:
        issues.append({'code': 'GODOT_RUNTIME_WITNESS_MISSING'})
    for record in witness:
        choices = record.get('choices') if isinstance(record, dict) else None
        node_id = record.get('node_id') if isinstance(record, dict) else None
        ending = record.get('ending') if isinstance(record, dict) else None
        try:
            if not isinstance(choices, list) or not 1 <= len(choices) <= 128:
                raise ValueError('WITNESS_PATH_INVALID')
            final = play(spec, choices)
            if final['node']['node_id'] != node_id or final['node']['ending'] != ending or final['status'] != 'ENDING':
                raise ValueError('WITNESS_STATE_MISMATCH')
        except ValueError:
            issues.append({'code': 'GODOT_RUNTIME_WITNESS_INVALID',
                           'node_id': node_id if isinstance(node_id, str) else None})
    if not issues:
        notes.append('Bounded typed state search completed; all declared ending witnesses replay exactly.')
    notes.append('Headless runtime acceptance is recorded separately from generation; generation is not execution.')
    return context, issues, notes, analysis


def compatibility(snapshot: dict) -> dict:
    context, issues, notes, analysis = _validate(snapshot)
    if not issues:
        try:
            GodotRuntimeStory.model_validate(_story_resource(snapshot, context))
        except Exception as exc:
            issues.append({'code': 'GODOT_RUNTIME_STORY_SCHEMA_INVALID', 'detail': type(exc).__name__})
    if snapshot.get('media_manifest'):
        notes.append('The approved media manifest is not packaged: asset IDs are recorded only.')
    return {'can_export': not issues, 'capabilities': deepcopy(CAPABILITIES), 'losses': list(LOSSES),
            'issues': issues, 'notes': notes}


def _condition_tree(expression: str) -> dict:
    from .interactive_story import parse_condition
    return parse_condition(expression)


def _story_resource(snapshot: dict, context: dict) -> dict:
    spec = context['spec']
    characters = context['characters']
    node_ids = {node['node_id'] for node in spec['nodes']}
    media_references = []
    nodes = []
    for node in spec['nodes']:
        speaker = characters.get(node['character_id']) if node.get('character_id') else ''
        choices = []
        for choice in node['choices']:
            choices.append({
                'id': choice['id'], 'label': choice['label'], 'target': choice['target'],
                'condition': _condition_tree(choice['condition']),
                'assignments': dict(choice['assignments']),
            })
        nodes.append({
            'node_id': node['node_id'], 'title': node['title'], 'dialogue': node['dialogue'],
            'speaker': speaker or '', 'ending': node['ending'], 'choices': choices,
        })
        for field, kind in (('background_asset_id', 'image'), ('music_asset_id', 'audio')):
            if node.get(field):
                media_references.append({'asset_id': node[field], 'kind': kind, 'node_id': node['node_id']})
    variables = [{'name': variable['name'], 'type': variable['type'], 'initial': variable['initial'],
                  'minimum': variable['minimum'], 'maximum': variable['maximum']} for variable in spec['variables']]
    witness = []
    for record in snapshot.get('witness') or []:
        if isinstance(record, dict) and record.get('node_id') in node_ids:
            witness.append({'node_id': record['node_id'], 'ending': record.get('ending') or '',
                            'choices': list(record.get('choices') or [])})
    return {
        'schema': RUNTIME_STORY_SCHEMA,
        'format_version': RUNTIME_STORY_FORMAT,
        'engine_target': TARGET_ID,
        'story_id': snapshot['story_id'],
        'revision': snapshot['revision'],
        'title': spec['title'],
        'spec_digest': snapshot['spec_digest'],
        'source_digest': snapshot['source_digest'],
        'review_receipt': snapshot['review_receipt'],
        'entry_node_id': spec['entry_node_id'],
        'max_steps': spec['max_steps'],
        'variables': variables,
        'nodes': nodes,
        'witness': witness,
        'media_references': media_references,
    }


# ---------------------------------------------------------------------------
# authoritative step projection (shared with the runtime verifier)
# ---------------------------------------------------------------------------
def expected_state(spec: dict, characters: dict, path) -> dict:
    """Authoritative per-step projection (Python playback) used by tests and verifier."""
    from .interactive_story import play
    result = play(spec, list(path))
    node = result['node']
    speaker = characters.get(node['character_id']) if node.get('character_id') else ''
    return {
        'node': {'node_id': node['node_id'], 'title': node['title'], 'dialogue': node['dialogue'],
                 'speaker': speaker or '', 'ending': node['ending']},
        'choices': [{'id': choice['id'], 'label': choice['label'], 'enabled': choice['enabled']}
                    for choice in result['choices']],
        'variables': result['variables'],
        'steps': result['steps'],
        'max_steps': result['max_steps'],
        'status': result['status'],
        'path': list(result['path']),
    }


# ---------------------------------------------------------------------------
# acceptance cases
# ---------------------------------------------------------------------------
def acceptance_cases(snapshot: dict, context: dict) -> dict:
    spec = context['spec']
    characters = context['characters']
    cases = []
    for index, record in enumerate(snapshot.get('witness') or []):
        choices = list(record.get('choices') or [])
        final = expected_state(spec, characters, choices)
        cases.append({'case_id': 'witness-' + str(index) + '-' + str(record.get('node_id')), 'choices': choices,
                      'expected_final': final})
    return {
        'schema': CASES_SCHEMA,
        'target_id': TARGET_ID,
        'format_version': FORMAT_VERSION,
        'story_id': snapshot['story_id'],
        'revision': snapshot['revision'],
        'spec_digest': snapshot['spec_digest'],
        'source_digest': snapshot['source_digest'],
        'authority': 'Python replay of the reviewed typed AST (interactive_story.play); one witness per discovered ending.',
        'runtime': {
            'main_scene': 'res://main.tscn',
            'story_path': 'res://data/story.json',
            'headless_command': ['<godot-console>', '--headless', '--path', '.', '--'],
            'state_record_prefix': 'POEMSEED_STATE ',
            'done_record_prefix': 'POEMSEED_DONE ',
            'error_record_prefix': 'POEMSEED_ERROR ',
            'witness_argument': '--witness-path',
            'save_argument': '--save',
            'load_argument': '--load',
            'result_argument': '--result',
            'exit_codes': {'ok': EXIT_OK, 'save_rejected': EXIT_SAVE_REJECTED, 'failed': EXIT_FAILED},
        },
        'cases': cases,
        'truncated': False,
        'evidence_note': 'Generating this project is not running it; see docs/v2/B07_GODOT_RUNTIME_EVIDENCE_20261020.json.',
    }


# ---------------------------------------------------------------------------
# build
# ---------------------------------------------------------------------------
def build(snapshot: dict, options: dict | None = None) -> dict:
    options = dict(options or {})
    context, issues, notes, analysis = _validate(snapshot)
    if issues: raise ValueError('GODOT_RUNTIME_STORY_UNSUPPORTED')
    story = _story_resource(snapshot, context)
    story_bytes = _encode_json(story)
    try:
        GodotRuntimeStory.model_validate_json(story_bytes)
    except Exception as exc:
        raise ValueError('GODOT_RUNTIME_STORY_ROUND_TRIP_FAILED') from exc
    files: dict[str, bytes] = {}
    for relative in FIXED_TEMPLATE_FILES:
        files[relative] = read_template(relative)
    files['project.godot'] = _render_project_godot(snapshot['story_id'])
    files['data/story.json'] = story_bytes
    files['data/story.schema.json'] = _encode_json(GodotRuntimeStory.model_json_schema(by_alias=True))
    cases = acceptance_cases(snapshot, context)
    files['acceptance/cases.json'] = _encode_json(cases)
    files['acceptance/README.txt'] = _acceptance_readme(snapshot, context).encode('utf-8')
    files['README.md'] = _readme(snapshot, context, cases).encode('utf-8')
    manifest_extra = {
        'godot_runtime': {
            'runtime_story_schema': RUNTIME_STORY_SCHEMA,
            'runtime_story_format': RUNTIME_STORY_FORMAT,
            'save_schema': SAVE_SCHEMA,
            'result_schema': RESULT_SCHEMA,
            'main_scene': 'res://main.tscn',
            'story_path': 'res://data/story.json',
            'save_path_policy': 'user:// plus plain ASCII segments and .json suffix, bounded 64 KiB',
            'template_files': {relative: hashlib.sha256(files[relative]).hexdigest() for relative in FIXED_TEMPLATE_FILES},
            'project_name': PROJECT_NAME_PREFIX + snapshot['story_id'],
            'entry_node_id': story['entry_node_id'],
            'max_steps': story['max_steps'],
            'nodes': len(story['nodes']),
            'variables': len(story['variables']),
            'witness_endings': len(story['witness']),
            'acceptance_command_shape': ['<godot-console>', '--headless', '--path', '<project>', '--',
                                         '--witness-path', '<choice_id,...>'],
            'stdout_record_prefixes': list(ACCEPTANCE_STDOUT_PREFIXES),
            'exit_codes': {'ok': EXIT_OK, 'save_rejected': EXIT_SAVE_REJECTED, 'failed': EXIT_FAILED},
        },
    }
    return {'files': files, 'manifest_extra': manifest_extra}


def _readme(snapshot: dict, context: dict, cases: dict) -> str:
    spec = context['spec']
    example = cases['cases'][0]['choices'][0] if cases['cases'] else 'choice_id'
    lines = [
        '# PoemSeed interactive story - Godot 4 runtime project',
        '',
        'Target: ' + TARGET_ID + ' (' + FORMAT_VERSION + ', kind RUNNABLE_PROJECT, adapter revision ' + str(ADAPTER_REVISION) + ').',
        '',
        'Story: ' + spec['title'],
        '- story id: ' + snapshot['story_id'],
        '- revision: ' + str(snapshot['revision']),
        '- spec digest: ' + snapshot['spec_digest'],
        '- source digest: ' + snapshot['source_digest'],
        '- review receipt: ' + snapshot['review_receipt'],
        '- entry node: ' + spec['entry_node_id'] + ', nodes: ' + str(len(spec['nodes'])),
        '- variables: ' + str(len(spec['variables'])) + ', max steps: ' + str(spec['max_steps']),
        '',
        '## Run it',
        '',
        '1. Install Godot 4.x (this project was generated for Godot 4 and verified with 4.7.stable).',
        '2. Open this folder from the Godot project manager, or run:',
        '   godot --path <this folder>',
        '3. Press Run. The window is 960x600; dialogue and choices are plain Labels and Buttons.',
        '',
        'The project reads only res://data/story.json. Media references are recorded as IDs in',
        'data/story.json but no media bytes are packaged or played. The story text is plain:',
        'BBCode, HTML and expressions are never parsed.',
        '',
        '## Headless acceptance (controlled)',
        '',
        'After the engine separator --, the runtime accepts:',
        '',
        '- --witness-path <id,id,...> replay one recorded choice path and print every step as JSON',
        '- --save user://slot.json save the current state (bounded local JSON)',
        '- --load user://slot.json load and validate a save before continuing',
        '- --result user://result.json write the final structured result',
        '',
        'Example: godot --headless --path <this folder> -- --witness-path ' + example,
        '',
        'Each step prints POEMSEED_STATE {json} with node, variables, choice enabled flags, steps and status.',
        'Exit code 0 is success, 2 is a rejected or mismatched save, 3 is a data or argument failure.',
        '',
        '## Safety contract',
        '',
        '- The runtime is the fixed GDScript template shipped with PoemSeed Studio; it is NOT generated per story.',
        '- It interprets only the bounded typed AST: bool/int values, restricted comparisons, and/or/not,',
        '  bounded assignments, node transitions, choice availability and an explicit step cap.',
        '- There is no eval, Expression.execute, dynamic code, network access, or arbitrary file access.',
        '- Save files are local user:// JSON with story id, revision, source digest and replay validation;',
        '  a mismatched save is rejected instead of applied.',
        '- Labels and Buttons are plain text and never render BBCode/HTML.',
        '',
        '## Evidence',
        '',
        'Generating this project is not running it. Independent evidence levels are recorded by the',
        'exporting product; only headless runtime execution and save/restore were claimed after real runs.',
        'See the export manifest.json and docs/v2/B07_GODOT_RUNTIME_EVIDENCE_20261020.json in the repository.',
        '',
    ]
    return '\n'.join(lines)


def _acceptance_readme(snapshot: dict, context: dict) -> str:
    spec = context['spec']
    return '\n'.join([
        'PoemSeed B07 Godot runtime acceptance cases',
        '',
        'acceptance/cases.json was generated from the reviewed typed AST by deterministic Python',
        'playback (interactive_story.play). It lists one witness per discovered ending with the',
        'authoritative final-state projection. Use it with:',
        '',
        '  godot --headless --path <project> -- --witness-path <case choices joined by comma>',
        '',
        'Compare each printed POEMSEED_STATE record and the final POEMSEED_DONE record with the',
        'expected final state. story id ' + snapshot['story_id'] + ', revision ' + str(snapshot['revision']) + '.',
        'max steps ' + str(spec['max_steps']) + ', endings ' + str(len(snapshot.get('witness') or [])) + '.',
        '',
    ])


def lifecycle() -> dict:
    return {'execution': 'BOUNDED_SYNCHRONOUS_PURE_GENERATION_NO_ENGINE_LAUNCH',
            'generation_is_not_runtime': True,
            'runtime_evidence': 'INDEPENDENT_LEVELS_RECORDED_AFTER_REAL_EXECUTION'}
