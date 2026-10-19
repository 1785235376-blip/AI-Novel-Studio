"""Explicit original Comic -> native Asset -> original Timeline draft handoff.

The bounded intent uses the original scope store and exact planned Asset IDs.
Preview is read-only. Confirm/resume/cancel are explicit and never dispatch jobs,
inherit approval, render video, or delete partial effects.
"""
from __future__ import annotations

import hashlib
import re
import base64
import copy
import stat
from uuid import uuid4
from contextlib import contextmanager
from typing import Literal

from pydantic import Field, model_validator

from .media import StrictModel, digest
from .common import StaleSourceError, check_version, now
from .comic_layers import ora_decode_budget
from .comic_publication import _render_page
from .comic_publication_budget import publication_budget, MAX_PAGE_PIXELS, MAX_ARCHIVE_BYTES
from ..services.comic_page_origin import CONTRACT as ASSET_CONTRACT, FIELD, FEATURES, ID, DIGEST, record, marker, ComicPagePin

CONTRACT = 'studio-comic-timeline-handoff/1'
COLLECTION = 'comic_timeline_handoffs_v1'
MAX_RECEIPTS = 32
LOSSES = ['WHOLE_PAGES_FLATTENED_TO_STATIC_PNG', 'NO_PANEL_MOTION_OR_AUDIO',
          'TIMELINE_DRAFT_ONLY_NO_VIDEO_RENDER_OR_APPROVAL', 'ORIGINAL_COMIC_PAGES_UNCHANGED']


class PageSelection(StrictModel):
    id: str = Field(pattern=ID, strict=True)
    version: int = Field(ge=1, le=2**53 - 1, strict=True)
    review_digest: str = Field(pattern=DIGEST, strict=True)
    duration_ms: int = Field(ge=1, le=600_000, strict=True)


class HandoffRequest(StrictModel):
    title: str = Field(min_length=1, max_length=200, strict=True)
    pages: list[PageSelection] = Field(min_length=1, max_length=4)
    width: int = Field(default=1280, ge=16, le=1920, strict=True)
    height: int = Field(default=720, ge=16, le=1080, strict=True)
    fps: int = Field(default=24, ge=1, le=60, strict=True)

    @model_validator(mode='after')
    def bounded(self):
        if len({p.id for p in self.pages}) != len(self.pages):
            raise ValueError('COMIC_HANDOFF_DUPLICATE_PAGE')
        if sum(p.duration_ms for p in self.pages) > 600_000:
            raise ValueError('COMIC_HANDOFF_DURATION_LIMIT')
        if self.width % 2 or self.height % 2:
            raise ValueError('COMIC_HANDOFF_EVEN_DIMENSIONS_REQUIRED')
        if any(ord(c) < 32 or 0xD800 <= ord(c) <= 0xDFFF for c in self.title):
            raise ValueError('COMIC_HANDOFF_TITLE_INVALID')
        return self


class HandoffConfirm(StrictModel):
    request_id: str = Field(pattern=r'^[A-Za-z0-9][A-Za-z0-9_-]{0,79}$', strict=True)
    request: HandoffRequest
    reviewed_preview_digest: str = Field(pattern=DIGEST, strict=True)
    acknowledge_losses: Literal[True]

    @model_validator(mode='before')
    @classmethod
    def explicit_acknowledgement(cls, value):
        if not isinstance(value, dict) or value.get('acknowledge_losses') is not True:
            raise ValueError('COMIC_HANDOFF_EXPLICIT_LOSS_ACK_REQUIRED')
        return value


class RenderedPagePin(StrictModel):
    source: ComicPagePin
    duration_ms: int = Field(ge=1, le=600_000, strict=True)
    width: int = Field(ge=64, le=1600, strict=True)
    height: int = Field(ge=64, le=12000, strict=True)
    png_sha256: str = Field(pattern=DIGEST, strict=True)
    bytes: int = Field(ge=1, le=25 * 1024 * 1024, strict=True)
    render_fingerprint: str = Field(pattern=DIGEST, strict=True)


