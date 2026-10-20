"""B07/DIF-10/E2E-07 C line: Godot 4 runnable runtime project target.

Covers the fixed GDScript template (hashes, static safety audit), the typed data
schema and witness, the deterministic bundle/manifest/receipt/zip, compatibility
gating, the unchanged legacy data adapter, the service end-to-end export, and - when
the real Godot 4 engine is available on this host - actual headless execution aligned
with authoritative Python playback plus two-process save/restore and tamper rejection.
"""
import base64
import hashlib
import json
import os
import re
import shutil
import subprocess
import zipfile
from copy import deepcopy
from pathlib import Path

import pytest

import app.experimental.interactive_export_contract as contract
import app.experimental.interactive_godot_export as godot_export
from app.experimental.interactive_story import (
    GodotExportAdapter, InteractiveStoryService, StorySpec, analyze,
)
from app.experimental.planning import PlanningService
from app.experimental.story_graph import StoryGraphService
from app.services.asset_library_service import AssetLibraryService
from test_r4_revision_intelligence import revision_env

TARGET_ID = 'GODOT_4_RUNTIME_PROJECT_V1'
LEGACY_TARGET_ID = 'GODOT_4_DATA_ADAPTER'
GODOT_HINTS = [r'D:\GameDev\Godot\Godot-4.7-stable\Godot_v4.7-stable_win64_console.exe']
PAYLOAD_FILES = {
    'README.md', 'acceptance/README.txt', 'acceptance/cases.json', 'data/story.json',
    'data/story.schema.json', 'main.gd', 'main.tscn', 'project.godot',
    'runtime/acceptance_runner.gd', 'runtime/save_store.gd', 'runtime/story_loader.gd',
    'runtime/story_runtime.gd',
}
FORBIDDEN_TOKENS = ['Expression', 'JavaScriptBridge', 'OS.execute', 'OS.shell_open',
                    'OS.create_process', 'HTTPRequest', 'HTTPClient', 'WebSocketPeer', 'DirAccess',
                    'ResourceLoader.load', 'RichTextLabel', 'bbcode']
FORBIDDEN_PATTERNS = [(r'(?<![A-Za-z0-9_])eval\s*\(', 'eval call'),
                      (r'(?<![A-Za-z0-9_])load\s*\(', 'dynamic load call')]


def engine_path():
    candidates = [os.environ.get('POEMSEED_GODOT_BIN'), *GODOT_HINTS]
    for name in ('godot', 'godot.exe', 'Godot_v4.7-stable_win64_console.exe'):
        found = shutil.which(name)
        if found:
            candidates.append(found)
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    return None


GODOT = engine_path()
requires_godot = pytest.mark.skipif(GODOT is None, reason='BLOCKED_ENVIRONMENT: Godot 4 executable not available')


def raw_spec():
    return {
        'title': 'B07 运行时 Story "quoted" \\ backslash',
        'graph_id': 'b07-runtime-graph',
        'graph_version': 2,
        'entry_node_id': 'n1',
        'max_steps': 6,
        'graph_record_ids': [],
        'variables': [
            {'name': 'courage', 'type': 'int', 'initial': 0, 'minimum': 0, 'maximum': 3},
            {'name': 'trust', 'type': 'bool', 'initial': True, 'minimum': 0, 'maximum': 100},
        ],
        'nodes': [
            {'node_id': 'n1', 'node_version': 1, 'title': '门', 'character_id': 'alice',
             'dialogue': '要出发吗？\n第二行 "引号"、反斜杠 \\ 和制表符\t结束。',
             'choices': [
                 {'id': 'go', 'label': '出发', 'target': 'n2',
                  'condition': 'trust and courage <= 1', 'assignments': {'courage': 2}},
                 {'id': 'wait', 'label': '等待', 'target': 'n3',
                  'condition': 'not trust or courage >= 0', 'assignments': {}},
             ]},
            {'node_id': 'n2', 'node_version': 1, 'title': '港', 'character_id': None,
             'dialogue': '海风吹过。', 'background_asset_id': 'bg-harbour',
             'choices': [
                 {'id': 'home', 'label': '回家', 'target': 'n4',
                  'condition': 'courage == 2 and trust', 'assignments': {}},
                 {'id': 'away', 'label': '离开', 'target': 'n5',
                  'condition': 'courage != 0', 'assignments': {}},
             ]},
            {'node_id': 'n3', 'node_version': 1, 'title': '山', 'character_id': 'alice',
             'dialogue': '山雾四起。', 'ending': '山结局'},
            {'node_id': 'n4', 'node_version': 1, 'title': '家', 'character_id': None,
             'dialogue': '灯还亮着。', 'ending': '港口结局'},
            {'node_id': 'n5', 'node_version': 1, 'title': '路', 'character_id': None,
             'dialogue': '路很长。', 'ending': '离去结局'},
        ],
    }


