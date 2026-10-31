"""Bounded frame preparation over the original workspace and Asset owners.

The interval is an observation window, never a V2V crop or semantic condition.
Preview owns no durable state. Explicit save commits one reviewed image through
AssetLibraryService, with lineage present in its first metadata write.
"""
from __future__ import annotations
import base64
import errno
import hashlib
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from ..experimental.common import StaleSourceError
from ..experimental.store import canonical
from ..services.asset_library_service import AssetIdempotencyConflict
from ..services import studio_video_reference_origin as origin_contract


class ReferencePreview(BaseModel):
    model_config = ConfigDict(strict=True, extra='forbid', allow_inf_nan=False)
    contract: Literal['studio-video-reference-preview/1']
    source_version: int = Field(ge=1, le=2**53-1)
    source_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    in_ms: int = Field(ge=0, lt=60000)
    out_ms: int = Field(gt=0, le=60000)
    sample_count: int = Field(ge=1, le=8)

    @model_validator(mode='after')
    def bounded_interval(self):
        if not 0 < self.out_ms - self.in_ms <= 10000:
            raise ValueError('VIDEO_REFERENCE_INTERVAL_INVALID')
        return self


class ReferenceSave(ReferencePreview):
    contract: Literal['studio-video-reference-asset/1']
    selected_index: int = Field(ge=0, le=7)
    reviewed_preview_digest: str = Field(pattern=r'^[a-f0-9]{64}$')
    reviewed_png_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    confirm_reference: Literal[True]
    idempotency_key: str = Field(pattern=r'^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$')

    @field_validator('confirm_reference', mode='before')
    @classmethod
    def exact_confirmation(cls, value):
        if value is not True: raise ValueError('VIDEO_REFERENCE_CONFIRMATION_REQUIRED')
        return value

    @model_validator(mode='after')
    def selected_frame(self):
        if self.selected_index >= self.sample_count: raise ValueError('VIDEO_REFERENCE_SELECTION_INVALID')
        return self


def digest(value):
    return hashlib.sha256(canonical(value).encode('utf-8')).hexdigest()


