"""Bounded lower-canvas run preflight (quote) for a local ComfyUI provider.

This is the first half of the lower-canvas run contract: convert the saved
CfGraph + widget params into a validated ComfyUI API prompt and return a quote
that requires explicit confirmation. It does NOT submit /prompt, poll history,
download results or write assets yet; dispatch/status/asset writeback stay a
separate, later contract.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import datetime, timedelta, timezone

from .comfy_node_library import (
    ComfyNodeLibraryError,
    _provider_configs,
    _select_provider,
    fetch_comfyui_object_info,
)

CONTRACT = "studio-lower-canvas-run-quote/1"
PROMPT_CONTRACT = "studio-lower-canvas-prompt/1"
MAX_NODES = 400
MAX_EDGES = 800
MAX_PROMPT_BYTES = 1_000_000
QUOTE_TTL_SECONDS = 300
PORT_WIDGET_KINDS = {"INT", "FLOAT", "STRING", "BOOLEAN"}
_NODE_ID = re.compile(r"^[A-Za-z0-9_.:-]{1,80}$")
_PARAM_NAME = re.compile(r"^[A-Za-z0-9_.-]{1,80}$")


class LowerCanvasRunError(ValueError):
    def __init__(self, code: str, *, status: int = 409, detail: str = ""):
        super().__init__(code)
        self.code = code
        self.status = int(status)
        self.detail = str(detail)[:240]


def _canonical(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha(value) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _widget_spec(spec) -> tuple[str, dict]:
    kind = spec[0] if isinstance(spec, (list, tuple)) and spec else None
    options = spec[1] if isinstance(spec, (list, tuple)) and len(spec) > 1 and isinstance(spec[1], dict) else {}
    if isinstance(kind, (list, tuple)):
        return "COMBO", options
    if isinstance(kind, str) and kind in PORT_WIDGET_KINDS:
        return kind, options
    return "", options


def _port_type(spec) -> str:
    if not isinstance(spec, (list, tuple)) or not spec:
        return ""
    kind = spec[0]
    return kind if isinstance(kind, str) and kind and kind not in PORT_WIDGET_KINDS else ""


def _port_count(info: dict) -> int:
    section = info.get("input") if isinstance(info.get("input"), dict) else {}
    count = 0
    for group in ("required", "optional"):
        rows = section.get(group)
        if isinstance(rows, dict):
            count += sum(1 for spec in rows.values() if _port_type(spec))
    return count


def _default_widget(kind: str, options: dict):
    if "default" in options:
        return options["default"]
    if kind == "BOOLEAN":
        return False
    if kind in {"INT", "FLOAT"}:
        return 0
    return ""


def _validate_param(kind: str, options: dict, value):
    if kind == "INT":
        return type(value) is int
    if kind == "FLOAT":
        return type(value) in {int, float} and math.isfinite(value)
    if kind == "BOOLEAN":
        return type(value) is bool
    if kind == "COMBO":
        choices = options.get("choices")
        # ComfyUI combo specs carry choices in spec[0], handled by caller.
        return isinstance(value, str) and (not isinstance(choices, list) or value in choices)
    if kind == "STRING":
        return isinstance(value, str) and len(value) <= 4096
    return False


def build_comfy_prompt(graph: dict, object_info: dict) -> dict:
    if not isinstance(graph, dict) or not isinstance(object_info, dict):
        raise LowerCanvasRunError("LOWER_CANVAS_GRAPH_INVALID", status=400)
    nodes = graph.get("nodes")
    edges = graph.get("edges")
    if not isinstance(nodes, list) or not isinstance(edges, list):
        raise LowerCanvasRunError("LOWER_CANVAS_GRAPH_INVALID", status=400)
    if not nodes:
        raise LowerCanvasRunError("LOWER_CANVAS_GRAPH_EMPTY", status=400)
    if len(nodes) > MAX_NODES or len(edges) > MAX_EDGES:
        raise LowerCanvasRunError("LOWER_CANVAS_GRAPH_TOO_LARGE", status=400)
    by_id: dict[str, dict] = {}
    for node in nodes:
        if not isinstance(node, dict) or not isinstance(node.get("id"), str) or not _NODE_ID.fullmatch(node["id"]):
            raise LowerCanvasRunError("LOWER_CANVAS_NODE_ID_INVALID", status=400)
        if node["id"] in by_id:
            raise LowerCanvasRunError("LOWER_CANVAS_NODE_ID_DUPLICATE", status=400)
        if not isinstance(node.get("t"), str) or not node["t"]:
            raise LowerCanvasRunError("LOWER_CANVAS_NODE_CLASS_INVALID", status=400)
        by_id[node["id"]] = node
    edge_targets: dict[tuple[str, int], tuple[str, int]] = {}
    for edge in edges:
        if not isinstance(edge, dict):
            raise LowerCanvasRunError("LOWER_CANVAS_EDGE_INVALID", status=400)
        a, b = edge.get("a"), edge.get("b")
        if a not in by_id or b not in by_id or a == b:
            raise LowerCanvasRunError("LOWER_CANVAS_EDGE_ENDPOINT_INVALID", status=400)
        try: a_slot, b_slot = int(edge.get("as", 0)), int(edge.get("bs", 0))
        except (TypeError, ValueError):
            raise LowerCanvasRunError("LOWER_CANVAS_EDGE_INVALID", status=400) from None
        if a_slot < 0 or b_slot < 0:
            raise LowerCanvasRunError("LOWER_CANVAS_EDGE_INVALID", status=400)
        source_info = object_info.get(by_id[a].get("t"))
        target_info = object_info.get(by_id[b].get("t"))
        if isinstance(source_info, dict):
            outputs = source_info.get("output") if isinstance(source_info.get("output"), list) else []
            if a_slot >= len(outputs):
                raise LowerCanvasRunError("LOWER_CANVAS_LINK_SLOT_INVALID", status=400, detail=f"{a}:{a_slot}")
        if isinstance(target_info, dict) and b_slot >= _port_count(target_info):
            raise LowerCanvasRunError("LOWER_CANVAS_LINK_SLOT_INVALID", status=400, detail=f"{b}:{b_slot}")
        if (b, b_slot) in edge_targets:
            raise LowerCanvasRunError("LOWER_CANVAS_INPUT_MULTI_LINKED", status=400)
        edge_targets[(b, b_slot)] = (a, a_slot)
    # Cycle rejection on the bounded node graph.
    indegree = {node_id: 0 for node_id in by_id}
    outgoing: dict[str, list[str]] = {node_id: [] for node_id in by_id}
    for (b, _), (a, _) in edge_targets.items():
        outgoing[a].append(b); indegree[b] += 1
    queue = [node_id for node_id, degree in indegree.items() if degree == 0]
    visited = 0
    while queue:
        node_id = queue.pop(); visited += 1
        for target in outgoing[node_id]:
            indegree[target] -= 1
            if indegree[target] == 0: queue.append(target)
    if visited != len(by_id):
        raise LowerCanvasRunError("LOWER_CANVAS_GRAPH_HAS_CYCLE", status=400)

    prompt: dict[str, dict] = {}
    output_nodes: list[str] = []
    for node_id, node in by_id.items():
        node_class = node["t"]
        info = object_info.get(node_class)
        if not isinstance(info, dict):
            raise LowerCanvasRunError("LOWER_CANVAS_NODE_CLASS_UNKNOWN", status=400, detail=node_class)
        input_section = info.get("input") if isinstance(info.get("input"), dict) else {}
        required = input_section.get("required") if isinstance(input_section.get("required"), dict) else {}
        optional = input_section.get("optional") if isinstance(input_section.get("optional"), dict) else {}
        params = node.get("params") if isinstance(node.get("params"), dict) else {}
        for key in params:
            if not isinstance(key, str) or not _PARAM_NAME.fullmatch(key):
                raise LowerCanvasRunError("LOWER_CANVAS_PARAM_NAME_INVALID", status=400)
        widgets = {name: spec[0] for name, spec in required.items() if isinstance(spec, (list, tuple)) and spec and not _port_type(spec)}
        widgets.update({name: spec[0] for name, spec in optional.items() if isinstance(spec, (list, tuple)) and spec and not _port_type(spec)})
        unknown = set(params) - set(widgets)
        if unknown:
            raise LowerCanvasRunError("LOWER_CANVAS_PARAM_UNKNOWN", status=400, detail=",".join(sorted(unknown))[:200])
        inputs: dict = {}
        port_index = 0
        for group_name, rows in (("required", required), ("optional", optional)):
            if not isinstance(rows, dict):
                continue
            for name, spec in rows.items():
                port_type = _port_type(spec)
                if port_type:
                    linked = edge_targets.get((node_id, port_index))
                    port_index += 1
                    if linked is not None:
                        source_id, source_slot = linked
                        source = by_id[source_id]
                        source_info = object_info.get(source["t"]) or {}
                        source_outputs = source_info.get("output") if isinstance(source_info.get("output"), list) else []
                        if source_slot >= len(source_outputs):
                            raise LowerCanvasRunError("LOWER_CANVAS_LINK_SLOT_INVALID", status=400, detail=f"{source_id}:{source_slot}")
                        source_type = source_outputs[source_slot]
                        if not (source_type == "*" or port_type == "*" or set(str(source_type).split(",")) & set(port_type.split(","))):
                            raise LowerCanvasRunError("LOWER_CANVAS_LINK_TYPE_MISMATCH", status=400)
                        inputs[name] = [source_id, source_slot]
                    elif group_name == "required":
                        raise LowerCanvasRunError("LOWER_CANVAS_REQUIRED_INPUT_UNLINKED", status=400, detail=f"{node_class}.{name}")
                    continue
                kind, options = _widget_spec(spec)
                if not kind:
                    raise LowerCanvasRunError("LOWER_CANVAS_INPUT_SPEC_INVALID", status=400, detail=f"{node_class}.{name}")
                if name in params:
                    value = params[name]
                    if kind == "COMBO":
                        choices = spec[0] if isinstance(spec, (list, tuple)) and isinstance(spec[0], (list, tuple)) else None
                        if not isinstance(value, str) or (choices is not None and value not in choices):
                            raise LowerCanvasRunError("LOWER_CANVAS_PARAM_INVALID", status=400, detail=f"{node_class}.{name}")
                    elif not _validate_param(kind, options, value):
                        raise LowerCanvasRunError("LOWER_CANVAS_PARAM_INVALID", status=400, detail=f"{node_class}.{name}")
                    inputs[name] = value
                elif group_name == "required":
                    if kind == "COMBO":
                        choices = spec[0] if isinstance(spec, (list, tuple)) and isinstance(spec[0], (list, tuple)) else []
                        inputs[name] = choices[0] if choices else ""
                    else:
                        inputs[name] = _default_widget(kind, options)
        prompt[node_id] = {"class_type": node_class, "inputs": inputs}
        if info.get("output_node") is True:
            output_nodes.append(node_id)
    if not output_nodes:
        raise LowerCanvasRunError("LOWER_CANVAS_OUTPUT_NODE_REQUIRED", status=400)
    if len(_canonical(prompt).encode("utf-8")) > MAX_PROMPT_BYTES:
        raise LowerCanvasRunError("LOWER_CANVAS_PROMPT_TOO_LARGE", status=400)
    return {
        "contract": PROMPT_CONTRACT,
        "prompt": prompt,
        "node_count": len(prompt),
        "edge_count": len(edge_targets),
        "output_nodes": output_nodes,
        "prompt_digest": _sha(prompt),
    }


def _load_draft(service, nid: str, scope: dict, kind: str) -> dict:
    from .lower_canvas_api import COLLECTION
    document = service.store.read(nid, scope)
    row = document.get("collections", {}).get(COLLECTION, {}).get(kind)
    if not isinstance(row, dict):
        raise LowerCanvasRunError("LOWER_CANVAS_DRAFT_NOT_FOUND", status=404)
    return row


def preflight_lower_canvas_run(service, nid: str, scope: dict, actor: str, kind: str,
                               *, expected_version: int, provider_id: str | None,
                               transport_factory=None) -> dict:
    from .comfy_node_library import ComfyNodeLibraryError
    row = _load_draft(service, nid, scope, kind)
    version = int(row.get("version") or 0)
    if version != expected_version:
        raise LowerCanvasRunError("LOWER_CANVAS_VERSION_CONFLICT", status=409, detail=str(version))
    configs = _provider_configs()
    pid, config, available = _select_provider(provider_id, configs)
    if config.get("local") is not True:
        raise LowerCanvasRunError("LOWER_CANVAS_RUN_LOCAL_PROVIDER_REQUIRED", status=409)
    try:
        fetched = fetch_comfyui_object_info(provider_id=pid, transport_factory=transport_factory)
    except ComfyNodeLibraryError as exc:
        raise LowerCanvasRunError(exc.code, status=503 if exc.status >= 500 else 409, detail=exc.detail) from None
    built = build_comfy_prompt(row.get("graph") or {}, fetched["payload"])
    expires_at = (datetime.now(timezone.utc) + timedelta(seconds=QUOTE_TTL_SECONDS)).isoformat()
    quote_core = {
        "contract": CONTRACT,
        "kind": kind,
        "draft_version": version,
        "provider_id": pid,
        "prompt_digest": built["prompt_digest"],
        "node_count": built["node_count"],
        "edge_count": built["edge_count"],
        "output_nodes": built["output_nodes"],
        "expires_at": expires_at,
    }
    quote_digest = _sha(quote_core)
    return {
        **quote_core,
        "quote_id": "lcq_" + quote_digest[:24],
        "quote_digest": quote_digest,
        "provider_local": True,
        "available_providers": available,
        "price": {"currency": "USD", "amount_micros": 0, "reason": "LOCAL_COMFYUI_NO_BILLING"},
        "confirmation_required": True,
        "execution": "NOT_DISPATCHED",
        "dispatch_contract": "NOT_IMPLEMENTED",
        "limits": {"nodes": MAX_NODES, "edges": MAX_EDGES, "prompt_bytes": MAX_PROMPT_BYTES,
                   "quote_ttl_seconds": QUOTE_TTL_SECONDS},
    }
