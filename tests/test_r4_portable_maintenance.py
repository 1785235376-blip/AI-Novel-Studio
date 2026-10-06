"""U14 remaining maintenance loops on original File/real-PostgreSQL authorities.

Only synthetic projects, owned import inputs and disposable export caches are
used. PostgreSQL matrix entries require the repository's disposable DB profile.
"""
import base64
from copy import deepcopy
import json

import pytest

from app.experimental.common import StaleSourceError
from app.experimental.portable_projects import PortableProjectsService, read_archive
from app.experimental.store import canonical
from app.experimental.ux import ReadContext
from app.experimental.writing_focus import WritingFocusService
from app.repositories.chapter_repository import VersionConflict
from app.source_privacy import content_digest, review_source_privacy
from test_r3_media_support import rig, wav_bytes
from test_r3_mounted_contracts import mounted, prefix, checked
from test_r4_portable_batches import work, add_media, confirm, upload
from test_r4_portable_batches_mounted import tools


def relink_preview(r, asset, raw, chapter_ids=None):
    return r.portable.preflight_relink(r.ctx, {**upload(raw, 'selected.wav'), 'kind': 'audio',
        'missing_id': asset['id'], 'chapter_ids': chapter_ids or [r.chapter['id']]})


def category(preview, kind):
    return next(c for c in preview['categories'] if c['kind'] == kind)


def delete_new_project(r, target):
    # Retire only this exact synthetic target's experimental metadata in PG.
    if r.backend == 'postgres':
        with r.store._connect() as connection:
            connection.execute('DELETE FROM experimental_scope_documents WHERE novel_id = %s', (target,))
    r.novels.delete(target)


def test_missing_digest_survives_restore_restart_second_export_and_exact_relink(work):
    r = work; asset, raw = add_media(r, True)
    original = deepcopy(r.chapters.get(r.chapter['id'])); history = deepcopy(r.chapters.history(r.chapter['id']))
    exported = r.portable.export(r.ctx, {'chapter_ids': [r.chapter['id']]})
    imported = r.portable.preflight_import(r.ctx, upload(r.portable.download(r.ctx, exported['id'], 1)))
    restored = r.portable.restore(r.ctx, imported['id'], confirm(imported)); target = restored['target_id']
    try:
        ctx = ReadContext(target, {'mode': 'local', 'novel_id': target}, r.actor)
        # Recreate services from the same original persistent authorities.
        portable = PortableProjectsService(r.store, r.novels, r.chapters,
            sources=WritingFocusService(r.store, r.novels, r.chapters), assets=r.assets)
        missing = portable.catalog(ctx)['missing'][0]
        assert missing['expected_sha256'] == asset['sha256']
        assert missing['id'] == restored['id_map']['media']['a0001']
        cid = restored['id_map']['chapters']['c0001']
        assert 'Alice' in r.chapters.get(cid)['content']
        again = portable.export(ctx, {'chapter_ids': [cid]})
        body = portable.download(ctx, again['id'], again['version']); manifest, payloads = read_archive(body)
        assert not payloads and manifest['media'][0]['sha256'] == asset['sha256']
        assert manifest['media'][0]['kind'] == 'audio'
        assert asset['id'].encode() not in body and r.nid.encode() not in body
        preview = portable.preflight_relink(ctx, {**upload(raw, 'moved.wav'), 'kind': 'audio',
            'missing_id': missing['id'], 'chapter_ids': [cid]})
        assert preview['digest_matches'] and preview['relink_review']['expected_sha256'] == asset['sha256']
        done = portable.relink(ctx, preview['id'], confirm(preview))
        assert done['status'] == 'RELINKED' and portable.catalog(ctx)['missing'] == []
        assert r.assets.content(done['id_map']['media'][missing['id']], actor_id=r.actor) == raw
        assert r.chapters.get(r.chapter['id']) == original and r.chapters.history(r.chapter['id']) == history
        # Recovery declaration is retained even after current references change.
        assert portable.list(target, ctx.scope, portable.MISSING_MEDIA)[0]['expected_sha256'] == asset['sha256']
    finally:
        delete_new_project(r, target)


