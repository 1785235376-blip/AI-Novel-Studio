"""Current-artifact binding for B07 target exports.

The first reproduced defect: global Godot/Ink runtime PASS was inherited by a
brand-new story that had never been run. The second reproduced defect: an upload
with matching digests was itself treated as system execution proof. These
regressions prove that an uploaded receipt is only an EXTERNAL ACCEPTANCE CLAIM:
exact binding stops cross-story/revision/artifact reuse, idempotency/conflict and
stale-revision rules are explicit, and no upload can make a runtime level PASS.
"""
from copy import deepcopy

import pytest
from fastapi import HTTPException

import app.experimental.interactive_export_contract as contract
from app.experimental.interactive_story import InteractiveStoryService
from app.experimental.common import StaleSourceError
from app.experimental.planning import PlanningService
from app.experimental.story_graph import StoryGraphService
from app.services.asset_library_service import AssetLibraryService
from test_r4_revision_intelligence import revision_env

GODOT = 'GODOT_4_RUNTIME_PROJECT_V1'
INK = 'INK_2_3_2_CURRENT_ARTIFACT_V1'


@pytest.fixture
def env(revision_env):
    e = revision_env
    e.planning = PlanningService(e.store, e.novels, e.chapters)
    e.story_graph = StoryGraphService(e.store, e.novels, e.chapters)
    e.assets = AssetLibraryService(e.store.root)
    e.service = InteractiveStoryService(e.store, e.novels, e.chapters, e.planning, e.story_graph, e.assets)
    e.novels.upsert_character(e.nid, 'alice', {'name': 'Alice'})
    e.graph = e.planning.create_graph(e.nid, e.scope, 'author', {'title': 'Binding', 'links': {'chapter_ids': [e.cid], 'character_ids': ['alice']}})
    e.nodes = [e.graph['root_node_id']]
    for title in ['Harbour', 'Mountain']:
        e.nodes.append(e.planning.create_node(e.nid, e.scope, 'author', {'graph_id': e.graph['id'], 'parent_id': e.nodes[0], 'level': 'VOLUME', 'title': title})['id'])
    return e


def spec(e, dialogue='Gate'):
    return {'title': 'Binding story', 'graph_id': e.graph['id'], 'graph_version': 1, 'entry_node_id': e.nodes[0],
            'variables': [{'name': 'courage', 'type': 'int', 'initial': 0, 'minimum': 0, 'maximum': 3}],
            'nodes': [
                {'node_id': e.nodes[0], 'node_version': 1, 'title': 'Gate', 'character_id': 'alice', 'dialogue': dialogue,
                 'choices': [{'id': 'harbour', 'label': 'H', 'target': e.nodes[1], 'condition': '', 'assignments': {'courage': 2}},
                             {'id': 'mountain', 'label': 'M', 'target': e.nodes[2], 'condition': '', 'assignments': {}}]},
                {'node_id': e.nodes[1], 'node_version': 1, 'title': 'Harbour', 'dialogue': 'H', 'ending': 'H ending'},
                {'node_id': e.nodes[2], 'node_version': 1, 'title': 'Mountain', 'dialogue': 'M', 'ending': 'M ending'}]}


def approve(e, row):
    row = e.service.review(e.nid, e.scope, 'author', row['id'], {'expected_version': row['version'], 'action': 'submit'})
    receipt = e.service.review_preview(e.nid, e.scope, 'author', row['id'], {'expected_version': row['version']})
    return e.service.review(e.nid, e.scope, 'author', row['id'], {'expected_version': row['version'], 'action': 'approve', 'preview_digest': receipt['preview_digest']})


def make_approved(e, dialogue='Gate'):
    return approve(e, e.service.create_story(e.nid, e.scope, 'author', {'spec': spec(e, dialogue)}))


