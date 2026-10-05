"""Version-fenced experimental planning. Approvals only change this planning graph.

Structured model adapters produce review proposals, never manuscript or legacy Canon.
The bundled adapter is explicitly deterministic Mock; no provider is contacted.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from .common import DomainService, StaleSourceError, new_row, change_row
from ..services.v1_capability_service import CapabilityVersionConflict


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class PlanningFields(StrictModel):
    goal: str = Field(default="", max_length=12000)
    conflict: str = Field(default="", max_length=12000)
    turning_point: str = Field(default="", max_length=12000)
    climax: str = Field(default="", max_length=12000)
    ending_intent: str = Field(default="", max_length=12000)
    character_objectives: dict[str, str] = Field(default_factory=dict, max_length=100)
    beats: dict[str, str] = Field(default_factory=dict, max_length=100)


class PlanningLinks(StrictModel):
    character_ids: list[str] = Field(default_factory=list, max_length=100)
    location_ids: list[str] = Field(default_factory=list, max_length=100)
    world_rule_ids: list[str] = Field(default_factory=list, max_length=100)
    chapter_ids: list[str] = Field(default_factory=list, max_length=1000)
    story_route_ids: list[str] = Field(default_factory=list, max_length=100)


class PlanningGraphIn(StrictModel):
    title: str = Field(min_length=1, max_length=240)
    fields: PlanningFields = Field(default_factory=PlanningFields)
    links: PlanningLinks = Field(default_factory=PlanningLinks)


class PlanningNodeIn(PlanningGraphIn):
    graph_id: str = Field(min_length=1, max_length=160)
    parent_id: str = Field(min_length=1, max_length=160)
    level: Literal["VOLUME", "CHAPTER", "SCENE"]
    position: int = Field(default=0, ge=0)


class PlanningNodeEditIn(PlanningGraphIn):
    expected_version: int = Field(ge=1)
    position: int = Field(default=0, ge=0)


class PlanningProposalIn(StrictModel):
    node_id: str = Field(min_length=1, max_length=160)
    expected_node_version: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=240)
    fields: PlanningFields = Field(default_factory=PlanningFields)
    links: PlanningLinks = Field(default_factory=PlanningLinks)
    rationale: str = Field(default="", max_length=12000)
    template_id: str | None = None


class PlanningTemplateIn(StrictModel):
    title: str = Field(min_length=1, max_length=240)
    description: str = Field(default="", max_length=4000)
    beats: dict[str, str] = Field(default_factory=dict, max_length=100)
    ending_options: list[str] = Field(default_factory=list, max_length=20)


class PlanningGenerateIn(StrictModel):
    node_id: str = Field(min_length=1, max_length=160)
    expected_node_version: int = Field(ge=1)
    adapter_id: str = "mock-structured-planner"
    template_id: str = "three-act"
    instruction: str = Field(default="", max_length=12000)
    candidate_count: int = Field(default=2, ge=1, le=8)


class PlanningAdapterRequest(StrictModel):
    schema_version: Literal[1] = 1
    node: dict[str, Any]
    ancestors: list[dict[str, Any]] = Field(default_factory=list)
    template: PlanningTemplateIn
    instruction: str
    candidate_count: int = Field(ge=1, le=8)


class PlanningAdapterCandidate(StrictModel):
    title: str = Field(min_length=1, max_length=240)
    fields: PlanningFields
    rationale: str = Field(default="", max_length=12000)


class PlanningAdapterOutput(StrictModel):
    schema_version: Literal[1] = 1
    execution_mode: Literal["MOCK_ONLY", "LOCAL_MODEL", "REMOTE_MODEL"]
    candidates: list[PlanningAdapterCandidate] = Field(min_length=1, max_length=8)


class StructuredPlanningAdapter(Protocol):
    adapter_id: str
    def generate(self, request: PlanningAdapterRequest) -> PlanningAdapterOutput: ...


class MockStructuredPlanningAdapter:
    adapter_id = "mock-structured-planner"

    def generate(self, request: PlanningAdapterRequest) -> PlanningAdapterOutput:
        candidates = []
        for index in range(request.candidate_count):
            fields = deepcopy(request.node["fields"])
            fields["goal"] = request.instruction or fields.get("goal") or "Define the next narrative goal"
            fields["beats"] = {**fields.get("beats", {}), **request.template.beats}
            options = request.template.ending_options
            if options:
                fields["ending_intent"] = options[index % len(options)]
            candidates.append(PlanningAdapterCandidate(
                title=f"Mock option {index + 1}", fields=PlanningFields.model_validate(fields),
                rationale="Deterministic schema fixture; literary quality is not verified.",
            ))
        return PlanningAdapterOutput(execution_mode="MOCK_ONLY", candidates=candidates)


BUILTIN_TEMPLATES = {
    "three-act": {"title": "Three acts (optional)", "description": "An editable starting point, not a required theory.", "beats": {"setup": "Establish the goal", "confrontation": "Complicate the goal", "resolution": "Resolve the central choice"}, "ending_options": []},
    "conflict-escalation": {"title": "Conflict escalation", "description": "Track rising stakes and a turning point.", "beats": {"pressure": "Initial pressure", "escalation": "Increasing cost", "climax": "Decisive action"}, "ending_options": []},
    "multiple-endings": {"title": "Alternative endings", "description": "Compare different outcomes without selecting one automatically.", "beats": {}, "ending_options": ["Hopeful resolution", "Tragic consequence", "Open-ended continuation"]},
}


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def collection(state: dict, name: str) -> dict:
    return state.setdefault("collections", {}).setdefault(name, {})


def require_row(state: dict, name: str, rid: str) -> dict:
    row = collection(state, name).get(rid)
    if row is None or row.get("novel_id") != state.get("novel_id") or row.get("scope") != state.get("scope"):
        raise FileNotFoundError(rid)
    return row


def scoped_sources(service: DomainService, nid: str, scope: dict, chapter_ids: list[str]) -> dict:
    if scope.get("mode") == "collaboration":
        for cid in chapter_ids:
            chapter = service.chapters.get(cid)
            if chapter.get("branch_id") != scope.get("branch_id"):
                raise ValueError("BRANCH_SOURCE_ADAPTER_REQUIRED: base manuscript is not branch evidence")
    return service.sources(nid, chapter_ids)


def entity_sources(service: DomainService, nid: str, scope: dict, links: dict, state: dict | None = None) -> dict:
    """Validate real references and fence even legacy entities without versions."""
    captures = {}
    for field, dataset in (("character_ids", "characters"), ("location_ids", "locations"), ("story_route_ids", "story_routes")):
        ids = links.get(field, [])
        if not ids:
            continue
        rows = {str(row.get("id")): row for row in service.novels.data_set(nid, dataset)}
        for rid in ids:
            if rid not in rows:
                raise ValueError(f"unknown {dataset} reference: {rid}")
            if rows[rid].get("branch_id") and rows[rid]["branch_id"] != scope.get("branch_id"):
                raise ValueError("entity belongs to another branch")
            captures[f"{dataset}:{rid}"] = digest(rows[rid])
    if links.get("world_rule_ids"):
        world = (state or service.store.read(nid, scope)).get("collections", {}).get("world_records", {})
        legacy = {str(row.get("id")): row for row in service.novels.data_set(nid, "canon")}
        for rid in links["world_rule_ids"]:
            row = world.get(rid)
            if row and row.get("status") == "APPROVED" and row.get("kind") == "ABILITY":
                captures[f"world:{rid}"] = digest({key: value for key, value in row.items() if key != "history"})
            elif rid in legacy:
                captures[f"canon:{rid}"] = digest(legacy[rid])
            else:
                raise ValueError(f"unknown approved world rule reference: {rid}")
    return captures


class PlanningService(DomainService):
    GRAPHS = "planning_graphs"
    NODES = "planning_nodes"
    PROPOSALS = "planning_proposals"
    TEMPLATES = "planning_templates"

    def _payload(self, value, model):
        return model.model_validate(value.model_dump() if isinstance(value, BaseModel) else value).model_dump()

    def _validate_links(self, nid, scope, fields, links, state=None):
        if set(fields["character_objectives"]) - set(links["character_ids"]):
            raise ValueError("character objectives require linked real characters")
        return scoped_sources(self, nid, scope, links["chapter_ids"]), entity_sources(self, nid, scope, links, state)

    def _ancestors(self, state, node):
        rows, seen = [], {node["id"]}
        current = node
        while current["parent_id"]:
            current = require_row(state, self.NODES, current["parent_id"])
            if current["id"] in seen or current["graph_id"] != node["graph_id"] or current["status"] == "ARCHIVED":
                raise StaleSourceError("planning ancestor is unavailable")
            seen.add(current["id"])
            rows.append(current)
        return list(reversed(rows))

    def _assert_fresh(self, nid, scope, row, state=None, allow_applied=False):
        state = state if state is not None else self.store.read(nid, scope)
        self.assert_sources(nid, row.get("sources", {}))
        try:
            scoped_sources(self, nid, scope, list(row.get("sources", {})))
            refs = entity_sources(self, nid, scope, row["links"], state)
        except (ValueError, FileNotFoundError) as exc:
            raise StaleSourceError("planning entity or branch source changed") from exc
        if refs != row.get("entity_sources", {}):
            raise StaleSourceError("planning entity source changed")
        node = require_row(state, self.NODES, row["node_id"])
        if require_row(state, self.GRAPHS, row["graph_id"])["status"] != "ACTIVE":
            raise StaleSourceError("planning graph is archived")
        ancestors = {ancestor["id"]: ancestor["version"] for ancestor in self._ancestors(state, node)}
        if ancestors != row.get("ancestor_versions", {}):
            raise StaleSourceError("planning ancestor context changed")
        expected_target = row["target_version"]
        if allow_applied and row["status"] == "APPROVED" and node.get("approved_proposal_id") == row["id"]:
            expected_target = row.get("applied_node_version")
        if node["version"] != expected_target or node["status"] == "ARCHIVED":
            raise StaleSourceError("planning target node changed")

    def _decorate(self, nid, scope, row, state=None):
        row = deepcopy(row)
        try:
            self._assert_fresh(nid, scope, row, state, allow_applied=True)
            row["stale"] = False
        except (ValueError, FileNotFoundError):
            row["stale"] = True
        return row

    def list_graphs(self, nid, scope):
        return self.list(nid, scope, self.GRAPHS)

    def create_graph(self, nid, scope, actor, value):
        payload = self._payload(value, PlanningGraphIn)
        self.novels.get(nid)
        sources, entities = self._validate_links(nid, scope, payload["fields"], payload["links"])
        with self.store.transaction(nid, scope) as state:
            graph = new_row(nid, scope, actor, {"title": payload["title"], "status": "ACTIVE"})
            node = new_row(nid, scope, actor, {**payload, "graph_id": graph["id"], "parent_id": None, "level": "PROJECT", "position": 0, "status": "DRAFT", "sources": sources, "entity_sources": entities})
            graph["root_node_id"] = node["id"]
            collection(state, self.GRAPHS)[graph["id"]] = graph
            collection(state, self.NODES)[node["id"]] = node
            return deepcopy(graph)

    def graph(self, nid, scope, gid):
        self.novels.get(nid)
        state = self.store.read(nid, scope)
        graph = deepcopy(require_row(state, self.GRAPHS, gid))
        graph["nodes"] = sorted((deepcopy(row) for row in collection(state, self.NODES).values() if row["graph_id"] == gid), key=lambda row: (row["position"], row["id"]))
        return graph

    def create_node(self, nid, scope, actor, value):
        payload = self._payload(value, PlanningNodeIn)
        self.novels.get(nid)
        sources, entities = self._validate_links(nid, scope, payload["fields"], payload["links"])
        with self.store.transaction(nid, scope) as state:
            graph = require_row(state, self.GRAPHS, payload["graph_id"])
            if graph["status"] != "ACTIVE":
                raise ValueError("planning graph is archived")
            parent = require_row(state, self.NODES, payload["parent_id"])
            expected_parent = {"VOLUME": "PROJECT", "CHAPTER": "VOLUME", "SCENE": "CHAPTER"}[payload["level"]]
            if parent["graph_id"] != payload["graph_id"] or parent["level"] != expected_parent or parent["status"] == "ARCHIVED":
                raise ValueError("planning hierarchy must be Project > Volume > Chapter > Scene in one graph")
            if payload["level"] == "CHAPTER" and len(payload["links"]["chapter_ids"]) != 1:
                raise ValueError("chapter planning nodes require one real chapter reference")
            if payload["level"] == "SCENE" and payload["links"]["chapter_ids"] != parent["links"]["chapter_ids"]:
                raise ValueError("scene chapter reference must match its parent chapter")
            row = new_row(nid, scope, actor, {**payload, "status": "DRAFT", "sources": sources, "entity_sources": entities})
            collection(state, self.NODES)[row["id"]] = row
            return deepcopy(row)

    def edit_node(self, nid, scope, actor, node_id, value):
        payload = self._payload(value, PlanningNodeEditIn)
        expected = payload.pop("expected_version")
        with self.store.transaction(nid, scope) as state:
            row = require_row(state, self.NODES, node_id)
            if row["status"] == "ARCHIVED" or require_row(state, self.GRAPHS, row["graph_id"])["status"] != "ACTIVE":
                raise ValueError("restore archived planning targets before editing")
            self._ancestors(state, row)
            if row["links"]["chapter_ids"] != payload["links"]["chapter_ids"] and row["level"] in {"CHAPTER", "SCENE"}:
                raise ValueError("a chapter or scene node cannot be rebound to another chapter")
            sources, entities = self._validate_links(nid, scope, payload["fields"], payload["links"], state)
            def update(target):
                target.update(payload, status="DRAFT", sources=sources, entity_sources=entities)
                target.pop("approved_proposal_id", None)
            change_row(row, actor, expected, update)
            return deepcopy(row)

    def transition_graph(self, nid, scope, actor, gid, action, expected_version):
        def update(row):
            if action == "archive" and row["status"] == "ACTIVE":
                row["status"] = "ARCHIVED"
            elif action == "restore" and row["status"] == "ARCHIVED":
                row["status"] = "ACTIVE"
            else:
                raise ValueError("invalid graph transition")
        return self.mutate(nid, scope, actor, self.GRAPHS, gid, expected_version, update)

    def transition_node(self, nid, scope, actor, node_id, action, expected_version):
        with self.store.transaction(nid, scope) as state:
            row = require_row(state, self.NODES, node_id)
            if row["level"] == "PROJECT":
                raise ValueError("archive the graph to archive its root")
            if require_row(state, self.GRAPHS, row["graph_id"])["status"] != "ACTIVE":
                raise ValueError("planning graph is archived")
            def update(target):
                if action == "archive" and target["status"] != "ARCHIVED":
                    if any(child["parent_id"] == node_id and child["status"] != "ARCHIVED" for child in collection(state, self.NODES).values()):
                        raise ValueError("archive active child nodes first")
                    target["status"] = "ARCHIVED"
                elif action == "restore" and target["status"] == "ARCHIVED":
                    if require_row(state, self.NODES, target["parent_id"])["status"] == "ARCHIVED":
                        raise ValueError("restore the parent node first")
                    target["status"] = "DRAFT"
                else:
                    raise ValueError("invalid node transition")
            change_row(row, actor, expected_version, update)
            return deepcopy(row)

    def templates(self, nid, scope):
        self.novels.get(nid)
        return [{"id": key, **deepcopy(value), "builtin": True} for key, value in BUILTIN_TEMPLATES.items()] + self.list(nid, scope, self.TEMPLATES)

    def create_template(self, nid, scope, actor, value):
        return self.create(nid, scope, actor, self.TEMPLATES, {**self._payload(value, PlanningTemplateIn), "status": "ACTIVE", "builtin": False})

    def _template(self, nid, scope, tid):
        row = BUILTIN_TEMPLATES.get(tid) or self.get(nid, scope, self.TEMPLATES, tid)
        return PlanningTemplateIn.model_validate({key: row[key] for key in PlanningTemplateIn.model_fields})

    def _proposal_row(self, nid, scope, actor, payload, state, execution_mode="USER_AUTHORED"):
        node = require_row(state, self.NODES, payload["node_id"])
        if require_row(state, self.GRAPHS, node["graph_id"])["status"] != "ACTIVE" or node["status"] == "ARCHIVED":
            raise ValueError("planning target is archived")
        expected = payload.pop("expected_node_version")
        if node["version"] != expected:
            raise CapabilityVersionConflict(deepcopy(node))
        if node["level"] in {"CHAPTER", "SCENE"} and payload["links"]["chapter_ids"] != node["links"]["chapter_ids"]:
            raise ValueError("proposal cannot rebind a chapter or scene node")
        sources, entities = self._validate_links(nid, scope, payload["fields"], payload["links"], state)
        return new_row(nid, scope, actor, {**payload, "graph_id": node["graph_id"], "target_version": expected, "ancestor_versions": {ancestor["id"]: ancestor["version"] for ancestor in self._ancestors(state, node)}, "status": "REVIEW", "sources": sources, "entity_sources": entities, "execution_mode": execution_mode, "privacy_state": "LOCAL_ONLY"})

    def create_proposal(self, nid, scope, actor, value):
        payload = self._payload(value, PlanningProposalIn)
        self.novels.get(nid)
        if payload["template_id"]:
            self._template(nid, scope, payload["template_id"])
        with self.store.transaction(nid, scope) as state:
            row = self._proposal_row(nid, scope, actor, payload, state)
            collection(state, self.PROPOSALS)[row["id"]] = row
            return deepcopy(row)

    def generate(self, nid, scope, actor, value):
        request = PlanningGenerateIn.model_validate(value.model_dump() if isinstance(value, BaseModel) else value)
        if request.adapter_id != MockStructuredPlanningAdapter.adapter_id:
            raise ValueError("planning adapter NOT_CONFIGURED; only explicit Mock is available")
        node = self.get(nid, scope, self.NODES, request.node_id)
        if node["version"] != request.expected_node_version:
            raise CapabilityVersionConflict(node)
        ancestors = self._ancestors(self.store.read(nid, scope), node)
        captured_ancestors = {ancestor["id"]: ancestor["version"] for ancestor in ancestors}
        captured_sources, captured_entities = self._validate_links(nid, scope, node["fields"], node["links"])
        output = MockStructuredPlanningAdapter().generate(PlanningAdapterRequest(node=node, ancestors=[{key: value for key, value in ancestor.items() if key != "history"} for ancestor in ancestors], template=self._template(nid, scope, request.template_id), instruction=request.instruction, candidate_count=request.candidate_count))
        # Validate the same public output schema before storing an entire batch atomically.
        output = PlanningAdapterOutput.model_validate(output.model_dump())
        rows = []
        with self.store.transaction(nid, scope) as state:
            self.assert_sources(nid, captured_sources)
            current_node = require_row(state, self.NODES, node["id"])
            if {ancestor["id"]: ancestor["version"] for ancestor in self._ancestors(state, current_node)} != captured_ancestors:
                raise StaleSourceError("planning ancestor context changed during adapter execution")
            if entity_sources(self, nid, scope, node["links"], state) != captured_entities:
                raise StaleSourceError("planning sources changed during adapter execution")
            for candidate in output.candidates:
                payload = PlanningProposalIn(node_id=node["id"], expected_node_version=node["version"], title=candidate.title, fields=candidate.fields, links=node["links"], rationale=candidate.rationale, template_id=request.template_id).model_dump()
                row = self._proposal_row(nid, scope, actor, payload, state, output.execution_mode)
                collection(state, self.PROPOSALS)[row["id"]] = row
                rows.append(deepcopy(row))
        return {"execution_mode": output.execution_mode, "items": rows}

    def proposals(self, nid, scope):
        state = self.store.read(nid, scope)
        self.novels.get(nid)
        return [self._decorate(nid, scope, row, state) for row in collection(state, self.PROPOSALS).values()]

    def proposal(self, nid, scope, pid):
        return self._decorate(nid, scope, self.get(nid, scope, self.PROPOSALS, pid))

    def compare(self, nid, scope, ids):
        if not 2 <= len(ids) <= 8 or len(set(ids)) != len(ids):
            raise ValueError("compare requires 2-8 different proposals")
        rows = [self.proposal(nid, scope, rid) for rid in ids]
        if len({row["node_id"] for row in rows}) != 1:
            raise ValueError("compare proposals for the same planning node")
        differences = {key: {row["id"]: row["fields"][key] for row in rows} for key in PlanningFields.model_fields if len({digest(row["fields"][key]) for row in rows}) > 1}
        return {"items": rows, "differences": differences, "target_node_id": rows[0]["node_id"]}

    def review(self, nid, scope, actor, item_id, action, expected_version):
        with self.store.transaction(nid, scope) as state:
            row = require_row(state, self.PROPOSALS, item_id)
            if row["version"] != expected_version:
                raise CapabilityVersionConflict(deepcopy(row))
            transitions = {"approve": ({"REVIEW"}, "APPROVED"), "reject": ({"REVIEW"}, "REJECTED"), "reopen": ({"REJECTED", "ARCHIVED"}, "REVIEW"), "archive": ({"REVIEW", "REJECTED", "APPROVED"}, "ARCHIVED")}
            if action not in transitions or row["status"] not in transitions[action][0]:
                raise ValueError("invalid planning review transition")
            if action == "approve":
                if require_row(state, self.GRAPHS, row["graph_id"])["status"] != "ACTIVE":
                    raise ValueError("planning graph is archived")
                self._assert_fresh(nid, scope, row, state)
                node = require_row(state, self.NODES, row["node_id"])
                def apply(target):
                    target.update(fields=deepcopy(row["fields"]), links=deepcopy(row["links"]), sources=deepcopy(row["sources"]), entity_sources=deepcopy(row["entity_sources"]), status="APPROVED", approved_proposal_id=row["id"])
                change_row(node, actor, row["target_version"], apply)
                applied_version = node["version"]
            def update(target):
                target["status"] = transitions[action][1]
                if action == "approve":
                    target["applied_node_version"] = applied_version
            change_row(row, actor, expected_version, update)
            return deepcopy(row)

    def restore(self, nid, scope, actor, pid, expected_version, historical_version):
        with self.store.transaction(nid, scope) as state:
            row = require_row(state, self.PROPOSALS, pid)
            old = next((entry for entry in row["history"] if entry.get("version") == historical_version), None)
            if old is None:
                raise FileNotFoundError("planning history version")
            # History content comes back for review with its original source fence.
            restored = {key: deepcopy(old[key]) for key in ("fields", "links", "title", "rationale", "sources", "entity_sources", "target_version", "ancestor_versions")}
            change_row(row, actor, expected_version, lambda target: target.update(restored, status="REVIEW", restored_from_version=historical_version))
            return deepcopy(row)

    def history(self, nid, scope, pid):
        return self.get(nid, scope, self.PROPOSALS, pid)["history"]

    def list_review_items(self, nid, scope):
        return [{**row, "domain": "planning", "source": "structured_planning", "preview": row["title"], "target": {"node_id": row["node_id"], "graph_id": row["graph_id"]}, "source_versions": row["sources"], "risk": "PLANNING_ONLY", "safe_batch": False, "allowed_actions": ["approve", "reject"] if row["status"] == "REVIEW" else ["reopen"] if row["status"] in {"REJECTED", "ARCHIVED"} else []} for row in self.proposals(nid, scope)]
