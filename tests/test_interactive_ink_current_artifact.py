"""B07 Ink current-artifact target: contract surface, legacy byte freeze, real File export.

Distinguishes deliberately:
* legacy fixture target INKJS_2_3_2_TYPED_TEXT_SUBSET (bytes frozen, runtime NOT_RUN)
* current-artifact target INK_2_3_2_CURRENT_ARTIFACT_V1 (real File service export,
  pinned inkjs 2.3.2 acceptance run by scripts/verify_ink_current_artifact.mjs)
* target-environment runtime evidence is opt-in and never asserted without a real run.
"""
import base64
import hashlib
import io
import json
import os
from copy import deepcopy
from pathlib import Path
import zipfile

import pytest

from app.experimental.interactive_export_contract import (
    CAPABILITY_KEYS, EVIDENCE_LEVELS, EVIDENCE_STATUSES, available_target_ids, build_export_bundle,
    compatibility_report, describe_target, historical_evidence_for, package_export_zip, read_zip_safely,
)
from app.experimental.interactive_story import StorySpec, analyze, play, digest
from app.experimental.ink_export import (
    LOSSES as LEGACY_LOSSES, PIN as LEGACY_PIN, TARGET as LEGACY_TARGET, InkExportAdapter,
)
from app.experimental.interactive_targets.ink import descriptor as ink_descriptor
from app.experimental.interactive_targets.ink.runtime import (
    INTEGRITY, PINNED_VERSION, RUNTIME_ENTRY_SHA256, STATUS_CODES,
)
from test_r4_revision_intelligence import revision_env
from test_r5_interactive_story import interactive_env, create, approve, spec
import test_storyverse_ink_exchange as legacy_fixture


TARGET = 'INK_2_3_2_CURRENT_ARTIFACT_V1'

GOLDEN_SPEC = {
    'title': 'Ink golden', 'graph_id': 'golden_graph', 'graph_version': 1, 'entry_node_id': 'gate', 'max_steps': 6,
    'variables': [{'name': 'flag', 'type': 'bool', 'initial': False},
                  {'name': 'count', 'type': 'int', 'initial': -3, 'minimum': -10000, 'maximum': 10000}],
    'nodes': [
        {'node_id': 'gate', 'node_version': 1, 'title': 'Gate', 'character_id': 'alice',
         'dialogue': 'Quote "[a]" {b} \u3016c \\\\nINCLUDE note.ink\nEXTERNAL evil() -> jump #tag',
         'choices': [{'id': 'again', 'label': 'Again # {x} [y] " ->', 'target': 'gate',
                      'assignments': {'flag': True, 'count': 10000}},
                     {'id': 'finish', 'label': 'Finish', 'target': 'end', 'condition': 'flag and count == 10000'},
                     {'id': 'other', 'label': 'Other', 'target': 'side', 'condition': 'not flag and count < 0'}]},
        {'node_id': 'end', 'node_version': 1, 'title': 'End', 'ending': 'Good ending \U0001f642'},
        {'node_id': 'side', 'node_version': 1, 'title': 'Side',
         'choices': [{'id': 'finish', 'label': 'Converge', 'target': 'end', 'assignments': {'count': 0}}]}]}
GOLDEN_CHARACTERS = {'alice': 'Alice "[literal]" {text} \u3016ruby'}

# Captured from the frozen legacy implementation; any rendering drift fails here.
LEGACY_FIXTURE_GOLDEN = {
    'ink/README.txt': 'df4d1abe67d621acd9d9ad4d434778648a1bb4aa04ffb021c2d9b3dbf494813d',
    'ink/story.ink': '13ba69b9fe5939c98cfdca42ccf98624460adbe6ca15cb2a7e87151e7ca4704c',
    'ink/validation.json': 'c7daddaad4893cf9fdcf2b52d450c8d00ced51ef472478280575daa44d551fb8',
}
LEGACY_GOLDEN_GOLDEN = {
    'ink/README.txt': 'df4d1abe67d621acd9d9ad4d434778648a1bb4aa04ffb021c2d9b3dbf494813d',
    'ink/story.ink': '8f350324fcacb7bc5e18208b422e880aa15a4cc3e6e9055bb4dc45b48e1bb340',
    'ink/validation.json': '99ab763dcd799882b51dab893aa2300d780b4d5d009a4e0c046a50d3334c97c6',
}


def _sha(value):
    return hashlib.sha256(value).hexdigest()


