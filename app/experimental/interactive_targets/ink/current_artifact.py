"""Current-artifact Ink delivery for the pinned inkjs 2.3.2 runtime.

This module is a restricted pure converter over the authorized story snapshot.
It renders the frozen typed Ink subset, derives per-step acceptance expectations
from the shared story authority (play()), pins the npm runtime by integrity and
never bundles, installs or executes runtime code in the product.

Bundle layout (relative to the deterministic target ZIP):
    ink/story.ink              generated source, frozen typed subset only
    ink/validation.json        source map, witness/loss/evidence record
    ink/runtime-pin.json       pinned inkjs 2.3.2 manifest and run instructions
    ink/README.txt             extraction, compile, run and acceptance steps
    acceptance/witness.json    per-step target-environment acceptance expectations

Evidence levels live in descriptor.py; nothing here upgrades them.
"""
from __future__ import annotations

import hashlib
import json

from . import descriptor as _descriptor
from .runtime import (
    EVENT_RESTORE, EVENT_SAVE, IMPLEMENTATION, RUNTIME_BASIS, RUNTIME_ENTRY,
    RUNTIME_ENTRY_SHA256, STATUS_CODES, STATUS_NAMES, evidence_record,
    runtime_pin_document,
)

TARGET_ID = _descriptor.TARGET_ID
FORMAT_VERSION = _descriptor.FORMAT_VERSION
ADAPTER_REVISION = _descriptor.ADAPTER_REVISION
WITNESS_SCHEMA = 'poemseed-ink-current-artifact-witness/1'
VALIDATION_SCHEMA = 'poemseed-ink-current-artifact-validation/1'
SCRIPT_PATH = 'ink/story.ink'
VALIDATION_PATH = 'ink/validation.json'
RUNTIME_PIN_PATH = 'ink/runtime-pin.json'
README_PATH = 'ink/README.txt'
WITNESS_PATH = 'acceptance/witness.json'
SCRIPT_HEADER = (
    '// PoemSeed Studio current Ink artifact for pinned inkjs 2.3.2. '
    'Compile with the pinned compiler and play with the pinned runtime; '
    'acceptance expectations are in acceptance/witness.json.'
)
MAX_ISSUES = 255
STEP_CAP_SEARCH_ATTEMPTS = 4
NATIVE_CSHARP_RUNTIME = 'NOT_RUN'


def _encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2).encode('utf-8')


def _sha256(value):
    return hashlib.sha256(value).hexdigest()


def _story_authority():
    from ...interactive_story import StorySpec, analyze, compile_story, digest, interpret, play
    return {'StorySpec': StorySpec, 'analyze': analyze, 'compile_story': compile_story,
            'digest': digest, 'interpret': interpret, 'play': play}


def _validated_spec(snapshot):
    return _story_authority()['StorySpec'].model_validate(snapshot['spec']).model_dump()


def _analysis(snapshot, spec):
    analysis = snapshot.get('analysis') if isinstance(snapshot.get('analysis'), dict) else None
    if analysis and isinstance(analysis.get('issues'), list) and 'can_review' in analysis:
        return analysis
    return _story_authority()['analyze'](spec)


def _characters(snapshot):
    return {str(character_id): str(name) for character_id, name in dict(snapshot.get('characters') or {}).items()}


def _ink_issues(spec, characters):
    """Only the frozen typed subset is representable; everything else is an issue."""
    issues = []
    for node in spec['nodes']:
        for field in ('dialogue', 'ending'):
            if '\r' in node[field] or '\t' in node[field]:
                issues.append({'code': 'INK_UNSUPPORTED_TEXT_CONTROL', 'node_id': node['node_id']})
        if node.get('character_id'):
            speaker = characters.get(node['character_id']) or ''
            if any(character in speaker for character in '\n\r\t'):
                issues.append({'code': 'INK_UNSUPPORTED_SPEAKER_WHITESPACE', 'node_id': node['node_id'],
                               'character_id': node['character_id']})
        for choice in node['choices']:
            if any(character in choice['label'] for character in '\n\r\t') or choice['label'] != choice['label'].strip():
                issues.append({'code': 'INK_UNSUPPORTED_CHOICE_WHITESPACE', 'node_id': node['node_id'],
                               'choice_id': choice['id']})
    return issues


