from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel,Field


class NarrativeContextView(BaseModel):
    project_id:str
    plot_threads:list[dict[str,Any]]=Field(default_factory=list)
    foreshadowing:list[dict[str,Any]]=Field(default_factory=list)
    mysteries:list[dict[str,Any]]=Field(default_factory=list)
    character_goals:list[dict[str,Any]]=Field(default_factory=list)
    findings:list[dict[str,Any]]=Field(default_factory=list)
    selection_reasons:list[dict[str,str]]=Field(default_factory=list)
    token_budget:int
    estimated_tokens:int=0
    truncated:bool=False


class NarrativeContextBuilder:
    ACTIVE={"threads":{"OPEN","SUSPENDED"},"foreshadowing":{"PLANTED","DEVELOPING"},"mysteries":{"OPEN","DEVELOPING"},"character_goals":{"ACTIVE"}}
    CATEGORY={"threads":"plot_threads","foreshadowing":"foreshadowing","mysteries":"mysteries","character_goals":"character_goals"}
    FALLBACK_REASON={"threads":"ACTIVE_THREAD","foreshadowing":"ACTIVE_FORESHADOWING","mysteries":"OPEN_MYSTERY","character_goals":"ACTIVE_CHARACTER_GOAL"}

    def __init__(self,narrative_repository,token_budget=800):self.repository=narrative_repository;self.token_budget=token_budget

    @staticmethod
    def _cost(item):return max(1,len(json.dumps(item,ensure_ascii=False,sort_keys=True,separators=(",",":")))//4)

    def build(self,project_id,chapter_id,chapter_version,current_character_ids=()):
        snapshot={kind:self.repository.list(project_id,kind) for kind in ("threads","foreshadowing","events","mysteries","character_goals","chapter_links","expectations","findings")}
        current_links=[x for x in snapshot["chapter_links"] if x.get("chapter_id")==chapter_id and x.get("chapter_version")==chapter_version]
        linked={(x["entity_type"],x["entity_id"]) for x in current_links};characters=set(current_character_ids)
        latest={}
        for event in snapshot["events"]:latest[event.get("subject_id")]=event
        expectations={}
        for item in snapshot["expectations"]:
            if item.get("active",True):expectations.setdefault(item["subject_id"],[]).append({"id":item["id"],"type":item["expectation_type"],"deadline_chapter":item["deadline_chapter"],"chapter_version_id":item.get("source_chapter_version_id"),"evidence_ids":item.get("evidence_ids",[])})
        entity_type={"threads":"PLOT_THREAD","foreshadowing":"FORESHADOWING","mysteries":"MYSTERY","character_goals":"CHARACTER_GOAL"}
        candidates=[]
        for kind in ("threads","foreshadowing","mysteries","character_goals"):
            for item in snapshot[kind]:
                if item.get("status") not in self.ACTIVE[kind]:continue
                key=(entity_type[kind],item["id"])
                if key in linked:priority,reason=0,"CURRENT_CHAPTER_LINK"
                elif kind=="character_goals" and item.get("character_id") in characters:priority,reason=1,"CURRENT_CHARACTER_GOAL"
                else:priority,reason=2,self.FALLBACK_REASON[kind]
                entry={"id":item["id"],"title":item.get("title",""),"status":item["status"],"selection_reason":reason}
                if kind=="character_goals":entry["character_id"]=item.get("character_id")
                event=latest.get(item["id"])
                if event:entry["latest_progress"]={"event_id":event["id"],"event_type":event["event_type"],"chapter_version_id":event["chapter_version_id"],"summary":event.get("payload",{}).get("summary",""),"evidence_ids":event.get("evidence_ids",[])}
                if item["id"] in expectations:entry["active_expectations"]=sorted(expectations[item["id"]],key=lambda x:x["id"])
                candidates.append((priority,("threads","foreshadowing","mysteries","character_goals").index(kind),item["id"],kind,entry))
        selected_ids={x[4]["id"] for x in candidates}
        finding_candidates=[]
        for item in snapshot["findings"]:
            if item.get("status")!="OPEN":continue
            selected=item.get("subject_id") in selected_ids;reason="OPEN_FINDING_FOR_SELECTED_ENTITY" if selected else "OPEN_FINDING"
            expected=expectations.get(item.get("subject_id"),[])
            entry={"finding_id":item["id"],"finding_type":item["finding_type"],"status":"OPEN","severity":item.get("severity","MEDIUM"),"subject_id":item.get("subject_id"),"description":item.get("description",""),"expectation_ids":[x["id"] for x in expected],"evidence_ids":item.get("evidence_ids",[]),"chapter_version_id":item.get("source_chapter_version_id"),"selection_reason":reason,"advisory_only":True}
            finding_candidates.append((3 if selected else 4,item["id"],entry))
        output={name:[] for name in self.CATEGORY.values()};output["findings"]=[];reasons=[];used=0;truncated=False
        for _,_,_,kind,entry in sorted(candidates):
            cost=self._cost(entry)
            if used+cost>self.token_budget:truncated=True;continue
            used+=cost;output[self.CATEGORY[kind]].append(entry);reasons.append({"id":entry["id"],"reason":entry["selection_reason"]})
        for _,_,entry in sorted(finding_candidates):
            cost=self._cost(entry)
            if used+cost>self.token_budget:truncated=True;continue
            used+=cost;output["findings"].append(entry);reasons.append({"id":entry["finding_id"],"reason":entry["selection_reason"]})
        return NarrativeContextView(project_id=project_id,selection_reasons=reasons,token_budget=self.token_budget,estimated_tokens=used,truncated=truncated,**output)
