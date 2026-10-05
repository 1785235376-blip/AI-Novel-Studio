"""Optional, real vector abstraction. Unconfigured means no embedding search.

The only bundled implementation is an explicitly labelled deterministic mock.
Provider implementations are trusted host dependencies, never user-supplied
executable plugins; remote calls require a final authoritative egress guard.
"""
from __future__ import annotations

import copy
import hashlib
import math
from dataclasses import dataclass
from typing import Literal, Protocol
from uuid import uuid4

from pydantic import Field, model_validator

from .common import DomainService, StaleSourceError, check_version, now, snapshot
from .media import StrictModel, digest, scene_sources


class EmbeddingCapability(StrictModel):
    provider_id: str = Field(min_length=1, max_length=240)
    model_id: str = Field(min_length=1, max_length=240)
    model_revision: str = Field(min_length=1, max_length=240)
    dimensions: int = Field(ge=1, le=8192)
    local: bool
    input_types: list[Literal["TEXT", "IMAGE"]] = Field(min_length=1, max_length=2)
    verification: Literal["MOCK_ONLY", "CONTRACT_VERIFIED"]


@dataclass(frozen=True)
class EmbeddingInput:
    kind: str
    text: str = ""
    image_bytes: bytes | None = None


class EmbeddingProvider(Protocol):
    capability: EmbeddingCapability

    def embed(self, inputs: list[EmbeddingInput]) -> list[list[float]]: ...


class MockEmbeddingProvider:
    """Hash vectors for exercising storage/search contracts, not semantics."""
    capability = EmbeddingCapability(provider_id="mock-embedding", model_id="mock-sha256", model_revision="1",
        dimensions=8, local=True, input_types=["TEXT", "IMAGE"], verification="MOCK_ONLY")

    def embed(self, inputs):
        return [[(byte - 127.5) / 127.5 for byte in hashlib.sha256(
            value.text.encode() if value.kind == "TEXT" else value.image_bytes or b"").digest()[:8]] for value in inputs]


class EntityRef(StrictModel):
    entity_type: Literal["ASSET", "CHARACTER", "SCENE"]
    entity_id: str = Field(min_length=1, max_length=240)
    screenplay_id: str | None = Field(default=None, max_length=240)

    @model_validator(mode="after")
    def scene_scope(self):
        if self.entity_type == "SCENE" and not self.screenplay_id:
            raise ValueError("scene embedding requires its screenplay")
        if self.entity_type != "SCENE" and self.screenplay_id:
            raise ValueError("screenplay only applies to scene embeddings")
        return self


class EmbeddingIndexIn(StrictModel):
    title: str = Field(min_length=1, max_length=240)
    entities: list[EntityRef] = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def distinct(self):
        keys = [digest(e.model_dump()) for e in self.entities]
        if len(keys) != len(set(keys)):
            raise ValueError("embedding entity references must be distinct")
        return self


class EmbeddingQueryIn(StrictModel):
    index_id: str = Field(min_length=1, max_length=240)
    text: str = Field(min_length=1, max_length=12000)
    limit: int = Field(default=10, ge=1, le=100)


class VectorRecord(StrictModel):
    id: str
    index_id: str
    index_version: int = Field(ge=1)
    entity: EntityRef
    source_version: int | str | None
    source_digest: str
    provider_id: str
    model_id: str
    model_revision: str
    dimensions: int
    vector: list[float]
    vector_digest: str
    verification: Literal["MOCK_ONLY", "CONTRACT_VERIFIED"]
    status: Literal["ACTIVE", "INVALIDATED", "REMOVED"] = "ACTIVE"


