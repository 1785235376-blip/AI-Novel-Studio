"""Two-image REFERENCES only: real File owners; no Host/model/PG claim."""
import base64
import hashlib
from copy import deepcopy
import io
import json
import zipfile
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from PIL import Image

from app.creative.service import CreativeService
from app.creative.workspace import IndependentWorkspaceService
from app.experimental.common import StaleSourceError
from app.experimental.media import MediaService
from app.experimental.production_lineage import ProductionLineageService
from app.experimental.portable_projects import PortableProjectsService, read_archive, LIMITS
from app.experimental.portable_projects_api import create_portable_projects_router
from app.experimental.ux import ReadContext
from app.experimental.writing_focus import WritingFocusService
from app.services.asset_library_service import AssetLibraryService
from app.services.v1_capability_service import CapabilityVersionConflict
from test_r3_media_support import rig
from test_r3_mounted_contracts import mounted, prefix, checked
from test_r4_portable_batches_mounted import tools


def confirm(row):
    return dict(expected_version=row['version'], snapshot_digest=row['snapshot_digest'], confirmed=True)


def upload(raw):
    return dict(filename='two-images.zip', content_base64=base64.b64encode(raw).decode())


@pytest.fixture
def images(rig, monkeypatch):
    r = rig
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'portable_projects_v2,narrative_production_v2,asset_lineage_v2')
    monkeypatch.setenv('V1_ACCEPTANCE_MODE', 'false')
    r.lineage = ProductionLineageService(r.store, r.novels, r.chapters, r.assets,
        MediaService(r.store, r.novels, r.chapters, assets=r.assets, screenplays=r.screenplays))
    r.workspace = IndependentWorkspaceService(CreativeService(r.store, r.novels, r.chapters), r.assets, r.lineage)
    r.sources = WritingFocusService(r.store, r.novels, r.chapters)
    r.portable = PortableProjectsService(r.store, r.novels, r.chapters, sources=r.sources, assets=r.assets, workspace=r.workspace)
    r.ctx = ReadContext(r.nid, r.scope, r.actor)
    r.workspace.activate(r.nid, r.scope, r.actor)
    rows = []
    with r.workspace._asset_scope(r.nid, r.scope):
        for color in ('red', 'blue'):
            buffer = io.BytesIO(); Image.new('RGB', (8, 8), color).save(buffer, format='PNG')
            rows.append(r.assets.create(r.nid, color+'.png', base64.b64encode(buffer.getvalue()).decode(), 'image/png', 'image',
                                        required_features=('narrative_production_v2',)))
    r.workspace.relationships.add(r.nid, r.scope, r.actor, rows[0]['id'], {'expected_version': rows[0]['version'], 'type': 'REFERENCES',
        'target': {'kind': 'ASSET', 'id': rows[1]['id'], 'version': rows[1]['version'], 'digest': rows[1]['sha256']}, 'reason': 'Synthetic author reference'})
    chapter = r.chapters.get(r.chapter['id'])
    r.chapters.save(chapter['id'], {'version': chapter['version'], 'document': {'type': 'doc', 'content': [
        {'type': 'image', 'attrs': {'asset_id': row['id']}} for row in rows]}})
    r.originals = rows
    r.reference = r.portable.catalog(r.ctx)['image_references'][0]
    yield r


def exported(r):
    row = r.portable.export(r.ctx, {'chapter_ids': [r.chapter['id']], 'image_reference_id': r.reference['id']})
    return r.portable.download(r.ctx, row['id'], row['version'])


def restored(r, activate=True):
    raw = exported(r); row = r.portable.preflight_import(r.ctx, upload(raw))
    row = r.portable.restore(r.ctx, row['id'], confirm(row))
    target = row['target_id']; scope = {'mode': 'local', 'novel_id': target}
    if activate: r.workspace.activate(target, scope, r.actor)
    return row, ReadContext(target, scope, r.actor)


def preview(r, row, ctx):
    return r.portable.preview_reference(r.ctx, row['id'], {k: v for k, v in confirm(row).items() if k != 'confirmed'}, ctx)


