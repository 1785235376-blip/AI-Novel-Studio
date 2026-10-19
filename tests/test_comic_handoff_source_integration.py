"""Actual Host/File HTTP and borrowed original phases; synthetic PNGs, no models."""
import base64
import copy
from contextlib import contextmanager
import hashlib
import io

from PIL import Image
import pytest

from test_r3_mounted_contracts import mounted, prefix, scoped, checked
from test_v2_independent_workspace_api import client
from test_comic_timeline_handoff_http import handoff_http, collaborative, counts
from test_comic_page_source_contract import source, request, empty_handles, effects

pytestmark = [pytest.mark.file_backend_only,
              pytest.mark.parametrize('mounted', ['file'], indirect=True),
              pytest.mark.parametrize('prefix', ['/api'], indirect=True)]


@pytest.fixture
def trusted_source_handoff(handoff_http):
    """For direct-service regressions: actual canonical File/Host/NOVEL owner.

    Service calls run on the same thread inside the original binding lease;
    mounted HTTP calls belong outside this fixture's held lease.
    """
    e = handoff_http
    e.raw_store, e.service = e.store, e.studio
    e.actor, actual_scope = e.api._workbench_authorize(e.nid, e.host, e.headers.get('X-Branch-ID'), 'domain.read')
    assert actual_scope == e.scope
    with e.comic.page_source_authority(request(e), e.nid, e.host, e.headers.get('X-Branch-ID')):
        yield e, e.production.comic_handoff


def intent(e, key='external-page'):
    aid, raw, row, review = source(e)
    body = {'title': 'SYNTHETIC original image draft', 'width': 640, 'height': 360, 'fps': 24,
            'pages': [{'id': row['id'], 'version': row['version'], 'review_digest': review, 'duration_ms': 6500}]}
    before = effects(e)
    report = checked(e.client.post(e.handoff_base + '/preview', headers=e.headers, json=body))
    assert effects(e) == before
    png = base64.b64decode(report['pages'][0]['png_base64'], validate=True)
    with Image.open(io.BytesIO(png)) as image:
        image.load()
        assert image.size == (320, 640) and image.getpixel((80, 120)) == (17, 34, 51)
        assert image.getpixel((200, 400)) == (255, 255, 255)
    return aid, row, png, {'request_id': key, 'request': body,
        'reviewed_preview_digest': report['preview']['preview_digest'], 'acknowledge_losses': True}


def fresh_owners(e, monkeypatch):
    """Reopen actual File stores/Asset/Comic while retaining the mounted router."""
    from app.creative.service import CreativeService
    from app.creative.graph_asset_inputs import GraphAssetInputs
    from app.experimental.store import ExperimentalStore
    from app.experimental.comic_layouts import ComicLayoutsService
    from app.services.asset_library_service import AssetLibraryService
    raw = ExperimentalStore(e.root, e.backend, e.url)
    creative = CreativeService(raw, e.novels, e.chapters)
    assets = AssetLibraryService(e.root)
    comic = ComicLayoutsService(raw, e.novels, e.chapters, e.screenplays, assets,
                                independent_store=creative.store)
    assert assets is not e.assets and raw is not e.store and comic is not e.comic
    for name, value in (('creative', creative), ('store', creative.store), ('assets', assets)):
        monkeypatch.setattr(e.studio, name, value)
    monkeypatch.setattr(e.production, 'store', creative.store)
    monkeypatch.setattr(e.production, 'timeline_inputs', GraphAssetInputs(e.production))
    monkeypatch.setattr(e.production, 'comic_images', None)
    monkeypatch.setattr(e.production, 'comic_handoff', None)
    monkeypatch.setattr(e.experimental, 'comic_layouts_service', comic)
    monkeypatch.setattr(e.api, 'asset_library_service', assets)
    e.production.configure_comic(comic)
    e.assets, e.store, e.comic = assets, raw, comic