class EmbeddingService(DomainService):
    INDEXES, VECTORS = "embedding_indexes", "embedding_vectors"

    def __init__(self, store, novels, chapters, provider=None, assets=None, screenplays=None):
        super().__init__(store, novels, chapters)
        self.provider, self.assets, self.screenplays = provider, assets, screenplays

    def status(self):
        return {"status": "NOT_CONFIGURED" if self.provider is None else "CONFIGURED",
                "capability": self._capability().model_dump() if self.provider else None,
                "lexical_fallback": False, "precision_claim": "VECTOR_SIMILARITY_ONLY"}

    def _capability(self):
        if self.provider is None:
            raise ValueError("EMBEDDING_NOT_CONFIGURED")
        return EmbeddingCapability.model_validate(self.provider.capability)

    def _source(self, nid, scope, ref):
        ref = EntityRef.model_validate(ref).model_dump()
        kind, eid = ref["entity_type"], ref["entity_id"]
        if kind == "ASSET":
            if self.assets is None:
                raise ValueError("EMBEDDING_ASSET_SERVICE_NOT_CONFIGURED")
            row = self.assets.get(eid, branch_id=scope.get("branch_id"))
            if row.get("novel_id") != nid or row.get("branch_id") != scope.get("branch_id"):
                raise FileNotFoundError(eid)
            if row.get("kind") != "image":
                raise ValueError("EMBEDDING_IMAGE_ASSET_REQUIRED")
            data = self.assets.content(eid, branch_id=scope.get("branch_id"))
            return {"version": row["version"], "digest": row["sha256"]}, EmbeddingInput("IMAGE", image_bytes=data)
        if kind == "CHARACTER":
            row = next((r for r in self.novels.data_set(nid, "characters") if r["id"] == eid and r.get("branch_id") == scope.get("branch_id")), None)
            if row is None:
                raise FileNotFoundError(eid)
            # Branch-local callers cannot infer project-main character sources.
            value = digest(row)
            return {"version": row.get("version"), "digest": value}, EmbeddingInput("TEXT", text=self._json(row))
        if self.screenplays is None:
            raise ValueError("EMBEDDING_SCREENPLAY_SERVICE_NOT_CONFIGURED")
        screenplay = next((r for r in self.screenplays.list(nid, branch_id=scope.get("branch_id"))
            if r["id"] == ref["screenplay_id"] and r.get("branch_id") == scope.get("branch_id")), None)
        if screenplay is None:
            raise FileNotFoundError(ref["screenplay_id"])
        row = next((r for r in screenplay.get("scenes", []) if r["id"] == eid), None)
        if row is None:
            raise FileNotFoundError(eid)
        sources = scene_sources(nid, scope, row, self.chapters)
        return {"version": screenplay.get("edit_version"), "digest": digest([row, sources])}, EmbeddingInput("TEXT", text=self._json(row))

    @staticmethod
    def _json(value):
        import json
        return json.dumps(value, sort_keys=True, ensure_ascii=False)

    def create_index(self, nid, scope, actor, body):
        data = EmbeddingIndexIn.model_validate(body).model_dump()
        for ref in data["entities"]:
            self._source(nid, scope, ref)
        data.update(status="NOT_CONFIGURED" if self.provider is None else "DRAFT", index_version=0,
                    model=None, execution_token=None, record_ids=[])
        return self.create(nid, scope, actor, self.INDEXES, data)

    def indexes(self, nid, scope):
        rows = self.list(nid, scope, self.INDEXES)
        for row in rows:
            row["stale"] = self._index_stale(nid, scope, row)
            row["provider_status"] = self.status()["status"]
        return rows

    def _index_stale(self, nid, scope, row):
        if row["status"] != "ACTIVE":
            return row["status"] == "INVALIDATED"
        try:
            if self.provider is not None and row.get("model") != self._capability().model_dump():
                return True
            for ref in row["entities"]:
                live, _ = self._source(nid, scope, ref)
                if live != row["source_snapshots"].get(digest(ref)):
                    return True
        except (FileNotFoundError, StaleSourceError):
            return True
        return False

    @staticmethod
    def _vectors(values, count, dimensions):
        if not isinstance(values, list) or len(values) != count:
            raise ValueError("EMBEDDING_RESULT_COUNT_INVALID")
        output = []
        for vector in values:
            if not isinstance(vector, (list, tuple)) or len(vector) != dimensions:
                raise ValueError("EMBEDDING_DIMENSION_MISMATCH")
            if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or abs(v) > 1e20 for v in vector):
                raise ValueError("EMBEDDING_VECTOR_INVALID")
            vector = [float(v) for v in vector]
            if sum(v * v for v in vector) == 0:
                raise ValueError("EMBEDDING_ZERO_VECTOR")
            output.append(vector)
        return output

    def _guard(self, capability, scope, check_authority, check_egress, payload):
        if scope.get("mode") == "collaboration" and check_authority is None:
            raise ValueError("EMBEDDING_AUTHORITY_REQUIRED")
        if check_authority:
            check_authority()
        if not capability.local:
            if check_egress is None:
                raise ValueError("EMBEDDING_EGRESS_AUTHORITY_REQUIRED")
            check_egress(payload, self.provider)
        if check_authority:
            check_authority()

    def rebuild(self, nid, scope, actor, rid, expected_version, check_authority=None, check_egress=None):
        capability = self._capability()
        provider = self.provider
        token = str(uuid4())
        def claim(row):
            if row["status"] == "REMOVED":
                raise ValueError("EMBEDDING_INDEX_REMOVED")
            if row["status"] == "BUILDING":
                raise ValueError("EMBEDDING_BUILD_ALREADY_RUNNING_INVALIDATE_TO_RECOVER")
            row.update(status="BUILDING", execution_token=token, error_code=None)
        index = self.mutate(nid, scope, actor, self.INDEXES, rid, expected_version, claim)
        try:
            snapshots, inputs = {}, []
            for ref in index["entities"]:
                source, value = self._source(nid, scope, ref)
                if value.kind not in capability.input_types:
                    raise ValueError("EMBEDDING_INPUT_UNSUPPORTED")
                snapshots[digest(ref)] = source
                inputs.append(value)
            self._guard(capability, scope, check_authority, check_egress, index)
            for ref in index["entities"]:
                source, _ = self._source(nid, scope, ref)
                if source != snapshots[digest(ref)]:
                    raise StaleSourceError("EMBEDDING_SOURCE_CHANGED")
            current = self.get(nid, scope, self.INDEXES, rid)
            if current["status"] != "BUILDING" or current.get("execution_token") != token or current["version"] != index["version"]:
                return current
            if self.provider is not provider or capability != self._capability():
                raise StaleSourceError("EMBEDDING_PROVIDER_CHANGED")
            vectors = self._vectors(provider.embed(inputs), len(inputs), capability.dimensions)
            if capability != self._capability():
                raise StaleSourceError("EMBEDDING_PROVIDER_CHANGED")
            if check_authority:
                check_authority()
            with self.store.transaction(nid, scope) as doc:
                current = doc["collections"][self.INDEXES][rid]
                if current["status"] != "BUILDING" or current.get("execution_token") != token or current["version"] != index["version"]:
                    return copy.deepcopy(current)
                for ref in index["entities"]:
                    source, _ = self._source(nid, scope, ref)
                    if source != snapshots[digest(ref)]:
                        raise StaleSourceError("EMBEDDING_SOURCE_CHANGED")
                version = current["index_version"] + 1
                records = doc["collections"].setdefault(self.VECTORS, {})
                for old_id in current["record_ids"]:
                    if old_id in records:
                        records[old_id].update(status="INVALIDATED", vector=[])
                ids = []
                for ref, vector in zip(index["entities"], vectors):
                    source = snapshots[digest(ref)]
                    record = VectorRecord(id=str(uuid4()), index_id=rid, index_version=version, entity=ref,
                        source_version=source["version"], source_digest=source["digest"], provider_id=capability.provider_id,
                        model_id=capability.model_id, model_revision=capability.model_revision, dimensions=capability.dimensions,
                        vector=vector, vector_digest=digest(vector), verification=capability.verification).model_dump()
                    record.update(novel_id=nid, scope=copy.deepcopy(scope), version=1, created_by=actor, updated_by=actor,
                                  created_at=now(), updated_at=now(), history=[])
                    records[record["id"]] = record
                    ids.append(record["id"])
                current.setdefault("history", []).append(snapshot(current))
                current.update(status="ACTIVE", index_version=version, model=capability.model_dump(), record_ids=ids,
                    source_snapshots=snapshots, execution_token=None, version=current["version"] + 1, updated_by=actor, updated_at=now())
                return copy.deepcopy(current)
        except Exception as exc:
            current = self.get(nid, scope, self.INDEXES, rid)
            if current["status"] == "BUILDING" and current.get("execution_token") == token:
                def fail(row):
                    row.update(status="FAILED", execution_token=None, error_code="EMBEDDING_SOURCE_STALE" if isinstance(exc, StaleSourceError) else "EMBEDDING_BUILD_FAILED")
                self.mutate(nid, scope, actor, self.INDEXES, rid, current["version"], fail)
            raise

    def transition(self, nid, scope, actor, rid, action, expected_version):
        if action not in {"invalidate", "remove"}:
            raise ValueError("EMBEDDING_ACTION_INVALID")
        with self.store.transaction(nid, scope) as doc:
            row = doc["collections"].get(self.INDEXES, {}).get(rid)
            if row is None:
                raise FileNotFoundError(rid)
            check_version(row, expected_version)
            if row["status"] == "REMOVED":
                raise ValueError("EMBEDDING_INDEX_REMOVED")
            row.setdefault("history", []).append(snapshot(row))
            target = "INVALIDATED" if action == "invalidate" else "REMOVED"
            row.update(status=target, execution_token=None, version=row["version"] + 1, updated_by=actor, updated_at=now())
            for vector in doc["collections"].get(self.VECTORS, {}).values():
                if vector["index_id"] == rid:
                    vector.update(status=target, vector=[])
            return copy.deepcopy(row)

    def records(self, nid, scope, index_id):
        self.get(nid, scope, self.INDEXES, index_id)
        return [{k: v for k, v in r.items() if k != "vector"} for r in self.list(nid, scope, self.VECTORS) if r["index_id"] == index_id]

    def query(self, nid, scope, body, check_authority=None, check_egress=None):
        data = EmbeddingQueryIn.model_validate(body)
        capability = self._capability()
        provider = self.provider
        index = self.get(nid, scope, self.INDEXES, data.index_id)
        if index["status"] != "ACTIVE" or self._index_stale(nid, scope, index):
            raise StaleSourceError("EMBEDDING_INDEX_STALE_REBUILD_REQUIRED")
        if "TEXT" not in capability.input_types:
            raise ValueError("EMBEDDING_TEXT_QUERY_UNSUPPORTED")
        self._guard(capability, scope, check_authority, check_egress, {"index": index, "query": data.text})
        current = self.get(nid, scope, self.INDEXES, data.index_id)
        if current["version"] != index["version"] or self._index_stale(nid, scope, current):
            raise StaleSourceError("EMBEDDING_INDEX_CHANGED")
        if self.provider is not provider or capability != self._capability():
            raise StaleSourceError("EMBEDDING_PROVIDER_CHANGED")
        vector = self._vectors(provider.embed([EmbeddingInput("TEXT", data.text)]), 1, capability.dimensions)[0]
        if self.provider is not provider or capability != self._capability():
            raise StaleSourceError("EMBEDDING_PROVIDER_CHANGED")
        if check_authority:
            check_authority()
        current = self.get(nid, scope, self.INDEXES, data.index_id)
        if current["version"] != index["version"] or self._index_stale(nid, scope, current):
            raise StaleSourceError("EMBEDDING_INDEX_CHANGED")
        norm = math.sqrt(sum(v * v for v in vector))
        results = []
        for row in self.list(nid, scope, self.VECTORS):
            if row["index_id"] != data.index_id or row["index_version"] != index["index_version"] or row["status"] != "ACTIVE":
                continue
            stored = self._vectors([row["vector"]], 1, capability.dimensions)[0]
            if digest(stored) != row["vector_digest"]:
                raise ValueError("EMBEDDING_VECTOR_INTEGRITY_FAILED")
            score = sum(a * b for a, b in zip(vector, stored)) / (norm * math.sqrt(sum(v * v for v in stored)))
            results.append({"record_id": row["id"], "entity": row["entity"], "score": max(-1.0, min(1.0, score)),
                            "source_digest": row["source_digest"], "verification": row["verification"]})
        return {"items": sorted(results, key=lambda r: (-r["score"], r["record_id"]))[:data.limit],
                "index_id": index["id"], "index_version": index["index_version"], "model": index["model"],
                "metric": "COSINE", "lexical_fallback": False}