def revise(e, row, dialogue='Revised dialogue'):
    value = deepcopy(row['spec']); value['nodes'][0]['dialogue'] = dialogue
    row = e.service.save(e.nid, e.scope, 'author', row['id'], {'expected_version': row['version'], 'spec': value})
    return approve(e, row)


def export(e, row, target=GODOT):
    value = {'expected_version': row['version']}
    preview = e.service.export_preview(e.nid, e.scope, 'author', row['id'], {**value, 'target_id': target})
    assert preview['can_export'] is True
    return e.service.export(e.nid, e.scope, 'author', row['id'], {**value, 'target_id': target, 'preview_digest': preview['preview_digest']})


def snapshot(e, row):
    raw = e.service._owned(e.nid, e.scope, 'author', row['id'])
    return e.service._snapshot(e.nid, e.scope, raw)


def descriptor(e, target=GODOT):
    return next(item for item in contract.all_target_descriptors() if item['target_id'] == target)


def receipt(e, row, out, target=GODOT, **overrides):
    snap = snapshot(e, row)
    target_descriptor = descriptor(e, target)
    runtime = target_descriptor['verification_runtime'] or {'name': 'Godot', 'version': '4.7.0', 'format': 'x'}
    value = {
        'schema': contract.VERIFICATION_SCHEMA,
        'target_id': target,
        'target_format_version': out['target_format_version'],
        'story_id': row['id'],
        'revision': row['version'],
        'spec_digest': snap['spec_digest'],
        'source_digest': snap['source_digest'],
        'artifact_sha256': out['sha256'],
        'files_digest': out['files_digest'],
        'runtime': {'name': runtime['name'], 'version': '4.7.0', 'format': runtime.get('format', '')},
        'checks': {'TARGET_RUNTIME_EXECUTED': 'PASS', 'SAVE_RESTORE_VERIFIED': 'PASS'},
        'evidence': {'SOURCE_IMPLEMENTED': 'PASS', 'SCHEMA_VALIDATED': 'PASS', 'FIXTURE_TESTED': 'PASS',
                     'GENERATED_ARTIFACT_VALIDATED': 'PASS', 'TARGET_RUNTIME_EXECUTED': 'PASS',
                     'SAVE_RESTORE_VERIFIED': 'PASS', 'WINDOWS_USABILITY_VERIFIED': 'NOT_RUN'},
        'verifier': 'tests/test_interactive_export_evidence_binding.py',
        'commands': [{'label': 'run', 'argv': ['godot', '--headless', '--path', '<artifact>'], 'exit_code': 0}],
        'log_sha256': 'f' * 64,
        'verified_at': '2026-10-20T00:00:00Z',
    }
    if target == INK:
        ink_runtime = descriptor(e, INK)['verification_runtime']
        value['runtime'] = {'name': ink_runtime['name'], 'version': ink_runtime['version'], 'format': ink_runtime.get('format', '')}
    value.update(overrides)
    return value


def record(e, row, value):
    return e.service.record_export_verification(e.nid, e.scope, 'author', row['id'],
                                                {'expected_version': row['version'], 'receipt': value})


def row_for(e, row, target=GODOT):
    targets = e.service.export_targets(e.nid, e.scope, 'author', row['id'], {'expected_version': row['version']})
    return next(item for item in targets['targets'] if item['target_id'] == target)