class PreviewReport(StrictModel):
    contract: Literal['studio-comic-timeline-handoff/1']
    scope_key: str = Field(pattern=DIGEST, strict=True)
    incarnation: str = Field(strict=True)
    actor: str = Field(min_length=1, max_length=240, strict=True)
    request: HandoffRequest
    request_digest: str = Field(pattern=DIGEST, strict=True)
    pages: list[RenderedPagePin] = Field(min_length=1, max_length=4)
    duration_ms: int = Field(ge=1, le=600_000, strict=True)
    losses: list[str]
    automatic_dispatch: Literal[False]
    model_called: Literal[False]
    video_rendered: Literal[False]
    approval_inherited: Literal[False]
    preview_digest: str = Field(pattern=DIGEST, strict=True)


def validate_preview(value):
    try:
        normalized = PreviewReport.model_validate(value).model_dump()
        if (normalized != value or value['losses'] != LOSSES
                or any(value[k] is not False for k in ('automatic_dispatch', 'model_called', 'video_rendered', 'approval_inherited'))
                or value['duration_ms'] != sum(p['duration_ms'] for p in value['pages'])
                or len(value['pages']) != len(value['request']['pages'])
                or digest(value['request']) != value['request_digest']
                or digest({k: v for k, v in value.items() if k != 'preview_digest'}) != value['preview_digest']):
            raise ValueError('invalid preview')
        for selected, page in zip(value['request']['pages'], value['pages']):
            if (any(selected[k] != page['source'][k] for k in ('id', 'version', 'review_digest'))
                    or selected['duration_ms'] != page['duration_ms'] or page['width'] * page['height'] > 16_000_000):
                raise ValueError('invalid preview')
    except (ValueError, TypeError, KeyError):
        raise ValueError('COMIC_HANDOFF_RECEIPT_CORRUPT') from None
    return normalized


def rendering_fingerprint():
    from .comic_layouts import renderer_status, font_status
    return digest({'recipe': 'original-comic-full-page-png/1',
                   'renderer': renderer_status(), 'font': font_status()})


def validate_timeline_origin(row, *, history=None):
    origin = row.get('comic_handoff_origin')
    fields = {'contract', 'receipt_id', 'request_id', 'preview_digest', 'creation_snapshot'}
    try:
        if not isinstance(origin, dict) or set(origin) != fields or origin['contract'] != CONTRACT:
            raise ValueError('invalid origin')
        import re
        if (not re.fullmatch(ID, origin['receipt_id'])
                or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,79}', origin['request_id'])
                or not re.fullmatch(DIGEST, origin['preview_digest'])):
            raise ValueError('invalid origin')
        snapshot = origin['creation_snapshot']
        if (not isinstance(snapshot, dict) or set(snapshot) != {'id', 'version', 'digest'}
                or snapshot['id'] != row['id'] or type(snapshot['version']) is not int or snapshot['version'] != 1
                or not re.fullmatch(DIGEST, snapshot['digest'])):
            raise ValueError('invalid origin')
        creation = row if row['version'] == 1 else next((entry for entry in (history if history is not None else row['history'])
                                                       if entry.get('version') == 1), None)
        if not isinstance(creation, dict) or creation.get('timeline_digest') != snapshot['digest']:
            raise ValueError('invalid origin')
    except (ValueError, TypeError, KeyError, AttributeError):
        raise ValueError('COMIC_HANDOFF_TIMELINE_ORIGIN_CORRUPT') from None
    return copy.deepcopy(origin)


