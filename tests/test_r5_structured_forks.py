"""B09 original structured authorities: selected graph mapping, diff3 and recovery."""
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from app.experimental.common import StaleSourceError
from app.experimental.planning import digest
from app.experimental.structured_forks import StructuredForksService, split
from test_r5_project_forks import env, confirmation


@pytest.fixture
def structured(env):
    e = env; e.structured = StructuredForksService(e.store, e.novels, e.chapters, sources=e.service.sources, assets=e.assets)
    e.novels.upsert_location(e.nid, 'harbor', {'name': 'Synthetic harbor', 'privacy_level': 'CLOUD_ALLOWED'})
    for rid in ['hero', 'friend']:
        e.novels.upsert_character(e.nid, rid, {'name': rid, 'current_location': 'harbor', 'privacy_level': 'CLOUD_ALLOWED'})
    e.novels.upsert_relationship(e.nid, 'allies', {'source_character_id': 'hero', 'target_character_id': 'friend', 'relationship_type': 'ally',
        'status': 'ACTIVE', 'description': 'Original connection', 'certainty': 'CONFIRMED', 'valid_from_event_id': '', 'valid_to_event_id': '', 'privacy_level': 'CLOUD_ALLOWED'})
    yield e
    for row in e.store.read(e.nid, e.ctx.scope)['collections'].get(e.structured.FORKS, {}).values():
        try: e.novels.delete(row['target_id'])
        except FileNotFoundError: pass


def preflight(e, keys=None):
    selected = e.structured.catalog(e.ctx)['records']
    if keys is not None: selected = [r for r in selected if r['key'] in keys]
    return e.structured.preflight(e.ctx, {'title': 'Synthetic structure fork', 'records': [{k: r[k] for k in ('kind', 'record_id', 'source_digest')} |
        {'license': 'Synthetic author-owned', 'allow_local_copy': True} for r in selected]})


def create(e, keys=None):
    pre = preflight(e, keys); return e.structured.create_fork(e.ctx, pre['id'], confirmation(pre))


def read(e, key, nid=None):
    return e.structured._read(replace(e.ctx, novel_id=nid, scope={'mode': 'local', 'novel_id': nid}) if nid else e.ctx, key)


def change(e, key, values, nid=None):
    kind, rid = split(key); row = read(e, key, nid); payload = {k: v for k, v in row.items() if k not in {'id', 'privacy_status'}} | values
    return e.novels.compare_and_swap_record(nid or e.nid, kind, rid, payload, digest(row))


def compare(e, row, choices=None):
    return e.structured.compare(e.ctx, row['id'], {'expected_version': row['version'], 'choices': choices or {}})


def apply(e, row, plan, choices=None, **kwargs):
    return e.structured.apply(e.ctx, row['id'], {'expected_version': row['version'], 'preview_digest': plan['preview_digest'], 'choices': choices or {}, 'confirmed': True}, **kwargs)


def test_structured_fork_maps_references_original_owners_and_never_copies_cloud_grants(structured):
    e = structured; originals = {r['key']: read(e, r['key']) for r in e.structured.catalog(e.ctx)['records']}
    row = create(e); assert row['record_count'] == 4
    assert len(e.chapters.list(row['target_id'])) == 0
    hero = read(e, row['id_map']['characters:hero'], row['target_id'])
    relationship = read(e, row['id_map']['relationships:allies'], row['target_id'])
    assert hero['current_location'] == split(row['id_map']['locations:harbor'])[1]
    assert relationship['source_character_id'] == hero['id']
    assert all(read(e, k, row['target_id'])['privacy_level'] == 'LOCAL_ONLY' for k in row['id_map'].values())
    assert all(read(e, k) == before for k, before in originals.items())
    assert all(p['source_digest'] == digest(originals[k]) and p['license'] for k, p in row['provenance'].items())
    preview = compare(e, row); assert preview['unresolved'] == 0 and preview['write_count'] == 0


def test_missing_mapping_unknown_fields_events_and_stale_selection_fail_before_creation(structured):
    e = structured
    with pytest.raises(ValueError, match='UNMAPPED'): preflight(e, ['characters:hero'])
    catalog = e.structured.catalog(e.ctx); item = next(r for r in catalog['records'] if r['key'] == 'locations:harbor')
    change(e, item['key'], {'name': 'Changed location'})
    with pytest.raises(StaleSourceError): e.structured.preflight(e.ctx, {'title': 'Stale', 'records': [{k: item[k] for k in ('kind','record_id','source_digest')} | {'license':'Mine','allow_local_copy':True}]})
    change(e, 'relationships:allies', {'valid_from_event_id': 'event-not-selected'})
    assert not next(r for r in e.structured.catalog(e.ctx)['records'] if r['key'] == 'relationships:allies')['supported']
    with pytest.raises(ValueError, match='EVENT_REFERENCE'): preflight(e)
    assert not e.store.read(e.nid, e.ctx.scope)['collections'].get(e.structured.FORKS)


