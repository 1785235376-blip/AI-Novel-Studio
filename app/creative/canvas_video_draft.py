"""Recoverable input metadata on the existing versioned Timeline row; never an execution proof."""
from copy import deepcopy
from typing import Literal
from pydantic import Field, field_validator, model_validator, model_serializer
from .canvas_video_task import (CanvasVideoCommand, CanvasVideoReturnBinding, CanvasVideoTaskExecution,
    FailedCanvasVideoOrigin, VideoRange, compile_timeline, pin, digest)
from .production_execution_models import ExecutionModel, ProductionSourceSnapshot
from ..experimental.common import StaleSourceError


class CanvasVideoDraft(ExecutionModel):
    contract: Literal['studio-canvas-video-draft/1']
    request_id: str = Field(pattern=r'^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$')
    parameters: VideoRange
    source_snapshots: list[ProductionSourceSnapshot] = Field(min_length=1, max_length=1)
    canvas_return: CanvasVideoReturnBinding
    derived_from: FailedCanvasVideoOrigin

    @field_validator('source_snapshots', mode='before')
    @classmethod
    def exact_sources(cls, value):
        if isinstance(value, list) and any(isinstance(s, dict) and 'reference_only' in s for s in value):
            raise ValueError('STUDIO_CANVAS_VIDEO_SOURCE_INVALID')
        return value

    @model_validator(mode='after')
    def closed_input(self):
        self.command({'id': 'draft-validation', 'version': 1, 'digest': '0'*64})
        return self

    @model_serializer(mode='wrap')
    def canonical_input(self, handler):
        value = handler(self)
        value['source_snapshots'] = [pin(s) for s in self.source_snapshots]
        return value

    def command(self, snapshot):
        return CanvasVideoCommand.model_validate({'contract': 'studio-canvas-video-trim/1',
            'operation_id': 'm9.timeline.multitrack', 'request_id': self.request_id,
            'provider_id': None, 'model_id': None, 'prompt': '', 'allow_cloud': False, 'license_note': '',
            'parameters': self.parameters.model_dump(), 'source_snapshots': [pin(s) for s in self.source_snapshots],
            'canvas_return': self.canvas_return.model_dump(), 'derived_from': self.derived_from.model_dump(),
            'timeline_snapshot': snapshot})


def saved(row, history=None):
    if 'canvas_video_draft' not in row:
        if 'canvas_video_draft_digest' in row: raise ValueError('STUDIO_CANVAS_VIDEO_DRAFT_CORRUPT')
        return None
    command = CanvasVideoCommand.model_validate(row['canvas_video_draft'])
    wire = command.model_dump()
    versions = [row, *(r for r in (row.get('history', []) if history is None else history) if r.get('version') != row['version'])]
    snapshots = [r for r in versions if r.get('version') == command.timeline_snapshot.version]
    if (command.derived_from is None or wire != row['canvas_video_draft']
            or row.get('canvas_video_draft_digest') != digest(wire)
            or command.timeline_snapshot.id != row['id'] or len(snapshots) != 1
            or command.timeline_snapshot.digest != snapshots[0].get('timeline_digest')
            or compile_timeline(command) != snapshots[0].get('timeline')):
        raise ValueError('STUDIO_CANVAS_VIDEO_DRAFT_CORRUPT')
    return command


def recheck(owner, nid, scope, actor, command, guard, document=None):
    execution = CanvasVideoTaskExecution(owner)
    execution._derived_origin(nid, scope, actor, command, guard)
    context = owner._base(nid, scope, actor, guard)
    owner._canvas_return_target(nid, scope, actor, command.canvas_return, context, guard, document=document)
    guard()


def attach(owner, nid, scope, actor, row, value, guard, document):
    value = CanvasVideoDraft.model_validate(value)
    command = value.command({'id': row['id'], 'version': row['version'], 'digest': row['timeline_digest']})
    if compile_timeline(command) != row['timeline']:
        raise ValueError('STUDIO_CANVAS_VIDEO_DRAFT_TIMELINE_CHANGED')
    prior = saved(row)
    if prior is not None:
        fields = ('request_id', 'source_snapshots', 'canvas_return', 'derived_from')
        before, after = prior.model_dump(), command.model_dump()
        if any(before[k] != after[k] for k in fields):
            raise StaleSourceError('STUDIO_CANVAS_VIDEO_DRAFT_BINDING_CHANGED')
    recheck(owner, nid, scope, actor, command, guard, document)
    wire = command.model_dump()
    row.update(canvas_video_draft=deepcopy(wire), canvas_video_draft_digest=digest(wire))
    return command