def _issue_records(issues):
    records = []
    for issue in issues:
        code = str(issue.get('code') or 'INK_COMPATIBILITY_ISSUE')[:120]
        record = {'code': code, 'detail': str(issue.get('detail') or '')[:400]}
        for key in ('node_id', 'choice_id', 'character_id'):
            if issue.get(key) is not None:
                record[key] = str(issue[key])[:160]
        records.append(record)
    return records


def _node_index(spec):
    return {node['node_id']: index for index, node in enumerate(spec['nodes'])}


def _render(spec, characters):
    from ...ink_export import render_subset_script
    return render_subset_script(spec, characters, SCRIPT_HEADER)


def _source_map(spec):
    from ...ink_export import mapping
    return mapping(spec)


def _variables(spec, source_map):
    return [{'name': variable['name'], 'type': variable['type'], 'initial': variable['initial'],
             'ink': source_map['variables'][variable['name']]} for variable in spec['variables']]


def _output_lines(node, characters):
    lines = []
    speaker = characters.get(node['character_id']) if node.get('character_id') else None
    if speaker:
        lines.append(speaker)
    if node['dialogue']:
        lines.extend(line for line in node['dialogue'].split('\n') if line)
    if node['ending']:
        lines.extend(line for line in node['ending'].split('\n') if line)
    return lines


def _expected_state(spec, characters, source_map, node_index, path):
    """Exact target expectation for one server-authoritative play state."""
    result = _story_authority()['play'](spec, path)
    node = result['node']
    enabled = [choice for choice in result['choices'] if choice['enabled']]
    variables = {variable['name']: result['variables'][variable['name']] for variable in spec['variables']}
    status_code = STATUS_CODES[result['status']]
    return {
        'step': result['steps'],
        'node_id': node['node_id'],
        'node_index': node_index[node['node_id']],
        'status': result['status'],
        'status_code': status_code,
        'variables': variables,
        'ink_variables': {source_map['variables'][name]: value for name, value in variables.items()},
        'ink_state': {'ans_node': node_index[node['node_id']], 'ans_steps': result['steps'],
                      'ans_status': status_code},
        'output_lines': _output_lines(node, characters),
        'output_text': '\n'.join(_output_lines(node, characters)) + ('\n' if _output_lines(node, characters) else ''),
        'choices': [{'id': choice['id'], 'label': choice['label'], 'index': index}
                    for index, choice in enumerate(enabled)],
    }


def _ending_cases(snapshot, spec, characters, source_map, node_index):
    endings = [story for story in (snapshot.get('witness') or []) if isinstance(story, dict)]
    if not endings:
        endings = list(_analysis(snapshot, spec).get('endings') or [])
    cases = []
    for ending in endings:
        node_id = ending.get('node_id')
        if node_id not in node_index:
            raise ValueError('INK_ACCEPTANCE_WITNESS_INVALID')
        path = [str(choice) for choice in (ending.get('choices') or [])]
        try:
            states = [_expected_state(spec, characters, source_map, node_index, path[:index])
                      for index in range(len(path) + 1)]
        except ValueError as error:
            raise ValueError('INK_ACCEPTANCE_WITNESS_INVALID') from error
        if states[-1]['status'] != 'ENDING' or states[-1]['node_id'] != node_id:
            raise ValueError('INK_ACCEPTANCE_WITNESS_INVALID')
        cases.append({
            'kind': 'ENDING',
            'ending_node_id': node_id,
            'ending_node_index': node_index[node_id],
            'ending_text': str(ending.get('ending') or ''),
            'choices': path,
            'states': states,
        })
    return cases


