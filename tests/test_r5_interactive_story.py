"""B07 typed parser, real File/opted-in PG, bounded preview and neutral/target export."""
import ast
import base64
from copy import deepcopy
import hashlib
import io
import json
import threading
import zipfile

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from test_r4_revision_intelligence import revision_env
from app.experimental.interactive_story import InteractiveStoryService, StorySpec, Variable, Choice, analyze, play, parse_condition, renpy_text, renpy_export
from app.experimental.common import StaleSourceError
from app.experimental.planning import PlanningService
from app.experimental.story_graph import StoryGraphService
from app.services.asset_library_service import AssetLibraryService
from app.services.v1_capability_service import CapabilityVersionConflict


@pytest.fixture
def interactive_env(revision_env):
    e = revision_env
    e.planning = PlanningService(e.store, e.novels, e.chapters)
    e.story_graph = StoryGraphService(e.store, e.novels, e.chapters)
    e.assets = AssetLibraryService(e.store.root)
    e.service = InteractiveStoryService(e.store, e.novels, e.chapters, e.planning, e.story_graph, e.assets)
    e.novels.upsert_character(e.nid, 'alice', {'name': 'Alice "[literal]" {text} 〖ruby'})
    e.graph = e.planning.create_graph(e.nid, e.scope, 'author', {'title': 'Synthetic choice tree', 'links': {'chapter_ids': [e.cid], 'character_ids': ['alice']}})
    e.nodes = [e.graph['root_node_id']]
    for title in ['Harbour', 'Mountain']:
        e.nodes.append(e.planning.create_node(e.nid, e.scope, 'author', {'graph_id': e.graph['id'], 'parent_id': e.nodes[0], 'level': 'VOLUME', 'title': title})['id'])
    return e


def spec(e):
    return StorySpec.model_validate({'title': 'Synthetic interactive adaptation', 'graph_id': e.graph['id'], 'graph_version': 1, 'entry_node_id': e.nodes[0],
        'variables': [{'name': 'courage', 'type': 'int', 'initial': 0, 'minimum': 0, 'maximum': 3}, {'name': 'trusted', 'type': 'bool', 'initial': True}],
        'nodes': [
            {'node_id': e.nodes[0], 'node_version': 1, 'title': 'Gate', 'character_id': 'alice', 'dialogue': 'Choose "[safe]" {safe} 〖safe🙂é\nnot code', 'choices': [
                {'id': 'harbour', 'label': 'To harbour', 'target': e.nodes[1], 'condition': 'trusted and courage >= 0', 'assignments': {'courage': 2}},
                {'id': 'mountain', 'label': 'To mountain', 'target': e.nodes[2], 'condition': 'not (courage > 3)', 'assignments': {'trusted': False}}]},
            {'node_id': e.nodes[1], 'node_version': 1, 'title': 'Harbour', 'dialogue': 'Home🙂', 'ending': 'Harbour ending'},
            {'node_id': e.nodes[2], 'node_version': 1, 'title': 'Mountain', 'dialogue': 'Beyond the ridge', 'ending': 'Mountain ending'},
        ]}).model_dump()


def create(e, value=None): return e.service.create_story(e.nid, e.scope, 'author', {'spec': value or spec(e)})
def review(e, row, action, **kw): return e.service.review(e.nid, e.scope, 'author', row['id'], {'expected_version': row['version'], 'action': action, **kw})
def approve(e, row):
    row = review(e, row, 'submit'); receipt = e.service.review_preview(e.nid, e.scope, 'author', row['id'], {'expected_version': row['version']})
    return review(e, row, 'approve', preview_digest=receipt['preview_digest'])


