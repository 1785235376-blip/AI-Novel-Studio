"""Visual identity projections over the original approved visual-memory owner.

Appearance records/assets stay authoritative. Comparison jobs contain only
versioned lineage and reviewed similarity results, never competing profiles.
"""
from __future__ import annotations

from typing import Literal, Protocol
from pydantic import Field, model_validator

from .media import StrictModel
from .embeddings import EmbeddingCapability, EmbeddingInput, EmbeddingService
from .common import StaleSourceError
from .planning import digest
from .review_adapter_jobs import ReviewAdapterJobs
from .vector_index import ExactCosineVectorIndex


class VisualEmbeddingProvider(Protocol):
    capability: EmbeddingCapability

    def embed(self, inputs: list[EmbeddingInput]) -> list[list[float]]: ...


class AppearanceReferenceIn(StrictModel):
    reference_id: str = Field(min_length=1, max_length=240)
    appearance_version: int = Field(ge=1)


class VisualIdentityCheckIn(StrictModel):
    character_id: str = Field(min_length=1, max_length=240)
    references: list[AppearanceReferenceIn] = Field(min_length=1, max_length=12)
    candidate_asset_id: str = Field(min_length=1, max_length=240)
    candidate_asset_version: int = Field(ge=1)
    target_media: Literal['IMAGE', 'VIDEO']
    drift_threshold: float = Field(default=0.75, ge=-1, le=1)

    @model_validator(mode='after')
    def distinct(self):
        ids = [item.reference_id for item in self.references]
        if len(ids) != len(set(ids)): raise ValueError('VISUAL_REFERENCE_DUPLICATE')
        return self


def profiles(service, nid, scope, actor):
    service.novels.get(nid)
    if service.visual_memory is None: raise ValueError('VISUAL_MEMORY_AUTHORITY_NOT_CONFIGURED')
    result = service.visual_memory.search_visual_memory(nid, entity_type='CHARACTER', limit=100,
                                                        branch_id=scope.get('branch_id'))
    rows = []
    for row in result['items']:
        # The legacy API's local list intentionally spans branches. The identity
        # engine is stricter: local queries only return local approved profiles.
        if row.get('branch_id') != scope.get('branch_id'): continue
        asset = service.assets.get(row['asset_id'], branch_id=scope.get('branch_id'), actor_id=actor)
        if asset.get('novel_id') != nid or asset.get('branch_id') != scope.get('branch_id'): continue
        appearance = row['searchable'].get('appearance') or {}
        rows.append({'id': row['id'], 'character_id': row['entity_id'], 'appearance_version': row['version'],
                     'appearance': appearance, 'clothing': row['searchable'].get('clothing') or {},
                     'hair': appearance.get('hair', {}), 'body': appearance.get('body', {}),
                     'accessories': appearance.get('accessories', []), 'approved_reference_asset': row['asset_id'],
                     'source_lineage': row['provenance'], 'novel_id': nid, 'scope': scope,
                     'navigation': {'owner': 'VISUAL_MEMORY', 'id': row['id']}})
    provider = service.provider
    available = provider is not None and provider.capability.verification == 'MOCK_ONLY' and provider.capability.local and 'IMAGE' in EmbeddingCapability.model_validate(provider.capability).input_types
    return {'items': rows, 'total': len(rows), 'truncated': result['indexed_count'] > 100,
            'authority': 'ORIGINAL_APPROVED_VISUAL_MEMORY', 'embedding_status': 'CONFIGURED' if available else 'NOT_CONFIGURED',
            'model_quality': 'NOT_RUN', 'automatic_canon': False}


def visual_identity_jobs(service):
    def source(nid, scope, actor, request):
        value = VisualIdentityCheckIn.model_validate(request)
        approved = {row['id']: row for row in profiles(service, nid, scope, actor)['items']}
        snapshots, inputs = [], []
        for ref in value.references:
            profile = approved.get(ref.reference_id)
            if profile is None or profile['character_id'] != value.character_id: raise FileNotFoundError(ref.reference_id)
            if profile['appearance_version'] != ref.appearance_version: raise StaleSourceError('VISUAL_APPEARANCE_CHANGED')
            source_ref = {'entity_type': 'ASSET', 'entity_id': profile['approved_reference_asset']}
            snap, data = service._source(nid, scope, source_ref, actor)
            snapshots.append({'profile_id': ref.reference_id, 'appearance_version': ref.appearance_version,
                              'asset_id': profile['approved_reference_asset'], 'asset': snap,
                              'profile_digest': digest(profile), 'lineage': profile['source_lineage']})
            inputs.append(data)
        candidate, candidate_input = service._source(nid, scope, {'entity_type': 'ASSET', 'entity_id': value.candidate_asset_id}, actor)
        if candidate['version'] != value.candidate_asset_version: raise StaleSourceError('VISUAL_CANDIDATE_CHANGED')
        snapshot = {'references': snapshots, 'candidate': {'asset_id': value.candidate_asset_id, **candidate},
                    'character_id': value.character_id, 'target_media': value.target_media}
        return snapshot, [candidate_input, *inputs]

    def execute(provider, inputs, request, guard):
        capability = EmbeddingCapability.model_validate(provider.capability)
        if 'IMAGE' not in capability.input_types: raise ValueError('VISUAL_IMAGE_EMBEDDING_NOT_CONFIGURED')
        guard()
        vectors = EmbeddingService._vectors(provider.embed(inputs), len(inputs), capability.dimensions)
        guard()
        records = [{'id': ref['reference_id'], 'entity': {'entity_type': 'ASSET', 'entity_id': ref['reference_id']},
                    'source_digest': digest(vector), 'source_version': ref['appearance_version'],
                    'verification': capability.verification, 'vector': vector}
                   for ref, vector in zip(request['references'], vectors[1:])]
        ranked = ExactCosineVectorIndex().search(vectors[0], records, len(records))
        matches = [{'reference_id': row['record_id'], 'similarity': row['score'],
                    'appearance_version': row['source_version'], 'drift_warning': row['score'] < request['drift_threshold']}
                   for row in ranked]
        return {'similarities': matches, 'metric': 'COSINE', 'threshold': request['drift_threshold'],
                'drift_warning': all(row['drift_warning'] for row in matches),
                'verification': capability.verification, 'model_quality': 'NOT_RUN',
                'selection_requires_review': True, 'target_media': request['target_media']}

    return ReviewAdapterJobs(service, 'visual_identity_checks', source, lambda: service.provider, execute)
