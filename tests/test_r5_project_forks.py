"""B09 actual original File / opted-in PostgreSQL, no manuscript store doubles."""
import base64
from copy import deepcopy
from dataclasses import replace
import os
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from app.config import Settings
from app.experimental.common import StaleSourceError
from app.experimental.flags import FLAGS
from app.experimental.project_forks import ProjectForksService, block_merge, rich_document
from app.experimental.store import ExperimentalStore
from app.experimental.ux import ReadContext
from app.experimental.writing_focus import WritingFocusService
from app.repositories.factory import create_repository_bundle
from app.revision_constraints import LOCK_ATTRIBUTE, node_digest
from app.services import ChapterService, NovelService
from app.services.asset_library_service import AssetLibraryService
from app.services.v1_capability_service import CapabilityVersionConflict
from test_r3_media_support import wav_bytes


def paragraph(text, **extra): return {'type': 'paragraph', 'content': [{'type': 'text', 'text': text}], **extra}
def document(*texts): return {'type': 'doc', 'content': [{'type': 'heading', 'attrs': {'level': 1}, 'content': [{'type': 'text', 'text': 'Original title'}]}] + [paragraph(t) for t in texts]}
def confirmation(row): return {'expected_version': row['version'], 'preview_digest': row['preview_digest'], 'confirmed': True}


@pytest.fixture(params=[pytest.param('file', marks=pytest.mark.file_backend_only), pytest.param('postgres', marks=pytest.mark.postgres_backend_only)])
def env(request, tmp_path, monkeypatch):
    backend = request.param; url = os.getenv('TEST_POSTGRES_DATABASE_URL', '') if backend == 'postgres' else ''
    if backend == 'postgres' and not url: pytest.fail('real PostgreSQL B09 contracts require TEST_POSTGRES_DATABASE_URL')
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', ','.join(FLAGS)); monkeypatch.setenv('V1_ACCEPTANCE_MODE', 'false')
    bundle = create_repository_bundle(Settings(storage_backend=backend, database_url=url, novel_data=tmp_path), data_root=tmp_path)
    novels, chapters = NovelService(bundle.novels, bundle.chapters), ChapterService(bundle.chapters)
    nid = 'fork-test-' + uuid4().hex; novels.create({'id': nid, 'title': 'Synthetic fork'})
    chapter = chapters.create(nid, {'title': 'Original title', 'content': 'Synthetic only'})
    chapter = chapters.save(chapter['id'], {'version': chapters.get(chapter['id'])['version'], 'document': document('One', 'Two', 'Three')})
    store = ExperimentalStore(tmp_path, backend, url); sources = WritingFocusService(store, novels, chapters); assets = AssetLibraryService(tmp_path)
    service = ProjectForksService(store, novels, chapters, sources=sources, assets=assets)
    e = SimpleNamespace(service=service, store=store, chapters=chapters, novels=novels, assets=assets, nid=nid, cid=chapter['id'], ctx=ReadContext(nid, {'mode': 'local', 'novel_id': nid}, 'local-author'))
    yield e
    # Only this fixture's generated synthetic projects. Never user projects.
    targets = [r['target_id'] for r in store.read(nid, e.ctx.scope)['collections'].get(service.FORKS, {}).values()]
    for target in targets:
        try: novels.delete(target)
        except FileNotFoundError: pass
    if backend == 'postgres':
        with store._connect() as conn: conn.execute('DELETE FROM experimental_scope_documents WHERE novel_id = %s', (nid,))
        novels.delete(nid); bundle.novels.database.engine.dispose()


def create(e, ids=None, permissions=None):
    preview = e.service.preflight(e.ctx, {'chapter_ids': ids or [e.cid], 'title': 'Reviewed synthetic fork', 'asset_permissions': permissions or []})
    assert preview['status'] == 'PREFLIGHT'
    return e.service.create_fork(e.ctx, preview['id'], confirmation(preview))


def mutate(e, cid, fn):
    current = e.chapters.get(cid); doc = deepcopy(current['document']); fn(doc)
    return e.chapters.save(cid, {'version': current['version'], 'document': doc})


def compare(e, row, choices=None): return e.service.compare(e.ctx, row['id'], {'expected_version': row['version'], 'choices': choices or {}})
def writers(e): return {'save_document': lambda cid, doc, version, source: e.chapters.save(cid, {'version': version, 'document': doc, 'source': source}), 'archive_chapter': e.chapters.archive, 'restore_archive': e.chapters.restore_archive}
def apply(e, row, preview, choices=None, **kwargs): return e.service.apply(e.ctx, row['id'], {'expected_version': row['version'], 'preview_digest': preview['preview_digest'], 'confirmed': True, 'choices': choices or {}}, **(writers(e) | kwargs))