def apply(r, row, ctx, guard=lambda: None):
    return r.portable.confirm_reference(r.ctx, row['id'], {**confirm(row), 'preview_digest': row['reference_review']['preview_digest']}, ctx, guard)


def test_file_export_restore_explicit_preview_confirm_reopen_uses_original_owner(images):
    r = images; before = deepcopy(r.chapters.get(r.chapter['id'])); raw = exported(r)
    manifest, payloads = read_archive(raw)
    assert manifest['format'] == 'AI_NOVEL_PORTABLE_IMAGE_REFERENCE_1' and len(payloads) == 2
    assert manifest['image_reference']['type'] == 'REFERENCES'
    assert all(row['id'].encode() not in raw for row in r.originals) and r.actor.encode() not in raw
    row, ctx = restored(r, False)
    assert row['reference_state'] == 'PENDING'
    with pytest.raises(ValueError, match='OPEN_RESTORED_STUDIO'): preview(r, row, ctx)
    r.workspace.activate(ctx.novel_id, ctx.scope, r.actor)
    assert r.workspace.relationships.graph(ctx.novel_id, ctx.scope)['edges'] == []
    reviewed = preview(r, row, ctx)
    assert r.workspace.relationships.graph(ctx.novel_id, ctx.scope)['edges'] == []
    result = apply(r, reviewed, ctx)
    assert result['reference_state'] == 'RESTORED' and result['version'] == reviewed['version'] + 2
    reopened_assets = AssetLibraryService(r.root)
    reopened_lineage = ProductionLineageService(r.store, r.novels, r.chapters, reopened_assets,
        MediaService(r.store, r.novels, r.chapters, assets=reopened_assets, screenplays=r.screenplays))
    reopened = IndependentWorkspaceService(CreativeService(r.store, r.novels, r.chapters), reopened_assets, reopened_lineage)
    graph = reopened.relationships.graph(ctx.novel_id, ctx.scope)
    assert len(graph['edges']) == 1
    edge = graph['edges'][0]
    assert edge['type'] == 'REFERENCES' and edge['state'] == 'CURRENT' and edge['created_by'] == r.actor
    assert edge['id'] != r.reference['id'] and edge['from'] == row['id_map']['media'][row['image_reference']['source']]
    assert edge['target']['id'] == row['id_map']['media'][row['image_reference']['target']]
    assert not graph['executable'] and r.chapters.get(r.chapter['id']) == before
    with pytest.raises((ValueError, CapabilityVersionConflict)): apply(r, reviewed, ctx)
    assert len(reopened.relationships.graph(ctx.novel_id, ctx.scope)['edges']) == 1


@pytest.mark.parametrize('change', ['missing', 'duplicate', 'foreign', 'incarnation', 'wrong-kind', 'stale', 'digest'])
def test_mapping_and_current_identity_denials_write_no_relation(images, change):
    r = images; row, ctx = restored(r)
    stored = r.portable._owned(r.ctx, row['id']); mapping = stored['id_map']['media']; alias = stored['manifest']['image_reference']['source']
    if change in {'missing', 'duplicate', 'foreign'}:
        if change == 'missing': mapping.pop(alias)
        elif change == 'duplicate': mapping[alias] = next(v for k, v in mapping.items() if k != alias)
        else: mapping[alias] = r.originals[0]['id']
        with r.store.transaction(r.nid, r.scope) as state: state['collections'][r.portable.RECORDS][row['id']]['id_map']['media'] = mapping
    elif change == 'incarnation':
        with r.store.transaction(r.nid, r.scope) as state: state['collections'][r.portable.RECORDS][row['id']]['target_incarnation'] = 'file:'+str(uuid4())
    else:
        with r.workspace._asset_scope(ctx.novel_id, ctx.scope):
            asset = r.assets.get(mapping[alias])
            if change == 'stale': r.assets.update_metadata(asset['id'], {'parameters': {'note': 'changed'}}, expected_version=asset['version'])
            else:
                # Corrupt synthetic fixture metadata only; never a product writer.
                path = r.assets.root / (asset['id']+'.json'); meta = json.loads(path.read_text(encoding='utf-8'))
                meta['kind' if change == 'wrong-kind' else 'sha256'] = 'audio' if change == 'wrong-kind' else '0'*64
                path.write_text(json.dumps(meta), encoding='utf-8')
    with pytest.raises((ValueError, FileNotFoundError, KeyError)): preview(r, row, ctx)
    with r.workspace._asset_scope(ctx.novel_id, ctx.scope):
        for aid in row['id_map']['media'].values():
            try: assert r.workspace.relationships.records(r.assets.get(aid)) == []
            except (ValueError, FileNotFoundError): pass


