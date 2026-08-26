from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
import json

from ..narrative import (ChapterNarrativeLink, NarrativeChangeProposal, NarrativeEntityType,
    NarrativeProgressType, NarrativeProposalPayload, NarrativeProposalStatus, NarrativeProposalType)


MAPPING = {
    NarrativeProposalType.PLOT_THREAD_ADVANCED: (NarrativeEntityType.PLOT_THREAD, NarrativeProgressType.ADVANCED, "progress_summary"),
    NarrativeProposalType.FORESHADOWING_DEVELOPED: (NarrativeEntityType.FORESHADOWING, NarrativeProgressType.DEVELOPED, "progress_summary"),
    NarrativeProposalType.FORESHADOWING_PAYOFF: (NarrativeEntityType.FORESHADOWING, NarrativeProgressType.PAYOFF, "payoff_summary"),
    NarrativeProposalType.MYSTERY_DEVELOPED: (NarrativeEntityType.MYSTERY, NarrativeProgressType.DEVELOPED, "progress_summary"),
    NarrativeProposalType.MYSTERY_ANSWERED: (NarrativeEntityType.MYSTERY, NarrativeProgressType.ANSWERED, "answer_summary"),
    NarrativeProposalType.CHARACTER_GOAL_ADVANCED: (NarrativeEntityType.CHARACTER_GOAL, NarrativeProgressType.ADVANCED, "progress_summary"),
    NarrativeProposalType.CHARACTER_GOAL_COMPLETED: (NarrativeEntityType.CHARACTER_GOAL, NarrativeProgressType.COMPLETED, "progress_summary"),
    NarrativeProposalType.CHARACTER_GOAL_FAILED: (NarrativeEntityType.CHARACTER_GOAL, NarrativeProgressType.FAILED, "progress_summary"),
}


class NarrativeProposalService:
    def __init__(self, repository, narrative_state_service):
        self.repository=repository;self.narrative_state_service=narrative_state_service

    def _validate(self, proposal_type, subject_type, payload):
        proposal_type=NarrativeProposalType(proposal_type);subject_type=NarrativeEntityType(subject_type)
        expected,progress,field=MAPPING[proposal_type]
        if subject_type is not expected:raise ValueError("proposal type is incompatible with subject type")
        typed=NarrativeProposalPayload(**payload)
        values=asdict(typed)
        if not values[field] or any(value for key,value in values.items() if key!=field):raise ValueError(f"{proposal_type} requires only {field}")
        return proposal_type,subject_type,progress,typed,values[field]

    def create_proposal(self, proposal:NarrativeChangeProposal):
        proposal_type,subject_type,_,typed,_=self._validate(proposal.proposal_type,proposal.subject_type,asdict(proposal.payload))
        self.narrative_state_service.get_subject(proposal.project_id,subject_type,proposal.subject_id)
        chapter_id,version=self._chapter(proposal.chapter_version_id)
        self.narrative_state_service._validate_provenance(proposal.project_id,ChapterNarrativeLink("validation",proposal.project_id,chapter_id,version,subject_type,proposal.subject_id,MAPPING[proposal_type][1],evidence_ids=proposal.evidence_ids,event_id="validation"))
        identity=[proposal.project_id,proposal_type,subject_type,proposal.subject_id,proposal.chapter_version_id,asdict(typed)]
        scope=getattr(self.repository,"scope",None)
        if scope:
            from ..collaboration import DEFAULT_WORKSPACE_ID,default_storyline_id,main_branch_id
            if not (scope.workspace_id==DEFAULT_WORKSPACE_ID and scope.storyline_id==default_storyline_id(scope.project_id) and scope.branch_id==main_branch_id(scope.project_id)):identity.extend([scope.workspace_id,scope.storyline_id,scope.branch_id])
        fingerprint=sha256(json.dumps(identity,sort_keys=True,separators=(",",":"),default=str).encode()).hexdigest()
        old=self.repository.get_proposal_by_fingerprint(proposal.project_id,fingerprint)
        if old:return old
        now=datetime.now(timezone.utc).isoformat();proposal.proposal_type=proposal_type;proposal.subject_type=subject_type;proposal.payload=typed;proposal.status=NarrativeProposalStatus.PENDING;proposal.fingerprint=fingerprint;proposal.created_at=now;proposal.updated_at=now
        self.repository.create(proposal.project_id,"proposals",asdict(proposal))
        return self.repository.get(proposal.project_id,"proposals",proposal.id)

    def list_proposals(self,project_id,status=None):
        rows=self.repository.list(project_id,"proposals")
        return [x for x in rows if status is None or x["status"]==NarrativeProposalStatus(status)]

    def get_proposal(self,project_id,proposal_id):return self.repository.get(project_id,"proposals",proposal_id)

    def accept_proposal(self,project_id,proposal_id):
        proposal=self.get_proposal(project_id,proposal_id)
        if proposal["status"]==NarrativeProposalStatus.ACCEPTED:return proposal
        if proposal["status"]!=NarrativeProposalStatus.PENDING:raise ValueError("rejected proposal cannot be accepted")
        proposal_type,subject_type,progress,_,summary=self._validate(proposal["proposal_type"],proposal["subject_type"],proposal["payload"])
        self.narrative_state_service.get_subject(project_id,subject_type,proposal["subject_id"])
        chapter_id,version=self._chapter(proposal["chapter_version_id"])
        link=ChapterNarrativeLink(f"proposal-link:{proposal_id}",project_id,chapter_id,version,subject_type,proposal["subject_id"],progress,summary,tuple(proposal["evidence_ids"]),f"proposal-event:{proposal_id}")
        accepted={**proposal,"status":NarrativeProposalStatus.ACCEPTED,"updated_at":datetime.now(timezone.utc).isoformat()}
        return self.narrative_state_service.apply_proposal(proposal,link,accepted)

    def reject_proposal(self,project_id,proposal_id):
        proposal=self.get_proposal(project_id,proposal_id)
        if proposal["status"]==NarrativeProposalStatus.REJECTED:return proposal
        if proposal["status"]!=NarrativeProposalStatus.PENDING:raise ValueError("accepted proposal cannot be rejected")
        updated={**proposal,"status":NarrativeProposalStatus.REJECTED,"updated_at":datetime.now(timezone.utc).isoformat()}
        return self.repository.update(project_id,"proposals",proposal_id,updated)

    @staticmethod
    def _chapter(chapter_version_id):
        try:chapter_id,version=chapter_version_id.rsplit(":v",1);return chapter_id,int(version)
        except (ValueError,TypeError):raise ValueError("invalid chapter_version_id")
