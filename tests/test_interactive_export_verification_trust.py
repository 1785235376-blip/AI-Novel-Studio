"""Mounted-API trust boundary for B07 export verification claims.

These are independent counterexamples against the real composed application:
an upload with matching digests, fabricated success fields or an arbitrary log
hash is retained only as an EXTERNAL acceptance claim. It can never make the
product report a system runtime PASS, cross a project/story/revision/incarnation,
overwrite stored evidence or bypass the existing authorization gate.
"""
import json
from uuid import uuid4

import pytest
from test_r3_mounted_contracts import checked, mounted, prefix, scoped
from test_r5_interactive_story_mounted import _verification_receipt, approve, create


GODOT = 'GODOT_4_RUNTIME_PROJECT_V1'


def _export(e, row, base=None, headers=None):
    headers = headers or {}
    base = base or e.base
    url = base + '/interactive-stories/' + row['id']
    preview = checked(e.client.post(url + '/export-preview', headers=headers,
                                    json={'expected_version': row['version'], 'target_id': GODOT}))
    exported = checked(e.client.post(url + '/export', headers=headers,
                                     json={'expected_version': row['version'],
                                           'preview_digest': preview['preview_digest'], 'target_id': GODOT}))
    return url, preview, exported


def _approve_at(e, row, base, headers=None, spec_patch=None):
    headers = headers or {}
    url = base + '/interactive-stories/' + row['id']
    if spec_patch is not None:
        value = json.loads(json.dumps(row['spec']))
        spec_patch(value)
        row = checked(e.client.put(url, headers=headers, json={'expected_version': row['version'], 'spec': value}))
    row = checked(e.client.post(url + '/review', headers=headers, json={'expected_version': row['version'], 'action': 'submit'}))
    receipt = checked(e.client.post(url + '/review-preview', headers=headers, json={'expected_version': row['version']}))
    return checked(e.client.post(url + '/review', headers=headers, json={'expected_version': row['version'],
                                                                         'action': 'approve', 'preview_digest': receipt['preview_digest']}))


def _story_in_project(e, base, headers=None, name='other'):
    headers = headers or {}
    graph = checked(e.client.post(base + '/planning/graphs', headers=headers,
                                  json={'title': 'Trust project ' + name}), 201)
    end = checked(e.client.post(base + '/planning/nodes', headers=headers,
                                json={'graph_id': graph['id'], 'parent_id': graph['root_node_id'],
                                      'level': 'VOLUME', 'title': 'Ending'}), 201)
    spec = {'title': 'Cross project story', 'graph_id': graph['id'], 'graph_version': graph['version'],
            'entry_node_id': graph['root_node_id'],
            'nodes': [
                {'node_id': graph['root_node_id'], 'node_version': 1, 'title': 'Gate',
                 'dialogue': 'Other project body',
                 'choices': [{'id': 'finish', 'label': 'Finish', 'target': end['id']}]},
                {'node_id': end['id'], 'node_version': 1, 'title': 'Ending', 'ending': 'Other ending'}]}
    row = checked(e.client.post(base + '/interactive-stories', headers=headers, json={'spec': spec}), 201)
    return row, _approve_at(e, row, base, headers)


def _target(e, row, headers=None, base=None):
    base = base or e.base
    current = checked(e.client.post(base + '/interactive-stories/' + row['id'] + '/export-targets',
                                    headers=headers, json={'expected_version': row['version']}))
    return next(item for item in current['targets'] if item['target_id'] == GODOT)


def _evidence_rows(e, export_record_id):
    service = e.experimental.interactive_story_service
    return [item for item in service.list(e.nid, e.scope, service.EVIDENCE_COLLECTION)
            if item.get('export_record_id') == export_record_id]