def save(e, created):
    timeline = created['timeline']
    return e.client.put(e.production_base + '/timelines/' + timeline['id'], headers=e.headers,
        json={'expected_version': timeline['version'], 'title': 'SYNTHETIC saved image draft',
              'timeline': timeline['timeline']})


def test_real_image_confirm_save_and_fresh_http_readback(handoff_http, monkeypatch):
    e = handoff_http
    aid, page, png, value = intent(e)
    created = checked(e.client.post(e.handoff_base, headers=e.headers, json=value))
    assert created['status'] == 'DRAFT_CREATED' and counts(e) == (2, 1, 1)
    assert not created['approval_inherited'] and not created['video_rendered']
    edited = checked(save(e, created)); assert edited['version'] == 2
    fresh_owners(e, monkeypatch)
    readback = checked(e.client.get(e.handoff_base + '/external-page', headers=e.headers))
    assert readback['timeline'] == edited and readback['timeline_state'] == 'MODIFIED_AFTER_CREATION'
    assert readback['timeline_snapshot'] == created['timeline_snapshot']
    with e.studio._asset_scope(e.nid, e.scope):
        with pytest.raises(FileNotFoundError): e.assets.get(aid)
        derived = e.assets.get(created['steps'][0]['asset_id'])
        assert e.assets.content(derived['id'], max_bytes=len(png)) == png
        assert derived['_comic_page_origin']['source']['id'] == page['id']
    assert counts(e) == (2, 1, 1)
    empty_handles(e)


def test_borrowed_grant_requires_original_locks_and_preserves_target_binding(handoff_http):
    e = handoff_http
    aid, raw, row, review = source(e); req = request(e); before = effects(e)
    with e.comic.page_source_authority(req, e.nid, e.host) as authority:
        with pytest.raises(ValueError, match='^COMIC_SOURCE_ORIGINAL_PHASE_REQUIRED$'):
            with e.comic.page_source_reader_in_phase(authority, row['id'], row['version'], review): pass
        with e.store.transaction(e.nid, e.scope):
            with pytest.raises(ValueError, match='^COMIC_SOURCE_ORIGINAL_PHASE_REQUIRED$'):
                with e.comic.page_source_reader_in_phase(authority, row['id'], row['version'], review): pass
        with e.production.timeline_inputs.phase(e.nid, e.scope, 'local-author', lambda: None):
            binding = e.assets._scope.binding; pinned = copy.deepcopy(binding)
            with e.comic.page_source_reader_in_phase(authority, row['id'], row['version'], review) as handle:
                with pytest.raises(FileNotFoundError): e.assets.get(aid)
                assert e.assets.page_source_content(handle, req, aid, max_bytes=len(raw)) == raw
                assert e.assets._scope.binding is binding and binding == pinned
        with pytest.raises(ValueError, match='^COMIC_SOURCE_HANDLE_INVALID$'):
            e.assets.page_source_metadata(handle, req, aid)
    assert effects(e) == before
    empty_handles(e)


