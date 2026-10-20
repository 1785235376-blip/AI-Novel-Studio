"""Passive provenance checks for original-Asset static GLB clay references."""
import copy
import math
import re

CONTRACT='studio-static-glb-clay-asset/1'
DIGEST=re.compile(r'^[a-f0-9]{64}$')


def marker(value):
    keys={'contract','actor','scope_key','incarnation','source','width','height','yaw','pitch','png_sha256','scene_index'}
    if not isinstance(value,dict) or set(value)!=keys or value.get('contract')!=CONTRACT:
        raise ValueError('MODEL_REFERENCE_ASSET_ORIGIN_INVALID')
    source=value['source']
    if (not isinstance(source,dict) or set(source)!={'id','version','sha256'}
            or not isinstance(source['id'],str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,239}',source['id'])
            or type(source['version']) is not int or not 1<=source['version']<=2**53-1
            or not isinstance(value['actor'],str) or not 1<=len(value['actor'])<=240
            or any(ord(c)<32 or ord(c)==127 for c in value['actor'])
            or not isinstance(value['incarnation'],str) or not re.fullmatch(r'(?:file|postgres):[a-f0-9-]{36}',value['incarnation'])
            or any(not isinstance(v,str) or not DIGEST.fullmatch(v) for v in (source['sha256'],value['scope_key'],value['png_sha256']))
            or type(value['width']) is not int or value['width']!=256 or type(value['height']) is not int or value['height']!=192
            or type(value['scene_index']) is not int or not 0<=value['scene_index']<=63
            or any(type(value[k]) not in (int,float) or not math.isfinite(value[k]) or abs(value[k])>bound for k,bound in [('yaw',180),('pitch',89)])):
        raise ValueError('MODEL_REFERENCE_ASSET_ORIGIN_INVALID')
    return copy.deepcopy(value)


def lineage(value,origin):
    source=origin['source']
    if (not isinstance(value,dict) or value.get('schema')!='asset-lineage-v2'
            or value.get('origin')!='MANUAL_EDIT' or value.get('sources')!={}
            or value.get('parents')!={source['id']:{'version':source['version'],'digest':source['sha256']}}
            or value.get('output_digest')!=origin['png_sha256']):
        raise ValueError('MODEL_REFERENCE_SOURCE_IMMUTABLE')


def record(meta):
    origin=marker(meta.get('_model_reference_origin'));binding=meta.get('_project_binding');features=meta.get('_required_features')
    if (not isinstance(binding,dict) or origin['scope_key']!=binding.get('scope_key') or origin['incarnation']!=binding.get('incarnation')
            or meta.get('_owner_actor_id') is not None or not isinstance(features,list)
            or any(not isinstance(f,str) for f in features) or not {'narrative_production_v2','asset_lineage_v2'}.issubset(features)
            or meta.get('kind')!='image' or meta.get('media_type')!='image/png' or meta.get('sha256')!=origin['png_sha256']
            or type(meta.get('version')) is not int or not 1<=meta['version']<=2**53-1
            or meta.get('source_asset_ids')!=[origin['source']['id']]
            or any(meta.get(k) is not None for k in ('source_job_id','provider_id','model_id','approved_at'))):
        raise ValueError('MODEL_REFERENCE_ASSET_ORIGIN_INVALID')
    lineage((meta.get('parameters') or {}).get('asset_lineage_v2'),origin)
    return origin


def source(assets,origin,nid,branch):
    from ..experimental.common import StaleSourceError
    row=assets.get(origin['source']['id'],branch_id=branch)
    if (row.get('novel_id')!=nid or row.get('branch_id')!=branch or row.get('kind')!='model'
            or row.get('media_type')!='model/gltf-binary' or type(row.get('version')) is not int or row.get('version')!=origin['source']['version']
            or row.get('sha256')!=origin['source']['sha256'] or not 0<row.get('size',0)<=8*1024*1024):
        raise StaleSourceError('MODEL_REFERENCE_SOURCE_CHANGED')
    assets._verified_content(row)
    return row


def pixels(data):
    # Reuse only the original bounded PNG byte parser/encoder, not mask meaning.
    from .studio_image_mask_authoring import _read_png, _png
    if not isinstance(data,bytes) or not 57<=len(data)<=65536:
        raise ValueError('MODEL_REFERENCE_ASSET_ORIGIN_INVALID')
    try:
        color,raw=_read_png(data,256,192,lambda:None)
        if color!=0 or any(raw[y*257]!=0 for y in range(192)) or _png(raw,256,192)!=data:
            raise ValueError('noncanonical diagnostic PNG')
    except ValueError:
        raise ValueError('MODEL_REFERENCE_ASSET_ORIGIN_INVALID') from None
