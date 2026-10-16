"""Experimental, durable creative teams. All outputs remain review artifacts.

The V1 DAG validator, agent output envelope and bounded local recipe transforms
are reused. No provider is dispatched here: deterministic execution establishes
contracts, never real-model literary quality. A node's receipt, artifact and
successor become durable in one scope transaction. Restart recovery never
silently replays a claimed operation whose outcome is unknown.
"""
from __future__ import annotations

import copy
import hashlib
import json
import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..agent_catalog import AGENTS
from ..services.agent_job_service import StructuredAgentOutput
from ..services.v1_capability_service import V1CapabilityService, WorkflowDefinitionIn
from ..workflow_recipes import execute_local_recipe_node
from .common import DomainService, StaleSourceError, now

_HOST_INSTANCE = str(uuid.uuid4())
_COLLECTION = "team_runs"
_TERMINAL = {"SUCCEEDED", "FAILED", "CANCELLED", "REJECTED"}


def _hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()


# Keep original roles' schemas/tool capabilities without mutating the V1 catalog.
_BASE_ROLES = {row["id"]: row for row in AGENTS}
ROLE_TEMPLATES = (
    {**_BASE_ROLES["planner"], "name": "Planner / Story Architect"},
    {**_BASE_ROLES["writer"], "name": "Writer"},
    {**_BASE_ROLES["editor"], "name": "Editor"},
    {**_BASE_ROLES["continuity"], "name": "Continuity Reviewer", "requires_approval": True},
    {"id": "screenwriter", "name": "Screenwriter", "prompt_role": "screenwriter", "tools": ["chapter.read", "screenplay.propose"], "output_schema": "screenplay_draft_proposal", "requires_approval": True},
    {**_BASE_ROLES["director"], "name": "Director / Shot Planner"},
    {**_BASE_ROLES["artist"], "name": "Art Planner"},
    {"id": "media_coordinator", "name": "Media Coordinator", "prompt_role": "media_coordinator", "tools": ["storyboard.read", "image_task.propose"], "output_schema": "media_task_proposal", "requires_approval": True},
)
_ROLES = {row["id"]: row for row in ROLE_TEMPLATES}


def _recipe(rid: str, name: str, steps: list[tuple[str, str, str]]) -> dict:
    nodes = [{"id": nid, "name": title, "type": "agent_task", "config": {"agent_role": role}} for nid, role, title in steps]
    nodes.append({"id": "human_approve", "name": "Human Approve", "type": "manual_approval", "config": {}})
    return {"id": rid, "name": name, "version": 1, "nodes": nodes,
            "edges": [{"source": left["id"], "target": right["id"]} for left, right in zip(nodes, nodes[1:])]}


TEAM_RECIPES = (
    _recipe("outline_chapter_editor", "Outline → Chapter Draft → Editor Review → Human Approve", [
        ("outline", "planner", "Outline"), ("chapter_draft", "writer", "Chapter Draft"), ("editor_review", "editor", "Editor Review")]),
    _recipe("continuity_fix", "Chapter → Continuity Review → Fix Proposal → Human Approve", [
        ("continuity_review", "continuity", "Continuity Review"), ("fix_proposal", "editor", "Fix Proposal")]),
    _recipe("screenplay_shots", "Novel/Chapter → Screenplay Draft → Shot Proposal → Human Approve", [
        ("screenplay_draft", "screenwriter", "Screenplay Draft"), ("shot_proposal", "director", "Shot Proposal")]),
    _recipe("storyboard_image_tasks", "Storyboard Planning → Image Task Proposal → Human Approve", [
        ("storyboard", "artist", "Storyboard Planning"), ("image_tasks", "media_coordinator", "Image Task Proposal")]),
)
_RECIPES = {row["id"]: row for row in TEAM_RECIPES}


class TeamRunIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    recipe_id: str = Field(min_length=1, max_length=80)
    chapter_ids: list[str] = Field(default_factory=list, max_length=200)
    instruction: str = Field(default="", max_length=8000)
    source_text: str = Field(default="", max_length=20000)

    @model_validator(mode="after")
    def input_present(self):
        if self.recipe_id not in _RECIPES:
            raise ValueError("unknown team recipe")
        if not (self.chapter_ids or self.source_text or self.instruction):
            raise ValueError("a chapter, source text or instruction is required")
        if len(set(self.chapter_ids)) != len(self.chapter_ids):
            raise ValueError("duplicate chapter ids")
        return self


