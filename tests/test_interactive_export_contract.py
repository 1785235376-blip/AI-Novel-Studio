"""B07/DIF-10 frozen export-target contract: safety, manifests, receipts, evidence."""
import base64
import hashlib
import io
import json
import types
import zipfile
from copy import deepcopy

import pytest

import app.experimental.interactive_export_contract as contract
import app.experimental.interactive_story as story_service
from app.experimental.interactive_story import InteractiveStoryService, StorySpec
from app.experimental.planning import PlanningService
from app.experimental.story_graph import StoryGraphService
from app.services.asset_library_service import AssetLibraryService
from test_r4_revision_intelligence import revision_env

FAKE_TARGET = 'FAKE_RUNTIME_PROJECT_V1'


def _all_caps(**overrides):
    mapping = {key: True for key in contract.CAPABILITY_KEYS}
    mapping.update(overrides)
    return mapping


FAKE_DESCRIPTOR = {
    'target_id': FAKE_TARGET, 'display_name': 'Fake runtime project (contract fixture)',
    'kind': 'RUNNABLE_PROJECT', 'format_version': 'fake-1', 'adapter_revision': 1,
    'engine': {'name': 'FakeEngine', 'minimum_version': '1.0', 'executables': ['fake-engine'],
               'version_args': ['--version'], 'env_override': 'FAKE_ENGINE_BIN', 'gui': False},
    'capabilities': _all_caps(media=(False, True, 'reference only')),
    'losses': ['FAKE_MEDIA_NOT_PLAYED'], 'runtime_requirements': ['FakeEngine 1.0'],
    'launch_instructions': 'Open the generated project in FakeEngine.',
    'integration_notes': ['contract fixture'], 'evidence': {'SOURCE_IMPLEMENTED': 'PASS', 'FIXTURE_TESTED': 'PASS'},
}


def fake_module():
    descriptor = deepcopy(FAKE_DESCRIPTOR)

    def compatibility(snapshot):
        issues = []
        for node in snapshot['spec']['nodes']:
            if node.get('dialogue') == 'unsupported':
                issues.append({'code': 'FAKE_DIALOGUE_UNSUPPORTED', 'node_id': node['node_id']})
        return {'can_export': not issues, 'capabilities': deepcopy(descriptor['capabilities']),
                'losses': ['FAKE_MEDIA_NOT_PLAYED'], 'issues': issues, 'notes': ['fake compatibility']}

    def build(snapshot, options):
        story = {'schema': 'fake-story/1', 'story_id': snapshot['story_id'], 'revision': snapshot['revision'],
                 'spec_digest': snapshot['spec_digest'], 'nodes': snapshot['spec']['nodes']}
        if options.get('include_witness'): story['witness'] = snapshot['witness']
        return {'files': {'project.godot': b'[application]\nconfig/name="fake"\n',
                          'data/story.json': json.dumps(story, ensure_ascii=False, sort_keys=True).encode('utf-8'),
                          'runtime/play.gd': b'extends Node\n# trusted runtime fixture\n'},
                'manifest_extra': {'fake_adapter': True}}
    return types.SimpleNamespace(DESCRIPTOR=descriptor, compatibility=compatibility, build=build)


@pytest.fixture
def fake_target(monkeypatch):
    contract.clear_target_cache()
    contract.clear_probe_cache()
    monkeypatch.setattr(contract, 'TARGET_MODULES', {**contract.TARGET_MODULES, FAKE_TARGET: '.fake_adapter_for_contract'})
    monkeypatch.setitem(contract._MODULE_CACHE, FAKE_TARGET, fake_module())
    yield FAKE_TARGET
    contract.clear_target_cache()
    contract.clear_probe_cache()
    contract.EVIDENCE_OVERRIDES.clear()


SPEC = {'title': 'Synthetic contract story', 'graph_id': 'graph-1', 'graph_version': 1, 'entry_node_id': 'n1',
        'max_steps': 4, 'graph_record_ids': [],
        'variables': [{'name': 'trusted', 'type': 'bool', 'initial': True, 'minimum': 0, 'maximum': 100}],
        'nodes': [
            {'node_id': 'n1', 'node_version': 1, 'title': 'Gate', 'dialogue': 'Plain dialogue', 'character_id': None,
             'background_asset_id': None, 'music_asset_id': None, 'ending': '',
             'choices': [{'id': 'go', 'label': 'Go', 'target': 'n2', 'condition': 'trusted', 'assignments': {}}]},
            {'node_id': 'n2', 'node_version': 1, 'title': 'End', 'dialogue': 'Bye', 'character_id': None,
             'background_asset_id': None, 'music_asset_id': None, 'ending': 'The end', 'choices': []}]}


