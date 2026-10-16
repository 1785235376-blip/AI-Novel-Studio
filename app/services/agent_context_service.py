from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from ..agent_catalog import resolve_agent
from ..privacy import cloud_safe_context


ROLE_SECTIONS = {
    "planner": ("outline","volumes","scenes","story_routes","characters","locations","timeline","foreshadowing","relationships","writing_context"),
    "writer": ("outline","volumes","scenes","story_routes","characters","locations","timeline","foreshadowing","relationships","writing_context"),
    "editor": ("outline","scenes","characters","writing_context"),
    "continuity": ("characters","locations","timeline","foreshadowing","relationships","writing_context"),
    "director": ("outline","volumes","scenes","characters","locations","writing_context"),
    "artist": ("characters","locations","scenes"),
    "reviewer": ("outline","characters","locations","timeline","relationships","writing_context"),
    "verifier": ("outline","characters","locations","canon","timeline","relationships","writing_context"),
}


class AgentContextService:
    def __init__(self, novels, chapters, context):self.novels,self.chapters,self.context=novels,chapters,context

    def build(self,agent_id,novel_id,chapter_number,instruction="",cloud=False,chapter_id=None):
        agent=resolve_agent(agent_id)
        if chapter_id is not None and (not isinstance(chapter_id, str) or ":" not in chapter_id or chapter_id.rsplit(":", 1)[0] != novel_id):
            raise FileNotFoundError(chapter_id)
        chapter=self.chapters.get(chapter_id if chapter_id is not None else f"{novel_id}:{chapter_number}")
        if chapter.get("novel_id", novel_id) != novel_id:
            raise FileNotFoundError(chapter_id)
        chapter_number=chapter.get("number", chapter_number)
        sections=ROLE_SECTIONS[agent_id];payload={}
        for section in sections:
            if section=="writing_context":payload[section]=self.context.build(novel_id,chapter_number,instruction,cloud,operation=agent_id,chapter_id=chapter["id"]) if self.context is not None else {}
            elif section=="outline":payload[section]=self.novels.get_outline(novel_id)
            else:payload[section]=self.novels.get_data_set(novel_id,section)
        if cloud:
            # Domain sections bypass the writing-context builder. Filter each
            # source before constructing prompts; unknown provenance stays local.
            for section, value in list(payload.items()):
                if section == "writing_context":
                    continue
                if isinstance(value, list):
                    payload[section] = cloud_safe_context(value)[0]
                elif isinstance(value, dict):
                    safe = cloud_safe_context([value])[0]
                    payload[section] = safe[0] if safe else {}
                else:
                    payload[section] = {}
        source_manifest=[{"section":key,"item_count":len(value) if isinstance(value,list) else (1 if value else 0)} for key,value in payload.items()]
        for source in source_manifest:
            if source["section"] == "writing_context" and ":~" in chapter["id"]:
                source.update(chapter_id=chapter["id"], chapter_version=chapter["version"])
        # Bind actual chapter prose as well as domain sources. Reviewer/Verifier
        # previously received no manuscript, so there was nothing to inspect.
        source = str(chapter.get("content") or "")
        if cloud and source:
            from ..source_privacy import effective_source_privacy
            if effective_source_privacy({**chapter,"novel_id":novel_id}, chapter.get("branch_id")) != "CLOUD_ALLOWED":
                source = ""
        payload["chapter_source"] = {"chapter_id":chapter["id"],"chapter_version":chapter["version"],"content":source}
        # Visual briefs retain their existing bounded three-section contract.
        if agent_id == "artist": payload.pop("chapter_source")
        else: source_manifest.append({"section":"chapter_source","item_count":1,"chapter_id":chapter["id"],"chapter_version":chapter["version"],"source_available":bool(source)})
        canonical=json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(",",":"),default=str)
        return {"context_contract_version":"1.0","agent_id":agent_id,"agent_name":agent["name"],"novel_id":novel_id,"chapter_id":chapter["id"],"chapter_version":chapter["version"],"target":"cloud" if cloud else "local","instruction":instruction,"sections":payload,"source_manifest":source_manifest,"context_hash":hashlib.sha256(canonical.encode()).hexdigest(),"created_at":datetime.now(timezone.utc).isoformat()}