def test_restored_missing_digest_is_actor_project_and_current_reference_scoped(work):
    r = work; asset, _ = add_media(r, True)
    exported = r.portable.export(r.ctx, {'chapter_ids': [r.chapter['id']]})
    imported = r.portable.preflight_import(r.ctx, upload(r.portable.download(r.ctx, exported['id'], 1)))
    restored = r.portable.restore(r.ctx, imported['id'], confirm(imported)); target = restored['target_id']
    try:
        ctx = ReadContext(target, {'mode': 'local', 'novel_id': target}, r.actor)
        foreign_actor = ReadContext(target, ctx.scope, 'different-author')
        assert r.portable.catalog(foreign_actor)['missing'][0]['expected_sha256'] is None
        missing_id = restored['id_map']['media']['a0001']
        assert r.portable._missing_metadata(r.ctx, missing_id) is None
        # A hidden current chapter cannot expose a retained import hash/count.
        restored_chapter = r.chapters.get(restored['id_map']['chapters']['c0001'])
        r.sources.chapter_reader = lambda _: [{**restored_chapter, 'hidden': True}]
        assert r.portable.catalog(ctx)['missing'] == []
    finally:
        delete_new_project(r, target)


def test_relink_report_freezes_hashes_chapter_versions_and_detects_current_change(work):
    r = work; asset, _ = add_media(r, True)
    chapter = r.chapters.get(r.chapter['id']); raw = wav_bytes(sample=101)
    row = relink_preview(r, asset, raw); report = row['relink_review']
    assert report['missing_id'] == asset['id'] and report['expected_sha256'] == asset['sha256']
    assert report['candidate_sha256'] != asset['sha256'] and report['can_confirm']
    assert report['affected_chapters'] == [{'id': chapter['id'], 'title': chapter['title'], 'version': chapter['version']}]
    assert report['conflicts'] == [{'code': 'DIGEST_MISMATCH', 'blocking': False}]
    r.chapters.save(chapter['id'], {'version': chapter['version'], 'document': chapter['document']})
    current = r.portable.records(r.ctx)['items'][0]['relink_review']
    assert current['affected_chapters'][0]['version'] == chapter['version']
    assert current['affected_chapters'][0]['current_version'] == chapter['version'] + 1
    assert not current['can_confirm'] and current['conflicts'][-1]['code'] == 'SOURCE_CHANGED'
    assert 'document' not in json.dumps(current) and 'Alice' not in json.dumps(current)
    with pytest.raises(StaleSourceError):
        r.portable.relink(r.ctx, row['id'], {**confirm(row), 'accept_different_digest': True})
    assert r.portable._owned(r.ctx, row['id'])['status'] == 'PREFLIGHT'


def test_relink_report_source_privacy_change_blocks_even_when_chapter_version_stays(work):
    r = work; asset, raw = add_media(r, True); row = relink_preview(r, asset, raw)
    chapter = r.chapters.get(r.chapter['id'])
    review_source_privacy(chapter, None, r.actor, 'CLOUD_ALLOWED', chapter['version'], content_digest(chapter), r.root)
    report = r.portable.records(r.ctx)['items'][0]['relink_review']
    assert report['affected_chapters'][0]['current_version'] == chapter['version']
    assert not report['can_confirm'] and report['conflicts'][-1]['code'] == 'SOURCE_CHANGED'
    with pytest.raises(StaleSourceError): r.portable.relink(r.ctx, row['id'], confirm(row))


@pytest.mark.parametrize('change', ['digest', 'reappeared'])
def test_relink_original_authority_change_blocks_before_any_new_asset(work, monkeypatch, change):
    r = work; asset, raw = add_media(r, True); row = relink_preview(r, asset, raw)
    before = deepcopy(r.chapters.get(r.chapter['id'])); assets = deepcopy(r.assets.list(r.nid, actor_id=r.actor))
    if change == 'digest':
        get = r.assets.get
        monkeypatch.setattr(r.assets, 'get', lambda aid, **kw: {**get(aid, **kw), 'sha256': 'b' * 64} if aid == asset['id'] else get(aid, **kw))
    else:
        (r.assets.root / (asset['id'] + '.bin')).write_bytes(raw)
    report = r.portable.records(r.ctx)['items'][0]['relink_review']
    assert not report['can_confirm'] and report['conflicts'][-1]['code'] == 'ORIGINAL_REFERENCE_CHANGED'
    with pytest.raises(StaleSourceError, match='ORIGINAL_REFERENCE_CHANGED'):
        r.portable.relink(r.ctx, row['id'], confirm(row))
    assert r.chapters.get(r.chapter['id']) == before
    assert r.assets.list(r.nid, actor_id=r.actor) == assets
    assert r.portable._owned(r.ctx, row['id'])['status'] == 'PREFLIGHT'