def test_stale_preview_duplicate_and_target_authority_are_denied(images):
    r = images; row, ctx = restored(r); reviewed = preview(r, row, ctx)
    with pytest.raises(ValueError, match='AUTHORITY'): apply(r, reviewed, ReadContext(r.nid, r.scope, r.actor))
    with r.workspace._asset_scope(ctx.novel_id, ctx.scope):
        target = r.assets.get(reviewed['reference_review']['target']['id'])
        r.assets.update_metadata(target['id'], {'parameters': {'note': 'changed'}}, expected_version=target['version'])
    with pytest.raises(StaleSourceError): apply(r, reviewed, ctx)
    assert r.workspace.relationships.graph(ctx.novel_id, ctx.scope)['edges'] == []


def test_unknown_after_original_write_never_replays(images, monkeypatch):
    r = images; row, ctx = restored(r); reviewed = preview(r, row, ctx)
    original = r.workspace.relationships.add; calls = []
    def lost(*args, **kwargs):
        calls.append(1); original(*args, **kwargs); raise OSError('synthetic lost receipt after real write')
    monkeypatch.setattr(r.workspace.relationships, 'add', lost)
    with pytest.raises(OSError): apply(r, reviewed, ctx)
    current = next(item for item in r.portable.records(r.ctx)['items'] if item['id'] == row['id'])
    assert current['reference_state'] == 'UNKNOWN' and len(calls) == 1
    with pytest.raises(ValueError, match='NOT_RETRYABLE'): preview(r, current, ctx)
    with pytest.raises((ValueError, CapabilityVersionConflict)): apply(r, reviewed, ctx)
    assert len(calls) == 1 and len(r.workspace.relationships.graph(ctx.novel_id, ctx.scope)['edges']) == 1


def test_actual_target_delete_recreate_cannot_adopt_old_mapping(images):
    r = images; row, ctx = restored(r)
    old_identity = r.workspace.store.incarnation(ctx.novel_id)
    r.novels.delete(ctx.novel_id)
    r.novels.create({'id': ctx.novel_id, 'title': 'Synthetic new incarnation'})
    r.workspace.activate(ctx.novel_id, ctx.scope, r.actor)
    assert r.workspace.store.incarnation(ctx.novel_id) != old_identity
    with pytest.raises(StaleSourceError, match='INCARNATION'): preview(r, row, ctx)
    assert r.workspace.relationships.graph(ctx.novel_id, ctx.scope)['edges'] == []


def test_duplicate_relation_and_source_cas_between_preview_and_writer(images, monkeypatch):
    r = images; row, ctx = restored(r); reviewed = preview(r, row, ctx)
    original = r.workspace.relationships.add
    def raced(*args, **kwargs):
        source = reviewed['reference_review']['source']
        with r.workspace._asset_scope(ctx.novel_id, ctx.scope):
            r.assets.update_metadata(source['id'], {'parameters': {'note': 'concurrent edit'}}, expected_version=source['version'])
        return original(*args, **kwargs)
    monkeypatch.setattr(r.workspace.relationships, 'add', raced)
    with pytest.raises(CapabilityVersionConflict): apply(r, reviewed, ctx)
    current = next(item for item in r.portable.records(r.ctx)['items'] if item['id'] == row['id'])
    assert current['reference_state'] == 'UNKNOWN' and r.workspace.relationships.graph(ctx.novel_id, ctx.scope)['edges'] == []
    with pytest.raises(ValueError, match='NOT_RETRYABLE'): preview(r, current, ctx)


