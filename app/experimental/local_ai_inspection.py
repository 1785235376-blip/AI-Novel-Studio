"""Bounded, passive Comfy API graph inspection. Imported graphs are NEVER adapters.

Only already-captured host discovery metadata is consumed. No filesystem reads,
network clients, process execution, model loading, or registry mutation live here.
Raw graphs and their values remain ephemeral; persisted/exported reports use an
allowlisted aggregate schema, never user-authored identifiers or literal values.
"""
from __future__ import annotations

import json
import math
import re
from collections import Counter, deque
from typing import Callable

from pydantic import BaseModel, ConfigDict, Field

from .common import DomainService, new_row

MAX_BYTES = 512 * 1024
MAX_NODES = 256
MAX_INPUTS = 128
MAX_EDGES = 4096
MAX_DEPTH = 24
MAX_VALUES = 20000
FEATURE = "local_ai_workflow_inspector_v2"
EXECUTION_POLICY = "DENY_ALL"
SCHEMA = "local-ai-workflow-inspection-v1"
OFFICIAL_SOURCES = [{"label": "ComfyUI 官方 API 路由与 object_info", "url": "https://docs.comfy.org/development/comfyui-server/comms_routes"}]
MODEL_FIELDS = frozenset({"ckpt_name", "unet_name", "model_name", "checkpoint", "checkpoint_name", "model_path", "vae_name", "clip_name", "clip_name1", "clip_name2", "lora_name", "control_net_name", "upscale_model"})
# These classify names, not code provenance. Even a familiar class can be replaced
# by an extension; no name in this list grants execution authority.
CORE_NAMES = frozenset({"CheckpointLoaderSimple", "KSampler", "KSamplerAdvanced", "EmptyLatentImage", "CLIPTextEncode", "VAEDecode", "VAEEncode", "SaveImage", "PreviewImage", "LoadImage", "VAELoader", "LoraLoader", "CLIPLoader", "DualCLIPLoader", "UNETLoader", "ControlNetLoader", "UpscaleModelLoader"})
SECRET_KEY = re.compile(r"(?i)(?:api.?key|secret|password|passwd|credential|authorization|access.?token|auth.?token|bearer)")
SECRET_VALUE = re.compile(r"(?i)(?:\bsk-[A-Za-z0-9_-]{8,}|\bBearer\s+\S+|-----BEGIN.*PRIVATE KEY|(?:api[_-]?key|password|access[_-]?token)\s*[:=])")
NETWORK = re.compile(r"(?i)(?:https?://|ftp://|wss?://|\b(?:http|download|upload|webhook|request|socket|fetch|api.?call)\b)")
CODE = re.compile(r"(?i)(?:python|javascript|subprocess|shell|execute|exec\b|eval\b|command|script|bash|powershell|code)")
PATH = re.compile(r"(?:^[a-zA-Z]:[\\/]|^[/\\~]|(?:^|[/\\])\.\.(?:[/\\]|$)|file://)")
IDENTIFIER = re.compile(r"^[\w. -]{1,100}$")


class InspectionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # Parse inside the service to reject duplicate keys / deep JSON and to avoid
    # Pydantic echoing the raw graph in a nested validation error.
    workflow_json: str = Field(max_length=MAX_BYTES)
    runtime_id: str = Field(default="", max_length=160)
    declared_alias: str = Field(default="", max_length=100)


def label(value):
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value) or SECRET_KEY.search(value) or SECRET_VALUE.search(value):
        return "[REDACTED]"
    return value


def duplicate_safe_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("WORKFLOW_DUPLICATE_KEY")
        result[key] = value
    return result


