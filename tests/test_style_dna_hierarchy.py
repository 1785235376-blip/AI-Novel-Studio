"""DIF-09 original-owner persistence, hierarchy and lifetime fences; no inference."""
from copy import deepcopy
from pathlib import Path
import json
import pytest
from app.creative.service import CreativeService, document_digest
from app.experimental.store import ExperimentalStore
from app.experimental.style_analysis import StyleAnalysisService
from app.experimental.style_dna import StyleDNAService, EPOCH
from app.experimental.planning import digest
from app.experimental.common import snapshot, StaleSourceError
from app.services.creation_workbench_service import CreationWorkbenchService, WorkbenchRecordIn
from app.services.v1_capability_service import V1CapabilityService
from app.source_privacy import content_digest
from app.style_dna_contract import DIMENSIONS, StyleDNA, StyleTarget
from test_v2_independent_workspace import rig


def configure(e):
    e.creative = CreativeService(ExperimentalStore(e.root, e.backend, e.url), e.novels, e.chapters)
    e.creation = CreationWorkbenchService(V1CapabilityService(e.root, e.novels, e.chapters, e.assets), e.chapters, e.novels)
    e.dna = StyleDNAService(e.creative, e.creation)
    e.creation.style_dna_service = e.dna
    e.style = StyleAnalysisService(e.creative.store.store, e.novels, e.chapters, e.creation)
    return e

@pytest.fixture
def dna(rig):
    e = configure(rig)
    e.chapter = e.chapters.create(e.nid, {'title': 'Source', 'content': 'A lantern in the rain.'})
    e.chapter = e.chapters.get(e.chapter['id'])
    e.document = e.creative.create(e.nid, e.scope, e.actor, {
        'mode': 'STORYBOARD', 'title': 'Saved original board', 'source_chapter_ids': [e.chapter['id']],
        'scenes': [{'id': 's1', 'sequence': 1, 'heading': 'Rain', 'source_chapter_id': e.chapter['id']},
                   {'id': 's2', 'sequence': 2, 'heading': 'Dawn', 'source_chapter_id': e.chapter['id']}],
        'shots': [{'id': 'q1', 'number': 1, 'scene_id': 's1', 'color': 'Authored cyan'},
                  {'id': 'q2', 'number': 2, 'scene_id': 's1'}, {'id': 'q3', 'number': 3, 'scene_id': 's2'}],
        'visual_target': {'style': 'Original visual theme', 'color': 'Original red'}})
    return e


def target(e, level='SHOT', scene='s1', shot='q1'):
    if level == 'GLOBAL': return {'level': level}
    if level == 'CHAPTER':
        return {'level': level, 'chapter': {'id': e.chapter['id'], 'version': e.chapter['version'], 'digest': content_digest(e.chapter)}}
    return {'level': level, 'document': {'id': e.document['id'], 'version': e.document['version'], 'digest': document_digest(e.document)},
            'scene_id': scene, **({'shot_id': shot} if level == 'SHOT' else {})}


def spec(e):
    return {'global_rules': {d: 'Global ' + d for d in DIMENSIONS}, 'overrides': [
        {'target': target(e, 'CHAPTER'), 'rules': {'color': 'Chapter blue'}},
        {'target': target(e, 'SCENE'), 'rules': {'color': 'Scene green'}},
        {'target': target(e), 'rules': {'color': 'Shot amber'}}]}


def profile(e, value=None):
    return e.style.save_profile(e.nid, e.scope, e.actor, {'title': 'Multimodal', 'instructions': 'Concrete nouns.',
        'chapter_ids': [e.chapter['id']], 'style_dna': value if value is not None else spec(e)})


def approve(e, p):
    return e.creation.transition_record(e.nid, e.scope, e.actor, p['id'], 'approve', p['version'])


def resolve(e, p, t=None, **kwargs):
    return e.dna.resolve(e.nid, e.scope, p['id'], {'expected_version': p['version'],
        'expected_digest': digest(snapshot(p)), 'target': t or target(e)}, **kwargs)


def test_persisted_original_owner_restart_hierarchy_and_no_target_mutation(dna):
    e = dna; before = deepcopy(e.document); chapter_before = e.chapters.get(e.chapter['id'])
    p = approve(e, profile(e))
    assert e.creation.get_record(e.nid, e.scope, p['id'])['style_dna'] == p['style_dna']
    assert p[EPOCH] == e.creative.store.incarnation(e.nid)
    configure(e)
    result = resolve(e, p)
    assert result['effective']['color']['value'] == 'Shot amber'
    assert result['effective']['writing_tone']['value'] == 'Global writing_tone'
    assert [c['level'] for c in result['contributors']] == ['GLOBAL', 'CHAPTER', 'SCENE', 'SHOT']
    assert {c['kind'] for c in result['conflicts']} == {'EXPLICIT_OVERRIDE', 'AUTHORED_TEXT_DIFFERS'}
    assert not result['model_called'] and not result['target_mutated'] and not result['execution_ready']
    assert resolve(e, p, target(e, shot='q2'))['effective']['color']['value'] == 'Scene green'
    assert resolve(e, p, target(e, scene='s2', shot='q3'))['effective']['color']['value'] == 'Chapter blue'
    assert resolve(e, p, target(e, 'GLOBAL'))['effective']['color']['value'] == 'Global color'
    assert e.creative.get(e.nid, e.scope, e.document['id']) == before
    assert e.chapters.get(e.chapter['id']) == chapter_before