def test_existing_reference_is_not_imported_twice(images):
    r = images; row, ctx = restored(r); reviewed = preview(r, row, ctx); proof = reviewed['reference_review']
    r.workspace.relationships.add(ctx.novel_id, ctx.scope, r.actor, proof['source']['id'], {
        'expected_version': proof['source']['version'], 'type': 'REFERENCES',
        'target': {'kind': 'ASSET', 'id': proof['target']['id'], 'version': proof['target']['version'], 'digest': proof['target']['sha256']}})
    with pytest.raises(StaleSourceError): apply(r, reviewed, ctx)
    assert len(r.workspace.relationships.graph(ctx.novel_id, ctx.scope)['edges']) == 1


def test_revoked_guard_and_double_confirmation_cas(images):
    r = images; row, ctx = restored(r); reviewed = preview(r, row, ctx)
    def revoked(): raise HTTPException(403, 'synthetic revoked authority')
    with pytest.raises(HTTPException): apply(r, reviewed, ctx, revoked)
    assert r.workspace.relationships.graph(ctx.novel_id, ctx.scope)['edges'] == []
    assert apply(r, reviewed, ctx)['reference_state'] == 'RESTORED'
    with pytest.raises(CapabilityVersionConflict): apply(r, reviewed, ctx)


@pytest.mark.parametrize('field,value', [('type', 'DERIVED_FROM'), ('type', 'APPROVED_FOR'), ('target', 'a9999'), ('source', 'a0001')])
def test_untrusted_profile_cannot_import_other_relationship_semantics(images, field, value):
    r = images; raw = exported(r)
    with zipfile.ZipFile(io.BytesIO(raw)) as z: entries = {n: z.read(n) for n in z.namelist()}
    doc = json.loads(entries['manifest.json'])
    if field == 'source': value = doc['image_reference']['target']
    doc['image_reference'][field] = value; entries['manifest.json'] = json.dumps(doc).encode()
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w') as z:
        for name, data in entries.items(): z.writestr(name, data)
    with pytest.raises(ValueError): read_archive(out.getvalue())


def test_api_original_target_authorization_host_flag_snapshot_and_no_store(images):
    r = images; row, ctx = restored(r); enabled = True; allow_target = True
    def authorize(nid, token, branch, permission):
        if token != 'synthetic-host' or branch is not None or (nid == ctx.novel_id and not allow_target): raise HTTPException(403, 'denied')
        return r.actor, {'mode': 'local', 'novel_id': nid}
    def flag(name):
        if not enabled: raise HTTPException(404, 'disabled')
    def host(token):
        if token != 'synthetic-host': raise HTTPException(401, 'host session required')
    app = FastAPI(); app.include_router(create_portable_projects_router(r.portable, authorize, flag, host))
    client = TestClient(app); base = f'/novels/{r.nid}/experimental/portable-projects/records/{row["id"]}'
    body = {k: v for k, v in confirm(row).items() if k != 'confirmed'}; headers = {'X-Session-Token': 'synthetic-host'}
    assert client.post(base+'/reference-preview', json=body).status_code == 401
    allow_target = False
    assert client.post(base+'/reference-preview', json=body, headers=headers).status_code == 403
    allow_target = True; enabled = False
    assert client.post(base+'/reference-preview', json=body, headers=headers).status_code == 404
    enabled = True
    response = client.post(base+'/reference-preview', json=body, headers=headers)
    assert response.status_code == 200 and response.headers['cache-control'] == 'no-store'
    reviewed = response.json()
    assert client.post(base+'/reference-confirm', json={**confirm(reviewed), 'preview_digest': '0'*64}, headers=headers).status_code == 422
    response = client.post(base+'/reference-confirm', json={**confirm(reviewed), 'preview_digest': reviewed['reference_review']['preview_digest']}, headers=headers)
    assert response.status_code == 200 and response.json()['reference_state'] == 'RESTORED'


