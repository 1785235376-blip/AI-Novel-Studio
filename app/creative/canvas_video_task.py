"""Typed single-card adapter to the original Timeline queue and CPU renderer.

No collection, worker, provider or alternate execution graph is owned here.
The author explicitly saves one original Timeline before preview/queue.
"""
from copy import deepcopy
import hashlib
import shutil
from typing import Literal

from pydantic import Field, field_validator, model_serializer, model_validator

from ..experimental.common import StaleSourceError
from ..experimental.store import canonical
from ..services.studio_timeline_export import export_profile_digest, validate_export_admission
from ..services.studio_timeline_render import normalize_studio_timeline
from .production_contracts import ProductionSourceSnapshot, Name, Digest
from .production_execution_models import CanvasReturnBinding, ExecutionModel


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def pin(source):
    return source.model_dump(exclude={'reference_only'}, exclude_none=True)


class CanvasVideoReturnBinding(CanvasReturnBinding):
    allowed_asset_kinds = frozenset({'video'})

    @field_validator('source', mode='before')
    @classmethod
    def fresh_video_pin(cls, value):
        if isinstance(value, dict) and 'reference_only' in value:
            raise ValueError('STUDIO_CANVAS_VIDEO_SOURCE_INVALID')
        return value


class VideoRange(ExecutionModel):
    in_ms: int = Field(ge=0, le=36_000_000)
    out_ms: int = Field(gt=0, le=36_000_000)
    include_audio: bool | None = None

    @field_validator('include_audio', mode='before')
    @classmethod
    def strict_audio_choice(cls, value):
        # Omission preserves the old silent command identity. Explicit null is not a choice.
        if type(value) is not bool:
            raise ValueError('STUDIO_CANVAS_VIDEO_AUDIO_CHOICE_INVALID')
        return value

    @model_serializer(mode='wrap')
    def preserve_silent_identity(self, handler):
        value = handler(self)
        if self.include_audio is None:
            value.pop('include_audio', None)
        return value

    @model_validator(mode='after')
    def frame_grid(self):
        if self.in_ms % 40 or self.out_ms % 40 or not 0 < self.out_ms-self.in_ms <= 120_000:
            raise ValueError('STUDIO_CANVAS_VIDEO_RANGE_INVALID')
        return self


class TimelinePin(ExecutionModel):
    id: Name
    version: int = Field(ge=1, le=2**53-1)
    digest: Digest


class CanvasVideoCommand(ExecutionModel):
    contract: Literal['studio-canvas-video-trim/1']
    operation_id: Literal['m9.timeline.multitrack']
    request_id: str = Field(pattern=r'^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$')
    provider_id: None
    model_id: None
    prompt: Literal['']
    allow_cloud: Literal[False]
    license_note: Literal['']
    parameters: VideoRange
    source_snapshots: list[ProductionSourceSnapshot] = Field(min_length=1, max_length=1)
    timeline_snapshot: TimelinePin
    canvas_return: CanvasVideoReturnBinding

    @field_validator('source_snapshots', mode='before')
    @classmethod
    def fresh_sources(cls, value):
        if isinstance(value, list) and any(isinstance(s, dict) and 'reference_only' in s for s in value):
            raise ValueError('STUDIO_CANVAS_VIDEO_SOURCE_INVALID')
        return value

    @model_validator(mode='after')
    def exact_source(self):
        if pin(self.source_snapshots[0]) != pin(self.canvas_return.source):
            raise ValueError('STUDIO_CANVAS_VIDEO_SOURCE_CHANGED')
        return self

    @model_serializer(mode='wrap')
    def canonical_sources(self, handler):
        value = handler(self)
        value['source_snapshots'] = [pin(s) for s in self.source_snapshots]
        return value


class CanvasVideoQueue(ExecutionModel):
    command: CanvasVideoCommand
    reviewed_preview_digest: Digest


def compile_timeline(command):
    parameters = command.parameters
    return normalize_studio_timeline({'schema_version': 2, 'duration_ms': parameters.out_ms-parameters.in_ms,
        'width': 640, 'height': 360, 'fps': 25, 'tracks': [{'id': 'canvas-video-track', 'kind': 'VIDEO',
            'order': 0, 'muted': False, 'gain_db': 0, 'role': 'PRIMARY', 'clips': [{
                'id': 'canvas-video-clip', 'source_snapshot': pin(command.source_snapshots[0]),
                'start_ms': 0, 'in_ms': parameters.in_ms, 'out_ms': parameters.out_ms,
                'x': 0, 'y': 0, 'width': 640, 'height': 360, 'speed_num': 1, 'speed_den': 1,
                'muted': False, 'gain_db': 0, 'fade_in_ms': 0, 'fade_out_ms': 0,
                'opacity': 1, 'include_audio': parameters.include_audio is True}]}], 'captions': []})


def export_profile():
    # Original closed H264 profile: browser-decodable, within the existing Asset budget.
    return {'preset': 'DELIVERY_H264_MP4', 'video_bitrate_kbps': 400, 'audio_bitrate_kbps': 96, 'crf': 23}


def recipe(command):
    result = {'contract': 'studio-execution-recipe/1', 'operation_id': command.operation_id,
        'adapter': 'LOCAL_FFMPEG', 'output_profile': 'DELIVERY_H264_MP4', 'timeline': compile_timeline(command),
        'export_profile': export_profile(), 'automatic_fallback': False}
    result['recipe_digest'] = digest(result)
    return result