def _snapshot(spec_value, characters=None, analysis=None, media_manifest=None, story_id='ink-current-story',
              revision=2, status='APPROVED'):
    spec_value = StorySpec.model_validate(spec_value).model_dump()
    analysis = analysis or analyze(spec_value)
    return {'story_id': story_id, 'revision': revision, 'status': status, 'title': spec_value['title'],
            'spec': deepcopy(spec_value), 'spec_digest': digest(spec_value),
            'source_digest': digest({'source': story_id, 'revision': revision}),
            'review_receipt': digest({'receipt': story_id, 'revision': revision}),
            'characters': dict(characters or {}), 'witness': deepcopy(analysis['endings']),
            'media_manifest': list(media_manifest or []), 'analysis': analysis}


def _bundle(snapshot):
    return build_export_bundle(TARGET, snapshot, {'include_witness': True, 'target_options': {}})


def _read_bundle(bundle):
    package = package_export_zip(bundle)
    return read_zip_safely(package['content'], package['prefix'])


def _scratch_artifact_dir():
    value = os.environ.get('POEMSEED_INK_ARTIFACT_DIR')
    return Path(value) if value else None


def _drop_artifacts(name, content, prefix, record):
    """Optional evidence sink: write the real exported ZIP and extracted bundle outside the repo."""
    root = _scratch_artifact_dir()
    if root is None:
        return None
    root.mkdir(parents=True, exist_ok=True)
    (root / (name + '.zip')).write_bytes(content)
    files = read_zip_safely(content, prefix)
    for relative, data in files.items():
        target = root / (name + '-bundle') / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    (root / (name + '-record.json')).write_text(
        json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True), encoding='utf-8')
    return root


def _runtime_env():
    node = os.environ.get('POEMSEED_NODE')
    root = os.environ.get('POEMSEED_INKJS_ROOT')
    if not node or not root:
        pytest.skip('pinned inkjs 2.3.2 runtime opt-in required (POEMSEED_NODE, POEMSEED_INKJS_ROOT)')
    return node, root


def _run_verifier(tmp_path, files, node, root, name='report', extra_args=None):
    import subprocess
    bundle_dir = tmp_path / (name + '-bundle')
    for relative, data in files.items():
        target = bundle_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    report = tmp_path / (name + '-report.json')
    command = [node, str(_verify_script()), '--bundle', str(bundle_dir), '--vendor', root,
               '--report', str(report), *(extra_args or [])]
    completed = subprocess.run(command, capture_output=True, text=True, encoding='utf-8',
                               errors='replace', timeout=240, check=False)
    payload = json.loads(report.read_text(encoding='utf-8')) if report.exists() else None
    return completed, payload, bundle_dir


def _verify_script():
    return Path(__file__).resolve().parents[1] / 'scripts' / 'verify_ink_current_artifact.mjs'


def _export_current(e, row, value, target=TARGET):
    preview = e.service.export_preview(e.nid, e.scope, 'author', row['id'], {**value, 'target_id': target})
    assert preview['selected_target']['target_id'] == target
    assert preview['selected_target']['compatibility']['can_export'] is True
    out = e.service.export(e.nid, e.scope, 'author', row['id'],
                           {**value, 'preview_digest': preview['preview_digest'], 'target_id': target})
    return preview, out


def _runtime_claim_expected():
    """Mirror InteractiveStoryService._runtime_claim: save/restore outranks runtime."""
    evidence = historical_evidence_for(TARGET)
    for level in ('SAVE_RESTORE_VERIFIED', 'TARGET_RUNTIME_EXECUTED'):
        if evidence.get(level) == 'PASS':
            return level
    blocked = evidence.get('TARGET_RUNTIME_EXECUTED') or evidence.get('SAVE_RESTORE_VERIFIED')
    return 'BLOCKED_ENVIRONMENT' if blocked in {'BLOCKED_ENVIRONMENT', 'BLOCKED_AUTHORITY'} else 'NOT_RUN'