SPEC = StorySpec.model_validate(raw_spec()).model_dump()
CHARACTERS = {'alice': '爱丽丝'}
ANALYSIS = analyze(SPEC)


def build_snapshot(spec=None, **overrides):
    spec = deepcopy(spec or SPEC)
    analysis = analyze(spec)
    snapshot = {
        'story_id': 'b07-godot-pytest', 'revision': 4, 'status': 'APPROVED', 'title': spec['title'],
        'spec': spec, 'spec_digest': contract.digest(spec),
        'source_digest': hashlib.sha256(b'b07-godot-source').hexdigest(),
        'review_receipt': hashlib.sha256(b'b07-godot-review').hexdigest(),
        'characters': dict(CHARACTERS), 'witness': analysis['endings'],
        'media_manifest': [{'asset_id': 'bg-harbour', 'version': 1, 'sha256': 'd' * 64, 'kind': 'image',
                            'missing': False, 'packaged': False, 'reason': 'REFERENCE_ONLY'}],
        'analysis': analysis,
    }
    snapshot.update(overrides)
    return snapshot


def build_bundle(snapshot=None):
    return contract.build_export_bundle(TARGET_ID, snapshot or build_snapshot())


# ---------------------------------------------------------------------------
# registry, descriptor, template
# ---------------------------------------------------------------------------
def test_target_registered_as_runnable_project_and_legacy_id_preserved():
    ids = contract.available_target_ids()
    assert TARGET_ID in ids and LEGACY_TARGET_ID in ids
    descriptor = contract.describe_target(TARGET_ID)
    assert descriptor.kind == 'RUNNABLE_PROJECT'
    assert descriptor.format_version == godot_export.FORMAT_VERSION == 'godot-runtime-project-1'
    assert descriptor.adapter_revision == 1
    assert descriptor.engine is not None and descriptor.engine.env_override == 'POEMSEED_GODOT_BIN'
    assert descriptor.engine.minimum_version == '4.0'
    assert set(descriptor.capabilities) == set(contract.CAPABILITY_KEYS)
    assert descriptor.capabilities['save'].supported is True and descriptor.capabilities['restore'].supported is True
    assert descriptor.capabilities['conditions'].supported is True and descriptor.capabilities['unicode'].supported is True
    legacy = contract.describe_target(LEGACY_TARGET_ID)
    assert legacy.kind == 'DATA_ONLY_ADAPTER' and legacy.format_version == 'godot-data-1'
    assert legacy.capabilities['save'].supported is False


def test_descriptor_evidence_is_honest_and_gui_is_never_claimed():
    evidence = contract.evidence_for(TARGET_ID)
    for level, status in evidence.items():
        assert status in contract.EVIDENCE_STATUSES, level
        if level in {'SOURCE_IMPLEMENTED', 'SCHEMA_VALIDATED', 'FIXTURE_TESTED',
                     'GENERATED_ARTIFACT_VALIDATED', 'TARGET_RUNTIME_EXECUTED', 'SAVE_RESTORE_VERIFIED'}:
            assert status == 'PASS', level
    assert evidence['WINDOWS_USABILITY_VERIFIED'] == 'NOT_RUN'
    descriptor = contract.describe_target(TARGET_ID)
    assert descriptor.evidence.get('WINDOWS_USABILITY_VERIFIED') is None
    assert any('GUI_USABILITY' in loss for loss in descriptor.losses)


def test_fixed_runtime_template_matches_pinned_hashes():
    pinned = godot_export.PINNED_TEMPLATE_SHA256
    assert len(pinned) == len(godot_export.FIXED_TEMPLATE_FILES) == 6
    assert pinned == godot_export.template_hashes()
    for relative, digest in pinned.items():
        assert re.fullmatch(r'[a-f0-9]{64}', digest), relative
        assert (godot_export.template_root() / relative).is_file(), relative
    template = (godot_export.template_root() / 'project.godot.tmpl').read_text(encoding='utf-8')
    assert template.count(godot_export.PROJECT_NAME_TOKEN) == 1
    assert 'config_version=5' in template and 'res://main.tscn' in template and '960' in template and '600' in template
    assert (godot_export.template_root() / 'runtime' / 'story_loader.gd').stat().st_size > 1000


def _strip_comments(text):
    return '\n'.join(line.split('#', 1)[0] for line in text.splitlines())


