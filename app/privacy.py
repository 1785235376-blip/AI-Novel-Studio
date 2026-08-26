from __future__ import annotations
import hashlib, json

def cloud_safe_context(entries:list[dict])->tuple[list[dict],list[str]]:
    safe=[]; omitted=[]
    for item in entries:
        level=item.get("privacy_level","CLOUD_ALLOWED")
        if level=="LOCAL_ONLY": omitted.append(str(item.get("id",item.get("name","unknown")))); continue
        copy=dict(item)
        if level=="REDACT_BEFORE_CLOUD":
            copy={"id":copy.get("id"),"type":copy.get("type","secret"),"constraint":"存在未到揭露时机的受保护事实；禁止猜测或揭露原文","privacy_level":level}
        safe.append(copy)
    return safe, omitted

def prompt_hash(value:object)->str:
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True).encode()).hexdigest()