# ---------------------------------------------------------------------------
# contract surface + legacy freeze
# ---------------------------------------------------------------------------
def test_new_target_registered_with_honest_descriptor():
    from app.experimental.interactive_export_contract import LEGACY_TARGETS
    ids = available_target_ids()
    assert ids.count(TARGET) == 1 and ids.count(LEGACY_TARGET) == 1
    assert LEGACY_TARGETS[LEGACY_TARGET]['kind'] == 'LEGACY_FRAGMENT'
    descriptor = describe_target(TARGET).model_dump(mode='json')
    assert descriptor['target_id'] == TARGET and descriptor['kind'] == 'RUNNABLE_PROJECT'
    assert descriptor['format_version'] == 'ink-current-artifact-2' and descriptor['adapter_revision'] == 2
    assert descriptor['verification_runtime'] == {'name': 'inkjs', 'version': PINNED_VERSION,
                                                   'version_mode': 'EXACT', 'format': 'ink-current-artifact-2'}
    assert set(descriptor['capabilities']) == set(CAPABILITY_KEYS)
    assert descriptor['engine']['name'].startswith('Node.js')
    evidence = historical_evidence_for(TARGET)
    assert set(evidence) == set(EVIDENCE_LEVELS)
    for level in ('SOURCE_IMPLEMENTED', 'SCHEMA_VALIDATED', 'FIXTURE_TESTED', 'GENERATED_ARTIFACT_VALIDATED'):
        assert evidence[level] == 'PASS'
    assert evidence['WINDOWS_USABILITY_VERIFIED'] == 'NOT_RUN'
    assert evidence['TARGET_RUNTIME_EXECUTED'] == 'PASS'
    assert evidence['SAVE_RESTORE_VERIFIED'] == 'PASS'
    # Legacy public names stay frozen for the old target.
    assert LEGACY_TARGET == 'INKJS_2_3_2_TYPED_TEXT_SUBSET'
    assert LEGACY_PIN['version'] == '2.3.2' and LEGACY_PIN['implementation'] == 'COMMUNITY_JAVASCRIPT_PORT_NOT_NATIVE_CSHARP'
    assert 'INK_CURRENT_ARTIFACT_TARGET_RUNTIME_NOT_RUN' in LEGACY_LOSSES
    assert ink_descriptor.TARGET_ID == TARGET
    assert PINNED_VERSION in ink_descriptor.DESCRIPTOR['runtime_requirements'][1]


def test_legacy_adapter_output_is_byte_frozen():
    adapter = InkExportAdapter()
    for story, characters, golden in (
            (legacy_fixture.story(), {}, LEGACY_FIXTURE_GOLDEN),
            (StorySpec.model_validate(GOLDEN_SPEC).model_dump(), GOLDEN_CHARACTERS, LEGACY_GOLDEN_GOLDEN)):
        files = adapter.files(story, characters)
        assert {name: _sha(data) for name, data in files.items()} == golden