class VideoReferencePreparation:
    def __init__(self, workspace): self.workspace = workspace

    @staticmethod
    def _guard(guard):
        if not callable(guard): raise ValueError('VIDEO_REFERENCE_AUTHORITY_REQUIRED')
        def current():
            from ..experimental.flags import require_flag
            guard()
            for feature in sorted(origin_contract.FEATURES): require_flag(feature)
        current()
        return current

    def _source(self, nid, scope, aid, body, guard):
        workspace = self.workspace
        row = workspace._row(nid, scope, aid)
        if (row.get('_owner_actor_id') is not None or row['kind'] != 'video'
                or row['media_type'] not in {'video/mp4', 'video/webm'}
                or (row['version'], row['sha256']) != (body.source_version, body.source_sha256)):
            raise StaleSourceError('VIDEO_REFERENCE_SOURCE_CHANGED')
        view = workspace._view(nid, scope, row)
        if view['provenance']['integrity'] != 'VERIFIED' or view['provenance']['stale']:
            raise StaleSourceError('VIDEO_REFERENCE_SOURCE_CHANGED')
        snapshot = {'kind': 'ASSET', 'id': aid, 'version': body.source_version,
                    'digest': body.source_sha256, 'asset_kind': 'video'}
        row, data = workspace.pinned_content(nid, scope, snapshot, max_bytes=25 * 1024 * 1024, guard=guard)
        return row, data

    def _prepare(self, nid, scope, aid, body, guard):
        workspace = self.workspace
        if workspace.project(nid, scope)['project']['entry_kind'] != 'NEUTRAL_STUDIO':
            raise ValueError('STUDIO_NEUTRAL_PROJECT_ACTIVATION_REQUIRED')
        with workspace._asset_scope(nid, scope):
            incarnation = workspace.store.incarnation(nid)
            _, data = self._source(nid, scope, aid, body, guard)
        def current():
            guard()
            if workspace.store.incarnation(nid) != incarnation:
                raise StaleSourceError('VIDEO_REFERENCE_SOURCE_CHANGED')
        from ..services.studio_video_reference_frames import prepare_frames
        measured = prepare_frames(data, body.in_ms, body.out_ms, body.sample_count, guard=current)
        current()
        with workspace._asset_scope(nid, scope):
            self._source(nid, scope, aid, body, current)
        result = {'contract': 'studio-video-reference-preview/1', 'novel_id': nid,
                  'branch_id': scope.get('branch_id'),
                  'source': {'id': aid, 'version': body.source_version, 'sha256': body.source_sha256},
                  'in_ms': body.in_ms, 'out_ms': body.out_ms, 'sample_count': body.sample_count,
                  **measured, 'model_called': False, 'semantic_analysis': False}
        result['preview_digest'] = digest(result)
        current()
        return result, incarnation

    def preview(self, nid, scope, aid, value, guard):
        body = ReferencePreview.model_validate(value); current = self._guard(guard)
        with self.workspace.store.existing_owner_only():
            return self._prepare(nid, scope, aid, body, current)[0]

    def save(self, nid, scope, actor, aid, value, guard):
        body = ReferenceSave.model_validate(value); current = self._guard(guard)
        if not isinstance(actor, str) or not actor: raise ValueError('VIDEO_REFERENCE_AUTHORITY_REQUIRED')
        with self.workspace.store.existing_owner_only():
            return self._save(nid, scope, actor, aid, body, current)

    def _save(self, nid, scope, actor, aid, body, guard):
        workspace = self.workspace
        scope_key = workspace.store.key(nid, scope)
        key = 'studio-video-reference:' + digest([scope_key, body.idempotency_key])
        with workspace._asset_scope(nid, scope):
            observed = workspace.assets.video_reference_retry(nid, key, branch_id=scope.get('branch_id'))
            observed_id = observed['id'] if observed else None
        preview, incarnation = self._prepare(nid, scope, aid, body, guard)
        frame = preview['frames'][body.selected_index]
        if (preview['preview_digest'] != body.reviewed_preview_digest or frame['png_sha256'] != body.reviewed_png_sha256):
            raise StaleSourceError('VIDEO_REFERENCE_REVIEW_CHANGED')
        png = base64.b64decode(frame['content_base64'], validate=True)
        origin = origin_contract.marker({'contract': origin_contract.CONTRACT, 'actor': actor,
            'scope_key': scope_key, 'incarnation': incarnation, 'source': preview['source'],
            'in_ms': body.in_ms, 'out_ms': body.out_ms, 'sample_count': body.sample_count,
            'selected_index': body.selected_index, 'preview_digest': preview['preview_digest'],
            'time_base': preview['media']['time_base'],
            **{k: frame[k] for k in ('source_frame_index', 'pts', 'time_ms', 'width', 'height', 'png_sha256')}})
        with workspace._asset_scope(nid, scope):
            def source_current():
                guard()
                if workspace.store.incarnation(nid) != incarnation: raise StaleSourceError('VIDEO_REFERENCE_SOURCE_CHANGED')
                return self._source(nid, scope, aid, body, guard)[0]
            source = source_current()
            prior = workspace.assets.video_reference_retry(nid, key, branch_id=scope.get('branch_id'))
            if observed_id is not None and (prior is None or prior['id'] != observed_id):
                raise ValueError('VIDEO_REFERENCE_RETRY_CHANGED')
            if prior is not None and prior.get(origin_contract.PRIVATE) != origin:
                raise AssetIdempotencyConflict('VIDEO_REFERENCE_IDEMPOTENCY_CONFLICT')
            usage = workspace.assets.project_usage(nid, branch_id=scope.get('branch_id'))
            if prior is None:
                if usage['count'] >= workspace.MAX_ASSETS or usage['bytes'] + len(png) > workspace.MAX_PROJECT_BYTES:
                    raise ValueError('CREATIVE_PROJECT_ASSET_QUOTA')
                workspace.storage_admission.require(len(png))
            def before_commit():
                source_current()
                if prior is None: workspace.storage_admission.require(1)
            features = tuple(sorted(origin_contract.FEATURES | set(source.get('_required_features', []))))
            try:
                row = workspace.assets.create(nid, 'video-reference-frame.png', frame['content_base64'], 'image/png', 'image', key,
                    branch_id=scope.get('branch_id'), required_features=features, guard=before_commit,
                    _initial_video_reference=origin, _video_reference_expected_retry_id=prior['id'] if prior else None)
            except OSError as exc:
                if exc.errno == errno.ENOSPC:
                    from .storage_admission import StudioStorageCapacityError
                    raise StudioStorageCapacityError('CREATIVE_STORAGE_LOW_SPACE') from None
                raise
            before_commit()
            result = {'asset': workspace._view(nid, scope, row), 'receipt': {
                **origin_contract.project(origin), 'replayed': prior is not None, 'asset_created': prior is None}}
        guard()
        if workspace.store.incarnation(nid) != incarnation: raise StaleSourceError('VIDEO_REFERENCE_SOURCE_CHANGED')
        return result
