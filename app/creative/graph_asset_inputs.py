"""Schema-3 input fences over the existing scope, asset and project owners.

No asset, queue or workflow state is owned here. Scope writes take the original
raw scope lease before asset -> project leases; guards never invert that order.
"""
from __future__ import annotations

from contextlib import contextmanager, ExitStack
from contextvars import ContextVar
from copy import deepcopy

from ..experimental.common import StaleSourceError
from ..experimental.store import canonical
from .graph_models import AssetParameters, MediaCandidatePort, validate_output_ports
from .project_store import BINDING, COLLECTIONS

_phase = ContextVar("creative_graph_asset_input_phase", default=None)


class GraphAssetInputs:
    def __init__(self, service):
        self.service, self.store, self.workspace = service, service.store, service.workspace

    def in_phase(self, nid, scope, actor):
        phase = _phase.get()
        return bool(phase and phase["service"] is self.service and phase["novel_id"] == nid
            and phase["scope"] == scope and phase["actor"] == actor)

    @contextmanager
    def phase(self, nid, scope, actor, guard, *, writable=False):
        """Yield the original incarnation view under fixed original assets.

        A writable phase is an explicit shared raw transaction. It performs the
        same incarnation-retention merge as CreativeProjectStore.transaction;
        it never opens another transaction while holding an asset lease.
        """
        key = self.store.key(nid, scope)
        if self.in_phase(nid, scope, actor):
            current = _phase.get()
            if writable and not current["writable"]:
                raise ValueError("CREATIVE_GRAPH_ASSET_READ_PHASE_MUTATION_DENIED")
            guard()
            yield current["state"]
            guard()
            return
        if (key in getattr(self.store._local, "active", {})
                or key in getattr(self.store.store._local, "active", {})
                or nid in getattr(self.store._local, "owners", {})):
            raise ValueError("CREATIVE_GRAPH_ASSET_PHASE_ORDER_INVALID")
        guard()
        # Keep asset/project leases through the raw owner's final atomic commit.
        # The stack is outside that transaction only for lease release ordering.
        with ExitStack() as lifecycle:
            with self.store.store.transaction(nid, scope) as raw:
                # Resolve briefly, releasing the project owner before asset locks.
                incarnation = self.store.incarnation(nid)
                lifecycle.enter_context(self.workspace._asset_scope(nid, scope))
                if self.store.incarnation(nid) != incarnation:
                    raise StaleSourceError("CREATIVE_GRAPH_AUTHORITY_CHANGED")
                state = self.store._view(raw, incarnation)
                before = canonical(state)
                if not hasattr(self.store._local, "active"):
                    self.store._local.active = {}
                self.store._local.active[key] = state
                token = _phase.set({"service": self.service, "novel_id": nid,
                    "scope": deepcopy(scope), "actor": actor, "state": state,
                    "writable": writable})
                try:
                    guard()
                    yield state
                    guard()
                    if self.store.incarnation(nid) != incarnation:
                        raise StaleSourceError("CREATIVE_GRAPH_AUTHORITY_CHANGED")
                    if not writable:
                        if canonical(state) != before:
                            raise ValueError("CREATIVE_GRAPH_ASSET_READ_PHASE_MUTATION_DENIED")
                    else:
                        for name in COLLECTIONS:
                            rows = state["collections"].get(name, {})
                            if any(not isinstance(row, dict) or row.get(BINDING) != incarnation for row in rows.values()):
                                raise ValueError("CREATIVE_PROJECT_BINDING_INVALID")
                            retained = {rid: row for rid, row in raw["collections"].get(name, {}).items()
                                if not isinstance(row, dict) or row.get(BINDING) != incarnation}
                            if retained:
                                state["collections"][name] = {**retained, **rows}
                        self.service._capacity(state)
                        raw.clear()
                        raw.update(deepcopy(state))
                finally:
                    _phase.reset(token)
                    self.store._local.active.pop(key, None)

    def transaction(self, nid, scope, actor, guard):
        return self.phase(nid, scope, actor, guard, writable=True)

    def _read(self, nid, scope, reference, guard):
        expected = AssetParameters.model_validate(reference).model_dump()
        guard()
        # Passing no actor is intentional: private generation candidates are
        # not graph ASSET_REF inputs, including the current actor's candidates.
        row = self.workspace._row(nid, scope, expected["asset_id"])
        if row.get("_owner_actor_id"):
            raise ValueError("CREATIVE_GRAPH_PRIVATE_ASSET_INPUT_DENIED")
        if (row["version"], row["sha256"], row["kind"]) != (
                expected["version"], expected["digest"], expected["kind"]):
            raise StaleSourceError("CREATIVE_GRAPH_EXTERNAL_REFERENCE_CHANGED")
        self.workspace.assets.content(row["id"], branch_id=scope.get("branch_id"))
        guard()
        return expected

    def read(self, nid, scope, actor, reference, guard):
        """Return a verified four-field reference, never binary/cache metadata."""
        if self.in_phase(nid, scope, actor):
            return self._read(nid, scope, reference, guard)
        with self.phase(nid, scope, actor, guard):
            return self._read(nid, scope, reference, guard)

    def read_candidate(self, nid, scope, actor, candidate, guard, *, graph_binding=None):
        """Verify an actor-private candidate without making it an ASSET_REF."""
        value = MediaCandidatePort.model_validate(candidate).model_dump()
        if not self.in_phase(nid, scope, actor):
            with self.phase(nid, scope, actor, guard):
                return self.read_candidate(nid, scope, actor, value, guard, graph_binding=graph_binding)
        guard()
        expected = value["asset"]
        asset = self.workspace.assets.get(expected["asset_id"], branch_id=scope.get("branch_id"), actor_id=actor)
        origin = asset.get("_studio_result_origin")
        if (asset.get("novel_id") != nid or asset.get("branch_id") != scope.get("branch_id")
                or asset.get("_owner_actor_id") != actor
                or (asset.get("version"), asset.get("sha256"), asset.get("kind")) != (
                    expected["version"], expected["digest"], expected["kind"])
                or not isinstance(origin, dict) or origin.get("contract") != "studio-production-result/1"
                or origin.get("job_id") != value["job_id"]
                or origin.get("actor") != actor or origin.get("request_digest") != value["request_digest"]
                or origin.get("scope_key") != self.store.key(nid, scope)
                or origin.get("incarnation") != self.store.incarnation(nid)
                or graph_binding is not None and origin.get("graph_binding") != graph_binding
                or value["owner"] == "timeline" and (graph_binding is None
                    or origin.get("operation_id") != "m9.timeline.multitrack" or expected["kind"] != "video")
                or asset.get("source_job_id") != value["job_id"]):
            raise StaleSourceError("CREATIVE_GRAPH_MEDIA_CANDIDATE_CHANGED")
        self.workspace.assets.content(asset["id"], branch_id=scope.get("branch_id"), actor_id=actor)
        guard()
        return value

    def validate_document(self, nid, scope, actor, row, state, guard):
        """Pure scope binding for an existing publication source lease.

        Deliberately reads no assets and starts no phase. The original production
        callback separately checks its actual ASSET sources under its own lease.
        """
        guard()
        graph = self.service._owned(nid, scope, actor, self.service.GRAPHS, row["graph_id"], state)
        saved = self.service._owned(nid, scope, actor, self.service.RUNS, row["id"], state)
        if (graph["version"] != row["graph_version"] or graph["definition_digest"] != row["graph_digest"]
                or row.get(BINDING) != graph[BINDING] or saved.get("graph_version") != row["graph_version"]
                or saved.get("graph_digest") != row["graph_digest"]):
            raise StaleSourceError("CREATIVE_GRAPH_RUN_DEFINITION_CHANGED")
        selected = row.get("selected_closure", [])
        nodes = [node for node in graph["definition"]["nodes"] if node["id"] in selected]
        edges = [edge for edge in graph["definition"]["edges"]
            if edge["source_node_id"] in selected and edge["target_node_id"] in selected]
        if (row.get("typed_nodes") != nodes or row.get("typed_edges") != edges
                or saved.get("typed_nodes") != nodes or saved.get("typed_edges") != edges):
            raise StaleSourceError("CREATIVE_GRAPH_RUN_BINDING_CHANGED")
        for node in nodes:
            if node["definition_id"] == "asset_reference":
                AssetParameters.model_validate(node["parameters"])
        by_id = {node["id"]: node for node in nodes}
        for node_id, output in row.get("typed_outputs", {}).items():
            node = by_id.get(node_id)
            if node is None:
                raise ValueError("CREATIVE_GRAPH_OUTPUT_SCHEMA_INVALID")
            if node["definition_id"] in {"asset_reference", "media_review"}:
                if set(output) != {"asset"}:
                    raise ValueError("CREATIVE_GRAPH_OUTPUT_SCHEMA_INVALID")
                AssetParameters.model_validate(output["asset"])
            elif node["definition_id"] in {"media_generate", "timeline_export"}:
                if set(output) != {"candidate"}:
                    raise ValueError("CREATIVE_GRAPH_OUTPUT_SCHEMA_INVALID")
                validate_output_ports(node["definition_id"], output, schema_version=3)
        guard()
        return saved

    def states(self, nid, scope, actor, definition, guard):
        result = []
        for node in definition["nodes"]:
            if node["definition_id"] != "asset_reference":
                continue
            try:
                self.read(nid, scope, actor, node["parameters"], guard)
                state = "CURRENT"
            except StaleSourceError:
                state = "STALE"
            except (FileNotFoundError, ValueError, KeyError):
                state = "UNAVAILABLE"
            result.append({"node_id": node["id"], "state": state})
        guard()
        return result

    def current(self, nid, scope, actor, row, guard, state=None):
        """Validate selected external inputs and already reviewed graph outputs."""
        definition = {"nodes": row.get("typed_nodes", [])}
        if any(item["state"] != "CURRENT" for item in self.states(nid, scope, actor, definition, guard)):
            raise StaleSourceError("CREATIVE_GRAPH_EXTERNAL_REFERENCE_CHANGED")
        nodes = {node["id"]: node for node in definition["nodes"]}
        for node_id, output in row.get("typed_outputs", {}).items():
            node = nodes.get(node_id)
            if node is None:
                raise ValueError("CREATIVE_GRAPH_OUTPUT_SCHEMA_INVALID")
            if node["definition_id"] == "asset_reference":
                if output != {"asset": node["parameters"]}:
                    raise StaleSourceError("CREATIVE_GRAPH_ASSET_OUTPUT_BINDING_CHANGED")
                self.read(nid, scope, actor, output["asset"], guard)
            elif node["definition_id"] == "media_review":
                if set(output) != {"asset"}:
                    raise ValueError("CREATIVE_GRAPH_OUTPUT_SCHEMA_INVALID")
                self.read(nid, scope, actor, output["asset"], guard)
        guard()
        return row

    def current_under_asset_lease(self, nid, scope, actor, row, guard):
        """Check all graph inputs inside an original publication asset lease.

        Starts no scope read, transaction or phase. The caller must first check
        the graph's pure document binding under its raw source lease and supply
        a Host/incarnation-only guard. Candidate ports are checked by their
        original job owner and may already have been promoted during recovery.
        """
        binding = getattr(self.workspace.assets._scope, "binding", None)
        if binding != {"novel_id": nid, "branch_id": scope.get("branch_id"),
                "incarnation": row.get(BINDING), "scope_key": self.store.key(nid, scope)}:
            raise ValueError("CREATIVE_GRAPH_ORIGINAL_ASSET_LEASE_REQUIRED")
        guard()
        selected = set(row.get("selected_closure", []))
        nodes = {node["id"]: node for node in row.get("typed_nodes", []) if node["id"] in selected}
        for node in nodes.values():
            if node["definition_id"] == "asset_reference":
                self._read(nid, scope, node["parameters"], guard)
        for node_id, output in row.get("typed_outputs", {}).items():
            node = nodes.get(node_id)
            if node is not None and node["definition_id"] == "media_review":
                if set(output) != {"asset"}:
                    raise ValueError("CREATIVE_GRAPH_OUTPUT_SCHEMA_INVALID")
                self._read(nid, scope, output["asset"], guard)
        guard()
        return row

    def execute_reference(self, nid, scope, actor, node, guard):
        if node.get("definition_id") != "asset_reference":
            raise ValueError("CREATIVE_GRAPH_ASSET_NODE_REQUIRED")
        return {"asset": self.read(nid, scope, actor, node["parameters"], guard)}