def test_runtime_template_has_no_dynamic_execution_network_or_rich_text():
    for relative in godot_export.FIXED_TEMPLATE_FILES:
        text = (godot_export.template_root() / relative).read_text(encoding='utf-8')
        code = _strip_comments(text) if relative.endswith('.gd') else text
        for token in FORBIDDEN_TOKENS:
            assert token not in code, relative + ': ' + token
        for pattern, description in FORBIDDEN_PATTERNS:
            assert not re.search(pattern, code), relative + ': ' + description
        if relative.endswith('.gd'):
            assert code.count('FileAccess.open') <= {'runtime/story_loader.gd': 1, 'runtime/save_store.gd': 2}.get(relative, 0)
            for line in code.splitlines():
                if 'load(' in line:
                    assert 'preload(' in line or '.load_file(' in line, relative + ': ' + line
    main_script = (godot_export.template_root() / 'main.gd').read_text(encoding='utf-8')
    for relative in godot_export.FIXED_TEMPLATE_FILES:
        if relative.startswith('runtime/'):
            assert 'preload("res://' + relative + '")' in main_script, relative
    assert 'Main' in (godot_export.template_root() / 'main.tscn').read_text(encoding='utf-8')
    loader = (godot_export.template_root() / 'runtime' / 'story_loader.gd').read_text(encoding='utf-8')
    for operator in ('"literal"', '"var"', '"not"', '"and"', '"or"', '"eq"', '"ne"', '"lt"', '"le"', '"gt"', '"ge"'):
        assert operator in loader, operator
    assert 'RichTextLabel' not in main_script and 'Label.new()' in main_script and 'Button.new()' in main_script


# ---------------------------------------------------------------------------
# typed data schema, witness, bundle
# ---------------------------------------------------------------------------
def test_story_resource_is_typed_and_preserves_unicode_and_escaping():
    bundle = build_bundle()
    story = json.loads(bundle.files['data/story.json'])
    model = godot_export.GodotRuntimeStory.model_validate(story)
    assert model.engine_target == TARGET_ID and model.format_version == godot_export.RUNTIME_STORY_FORMAT
    assert model.revision == 4 and model.story_id == 'b07-godot-pytest'
    assert model.entry_node_id == SPEC['entry_node_id']
    node = model.nodes[0]
    assert node.dialogue == SPEC['nodes'][0]['dialogue']
    assert spec_dialogue_has_escaping(node.dialogue)
    condition = model.nodes[1].choices[0].condition
    assert condition.op == 'and' and condition.args[0].op == 'eq'
    assert condition.args[1].op == 'var' and condition.args[1].name == 'trust'
    assert model.media_references[0].asset_id == 'bg-harbour'
    assert {record.node_id for record in model.witness} == {record['node_id'] for record in ANALYSIS['endings']}
    for record in model.witness:
        final = godot_export.expected_state(SPEC, CHARACTERS, record.choices)
        assert final['node']['node_id'] == record.node_id
        assert final['status'] == 'ENDING'
        assert final['node']['ending'] == record.ending
    schema = json.loads(bundle.files['data/story.schema.json'])
    assert schema.get('title') == 'GodotRuntimeStory'
    assert 'properties' in schema


def spec_dialogue_has_escaping(text):
    return '\n' in text and '"' in text and '\\' in text and '\t' in text and '。' in text


def test_bundle_manifest_receipt_hashes_and_zip_are_deterministic():
    first = build_bundle()
    second = build_bundle()
    assert first.files == second.files and first.files_digest == second.files_digest
    assert first.target_id == TARGET_ID and first.kind == 'RUNNABLE_PROJECT'
    assert set(first.files) == PAYLOAD_FILES | {'manifest.json', 'source-receipt.json'}
    payload = {path: content for path, content in first.files.items() if path not in {'manifest.json', 'source-receipt.json'}}
    manifest = json.loads(first.files['manifest.json'])
    receipt = json.loads(first.files['source-receipt.json'])
    assert manifest['target_id'] == TARGET_ID and receipt['target_id'] == TARGET_ID
    assert manifest['target_kind'] == 'RUNNABLE_PROJECT' and manifest['target_format_version'] == godot_export.FORMAT_VERSION
    assert manifest['payload_files_digest'] == contract.files_digest(payload)
    assert [entry['path'] for entry in manifest['files']] == sorted(payload)
    for entry in manifest['files']:
        assert entry['sha256'] == hashlib.sha256(payload[entry['path']]).hexdigest()
        assert entry['bytes'] == len(payload[entry['path']])
    assert receipt['manifest_sha256'] == hashlib.sha256(first.files['manifest.json']).hexdigest()
    assert receipt['payload_files_digest'] == first.payload_files_digest
    assert receipt['capabilities_supported'] and 'media' in receipt['capabilities_unsupported']
    runtime = manifest['extra']['godot_runtime']
    assert runtime['template_files'] == godot_export.template_hashes()
    assert runtime['runtime_story_schema'] == godot_export.RUNTIME_STORY_SCHEMA
    assert runtime['main_scene'] == 'res://main.tscn'
    assert runtime['save_path_policy'].startswith('user://')
    assert manifest['runtime']['evidence']['WINDOWS_USABILITY_VERIFIED'] == 'NOT_RUN'
    assert manifest['runtime']['evidence']['TARGET_RUNTIME_EXECUTED'] == 'PASS'
    project = payload['project.godot'].decode('utf-8')
    assert 'config_version=5' in project and 'run/main_scene="res://main.tscn"' in project
    assert 'config/name="PoemSeed Story b07-godot-pytest"' in project
    assert 'viewport_width=960' in project and 'viewport_height=600' in project
    package = contract.package_export_zip(first)
    assert package['content'] == contract.package_export_zip(second)['content']
    read_back = contract.read_zip_safely(package['content'], package['prefix'])
    assert read_back == first.files
    assert package['file_count'] == len(first.files) == 14


