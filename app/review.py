from __future__ import annotations
import re
from datetime import datetime


def world_rule_violations(project_id: str, haystack: str, rules: list[dict]) -> list[dict]:
    """Explicit forbidden-term checks shared by generation and manual scans."""
    serialized = (haystack or "").casefold()
    findings = []
    for rule in rules:
        payload = rule.get("approved_payload") or rule.get("payload") or rule
        terms = payload.get("forbidden_terms") or payload.get("forbidden") or []
        if isinstance(terms, str): terms = [terms]
        hits = [str(term) for term in terms if str(term) and str(term).casefold() in serialized]
        if hits:
            findings.append({"id": f"WORLD_RULE:{rule.get('id', 'unknown')}", "project_id": project_id,
                "finding_type": "WORLD_RULE_VIOLATION", "severity": "HIGH",
                "description": f"内容触发世界规则：{payload.get('statement', '未命名规则')}",
                "rule_id": rule.get("id"), "subject_type": "WORLD_RULE", "subject_id": rule.get("id"), "evidence_ids": hits})
    return findings


def _instant(value):
    if not isinstance(value, str): return None
    try: return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError: return None

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
    for finding in world_rule_violations(context.get("novel_id", ""), draft, context.get("world_rules", [])):
        issues.append({**finding, "code": "WORLD_RULE_VIOLATION", "message": finding["description"]})
    for event in context.get("timeline", []):
        start, end = _instant(event.get("start_time") or event.get("time")), _instant(event.get("end_time"))
        if start is None or end is None or (start.tzinfo is None) != (end.tzinfo is None): continue
        if start > end:
            issues.append({"code": "TIMELINE_ORDER_VIOLATION", "severity": "ERROR", "subject_id": event.get("id"),
                           "message": f"时间事件{event.get('title') or event.get('id')}结束早于开始，生成上下文存在时间冲突。"})
    return issues