def test_per_field_three_way_rename_conflict_disjoint_merge_checkpoint_and_restore(structured):
    e = structured; row = create(e); target = row['id_map']['characters:hero']
    change(e, 'characters:hero', {'name': 'Original rename', 'goal': 'Original goal'})
    change(e, target, {'name': 'Fork rename', 'personality': 'Fork personality'}, row['target_id'])
    plan = compare(e, row); conflict = next(c for r in plan['records'] for c in r['changes'] if c['kind'] == 'CONFLICT')
    assert conflict['reason'] == 'RENAME' and plan['unresolved'] == 1
    with pytest.raises(ValueError, match='UNRESOLVED'): apply(e, row, plan)
    choices = {conflict['id']: 'FORK'}; plan = compare(e, row, choices); before = read(e, 'characters:hero')
    done = apply(e, row, plan, choices); actual = read(e, 'characters:hero')
    assert actual['name'] == 'Fork rename' and actual['goal'] == 'Original goal' and actual['personality'] == 'Fork personality'
    assert actual['privacy_level'] == 'LOCAL_ONLY' and done['status'] == 'COMPLETED'
    recovery = e.structured.recovery(e.ctx, done['id'], {'expected_version': done['version']})
    assert recovery['checkpoint']['characters:hero'] == before
    restored = e.structured.restore_checkpoint(e.ctx, done['id'], {'expected_version': done['version'], 'preview_digest': recovery['preview_digest'], 'confirmed': True})
    assert restored['status'] == 'RESTORED' and read(e, 'characters:hero')['name'] == before['name']
    assert read(e, target, row['target_id'])['name'] == 'Fork rename'


def test_delete_modify_choice_blocks_dangling_selected_and_unselected_cross_references(structured):
    e = structured; row = create(e)
    change(e, row['id_map']['characters:hero'], {'status': 'ARCHIVED'}, row['target_id'])
    plan = compare(e, row); choices = {c['id']: 'FORK' for r in plan['records'] for c in r['changes'] if c['kind'] == 'CONFLICT'}
    plan = compare(e, row, choices)
    assert not plan['can_apply'] and plan['blocked'][0]['code'] == 'FORK_CROSS_REFERENCE_MISSING_OR_ARCHIVED'
    with pytest.raises(ValueError, match='UNRESOLVED'): apply(e, row, plan, choices)
    # A relationship outside the selected set still prevents a dangling archive.
    other = create(e, ['locations:harbor', 'characters:hero'])
    change(e, other['id_map']['characters:hero'], {'status': 'ARCHIVED'}, other['target_id'])
    plan = compare(e, other); choices = {c['id']: 'FORK' for r in plan['records'] for c in r['changes'] if c['kind'] == 'CONFLICT'}
    plan = compare(e, other, choices)
    assert any(b['code'] == 'FORK_UNSELECTED_DEPENDENT_REQUIRES_REVIEW' for b in plan['blocked'])


@pytest.mark.parametrize('side', ['original', 'fork', 'authority'])
def test_current_source_and_authorization_guards_at_apply(structured, side):
    e = structured; row = create(e); target = row['id_map']['characters:hero']
    change(e, target, {'name': 'Fork change'}, row['target_id']); plan = compare(e, row)
    if side == 'original': change(e, 'characters:hero', {'goal': 'New author text'})
    elif side == 'fork': change(e, target, {'goal': 'New fork text'}, row['target_id'])
    def deny(): raise HTTPException(403, 'revoked')
    with pytest.raises((StaleSourceError, HTTPException)): apply(e, row, plan, **({'reauthorize': deny} if side == 'authority' else {}))
    assert read(e, 'characters:hero')['name'] == 'hero'
    assert not e.store.read(e.nid, e.ctx.scope)['collections'].get(e.structured.MERGES)


def test_interrupted_original_cas_is_durable_unknown_never_replayed_and_reviewable(structured, monkeypatch):
    e = structured; row = create(e)
    for key in ['characters:hero', 'characters:friend']: change(e, row['id_map'][key], {'name': 'Fork ' + key}, row['target_id'])
    plan = compare(e, row); writer = e.novels.compare_and_swap_record; calls = []
    def lost(*args, **kwargs):
        result = writer(*args, **kwargs); calls.append(args[2]); raise RuntimeError('receipt lost')
    monkeypatch.setattr(e.novels, 'compare_and_swap_record', lost)
    with pytest.raises(RuntimeError): apply(e, row, plan)
    raw = list(e.store.read(e.nid, e.ctx.scope)['collections'][e.structured.MERGES].values())[0]
    assert raw['status'] == 'RECOVERY_REQUIRED' and raw['journal'][0]['status'] == 'CLAIMED' and len(calls) == 1
    review = e.structured.recovery(e.ctx, raw['id'], {'expected_version': raw['version']})
    assert review['no_automatic_retry'] and review['current'] != review['checkpoint']
    monkeypatch.setattr(e.novels, 'compare_and_swap_record', writer)
    done = e.structured.restore_checkpoint(e.ctx, raw['id'], {'expected_version': raw['version'], 'preview_digest': review['preview_digest'], 'confirmed': True})
    assert done['status'] == 'RESTORED'
    assert read(e, 'characters:hero')['name'] == 'hero' and read(e, 'characters:friend')['name'] == 'friend'