def test_image_orphan_png_requires_explicit_resume_then_save_reopen(handoff_http, monkeypatch):
    e = handoff_http
    _, _, png, value = intent(e, 'image-orphan')
    def interrupted(*args, **kwargs): raise OSError('SYNTHETIC pre-metadata interruption')
    with monkeypatch.context() as patch:
        patch.setattr(e.assets, 'create', interrupted)
        assert e.client.post(e.handoff_base, headers=e.headers, json=value).status_code == 503
    observed = checked(e.client.get(e.handoff_base + '/image-orphan', headers=e.headers))
    assert observed['status'] == 'PLANNED' and observed['version'] == 1
    aid = observed['steps'][0]['asset_id']
    assert not e.assets._meta_path(aid).exists() and not e.assets._bin_path(aid).exists()
    e.assets._bin_path(aid).write_bytes(png)  # Actual unindexed crash artifact, not a cached source reader.
    fresh_owners(e, monkeypatch)
    before = effects(e)
    observed = checked(e.client.get(e.handoff_base + '/image-orphan', headers=e.headers))
    assert observed['steps'][0]['observed_state'] == 'UNINDEXED_BYTES_AWAITING_EXPLICIT_RESUME'
    assert effects(e) == before and counts(e) == (2, 0, 1)
    created = checked(e.client.post(e.handoff_base + '/image-orphan/resume', headers=e.headers,
                                    json={'expected_version': observed['version']}))
    assert created['status'] == 'DRAFT_CREATED' and created['steps'][0]['asset_id'] == aid
    edited = checked(save(e, created)); assert edited['version'] == 2
    fresh_owners(e, monkeypatch)
    readback = checked(e.client.get(e.handoff_base + '/image-orphan', headers=e.headers))
    assert readback['timeline'] == edited and readback['timeline_snapshot'] == created['timeline_snapshot']
    with e.studio._asset_scope(e.nid, e.scope):
        assert e.assets.content(aid, max_bytes=len(png)) == png
    assert counts(e) == (2, 1, 1)
    empty_handles(e)


def test_image_lost_reply_after_real_commit_reads_back_without_replay(handoff_http, monkeypatch):
    from app.experimental.comic_timeline_handoff import COLLECTION
    e = handoff_http
    _, _, _, value = intent(e, 'image-lost-reply')
    original, armed = e.store.transaction, True
    @contextmanager
    def lost_reply(*args, **kwargs):
        nonlocal armed
        lost = False
        with original(*args, **kwargs) as state:
            yield state
            if armed and any(r['status'] == 'DRAFT_CREATED' for r in state['collections'].get(COLLECTION, {}).values()):
                armed, lost = False, True
        if lost: raise OSError('SYNTHETIC real commit reply lost')
    with monkeypatch.context() as patch:
        patch.setattr(e.store, 'transaction', lost_reply)
        assert e.client.post(e.handoff_base, headers=e.headers, json=value).status_code == 503
    assert not armed and counts(e) == (2, 1, 1)
    fresh_owners(e, monkeypatch)
    before = effects(e)
    observed = checked(e.client.get(e.handoff_base + '/image-lost-reply', headers=e.headers))
    assert observed['status'] == 'DRAFT_CREATED' and effects(e) == before
    replay = checked(e.client.post(e.handoff_base, headers=e.headers, json=value))
    assert replay['timeline_snapshot'] == observed['timeline_snapshot'] and effects(e) == before
    empty_handles(e)


@pytest.mark.parametrize('change', ['_studio_result_origin', '_comic_ora_origin', 'lineage'])
def test_unsupported_source_family_never_enters_confirm(handoff_http, change):
    e = handoff_http
    aid, _, _, value = intent(e)
    meta = e.assets._load(aid)
    if change == 'lineage': meta['parameters'] = {'asset_lineage_v2': {}}
    else: meta[change] = None
    e.assets._write_meta(meta); before = effects(e)
    response = e.client.post(e.handoff_base, headers=e.headers, json=value)
    assert response.status_code == 422, response.text
    assert response.json() == {'detail': {'code': 'EXPERIMENTAL_INVALID'}}
    assert effects(e) == before and counts(e) == (1, 0, 0)
    empty_handles(e)