def test_acceptance_cases_are_the_python_playback_oracle():
    bundle = build_bundle()
    cases = json.loads(bundle.files['acceptance/cases.json'])
    assert cases['schema'] == godot_export.CASES_SCHEMA
    assert cases['target_id'] == TARGET_ID
    assert cases['truncated'] is False
    assert len(cases['cases']) == len(ANALYSIS['endings'])
    for case in cases['cases']:
        expected = godot_export.expected_state(SPEC, CHARACTERS, case['choices'])
        assert case['expected_final'] == expected
        assert expected['status'] == 'ENDING'
        assert case['choices']


def test_compatibility_blocks_unanalyzable_stories_and_reports_why():
    cycle = StorySpec.model_validate({
        'title': 'cycle', 'graph_id': 'cycle-graph', 'graph_version': 1, 'entry_node_id': 'c1', 'max_steps': 3,
        'variables': [{'name': 'flag', 'type': 'bool', 'initial': True, 'minimum': 0, 'maximum': 100}],
        'nodes': [{'node_id': 'c1', 'node_version': 1, 'title': 'loop', 'dialogue': 'again',
                   'choices': [{'id': 'loop', 'label': 'again', 'target': 'c1', 'condition': 'flag', 'assignments': {}}]}],
    }).model_dump()
    snapshot = build_snapshot(spec=cycle, witness=[])
    report = godot_export.compatibility(snapshot)
    assert report['can_export'] is False
    codes = {issue['code'] for issue in report['issues']}
    assert any(code.startswith('GODOT_RUNTIME_ANALYSIS:') for code in codes)
    with pytest.raises(ValueError):
        contract.build_export_bundle(TARGET_ID, snapshot)
    no_ending = StorySpec.model_validate({
        'title': 'dead', 'graph_id': 'dead-graph', 'graph_version': 1, 'entry_node_id': 'd1', 'max_steps': 4,
        'variables': [{'name': 'open', 'type': 'bool', 'initial': False, 'minimum': 0, 'maximum': 100}],
        'nodes': [
            {'node_id': 'd1', 'node_version': 1, 'title': 'locked', 'dialogue': 'locked',
             'choices': [{'id': 'open', 'label': 'open', 'target': 'd2', 'condition': 'open', 'assignments': {}}]},
            {'node_id': 'd2', 'node_version': 1, 'title': 'out', 'dialogue': 'out', 'ending': 'out'},
        ],
    }).model_dump()
    report = godot_export.compatibility(build_snapshot(spec=no_ending, witness=[]))
    assert report['can_export'] is False
    assert any(issue['code'] == 'GODOT_RUNTIME_ANALYSIS:CONDITIONAL_NO_EXIT' for issue in report['issues'])
    missing_witness = godot_export.compatibility(build_snapshot(witness=[]))
    assert missing_witness['can_export'] is False
    assert any(issue['code'] == 'GODOT_RUNTIME_WITNESS_MISSING' for issue in missing_witness['issues'])


def test_compatibility_reports_missing_speaker_and_invalid_spec():
    snapshot = build_snapshot()
    snapshot['characters'] = {}
    report = godot_export.compatibility(snapshot)
    assert report['can_export'] is False
    assert any(issue['code'] == 'GODOT_RUNTIME_SPEAKER_UNAVAILABLE' for issue in report['issues'])
    broken = build_snapshot()
    broken['spec'] = {**broken['spec'], 'nodes': 'not-a-list'}
    report = godot_export.compatibility(broken)
    assert report['can_export'] is False
    assert report['issues'][0]['code'] == 'GODOT_RUNTIME_SPEC_INVALID'
    tampered = build_snapshot()
    tampered['witness'] = [{'node_id': 'n1', 'ending': 'wrong', 'choices': ['go']}]
    report = godot_export.compatibility(tampered)
    assert any(issue['code'] == 'GODOT_RUNTIME_WITNESS_INVALID' for issue in report['issues'])