def test_selected_fork_preserves_rich_marks_locks_and_stable_mapping(env):
    e = env
    def rich(doc):
        doc['content'][1]['content'][0]['marks'] = [{'type': 'bold'}, {'type': 'italic'}]
        node = doc['content'][2]; node['attrs'] = {LOCK_ATTRIBUTE: {'id': 'synthetic-lock', 'state': 'LOCKED', 'digest': node_digest(node)}}
    mutate(e, e.cid, rich); before = e.chapters.get(e.cid); history = e.chapters.history(e.cid)
    extra = e.chapters.create(e.nid, {'title': 'Unselected', 'content': 'Must not copy'})
    row = create(e); copied = e.chapters.get(row['id_map']['chapters'][e.cid])
    assert copied['document'] == before['document'] and copied['id'] != e.cid
    assert list(row['id_map']['chapters']) == [e.cid] and len(e.chapters.list(row['target_id'])) == 1
    assert e.chapters.get(e.cid) == before and e.chapters.history(e.cid) == history
    assert e.chapters.get(extra['id']) and row['status'] == 'FORKED'
    raw = e.service._owned(e.ctx, e.service.FORKS, row['id']); assert all(j['status'] == 'DONE' for j in raw['journal'])
    assert all('baseline' not in h for h in raw['history'])
    with pytest.raises(ValueError): e.service.create_fork(e.ctx, row['id'], confirmation(row))


def test_bilateral_same_block_requires_per_conflict_choice_and_new_history(env):
    e = env; row = create(e); target = row['id_map']['chapters'][e.cid]
    mutate(e, e.cid, lambda d: d['content'].__setitem__(1, paragraph('Original edit')))
    mutate(e, target, lambda d: d['content'].__setitem__(1, paragraph('Fork edit')))
    preview = compare(e, row); assert preview['unresolved'] == 1 and not preview['can_apply']
    with pytest.raises(ValueError, match='UNRESOLVED'): apply(e, row, preview)
    conflict = preview['chapters'][0]['segments'][0]; assert conflict['base'][0] == paragraph('One')
    choice = {conflict['id']: 'FORK'}; reviewed = compare(e, row, choice); assert reviewed['can_apply']
    old = e.chapters.get(e.cid); done = apply(e, row, reviewed, choice)
    assert done['status'] == 'COMPLETED' and e.chapters.get(e.cid)['document']['content'][1] == paragraph('Fork edit')
    assert any(v['version'] == old['version'] and v['document'] == old['document'] for v in e.chapters.history(e.cid))
    assert e.chapters.get(target)['document']['content'][1] == paragraph('Fork edit')
    with pytest.raises(CapabilityVersionConflict): apply(e, row, reviewed, choice)


def test_unilateral_and_disjoint_changes_merge_without_last_write_wins(env):
    e = env; row = create(e); target = row['id_map']['chapters'][e.cid]
    mutate(e, e.cid, lambda d: d['content'].__setitem__(1, paragraph('Original one')))
    mutate(e, target, lambda d: d['content'].__setitem__(3, paragraph('Fork three')))
    preview = compare(e, row); assert preview['unresolved'] == 0
    apply(e, row, preview); nodes = e.chapters.get(e.cid)['document']['content']
    assert nodes[1] == paragraph('Original one') and nodes[3] == paragraph('Fork three')


def test_rename_and_delete_modify_conflicts_are_explicit_and_archive_recoverable(env):
    e = env; row = create(e); target = row['id_map']['chapters'][e.cid]
    e.chapters.rename(e.cid, 'Original rename', e.chapters.get(e.cid)['version'])
    e.chapters.rename(target, 'Fork rename', e.chapters.get(target)['version'])
    preview = compare(e, row); conflict = preview['chapters'][0]['segments'][0]
    assert conflict['reason'] == 'RENAME_OR_HEADING'
    e.chapters.archive(target, e.chapters.get(target)['version'])
    preview = compare(e, row); assert preview['unresolved'] == 1
    conflict = preview['chapters'][0]['segments'][0]; assert conflict['reason'] == 'CHAPTER_DELETION_OR_DELETE_MODIFY'
    choice = {conflict['id']: 'FORK'}; reviewed = compare(e, row, choice); done = apply(e, row, reviewed, choice)
    assert e.chapters.get(e.cid)['is_archived'] and e.novels.get(e.nid) and e.novels.get(row['target_id'])
    recovery = e.service.recovery(e.ctx, done['id'], {'expected_version': done['version']})
    assert recovery['can_restore']
    result = e.service.restore_checkpoint(e.ctx, done['id'], {'expected_version': done['version'], 'preview_digest': recovery['preview_digest'], 'confirmed': True}, **writers(e))
    assert result['status'] == 'RESTORED' and not e.chapters.get(e.cid)['is_archived']
    assert e.chapters.get(e.cid)['title'] == 'Original rename'


