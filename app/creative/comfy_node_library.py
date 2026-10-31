"""Read-only ComfyUI node-library import for the Studio canvas.

The canvas node library is a closed Studio catalog. This module adds a separate,
read-only metadata bridge over a configured ComfyUI provider's ``/object_info``:
it never adds executable Studio definitions, never submits a workflow and never
executes a node. A future execution adapter must explicitly map a ComfyUI node
class to a bounded Studio execution step first.

All parsing is defensive: bounded node/input/output counts, bounded strings and
choices, deterministic ordering, no endpoint credentials or query strings in the
response, and no unbounded provider payloads.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from urllib.parse import urlsplit

from ..net_safety import validate_provider_endpoint

CONTRACT = "studio-comfyui-node-library/1"
COMPATIBILITY_CONTRACT = "studio-comfyui-node-compatibility/1"
SOURCE = "COMFYUI_OBJECT_INFO"

MAX_NODES = 2000
MAX_INPUTS_PER_NODE = 128
MAX_OUTPUTS_PER_NODE = 32
MAX_CHOICES = 128
MAX_TEXT = 240
MAX_NAME = 160
MAX_RESPONSE_BYTES = 4 * 1024 * 1024
FETCH_TIMEOUT_SECONDS = 10

_CONTROL = re.compile(r"[\x00-\x1f\x7f]+")
_DEFINITION_SLUG = re.compile(r"[^A-Za-z0-9_.-]+")
_PRIMITIVE_TYPES = {"INT", "FLOAT", "STRING", "BOOLEAN"}
# ComfyUI types that have a direct, additive mapping into Studio's typed ports.
_STUDIO_TYPE_HINTS = {
    "IMAGE": "IMAGE",
    "VIDEO": "VIDEO",
    "AUDIO": "AUDIO",
    "MASK": "MASK",
    "LATENT": "LATENT",
    "MODEL": "MODEL",
    "CLIP": "CLIP",
    "VAE": "VAE",
    "CONDITIONING": "CONDITIONING",
    "CONTROL_NET": "CONTROL_NET",
    "INT": "INT",
    "FLOAT": "FLOAT",
    "STRING": "TEXT",
    "BOOLEAN": "BOOLEAN",
    "COMBO": "CHOICE",
}


class ComfyNodeLibraryError(ValueError):
    """Bounded, explicit failure for the node-library bridge."""

    def __init__(self, code: str, *, status: int = 409, detail: str = ""):
        super().__init__(code)
        self.code = code
        self.status = int(status)
        self.detail = _text(detail)


def _text(value: object, limit: int = MAX_TEXT) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        value = str(value)
    return _CONTROL.sub(" ", value).strip()[:limit]


def _name(value: object) -> str:
    text = _text(value, MAX_NAME)
    return text if text else ""


def _type(value: object) -> str:
    if isinstance(value, str):
        return _text(value, 80) or "UNKNOWN"
    if isinstance(value, (list, tuple)) and value:
        return "COMBO"
    return "UNKNOWN"


def _choices(spec: object) -> list[str]:
    if not isinstance(spec, (list, tuple)) or not spec:
        return []
    first = spec[0]
    if not isinstance(first, (list, tuple)):
        return []
    result: list[str] = []
    for choice in list(first)[:MAX_CHOICES]:
        text = _text(choice, 80)
        if text and text not in result:
            result.append(text)
    return result


def _input_entry(name: object, spec: object, *, required: bool) -> dict | None:
    name = _name(name)
    if not name or not isinstance(spec, (list, tuple)) or not spec:
        return None
    raw_type = spec[0]
    node_type = _type(raw_type)
    options: dict = {}
    if isinstance(spec, (list, tuple)) and len(spec) > 1 and isinstance(spec[1], dict):
        options = spec[1]
    entry = {
        "name": name,
        "type": node_type,
        "required": bool(required),
        "has_default": "default" in options,
    }
    choices = _choices(spec)
    if choices:
        entry["choices"] = choices
    # Only scalar primitive defaults are exposed; model/file/URI defaults stay hidden.
    if node_type in _PRIMITIVE_TYPES and "default" in options:
        default = options["default"]
        if isinstance(default, (bool, int, float)):
            entry["default"] = default
        elif isinstance(default, str):
            entry["default"] = _text(default, 120)
    return entry


def _output_entries(info: dict) -> list[dict]:
    raw_types = info.get("output")
    raw_names = info.get("output_name")
    raw_is_list = info.get("output_is_list")
    types = list(raw_types) if isinstance(raw_types, (list, tuple)) else []
    names = list(raw_names) if isinstance(raw_names, (list, tuple)) else []
    is_list = list(raw_is_list) if isinstance(raw_is_list, (list, tuple)) else []
    entries: list[dict] = []
    for index, raw_type in enumerate(types[:MAX_OUTPUTS_PER_NODE]):
        name = _name(names[index]) if index < len(names) else ""
        entries.append({
            "index": index,
            "type": _type(raw_type),
            "name": name or f"output_{index + 1}",
            "is_list": bool(is_list[index]) if index < len(is_list) else False,
        })
    return entries


def _node_descriptor(node_class: str, info: object) -> dict | None:
    if not isinstance(info, dict):
        return None
    node_class = _name(node_class)
    if not node_class:
        return None
    inputs: list[dict] = []
    input_section = info.get("input")
    if isinstance(input_section, dict):
        for group, required in (("required", True), ("optional", False)):
            rows = input_section.get(group)
            if not isinstance(rows, dict):
                continue
            for name, spec in rows.items():
                if len(inputs) >= MAX_INPUTS_PER_NODE:
                    break
                entry = _input_entry(name, spec, required=required)
                if entry is not None:
                    inputs.append(entry)
    slug = _DEFINITION_SLUG.sub("_", node_class).strip("_") or "node"
    digest = hashlib.sha256(node_class.encode("utf-8")).hexdigest()[:8]
    definition_id = f"comfyui.{slug[:100]}.{digest}"
    return {
        "node_class": node_class,
        "definition_id": definition_id,
        "display_name": _name(info.get("display_name")) or node_class,
        "category": _text(info.get("category"), 120),
        "description": _text(info.get("description")),
        "output_node": bool(info.get("output_node")),
        "deprecated": bool(info.get("deprecated")),
        "inputs": inputs,
        "outputs": _output_entries(info),
    }


def studio_type_hints(node: dict) -> list[str]:
    kinds: list[str] = []
    for row in node.get("inputs", []):
        mapped = _STUDIO_TYPE_HINTS.get(str(row.get("type", "")).upper())
        if mapped and mapped not in kinds:
            kinds.append(mapped)
    for row in node.get("outputs", []):
        mapped = _STUDIO_TYPE_HINTS.get(str(row.get("type", "")).upper())
        if mapped and mapped not in kinds:
            kinds.append(mapped)
    return kinds


def parse_comfyui_object_info(payload: object, *, max_nodes: int = MAX_NODES) -> dict:
    if type(max_nodes) is not int or max_nodes < 1:
        raise ValueError("COMFYUI_NODE_LIBRARY_LIMIT_INVALID")
    if not isinstance(payload, dict):
        raise ComfyNodeLibraryError("COMFYUI_NODE_LIBRARY_INVALID", status=502,
            detail="ComfyUI /object_info must be a JSON object")
    nodes: list[dict] = []
    ignored = 0
    keys = sorted(payload, key=lambda value: str(value))
    for node_class in keys:
        descriptor = _node_descriptor(str(node_class), payload[node_class])
        if descriptor is None:
            ignored += 1
            continue
        if len(nodes) >= max_nodes:
            ignored += 1
            continue
        descriptor["studio_type_hints"] = studio_type_hints(descriptor)
        nodes.append(descriptor)
    nodes.sort(key=lambda node: (node["category"], node["display_name"].lower(), node["node_class"]))
    return {
        "contract": CONTRACT,
        "source": SOURCE,
        "node_count": len(nodes),
        "ignored_nodes": ignored,
        "truncated": ignored > 0 and len(nodes) >= max_nodes,
        "nodes": nodes,
    }


def _endpoint_origin(endpoint: str) -> str:
    parsed = urlsplit(endpoint)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    return _text(origin, 200)


def _provider_configs() -> dict:
    from ..asset_provider_config import load as load_asset_provider_config
    saved = load_asset_provider_config()
    if not isinstance(saved, dict):
        return {}
    return {str(key): value for key, value in saved.items() if isinstance(value, dict)}


def _select_provider(provider_id: str | None, configs: dict) -> tuple[str, dict, list[str]]:
    comfy = sorted((pid, cfg) for pid, cfg in configs.items()
                   if str(cfg.get("api_style", "")).lower() == "comfyui")
    if not comfy:
        raise ComfyNodeLibraryError("COMFYUI_PROVIDER_NOT_CONFIGURED", status=409,
            detail="No saved ComfyUI provider configuration with api_style=comfyui and an endpoint")
    available = [pid for pid, _ in comfy]
    if provider_id is not None:
        selected = next(((pid, cfg) for pid, cfg in comfy if pid == provider_id), None)
        if selected is None:
            raise ComfyNodeLibraryError("COMFYUI_PROVIDER_NOT_CONFIGURED", status=409,
                detail="Requested provider is not a saved ComfyUI provider")
        pid, cfg = selected
    else:
        pid, cfg = comfy[0]
    if cfg.get("enabled") is False:
        raise ComfyNodeLibraryError("COMFYUI_PROVIDER_DISABLED", status=409,
            detail="The selected ComfyUI provider is disabled")
    endpoint = str(cfg.get("endpoint") or "").strip()
    if not endpoint:
        raise ComfyNodeLibraryError("COMFYUI_PROVIDER_NOT_CONFIGURED", status=409,
            detail="The selected ComfyUI provider has no endpoint")
    return pid, cfg, available


def _transport_for(endpoint: str):
    from ..model_center.discovery_bridge import _LocalImageTransport
    return _LocalImageTransport(endpoint, configured=True, trust_env=False)


def fetch_comfyui_object_info(*, provider_id: str | None = None, guard=lambda: None,
                              transport_factory=None) -> dict:
    """Fetch the configured provider's raw /object_info under strict bounds.

    Returns the raw payload plus bounded source metadata; no parsing/normalizing
    happens here so the passthrough proxy can preserve ComfyUI's native shape.
    """
    if not callable(guard):
        raise ValueError("COMFYUI_NODE_LIBRARY_GUARD_INVALID")
    configs = _provider_configs()
    pid, cfg, available = _select_provider(provider_id, configs)
    endpoint = str(cfg.get("endpoint") or "").strip().rstrip("/")
    try:
        validate_provider_endpoint(endpoint)
    except ValueError as exc:
        raise ComfyNodeLibraryError("COMFYUI_ENDPOINT_REJECTED", status=409,
            detail=str(exc)[:200]) from None
    guard()
    transport = (transport_factory or _transport_for)(endpoint)
    try:
        transport.max_response_bytes = MAX_RESPONSE_BYTES
        transport.max_wire_bytes = MAX_RESPONSE_BYTES
    except AttributeError:
        pass
    guard()
    try:
        response = transport.get(endpoint + "/object_info", timeout=FETCH_TIMEOUT_SECONDS,
                                 dispatch_guard=guard)
    except ComfyNodeLibraryError:
        raise
    except Exception as exc:
        raise ComfyNodeLibraryError("COMFYUI_NODE_LIBRARY_UNAVAILABLE", status=503,
            detail=type(exc).__name__) from None
    status = int(getattr(response, "status_code", 0))
    if status < 200 or status >= 300:
        raise ComfyNodeLibraryError("COMFYUI_NODE_LIBRARY_UNAVAILABLE", status=502,
            detail=f"object_info HTTP {status}")
    body = getattr(response, "content", b"")
    if not isinstance(body, (bytes, bytearray, str)):
        raise ComfyNodeLibraryError("COMFYUI_NODE_LIBRARY_INVALID", status=502,
            detail="object_info response body is not bytes")
    raw = bytes(body) if not isinstance(body, str) else body.encode("utf-8", "replace")
    if not raw:
        raise ComfyNodeLibraryError("COMFYUI_NODE_LIBRARY_INVALID", status=502,
            detail="object_info response is empty")
    if len(raw) > MAX_RESPONSE_BYTES:
        raise ComfyNodeLibraryError("COMFYUI_NODE_LIBRARY_TOO_LARGE", status=502,
            detail=f"object_info exceeds {MAX_RESPONSE_BYTES} bytes")
    guard()
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeError, ValueError):
        raise ComfyNodeLibraryError("COMFYUI_NODE_LIBRARY_INVALID", status=502,
            detail="object_info is not valid UTF-8 JSON") from None
    if not isinstance(payload, dict):
        raise ComfyNodeLibraryError("COMFYUI_NODE_LIBRARY_INVALID", status=502,
            detail="ComfyUI /object_info must be a JSON object")
    guard()
    return {
        "provider_id": pid,
        "available_providers": available,
        "endpoint_origin": _endpoint_origin(endpoint),
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "source_version": hashlib.sha256(raw).hexdigest(),
        "payload": payload,
        "raw_bytes": len(raw),
    }


def load_comfyui_node_library(*, provider_id: str | None = None, guard=lambda: None,
                              transport_factory=None) -> dict:
    """Fetch and normalize one configured ComfyUI provider's node metadata.

    Read-only: no workflow is submitted, no file is written, no node is executed.
    """
    fetched = fetch_comfyui_object_info(provider_id=provider_id, guard=guard,
        transport_factory=transport_factory)
    payload = fetched.pop("payload")
    result = parse_comfyui_object_info(payload)
    for node in result["nodes"]:
        node["studio_type_hints"] = studio_type_hints(node)
    result.update({
        "provider_id": fetched["provider_id"],
        "available_providers": fetched["available_providers"],
        "endpoint_origin": fetched["endpoint_origin"],
        "observed_at": fetched["observed_at"],
        "source_version": fetched["source_version"],
        "compatibility": {
            "contract": COMPATIBILITY_CONTRACT,
            "purpose": "NODE_LIBRARY_METADATA_ONLY",
            "execution": "NOT_CONNECTED",
            "studio_executable": False,
            "requires_explicit_workflow_mapping": True,
            "execution_owner": "provider-specific workflow adapter (not implemented here)",
        },
        "limits": {
            "max_nodes": MAX_NODES,
            "max_inputs_per_node": MAX_INPUTS_PER_NODE,
            "max_outputs_per_node": MAX_OUTPUTS_PER_NODE,
            "max_choices": MAX_CHOICES,
            "max_response_bytes": MAX_RESPONSE_BYTES,
            "timeout_seconds": FETCH_TIMEOUT_SECONDS,
            "cache": "NONE_LIVE_READ_ONLY",
        },
    })
    from .comfy_node_mapping import annotate_node_library
    result = annotate_node_library(result)
    guard()
    return result