def test_current_artifact_bundle_shape_witness_and_determinism():
    snapshot = _snapshot(GOLDEN_SPEC, GOLDEN_CHARACTERS)
    compatibility = compatibility_report(TARGET, snapshot)
    assert compatibility['can_export'] is True and compatibility['issues'] == []
    assert set(compatibility['capabilities']) == set(CAPABILITY_KEYS)
    assert compatibility['capabilities']['media']['supported'] is False
    bundle = _bundle(snapshot)
    files = _read_bundle(bundle)
    assert set(files) == {'ink/story.ink', 'ink/validation.json', 'ink/runtime-pin.json', 'ink/README.txt',
                          'ink/player/save_envelope.mjs', 'ink/player/save-envelope.schema.json',
                          'acceptance/witness.json', 'manifest.json', 'source-receipt.json'}
    # The delivered player helper is our own dependency-free ESM; no third-party
    # runtime or extra executable script may be bundled.
    assert [name for name in files if name.endswith(('.js', '.cjs', '.mjs'))] == ['ink/player/save_envelope.mjs']
    player_bytes = files['ink/player/save_envelope.mjs']
    assert b'require(' not in player_bytes and b'import ' not in player_bytes
    runtime_pin_json = json.loads(files['ink/runtime-pin.json'])
    envelope_pin = runtime_pin_json['save_restore']['envelope']
    assert envelope_pin['schema'] == 'poemseed-ink-save-envelope/1'
    assert envelope_pin['player_module']['sha256'] == _sha(player_bytes)
    assert envelope_pin['legacy_policy'] == 'UNBOUND_LEGACY_SAVE_REJECTED_EXPLICIT_MIGRATION_REQUIRED'
    assert envelope_pin['binding_fields'] == ['story_id', 'revision', 'compiled_artifact_sha256', 'target_format_version', 'runtime']
    validation_envelope = json.loads(files['ink/validation.json'])['save_restore']
    assert validation_envelope['envelope']['player_module']['sha256'] == _sha(player_bytes)
    assert validation_envelope['legacy_policy'] == 'UNBOUND_LEGACY_SAVE_REJECTED_EXPLICIT_MIGRATION_REQUIRED'
    assert json.loads(files['ink/player/save-envelope.schema.json'])['$id'] == 'poemseed-ink-save-envelope/1'
    assert b'require(' not in files['ink/story.ink']
    legacy_script = InkExportAdapter().files(StorySpec.model_validate(GOLDEN_SPEC).model_dump(), GOLDEN_CHARACTERS)['ink/story.ink']
    current_script = files['ink/story.ink']
    assert current_script.split(b'\n', 1)[1] == legacy_script.split(b'\n', 1)[1]
    assert current_script.startswith(b'// PoemSeed Studio current Ink artifact')
    witness = json.loads(files['acceptance/witness.json'])
    assert witness['schema'] == 'poemseed-ink-current-artifact-witness/1'
    assert witness['runtime']['version'] == PINNED_VERSION and witness['runtime']['integrity'] == INTEGRITY
    assert witness['runtime']['runtime_bundled'] is False
    assert witness['runtime']['runtime_entry']['sha256'] == RUNTIME_ENTRY_SHA256
    assert witness['script']['sha256'] == _sha(current_script)
    assert witness['endings'] and witness['step_cap_cases']
    spec_value = snapshot['spec']
    node_index = {node['node_id']: position for position, node in enumerate(spec_value['nodes'])}
    for case in witness['endings']:
        expected = [play(spec_value, case['choices'][:position]) for position in range(len(case['choices']) + 1)]
        assert [state['step'] for state in case['states']] == [authority['steps'] for authority in expected]
        for state, authority in zip(case['states'], expected):
            assert state['node_id'] == authority['node']['node_id']
            assert state['status'] == authority['status'] and state['status_code'] == STATUS_CODES[authority['status']]
            assert state['variables'] == authority['variables']
            assert state['ink_state'] == {'ans_node': node_index[authority['node']['node_id']],
                                          'ans_steps': authority['steps'],
                                          'ans_status': STATUS_CODES[authority['status']]}
            assert [choice['id'] for choice in state['choices']] == [choice['id'] for choice in authority['choices'] if choice['enabled']]
            assert [choice['index'] for choice in state['choices']] == list(range(len(state['choices'])))
        assert case['states'][-1]['status'] == 'ENDING'
    for case in witness['step_cap_cases']:
        assert case['states'][-1]['status'] == 'STEP_CAP_REACHED'
        assert case['states'][-1]['status_code'] == 2 and len(case['choices']) == spec_value['max_steps']
        assert [state['step'] for state in case['states']] == list(range(len(case['choices']) + 1))
    validation = json.loads(files['ink/validation.json'])
    assert validation['witness']['sha256'] == _sha(files['acceptance/witness.json'])
    assert validation['runtime_pin']['sha256'] == _sha(files['ink/runtime-pin.json'])
    assert validation['schema'] == 'poemseed-ink-current-artifact-validation/1'
    assert validation['security'] == {'typed_subset_only': True, 'include_allowed': False,
                                      'external_functions_allowed': False, 'user_code_allowed': False,
                                      'dynamic_paths_allowed': False, 'unbounded_loops_allowed': False,
                                      'network_allowed': False, 'runtime_code_bundled': False}
    assert validation['native_csharp_runtime'] == 'NOT_RUN'
    assert validation['evidence']['TARGET_RUNTIME_EXECUTED'] == 'PASS'
    assert validation['evidence']['SAVE_RESTORE_VERIFIED'] == 'PASS'
    assert validation['source_map']['nodes'] == {'gate': 'ans_node_0', 'end': 'ans_node_1', 'side': 'ans_node_2'}
    manifest = json.loads(files['manifest.json'])
    assert manifest['target_id'] == TARGET and manifest['target_kind'] == 'RUNNABLE_PROJECT'
    assert manifest['extra']['ink_current_artifact']['runtime']['bundled'] is False
    assert manifest['extra']['ink_current_artifact']['native_csharp_runtime'] == 'NOT_RUN'
    receipt = json.loads(files['source-receipt.json'])
    assert receipt['target_id'] == TARGET and receipt['story_id'] == snapshot['story_id']
    assert receipt['capabilities_unsupported'] == ['media']
    again = _bundle(_snapshot(GOLDEN_SPEC, GOLDEN_CHARACTERS))
    assert again.files_digest == bundle.files_digest


def test_media_references_are_reported_not_packaged():
    media = [{'asset_id': 'asset-1', 'version': 1, 'sha256': 'a' * 64, 'kind': 'image',
              'missing': False, 'packaged': False, 'reason': 'TEXT_SUBSET_REFERENCE_ONLY'}]
    snapshot = _snapshot(GOLDEN_SPEC, GOLDEN_CHARACTERS, media_manifest=media)
    compatibility = compatibility_report(TARGET, snapshot)
    assert compatibility['can_export'] is True
    assert 'MEDIA_REFERENCES_NOT_EMBEDDED_OR_PLAYED' in compatibility['losses']
    files = _read_bundle(_bundle(snapshot))
    assert not any(name.startswith('media/') for name in files)
    assert json.loads(files['ink/validation.json'])['capabilities']['media']['supported'] is False


