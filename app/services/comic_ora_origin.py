"""Server-owned private ORA staging marker; never archive-provided authority."""
import copy
import re
from uuid import UUID

FIELD = '_comic_ora_origin'
CONTRACT = 'comic-ora-private-stage/1'
FEATURES = frozenset({'comic_layouts_v2', 'narrative_production_v2'})


def marker(value):
    fields = {'contract', 'actor', 'scope_key', 'incarnation', 'receipt_id', 'asset_id',
              'archive_sha256', 'member_sha256', 'png_sha256', 'index', 'origin_status'}
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError('COMIC_ORA_ORIGIN_INVALID')
    if (value['contract'] != CONTRACT or value['origin_status'] != 'UNVERIFIED_EXTERNAL_RASTER'
            or not isinstance(value['actor'], str) or not 1 <= len(value['actor']) <= 240
            or any(ord(c) < 32 or ord(c) == 127 for c in value['actor'])
            or type(value['index']) is not int or not 0 <= value['index'] < 256
            or not isinstance(value['incarnation'], str)
            or not re.fullmatch(r'(?:file|postgres):[a-f0-9-]{36}', value['incarnation'])
            or any(not isinstance(value[k], str) or not re.fullmatch('[a-f0-9]{64}', value[k])
                   for k in ('scope_key', 'archive_sha256', 'member_sha256', 'png_sha256'))):
        raise ValueError('COMIC_ORA_ORIGIN_INVALID')
    try:
        for k in ('receipt_id', 'asset_id'):
            parsed = UUID(value[k])
            if parsed.version != 4 or str(parsed) != value[k]: raise ValueError()
    except (ValueError, TypeError, AttributeError):
        raise ValueError('COMIC_ORA_ORIGIN_INVALID') from None
    return copy.deepcopy(value)


def record(meta):
    origin = marker(meta.get(FIELD)); binding = meta.get('_project_binding')
    if (not isinstance(binding, dict) or origin['scope_key'] != binding.get('scope_key')
            or origin['incarnation'] != binding.get('incarnation')
            or meta.get('_owner_actor_id') != origin['actor'] or meta.get('id') != origin['asset_id']
            or meta.get('sha256') != origin['png_sha256'] or meta.get('kind') != 'image'
            or meta.get('media_type') != 'image/png'
            or not FEATURES.issubset(meta.get('_required_features', []))
            or any(meta.get(k) is not None for k in ('approved_at', 'source_job_id', 'provider_id', 'model_id', '_origin_provenance'))
            or meta.get('source_asset_ids') not in (None, [])):
        raise ValueError('COMIC_ORA_ORIGIN_INVALID')
    return origin
