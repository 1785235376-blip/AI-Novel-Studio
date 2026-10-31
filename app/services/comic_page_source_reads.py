"""Owner-registered, phase-local Comic source reads. No target scope mutation.

First profile: direct, manually reviewed, unbound images without lineage or
private origins. Other source families are refused, never treated as uploads.
"""
from __future__ import annotations

import asyncio
import copy
from contextlib import contextmanager
import threading

from ..experimental.media import digest

_KEY = object()
_MAX_HANDLES = 16


class _Handle:
    __slots__ = ()
    def __new__(cls, key=None):
        if key is not _KEY:
            raise ValueError('COMIC_SOURCE_HANDLE_INVALID')
        return super().__new__(cls)
    def __copy__(self): raise TypeError('COMIC_SOURCE_HANDLE_NOT_COPYABLE')
    def __deepcopy__(self, memo): raise TypeError('COMIC_SOURCE_HANDLE_NOT_COPYABLE')
    def __reduce_ex__(self, protocol): raise TypeError('COMIC_SOURCE_HANDLE_NOT_SERIALIZABLE')


def _task():
    try: return asyncio.current_task()
    except RuntimeError: return None


def _canonical(owner, comic):
    from .. import api
    from ..experimental import api as experimental
    from ..experimental.comic_layouts import ComicLayoutsService
    if (type(comic) is not ComicLayoutsService or comic is not experimental.comic_layouts_service
            or owner is not api.asset_library_service or comic.assets is not owner
            or comic.novels is not api.novel_service or comic.chapters is not api.chapter_service
            or comic._independent_owner().store is not comic.store):
        raise ValueError('COMIC_SOURCE_ORIGINAL_OWNERS_REQUIRED')
    return ComicLayoutsService


def _record(owner, handle, request, kind):
    if type(handle) is not _Handle:
        raise ValueError('COMIC_SOURCE_HANDLE_INVALID')
    with owner._page_source_lock:
        row = owner._page_source_handles.get(handle)
        if (row is None or row['owner'] is not owner or row['kind'] != kind or row['request'] is not request
                or row['thread'] != threading.get_ident() or row['task'] is not _task()
                or row['variable'].get() is not handle):
            raise ValueError('COMIC_SOURCE_HANDLE_INVALID')
        # Token.reset is context-specific. Probe/rotate only our private handle
        # marker; a copied Context cannot reset this token and cannot consume it.
        try:
            row['variable'].reset(row['context_token'])
        except (ValueError, RuntimeError):
            raise ValueError('COMIC_SOURCE_HANDLE_INVALID') from None
        row['context_token'] = row['variable'].set(handle)
        return row


def _close(owner, handle):
    with owner._page_source_lock:
        row = owner._page_source_handles.get(handle)
        if row is not None:
            _record(owner, handle, row['request'], row['kind'])
            row['variable'].reset(row['context_token'])
            del owner._page_source_handles[handle]


class _Phase:
    """Reject a foreign exit before advancing the original lease generator."""
    def __init__(self, owner, manager):
        self._owner, self._manager, self._handle = owner, manager, None
        self._started = False

    def __enter__(self):
        if self._started:
            raise ValueError('COMIC_SOURCE_PHASE_REUSED')
        self._started = True
        self._handle = self._manager.__enter__()
        return self._handle

    def __exit__(self, *error):
        row = self._owner._page_source_handles.get(self._handle)
        if row is None:
            raise ValueError('COMIC_SOURCE_HANDLE_INVALID')
        _record(self._owner, self._handle, row['request'], row['kind'])
        return self._manager.__exit__(*error)


def authority(owner, comic, request, nid, token, branch):
    return _Phase(owner, _authority_phase(owner, comic, request, nid, token, branch))


@contextmanager
def _authority_phase(owner, comic, request, nid, token, branch):
    cls = _canonical(owner, comic)
    if owner._page_source_request.get() is not None or getattr(owner._scope, 'binding', None) is not None:
        raise ValueError('COMIC_SOURCE_AUTHORITY_PHASE_ORDER_INVALID')
    # This trusted method resolves actual Host/session/NOVEL read authority and
    # holds the original owners. A caller-supplied guard is never accepted.
    with cls._page_source_authority(comic, request, nid, token, branch) as current:
        current['guard']()
        # No generic registration helper accepts a context or guard. Mint only
        # inside the original Host/session/NOVEL lease above.
        with owner._page_source_lock:
            if len(owner._page_source_handles) >= _MAX_HANDLES:
                raise ValueError('COMIC_SOURCE_HANDLE_LIMIT')
            handle = _Handle(_KEY)
            variable = owner._page_source_request
            marker = variable.set(handle)
            owner._page_source_handles[handle] = dict(owner=owner, kind='authority', request=request,
                thread=threading.get_ident(), task=_task(), variable=variable, context_token=marker,
                comic=comic, cls=cls, authority=current)
        try:
            yield handle
            current['guard']()
        finally:
            _close(owner, handle)


