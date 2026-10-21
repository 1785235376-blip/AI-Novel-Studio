"""Two strict PNG layers over the original Image Job and Asset owners.

Straight-alpha source-over in encoded channel values; integer arithmetic with
half-up rounding only at the final RGBA8 output. No ICC/linear-light conversion.
All alpha-zero output RGB is zero, including when alpha rounded down to zero.
"""
from copy import deepcopy
import hashlib
import json
import struct

from .studio_image_cutout import _rgba_png, _unfilter, _sha256
from .studio_image_mask_authoring import _read_png, dimensions, SOURCE_MAX_BYTES

OPERATION = 'm5.image.composite'
CONTRACT = 'cpu-two-layer-composite/1'
ALGORITHM = 'ENCODED_RGBA8_STRAIGHT_SOURCE_OVER_HALF_UP_V1'
OUTPUT_PROFILE = 'PNG_RGBA8_STORED_DEFLATE_ZERO_ALPHA_RGB'
MAX_OUTPUT_BYTES = 4195716


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def layers(value):
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError('STUDIO_IMAGE_COMPOSITE_TWO_LAYERS_REQUIRED')
    result = []
    for item in value:
        if hasattr(item, 'model_dump'): item = item.model_dump()
        if (not isinstance(item, dict) or set(item) != {'source', 'visible', 'opacity'}
                or type(item['visible']) is not bool or type(item['opacity']) is not int or not 0 <= item['opacity'] <= 255):
            raise ValueError('STUDIO_IMAGE_COMPOSITE_LAYER_INVALID')
        source = item['source']
        if (not isinstance(source, dict) or set(source) != {'id', 'kind', 'asset_kind', 'version', 'digest'}
                or source['kind'] != 'ASSET' or source['asset_kind'] != 'image'
                or type(source['version']) is not int or source['version'] < 1):
            raise ValueError('STUDIO_IMAGE_COMPOSITE_SOURCE_INVALID')
        result.append(deepcopy(item))
    if result[0]['source']['id'] == result[1]['source']['id']:
        raise ValueError('STUDIO_IMAGE_COMPOSITE_SOURCE_DUPLICATE')
    return result


def recipe(value):
    result = {'contract': 'studio-execution-recipe/1', 'operation_id': OPERATION,
        'adapter': 'LOCAL_CPU_COMPOSITE', 'parameters': {}, 'layers': layers(value),
        'algorithm': ALGORITHM, 'output_profile': OUTPUT_PROFILE, 'automatic_fallback': False}
    return {**result, 'recipe_digest': digest(result)}


def validate_context(body, context):
    from ..creative.production_execution_models import MediaCommand
    command = context.get('command')
    if not isinstance(command, dict) or not isinstance(context.get('execution_recipe'), dict):
        raise ValueError('STUDIO_IMAGE_COMPOSITE_BINDING_REQUIRED')
    checked = MediaCommand.model_validate(command)
    expected = checked.model_dump(exclude={'source_snapshots', 'allow_cloud', 'license_note', 'request_id', 'canvas_return'})
    expected['parameters'] = checked.parameters.model_dump(exclude_none=True)
    if (expected != body or checked.operation_id != OPERATION
            or context['sources'] != [item['source'] for item in layers(body['image_layers'])]
            or context['execution_recipe'] != recipe(body['image_layers'])
            or context.get('provider_binding') is not None or 'graph_binding' in context
            or context['request_digest'] != digest({'context': {k: v for k, v in context.items() if k not in {'command', 'request_digest'}}, 'command': command})):
        raise ValueError('STUDIO_IMAGE_COMPOSITE_BINDING_CHANGED')


def validate_inputs(values, checkpoint=lambda: None):
    if not isinstance(values, (list, tuple)) or len(values) != 2:
        raise ValueError('STUDIO_IMAGE_COMPOSITE_TWO_LAYERS_REQUIRED')
    decoded, size = [], None
    for data in values:
        if not isinstance(data, bytes) or not 57 <= len(data) <= SOURCE_MAX_BYTES:
            raise ValueError('STUDIO_IMAGE_COMPOSITE_SOURCE_LIMIT')
        width, height = struct.unpack('>II', data[16:24]); dimensions(width, height)
        if size is not None and size != (width, height):
            raise ValueError('STUDIO_IMAGE_COMPOSITE_DIMENSIONS_MISMATCH')
        color, raw = _read_png(data, width, height, checkpoint)
        decoded.append((color, raw)); size = (width, height)
    return (*size, decoded)


