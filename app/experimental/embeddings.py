"""Optional, real vector abstraction. Unconfigured means no embedding search.

The real local adapter reuses explicit Model Center discovery registrations.
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

from .common import DomainService, StaleSourceError, check_version, now, snapshot, new_row
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


class LocalOllamaEmbeddingProvider:
    """Bounded real /api/embed transport under the original registration authority.

    No model installation, enablement, credentials, process launch or cloud
    fallback. A local HTTP endpoint alone is never evidence of local inference.
    """
    def __init__(self, bridge, registration_id, dimensions):
        from ..model_center.discovery_probes import LocalProbeClient
        self.bridge, self.registration_id, self.dimensions = bridge, registration_id, dimensions
        self.client = LocalProbeClient(timeout=30)

    def _registration(self):
        from .flags import enabled_flags
        if 'visual_embeddings' not in enabled_flags(): raise ValueError('EMBEDDING_FEATURE_DISABLED')
        from ..model_runtime import ModelRuntimeError
        try: row = self.bridge.guard(self.registration_id)
        except ModelRuntimeError as exc: raise ValueError('EMBEDDING_MODEL_CENTER_ROUTE_UNAVAILABLE') from exc
        if (row.get('runtime_type') != 'OLLAMA' or 'EMBEDDING' not in row.get('verified_capabilities', [])
            or row.get('source_locality') != 'LOCAL_VERIFIED' or not row.get('license_confirmed')
            or not row.get('model_evidence_fingerprint')):
            raise ValueError('EMBEDDING_VERIFIED_LOCAL_REGISTRATION_REQUIRED')
        return row

    @property
    def capability(self):
        row = self._registration()
        return EmbeddingCapability(provider_id=row['provider_id'], model_id=row['id'],
            model_revision=digest([row['model_evidence_fingerprint'], row.get('runtime_fingerprint'), row.get('enabled_at')]),
            dimensions=self.dimensions, local=True, input_types=['TEXT'], verification='CONTRACT_VERIFIED')

    def embed(self, inputs):
        return self.embed_guarded(inputs, lambda: None)

    def embed_guarded(self, inputs, dispatch_guard):
        if not inputs or len(inputs) > 500 or any(value.kind != 'TEXT' for value in inputs):
            raise ValueError('EMBEDDING_TEXT_INPUT_REQUIRED')
        if sum(len(value.text.encode()) for value in inputs) > 2 * 1024 * 1024:
            raise ValueError('EMBEDDING_INPUT_LIMIT')
        before = self.capability
        row = self._registration()
        self.bridge.service.check_model_dispatch(row)
        dispatch_guard()
        row = self._registration()
        if self.capability != before: raise StaleSourceError('EMBEDDING_PROVIDER_CHANGED')
        payload = self.client.json(row['runtime_config']['endpoint'], '/api/embed', body={
            'model': row['model_name'], 'input': [value.text for value in inputs], 'truncate': False, 'keep_alive': '0s'})
        if self.capability != before: raise StaleSourceError('EMBEDDING_PROVIDER_CHANGED')
        if not isinstance(payload, dict) or payload.get('error') or payload.get('model') != row['model_name']:
            raise ValueError('EMBEDDING_PROVIDER_RESPONSE_INVALID')
        return EmbeddingService._vectors(payload.get('embeddings'), len(inputs), before.dimensions)


class EntityRef(StrictModel):
    entity_type: Literal["ASSET", "CHARACTER", "SCENE", "RESEARCH"]
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
    registration_id: str | None = Field(default=None, min_length=1, max_length=240)
    dimensions: int | None = Field(default=None, ge=1, le=8192)

    @model_validator(mode="after")
    def distinct(self):
        if (self.registration_id is None) != (self.dimensions is None):
            raise ValueError('EMBEDDING_REGISTRATION_DIMENSIONS_REQUIRED')
        keys = [digest(e.model_dump()) for e in self.entities]
        if len(keys) != len(set(keys)):
            raise ValueError("embedding entity references must be distinct")
        return self


class EmbeddingIndexEditIn(EmbeddingIndexIn):
    expected_version: int = Field(ge=1)


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

    def __init__(self, store, novels, chapters, provider=None, assets=None, screenplays=None, research=None, discovery_bridge=None):
        super().__init__(store, novels, chapters)
        self.provider, self.assets, self.screenplays = provider, assets, screenplays
        self.research, self.discovery_bridge = research, discovery_bridge
        self.research_guard = lambda: None

    def status(self):
        return {"status": "NOT_CONFIGURED" if self.provider is None else "CONFIGURED",
                "capability": self._capability().model_dump() if self.provider else None,
                "lexical_fallback": False, "precision_claim": "VECTOR_SIMILARITY_ONLY"}

    def _capability(self):
        if self.provider is None:
            raise ValueError("EMBEDDING_NOT_CONFIGURED")
        return EmbeddingCapability.model_validate(self.provider.capability)

    def catalog(self, nid, scope, actor):
        self.novels.get(nid)
        branch = scope.get('branch_id')
        rows, unavailable = [], []
        def add(kind, eid, title, version, *, screenplay_id=None, input_type='TEXT', reason=None):
            rows.append({'entity': {'entity_type': kind, 'entity_id': eid, 'screenplay_id': screenplay_id},
                'title': title, 'source_version': version, 'input_type': input_type,
                'available': reason is None, 'reason': reason})
        for row in self.novels.data_set(nid, 'characters'):
            if row.get('branch_id') == branch:
                add('CHARACTER', row['id'], row.get('name') or row['id'], row.get('version'))
        if self.assets is not None:
            for row in self.assets.list(nid, branch_id=branch, actor_id=actor):
                if row.get('branch_id') == branch and row.get('kind') == 'image':
                    add('ASSET', row['id'], row.get('filename') or row['id'], row.get('version'), input_type='IMAGE')
        else: unavailable.append('ASSET_SERVICE_NOT_CONFIGURED')
        if self.screenplays is not None:
            for screenplay in self.screenplays.list(nid, branch_id=branch):
                if screenplay.get('branch_id') != branch: continue
                for row in screenplay.get('scenes', []):
                    ref = {'entity_type': 'SCENE', 'entity_id': row['id'], 'screenplay_id': screenplay['id']}
                    try: self._source(nid, scope, ref, actor); reason = None
                    except (ValueError, FileNotFoundError): reason = 'SOURCE_UNAVAILABLE_OR_STALE'
                    add('SCENE', row['id'], row.get('title') or row.get('heading') or row['id'], screenplay.get('edit_version'), screenplay_id=screenplay['id'], reason=reason)
        else: unavailable.append('SCREENPLAY_SERVICE_NOT_CONFIGURED')
        if self.research is not None:
            from fastapi import HTTPException
            try:
                self.research_guard()
                for row in self.research.sources(nid, scope, actor)['items']:
                    add('RESEARCH', row['id'], row['title'], row['version'], reason=None if row['paragraph_count'] else 'OCR_OR_TEXT_NOT_AVAILABLE')
            except HTTPException as exc:
                if exc.status_code != 404: raise
                unavailable.append('RESEARCH_FEATURE_DISABLED')
        else: unavailable.append('RESEARCH_SERVICE_NOT_CONFIGURED')
        return {'items': rows[:500], 'truncated': len(rows) > 500, 'unavailable': unavailable, 'scope': copy.deepcopy(scope)}

    def providers(self):
        if self.discovery_bridge is None: return {'items': [], 'configuration': 'EXISTING_MODEL_CENTER'}
        rows = []
        for row in list(self.discovery_bridge.service.registrations.values()):
            if row.get('runtime_type') != 'OLLAMA' or 'EMBEDDING' not in row.get('verified_capabilities', []): continue
            rows.append({key: row.get(key) for key in ('id', 'display_name', 'provider_id', 'enabled', 'enable_eligible', 'license_confirmed', 'source_locality')})
        return {'items': rows, 'configuration': 'EXISTING_MODEL_CENTER', 'inference': 'NOT_RUN'}

    def _provider(self, index):
        if index.get('registration_id'):
            if self.discovery_bridge is None: raise ValueError('EMBEDDING_MODEL_CENTER_NOT_CONFIGURED')
            return LocalOllamaEmbeddingProvider(self.discovery_bridge, index['registration_id'], index['dimensions'])
        if self.provider is None: raise ValueError('EMBEDDING_NOT_CONFIGURED')
        return self.provider

    def _provider_current(self, provider, index, capability):
        if index.get('registration_id'):
            return self.discovery_bridge is provider.bridge and capability == provider.capability
        return self.provider is provider and capability == self._capability()

    @staticmethod
    def _requires_owner(index):
        return bool(index.get('private_sources')) or any(ref.get('entity_type') == 'RESEARCH' for ref in index['entities'])

    def owned_index(self, nid, scope, rid, actor=None):
        row = self.get(nid, scope, self.INDEXES, rid)
        if any(ref.get('entity_type') == 'RESEARCH' for ref in row['entities']): self.research_guard()
        if self._requires_owner(row):
            if actor != row['created_by']: raise FileNotFoundError(rid)
        return row

    def _source(self, nid, scope, ref, actor=None):
        ref = EntityRef.model_validate(ref).model_dump()
        kind, eid = ref["entity_type"], ref["entity_id"]
        if kind == "RESEARCH":
            self.research_guard()
            if self.research is None: raise ValueError('EMBEDDING_RESEARCH_NOT_CONFIGURED')
            if actor is None: raise ValueError('EMBEDDING_RESEARCH_ACTOR_REQUIRED')
            row = self.research.source(nid, scope, actor, eid)
            text = '\n\n'.join(paragraph['text'] for paragraph in row.get('paragraphs', []))
            if not text: raise ValueError('EMBEDDING_RESEARCH_TEXT_NOT_AVAILABLE')
            return {'version': row['version'], 'digest': row['content_sha256']}, EmbeddingInput('TEXT', text=text)
        if kind == "ASSET":
            if self.assets is None:
                raise ValueError("EMBEDDING_ASSET_SERVICE_NOT_CONFIGURED")
            row = self.assets.get(eid, branch_id=scope.get("branch_id"), actor_id=actor)
            if row.get("novel_id") != nid or row.get("branch_id") != scope.get("branch_id"):
                raise FileNotFoundError(eid)
            if row.get("kind") != "image":
                raise ValueError("EMBEDDING_IMAGE_ASSET_REQUIRED")
            data = self.assets.content(eid, branch_id=scope.get("branch_id"), actor_id=actor)
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

    def create_index(self, nid, scope, actor, body, check_authority=None):
        data = EmbeddingIndexIn.model_validate(body).model_dump()
        data['private_sources'] = False
        for ref in data["entities"]:
            self._source(nid, scope, ref, actor)
            if ref['entity_type'] == 'ASSET' and self.assets.get(ref['entity_id'], branch_id=scope.get('branch_id'), actor_id=actor).get('_owner_actor_id'):
                data['private_sources'] = True
        if data.get('registration_id'):
            self._provider(data).capability
        data.update(status="NOT_CONFIGURED" if self.provider is None and not data.get('registration_id') else "DRAFT", index_version=0,
                    model=None, execution_token=None, record_ids=[])
        with self.store.transaction(nid, scope) as doc:
            if check_authority: check_authority()
            row = new_row(nid, scope, actor, data)
            doc['collections'].setdefault(self.INDEXES, {})[row['id']] = row
            if check_authority: check_authority()
            return copy.deepcopy(row)

    def edit_index(self, nid, scope, actor, rid, body, check_authority=None):
        data = EmbeddingIndexEditIn.model_validate(body)
        with self.store.transaction(nid, scope) as doc:
            if check_authority: check_authority()
            index = self.owned_index(nid, scope, rid, actor)
            if index['status'] in {'BUILDING', 'REMOVED'}: raise ValueError('EMBEDDING_INDEX_NOT_EDITABLE')
            check_version(index, data.expected_version)
            for ref in data.entities: self._source(nid, scope, ref, actor)
            if data.registration_id: self._provider(data.model_dump()).capability
            row = doc['collections'][self.INDEXES][rid]
            row.setdefault('history', []).append(snapshot(row))
            row.update(data.model_dump(exclude={'expected_version'}), status='INVALIDATED', execution_token=None,
                       private_sources=row.get('private_sources', False) or self._requires_owner(index) or any(ref.entity_type == 'ASSET' and self.assets.get(ref.entity_id, branch_id=scope.get('branch_id'), actor_id=actor).get('_owner_actor_id') for ref in data.entities),
                       version=row['version'] + 1, updated_by=actor, updated_at=now())
            for vector in doc['collections'].get(self.VECTORS, {}).values():
                if vector['index_id'] == rid: vector.update(status='INVALIDATED', vector=[])
            if check_authority: check_authority()
            return copy.deepcopy(row)

    def indexes(self, nid, scope, actor=None):
        rows = [row for row in self.list(nid, scope, self.INDEXES) if not self._requires_owner(row) or row["created_by"] == actor]
        for row in rows:
            if any(ref.get('entity_type') == 'RESEARCH' for ref in row['entities']): self.research_guard()
            row["stale"] = self._index_stale(nid, scope, row, actor)
            try: self._provider(row).capability; row['provider_status'] = 'CONFIGURED'
            except (ValueError, RuntimeError): row['provider_status'] = 'NOT_CONFIGURED'
        return rows

    def _index_stale(self, nid, scope, row, actor=None):
        if row["status"] != "ACTIVE":
            return row["status"] == "INVALIDATED"
        try:
            if row.get("model") != EmbeddingCapability.model_validate(self._provider(row).capability).model_dump():
                return True
            for ref in row["entities"]:
                live, _ = self._source(nid, scope, ref, actor)
                if live != row["source_snapshots"].get(digest(ref)):
                    return True
        except (FileNotFoundError, ValueError, RuntimeError):
            return True
        return False

    @staticmethod
    def _vectors(values, count, dimensions):
        if count * dimensions > 262144: raise ValueError("EMBEDDING_VECTOR_BUDGET_EXCEEDED")
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
        initial = self.owned_index(nid, scope, rid, actor)
        provider = self._provider(initial)
        capability = EmbeddingCapability.model_validate(provider.capability)
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
                source, value = self._source(nid, scope, ref, actor)
                if value.kind not in capability.input_types:
                    raise ValueError("EMBEDDING_INPUT_UNSUPPORTED")
                snapshots[digest(ref)] = source
                inputs.append(value)
            self._guard(capability, scope, check_authority, check_egress, index)
            for ref in index["entities"]:
                source, _ = self._source(nid, scope, ref, actor)
                if source != snapshots[digest(ref)]:
                    raise StaleSourceError("EMBEDDING_SOURCE_CHANGED")
            current = self.get(nid, scope, self.INDEXES, rid)
            if current["status"] != "BUILDING" or current.get("execution_token") != token or current["version"] != index["version"]:
                return current
            if not self._provider_current(provider, index, capability):
                raise StaleSourceError("EMBEDDING_PROVIDER_CHANGED")
            def final_dispatch():
                self._guard(capability, scope, check_authority, check_egress, index)
                latest = self.owned_index(nid, scope, rid, actor)
                if latest['version'] != index['version'] or latest.get('execution_token') != token:
                    raise StaleSourceError('EMBEDDING_BUILD_CANCELLED')
                for ref in index['entities']:
                    source, _ = self._source(nid, scope, ref, actor)
                    if source != snapshots[digest(ref)]: raise StaleSourceError('EMBEDDING_SOURCE_CHANGED')
            values = provider.embed_guarded(inputs, final_dispatch) if type(provider) is LocalOllamaEmbeddingProvider else provider.embed(inputs)
            vectors = self._vectors(values, len(inputs), capability.dimensions)
            if not self._provider_current(provider, index, capability):
                raise StaleSourceError("EMBEDDING_PROVIDER_CHANGED")
            if check_authority:
                check_authority()
            with self.store.transaction(nid, scope) as doc:
                current = doc["collections"][self.INDEXES][rid]
                if current["status"] != "BUILDING" or current.get("execution_token") != token or current["version"] != index["version"]:
                    return copy.deepcopy(current)
                for ref in index["entities"]:
                    source, _ = self._source(nid, scope, ref, actor)
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

    def transition(self, nid, scope, actor, rid, action, expected_version, check_authority=None):
        self.owned_index(nid, scope, rid, actor)
        if action not in {"invalidate", "remove", "cancel"}:
            raise ValueError("EMBEDDING_ACTION_INVALID")
        with self.store.transaction(nid, scope) as doc:
            if check_authority: check_authority()
            row = doc["collections"].get(self.INDEXES, {}).get(rid)
            if row is None:
                raise FileNotFoundError(rid)
            check_version(row, expected_version)
            if row["status"] == "REMOVED":
                raise ValueError("EMBEDDING_INDEX_REMOVED")
            row.setdefault("history", []).append(snapshot(row))
            if action == 'cancel' and row['status'] != 'BUILDING': raise ValueError('EMBEDDING_BUILD_NOT_RUNNING')
            target = "REMOVED" if action == "remove" else "INVALIDATED"
            row.update(status=target, execution_token=None, version=row["version"] + 1, updated_by=actor, updated_at=now())
            for vector in doc["collections"].get(self.VECTORS, {}).values():
                if vector["index_id"] == rid:
                    vector.update(status=target, vector=[])
            if check_authority: check_authority()
            return copy.deepcopy(row)

    def records(self, nid, scope, index_id, actor=None):
        self.owned_index(nid, scope, index_id, actor)
        return [{k: v for k, v in r.items() if k != "vector"} for r in self.list(nid, scope, self.VECTORS) if r["index_id"] == index_id]

    def query(self, nid, scope, body, check_authority=None, check_egress=None, actor=None):
        data = EmbeddingQueryIn.model_validate(body)
        index = self.owned_index(nid, scope, data.index_id, actor)
        provider = self._provider(index)
        capability = EmbeddingCapability.model_validate(provider.capability)
        if index["status"] != "ACTIVE" or self._index_stale(nid, scope, index, actor):
            raise StaleSourceError("EMBEDDING_INDEX_STALE_REBUILD_REQUIRED")
        if "TEXT" not in capability.input_types:
            raise ValueError("EMBEDDING_TEXT_QUERY_UNSUPPORTED")
        self._guard(capability, scope, check_authority, check_egress, {"index": index, "query": data.text})
        current = self.get(nid, scope, self.INDEXES, data.index_id)
        if current["version"] != index["version"] or self._index_stale(nid, scope, current, actor):
            raise StaleSourceError("EMBEDDING_INDEX_CHANGED")
        if not self._provider_current(provider, index, capability):
            raise StaleSourceError("EMBEDDING_PROVIDER_CHANGED")
        def final_dispatch():
            self._guard(capability, scope, check_authority, check_egress, {'index': index, 'query': data.text})
            latest = self.owned_index(nid, scope, data.index_id, actor)
            if latest['version'] != index['version'] or self._index_stale(nid, scope, latest, actor):
                raise StaleSourceError('EMBEDDING_INDEX_CHANGED')
        inputs = [EmbeddingInput('TEXT', data.text)]
        values = provider.embed_guarded(inputs, final_dispatch) if type(provider) is LocalOllamaEmbeddingProvider else provider.embed(inputs)
        vector = self._vectors(values, 1, capability.dimensions)[0]
        if not self._provider_current(provider, index, capability):
            raise StaleSourceError("EMBEDDING_PROVIDER_CHANGED")
        if check_authority:
            check_authority()
        current = self.get(nid, scope, self.INDEXES, data.index_id)
        if current["version"] != index["version"] or self._index_stale(nid, scope, current, actor):
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
        if check_authority: check_authority()
        latest = self.owned_index(nid, scope, data.index_id, actor)
        if latest['version'] != index['version'] or self._index_stale(nid, scope, latest, actor):
            raise StaleSourceError('EMBEDDING_INDEX_CHANGED')
        return {"items": sorted(results, key=lambda r: (-r["score"], r["record_id"]))[:data.limit],
                "index_id": index["id"], "index_version": index["index_version"], "model": index["model"],
                "metric": "COSINE", "lexical_fallback": False}