def snapshot(**overrides):
    value = {'story_id': 'story-1', 'revision': 2, 'status': 'APPROVED', 'title': SPEC['title'], 'spec': deepcopy(SPEC),
             'spec_digest': 'a' * 64, 'source_digest': 'b' * 64, 'review_receipt': 'c' * 64,
             'characters': {'alice': 'Alice'}, 'media_manifest': [],
             'witness': [{'node_id': 'n2', 'ending': 'The end', 'choices': ['go']}],
             'analysis': {'can_review': True, 'analysis_complete': True, 'issues': [], 'warnings': [],
                          'states_checked': 2, 'endings': [{'node_id': 'n2', 'ending': 'The end', 'choices': ['go']}],
                          'state_limit_reached': False, 'step_limit_reached': False, 'max_steps': 4}}
    value.update(overrides)
    return value


# ---------------------------------------------------------------------------
# registry and descriptors
# ---------------------------------------------------------------------------
def test_legacy_target_ids_and_output_contract_are_preserved():
    assert set(contract.LEGACY_TARGETS) == {'RENPY_8_5_4_TEXT_MENU_SUBSET', 'GODOT_4_DATA_ADAPTER', 'INKJS_2_3_2_TYPED_TEXT_SUBSET'}
    described = contract.describe_target('RENPY_8_5_4_TEXT_MENU_SUBSET')
    assert described.kind == 'LEGACY_FRAGMENT' and described.engine.minimum_version == '8.5.4'
    assert described.capabilities['save'].supported is False and described.capabilities['conditions'].supported is True
    document = contract.contract_document()
    assert document['version'] == contract.CONTRACT_VERSION
    assert document['adapter_contract']['may_execute_story_or_user_code'] is False
    assert tuple(document['capabilities']) == contract.CAPABILITY_KEYS


def test_adapter_descriptor_is_normalized_and_strictly_validated(fake_target):
    descriptor = contract.describe_target(fake_target)
    assert descriptor.kind == 'RUNNABLE_PROJECT'
    assert set(descriptor.capabilities) == set(contract.CAPABILITY_KEYS)
    assert descriptor.capabilities['save'].supported is True
    broken = {**FAKE_DESCRIPTOR, 'evidence': {'NOT_A_LEVEL': 'PASS'}}
    with pytest.raises(Exception): contract.TargetDescriptor.model_validate(broken)
    broken = {**FAKE_DESCRIPTOR, 'capabilities': {}}
    with pytest.raises(Exception): contract.TargetDescriptor.model_validate(broken)
    with pytest.raises(ValueError): contract.describe_target('NO_SUCH_TARGET')


def test_evidence_levels_default_to_not_run_and_never_upgrade(fake_target):
    evidence = contract.evidence_for(fake_target)
    assert evidence['SOURCE_IMPLEMENTED'] == 'PASS' and evidence['FIXTURE_TESTED'] == 'PASS'
    assert evidence['TARGET_RUNTIME_EXECUTED'] == 'NOT_RUN' and evidence['SAVE_RESTORE_VERIFIED'] == 'NOT_RUN'
    assert evidence['WINDOWS_USABILITY_VERIFIED'] == 'NOT_RUN'
    contract.EVIDENCE_OVERRIDES[FAKE_TARGET] = {'TARGET_RUNTIME_EXECUTED': 'PASS'}
    assert contract.evidence_for(fake_target)['TARGET_RUNTIME_EXECUTED'] == 'PASS'
    assert contract.evidence_for('NO_SUCH_TARGET')['TARGET_RUNTIME_EXECUTED'] == 'NOT_RUN'
    bundle = contract.build_export_bundle(fake_target, snapshot())
    assert bundle.manifest['runtime']['evidence']['TARGET_RUNTIME_EXECUTED'] == 'PASS'