def _authority_record(owner, handle, comic=None):
    row = owner._page_source_handles.get(handle) if type(handle) is _Handle else None
    if row is None:
        raise ValueError('COMIC_SOURCE_HANDLE_INVALID')
    row = _record(owner, handle, row['request'], 'authority')
    _canonical(owner, row['comic'])
    if comic is not None and row['comic'] is not comic:
        raise ValueError('COMIC_SOURCE_HANDLE_INVALID')
    row['authority']['guard']()
    return row


def current_authority(owner, comic, nid, scope, actor):
    handle = owner._page_source_request.get()
    row = _authority_record(owner, handle, comic)
    context = row['authority']
    if (context['nid'], context['scope'], context['actor']) != (nid, scope, actor):
        raise ValueError('COMIC_SOURCE_AUTHORITY_CHANGED')
    return handle, row['request']


def _leaf(owner, comic, context, aid, binding):
    meta = owner._load(aid)
    from ..experimental.comic_layouts import ComicLayoutsService
    if (meta.get('novel_id'), meta.get('branch_id')) != (context['nid'], context['scope'].get('branch_id')):
        raise FileNotFoundError(aid)
    if (any(key.startswith('_') for key in meta)
            or meta.get('deleted_at') or not meta.get('approved_at')
            or meta.get('kind') != 'image' or meta.get('media_type') not in {'image/png', 'image/jpeg', 'image/webp'}
            or not ComicLayoutsService._manual(meta)
            or any(key in meta.get('parameters', {}) for key in ('asset_lineage_v2', 'asset_relationships_v2'))):
        raise ValueError('COMIC_SOURCE_PROFILE_UNSUPPORTED')
    projected = {**copy.deepcopy(meta), '_comic_source_privacy': {}}
    if ComicLayoutsService._binding(comic, projected) != binding:
        raise ValueError('COMIC_SOURCE_DEPENDENCY_CHANGED')
    return meta


@contextmanager
def _source_phase(owner, comic, authority_handle, page_id, version, review_digest):
    auth = _authority_record(owner, authority_handle, comic)
    if owner._page_source_grant.get() is not None:
        raise ValueError('COMIC_SOURCE_GRANT_NESTED')
    context, cls = auth['authority'], auth['cls']
    # Minimal slice uses the original source phase. It does not yet hook a
    # Graph write phase or integrate the Timeline handoff.
    with cls._independent_transaction(comic, context['nid'], context['scope']) as state:
        plan = cls._page_source_plan(comic, context, page_id, version, review_digest)
        pins = {aid: _leaf(owner, comic, context, aid, binding) for aid, binding in plan['assets'].items()}
        if sum(meta['size'] for meta in pins.values()) > 64 * 1024 * 1024:
            raise ValueError('COMIC_SOURCE_BYTES_LIMIT')
        pinned_digests = {aid: digest(meta) for aid, meta in pins.items()}
        before = digest(state)
        with owner._page_source_lock:
            if len(owner._page_source_handles) >= _MAX_HANDLES:
                raise ValueError('COMIC_SOURCE_HANDLE_LIMIT')
            handle = _Handle(_KEY)
            variable = owner._page_source_grant
            marker = variable.set(handle)
            owner._page_source_handles[handle] = dict(owner=owner, kind='grant', request=auth['request'],
                thread=threading.get_ident(), task=_task(), variable=variable, context_token=marker,
                authority_handle=authority_handle, comic=comic, cls=cls, state=state, plan=plan,
                pins=pinned_digests)
        try:
            revalidate(owner, handle, auth['request'])
            yield handle
            revalidate(owner, handle, auth['request'])
            if digest(state) != before:
                raise ValueError('COMIC_SOURCE_READ_PHASE_MUTATION')
        finally:
            _close(owner, handle)


def open_sources(owner, comic, authority_handle, page_id, version, review_digest):
    return _Phase(owner, _source_phase(owner, comic, authority_handle, page_id, version, review_digest))


def _leased_phase(owner, comic, context):
    """Borrow actual leases, never start a transaction under a target binding."""
    key, nid = context['scope_key'], context['nid']
    project = comic._independent_owner()
    raw = getattr(comic.store._local, 'active', {}).get(key)
    if (raw is None or getattr(project._local, 'owners', {}).get(nid) != context['incarnation']
            or not owner._lock._is_owned()):
        raise ValueError('COMIC_SOURCE_ORIGINAL_PHASE_REQUIRED')
    view = getattr(project._local, 'active', {}).get(key)
    if view is not None:
        from ..experimental import api as experimental
        production = experimental.studio_production_service
        expected = dict(novel_id=nid, branch_id=context['scope'].get('branch_id'),
                        scope_key=key, incarnation=context['incarnation'])
        if (production.store is not project or production.workspace.assets is not owner
                or production.comic_handoff is None or production.comic_handoff.comic is not comic
                or not production.timeline_inputs.in_phase(nid, context['scope'], context['actor'])
                or getattr(owner._scope, 'binding', None) != expected):
            raise ValueError('COMIC_SOURCE_ORIGINAL_PHASE_REQUIRED')
    elif getattr(owner._scope, 'binding', None) is not None:
        raise ValueError('COMIC_SOURCE_ORIGINAL_PHASE_REQUIRED')
    return raw, view