def test_legacy_omission_update_restore_and_new_profile_requirement(dna):
    e = dna
    legacy = e.style.save_profile(e.nid, e.scope, e.actor, {'title': 'Legacy', 'instructions': 'Plain.'})
    assert 'style_dna' not in legacy and EPOCH not in legacy
    legacy_bytes = deepcopy(legacy)
    with pytest.raises(FileNotFoundError): resolve(e, legacy)
    assert e.creation.get_record(e.nid, e.scope, legacy['id']) == legacy_bytes
    with pytest.raises(ValueError, match='NEW_PROFILE'):
        e.creation.save_record(e.nid, e.scope, e.actor, WorkbenchRecordIn(kind='STYLE', title='Upgrade', instructions='Plain.', style_dna=spec(e)), legacy['id'], 1)
    p = profile(e); original = deepcopy(p['style_dna'])
    updated = e.creation.save_record(e.nid, e.scope, e.actor, WorkbenchRecordIn(kind='STYLE', title='Rename only', instructions='Plain.'), p['id'], 1)
    assert updated['style_dna'] == original and updated[EPOCH] == p[EPOCH]
    restored = e.creation.transition_record(e.nid, e.scope, e.actor, p['id'], 'restore', 2, 1)
    assert restored['style_dna'] == original and restored[EPOCH] == p[EPOCH] and restored['status'] == 'DRAFT'
    with pytest.raises(ValueError, match='CLEAR'):
        e.creation.save_record(e.nid, e.scope, e.actor, WorkbenchRecordIn(kind='STYLE', title='Clear', instructions='Plain.', style_dna=None), p['id'], 3)
    with pytest.raises(ValueError, match='EXECUTION_ADOPTION'):
        e.creation.generation_inputs(e.nid, e.scope, approve(e, restored)['id'])


@pytest.mark.parametrize('change', ['chapter', 'document', 'missing_scene', 'mismatched_shot'])
def test_exact_sources_and_ancestry_fail_closed(dna, change):
    e = dna; p = approve(e, profile(e)); t = target(e)
    if change == 'chapter':
        e.chapters.save(e.chapter['id'], {'content': 'Changed', 'version': e.chapter['version']})
    elif change == 'document':
        with e.creative.store.transaction(e.nid, e.scope) as state:
            state['collections'][e.creative.COLLECTION][e.document['id']]['title'] = 'Unversioned change'
    elif change == 'missing_scene': t['scene_id'] = 'missing'
    else: t['scene_id'] = 's2'
    with pytest.raises((ValueError, FileNotFoundError)):
        resolve(e, p, t)


def test_delete_recreate_same_public_id_cannot_adopt_or_disclose_old_style(dna):
    e = dna; p = approve(e, profile(e)); old_chapter = deepcopy(e.chapter)
    e.novels.delete(e.nid)
    e.create_project(nid=e.nid)
    e.chapter = e.chapters.create(e.nid, {'title': old_chapter['title'], 'content': old_chapter['content']})
    e.chapter = e.chapters.get(e.chapter['id'])
    marker = e.root / 'novels' / e.nid / 'creative_project_v2.json'
    if e.backend == 'file': assert not marker.exists()
    for call in [lambda: e.creation.get_record(e.nid, e.scope, p['id']), lambda: resolve(e, p),
                 lambda: e.creation.transition_record(e.nid, e.scope, e.actor, p['id'], 'approve', 999),
                 lambda: e.creation.transition_record(e.nid, e.scope, e.actor, p['id'], 'restore', 999, 1),
                 lambda: e.creation.save_record(e.nid, e.scope, e.actor, WorkbenchRecordIn(kind='STYLE', title='Edit', instructions='Plain.'), p['id'], 999)]:
        with pytest.raises(FileNotFoundError): call()
    assert e.creation.list_records(e.nid, e.scope)['items'] == []
    if e.backend == 'file': assert not marker.exists()
    fresh = profile(e, {'global_rules': {'color': 'New owner'}})
    assert fresh[EPOCH] != p[EPOCH]
    with pytest.raises(FileNotFoundError): resolve(e, p)
    visible = e.creation.list_records(e.nid, e.scope)['items']
    assert [r['id'] for r in visible] == [fresh['id']]
    assert visible[0]['style_dna_resolution']['stale'] is False


