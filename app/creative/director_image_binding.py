"""Disjoint passive IMAGE V3 identities; never execution authority."""
from typing import Literal
from pydantic import Field, model_validator
from .director_binding import _Frozen, Identifier, Digest
from .director_image_source import DirectorImageSource

OPERATION = 'creative_director_image_v3'
ORIGIN = 'creative_director_image_model_v3'
FIELD = 'director_image_binding'

class ImageTarget(_Frozen):
    document_id: Identifier
    version: int = Field(ge=1)
    digest: Digest
    scene_id: Identifier

class ImageBinding(_Frozen):
    contract: Literal['CREATIVE_DIRECTOR_IMAGE_REQUEST_V3'] = 'CREATIVE_DIRECTOR_IMAGE_REQUEST_V3'
    source: DirectorImageSource
    target: ImageTarget
    route_digest: Digest
    preview_digest: Digest

    @property
    def project_id(self): return self.source.project_id


def is_image_job(value):
    get = value.get if isinstance(value, dict) else lambda key, default=None: getattr(value, key, default)
    return (get(FIELD) is not None or get('operation') == OPERATION or get('experimental_origin') == ORIGIN)


def job_binding(value):
    from uuid import UUID
    binding = ImageBinding.model_validate(value.get(FIELD))
    source = binding.source
    if (value.get('operation') != OPERATION or value.get('experimental_origin') != ORIGIN
            or value.get('novel_id') != source.project_id or value.get('actor_id') != source.actor_id
            or value.get('scope') != source.scope.model_dump() or value.get('profile') != 'LOCAL_ONLY'
            or value.get('chapter_id') is not None
            or any(value.get(k) is not None for k in ('creative_director_binding','graph_binding','adaptation_binding','research_ocr_binding'))
            or str(UUID(value['id'])) != value['id']):
        raise ValueError('DIRECTOR_IMAGE_JOB_IDENTITY_INVALID')
    import re
    if not re.fullmatch('[a-f0-9]{64}', value.get('expected_request_digest') or ''):
        raise ValueError('DIRECTOR_IMAGE_REQUEST_DIGEST_REQUIRED')
    return {'project_id': source.project_id, 'project_incarnation': source.project_incarnation,
            'actor_id': source.actor_id, 'scope': source.scope.model_dump()}