def test_real_storage_two_endings_and_source_safe_restart(interactive_env):
    e = interactive_env; before = deepcopy((e.chapters.get(e.cid), e.planning.graph(e.nid, e.scope, e.graph['id']), e.novels.data_set(e.nid, 'characters')))
    row = create(e); assert row['privacy_level'] == 'LOCAL_ONLY' and row['analysis']['can_review']
    for path, ending in [(['harbour'], 'Harbour ending'), (['mountain'], 'Mountain ending')]:
        result = e.service.preview(e.nid, e.scope, 'author', row['id'], {'expected_version': 1, 'choices': path})
        assert result['status'] == 'ENDING' and result['node']['ending'] == ending
    assert e.service.preview(e.nid, e.scope, 'author', row['id'], {'expected_version': 1})['character_name'].startswith('Alice')
    assert row['analysis']['endings'][0]['choices'] == ['harbour']
    restarted = InteractiveStoryService(e.store, e.novels, e.chapters, e.planning, e.story_graph, e.assets)
    assert restarted.story(e.nid, e.scope, 'author', row['id'])['spec'] == row['spec']
    assert before == (e.chapters.get(e.cid), e.planning.graph(e.nid, e.scope, e.graph['id']), e.novels.data_set(e.nid, 'characters'))
    assert not restarted.stories(e.nid, e.scope, 'other')['items']
    with pytest.raises(FileNotFoundError): restarted.story(e.nid, e.scope, 'other', row['id'])
    with pytest.raises(FileNotFoundError): restarted.story(e.nid, {**e.scope, 'branch_id': 'another'}, 'author', row['id'])


@pytest.mark.parametrize('expression', ['__import__("os")', 'a.x', 'a[0]', 'lambda: True', '(x := 1)', '[x for x in a]', '2 ** 9999', '1 + 2', '"yes"', 'float("nan")', 'True if x else False', 'x in y', '10001', '1.2', '[]', '{1:2}'])
def test_restricted_parser_rejects_code_without_execution(expression):
    with pytest.raises(ValueError): parse_condition(expression)


def test_parser_and_scalar_type_edges():
    assert parse_condition('not (trusted and courage >= -2)')['op'] == 'not'
    with pytest.raises(ValidationError): Variable(name='x', type='int', initial=True)
    with pytest.raises(ValidationError): Variable(name='x', type='bool', initial=1)
    with pytest.raises(ValidationError): Variable(name='x', type='int', initial=10001)
    with pytest.raises(ValidationError): Choice(id='x', label='x', target='n', assignments={'x': 'exec'})
    with pytest.raises(ValueError): parse_condition('not ' * 20 + 'True')
    with pytest.raises(ValidationError): StorySpec.model_validate({'title': 'x', 'nodes': [], 'graph_id': 'g', 'graph_version': True, 'entry_node_id': 'n'})


@pytest.mark.parametrize('kind,code', [('undefined', 'UNDEFINED_VARIABLE'), ('type', 'CONDITION_TYPE_MISMATCH'), ('bound', 'ASSIGNMENT_OUT_OF_BOUNDS'), ('assignment', 'ASSIGNMENT_TYPE_MISMATCH'), ('target', 'UNDEFINED_TARGET'), ('dead', 'CONDITIONAL_NO_EXIT')])
def test_path_analysis_detects_invalid_and_undefined(interactive_env, kind, code):
    s = spec(interactive_env); c = s['nodes'][0]['choices'][0]
    if kind == 'undefined': c['condition'] = 'missing == 1'
    if kind == 'type': c['condition'] = 'trusted > False'
    if kind == 'bound': c['assignments'] = {'courage': 4}
    if kind == 'assignment': c['assignments'] = {'courage': True}
    if kind == 'target': c['target'] = 'missing-node'
    if kind == 'dead':
        for c in s['nodes'][0]['choices']: c['condition'] = 'False'
    result = analyze(s); assert code in {r['code'] for r in result['issues']} and not result['can_review']


def test_unreachable_cycle_no_exit_and_step_cap_are_explicit(interactive_env):
    s = spec(interactive_env); s['max_steps'] = 3
    s['nodes'][0]['choices'][1]['target'] = s['entry_node_id']
    result = analyze(s); codes = {r['code'] for r in result['warnings']}
    assert {'CYCLE_STEP_CAP_REQUIRED', 'UNREACHABLE_NODE'} <= codes
    assert play(s, ['mountain'] * 3)['status'] == 'STEP_CAP_REACHED'
    with pytest.raises(ValueError, match='STEP_CAP'): play(s, ['mountain'] * 4)
    s['nodes'][0]['choices'] = [s['nodes'][0]['choices'][1]]
    assert 'NO_ENDING_PATH' in {r['code'] for r in analyze(s)['issues']}
    s['nodes'][0]['choices'] = []
    assert 'NO_EXIT' in {r['code'] for r in analyze(s)['issues']}


