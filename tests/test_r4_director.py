"""A08 deterministic geometry, real File/PG histories and mounted API boundaries."""
import copy
import json
import pytest
from app.experimental.director import DirectorService, camera_checks, screenplay_projection
from app.experimental.common import StaleSourceError
from app.repositories.chapter_repository import VersionConflict
from test_r3_media_support import rig, branch_scope


def screenplay(rig):
    row = rig.screenplays.create(rig.nid)
    row = rig.screenplays.approve(rig.nid, row['id'], row['edit_version'])
    return rig.screenplays.plan_shots(rig.nid, row['id'], row['edit_version'])


def plan_body(row, **kw):
    return {'title': 'Alternative framing', 'screenplay_id': row['id'], 'expected_screenplay_version': row['edit_version'],
            'shots': [{'shot_id': r['id'], 'shot_size': 'WIDE', 'camera_angle': 'EYE_LEVEL', 'camera_motion': 'PAN', 'duration_seconds': 8,
                       'director': {'scene_purpose': 'Reveal the harbor', 'viewpoint': 'Observer', **kw}} for r in row['shots']]}


@pytest.fixture
def director(rig):
    return DirectorService(rig.store, rig.novels, rig.chapters, rig.screenplays)


def geometry(y):
    return {'coordinate_system': 'scene-meters-x-right-y-up', 'axis': ['a', 'b'], 'character_positions': {'a': {'x': 0, 'y': 0}, 'b': {'x': 10, 'y': 0}}, 'camera_position': {'x': 5, 'y': y}}


def test_exact_geometry_and_missing_evidence_are_not_text_guesses():
    shots = [{'id': 'a', 'scene_id': 'scene', 'director': geometry(2)}, {'id': 'b', 'scene_id': 'scene', 'director': geometry(-2)}]
    axis = camera_checks(shots)[0]
    assert axis['state'] == 'AXIS_CROSSING' and axis['cross_products'] == ['20', '-20']
    shots[1]['director'].update(intentional_axis_crossing=True, override_reason='Intentional disorientation')
    assert camera_checks(shots)[0]['state'] == 'INTENTIONAL_OVERRIDE'
    for mutation in [lambda x: x['director'].pop('camera_position'), lambda x: x['director'].update(camera_position={'x': 2, 'y': 0}),
                     lambda x: x.update(scene_id='other'), lambda x: x['director'].update(coordinate_system='different')]:
        sample = copy.deepcopy(shots); mutation(sample[1])
        assert camera_checks(sample)[0]['state'] == 'INSUFFICIENT_EVIDENCE'
    assert camera_checks([{'id': 'a'}, {'id': 'b', 'subject_position': 'crossed axis'}])[0]['state'] == 'INSUFFICIENT_EVIDENCE'
    shots[0]['director'].update(screen_direction='RIGHT_TO_LEFT', subject_movement={'start': {'x': 0, 'y': 0}, 'end': {'x': 1, 'y': 0}})
    assert camera_checks(shots)[1]['state'] == 'CONSISTENT'


def test_draft_compare_apply_real_versions_and_downstream_invalidation(rig, director):
    row = screenplay(rig)
    row = rig.screenplays.approve_shots(rig.nid, row['id'], row['edit_version'])
    row = rig.screenplays.plan_storyboard(rig.nid, row['id'], row['edit_version'])
    original = copy.deepcopy(row)
    one = director.create_plan(rig.nid, rig.scope, rig.actor, plan_body(row))
    two = director.create_plan(rig.nid, rig.scope, rig.actor, {**plan_body(row), 'title': 'Second alternative'})
    assert rig.screenplays.list(rig.nid)[0] == original
    comparison = director.compare(rig.nid, rig.scope, rig.actor, [one['id'], two['id']])
    assert len(comparison['candidates']) == 2 and comparison['original'][0]['shot_size'] == 'MEDIUM'
    result = director.apply(rig.nid, rig.scope, rig.actor, one['id'], one['version'], comparison['application_digests'][one['id']])
    assert result['edit_version'] == row['edit_version'] + 1 and result['shot_status'] == 'DRAFT'
    saved = rig.screenplays.list(rig.nid)[0]
    assert saved['shots'][0]['shot_size'] == 'WIDE' and saved['shots'][0]['director']['scene_purpose'] == 'Reveal the harbor'
    assert 'storyboard' not in saved and saved['director_stale_outputs'][0]['review_state'] == 'STALE_PENDING_REVIEW'
    assert saved['version_history'][-1] == {k: v for k, v in original.items() if k != 'version_history'}
    stale = next(r for r in director.plans(rig.nid, rig.scope, rig.actor)['items'] if r['id'] == two['id'])
    assert stale['stale'] and 'shots' not in stale
    assert 'Reveal the harbor' not in json.dumps(screenplay_projection(saved))
    assert 'director_stale_outputs' not in json.dumps(screenplay_projection(saved, enabled=True))
    # Original approval gate remains authoritative and creates another version.
    approved = rig.screenplays.approve_shots(rig.nid, row['id'], result['edit_version'])
    assert approved['shot_status'] == 'APPROVED'


