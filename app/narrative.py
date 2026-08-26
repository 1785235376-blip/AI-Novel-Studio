from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from hashlib import sha256
import json


class ThreadStatus(StrEnum):
    OPEN = "OPEN"
    SUSPENDED = "SUSPENDED"
    RESOLVED = "RESOLVED"
    ABANDONED = "ABANDONED"


class ForeshadowingStatus(StrEnum):
    PLANTED = "PLANTED"
    DEVELOPING = "DEVELOPING"
    PAYOFF = "PAYOFF"
    RETRACTED = "RETRACTED"

class MysteryStatus(StrEnum):
    OPEN="OPEN"; DEVELOPING="DEVELOPING"; ANSWERED="ANSWERED"; ABANDONED="ABANDONED"

class CharacterGoalStatus(StrEnum):
    ACTIVE="ACTIVE"; SUSPENDED="SUSPENDED"; COMPLETED="COMPLETED"; FAILED="FAILED"; ABANDONED="ABANDONED"

class NarrativeEntityType(StrEnum):
    PLOT_THREAD="PLOT_THREAD"; FORESHADOWING="FORESHADOWING"; MYSTERY="MYSTERY"; CHARACTER_GOAL="CHARACTER_GOAL"

class NarrativeProgressType(StrEnum):
    ADVANCED="ADVANCED"; DEVELOPED="DEVELOPED"; PAYOFF="PAYOFF"; ANSWERED="ANSWERED"; COMPLETED="COMPLETED"; FAILED="FAILED"

class NarrativeProposalStatus(StrEnum):PENDING="PENDING";ACCEPTED="ACCEPTED";REJECTED="REJECTED"
class NarrativeProposalType(StrEnum):
    PLOT_THREAD_ADVANCED="PLOT_THREAD_ADVANCED";FORESHADOWING_DEVELOPED="FORESHADOWING_DEVELOPED";FORESHADOWING_PAYOFF="FORESHADOWING_PAYOFF";MYSTERY_DEVELOPED="MYSTERY_DEVELOPED";MYSTERY_ANSWERED="MYSTERY_ANSWERED";CHARACTER_GOAL_ADVANCED="CHARACTER_GOAL_ADVANCED";CHARACTER_GOAL_COMPLETED="CHARACTER_GOAL_COMPLETED";CHARACTER_GOAL_FAILED="CHARACTER_GOAL_FAILED"


@dataclass(frozen=True)
class NarrativeEvent:
    id: str
    project_id: str
    event_type: str
    subject_id: str
    chapter_version_id: str
    evidence_ids: tuple[str, ...] = ()
    payload: dict = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def fingerprint(self):
        raw=json.dumps([self.project_id,self.event_type,self.subject_id,self.chapter_version_id,self.evidence_ids,self.payload],sort_keys=True,separators=(",",":"))
        return sha256(raw.encode()).hexdigest()


@dataclass
class PlotThread:
    id: str
    project_id: str
    title: str
    status: ThreadStatus = ThreadStatus.OPEN
    description: str = ""
    event_ids: list[str] = field(default_factory=list)


@dataclass
class Foreshadowing:
    id: str
    project_id: str
    title: str
    status: ForeshadowingStatus = ForeshadowingStatus.PLANTED
    thread_id: str | None = None
    planted_event_id: str | None = None
    payoff_event_id: str | None = None

@dataclass
class Mystery:
    id:str; project_id:str; title:str; description:str=""; status:MysteryStatus=MysteryStatus.OPEN
    opened_chapter_version_id:str|None=None; answered_chapter_version_id:str|None=None

@dataclass
class CharacterGoal:
    id:str; project_id:str; character_id:str; title:str; description:str=""; status:CharacterGoalStatus=CharacterGoalStatus.ACTIVE
    started_chapter_version_id:str|None=None; completed_chapter_version_id:str|None=None

@dataclass(frozen=True)
class ChapterNarrativeLink:
    id:str; project_id:str; chapter_id:str; chapter_version:int; entity_type:NarrativeEntityType
    entity_id:str; progress_type:NarrativeProgressType; summary:str=""; evidence_ids:tuple[str,...]=(); event_id:str=""

@dataclass(frozen=True)
class NarrativeProposalPayload:
    progress_summary:str|None=None;payoff_summary:str|None=None;answer_summary:str|None=None

@dataclass
class NarrativeChangeProposal:
    id:str;project_id:str;proposal_type:NarrativeProposalType;subject_type:NarrativeEntityType;subject_id:str;chapter_version_id:str
    payload:NarrativeProposalPayload;evidence_ids:tuple[str,...]=();summary:str="";status:NarrativeProposalStatus=NarrativeProposalStatus.PENDING
    fingerprint:str="";created_at:str="";updated_at:str=""