def test_relink_report_cannot_expose_now_hidden_asset_metadata(work, monkeypatch):
    r = work; asset, raw = add_media(r, True); row = relink_preview(r, asset, raw); get = r.assets.get
    monkeypatch.setattr(r.assets, 'get', lambda aid, **kw: {**get(aid, **kw), 'hidden': True})
    assert r.portable.records(r.ctx)['items'] == []
    with pytest.raises(FileNotFoundError): r.portable.relink(r.ctx, row['id'], confirm(row))
    assert r.portable.catalog(r.ctx)['missing'] == []


def test_partial_relink_retains_report_originals_and_measured_recovery_input(work, monkeypatch):
    r = work; asset, raw = add_media(r, True)
    second = r.chapters.create(r.nid, {'title': 'Second synthetic reference', 'content': ''})
    chapter = r.chapters.get(second['id'])
    r.chapters.save(chapter['id'], {'version': chapter['version'], 'document': {'type': 'doc', 'content': [{'type': 'audio', 'attrs': {'asset_id': asset['id']}}]}})
    before = deepcopy(r.chapters.get(second['id'])); history = deepcopy(r.chapters.history(second['id']))
    row = relink_preview(r, asset, raw, [r.chapter['id'], second['id']]); save = r.chapters.save
    def fail_second(cid, payload):
        if cid == second['id']: raise VersionConflict({**before, 'version': 99})
        return save(cid, payload)
    monkeypatch.setattr(r.chapters, 'save', fail_second)
    with pytest.raises(VersionConflict): r.portable.relink(r.ctx, row['id'], confirm(row))
    result = r.portable.records(r.ctx)['items'][0]
    assert result['status'] == 'RECOVERY_REQUIRED' and not result['relink_review']['can_confirm']
    assert len(result['relink_review']['affected_chapters']) == 2 and result['relink_review']['expected_sha256'] == asset['sha256']
    assert list(result['id_map']['chapters']) == [r.chapter['id']]
    assert r.chapters.get(second['id']) == before and r.chapters.history(second['id']) == history
    preview = r.portable.storage(r.ctx); recovery = category(preview, 'TEMPORARY_FAILED_FILES')
    assert recovery['bytes'] == 2 * len(raw) and not recovery['cleanable'] and recovery['unmeasured_records'] == 0
    assert row['id'] not in {c['id'] for c in preview['eligible']}
    assert r.assets.get(asset['id'])['sha256'] == asset['sha256']


def test_storage_measures_original_history_and_owned_inputs_without_deleting_them(work):
    r = work; asset, raw = add_media(r)
    exported = r.portable.export(r.ctx, {'chapter_ids': [r.chapter['id']]})
    body = r.portable.download(r.ctx, exported['id'], 1)
    imported = r.portable.preflight_import(r.ctx, upload(body))
    history = deepcopy(r.chapters.history(r.chapter['id'])); preview = r.portable.storage(r.ctx)
    expected = sum(len(canonical(item['document']).encode()) for item in history)
    assert category(preview, 'HISTORY')['bytes'] == expected
    assert category(preview, 'HISTORY')['measurement'] == 'AUTHORIZED_ACTIVE_CHAPTER_HISTORY_CONTENT_BYTES'
    assert category(preview, 'TEMPORARY_FAILED_FILES')['bytes'] == len(body)
    r.portable.cleanup(r.ctx, {'record_ids': [exported['id']], 'preview_digest': preview['preview_digest'], 'confirmed': True})
    assert r.portable._read_file(r.ctx, r.portable._owned(r.ctx, imported['id'])) == body
    assert r.chapters.history(r.chapter['id']) == history and r.assets.content(asset['id']) == raw
    other = ReadContext(r.nid, r.scope, 'different-author')
    assert category(r.portable.storage(other), 'TEMPORARY_FAILED_FILES')['bytes'] == 0


def test_storage_custom_reader_does_not_reach_base_history_and_unknown_inputs_are_preserved(work, monkeypatch):
    r = work; row = r.portable.export(r.ctx, {'chapter_ids': [r.chapter['id']]})
    imported = r.portable.preflight_import(r.ctx, upload(r.portable.download(r.ctx, row['id'], 1)))
    path = r.portable._file(r.ctx, imported['id']); path.write_bytes(b'changed synthetic cache')
    original = r.chapters.get(r.chapter['id']); r.sources.chapter_reader = lambda _: [original]
    def forbidden(*_): raise AssertionError('custom/branch source must not read base history')
    monkeypatch.setattr(r.chapters, 'history', forbidden)
    preview = r.portable.storage(r.ctx)
    assert category(preview, 'HISTORY')['bytes'] is None
    recovery = category(preview, 'TEMPORARY_FAILED_FILES')
    assert recovery['bytes'] == 0 and recovery['unmeasured_records'] == 1
    assert path.read_bytes() == b'changed synthetic cache' and imported['id'] not in {r['id'] for r in preview['eligible']}


