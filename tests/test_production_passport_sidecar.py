"""Unsigned Passport File/optional actual-PG owner tests; no model/network calls."""
import hashlib
import io
import json
import zipfile

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from test_r3_media_support import rig
from test_r4_production_lineage import production, prepared, asset, declaration
from app.experimental.common import StaleSourceError
from app.experimental.production_lineage_api import create_production_lineage_router
from app.experimental import production_passport


def approved(rig, production, **kwargs):
    _, task, manifest = prepared(rig, production, **kwargs)
    pid = task['proposal_ids'][0]
    proposal = production.media.get(rig.nid, rig.scope, production.media.PROPOSALS, pid)
    reviewed = production.media.review(rig.nid, rig.scope, rig.actor, pid, 'approve', proposal['version'])
    return manifest, reviewed


def download(rig, production, manifest, proposal, guard=lambda: None):
    return production.passport(rig.nid, rig.scope, manifest['id'], proposal['id'], manifest['version'], guard)


def test_bundle_exact_bytes_reports_no_writes_and_closed_redaction(rig, production):
    a = asset(rig, '/private/key-sk-secret.png')
    production.annotate(rig.nid, rig.scope, rig.actor, a['id'], declaration(1, license={
        'label': '<script>sk-secret</script>', 'source': r'C:\private\key', 'note': 'https://user:password@secret.test'}))
    m, p = approved(rig, production, reference_asset_ids=[a['id']])
    before = rig.store.read(rig.nid, rig.scope)
    raw = download(rig, production, m, p)
    assert rig.store.read(rig.nid, rig.scope) == before
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        report = json.loads(archive.read('passport.json'))
        text = archive.read('passport.txt').decode()
        content = archive.read(report['output']['path'])
        assert len(archive.namelist()) == 3
    assert hashlib.sha256(content).hexdigest() == report['output']['sha256'] == m['outputs'][0]['digest']
    assert report['output']['size'] == len(content)
    assert text.split('Machine report (identical evidence fields):\n')[1].strip() == json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2)
    for secret in (rig.nid, rig.chapter['id'], a['id'], p['id'], p['asset_id'], 'sk-secret', '/private', 'C:\\private', 'password', '<script>', 'PRIVATE PROMPT'):
        assert secret not in json.dumps(report) and secret not in text
    assert report['credential'] == {'state': 'UNSIGNED_SIDECAR', 'c2pa': False, 'signature': None}
    assert report['approval']['state'] == 'APPROVED'
    assert 'FULL_DIF12_NOT_ACCEPTED' in report['limitations']
    assert hashlib.sha256(content + b'x').hexdigest() != report['output']['sha256']
    assert any(node['license_declaration']['state'] == 'REDACTED' for node in report['lineage']['assets'])
    assert download(rig, production, m, p) == raw


@pytest.mark.parametrize('status', ['PENDING_REVIEW', 'REJECTED', 'APPROVING'])
def test_only_original_approved_proposal(rig, production, status):
    m, p = approved(rig, production)
    with rig.store.transaction(rig.nid, rig.scope) as doc:
        doc['collections'][production.media.PROPOSALS][p['id']]['status'] = status
    with pytest.raises(ValueError, match='APPROVED_OUTPUT_REQUIRED'):
        download(rig, production, m, p)


@pytest.mark.parametrize('target', ['asset_bytes', 'proposal_bytes', 'approval', 'link', 'manifest'])
def test_corrupt_or_relinked_evidence_rejected(rig, production, target):
    m, p = approved(rig, production)
    if target == 'asset_bytes':
        rig.assets._bin_path(p['asset_id']).write_bytes(b'corrupt')
    else:
        with rig.store.transaction(rig.nid, rig.scope) as doc:
            row = doc['collections'][production.media.PROPOSALS][p['id']]
            if target == 'proposal_bytes': row['content_base64'] = 'Y29ycnVwdA=='
            if target == 'approval': row['approved_at'] = 'not-original'
            if target == 'link': row['asset_id'] = asset(rig)['id']
            if target == 'manifest': doc['collections'][production.MANIFESTS][m['id']]['outputs'][0]['digest'] = '0' * 64
    with pytest.raises((ValueError, FileNotFoundError)):
        download(rig, production, m, p)