def test_condition_blocks_forged_choice_and_ending_continuation(interactive_env):
    s = spec(interactive_env); s['nodes'][0]['choices'][0]['condition'] = 'False'
    assert not play(s, [])['choices'][0]['enabled']
    with pytest.raises(ValueError, match='CHOICE_UNAVAILABLE'): play(s, ['harbour'])
    with pytest.raises(ValueError, match='CHOICE_UNAVAILABLE'): play(s, ['mountain', 'mountain'])


@pytest.mark.parametrize('drift', ['chapter', 'privacy', 'character', 'plan', 'graph', 'deleted'])
def test_source_drift_withholds_all_derived_content_and_blocks_approval(interactive_env, drift):
    e = interactive_env; row = review(e, create(e), 'submit')
    receipt = e.service.review_preview(e.nid, e.scope, 'author', row['id'], {'expected_version': row['version']})
    if drift == 'chapter': e.chapters.save(e.cid, {'version': e.chapter['version'], 'content': 'changed'})
    elif drift == 'privacy':
        from app.source_privacy import content_digest, review_source_privacy
        review_source_privacy(e.chapter, None, 'author', 'CLOUD_ALLOWED', e.chapter['version'], content_digest(e.chapter), e.store.root)
    elif drift == 'character': e.novels.upsert_character(e.nid, 'alice', {'name': 'Different'})
    elif drift == 'plan': e.planning.edit_node(e.nid, e.scope, 'author', e.nodes[1], {'title': 'Changed', 'expected_version': 1})
    elif drift == 'graph': e.planning.transition_graph(e.nid, e.scope, 'author', e.graph['id'], 'archive', 1)
    else: e.chapters.delete(e.cid)
    view = e.service.story(e.nid, e.scope, 'author', row['id'])
    assert view['stale'] and view['content_withheld'] and 'spec' not in view and 'analysis' not in view
    assert 'Choose' not in json.dumps(e.service.stories(e.nid, e.scope, 'author'))
    with pytest.raises((StaleSourceError, FileNotFoundError)): review(e, row, 'approve', preview_digest=receipt['preview_digest'])
    archived = review(e, row, 'archive'); assert archived['status'] == 'ARCHIVED'


def test_final_reauthorization_rolls_back_and_exact_review_invalidates(interactive_env):
    e = interactive_env; row = review(e, create(e), 'submit'); before = e.store.read(e.nid, e.scope)
    receipt = e.service.review_preview(e.nid, e.scope, 'author', row['id'], {'expected_version': row['version']}); calls = []
    def revoke():
        calls.append(1)
        if len(calls) >= 3: raise HTTPException(403, {'code': 'REVOKED'})
    with pytest.raises(HTTPException):
        e.service.review(e.nid, e.scope, 'author', row['id'], {'expected_version': row['version'], 'action': 'approve', 'preview_digest': receipt['preview_digest']}, reauthorize=revoke)
    assert e.store.read(e.nid, e.scope) == before
    changed = e.service.save(e.nid, e.scope, 'author', row['id'], {'expected_version': row['version'], 'spec': spec(e)})
    with pytest.raises(CapabilityVersionConflict) as error: review(e, row, 'approve', preview_digest=receipt['preview_digest'])
    assert set(error.value.current) == {'id', 'version', 'status'}
    changed = review(e, changed, 'submit')
    with pytest.raises(StaleSourceError): review(e, changed, 'approve', preview_digest=receipt['preview_digest'])