@pytest.mark.parametrize('side', ['source', 'target'])
def test_original_and_fork_version_drift_invalidate_review(env, side):
    e = env; row = create(e); target = row['id_map']['chapters'][e.cid]
    mutate(e, target, lambda d: d['content'].__setitem__(1, paragraph('Fork one')))
    preview = compare(e, row); cid = e.cid if side == 'target' else target
    mutate(e, cid, lambda d: d['content'].__setitem__(3, paragraph('Newer author write')))
    before = e.chapters.get(e.cid)
    with pytest.raises(StaleSourceError): apply(e, row, preview)
    assert e.chapters.get(e.cid) == before and not e.store.read(e.nid, e.ctx.scope)['collections'].get(e.service.MERGES)


def test_preflight_source_drift_and_authority_revocation_preserve_original(env):
    e = env; pre = e.service.preflight(e.ctx, {'chapter_ids': [e.cid], 'title': 'Selected'})
    mutate(e, e.cid, lambda d: d['content'].__setitem__(1, paragraph('newer')))
    with pytest.raises(StaleSourceError): e.service.create_fork(e.ctx, pre['id'], confirmation(pre))
    row = create(e); target = row['id_map']['chapters'][e.cid]
    mutate(e, target, lambda d: d['content'].__setitem__(3, paragraph('Fork edit')))
    preview = compare(e, row); before = e.chapters.get(e.cid)
    def denied(): raise HTTPException(403, 'revoked')
    with pytest.raises(HTTPException): apply(e, row, preview, reauthorize=denied)
    assert e.chapters.get(e.cid) == before


def test_lock_changes_block_without_silent_mark_flattening(env):
    e = env
    def lock(doc):
        node = doc['content'][1]; node['attrs'] = {LOCK_ATTRIBUTE: {'id': 'lock', 'state': 'LOCKED', 'digest': node_digest(node)}}
    mutate(e, e.cid, lock); row = create(e); target = row['id_map']['chapters'][e.cid]
    mutate(e, target, lambda d: d['content'][1]['content'][0].update(text='Fork manual change'))
    preview = compare(e, row)
    assert not preview['can_apply'] and preview['blocked'][0]['code'] == 'FORK_LOCKED_PARAGRAPH_CHANGE'
    with pytest.raises(ValueError): apply(e, row, preview)
    with pytest.raises(ValueError, match='UNSUPPORTED'):
        rich_document({'type': 'doc', 'content': [{'type': 'characterReference', 'attrs': {'character_id': 'must-map'}}]})
    with pytest.raises(ValueError, match='UNSUPPORTED'):
        rich_document({'type': 'doc', 'content': [{'type': 'paragraph', 'content': [{'type': 'text', 'text': 'link', 'marks': [{'type': 'link', 'attrs': {'href': 'javascript:x'}}]}]}]})


def test_interrupted_multi_write_has_checkpoint_and_no_replay_then_explicit_restore(env):
    e = env; second = e.chapters.create(e.nid, {'title': 'Second', 'content': 'Before second'})
    row = create(e, [e.cid, second['id']]); checkpoint = {cid: e.chapters.get(cid)['document'] for cid in row['id_map']['chapters']}
    for target in row['id_map']['chapters'].values(): mutate(e, target, lambda d: d['content'].append(paragraph('fork append')))
    preview = compare(e, row); count = 0; write = writers(e)['save_document']
    def interrupted(*args):
        nonlocal count
        count += 1
        if count == 2: raise RuntimeError('synthetic interruption')
        return write(*args)
    with pytest.raises(RuntimeError): apply(e, row, preview, save_document=interrupted)
    raw = list(e.store.read(e.nid, e.ctx.scope)['collections'][e.service.MERGES].values())[0]
    assert raw['status'] == 'RECOVERY_REQUIRED' and [j['status'] for j in raw['journal']] == ['DONE', 'CLAIMED']
    before = deepcopy(e.chapters.get(e.cid))
    with pytest.raises(CapabilityVersionConflict): apply(e, row, preview)
    assert e.chapters.get(e.cid) == before and count == 2
    recovery = e.service.recovery(e.ctx, raw['id'], {'expected_version': raw['version']})
    assert {r['state'] for r in recovery['observations']} == {'CONFIRMED_RECEIPT', 'CHECKPOINT_UNCHANGED'}
    restored = e.service.restore_checkpoint(e.ctx, raw['id'], {'expected_version': raw['version'], 'preview_digest': recovery['preview_digest'], 'confirmed': True}, **writers(e))
    assert restored['status'] == 'RESTORED'
    assert all(e.chapters.get(cid)['document'] == doc for cid, doc in checkpoint.items())