# ---------------------------------------------------------------------------
# path and size safety
# ---------------------------------------------------------------------------
@pytest.mark.parametrize('path', ['../evil', '/absolute', 'a\\\\b', 'C:/evil', 'con', 'CON.txt', 'a//b', './a', 'a/../b',
                                  'trailing./x', 'trailing /x', '.hidden', 'a/' + 'b' * 300])
def test_bundle_paths_reject_traversal_absolute_reserved_and_invalid(path):
    with pytest.raises(ValueError): contract.safe_bundle_path(path)


@pytest.mark.parametrize('path', ['project.godot', 'game/story.rpy', 'data/story.json', 'scripts/play.gd',
                                  'acceptance/witness.json', 'README.txt', 'game/options.rpy'])
def test_bundle_paths_accept_plain_project_paths(path):
    assert contract.safe_bundle_path(path) == path


def test_normalize_files_rejects_collisions_and_oversize():
    with pytest.raises(ValueError): contract.normalize_files({'story.json': b'{}', 'Story.json': b'{}'})
    with pytest.raises(ValueError): contract.normalize_files({'story.json': 'text'})
    with pytest.raises(ValueError): contract.normalize_files({'big.bin': b'x' * (contract.MAX_FILE_BYTES + 1)})
    with pytest.raises(ValueError): contract.normalize_files({})
    assert list(contract.normalize_files({'b.txt': b'b', 'a.txt': b'a'})) == ['b.txt', 'a.txt']


# ---------------------------------------------------------------------------
# bundle, manifest, receipt, zip
# ---------------------------------------------------------------------------
def test_bundle_manifest_and_receipt_bind_every_file(fake_target):
    bundle = contract.build_export_bundle(fake_target, snapshot())
    files = bundle.files
    manifest = json.loads(files['manifest.json']); receipt = json.loads(files['source-receipt.json'])
    assert manifest['schema'] == contract.MANIFEST_SCHEMA and receipt['schema'] == contract.RECEIPT_SCHEMA
    payload = {path: content for path, content in files.items() if path not in {'manifest.json', 'source-receipt.json'}}
    assert sorted(payload) == sorted(entry['path'] for entry in manifest['files'])
    for entry in manifest['files']:
        assert entry['sha256'] == hashlib.sha256(payload[entry['path']]).hexdigest()
        assert entry['bytes'] == len(payload[entry['path']])
    assert manifest['payload_files_digest'] == contract.files_digest(payload)
    assert receipt['manifest_sha256'] == hashlib.sha256(files['manifest.json']).hexdigest()
    assert receipt['spec_digest'] == 'a' * 64 and receipt['source_digest'] == 'b' * 64
    assert receipt['target_id'] == fake_target and manifest['target_id'] == fake_target
    assert receipt['capabilities_supported'] and 'media' in receipt['capabilities_unsupported']
    assert manifest['story']['witness_digest'] == contract.digest(snapshot()['witness'])
    assert manifest['generation']['wall_clock_included'] is False
    contract.verify_bundle(bundle)


def test_bundle_is_deterministic_and_tampering_fails(fake_target):
    first = contract.build_export_bundle(fake_target, snapshot())
    second = contract.build_export_bundle(fake_target, snapshot())
    assert first.files == second.files and first.files_digest == second.files_digest
    tampered = first.model_copy(deep=True)
    tampered.files['data/story.json'] = tampered.files['data/story.json'] + b' '
    with pytest.raises(ValueError): contract.verify_bundle(tampered)
    with pytest.raises(ValueError): contract.build_export_bundle(fake_target, snapshot(spec={**SPEC, 'nodes': []}))


def test_zip_container_is_deterministic_and_read_back_is_safe(fake_target):
    bundle = contract.build_export_bundle(fake_target, snapshot())
    first = contract.package_export_zip(bundle); second = contract.package_export_zip(bundle)
    assert first['content'] == second['content'] and first['sha256'] == second['sha256']
    files = contract.read_zip_safely(first['content'], first['prefix'])
    assert set(files) == set(bundle.files)
    assert all(name.startswith(first['prefix']) and '..' not in name for name in [first['prefix']])
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as archive:
        archive.writestr(first['prefix'] + '../escape.txt', b'x')
    with pytest.raises(ValueError): contract.read_zip_safely(buffer.getvalue(), first['prefix'])