def test_disabled_injection_generated_path_and_reauthorization(dna):
    e = dna; p = approve(e, profile(e))
    e.creation.style_dna_service = None
    with pytest.raises(FileNotFoundError): e.style.resolve_style(e.nid, e.scope, p['id'], {})
    with pytest.raises(FileNotFoundError): e.creation.get_record(e.nid, e.scope, p['id'])
    e.creation.style_dna_service = e.dna
    with pytest.raises(ValueError, match='AUTHORED_CREATE'):
        e.creation.save_generated_record(e.nid, e.scope, e.actor, WorkbenchRecordIn(kind='STYLE', title='Generated', instructions='Plain.', style_dna=spec(e)), {})
    def deny(): raise PermissionError('revoked')
    with pytest.raises(PermissionError): resolve(e, p, reauthorize=deny)
    e.dna.require_enabled = deny
    with pytest.raises(PermissionError): resolve(e, p)


@pytest.mark.parametrize('invalid', ['duplicate', 'unknown_dimension', 'blank', 'forged_epoch', 'wrong_shape'])
def test_closed_contract(dna, invalid):
    e = dna; value = spec(e)
    if invalid == 'duplicate': value['overrides'].append(deepcopy(value['overrides'][0]))
    elif invalid == 'unknown_dimension': value['global_rules']['unsupported'] = 'No'
    elif invalid == 'blank': value['global_rules']['color'] = '  '
    elif invalid == 'forged_epoch': value[EPOCH] = 'file:forged'
    else: value['overrides'][0]['target']['scene_id'] = 'unowned'
    with pytest.raises(ValueError): StyleDNA.model_validate(value)


def test_explicit_global_create_can_initialize_but_unbound_read_cannot(rig):
    e = configure(rig)
    marker = e.root / 'novels' / e.nid / 'creative_project_v2.json'
    legacy = e.creation.save_record(e.nid, e.scope, e.actor, WorkbenchRecordIn(kind='STYLE', title='Legacy', instructions='Plain.'))
    if e.backend == 'file': assert not marker.exists()
    with pytest.raises(FileNotFoundError): resolve(e, legacy, {'level': 'GLOBAL'})
    if e.backend == 'file': assert not marker.exists()
    fresh = e.creation.save_record(e.nid, e.scope, e.actor, WorkbenchRecordIn(kind='STYLE', title='Authored', instructions='Plain.', style_dna={'global_rules': {'color': 'Amber'}}))
    assert fresh[EPOCH] == e.creative.store.incarnation(e.nid)
    approved = approve(e, fresh)
    assert resolve(e, approved, {'level': 'GLOBAL'})['effective']['color']['value'] == 'Amber'
    # Legacy row was neither stamped nor rewritten by creating the new profile.
    assert e.creation.get_record(e.nid, e.scope, legacy['id']) == legacy


def test_revoked_save_and_transition_are_not_committed(dna):
    e = dna; p = profile(e)
    before = e.creation.store._path('creation_records').read_bytes()
    calls = []
    def deny_late():
        calls.append(True)
        if len(calls) == 2: raise PermissionError('revoked before commit')
    body = WorkbenchRecordIn(kind='STYLE', title='Do not commit', instructions='Plain.')
    with pytest.raises(PermissionError):
        e.creation.save_record(e.nid, e.scope, e.actor, body, p['id'], p['version'], reauthorize=deny_late)
    assert e.creation.store._path('creation_records').read_bytes() == before
    calls.clear()
    with pytest.raises(PermissionError):
        e.creation.transition_record(e.nid, e.scope, e.actor, p['id'], 'approve', p['version'], reauthorize=deny_late)
    assert e.creation.store._path('creation_records').read_bytes() == before


def test_independent_document_has_no_inferred_chapter_and_unknown_dimensions(dna):
    e = dna
    e.document = e.creative.create(e.nid, e.scope, e.actor, {'mode': 'STORYBOARD', 'title': 'Independent',
        'source_independent': True, 'scenes': [{'id': 's1', 'sequence': 1, 'heading': 'Independent scene'}],
        'shots': [{'id': 'q1', 'number': 1, 'scene_id': 's1'}]})
    p = approve(e, profile(e, {'global_rules': {'color': 'Amber'}, 'overrides': [
        {'target': target(e, 'CHAPTER'), 'rules': {'color': 'Chapter must not apply'}}]}))
    result = resolve(e, p)
    assert result['effective']['color']['value'] == 'Amber'
    assert result['uncovered_dimensions'] == [d for d in DIMENSIONS if d != 'color']
    assert [c['level'] for c in result['contributors']] == ['GLOBAL']
