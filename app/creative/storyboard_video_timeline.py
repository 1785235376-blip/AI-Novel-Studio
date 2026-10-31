"""Bounded video-only assembly through original Storyboard/Timeline/Asset owners.

No new collection, engine, queue, provider or approval authority. Preview reads
formal reviewed outputs, and Save atomically appends one original Timeline.
"""
from copy import deepcopy
from pydantic import Field, model_validator
from .models import StrictCreativeModel, Identifier
from .storyboard import (StoryboardApproval, OriginalSnapshot, StoryboardVideoResult,
    ShotAction, storyboard_receipt, validate_storyboard_timeline_origin)
from .production_execution import TIMELINES, digest
from ..experimental.common import StaleSourceError, check_version

CONTRACT = 'studio-storyboard-video-timeline/1'
RECEIPT = 'storyboard_video_create_receipt'


class VideoClipSelection(StrictCreativeModel):
    shot_id: Identifier
    shot_version: int = Field(ge=1, strict=True)
    shot_digest: str = Field(pattern=r'^[a-f0-9]{64}$', strict=True)
    in_ms: int = Field(default=0, ge=0, le=600_000, strict=True)
    out_ms: int | None = Field(default=None, ge=1, le=600_000, strict=True)
    include_audio: bool = Field(default=False, strict=True)


class VideoTimelineInput(StoryboardApproval):
    title: str = Field(min_length=1, max_length=240, strict=True)
    clips: list[VideoClipSelection] = Field(min_length=1, max_length=4)
    width: int = Field(default=1280, ge=16, le=1920, strict=True)
    height: int = Field(default=720, ge=16, le=1080, strict=True)
    fps: int = Field(default=24, ge=1, le=60, strict=True)

    @model_validator(mode='after')
    def unique_shots(self):
        if len({clip.shot_id for clip in self.clips}) != len(self.clips):
            raise ValueError('STORYBOARD_VIDEO_TIMELINE_DUPLICATE_SHOT')
        return self


class VideoTimelineCreate(VideoTimelineInput):
    request_id: str = Field(pattern=r'^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$', strict=True)
    preview_digest: str = Field(pattern=r'^[a-f0-9]{64}$', strict=True)


class VideoCreationReceipt(StrictCreativeModel):
    contract: str
    request: VideoTimelineCreate
    document_id: Identifier
    request_digest: str = Field(pattern=r'^[a-f0-9]{64}$', strict=True)
    creation_snapshot: OriginalSnapshot
    origin_digest: str = Field(pattern=r'^[a-f0-9]{64}$', strict=True)
    preview: dict


def _request_digest(rid, body):
    return digest({'contract': CONTRACT, 'document_id': rid, 'request': body.model_dump()})


def _metadata(owner, nid, scope, actor, rid, body, guard, *, state=None):
    row = owner.creative.get(nid, scope, rid); check_version(row, body.expected_version)
    receipt = storyboard_receipt(row)
    if not receipt['approved'] or receipt['content_digest'] != body.reviewed_content_digest:
        raise StaleSourceError('CREATIVE_STORYBOARD_APPROVAL_REQUIRED')
    results = []
    for clip in body.clips:
        _, shot = owner._owned_shot(row, clip.shot_id, ShotAction(expected_version=body.expected_version,
            shot_version=clip.shot_version, shot_digest=clip.shot_digest))
        if not shot.get('video_result'): raise ValueError('STORYBOARD_VIDEO_TIMELINE_REVIEWED_VIDEO_REQUIRED')
        result = StoryboardVideoResult.model_validate(shot['video_result'])
        # Full original job/candidate admission is outside the writable Asset
        # phase; byte/provenance checks are repeated under the original phase.
        if state is None:
            job, checked = owner._approved_video(nid, scope, actor, result.asset, result.job, guard)
            if checked != shot['video_result']: raise StaleSourceError('CREATIVE_STORYBOARD_VIDEO_RESULT_CHANGED')
        if state is not None:
            owner._video_metadata(nid, scope, receipt, result.model_dump(), guard, state=state)
        results.append(result.model_dump())
    guard()
    return receipt, results


