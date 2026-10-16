"""Closed ComfyUI image recipes, projected from an explicit metadata observation.

No registry, arbitrary client workflow, installation or inference authority lives
here. Component advertisements are structural evidence, never model execution.
The fixed nodes follow the official ComfyUI Flux/Qwen tutorials and core nodes.
"""
from __future__ import annotations

import copy
import math
import re

RECIPES = (
    {'id': 'comfy-sd-checkpoint-v1', 'display_name': 'Stable Diffusion checkpoint (T2I)',
     'family': 'STABLE_DIFFUSION', 'capability': 'IMAGE', 'model_loader': 'CheckpointLoaderSimple',
     'model_input': 'ckpt_name', 'required_nodes': ['CheckpointLoaderSimple', 'KSampler', 'EmptyLatentImage', 'CLIPTextEncode', 'VAEDecode', 'SaveImage']},
    {'id': 'comfy-flux1-v1', 'display_name': 'FLUX.1 fixed image recipe', 'family': 'FLUX',
     'capability': 'IMAGE', 'model_loader': 'UNETLoader', 'model_input': 'unet_name',
     'required_nodes': ['UNETLoader', 'DualCLIPLoader', 'VAELoader', 'FluxGuidance', 'KSampler', 'EmptySD3LatentImage', 'CLIPTextEncode', 'VAEDecode', 'SaveImage']},
    {'id': 'comfy-qwen-image-v1', 'display_name': 'Qwen Image fixed image recipe', 'family': 'QWEN_IMAGE',
     'capability': 'IMAGE', 'model_loader': 'UNETLoader', 'model_input': 'unet_name',
     'required_nodes': ['UNETLoader', 'CLIPLoader', 'VAELoader', 'ModelSamplingAuraFlow', 'KSampler', 'EmptySD3LatentImage', 'CLIPTextEncode', 'VAEDecode', 'SaveImage']},
    {'id': 'comfy-upscale-model-v1', 'display_name': 'Compatible image upscale model', 'family': 'IMAGE_UPSCALE',
     'capability': 'IMAGE', 'model_loader': 'UpscaleModelLoader', 'model_input': 'model_name',
     'required_nodes': ['UpscaleModelLoader', 'ImageUpscaleWithModel', 'ImageScale', 'LoadImage', 'SaveImage']},
)
FILE_NAME = re.compile(r'^[^\x00-\x1f\x7f]{1,256}$')
UPLOAD_NAME = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.-]{0,239}$')


def _fields(info, node):
    definition = info.get(node)
    if not isinstance(definition, dict) or not isinstance(definition.get('input'), dict):
        raise ValueError('IMAGE_RECIPE_NODE_SCHEMA_INVALID')
    required = definition['input'].get('required', {})
    optional = definition['input'].get('optional', {})
    if not isinstance(required, dict) or not isinstance(optional, dict) or len(required) + len(optional) > 128:
        raise ValueError('IMAGE_RECIPE_NODE_SCHEMA_INVALID')
    return required, {**required, **optional}


def _options(info, node, field):
    schema = _fields(info, node)[1].get(field)
    if (not isinstance(schema, (list, tuple)) or not schema or not isinstance(schema[0], list)
            or len(schema[0]) > 512 or any(not isinstance(v, str) or not FILE_NAME.fullmatch(v) for v in schema[0])):
        raise ValueError('IMAGE_RECIPE_COMPONENT_SCHEMA_INVALID')
    return schema[0]


def _component(info, node, field, names):
    advertised = _options(info, node, field)
    matches = [name for name in advertised if name.replace('\\', '/').rsplit('/', 1)[-1] in names]
    # Ambiguous installations require a future explicit component binding.
    if len(matches) != 1:
        raise ValueError('IMAGE_RECIPE_COMPONENT_BINDING_REQUIRED')
    return matches[0]


