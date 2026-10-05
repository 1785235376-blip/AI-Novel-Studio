"""Evidence-bound local rubric findings using the existing review_threads authority.

Receipts live in ExperimentalStore. Review decisions live only in the original
creation workbench review threads (durable sidecar in both storage profiles).
No finding can apply a manuscript revision or promote Canon.
"""
from __future__ import annotations

from copy import deepcopy
import uuid
from typing import Literal, Protocol

from pydantic import Field, ValidationError

from .common import StaleSourceError, check_version, change_row, new_row, now
from .planning import StrictModel, collection, require_row, digest
from .style_analysis import SourceFencedService, paragraphs
from ..repositories.file.mutation_coordinator import workspace_mutation

FEATURE = "narrative_quality_judge_v2"
RUBRIC = {"id": "narrative-rules-v1", "version": 1, "title": "证据审稿规则 v1",
          "checks": ["EXACT_REPEATED_PARAGRAPH", "REVIEWED_WORLD_CONFLICT"],
          "limitations": ["重复不等于错误，引用、强调和题材惯例可忽略。", "世界冲突只比较已审核结构化资料，并要求选定章节内有原文定位。", "节奏、对白质量、人物动机、伏笔、场景目的和支线推进缺乏充分证据时弃权。", "无文学评分、概率或真实模型质量保证。"]}


class JudgeRunIn(StrictModel):
    chapter_ids: list[str] = Field(min_length=1, max_length=20)
    expected_versions: dict[str, int] = Field(min_length=1, max_length=20)
    rubric_id: Literal["narrative-rules-v1"] = "narrative-rules-v1"
    adapter_id: str | None = Field(default=None, max_length=160)


class JudgeEvidence(StrictModel):
    chapter_id: str = Field(min_length=1, max_length=240)
    chapter_version: int = Field(ge=1)
    paragraph: int = Field(ge=1)
    start: int = Field(ge=0)
    end: int = Field(ge=1)
    quote: str = Field(min_length=1, max_length=2000)


class ModelOpinion(StrictModel):
    category: Literal["PACING", "DIALOGUE", "CHARACTER", "FORESHADOWING", "SCENE_PURPOSE", "SUBPLOT", "REPETITION"]
    explanation: str = Field(min_length=1, max_length=2000)
    suggestion: str = Field(min_length=1, max_length=2000)
    evidence: list[JudgeEvidence] = Field(min_length=1, max_length=5)
    boundary: str = Field(min_length=1, max_length=1000)


class JudgeAdapterOutput(StrictModel):
    opinions: list[ModelOpinion] = Field(default_factory=list, max_length=20)


class JudgeAdapter(Protocol):
    """Explicitly injected local adapter. No remote fallback or implicit registration."""
    adapter_id: str
    model_identity: str
    execution_mode: Literal["LOCAL_MODEL"]
    def judge(self, request: dict) -> JudgeAdapterOutput: ...


class JudgeReviewIn(StrictModel):
    expected_version: int = Field(ge=1)
    action: Literal["review", "ignore", "reopen"]
    reason: str = Field(min_length=1, max_length=2000)
    revision_chapter_id: str | None = Field(default=None, max_length=240)
    revision_version: int | None = Field(default=None, ge=1)


def validate_evidence(evidence, chapters):
    validated = []
    for item in evidence:
        try:
            value = JudgeEvidence.model_validate(item).model_dump()
        except ValidationError:
            raise ValueError("judge evidence schema is invalid") from None
        chapter = chapters.get(value["chapter_id"])
        if not chapter or chapter["version"] != value["chapter_version"]:
            raise ValueError("judge evidence references an unselected source version")
        text = chapter.get("content", "")
        para = next((p for p in paragraphs(text) if p["paragraph"] == value["paragraph"]), None)
        if (not para or not (para["start"] <= value["start"] < value["end"] <= para["end"])
                or text[value["start"]:value["end"]] != value["quote"]):
            raise ValueError("judge evidence quote, offset or paragraph is invalid")
        validated.append(value)
    if not validated: raise ValueError("judge findings require source evidence")
    return validated


def anchor(chapter, text):
    if not text or len(text) > 2000: return None
    for para in paragraphs(chapter.get("content", "")):
        index = para["quote"].find(text)
        if index >= 0:
            start = para["start"] + index
            return {"chapter_id": chapter["id"], "chapter_version": chapter["version"], "paragraph": para["paragraph"], "start": start, "end": start + len(text), "quote": text}
    return None


