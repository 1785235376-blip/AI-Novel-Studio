"""Legacy (725) receipt replay compatibility for B07 export claims.

The reproduced defect: rows written by 725 have no claim_digest. Replaying the
exact same receipt on 6c857 was treated as a conflict instead of an idempotent
replay. These regressions derive the missing digest from the stored receipt for
comparison only, keep the historical row untouched, and still reject genuine
conflicts, stale revisions, cross-story/project reuse and runtime upgrades.
"""
import json
from copy import deepcopy

import pytest
from test_r3_mounted_contracts import mounted, checked, scoped, prefix
from test_r5_interactive_story_mounted import _verification_receipt, approve, create
from test_r4_revision_intelligence import revision_env
from test_interactive_export_evidence_binding import env, export, make_approved, receipt, record, revise, row_for

GODOT = 'GODOT_4_RUNTIME_PROJECT_V1'


def _insert_legacy_row(e, row, out, value):
    """Recreate the exact 725 storage shape: no claim_digest/origin/trust fields."""
    from app.experimental.common import new_row
    with e.store.transaction(e.nid, e.scope) as doc:
        legacy = new_row(e.nid, e.scope, 'author', {
            'status': 'RECORDED', 'export_record_id': out['export_record_id'],
            'story_id': row['id'], 'revision': row['version'], 'target_id': GODOT,
            'artifact_sha256': out['sha256'], 'files_digest': out['files_digest'],
            'receipt': deepcopy(value),
        })
        doc['collections'].setdefault(e.service.EVIDENCE_COLLECTION, {})[legacy['id']] = legacy
    return legacy


def _evidence_rows(e):
    return [item for item in e.service.list(e.nid, e.scope, e.service.EVIDENCE_COLLECTION)]


def test_legacy_identical_replay_is_idempotent_and_preserves_audit(env):
    e = env
    row = make_approved(e)
    out = export(e, row)
    value = receipt(e, row, out)
    legacy = _insert_legacy_row(e, row, out, value)
    before_rows = deepcopy(_evidence_rows(e))
    replay = record(e, row, value)
    assert replay['status'] == 'IDEMPOTENT'
    assert replay['evidence_record_id'] == legacy['id']
    assert replay['legacy_compatibility'] == {'matched_legacy_record': True,
                                              'digest_derived_from_stored_receipt': True,
                                              'stored_row_rewritten': False}
    assert replay['evidence_record_audit']['origin'] == 'LEGACY_RECORD_NO_ORIGIN'
    assert replay['evidence_record_audit']['stored_row_rewritten'] is False
    after_rows = _evidence_rows(e)
    assert len(after_rows) == 1
    # Historical row is not rewritten into a new trust/claim shape.
    assert after_rows == before_rows
    view = row_for(e, row)['artifact_evidence']
    assert view['status'] == 'EXTERNALLY_ASSERTED_PENDING'
    assert view['levels']['TARGET_RUNTIME_EXECUTED'] == 'NOT_RUN'
    assert view['levels']['SAVE_RESTORE_VERIFIED'] == 'NOT_RUN'
    assert row_for(e, row)['runtime_claim'] == 'UNVERIFIED'


def test_new_identical_replay_stays_idempotent(env):
    e = env
    row = make_approved(e)
    out = export(e, row)
    value = receipt(e, row, out)
    first = record(e, row, value)
    second = record(e, row, value)
    assert first['status'] == 'RECORDED' and second['status'] == 'IDEMPOTENT'
    assert second['evidence_record_id'] == first['evidence_record_id']
    assert second['legacy_compatibility'] is None
    assert len(_evidence_rows(e)) == 1


def test_legacy_different_claim_is_still_a_conflict(env):
    e = env
    row = make_approved(e)
    out = export(e, row)
    value = receipt(e, row, out)
    _insert_legacy_row(e, row, out, value)
    conflicting = receipt(e, row, out, log_sha256='a' * 64, verified_at='2026-10-20T05:00:00Z')
    from app.experimental.common import StaleSourceError
    with pytest.raises(StaleSourceError, match='EXPORT_VERIFICATION_CONFLICT'):
        record(e, row, conflicting)
    rows = _evidence_rows(e)
    assert len(rows) == 1
    assert rows[0]['receipt']['log_sha256'] == 'f' * 64
    assert 'claim_digest' not in rows[0]


def test_legacy_replay_after_revision_change_is_rejected(env):
    e = env
    row = make_approved(e)
    out = export(e, row)
    value = receipt(e, row, out)
    _insert_legacy_row(e, row, out, value)
    revised = revise(e, row)
    from app.experimental.common import StaleSourceError
    with pytest.raises(StaleSourceError, match='EXPORT_VERIFICATION_STALE_REVISION'):
        record(e, revised, value)
    assert row_for(e, revised)['artifact_evidence_status'] == 'STALE_REVISION'
    assert row_for(e, revised)['runtime_claim'] == 'UNVERIFIED'