def _step_cap_case(spec, characters, source_map, node_index):
    """Bounded walk that reaches the exact step cap, if the story can reach it."""
    authority = _story_authority()
    nodes, compiled, issues = authority['compile_story'](spec)
    if issues:
        return None
    initial = {variable['name']: variable['initial'] for variable in spec['variables']}
    max_steps = spec['max_steps']

    def enabled_choices(node_id, values):
        return [choice for choice in nodes[node_id]['choices']
                if authority['interpret'](compiled[(node_id, choice['id'])], values)]

    def state_key(node_id, values):
        return (node_id, tuple(sorted(values.items())))

    for attempt in range(STEP_CAP_SEARCH_ATTEMPTS):
        values, node_id, path, seen = dict(initial), spec['entry_node_id'], [], set()
        seen.add(state_key(node_id, values))
        while len(path) < max_steps:
            options = enabled_choices(node_id, values)
            if not options:
                break
            rotated = [options[(position + attempt) % len(options)] for position in range(len(options))]
            rotated.sort(key=lambda choice: 0 if state_key(choice['target'], {**values, **choice['assignments']}) in seen else 1)
            choice = rotated[0]
            path.append(choice['id'])
            values = {**values, **choice['assignments']}
            node_id = choice['target']
            seen.add(state_key(node_id, values))
        if len(path) == max_steps and authority['play'](spec, path)['status'] == 'STEP_CAP_REACHED':
            states = [_expected_state(spec, characters, source_map, node_index, path[:index])
                      for index in range(len(path) + 1)]
            return {'kind': 'STEP_CAP', 'choices': path, 'states': states}
    return None


def compatibility(snapshot):
    """Contract compatibility surface: can this snapshot become a current artifact?"""
    spec = _validated_spec(snapshot)
    characters = _characters(snapshot)
    analysis = _analysis(snapshot, spec)
    analysis_issues = _issue_records(analysis.get('issues') or [])
    ink_issues = _issue_records(_ink_issues(spec, characters))
    if not analysis.get('can_review') and not analysis_issues:
        analysis_issues = [{'code': 'STORY_ANALYSIS_INCOMPLETE', 'detail': 'bounded path analysis must complete before export'}]
    records = analysis_issues + ink_issues
    notes = list(_descriptor.INTEGRATION_NOTES) + [
        'CURRENT_ARTIFACT_INCLUDES_PINNED_RUNTIME_MANIFEST_NOT_RUNTIME_CODE',
        'NATIVE_CSHARP_INK_RUNTIME_NOT_RUN',
    ]
    if len(records) > MAX_ISSUES:
        records = records[:MAX_ISSUES]
        notes.append('COMPATIBILITY_ISSUES_TRUNCATED')
    capabilities = {key: {'supported': bool(value[0]), 'lossy': bool(value[1]), 'note': str(value[2])}
                    for key, value in _descriptor.CAPABILITIES.items()}
    return {
        'can_export': bool(analysis.get('can_review')) and not ink_issues,
        'capabilities': capabilities,
        'losses': list(_descriptor.LOSSES),
        'issues': records,
        'notes': notes[:32],
    }