def parse_workflow(raw):
    try:
        size = len(raw.encode("utf-8"))
    except UnicodeError:
        raise ValueError("WORKFLOW_INVALID_ENCODING") from None
    if size > MAX_BYTES:
        raise ValueError("WORKFLOW_TOO_LARGE")
    # Bound depth before json.loads itself can recurse or allocate a deep tree.
    depth = 0
    quoted = escaped = False
    for char in raw:
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char in "[{":
            depth += 1
            if depth > MAX_DEPTH:
                raise ValueError("WORKFLOW_TOO_DEEP")
        elif char in "]}":
            depth -= 1
    try:
        parsed = json.loads(raw, object_pairs_hook=duplicate_safe_object,
                            parse_constant=lambda _: (_ for _ in ()).throw(ValueError("WORKFLOW_NONFINITE_NUMBER")))
    except (json.JSONDecodeError, RecursionError):
        raise ValueError("WORKFLOW_INVALID_JSON") from None
    except ValueError as error:
        if str(error) in {"WORKFLOW_DUPLICATE_KEY", "WORKFLOW_NONFINITE_NUMBER"}:
            raise
        raise ValueError("WORKFLOW_INVALID_JSON") from None
    if not isinstance(parsed, dict):
        raise ValueError("WORKFLOW_API_OBJECT_REQUIRED")
    # Accept API graph and the /prompt envelope; UI graph export is not API form.
    graph = parsed.get("prompt") if "prompt" in parsed else parsed
    if not isinstance(graph, dict) or not graph or "nodes" in graph:
        raise ValueError("WORKFLOW_API_FORMAT_REQUIRED")
    if len(graph) > MAX_NODES:
        raise ValueError("WORKFLOW_NODE_LIMIT")
    count = 0
    stack = [parsed]
    while stack:
        value = stack.pop()
        count += 1
        if count > MAX_VALUES:
            raise ValueError("WORKFLOW_VALUE_LIMIT")
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("WORKFLOW_NONFINITE_NUMBER")
        if isinstance(value, dict):
            stack.extend(value.values())
        elif isinstance(value, list):
            stack.extend(value)
    for node_id, node in graph.items():
        if not isinstance(node_id, str) or not node_id or len(node_id) > 160 or not isinstance(node, dict):
            raise ValueError("WORKFLOW_NODE_INVALID")
        if not isinstance(node.get("class_type"), str) or not 0 < len(node["class_type"]) <= 200:
            raise ValueError("WORKFLOW_NODE_CLASS_REQUIRED")
        if not isinstance(node.get("inputs"), dict) or len(node["inputs"]) > MAX_INPUTS:
            raise ValueError("WORKFLOW_INPUTS_INVALID")
    return parsed, graph, size


def value_risks(value):
    """Heuristics are warnings, never a proof of safety. Do not echo values."""
    found = set()
    stack = [("", value)]
    while stack:
        key, item = stack.pop()
        if SECRET_KEY.search(key):
            found.add("CREDENTIAL_MATERIAL")
        if isinstance(item, str):
            if SECRET_VALUE.search(item): found.add("CREDENTIAL_MATERIAL")
            if NETWORK.search(item): found.add("NETWORK_REFERENCE")
            if PATH.search(item): found.add("FILESYSTEM_REFERENCE")
            if CODE.search(key): found.add("CODE_INPUT")
        elif isinstance(item, dict):
            stack.extend((str(k), v) for k, v in item.items())
        elif isinstance(item, list):
            stack.extend((key, v) for v in item)
    return found