# ---------------------------------------------------------------------------
# the reported defect: a never-run story must not look runtime-verified
# ---------------------------------------------------------------------------
def test_new_export_never_inherits_historical_runtime_pass(env):
    e = env; row = make_approved(e)
    current = row_for(e, row)
    assert current['historical_evidence']['TARGET_RUNTIME_EXECUTED'] == 'PASS'
    assert current['artifact_evidence_status'] == 'NOT_EXPORTED'
    assert current['runtime_claim'] == 'UNVERIFIED'
    out = export(e, row)
    assert out['artifact_evidence_status'] == 'UNVERIFIED'
    assert out['runtime_claim'] == 'UNVERIFIED'
    assert out['evidence']['TARGET_RUNTIME_EXECUTED'] == 'NOT_RUN'
    assert out['evidence']['SAVE_RESTORE_VERIFIED'] == 'NOT_RUN'
    assert out['historical_evidence']['TARGET_RUNTIME_EXECUTED'] == 'PASS'
    manifest_runtime = out['manifest']['runtime']
    assert 'evidence' not in manifest_runtime
    assert manifest_runtime['historical_evidence']['TARGET_RUNTIME_EXECUTED'] == 'PASS'
    assert manifest_runtime['current_artifact_evidence']['status'] == 'UNVERIFIED_AT_GENERATION'
    assert manifest_runtime['current_artifact_evidence']['binding_requirements']['artifact_sha256'].startswith('the deterministic')
    # the artifact identity the receipt must bind is exposed
    assert out['verification']['binding']['artifact_sha256'] == out['sha256']
    assert out['verification']['binding']['files_digest'] == out['files_digest']
    assert out['verification']['binding']['story_id'] == row['id']
    assert out['verification']['binding']['revision'] == row['version']


def test_valid_receipt_is_an_external_claim_never_a_system_pass(env):
    e = env; row = make_approved(e); out = export(e, row)
    result = record(e, row, receipt(e, row, out))
    assert result['status'] == 'RECORDED'
    assert result['origin'] == 'EXTERNAL_SUBMISSION' and result['trust'] == 'EXTERNAL_UNVERIFIED'
    assert result['system_verification'] == 'NOT_PERFORMED' and result['system_runtime_levels'] == 'NOT_RUN'
    view = result['artifact_evidence']
    assert view['status'] == 'EXTERNALLY_ASSERTED_PENDING'
    assert view['claim_trust'] == 'EXTERNAL_UNVERIFIED' and view['system_verification'] == 'NOT_PERFORMED'
    assert view['levels']['TARGET_RUNTIME_EXECUTED'] == 'NOT_RUN'
    assert view['levels']['SAVE_RESTORE_VERIFIED'] == 'NOT_RUN'
    assert view['levels']['GENERATED_ARTIFACT_VALIDATED'] == 'PASS'
    assert view['asserted_levels']['TARGET_RUNTIME_EXECUTED'] == 'PASS'
    assert view['latest_external_claim']['verifier'].endswith('evidence_binding.py')
    assert len(view['latest_external_claim']['claim_digest']) == 64
    assert result['runtime_claim'] == 'UNVERIFIED'
    current = row_for(e, row)
    assert current['artifact_evidence_status'] == 'EXTERNALLY_ASSERTED_PENDING'
    assert current['runtime_claim'] == 'UNVERIFIED'
    # Re-exporting the identical deterministic artifact keeps the same artifact
    # identity and the same external claim (never an inherited PASS).
    again = export(e, row)
    assert again['sha256'] == out['sha256']
    assert again['export_record_id'] == out['export_record_id']
    assert again['artifact_evidence_status'] == 'EXTERNALLY_ASSERTED_PENDING'
    assert again['evidence']['TARGET_RUNTIME_EXECUTED'] == 'NOT_RUN'
    assert again['verification']['external_claim_only'] is True
    assert again['verification']['system_verification'] == 'NOT_PERFORMED'
    assert again['manifest']['runtime']['current_artifact_evidence']['status'] == 'UNVERIFIED_AT_GENERATION'
    assert contract.artifact_evidence.__doc__ and 'EXTERNAL ACCEPTANCE CLAIMS' in contract.artifact_evidence.__doc__


def test_new_story_never_receives_another_story_receipt(env):
    e = env; first = make_approved(e, 'First'); out = export(e, first); record(e, first, receipt(e, first, out))
    second = make_approved(e, 'Second')
    second_out = export(e, second)
    assert second_out['artifact_evidence_status'] != 'PASS'
    foreign = receipt(e, first, out, story_id=first['id'])
    with pytest.raises(ValueError, match='EXPORT_VERIFICATION_NOT_BOUND_TO_RECORDED_ARTIFACT'):
        record(e, second, foreign)
    assert row_for(e, second)['artifact_evidence_status'] != 'PASS'