def _resolve(owner, nid, scope, actor, rid, body, guard):
    if owner.production is None: raise ValueError('CREATIVE_STORYBOARD_TIMELINE_OWNER_REQUIRED')
    owner.production._base(nid, scope, actor, guard)
    receipt, results = _metadata(owner, nid, scope, actor, rid, body, guard)
    with owner._phase(nid, scope, actor, guard) as state:
        checked_receipt, checked_results = _metadata(owner, nid, scope, actor, rid, body, guard, state=state)
        if checked_receipt != receipt or checked_results != results: raise StaleSourceError('STORYBOARD_VIDEO_TIMELINE_SOURCE_CHANGED')
    items, clips, start, total = [], [], 0, 0
    from ..services.studio_timeline_render import MAX_SOURCE_BYTES
    for index, (selection, result) in enumerate(zip(body.clips, results)):
        asset = result['asset']
        pin = {'kind': 'ASSET', 'asset_kind': 'video', 'id': asset['asset_id'], 'version': asset['version'], 'digest': asset['digest']}
        source = owner.production.source(nid, scope, pin, guard, inspection_guard=guard, include_video_dimensions=True)
        measured = source['measured']; total += len(source['data'])
        if total > MAX_SOURCE_BYTES: raise ValueError('STUDIO_TIMELINE_SOURCE_BYTES_LIMIT')
        out_ms = measured['duration_ms'] if selection.out_ms is None else selection.out_ms
        if not 0 <= selection.in_ms < out_ms <= measured['duration_ms']:
            raise ValueError('CREATIVE_STORYBOARD_VIDEO_RANGE_INVALID')
        if selection.include_audio:
            from ..media_files import inspect_media
            inspect_media(source['data'], 'audio', guard=guard)
        clip_id = f'storyboard-video-{index + 1}'
        clip = {'id': clip_id, 'source_snapshot': pin, 'start_ms': start, 'in_ms': selection.in_ms, 'out_ms': out_ms, 'include_audio': selection.include_audio}
        clips.append(clip)
        items.append({'clip_id': clip_id, 'shot_id': selection.shot_id, 'shot_version': selection.shot_version,
            'shot_digest': selection.shot_digest, 'video_result': result, 'measured': measured, 'start_ms': start,
            'in_ms': selection.in_ms, 'out_ms': out_ms, 'include_audio': selection.include_audio})
        start += out_ms - selection.in_ms
    if start > 600_000: raise ValueError('CREATIVE_STORYBOARD_TIMELINE_DURATION_LIMIT')
    timeline = {'schema_version': 2, 'duration_ms': start, 'width': body.width, 'height': body.height, 'fps': body.fps,
        'tracks': [{'id': 'storyboard-video', 'kind': 'VIDEO', 'order': 0, 'clips': clips}], 'captions': []}
    from ..services.studio_timeline_render import normalize_studio_timeline
    timeline = normalize_studio_timeline(timeline)
    checked_receipt, checked_results = _metadata(owner, nid, scope, actor, rid, body, guard)
    with owner._phase(nid, scope, actor, guard) as state:
        _metadata(owner, nid, scope, actor, rid, body, guard, state=state)
    if checked_receipt != receipt or checked_results != results: raise StaleSourceError('STORYBOARD_VIDEO_TIMELINE_SOURCE_CHANGED')
    request = VideoTimelineInput.model_validate(body.model_dump(exclude={'request_id', 'preview_digest'})).model_dump()
    result = {'contract': CONTRACT, 'document_snapshot': receipt['document_snapshot'], 'content_digest': receipt['content_digest'],
        'request': request, 'clips': items, 'timeline': timeline, 'automatic_dispatch': False, 'model_called': False, 'rendered': False}
    result['preview_digest'] = digest([actor, scope, result])
    guard()
    return result


def preview(owner, nid, scope, actor, rid, value, guard):
    return _resolve(owner, nid, scope, actor, rid, VideoTimelineInput.model_validate(value), guard)


def validate_video_creation_receipt(row, *, history=None):
    proof = VideoCreationReceipt.model_validate(row[RECEIPT]); body = proof.request; shown = proof.preview
    origin = validate_storyboard_timeline_origin(row, history=history)
    ancestors = row.get('history', []) if history is None else history
    snapshots = [*[item for item in ancestors if item.get('version') != row['version']], row]
    created = [item for item in snapshots if item.get('version') == 1]
    if (proof.contract != CONTRACT or proof.document_id != origin['document_snapshot']['id'] or len(created) != 1
            or proof.request_digest != _request_digest(proof.document_id, body) or proof.origin_digest != digest(origin)
            or proof.creation_snapshot.model_dump() != origin['timeline_snapshot'] or proof.creation_snapshot.version != 1
            or created[0]['timeline'] != shown['timeline'] or created[0]['title'] != body.title
            or shown['document_snapshot'] != origin['document_snapshot'] or shown['content_digest'] != origin['content_digest']
            or shown['request'] != body.model_dump(exclude={'request_id', 'preview_digest'})
            or shown['preview_digest'] != body.preview_digest
            or digest([row['created_by'], row['scope'], {k:v for k,v in shown.items() if k != 'preview_digest'}]) != body.preview_digest
            or origin['shots'] != [{k:item[k] for k in ('clip_id','shot_id','shot_version','shot_digest')} for item in shown['clips']]):
        raise StaleSourceError('STORYBOARD_VIDEO_TIMELINE_RECEIPT_CHANGED')
    return proof.model_dump()