def _readme(snapshot, spec, script, witness, runtime_pin, validation_sha):
    lines = [
        'PoemSeed Studio Ink current-artifact delivery (target ' + TARGET_ID + ').',
        'Story: ' + str(snapshot.get('title')) + ' (id ' + str(snapshot.get('story_id')) + ', revision ' + str(snapshot.get('revision')) + ').',
        'This is a current-work delivery, not a historical fixture. Extract into a NEW empty directory.',
        '',
        'Files:',
        '  ink/story.ink             generated source, frozen typed Ink subset only (sha256 ' + _sha256(script) + ')',
        '  ink/validation.json       source map, witness/loss/evidence record (sha256 ' + validation_sha + ')',
        '  ink/runtime-pin.json      pinned inkjs 2.3.2 registry URL, sha512 integrity and run instructions',
        '  ink/README.txt            this file',
        '  acceptance/witness.json   per-step acceptance expectations for every discovered ending',
        '',
        'Target environment steps:',
        '  1. In the extracted directory run: npm install inkjs@2.3.2',
        '     Confirm the installed package integrity matches ink/runtime-pin.json (sha512).',
        '  2. Compile ink/story.ink with the pinned compiler and deny Ink file access',
        '     (ResolveInkFilename / LoadInkFileContents must throw; INCLUDE is never emitted).',
        '  3. Play the compiled artifact with the pinned runtime. For every acceptance case in',
        '     acceptance/witness.json assert, per step: output text equals output_lines,',
        '     currentChoices labels equal states[i].choices in order, ans_node/ans_steps/ans_status',
        '     and typed variables equal ink_state / variables.',
        '  4. Save with story.state.ToJson(), restore with story.state.LoadJson() in a fresh process,',
        '     and resume to the ending state.',
        '',
        'Security: only the frozen typed subset is emitted. No INCLUDE, external function, user code,',
        'remote import, dynamic path, unbounded loop, eval or network access is present. Cycles end at',
        'the generated ans_steps step cap. Present text as plain text, never as HTML or BBCode.',
        '',
        'Known limits:',
        '  Native C# Ink runtime is NOT_RUN; only the community JavaScript port inkjs 2.3.2 is verified.',
        '  No runtime code is bundled; the pinned npm install is a target-environment step.',
        '  Media references are manifest-only and never packaged or played.',
        '  Blank lines and paragraph spacing normalize in Ink text presentation.',
        '  Character names are plain text lines, not Ink tags/attributes.',
        '  Target font rendering is not verified.',
        '',
        'Runtime pin: ' + runtime_pin['package'] + ' ' + runtime_pin['version'] + ' (' + runtime_pin['integrity'] + ').',
        'Acceptance verifier shipped with the product: scripts/verify_ink_current_artifact.mjs.',
    ]
    return ('\n'.join(lines) + '\n').encode('utf-8')