def test_legacy_godot_data_adapter_output_is_unchanged():
    resource = GodotExportAdapter().resource(deepcopy(SPEC), dict(CHARACTERS))
    assert resource['schema'] == 'ai-novel-godot-story/1'
    assert resource['engine_target'] == LEGACY_TARGET_ID
    assert resource['runtime_verification'] == 'NOT_RUN'
    assert resource['importer_status'] == 'TARGET_INTEGRATION_REQUIRED'
    files = GodotExportAdapter().files(deepcopy(SPEC), dict(CHARACTERS))
    assert set(files) == {'godot/story.json', 'godot/story.schema.json', 'godot/README.txt'}
    decoded = json.loads(files['godot/story.json'])
    assert decoded['schema'] == 'ai-novel-godot-story/1'
    assert decoded['nodes'][0]['choices'][0]['target_index'] == 1
    descriptor = contract.describe_target(LEGACY_TARGET_ID)
    assert descriptor.format_version == 'godot-data-1'
    assert descriptor.kind == 'DATA_ONLY_ADAPTER'


# ---------------------------------------------------------------------------
# service end-to-end
# ---------------------------------------------------------------------------
@pytest.fixture
def interactive_env(revision_env):
    e = revision_env
    e.planning = PlanningService(e.store, e.novels, e.chapters)
    e.story_graph = StoryGraphService(e.store, e.novels, e.chapters)
    e.assets = AssetLibraryService(e.store.root)
    e.service = InteractiveStoryService(e.store, e.novels, e.chapters, e.planning, e.story_graph, e.assets)
    e.novels.upsert_character(e.nid, 'alice', {'name': 'Alice'})
    e.graph = e.planning.create_graph(e.nid, e.scope, 'author', {'title': 'Godot runtime tree',
        'links': {'chapter_ids': [e.cid], 'character_ids': ['alice']}})
    e.nodes = [e.graph['root_node_id']]
    for title in ['Harbour', 'Mountain']:
        e.nodes.append(e.planning.create_node(e.nid, e.scope, 'author', {
            'graph_id': e.graph['id'], 'parent_id': e.nodes[0], 'level': 'VOLUME', 'title': title})['id'])
    return e


def service_spec(e):
    return {'title': 'Synthetic Godot runtime adaptation', 'graph_id': e.graph['id'], 'graph_version': 1,
            'entry_node_id': e.nodes[0], 'graph_record_ids': [],
            'variables': [{'name': 'courage', 'type': 'int', 'initial': 0, 'minimum': 0, 'maximum': 3},
                          {'name': 'trusted', 'type': 'bool', 'initial': True}],
            'nodes': [
                {'node_id': e.nodes[0], 'node_version': 1, 'title': 'Gate', 'character_id': 'alice', 'dialogue': 'Choose',
                 'choices': [{'id': 'harbour', 'label': 'To harbour', 'target': e.nodes[1], 'condition': 'trusted',
                              'assignments': {'courage': 2}},
                             {'id': 'mountain', 'label': 'To mountain', 'target': e.nodes[2],
                              'condition': 'not (courage > 3)', 'assignments': {'trusted': False}}]},
                {'node_id': e.nodes[1], 'node_version': 1, 'title': 'Harbour', 'dialogue': 'Home', 'ending': 'Harbour ending'},
                {'node_id': e.nodes[2], 'node_version': 1, 'title': 'Mountain', 'dialogue': 'Beyond', 'ending': 'Mountain ending'}]}


def create_approved(e):
    row = e.service.create_story(e.nid, e.scope, 'author', {'spec': service_spec(e)})
    row = e.service.review(e.nid, e.scope, 'author', row['id'], {'expected_version': row['version'], 'action': 'submit'})
    receipt = e.service.review_preview(e.nid, e.scope, 'author', row['id'], {'expected_version': row['version']})
    return e.service.review(e.nid, e.scope, 'author', row['id'], {
        'expected_version': row['version'], 'action': 'approve', 'preview_digest': receipt['preview_digest']})


def zip_prefix(story_id):
    return 'interactive-' + contract._filename_slug(TARGET_ID) + '-' + story_id + '/'