def test_mounted_relink_report_and_original_changed_conflict_stay_public_safe(tools):
    e = tools; base = e.base + '/portable-projects'; raw = wav_bytes()
    asset = e.assets.create(e.nid, 'synthetic.wav', base64.b64encode(raw).decode(), 'audio/wav', 'audio')
    chapter = e.chapters.get(e.chapter['id']); chapter['document']['content'].append({'type': 'audio', 'attrs': {'asset_id': asset['id']}})
    e.chapters.save(chapter['id'], {'version': chapter['version'], 'document': chapter['document']})
    (e.assets.root / (asset['id'] + '.bin')).unlink()
    row = checked(e.client.post(base + '/relink-preflight', json={**upload(raw, 'moved.wav'), 'kind': 'audio', 'missing_id': asset['id'], 'chapter_ids': [chapter['id']]}))
    assert row['relink_review']['expected_sha256'] == row['relink_review']['candidate_sha256'] == asset['sha256']
    assert row['relink_review']['affected_chapters'][0]['version'] == chapter['version'] + 1
    (e.assets.root / (asset['id'] + '.bin')).write_bytes(raw)
    conflict = e.client.post(base + f"/records/{row['id']}/relink", json=confirm(row))
    assert conflict.status_code == 409 and conflict.json()['detail']['message'] == 'PORTABLE_ORIGINAL_REFERENCE_CHANGED'
    response = e.client.get(base + '/records'); report = checked(response)['items'][0]['relink_review']
    assert response.headers['cache-control'] == 'no-store' and not report['can_confirm']
    assert 'document' not in response.text and 'content_base64' not in response.text and str(e.root) not in response.text


def test_unknown_digest_needs_explicit_choice_and_older_record_requires_new_preflight(work):
    r = work; current = r.chapters.get(r.chapter['id'])
    current['document']['content'].append({'type': 'audio', 'attrs': {'asset_id': 'missing-unknown'}})
    r.chapters.save(current['id'], {'version': current['version'], 'document': current['document']})
    row = relink_preview(r, {'id': 'missing-unknown'}, wav_bytes())
    assert row['relink_review']['expected_sha256'] is None
    assert row['relink_review']['conflicts'] == [{'code': 'ORIGINAL_DIGEST_UNKNOWN', 'blocking': False}]
    with pytest.raises(ValueError, match='EXPLICIT_REPLACEMENT'):
        r.portable.relink(r.ctx, row['id'], confirm(row))
    with r.store.transaction(r.nid, r.scope) as state:
        state['collections'][r.portable.RECORDS][row['id']].pop('relink_review')
    report = r.portable.records(r.ctx)['items'][0]['relink_review']
    assert not report['can_confirm'] and report['conflicts'][0]['code'] == 'PREFLIGHT_REQUIRED'
    with pytest.raises(StaleSourceError, match='PREFLIGHT_REQUIRED'):
        r.portable.relink(r.ctx, row['id'], {**confirm(row), 'accept_different_digest': True})


def test_original_reference_is_rechecked_at_actual_chapter_write_boundary(work, monkeypatch):
    r = work; asset, raw = add_media(r, True); row = relink_preview(r, asset, raw)
    before = deepcopy(r.chapters.get(r.chapter['id'])); create = r.assets.create
    def reappeared(*args, **kwargs):
        result = create(*args, **kwargs)
        (r.assets.root / (asset['id'] + '.bin')).write_bytes(raw)
        return result
    monkeypatch.setattr(r.assets, 'create', reappeared)
    with pytest.raises(StaleSourceError, match='ORIGINAL_REFERENCE_CHANGED'):
        r.portable.relink(r.ctx, row['id'], confirm(row))
    assert r.chapters.get(r.chapter['id']) == before
    result = r.portable.records(r.ctx)['items'][0]
    assert result['status'] == 'RECOVERY_REQUIRED' and result['id_map']['chapters'] == {}
    assert r.assets.content(asset['id']) == raw
