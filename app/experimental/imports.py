"""Durable, bounded semantic-import jobs with reviewable exact source evidence.

The built-in extractor is LOCAL_HEURISTIC, not a literary-quality model. Adapters
can return structured candidates but cannot write the manuscript or Canon.
Explicit commit reuses the existing conservative per-target apply journal.
"""
from __future__ import annotations

import copy
from bisect import bisect_right
import hashlib
import json
import re
import unicodedata
import uuid
from datetime import datetime, timedelta, timezone
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from .common import DomainService, StaleSourceError, check_version, now, snapshot
from ..knowledge_extraction import extract_knowledge_candidates
from ..services.import_apply_service import ImportApplyInterrupted, ImportApplyService, KINDS

JOBS = "semantic_import_jobs"
CHUNKS = "semantic_import_chunks"
CANDIDATES = "semantic_import_candidates"
SUPPORTED_KINDS = ("characters", "locations", "organizations", "timeline_events", "foreshadowing", "world_rules", "relationships")
MAX_CHARS = 12_000_000
MAX_CHUNKS = 12000
MAX_CANDIDATES = 10000


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def stable_id(*parts) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, json.dumps(parts, ensure_ascii=False, sort_keys=True)))


def normalized(value: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", value)).strip().casefold()


class ExtractedCandidate(BaseModel):
    """Adapter offsets are Unicode character offsets relative to its chunk."""
    model_config = ConfigDict(extra="forbid", strict=True)
    kind: Literal["characters", "locations", "organizations", "timeline_events", "foreshadowing", "world_rules", "relationships"]
    label: str = Field(min_length=1, max_length=500)
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    quote: str = Field(min_length=1, max_length=65536)
    aliases: list[str] = Field(default_factory=list, max_length=30)
    attributes: dict[str, str] = Field(default_factory=dict)
    confidence: float = Field(default=0.5, ge=0, le=1)


class SemanticExtractionAdapter(Protocol):
    adapter_id: str
    verification: str

    def extract(self, chunk: dict) -> list[dict]: ...


class DeterministicSemanticAdapter:
    adapter_id = "local-semantic-rules-v2"
    verification = "LOCAL_HEURISTIC"

    def extract(self, chunk: dict) -> list[dict]:
        text = chunk["text"]
        groups = extract_knowledge_candidates([{
            "id": chunk["chapter_id"], "number": chunk["chapter_number"],
            "version": chunk["chapter_version"], "title": chunk["chapter_title"], "content": text,
        }])
        rows = []
        for kind, candidates in groups.items():
            for candidate in candidates:
                for evidence in candidate["source_evidence"]:
                    rows.append({"kind": kind, "label": candidate.get("name") or candidate["title"],
                                 "start": evidence["start"], "end": evidence["end"], "quote": evidence["quote"],
                                 "confidence": float(candidate["confidence"])})
        # Explicit labels are intentionally narrow. Ambiguous free prose remains
        # a candidate extraction problem for a future reviewed model adapter.
        patterns = (
            ("organizations", r"(?:Organization|Faction|组织|阵营)\s*[:：]\s*([^\n。.!?]{1,100})"),
            ("world_rules", r"(?:Rule|World rule|规则|世界规则)\s*[:：]\s*([^\n。.!?]{1,240})"),
            ("relationships", r"(?:Relationship|关系)\s*[:：]\s*([^\n。.!?]{1,240})"),
        )
        for kind, pattern in patterns:
            for match in re.finditer(pattern, text, re.I):
                rows.append({"kind": kind, "label": match.group(1).strip(), "start": match.start(),
                             "end": match.end(), "quote": match.group(0), "confidence": 0.5})
        for match in re.finditer(r"([A-Z][a-z]+(?: [A-Z][a-z]+)?)\s+(?:aka|also known as)\s+([A-Z][a-z]+(?: [A-Z][a-z]+)?)", text):
            rows.append({"kind": "characters", "label": match.group(1), "aliases": [match.group(2)],
                         "start": match.start(), "end": match.end(), "quote": match.group(0), "confidence": 0.6})
        return rows


class SemanticImportService(DomainService):
    def __init__(self, store, novels, chapters, apply_service=None, adapters=None):
        super().__init__(store, novels, chapters)
        self.apply_service = apply_service
        default = DeterministicSemanticAdapter()
        self.adapters = {default.adapter_id: default}
        for adapter in adapters or ():
            if adapter.adapter_id in self.adapters:
                raise ValueError("duplicate semantic extraction adapter")
            self.adapters[adapter.adapter_id] = adapter

    @staticmethod
    def _record(nid, scope, actor, rid, payload):
        return {**copy.deepcopy(payload), "id": rid, "novel_id": nid, "scope": copy.deepcopy(scope),
                "version": 1, "created_by": actor, "updated_by": actor, "created_at": now(), "updated_at": now(), "history": []}

    @staticmethod
    def _touch(row, actor, action):
        before = snapshot(row)
        # Evidence itself is retained on the candidate. Audit append/counts,
        # rather than copying an entire long-book evidence set on every chunk.
        if "source_evidence" in before:
            before["source_evidence_count"] = len(before.pop("source_evidence"))
        if "sources" in before:
            before["source_count"] = len(before.pop("sources"))
        if "commit_intent" in before:
            before["commit_candidate_ids"] = before.pop("commit_intent")["candidate_ids"]
        before.pop("apply_checkpoint", None)
        row.setdefault("history", []).append({"version": row["version"], "action": action,
                                              "actor": actor, "at": now(), "snapshot": before})
        row["history"] = row["history"][-50:]
        row.update(version=row["version"] + 1, updated_by=actor, updated_at=now())

    @staticmethod
    def _row(doc, collection, rid):
        row = doc["collections"].get(collection, {}).get(rid)
        if row is None or row.get("novel_id") != doc["novel_id"] or row.get("scope") != doc["scope"]:
            raise FileNotFoundError(rid)
        return row

    def create_job(self, nid, scope, actor, chapter_ids, *, chunk_size=8000, overlap=256,
                   adapter_id="local-semantic-rules-v2"):
        if scope.get("mode") != "local":
            raise ValueError("IMPORT_BRANCH_SOURCE_ADAPTER_REQUIRED")
        if adapter_id not in self.adapters:
            raise ValueError("SEMANTIC_ADAPTER_NOT_CONFIGURED")
        if not 256 <= chunk_size <= 32000 or not 0 <= overlap < min(chunk_size // 2, 1025):
            raise ValueError("invalid chunk size or overlap")
        if not chapter_ids or len(chapter_ids) > 2000 or len(set(chapter_ids)) != len(chapter_ids):
            raise ValueError("select 1-2000 unique source chapters")
        sources = self.sources(nid, chapter_ids)
        job_id = str(uuid.uuid4())
        chunks = []
        total = 0
        for cid in chapter_ids:
            chapter = self.chapters.get(cid)
            text = str(chapter.get("content") or "")
            total += len(text)
            if total > MAX_CHARS:
                raise ValueError("semantic import exceeds 12 million source characters; split into jobs")
            paragraph_starts = [0] + [match.end() for match in re.finditer(r"\n\n", text)]
            for start in range(0, len(text), chunk_size):
                end = min(start + chunk_size + overlap, len(text))
                begin = max(0, start - overlap)
                chunk_id = stable_id(job_id, cid, start)
                chunks.append(self._record(nid, scope, actor, chunk_id, {
                    "job_id": job_id, "chapter_id": cid, "chapter_number": chapter.get("number", 1),
                    "chapter_title": chapter.get("title", cid), "chapter_version": sources[cid]["version"],
                    "content_sha256": sources[cid]["digest"], "text": text[begin:end],
                    "start": begin, "end": end, "paragraph_base": bisect_right(paragraph_starts, begin),
                    "paragraph_starts": [offset for offset in paragraph_starts if begin < offset <= end],
                    "status": "PENDING", "attempt": 0,
                }))
                if len(chunks) > MAX_CHUNKS:
                    raise ValueError("semantic import chunk limit exceeded")
        if not chunks:
            raise ValueError("source chapters contain no text")
        self.assert_sources(nid, sources)
        job = self._record(nid, scope, actor, job_id, {
            "status": "QUEUED", "sources": sources, "chapter_ids": chapter_ids,
            "adapter_id": adapter_id, "verification": self.adapters[adapter_id].verification,
            "chunk_size": chunk_size, "overlap": overlap, "chunk_ids": [c["id"] for c in chunks],
            "total_chunks": len(chunks), "completed_chunks": 0, "candidate_count": 0,
            "privacy_state": "LOCAL_ONLY", "applied": False, "generation": 1,
        })
        with self.store.transaction(nid, scope) as doc:
            doc["collections"].setdefault(JOBS, {})[job_id] = job
            doc["collections"].setdefault(CHUNKS, {}).update({c["id"]: c for c in chunks})
        return copy.deepcopy(job)

    def jobs(self, nid, scope):
        return self.list(nid, scope, JOBS)

    def job(self, nid, scope, job_id):
        return self.get(nid, scope, JOBS, job_id)

    def candidates(self, nid, scope, job_id=None):
        rows = self.list(nid, scope, CANDIDATES)
        freshness = {}
        selected = []
        for row in rows:
            if job_id is not None and row["job_id"] != job_id:
                continue
            if row["job_id"] not in freshness:
                freshness[row["job_id"]] = self.stale(nid, row["sources"])
            row["stale"] = bool(row.get("stale") or freshness[row["job_id"]])
            selected.append(row)
        return selected

    def chunks(self, nid, scope, job_id):
        self.job(nid, scope, job_id)
        return [{k: v for k, v in row.items() if k not in {"text", "history", "claim_token"}}
                for row in self.list(nid, scope, CHUNKS) if row["job_id"] == job_id]

    def _assert_fresh(self, nid, scope, job, actor):
        try:
            self.assert_sources(nid, job["sources"])
        except (StaleSourceError, FileNotFoundError):
            with self.store.transaction(nid, scope) as doc:
                live = self._row(doc, JOBS, job["id"])
                if live["status"] != "STALE":
                    self._touch(live, actor, "SOURCE_STALE")
                    live.update(status="STALE", stale=True, error_code="IMPORT_SOURCE_STALE")
                for row in doc["collections"].get(CANDIDATES, {}).values():
                    if row["job_id"] == job["id"] and not row.get("stale"):
                        self._touch(row, actor, "SOURCE_STALE")
                        row["stale"] = True
            raise StaleSourceError("IMPORT_SOURCE_STALE") from None

    def _validated_output(self, chunk, result):
        if not isinstance(result, list) or len(result) > 1000:
            raise ValueError("adapter must return at most 1000 candidates per chunk")
        rows = []
        for raw in result:
            row = ExtractedCandidate.model_validate(raw).model_dump()
            if not row["label"].strip() or row["start"] >= row["end"] or row["end"] > len(chunk["text"]):
                raise ValueError("invalid extraction source span")
            if chunk["text"][row["start"]:row["end"]] != row["quote"]:
                raise ValueError("extraction evidence quote does not match exact source span")
            if any(not isinstance(v, str) or not v.strip() or len(v) > 500 for v in row["aliases"]):
                raise ValueError("invalid entity alias")
            if len(row["attributes"]) > 40 or any(len(k) > 100 or len(v) > 2000 for k, v in row["attributes"].items()):
                raise ValueError("candidate attributes exceed contract bounds")
            row["evidence"] = {
                "chapter_id": chunk["chapter_id"], "chapter_number": chunk["chapter_number"],
                "chapter_version": chunk["chapter_version"], "content_sha256": chunk["content_sha256"],
                "start": chunk["start"] + row["start"], "end": chunk["start"] + row["end"],
                "paragraph": chunk["paragraph_base"] + bisect_right(chunk["paragraph_starts"], chunk["start"] + row["start"]),
                "quote": row["quote"], "quote_sha256": digest(row["quote"]), "chunk_id": chunk["id"],
            }
            rows.append(row)
        return rows

    def _add_candidates(self, doc, nid, scope, actor, job, output):
        candidates = doc["collections"].setdefault(CANDIDATES, {})
        for value in output:
            # Same explicit facts can share an evidence group. Name-only identity
            # remains unconfirmed and receives resolution suggestions below.
            key = [job["id"], value["kind"], normalized(value["label"]), value["attributes"]]
            if value["kind"] == "timeline_events":
                key.append(value["evidence"]["chapter_id"])
            cid = stable_id(*key)
            evidence = value["evidence"]
            if cid in candidates:
                candidate = candidates[cid]
                duplicate = any(all(old[k] == evidence[k] for k in ("chapter_id", "start", "end", "quote_sha256"))
                                for old in candidate["source_evidence"])
                if not duplicate:
                    self._touch(candidate, actor, "EVIDENCE_ADDED")
                    candidate["source_evidence"].append(evidence)
                    candidate["status"] = "PENDING"  # new evidence always invalidates a previous review
                candidate["aliases"] = sorted(set(candidate["aliases"] + value["aliases"]))
            else:
                if sum(c["job_id"] == job["id"] for c in candidates.values()) >= MAX_CANDIDATES:
                    raise ValueError("semantic import candidate limit exceeded")
                candidates[cid] = self._record(nid, scope, actor, cid, {
                    "job_id": job["id"], "status": "PENDING", "kind": value["kind"],
                    "label": value["label"], "aliases": value["aliases"], "attributes": value["attributes"],
                    "source_evidence": [evidence], "confidence": value["confidence"],
                    "analysis_source": job["verification"], "sources": copy.deepcopy(job["sources"]),
                    "resolution_suggestions": [], "conflicts": [], "stale": False, "applied": False,
                    "privacy_state": "LOCAL_ONLY", "risk": "REVIEW_REQUIRED",
                    "target": KINDS.get(value["kind"], "MANUAL_PROMOTION_REQUIRED"),
                })
        rows = [row for row in candidates.values() if row["job_id"] == job["id"]]
        self._resolution(rows)
        job["candidate_count"] = len(rows)

    @staticmethod
    def _resolution(rows):
        buckets = {}
        for row in rows:
            row["resolution_suggestions"] = []
            row["conflicts"] = []
            for alias in {normalized(row["label"]), *(normalized(a) for a in row["aliases"])}:
                buckets.setdefault((row["kind"], alias), []).append(row)
            if len({e["chapter_id"] for e in row["source_evidence"]}) > 1:
                row["resolution_suggestions"].append({"type": "SAME_NAME_ACROSS_CHAPTERS", "identity_confirmed": False})
        for bucket in buckets.values():
            for i, left in enumerate(bucket):
                for right in bucket[i + 1:]:
                    differences = [key for key in left["attributes"].keys() & right["attributes"].keys()
                                   if left["attributes"][key] != right["attributes"][key]]
                    for source, target in ((left, right), (right, left)):
                        suggestion = {"type": "ALIAS_OR_DUPLICATE", "candidate_id": target["id"], "identity_confirmed": False}
                        if suggestion not in source["resolution_suggestions"]:
                            source["resolution_suggestions"].append(suggestion)
                        if differences:
                            conflict = {"candidate_id": target["id"], "fields": sorted(differences), "status": "REVIEW_REQUIRED"}
                            if conflict not in source["conflicts"]:
                                source["conflicts"].append(conflict)
        for row in rows:
            row["risk"] = "CONFLICT" if row["conflicts"] else "REVIEW_REQUIRED"

    def process(self, nid, scope, actor, job_id, expected_version, max_chunks=1):
        if not 1 <= max_chunks <= 100:
            raise ValueError("process 1-100 chunks at a time")
        job = self.job(nid, scope, job_id)
        check_version(job, expected_version)
        self._assert_fresh(nid, scope, job, actor)
        for _ in range(max_chunks):
            with self.store.transaction(nid, scope) as doc:
                live = self._row(doc, JOBS, job_id)
                check_version(live, expected_version)
                if live["status"] not in {"QUEUED", "ANALYZING"}:
                    raise ValueError("IMPORT_JOB_NOT_RUNNABLE")
                chunks = [self._row(doc, CHUNKS, cid) for cid in live["chunk_ids"]]
                if any(chunk["status"] == "RUNNING" for chunk in chunks):
                    raise ValueError("IMPORT_CHUNK_ALREADY_RUNNING")
                pending = next((chunk for chunk in chunks if chunk["status"] == "PENDING"), None)
                if pending is None:
                    raise ValueError("IMPORT_JOB_HAS_NO_PENDING_CHUNKS")
                claim = str(uuid.uuid4())
                pending.update(status="RUNNING", claim_token=claim, attempt=pending["attempt"] + 1,
                               lease_expires_at=(datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat())
                self._touch(live, actor, "CHUNK_CLAIMED")
                live["status"] = "ANALYZING"
                chunk = copy.deepcopy(pending)
                captured_generation = live["generation"]
            try:
                result = self.adapters[job["adapter_id"]].extract(copy.deepcopy(chunk))
                output = self._validated_output(chunk, result)
                self._assert_fresh(nid, scope, job, actor)
                with self.store.transaction(nid, scope) as doc:
                    live = self._row(doc, JOBS, job_id)
                    pending = self._row(doc, CHUNKS, chunk["id"])
                    if live["status"] != "ANALYZING" or live["generation"] != captured_generation or pending.get("claim_token") != claim:
                        raise ValueError("IMPORT_LATE_CALLBACK_REJECTED")
                    self._add_candidates(doc, nid, scope, actor, live, output)
                    pending.update(status="COMPLETED", completed_at=now(), output_count=len(output))
                    pending.pop("claim_token", None)
                    self._touch(live, actor, "CHUNK_COMPLETED")
                    live["completed_chunks"] += 1
                    live["status"] = "NEEDS_REVIEW" if live["completed_chunks"] == live["total_chunks"] else "ANALYZING"
                    expected_version = live["version"]
                    job = copy.deepcopy(live)
            except Exception as exc:
                with self.store.transaction(nid, scope) as doc:
                    live = self._row(doc, JOBS, job_id)
                    pending = self._row(doc, CHUNKS, chunk["id"])
                    if live["status"] == "ANALYZING" and pending.get("claim_token") == claim:
                        pending.update(status="FAILED", error_code="EXTRACTION_FAILED")
                        pending.pop("claim_token", None)
                        self._touch(live, actor, "CHUNK_FAILED")
                        live.update(status="FAILED", error_code="EXTRACTION_FAILED")
                raise exc
            if job["status"] == "NEEDS_REVIEW":
                break
        return job

    def transition(self, nid, scope, actor, job_id, action, expected_version):
        if action not in {"pause", "resume", "cancel", "retry", "recover"}:
            raise ValueError("unsupported import transition")
        if action in {"resume", "retry", "recover"}:
            self._assert_fresh(nid, scope, self.job(nid, scope, job_id), actor)
        with self.store.transaction(nid, scope) as doc:
            job = self._row(doc, JOBS, job_id)
            check_version(job, expected_version)
            allowed = {"pause": {"QUEUED", "ANALYZING"}, "resume": {"PAUSED"},
                       "cancel": {"QUEUED", "ANALYZING", "PAUSED", "FAILED", "NEEDS_REVIEW", "STALE"},
                       "retry": {"FAILED"}, "recover": {"ANALYZING"}}
            if job["status"] not in allowed[action]:
                raise ValueError("IMPORT_TRANSITION_NOT_ALLOWED")
            chunks = [self._row(doc, CHUNKS, cid) for cid in job["chunk_ids"]]
            if action == "recover" and any(c["status"] == "RUNNING" and c["lease_expires_at"] > now() for c in chunks):
                raise ValueError("IMPORT_LEASE_STILL_ACTIVE")
            self._touch(job, actor, action.upper())
            job["generation"] += 1
            for chunk in chunks:
                if chunk["status"] == "RUNNING" or (action == "retry" and chunk["status"] == "FAILED"):
                    chunk["status"] = "PENDING"
                    chunk.pop("claim_token", None)
            job["status"] = {"pause": "PAUSED", "cancel": "CANCELLED"}.get(action, "QUEUED")
            job.pop("error_code", None)
            return copy.deepcopy(job)

    def _validate_evidence(self, nid, row, cache=None, verified_jobs=None):
        cache = {} if cache is None else cache
        verified_jobs = set() if verified_jobs is None else verified_jobs
        if row["job_id"] not in verified_jobs:
            self.assert_sources(nid, row["sources"])
            verified_jobs.add(row["job_id"])
        if not row["source_evidence"]:
            raise ValueError("IMPORT_EVIDENCE_REQUIRED")
        for evidence in row["source_evidence"]:
            cid = evidence["chapter_id"]
            if cid not in row["sources"]:
                raise ValueError("IMPORT_EVIDENCE_SCOPE_MISMATCH")
            if cid not in cache:
                cache[cid] = self.chapters.get(cid)
            chapter = cache[cid]
            text = str(chapter.get("content") or "")
            if chapter.get("novel_id") != nid or chapter["version"] != evidence["chapter_version"] or digest(text) != evidence["content_sha256"]:
                raise StaleSourceError("IMPORT_SOURCE_STALE")
            if not 0 <= evidence["start"] < evidence["end"] <= len(text):
                raise ValueError("IMPORT_EVIDENCE_INVALID")
            quote = text[evidence["start"]:evidence["end"]]
            if quote != evidence["quote"] or digest(quote) != evidence["quote_sha256"]:
                raise ValueError("IMPORT_EVIDENCE_INVALID")

    def review_batch(self, nid, scope, actor, items, job_id=None):
        if not items or len(items) > 200 or len({i["id"] for i in items}) != len(items):
            raise ValueError("review 1-200 unique candidates")
        read_doc = self.store.read(nid, scope)
        checked_jobs = set()
        for item in items:
            row = self._row(read_doc, CANDIDATES, item["id"])
            if item["action"].lower() == "approve" and row["job_id"] not in checked_jobs:
                self._assert_fresh(nid, scope, self._row(read_doc, JOBS, row["job_id"]), actor)
                checked_jobs.add(row["job_id"])
        with self.store.transaction(nid, scope) as doc:
            rows = []
            evidence_cache, verified_jobs = {}, set()
            for item in items:
                row = self._row(doc, CANDIDATES, item["id"])
                check_version(row, item["expected_version"])
                if job_id and row["job_id"] != job_id:
                    raise ValueError("IMPORT_REVIEW_JOB_MISMATCH")
                job = self._row(doc, JOBS, row["job_id"])
                action = str(item["action"]).lower()
                if action not in {"approve", "reject", "reopen"}:
                    raise ValueError("unsupported import review action")
                if row["status"] in {"COMMITTING", "COMMITTED"} or job.get("commit_intent"):
                    raise ValueError("IMPORT_REVIEW_ALREADY_COMMITTED")
                if job["status"] not in {"NEEDS_REVIEW", "STALE"}:
                    raise ValueError("IMPORT_ANALYSIS_NOT_COMPLETE")
                if action == "approve":
                    self._validate_evidence(nid, row, evidence_cache, verified_jobs)
                rows.append((row, action))
            final = {row["id"]: {"approve": "APPROVED", "reject": "REJECTED", "reopen": "PENDING"}[action] for row, action in rows}
            for row, action in rows:
                if action == "approve":
                    for conflict in row["conflicts"]:
                        other = self._row(doc, CANDIDATES, conflict["candidate_id"])
                        if final.get(other["id"], other["status"]) == "APPROVED":
                            raise ValueError("IMPORT_CONFLICT_REQUIRES_RESOLUTION")
            for row, action in rows:
                self._touch(row, actor, action.upper())
                row.update(status=final[row["id"]], reviewed_by=actor, reviewed_at=now())
            return [copy.deepcopy(row) for row, _ in rows]

    def review(self, nid, scope, actor, item_id, action, expected_version):
        return self.review_batch(nid, scope, actor, [{"id": item_id, "action": action, "expected_version": expected_version}])[0]

    def commit(self, nid, scope, actor, job_id, expected_version, candidate_ids=None, *, reauthorize=None):
        if scope.get("mode") != "local":
            raise ValueError("IMPORT_BRANCH_PROMOTION_ADAPTER_REQUIRED")
        job = self.job(nid, scope, job_id)
        check_version(job, expected_version)
        if self.apply_service is None:
            raise ValueError("IMPORT_APPLY_NOT_CONFIGURED")
        if job["status"] == "COMMITTED":
            if candidate_ids is not None and sorted(candidate_ids) != sorted(job["commit_intent"]["candidate_ids"]):
                raise ValueError("IMPORT_COMMIT_SELECTION_CHANGED")
            return job
        self._assert_fresh(nid, scope, job, actor)
        with self.store.transaction(nid, scope) as doc:
            live = self._row(doc, JOBS, job_id)
            check_version(live, expected_version)
            if live["status"] not in {"NEEDS_REVIEW", "APPLYING", "PARTIAL"}:
                raise ValueError("IMPORT_JOB_NOT_COMMITTABLE")
            selected = sorted(candidate_ids) if candidate_ids is not None else (
                live.get("commit_intent", {}).get("candidate_ids") or sorted(
                    r["id"] for r in doc["collections"].get(CANDIDATES, {}).values()
                    if r["job_id"] == job_id and r["status"] == "APPROVED"))
            if not selected or len(selected) > 1000 or len(set(selected)) != len(selected):
                raise ValueError("commit 1-1000 unique explicitly approved candidates")
            payload = {kind: [] for kind in KINDS}
            evidence_cache, verified_jobs = {}, set()
            for cid in selected:
                candidate = self._row(doc, CANDIDATES, cid)
                if candidate["job_id"] != job_id or candidate["status"] not in {"APPROVED", "COMMITTING"}:
                    raise ValueError("IMPORT_CANDIDATE_NOT_APPROVED")
                if candidate["kind"] not in KINDS:
                    raise ValueError("IMPORT_TARGET_REQUIRES_MANUAL_PROMOTION_ADAPTER")
                self._validate_evidence(nid, candidate, evidence_cache, verified_jobs)
                name_key = "name" if candidate["kind"] in {"characters", "locations"} else "title"
                payload[candidate["kind"]].append({**candidate["attributes"], "candidate_id": cid,
                    "id": stable_id("semantic-import-target", job_id, cid), name_key: candidate["label"],
                    "chapter_number": candidate["source_evidence"][0]["chapter_number"],
                    "source_evidence": candidate["source_evidence"], "privacy_level": "LOCAL_ONLY"})
            intent = {"candidate_ids": selected, "payload": payload, "review_id": "semantic-v2-" + job_id}
            if live.get("commit_intent") and live["commit_intent"] != intent:
                raise ValueError("IMPORT_COMMIT_SELECTION_CHANGED")
            if not live.get("commit_intent"):
                self._touch(live, actor, "COMMIT_PREPARED")
                live.update(status="APPLYING", commit_intent=intent)
                for cid in selected:
                    candidate = self._row(doc, CANDIDATES, cid)
                    self._touch(candidate, actor, "COMMIT_PREPARED")
                    candidate["status"] = "COMMITTING"
        # The existing journal checkpoints before and after EACH upsert. A crash
        # in the ambiguous write/checkpoint gap fails closed for manual review.
        try:
            underlying = self.apply_service.novels
            owner = self

            class GuardedNovelService:
                def data_set(self, project, kind):
                    return underlying.data_set(project, kind)

                def review_import_knowledge(self, project, decision, candidates):
                    if reauthorize is not None:
                        reauthorize()
                    source_ids = {e["chapter_id"] for values in candidates.values() for value in values for e in value["source_evidence"]}
                    owner.assert_sources(nid, {cid: job["sources"][cid] for cid in source_ids})
                    return underlying.review_import_knowledge(project, decision, candidates)

            if reauthorize is not None:
                reauthorize()
            guarded = ImportApplyService(GuardedNovelService(), self.apply_service.root)
            result = guarded.apply(intent["review_id"], nid, payload, actor_id=actor)
        except Exception as exc:
            with self.store.transaction(nid, scope) as doc:
                live = self._row(doc, JOBS, job_id)
                if live["status"] != "COMMITTED" and live.get("commit_intent") == intent:
                    self._touch(live, actor, "COMMIT_INTERRUPTED")
                    live.update(status="PARTIAL", error_code="IMPORT_APPLY_INTERRUPTED")
                    if isinstance(exc, ImportApplyInterrupted):
                        live["apply_checkpoint"] = copy.deepcopy(exc.detail)
            raise
        with self.store.transaction(nid, scope) as doc:
            live = self._row(doc, JOBS, job_id)
            if live.get("commit_intent") != intent:
                raise ValueError("IMPORT_COMMIT_INTENT_CHANGED")
            if live["status"] != "COMMITTED":
                self._touch(live, actor, "COMMIT_COMPLETED")
                live.update(status="COMMITTED", applied=True, apply_checkpoint=copy.deepcopy(result))
                live.pop("error_code", None)
                for cid in selected:
                    candidate = self._row(doc, CANDIDATES, cid)
                    self._touch(candidate, actor, "COMMIT_COMPLETED")
                    candidate.update(status="COMMITTED", applied=True)
            return copy.deepcopy(live)

    def list_review_items(self, nid, scope):
        result = []
        for row in self.candidates(nid, scope):
            stale = row.get("stale", False)
            try:
                self.assert_sources(nid, row["sources"])
            except (StaleSourceError, FileNotFoundError):
                stale = True
            job = self.job(nid, scope, row["job_id"])
            allowed = []
            if row["status"] not in {"COMMITTING", "COMMITTED"} and not job.get("commit_intent") and job["status"] in {"NEEDS_REVIEW", "STALE"}:
                allowed = (["approve"] if not stale else []) + ["reject", "reopen"]
            result.append({**row, "domain": "import", "source": row["job_id"],
                           "source_versions": copy.deepcopy(row["sources"]), "stale": stale,
                           "preview": row["label"], "batch_safe": bool(allowed),
                           "allowed_actions": allowed})
        return result
