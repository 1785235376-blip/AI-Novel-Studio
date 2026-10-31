"""Passive provenance for explicitly reviewed sampled video reference images."""
from __future__ import annotations
import copy
from fractions import Fraction
import re

CONTRACT = 'studio-video-reference-asset/1'
PRIVATE = '_video_reference_origin'
FEATURES = {'narrative_production_v2', 'asset_lineage_v2'}
PROOF_KEYS = ('in_ms', 'out_ms', 'sample_count', 'selected_index', 'source_frame_index', 'pts',
              'time_base', 'time_ms', 'width', 'height', 'png_sha256', 'preview_digest')


def marker(value):
    def invalid(): raise ValueError('VIDEO_REFERENCE_ORIGIN_INVALID')
    if not isinstance(value, dict) or set(value) != {'contract', 'actor', 'scope_key', 'incarnation', 'source', *PROOF_KEYS} or value.get('contract') != CONTRACT:
        invalid()
    source = value['source']
    if not isinstance(source, dict) or set(source) != {'id', 'version', 'sha256'}: invalid()
    if (not isinstance(source['id'], str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,239}', source['id'])
            or type(source['version']) is not int or not 1 <= source['version'] <= 2**53 - 1
            or not isinstance(value['actor'], str) or not 1 <= len(value['actor']) <= 240
            or any(ord(c) < 32 or ord(c) == 127 for c in value['actor'])
            or not isinstance(value['incarnation'], str) or not re.fullmatch(r'(?:file|postgres):[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}', value['incarnation'])): invalid()
    for item in (source['sha256'], value['scope_key'], value['png_sha256'], value['preview_digest']):
        if not isinstance(item, str) or not re.fullmatch(r'[a-f0-9]{64}', item): invalid()
    for key in ('in_ms', 'out_ms', 'sample_count', 'selected_index', 'source_frame_index', 'pts', 'width', 'height'):
        if type(value[key]) is not int: invalid()
    if (not 0 <= value['in_ms'] < value['out_ms'] <= 60000 or value['out_ms'] - value['in_ms'] > 10000
            or not 1 <= value['sample_count'] <= 8 or not 0 <= value['selected_index'] < value['sample_count']
            or not 0 <= value['source_frame_index'] < 4096 or not 0 <= value['pts'] <= 2**53 - 1
            or not 1 <= value['width'] <= 320 or not 1 <= value['height'] <= 320): invalid()
    for key in ('time_base', 'time_ms'):
        row = value[key]
        if (not isinstance(row, dict) or set(row) != {'num', 'den'}
                or type(row['num']) is not int or type(row['den']) is not int
                or not 0 <= row['num'] <= 2**53 - 1 or not 1 <= row['den'] <= 2**53 - 1): invalid()
        if Fraction(row['num'], row['den']).numerator != row['num'] or Fraction(row['num'], row['den']).denominator != row['den']: invalid()
    base = Fraction(value['time_base']['num'], value['time_base']['den'])
    timestamp = Fraction(value['time_ms']['num'], value['time_ms']['den'])
    requested = value['in_ms'] + (value['out_ms'] - value['in_ms']) * value['selected_index'] // value['sample_count']
    if base <= 0 or timestamp != value['pts'] * base * 1000 or not requested <= timestamp < value['out_ms']: invalid()
    return copy.deepcopy(value)


def lineage(value, origin):
    source = origin['source']
    if (not isinstance(value, dict) or value.get('schema') != 'asset-lineage-v2'
            or value.get('origin') != 'MANUAL_EDIT' or value.get('sources') != {}
            or value.get('parents') != {source['id']: {'version': source['version'], 'digest': source['sha256']}}
            or value.get('output_digest') != origin['png_sha256']):
        raise ValueError('VIDEO_REFERENCE_SOURCE_IMMUTABLE')


def record(meta):
    origin = marker(meta.get(PRIVATE)); binding = meta.get('_project_binding'); features = meta.get('_required_features')
    if (not isinstance(binding, dict) or origin['scope_key'] != binding.get('scope_key') or origin['incarnation'] != binding.get('incarnation')
            or meta.get('_owner_actor_id') is not None or not isinstance(features, list)
            or any(not isinstance(f, str) for f in features) or not FEATURES.issubset(features)
            or meta.get('kind') != 'image' or meta.get('media_type') != 'image/png' or meta.get('sha256') != origin['png_sha256']
            or type(meta.get('version')) is not int or not 1 <= meta['version'] <= 2**53 - 1
            or meta.get('source_asset_ids') != [origin['source']['id']]
            or any(meta.get(k) is not None for k in ('source_job_id', 'provider_id', 'model_id', 'approved_at'))):
        raise ValueError('VIDEO_REFERENCE_ORIGIN_INVALID')
    lineage((meta.get('parameters') or {}).get('asset_lineage_v2'), origin)
    return origin


def source(assets, origin, nid, branch):
    from ..experimental.common import StaleSourceError
    row = assets.get(origin['source']['id'], branch_id=branch)
    if (row.get('novel_id') != nid or row.get('branch_id') != branch or row.get('kind') != 'video'
            or row.get('media_type') not in {'video/mp4', 'video/webm'} or row.get('_owner_actor_id') is not None
            or type(row.get('version')) is not int or row['version'] != origin['source']['version']
            or row.get('sha256') != origin['source']['sha256'] or not 0 < row.get('size', 0) <= 25 * 1024 * 1024):
        raise StaleSourceError('VIDEO_REFERENCE_SOURCE_CHANGED')
    assets._verified_content(row)
    return row


def project(origin):
    origin = marker(origin)
    return {'contract': CONTRACT, 'source_asset_id': origin['source']['id'],
            'source_version': origin['source']['version'], 'source_sha256': origin['source']['sha256'],
            **{key: copy.deepcopy(origin[key]) for key in PROOF_KEYS}, 'model_called': False, 'semantic_analysis': False}