def test_source_actor_branch_conflict_and_revocation_fail_closed(rig, director):
    row = screenplay(rig); plan = director.create_plan(rig.nid, rig.scope, rig.actor, plan_body(row))
    compare = director.compare(rig.nid, rig.scope, rig.actor, [plan['id']])
    with pytest.raises(FileNotFoundError): director.compare(rig.nid, rig.scope, 'other-actor', [plan['id']])
    assert director.plans(rig.nid, branch_scope(rig), rig.actor)['items'] == []
    with pytest.raises(StaleSourceError): director.apply(rig.nid, rig.scope, rig.actor, plan['id'], 1, '0' * 64)
    def revoked(): raise PermissionError('revoked')
    with pytest.raises(PermissionError): director.apply(rig.nid, rig.scope, rig.actor, plan['id'], 1, compare['application_digests'][plan['id']], revoked)
    assert rig.screenplays.list(rig.nid)[0]['edit_version'] == row['edit_version']
    rig.chapters.save(rig.chapter['id'], {'version': rig.chapter['version'], 'content': 'Changed source'})
    assert director.plans(rig.nid, rig.scope, rig.actor)['items'][0]['stale']
    with pytest.raises(StaleSourceError): director.apply(rig.nid, rig.scope, rig.actor, plan['id'], 1, compare['application_digests'][plan['id']])


def test_plan_character_and_override_validation(rig, director):
    row = screenplay(rig)
    with pytest.raises(ValueError, match='REQUIRES_REASON'): director.create_plan(rig.nid, rig.scope, rig.actor, plan_body(row, intentional_axis_crossing=True))
    with pytest.raises(ValueError, match='UNKNOWN_CHARACTER'): director.create_plan(rig.nid, rig.scope, rig.actor, plan_body(row, **geometry(3)))
    with pytest.raises(ValueError): director.create_plan(rig.nid, rig.scope, rig.actor, plan_body(row, camera_position={'x': float('inf'), 'y': 1}))


def test_existing_shot_edit_preserves_director_fields_and_history(rig, director):
    row = screenplay(rig); plan = director.create_plan(rig.nid, rig.scope, rig.actor, plan_body(row))
    comparison = director.compare(rig.nid, rig.scope, rig.actor, [plan['id']])
    director.apply(rig.nid, rig.scope, rig.actor, plan['id'], 1, comparison['application_digests'][plan['id']])
    saved = rig.screenplays.list(rig.nid)[0]; shot = saved['shots'][0]
    updated = rig.screenplays.update_shot(rig.nid, row['id'], shot['id'], {**shot, 'shot_size': 'CLOSE', 'expected_version': saved['edit_version']})
    assert updated['shots'][0]['director'] == shot['director']
    with pytest.raises(VersionConflict):
        rig.screenplays.update_shot(rig.nid, row['id'], shot['id'], {**shot, 'expected_version': saved['edit_version']})


def test_receipt_failure_recovers_after_restart_without_second_screenplay_write(rig, director, monkeypatch):
    row=screenplay(rig);plan=director.create_plan(rig.nid,rig.scope,rig.actor,plan_body(row))
    compare=director.compare(rig.nid,rig.scope,rig.actor,[plan['id']])
    original=director.mutate
    def fail_receipt(*args,**kwargs):raise OSError('synthetic receipt failure')
    monkeypatch.setattr(director,'mutate',fail_receipt)
    with pytest.raises(OSError):director.apply(rig.nid,rig.scope,rig.actor,plan['id'],1,compare['application_digests'][plan['id']])
    version=rig.screenplays.list(rig.nid)[0]['edit_version']
    restarted=DirectorService(rig.store,rig.novels,rig.chapters,rig.screenplays)
    recovered=restarted.apply(rig.nid,rig.scope,rig.actor,plan['id'],1,compare['application_digests'][plan['id']])
    assert recovered['recovered'] and recovered['edit_version']==version
    assert restarted.get(rig.nid,rig.scope,director.PLANS,plan['id'])['status']=='APPLIED'
    assert rig.screenplays.list(rig.nid)[0]['edit_version']==version