def test_nonmember_and_version_conflict(rig, production):
    m, p = approved(rig, production)
    with pytest.raises(ValueError, match='NOT_IN_MANIFEST'):
        production.passport(rig.nid, rig.scope, m['id'], 'other', m['version'])
    from app.services.v1_capability_service import CapabilityVersionConflict
    with pytest.raises(CapabilityVersionConflict):
        production.passport(rig.nid, rig.scope, m['id'], p['id'], 99)


def test_change_during_serialization_rejected(rig, production, monkeypatch):
    m, p = approved(rig, production)
    original = production_passport.serialize
    def changing(report, content):
        result = original(report, content)
        production.annotate(rig.nid, rig.scope, rig.actor, p['asset_id'], declaration(rig.assets.get(p['asset_id'])['version']))
        return result
    monkeypatch.setattr(production_passport, 'serialize', changing)
    with pytest.raises(StaleSourceError, match='EVIDENCE_CHANGED'):
        download(rig, production, m, p)


def test_route_current_read_authority_flags_and_private_headers(rig, production):
    m, p = approved(rig, production)
    allowed = [True]; flags = [True]; permissions = []
    def auth(nid, token, branch, permission):
        permissions.append(permission)
        if token != 'valid' or not allowed[0]: raise HTTPException(403, 'denied')
        return rig.actor, rig.scope
    def require(name):
        if not flags[0]: raise HTTPException(404, 'disabled')
    app = FastAPI(); app.include_router(create_production_lineage_router(production, auth, require))
    client = TestClient(app)
    path = f'/novels/{rig.nid}/experimental/production/manifests/{m["id"]}/outputs/{p["id"]}/passport?expected_version=1'
    assert client.get(path).status_code == 403
    response = client.get(path, headers={'X-Session-Token': 'valid'})
    assert response.status_code == 200
    assert response.headers['content-type'] == 'application/zip'
    assert response.headers['cache-control'] == 'no-store'
    assert response.headers['x-content-type-options'] == 'nosniff'
    assert set(permissions) == {'domain.read'}
    flags[0] = False
    assert client.get(path, headers={'X-Session-Token': 'valid'}).status_code == 404
    flags[0] = True; allowed[0] = False
    assert client.get(path, headers={'X-Session-Token': 'valid'}).status_code == 403


def test_revocation_during_assembly_never_returns_bundle(rig, production):
    m, p = approved(rig, production)
    calls = [0]
    def guard():
        calls[0] += 1
        if calls[0] > 3: raise HTTPException(403, 'denied')
    with pytest.raises(HTTPException): download(rig, production, m, p, guard)


def test_denied_ancestor_has_no_identifier_digest_or_history_hint(rig, production):
    a = asset(rig, 'secret-ancestor', payload=b'private-ancestor-only-bytes')
    b = asset(rig, 'authorized-parent')
    production.annotate(rig.nid, rig.scope, rig.actor, b['id'], declaration(1, [a['id']]))
    m, p = approved(rig, production, reference_asset_ids=[b['id']])
    row = rig.assets.get(a['id']); row['branch_id'] = 'foreign-private'; rig.assets._write_meta(row)
    raw = download(rig, production, m, p)
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        text = archive.read('passport.json').decode()
        report = json.loads(text)
    assert report['lineage']['coverage'] == 'INCOMPLETE'
    assert a['id'] not in text and 'secret-ancestor' not in text
    assert row['sha256'] not in text
    assert all(not n['parents'] for n in report['lineage']['assets'] if n['ref'] == 'asset-2')


def test_private_root_and_wrong_branch_rejected(rig, production):
    m, p = approved(rig, production)
    row = rig.assets.get(p['asset_id']); row['hidden'] = True; rig.assets._write_meta(row)
    with pytest.raises(ValueError, match='APPROVAL_ASSET_LINK_INVALID'):
        download(rig, production, m, p)
    row['hidden'] = False; row['branch_id'] = 'foreign'; rig.assets._write_meta(row)
    with pytest.raises(FileNotFoundError): download(rig, production, m, p)


def test_source_drift_is_not_old_approval_for_new_content(rig, production):
    m, p = approved(rig, production)
    current = rig.chapters.get(rig.chapter['id'])
    rig.chapters.save(current['id'], {'version': current['version'], 'content': 'Changed source', 'source': 'USER'})
    with pytest.raises((StaleSourceError, ValueError)):
        download(rig, production, m, p)