def test_concurrent_cas_has_one_winner_and_archive_restore_preserves_draft(interactive_env):
    e = interactive_env; row = create(e); barrier = threading.Barrier(3); outcomes = []
    def write():
        barrier.wait()
        try: e.service.save(e.nid, e.scope, 'author', row['id'], {'expected_version': 1, 'spec': spec(e)}); outcomes.append('saved')
        except CapabilityVersionConflict: outcomes.append('conflict')
    threads = [threading.Thread(target=write) for _ in range(2)]
    for thread in threads: thread.start()
    barrier.wait()
    for thread in threads: thread.join(10); assert not thread.is_alive()
    assert sorted(outcomes) == ['conflict', 'saved']
    row = e.service.story(e.nid, e.scope, 'author', row['id']); row = review(e, row, 'archive')
    with pytest.raises(ValueError): e.service.preview(e.nid, e.scope, 'author', row['id'], {'expected_version': row['version']})
    restored = review(e, row, 'restore'); assert restored['spec'] == spec(e) and restored['status'] == 'DRAFT'


def test_reviewed_independent_bundle_neutral_schema_safe_renpy_and_checksums(interactive_env):
    e = interactive_env; row = approve(e, create(e)); value = {'expected_version': row['version']}
    preview = e.service.export_preview(e.nid, e.scope, 'author', row['id'], value)
    assert preview['can_export'] and preview['target_runtime'] == 'NOT_RUN'
    out = e.service.export(e.nid, e.scope, 'author', row['id'], {**value, 'preview_digest': preview['preview_digest']})
    data = base64.b64decode(out['content_base64']); assert hashlib.sha256(data).hexdigest() == out['sha256']
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        prefix = f"interactive-story-{row['id']}/"; names = archive.namelist()
        assert all(name.startswith(prefix) and '..' not in name and not name.startswith('/') for name in names)
        neutral = json.loads(archive.read(prefix + 'story.json')); assert neutral['schema'] == 'ai-novel-interactive-story/1'
        assert neutral['spec']['nodes'][0]['node_id'] == e.nodes[0]
        assert neutral['spec']['nodes'][0]['choices'][0]['condition_tree']['op'] == 'and'
        target = archive.read(prefix + 'game/story.rpy').decode(); assert 'label start:' in target
        assert 'ans_steps >= 32' in target and 'jump ans_node_1' in target and 'jump ans_node_2' in target
        assert '[[safe]' in target and '{{safe}' in target and '〖〖safe' in target
        assert 'import ' not in target and 'eval(' not in target and 'exec(' not in target
        checksums = json.loads(archive.read(prefix + 'checksums.json'))
        for name, sha in checksums.items(): assert hashlib.sha256(archive.read(prefix + name)).hexdigest() == sha
    reopened = review(e, row, 'reopen')
    with pytest.raises(CapabilityVersionConflict): e.service.export(e.nid, e.scope, 'author', row['id'], {**value, 'preview_digest': preview['preview_digest']})
    assert not e.service.export_preview(e.nid, e.scope, 'author', row['id'], {'expected_version': reopened['version']})['can_export']


def test_target_escaping_all_user_strings_are_one_literal():
    source = '"\nlabel injected:\n    $ dangerous()\\ [danger()] {a=https://bad} 〖ruby %'
    escaped = renpy_text(source)
    literal = ast.literal_eval(escaped)
    assert '\nlabel injected:' in literal and '[[danger()]' in literal and '{{a=' in literal
    assert '\n' not in escaped and '\\n' in escaped


def test_media_manifest_never_promotes_private_assets_or_executes_missing_files(interactive_env):
    e = interactive_env
    asset = e.assets.create(e.nid, 'bg.png', base64.b64encode(b'synthetic reference only').decode(), 'image/png', 'image')
    s = spec(e); s['nodes'][0]['background_asset_id'] = asset['id']; row = approve(e, create(e, s))
    p = e.service.export_preview(e.nid, e.scope, 'author', row['id'], {'expected_version': row['version']})
    assert p['media_manifest'][0]['missing'] is False and not p['media_manifest'][0]['packaged']
    e.assets._bin_path(asset['id']).unlink()
    p2 = e.service.export_preview(e.nid, e.scope, 'author', row['id'], {'expected_version': row['version']})
    assert p2['media_manifest'][0]['missing'] and p2['preview_digest'] != p['preview_digest']
    with pytest.raises(StaleSourceError): e.service.export(e.nid, e.scope, 'author', row['id'], {'expected_version': row['version'], 'preview_digest': p['preview_digest']})
    private = e.assets.create(e.nid, 'private.png', base64.b64encode(b'private').decode(), 'image/png', 'image', owner_actor_id='author')
    s['nodes'][0]['background_asset_id'] = private['id']
    with pytest.raises(FileNotFoundError): create(e, s)
    assert private['id'] not in {a['id'] for a in e.service.catalog(e.nid, e.scope)['assets']}