def test_service_exports_runnable_godot_project_end_to_end(interactive_env):
    e = interactive_env
    row = create_approved(e)
    value = {'expected_version': row['version']}
    targets = e.service.export_targets(e.nid, e.scope, 'author', row['id'], value)
    target = next(item for item in targets['targets'] if item['target_id'] == TARGET_ID)
    assert target['kind'] == 'RUNNABLE_PROJECT'
    assert target['compatibility']['can_export'] is True
    assert target['export_ready'] is True
    assert target['engine_probe']['status'] in {'READY', 'NOT_INSTALLED', 'UNSUPPORTED_VERSION', 'PROBE_FAILED'}
    assert target['evidence']['TARGET_RUNTIME_EXECUTED'] == 'PASS'
    assert target['runtime_claim'] == 'SAVE_RESTORE_VERIFIED'
    preview = e.service.export_preview(e.nid, e.scope, 'author', row['id'], {**value, 'target_id': TARGET_ID})
    assert preview['can_export'] is True and preview['target_id'] == TARGET_ID
    assert preview['selected_target']['target_id'] == TARGET_ID
    out = e.service.export(e.nid, e.scope, 'author', row['id'], {
        **value, 'target_id': TARGET_ID, 'preview_digest': preview['preview_digest']})
    content = base64.b64decode(out['content_base64'])
    assert hashlib.sha256(content).hexdigest() == out['sha256']
    assert out['target_id'] == TARGET_ID and out['file_count'] == 14
    assert out['runtime_claim'] == 'SAVE_RESTORE_VERIFIED' and out['published'] is False
    files = contract.read_zip_safely(content, zip_prefix(row['id']))
    assert set(files) == PAYLOAD_FILES | {'manifest.json', 'source-receipt.json'}
    story = json.loads(files['data/story.json'])
    godot_export.GodotRuntimeStory.model_validate(story)
    assert story['story_id'] == row['id'] and story['revision'] == row['version']
    assert story['spec_digest'] == contract.digest(row['spec'])
    cases = json.loads(files['acceptance/cases.json'])
    assert cases['cases'] and cases['story_id'] == row['id']
    manifest = json.loads(files['manifest.json'])
    assert manifest['target_kind'] == 'RUNNABLE_PROJECT'
    assert manifest['extra']['godot_runtime']['template_files'] == godot_export.template_hashes()
    assert manifest['runtime']['evidence']['SAVE_RESTORE_VERIFIED'] == 'PASS'
    assert manifest['runtime']['evidence']['WINDOWS_USABILITY_VERIFIED'] == 'NOT_RUN'
    # the legacy combined export is untouched and still carries the old data adapter output
    legacy_preview = e.service.export_preview(e.nid, e.scope, 'author', row['id'], value)
    legacy = e.service.export(e.nid, e.scope, 'author', row['id'], {**value, 'preview_digest': legacy_preview['preview_digest']})
    with zipfile.ZipFile(__import__('io').BytesIO(base64.b64decode(legacy['content_base64']))) as archive:
        names = archive.namelist()
        assert any(name.endswith('godot/story.json') for name in names)
        assert any(name.endswith('game/story.rpy') for name in names)
        legacy_story = json.loads(archive.read(next(name for name in names if name.endswith('godot/story.json'))))
        assert legacy_story['engine_target'] == LEGACY_TARGET_ID


def test_service_blocks_godot_export_for_unapproved_revision(interactive_env):
    e = interactive_env
    row = e.service.create_story(e.nid, e.scope, 'author', {'spec': service_spec(e)})
    value = {'expected_version': row['version']}
    preview = e.service.export_preview(e.nid, e.scope, 'author', row['id'], {**value, 'target_id': TARGET_ID})
    assert preview['can_export'] is False
    assert preview['selected_target']['export_ready'] is False
    with pytest.raises(ValueError):
        e.service.export(e.nid, e.scope, 'author', row['id'], {
            **value, 'target_id': TARGET_ID, 'preview_digest': preview['preview_digest']})
    with pytest.raises(ValueError):
        e.service.export_preview(e.nid, e.scope, 'author', row['id'], {**value, 'target_id': 'NO_SUCH_TARGET'})


# ---------------------------------------------------------------------------
# real Godot runtime execution
# ---------------------------------------------------------------------------
def _run(project, user_args, timeout=120):
    argv = [GODOT, '--headless', '--quit-after', '900', '--path', str(project), '--', *user_args]
    process = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        stdout, stderr = process.communicate()
        raise AssertionError('Godot runtime timed out: ' + ' '.join(argv))
    text = stdout.decode('utf-8', 'replace')
    records = {'states': [], 'done': None, 'error': None, 'saved': None, 'result': None,
               'restored': None, 'user_dir': None, 'exit_code': process.returncode,
               'stderr': stderr.decode('utf-8', 'replace'), 'argv': argv}
    for line in text.splitlines():
        if 'POEMSEED_STATE ' in line:
            records['states'].append(json.loads(line.split('POEMSEED_STATE ', 1)[1]))
        elif 'POEMSEED_DONE ' in line:
            records['done'] = json.loads(line.split('POEMSEED_DONE ', 1)[1])
        elif 'POEMSEED_ERROR ' in line:
            records['error'] = json.loads(line.split('POEMSEED_ERROR ', 1)[1])
        elif 'POEMSEED_SAVED ' in line:
            records['saved'] = json.loads(line.split('POEMSEED_SAVED ', 1)[1])
        elif 'POEMSEED_RESULT ' in line:
            records['result'] = json.loads(line.split('POEMSEED_RESULT ', 1)[1])
        elif 'POEMSEED_RESTORED ' in line:
            records['restored'] = json.loads(line.split('POEMSEED_RESTORED ', 1)[1])
        elif 'POEMSEED_USERDIR ' in line:
            records['user_dir'] = Path(line.split('POEMSEED_USERDIR ', 1)[1].strip().rstrip('/' + os.sep))
    return records