@contextmanager
def _borrowed_phase(owner, comic, authority_handle, page_id, version, review_digest):
    auth = _authority_record(owner, authority_handle, comic)
    if owner._page_source_grant.get() is not None:
        raise ValueError('COMIC_SOURCE_GRANT_NESTED')
    context, cls = auth['authority'], auth['cls']
    raw, view = _leased_phase(owner, comic, context)
    plan = cls._page_source_plan(comic, context, page_id, version, review_digest)
    pins = {aid: _leaf(owner, comic, context, aid, binding) for aid, binding in plan['assets'].items()}
    if sum(meta['size'] for meta in pins.values()) > 64 * 1024 * 1024:
        raise ValueError('COMIC_SOURCE_BYTES_LIMIT')
    pinned_digests = {aid: digest(meta) for aid, meta in pins.items()}
    before = digest(raw)
    with owner._page_source_lock:
        if len(owner._page_source_handles) >= _MAX_HANDLES:
            raise ValueError('COMIC_SOURCE_HANDLE_LIMIT')
        handle = _Handle(_KEY)
        variable = owner._page_source_grant
        marker = variable.set(handle)
        owner._page_source_handles[handle] = dict(owner=owner, kind='grant', request=auth['request'],
            thread=threading.get_ident(), task=_task(), variable=variable, context_token=marker,
            authority_handle=authority_handle, comic=comic, cls=cls, state=raw, target_state=view,
            borrowed=True, plan=plan, pins=pinned_digests)
    try:
        revalidate(owner, handle, auth['request'])
        yield handle
        revalidate(owner, handle, auth['request'])
        if digest(raw) != before:
            raise ValueError('COMIC_SOURCE_READ_PHASE_MUTATION')
    finally:
        _close(owner, handle)


def open_in_phase(owner, comic, authority_handle, page_id, version, review_digest):
    return _Phase(owner, _borrowed_phase(owner, comic, authority_handle, page_id, version, review_digest))


def _grant(owner, handle, request):
    row = _record(owner, handle, request, 'grant')
    auth = _authority_record(owner, row['authority_handle'], row['comic'])
    context = auth['authority']
    key = context['scope_key']
    if row['comic'].store._local.active.get(key) is not row['state']:
        raise ValueError('COMIC_SOURCE_PHASE_EXPIRED')
    if row.get('borrowed'):
        raw, view = _leased_phase(owner, row['comic'], context)
        if raw is not row['state'] or view is not row['target_state']:
            raise ValueError('COMIC_SOURCE_PHASE_EXPIRED')
        if view is not None:
            page = view['collections'].get(row['comic'].RECORDS, {}).get(row['plan']['page_id'])
            if digest(page) != row['plan']['row_digest']:
                raise ValueError('COMIC_SOURCE_PAGE_CHANGED')
    expected = dict(novel_id=context['nid'], branch_id=context['scope'].get('branch_id'),
                    scope_key=key, incarnation=context['incarnation'])
    active = getattr(owner._scope, 'binding', None)
    if active is not None and active != expected:
        raise ValueError('COMIC_SOURCE_SCOPE_CHANGED')
    plan = row['cls']._page_source_plan(row['comic'], context, row['plan']['page_id'],
        row['plan']['version'], row['plan']['review_digest'])
    if plan != row['plan']:
        raise ValueError('COMIC_SOURCE_PAGE_CHANGED')
    return row, context


def metadata(owner, handle, request, aid):
    row, context = _grant(owner, handle, request)
    if aid not in row['pins']:
        raise FileNotFoundError(aid)
    meta = _leaf(owner, row['comic'], context, aid, row['plan']['assets'][aid])
    if digest(meta) != row['pins'][aid]:
        raise ValueError('COMIC_SOURCE_DEPENDENCY_CHANGED')
    return copy.deepcopy(meta)


def content(owner, handle, request, aid, maximum):
    meta = metadata(owner, handle, request, aid)
    data = owner._verified_bounded_content(meta, maximum, lambda: _grant(owner, handle, request))
    if metadata(owner, handle, request, aid) != meta:
        raise ValueError('COMIC_SOURCE_DEPENDENCY_CHANGED')
    return data


def revalidate(owner, handle, request):
    row, context = _grant(owner, handle, request)
    result = row['cls']._validate_page_source_grant(row['comic'], handle, request, context, row['plan'])
    for aid in row['pins']:
        metadata(owner, handle, request, aid)
    _grant(owner, handle, request)
    return result


def render(owner, handle, request):
    row, context = _grant(owner, handle, request)
    data = row['cls']._render_page_source_grant(row['comic'], handle, request, context, row['plan'])
    _grant(owner, handle, request)
    return data
