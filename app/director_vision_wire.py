"""Pure Ollama /api/chat vision codec, NOT a runtime/provider adapter.

No HTTP client, endpoint, credentials, installation or registration exists here.
Encoded image bytes are transient wire data and must never be persisted/logged.
Source: https://docs.ollama.com/capabilities/vision and /api/chat, checked
2026-10-18. Ollama does not version this REST contract; live compatibility and
image-understanding quality remain NOT_RUN.
"""
import base64
from hashlib import sha256
import json
from pydantic import Field

from .creative.director_binding import _Frozen, Identifier, Digest
from .creative.director_image_source import DirectorImageSource, decode_image

MAX_PROMPT_BYTES = 16000
MAX_RESPONSE_BYTES = 128000


class VisionWireParameters(_Frozen):
    max_output_tokens: int = Field(default=512, ge=1, le=2048)
    temperature: float = Field(default=0.0, ge=0, le=2, allow_inf_nan=False)


class VisionWireIdentity(_Frozen):
    model_id: Identifier
    source_digest: Digest
    prompt_digest: Digest


class OllamaDirectorVisionCodec:
    contract = 'DIRECTOR_OLLAMA_VISION_WIRE_V3'
    # Registration of this codec would still not supply an executable provider.
    execution_available = False

    @staticmethod
    def encode(*, model_id, source, content, prompt, parameters, guard):
        source = DirectorImageSource.model_validate(source)
        parameters = VisionWireParameters.model_validate(parameters)
        if (not isinstance(prompt, str) or not prompt.strip()
                or '\x00' in prompt or len(prompt.encode('utf-8')) > MAX_PROMPT_BYTES):
            raise ValueError('DIRECTOR_IMAGE_PROMPT_INVALID')
        identity = VisionWireIdentity(model_id=model_id, source_digest=source.asset.sha256,
            prompt_digest=sha256(prompt.encode()).hexdigest())
        width, height = decode_image(content, source.media_type, guard=guard)
        if (len(content) != source.byte_count or sha256(content).hexdigest() != source.asset.sha256
                or (width, height) != (source.width, source.height)):
            raise ValueError('DIRECTOR_IMAGE_WIRE_SOURCE_CHANGED')
        return {'model': identity.model_id, 'messages': [{'role': 'user', 'content': prompt,
            'images': [base64.b64encode(content).decode('ascii')]}], 'stream': False,
            'format': 'json', 'options': {'temperature': parameters.temperature,
                                        'num_predict': parameters.max_output_tokens}}

    @staticmethod
    def decode(data, *, model_id):
        """Decode bounded wire bytes only; never certify provenance or model calls."""
        if type(data) is not bytes or not 0 < len(data) <= MAX_RESPONSE_BYTES:
            raise ValueError('DIRECTOR_IMAGE_WIRE_RESPONSE_INVALID')
        def pairs(items):
            result = {}
            for key, value in items:
                if key in result:
                    raise ValueError('duplicate key')
                result[key] = value
            return result
        try:
            value = json.loads(data, object_pairs_hook=pairs,
                parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite')))
            message = value['message']
            text = message['content']
            if (value.get('model') != model_id or value.get('done') is not True
                    or value.get('done_reason') != 'stop' or value.get('error')
                    or message.get('role') != 'assistant' or 'tool_calls' in message
                    or 'images' in message or type(text) is not str or not text.strip()
                    or '\x00' in text or len(text.encode()) > MAX_RESPONSE_BYTES):
                raise ValueError('invalid completion')
        except (ValueError, UnicodeError, KeyError, TypeError, AttributeError, RecursionError):
            raise ValueError('DIRECTOR_IMAGE_WIRE_RESPONSE_INVALID') from None
        return text
