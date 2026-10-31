"""Bounded lower-canvas run preflight (quote) for a local ComfyUI provider.

This is the first half of the lower-canvas run contract: convert the saved
CfGraph + widget params into a validated ComfyUI API prompt and return a quote
that requires explicit confirmation. It does NOT submit /prompt, poll history,
download results or write assets yet; dispatch/status/asset writeback stay a
separate, later contract.
"""
from __future__ import annotations

import hashlib
import base64
import json
import math
import re
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

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
RUNS_COLLECTION = "lower_canvas_runs_v1"
QUOTES_COLLECTION = "lower_canvas_run_quotes_v1"
IMAGE_MAX_BYTES = 16 * 1024 * 1024
VIDEO_MAX_BYTES = 64 * 1024 * 1024
RUN_MAX_OUTPUT_BYTES = 256 * 1024 * 1024
RUN_MAX_IMAGES = 32
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
                               transport_factory=None, include_prompt: bool = False,
                               store_quote: bool = True) -> dict:
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
    }
    quote_digest = _sha(quote_core)
    result = {
        **quote_core,
        "expires_at": expires_at,
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
    if store_quote:
        now = datetime.now(timezone.utc)
        if datetime.fromisoformat(expires_at) <= now:
            raise LowerCanvasRunError("LOWER_CANVAS_RUN_QUOTE_INVALID", status=400)
        with service.store.transaction(nid, scope) as document:
            quotes = document["collections"].setdefault(QUOTES_COLLECTION, {})
            quotes[result["quote_id"]] = {
                "id": result["quote_id"], "kind": kind, "quote_digest": quote_digest,
                "draft_version": version, "provider_id": pid,
                "created_at": now.isoformat(), "expires_at": expires_at, "consumed_at": None,
            }
    if include_prompt:
        # Internal-only fields for the synchronous local dispatch path; never
        # serialized by the preflight HTTP route.
        result["_prompt"] = built["prompt"]
        result["_prompt_digest"] = built["prompt_digest"]
        result["_endpoint"] = fetched.get("endpoint", "")
    return result


def _run_id(quote_digest: str) -> str:
    return "lcr_" + hashlib.sha256(quote_digest.encode("utf-8")).hexdigest()[:24]


def _public_run(row: dict) -> dict:
    return {
        "contract": "studio-lower-canvas-run/1",
        "id": row["id"],
        "kind": row["kind"],
        "status": row["status"],
        "draft_version": row["draft_version"],
        "quote_digest": row["quote_digest"],
        "provider_id": row["provider_id"],
        "node_count": row["node_count"],
        "edge_count": row["edge_count"],
        "output_nodes": list(row["output_nodes"]),
        "prompt_digest": row["prompt_digest"],
        "assets": list(row.get("assets") or []),
        "error": row.get("error"),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "execution": "SYNCHRONOUS_LOCAL_COMFYUI",
    }


def _media_kind(data: bytes) -> tuple[str, str]:
    if data.startswith(b"\x89PNG\r\n\x1a\n"): return "image", "image/png"
    if data.startswith(b"\xff\xd8\xff"): return "image", "image/jpeg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP": return "image", "image/webp"
    if data[4:8] == b"ftyp": return "video", "video/mp4"
    if data.startswith(b"\x1a\x45\xdf\xa3"): return "video", "video/webm"
    raise LowerCanvasRunError("LOWER_CANVAS_RESULT_MEDIA_INVALID", status=502)


def _response_json(response):
    try:
        return response.json()
    except Exception:
        raise LowerCanvasRunError("LOWER_CANVAS_COMFYUI_RESPONSE_INVALID", status=502) from None


def _response_status(response) -> int:
    try:
        return int(response.status_code)
    except (TypeError, ValueError):
        return 0


def _check_response(response, code: str) -> None:
    status = _response_status(response)
    if status < 200 or status >= 300:
        raise LowerCanvasRunError(code, status=502, detail=f"HTTP {status}")


def execute_comfy_prompt(transport, endpoint: str, prompt: dict, *, guard=lambda: None,
                         timeout_seconds: int = 120, poll_interval: float = 1.0,
                         sleep=time.sleep) -> dict:
    """Submit one already validated prompt to a local ComfyUI and fetch its images.

    Synchronous and bounded: one /prompt, bounded /history polling, then a bounded
    /view download per output image. No retries and no silent retry on timeout.
    """
    endpoint = endpoint.rstrip("/")
    if not endpoint:
        raise LowerCanvasRunError("LOWER_CANVAS_PROVIDER_ENDPOINT_MISSING", status=409)
    guard()
    try:
        response = transport.post(endpoint + "/prompt", json={"prompt": prompt}, timeout=30,
                                  dispatch_guard=guard)
    except Exception as exc:
        raise LowerCanvasRunError("LOWER_CANVAS_COMFYUI_UNAVAILABLE", status=503,
                                  detail=type(exc).__name__) from None
    _check_response(response, "LOWER_CANVAS_COMFYUI_PROMPT_REJECTED")
    payload = _response_json(response)
    prompt_id = payload.get("prompt_id") if isinstance(payload, dict) else None
    if not isinstance(prompt_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,240}", prompt_id):
        raise LowerCanvasRunError("LOWER_CANVAS_COMFYUI_PROMPT_ID_INVALID", status=502)
    deadline = time.monotonic() + max(1, int(timeout_seconds))
    outputs = None
    while time.monotonic() < deadline:
        guard()
        try:
            history = transport.get(endpoint + "/history/" + quote(prompt_id, safe=""),
                                    timeout=10, dispatch_guard=guard)
        except Exception as exc:
            raise LowerCanvasRunError("LOWER_CANVAS_COMFYUI_UNAVAILABLE", status=503,
                                      detail=type(exc).__name__) from None
        _check_response(history, "LOWER_CANVAS_COMFYUI_HISTORY_FAILED")
        body = _response_json(history)
        entry = body.get(prompt_id) if isinstance(body, dict) else None
        if not isinstance(entry, dict):
            sleep(poll_interval); continue
        status = entry.get("status") if isinstance(entry.get("status"), dict) else {}
        state = str(status.get("status_str") or "").lower()
        if state in {"error", "failed"}:
            raise LowerCanvasRunError("LOWER_CANVAS_COMFYUI_EXECUTION_FAILED", status=502)
        candidate = entry.get("outputs")
        if isinstance(candidate, dict) and candidate:
            outputs = candidate
            break
        if state in {"success", "completed"}:
            break
        sleep(poll_interval)
    if not isinstance(outputs, dict) or not outputs:
        raise LowerCanvasRunError("LOWER_CANVAS_COMFYUI_TIMEOUT", status=504)
    images: list[dict] = []
    total_bytes = 0
    for node_output in outputs.values():
        if len(images) >= RUN_MAX_IMAGES:
            raise LowerCanvasRunError("LOWER_CANVAS_RESULT_TOO_MANY", status=502)
        rows = node_output.get("images") if isinstance(node_output, dict) else None
        if not isinstance(rows, list):
            continue
        for row in rows:
            if len(images) >= RUN_MAX_IMAGES:
                raise LowerCanvasRunError("LOWER_CANVAS_RESULT_TOO_MANY", status=502)
            if not isinstance(row, dict): continue
            filename, subfolder = row.get("filename"), row.get("subfolder") or ""
            kind = row.get("type") or "output"
            if (not isinstance(filename, str) or not filename or len(filename) > 255
                    or "/" in filename or "\\" in filename or any(ord(c) < 32 for c in filename)
                    or not isinstance(subfolder, str) or len(subfolder) > 255 or ".." in subfolder
                    or kind not in {"output", "temp"}):
                raise LowerCanvasRunError("LOWER_CANVAS_RESULT_REFERENCE_INVALID", status=502)
            guard()
            try:
                view = transport.get(endpoint + "/view", params={"filename": filename, "subfolder": subfolder,
                                      "type": kind}, timeout=30, dispatch_guard=guard)
            except Exception as exc:
                raise LowerCanvasRunError("LOWER_CANVAS_COMFYUI_UNAVAILABLE", status=503,
                                          detail=type(exc).__name__) from None
            _check_response(view, "LOWER_CANVAS_RESULT_DOWNLOAD_FAILED")
            content = getattr(view, "content", b"")
            if not isinstance(content, (bytes, bytearray)) or not content:
                raise LowerCanvasRunError("LOWER_CANVAS_RESULT_BYTES_INVALID", status=502)
            content = bytes(content)
            kind, media_type = _media_kind(content)
            per_file = IMAGE_MAX_BYTES if kind == "image" else VIDEO_MAX_BYTES
            if len(content) > per_file or total_bytes + len(content) > RUN_MAX_OUTPUT_BYTES:
                raise LowerCanvasRunError("LOWER_CANVAS_RESULT_TOO_LARGE", status=502)
            total_bytes += len(content)
            images.append({"filename": filename, "kind": kind, "media_type": media_type,
                           "sha256": hashlib.sha256(content).hexdigest(), "size": len(content),
                           "content": content})
    if not images:
        raise LowerCanvasRunError("LOWER_CANVAS_RESULT_EMPTY", status=502)
    return {"prompt_id": prompt_id, "images": images}


def _default_asset_writer(service, nid: str, scope: dict, actor: str):
    def write(image: dict) -> dict:
        if not hasattr(service, "assets"):
            raise LowerCanvasRunError("LOWER_CANVAS_ASSET_OWNER_MISSING", status=503)
        kind = str(image.get("kind") or "image")
        if kind == "video":
            from ..media_files import inspect_media
            measured = inspect_media(image["content"], "video", include_video_dimensions=True)
        else:
            from ..media_files import inspect_image
            measured = inspect_image(image["content"])
        # Project/branch-scoped generated result. Do not set an owner-only marker:
        # the regular project asset/detail/download routes are actor-agnostic.
        # The writer must run inside the workspace asset scope so the recorded
        # _project_binding matches the project route's active binding.
        scope_context = service._asset_scope(nid, scope) if hasattr(service, "_asset_scope") else nullcontext()
        with scope_context:
            row = service.assets.create(nid, image["filename"], base64.b64encode(image["content"]).decode("ascii"),
                measured["media_type"], kind, branch_id=scope.get("branch_id"))
        return {"id": row["id"], "version": row.get("version", 1), "kind": kind,
                "extension": measured.get("extension"),
                "filename": row.get("filename", image["filename"]),
                "media_type": row.get("media_type", measured["media_type"]),
                "sha256": row.get("sha256", image["sha256"]), "size": row.get("size", image["size"]),
                "width": measured.get("width"), "height": measured.get("height"),
                "duration_seconds": measured.get("duration_seconds")}
    return write


def dispatch_lower_canvas_run(service, nid: str, scope: dict, actor: str, kind: str, *,
                              expected_version: int, quote_id: str, quote_digest: str, provider_id: str | None,
                              transport_factory=None, asset_writer=None,
                              timeout_seconds: int = 120, poll_interval: float = 1.0,
                              guard=lambda: None) -> dict:
    """Synchronously execute one previously quoted local ComfyUI draft.

    One quote digest starts at most one run. The run row is persisted before the
    provider call; assets are written through the existing asset owner only after
    bounded result validation. Any provider/asset failure yields a FAILED run with
    a bounded code, never a fabricated success.
    """
    if not isinstance(quote_digest, str) or not re.fullmatch(r"[a-f0-9]{64}", quote_digest):
        raise LowerCanvasRunError("LOWER_CANVAS_RUN_QUOTE_INVALID", status=400)
    if not isinstance(quote_id, str) or not re.fullmatch(r"lcq_[a-f0-9]{24}", quote_id):
        raise LowerCanvasRunError("LOWER_CANVAS_RUN_QUOTE_INVALID", status=400)
    now_dt = datetime.now(timezone.utc).isoformat()
    with service.store.transaction(nid, scope) as document:
        rows = document["collections"].setdefault(RUNS_COLLECTION, {})
        for row in rows.values():
            if isinstance(row, dict) and row.get("quote_digest") == quote_digest:
                return _public_run(row)
        quotes = document["collections"].setdefault(QUOTES_COLLECTION, {})
        stored_quote = quotes.get(quote_id)
        if (not isinstance(stored_quote, dict) or stored_quote.get("quote_digest") != quote_digest
                or stored_quote.get("kind") != kind or stored_quote.get("consumed_at") is not None):
            raise LowerCanvasRunError("LOWER_CANVAS_RUN_QUOTE_STALE", status=409)
        try:
            expired = datetime.fromisoformat(str(stored_quote["expires_at"])) <= datetime.now(timezone.utc)
        except (KeyError, ValueError):
            raise LowerCanvasRunError("LOWER_CANVAS_RUN_QUOTE_STALE", status=409) from None
        if expired:
            raise LowerCanvasRunError("LOWER_CANVAS_RUN_QUOTE_EXPIRED", status=409)
        stored_quote["consumed_at"] = now_dt
    quote = preflight_lower_canvas_run(service, nid, scope, actor, kind,
        expected_version=expected_version, provider_id=provider_id,
        transport_factory=transport_factory, include_prompt=True, store_quote=False)
    if quote["quote_digest"] != quote_digest:
        raise LowerCanvasRunError("LOWER_CANVAS_RUN_QUOTE_STALE", status=409)
    prompt = quote.pop("_prompt")
    endpoint = str(quote.pop("_endpoint") or "")
    run_id = _run_id(quote_digest)
    now = datetime.now(timezone.utc).isoformat()
    guard()
    with service.store.transaction(nid, scope) as document:
        rows = document["collections"].setdefault(RUNS_COLLECTION, {})
        for row in rows.values():
            if isinstance(row, dict) and row.get("quote_digest") == quote_digest:
                return _public_run(row)
        row = {
            "id": run_id, "kind": kind, "status": "RUNNING", "draft_version": expected_version,
            "quote_digest": quote_digest, "provider_id": quote["provider_id"],
            "node_count": quote["node_count"], "edge_count": quote["edge_count"],
            "output_nodes": list(quote["output_nodes"]), "prompt_digest": quote["prompt_digest"],
            "assets": [], "error": None, "created_at": now, "updated_at": now,
        }
        rows[run_id] = row
        guard()
    def finish(status: str, assets=None, error=None):
        guard()
        with service.store.transaction(nid, scope) as document:
            current = document["collections"].setdefault(RUNS_COLLECTION, {}).get(run_id)
            if not isinstance(current, dict):
                raise LowerCanvasRunError("LOWER_CANVAS_RUN_NOT_FOUND", status=404)
            current.update(status=status, assets=list(assets or []), error=error,
                           updated_at=datetime.now(timezone.utc).isoformat())
            public = _public_run(current)
            guard()
        return public
    try:
        transport = (transport_factory or _transport_for_endpoint)(endpoint)
        result = execute_comfy_prompt(transport, endpoint, prompt, timeout_seconds=timeout_seconds,
                                      poll_interval=poll_interval, guard=guard)
        writer = asset_writer or _default_asset_writer(service, nid, scope, actor)
        assets = [writer(image) for image in result["images"]]
        return finish("COMPLETED", assets=assets)
    except LowerCanvasRunError as exc:
        return finish("FAILED", error={"code": exc.code, "status": exc.status})
    except Exception as exc:
        return finish("FAILED", error={"code": "LOWER_CANVAS_RUN_FAILED", "reason": type(exc).__name__})


def _transport_for_endpoint(endpoint: str):
    from .comfy_node_library import _transport_for
    return _transport_for(endpoint)


def get_lower_canvas_run(service, nid: str, scope: dict, kind: str, run_id: str) -> dict:
    document = service.store.read(nid, scope)
    rows = document.get("collections", {}).get(RUNS_COLLECTION, {})
    row = rows.get(run_id) if isinstance(rows, dict) else None
    if not isinstance(row, dict) or row.get("kind") != kind:
        raise LowerCanvasRunError("LOWER_CANVAS_RUN_NOT_FOUND", status=404)
    return _public_run(row)
