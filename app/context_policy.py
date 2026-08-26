from __future__ import annotations

import json
from enum import StrEnum
from typing import Any

from pydantic import BaseModel,Field


class ContextAuthorityLevel(StrEnum):
    AUTHORITATIVE="AUTHORITATIVE";CONSTRAINING="CONSTRAINING";SUPPORTING="SUPPORTING";ADVISORY="ADVISORY"

class ContextSourceType(StrEnum):
    CANON="CANON";ACCEPTED_CHAPTER="ACCEPTED_CHAPTER";TIMELINE="TIMELINE";CHARACTER_KNOWLEDGE="CHARACTER_KNOWLEDGE";LORE_MEMORY="LORE_MEMORY";NARRATIVE_STATE="NARRATIVE_STATE";NARRATIVE_FINDING="NARRATIVE_FINDING";EVIDENCE_REFERENCE="EVIDENCE_REFERENCE"

class ContextSourceMetadata(BaseModel):
    source_type:ContextSourceType;authority_level:ContextAuthorityLevel;source_id:str;project_id:str
    chapter_version_id:str|None=None;evidence_ids:list[str]=Field(default_factory=list);selection_reasons:list[str]=Field(default_factory=list)
    locality:str="CLOUD_ALLOWED";fact_key:str|None=None

class ContextPolicyItem(BaseModel):
    metadata:ContextSourceMetadata;value:Any

class ContextConflict(BaseModel):
    conflict_key:str;higher_authority_sources:list[str];lower_authority_sources:list[str]=Field(default_factory=list)
    resolution_policy:str;writer_visibility:str;reason:str

class ContextPolicyResult(BaseModel):
    authoritative:list[ContextPolicyItem]=Field(default_factory=list);constraining:list[ContextPolicyItem]=Field(default_factory=list)
    supporting:list[ContextPolicyItem]=Field(default_factory=list);advisory:list[ContextPolicyItem]=Field(default_factory=list)
    conflicts:list[ContextConflict]=Field(default_factory=list);duplicate_count:int=0;budget_usage:dict[str,int]=Field(default_factory=dict)
    truncated_sources:list[str]=Field(default_factory=list);authoritative_context_truncated:bool=False;total_token_budget:int
    writer_contract:list[str]=Field(default_factory=lambda:["Higher-authority context overrides lower-authority context.","Advisories are warnings, not facts.","Do not guess through unresolved authoritative conflicts.","Context does not permit source-state mutation."])


