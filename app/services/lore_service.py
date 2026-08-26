from __future__ import annotations

from app.lore.enums import EvidenceStatus, RelationRelevance
from app.lore.schemas import Evidence, LoreProposal, ProposalEvidenceRelation
from app.repositories.lore_interfaces import LoreRepositoryProtocol


class LoreService:
    def __init__(self, repository: LoreRepositoryProtocol):
        self.repository = repository

    def create_evidence(self, item: dict) -> dict:
        return self.repository.create_evidence(Evidence.model_validate(item).model_dump(mode="json"))

    def invalidate_evidence(self, evidence_id: str, reason: str) -> dict:
        if not reason.strip(): raise ValueError("invalidation reason is required")
        return self.repository.invalidate_evidence(evidence_id, reason.strip())

    def create_proposal(self, item: dict, relations: list[dict]) -> dict:
        proposal = LoreProposal.model_validate(item)
        if not relations: raise ValueError("proposal requires evidence")
        parsed = [ProposalEvidenceRelation.model_validate({**relation, "proposal_id": proposal.id}) for relation in relations]
        if not any(relation.relevance == RelationRelevance.PRIMARY for relation in parsed):
            raise ValueError("proposal requires PRIMARY evidence")
        evidence_items = [self.repository.get_evidence(relation.evidence_id) for relation in parsed]
        if any(evidence["novel_id"] != proposal.novel_id for evidence in evidence_items):
            raise ValueError("proposal and evidence must belong to the same novel")
        created = self.repository.create_proposal(proposal.model_dump(mode="json"))
        for relation in parsed: self.repository.link_evidence(relation.model_dump(mode="json"))
        return created

    def approve_proposal(self, proposal_id: str, approved_payload: dict, reviewer: str) -> dict:
        if not reviewer.strip(): raise ValueError("reviewer is required")
        proposal = self.repository.get_proposal(proposal_id)
        relations = self.repository.list_proposal_evidence(proposal_id)
        if not relations: raise ValueError("proposal requires evidence")
        evidence_items = [self.repository.get_evidence(relation["evidence_id"]) for relation in relations]
        if any(evidence["novel_id"] != proposal["novel_id"] for evidence in evidence_items):
            raise ValueError("proposal and evidence must belong to the same novel")
        if any(evidence["status"] != EvidenceStatus.ACTIVE for evidence in evidence_items):
            raise ValueError("all proposal evidence must be ACTIVE")
        return self.repository.approve_proposal(proposal_id, approved_payload, reviewer.strip())

    def reject_proposal(self, proposal_id: str, reviewer: str, reason: str | None = None) -> dict:
        if not reviewer.strip(): raise ValueError("reviewer is required")
        return self.repository.reject_proposal(proposal_id, reviewer.strip(), reason)