def test_unsupported_content_fails_closed():
    def refuses(snapshot):
        compatibility = compatibility_report(TARGET, snapshot)
        assert compatibility['can_export'] is False and compatibility['issues']
        with pytest.raises(ValueError):
            build_export_bundle(TARGET, snapshot, {'include_witness': True, 'target_options': {}})
        from app.experimental.interactive_targets.ink.current_artifact import build
        with pytest.raises(ValueError, match='INK_CURRENT_ARTIFACT_UNSUPPORTED'):
            build(snapshot, {})
        return compatibility

    bad_choice = deepcopy(GOLDEN_SPEC)
    bad_choice['nodes'][0]['choices'][0]['label'] = 'two\nlines'
    assert any(issue['code'] == 'INK_UNSUPPORTED_CHOICE_WHITESPACE'
               for issue in refuses(_snapshot(bad_choice, GOLDEN_CHARACTERS))['issues'])

    bad_text = deepcopy(GOLDEN_SPEC)
    bad_text['nodes'][0]['dialogue'] = 'tab\there'
    assert any(issue['code'] == 'INK_UNSUPPORTED_TEXT_CONTROL'
               for issue in refuses(_snapshot(bad_text, GOLDEN_CHARACTERS))['issues'])

    assert any(issue['code'] == 'INK_UNSUPPORTED_SPEAKER_WHITESPACE'
               for issue in refuses(_snapshot(GOLDEN_SPEC, {'alice': 'Alice\nsecond'}))['issues'])

    dead = deepcopy(GOLDEN_SPEC)
    for choice in dead['nodes'][0]['choices']:
        choice['condition'] = 'False'
    analysis = analyze(StorySpec.model_validate(dead).model_dump())
    assert analysis['can_review'] is False
    assert any(issue['code'] == 'CONDITIONAL_NO_EXIT'
               for issue in refuses(_snapshot(dead, GOLDEN_CHARACTERS, analysis=analysis))['issues'])


def test_tampered_authority_witness_is_rejected():
    snapshot = _snapshot(GOLDEN_SPEC, GOLDEN_CHARACTERS)
    tampered = deepcopy(snapshot)
    tampered['witness'] = [{'node_id': 'end', 'ending': 'Good ending', 'choices': ['finish']}]
    from app.experimental.interactive_targets.ink.current_artifact import build
    with pytest.raises(ValueError, match='INK_ACCEPTANCE_WITNESS_INVALID'):
        build(tampered, {})
    empty = deepcopy(snapshot)
    empty['witness'] = []
    empty['analysis'] = {**empty['analysis'], 'endings': []}
    with pytest.raises(ValueError, match='INK_ACCEPTANCE_WITNESS_EMPTY'):
        build(empty, {})