def _find(owner, nid, scope, actor, rid, request_id, context, state):
    owner.creative.get(nid, scope, rid)
    found = []
    for row in state['collections'].get(TIMELINES, {}).values():
        if row.get('created_by') != actor or RECEIPT not in row: continue
        proof = validate_video_creation_receipt(row)
        if proof['request']['request_id'] != request_id: continue
        owner.production._owned_timeline(nid, scope, actor, row['id'], context, state)
        if proof['document_id'] != rid: raise StaleSourceError('CREATIVE_STORYBOARD_CREATE_IDEMPOTENCY_CONFLICT')
        found.append(row)
    if len(found) > 1: raise ValueError('CREATIVE_STORYBOARD_CREATE_RECEIPT_AMBIGUOUS')
    return found


def _response(owner, row, scope, replayed):
    return {'contract': CONTRACT, 'creation_receipt': validate_video_creation_receipt(row),
        'timeline': owner.production._timeline_view(row, scope), 'storyboard_origin': deepcopy(row['storyboard_origin']),
        'replayed': replayed, 'automatic_dispatch': False, 'model_called': False, 'rendered': False}


def create(owner, nid, scope, actor, rid, value, guard):
    body = VideoTimelineCreate.model_validate(value)
    context = owner.production._base(nid, scope, actor, guard)
    # Check durable UNKNOWN recovery before any new source work.
    with owner._phase(nid, scope, actor, guard) as state:
        matches = _find(owner, nid, scope, actor, rid, body.request_id, context, state)
        if matches:
            if validate_video_creation_receipt(matches[0])['request_digest'] != _request_digest(rid, body):
                raise StaleSourceError('CREATIVE_STORYBOARD_CREATE_IDEMPOTENCY_CONFLICT')
            guard(); return _response(owner, matches[0], scope, True)
    shown = _resolve(owner, nid, scope, actor, rid, body, guard)
    if shown['preview_digest'] != body.preview_digest: raise StaleSourceError('STORYBOARD_VIDEO_TIMELINE_PREVIEW_CHANGED')
    with owner._phase(nid, scope, actor, guard, write=True) as state:
        matches = _find(owner, nid, scope, actor, rid, body.request_id, context, state)
        if matches:
            if validate_video_creation_receipt(matches[0])['request_digest'] != _request_digest(rid, body):
                raise StaleSourceError('CREATIVE_STORYBOARD_CREATE_IDEMPOTENCY_CONFLICT')
            guard(); return _response(owner, matches[0], scope, True)
        receipt, results = _metadata(owner, nid, scope, actor, rid, body, guard, state=state)
        if receipt['document_snapshot'] != shown['document_snapshot'] or results != [item['video_result'] for item in shown['clips']]:
            raise StaleSourceError('STORYBOARD_VIDEO_TIMELINE_SOURCE_CHANGED')
        timeline = owner.production.timeline_save(nid, scope, actor, None, {'expected_version': 0, 'title': body.title, 'timeline': shown['timeline']}, guard)
        row = state['collections'][TIMELINES][timeline['id']]
        origin = {'contract': 'studio-storyboard-timeline-draft/1', 'document_snapshot': receipt['document_snapshot'],
            'content_digest': receipt['content_digest'], 'timeline_snapshot': {'id': row['id'], 'version': row['version'], 'digest': row['timeline_digest']},
            'shots': [{k:item[k] for k in ('clip_id','shot_id','shot_version','shot_digest')} for item in shown['clips']], 'model_called': False, 'rendered': False}
        row['storyboard_origin'] = origin
        row[RECEIPT] = {'contract': CONTRACT, 'request': body.model_dump(), 'document_id': rid,
            'request_digest': _request_digest(rid, body), 'creation_snapshot': origin['timeline_snapshot'], 'origin_digest': digest(origin), 'preview': shown}
        owner.production._capacity(state); guard()
        return _response(owner, row, scope, False)


def recover(owner, nid, scope, actor, rid, request_id, guard):
    import re
    if not isinstance(request_id, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,99}', request_id):
        raise ValueError('CREATIVE_STORYBOARD_CREATE_REQUEST_INVALID')
    context = owner.production._base(nid, scope, actor, guard)
    with owner._phase(nid, scope, actor, guard) as state:
        matches = _find(owner, nid, scope, actor, rid, request_id, context, state)
        if not matches: raise FileNotFoundError(request_id)
        guard(); return _response(owner, matches[0], scope, True)