def assert_typed_equal(expected, actual, where='state'):
    assert type(expected) is type(actual), where + ': type ' + type(expected).__name__ + ' != ' + type(actual).__name__
    if isinstance(expected, dict):
        assert set(expected) == set(actual), where + ': keys ' + str(set(expected) ^ set(actual))
        for key in expected:
            assert_typed_equal(expected[key], actual[key], where + '.' + str(key))
        return
    if isinstance(expected, list):
        assert len(expected) == len(actual), where + ': length'
        for index, (left, right) in enumerate(zip(expected, actual)):
            assert_typed_equal(left, right, where + '[' + str(index) + ']')
        return
    assert expected == actual, where + ': ' + repr(expected) + ' != ' + repr(actual)


def _extract_project(tmp_path):
    bundle = build_bundle()
    package = contract.package_export_zip(bundle)
    project = tmp_path / 'project'
    project.mkdir()
    with zipfile.ZipFile(__import__('io').BytesIO(package['content'])) as archive:
        for name in archive.namelist():
            relative = name[len(package['prefix']):]
            if not relative:
                continue
            destination = project / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(archive.read(name))
    return project, bundle


@requires_godot
def test_real_godot_headless_run_aligns_every_step_with_python_playback(tmp_path):
    project, bundle = _extract_project(tmp_path)
    initial = _run(project, ['--print-user-dir'])
    assert initial['exit_code'] == 0, initial
    assert 'SCRIPT ERROR' not in initial['stderr']
    cases = json.loads((project / 'acceptance/cases.json').read_text(encoding='utf-8'))
    assert_typed_equal([godot_export.expected_state(SPEC, CHARACTERS, [])], initial['states'], 'initial')
    assert initial['done']['path'] == [] and initial['done']['status'] == 'PLAYING'
    states_compared = 1
    for case in cases['cases']:
        path = case['choices']
        result = _run(project, ['--witness-path', ','.join(path)])
        assert result['exit_code'] == 0, result
        expected = [godot_export.expected_state(SPEC, CHARACTERS, path[:depth]) for depth in range(len(path) + 1)]
        assert_typed_equal(expected, result['states'], 'case-' + ','.join(path))
        assert result['done']['path'] == path and result['done']['status'] == 'ENDING'
        assert_typed_equal(case['expected_final'], result['states'][-1], 'cases-json-final')
        states_compared += len(expected)
    assert len(cases['cases']) == len(ANALYSIS['endings']) == 3
    assert states_compared >= 8


