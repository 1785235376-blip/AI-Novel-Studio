"""Caption task adapter over GenerationRuntime's original admitted AUDIO node."""
from __future__ import annotations

import copy
from fractions import Fraction
import math

from .media import digest
from .subtitle_processing import ProcessingDefinition, ProcessingRequest, ProcessingResult
from .subtitle_timeline import Cue
from ..audio_processing_runtime import AudioProcessingModelNode, AudioProcessingRequest


class ModelRuntimeSubtitleAdapter:
    """Explicit original ASR route; no model install, launch or fallback.

    The node must already use the host's original durable registries. A changed
    provider/model/admission requires explicit host reinstallation of this route
    and the existing cancel/resume or a new caption task; it is never rebound.
    """
    def __init__(self, node, *, provider_id, model_id):
        if not isinstance(node, AudioProcessingModelNode):
            raise ValueError('PROCESSING_ORIGINAL_MODEL_NODE_REQUIRED')
        self.node, self.provider_id, self.model_id = node, provider_id, model_id
        self._binding = node.binding(provider_id, model_id, 'ASR')
        self.definition = ProcessingDefinition('model-runtime.asr.' + digest([provider_id, model_id])[:32],
            '1:' + self._binding['route_digest'], ('ASR',))

    @property
    def model_binding(self):
        return copy.deepcopy(self._binding)

    def model_runtime_admitted(self):
        try:
            return self.node.binding(self.provider_id, self.model_id, 'ASR') == self._binding
        except (ValueError, RuntimeError, FileNotFoundError):
            return False

    def process(self, request: ProcessingRequest) -> ProcessingResult:
        if not isinstance(request, ProcessingRequest) or request.operation != 'ASR' or request.transcript:
            raise ValueError('PROCESSING_ASR_REQUEST_REQUIRED')
        request.guard()
        duration = Fraction(**request.caption['media']['duration_seconds']) * 1000
        language = request.caption['language'].split('-', 1)[0].lower()
        response = self.node.execute(AudioProcessingRequest(self.provider_id, self.model_id, 'ASR',
            request.media, request.media_type, language, math.ceil(duration), request.source_digest,
            self._binding['route_digest'], request.request_id, dispatch_guard=request.guard))
        request.guard()
        base = request.caption['timebase']
        rate = Fraction(base['numerator'], base['denominator']) / 1000
        cues, previous_end = [], -1
        identity = digest([request.request_id, request.source_digest])[:32]
        for index, segment in enumerate(response.segments):
            if (not isinstance(segment, dict) or set(segment) != {'id', 'start_ms', 'end_ms', 'text'}
                    or type(segment.get('start_ms')) is not int or type(segment.get('end_ms')) is not int):
                raise ValueError('PROCESSING_MODEL_SEGMENT_INVALID')
            start, end = segment['start_ms'] * rate, segment['end_ms'] * rate
            start_tick, end_tick = start.numerator // start.denominator, math.ceil(end)
            cue = Cue(id='asr-' + identity + '-' + str(index + 1), start_tick=start_tick, end_tick=end_tick,
                text=segment['text'], overlap_reason='ASR_MODEL_SEGMENT_OVERLAP_REVIEW_REQUIRED' if start_tick < previous_end else '')
            cues.append(cue.model_dump()); previous_end = max(previous_end, end_tick)
        receipt = copy.deepcopy(response.receipt)
        receipt.update(cues_digest=digest(cues), timebase=copy.deepcopy(base), caption_version=request.caption['version'],
            media_snapshot=copy.deepcopy(request.caption['asset_snapshot']))
        return ProcessingResult(cues=tuple(cues), receipt=receipt)
