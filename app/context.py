from __future__ import annotations
import json
from pathlib import Path
from .privacy import cloud_safe_context

def _read(path:Path, default):
    try: return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError: return default

def build_context(data_root:Path, novel_id:str, chapter:int, instruction:str, cloud:bool=False)->dict:
    root=data_root/"novels"/novel_id
    meta=_read(root/"novel.json",{}); characters=_read(root/"characters"/"characters.json",[]); locations=_read(root/"locations"/"locations.json",[])
    state=_read(root/"story_state.json",{}); secrets=_read(root/"secrets.json",[]); foreshadowing=_read(root/"foreshadowing.json",[]); summaries=_read(root/"summaries"/"index.json",[])
    relevant_names={str(x) for x in state.get("active_characters",[])}
    selected=[c for c in characters if c.get("id") in relevant_names or c.get("name") in instruction]
    secret_context=[s for s in secrets if chapter < s.get("earliest_reveal_chapter",10**9) or s.get("status")=="ACTIVE"]
    omitted=[]
    if cloud: secret_context,omitted=cloud_safe_context(secret_context)
    return build_context_from_sources({"novel":meta,"characters":characters,"locations":locations,"story_state":state,"secrets":secrets,"foreshadowing":foreshadowing,"summaries":summaries,"style_profile":_read(root/"style"/"profile.json",{})},novel_id,chapter,instruction,cloud)

def build_context_from_sources(sources:dict,novel_id:str,chapter:int,instruction:str,cloud:bool=False)->dict:
    meta=sources.get("novel",{});characters=sources.get("characters",[]);locations=sources.get("locations",[]);state=sources.get("story_state",{});secrets=sources.get("secrets",[]);foreshadowing=sources.get("foreshadowing",[]);summaries=sources.get("summaries",[])
    relevant_names={str(x) for x in state.get("active_characters",[])};selected=[c for c in characters if c.get("id") in relevant_names or c.get("name") in instruction]
    secret_context=[s for s in secrets if chapter<s.get("earliest_reveal_chapter",10**9) or s.get("status")=="ACTIVE"];omitted=[]
    if cloud:secret_context,omitted=cloud_safe_context(secret_context)
    return {"novel":meta.get("title",novel_id),"novel_id":novel_id,"volume":state.get("volume",1),"chapter":chapter,"chapter_goal":instruction,"pov":state.get("pov"),"story_time":state.get("story_time"),"characters":selected,"relationships":state.get("relationships",[]),"locations":locations,"current_story_state":state,"active_foreshadowing":[f for f in foreshadowing if f.get("status")=="OPEN"],"forbidden_secrets":secret_context,"privacy_omissions":omitted,"recent_chapter_summary":summaries[-3:],"long_term_summary":meta.get("long_term_summary",""),"style_profile":sources.get("style_profile",{}),"must_include":[],"must_not_include":["未经批准改变 Canon","提前揭露受保护秘密"]}