def validate_workflow(info, graph):
    """Validate every emitted input, link type, fixed enum and scalar bound."""
    if not isinstance(info, dict) or len(info) > 4096 or not isinstance(graph, dict) or len(graph) > 40:
        raise ValueError('IMAGE_RECIPE_NODE_SCHEMA_INVALID')
    for node_id, node in graph.items():
        if set(node) != {'class_type', 'inputs'} or not isinstance(node['inputs'], dict):
            raise ValueError('IMAGE_RECIPE_NODE_SCHEMA_INVALID')
        required, fields = _fields(info, node['class_type'])
        if not set(required) <= set(node['inputs']) or set(node['inputs']) - set(fields):
            raise ValueError('IMAGE_RECIPE_NODE_INPUT_INVALID')
        definition = info[node['class_type']]
        outputs = definition.get('output')
        if not isinstance(outputs, (list, tuple)) or any(not isinstance(t, str) for t in outputs):
            raise ValueError('IMAGE_RECIPE_NODE_OUTPUT_INVALID')
        for field, value in node['inputs'].items():
            schema = fields[field]
            if not isinstance(schema, (list, tuple)) or not schema:
                raise ValueError('IMAGE_RECIPE_NODE_INPUT_INVALID')
            kind = schema[0]
            options = schema[1] if len(schema) > 1 and isinstance(schema[1], dict) else {}
            if isinstance(value, list):
                if (len(value) != 2 or value[0] not in graph or type(value[1]) is not int or value[1] < 0
                        or not isinstance(kind, str)):
                    raise ValueError('IMAGE_RECIPE_LINK_INVALID')
                source_outputs = info.get(graph[value[0]]['class_type'], {}).get('output', [])
                if value[1] >= len(source_outputs) or source_outputs[value[1]] != kind:
                    raise ValueError('IMAGE_RECIPE_LINK_INVALID')
            elif isinstance(kind, list):
                # LoadImage's dynamic choices change after our validated upload;
                # only its server-generated safe input filename can enter here.
                if node['class_type'] == 'LoadImage' and field == 'image':
                    if not isinstance(value, str) or not UPLOAD_NAME.fullmatch(value) or '..' in value:
                        raise ValueError('IMAGE_RECIPE_UPLOAD_NAME_INVALID')
                    if any(not isinstance(v, str) for v in kind):
                        raise ValueError('IMAGE_RECIPE_NODE_INPUT_INVALID')
                elif value not in kind:
                    raise ValueError('IMAGE_RECIPE_OPTION_UNSUPPORTED')
            elif kind == 'STRING':
                if not isinstance(value, str): raise ValueError('IMAGE_RECIPE_NODE_INPUT_INVALID')
            elif kind == 'BOOLEAN':
                if type(value) is not bool: raise ValueError('IMAGE_RECIPE_NODE_INPUT_INVALID')
            elif kind in {'INT', 'FLOAT'}:
                if (type(value) not in ({int} if kind == 'INT' else {int, float}) or not math.isfinite(value)
                        or value < options.get('min', -math.inf) or value > options.get('max', math.inf)):
                    raise ValueError('IMAGE_RECIPE_NODE_INPUT_INVALID')
            else:
                raise ValueError('IMAGE_RECIPE_NODE_INPUT_INVALID')
    return graph