class TeamOutput(StructuredAgentOutput):
    model_config = ConfigDict(extra="forbid")
    summary: str = Field(max_length=8000)
    proposals: list[dict] = Field(default_factory=list, max_length=100)
    findings: list[dict] = Field(default_factory=list, max_length=100)


class TeamService(DomainService):
    def __init__(self, store, novels, chapters, *, host_id: str | None = None, branch_chapters=None):
        super().__init__(store, novels, chapters)
        self.host_id = host_id or _HOST_INSTANCE
        # Optional server-owned factory: scope -> genuinely branch-bound reader.
        # The ordinary chapter service reads base manuscript and is not a branch
        # snapshot. Never label that content as belonging to a branch.
        self.branch_chapters = branch_chapters

    def _source_domain(self, scope):
        if scope.get("mode") != "collaboration":
            return self
        if self.branch_chapters is None:
            raise StaleSourceError("branch chapter snapshots are unavailable; use explicit source text or local mode")
        return DomainService(self.store, self.novels, self.branch_chapters(copy.deepcopy(scope)))

    def _assert_run_sources(self, nid, row):
        if row["sources"]:
            self._source_domain(row["execution_scope"]["scope"]).assert_sources(nid, row["sources"])

    @staticmethod
    def catalog() -> dict:
        return {"schema_version": 1, "experimental": True, "roles": copy.deepcopy(ROLE_TEMPLATES),
                "recipes": copy.deepcopy(TEAM_RECIPES), "execution_modes": ["contract"],
                "verification": "CONTRACT_VERIFIED", "model_called": False, "applied": False}

    def _view(self, nid: str, row: dict) -> dict:
        result = copy.deepcopy(row)
        try:
            self._assert_run_sources(nid, result)
            result["stale"] = False
        except (StaleSourceError, FileNotFoundError, KeyError):
            result["stale"] = True
        result["recovery_required"] = any(state["status"] == "WORKING" and state.get("host_id") != self.host_id
                                           for state in result["node_states"].values())
        return result

    def list_runs(self, nid, scope):
        rows = [self._view(nid, row) for row in self.list(nid, scope, _COLLECTION)]
        return {"items": rows, "total": len(rows)}

    def get_run(self, nid, scope, run_id):
        return self._view(nid, self.get(nid, scope, _COLLECTION, run_id))

    def create_run(self, nid, scope, actor, body: TeamRunIn | dict):
        body = TeamRunIn.model_validate(body)
        source_domain = self._source_domain(scope) if body.chapter_ids else self
        source_versions = source_domain.sources(nid, body.chapter_ids)
        chapters = [source_domain.chapters.get(cid) for cid in body.chapter_ids]
        source_text = body.source_text or "\n\n".join(str(row.get("content", "")) for row in chapters) or body.instruction
        if len(source_text) > 200000:
            raise ValueError("team input exceeds 200000 characters; select fewer chapters")
        source_domain.assert_sources(nid, source_versions)
        recipe = copy.deepcopy(_RECIPES[body.recipe_id])
        definition = WorkflowDefinitionIn(novel_id=nid, title=recipe["name"], nodes=recipe["nodes"], edges=recipe["edges"]).model_dump(mode="json")
        definition["topological_order"] = V1CapabilityService._workflow_order(definition["nodes"], definition["edges"])
        payload = {
            "recipe_id": body.recipe_id, "recipe_version": recipe["version"], "definition_snapshot": definition,
            "execution_scope": {"project_id": nid, "workspace_id": scope.get("workspace_id", "local"),
                                "branch_id": scope.get("branch_id", "local"), "scope": copy.deepcopy(scope)},
            "sources": source_versions, "source_text": source_text, "instruction": body.instruction,
            "execution_mode": "contract", "verification": "CONTRACT_VERIFIED", "model_called": False,
            "external_calls": 0, "applied": False, "privacy_state": "LOCAL_ONLY", "status": "RUNNING",
            "attempt": 1, "generation": 1, "artifacts": {}, "review": None,
            "node_states": {node["id"]: {"status": "PENDING", "attempt": 0, "receipt": None, "error": None} for node in definition["nodes"]},
        }
        payload["context_hash"] = _hash({key: payload[key] for key in ("recipe_id", "recipe_version", "execution_scope", "sources", "source_text", "instruction")})
        self._advance(payload)
        return self.create(nid, scope, actor, _COLLECTION, payload)

    @staticmethod
    def _advance(row):
        if row["status"] in _TERMINAL | {"PAUSED"}:
            return
        nodes = {node["id"]: node for node in row["definition_snapshot"]["nodes"]}
        states = row["node_states"]
        incoming = {node_id: [] for node_id in nodes}
        for edge in row["definition_snapshot"]["edges"]:
            incoming[edge["target"]].append(edge["source"])
        row["status"] = "RUNNING"
        for node_id in row["definition_snapshot"]["topological_order"]:
            state = states[node_id]
            if state["status"] == "RESULT_READY":
                # A recorded receipt survives a host stopping before advancement.
                receipt, artifact = state.get("receipt"), row["artifacts"].get(node_id)
                if (not receipt or not artifact or artifact.get("receipt_id") != receipt.get("id")
                        or receipt.get("context_hash") != row["context_hash"]
                        or receipt.get("output_hash") != _hash(artifact.get("output"))
                        or artifact.get("sources") != row["sources"]
                        or artifact.get("scope") != row["execution_scope"]):
                    raise ValueError("team output receipt is incomplete or inconsistent")
                state["status"] = "SUCCEEDED"
            if state["status"] == "SUCCEEDED":
                continue
            if state["status"] == "FAILED":
                row["status"] = "FAILED"
                break
            if any(states[parent]["status"] != "SUCCEEDED" for parent in incoming[node_id]):
                continue
            if nodes[node_id]["type"] == "manual_approval":
                state["status"] = "WAITING_APPROVAL"
                row["status"] = "WAITING_APPROVAL"
            elif state["status"] == "PENDING":
                state["status"] = "READY"
        if all(state["status"] == "SUCCEEDED" for state in states.values()):
            row["status"] = "SUCCEEDED"
        row["current_node_ids"] = [nid for nid, state in states.items() if state["status"] in {"READY", "WORKING", "WAITING_APPROVAL"}]

    def claim_node(self, nid, scope, actor, run_id, node_id, expected_version):
        def claim(row):
            self._assert_run_sources(nid, row)
            state = row["node_states"].get(node_id)
            if row["status"] != "RUNNING" or not state or state["status"] != "READY":
                raise ValueError("team node is not ready to claim")
            state.update(status="WORKING", execution_token=str(uuid.uuid4()), host_id=self.host_id,
                         claimed_by=actor, claimed_at=now(), context_hash=row["context_hash"],
                         generation=row["generation"], attempt=state["attempt"] + 1, error=None)
        return self.mutate(nid, scope, actor, _COLLECTION, run_id, expected_version, claim)

    @staticmethod
    def _validate_output(row, node_id, output):
        parsed = TeamOutput.model_validate(output).model_dump(mode="json", by_alias=True)
        node = next(node for node in row["definition_snapshot"]["nodes"] if node["id"] == node_id)
        role_id = node["config"]["agent_role"]
        if (parsed["schema"] != _ROLES[role_id]["output_schema"] or parsed["agent_id"] != role_id
                or parsed["context_hash"] != row["context_hash"]):
            raise ValueError("team output envelope does not match the claimed role and sources")
        if len(json.dumps(parsed, ensure_ascii=False, allow_nan=False).encode()) > 128000:
            raise ValueError("team output exceeds the 128000 byte limit")
        return parsed

    def complete_node(self, nid, scope, actor, run_id, node_id, expected_version, execution_token,
                      context_hash, output=None, error=None):
        if (output is None) == (error is None):
            raise ValueError("supply exactly one of output or error")
        def complete(row):
            self._assert_run_sources(nid, row)
            state = row["node_states"].get(node_id)
            if (row["status"] != "RUNNING" or not state or state["status"] != "WORKING"
                    or state.get("execution_token") != execution_token or state.get("context_hash") != context_hash
                    or row["context_hash"] != context_hash or state.get("generation") != row["generation"]
                    or state.get("claimed_by") != actor or state.get("host_id") != self.host_id):
                raise ValueError("team callback is no longer authorized for this attempt")
            if error is not None:
                state.update(status="FAILED", error={"code": "NODE_EXECUTION_FAILED", "message": "The node did not complete; explicitly retry after review."}, finished_at=now())
                row["status"] = "FAILED"
                row["current_node_ids"] = []
                return
            parsed = self._validate_output(row, node_id, output)
            receipt = {"id": str(uuid.uuid4()), "execution_token": execution_token, "context_hash": context_hash,
                       "output_hash": _hash(parsed), "received_at": now(), "attempt": state["attempt"]}
            # One atomic scope transaction: there is no durable success without
            # its output, or durable output without its deduplication receipt.
            row["artifacts"][node_id] = {"id": f"{run_id}:{node_id}:{state['attempt']}", "node_id": node_id,
                "status": "PROPOSED", "output": parsed, "sources": copy.deepcopy(row["sources"]),
                "scope": copy.deepcopy(row["execution_scope"]), "receipt_id": receipt["id"],
                "verification": "CONTRACT_VERIFIED", "model_called": False, "applied": False}
            state.update(status="RESULT_READY", receipt=receipt, finished_at=now(), error=None)
            self._advance(row)
        return self.mutate(nid, scope, actor, _COLLECTION, run_id, expected_version, complete)

    def _contract_output(self, row, node_id):
        node = next(node for node in row["definition_snapshot"]["nodes"] if node["id"] == node_id)
        role_id = node["config"]["agent_role"]
        # The bounded V1 transformer works on explicit excerpts. Retain a full
        # immutable source digest and disclose truncation; do not invent prose.
        source = row["source_text"]
        excerpt = "\n".join(source[:20000].splitlines()[:100]) or row["instruction"] or "Review the supplied source."
        kind = "shot_proposals" if role_id in {"director", "artist", "media_coordinator"} else "draft_prepare"
        transformed = execute_local_recipe_node(kind, {"source_text": excerpt}, {}, {})
        transformed.update(role=role_id, source_excerpt=excerpt != source, source_digest=_hash(source),
                           instruction=row["instruction"], upstream_artifact_ids=[artifact["id"] for artifact in row["artifacts"].values()],
                           semantic_quality="NOT_VERIFIED", proposal_only=True)
        if role_id in {"editor", "continuity"}:
            transformed = {"review_input": transformed, "checks_executed": [], "semantic_quality": "NOT_VERIFIED",
                           "note": "Input prepared for editorial/continuity review; no semantic model executed.", "applied": False}
        return {"schema": _ROLES[role_id]["output_schema"], "agent_id": role_id,
                "summary": "Local contract artifact prepared from supplied input. No model called; human review required.",
                "proposals": [transformed], "findings": [], "context_hash": row["context_hash"]}

    def execute(self, nid, scope, actor, run_id, expected_version, check_authority=None):
        """Advance locally to the human gate. Never run paid/provider APIs."""
        row = self.get_run(nid, scope, run_id)
        # Claim performs the version check atomically, including concurrent starts.
        if row["version"] != expected_version:
            from .common import check_version
            check_version(row, expected_version)
        if row["status"] != "RUNNING":
            raise ValueError("only a running team recipe can execute")
        for _ in row["definition_snapshot"]["topological_order"]:
            node_id = next((key for key, state in row["node_states"].items() if state["status"] == "READY"), None)
            if node_id is None:
                break
            if check_authority is not None:
                check_authority()
            row = self.claim_node(nid, scope, actor, run_id, node_id, row["version"])
            state = row["node_states"][node_id]
            try:
                output = self._contract_output(row, node_id)
            except Exception:
                return self.complete_node(nid, scope, actor, run_id, node_id, row["version"], state["execution_token"], row["context_hash"], error="CONTRACT_EXECUTION_FAILED")
            if check_authority is not None:
                check_authority()
            row = self.complete_node(nid, scope, actor, run_id, node_id, row["version"], state["execution_token"], row["context_hash"], output=output)
        return row

    def transition(self, nid, scope, actor, run_id, action, expected_version, check_authority=None):
        if action == "execute":
            return self.execute(nid, scope, actor, run_id, expected_version, check_authority=check_authority)
        if action == "recover":
            return self.recover(nid, scope, actor, run_id, expected_version)
        def change(row):
            status = row["status"]
            if action == "pause":
                if status not in {"RUNNING", "WAITING_APPROVAL"}:
                    raise ValueError("only an active team recipe can pause")
                row["status"] = "PAUSED"
            elif action == "resume":
                if status != "PAUSED":
                    raise ValueError("only a paused team recipe can resume")
                self._assert_run_sources(nid, row)
                row["status"] = "RUNNING"
            elif action == "cancel":
                if status in _TERMINAL:
                    raise ValueError("a terminal team recipe cannot cancel")
                row["status"] = "CANCELLED"
            elif action == "retry":
                if status not in {"FAILED", "CANCELLED"}:
                    raise ValueError("only failed or cancelled team recipes can retry")
                self._assert_run_sources(nid, row)
                for state in row["node_states"].values():
                    if state["status"] in {"FAILED", "WORKING"}:
                        state.update(status="PENDING", execution_token=None, receipt=None, error=None)
                row.update(status="RUNNING", attempt=row["attempt"] + 1)
            else:
                raise ValueError("unsupported team action")
            row["generation"] += 1
            # Pause/cancel invalidate callbacks immediately. An in-flight output
            # may have been produced, so resuming requires explicit retry.
            for state in row["node_states"].values():
                if state["status"] == "WORKING":
                    state.update(status="FAILED", execution_token=None,
                                 error={"code": "INTERRUPTED", "replay_safe": False})
            self._advance(row)
            if row["status"] in _TERMINAL | {"PAUSED"}:
                row["current_node_ids"] = []
        return self.mutate(nid, scope, actor, _COLLECTION, run_id, expected_version, change)

    def recover(self, nid, scope, actor, run_id, expected_version):
        def reconcile(row):
            if row["status"] in _TERMINAL:
                raise ValueError("terminal team recipe does not require recovery")
            working = [state for state in row["node_states"].values() if state["status"] == "WORKING"]
            if any(state.get("host_id") == self.host_id for state in working):
                raise ValueError("this host still owns the active attempt; pause or cancel it explicitly")
            self._assert_run_sources(nid, row)
            row["generation"] += 1
            for state in working:
                state.update(status="FAILED", execution_token=None,
                             error={"code": "INTERRUPTED", "replay_safe": False}, finished_at=now())
            row["recovered_at"] = now()
            if working:
                row["status"] = "FAILED"
                row["current_node_ids"] = []
            else:
                self._advance(row)
        return self.mutate(nid, scope, actor, _COLLECTION, run_id, expected_version, reconcile)

    def list_review_items(self, nid, scope):
        items = []
        for row in self.list_runs(nid, scope)["items"]:
            if row["status"] not in {"WAITING_APPROVAL", "SUCCEEDED", "REJECTED"}:
                continue
            review_status = {"WAITING_APPROVAL": "PENDING", "SUCCEEDED": "APPROVED", "REJECTED": "REJECTED"}[row["status"]]
            items.append({"id": row["id"], "domain": "agent_team", "source": "team_recipe", "novel_id": nid,
                "scope": copy.deepcopy(scope), "version": row["version"], "source_versions": row["sources"],
                "source_hash": row["context_hash"], "created_by": row["created_by"], "actor": row.get("updated_by", row["created_by"]),
                "status": review_status, "stale": row["stale"], "risk": "PROPOSAL_ONLY", "privacy_state": "LOCAL_ONLY",
                "preview": row["definition_snapshot"]["title"], "target": {"run_id": row["id"], "node_id": "human_approve"},
                "allowed_actions": (["approve", "reject"] if review_status == "PENDING" else ["reopen"]), "batch_safe": False})
        return items

    def review(self, nid, scope, actor, item_id, action, expected_version):
        def decide(row):
            state = row["node_states"]["human_approve"]
            if action == "reopen":
                if row["status"] not in {"SUCCEEDED", "REJECTED"}:
                    raise ValueError("only a reviewed recipe can reopen")
                state["status"] = "WAITING_APPROVAL"
                row["status"] = "WAITING_APPROVAL"
                artifact_status = "PROPOSED"
            elif action in {"approve", "reject"}:
                if row["status"] != "WAITING_APPROVAL" or state["status"] != "WAITING_APPROVAL":
                    raise ValueError("team recipe is not awaiting human approval")
                if action == "approve":
                    self._assert_run_sources(nid, row)
                state["status"] = "SUCCEEDED" if action == "approve" else "REJECTED"
                row["status"] = "SUCCEEDED" if action == "approve" else "REJECTED"
                artifact_status = "APPROVED" if action == "approve" else "REJECTED"
            else:
                raise ValueError("unsupported team review action")
            for artifact in row["artifacts"].values():
                artifact["status"] = artifact_status
            row["review"] = {"action": action, "actor": actor, "at": now(), "source_hash": row["context_hash"]}
            row["generation"] += 1
            row["current_node_ids"] = ["human_approve"] if action == "reopen" else []
        return self.mutate(nid, scope, actor, _COLLECTION, item_id, expected_version, decide)