# ---------------------------------------------------------------------------
# real File service: create -> review -> approve -> export current artifact
# ---------------------------------------------------------------------------
def test_real_file_service_exports_current_artifact_zip(interactive_env):
    e = interactive_env
    row = approve(e, create(e))
    value = {'expected_version': row['version']}
    preview = e.service.export_preview(e.nid, e.scope, 'author', row['id'], value)
    targets = {target['target_id']: target for target in preview['targets']}
    assert TARGET in targets and preview['ink_target']['version'] == '2.3.2'
    assert targets[TARGET]['historical_evidence'] == historical_evidence_for(TARGET)
    assert targets[TARGET]['artifact_evidence_status'] == 'NOT_EXPORTED'
    assert targets[TARGET]['runtime_claim'] == 'UNVERIFIED'
    assert targets[TARGET]['export_ready'] is True

    preview, out = _export_current(e, row, value)
    assert out['target_id'] == TARGET and out['mime'] == 'application/zip'
    assert out['filename'].endswith('.zip') and out['file_count'] == 9
    content = base64.b64decode(out['content_base64'])
    assert hashlib.sha256(content).hexdigest() == out['sha256']
    prefix = 'interactive-ink-2-3-2-current-artifact-v1-' + row['id'] + '/'
    files = read_zip_safely(content, prefix)
    witness = json.loads(files['acceptance/witness.json'])
    assert witness['story']['id'] == row['id'] and witness['story']['revision'] == row['version']
    node_ids = [node['node_id'] for node in row['spec']['nodes']]
    ending_texts = {node['ending'] for node in row['spec']['nodes'] if node['ending']}
    assert witness['endings']
    for case in witness['endings']:
        assert case['choices'] in [ending['choices'] for ending in row['analysis']['endings']]
        states = [play(row['spec'], case['choices'][:position]) for position in range(len(case['choices']) + 1)]
        for state, authority in zip(case['states'], states):
            assert state['node_index'] == node_ids.index(authority['node']['node_id'])
            assert state['variables'] == authority['variables']
            assert [choice['label'] for choice in state['choices']] == \
                [choice['label'] for choice in authority['choices'] if choice['enabled']]
        assert case['states'][-1]['status'] == 'ENDING'
        assert any(line in ending_texts for line in case['states'][-1]['output_lines'])
    assert json.loads(files['ink/validation.json'])['story']['spec_digest'] == digest(row['spec'])
    assert out['runtime_claim'] == 'UNVERIFIED'
    assert out['evidence']['TARGET_RUNTIME_EXECUTED'] == 'NOT_RUN'
    assert out['historical_evidence']['TARGET_RUNTIME_EXECUTED'] == 'PASS'
    assert out['artifact_evidence_status'] == 'UNVERIFIED'
    assert out['published'] is False
    record = {
        'target_id': TARGET, 'story_id': row['id'], 'revision': row['version'], 'zip_sha256': out['sha256'],
        'file_count': out['file_count'], 'files_digest': out['files_digest'], 'filename': out['filename'],
        'spec_digest': witness['story']['spec_digest'],
        'witness_sha256': _sha(files['acceptance/witness.json']),
        'script_sha256': _sha(files['ink/story.ink']),
        'runtime_pin_sha256': _sha(files['ink/runtime-pin.json']),
        'runtime_claim': out['runtime_claim'], 'evidence': out['evidence'],
        'preview_digest': preview['preview_digest'], 'files': sorted(files),
        'zip_file_sha256': {name: _sha(data) for name, data in files.items()},
    }
    _drop_artifacts('current-artifact-main', content, prefix, record)

    # Legacy multi-file export is untouched: same Ink bytes and same preview surface.
    legacy_preview = e.service.export_preview(e.nid, e.scope, 'author', row['id'], value)
    assert legacy_preview['ink_target'] == {**LEGACY_PIN, 'compatibility': 'SUPPORTED_SUBSET'}
    assert any(adapter['target'] == LEGACY_TARGET for adapter in legacy_preview['engine_adapters'])
    legacy_out = e.service.export(e.nid, e.scope, 'author', row['id'],
                                  {**value, 'preview_digest': legacy_preview['preview_digest']})
    characters = e.service._owned(e.nid, e.scope, 'author', row['id'])['capture']['characters']
    legacy_files = InkExportAdapter().files(row['spec'], characters)
    with zipfile.ZipFile(io.BytesIO(base64.b64decode(legacy_out['content_base64']))) as archive:
        prefix = 'interactive-story-' + row['id'] + '/'
        assert archive.read(prefix + 'ink/story.ink') == legacy_files['ink/story.ink']
        assert archive.read(prefix + 'ink/README.txt') == legacy_files['ink/README.txt']
        assert json.loads(archive.read(prefix + 'ink/validation.json')) == json.loads(legacy_files['ink/validation.json'])


def test_real_file_service_loop_story_has_step_cap_acceptance(interactive_env):
    e = interactive_env
    loop_spec = StorySpec.model_validate({
        'title': 'Ink loop current artifact', 'graph_id': e.graph['id'], 'graph_version': 1,
        'entry_node_id': e.nodes[0], 'max_steps': 2,
        'variables': [{'name': 'flag', 'type': 'bool', 'initial': False},
                      {'name': 'count', 'type': 'int', 'initial': 0, 'minimum': 0, 'maximum': 1}],
        'nodes': [
            {'node_id': e.nodes[0], 'node_version': 1, 'title': 'Loop gate', 'character_id': 'alice',
             'dialogue': '\u5faa\u73af\u5165\u53e3 \U0001f642 \\\\ "', 'choices': [
                 {'id': 'loop', 'label': '\u518d\u6765\u4e00\u6b21', 'target': e.nodes[0],
                  'assignments': {'flag': True, 'count': 1}},
                 {'id': 'exit', 'label': '\u79bb\u5f00', 'target': e.nodes[2]}]},
            {'node_id': e.nodes[1], 'node_version': 1, 'title': 'Unused ending', 'ending': 'Unused unreachable ending'},
            {'node_id': e.nodes[2], 'node_version': 1, 'title': 'Ending', 'ending': '\u7ed3\u5c40 \U0001f642'}]}
    ).model_dump()
    row = approve(e, create(e, loop_spec))
    value = {'expected_version': row['version']}
    preview, out = _export_current(e, row, value)
    assert preview['selected_target']['compatibility']['can_export'] is True
    content = base64.b64decode(out['content_base64'])
    prefix = 'interactive-ink-2-3-2-current-artifact-v1-' + row['id'] + '/'
    files = read_zip_safely(content, prefix)
    witness = json.loads(files['acceptance/witness.json'])
    assert witness['max_steps'] == 2 and witness['endings']
    assert len(witness['step_cap_cases']) == 1
    case = witness['step_cap_cases'][0]
    assert case['choices'] == ['loop', 'loop']
    assert [state['status'] for state in case['states']] == ['PLAYING', 'PLAYING', 'STEP_CAP_REACHED']
    assert case['states'][-1]['ink_state']['ans_status'] == 2
    assert play(row['spec'], ['loop', 'loop'])['status'] == 'STEP_CAP_REACHED'
    record = {'target_id': TARGET, 'story_id': row['id'], 'revision': row['version'],
              'zip_sha256': out['sha256'], 'file_count': out['file_count'],
              'script_sha256': _sha(files['ink/story.ink']), 'witness_sha256': _sha(files['acceptance/witness.json']),
              'filename': out['filename'], 'step_cap_choices': case['choices'],
              'preview_digest': preview['preview_digest'], 'files': sorted(files)}
    _drop_artifacts('current-artifact-loop', content, prefix, record)