def build_workflow(recipe, prompt, parameters, *, operation='t2i', uploads=(), weights=(), mask=None, source_dimensions=None):
    """Build one fixed graph; weights alter actual normalized pixel blending."""
    if operation not in recipe['operations']:
        raise ValueError('IMAGE_RECIPE_OPERATION_NOT_CONFIGURED')
    if operation == 'upscale':
        return build_upscale_workflow(recipe, prompt, parameters, uploads=uploads,
            weights=weights, mask=mask, source_dimensions=source_dimensions)
    p = dict(parameters)
    if set(p) - {'width', 'height', 'steps', 'seed', 'negative_prompt', 'denoising_strength'}:
        raise ValueError('IMAGE_PARAMETER_UNSUPPORTED')
    if operation != 't2i' and {'width', 'height'} & set(p):
        raise ValueError('IMAGE_PARAMETER_UNSUPPORTED')
    if 'denoising_strength' in p and (operation == 't2i' or type(p['denoising_strength']) not in {int, float}
            or not math.isfinite(p['denoising_strength']) or not 0 < p['denoising_strength'] <= 1):
        raise ValueError('IMAGE_PARAMETER_UNSUPPORTED')
    rid, c = recipe['recipe_id'], recipe['components']
    if rid == 'comfy-flux1-v1' and 'negative_prompt' in p:
        # CFG 1 ignores unconditional conditioning in this fixed Flux recipe.
        raise ValueError('IMAGE_PARAMETER_UNSUPPORTED')
    graph = {}
    if rid == 'comfy-sd-checkpoint-v1':
        graph['4'] = {'class_type': 'CheckpointLoaderSimple', 'inputs': {'ckpt_name': c['model']}}
        model, clip, vae = ['4', 0], ['4', 1], ['4', 2]
        latent_class, cfg, default_steps = 'EmptyLatentImage', 7, 28
    else:
        graph['4'] = {'class_type': 'UNETLoader', 'inputs': {'unet_name': c['model'], 'weight_dtype': 'default'}}
        graph['12'] = {'class_type': 'VAELoader', 'inputs': {'vae_name': c['vae']}}
        model, clip, vae = ['4', 0], ['11', 0], ['12', 0]
        latent_class = 'EmptySD3LatentImage'
        if rid == 'comfy-flux1-v1':
            graph['11'] = {'class_type': 'DualCLIPLoader', 'inputs': {'clip_name1': c['clip_l'], 'clip_name2': c['t5xxl'], 'type': 'flux'}}
            cfg, default_steps = 1, 4 if 'schnell' in c['model'].lower() else 28
        elif rid == 'comfy-qwen-image-v1':
            graph['11'] = {'class_type': 'CLIPLoader', 'inputs': {'clip_name': c['clip'], 'type': 'qwen_image'}}
            graph['13'] = {'class_type': 'ModelSamplingAuraFlow', 'inputs': {'model': model, 'shift': 3.1}}
            model, cfg, default_steps = ['13', 0], 4, 20
        else:
            raise ValueError('IMAGE_RECIPE_UNKNOWN')
    graph['6'] = {'class_type': 'CLIPTextEncode', 'inputs': {'text': prompt, 'clip': clip}}
    graph['7'] = {'class_type': 'CLIPTextEncode', 'inputs': {'text': p.get('negative_prompt', '' if rid != 'comfy-sd-checkpoint-v1' else 'low quality, blurry, artifacts'), 'clip': clip}}
    positive = ['6', 0]
    if rid == 'comfy-flux1-v1':
        graph['14'] = {'class_type': 'FluxGuidance', 'inputs': {'conditioning': positive, 'guidance': 3.5}}
        positive = ['14', 0]
    graph['5'] = {'class_type': latent_class, 'inputs': {'width': p.get('width', 1024), 'height': p.get('height', 1024), 'batch_size': 1}}
    if operation != 't2i':
        if (not 1 <= len(uploads) <= recipe['reference_limit'] or len(uploads) != len(weights)
                or any(type(w) not in {int, float} or not math.isfinite(w) or not 0 < w <= 1 for w in weights)):
            raise ValueError('IMAGE_RECIPE_REFERENCES_INVALID')
        if operation == 'inpaint' and (len(uploads) != 1 or not mask):
            raise ValueError('IMAGE_RECIPE_INPAINT_INPUT_INVALID')
        total, blended = weights[0], ['20', 0]
        for index, name in enumerate(uploads):
            graph[str(20 + index)] = {'class_type': 'LoadImage', 'inputs': {'image': name}}
            if index:
                blend_id = str(30 + index)
                graph[blend_id] = {'class_type': 'ImageBlend', 'inputs': {'image1': blended,
                    'image2': [str(20 + index), 0], 'blend_factor': weights[index] / (total + weights[index]), 'blend_mode': 'normal'}}
                total += weights[index]; blended = [blend_id, 0]
        graph['5'] = {'class_type': 'VAEEncode', 'inputs': {'pixels': blended, 'vae': vae}}
        if operation == 'inpaint':
            graph['25'] = {'class_type': 'LoadImage', 'inputs': {'image': mask}}
            graph['26'] = {'class_type': 'ImageToMask', 'inputs': {'image': ['25', 0], 'channel': 'red'}}
            graph['27'] = {'class_type': 'InvertMask', 'inputs': {'mask': ['26', 0]}}
            graph['5'] = {'class_type': 'VAEEncodeForInpaint', 'inputs': {'pixels': blended, 'vae': vae, 'mask': ['27', 0], 'grow_mask_by': 0}}
    elif uploads or weights or mask:
        raise ValueError('IMAGE_RECIPE_T2I_INPUT_INVALID')
    graph['3'] = {'class_type': 'KSampler', 'inputs': {'seed': p.get('seed', 0), 'steps': p.get('steps', default_steps),
        'cfg': cfg, 'sampler_name': 'euler', 'scheduler': 'normal', 'denoise': 1 if operation == 't2i' else p.get('denoising_strength', 0.6),
        'model': model, 'positive': positive, 'negative': ['7', 0], 'latent_image': ['5', 0]}}
    graph['8'] = {'class_type': 'VAEDecode', 'inputs': {'samples': ['3', 0], 'vae': vae}}
    output = ['8', 0]
    if operation == 'inpaint':
        graph['28'] = {'class_type': 'ImageCompositeMasked', 'inputs': {'destination': ['20', 0], 'source': output,
            'x': 0, 'y': 0, 'resize_source': False, 'mask': ['27', 0]}}
        output = ['28', 0]
    graph['9'] = {'class_type': 'SaveImage', 'inputs': {'filename_prefix': 'AI-Novel-Studio', 'images': output}}
    return graph