def test_lineage_cycle_and_limits_fail_closed(rig, production, monkeypatch):
    a = asset(rig)
    m, p = approved(rig, production, reference_asset_ids=[a['id']])
    monkeypatch.setattr(production_passport, 'MAX_NODES', 1)
    with pytest.raises(ValueError, match='LINEAGE_LIMIT'): download(rig, production, m, p)
    monkeypatch.setattr(production_passport, 'MAX_NODES', 100)
    row = rig.assets.get(a['id']); row['source_asset_ids'] = [p['asset_id']]; rig.assets._write_meta(row)
    with pytest.raises(ValueError, match='LINEAGE_CYCLE'): download(rig, production, m, p)


def test_bounded_output_and_missing_license_are_honest(rig, production, monkeypatch):
    m, p = approved(rig, production)
    raw = download(rig, production, m, p)
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        report = json.loads(archive.read('passport.json'))
    assert report['lineage']['assets'][0]['license_declaration']['state'] == 'MISSING'
    monkeypatch.setattr(production_passport, 'MAX_OUTPUT', 1)
    with pytest.raises(ValueError, match='OUTPUT_LIMIT'): download(rig, production, m, p)


def test_old_json_export_remains_identical(rig, production):
    m, p = approved(rig, production)
    before = production.export(rig.nid, rig.scope, m['id'])
    download(rig, production, m, p)
    assert production.export(rig.nid, rig.scope, m['id']) == before


@pytest.mark.parametrize('change', ['approval', 'privacy', 'version'])
def test_second_pass_content_read_cannot_hide_current_owner_change(rig, production, monkeypatch, change):
    m, p = approved(rig, production)
    original = rig.assets.content
    calls = [0]
    def racing(*args, **kwargs):
        data = original(*args, **kwargs)
        calls[0] += 1
        # First pass reads selected asset, then the root traversal; second
        # pass does the same. Mutate after the second root content read.
        if calls[0] == 4:
            if change == 'approval':
                with rig.store.transaction(rig.nid, rig.scope) as doc:
                    doc['collections'][production.media.PROPOSALS][p['id']]['status'] = 'REJECTED'
            else:
                row = rig.assets.get(p['asset_id'])
                if change == 'privacy': row['hidden'] = True
                else: row['version'] += 1
                rig.assets._write_meta(row)
        return data
    monkeypatch.setattr(rig.assets, 'content', racing)
    with pytest.raises(StaleSourceError, match='EVIDENCE_CHANGED'):
        download(rig, production, m, p)


def test_bound_proposal_snapshot_does_not_reread_preview(rig, production, monkeypatch):
    m, p = approved(rig, production)
    def forbidden(*args, **kwargs):
        raise AssertionError('must not reread/decode unbounded replacement proposal')
    monkeypatch.setattr(production.media, 'preview', forbidden)
    assert download(rig, production, m, p)


def test_transient_authority_value_error_in_parent_read_is_not_optional(rig, production):
    m, p = approved(rig, production)
    calls = [0]
    def guard():
        calls[0] += 1
        # First bounded read uses calls 2..8; optional root traversal starts 9.
        if calls[0] == 9: raise ValueError('PRODUCTION_AUTHORITY_CHANGED')
    with pytest.raises(ValueError, match='PASSPORT_AUTHORITY_CHANGED'):
        download(rig, production, m, p, guard)


def test_second_pass_ancestor_only_chapter_change_is_fenced(rig, production, monkeypatch):
    a = asset(rig)
    chapter = rig.chapters.create(rig.nid, {'title': 'Ancestor only', 'content': 'Original'})
    production.annotate(rig.nid, rig.scope, rig.actor, a['id'], declaration(1, chapter_ids=[chapter['id']]))
    m, p = approved(rig, production, reference_asset_ids=[a['id']])
    original = rig.assets.content
    calls = [0]
    def racing(*args, **kwargs):
        data = original(*args, **kwargs)
        calls[0] += 1
        # Root then parent and root traversal each pass; mutate after the
        # second pass has already projected the ancestor chapter binding.
        if calls[0] == 6:
            current = rig.chapters.get(chapter['id'])
            rig.chapters.save(chapter['id'], {'version': current['version'], 'content': 'Changed', 'source': 'USER'})
        return data
    monkeypatch.setattr(rig.assets, 'content', racing)
    with pytest.raises(StaleSourceError, match='EVIDENCE_CHANGED'):
        download(rig, production, m, p)