class NarrativeJudgeService(SourceFencedService):
    RUNS = "narrative_judge_runs"

    def __init__(self, store, novels, chapters, creation, world, planning=None, adapters=()):
        super().__init__(store, novels, chapters)
        self.creation, self.world, self.planning = creation, world, planning
        self.model_coordinator = None
        self.adapters = {adapter.adapter_id: adapter for adapter in adapters}
        if len(self.adapters) != len(adapters): raise ValueError("duplicate judge adapter")

    def catalog(self, nid, scope):
        return {"chapters": self.chapter_catalog(nid, scope), "rubrics": [deepcopy(RUBRIC)],
                "adapters": [{"id": a.adapter_id, "model_identity": a.model_identity, "execution_mode": a.execution_mode,
                              "independence": "UNVERIFIED", "quality_verification": "NOT_VERIFIED"}
                             for a in self.adapters.values() if a.execution_mode == "LOCAL_MODEL"]}

    def _context(self, nid, scope, chapter_ids):
        state = self.store.read(nid, scope)
        # Context is limited to exact selected chapters. Unselected semantic
        # records never affect output counts, explanations, or adapter requests.
        world = {r["id"]: r for r in self.world.records(nid, scope)
                 if r["status"] == "APPROVED" and not r["stale"] and r.get("chapter_id") in chapter_ids}
        planning = {rid: row for rid, row in state.get("collections", {}).get("planning_nodes", {}).items()
                    if row.get("status") == "APPROVED" and row.get("scope") == scope
                    and set(row.get("links", {}).get("chapter_ids", []))
                    and set(row["links"]["chapter_ids"]).issubset(chapter_ids)}
        return world, planning

    def _context_fingerprint(self, nid, scope, chapter_ids):
        world, planning = self._context(nid, scope, chapter_ids)
        return digest([world, planning])

    def _fresh(self, nid, scope, receipt):
        self.assert_capture(nid, scope, receipt["sources"])
        if self._context_fingerprint(nid, scope, list(receipt["sources"])) != receipt["context_digest"]:
            raise StaleSourceError("reviewed world or planning context changed")

    def _finding_public(self, nid, scope, row, receipt=None):
        details = row.get("narrative_judge")
        if not details: raise FileNotFoundError(row["id"])
        receipt = receipt or require_row(self.store.read(nid, scope), self.RUNS, details["run_id"])
        try:
            self._fresh(nid, scope, receipt)
        except (ValueError, FileNotFoundError):
            return {"id": row["id"], "version": row["version"], "status": row["status"], "decision": details["decision"], "stale": True,
                    "evidence": [], "boundary": "来源已变化；旧证据与评语已隐藏，请重新审稿。"}
        return {"id": row["id"], "version": row["version"], "status": row["status"], **deepcopy(details), "stale": False,
                "review_history": deepcopy(row.get("history", [])), "messages": deepcopy(row["messages"])}

    def _threads(self, nid, scope):
        with self.creation.store._lock, workspace_mutation(self.creation.store.root, "creation-workbench"):
            return [r for r in self.creation._rows("review_threads") if self.creation._match(r, nid, scope) and r.get("narrative_judge")]

    def _public(self, nid, scope, receipt):
        result = {k: deepcopy(v) for k, v in receipt.items() if k not in {"sources", "context_digest", "finding_ids", "history", "request"}}
        try:
            self._fresh(nid, scope, receipt)
        except (ValueError, FileNotFoundError):
            return {"id": receipt["id"], "version": receipt["version"], "status": receipt["status"], "stale": True,
                    "findings": [], "abstentions": ["来源或审核资料已变化；旧结果已隐藏，请重新审稿。"], "verification": receipt["verification"], "model_called": receipt["model_called"],
                    "model_preview": None, "model_execution": deepcopy(receipt.get("model_execution"))}
        rows = {row["id"]: row for row in self._threads(nid, scope)}
        result["findings"] = [self._finding_public(nid, scope, rows[rid], receipt) for rid in receipt["finding_ids"] if rid in rows]
        result["stale"] = False
        return result

    def runs(self, nid, scope):
        return [self._public(nid, scope, row) for row in self.list(nid, scope, self.RUNS)]

    def run(self, nid, scope, rid):
        return self._public(nid, scope, require_row(self.store.read(nid, scope), self.RUNS, rid))

    def _deterministic(self, nid, scope, chapters):
        findings, seen = [], {}
        for chapter in chapters.values():
            for para in paragraphs(chapter.get("content", "")):
                text = para["quote"]
                if len(text.strip()) < 8 or len(text) > 2000: continue
                evidence = {"chapter_id": chapter["id"], "chapter_version": chapter["version"], **para}
                if text in seen:
                    findings.append({"code": "EXACT_REPEATED_PARAGRAPH", "category": "REPETITION", "severity": "INFO",
                                     "explanation": "选定文本中出现完全相同的段落。", "suggestion": "核对这是有意重复、引用还是需要精简的说明。",
                                     "boundary": "确定性文本相等，不是文学错误判定；可保留并说明理由。", "origin": "DETERMINISTIC", "evidence": [seen[text], evidence]})
                else: seen[text] = evidence
                if len(findings) >= 40: return findings, True
        world, _ = self._context(nid, scope, list(chapters))
        # Run the existing continuity authority, but require every referenced
        # record and its supporting phrase to be in the selected source scope.
        for finding in self.world.continuity(nid, scope)["items"]:
            ids = [finding["record_id"], *finding["related_record_ids"]]
            if not set(ids).issubset(world): continue
            evidence = []
            for rid in ids:
                row = world[rid]
                candidates = [row["data"].get(key) for key in ("description", "state", "from_state", "explanation")]
                proof = next((match for value in candidates if isinstance(value, str) and value and (match := anchor(chapters[row["chapter_id"]], value))), None)
                if not proof: break
                evidence.append(proof)
            if len(evidence) != len(ids): continue
            findings.append({"code": finding["code"], "category": "CHARACTER" if "CHARACTER" in finding["code"] else "WORLD_CONSISTENCY", "severity": "WARNING",
                             "explanation": finding["message"], "suggestion": "复核原文和已审核世界记录；有意的倒叙、不可靠叙述或变化可注明理由。",
                             "boundary": "冲突依据是已审核结构化记录；引文只定位对应陈述，不能证明作品存在错误。", "origin": "DETERMINISTIC",
                             "evidence": evidence, "world_record_ids": ids})
            if len(findings) >= 40: return findings, True
        return findings, False

    def create_run(self, nid, scope, actor, value, reauthorize=lambda: None):
        data = JudgeRunIn.model_validate(value.model_dump() if hasattr(value, "model_dump") else value)
        if set(data.expected_versions) != set(data.chapter_ids): raise ValueError("provide exactly the selected chapter versions")
        sources, chapters = self.capture(nid, scope, data.chapter_ids, data.expected_versions)
        context_digest = self._context_fingerprint(nid, scope, data.chapter_ids)
        adapter = self.adapters.get(data.adapter_id) if data.adapter_id else None
        if data.adapter_id and (adapter is None or adapter.execution_mode != "LOCAL_MODEL"):
            raise ValueError("JUDGE_LOCAL_ADAPTER_NOT_CONFIGURED")
        identity = {"adapter_id": adapter.adapter_id, "model_identity": adapter.model_identity, "execution_mode": adapter.execution_mode} if adapter else None
        run_id = str(uuid.uuid5(uuid.NAMESPACE_URL, digest([nid, scope, actor, sources, context_digest, data.model_dump(), identity])))
        existing = collection(self.store.read(nid, scope), self.RUNS).get(run_id)
        if existing:
            reauthorize(); return self._public(nid, scope, existing)
        findings, truncated = self._deterministic(nid, scope, chapters)
        if adapter:
            reauthorize(); self.assert_capture(nid, scope, sources)
            try:
                output = JudgeAdapterOutput.model_validate(adapter.judge({"rubric": deepcopy(RUBRIC), "chapters": deepcopy(list(chapters.values())), "privacy_level": "LOCAL_ONLY", "maximum_opinions": 20, "independence": "UNVERIFIED"}))
            except ValidationError:
                raise ValueError("JUDGE_ADAPTER_OUTPUT_INVALID") from None
            for opinion in output.opinions:
                findings.append({**opinion.model_dump(), "code": "MODEL_OPINION", "severity": "INFO", "origin": "MODEL_ASSESSMENT", "model": identity,
                                 "independence": "UNVERIFIED", "quality_verification": "NOT_VERIFIED"})
        for finding in findings: finding["evidence"] = validate_evidence(finding["evidence"], chapters)
        payload = {"status": "COMPLETED", "sources": sources, "context_digest": context_digest, "request": data.model_dump(),
                   "rubric": deepcopy(RUBRIC), "finding_ids": [], "privacy_level": "LOCAL_ONLY", "model_called": bool(adapter),
                   "verification": "LOCAL_ADAPTER_UNVERIFIED" if adapter else "DETERMINISTIC_RULES", "findings_truncated": truncated,
                   "abstentions": ["未对节奏、对白质量、人物动机、伏笔、场景目的和支线推进作出确定性判断。"],
                   "review_storage": self.creation.store.storage_mode, "receipt_storage": self.store.storage_mode}
        receipt = new_row(nid, scope, actor, payload); receipt["id"] = run_id
        # Stable IDs let a retry recover a failed receipt write without adding a
        # second review thread. The existing sidecar authority remains singular.
        with self.creation.store._lock, workspace_mutation(self.creation.store.root, "creation-workbench"):
            with self.store.transaction(nid, scope) as state:
                if run_id in collection(state, self.RUNS):
                    reauthorize(); return self._public(nid, scope, collection(state, self.RUNS)[run_id])
                if len(collection(state, self.RUNS)) >= 200: raise ValueError("judge receipt limit reached")
                self._fresh(nid, scope, receipt); reauthorize()
                rows = self.creation._rows("review_threads")
                for index, finding in enumerate(findings):
                    rid = str(uuid.uuid5(uuid.UUID(run_id), str(index)))
                    receipt["finding_ids"].append(rid)
                    existing_thread = next((r for r in rows if r["id"] == rid), None)
                    if existing_thread:
                        if not self.creation._match(existing_thread, nid, scope): raise ValueError("review thread scope conflict")
                        continue
                    proof = finding["evidence"][0]
                    rows.append({"id": rid, "novel_id": nid, "scope": deepcopy(scope), "anchor": {"chapter_id": proof["chapter_id"], "chapter_version": proof["chapter_version"], "quote": proof["quote"], "content_sha256": sources[proof["chapter_id"]]["digest"]},
                                 "status": "OPEN", "version": 1, "created_at": now(), "updated_at": now(),
                                 "messages": [{"id": str(uuid.uuid4()), "actor_id": actor, "text": finding["explanation"], "at": now()}],
                                 "history": [{"action": "JUDGE_CREATED", "actor_id": actor, "at": now()}],
                                 "narrative_judge": {**finding, "run_id": run_id, "decision": "PENDING", "privacy_level": "LOCAL_ONLY"}})
                self._fresh(nid, scope, receipt); reauthorize()
                self.creation.store._write("review_threads", rows)
                collection(state, self.RUNS)[run_id] = receipt
        return self._public(nid, scope, receipt)

    def record_model_result(self, ctx, previous, execution, opinions, guard):
        """Publish validated model opinions into the original review authority.

        Stable per-job finding IDs recover a sidecar write without reexecuting
        the model. All output is validated before the first review-thread write.
        """
        nid, scope, actor, run_id = ctx.novel_id, ctx.scope, ctx.actor, previous['id']
        if opinions is None and execution == previous.get('model_execution'):
            self._fresh(nid, scope, previous); guard()
            return self.run(nid, scope, run_id)
        with self.creation.store._lock, workspace_mutation(self.creation.store.root, 'creation-workbench'):
            with self.store.transaction(nid, scope) as state:
                receipt = require_row(state, self.RUNS, run_id)
                self._fresh(nid, scope, receipt); guard()
                check_version({k: receipt[k] for k in ('id', 'version', 'status')}, previous['version'])
                if receipt['created_by'] != actor: raise ValueError('JUDGE_MODEL_ACTOR_MISMATCH')
                if receipt.get('model_execution') != previous.get('model_execution'): raise ValueError('JUDGE_MODEL_RECEIPT_CHANGED')
                ids = list(receipt['finding_ids'])
                if opinions is not None:
                    _, chapters = self.capture(nid, scope, list(receipt['sources']))
                    for opinion in opinions: validate_evidence(opinion['evidence'], chapters)
                    route = receipt['model_preview']['broker']['chosen']
                    identity = {k: deepcopy(route[k]) for k in ('route_id', 'provider_id', 'model_id', 'fingerprint', 'identity', 'synthetic')}
                    rows = self.creation._rows('review_threads')
                    for index, opinion in enumerate(opinions):
                        rid = str(uuid.uuid5(uuid.UUID(run_id), 'model:' + execution['job_id'] + ':' + str(index)))
                        if rid not in ids: ids.append(rid)
                        existing = next((r for r in rows if r['id'] == rid), None)
                        if existing:
                            if not self.creation._match(existing, nid, scope): raise ValueError('review thread scope conflict')
                            continue
                        proof = opinion['evidence'][0]
                        finding = {**deepcopy(opinion), 'code': 'MODEL_OPINION', 'severity': 'INFO', 'origin': 'MODEL_ASSESSMENT',
                            'model': identity, 'job_id': execution['job_id'], 'rubric': receipt['model_preview']['rubric'],
                            'independence': 'UNVERIFIED', 'quality_verification': receipt['model_preview']['quality_verification'],
                            'run_id': run_id, 'decision': 'PENDING', 'privacy_level': 'LOCAL_ONLY'}
                        rows.append({'id': rid, 'novel_id': nid, 'scope': deepcopy(scope),
                            'anchor': {'chapter_id': proof['chapter_id'], 'chapter_version': proof['chapter_version'],
                                'quote': proof['quote'], 'content_sha256': receipt['sources'][proof['chapter_id']]['digest']},
                            'status': 'OPEN', 'version': 1, 'created_at': now(), 'updated_at': now(),
                            'messages': [{'id': str(uuid.uuid4()), 'actor_id': actor, 'text': opinion['explanation'], 'at': now()}],
                            'history': [{'action': 'JUDGE_MODEL_CREATED', 'actor_id': actor, 'at': now()}], 'narrative_judge': finding})
                    self._fresh(nid, scope, receipt); guard()
                    self.creation.store._write('review_threads', rows)
                change_row(receipt, actor, receipt['version'], lambda r: r.update(model_execution=deepcopy(execution), finding_ids=ids,
                    model_called=execution['model_called'], verification='RULES_AND_UNVERIFIED_MODEL' if opinions is not None else r['verification']))
                self._fresh(nid, scope, receipt); guard()
        return self.run(nid, scope, run_id)

    def review(self, nid, scope, actor, rid, value, reauthorize=lambda: None):
        data = JudgeReviewIn.model_validate(value.model_dump() if hasattr(value, "model_dump") else value)
        if bool(data.revision_chapter_id) != bool(data.revision_version): raise ValueError("revision linkage requires both chapter and version")
        with self.creation.store._lock, workspace_mutation(self.creation.store.root, "creation-workbench"):
            rows = self.creation._rows("review_threads")
            row = self.creation._find(rows, nid, scope, rid)
            info = row.get("narrative_judge")
            if not info: raise FileNotFoundError(rid)
            receipt = require_row(self.store.read(nid, scope), self.RUNS, info["run_id"])
            self._fresh(nid, scope, receipt)
            check_version(row, data.expected_version)
            if data.revision_chapter_id:
                if data.revision_chapter_id not in receipt["sources"]: raise ValueError("revision must refer to a selected chapter")
                self.capture(nid, scope, [data.revision_chapter_id], {data.revision_chapter_id: data.revision_version})
            reauthorize()
            info["decision"] = {"review": "REVIEWED", "ignore": "IGNORED", "reopen": "PENDING"}[data.action]
            info["revision"] = {"chapter_id": data.revision_chapter_id, "version": data.revision_version} if data.revision_chapter_id else None
            row["status"] = "OPEN" if data.action == "reopen" else "RESOLVED"
            row["messages"].append({"id": str(uuid.uuid4()), "actor_id": actor, "text": data.reason, "at": now()})
            row["history"].append({"action": data.action.upper(), "reason": data.reason, "actor_id": actor, "at": now()})
            row.update(version=row["version"] + 1, updated_at=now())
            self._fresh(nid, scope, receipt); reauthorize()
            self.creation.store._write("review_threads", rows)
            return self._finding_public(nid, scope, row, receipt)

    def list_review_items(self, nid, scope):
        output = []
        for receipt in self.list(nid, scope, self.RUNS):
            run = self._public(nid, scope, receipt)
            if run["stale"]: continue
            for row in run["findings"]:
                output.append({**row, "novel_id": nid, "scope": scope, "source": "narrative_judge", "preview": row["explanation"],
                               "target": {"module": "narrative_quality_judge_v2", "run_id": receipt["id"], "finding_id": row["id"]},
                               "allowed_actions": [], "risk": "ADVISORY_NO_AUTOMATIC_EDITS"})
        return output