class ContextPolicy:
    AUTHORITY={ContextSourceType.CANON:ContextAuthorityLevel.AUTHORITATIVE,ContextSourceType.ACCEPTED_CHAPTER:ContextAuthorityLevel.AUTHORITATIVE,ContextSourceType.TIMELINE:ContextAuthorityLevel.CONSTRAINING,ContextSourceType.CHARACTER_KNOWLEDGE:ContextAuthorityLevel.CONSTRAINING,ContextSourceType.LORE_MEMORY:ContextAuthorityLevel.SUPPORTING,ContextSourceType.NARRATIVE_STATE:ContextAuthorityLevel.SUPPORTING,ContextSourceType.NARRATIVE_FINDING:ContextAuthorityLevel.ADVISORY,ContextSourceType.EVIDENCE_REFERENCE:ContextAuthorityLevel.SUPPORTING}
    AUTHORITY_ORDER={ContextAuthorityLevel.AUTHORITATIVE:0,ContextAuthorityLevel.CONSTRAINING:1,ContextAuthorityLevel.SUPPORTING:2,ContextAuthorityLevel.ADVISORY:3}
    SOURCE_ORDER={source:index for index,source in enumerate(ContextSourceType)}
    ALLOCATION={ContextAuthorityLevel.AUTHORITATIVE:40,ContextAuthorityLevel.CONSTRAINING:25,ContextAuthorityLevel.SUPPORTING:25,ContextAuthorityLevel.ADVISORY:10}

    def __init__(self,total_token_budget=2400):self.total_token_budget=total_token_budget
    @staticmethod
    def estimate(item):return max(1,len(json.dumps(item.model_dump(mode="json"),ensure_ascii=False,sort_keys=True,separators=(",",":")))//4)
    def metadata(self,source_type,source_id,project_id,**kwargs):return ContextSourceMetadata(source_type=source_type,authority_level=self.AUTHORITY[ContextSourceType(source_type)],source_id=source_id,project_id=project_id,**kwargs)
    def apply(self,items:list[ContextPolicyItem],cloud=False):
        eligible=[x for x in items if not (cloud and x.metadata.locality=="LOCAL_ONLY")]
        deduped={};duplicates=0
        for item in sorted(eligible,key=self._sort_key):
            m=item.metadata;canonical=json.dumps(item.value,ensure_ascii=False,sort_keys=True,separators=(",",":"));key=(m.source_type,m.source_id,m.chapter_version_id,canonical)
            if key not in deduped:deduped[key]=item;continue
            duplicates+=1;old=deduped[key];old.metadata.selection_reasons=sorted(set(old.metadata.selection_reasons+m.selection_reasons))
        values=list(deduped.values());omitted=set();conflicts=[]
        groups={}
        for item in values:
            if item.metadata.fact_key:groups.setdefault(item.metadata.fact_key,[]).append(item)
        for key,group in sorted(groups.items()):
            distinct={json.dumps(x.value,ensure_ascii=False,sort_keys=True,separators=(",",":")) for x in group}
            if len(distinct)<2:continue
            best=min(self.AUTHORITY_ORDER[x.metadata.authority_level] for x in group);high=[x for x in group if self.AUTHORITY_ORDER[x.metadata.authority_level]==best];low=[x for x in group if x not in high]
            if len({json.dumps(x.value,ensure_ascii=False,sort_keys=True,separators=(",",":")) for x in high})>1:
                conflicts.append(ContextConflict(conflict_key=key,higher_authority_sources=sorted(x.metadata.source_id for x in high),lower_authority_sources=sorted(x.metadata.source_id for x in low),resolution_policy="UNRESOLVED_HIGH_AUTHORITY_CONFLICT",writer_visibility="VISIBLE",reason="Conflicting highest-authority structured values; do not invent a resolution."))
            else:
                omitted.update((x.metadata.source_type,x.metadata.source_id,x.metadata.chapter_version_id) for x in low);conflicts.append(ContextConflict(conflict_key=key,higher_authority_sources=sorted(x.metadata.source_id for x in high),lower_authority_sources=sorted(x.metadata.source_id for x in low),resolution_policy="HIGHER_AUTHORITY_WINS",writer_visibility="VISIBLE",reason="Lower-authority conflicting values omitted."))
        kept=[x for x in values if (x.metadata.source_type,x.metadata.source_id,x.metadata.chapter_version_id) not in omitted]
        result=ContextPolicyResult(total_token_budget=self.total_token_budget,conflicts=conflicts,duplicate_count=duplicates);truncated=[]
        for authority in ContextAuthorityLevel:
            cap=self.total_token_budget*self.ALLOCATION[authority]//100;used=0;target=getattr(result,authority.value.lower())
            for item in sorted((x for x in kept if x.metadata.authority_level==authority),key=self._sort_key):
                cost=self.estimate(item)
                if used+cost>cap:truncated.append(item.metadata.source_id);continue
                used+=cost;target.append(item)
            result.budget_usage[authority.value]=used
            if authority is ContextAuthorityLevel.AUTHORITATIVE and any(x.metadata.authority_level==authority and x.metadata.source_id in truncated for x in kept):result.authoritative_context_truncated=True
        result.truncated_sources=truncated;return result
    def _sort_key(self,item):
        m=item.metadata;canonical=json.dumps(item.value,ensure_ascii=False,sort_keys=True,separators=(",",":"));return (self.AUTHORITY_ORDER[m.authority_level],self.SOURCE_ORDER[m.source_type],m.chapter_version_id or "",m.source_id,canonical)