def project_comfy_image_recipe(info, model_name, family):
    """Return only positively validated operations and exact component names."""
    try:
        if family == 'IMAGE_UPSCALE':
            return project_comfy_upscale_recipe(info, model_name)
        template = next(r for r in RECIPES if r['family'] == family)
        if model_name not in _options(info, template['model_loader'], template['model_input']): return None
        c = {'model': model_name}
        if family == 'FLUX':
            if not re.fullmatch(r'flux1-(?:dev|schnell)(?:[-_.][A-Za-z0-9_.-]+)?\.safetensors', model_name.replace('\\', '/').rsplit('/', 1)[-1], re.I): return None
            c.update(clip_l=_component(info, 'DualCLIPLoader', 'clip_name1', {'clip_l.safetensors'}),
                     t5xxl=_component(info, 'DualCLIPLoader', 'clip_name2', {'t5xxl_fp16.safetensors', 't5xxl_fp8_e4m3fn.safetensors'}),
                     vae=_component(info, 'VAELoader', 'vae_name', {'ae.safetensors'}))
        elif family == 'QWEN_IMAGE':
            if model_name.replace('\\', '/').rsplit('/', 1)[-1] not in {'qwen_image_fp8_e4m3fn.safetensors', 'qwen_image_bf16.safetensors'}: return None
            c.update(clip=_component(info, 'CLIPLoader', 'clip_name', {'qwen_2.5_vl_7b_fp8_scaled.safetensors', 'qwen_2.5_vl_7b_bf16.safetensors'}),
                     vae=_component(info, 'VAELoader', 'vae_name', {'qwen_image_vae.safetensors'}))
        recipe = {'recipe_id': template['id'], 'components': c, 'operations': ['t2i'], 'reference_limit': 1,
            'reference_semantics': 'SINGLE_IMAGE_INITIALIZATION', 'mask_semantics': None,
            'structural_only': True, 'inference_verified': False}
        validate_workflow(info, build_workflow(recipe, 'structure validation', {}))
        for operation in ('i2i', 'reference', 'inpaint'):
            probe = {**recipe, 'operations': [*recipe['operations'], operation], 'reference_limit': 5}
            try:
                validate_workflow(info, build_workflow(probe, 'structure validation', {}, operation=operation,
                    uploads=('source.png', 'reference.png') if operation == 'reference' else ('source.png',),
                    weights=(1, 0.5) if operation == 'reference' else (1,), mask='mask.png' if operation == 'inpaint' else None))
            except (ValueError, TypeError, KeyError, IndexError):
                continue
            recipe['operations'].append(operation)
        if 'reference' in recipe['operations']:
            recipe.update(reference_limit=5, reference_semantics='WEIGHTED_PIXEL_INITIALIZATION')
        if 'inpaint' in recipe['operations']: recipe['mask_semantics'] = 'WHITE_KEEP_BLACK_REPAINT'
        return copy.deepcopy(recipe)
    except (ValueError, TypeError, KeyError, StopIteration, IndexError, AttributeError):
        return None


def public_capabilities(recipe):
    result = {key: copy.deepcopy(recipe[key]) for key in ('recipe_id', 'reference_limit', 'reference_semantics',
        'mask_semantics', 'structural_only', 'inference_verified')}
    if recipe['recipe_id'] == 'comfy-upscale-model-v1':
        result['upscaling'] = {'scales': [2, 4], 'output_format': 'PNG',
            'output_size_limit': 4096, 'output_pixel_limit': 16777216}
    return result


def upscale_dimensions(source_dimensions, scale):
    if (type(scale) is not int or scale not in (2, 4) or not isinstance(source_dimensions, dict)
            or set(source_dimensions) != {'width', 'height'}
            or any(type(source_dimensions[k]) is not int or not 1 <= source_dimensions[k] <= 2048
                   for k in ('width', 'height'))):
        raise ValueError('STUDIO_IMAGE_UPSCALE_DIMENSIONS_INVALID')
    target = {key: source_dimensions[key] * scale for key in ('width', 'height')}
    if max(target.values()) > 4096 or target['width'] * target['height'] > 16777216:
        raise ValueError('STUDIO_IMAGE_UPSCALE_OUTPUT_LIMIT')
    return target