def test_revised_story_stales_previous_artifact_evidence(env):
    e = env; row = make_approved(e); out = export(e, row); record(e, row, receipt(e, row, out))
    revised = revise(e, row)
    current = row_for(e, revised)
    assert current['artifact_evidence_status'] == 'STALE_REVISION'
    assert current['runtime_claim'] == 'UNVERIFIED'
    assert current['artifact_evidence']['levels']['TARGET_RUNTIME_EXECUTED'] == 'NOT_RUN'
    revised_out = export(e, revised)
    assert revised_out['sha256'] != out['sha256']
    assert revised_out['artifact_evidence_status'] == 'NOT_EXPORTED' or revised_out['artifact_evidence_status'] != 'PASS'
    with pytest.raises(StaleSourceError, match='EXPORT_VERIFICATION_STALE_REVISION'):
        record(e, revised, receipt(e, row, out))


@pytest.mark.parametrize('field,value,match', [
    ('story_id', 'another-story', 'EXPORT_VERIFICATION_NOT_BOUND_TO_RECORDED_ARTIFACT'),
    ('revision', 99, 'EXPORT_VERIFICATION_STALE_REVISION'),
    ('spec_digest', '9' * 64, 'EXPORT_VERIFICATION_NOT_BOUND_TO_RECORDED_ARTIFACT'),
    ('source_digest', '9' * 64, 'EXPORT_VERIFICATION_NOT_BOUND_TO_RECORDED_ARTIFACT'),
    ('artifact_sha256', '9' * 64, 'EXPORT_VERIFICATION_NOT_BOUND_TO_RECORDED_ARTIFACT'),
    ('files_digest', '9' * 64, 'EXPORT_VERIFICATION_NOT_BOUND_TO_RECORDED_ARTIFACT'),
    ('target_format_version', 'wrong-format', 'EXPORT_VERIFICATION_NOT_BOUND_TO_RECORDED_ARTIFACT'),
])
def test_tampered_or_foreign_receipts_are_rejected(env, field, value, match):
    e = env; row = make_approved(e); out = export(e, row)
    with pytest.raises(ValueError, match=match):
        record(e, row, receipt(e, row, out, **{field: value}))
    assert row_for(e, row)['artifact_evidence_status'] != 'PASS'


def test_wrong_target_and_runtime_receipts_are_rejected(env):
    e = env; row = make_approved(e); out = export(e, row)
    with pytest.raises(ValueError):
        record(e, row, receipt(e, row, out, target_id=INK, target_format_version='ink-current-artifact-2'))
    wrong_runtime = receipt(e, row, out)
    wrong_runtime['runtime']['name'] = 'Unity'
    with pytest.raises(ValueError, match='EXPORT_VERIFICATION_BINDING_INVALID:RUNTIME_MISMATCH'):
        record(e, row, wrong_runtime)
    old_runtime = receipt(e, row, out)
    old_runtime['runtime']['version'] = '3.0.0'
    with pytest.raises(ValueError, match='EXPORT_VERIFICATION_BINDING_INVALID:RUNTIME_MISMATCH'):
        record(e, row, old_runtime)
    assert row_for(e, row)['artifact_evidence_status'] != 'PASS'