def test_compatibility_reports_media_loss_and_target_issues(fake_target):
    report = contract.compatibility_report(fake_target, snapshot(media_manifest=[{'asset_id': 'a1', 'missing': False, 'packaged': False, 'reason': 'x'}]))
    assert report['target_id'] == fake_target and 'MEDIA_REFERENCES_NOT_EMBEDDED_OR_PLAYED' in report['losses']
    bad = snapshot(); bad['spec'] = {**SPEC, 'nodes': [{**SPEC['nodes'][0], 'dialogue': 'unsupported'}, SPEC['nodes'][1]]}
    report = contract.compatibility_report(fake_target, bad)
    assert report['can_export'] is False and report['issues'][0]['code'] == 'FAKE_DIALOGUE_UNSUPPORTED'
    with pytest.raises(ValueError): contract.build_export_bundle(fake_target, bad)


# ---------------------------------------------------------------------------
# engine probing
# ---------------------------------------------------------------------------
def test_engine_probe_reports_absent_ready_unsupported_and_override(monkeypatch):
    engine = dict(FAKE_DESCRIPTOR['engine'])
    contract.clear_probe_cache()
    monkeypatch.delenv('FAKE_ENGINE_BIN', raising=False)
    monkeypatch.setattr(contract.shutil, 'which', lambda name: None)
    assert contract.probe_engine(engine)['status'] == 'NOT_INSTALLED'
    contract.clear_probe_cache()
    monkeypatch.setattr(contract.shutil, 'which', lambda name: 'C:/fake/fake-engine.exe')
    monkeypatch.setattr(contract, '_run_version', lambda path, args, timeout=5.0: 'FakeEngine 1.2.3')
    ready = contract.probe_engine(engine)
    assert ready['status'] == 'READY' and ready['detected'] is True and ready['version'] == '1.2.3' and ready['version_ok'] is True
    contract.clear_probe_cache()
    monkeypatch.setattr(contract, '_run_version', lambda path, args, timeout=5.0: 'FakeEngine 0.9.0')
    assert contract.probe_engine(engine)['status'] == 'UNSUPPORTED_VERSION'
    contract.clear_probe_cache()
    monkeypatch.setenv('FAKE_ENGINE_BIN', 'C:/override/fake-engine.exe')
    monkeypatch.setattr(contract, '_run_version', lambda path, args, timeout=5.0: 'FakeEngine 2.0.0')
    assert contract.probe_engine(engine)['executable'] == 'C:/override/fake-engine.exe'
    assert contract.probe_engine(None)['status'] == 'NOT_REQUIRED'
    contract.clear_probe_cache()


# ---------------------------------------------------------------------------
# service integration
# ---------------------------------------------------------------------------
@pytest.fixture
def interactive_env(revision_env):
    e = revision_env
    e.planning = PlanningService(e.store, e.novels, e.chapters)
    e.story_graph = StoryGraphService(e.store, e.novels, e.chapters)
    e.assets = AssetLibraryService(e.store.root)
    e.service = InteractiveStoryService(e.store, e.novels, e.chapters, e.planning, e.story_graph, e.assets)
    e.novels.upsert_character(e.nid, 'alice', {'name': 'Alice'})
    e.graph = e.planning.create_graph(e.nid, e.scope, 'author', {'title': 'Synthetic choice tree', 'links': {'chapter_ids': [e.cid], 'character_ids': ['alice']}})
    e.nodes = [e.graph['root_node_id']]
    for title in ['Harbour', 'Mountain']:
        e.nodes.append(e.planning.create_node(e.nid, e.scope, 'author', {'graph_id': e.graph['id'], 'parent_id': e.nodes[0], 'level': 'VOLUME', 'title': title})['id'])
    return e