def test_legacy_manifest_and_archive_bytes_unchanged(images):
    """Frozen vector measured from the actual df07 codec; no Git history needed."""
    r = images
    chapter = r.chapters.get(r.chapter['id'])
    r.chapters.save(chapter['id'], {'version': chapter['version'], 'document': {'type': 'doc', 'content': [{'type': 'paragraph', 'content': [{'type': 'text', 'text': 'Frozen portable legacy vector.'}]}]}})
    manifest, raw, _ = r.portable._build(r.ctx, [r.chapter['id']])
    assert manifest['format'] == 'AI_NOVEL_PORTABLE_1' and manifest['limitations'] == LIMITS
    assert 'image_reference' not in manifest
    assert hashlib.sha256(raw).hexdigest() == 'bbc13f452e9545161c3c9073aeca6f29a833a4fab4b2dde54bf16c201182d188'


def test_actual_mounted_both_prefixes_new_profile_uses_existing_composition(tools, monkeypatch):
    """Actual app/router/auth composition; the registered Host session is synthetic."""
    e = tools; ws = e.experimental.independent_workspace_service
    import os
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', os.environ.get('EXPERIMENTAL_FEATURES', '')+',narrative_production_v2,asset_lineage_v2')
    assert e.portable.workspace is ws  # the single production composition injection
    monkeypatch.setattr(ws.creative, 'store', e.store)
    monkeypatch.setattr(ws.creative, 'novels', e.novels)
    monkeypatch.setattr(ws.creative, 'chapters', e.chapters)
    for name, value in (('store', ws.creative.store), ('novels', e.novels), ('assets', e.assets), ('lineage', e.experimental.production_lineage_service)):
        monkeypatch.setattr(ws, name, value)
    actor, scope = e.experimental.authorize(e.nid, 'portable-host', None, 'domain.write')
    ws.activate(e.nid, scope, actor)
    assets = []
    with ws._asset_scope(e.nid, scope):
        for color in ('red', 'blue'):
            data = io.BytesIO(); Image.new('RGB', (8, 8), color).save(data, format='PNG')
            assets.append(e.assets.create(e.nid, color+'.png', base64.b64encode(data.getvalue()).decode(), 'image/png', 'image', required_features=('narrative_production_v2',)))
    ws.relationships.add(e.nid, scope, actor, assets[0]['id'], {'expected_version': 1, 'type': 'REFERENCES',
        'target': {'kind': 'ASSET', 'id': assets[1]['id'], 'version': 1, 'digest': assets[1]['sha256']}})
    current = e.chapters.get(e.chapter['id'])
    e.chapters.save(current['id'], {'version': current['version'], 'document': {'type': 'doc', 'content': [{'type': 'image', 'attrs': {'asset_id': a['id']}} for a in assets]}})
    base = e.base+'/portable-projects'
    candidate = checked(e.client.get(base+'/catalog'))['image_references'][0]
    exported_row = checked(e.client.post(base+'/export', json={'chapter_ids': [current['id']], 'image_reference_id': candidate['id']}))
    raw = e.client.get(base+f"/records/{exported_row['id']}/file?expected_version=1")
    assert raw.status_code == 200
    imported = checked(e.client.post(base+'/import-preflight', json=upload(raw.content)))
    restored_row = checked(e.client.post(base+f"/records/{imported['id']}/restore", json=confirm(imported)))
    target = restored_row['target_id']; target_scope = {'mode': 'local', 'novel_id': target}
    assert ws.relationships.graph(target, target_scope)['edges'] == []
    ws.activate(target, target_scope, actor)
    path = base+f"/records/{imported['id']}"
    body = {k: v for k, v in confirm(restored_row).items() if k != 'confirmed'}
    reviewed = checked(e.client.post(path+'/reference-preview', json=body))
    done = checked(e.client.post(path+'/reference-confirm', json={**confirm(reviewed), 'preview_digest': reviewed['reference_review']['preview_digest']}))
    assert done['reference_state'] == 'RESTORED'
    assert len(ws.relationships.graph(target, target_scope)['edges']) == 1