def test_write_then_unknown_receipt_is_never_retried_and_recovery_detects_it(env):
    e = env; row = create(e); mutate(e, row['id_map']['chapters'][e.cid], lambda d: d['content'].append(paragraph('intent')))
    preview = compare(e, row); write = writers(e)['save_document']; count = 0
    def unknown(*args):
        nonlocal count
        count += 1; write(*args); raise RuntimeError('lost acknowledgement')
    with pytest.raises(RuntimeError): apply(e, row, preview, save_document=unknown)
    raw = list(e.store.read(e.nid, e.ctx.scope)['collections'][e.service.MERGES].values())[0]
    recovery = e.service.recovery(e.ctx, raw['id'], {'expected_version': raw['version']})
    assert recovery['observations'][0]['state'] == 'MATCHES_INTENT_UNCONFIRMED' and raw['journal'][0]['status'] == 'CLAIMED'
    with pytest.raises(CapabilityVersionConflict): apply(e, row, preview, save_document=unknown)
    assert count == 1
    # Newer author edits invalidate even a separately approved recovery preview.
    mutate(e, e.cid, lambda d: d['content'].append(paragraph('after recovery preview')))
    with pytest.raises(StaleSourceError): e.service.restore_checkpoint(e.ctx, raw['id'], {'expected_version': raw['version'], 'preview_digest': recovery['preview_digest'], 'confirmed': True}, **writers(e))


def test_process_exit_leaves_durable_claim_and_unavailable_automatic_replay(env):
    e = env; row = create(e); mutate(e, row['id_map']['chapters'][e.cid], lambda d: d['content'].append(paragraph('intent')))
    preview = compare(e, row)
    def stopped(*args): raise SystemExit('synthetic process exit')
    with pytest.raises(SystemExit): apply(e, row, preview, save_document=stopped)
    raw = list(e.store.read(e.nid, e.ctx.scope)['collections'][e.service.MERGES].values())[0]
    assert raw['status'] == 'APPLYING' and raw['journal'][0]['status'] == 'CLAIMED'
    current_fork = e.service._owned(e.ctx, e.service.FORKS, row['id'])
    with pytest.raises(ValueError, match='RECOVERY'): compare(e, current_fork)
    assert e.service.recovery(e.ctx, raw['id'], {'expected_version': raw['version']})['no_automatic_retry']


def test_asset_license_id_map_provenance_and_unsupported_cross_reference(env):
    e = env; asset = e.assets.create(e.nid, 'synthetic.wav', base64.b64encode(wav_bytes()).decode(), 'audio/wav', 'audio')
    mutate(e, e.cid, lambda d: d['content'].append({'type': 'audio', 'attrs': {'asset_id': asset['id']}}))
    with pytest.raises(ValueError, match='LICENSE_REQUIRED'): create(e)
    permissions = [{'asset_id': asset['id'], 'version': asset['version'], 'sha256': asset['sha256'], 'license': 'Synthetic author-owned test media', 'allow_local_copy': True}]
    row = create(e, permissions=permissions); copied = row['id_map']['assets'][asset['id']]
    assert copied != asset['id'] and e.assets.content(copied) == e.assets.content(asset['id'])
    provenance = e.assets.get(copied)['_origin_provenance']; assert provenance['source_asset_id'] == asset['id'] and provenance['source_sha256'] == asset['sha256']
    assert compare(e, row)['write_count'] == 0
    target = row['id_map']['chapters'][e.cid]
    foreign = e.assets.create(row['target_id'], 'new.wav', base64.b64encode(wav_bytes(sample=999)).decode(), 'audio/wav', 'audio')
    mutate(e, target, lambda d: d['content'].append({'type': 'audio', 'attrs': {'asset_id': foreign['id']}}))
    with pytest.raises(ValueError, match='UNDECLARED_MEDIA'): compare(e, row)