@requires_godot
def test_real_godot_two_process_save_restore_and_rejection_matrix(tmp_path):
    project, _ = _extract_project(tmp_path)
    cases = json.loads((project / 'acceptance/cases.json').read_text(encoding='utf-8'))
    path = max(cases['cases'], key=lambda case: len(case['choices']))['choices']
    assert len(path) >= 2
    prefix, continuation = path[:1], path[1:]
    user_dir = None
    try:
        first = _run(project, ['--witness-path', ','.join(prefix), '--save', 'user://pytest-godot-save.json'])
        assert first['exit_code'] == 0, first
        expected_prefix_states = [godot_export.expected_state(SPEC, CHARACTERS, prefix[:depth])
                                  for depth in range(len(prefix) + 1)]
        assert_typed_equal(expected_prefix_states, first['states'], 'saved-state')
        user_dir = first['user_dir']
        assert user_dir is not None and user_dir.is_dir()
        save_file = user_dir / 'pytest-godot-save.json'
        save_bytes = save_file.read_bytes()
        assert first['saved']['sha256'] == hashlib.sha256(save_bytes).hexdigest()
        save = json.loads(save_bytes.decode('utf-8'))
        assert save['schema'] == godot_export.SAVE_SCHEMA and save['save_schema_version'] == 1
        assert save['story']['id'] == 'b07-godot-pytest' and save['story']['revision'] == 4
        assert save['path'] == prefix and save['steps'] == len(prefix)
        # restore then continue in a second process
        second = _run(project, ['--load', 'user://pytest-godot-save.json', '--witness-path', ','.join(continuation),
                                '--result', 'user://pytest-godot-result.json'])
        assert second['exit_code'] == 0, second
        expected = [godot_export.expected_state(SPEC, CHARACTERS, prefix)]
        for depth in range(1, len(continuation) + 1):
            expected.append(godot_export.expected_state(SPEC, CHARACTERS, prefix + continuation[:depth]))
        assert_typed_equal(expected, second['states'], 'restored-continuation')
        direct = godot_export.expected_state(SPEC, CHARACTERS, path)
        assert_typed_equal(direct, second['states'][-1], 'restored-final')
        assert second['restored']['steps'] == len(prefix)
        result_payload = json.loads((user_dir / 'pytest-godot-result.json').read_text(encoding='utf-8'))
        assert result_payload['schema'] == godot_export.RESULT_SCHEMA
        assert_typed_equal(direct, result_payload['state'], 'result-file')
        # tampered saves must be rejected, never applied
        tampered = deepcopy(save)
        tampered['story']['revision'] = 5
        (user_dir / 'pytest-reject-revision.json').write_text(json.dumps(tampered), encoding='utf-8')
        rejected = _run(project, ['--load', 'user://pytest-reject-revision.json'])
        assert rejected['exit_code'] == 2 and rejected['error']['code'] == 'SAVE_REJECTED'
        tampered = deepcopy(save)
        tampered['story']['source_digest'] = '0' * 64
        (user_dir / 'pytest-reject-source.json').write_text(json.dumps(tampered), encoding='utf-8')
        rejected = _run(project, ['--load', 'user://pytest-reject-source.json'])
        assert rejected['exit_code'] == 2 and rejected['error']['code'] == 'SAVE_REJECTED'
        tampered = deepcopy(save)
        tampered['variables']['courage'] = 3
        (user_dir / 'pytest-reject-variables.json').write_text(json.dumps(tampered), encoding='utf-8')
        rejected = _run(project, ['--load', 'user://pytest-reject-variables.json'])
        assert rejected['exit_code'] == 2 and rejected['error']['code'] == 'SAVE_REJECTED'
        (user_dir / 'pytest-reject-corrupt.json').write_text('{not-json', encoding='utf-8')
        rejected = _run(project, ['--load', 'user://pytest-reject-corrupt.json'])
        assert rejected['exit_code'] == 2 and rejected['error']['code'] == 'SAVE_REJECTED'
        # path safety: traversal and absolute paths are refused without creating files
        escape = user_dir.parent / 'pytest-godot-escape.json'
        if escape.exists():
            escape.unlink()
        traversal = _run(project, ['--result', 'user://../pytest-godot-escape.json'])
        assert traversal['exit_code'] == 3 and traversal['error']['code'] == 'RESULT_WRITE_FAILED'
        assert not escape.exists()
        absolute = _run(project, ['--save', 'C:/Windows/Temp/pytest-godot-absolute.json'])
        assert absolute['exit_code'] == 3 and absolute['error']['code'] == 'SAVE_WRITE_FAILED'
        assert not Path('C:/Windows/Temp/pytest-godot-absolute.json').exists()
    finally:
        if user_dir is not None and user_dir.is_dir():
            for name in ('pytest-godot-save.json', 'pytest-godot-result.json', 'pytest-reject-revision.json',
                         'pytest-reject-source.json', 'pytest-reject-variables.json', 'pytest-reject-corrupt.json'):
                target = user_dir / name
                if target.exists():
                    target.unlink()


# ---------------------------------------------------------------------------
# committed evidence cross-check
# ---------------------------------------------------------------------------
def test_committed_runtime_evidence_matches_descriptor_claims():
    path = Path(__file__).resolve().parent.parent / 'docs' / 'v2' / 'B07_GODOT_RUNTIME_EVIDENCE_20261020.json'
    if not path.is_file():
        pytest.skip('runtime evidence not generated in this checkout')
    evidence = json.loads(path.read_text(encoding='utf-8'))
    assert evidence['status'] == 'PASS'
    assert evidence['target']['target_id'] == TARGET_ID
    assert evidence['engine']['version_exit_code'] == 0
    levels = evidence['evidence_levels']
    assert levels['TARGET_RUNTIME_EXECUTED'] == 'PASS'
    assert levels['SAVE_RESTORE_VERIFIED'] == 'PASS'
    assert levels['WINDOWS_USABILITY_VERIFIED'] == 'NOT_RUN'
    claims = contract.evidence_for(TARGET_ID)
    for level, status in levels.items():
        assert claims[level] == status, level
    assert evidence['alignment']['states_compared'] > 0
    assert evidence['save_restore']['restored_states_compared'] > 0
    assert all(case['status'] == 'PASS' for case in evidence['save_restore']['rejection_cases'])