def validate_context(context):
    """Pure immutable receipt validation; stale targets remain readable."""
    command = CanvasVideoCommand.model_validate(context['canvas_video'])
    wire = command.model_dump()
    expected = {'actor', 'scope_key', 'incarnation', 'request_id', 'operation_id', 'sources',
        'timeline_snapshot', 'provider_binding', 'license_note', 'rights', 'execution_recipe',
        'export_profile', 'export_profile_digest', 'canvas_video', 'request_digest'}
    if (set(context) != expected or context['canvas_video'] != wire
            or context['incarnation'] != command.canvas_return.incarnation
            or context['request_id'] != command.request_id or context['operation_id'] != command.operation_id
            or context['sources'] != wire['source_snapshots'] or context['timeline_snapshot'] != wire['timeline_snapshot']
            or context['provider_binding'] is not None or context['license_note'] != '' or context['rights'] != {'license_note': ''}
            or context['execution_recipe'] != recipe(command) or context['export_profile'] != export_profile()
            or context['export_profile_digest'] != export_profile_digest(context['export_profile'])
            or context['request_digest'] != digest({k: v for k, v in context.items() if k != 'request_digest'})):
        raise ValueError('STUDIO_CANVAS_VIDEO_CONTEXT_CHANGED')
    return command


class CanvasVideoTaskExecution:
    def __init__(self, owner):
        self.owner = owner

    def current(self, nid, scope, actor, context, guard, *, document=None):
        command = validate_context(context)
        self.owner._canvas_return_target(nid, scope, actor, command.canvas_return, context, guard, document=document)
        row = (self.owner.timeline_get(nid, scope, actor, command.timeline_snapshot.id, guard) if document is None
            else self.owner._owned_timeline(nid, scope, actor, command.timeline_snapshot.id, context, document))
        if ((row['version'], row['timeline_digest']) != (command.timeline_snapshot.version, command.timeline_snapshot.digest)
                or row['timeline'] != compile_timeline(command)):
            raise StaleSourceError('STUDIO_CANVAS_VIDEO_TIMELINE_CHANGED')
        guard()
        return command

    def prepare(self, nid, scope, actor, value, guard):
        command = CanvasVideoCommand.model_validate(value)
        context = self.owner._base(nid, scope, actor, guard)
        wire = command.model_dump()
        context.update(request_id=command.request_id, operation_id=command.operation_id,
            sources=wire['source_snapshots'], timeline_snapshot=wire['timeline_snapshot'], provider_binding=None,
            license_note='', rights={'license_note': ''}, execution_recipe=recipe(command),
            export_profile=export_profile(), export_profile_digest=export_profile_digest(export_profile()),
            canvas_video=wire)
        context['request_digest'] = digest(context)
        self.current(nid, scope, actor, context, guard)
        validate_export_admission(context['execution_recipe']['timeline'], context['export_profile'], self.owner.workspace.assets.MAX_BYTES)
        # The existing source owner validates bytes and measures actual duration.
        observed = self.owner.source(nid, scope, wire['source_snapshots'][0], guard)
        duration = observed['measured'].get('duration_ms')
        if type(duration) not in (int, float) or command.parameters.out_ms > duration:
            raise ValueError('STUDIO_CANVAS_VIDEO_SOURCE_RANGE_INVALID')
        self.current(nid, scope, actor, context, guard)
        result = {'contract': 'studio-canvas-video-preview/1', 'novel_id': nid, 'branch_id': scope.get('branch_id'),
            'command': wire, 'request_digest': context['request_digest'], 'execution_recipe': deepcopy(context['execution_recipe']),
            'execution_available': bool(shutil.which('ffmpeg') and shutil.which('ffprobe')),
            'automatic_dispatch': False, 'product_acceptance': 'LOCAL_REQUIRED'}
        result['preview_digest'] = digest(result)
        return result, context

    def preview(self, nid, scope, actor, value, guard):
        return self.prepare(nid, scope, actor, value, guard)[0]

    def queue(self, nid, scope, actor, value, guard):
        body = CanvasVideoQueue.model_validate(value)
        preview, context = self.prepare(nid, scope, actor, body.command.model_dump(), guard)
        if preview['preview_digest'] != body.reviewed_preview_digest:
            raise StaleSourceError('STUDIO_CANVAS_VIDEO_PREVIEW_CHANGED')
        if not preview['execution_available']:
            raise ValueError('STUDIO_VIDEO_CPU_TOOLS_UNAVAILABLE')
        row = self.owner.video_owner.queue_studio(nid, scope.get('branch_id'), actor,
            context['execution_recipe']['timeline'], context=context, guard=guard, export_profile=context['export_profile'])
        self.current(nid, scope, actor, context, guard)
        return self.owner.view(row, 'timeline')

    def execute(self, nid, scope, actor, jid, action, guard):
        row, context = self.owner._row(nid, scope, actor, 'timeline', jid, guard)
        if 'canvas_video' not in context or context.get('graph_binding') is not None:
            raise ValueError('STUDIO_CANVAS_VIDEO_JOB_REQUIRED')
        self.current(nid, scope, actor, context, guard)
        def execution_guard():
            guard()
            self.current(nid, scope, actor, context, guard)
        # Scope/target checks use the original raw source lease at publication;
        # no raw-store lookup is introduced under the asset/project lease.
        publish, _ = self.owner._callbacks(nid, scope, actor, context, guard)
        rendered = self.owner.video_owner.execute_studio(nid, scope.get('branch_id'), actor, jid,
            action.expected_version, action.expected_request_digest, context=context, guard=execution_guard,
            source_guard=self.owner._source_guard(nid, scope, guard), publish=publish,
            inspect_source=self.owner._source_guard(nid, scope, guard))
        return self.owner.view(rendered, 'timeline')