def test_invalid_receipt_records_are_rejected(env):
    e = env; row = make_approved(e); out = export(e, row)
    bad_schema = receipt(e, row, out); bad_schema['schema'] = 'other/1'
    with pytest.raises(ValueError, match='EXPORT_VERIFICATION_RECEIPT_INVALID'):
        record(e, row, bad_schema)
    non_runtime_level = receipt(e, row, out); non_runtime_level['checks'] = {'SCHEMA_VALIDATED': 'PASS'}
    with pytest.raises(ValueError, match='EXPORT_VERIFICATION_RECEIPT_INVALID'):
        record(e, row, non_runtime_level)
    no_pass = receipt(e, row, out); no_pass['checks'] = {'TARGET_RUNTIME_EXECUTED': 'FAIL'}
    with pytest.raises(ValueError, match='EXPORT_VERIFICATION_RECEIPT_INVALID'):
        record(e, row, no_pass)
    assert row_for(e, row)['artifact_evidence_status'] != 'PASS'


def test_ink_runtime_identity_is_exactly_bound(env):
    e = env; row = make_approved(e); out = export(e, row, INK)
    good = receipt(e, row, out, target=INK)
    recorded = record(e, row, good)
    assert recorded['artifact_evidence']['status'] == 'EXTERNALLY_ASSERTED_PENDING'
    assert recorded['artifact_evidence']['levels']['TARGET_RUNTIME_EXECUTED'] == 'NOT_RUN'
    other = make_approved(e, 'Ink other'); other_out = export(e, other, INK)
    old = receipt(e, other, other_out, target=INK)
    old['runtime']['version'] = '2.2.0'
    with pytest.raises(ValueError, match='EXPORT_VERIFICATION_BINDING_INVALID:RUNTIME_MISMATCH'):
        record(e, other, old)


def test_missing_evidence_is_unverified_not_pass(env):
    e = env; row = make_approved(e); export(e, row)
    current = row_for(e, row)
    assert current['artifact_evidence_status'] == 'UNVERIFIED'
    assert current['artifact_evidence']['levels']['TARGET_RUNTIME_EXECUTED'] == 'NOT_RUN'
    assert current['runtime_claim'] == 'UNVERIFIED'
    assert current['historical_evidence']['TARGET_RUNTIME_EXECUTED'] == 'PASS'


def test_revoked_authority_rolls_back_recorded_evidence(env):
    e = env; row = make_approved(e); out = export(e, row)
    before = e.store.read(e.nid, e.scope)
    calls = []

    def revoke():
        calls.append(1)
        if len(calls) >= 2: raise HTTPException(403, {'code': 'REVOKED'})

    with pytest.raises(HTTPException):
        e.service.record_export_verification(e.nid, e.scope, 'author', row['id'],
                                             {'expected_version': row['version'], 'receipt': receipt(e, row, out)},
                                             reauthorize=revoke)
    assert e.store.read(e.nid, e.scope) == before
    assert row_for(e, row)['artifact_evidence_status'] != 'PASS'


# ---------------------------------------------------------------------------
# the second reported defect: a self-reported "success" upload is not proof
# ---------------------------------------------------------------------------
def test_forged_success_fields_are_kept_only_as_an_external_claim(env):
    e = env; row = make_approved(e); out = export(e, row)
    forged = receipt(e, row, out, verifier='self-declared-runner',
                     log_sha256='f' * 64,
                     commands=[{'label': 'fabricated', 'argv': [], 'exit_code': 0}])
    result = record(e, row, forged)
    assert result['trust'] == 'EXTERNAL_UNVERIFIED'
    assert result['system_verification'] == 'NOT_PERFORMED'
    assert result['artifact_evidence']['status'] == 'EXTERNALLY_ASSERTED_PENDING'
    assert result['artifact_evidence']['levels']['TARGET_RUNTIME_EXECUTED'] == 'NOT_RUN'
    assert result['artifact_evidence']['levels']['SAVE_RESTORE_VERIFIED'] == 'NOT_RUN'
    assert result['runtime_claim'] == 'UNVERIFIED'
    claim = result['artifact_evidence']['latest_external_claim']
    assert claim['commands'][0]['label'] == 'fabricated'
    assert claim['log_sha256'] == 'f' * 64
    current = row_for(e, row)
    assert current['runtime_claim'] == 'UNVERIFIED'
    assert current['artifact_evidence']['status'] == 'EXTERNALLY_ASSERTED_PENDING'
    exported_again = export(e, row)
    assert exported_again['evidence']['TARGET_RUNTIME_EXECUTED'] == 'NOT_RUN'
    assert exported_again['runtime_claim'] == 'UNVERIFIED'


