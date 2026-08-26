from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from ..agent_catalog import AGENTS


ROLE_SECTIONS = {
    "planner": ("outline","volumes","scenes","story_routes","characters","locations","timeline","foreshadowing","relationships"),
    "writer": ("outline","volumes","scenes","story_routes","characters","locations","timeline","foreshadowing","relationships","writing_context"),
    "editor": ("outline","scenes","characters","writing_context"),
    "continuity": ("characters","locations","timeline","foreshadowing","relationships","writing_context"),
    "director": ("outline","volumes","scenes","characters","locations","writing_context"),
    "artist": ("characters","locations","scenes"),
}


class AgentContextService:
    def __init__(self, novels, chapters, context):self.novels,self.chapters,self.context=novels,chapters,context

    def build(self,agent_id,novel_id,chapter_number,instruction="",cloud=False):
        agent=next((item for item in AGENTS if item["id"]==agent_id),None)
        if agent is None:raise KeyError(agent_id)
        sections=ROLE_SECTIONS[agent_id];payload={}
        for section in sections:
            if section=="writing_context":payload[section]=self.context.build(novel_id,chapter_number,instruction,cloud,operation=agent_id)
            elif section=="outline":payload[section]=self.novels.get_outline(novel_id)
            else:payload[section]=self.novels.get_data_set(novel_id,section)
        chapter=self.chapters.get(f"{novel_id}:{chapter_number}")
        source_manifest=[{"section":key,"item_count":len(value) if isinstance(value,list) else (1 if value else 0)} for key,value in payload.items()]
        canonical=json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(",",":"),default=str)
        return {"context_contract_version":"1.0","agent_id":agent_id,"agent_name":agent["name"],"novel_id":novel_id,"chapter_id":chapter["id"],"chapter_version":chapter["version"],"target":"cloud" if cloud else "local","instruction":instruction,"sections":payload,"source_manifest":source_manifest,"context_hash":hashlib.sha256(canonical.encode()).hexdigest(),"created_at":datetime.now(timezone.utc).isoformat()}
