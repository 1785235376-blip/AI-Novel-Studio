"""V3 terminal evidence in the original generation repository only."""
from contextvars import ContextVar
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Literal
from pydantic import Field
from .director_binding import _Frozen, Digest
from .director_image_binding import ImageBinding, job_binding
from .director_terminal_evidence import digest

FIELD = 'director_image_terminal_v3'
_publication = ContextVar('director_image_terminal_publication', default=None)

class ImageAdvice(_Frozen):
    contract: Literal['DIRECTOR_IMAGE_ADVICE_V3'] = 'DIRECTOR_IMAGE_ADVICE_V3'
    observations: list[str] = Field(min_length=1, max_length=8)
    suggestions: list[str] = Field(min_length=1, max_length=8)
    uncertainty: str = Field(min_length=1, max_length=2000)


def parse_advice(text):
    if not isinstance(text, str) or not 0 < len(text.encode()) <= 128000:
        raise ValueError('DIRECTOR_IMAGE_OUTPUT_INVALID')
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result: raise ValueError('duplicate key')
            result[key] = value
        return result
    def constant(_): raise ValueError('nonfinite')
    try:
        result = ImageAdvice.model_validate(json.loads(text, object_pairs_hook=pairs, parse_constant=constant))
        if any(not value.strip() or len(value) > 2000 for value in [*result.observations, *result.suggestions]):
            raise ValueError('invalid advice')
        return result.model_dump()
    except (ValueError, TypeError, RecursionError):
        raise ValueError('DIRECTOR_IMAGE_OUTPUT_INVALID') from None


def validate(item, evidence):
    job_binding(item)
    if (not isinstance(evidence, dict) or set(evidence) != {'contract','job_id','binding','request_digest','output_digest','output_bytes','accounting','consumer_authority','checkpoint_at','semantics'}
            or evidence['semantics'] != 'AUTHORITY_AND_BOUNDS_SAMPLED_PRE_COMMIT'
            or evidence['contract'] != 'DIRECTOR_IMAGE_TERMINAL_V3' or evidence['consumer_authority'] is not False
            or evidence['job_id'] != item['id'] or evidence['binding'] != item['director_image_binding']
            or evidence['request_digest'] != item['expected_request_digest']
            or item.get('provider') != item.get('requested_provider') or item.get('model') != item.get('requested_model')
            or item.get('execution_outcome') != 'COMPLETED'
            or item.get('status') != 'COMPLETED' or item.get('terminal_hook_status') != 'COMPLETED'
            or evidence['output_digest'] != sha256(item.get('output','').encode()).hexdigest()
            or evidence['output_bytes'] != len(item.get('output','').encode())
            or evidence['accounting'].get('status') != 'UNKNOWN_UPSTREAM'
            or evidence['accounting'].get('actual_microusd') is not None
            or evidence['accounting'].get('job_id') != item['id']
            or evidence['accounting'].get('dispatched') is not True
            or evidence['accounting'].get('job_status') != 'COMPLETED'
            or evidence['accounting'].get('created_by') != item['actor_id']
            or evidence['accounting'].get('scope') != item['scope']
            or evidence['accounting'].get('provider_id') != item.get('requested_provider')
            or evidence['accounting'].get('model_id') != item.get('requested_model')
            or evidence['accounting'].get('authorization_digest') != item['expected_request_digest']
            or evidence['accounting'].get('director_image_binding_digest') != item['expected_request_digest']
            or evidence['accounting'].get('director_image_incarnation') != item['director_image_binding']['source']['project_incarnation']):
        raise ValueError('DIRECTOR_IMAGE_TERMINAL_INVALID')
    checkpoint,deadline = datetime.fromisoformat(evidence['checkpoint_at']),datetime.fromisoformat(item['generation_deadline'])
    if checkpoint.tzinfo is None or deadline.tzinfo is None or checkpoint >= deadline:
        raise ValueError('DIRECTOR_IMAGE_TERMINAL_DEADLINE_INVALID')
    parse_advice(item['output'])
    return deepcopy(evidence)


def preserve(previous, item):
    old = (previous or {}).get(FIELD)
    supplied = item.get(FIELD)
    if old is not None:
        if supplied != old: raise ValueError('DIRECTOR_IMAGE_TERMINAL_IMMUTABLE')
        validate(item, supplied)
    elif supplied is not None:
        active = _publication.get()
        if active is None or active != (item['id'], digest(item)):
            raise ValueError('DIRECTOR_IMAGE_TERMINAL_PRIVATE_OWNER_REQUIRED')
        validate(item, supplied)
    return item


def publish(manager, job, capability, accounting):
    capability.current()
    if capability.publication_state != 'PENDING': raise ValueError('DIRECTOR_IMAGE_PUBLICATION_ALREADY_ATTEMPTED')
    capability.publication_state = 'PUBLISHING'
    item = job.public()
    evidence = {'contract':'DIRECTOR_IMAGE_TERMINAL_V3','job_id':job.id,
        'binding':deepcopy(job.director_image_binding),'request_digest':job.expected_request_digest,
        'output_digest':sha256(job.output.encode()).hexdigest(),'output_bytes':len(job.output.encode()),
        'accounting':deepcopy(accounting),'consumer_authority':False,
        'checkpoint_at':datetime.now(timezone.utc).isoformat(),'semantics':'AUTHORITY_AND_BOUNDS_SAMPLED_PRE_COMMIT'}
    item[FIELD] = evidence
    validate(item, evidence)
    token = _publication.set((job.id,digest(item)))
    try:
        with capability.coordinator.transaction(capability.binding,capability.guard,capability.host):
            capability.current()
            manager.persistence.save(item)
            saved = manager.persistence.get(job.id)
            if saved.get(FIELD) != evidence: raise ValueError('DIRECTOR_IMAGE_PUBLICATION_UNCONFIRMED')
            validate(saved, evidence)
            capability.current()
        job.director_image_terminal_v3 = evidence
        capability.publication_state = 'CONFIRMED'
    except Exception:
        capability.publication_state = 'UNKNOWN'
        raise
    finally: _publication.reset(token)
    return evidence
