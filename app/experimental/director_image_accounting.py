"""Bounded human declarations over original IMAGE terminal accounting.

These receipts are passive local accounting evidence, not measured usage,
provider invoices, execution authority, or recovery of an orphaned executor.
The caller must validate the terminal against the original saved job and hold
the original coordinator's scope -> Asset -> project transaction.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from hashlib import sha256
import re
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .common import snapshot
from .store import canonical

PROFILE = 'LOCAL_VISION_IMAGE_UNDERSTANDING_V3'
DECLARATION_FIELD = 'director_image_cost_declaration'
SEMANTICS = 'HUMAN_DECLARATION_NOT_MEASURED_OR_PROVIDER_VERIFIED'


def _digest(value):
    return sha256(canonical(value).encode()).hexdigest()


class DirectorImageCostDeclarationInput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, frozen=True,
                              revalidate_instances='always')
    contract: Literal['DIRECTOR_IMAGE_COST_DECLARATION_V3'] = 'DIRECTOR_IMAGE_COST_DECLARATION_V3'
    request_id: str = Field(min_length=1, max_length=160)
    expected_version: int = Field(ge=1, le=2**53 - 1)
    reviewed_terminal_digest: str = Field(pattern=r'^[0-9a-f]{64}$')
    declared_microusd: int = Field(ge=0, le=10**12)
    evidence_note: str = Field(min_length=1, max_length=500)
    confirmed_declaration: bool

    @model_validator(mode='after')
    def explicit_declaration(self):
        if (not self.request_id.strip() or not self.evidence_note.strip()
                or self.confirmed_declaration is not True):
            raise ValueError('BROKER_IMAGE_EXPLICIT_COST_DECLARATION_REQUIRED')
        return self


def terminal_accounting(nid, scope, actor, terminal):
    """Check the immutable IMAGE identity in a server-validated terminal."""
    from ..creative.director_image_binding import ImageBinding
    try:
        if not isinstance(terminal, dict) or set(terminal) != {
                'contract', 'job_id', 'binding', 'request_digest', 'output_digest',
                'output_bytes', 'accounting', 'consumer_authority', 'checkpoint_at', 'semantics'}:
            raise ValueError()
        binding = ImageBinding.model_validate(terminal['binding'])
        source = binding.source
        row = terminal['accounting']
        if (terminal['contract'] != 'DIRECTOR_IMAGE_TERMINAL_V3'
                or terminal['consumer_authority'] is not False
                or terminal['semantics'] != 'AUTHORITY_AND_BOUNDS_SAMPLED_PRE_COMMIT'
                or str(UUID(terminal['job_id'])) != terminal['job_id']
                or not re.fullmatch(r'[0-9a-f]{64}', terminal['request_digest'])
                or not re.fullmatch(r'[0-9a-f]{64}', terminal['output_digest'])
                or type(terminal['output_bytes']) is not int
                or not 0 < terminal['output_bytes'] <= 128000
                or datetime.fromisoformat(terminal['checkpoint_at']).tzinfo is None
                or source.project_id != nid or source.scope.model_dump() != scope
                or source.actor_id != actor or not isinstance(row, dict)
                or row.get('novel_id') != nid or row.get('scope') != scope
                or row.get('created_by') != actor or row.get('job_id') != terminal['job_id']
                or row.get('candidate_profile') != PROFILE
                or row.get('director_image_incarnation') != source.project_incarnation
                or row.get('authorization_digest') != terminal['request_digest']
                or row.get('director_image_binding_digest') != terminal['request_digest']
                or 'native_ocr_incarnation' in row or DECLARATION_FIELD in row
                or row.get('status') != 'UNKNOWN_UPSTREAM'
                or row.get('cost_state') != 'UNKNOWN_UPSTREAM'
                or row.get('actual_microusd') is not None
                or row.get('dispatched') is not True or row.get('job_status') != 'COMPLETED'
                or row.get('currency') != 'USD'
                or type(row.get('version')) is not int or not 1 <= row['version'] < 2**53 - 1
                or not isinstance(row.get('history'), list)
                or any(not isinstance(item, dict) or 'history' in item for item in row['history'])
                or not re.fullmatch(r'[0-9a-f]{64}', row.get('id', ''))):
            raise ValueError()
        # Canonical validation also rejects non-finite or non-JSON proof data.
        canonical(terminal)
        return deepcopy(row)
    except (ValueError, TypeError, KeyError, AttributeError):
        raise ValueError('BROKER_IMAGE_TERMINAL_ACCOUNTING_INVALID') from None


def declaration_proof(body, terminal, original):
    """Deterministic receipt for one exact reviewed declaration and terminal."""
    request = body.model_dump()
    proof = {
        'contract': 'DIRECTOR_IMAGE_COST_DECLARATION_RECEIPT_V3',
        'request': request, 'request_id': body.request_id,
        'request_digest': _digest(request),
        'reservation_id': original['id'], 'job_id': original['job_id'],
        'novel_id': original['novel_id'], 'scope': deepcopy(original['scope']),
        'actor_id': original['created_by'],
        'project_incarnation': original['director_image_incarnation'],
        'authorization_digest': original['authorization_digest'],
        'reviewed_terminal_digest': _digest(terminal),
        'terminal_accounting_digest': _digest(original),
        'previous_version': original['version'], 'resolved_version': original['version'] + 1,
        'declared_microusd': body.declared_microusd, 'measurement_verified': False,
        'cost_state': 'HUMAN_DECLARED_LOCAL_COST', 'evidence_kind': 'HUMAN_DECLARED_LOCAL_COST',
        'semantics': SEMANTICS,
    }
    return {**proof, 'receipt_digest': _digest(proof)}


def declaration_changes(body, proof, original):
    amount = body.declared_microusd
    reserve = original.get('reserve_microusd')
    return {
        'status': 'RECONCILED', 'cost_state': 'HUMAN_DECLARED_LOCAL_COST',
        'declared_microusd': amount, 'measurement_verified': False,
        # Compatibility with original budget arithmetic, explicitly not usage.
        'actual_microusd': amount, 'accounted_microusd': amount,
        'actual_microusd_semantics': SEMANTICS,
        'reconciliation_source': 'EXPLICIT_HUMAN_LOCAL_COST_DECLARATION',
        'reconciliation_note': body.evidence_note, 'upstream_terminal_confirmed': True,
        'reconciled_orphan': False, 'automatic_replay': False,
        'overrun': reserve is not None and amount > reserve,
        'overrun_acknowledged': True, DECLARATION_FIELD: deepcopy(proof),
    }


def validate_director_image_cost_resolution(nid, scope, actor, ledger, *, terminal):
    """Return proof only for the exact original one-step ledger declaration.

