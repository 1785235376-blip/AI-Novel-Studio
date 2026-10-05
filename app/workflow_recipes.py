"""Bounded, local-only recipe transformations. Outputs are review artifacts.

No result writes chapter text, Canon, assets or queues a model/media request.
"""
from __future__ import annotations

import hashlib

RECIPES = (
    {"id": "import_knowledge", "name": "导入资料 → 知识候选 → 审核", "type": "knowledge_candidates", "result": "REVIEWED_KNOWLEDGE_CANDIDATES"},
    {"id": "planning_draft", "name": "创作规划 → 草稿 → 审阅", "type": "draft_prepare", "result": "REVIEWED_DRAFT"},
    {"id": "screenplay_assets", "name": "剧本 → 镜头分镜 → 资源任务提案", "type": "shot_proposals", "result": "REVIEWED_ASSET_TASK_PROPOSALS"},
)


def recipe_definition(recipe_id: str, novel_id: str) -> dict:
    recipe = next((item for item in RECIPES if item["id"] == recipe_id), None)
    if recipe is None:
        raise ValueError("unknown workflow recipe")
    return {"novel_id": novel_id, "title": recipe["name"],
            "description": "本地规则转换；结果保留为审核材料，不写入正式正文、Canon 或启动外部服务。",
            "nodes": [
                {"id": "prepare", "type": recipe["type"], "name": "整理输入材料"},
                {"id": "review", "type": "manual_approval", "name": "审核候选结果"},
                {"id": "artifact", "type": "review_artifact", "name": "保存已审核材料", "config": {"result_type": recipe["result"]}},
            ], "edges": [{"source": "prepare", "target": "review"}, {"source": "review", "target": "artifact"}]}


def execute_local_recipe_node(kind: str, inputs: dict, states: dict, config: dict) -> dict:
    if kind == "review_artifact":
        return {"artifact_type": config.get("result_type", "REVIEWED_PROPOSAL"),
                "content": [state["output"] for state in states.values() if state.get("output") and state["output"].get("provenance")],
                "applied": False, "external_calls": 0}
    text = inputs.get("source_text")
    if not isinstance(text, str) or not text.strip() or len(text) > 20000:
        raise ValueError("source_text must contain 1-20000 characters")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) > 100:
        raise ValueError("source_text exceeds the 100 item recipe limit")
    base = {"provenance": {"method": "LOCAL_RULES", "source_sha256": hashlib.sha256(text.encode()).hexdigest()},
            "model_called": False, "applied": False}
    if kind == "knowledge_candidates":
        return {**base, "candidates": [{"source_line": index+1, "text": line, "status": "PENDING", "privacy_level": "LOCAL_ONLY"} for index, line in enumerate(lines)]}
    if kind == "draft_prepare":
        return {**base, "plan": [{"sequence": index+1, "beat": line} for index, line in enumerate(lines)],
                "draft": text, "draft_origin": "USER_SUPPLIED", "status": "DRAFT_REQUIRES_REVIEW"}
    if kind == "shot_proposals":
        return {**base, "shots": [{"sequence": index+1, "description": line, "asset_task": {"status": "PROPOSAL", "submitted": False}} for index, line in enumerate(lines)]}
    raise ValueError("unsupported local recipe node")