def service_spec(e):
    return {'title': 'Synthetic interactive adaptation', 'graph_id': e.graph['id'], 'graph_version': 1, 'entry_node_id': e.nodes[0],
            'variables': [{'name': 'courage', 'type': 'int', 'initial': 0, 'minimum': 0, 'maximum': 3},
                          {'name': 'trusted', 'type': 'bool', 'initial': True}],
            'nodes': [
                {'node_id': e.nodes[0], 'node_version': 1, 'title': 'Gate', 'character_id': 'alice', 'dialogue': 'Choose',
                 'choices': [{'id': 'harbour', 'label': 'To harbour', 'target': e.nodes[1], 'condition': 'trusted', 'assignments': {'courage': 2}},
                             {'id': 'mountain', 'label': 'To mountain', 'target': e.nodes[2], 'condition': 'not (courage > 3)', 'assignments': {'trusted': False}}]},
                {'node_id': e.nodes[1], 'node_version': 1, 'title': 'Harbour', 'dialogue': 'Home', 'ending': 'Harbour ending'},
                {'node_id': e.nodes[2], 'node_version': 1, 'title': 'Mountain', 'dialogue': 'Beyond', 'ending': 'Mountain ending'}]}


def create_approved(e):
    row = e.service.create_story(e.nid, e.scope, 'author', {'spec': service_spec(e)})
    row = e.service.review(e.nid, e.scope, 'author', row['id'], {'expected_version': row['version'], 'action': 'submit'})
    receipt = e.service.review_preview(e.nid, e.scope, 'author', row['id'], {'expected_version': row['version']})
    return e.service.review(e.nid, e.scope, 'author', row['id'], {'expected_version': row['version'], 'action': 'approve', 'preview_digest': receipt['preview_digest']})


