"""Closed, explicit failed-local retry admission; no execution or alternate owner."""
from .graph_models import MAX_RUNS
from ..experimental.common import check_version

LOCAL_RETRY_IDS = frozenset({"text_input", "text_reference", "draft_prepare",
    "manual_transform", "director_note", "human_review"})
CONTRACT = "creative-graph-failed-local-retry/1"


def validate_source(executor, nid, scope, actor, source, graph, body, guard, state):
    check_version(source, body.expected_version)
    if source["status"] != "FAILED":
        raise ValueError("CREATIVE_GRAPH_RETRY_FAILED_REQUIRED")
    if (graph["definition"]["schema_version"] != 1 or source.get("graph_schema_version", 1) != 1
            or not graph["definition"]["nodes"]
            or any(node["definition_id"] not in LOCAL_RETRY_IDS for node in graph["definition"]["nodes"])
            or any(source.get(key) for key in ("model_execution_contract", "media_execution_contract",
                "model_execution", "media_executions", "model_preview", "media_previews", "model_called", "external_ai_calls", "external_calls"))
            or source.get("execution_mode") != "ORIGINAL_WORKFLOW_LOCAL_RULES"
            or source.get("input") != {}):
        raise ValueError("CREATIVE_GRAPH_RETRY_SCHEMA1_LOCAL_REQUIRED")
    attempt = source.get("attempt")
    if type(attempt) is not int or not 1 <= attempt < MAX_RUNS:
        raise ValueError("CREATIVE_GRAPH_RETRY_ATTEMPT_INVALID")
    executor._current(nid, scope, actor, source, guard, state)
    if any(node["status"] in {"WORKING", "QUEUED"} for node in source["node_states"].values()):
        raise ValueError("CREATIVE_GRAPH_RETRY_UNSETTLED_NODE")
    guard()
