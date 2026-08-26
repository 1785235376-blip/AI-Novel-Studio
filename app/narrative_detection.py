from __future__ import annotations
from dataclasses import dataclass,field
from enum import StrEnum
from hashlib import sha256
import json

class NarrativeFindingStatus(StrEnum):OPEN="OPEN";RESOLVED="RESOLVED"
@dataclass(frozen=True)
class NarrativeExpectation:
 id:str;project_id:str;subject_type:str;subject_id:str;expectation_type:str;deadline_chapter:int;evidence_ids:tuple[str,...]=();source_chapter_version_id:str|None=None;active:bool=True
@dataclass
class NarrativeFinding:
 id:str;project_id:str;finding_type:str;subject_id:str;description:str;severity:str="MEDIUM";status:NarrativeFindingStatus=NarrativeFindingStatus.OPEN;evidence_ids:list[str]=field(default_factory=list);source_chapter_version_id:str|None=None
@dataclass
class NarrativeRuleContext:
 project_id:str;current_chapter:int;expectations:list[NarrativeExpectation]=field(default_factory=list);thread_last_progress:dict[str,int]=field(default_factory=dict);foreshadowing_payoff_chapter:dict[str,int]=field(default_factory=dict);mysteries:list[dict]=field(default_factory=list);character_goals:list[dict]=field(default_factory=list);narrative_events:list[dict]=field(default_factory=list);storyline_id:str|None=None;branch_id:str|None=None
def _finding(ctx,rule,e):
 identity=[ctx.project_id,rule,e.subject_id,e.id]
 if ctx.storyline_id is not None or ctx.branch_id is not None:identity.extend([ctx.storyline_id,ctx.branch_id])
 raw=json.dumps(identity,separators=(",",":"));fid=sha256(raw.encode()).hexdigest()
 return NarrativeFinding(fid,ctx.project_id,rule,e.subject_id,f"Explicit expectation {e.id} is overdue.",evidence_ids=list(e.evidence_ids),source_chapter_version_id=e.source_chapter_version_id)
def thread_stale(ctx):
 return [_finding(ctx,"THREAD_STALE",e) for e in ctx.expectations if e.active and e.expectation_type=="THREAD_PROGRESS_BY" and ctx.current_chapter>e.deadline_chapter and ctx.thread_last_progress.get(e.subject_id,0)<e.deadline_chapter]
def foreshadowing_overdue(ctx):
 return [_finding(ctx,"FORESHADOWING_OVERDUE",e) for e in ctx.expectations if e.active and e.expectation_type=="FORESHADOWING_PAYOFF_BY" and ctx.current_chapter>e.deadline_chapter and ctx.foreshadowing_payoff_chapter.get(e.subject_id,10**9)>e.deadline_chapter]
def mystery_overdue(ctx):
 states={x["id"]:x.get("status") for x in ctx.mysteries if x.get("project_id")==ctx.project_id}
 return [_finding(ctx,"MYSTERY_OVERDUE",e) for e in ctx.expectations if e.active and e.expectation_type=="MYSTERY_ANSWER_BY" and ctx.current_chapter>e.deadline_chapter and states.get(e.subject_id) in {"OPEN","DEVELOPING"}]
def character_goal_stale(ctx):
 states={x["id"]:x.get("status") for x in ctx.character_goals if x.get("project_id")==ctx.project_id}
 progressed={x.get("subject_id") for x in ctx.narrative_events if x.get("project_id")==ctx.project_id and x.get("event_type")=="CHARACTER_GOAL:ADVANCED"}
 return [_finding(ctx,"CHARACTER_GOAL_STALE",e) for e in ctx.expectations if e.active and e.expectation_type=="CHARACTER_GOAL_PROGRESS_BY" and ctx.current_chapter>e.deadline_chapter and states.get(e.subject_id)=="ACTIVE" and e.subject_id not in progressed]
class NarrativeRuleRegistry:
 def __init__(self):self.rules={}
 def register(self,rule_id,fn):
  if rule_id in self.rules:raise ValueError(rule_id)
  self.rules[rule_id]=fn
 def evaluate(self,ctx):
  out=[]
  for fn in self.rules.values():out.extend(fn(ctx))
  return out
 def evaluate_isolated(self,ctx):
  out=[];successful=[]
  for key,fn in self.rules.items():
   try:out.extend(fn(ctx));successful.append(key)
   except Exception:pass
  return out,successful
registry=NarrativeRuleRegistry();registry.register("THREAD_STALE",thread_stale);registry.register("FORESHADOWING_OVERDUE",foreshadowing_overdue);registry.register("MYSTERY_OVERDUE",mystery_overdue);registry.register("CHARACTER_GOAL_STALE",character_goal_stale)