class ComicTimelineHandoff:
    def __init__(self, comic, production):
        workspace = production.workspace
        if (comic.store is not production.store.store or comic.assets is not workspace.assets
                or comic._independent_owner() is not production.store or workspace.store is not production.store):
            raise ValueError('COMIC_HANDOFF_ORIGINAL_OWNERS_REQUIRED')
        self.comic, self.production, self.workspace = comic, production, workspace
        self.store, self.owner, self.assets = comic.store, production.store, workspace.assets

    def _authority(self, nid, scope, actor, guard):
        from .flags import enabled_flags
        guard()
        if not FEATURES.issubset(enabled_flags()):
            raise ValueError('COMIC_HANDOFF_FEATURES_REQUIRED')
        if (not isinstance(actor, str) or not 1 <= len(actor) <= 240
                or any(ord(c) < 32 or ord(c) == 127 or 0xD800 <= ord(c) <= 0xDFFF for c in actor)):
            raise ValueError('COMIC_HANDOFF_ACTOR_INVALID')
        with self.owner.existing_owner_only():
            return self.production._base(nid, scope, actor, guard)

    @contextmanager
    def _phase(self, nid, scope, actor, guard):
        self._authority(nid, scope, actor, guard)
        # Preserve Comic's existing unbound-upload and bound-result namespaces.
        # The original Comic transaction owns scope -> Asset -> project locks;
        # imposing a Timeline Asset binding here would hide legacy page images.
        with self.comic._independent_transaction(nid, scope) as state:
            context = self._authority(nid, scope, actor, guard)
            yield state, context
            self._authority(nid, scope, actor, guard)

    def _page(self, nid, scope, actor, selected):
        row = self.comic._row(nid, scope, actor, selected['id'])
        check_version(row, selected['version'])
        if not self.comic._independent(row) or row['document']['preset'] != 'PAGE':
            raise ValueError('COMIC_HANDOFF_INDEPENDENT_PAGE_REQUIRED')
        report = self.comic.preflight(nid, scope, actor, row['id'], row['version'])
        if (row['status'] != 'APPROVED' or (row.get('approval') or {}).get('digest') != report['review_digest']
                or selected['review_digest'] != report['review_digest']):
            raise StaleSourceError('COMIC_HANDOFF_CURRENT_APPROVAL_REQUIRED')
        if not report['can_render']:
            raise ValueError('COMIC_PREFLIGHT_BLOCKED')
        return row, report

    def _materialize(self, nid, scope, actor, body, context, guard):
        selected = [page.model_dump() for page in body.pages]
        # Admit every page and aggregate geometry before decoding even one source.
        rows = [self.comic._row(nid, scope, actor, page['id']) for page in selected]
        for row, page in zip(rows, selected):
            check_version(row, page['version'])
            if not self.comic._independent(row) or row['document']['preset'] != 'PAGE':
                raise ValueError('COMIC_HANDOFF_INDEPENDENT_PAGE_REQUIRED')
        if sum(r['document']['width'] * r['document']['height'] for r in rows) > MAX_PAGE_PIXELS:
            raise ValueError('COMIC_HANDOFF_PAGE_PIXEL_LIMIT')
        fingerprint = rendering_fingerprint()
        pins, images = [], []
        with publication_budget(), ora_decode_budget():
            for page in selected:
                guard()
                row, _ = self._page(nid, scope, actor, page)
                data = _render_page(self.comic, nid, scope, actor, row)
                if not 0 < len(data) <= self.assets.MAX_BYTES:
                    raise ValueError('COMIC_HANDOFF_ASSET_SIZE_LIMIT')
                images.append(data)
                if sum(map(len, images)) > MAX_ARCHIVE_BYTES:
                    raise ValueError('COMIC_HANDOFF_OUTPUT_SIZE_LIMIT')
                pins.append({'source': {'id': row['id'], 'version': row['version'],
                    'review_digest': page['review_digest'], 'document_digest': digest(row['document'])},
                    'duration_ms': page['duration_ms'], 'width': row['document']['width'],
                    'height': row['document']['height'], 'png_sha256': hashlib.sha256(data).hexdigest(),
                    'bytes': len(data), 'render_fingerprint': fingerprint})
            # Keep original authority/current source checks after all CPU work.
            for page in selected:
                self._page(nid, scope, actor, page)
            if fingerprint != rendering_fingerprint():
                raise StaleSourceError('COMIC_HANDOFF_RENDERER_CHANGED')
        guard()
        report = {'contract': CONTRACT, 'scope_key': context['scope_key'], 'incarnation': context['incarnation'],
                  'actor': actor, 'request': body.model_dump(), 'request_digest': digest(body.model_dump()),
                  'pages': pins, 'duration_ms': sum(p.duration_ms for p in body.pages),
                  'losses': list(LOSSES), 'automatic_dispatch': False, 'model_called': False,
                  'video_rendered': False, 'approval_inherited': False}
        report['preview_digest'] = digest(report)
        return report, tuple(images)

    def preview(self, nid, scope, actor, value, guard=lambda: None):
        """Return the bounded report and actual full-page PNGs without persistence."""
        body = HandoffRequest.model_validate(value)
        # A missing selection fails before opening a scope transaction.
        self._authority(nid, scope, actor, guard)
        for page in body.pages:
            self.comic._row(nid, scope, actor, page.id)
        with self._phase(nid, scope, actor, guard) as (_, context):
            return self._materialize(nid, scope, actor, body, context, guard)


    @contextmanager
    def _write_phase(self, nid, scope, actor, guard, *, write=False):
        self._authority(nid, scope, actor, guard)
        with self.owner.existing_owner_only(), self.production.timeline_inputs.phase(
                nid, scope, actor, guard, writable=write) as state:
            context = self._authority(nid, scope, actor, guard)
            yield state, context
            self._authority(nid, scope, actor, guard)

    @staticmethod
    def _request_id(value):
        import re
        if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,79}', value):
            raise ValueError('COMIC_HANDOFF_REQUEST_ID_INVALID')

    def _receipt(self, state, nid, scope, actor, request_id, context):
        self._request_id(request_id)
        rows = state['collections'].get(COLLECTION, {})
        matches = [r for r in rows.values() if isinstance(r, dict) and r.get('actor') == actor
                   and r.get('request_id') == request_id and r.get('incarnation') == context['incarnation']]
        if not matches:
            raise FileNotFoundError(request_id)
        if len(matches) != 1:
            raise ValueError('COMIC_HANDOFF_RECEIPT_AMBIGUOUS')
        row = matches[0]
        if (row.get('contract') != CONTRACT or row.get('novel_id') != nid or row.get('scope') != scope
                or rows.get(row.get('id')) is not row or type(row.get('version')) is not int
                or set(row) != {'id', 'contract', 'novel_id', 'scope', 'actor', 'incarnation', 'request_id',
                    'version', 'status', 'created_at', 'confirm', 'preview', 'steps', 'timeline_snapshot'}
                or not 1 <= row['version'] <= 8 or row.get('status') not in {'PLANNED', 'DRAFT_CREATED', 'CANCELLED'}):
            raise ValueError('COMIC_HANDOFF_RECEIPT_CORRUPT')
        request = HandoffConfirm.model_validate(row.get('confirm')).model_dump()
        report = row.get('preview')
        validate_preview(report)
        if (request['request_id'] != request_id or not isinstance(report, dict)
                or digest({k: v for k, v in report.items() if k != 'preview_digest'}) != report.get('preview_digest')
                or request['reviewed_preview_digest'] != report['preview_digest']
                or request['request'] != report.get('request') or report.get('request_digest') != digest(request['request'])
                or (report.get('actor'), report.get('scope_key'), report.get('incarnation')) !=
                   (actor, context['scope_key'], context['incarnation'])
                or not isinstance(row.get('steps'), list) or len(row['steps']) != len(request['request']['pages'])
                or len({step.get('asset_id') for step in row['steps']}) != len(row['steps'])):
            raise ValueError('COMIC_HANDOFF_RECEIPT_CORRUPT')
        for index, step in enumerate(row['steps']):
            if set(step) != {'asset_id', 'state', 'asset_version'} or step['state'] not in {'PENDING', 'READY'}:
                raise ValueError('COMIC_HANDOFF_RECEIPT_CORRUPT')
            self._origin(row, step, index)
            if ((step['state'] == 'PENDING' and step['asset_version'] is not None)
                    or (step['state'] == 'READY' and (type(step['asset_version']) is not int or step['asset_version'] != 1))):
                raise ValueError('COMIC_HANDOFF_RECEIPT_CORRUPT')
        snapshot = row.get('timeline_snapshot')
        if row['status'] == 'DRAFT_CREATED':
            if (not isinstance(snapshot, dict) or set(snapshot) != {'id', 'version', 'digest'}
                    or type(snapshot.get('version')) is not int or snapshot['version'] != 1
                    or any(step['state'] != 'READY' for step in row['steps'])):
                raise ValueError('COMIC_HANDOFF_RECEIPT_CORRUPT')
            from ..services.studio_timeline_render import _identity
            _identity(snapshot['id'])
            if not isinstance(snapshot['digest'], str) or not re.fullmatch(r'[a-f0-9]{64}', snapshot['digest']):
                raise ValueError('COMIC_HANDOFF_RECEIPT_CORRUPT')
        elif snapshot is not None:
            raise ValueError('COMIC_HANDOFF_RECEIPT_CORRUPT')
        return row

    def _origin(self, row, step, index):
        page = row['preview']['pages'][index]
        return marker({'contract': ASSET_CONTRACT, 'actor': row['actor'],
            'scope_key': row['preview']['scope_key'], 'incarnation': row['incarnation'],
            'receipt_id': row['id'], 'asset_id': step['asset_id'], 'index': index,
            'request_digest': row['preview']['request_digest'], 'preview_digest': row['preview']['preview_digest'],
            **{key: copy.deepcopy(page[key]) for key in ('source', 'width', 'height', 'png_sha256', 'render_fingerprint')}})

    def _verify_asset(self, row, index, guard):
        step = row['steps'][index]
        meta = self.assets.get(step['asset_id'], branch_id=row['scope'].get('branch_id'))
        if (record(meta) != self._origin(row, step, index) or meta['version'] != 1
                or meta.get('idempotency_key') != 'comic-page:' + row['id'] + ':' + str(index)):
            raise StaleSourceError('COMIC_HANDOFF_ASSET_CHANGED')
        self.assets.content(meta['id'], branch_id=row['scope'].get('branch_id'))
        guard()
        return meta

    def _public(self, row, guard):
        result = {key: copy.deepcopy(row[key]) for key in ('id', 'request_id', 'version', 'status', 'steps', 'preview')}
        for index, step in enumerate(row['steps']):
            observed = 'AWAITING_EXPLICIT_RESUME'
            if self.assets._meta_path(step['asset_id']).exists():
                self._verify_asset(row, index, guard)
                observed = 'READY' if step['state'] == 'READY' else 'COMMITTED_AWAITING_EXPLICIT_RESUME'
            elif self.assets._bin_path(step['asset_id']).exists():
                observed = 'UNINDEXED_BYTES_AWAITING_EXPLICIT_RESUME'
            elif step['state'] == 'READY':
                raise StaleSourceError('COMIC_HANDOFF_ASSET_MISSING')
            result['steps'][index]['observed_state'] = observed
        result['timeline_snapshot'] = copy.deepcopy(row.get('timeline_snapshot'))
        result.update(automatic_dispatch=False, model_called=False, video_rendered=False, approval_inherited=False,
                      source_current_checked=False)
        return result

    def status(self, nid, scope, actor, request_id, guard=lambda: None):
        with self._write_phase(nid, scope, actor, guard) as (state, context):
            row = self._receipt(state, nid, scope, actor, request_id, context)
            result = self._public(row, guard)
            if row['status'] == 'DRAFT_CREATED':
                # Read back the original row; never recreate a lost reply.
                result['timeline'] = self.production.timeline_get(nid, scope, actor, row['timeline_snapshot']['id'], guard)
                projected = result['timeline'].get('comic_handoff_origin')
                if (not isinstance(projected, dict) or projected['receipt_id'] != row['id']
                        or projected['request_id'] != row['request_id']
                        or projected['preview_digest'] != row['preview']['preview_digest']
                        or projected['creation_snapshot'] != row['timeline_snapshot']):
                    raise ValueError('COMIC_HANDOFF_TIMELINE_RECEIPT_CHANGED')
                result['timeline_state'] = ('CREATION_SNAPSHOT' if
                    (result['timeline']['version'], result['timeline']['timeline_digest']) ==
                    (row['timeline_snapshot']['version'], row['timeline_snapshot']['digest']) else 'MODIFIED_AFTER_CREATION')
            return result

    def confirm(self, nid, scope, actor, value, guard=lambda: None):
        body = HandoffConfirm.model_validate(value)
        with self._write_phase(nid, scope, actor, guard, write=True) as (state, context):
            try:
                prior = self._receipt(state, nid, scope, actor, body.request_id, context)
            except FileNotFoundError:
                prior = None
            if prior is not None:
                if prior['confirm'] != body.model_dump():
                    raise StaleSourceError('COMIC_HANDOFF_REQUEST_CONFLICT')
                return self.status(nid, scope, actor, body.request_id, guard)  # partial effects require explicit resume
            report, images = self._materialize(nid, scope, actor, body.request, context, guard)
            if body.reviewed_preview_digest != report['preview_digest']:
                raise StaleSourceError('COMIC_HANDOFF_PREVIEW_CHANGED')
            rows = state['collections'].setdefault(COLLECTION, {})
            if sum(r.get('incarnation') == context['incarnation'] for r in rows.values()) >= MAX_RECEIPTS:
                raise ValueError('COMIC_HANDOFF_RECEIPT_LIMIT')
            usage, _ = self._usage(state, nid, scope, context, guard)
            if (usage['count'] + len(images) > self.workspace.MAX_ASSETS
                    or usage['bytes'] + sum(map(len, images)) > self.workspace.MAX_PROJECT_BYTES):
                raise ValueError('CREATIVE_PROJECT_ASSET_QUOTA')
            self.workspace.storage_admission.require(sum(map(len, images)))
            rid = str(uuid4())
            rows[rid] = {'id': rid, 'contract': CONTRACT, 'novel_id': nid, 'scope': copy.deepcopy(scope),
                'actor': actor, 'incarnation': context['incarnation'], 'request_id': body.request_id,
                'version': 1, 'status': 'PLANNED', 'created_at': now(), 'confirm': body.model_dump(),
                'preview': report, 'steps': [{'asset_id': str(uuid4()), 'state': 'PENDING', 'asset_version': None}
                                           for _ in images], 'timeline_snapshot': None}
        return self.resume(nid, scope, actor, body.request_id, 1, guard)

    def _usage(self, state, nid, scope, context, guard):
        usage = self.assets.project_usage(nid, branch_id=scope.get('branch_id'))
        orphan_bytes = {}
        rows = [r for r in state['collections'].get(COLLECTION, {}).values()
                if r.get('incarnation') == context['incarnation']]
        if len(rows) > MAX_RECEIPTS:
            raise ValueError('COMIC_HANDOFF_RECEIPT_LIMIT')
        seen = set()
        for candidate in rows:
            row = self._receipt(state, nid, scope, candidate['actor'], candidate['request_id'], context)
            for index, step in enumerate(row['steps']):
                aid = step['asset_id']
                if aid in seen: raise ValueError('COMIC_HANDOFF_RECEIPT_CORRUPT')
                seen.add(aid)
                if self.assets._meta_path(aid).exists():
                    self._verify_asset(row, index, guard)
                    continue
                try: info = self.assets._bin_path(aid).lstat()
                except FileNotFoundError: continue
                if (not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= self.assets.MAX_BYTES
                        or getattr(info, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400)):
                    raise ValueError('COMIC_HANDOFF_ORPHAN_INVALID')
                orphan_bytes[aid] = info.st_size
        return {'count': usage['count'] + len(orphan_bytes), 'bytes': usage['bytes'] + sum(orphan_bytes.values())}, orphan_bytes

    def resume(self, nid, scope, actor, request_id, expected_version, guard=lambda: None):
        if type(expected_version) is not int or not 1 <= expected_version <= 8:
            raise ValueError('COMIC_HANDOFF_VERSION_INVALID')
        with self._write_phase(nid, scope, actor, guard) as (state, context):
            row = self._receipt(state, nid, scope, actor, request_id, context)
            check_version(row, expected_version)
            if row['status'] != 'PLANNED':
                raise ValueError('COMIC_HANDOFF_NOT_RESUMABLE')
            report, images = self._materialize(nid, scope, actor, HandoffRequest.model_validate(row['preview']['request']), context, guard)
            if report != row['preview']:
                raise StaleSourceError('COMIC_HANDOFF_PREVIEW_CHANGED')
        version = expected_version
        for index, data in enumerate(images):
            with self._write_phase(nid, scope, actor, guard, write=True) as (state, context):
                row = self._receipt(state, nid, scope, actor, request_id, context)
                check_version(row, version)
                if row['status'] != 'PLANNED': raise ValueError('COMIC_HANDOFF_NOT_RESUMABLE')
                self._require_sources(nid, scope, actor, row, guard)
                step = row['steps'][index]
                if step['state'] == 'READY':
                    self._verify_asset(row, index, guard)
                    continue
                if self.assets._meta_path(step['asset_id']).exists():
                    meta = self._verify_asset(row, index, guard)
                else:
                    usage, orphans = self._usage(state, nid, scope, context, guard)
                    retained = orphans.get(step['asset_id'], 0)
                    if (usage['count'] + (0 if retained else 1) > self.workspace.MAX_ASSETS
                            or usage['bytes'] - retained + len(data) > self.workspace.MAX_PROJECT_BYTES):
                        raise ValueError('CREATIVE_PROJECT_ASSET_QUOTA')
                    self.workspace.storage_admission.require(len(data))
                    def before_commit():
                        self._authority(nid, scope, actor, guard)
                        self._require_sources(nid, scope, actor, row, guard)
                        self.workspace.storage_admission.require(1)
                    meta = self.assets.create(nid, 'comic-page-' + str(index + 1) + '.png',
                        base64.b64encode(data).decode('ascii'), 'image/png', 'image',
                        'comic-page:' + row['id'] + ':' + str(index), branch_id=scope.get('branch_id'),
                        required_features=tuple(sorted(FEATURES)), guard=before_commit,
                        _initial_comic_page=self._origin(row, step, index))
                if meta['id'] != step['asset_id']:
                    raise ValueError('COMIC_HANDOFF_ASSET_ID_CHANGED')
                self._verify_asset(row, index, guard)
                step.update(state='READY', asset_version=1)
                row['version'] += 1
                version = row['version']
        with self._write_phase(nid, scope, actor, guard, write=True) as (state, context):
            row = self._receipt(state, nid, scope, actor, request_id, context)
            check_version(row, version)
            if row['status'] != 'PLANNED': raise ValueError('COMIC_HANDOFF_NOT_RESUMABLE')
            self._require_sources(nid, scope, actor, row, guard)
            clips, start = [], 0
            for index, (step, page) in enumerate(zip(row['steps'], row['preview']['pages'])):
                meta = self._verify_asset(row, index, guard)
                clips.append({'id': 'comic-page-' + str(index + 1), 'source_snapshot': {'kind': 'ASSET',
                    'id': meta['id'], 'asset_kind': 'image', 'version': meta['version'], 'digest': meta['sha256']},
                    'start_ms': start, 'in_ms': 0, 'out_ms': page['duration_ms'], 'include_audio': False})
                start += page['duration_ms']
            request = row['preview']['request']
            timeline = {'schema_version': 2, 'duration_ms': start,
                **{k: request[k] for k in ('width', 'height', 'fps')},
                'tracks': [{'id': 'comic-pages-video', 'kind': 'VIDEO', 'order': 0, 'clips': clips}], 'captions': []}
            saved = self.production.timeline_save(nid, scope, actor, None,
                {'expected_version': 0, 'title': request['title'], 'timeline': timeline}, guard)
            snapshot = {'id': saved['id'], 'version': saved['version'], 'digest': saved['timeline_digest']}
            from ..creative.production_execution import TIMELINES
            state['collections'][TIMELINES][saved['id']]['comic_handoff_origin'] = {
                'contract': CONTRACT, 'receipt_id': row['id'], 'request_id': request_id,
                'preview_digest': row['preview']['preview_digest'], 'creation_snapshot': copy.deepcopy(snapshot)}
            row.update(status='DRAFT_CREATED', timeline_snapshot=snapshot, version=row['version'] + 1)
        return self.status(nid, scope, actor, request_id, guard)

    def cancel(self, nid, scope, actor, request_id, expected_version, guard=lambda: None):
        if type(expected_version) is not int:
            raise ValueError('COMIC_HANDOFF_VERSION_INVALID')
        with self._write_phase(nid, scope, actor, guard, write=True) as (state, context):
            row = self._receipt(state, nid, scope, actor, request_id, context)
            check_version(row, expected_version)
            if row['status'] != 'PLANNED': raise ValueError('COMIC_HANDOFF_NOT_CANCELLABLE')
            row.update(status='CANCELLED', version=row['version'] + 1)
            # Retained Assets remain explicit receipt evidence; cancellation is
            # never an inferred rollback or an implicit destructive cleanup.
            return self._public(row, guard)

    def source_current(self, nid, scope, actor, meta, guard=lambda: None):
        """Only call under the original raw scope -> Asset -> project phase."""
        if not self.production.timeline_inputs.in_phase(nid, scope, actor):
            raise ValueError('COMIC_HANDOFF_SOURCE_PHASE_REQUIRED')
        origin = record(meta)
        context = self._authority(nid, scope, actor, guard)
        if (origin['actor'], origin['scope_key'], origin['incarnation']) != (actor, context['scope_key'], context['incarnation']):
            raise StaleSourceError('COMIC_HANDOFF_SOURCE_OWNER_CHANGED')
        state = self.owner.read(nid, scope)
        receipt = self._receipt(state, nid, scope, actor, self._request_for_receipt(state, origin['receipt_id']), context)
        if (receipt['id'] != origin['receipt_id'] or receipt['status'] == 'CANCELLED'
                or origin['index'] >= len(receipt['steps'])
                or self._origin(receipt, receipt['steps'][origin['index']], origin['index']) != origin):
            raise StaleSourceError('COMIC_HANDOFF_SOURCE_CHANGED')
        self._require_sources(nid, scope, actor, receipt, guard)
        guard()
        return origin


    @staticmethod
    def _request_for_receipt(state, receipt_id):
        row = state['collections'].get(COLLECTION, {}).get(receipt_id)
        if not isinstance(row, dict):
            raise ValueError('COMIC_HANDOFF_RECEIPT_UNAVAILABLE')
        return row.get('request_id')

    def _require_sources(self, nid, scope, actor, receipt, guard):
        for page in receipt['preview']['pages']:
            current, _ = self._page(nid, scope, actor, page['source'])
            if (digest(current['document']) != page['source']['document_digest']
                    or rendering_fingerprint() != page['render_fingerprint']):
                raise StaleSourceError('COMIC_HANDOFF_SOURCE_CHANGED')
        guard()