def test_service_export_targets_and_target_bundle(interactive_env, fake_target):
    e = interactive_env; row = create_approved(e)
    targets = e.service.export_targets(e.nid, e.scope, 'author', row['id'], {'expected_version': row['version']})
    assert targets['schema'] == contract.TARGETS_SCHEMA
    assert {'RENPY_8_5_4_TEXT_MENU_SUBSET', 'GODOT_4_DATA_ADAPTER', 'INKJS_2_3_2_TYPED_TEXT_SUBSET', fake_target} <= {item['target_id'] for item in targets['targets']}
    assert targets['can_export_any'] is True
    fake = next(item for item in targets['targets'] if item['target_id'] == fake_target)
    assert fake['export_ready'] is True and fake['engine_probe']['status'] in {'NOT_INSTALLED', 'READY', 'UNSUPPORTED_VERSION', 'PROBE_FAILED', 'NOT_REQUIRED'}
    assert targets['witness'] and targets['story']['spec_digest'] == contract.digest(row['spec'])
    value = {'expected_version': row['version']}
    preview = e.service.export_preview(e.nid, e.scope, 'author', row['id'], {**value, 'target_id': fake_target})
    assert preview['can_export'] is True and preview['target_id'] == fake_target
    assert preview['selected_target']['target_id'] == fake_target
    out = e.service.export(e.nid, e.scope, 'author', row['id'], {**value, 'target_id': fake_target, 'preview_digest': preview['preview_digest']})
    data = base64.b64decode(out['content_base64'])
    assert hashlib.sha256(data).hexdigest() == out['sha256'] and out['target_id'] == fake_target
    assert out['runtime_claim'] == 'NOT_RUN' and out['target_runtime'] == 'NOT_RUN'
    files = contract.read_zip_safely(data, 'interactive-fake-runtime-project-v1-' + row['id'] + '/')
    assert {'manifest.json', 'source-receipt.json', 'project.godot', 'data/story.json', 'runtime/play.gd'} == set(files)
    manifest = json.loads(files['manifest.json'])
    assert manifest['target_kind'] == 'RUNNABLE_PROJECT' and manifest['contract_version'] == contract.CONTRACT_VERSION
    assert manifest['runtime']['evidence']['TARGET_RUNTIME_EXECUTED'] == 'NOT_RUN'
    assert json.loads(files['data/story.json'])['story_id'] == row['id']
    assert manifest['story']['spec_digest'] == hashlib.sha256(json.dumps(row['spec'], ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()


def test_preview_digest_is_host_independent_and_unknown_target_rejected(interactive_env, fake_target, monkeypatch):
    e = interactive_env; row = create_approved(e); value = {'expected_version': row['version']}
    probes = []
    monkeypatch.setattr(story_service, 'probe_engine', lambda engine, **kw: probes.append(engine) or {'status': 'NOT_INSTALLED', 'detected': False, 'executable': None, 'version': None, 'version_ok': False, 'detail': 'x', 'declared': None})
    first = e.service.export_preview(e.nid, e.scope, 'author', row['id'], value)
    monkeypatch.setattr(story_service, 'probe_engine', lambda engine, **kw: {'status': 'READY', 'detected': True, 'executable': 'C:/engine', 'version': '9.9.9', 'version_ok': True, 'detail': 'y', 'declared': None})
    second = e.service.export_preview(e.nid, e.scope, 'author', row['id'], value)
    assert first['preview_digest'] == second['preview_digest']
    with pytest.raises(ValueError): e.service.export_preview(e.nid, e.scope, 'author', row['id'], {**value, 'target_id': 'NO_SUCH_TARGET'})


def test_incompatible_target_blocks_export_but_legacy_bundle_stays(interactive_env, fake_target, monkeypatch):
    e = interactive_env; row = create_approved(e); value = {'expected_version': row['version']}
    original = story_service.compatibility_report
    monkeypatch.setattr(story_service, 'compatibility_report', lambda target_id, snapshot: ({**original(target_id, snapshot), 'can_export': False} if target_id == fake_target else original(target_id, snapshot)))
    preview = e.service.export_preview(e.nid, e.scope, 'author', row['id'], {**value, 'target_id': fake_target})
    assert preview['can_export'] is False
    with pytest.raises(ValueError): e.service.export(e.nid, e.scope, 'author', row['id'], {**value, 'target_id': fake_target, 'preview_digest': preview['preview_digest']})
    monkeypatch.setattr(story_service, 'compatibility_report', original)
    legacy = e.service.export_preview(e.nid, e.scope, 'author', row['id'], value)
    assert legacy['can_export'] is True and 'target_id' not in legacy
    legacy_out = e.service.export(e.nid, e.scope, 'author', row['id'], {**value, 'preview_digest': legacy['preview_digest']})
    with zipfile.ZipFile(io.BytesIO(base64.b64decode(legacy_out['content_base64']))) as archive:
        names = archive.namelist()
        assert any(name.endswith('game/story.rpy') for name in names)
        assert any(name.endswith('ink/validation.json') for name in names)
        assert legacy_out['target_runtime'] == 'NOT_RUN'


def test_target_export_requires_approved_current_revision(interactive_env, fake_target):
    e = interactive_env
    row = e.service.create_story(e.nid, e.scope, 'author', {'spec': service_spec(e)})
    value = {'expected_version': row['version']}
    preview = e.service.export_preview(e.nid, e.scope, 'author', row['id'], {**value, 'target_id': fake_target})
    assert preview['can_export'] is False and preview['selected_target']['export_ready'] is False
    with pytest.raises(ValueError): e.service.export(e.nid, e.scope, 'author', row['id'], {**value, 'target_id': fake_target, 'preview_digest': preview['preview_digest']})


def test_legacy_targets_are_compatibility_only_and_never_standalone(interactive_env, fake_target):
    e = interactive_env; row = create_approved(e); value = {'expected_version': row['version']}
    assert contract.single_target_exportable('RENPY_8_5_4_TEXT_MENU_SUBSET') is False
    assert contract.single_target_exportable('GODOT_4_DATA_ADAPTER') is False
    assert contract.single_target_exportable(fake_target) is True
    targets = e.service.export_targets(e.nid, e.scope, 'author', row['id'], value)
    legacy = next(item for item in targets['targets'] if item['target_id'] == 'RENPY_8_5_4_TEXT_MENU_SUBSET')
    assert legacy['export_ready'] is False and legacy['single_export_ready'] is False
    assert legacy['compatibility']['capabilities']['save']['supported'] is False
    preview = e.service.export_preview(e.nid, e.scope, 'author', row['id'], {**value, 'target_id': 'RENPY_8_5_4_TEXT_MENU_SUBSET'})
    assert preview['can_export'] is False and preview['selected_target']['single_export_ready'] is False
    with pytest.raises(ValueError):
        e.service.export(e.nid, e.scope, 'author', row['id'], {**value, 'target_id': 'RENPY_8_5_4_TEXT_MENU_SUBSET', 'preview_digest': preview['preview_digest']})
