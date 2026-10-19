"""Actual File/canonical owners, Host session and NOVEL authority; no inference."""
import base64
import asyncio
import copy
from contextlib import contextmanager
from contextvars import Context, copy_context
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import hashlib
import os
import pickle

import pytest
from starlette.requests import Request
from fastapi import HTTPException

from app.services.asset_library_service import AssetLibraryService
from test_v2_independent_workspace import png_bytes
from test_v2_independent_workspace_api import client
from test_r3_mounted_contracts import mounted, prefix, scoped, checked
from test_comic_timeline_handoff_http import handoff_http, collaborative, approved_page

pytestmark = [pytest.mark.file_backend_only,
              pytest.mark.parametrize('mounted', ['file'], indirect=True),
              pytest.mark.parametrize('prefix', ['/api'], indirect=True)]


def source(e, count=1):
    raw = png_bytes(b'\x11\x22\x33')
    panels = []
    for index in range(count):
        asset = e.assets.create(e.nid, 'SYNTHETIC-leaf-source.png', base64.b64encode(raw).decode(), 'image/png',
                                branch_id=e.scope.get('branch_id'))
        approved = checked(e.client.post(e.comic_base + '/images/' + asset['id'] + '/approve',
            headers=e.headers, json={'expected_version': 1}))
        panels.append({'id': 'p' + str(index), 'artwork_mode': 'IMAGE', 'order': index + 1,
            'x': 24 + (index % 2) * 140, 'y': 24 + (index // 2) * 300,
            'width': 120, 'height': 270, 'asset_id': asset['id'], 'expected_asset_version': approved['version']})
    row = checked(e.client.post(e.comic_base + '/records', headers=e.headers, json={
        'title': 'SYNTHETIC leaf PAGE', 'source_mode': 'INDEPENDENT', 'preset': 'PAGE',
        'width': 320, 'height': 640, 'segment_height': 320,
        'panels': panels}), 201)
    url = e.comic_base + '/records/' + row['id']
    report = checked(e.client.post(url + '/preflight', headers=e.headers, json={'expected_version': row['version']}))
    row = checked(e.client.post(url + '/approve', headers=e.headers, json={
        'expected_version': row['version'], 'review_digest': report['review_digest'], 'acknowledge_warnings': True}))
    return asset['id'], raw, row, report['review_digest']


def request(e, *, origin=None, remote='testclient'):
    headers = [(k.lower().encode(), v.encode()) for k, v in e.headers.items()]
    headers.append((b'origin', (origin or e.main.settings.frontend_origin).encode()))
    return Request({'type': 'http', 'http_version': '1.1', 'scheme': 'http', 'method': 'POST',
        'path': '/source-contract-test', 'query_string': b'', 'headers': headers,
        'client': (remote, 1234), 'server': ('testserver', 80)})


@contextmanager
def grant(e, req, row, review):
    with e.comic.page_source_authority(req, e.nid, e.headers['X-Session-Token'], e.headers.get('X-Branch-ID')) as authority:
        with e.comic.page_source_reader(authority, row['id'], row['version'], review) as handle:
            yield handle


def effects(e):
    return (copy.deepcopy(e.store.read(e.nid, e.scope)),
            {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in e.assets.root.iterdir() if p.is_file()})


def empty_handles(e):
    assert not e.assets._page_source_handles
    assert e.assets._page_source_request.get() is e.assets._page_source_grant.get() is None


def invalid_read(e, handle, req, aid):
    with pytest.raises(ValueError, match='^COMIC_SOURCE_HANDLE_INVALID$'):
        e.assets.page_source_metadata(handle, req, aid)


def test_actual_owner_leaf_grant_reads_under_target_binding_without_changing_it(handoff_http, monkeypatch):
    e = handoff_http
    aid, raw, row, review = source(e); req = request(e)
    before = effects(e)
    verified = AssetLibraryService._verified_bounded_content
    receivers = []
    def verify(owner, *args, **kwargs):
        receivers.append(owner)
        assert owner is e.assets
        return verified(owner, *args, **kwargs)
    def no_second_owner(*_args, **_kwargs):
        pytest.fail('source grant constructed another Asset owner')
    monkeypatch.setattr(AssetLibraryService, '_verified_bounded_content', verify)
    monkeypatch.setattr(AssetLibraryService, '__init__', no_second_owner)
    with grant(e, req, row, review) as handle:
        assert e.assets.page_source_content(handle, req, aid, max_bytes=len(raw)) == raw
        with e.studio._asset_scope(e.nid, e.scope):
            binding = e.assets._scope.binding
            pinned = copy.deepcopy(binding)
            with pytest.raises(FileNotFoundError): e.assets.get(aid)
            assert e.assets.page_source_metadata(handle, req, aid)['id'] == aid
            assert e.assets.page_source_content(handle, req, aid, max_bytes=len(raw)) == raw
            assert e.assets._scope.binding is binding and binding == pinned
            assert e.assets.revalidate_page_sources(handle, req)['can_render']
        assert getattr(e.assets._scope, 'binding', None) is None
    assert receivers and all(owner is e.assets for owner in receivers)
    empty_handles(e)
    assert effects(e) == before
    with pytest.raises(ValueError, match='^COMIC_SOURCE_HANDLE_INVALID$'):
        e.assets.page_source_metadata(handle, req, aid)


def test_handles_cannot_be_constructed_copied_serialized_or_replaced_by_data(handoff_http):
    from app.services.comic_page_source_reads import _Handle
    e = handoff_http
    aid, raw, row, review = source(e); req = request(e); before = effects(e)
    @dataclass
    class FakeAuthority:
        page_id: str
        guard: object
    with grant(e, req, row, review) as handle:
        with pytest.raises(ValueError, match='HANDLE_INVALID'): _Handle()
        for copier in (copy.copy, copy.deepcopy, pickle.dumps):
            with pytest.raises(TypeError): copier(handle)
        for fake in (None, {}, {'page_id': row['id'], 'guard': lambda: None},
                     FakeAuthority(row['id'], lambda: None), object.__new__(_Handle)):
            invalid_read(e, fake, req, aid)
        assert e.assets.page_source_content(handle, req, aid, max_bytes=len(raw)) == raw
    empty_handles(e)
    assert effects(e) == before


def test_grant_rejects_other_request_thread_copied_context_and_owner(handoff_http):
    e = handoff_http
    aid, raw, row, review = source(e); req = request(e); before = effects(e)
    with grant(e, req, row, review) as handle:
        invalid_read(e, handle, request(e), aid)
        with ThreadPoolExecutor(max_workers=1) as pool:
            pool.submit(invalid_read, e, handle, req, aid).result(timeout=5)
            pool.submit(copy_context().run, invalid_read, e, handle, req, aid).result(timeout=5)
        copy_context().run(invalid_read, e, handle, req, aid)
        # A copied receiver shares the registry but still cannot use its entries.
        copied = copy.copy(e.assets)
        with pytest.raises(ValueError, match='HANDLE_INVALID'):
            copied.page_source_metadata(handle, req, aid)
        assert e.assets.page_source_content(handle, req, aid, max_bytes=len(raw)) == raw
    empty_handles(e)
    assert effects(e) == before


def test_grant_cannot_move_between_async_tasks(handoff_http):
    e = handoff_http
    aid, raw, row, review = source(e); req = request(e); before = effects(e)
    async def exercise():
        with grant(e, req, row, review) as handle:
            async def child(): invalid_read(e, handle, req, aid)
            await asyncio.create_task(child())
            assert e.assets.page_source_content(handle, req, aid, max_bytes=len(raw)) == raw
    asyncio.run(exercise())
    empty_handles(e)
    assert effects(e) == before


def test_phase_expiry_exception_and_authority_handles_never_become_read_grants(handoff_http):
    e = handoff_http
    aid, raw, row, review = source(e); req = request(e); before = effects(e)
    with e.comic.page_source_authority(req, e.nid, e.host) as authority:
        invalid_read(e, authority, req, aid)
        for fake in ({'guard': lambda: None}, {'_authority': authority}, row):
            with pytest.raises(ValueError, match='HANDLE_INVALID'):
                with e.comic.page_source_reader(fake, row['id'], row['version'], review): pass
        with pytest.raises(RuntimeError, match='SYNTHETIC abort'):
            with e.comic.page_source_reader(authority, row['id'], row['version'], review) as handle:
                raise RuntimeError('SYNTHETIC abort')
        invalid_read(e, handle, req, aid)
        assert len(e.assets._page_source_handles) == 1
        # A new phase uses a new registered identity.
        with e.comic.page_source_reader(authority, row['id'], row['version'], review) as newer:
            assert newer is not handle
            invalid_read(e, handle, req, aid)
            assert e.assets.page_source_content(newer, req, aid, max_bytes=len(raw)) == raw
    with pytest.raises(ValueError, match='HANDLE_INVALID'):
        with e.comic.page_source_reader(authority, row['id'], row['version'], review): pass
    empty_handles(e)
    assert effects(e) == before


@pytest.mark.parametrize('case', ['missing-token', 'unknown-token', 'origin', 'remote', 'forwarded', 'not-request'])
def test_original_host_session_is_required_before_mint(handoff_http, case):
    e = handoff_http
    _, _, row, review = source(e); before = effects(e)
    req = request(e, origin='https://foreign.invalid' if case == 'origin' else None,
                  remote='203.0.113.1' if case == 'remote' else 'testclient')
    if case == 'forwarded': req.scope['headers'].append((b'forwarded', b'for=127.0.0.1'))
    if case == 'not-request': req = {'guard': lambda: None}
    token = '' if case == 'missing-token' else 'SYNTHETIC-unknown' if case == 'unknown-token' else e.host
    with pytest.raises((HTTPException, ValueError)):
        with e.comic.page_source_authority(req, e.nid, token):
            pytest.fail('untrusted Host/session minted source authority')
    empty_handles(e)
    assert effects(e) == before


def test_image_authority_and_novel_write_do_not_replace_novel_source_read(handoff_http, monkeypatch):
    from app.authorization import PermissionAssignment, ModalityDomain
    from test_comic_independent import image_scope
    e = collaborative(handoff_http, monkeypatch)
    aid, raw, row, review = source(e)
    blank, _ = approved_page(e)
    auth_scope = image_scope(e)
    before = effects(e)
    # IMAGE can list source-free PAGEs; the source-bearing PAGE stays private
    # until the original NOVEL source-read permission is present.
    visible = [r['id'] for r in checked(e.client.get(e.comic_base + '/records', headers=e.headers))['items']]
    assert blank['id'] in visible and row['id'] not in visible
    req = request(e)
    for with_write in (False, True):
        if with_write:
            e.authorization.assign_permission(PermissionAssignment('write-source-' + e.role, e.lead,
                'domain.write', ModalityDomain.NOVEL, auth_scope, e.lead))
        with pytest.raises(HTTPException) as denied:
            with grant(e, req, row, review): pytest.fail('NOVEL source-read bypass')
        assert denied.value.status_code == 403
        empty_handles(e)
    e.authorization.assign_permission(PermissionAssignment('read-source-' + e.role, e.lead,
        'domain.read', ModalityDomain.NOVEL, auth_scope, e.lead))
    with grant(e, req, row, review) as handle:
        assert e.assets.page_source_content(handle, req, aid, max_bytes=len(raw)) == raw
    assert effects(e) == before
    empty_handles(e)


def test_exact_allowlist_and_native_byte_limits(handoff_http, monkeypatch):
    from app.services import asset_bounded_file_windows as native
    e = handoff_http
    aid, raw, row, review = source(e); req = request(e)
    other = e.assets.create(e.nid, 'SYNTHETIC-unselected.png', base64.b64encode(raw).decode(), 'image/png')['id']
    before = effects(e)
    with grant(e, req, row, review) as handle:
        for denied in (other, '../private-canary', 'SYNTHETIC-unknown'):
            with pytest.raises(FileNotFoundError): e.assets.page_source_metadata(handle, req, denied)
            with pytest.raises(FileNotFoundError): e.assets.page_source_content(handle, req, denied, max_bytes=len(raw))
        for limit in (False, 0, -1, '73', e.assets.MAX_BYTES + 1, len(raw) - 1):
            with pytest.raises(ValueError, match='ASSET_BOUNDED_READ_LIMIT'):
                e.assets.page_source_content(handle, req, aid, max_bytes=limit)
        if os.name == 'nt':
            with monkeypatch.context() as m:
                m.setattr(native, 'windows_bounded_read_supported', lambda: False)
                with pytest.raises(ValueError, match='^ASSET_BOUNDED_READ_UNSUPPORTED$'):
                    e.assets.page_source_content(handle, req, aid, max_bytes=len(raw))
        assert e.assets.page_source_content(handle, req, aid, max_bytes=len(raw)) == raw
    assert effects(e) == before
    empty_handles(e)


@pytest.mark.parametrize('change', ['approval', 'version', 'digest', 'project', 'branch', 'private', 'lineage', 'parent', 'deleted'])
def test_every_read_rechecks_actual_metadata_and_closed_leaf_profile(handoff_http, change):
    e = handoff_http
    aid, raw, row, review = source(e); req = request(e); before = effects(e)
    original = e.assets._load(aid)
    replacement = copy.deepcopy(original)
    if change == 'approval': replacement['approved_at'] = None
    if change == 'version': replacement['version'] += 1
    if change == 'digest': replacement['sha256'] = '0' * 64
    if change == 'project': replacement['novel_id'] = 'SYNTHETIC-foreign-project'
    if change == 'branch': replacement['branch_id'] = 'SYNTHETIC-foreign-branch'
    if change == 'private': replacement['_unknown_private_origin'] = None
    if change == 'lineage': replacement['parameters'] = {'asset_lineage_v2': {}}
    if change == 'parent': replacement['source_asset_ids'] = ['SYNTHETIC-ancestor']
    if change == 'deleted': replacement['deleted_at'] = 'SYNTHETIC-deleted'
    with grant(e, req, row, review) as handle:
        try:
            e.assets._write_meta(replacement)
            with pytest.raises((ValueError, FileNotFoundError)):
                e.assets.page_source_metadata(handle, req, aid)
            with pytest.raises((ValueError, FileNotFoundError)):
                e.assets.page_source_content(handle, req, aid, max_bytes=len(raw))
        finally: e.assets._write_meta(original)
        assert e.assets.page_source_content(handle, req, aid, max_bytes=len(raw)) == raw
    assert effects(e) == before
    empty_handles(e)


def test_corrupt_content_is_rejected_by_original_native_reader(handoff_http):
    from app.services.asset_library_service import AssetIntegrityError
    e = handoff_http
    aid, raw, row, review = source(e); req = request(e); before = effects(e)
    with grant(e, req, row, review) as handle:
        try:
            e.assets._bin_path(aid).write_bytes(bytes([raw[0] ^ 1]) + raw[1:])
            with pytest.raises(AssetIntegrityError):
                e.assets.page_source_content(handle, req, aid, max_bytes=len(raw))
        finally: e.assets._bin_path(aid).write_bytes(raw)
    assert effects(e) == before
    empty_handles(e)


@pytest.mark.parametrize('change', ['version', 'document', 'review', 'actor', 'epoch', 'unrelated'])
def test_phase_rechecks_page_and_rolls_back_any_scope_mutation(handoff_http, change):
    e = handoff_http
    aid, raw, row, review = source(e); req = request(e); before = effects(e)
    with pytest.raises((ValueError, FileNotFoundError)):
        with grant(e, req, row, review) as handle:
            state = e.store._local.active[e.store.key(e.nid, e.scope)]
            live = state['collections'][e.comic.RECORDS][row['id']]
            if change == 'version': live['version'] += 1
            if change == 'document': live['document']['panels'][0]['x'] += 1
            if change == 'review': live['approval']['digest'] = '0' * 64
            if change == 'actor': live['created_by'] = 'SYNTHETIC-other-actor'
            if change == 'epoch': live['project_incarnation'] = 'file:00000000-0000-0000-0000-000000000000'
            if change == 'unrelated': state['collections']['SYNTHETIC-unrelated'] = {}
            if change != 'unrelated':
                with pytest.raises((ValueError, FileNotFoundError)):
                    e.assets.page_source_metadata(handle, req, aid)
    assert effects(e) == before
    empty_handles(e)


@pytest.mark.parametrize('change', ['revoke', 'same-binding-aba', 'feature'])
def test_phase_exit_rechecks_real_session_aba_and_features(handoff_http, monkeypatch, change):
    from app.services.comic_page_origin import FEATURES
    e = handoff_http
    _, _, row, review = source(e); req = request(e); before = effects(e)
    with pytest.raises((HTTPException, ValueError)):
        with grant(e, req, row, review):
            if change == 'feature':
                monkeypatch.setenv('EXPERIMENTAL_FEATURES', ','.join(sorted(FEATURES - {'asset_lineage_v2'})))
            else:
                session = e.sessions.resolve(e.host).session
                e.sessions.revoke(e.host)
                if change == 'same-binding-aba': e.sessions.register(e.host, session)
    assert effects(e) == before
    empty_handles(e)


def test_four_authoritative_leaf_ids_are_readable_without_other_ids(handoff_http):
    e = handoff_http
    _, raw, row, review = source(e, 4); req = request(e); before = effects(e)
    sources = e.store.read(e.nid, e.scope)['collections'][e.comic.RECORDS][row['id']]['asset_sources']
    with grant(e, req, row, review) as handle:
        assert len(sources) == 4
        for aid in sources:
            assert e.assets.page_source_content(handle, req, aid, max_bytes=len(raw)) == raw
        assert e.assets.revalidate_page_sources(handle, req)['can_render']
    assert effects(e) == before
    empty_handles(e)


def test_only_original_mounted_receivers_can_mint(handoff_http):
    e = handoff_http
    _, _, row, review = source(e); req = request(e); before = effects(e)
    for owner, comic in ((copy.copy(e.assets), e.comic), (e.assets, copy.copy(e.comic))):
        with pytest.raises(ValueError, match='^COMIC_SOURCE_ORIGINAL_OWNERS_REQUIRED$'):
            with owner.comic_source_authority(comic, req, e.nid, e.host): pass
    assert effects(e) == before
    empty_handles(e)


def test_actual_binding_order_and_foreign_binding_are_not_bypassed(handoff_http):
    e = handoff_http
    aid, _, row, review = source(e); req = request(e); before = effects(e)
    with e.studio._asset_scope(e.nid, e.scope):
        binding = e.assets._scope.binding
        with pytest.raises(ValueError, match='^COMIC_SOURCE_AUTHORITY_PHASE_ORDER_INVALID$'):
            with e.comic.page_source_authority(req, e.nid, e.host): pass
        assert e.assets._scope.binding is binding
    with grant(e, req, row, review) as handle:
        with e.studio._asset_scope(e.nid, {**e.scope, 'branch_id': 'SYNTHETIC-other-branch'}):
            binding = e.assets._scope.binding; pinned = copy.deepcopy(binding)
            with pytest.raises(ValueError, match='^COMIC_SOURCE_SCOPE_CHANGED$'):
                e.assets.page_source_metadata(handle, req, aid)
            assert e.assets._scope.binding is binding and binding == pinned
    assert effects(e) == before
    empty_handles(e)


@pytest.mark.parametrize('field', ['_studio_result_origin', '_comic_ora_origin', '_comic_page_origin',
    '_manual_mask_origin', '_model_reference_origin', '_video_reference_origin', '_text_result_origin',
    '_owner_actor_id', '_project_binding', 'lineage', 'ancestors'])
def test_mint_refuses_private_or_derived_source_families_even_with_falsey_markers(handoff_http, field):
    e = handoff_http
    aid, _, row, review = source(e); req = request(e)
    meta = e.assets._load(aid)
    if field == 'lineage': meta['parameters'] = {'asset_lineage_v2': {}}
    elif field == 'ancestors': meta['source_asset_ids'] = ['SYNTHETIC-parent']
    else: meta[field] = None
    e.assets._write_meta(meta)
    before = effects(e)
    with pytest.raises(ValueError, match='^COMIC_SOURCE_PROFILE_UNSUPPORTED$'):
        with grant(e, req, row, review): pass
    assert effects(e) == before
    empty_handles(e)


@pytest.mark.parametrize('case', ['version', 'boolean-version', 'review', 'unapproved', 'hidden-id', 'five-ids', 'zero-ids'])
def test_mint_requires_exact_reviewed_page_and_dependency_capacity(handoff_http, case):
    e = handoff_http
    aid, _, row, review = source(e); req = request(e)
    with e.store.transaction(e.nid, e.scope) as state:
        live = state['collections'][e.comic.RECORDS][row['id']]
        if case == 'unapproved': live['status'] = 'DRAFT'
        if case == 'hidden-id': live['asset_sources']['SYNTHETIC-hidden-id'] = copy.deepcopy(live['asset_sources'][aid])
        if case in ('five-ids', 'zero-ids'):
            binding = copy.deepcopy(live['asset_sources'][aid])
            live['document']['panels'] = []
            live['asset_sources'] = {}
            if case == 'five-ids':
                for n in range(5):
                    key = 'SYNTHETIC-source-' + str(n)
                    live['document']['panels'].append({'id': key, 'artwork_mode': 'IMAGE', 'asset_id': key})
                    live['asset_sources'][key] = copy.deepcopy(binding)
    before = effects(e)
    version = row['version'] + 1 if case == 'version' else True if case == 'boolean-version' else row['version']
    pin = '0' * 64 if case == 'review' else review
    with pytest.raises(ValueError):
        with e.comic.page_source_authority(req, e.nid, e.host) as authority:
            with e.comic.page_source_reader(authority, row['id'], version, pin): pass
    assert effects(e) == before
    empty_handles(e)


def test_missing_original_project_marker_is_never_created(handoff_http):
    e = handoff_http
    _, _, row, review = source(e); req = request(e); before = effects(e)
    marker = e.root / 'novels' / e.nid / 'creative_project_v2.json'
    saved = marker.read_bytes()
    marker.unlink()
    try:
        with pytest.raises(FileNotFoundError):
            with grant(e, req, row, review): pass
        assert not marker.exists()
        empty_handles(e)
    finally: marker.write_bytes(saved)
    assert effects(e) == before


def test_handle_capacity_uses_real_registered_frames_and_releases_all(handoff_http):
    e = handoff_http
    _, _, row, review = source(e); req = request(e); before = effects(e)
    frames = []
    try:
        for _ in range(16):
            context = Context()
            manager = e.comic.page_source_authority(req, e.nid, e.host)
            handle = context.run(manager.__enter__)
            frames.append((context, manager, handle))
        assert len(e.assets._page_source_handles) == 16
        with pytest.raises(ValueError, match='^COMIC_SOURCE_HANDLE_LIMIT$'):
            with e.comic.page_source_authority(req, e.nid, e.host): pass
        context, _, authority = frames[0]
        def overflow_grant():
            with e.comic.page_source_reader(authority, row['id'], row['version'], review): pass
        with pytest.raises(ValueError, match='^COMIC_SOURCE_HANDLE_LIMIT$'):
            context.run(overflow_grant)
        assert len(e.assets._page_source_handles) == 16
    finally:
        for context, manager, _ in reversed(frames): context.run(manager.__exit__, None, None, None)
    assert effects(e) == before
    empty_handles(e)


def test_novel_read_revocation_and_original_leases_cover_phase_exit(handoff_http, monkeypatch):
    e = collaborative(handoff_http, monkeypatch)
    aid, raw, row, review = source(e); req = request(e); before = effects(e)
    depth = {'session': 0, 'authorization': 0, 'project': 0}
    def tracing(original, name):
        @contextmanager
        def wrapper(*args, **kwargs):
            with original(*args, **kwargs) as result:
                depth[name] += 1
                try: yield result
                finally: depth[name] -= 1
        return wrapper
    monkeypatch.setattr(e.sessions, 'binding_lease', tracing(e.sessions.binding_lease, 'session'))
    repository = e.authorization.repository
    monkeypatch.setattr(repository, 'mutation', tracing(repository.mutation, 'authorization'))
    # The implementation invokes the trusted class method, so trace actual
    # owners below it rather than replace the authority or source producer.
    owner = e.comic._independent_owner()
    monkeypatch.setattr(owner, 'owner_lease', tracing(owner.owner_lease, 'project'))
    original = AssetLibraryService._verified_bounded_content
    reads = []
    def verified(receiver, *args, **kwargs):
        assert receiver is e.assets
        assert depth['session'] > 0 and depth['authorization'] > 0 and depth['project'] > 0
        assert receiver._lock._is_owned()
        assert e.store.key(e.nid, e.scope) in e.store._local.active
        reads.append(True)
        return original(receiver, *args, **kwargs)
    monkeypatch.setattr(AssetLibraryService, '_verified_bounded_content', verified)
    with pytest.raises(HTTPException) as denied:
        with grant(e, req, row, review) as handle:
            assert e.assets.page_source_content(handle, req, aid, max_bytes=len(raw)) == raw
            e.authorization.revoke_role(e.role, e.lead)
            with pytest.raises(HTTPException): e.assets.page_source_metadata(handle, req, aid)
    assert denied.value.status_code == 403 and reads
    assert all(value == 0 for value in depth.values())
    assert effects(e) == before
    empty_handles(e)


def test_foreign_phase_exit_is_rejected_without_closing_the_original_phase(handoff_http):
    e = handoff_http
    aid, raw, row, review = source(e); req = request(e); before = effects(e)
    authority_phase = e.comic.page_source_authority(req, e.nid, e.host)
    with authority_phase as authority:
        source_phase = e.comic.page_source_reader(authority, row['id'], row['version'], review)
        with source_phase as handle:
            for phase in (source_phase, authority_phase):
                with pytest.raises(ValueError, match='^COMIC_SOURCE_HANDLE_INVALID$'):
                    copy_context().run(phase.__exit__, None, None, None)
                with ThreadPoolExecutor(max_workers=1) as pool:
                    with pytest.raises(ValueError, match='^COMIC_SOURCE_HANDLE_INVALID$'):
                        pool.submit(phase.__exit__, None, None, None).result(timeout=5)
            assert len(e.assets._page_source_handles) == 2
            assert e.assets.page_source_content(handle, req, aid, max_bytes=len(raw)) == raw
        invalid_read(e, handle, req, aid)
        with pytest.raises(ValueError, match='^COMIC_SOURCE_PHASE_REUSED$'):
            with source_phase: pass
    assert effects(e) == before
    empty_handles(e)


@pytest.mark.skipif(os.name != 'nt', reason='native Windows close boundary')
def test_original_native_final_close_rechecks_current_host(handoff_http, monkeypatch):
    from app.services import asset_bounded_file_windows as native
    e = handoff_http
    aid, raw, row, review = source(e); req = request(e); before = effects(e)
    original = native._Kernel.close
    closed = []
    def revoke_after_real_close(kernel, handle):
        result = original(kernel, handle)
        closed.append(result)
        if len(closed) == 1: e.sessions.revoke(e.host)
        return result
    with pytest.raises((HTTPException, ValueError)):
        with grant(e, req, row, review) as handle:
            monkeypatch.setattr(native._Kernel, 'close', revoke_after_real_close)
            e.assets.page_source_content(handle, req, aid, max_bytes=len(raw))
    assert closed and all(closed)
    assert effects(e) == before
    empty_handles(e)
