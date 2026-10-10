from __future__ import annotations
import json
from pathlib import Path
from .config import settings
class AgentRegistry:
    aliases={"planner":"plot_planner","reviewer":"continuity_reviewer","canon_checker":"continuity_reviewer","character_checker":"character_keeper"}
    def __init__(self): self.root=settings.prompt_path if settings.prompt_path.is_absolute() else settings.root/settings.prompt_path
    def prompt(self,name:str)->str:
        actual=self.aliases.get(name,name); path=self.root/actual/"system.md"
        if not path.exists(): raise KeyError(name)
        return path.read_text(encoding="utf-8")
class AgentRunner:
    def __init__(self,registry:AgentRegistry): self.registry=registry
    def build_prompt(self,agent:str,context:dict,task:str,source:str="")->str:
        adapted=dict(context)
        if agent!="writer":
            # Legacy raw memory/policy contracts remain isolated. Original
            # source-bound author operations receive a bounded supporting view
            # so editors/reviewers can actually preserve approved continuity.
            if adapted.get("novel_id") and "chapter" in adapted:
                memory=adapted.get("lore_memory",{})
                if memory:
                    adapted["continuity_memory"]={"accepted_character_memories":memory.get("short_memory",[])+memory.get("medium_memory",[]),
                        "long_term_snapshots":memory.get("long_memory",[]),"evidence_summary":memory.get("evidence_summary",[]),
                        "authority":"SUPPORTING_DOES_NOT_OVERRIDE_CANON"}
                if adapted.get("narrative_context"):
                    adapted["narrative_constraints"]=adapted["narrative_context"]
            adapted.pop("lore_memory",None);adapted.pop("narrative_context",None);adapted.pop("context_policy",None)
        return self.registry.prompt(agent)+"\n\nTASK:\n"+task+"\n\nCONTEXT:\n"+json.dumps(adapted,ensure_ascii=False)+("\n\nSOURCE:\n"+source if source else "")
registry=AgentRegistry(); agent_runner=AgentRunner(registry)
