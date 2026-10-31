"""Passive, server-only provenance for original Comic page render copies.

This is an Asset origin, not a generation source or an approval receipt. The
current Comic owner must validate the pinned page before use.
"""
from __future__ import annotations

import copy
import io
from typing import Literal

from pydantic import Field, model_validator

from ..experimental.media import StrictModel

CONTRACT = 'studio-comic-page-asset/1'
FIELD = '_comic_page_origin'
FEATURES = frozenset({'narrative_production_v2', 'asset_lineage_v2', 'comic_layouts_v2', 'ai_director_v2'})
ID = r'^[A-Za-z0-9][A-Za-z0-9_-]{0,239}$'
DIGEST = r'^[a-f0-9]{64}$'
INCARNATION = r'^(?:file|postgres):[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$'


class ComicPagePin(StrictModel):
    id: str = Field(pattern=ID, strict=True)
    version: int = Field(ge=1, le=2**53 - 1, strict=True)
    review_digest: str = Field(pattern=DIGEST, strict=True)
    document_digest: str = Field(pattern=DIGEST, strict=True)


class ComicPageOrigin(StrictModel):
    contract: Literal['studio-comic-page-asset/1']
    actor: str = Field(min_length=1, max_length=240, strict=True)
    scope_key: str = Field(pattern=DIGEST, strict=True)
    incarnation: str = Field(pattern=INCARNATION, strict=True)
    receipt_id: str = Field(pattern=ID, strict=True)
    asset_id: str = Field(pattern=ID, strict=True)
    index: int = Field(ge=0, le=3, strict=True)
    request_digest: str = Field(pattern=DIGEST, strict=True)
    preview_digest: str = Field(pattern=DIGEST, strict=True)
    source: ComicPagePin
    width: int = Field(ge=64, le=1600, strict=True)
    height: int = Field(ge=64, le=12000, strict=True)
    png_sha256: str = Field(pattern=DIGEST, strict=True)
    render_fingerprint: str = Field(pattern=DIGEST, strict=True)

    @model_validator(mode='after')
    def bounded(self):
        if (self.width * self.height > 16_000_000
                or any(ord(c) < 32 or ord(c) == 127 or 0xD800 <= ord(c) <= 0xDFFF for c in self.actor)):
            raise ValueError('COMIC_PAGE_ORIGIN_INVALID')
        return self


def marker(value):
    try:
        return ComicPageOrigin.model_validate(value).model_dump()
    except (ValueError, TypeError):
        raise ValueError('COMIC_PAGE_ORIGIN_INVALID') from None


def validate_png(data, origin):
    """Decode bounded native output; MIME and a matching hash are insufficient."""
    from PIL import Image
    import hashlib
    origin = marker(origin)
    if not isinstance(data, bytes) or not 0 < len(data) <= 25 * 1024 * 1024:
        raise ValueError('COMIC_PAGE_PNG_INVALID')
    if hashlib.sha256(data).hexdigest() != origin['png_sha256']:
        raise ValueError('COMIC_PAGE_PNG_INVALID')
    try:
        with Image.open(io.BytesIO(data)) as image:
            if (image.format != 'PNG' or image.size != (origin['width'], origin['height'])
                    or image.mode != 'RGB' or getattr(image, 'n_frames', 1) != 1):
                raise ValueError('COMIC_PAGE_PNG_INVALID')
            image.load()
    except (OSError, Image.DecompressionBombError):
        raise ValueError('COMIC_PAGE_PNG_INVALID') from None


def record(meta):
    origin = marker(meta.get(FIELD))
    binding, features = meta.get('_project_binding'), meta.get('_required_features')
    if (not isinstance(binding, dict)
            or (binding.get('scope_key'), binding.get('incarnation')) != (origin['scope_key'], origin['incarnation'])
            or meta.get('id') != origin['asset_id'] or meta.get('_owner_actor_id') is not None
            or meta.get('kind') != 'image' or meta.get('media_type') != 'image/png'
            or meta.get('sha256') != origin['png_sha256']
            or type(meta.get('version')) is not int or not 1 <= meta['version'] <= 2**53 - 1
            or not isinstance(features, list) or any(not isinstance(f, str) for f in features)
            or not FEATURES.issubset(features) or meta.get('source_asset_ids') != []
            or any(meta.get(k) is not None for k in ('source_job_id', 'provider_id', 'model_id', 'approved_at'))
            or any(k in meta for k in ('_studio_result_origin', '_comic_ora_origin', '_manual_mask_origin',
                                      '_model_reference_origin', '_video_reference_origin', '_text_result_origin'))):
        raise ValueError('COMIC_PAGE_ORIGIN_INVALID')
    return origin


def project(origin):
    origin = marker(origin)
    return {'contract': CONTRACT, 'source': copy.deepcopy(origin['source']),
            'png_sha256': origin['png_sha256'], 'render_fingerprint': origin['render_fingerprint'],
            'classification': 'ORIGINAL_COMIC_RENDER_COPY', 'approval_inherited': False,
            'model_called': False}
