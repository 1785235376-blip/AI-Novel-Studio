"""Opt-in lossless WebP delivery over the existing bounded CPU mask renderer.

Only its internally rendered PNG reaches Pillow. No new source decoder, job,
provider, subprocess or publication owner is introduced.
"""
from __future__ import annotations

import hashlib
import io
import json
import re
import struct

PARAMETER = 'cutout_output'
PROFILE = 'WEBP_LOSSLESS_V1'
OUTPUT_PROFILE = 'WEBP_RGBA8_LOSSLESS_EXACT_V1'
CONTRACT = 'cpu-binary-mask-cutout-webp/1'
MAX_BYTES = 8 * 1024 * 1024


def parameters_valid(parameters):
    return parameters == {PARAMETER: PROFILE}


def _digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')).hexdigest()


def validate_context(body, context):
    if not parameters_valid(body['parameters']):
        raise ValueError('STUDIO_IMAGE_CUTOUT_WEBP_BINDING_CHANGED')
    recipe, command = context.get('execution_recipe'), context.get('command')
    fields = {'contract', 'operation_id', 'adapter', 'parameters', 'automatic_fallback', 'output_profile', 'mask_policy', 'recipe_digest'}
    if not isinstance(recipe, dict) or not isinstance(command, dict):
        raise ValueError('STUDIO_IMAGE_CUTOUT_WEBP_BINDING_REQUIRED')
    from ..creative.production_execution_models import MediaCommand
    MediaCommand.model_validate(command)
    if (set(recipe) != fields or recipe['contract'] != 'studio-execution-recipe/1'
            or recipe['operation_id'] != 'm5.image.cutout' or recipe['adapter'] != 'LOCAL_CPU_MASK'
            or recipe['parameters'] != body['parameters'] or recipe['automatic_fallback'] is not False
            or recipe['output_profile'] != OUTPUT_PROFILE or recipe['mask_policy'] != 'WHITE_KEEP_BLACK_TRANSPARENT_ZERO'
            or recipe['recipe_digest'] != _digest({key: value for key, value in recipe.items() if key != 'recipe_digest'})
            or command.get('parameters') != body['parameters']
            or context['request_digest'] != _digest({'context': {key: value for key, value in context.items() if key not in {'command', 'request_digest'}}, 'command': command})):
        raise ValueError('STUDIO_IMAGE_CUTOUT_WEBP_BINDING_CHANGED')


def encode(png, proof, checkpoint):
    from PIL import Image, features
    if not features.check('webp'):
        raise ValueError('IMAGE_CUTOUT_WEBP_UNAVAILABLE')
    checkpoint()
    if hashlib.sha256(png).hexdigest() != proof['output_sha256']:
        raise ValueError('IMAGE_CUTOUT_WEBP_PIXELS_CHANGED')
    class BoundedOutput(io.BytesIO):
        def write(self, data):
            checkpoint()
            if self.tell() + len(data) > MAX_BYTES: raise ValueError('IMAGE_CUTOUT_WEBP_OUTPUT_LIMIT')
            return super().write(data)
    with Image.open(io.BytesIO(png)) as source:
        if source.format != 'PNG' or source.size != (proof['width'], proof['height']):
            raise ValueError('IMAGE_CUTOUT_WEBP_PIXELS_CHANGED')
        with source.convert('RGBA') as image, BoundedOutput() as output:
            rgba = image.tobytes(); checkpoint()
            image.save(output, format='WEBP', lossless=True, quality=100, method=4, exact=True)
            data = output.getvalue()
    checkpoint()
    if (not 25 <= len(data) <= MAX_BYTES or data[:4] != b'RIFF' or data[8:16] != b'WEBPVP8L'
            or struct.unpack_from('<I', data, 4)[0] + 8 != len(data)
            or 20 + struct.unpack_from('<I', data, 16)[0] + (struct.unpack_from('<I', data, 16)[0] & 1) != len(data)):
        raise ValueError('IMAGE_CUTOUT_WEBP_PROFILE_INVALID')
    with Image.open(io.BytesIO(data)) as decoded:
        if decoded.format != 'WEBP' or decoded.size != (proof['width'], proof['height']) or getattr(decoded, 'n_frames', 1) != 1:
            raise ValueError('IMAGE_CUTOUT_WEBP_PROFILE_INVALID')
        with decoded.convert('RGBA') as restored:
            if restored.tobytes() != rgba:
                raise ValueError('IMAGE_CUTOUT_WEBP_PIXELS_CHANGED')
    checkpoint()
    return data, {**proof, 'contract': CONTRACT, 'output_sha256': hashlib.sha256(data).hexdigest(),
        'output_bytes': len(data), 'rgba_sha256': hashlib.sha256(rgba).hexdigest()}


def validate_proof(row):
    from .studio_image_mask_authoring import dimensions
    proof = row['processing_proof']
    fields = {'contract', 'width', 'height', 'source_sha256', 'mask_sha256', 'output_sha256', 'output_bytes', 'keep_pixels', 'remove_pixels', 'rgba_sha256'}
    if not isinstance(proof, dict) or set(proof) != fields or proof['contract'] != CONTRACT:
        raise ValueError('STUDIO_IMAGE_CUTOUT_WEBP_PROOF_INVALID')
    dimensions(proof['width'], proof['height'])
    for key in ('source_sha256', 'mask_sha256', 'output_sha256', 'rgba_sha256'):
        if not isinstance(proof[key], str) or not re.fullmatch('[a-f0-9]{64}', proof[key]):
            raise ValueError('STUDIO_IMAGE_CUTOUT_WEBP_PROOF_INVALID')
    if (any(type(proof[key]) is not int or proof[key] <= 0 for key in ('keep_pixels', 'remove_pixels', 'output_bytes'))
            or proof['keep_pixels'] + proof['remove_pixels'] != proof['width'] * proof['height']
            or not 25 <= proof['output_bytes'] <= MAX_BYTES
            or [proof['source_sha256'], proof['mask_sha256']] != [source['digest'] for source in row['context']['sources']]
            or row.get('publication_ready') != {'kind': 'image', 'output_digest': proof['output_sha256'], 'output_bytes': proof['output_bytes'], 'media_type': 'image/webp'}
            or row.get('output_digest') not in {None, proof['output_sha256']}):
        raise ValueError('STUDIO_IMAGE_CUTOUT_WEBP_PROOF_INVALID')