def test_forged_success_upload_is_an_external_claim_only(mounted):
    e = mounted
    row, _ = create(e); row = approve(e, row)
    url, preview, exported = _export(e, row)
    forged = _verification_receipt(row, exported, preview,
                                   log_sha256='f' * 64,
                                   commands=[{'label': 'self-reported', 'argv': [], 'exit_code': 0}],
                                   verifier='self-declared-runner')
    recorded = checked(e.client.post(url + '/export-verification',
                                     json={'expected_version': row['version'], 'receipt': forged}))
    assert recorded['status'] == 'RECORDED'
    assert recorded['origin'] == 'EXTERNAL_SUBMISSION'
    assert recorded['trust'] == 'EXTERNAL_UNVERIFIED'
    assert recorded['system_verification'] == 'NOT_PERFORMED'
    view = recorded['artifact_evidence']
    assert view['status'] == 'EXTERNALLY_ASSERTED_PENDING'
    assert view['system_verification'] == 'NOT_PERFORMED'
    for level in ('TARGET_RUNTIME_EXECUTED', 'SAVE_RESTORE_VERIFIED'):
        assert view['levels'][level] == 'NOT_RUN'
        assert view['asserted_levels'][level] == 'PASS'
    assert recorded['runtime_claim'] == 'UNVERIFIED'
    current = _target(e, row)
    assert current['artifact_evidence_status'] == 'EXTERNALLY_ASSERTED_PENDING'
    assert current['runtime_claim'] == 'UNVERIFIED'
    claim = current['artifact_evidence']['latest_external_claim']
    assert claim['verifier'] == 'self-declared-runner'
    assert claim['log_sha256'] == 'f' * 64
    assert len(claim['claim_digest']) == 64
    # The download payload re-read from the service still says NOT_RUN.
    again_url, again_preview, again = _export(e, row)
    assert again['sha256'] == exported['sha256'] and again['export_record_id'] == exported['export_record_id']
    assert again['artifact_evidence_status'] == 'EXTERNALLY_ASSERTED_PENDING'
    assert again['evidence']['TARGET_RUNTIME_EXECUTED'] == 'NOT_RUN'
    assert again['runtime_claim'] == 'UNVERIFIED'
    assert again['verification']['external_claim_only'] is True
    # Historical adapter evidence is readable but remains labelled historical.
    assert again['historical_evidence']['TARGET_RUNTIME_EXECUTED'] == 'PASS'


def test_read_only_users_cannot_write_claims(mounted, monkeypatch):
    e = scoped(mounted, monkeypatch)
    row, _ = create(e, e.headers, chapter=False); row = approve(e, row, e.headers)
    url, preview, exported = _export(e, row, headers=e.headers)
    receipt = _verification_receipt(row, exported, preview)
    viewer = e.client.post(url + '/export-verification', headers=e.viewer_headers,
                           json={'expected_version': row['version'], 'receipt': receipt})
    assert viewer.status_code == 403
    anonymous = e.client.post(url + '/export-verification',
                              json={'expected_version': row['version'], 'receipt': receipt})
    assert anonymous.status_code == 401
    other_branch = e.client.post(url + '/export-verification',
                                 headers={**e.headers, 'X-Branch-ID': e.other_branch},
                                 json={'expected_version': row['version'], 'receipt': receipt})
    assert other_branch.status_code == 403
    allowed = checked(e.client.post(url + '/export-verification', headers=e.headers,
                                    json={'expected_version': row['version'], 'receipt': receipt}))
    assert allowed['status'] == 'RECORDED' and allowed['trust'] == 'EXTERNAL_UNVERIFIED'


def test_claims_do_not_cross_projects_or_stories(mounted):
    e = mounted
    row, _ = create(e); row = approve(e, row)
    url, preview, exported = _export(e, row)
    receipt = _verification_receipt(row, exported, preview)
    # another story in the same project cannot absorb this claim
    other, _ = create(e); other = approve(e, other)
    other_url = e.base + '/interactive-stories/' + other['id']
    cross_story = e.client.post(other_url + '/export-verification',
                                json={'expected_version': other['version'], 'receipt': receipt})
    assert cross_story.status_code == 422
    # a story owned by another project cannot absorb it either
    nid = 'trust-other-' + uuid4().hex
    checked(e.client.post(e.prefix + '/novels', json={'id': nid, 'title': 'Trust other project'}), 201)
    other_base = e.prefix + '/novels/' + nid + '/experimental'
    story_b, approved_b = _story_in_project(e, other_base, name='B')
    url_b = other_base + '/interactive-stories/' + approved_b['id']
    cross_project = e.client.post(url_b + '/export-verification',
                                  json={'expected_version': approved_b['version'], 'receipt': receipt})
    assert cross_project.status_code == 422
    # the first project's story is not addressable under the other project route
    assert e.client.post(other_base + '/interactive-stories/' + row['id'] + '/export-verification',
                         json={'expected_version': row['version'], 'receipt': receipt}).status_code in {403, 404}
    assert _target(e, row)['artifact_evidence_status'] == 'UNVERIFIED'