def build(snapshot, options):
    """Contract build surface: deterministic in-memory bundle for the approved snapshot."""
    del options  # Target options cannot change story semantics; output is deterministic.
    spec = _validated_spec(snapshot)
    characters = _characters(snapshot)
    report = compatibility(snapshot)
    if not report['can_export']:
        raise ValueError('INK_CURRENT_ARTIFACT_UNSUPPORTED')
    script = _render(spec, characters)
    source_map = _source_map(spec)
    node_index = _node_index(spec)
    variables = _variables(spec, source_map)
    ending_cases = _ending_cases(snapshot, spec, characters, source_map, node_index)
    if not ending_cases:
        raise ValueError('INK_ACCEPTANCE_WITNESS_EMPTY')
    step_cap_case = _step_cap_case(spec, characters, source_map, node_index)
    runtime_pin = runtime_pin_document()
    runtime_pin['target_id'] = TARGET_ID
    runtime_pin['format_version'] = FORMAT_VERSION
    runtime_pin['adapter_revision'] = ADAPTER_REVISION
    witness = {
        'schema': WITNESS_SCHEMA,
        'target_id': TARGET_ID,
        'format_version': FORMAT_VERSION,
        'adapter_revision': ADAPTER_REVISION,
        'story': {
            'id': str(snapshot.get('story_id')),
            'revision': snapshot.get('revision'),
            'title': str(snapshot.get('title')),
            'spec_digest': snapshot.get('spec_digest'),
            'source_digest': snapshot.get('source_digest'),
        },
        'script': {'path': SCRIPT_PATH, 'sha256': _sha256(script), 'bytes': len(script)},
        'runtime': runtime_pin,
        'variables': variables,
        'ink_state_variables': {'node': 'ans_node', 'steps': 'ans_steps', 'status': 'ans_status'},
        'status_codes': dict(STATUS_CODES),
        'status_names': {str(code): name for code, name in STATUS_NAMES.items()},
        'max_steps': spec['max_steps'],
        'endings': ending_cases,
        'step_cap_cases': [step_cap_case] if step_cap_case else [],
        'coverage': 'EVERY_DISCOVERED_ENDING_WITNESS_PLUS_ONE_BOUNDED_STEP_CAP_CASE_WHEN_REACHABLE',
        'method': 'SHARED_SERVER_AUTHORITY_PLAY_EXPECTATIONS_PER_STEP',
        'runtime_basis': RUNTIME_BASIS,
        'native_csharp_runtime': NATIVE_CSHARP_RUNTIME,
        'losses': list(_descriptor.LOSSES),
        'notes': [
            'Each state lists the choices the pinned runtime must expose, in order, so selection is by witness id.',
            'output_lines are the exact plain-text lines the generated script emits for that state.',
            'variables use original story names; ink_variables use the generated Ink VAR names.',
            'The loop step-cap case asserts the generated ans_steps branch ends the story at max_steps.',
        ],
    }
    witness_bytes = _encode(witness)
    runtime_pin_bytes = _encode(runtime_pin)
    validation = {
        'schema': VALIDATION_SCHEMA,
        'target_id': TARGET_ID,
        'format_version': FORMAT_VERSION,
        'adapter_revision': ADAPTER_REVISION,
        'story': witness['story'],
        'script': {'path': SCRIPT_PATH, 'sha256': _sha256(script), 'bytes': len(script)},
        'witness': {'path': WITNESS_PATH, 'sha256': _sha256(witness_bytes),
                    'endings': len(ending_cases), 'step_cap_cases': 1 if step_cap_case else 0,
                    'states': sum(len(case['states']) for case in ending_cases)
                              + (len(step_cap_case['states']) if step_cap_case else 0)},
        'runtime_pin': {'path': RUNTIME_PIN_PATH, 'sha256': _sha256(runtime_pin_bytes),
                        'package': runtime_pin['package'], 'version': runtime_pin['version'],
                        'integrity': runtime_pin['integrity'],
                        'runtime_entry': runtime_pin['runtime_entry'],
                        'runtime_bundled': False},
        'source_map': source_map,
        'status_codes': dict(STATUS_CODES),
        'capabilities': report['capabilities'],
        'issues': report['issues'],
        'losses': list(report['losses']),
        'evidence': evidence_record(),
        'implementation': IMPLEMENTATION,
        'runtime_basis': RUNTIME_BASIS,
        'native_csharp_runtime': NATIVE_CSHARP_RUNTIME,
        'artifact_runtime': 'NOT_RUN_BY_PRODUCT_GENERATION; ACCEPTANCE_EXPECTATIONS_FOR_PINNED_INKJS_2_3_2',
        'save_restore': {'save': EVENT_SAVE, 'restore': EVENT_RESTORE},
        'security': {
            'typed_subset_only': True,
            'include_allowed': False,
            'external_functions_allowed': False,
            'user_code_allowed': False,
            'dynamic_paths_allowed': False,
            'unbounded_loops_allowed': False,
            'network_allowed': False,
            'runtime_code_bundled': False,
        },
        'verification': {
            'script': 'scripts/verify_ink_current_artifact.mjs',
            'acceptance_witness': WITNESS_PATH,
            'expected_report_schema': 'poemseed-ink-current-artifact-verification/1',
        },
    }
    validation_bytes = _encode(validation)
    readme = _readme(snapshot, spec, script, witness_bytes, runtime_pin, _sha256(validation_bytes))
    files = {
        SCRIPT_PATH: script,
        VALIDATION_PATH: validation_bytes,
        RUNTIME_PIN_PATH: runtime_pin_bytes,
        README_PATH: readme,
        WITNESS_PATH: witness_bytes,
    }
    manifest_extra = {
        'ink_current_artifact': {
            'target_id': TARGET_ID,
            'format_version': FORMAT_VERSION,
            'script_sha256': _sha256(script),
            'witness_sha256': _sha256(witness_bytes),
            'endings': len(ending_cases),
            'step_cap_cases': 1 if step_cap_case else 0,
            'runtime': {'package': runtime_pin['package'], 'version': runtime_pin['version'],
                        'integrity': runtime_pin['integrity'], 'runtime_entry_sha256': RUNTIME_ENTRY_SHA256,
                        'entry': RUNTIME_ENTRY, 'bundled': False},
            'runtime_basis': RUNTIME_BASIS,
            'native_csharp_runtime': NATIVE_CSHARP_RUNTIME,
            'evidence': evidence_record(),
            'acceptance': {'witness': WITNESS_PATH, 'verifier': 'scripts/verify_ink_current_artifact.mjs'},
        }
    }
    return {'files': files, 'manifest_extra': manifest_extra}