def test_rejected_plan_cannot_be_applied_by_an_inflight_old_review(rig, director):
    row=screenplay(rig);plan=director.create_plan(rig.nid,rig.scope,rig.actor,plan_body(row))
    compare=director.compare(rig.nid,rig.scope,rig.actor,[plan['id']])
    called=False
    def changed_decision():
        nonlocal called
        if not called:
            called=True;director.reject(rig.nid,rig.scope,rig.actor,plan['id'],1)
    from app.services.v1_capability_service import CapabilityVersionConflict
    with pytest.raises(CapabilityVersionConflict):
        director.apply(rig.nid,rig.scope,rig.actor,plan['id'],1,compare['application_digests'][plan['id']],changed_decision)
    assert rig.screenplays.list(rig.nid)[0]['edit_version']==row['edit_version']


def test_source_moved_to_other_branch_hides_entire_draft(rig,director):
    row=screenplay(rig);plan=director.create_plan(rig.nid,rig.scope,rig.actor,plan_body(row))
    # A source repository scope change is simulated without leaking IDs in views.
    original=director.chapters.get
    def moved(cid):
        value=original(cid)
        return {**value,'branch_id':'hidden-branch'} if cid==rig.chapter['id'] else value
    director.chapters=type('MovedSource',(),{'get':staticmethod(moved)})()
    assert director.plans(rig.nid,rig.scope,rig.actor)['items']==[]
    assert director.catalog(rig.nid,rig.scope,rig.actor)['screenplays']==[]


def test_character_revision_invalidates_position_plan_without_copying_character_secrets(rig,director):
    row=screenplay(rig)
    value=plan_body(row,character_positions={'alice':{'x':0,'y':0}})
    plan=director.create_plan(rig.nid,rig.scope,rig.actor,value)
    stored=director.get(rig.nid,rig.scope,director.PLANS,plan['id'])
    assert 'Careful' not in json.dumps(stored) and 'alice' in stored['character_sources']
    rig.novels.upsert_character(rig.nid,'alice',{'name':'Alice','personality':'Changed current character'})
    projected=director.plans(rig.nid,rig.scope,rig.actor)['items'][0]
    assert projected['stale'] and 'shots' not in projected
    with pytest.raises(StaleSourceError):director.compare(rig.nid,rig.scope,rig.actor,[plan['id']])


def test_applied_metadata_is_projected_only_with_current_source_privacy(rig,director):
    from app.source_privacy import review_source_privacy, content_digest
    row=screenplay(rig);plan=director.create_plan(rig.nid,rig.scope,rig.actor,plan_body(row))
    compared=director.compare(rig.nid,rig.scope,rig.actor,[plan['id']])
    director.apply(rig.nid,rig.scope,rig.actor,plan['id'],1,compared['application_digests'][plan['id']])
    saved=rig.screenplays.list(rig.nid)[0]
    assert 'Reveal the harbor' in json.dumps(director.project_screenplay(saved,enabled=True))
    review_source_privacy(rig.chapter,None,rig.actor,'CLOUD_ALLOWED',rig.chapter['version'],content_digest(rig.chapter),rig.root)
    safe=director.project_screenplay(saved,enabled=True)
    assert 'Reveal the harbor' not in json.dumps(safe) and 'director_source_evidence' not in json.dumps(safe)
    assert safe['shots'][0]['shot_size']=='WIDE'


def test_invalidated_asset_refs_are_only_in_original_history_not_current_exports(rig,director):
    row=screenplay(rig)
    row=rig.screenplays.novels.save_screenplay(rig.nid,{**row,'motion_tasks':[{'id':'historical-task','asset_id':'hidden-old-output','status':'SUCCEEDED'}]},expected_version=row['edit_version'])
    plan=director.create_plan(rig.nid,rig.scope,rig.actor,plan_body(row))
    comparison=director.compare(rig.nid,rig.scope,rig.actor,[plan['id']])
    director.apply(rig.nid,rig.scope,rig.actor,plan['id'],1,comparison['application_digests'][plan['id']])
    saved=rig.screenplays.list(rig.nid)[0]
    assert saved['director_stale_outputs'][0]['collections']==['motion_tasks']
    assert 'hidden-old-output' in json.dumps(saved['version_history'])
    assert 'hidden-old-output' not in json.dumps({k:v for k,v in saved.items() if k!='version_history'})
    exported=rig.novels.export_snapshot(rig.nid,asset_library=rig.assets,format='screenplay-package')
    assert 'hidden-old-output' not in json.dumps(exported['resource_manifest'])
    assert exported['resource_manifest']['missing_count']==0
    history=rig.screenplays.history(rig.nid,row['id'])
    safe=director.project_screenplay(history,enabled=True)
    assert 'hidden-old-output' not in json.dumps(safe)
    assert any(item.get('downstream_review_state')=='STALE_PENDING_REVIEW' for item in safe['items'])