def test_story_graph_ids_are_reused_and_revocation_invalidates(interactive_env):
    e = interactive_env
    e.novels.upsert_location(e.nid, 'harbour', {'name': 'Harbour'})
    record = e.story_graph.create_record(e.nid, e.scope, 'author', {'kind': 'STORY_RELATION', 'title': 'At the harbour', 'chapter_id': e.cid,
        'data': {'subject': {'kind': 'CHARACTER', 'id': 'alice'}, 'object': {'kind': 'LOCATION', 'id': 'harbour'}, 'relation': 'LOCATED_AT', 'layer': 'WORLD_FACT', 'statement': 'Alice reaches the harbour'}})
    s = spec(e); s['graph_record_ids'] = [record['id']]
    with pytest.raises(ValueError): create(e, s)
    record = e.story_graph.review(e.nid, e.scope, 'author', record['id'], 'approve', record['version'])
    row = create(e, s); assert row['spec']['graph_record_ids'] == [record['id']]
    e.story_graph.review(e.nid, e.scope, 'author', record['id'], 'archive', record['version'])
    assert e.service.story(e.nid, e.scope, 'author', row['id'])['stale']


def test_current_planning_link_entities_are_fenced_even_if_not_dialogue_characters(interactive_env):
    e = interactive_env; s = spec(e); s['nodes'][0]['character_id'] = None; row = create(e, s)
    e.novels.upsert_character(e.nid, 'alice', {'name': 'Changed plan entity'})
    assert e.service.story(e.nid, e.scope, 'author', row['id'])['stale']


def test_state_explosion_is_bounded_and_cannot_approve_incomplete_analysis():
    variables = [{'name': f'v{i}', 'type': 'bool', 'initial': False} for i in range(13)]
    nodes = []
    for i in range(13):
        choices = [{'id': 'yes', 'label': 'Yes', 'target': f'n{(i + 1) % 13}', 'assignments': {f'v{i}': True}},
                   {'id': 'no', 'label': 'No', 'target': f'n{(i + 1) % 13}', 'assignments': {f'v{i}': False}},
                   {'id': 'end', 'label': 'End', 'target': 'ending'}]
        nodes.append({'node_id': f'n{i}', 'node_version': 1, 'title': f'Node {i}', 'choices': choices})
    nodes.append({'node_id': 'ending', 'node_version': 1, 'title': 'End', 'ending': 'Done'})
    s = StorySpec.model_validate({'title': 'Bounded', 'graph_id': 'g', 'graph_version': 1, 'entry_node_id': 'n0', 'nodes': nodes, 'variables': variables, 'max_steps': 128}).model_dump()
    result = analyze(s)
    assert result['states_checked'] == 4096 and result['state_limit_reached'] and not result['analysis_complete'] and not result['can_review']


def test_server_playback_detects_same_version_asset_and_metadata_drift(interactive_env):
    e = interactive_env; asset = e.assets.create(e.nid, 'music.wav', base64.b64encode(b'not executed').decode(), 'audio/wav', 'audio')
    s = spec(e); s['nodes'][0]['music_asset_id'] = asset['id']; row = create(e, s)
    e.assets.delete(asset['id'])
    assert e.service.story(e.nid, e.scope, 'author', row['id'])['stale']
    with pytest.raises(FileNotFoundError): e.service.preview(e.nid, e.scope, 'author', row['id'], {'expected_version': row['version']})


