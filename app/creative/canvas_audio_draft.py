"""Recoverable audio input on original Timeline CAS rows; no saved execution grant."""
from copy import deepcopy
from typing import Literal
from pydantic import Field, field_validator, model_serializer, model_validator
from .production_execution_models import (ExecutionModel, MediaCommand, ProductionSourceSnapshot,
    CanvasReturnBinding, CanvasAudioTemplateParameters, CanvasAudioWorkflowTemplateRef, FailedCanvasAudioOrigin)
import hashlib
from ..experimental.store import canonical
from ..experimental.common import StaleSourceError
from ..services.studio_timeline_render import normalize_studio_timeline


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def pin(source):
    return source.model_dump(exclude={'reference_only'}, exclude_none=True)


class CanvasAudioDraft(ExecutionModel):
    contract: Literal['studio-canvas-audio-draft/1']
    request_id: str = Field(pattern=r'^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$')
    parameters: CanvasAudioTemplateParameters
    source_snapshots: list[ProductionSourceSnapshot] = Field(min_length=1, max_length=1)
    canvas_return: CanvasReturnBinding
    template_ref: CanvasAudioWorkflowTemplateRef | None = None
    derived_from: FailedCanvasAudioOrigin | None = None
    license_note: str = Field(default='', max_length=2000)

    @field_validator('source_snapshots', mode='before')
    @classmethod
    def exact_sources(cls, value):
        if isinstance(value, list) and any(isinstance(s, dict) and 'reference_only' in s for s in value):
            raise ValueError('STUDIO_CANVAS_AUDIO_DRAFT_INVALID')
        return value

    @model_validator(mode='after')
    def closed_input(self):
        self.command()
        return self

    @model_serializer(mode='wrap')
    def canonical_input(self, handler):
        value = handler(self)
        value['source_snapshots'] = [pin(s) for s in self.source_snapshots]
        for key in ('template_ref', 'derived_from'):
            if value.get(key) is None: value.pop(key, None)
        return value

    def command(self):
        return MediaCommand.model_validate({'operation_id': 'm8.audio.trim', 'request_id': self.request_id,
            'provider_id': None, 'model_id': None, 'prompt': '', 'allow_cloud': False,
            'license_note': self.license_note, 'parameters': self.parameters.model_dump(),
            'source_snapshots': [pin(s) for s in self.source_snapshots], 'canvas_return': self.canvas_return.model_dump(),
            **({'template_ref': self.template_ref.model_dump()} if self.template_ref is not None else {}),
            **({'derived_from': self.derived_from.model_dump()} if self.derived_from is not None else {})})


def compile_timeline(value):
    value = CanvasAudioDraft.model_validate(value)
    p = value.parameters
    return normalize_studio_timeline({'schema_version': 3, 'media_kind': 'AUDIO',
        'duration_ms': p.out_ms - p.in_ms, 'tracks': [{'id': 'canvas-audio-track', 'kind': 'AUDIO',
            'order': 0, 'role': 'DIALOGUE', 'muted': False, 'gain_db': 0, 'clips': [{
                'id': 'canvas-audio-clip', 'source_snapshot': pin(value.source_snapshots[0]),
                'start_ms': 0, 'in_ms': p.in_ms, 'out_ms': p.out_ms,
                'speed_num': 1, 'speed_den': 1, 'muted': False, 'gain_db': p.gain_db or 0,
                'fade_in_ms': p.fade_in_ms or 0, 'fade_out_ms': p.fade_out_ms or 0}]}]})


def saved(row, history=None):
    if 'canvas_audio_draft' not in row:
        if 'canvas_audio_draft_digest' in row: raise ValueError('STUDIO_CANVAS_AUDIO_DRAFT_CORRUPT')
        return None
    wire = row['canvas_audio_draft']
    if not isinstance(wire, dict): raise ValueError('STUDIO_CANVAS_AUDIO_DRAFT_CORRUPT')
    snapshot = wire.get('timeline_snapshot')
    value = CanvasAudioDraft.model_validate({k:v for k,v in wire.items() if k != 'timeline_snapshot'})
    versions = [row, *(r for r in (row.get('history', []) if history is None else history) if r.get('version') != row['version'])]
    entries = [r for r in versions if isinstance(snapshot, dict) and r.get('version') == snapshot.get('version')]
    if (not isinstance(snapshot, dict) or set(snapshot) != {'id','version','digest'}
            or snapshot.get('id') != row['id'] or type(snapshot.get('version')) is not int or len(entries) != 1
            or snapshot.get('digest') != entries[0].get('timeline_digest')
            or {**value.model_dump(), 'timeline_snapshot':snapshot} != wire
            or row.get('canvas_audio_draft_digest') != digest(wire)
            or compile_timeline(value) != entries[0].get('timeline') or 'canvas_video_draft' in row):
        raise ValueError('STUDIO_CANVAS_AUDIO_DRAFT_CORRUPT')
    return value


def recheck(owner, nid, scope, actor, value, guard, document=None):
    value = CanvasAudioDraft.model_validate(value)
    command = value.command()
    context = owner._base(nid, scope, actor, guard)
    for row in owner._audio(scope, actor).list(nid, context, guard):
        if row.get('context', {}).get('request_id') == value.request_id:
            raise StaleSourceError('STUDIO_CANVAS_AUDIO_DRAFT_ALREADY_ADMITTED')
    from .canvas_audio_task_provenance import validate_task_provenance
    if command.template_ref is not None or command.derived_from is not None:
        validate_task_provenance(owner, nid, scope, actor, command, context, guard, document=document)
    context.update(command=command.model_dump(), sources=[pin(s) for s in command.source_snapshots], operation_id=command.operation_id)
    if document is None:
        owner._sources_current(nid, scope, context, guard)
    else:
        if (not owner.timeline_inputs.in_phase(nid, scope, actor)
                or owner.store._local.active.get(owner.store.key(nid, scope)) is not document):
            raise ValueError('STUDIO_CANVAS_AUDIO_DRAFT_SOURCE_PHASE_CHANGED')
        owner._timeline_sources_current(nid, scope, compile_timeline(value), guard)
    owner._canvas_return_target(nid, scope, actor, command.canvas_return, context, guard, document=document)
    if owner._binding(command) is not None or owner._recipe(command).get('adapter') != 'LOCAL_FFMPEG':
        raise ValueError('STUDIO_CANVAS_AUDIO_DRAFT_ROUTE_CHANGED')
    owner._egress(nid, scope, command, None, guard)
    guard()


def attach(owner, nid, scope, actor, row, value, guard, document):
    value = CanvasAudioDraft.model_validate(value)
    if compile_timeline(value) != row['timeline'] or 'canvas_video_draft' in row:
        raise ValueError('STUDIO_CANVAS_AUDIO_DRAFT_TIMELINE_CHANGED')
    prior = saved(row)
    if prior is not None:
        before, after = prior.model_dump(), value.model_dump()
        if any(before.get(k) != after.get(k) for k in ('request_id','source_snapshots','canvas_return','template_ref','derived_from')):
            raise StaleSourceError('STUDIO_CANVAS_AUDIO_DRAFT_BINDING_CHANGED')
    recheck(owner, nid, scope, actor, value, guard, document)
    wire = {**value.model_dump(), 'timeline_snapshot':{'id':row['id'],'version':row['version'],'digest':row['timeline_digest']}}
    row.update(canvas_audio_draft=deepcopy(wire), canvas_audio_draft_digest=digest(wire))
    return value