def render(values, settings, checkpoint=lambda: None):
    settings = layers(settings)
    width, height, decoded = validate_inputs(values, checkpoint)
    if any(_sha256(data, checkpoint) != item['source']['digest'] for data, item in zip(values, settings)):
        raise ValueError('STUDIO_IMAGE_COMPOSITE_SOURCE_CHANGED')
    previous = [bytearray(width * {0: 1, 2: 3, 4: 2, 6: 4}[color]) for color, _ in decoded]
    output = bytearray(height * (width * 4 + 1)); denominator = 255 * 255
    opacity = [item['opacity'] if item['visible'] else 0 for item in settings]
    for y in range(height):
        checkpoint(); rows = []
        for index, (color, raw) in enumerate(decoded):
            channels = {0: 1, 2: 3, 4: 2, 6: 4}[color]; stride = width * channels + 1
            start = y * stride
            row = _unfilter(bytearray(raw[start + 1:start + stride]), previous[index], channels, raw[start])
            previous[index] = row
            rgba = []
            for x in range(width):
                p = x * channels
                rgba.append((row[p], row[p], row[p], row[p + 1] if color == 4 else 255) if color in {0, 4}
                    else (*row[p:p + 3], row[p + 3] if color == 6 else 255))
            rows.append(rgba)
        for x, (bottom, top) in enumerate(zip(*rows)):
            ab, at = bottom[3] * opacity[0], top[3] * opacity[1]
            alpha = at * denominator + ab * (denominator - at)
            a = (alpha * 255 + denominator * denominator // 2) // (denominator * denominator)
            target = y * (width * 4 + 1) + 1 + x * 4
            if a:
                output[target:target + 4] = bytes([ (top[c] * at * denominator + bottom[c] * ab * (denominator - at) + alpha // 2) // alpha for c in range(3)] + [a])
    data = _rgba_png(bytes(output), width, height, checkpoint)
    # Re-decode the produced artifact, including every invisible RGB byte.
    color, restored = _read_png(data, width, height, checkpoint)
    if color != 6 or restored != output:
        raise ValueError('STUDIO_IMAGE_COMPOSITE_OUTPUT_CHANGED')
    rgba = b''.join(output[y * (width * 4 + 1) + 1:(y + 1) * (width * 4 + 1)] for y in range(height))
    proof = {'contract': CONTRACT, 'algorithm': ALGORITHM, 'width': width, 'height': height,
        'source_sha256': [item['source']['digest'] for item in settings], 'layers_digest': digest(settings),
        'output_sha256': _sha256(data, checkpoint), 'rgba_sha256': _sha256(rgba, checkpoint), 'output_bytes': len(data)}
    checkpoint(); return data, proof


def validate_proof(row):
    proof = row.get('processing_proof')
    if proof is None:
        if row.get('publication_ready') or row.get('output_asset_id') or row.get('status') in {'AWAITING_REVIEW', 'REVIEWING', 'APPROVED'}:
            raise ValueError('STUDIO_IMAGE_COMPOSITE_PROOF_REQUIRED')
        return
    import re
    expected = {'contract', 'algorithm', 'width', 'height', 'source_sha256', 'layers_digest', 'output_sha256', 'rgba_sha256', 'output_bytes'}
    if (not isinstance(proof, dict) or set(proof) != expected or proof['contract'] != CONTRACT or proof['algorithm'] != ALGORITHM
            or proof['source_sha256'] != [s['digest'] for s in row['context']['sources']]
            or proof['layers_digest'] != digest(layers(row['body']['image_layers']))
            or any(not isinstance(proof[k], str) or not re.fullmatch('[a-f0-9]{64}', proof[k]) for k in ('layers_digest', 'output_sha256', 'rgba_sha256'))
            or type(proof['output_bytes']) is not int or not 57 <= proof['output_bytes'] <= MAX_OUTPUT_BYTES):
        raise ValueError('STUDIO_IMAGE_COMPOSITE_PROOF_INVALID')
    dimensions(proof['width'], proof['height'])
    ready = row.get('publication_ready')
    if ready and ready != {'kind': 'image', 'output_digest': proof['output_sha256'], 'output_bytes': proof['output_bytes'], 'media_type': 'image/png'}:
        raise ValueError('STUDIO_IMAGE_COMPOSITE_PROOF_INVALID')
    if row.get('output_digest') is not None and row['output_digest'] != proof['output_sha256']:
        raise ValueError('STUDIO_IMAGE_COMPOSITE_PROOF_INVALID')