def test_identical_claim_replay_is_idempotent(env):
    e = env; row = make_approved(e); out = export(e, row); value = receipt(e, row, out)
    first = record(e, row, value)
    second = record(e, row, value)
    assert first['status'] == 'RECORDED' and second['status'] == 'IDEMPOTENT'
    assert second['evidence_record_id'] == first['evidence_record_id']
    rows = [item for item in e.service.list(e.nid, e.scope, e.service.EVIDENCE_COLLECTION)
            if item.get('export_record_id') == out['export_record_id']]
    assert len(rows) == 1


def test_conflicting_claim_does_not_overwrite_stored_evidence(env):
    e = env; row = make_approved(e); out = export(e, row)
    first = record(e, row, receipt(e, row, out))
    conflicting = receipt(e, row, out, log_sha256='a' * 64, verified_at='2026-10-20T01:00:00Z')
    with pytest.raises(StaleSourceError, match='EXPORT_VERIFICATION_CONFLICT'):
        record(e, row, conflicting)
    current = row_for(e, row)
    assert current['artifact_evidence_status'] == 'EXTERNALLY_ASSERTED_PENDING'
    claim = current['artifact_evidence']['latest_external_claim']
    assert claim['claim_digest'] == first['claim_digest']
    assert claim['log_sha256'] == 'f' * 64
    rows = [item for item in e.service.list(e.nid, e.scope, e.service.EVIDENCE_COLLECTION)
            if item.get('export_record_id') == out['export_record_id']]
    assert len(rows) == 1


def test_claim_for_replaced_revision_is_rejected_after_verification(env):
    e = env; row = make_approved(e); out = export(e, row)
    record(e, row, receipt(e, row, out))
    revised = revise(e, row)
    current = row_for(e, revised)
    assert current['artifact_evidence_status'] == 'STALE_REVISION'
    assert current['runtime_claim'] == 'UNVERIFIED'
    with pytest.raises(StaleSourceError, match='EXPORT_VERIFICATION_STALE_REVISION'):
        record(e, revised, receipt(e, row, out))
    fresh = export(e, revised)
    assert fresh['artifact_evidence_status'] == 'UNVERIFIED'
    assert fresh['evidence']['TARGET_RUNTIME_EXECUTED'] == 'NOT_RUN'
    assert fresh['runtime_claim'] == 'UNVERIFIED'


def test_claim_after_source_authority_change_is_rejected(env):
    e = env; row = make_approved(e); out = export(e, row)
    e.chapters.save(e.cid, {'version': e.chapters.get(e.cid)['version'], 'content': 'Changed after export'})
    with pytest.raises(StaleSourceError):
        record(e, row, receipt(e, row, out))
    with pytest.raises(StaleSourceError):
        row_for(e, row)


def test_export_identity_is_stable_and_not_duplicated(env):
    e = env; row = make_approved(e); first = export(e, row); second = export(e, row)
    assert first['export_record_id'] == second['export_record_id']
    assert first['sha256'] == second['sha256']
    exports = [item for item in e.service.list(e.nid, e.scope, e.service.EXPORT_COLLECTION)
               if item.get('target_id') == GODOT]
    assert len(exports) == 1
    assert contract.contract_document()['evidence_policy']['verification_receipts'] == \
        'EXTERNAL_ACCEPTANCE_CLAIMS_NOT_SYSTEM_EXECUTION'
    assert contract.contract_document()['evidence_policy']['system_runtime_verification'] == \
        'NOT_AVAILABLE_IN_THIS_PRODUCT'