class NarrativeStateView:
    def __init__(self, project_id: str, threads=(), foreshadowing=(), events=(), mysteries=(), character_goals=()):
        self.project_id=project_id; self.threads=list(threads); self.foreshadowing=list(foreshadowing); self.events=list(events);self.mysteries=list(mysteries);self.character_goals=list(character_goals)

    def reconstruct(self, event_history):
        seen={event.id for event in self.events}
        for event in sorted(event_history,key=lambda e:(e.created_at,e.id)):
            if event.project_id!=self.project_id or event.id in seen: continue
            self.events.append(event)
            seen.add(event.id)
            for thread in self.threads:
                if thread.id==event.subject_id and event.id not in thread.event_ids: thread.event_ids.append(event.id)
        return self


def transition_thread(thread: PlotThread, target: ThreadStatus) -> PlotThread:
    allowed={ThreadStatus.OPEN:{ThreadStatus.SUSPENDED,ThreadStatus.RESOLVED,ThreadStatus.ABANDONED},ThreadStatus.SUSPENDED:{ThreadStatus.OPEN,ThreadStatus.RESOLVED,ThreadStatus.ABANDONED},ThreadStatus.RESOLVED:set(),ThreadStatus.ABANDONED:set()}
    if target not in allowed[thread.status]: raise ValueError(f"Illegal PlotThread transition {thread.status}->{target}")
    thread.status=target; return thread


def transition_foreshadowing(item: Foreshadowing, target: ForeshadowingStatus, payoff_event_id: str | None = None) -> Foreshadowing:
    allowed={ForeshadowingStatus.PLANTED:{ForeshadowingStatus.DEVELOPING,ForeshadowingStatus.RETRACTED},ForeshadowingStatus.DEVELOPING:{ForeshadowingStatus.PAYOFF,ForeshadowingStatus.RETRACTED},ForeshadowingStatus.PAYOFF:set(),ForeshadowingStatus.RETRACTED:set()}
    if target not in allowed[item.status]: raise ValueError(f"Illegal Foreshadowing transition {item.status}->{target}")
    if target is ForeshadowingStatus.PAYOFF and not payoff_event_id: raise ValueError("Payoff requires an event")
    item.status=target; item.payoff_event_id=payoff_event_id or item.payoff_event_id; return item

def transition_mystery(item:Mystery,target:MysteryStatus,chapter_version_id:str|None=None)->Mystery:
    allowed={MysteryStatus.OPEN:{MysteryStatus.DEVELOPING,MysteryStatus.ANSWERED,MysteryStatus.ABANDONED},MysteryStatus.DEVELOPING:{MysteryStatus.ANSWERED,MysteryStatus.ABANDONED},MysteryStatus.ANSWERED:set(),MysteryStatus.ABANDONED:set()}
    if target not in allowed[item.status]:raise ValueError(f"Illegal Mystery transition {item.status}->{target}")
    item.status=target
    if target is MysteryStatus.ANSWERED:item.answered_chapter_version_id=chapter_version_id
    return item

def transition_character_goal(item:CharacterGoal,target:CharacterGoalStatus,chapter_version_id:str|None=None)->CharacterGoal:
    active={CharacterGoalStatus.SUSPENDED,CharacterGoalStatus.COMPLETED,CharacterGoalStatus.FAILED,CharacterGoalStatus.ABANDONED}
    suspended={CharacterGoalStatus.ACTIVE,CharacterGoalStatus.COMPLETED,CharacterGoalStatus.FAILED,CharacterGoalStatus.ABANDONED}
    allowed={CharacterGoalStatus.ACTIVE:active,CharacterGoalStatus.SUSPENDED:suspended,CharacterGoalStatus.COMPLETED:set(),CharacterGoalStatus.FAILED:set(),CharacterGoalStatus.ABANDONED:set()}
    if target not in allowed[item.status]:raise ValueError(f"Illegal CharacterGoal transition {item.status}->{target}")
    item.status=target
    if target is CharacterGoalStatus.COMPLETED:item.completed_chapter_version_id=chapter_version_id
    return item

PROGRESS_ENTITY_TYPES={
    NarrativeEntityType.PLOT_THREAD:{NarrativeProgressType.ADVANCED},
    NarrativeEntityType.FORESHADOWING:{NarrativeProgressType.DEVELOPED,NarrativeProgressType.PAYOFF},
    NarrativeEntityType.MYSTERY:{NarrativeProgressType.DEVELOPED,NarrativeProgressType.ANSWERED},
    NarrativeEntityType.CHARACTER_GOAL:{NarrativeProgressType.ADVANCED,NarrativeProgressType.COMPLETED,NarrativeProgressType.FAILED},
}
def validate_chapter_narrative_link(link:ChapterNarrativeLink):
    if link.progress_type not in PROGRESS_ENTITY_TYPES[link.entity_type]:raise ValueError(f"{link.progress_type} is invalid for {link.entity_type}")
    return link
