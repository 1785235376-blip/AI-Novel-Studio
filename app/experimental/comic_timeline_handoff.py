"""Read-only whole-page preview for an explicit original Comic handoff.

This first slice owns no persistence, Asset creation, approval, job or queue.
Confirm/resume require coordinated native Asset and Timeline owner wiring.
"""
from __future__ import annotations

import hashlib
from contextlib import contextmanager
from typing import Literal

from pydantic import Field, model_validator

from .media import StrictModel, digest
from .common import StaleSourceError, check_version
from .comic_layers import ora_decode_budget
from .comic_publication import _render_page
from .comic_publication_budget import publication_budget, MAX_PAGE_PIXELS, MAX_ARCHIVE_BYTES
from ..services.comic_page_origin import FEATURES, ID, DIGEST

CONTRACT = 'studio-comic-timeline-handoff/1'
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
        from .comic_layouts import renderer_status, font_status
        selected = [page.model_dump() for page in body.pages]
        # Admit every page and aggregate geometry before decoding even one source.
        rows = [self.comic._row(nid, scope, actor, page['id']) for page in selected]
        for row, page in zip(rows, selected):
            check_version(row, page['version'])
            if not self.comic._independent(row) or row['document']['preset'] != 'PAGE':
                raise ValueError('COMIC_HANDOFF_INDEPENDENT_PAGE_REQUIRED')
        if sum(r['document']['width'] * r['document']['height'] for r in rows) > MAX_PAGE_PIXELS:
            raise ValueError('COMIC_HANDOFF_PAGE_PIXEL_LIMIT')
        fingerprint = digest({'recipe': 'original-comic-full-page-png/1',
                              'renderer': renderer_status(), 'font': font_status()})
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
            if fingerprint != digest({'recipe': 'original-comic-full-page-png/1',
                                     'renderer': renderer_status(), 'font': font_status()}):
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