def test_actual_novel_read_write_revocation_blocks_confirm_resume_and_save(handoff_http, monkeypatch):
    from app.authorization import AuthorizationScope, ScopeKind, PermissionAssignment, ModalityDomain
    e = collaborative(handoff_http, monkeypatch)
    _, _, _, value = intent(e, 'image-revoked')
    def interrupted(*args, **kwargs): raise OSError('SYNTHETIC partial intent')
    with monkeypatch.context() as patch:
        patch.setattr(e.assets, 'create', interrupted)
        assert e.client.post(e.handoff_base, headers=e.headers, json=value).status_code == 503
    e.authorization.revoke_role(e.role, e.lead)
    before = effects(e)
    assert e.client.post(e.handoff_base, headers=e.headers, json=value).status_code == 403
    auth_scope = AuthorizationScope(ScopeKind.BRANCH, e.workspace, e.nid, e.storyline, e.branch)
    read_id = 'image-read-' + e.role
    e.authorization.assign_permission(PermissionAssignment(read_id, e.lead, 'domain.read', ModalityDomain.NOVEL, auth_scope, e.lead))
    observed = checked(e.client.get(e.handoff_base + '/image-revoked', headers=e.headers))
    assert observed['status'] == 'PLANNED' and effects(e) == before
    assert e.client.post(e.handoff_base + '/image-revoked/resume', headers=e.headers,
                         json={'expected_version': observed['version']}).status_code == 403
    e.authorization.assign_permission(PermissionAssignment('image-write-' + e.role, e.lead,
        'domain.write', ModalityDomain.NOVEL, auth_scope, e.lead))
    created = checked(e.client.post(e.handoff_base + '/image-revoked/resume', headers=e.headers,
                                   json={'expected_version': observed['version']}))
    e.authorization.revoke_permission(read_id, e.lead)
    before = effects(e)
    assert save(e, created).status_code == 403
    assert effects(e) == before and counts(e) == (2, 1, 1)
    empty_handles(e)


def test_source_edit_after_preview_and_late_asset_commit_guard_both_reject(handoff_http, monkeypatch):
    e = handoff_http
    aid, _, _, value = intent(e)
    original_meta = e.assets._load(aid)
    changed = {**original_meta, 'version': original_meta['version'] + 1}
    e.assets._write_meta(changed); before = effects(e)
    assert e.client.post(e.handoff_base, headers=e.headers, json=value).status_code == 422
    assert effects(e) == before and counts(e) == (1, 0, 0)
    e.assets._write_meta(original_meta)
    original_create = e.assets.create
    callbacks = []
    def late_change(*args, **kwargs):
        before_commit = kwargs['guard']
        def current():
            e.assets._write_meta(changed); callbacks.append(True)
            before_commit()
        kwargs['guard'] = current
        return original_create(*args, **kwargs)
    with monkeypatch.context() as patch:
        patch.setattr(e.assets, 'create', late_change)
        response = e.client.post(e.handoff_base, headers=e.headers, json=value)
        assert response.status_code == 422, response.text
    assert callbacks and counts(e) == (1, 0, 1)
    e.assets._write_meta(original_meta)
    observed = checked(e.client.get(e.handoff_base + '/external-page', headers=e.headers))
    assert observed['status'] == 'PLANNED' and observed['steps'][0]['state'] == 'PENDING'
    empty_handles(e)


def test_timeline_save_rechecks_source_after_body_before_raw_commit(handoff_http, monkeypatch):
    e = handoff_http
    aid, _, _, value = intent(e)
    created = checked(e.client.post(e.handoff_base, headers=e.headers, json=value))
    before = effects(e); original_meta = e.assets._load(aid)
    original_check = e.production._timeline_sources_current
    calls = []
    def change_after_check(*args, **kwargs):
        result = original_check(*args, **kwargs)
        calls.append(True)
        if len(calls) == 1:
            e.assets._write_meta({**original_meta, 'approved_at': None})
        return result
    try:
        with monkeypatch.context() as patch:
            patch.setattr(e.production, '_timeline_sources_current', change_after_check)
            response = save(e, created)
            assert response.status_code == 422, response.text
    finally: e.assets._write_meta(original_meta)
    assert calls and effects(e) == before
    observed = checked(e.client.get(e.handoff_base + '/external-page', headers=e.headers))
    assert observed['timeline'] == created['timeline']
    empty_handles(e)