# ---------------------------------------------------------------------------
# pinned inkjs 2.3.2 target-environment acceptance (opt-in, never auto-passed)
# ---------------------------------------------------------------------------
def test_pinned_runtime_executes_exported_current_artifact(interactive_env, tmp_path):
    node, root = _runtime_env()
    e = interactive_env
    row = approve(e, create(e))
    value = {'expected_version': row['version']}
    _, out = _export_current(e, row, value)
    prefix = 'interactive-ink-2-3-2-current-artifact-v1-' + row['id'] + '/'
    files = read_zip_safely(base64.b64decode(out['content_base64']), prefix)
    completed, report, _ = _run_verifier(tmp_path, files, node, root, 'main')
    assert completed.returncode == 0, completed.stderr[-4000:] + completed.stdout[-2000:]
    assert report['result'] == 'PASS', json.dumps(report, ensure_ascii=False)[:4000]
    assert report['vendor']['version'] == '2.3.2'
    assert report['vendor']['runtime_entry_sha256'] == RUNTIME_ENTRY_SHA256
    assert report['source']['sha256'] == _sha(files['ink/story.ink'])
    assert report['compile']['success'] is True and report['compile']['errors'] == []
    assert report['compile']['file_calls'] == 0
    assert report['runtime']['artifact_consumed'] is True
    assert report['runtime']['cases'] and all(case['passed'] for case in report['runtime']['cases'])
    assert len(report['runtime']['cases']) == len(json.loads(files['acceptance/witness.json'])['endings'])
    assert report['cross_process']['performed'] is True and report['cross_process']['passed'] is True
    assert report['cross_process']['fresh_process'] is True
    assert report['assertions']['save_envelope'] == 'PASS'
    assert report['delivered_player']['sha256'] == report['delivered_player']['pinned_sha256']
    assert len(report['save_restore_negatives']) >= 8
    assert all(item['passed'] for item in report['save_restore_negatives'])
    assert {item['expected_code'] for item in report['save_restore_negatives']} >= {
        'SAVE_ENVELOPE_STORY_MISMATCH', 'SAVE_ENVELOPE_REVISION_MISMATCH',
        'SAVE_ENVELOPE_INTEGRITY_INVALID', 'LEGACY_SAVE_ENVELOPE_REQUIRED', 'SAVE_ENVELOPE_ARTIFACT_MISMATCH'}
    if report['assertions']['save_restore'] == 'NOT_APPLICABLE_SINGLE_STEP':
        assert report['cross_process']['after_choice_possible'] is False
    assert report['native_csharp_runtime'] == 'NOT_RUN'
    assert report['runtime']['ending_reached'] is True
    assert report['unicode_and_escape'] == 'PASS'
    artifact_dir = _scratch_artifact_dir()
    if artifact_dir is not None:
        artifact_dir.mkdir(parents=True, exist_ok=True)
        (artifact_dir / 'verification-main.json').write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding='utf-8')
        (artifact_dir / 'verification-main.command.json').write_text(json.dumps({
            'node': node, 'vendor': root, 'bundle': str(tmp_path / 'main-bundle'),
            'report': str(tmp_path / 'main-report.json'), 'exit_code': completed.returncode,
            'stdout_tail': completed.stdout[-3000:], 'stderr_tail': completed.stderr[-3000:],
        }, ensure_ascii=False, indent=2), encoding='utf-8')