def test_branch_ids_never_resolve_project_manuscript_or_structured_record_fallback(structured):
    e = structured; scope = {'mode': 'collaboration', 'novel_id': e.nid, 'branch_id': 'branch-real'}
    ctx = replace(e.ctx, scope=scope, branch='branch-real')
    assert not e.structured.catalog(ctx)['available']
    with pytest.raises(ValueError, match='BRANCH_WRITER'): e.structured.preflight(ctx, {'title':'Forbidden', 'records':[]})


def linked_preflight(e, manuscript):
    selected = e.structured.catalog(e.ctx)['records']
    return e.structured.preflight(e.ctx, {'title': 'Reviewed combined fork structures',
        'manuscript_fork': {'fork_id': manuscript['id'], 'expected_version': manuscript['version']},
        'records': [{k:r[k] for k in ('kind','record_id','source_digest')} | {'license':'Synthetic author-owned','allow_local_copy':True} for r in selected]})


def test_attach_selected_records_to_same_owned_manuscript_fork_preserves_manuscript(structured):
    from test_r5_project_forks import create as manuscript_fork
    e = structured; manuscript = manuscript_fork(e); before = e.chapters.get(manuscript['id_map']['chapters'][e.cid]); count = len(e.novels.list())
    pre = linked_preflight(e, manuscript); assert pre['target_id'] == manuscript['target_id']
    row = e.structured.create_fork(e.ctx, pre['id'], confirmation(pre))
    assert len(e.novels.list()) == count and row['target_id'] == manuscript['target_id']
    assert e.chapters.get(before['id']) == before
    assert row['journal'][0]['kind'] == 'VERIFY_OWNED_MANUSCRIPT_FORK'
    assert not any(j['kind'] == 'CREATE_PROJECT' for j in row['journal'])
    assert read(e, row['id_map']['characters:hero'], row['target_id'])['current_location'] == split(row['id_map']['locations:harbor'])[1]
    change(e, row['id_map']['characters:hero'], {'name': 'Combined fork character'}, row['target_id'])
    done = apply(e, row, compare(e, row)); assert done['status'] == 'COMPLETED'
    assert read(e, 'characters:hero')['name'] == 'Combined fork character' and e.chapters.get(before['id']) == before


@pytest.mark.parametrize('change_side', ['original', 'fork', 'permission', 'collision', 'owner'])
def test_attach_binding_rechecks_exact_manuscript_target_and_never_overwrites_collision(structured, change_side):
    from test_r5_project_forks import create as manuscript_fork, mutate, paragraph
    e = structured; manuscript = manuscript_fork(e); pre = linked_preflight(e, manuscript)
    if change_side == 'original': mutate(e, e.cid, lambda doc: doc['content'].__setitem__(1, paragraph('New original after preview')))
    if change_side == 'fork': mutate(e, manuscript['id_map']['chapters'][e.cid], lambda doc: doc['content'].__setitem__(1, paragraph('New fork after preview')))
    if change_side == 'collision':
        key = pre['id_map']['locations:harbor']; e.novels.upsert_location(pre['target_id'], split(key)[1], {'name':'Existing collision must remain','privacy_level':'LOCAL_ONLY'})
    if change_side == 'owner':
        ctx = replace(e.ctx, actor='another-author')
        with pytest.raises(FileNotFoundError): e.structured.create_fork(ctx, pre['id'], confirmation(pre))
        return
    def deny(_nid): raise HTTPException(403, 'target access revoked')
    from app.repositories.chapter_repository import VersionConflict
    with pytest.raises((StaleSourceError, HTTPException, VersionConflict)):
        e.structured.create_fork(e.ctx, pre['id'], confirmation(pre), target_authorize=deny if change_side=='permission' else lambda _: None)
    if change_side == 'collision': assert read(e, pre['id_map']['locations:harbor'], pre['target_id'])['name'] == 'Existing collision must remain'
    assert len(e.chapters.list(manuscript['target_id'])) == 1


def test_attach_input_never_accepts_arbitrary_target_project_or_story_route_id(structured):
    e = structured
    with pytest.raises(ValueError): e.structured.preflight(e.ctx, {'title':'No arbitrary target','target_id':e.nid,'records':[]})
    selected = e.structured.catalog(e.ctx)['records']
    with pytest.raises(FileNotFoundError):
        e.structured.preflight(e.ctx, {'title':'No story-route confusion','manuscript_fork':{'fork_id':'main-route','expected_version':1},
            'records':[{k:r[k] for k in ('kind','record_id','source_digest')} | {'license':'Mine','allow_local_copy':True} for r in selected]})