def test_borrowed_grant_rejects_changed_target_view_and_rolls_back(handoff_http):
    e = handoff_http
    aid, _, row, review = source(e); req = request(e); before = effects(e)
    with e.comic.page_source_authority(req, e.nid, e.host) as authority:
        with pytest.raises(ValueError, match='^COMIC_SOURCE_PAGE_CHANGED$'):
            with e.production.timeline_inputs.transaction(e.nid, e.scope, 'local-author', lambda: None) as state:
                with e.comic.page_source_reader_in_phase(authority, row['id'], row['version'], review) as grant:
                    state['collections'][e.comic.RECORDS][row['id']]['document']['panels'][0]['x'] += 1
                    with pytest.raises(ValueError, match='^COMIC_SOURCE_PAGE_CHANGED$'):
                        e.assets.page_source_metadata(grant, req, aid)
    assert effects(e) == before
    empty_handles(e)


def test_actual_host_revocation_after_source_render_returns_no_preview(handoff_http, monkeypatch):
    from app.experimental.comic_layouts import ComicLayoutsService
    e = handoff_http
    _, _, row, review = source(e)
    body = {'title': 'SYNTHETIC host revoked render', 'pages': [
        {'id': row['id'], 'version': row['version'], 'review_digest': review, 'duration_ms': 1000}]}
    before = effects(e); rendered = []
    original = ComicLayoutsService._render_page_source_grant
    def revoke_after_render(*args, **kwargs):
        data = original(*args, **kwargs)
        rendered.append(data)
        e.sessions.revoke(e.host)
        return data
    monkeypatch.setattr(ComicLayoutsService, '_render_page_source_grant', revoke_after_render)
    response = e.client.post(e.handoff_base + '/preview', headers=e.headers, json=body)
    assert response.status_code == 401 and 'pages' not in response.json()
    assert rendered and effects(e) == before and counts(e) == (1, 0, 0)
    empty_handles(e)


def test_approved_page_and_arbitrary_guard_cannot_replace_actual_source_authority(handoff_http):
    e = handoff_http
    _, _, row, review = source(e); before = effects(e)
    body = {'title': 'SYNTHETIC no source authority', 'pages': [
        {'id': row['id'], 'version': row['version'], 'review_digest': review, 'duration_ms': 1000}]}
    with pytest.raises(ValueError, match='^COMIC_SOURCE_HANDLE_INVALID$'):
        e.production.comic_handoff.preview(e.nid, e.scope, 'local-author', body, lambda: None)
    assert effects(e) == before and counts(e) == (1, 0, 0)
    empty_handles(e)


def test_old_asset_commit_callback_cannot_borrow_a_new_phase_or_request(handoff_http, monkeypatch):
    e = handoff_http
    _, _, _, value = intent(e, 'expired-callback')
    callbacks = []
    def retain_callback(*args, **kwargs):
        callbacks.append(kwargs['guard'])
        raise OSError('SYNTHETIC delayed callback')
    with e.comic.page_source_authority(request(e), e.nid, e.host):
        with monkeypatch.context() as patch:
            patch.setattr(e.assets, 'create', retain_callback)
            with pytest.raises(OSError, match='SYNTHETIC delayed callback'):
                e.production.comic_handoff.confirm(e.nid, e.scope, 'local-author', value)
        assert len(callbacks) == 1
        before = effects(e)
        with e.production.timeline_inputs.phase(e.nid, e.scope, 'local-author', lambda: None):
            with pytest.raises(ValueError, match='^COMIC_HANDOFF_SOURCE_PHASE_EXPIRED$'):
                callbacks[0]()
        assert effects(e) == before
    empty_handles(e)
    with e.comic.page_source_authority(request(e), e.nid, e.host):
        with e.production.timeline_inputs.phase(e.nid, e.scope, 'local-author', lambda: None):
            with pytest.raises(ValueError, match='^COMIC_HANDOFF_SOURCE_PHASE_EXPIRED$'):
                callbacks[0]()
    assert effects(e) == before and counts(e) == (1, 0, 1)
    empty_handles(e)