def test_collaboration_scope_never_reads_local_chapters(env):
    e = env; scope = {'mode': 'collaboration', 'novel_id': e.nid, 'workspace_id': 'workspace', 'storyline_id': 'storyline', 'branch_id': 'branch'}
    ctx = replace(e.ctx, scope=scope, branch='branch')
    assert e.service.catalog(ctx)['chapters'] == []
    with pytest.raises(ValueError, match='COLLABORATION'): e.service.preflight(ctx, {'chapter_ids': [e.cid], 'title': 'Forbidden'})
    assert not e.store.read(e.nid, scope)['collections']


@pytest.mark.parametrize('left,right', [([paragraph('A')], [paragraph('B')]), ([], [paragraph('A')]), ([paragraph('A'), paragraph('B')], [paragraph('A'), paragraph('C'), paragraph('D')])])
def test_diff3_unilateral_projection_law(left, right):
    for original, fork, expected in [(right, left, right), (left, right, right), (right, right, right)]:
        segments = block_merge(left, original, fork); output = []
        for seg in segments:
            assert seg['kind'] != 'CONFLICT'
            output.extend(seg['nodes'] if seg['kind'] == 'UNCHANGED' else seg['ORIGINAL'] if seg['kind'] == 'ORIGINAL_ONLY' else seg['FORK'])
        assert output == expected


def test_concurrent_apply_claim_allows_one_original_write(env):
    from concurrent.futures import ThreadPoolExecutor
    import threading
    e = env; row = create(e); mutate(e, row['id_map']['chapters'][e.cid], lambda d: d['content'].append(paragraph('single accepted change')))
    preview = compare(e, row); entered = threading.Event(); release = threading.Event(); writes = []
    save = writers(e)['save_document']
    def paused(*args):
        entered.set(); assert release.wait(5); writes.append(args[0]); return save(*args)
    def competing():
        try: return apply(e, row, preview, save_document=paused)['status']
        except (CapabilityVersionConflict, ValueError): return 'CONFLICT'
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(competing); assert entered.wait(5)
        second = pool.submit(competing); release.set()
        assert sorted([first.result(timeout=10), second.result(timeout=10)]) == ['COMPLETED', 'CONFLICT']
    assert writes == [e.cid]


def test_current_source_authority_checked_again_between_writes(env):
    e = env; second = e.chapters.create(e.nid, {'title': 'Two', 'content': 'untouched'})
    row = create(e, [e.cid, second['id']])
    for cid in row['id_map']['chapters'].values(): mutate(e, cid, lambda d: d['content'].append(paragraph('fork edit')))
    preview = compare(e, row); allowed = [True]; calls = []; save = writers(e)['save_document']
    def guard():
        if not allowed[0]: raise HTTPException(403, 'revoked')
    def revoke(*args):
        calls.append(args[0]); result = save(*args); allowed[0] = False; return result
    with pytest.raises(HTTPException): apply(e, row, preview, save_document=revoke, reauthorize=guard)
    assert calls == [e.cid] and 'fork edit' not in e.chapters.get(second['id'])['content']
    raw = list(e.store.read(e.nid, e.ctx.scope)['collections'][e.service.MERGES].values())[0]
    assert raw['status'] == 'RECOVERY_REQUIRED' and raw['checkpoint'][second['id']]['document']


def test_failed_new_project_fork_is_visible_without_duplicate_create(env, monkeypatch):
    e = env; preview = e.service.preflight(e.ctx, {'chapter_ids': [e.cid], 'title': 'Interrupted new target'})
    original = e.chapters.save
    def fail(*args, **kwargs): raise RuntimeError('synthetic copied document failure')
    monkeypatch.setattr(e.chapters, 'save', fail)
    with pytest.raises(RuntimeError): e.service.create_fork(e.ctx, preview['id'], confirmation(preview))
    raw = e.service._owned(e.ctx, e.service.FORKS, preview['id'])
    assert raw['status'] == 'RECOVERY_REQUIRED' and e.novels.get(raw['target_id'])
    assert raw['id_map']['chapters'][e.cid] and raw['journal'][-1]['status'] == 'CLAIMED'
    with pytest.raises(CapabilityVersionConflict): e.service.create_fork(e.ctx, preview['id'], confirmation(preview))
    assert len(e.novels.list()) == 2
    monkeypatch.setattr(e.chapters, 'save', original)