def test_pinned_runtime_executes_loop_step_cap_artifact(interactive_env, tmp_path):
    node, root = _runtime_env()
    e = interactive_env
    loop_spec = StorySpec.model_validate({
        'title': 'Ink loop runtime', 'graph_id': e.graph['id'], 'graph_version': 1, 'entry_node_id': e.nodes[0],
        'max_steps': 3,
        'variables': [{'name': 'flag', 'type': 'bool', 'initial': False},
                      {'name': 'count', 'type': 'int', 'initial': 0, 'minimum': 0, 'maximum': 2}],
        'nodes': [
            {'node_id': e.nodes[0], 'node_version': 1, 'title': 'Loop gate', 'dialogue': 'Loop body',
             'choices': [{'id': 'loop', 'label': 'Loop again', 'target': e.nodes[0],
                          'assignments': {'flag': True}},
                         {'id': 'exit', 'label': 'Exit', 'target': e.nodes[2]}]},
            {'node_id': e.nodes[1], 'node_version': 1, 'title': 'Unused ending', 'ending': 'Unused unreachable ending'},
            {'node_id': e.nodes[2], 'node_version': 1, 'title': 'Ending', 'ending': 'Loop ending'}]}
    ).model_dump()
    row = approve(e, create(e, loop_spec))
    value = {'expected_version': row['version']}
    _, out = _export_current(e, row, value)
    prefix = 'interactive-ink-2-3-2-current-artifact-v1-' + row['id'] + '/'
    files = read_zip_safely(base64.b64decode(out['content_base64']), prefix)
    assert json.loads(files['acceptance/witness.json'])['step_cap_cases']
    completed, report, _ = _run_verifier(tmp_path, files, node, root, 'loop')
    assert completed.returncode == 0, (json.dumps(report, ensure_ascii=False)[:5000] if report else (completed.stderr or '')[-4000:])
    assert report['result'] == 'PASS'
    step_cap = [case for case in report['runtime']['cases'] if case['kind'] == 'STEP_CAP']
    assert len(step_cap) == 1 and step_cap[0]['passed'] is True
    assert step_cap[0]['final_status'] == 'STEP_CAP_REACHED'
    assert report['runtime']['step_cap_enforced'] is True
    # The loop witness has a real post-choice save with changed variables.
    assert report['assertions']['save_restore'] == 'PASS', json.dumps(report['cross_process'], ensure_ascii=False)[:2000]
    assert report['cross_process']['saved_after_choice'] is True
    assert report['cross_process']['variables_changed_before_save'] is True
    assert report['cross_process']['save_at_step'] >= 1
    assert report['cross_process']['remaining']
    assert report['save_envelope']['pinned'] is True


def test_verifier_detects_tampered_current_artifact(interactive_env, tmp_path):
    node, root = _runtime_env()
    e = interactive_env
    row = approve(e, create(e))
    value = {'expected_version': row['version']}
    _, out = _export_current(e, row, value)
    prefix = 'interactive-ink-2-3-2-current-artifact-v1-' + row['id'] + '/'
    files = read_zip_safely(base64.b64decode(out['content_base64']), prefix)
    tampered = dict(files)
    marker = 'Choose'.encode('utf-8')
    assert marker in tampered['ink/story.ink']
    tampered['ink/story.ink'] = tampered['ink/story.ink'].replace(marker, b'ChoosX', 1)
    completed, report, _ = _run_verifier(tmp_path, tampered, node, root, 'tampered')
    assert completed.returncode != 0, 'a tampered story source must not pass acceptance'
    assert report is not None and report['result'] == 'FAIL'
    assert report['assertions']['text'] == 'FAIL'


def test_verifier_accepts_the_exported_zip_directly(interactive_env, tmp_path):
    node, root = _runtime_env()
    import subprocess
    e = interactive_env
    row = approve(e, create(e))
    value = {'expected_version': row['version']}
    _, out = _export_current(e, row, value)
    zip_file = tmp_path / 'exported-ink.zip'
    zip_file.write_bytes(base64.b64decode(out['content_base64']))
    report_file = tmp_path / 'zip-report.json'
    completed = subprocess.run([node, str(_verify_script()), '--bundle', str(zip_file), '--vendor', root,
                                '--report', str(report_file)], capture_output=True, text=True, encoding='utf-8',
                               errors='replace', timeout=240, check=False)
    payload = json.loads(report_file.read_text(encoding='utf-8')) if report_file.exists() else None
    assert completed.returncode == 0, (completed.stderr or '')[-3000:] + json.dumps(payload, ensure_ascii=False)[:2000]
    assert payload['result'] == 'PASS'
    assert payload['bundle_extracted'] is True
    assert payload['bundle_zip_sha256'] == _sha(zip_file.read_bytes())
    assert payload['delivered_player']['sha256'] == payload['delivered_player']['pinned_sha256']
    assert payload['save_envelope']['pinned'] is True