def test_revision_and_source_changes_invalidate_old_claims(mounted):
    e = mounted
    row, _ = create(e); row = approve(e, row)
    url, preview, exported = _export(e, row)
    recorded = checked(e.client.post(url + '/export-verification',
                                     json={'expected_version': row['version'],
                                           'receipt': _verification_receipt(row, exported, preview)}))
    assert recorded['artifact_evidence']['status'] == 'EXTERNALLY_ASSERTED_PENDING'
    # revision change: new revision must not inherit the old claim
    revised = _approve_at(e, row, e.base, spec_patch=lambda spec: spec['nodes'][0].__setitem__(
        'dialogue', spec['nodes'][0]['dialogue'] + ' revised'))
    assert revised['version'] > row['version']
    current = _target(e, revised)
    assert current['artifact_evidence_status'] == 'STALE_REVISION'
    assert current['runtime_claim'] == 'UNVERIFIED'
    assert current['artifact_evidence']['levels']['TARGET_RUNTIME_EXECUTED'] == 'NOT_RUN'
    replay = e.client.post(url + '/export-verification',
                           json={'expected_version': revised['version'],
                                 'receipt': _verification_receipt(row, exported, preview)})
    assert replay.status_code == 409 and 'STALE_REVISION' in replay.text
    revised_url, revised_preview, revised_export = _export(e, revised)
    assert revised_export['sha256'] != exported['sha256']
    assert revised_export['artifact_evidence_status'] == 'UNVERIFIED'
    assert revised_export['runtime_claim'] == 'UNVERIFIED'
    # source incarnation change fences claims and reads
    e.chapters.save(e.chapter['id'], {'version': e.chapter['version'], 'content': 'Changed after verification'})
    stale = e.client.post(url + '/export-targets', json={'expected_version': revised['version']})
    assert stale.status_code == 409
    stale_claim = e.client.post(url + '/export-verification',
                                json={'expected_version': revised['version'],
                                      'receipt': _verification_receipt(row, exported, preview)})
    assert stale_claim.status_code == 409


def test_duplicate_is_idempotent_and_conflict_does_not_overwrite(mounted):
    e = mounted
    row, _ = create(e); row = approve(e, row)
    url, preview, exported = _export(e, row)
    receipt = _verification_receipt(row, exported, preview)
    first = checked(e.client.post(url + '/export-verification',
                                  json={'expected_version': row['version'], 'receipt': receipt}))
    second = checked(e.client.post(url + '/export-verification',
                                   json={'expected_version': row['version'], 'receipt': receipt}))
    assert first['status'] == 'RECORDED' and second['status'] == 'IDEMPOTENT'
    assert second['evidence_record_id'] == first['evidence_record_id']
    assert len(_evidence_rows(e, exported['export_record_id'])) == 1
    conflicting = _verification_receipt(row, exported, preview, log_sha256='a' * 64,
                                        verified_at='2026-10-20T02:00:00Z')
    rejected = e.client.post(url + '/export-verification',
                             json={'expected_version': row['version'], 'receipt': conflicting})
    assert rejected.status_code == 409 and 'EXPORT_VERIFICATION_CONFLICT' in rejected.text
    current = _target(e, row)
    claim = current['artifact_evidence']['latest_external_claim']
    assert claim['claim_digest'] == first['claim_digest']
    assert claim['log_sha256'] == 'f' * 64
    assert len(_evidence_rows(e, exported['export_record_id'])) == 1
    # A claim from a different verifier is a separate, explicitly listed claim,
    # still external and still not a PASS.
    independent = _verification_receipt(row, exported, preview, verifier='independent-manual-reviewer',
                                        log_sha256='b' * 64, verified_at='2026-10-20T03:00:00Z')
    third = checked(e.client.post(url + '/export-verification',
                                  json={'expected_version': row['version'], 'receipt': independent}))
    assert third['status'] == 'RECORDED'
    view = _target(e, row)['artifact_evidence']
    assert view['status'] == 'EXTERNALLY_ASSERTED_PENDING'
    assert len(view['external_claims']) == 2
    assert view['levels']['SAVE_RESTORE_VERIFIED'] == 'NOT_RUN'


def test_same_artifact_reexport_keeps_identity_and_claim(mounted):
    e = mounted
    row, _ = create(e); row = approve(e, row)
    url, preview, first = _export(e, row)
    checked(e.client.post(url + '/export-verification',
                          json={'expected_version': row['version'],
                                'receipt': _verification_receipt(row, first, preview)}))
    _, _, second = _export(e, row)
    assert first['sha256'] == second['sha256']
    assert first['export_record_id'] == second['export_record_id']
    assert second['artifact_evidence_status'] == 'EXTERNALLY_ASSERTED_PENDING'
    assert len(_evidence_rows(e, first['export_record_id'])) == 1