def test_legacy_receipt_does_not_cross_story_or_scope(env):
    e = env
    first = make_approved(e, 'First')
    out = export(e, first)
    value = receipt(e, first, out)
    _insert_legacy_row(e, first, out, value)
    second = make_approved(e, 'Second')
    out_second = export(e, second)
    with pytest.raises(ValueError, match='EXPORT_VERIFICATION_NOT_BOUND_TO_RECORDED_ARTIFACT'):
        record(e, second, value)
    assert row_for(e, second)['artifact_evidence_status'] != 'PASS'
    assert out_second['artifact_evidence_status'] == 'UNVERIFIED'


def test_legacy_compat_never_restores_system_runtime_pass(env):
    e = env
    row = make_approved(e)
    out = export(e, row)
    # Even a legacy row whose receipt claims PASS is external history only.
    value = receipt(e, row, out)
    _insert_legacy_row(e, row, out, value)
    replay = record(e, row, value)
    assert replay['system_verification'] == 'NOT_PERFORMED'
    assert replay['system_runtime_levels'] == 'NOT_RUN'
    assert replay['runtime_claim'] == 'UNVERIFIED'
    targets = e.service.export_targets(e.nid, e.scope, 'author', row['id'],
                                       {'expected_version': row['version']})
    godot = next(item for item in targets['targets'] if item['target_id'] == GODOT)
    assert godot['artifact_evidence_status'] == 'EXTERNALLY_ASSERTED_PENDING'
    assert godot['runtime_claim'] == 'UNVERIFIED'
    assert godot['artifact_evidence']['levels']['TARGET_RUNTIME_EXECUTED'] == 'NOT_RUN'


def test_mounted_legacy_replay_is_idempotent_and_scope_checked(mounted, monkeypatch):
    e = scoped(mounted, monkeypatch)
    row, _ = create(e, e.headers, chapter=False)
    row = approve(e, row, e.headers)
    url = e.base + '/interactive-stories/' + row['id']
    body_value = {'expected_version': row['version'], 'target_id': GODOT}
    preview = checked(e.client.post(url + '/export-preview', headers=e.headers, json=body_value))
    exported = checked(e.client.post(url + '/export', headers=e.headers,
                                     json={**body_value, 'preview_digest': preview['preview_digest']}))
    receipt_value = _verification_receipt(row, exported, preview)
    service = e.experimental.interactive_story_service
    from app.experimental.common import new_row
    with e.store.transaction(e.nid, e.scope) as doc:
        legacy = new_row(e.nid, e.scope, 'author', {
            'status': 'RECORDED', 'export_record_id': exported['export_record_id'],
            'story_id': row['id'], 'revision': row['version'], 'target_id': GODOT,
            'artifact_sha256': exported['sha256'], 'files_digest': exported['files_digest'],
            'receipt': receipt_value,
        })
        doc['collections'].setdefault(service.EVIDENCE_COLLECTION, {})[legacy['id']] = legacy
    first = checked(e.client.post(url + '/export-verification', headers=e.headers,
                                  json={'expected_version': row['version'], 'receipt': receipt_value}))
    second = checked(e.client.post(url + '/export-verification', headers=e.headers,
                                   json={'expected_version': row['version'], 'receipt': receipt_value}))
    assert first['status'] == 'IDEMPOTENT' and second['status'] == 'IDEMPOTENT'
    assert first['evidence_record_id'] == legacy['id'] == second['evidence_record_id']
    assert first['legacy_compatibility']['stored_row_rewritten'] is False
    current = checked(e.client.post(url + '/export-targets', headers=e.headers,
                                    json={'expected_version': row['version']}))
    godot = next(item for item in current['targets'] if item['target_id'] == GODOT)
    assert godot['artifact_evidence_status'] == 'EXTERNALLY_ASSERTED_PENDING'
    assert godot['runtime_claim'] == 'UNVERIFIED'
    assert godot['artifact_evidence']['levels']['TARGET_RUNTIME_EXECUTED'] == 'NOT_RUN'
    viewer = e.client.post(url + '/export-verification', headers=e.viewer_headers,
                           json={'expected_version': row['version'], 'receipt': receipt_value})
    assert viewer.status_code == 403
    other_branch = e.client.post(url + '/export-verification',
                                 headers={**e.headers, 'X-Branch-ID': e.other_branch},
                                 json={'expected_version': row['version'], 'receipt': receipt_value})
    assert other_branch.status_code == 403