def test_media_digest_or_source_version_drift_blocks_fork_and_compare(env):
    e = env; asset = e.assets.create(e.nid, 'media.wav', base64.b64encode(wav_bytes()).decode(), 'audio/wav', 'audio')
    mutate(e, e.cid, lambda d: d['content'].append({'type': 'audio', 'attrs': {'asset_id': asset['id']}}))
    permission = {'asset_id': asset['id'], 'version': asset['version'], 'sha256': asset['sha256'], 'license': 'Synthetic author-owned', 'allow_local_copy': True}
    row = create(e, permissions=[permission]); target = row['id_map']['assets'][asset['id']]
    e.assets.update_metadata(target, {'parameters': {'changed': True}}, expected_version=e.assets.get(target)['version'])
    with pytest.raises(StaleSourceError, match='TARGET_ASSET'): compare(e, row)


def test_preflight_legacy_file_projection_does_not_materialize_documents(env):
    if not isinstance(env.chapters.repository, __import__('app.repositories.file.chapter', fromlist=['FileChapterRepository']).FileChapterRepository):
        # PostgreSQL has no lazy document materialization; its read-only check
        # is the unchanged original version/history assertion below.
        before = env.chapters.get(env.cid); history = env.chapters.history(env.cid)
        env.service.preflight(env.ctx, {'chapter_ids': [env.cid], 'title': 'Pure PG preflight'})
        assert env.chapters.get(env.cid) == before and env.chapters.history(env.cid) == history
        return
    e = env; created = e.chapters.create(e.nid, {'title': 'Legacy', 'content': 'Preserve original bytes'})
    path = e.chapters.repository._paths(created['id'])[2]; assert not path.exists()
    e.service.preflight(e.ctx, {'chapter_ids': [created['id']], 'title': 'Pure read preflight'})
    assert not path.exists()


def test_write_acknowledgement_without_changed_original_is_not_success(env):
    e = env; row = create(e); mutate(e, row['id_map']['chapters'][e.cid], lambda d: d['content'].append(paragraph('intended')))
    preview = compare(e, row)
    with pytest.raises(StaleSourceError, match='RECEIPT_UNCERTAIN'):
        apply(e, row, preview, save_document=lambda cid, *_: e.chapters.get(cid))
    raw = list(e.store.read(e.nid, e.ctx.scope)['collections'][e.service.MERGES].values())[0]
    assert raw['status'] == 'RECOVERY_REQUIRED' and raw['journal'][0]['status'] == 'ACKNOWLEDGED'
    recovery = e.service.recovery(e.ctx, raw['id'], {'expected_version': raw['version']})
    assert recovery['observations'][0]['state'] == 'CHECKPOINT_UNCHANGED'


def test_catalog_missing_media_does_not_block_unrelated_selected_chapters(env):
    e = env; bad = e.chapters.create(e.nid, {'title': 'Missing media', 'content': 'synthetic'})
    mutate(e, bad['id'], lambda d: d['content'].append({'type': 'audio', 'attrs': {'asset_id': 'missing-synthetic'}}))
    catalog = e.service.catalog(e.ctx)
    assert catalog['available'] and not catalog['assets'][0]['available']
    assert catalog['assets'][0]['filename'] == '不可用媒体引用'
    assert create(e)['status'] == 'FORKED'


def test_original_checkpoint_restore_survives_lost_or_revoked_fork(env):
    e = env; row = create(e); before = e.chapters.get(e.cid)['document']
    mutate(e, row['id_map']['chapters'][e.cid], lambda d: d['content'].append(paragraph('fork change')))
    done = apply(e, row, compare(e, row)); e.novels.delete(row['target_id'])
    def fork_unavailable(_): raise HTTPException(403, 'fork authority revoked')
    preview = e.service.recovery(e.ctx, done['id'], {'expected_version': done['version']}, target_authorize=fork_unavailable)
    assert preview['can_restore']
    restored = e.service.restore_checkpoint(e.ctx, done['id'], {'expected_version': done['version'], 'preview_digest': preview['preview_digest'], 'confirmed': True}, target_authorize=fork_unavailable, **writers(e))
    assert restored['status'] == 'RESTORED' and e.chapters.get(e.cid)['document'] == before
    assert not e.service.records(e.ctx, target_authorize=fork_unavailable)['items'][0]['target_available']
