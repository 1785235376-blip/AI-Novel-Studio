from __future__ import annotations

from .enums import EvidenceStatus, ProposalStatus


def require_proposal_transition(current: str, target: str) -> None:
    if current != ProposalStatus.PENDING or target not in {ProposalStatus.APPROVED, ProposalStatus.REJECTED}:
        raise ValueError(f"invalid proposal transition: {current} -> {target}")


def require_evidence_transition(current: str, target: str) -> None:
    if current != EvidenceStatus.ACTIVE or target != EvidenceStatus.INVALIDATED:
        raise ValueError(f"invalid evidence transition: {current} -> {target}")