The original terminal remains UNKNOWN_UPSTREAM forever. Its full prior
history and exact history-free terminal snapshot must be retained by the
original change_row transition. No caller-supplied or reconstructed history
can stand in for a terminal loaded and validated by the coordinator.
"""
    original = terminal_accounting(nid, scope, actor, terminal)
    try:
        proof = ledger[DECLARATION_FIELD]
        body = DirectorImageCostDeclarationInput.model_validate(proof['request'])
        expected_proof = declaration_proof(body, terminal, original)
        if (body.expected_version != original['version']
                or body.reviewed_terminal_digest != _digest(terminal)
                or canonical(proof) != canonical(expected_proof)
                or datetime.fromisoformat(ledger['updated_at']).tzinfo is None):
            raise ValueError()
        expected = deepcopy(original)
        expected.update(declaration_changes(body, expected_proof, original))
        expected.update(version=original['version'] + 1, updated_by=actor,
                        updated_at=ledger['updated_at'],
                        history=deepcopy(original['history']) + [snapshot(original)])
        if canonical(ledger) != canonical(expected):
            raise ValueError()
        return deepcopy(expected_proof)
    except (ValueError, TypeError, KeyError, AttributeError):
        raise ValueError('BROKER_IMAGE_COST_RESOLUTION_INVALID') from None
