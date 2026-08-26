from __future__ import annotations
import re

def deterministic_review(draft:str, context:dict)->list[dict]:
    issues=[]
    for c in context.get("characters",[]):
        name=c.get("name","")
        if c.get("status")=="DEAD" and name and name in draft and not any(x in draft for x in ("回忆","尸体","遗像","梦见")):
            issues.append({"code":"DEAD_CHARACTER","severity":"ERROR","message":f"死亡角色{name}无解释出场"})
        if c.get("status")=="MISSING" and name and name in draft and not any(x in draft for x in ("寻找","失踪","下落","线索","回忆")):
            issues.append({"code":"MISSING_CHARACTER","severity":"WARNING","message":f"失踪人物{name}直接出场，缺少回归或追踪说明"})
        age=c.get("age")
        if age and name:
            for found in re.findall(re.escape(name)+r"[^。！？\n]{0,12}?(\d{1,3})岁",draft):
                if int(found)!=int(age): issues.append({"code":"CANON_CONFLICT","severity":"ERROR","message":f"{name}年龄应为{age}，正文为{found}"})
    chapter=context.get("chapter",0)
    for s in context.get("forbidden_secrets",[]):
        if chapter<s.get("earliest_reveal_chapter",10**9) and s.get("content") and s["content"] in draft:
            issues.append({"code":"SECRET_LEAK","severity":"ERROR","message":f"秘密 {s.get('id')} 提前泄露"})
    return issues