class LocalAIInspectionService(DomainService):
    REPORTS = "local_ai_workflow_reports"

    def __init__(self, store, novels, chapters, *, discovery_snapshot: Callable, adapter_definitions: Callable):
        super().__init__(store, novels, chapters)
        self.discovery_snapshot = discovery_snapshot
        self.adapter_definitions = adapter_definitions

    def metadata(self):
        snap = self.discovery_snapshot()
        scan = snap.get("scan") or {}
        runtimes = []
        for row in scan.get("runtimes", [])[:20]:
            if row.get("type") == "COMFYUI":
                runtimes.append({"id": row["id"], "label": f"ComfyUI {len(runtimes) + 1}",
                                 "observed_status": row.get("status", "NOT_VERIFIED"),
                                 "version": label(row.get("version")) if row.get("version") else None})
        return {"runtimes": runtimes, "snapshot_state": "NOT_SCANNED" if not snap.get("scan") else scan.get("status", "NOT_VERIFIED"),
                "observed_at": scan.get("finished_at"), "execution_policy": EXECUTION_POLICY,
                "limits": {"bytes": MAX_BYTES, "nodes": MAX_NODES, "inputs_per_node": MAX_INPUTS, "edges": MAX_EDGES, "depth": MAX_DEPTH},
                "official_sources": OFFICIAL_SOURCES}

    def inspect(self, body: InspectionInput):
        parsed, graph, size = parse_workflow(body.workflow_json)
        snap = self.discovery_snapshot()
        scan = snap.get("scan") or {}
        runtime = next((row for row in scan.get("runtimes", [])[:20] if row.get("id") == body.runtime_id and row.get("type") == "COMFYUI"), None)
        if body.runtime_id and runtime is None:
            raise ValueError("WORKFLOW_RUNTIME_SNAPSHOT_CHANGED")
        # Never combine evidence from different runtime IDs/endpoints.
        candidates = [r for r in scan.get("candidates", [])[:10240]
                      if runtime and r.get("runtime_id") == body.runtime_id and r.get("runtime_type") == "COMFYUI"]
        known_nodes = set()
        model_bindings = set()
        for candidate in candidates:
            evidence = candidate.get("evidence") or {}
            known_nodes.update(n for n in evidence.get("node_classes", [])[:4096] if isinstance(n, str))
            if evidence.get("model_listed") is True:
                for binding in evidence.get("loader_bindings", [])[:128]:
                    model_bindings.add((binding.get("node_class"), binding.get("input_field"), candidate.get("model_name")))
        registrations = [r for r in snap.get("registrations", [])[:2048]
                         if runtime and r.get("runtime_id") == body.runtime_id and r.get("runtime_type") == "COMFYUI"]
        issues = []
        def issue(code, severity="UNKNOWN", node=None, input_ref=None):
            row = {"code": code, "severity": severity}
            if node: row["node"] = node
            if input_ref: row["input"] = input_ref
            issues.append(row)
        for code in sorted(value_risks(parsed)):
            issue(code, "RISK")
        if not runtime: issue("RUNTIME_SNAPSHOT_REQUIRED")
        elif runtime.get("status") not in {"RUNNING", "DISCOVERED"}: issue("RUNTIME_NOT_AVAILABLE_IN_SNAPSHOT", "MISSING")
        if scan.get("status") not in {"COMPLETED", "PARTIAL"}: issue("DISCOVERY_SNAPSHOT_INCOMPLETE")
        if not known_nodes: issue("NODE_CATALOG_NOT_CAPTURED")
        issue("NODE_INPUT_OUTPUT_SCHEMA_NOT_CAPTURED")
        issue("SNAPSHOT_IS_NOT_LIVE_VALIDATION")
        issue("LICENSE_REVIEW_REQUIRED" if not registrations or not all(r.get("license_confirmed") for r in registrations) else "LICENSE_SCOPE_NOT_BOUND_TO_IMPORTED_GRAPH")
        issue("HARDWARE_MEMORY_NOT_ESTIMATED")
        refs = {nid: f"node-{index + 1}" for index, nid in enumerate(graph)}
        nodes, edges, models, outputs = [], [], [], []
        deps = {nid: set() for nid in graph}
        classes = {node["class_type"] for node in graph.values()}
        for nid, node in graph.items():
            ref, class_type = refs[nid], node["class_type"]
            existence = "LISTED_IN_SNAPSHOT" if class_type in known_nodes else "NOT_LISTED_IN_SNAPSHOT" if known_nodes else "UNKNOWN"
            if existence == "NOT_LISTED_IN_SNAPSHOT": issue("NODE_NOT_LISTED", "MISSING", ref)
            if class_type not in CORE_NAMES: issue("NODE_IMPLEMENTATION_UNKNOWN", "UNKNOWN", ref)
            if CODE.search(class_type): issue("CODE_EXECUTION_NODE", "RISK", ref)
            if re.search(r"(?i)(http|download|upload|webhook|socket|fetch|api.?call)", class_type): issue("NETWORK_NODE", "RISK", ref)
            if re.search(r"(?i)(save|load|read|write|file)", class_type): issue("FILE_IO_NODE", "RISK", ref)
            inputs = []
            for index, (key, value) in enumerate(node["inputs"].items()):
                input_ref = f"input-{index + 1}"
                item = {"ref": input_ref, "name": label(key), "kind": "LITERAL_REDACTED"}
                if isinstance(value, list) and len(value) == 2 and isinstance(value[0], (str, int)) and not isinstance(value[0], bool):
                    source, slot = str(value[0]), value[1]
                    item["kind"] = "LINK"
                    if source not in graph:
                        issue("LINK_SOURCE_MISSING", "ERROR", ref, input_ref)
                    elif not isinstance(slot, int) or isinstance(slot, bool) or not 0 <= slot <= 255:
                        issue("LINK_SLOT_INVALID", "ERROR", ref, input_ref)
                    else:
                        deps[nid].add(source)
                        if len(edges) >= MAX_EDGES: raise ValueError("WORKFLOW_EDGE_LIMIT")
                        edges.append({"from": refs[source], "output_slot": slot, "to": ref, "input": input_ref, "schema_validation": "NOT_VERIFIED"})
                        item.update(source=refs[source], output_slot=slot)
                elif isinstance(value, (dict, list)):
                    item["kind"] = "COMPOSITE_UNVERIFIED"
                    issue("INPUT_LITERAL_SCHEMA_UNVERIFIED", "UNKNOWN", ref, input_ref)
                if key in MODEL_FIELDS:
                    listed = isinstance(value, str) and (class_type, key, value) in model_bindings
                    models.append({"node": ref, "input": input_ref, "field": label(key), "reference": label(value) if isinstance(value, str) else "[NON_LITERAL]",
                                   "status": "LISTED_METADATA_ONLY" if listed else "NOT_LISTED" if model_bindings else "UNKNOWN",
                                   "file_exists": "NOT_VERIFIED", "generation": "NOT_RUN"})
                    if not listed: issue("MODEL_COMPONENT_NOT_LISTED" if model_bindings else "MODEL_COMPONENT_UNKNOWN", "MISSING" if model_bindings else "UNKNOWN", ref, input_ref)
                inputs.append(item)
            nodes.append({"ref": ref, "class_type": label(class_type), "registry_status": existence, "inputs": inputs, "implementation_trust": "NOT_VERIFIED"})
            if class_type in {"SaveImage", "PreviewImage"}:
                outputs.append({"node": ref, "kind": "IMAGE_SINK_BY_NAME", "contract": "NOT_VERIFIED"})
        if len(edges) > MAX_EDGES: raise ValueError("WORKFLOW_EDGE_LIMIT")
        # Iterative topological check avoids recursion even at the node bound.
        consumers = {nid: set() for nid in graph}
        indegree = {nid: len(values) for nid, values in deps.items()}
        for nid, dependencies in deps.items():
            for source in dependencies: consumers[source].add(nid)
        queue = deque(nid for nid, degree in indegree.items() if not degree)
        visited = 0
        while queue:
            source = queue.popleft(); visited += 1
            for target in consumers[source]:
                indegree[target] -= 1
                if not indegree[target]: queue.append(target)
        if visited != len(graph): issue("WORKFLOW_CYCLE", "ERROR")
        if not outputs: issue("OUTPUT_MAPPING_UNVERIFIED")
        adapter_rows = []
        for adapter in snap.get("workflow_adapters", [])[:100]:
            required = set(adapter.get("required_nodes") or [])
            adapter_rows.append({"id": label(adapter.get("id")), "source": "LOCAL_AI_DISCOVERY",
                                 "state": "REQUIRED_NODE_NAMES_PRESENT_ONLY" if required and required <= classes else "REQUIRED_NODES_NOT_PRESENT",
                                 "missing_nodes": [label(n) for n in sorted(required - classes)], "imported_graph_bound": False})
        for adapter in self.adapter_definitions().get("items", [])[:100]:
            adapter_rows.append({"id": label(adapter.get("adapter_id")), "source": "R3_MEDIA_REGISTRY",
                                 "state": adapter.get("state", "ADAPTER_REQUIRED"), "imported_graph_bound": False})
        issue("IMPORTED_GRAPH_HAS_NO_REVIEWED_ADAPTER")
        status = "INVALID" if any(i["severity"] == "ERROR" for i in issues) else "REVIEW_REQUIRED"
        counts = dict(Counter(i["severity"] for i in issues))
        summary = {"schema": SCHEMA, "inspection_version": 1, "status": status, "execution_policy": EXECUTION_POLICY,
                   "verification": "STRUCTURAL_METADATA_ONLY", "real_runtime": "NOT_RUN", "real_model": "NOT_RUN",
                   "counts": {"nodes": len(nodes), "edges": len(edges), "model_components": len(models), "output_candidates": len(outputs), "bytes": size, "issues": counts},
                   "issue_codes": sorted({i["code"] for i in issues}), "raw_workflow_included": False,
                   "literal_values_included": False, "host_inventory_included": False, "uploaded": False}
        return {**summary, "nodes": nodes, "edges": edges, "model_components": models, "outputs": outputs,
                "issues": issues, "adapters": adapter_rows, "runnable": False,
                "declared_alias": {"label": label(body.declared_alias) if body.declared_alias else None, "verification": "USER_DECLARED_NOT_VERIFIED"},
                "snapshot": {"state": scan.get("status", "NOT_SCANNED"), "observed_at": scan.get("finished_at"), "runtime_version": label(runtime.get("version")) if runtime and runtime.get("version") else None},
                "official_sources": OFFICIAL_SOURCES, "export_summary": summary}

    def save_report(self, nid, scope, actor, body):
        # Recompute, never trust client-submitted inspection status or risk codes.
        report = self.inspect(body)["export_summary"]
        self.novels.get(nid)
        with self.store.transaction(nid, scope) as doc:
            rows = doc["collections"].setdefault(self.REPORTS, {})
            if len(rows) >= 100: raise ValueError("WORKFLOW_REPORT_LIMIT")
            row = new_row(nid, scope, actor, {"summary": report, "status": "CHECKED", "privacy_level": "LOCAL_ONLY"})
            rows[row["id"]] = row
            return row