def build_upscale_workflow(recipe, prompt, parameters, *, uploads, weights, mask, source_dimensions):
    if (recipe['recipe_id'] != 'comfy-upscale-model-v1' or prompt != '' or set(parameters) != {'scale'}
            or len(uploads) != 1 or len(weights) != 1 or type(weights[0]) not in {int, float}
            or weights[0] != 1 or mask is not None):
        raise ValueError('STUDIO_IMAGE_UPSCALE_INPUT_INVALID')
    target = upscale_dimensions(source_dimensions, parameters['scale'])
    # The model's intrinsic scale may differ from the delivery scale. A fixed
    # Lanczos resize makes the reviewed target exact; it never selects a model.
    return {
        '20': {'class_type': 'LoadImage', 'inputs': {'image': uploads[0]}},
        '4': {'class_type': 'UpscaleModelLoader', 'inputs': {'model_name': recipe['components']['model']}},
        '8': {'class_type': 'ImageUpscaleWithModel', 'inputs': {'upscale_model': ['4', 0], 'image': ['20', 0]}},
        '28': {'class_type': 'ImageScale', 'inputs': {'image': ['8', 0], 'upscale_method': 'lanczos',
            'width': target['width'], 'height': target['height'], 'crop': 'disabled'}},
        '9': {'class_type': 'SaveImage', 'inputs': {'filename_prefix': 'AI-Novel-Studio', 'images': ['28', 0]}},
    }


def project_comfy_upscale_recipe(info, model_name):
    """Exact advertised loader + typed fixed nodes, including RealESRGAN/SwinIR.

    Architecture support belongs to the installed Comfy loader. Filename family
    labels never grant compatibility, infer native scale or download anything.
    """
    try:
        if model_name not in _options(info, 'UpscaleModelLoader', 'model_name'):
            return None
        recipe = {'recipe_id': 'comfy-upscale-model-v1', 'components': {'model': model_name},
            'operations': ['upscale'], 'reference_limit': 1, 'reference_semantics': 'SINGLE_IMAGE_INITIALIZATION',
            'mask_semantics': None, 'structural_only': True, 'inference_verified': False}
        for scale in (2, 4):
            validate_workflow(info, build_workflow(recipe, '', {'scale': scale}, operation='upscale',
                uploads=('source.png',), weights=(1,), source_dimensions={'width': 64, 'height': 64}))
        return copy.deepcopy(recipe)
    except (ValueError, TypeError, KeyError, IndexError, AttributeError):
        return None


def project_automatic1111_image_recipe(info, model_name):
    """Require an explicit OpenAPI observation of the fixed img2img body."""
    try:
        schema = info['paths']['/sdapi/v1/img2img']['post']['requestBody']['content']['application/json']['schema']
        if set(schema) == {'$ref'}:
            path = schema['$ref'].split('/')
            if len(path) != 4 or path[:3] != ['#', 'components', 'schemas']: return None
            schema = info['components']['schemas'][path[3]]
        properties = schema['properties']
        expected = {'init_images': 'array', 'mask': 'string', 'denoising_strength': 'number',
            'inpainting_mask_invert': 'integer', 'inpaint_full_res': 'boolean', 'inpaint_full_res_padding': 'integer',
            'inpainting_fill': 'integer', 'mask_blur': 'integer', 'resize_mode': 'integer', 'width': 'integer', 'height': 'integer',
            'steps': 'integer', 'seed': 'integer', 'prompt': 'string', 'negative_prompt': 'string', 'override_settings': 'object'}
        if any(not isinstance(properties.get(k), dict) or properties[k].get('type') != t for k, t in expected.items()): return None
        if properties['init_images'].get('items', {}).get('type') != 'string': return None
        return {'recipe_id': 'automatic1111-img2img-v1', 'components': {'model': model_name},
            'operations': ['t2i', 'i2i', 'inpaint'], 'reference_limit': 1,
            'reference_semantics': 'SINGLE_IMAGE_INITIALIZATION', 'mask_semantics': 'WHITE_KEEP_BLACK_REPAINT',
            'structural_only': True, 'inference_verified': False}
    except (KeyError, TypeError, AttributeError):
        return None
