from __future__ import annotations

AGENT_CATALOG_VERSION = "1.0"

AGENTS = (
    {"id":"planner","name":"策划 Agent","description":"负责主题、大纲、卷、场景和剧情路线规划。","prompt_role":"plot_planner","tools":["outline.read","outline.propose","volumes.read","scenes.read","story_routes.read"],"output_schema":"story_plan_proposal","requires_approval":True},
    {"id":"writer","name":"作家 Agent","description":"依据已批准上下文生成正文、续写和不同候选草稿。","prompt_role":"writer","tools":["context.read","chapter.read","draft.generate"],"output_schema":"chapter_draft","requires_approval":True},
    {"id":"editor","name":"编辑 Agent","description":"负责润色、改写、节奏与表达建议，不直接覆盖正文。","prompt_role":"editor","tools":["chapter.read","draft.rewrite","diff.propose"],"output_schema":"editor_revision_proposal","requires_approval":True},
    {"id":"continuity","name":"连贯性 Agent","description":"检查人物、时间、关系、知识和世界规则冲突。","prompt_role":"continuity_reviewer","tools":["canon.read","timeline.read","characters.read","continuity.check"],"output_schema":"continuity_findings","requires_approval":False},
    {"id":"director","name":"导演 Agent","description":"为后续影视化组织场景、动作、镜头意图和节奏。","prompt_role":"director","tools":["chapter.read","scenes.read","shot_plan.propose"],"output_schema":"direction_proposal","requires_approval":True},
    {"id":"artist","name":"美术 Agent","description":"规划人物、地点、道具和分镜的视觉需求，不直接调用未启用的图片运行时。","prompt_role":"world_keeper","tools":["characters.read","locations.read","visual_brief.propose"],"output_schema":"visual_brief","requires_approval":True},
)


def public_agent_catalog() -> dict:
    return {"catalog_version":AGENT_CATALOG_VERSION,"agents":[dict(item) for item in AGENTS]}
