"""Lower-canvas draft persistence for the ComfyUI-style dual canvas.

This is intentionally a *draft* surface: GET/PUT store the frontend's CfGraph
(nodes/edges) per project scope with an optimistic version. It never submits a
ComfyUI prompt, never executes a node, never prices a run and writes no assets.
Execution endpoints are a separate, later contract.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator

COLLECTION = "lower_canvas_v1"
KINDS = ("image", "video")
MAX_NODES = 400
MAX_EDGES = 800
MAX_TITLE = 200
MAX_GRAPH_BYTES = 1_000_000


class LowerCanvasNode(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1, max_length=120)
    t: str = Field(min_length=1, max_length=160)
    x: float
    y: float
    title: str = Field(default="", max_length=MAX_TITLE)

    @field_validator("id", "t", "title")
    @classmethod
    def _no_control(cls, value: str) -> str:
        if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
            raise ValueError("control characters are not allowed")
        return value


class LowerCanvasEdge(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1, max_length=120)
    a: str = Field(min_length=1, max_length=120)
    as_: int = Field(alias="as", ge=0, le=4096)
    b: str = Field(min_length=1, max_length=120)
    bs: int = Field(ge=0, le=4096)


class LowerCanvasGraph(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nodes: list[LowerCanvasNode] = Field(default_factory=list)
    edges: list[LowerCanvasEdge] = Field(default_factory=list)


class LowerCanvasSave(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=0, le=1_000_000)
    graph: LowerCanvasGraph


class LowerCanvasVersionConflict(Exception):
    def __init__(self, current_version: int):
        self.current_version = int(current_version)
        super().__init__("LOWER_CANVAS_VERSION_CONFLICT")


def _validate_kind(kind: str) -> str:
    if kind not in KINDS:
        raise HTTPException(404, {"code": "LOWER_CANVAS_KIND_INVALID"})
    return kind


def _graph_payload(graph: LowerCanvasGraph) -> dict:
    if len(graph.nodes) > MAX_NODES or len(graph.edges) > MAX_EDGES:
        raise HTTPException(400, {"code": "LOWER_CANVAS_GRAPH_TOO_LARGE"})
    node_ids = [node.id for node in graph.nodes]
    if len(node_ids) != len(set(node_ids)):
        raise HTTPException(400, {"code": "LOWER_CANVAS_NODE_ID_DUPLICATE"})
    known = set(node_ids)
    edge_ids = [edge.id for edge in graph.edges]
    if len(edge_ids) != len(set(edge_ids)):
        raise HTTPException(400, {"code": "LOWER_CANVAS_EDGE_ID_DUPLICATE"})
    for edge in graph.edges:
        if edge.a not in known or edge.b not in known:
            raise HTTPException(400, {"code": "LOWER_CANVAS_EDGE_ENDPOINT_MISSING"})
        if edge.a == edge.b:
            raise HTTPException(400, {"code": "LOWER_CANVAS_EDGE_SELF_LOOP"})
    payload = graph.model_dump(by_alias=True)
    import json
    if len(json.dumps(payload, ensure_ascii=False).encode("utf-8")) > MAX_GRAPH_BYTES:
        raise HTTPException(400, {"code": "LOWER_CANVAS_GRAPH_TOO_LARGE"})
    return payload


def _public(kind: str, row: dict | None) -> dict:
    row = row if isinstance(row, dict) else {}
    return {
        "kind": kind,
        "version": int(row.get("version") or 0),
        "graph": row.get("graph") or {"nodes": [], "edges": []},
        "updated_at": row.get("updated_at"),
        "updated_by": row.get("updated_by"),
        "execution": "NOT_IMPLEMENTED",
        "limits": {"nodes": MAX_NODES, "edges": MAX_EDGES, "graph_bytes": MAX_GRAPH_BYTES},
    }


def read_lower_canvas(service, nid: str, scope: dict, kind: str) -> dict:
    kind = _validate_kind(kind)
    document = service.store.read(nid, scope)
    row = document.get("collections", {}).get(COLLECTION, {}).get(kind)
    return _public(kind, row)


def save_lower_canvas(service, nid: str, scope: dict, actor: str, kind: str,
                      body: LowerCanvasSave, guard=lambda: None) -> dict:
    kind = _validate_kind(kind)
    graph = _graph_payload(body.graph)
    with service.store.transaction(nid, scope) as document:
        rows = document["collections"].setdefault(COLLECTION, {})
        row = rows.get(kind)
        current = int(row["version"]) if isinstance(row, dict) else 0
        if body.expected_version != current:
            raise LowerCanvasVersionConflict(current)
        now = datetime.now(timezone.utc).isoformat()
        row = {
            "id": kind,
            "kind": kind,
            "version": current + 1,
            "graph": graph,
            "updated_at": now,
            "updated_by": str(actor or "")[:120],
        }
        rows[kind] = row
        guard()
    return _public(kind, row)


def create_lower_canvas_router(service, invoke):
    router = APIRouter(tags=["Studio lower canvas"])

    def _invoke(nid, token, branch, permission, callback):
        return invoke(nid, token, branch, permission, callback)

    @router.get("/projects/{nid}/studio/lower-canvas/{kind}")
    def lower_canvas_get(nid: str, kind: str, x_session_token: str | None = Header(None),
                         x_branch_id: str | None = Header(None)):
        return _invoke(nid, x_session_token, x_branch_id, "domain.read",
            lambda actor, scope, guard: read_lower_canvas(service, nid, scope, kind))

    @router.put("/projects/{nid}/studio/lower-canvas/{kind}")
    def lower_canvas_put(nid: str, kind: str, body: LowerCanvasSave,
                         x_session_token: str | None = Header(None),
                         x_branch_id: str | None = Header(None)):
        try:
            return _invoke(nid, x_session_token, x_branch_id, "domain.write",
                lambda actor, scope, guard: save_lower_canvas(
                    service, nid, scope, actor, kind, body, guard))
        except LowerCanvasVersionConflict as exc:
            raise HTTPException(409, {"code": "LOWER_CANVAS_VERSION_CONFLICT",
                "current_version": exc.current_version}) from None

    return router