def test_renpy_generated_subset_has_resolved_labels_and_only_typed_expressions(interactive_env):
    script = renpy_export(spec(interactive_env), {'alice': 'Name [bad()] {a=jump:evil}'})
    labels = {line.split()[1][:-1] for line in script.splitlines() if line.startswith('label ')}
    for line in script.splitlines():
        text = line.strip()
        if text.startswith('jump '): assert text.split()[1] in labels
        if text.startswith('$ '):
            tree = ast.parse(text[2:], mode='exec'); assert len(tree.body) == 1
            assert isinstance(tree.body[0], (ast.Assign, ast.AugAssign))
            assert all(not isinstance(n, (ast.Call, ast.Attribute, ast.Subscript)) for n in ast.walk(tree))
        if text.startswith('if '):
            tree = ast.parse(text[3:-1], mode='eval'); assert not any(isinstance(n, (ast.Call, ast.Attribute, ast.Subscript)) for n in ast.walk(tree))
    assert {'start', 'ans_node_0', 'ans_node_1', 'ans_node_2'} == labels


def test_explicit_source_rebind_preserves_user_choices_but_revokes_approval(interactive_env):
    e = interactive_env; row = approve(e, create(e)); previous = deepcopy(row['spec'])
    e.chapters.save(e.cid, {'version': e.chapter['version'], 'content': 'Changed original'})
    assert e.service.story(e.nid, e.scope, 'author', row['id'])['stale']
    p = e.service.refresh_preview(e.nid, e.scope, 'author', row['id'], {'expected_version': row['version']})
    assert p['changed_source_count'] == 1 and p['retained_nodes'] == 3
    restored = e.service.refresh(e.nid, e.scope, 'author', row['id'], {'expected_version': row['version'], 'preview_digest': p['preview_digest']})
    assert restored['status'] == 'DRAFT' and not restored['stale'] and restored['spec'] == previous
    assert not e.service.export_preview(e.nid, e.scope, 'author', row['id'], {'expected_version': restored['version']})['can_export']


def test_rebind_exact_source_receipt_rejects_further_drift_and_deleted_refs(interactive_env):
    e = interactive_env; row = create(e)
    p = e.service.refresh_preview(e.nid, e.scope, 'author', row['id'], {'expected_version': row['version']})
    e.chapters.save(e.cid, {'version': e.chapter['version'], 'content': 'Changed after preview'})
    with pytest.raises(StaleSourceError): e.service.refresh(e.nid, e.scope, 'author', row['id'], {'expected_version': row['version'], 'preview_digest': p['preview_digest']})
    e.chapters.delete(e.cid)
    with pytest.raises(FileNotFoundError): e.service.refresh_preview(e.nid, e.scope, 'author', row['id'], {'expected_version': row['version']})


def test_asset_origin_feature_revocation_withholds_adaptation(interactive_env, monkeypatch):
    from app.experimental.flags import FLAGS
    e = interactive_env; monkeypatch.setenv('EXPERIMENTAL_FEATURES', ','.join(FLAGS))
    asset = e.assets.create(e.nid, 'approved-origin.png', base64.b64encode(b'origin-bound').decode(), 'image/png', 'image', required_features=('cover_storyboard_generation',))
    s = spec(e); s['nodes'][0]['background_asset_id'] = asset['id']; row = create(e, s)
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', ','.join(f for f in FLAGS if f != 'cover_storyboard_generation'))
    assert e.service.story(e.nid, e.scope, 'author', row['id'])['stale']
    with pytest.raises(FileNotFoundError): e.service.refresh_preview(e.nid, e.scope, 'author', row['id'], {'expected_version': row['version']})


def test_delayed_preview_cannot_return_after_concurrent_adaptation_save(interactive_env, monkeypatch):
    import app.experimental.interactive_story as module
    e = interactive_env; row = create(e); original = module.play
    def delayed(specification, path):
        result = original(specification, path)
        e.service.save(e.nid, e.scope, 'author', row['id'], {'expected_version': row['version'], 'spec': spec(e)})
        return result
    monkeypatch.setattr(module, 'play', delayed)
    with pytest.raises(CapabilityVersionConflict): e.service.preview(e.nid, e.scope, 'author', row['id'], {'expected_version': row['version']})
