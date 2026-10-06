"""Bounded local statistics derived from the existing, versioned STYLE authority.

No model, egress, manuscript edit or second style-profile store is created here.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import re
import uuid
from typing import Literal

from pydantic import Field

from .common import DomainService, StaleSourceError, new_row, check_version, change_row, now
from .planning import StrictModel, collection, require_row, digest, entity_sources
from ..services.creation_workbench_service import WorkbenchRecordIn
from ..source_privacy import content_digest, source_privacy_status

FEATURE = "style_dna_v2"
METHOD = "unicode-style-statistics-v2-independent-samples"
OPERATIONS = ("continue", "rewrite", "polish", "brainstorm", "review")
MAX_CHARACTERS = 100_000


class StyleProfileIn(StrictModel):
    title: str = Field(min_length=1, max_length=200)
    instructions: str = Field(min_length=1, max_length=120)
    rules: list[str] = Field(default_factory=list, max_length=50)
    chapter_ids: list[str] = Field(default_factory=list, max_length=20)
    character_ids: list[str] = Field(default_factory=list, max_length=50)


class StyleProfileEditIn(StyleProfileIn):
    expected_version: int = Field(ge=1)


class SampleIn(StrictModel):
    chapter_id: str = Field(min_length=1, max_length=240)
    expected_version: int = Field(ge=1)
    start: int = Field(default=0, ge=0)
    end: int | None = Field(default=None, ge=1)


class ComparisonIn(StrictModel):
    chapter_id: str = Field(min_length=1, max_length=240)
    expected_version: int = Field(ge=1)
    language: Literal["en", "zh"]


class StyleAnalysisIn(StrictModel):
    style_id: str = Field(min_length=1, max_length=240)
    expected_style_version: int = Field(ge=1)
    language: Literal["en", "zh"]
    samples: list[SampleIn] = Field(min_length=1, max_length=20)
    comparison: ComparisonIn | None = None
    operations: list[Literal["continue", "rewrite", "polish", "brainstorm", "review"]] = Field(default_factory=lambda: list(OPERATIONS), min_length=1, max_length=5)


class StylePreviewIn(StrictModel):
    expected_version: int = Field(ge=1)
    operation: Literal["continue", "rewrite", "polish", "brainstorm", "review"]
    character_id: str | None = Field(default=None, max_length=240)


def paragraphs(text):
    """One nonempty line is one paragraph, exact Python Unicode offsets."""
    nonempty = (m for m in re.finditer(r"[^\r\n]+", text) if m.group().strip())
    return [{"paragraph": i + 1, "start": m.start(), "end": m.end(), "quote": m.group()}
            for i, m in enumerate(nonempty)]


def metrics(text, language):
    if language not in {"en", "zh"}:
        raise ValueError("unsupported statistics language")
    if len(text) > MAX_CHARACTERS:
        raise ValueError("statistics input exceeds bounded character limit")
    units = re.findall(r"[A-Za-z]+(?:['’][A-Za-z]+)?", text.casefold()) if language == "en" else re.findall(r"[\u3400-\u4dbf\u4e00-\u9fff]", text)
    sentence_parts = [s for s in re.split(r"[.!?]+" if language == "en" else r"[。！？]+", text) if s.strip()]
    sentence_lengths = [len(re.sub(r"\s", "", s)) for s in sentence_parts]
    paras = paragraphs(text)
    para_lengths = [len(re.sub(r"\s", "", p["quote"])) for p in paras]
    vocabulary = Counter(units)
    dialogue = list(re.finditer(r'“[^”\n]*”|「[^」\n]*」|『[^』\n]*』|"[^"\n]*"', text))
    cue_words = ("i", "me", "my", "we", "our", "you", "he", "she", "they") if language == "en" else ("我", "我们", "你", "他", "她", "他们")
    cues = {word: len(re.findall(r"\b" + re.escape(word) + r"\b", text.casefold())) if language == "en" else text.count(word) for word in cue_words}
    return {"characters": len(text), "nonspace_characters": len(re.sub(r"\s", "", text)),
            "unit": "LATIN_WORD" if language == "en" else "HAN_CHARACTER_NOT_WORD", "unit_count": len(units),
            "sentence_count": len(sentence_parts), "sentence_lengths_nonspace": sentence_lengths,
            "paragraph_count": len(paras), "paragraph_lengths_nonspace": para_lengths,
            "dialogue_characters": sum(max(0, len(m.group()) - 2) for m in dialogue),
            "dialogue_spans": [{"start": m.start(), "end": m.end()} for m in dialogue],
            "sentence_length_mean": {"numerator": sum(sentence_lengths), "denominator": len(sentence_lengths)},
            "paragraph_length_mean": {"numerator": sum(para_lengths), "denominator": len(para_lengths)},
            "dialogue_share_nonspace": {"numerator": sum(len(re.sub(r"\s", "", m.group()[1:-1])) for m in dialogue), "denominator": len(re.sub(r"\s", "", text))},
            "repeated_unit_share": {"numerator": len(units) - len(vocabulary), "denominator": len(units)},
            "unique_units": len(vocabulary), "repeated_units": [{"unit": k, "count": v} for k, v in sorted(vocabulary.items(), key=lambda kv: (-kv[1], kv[0])) if v > 1][:30],
            "frequent_units": [{"unit": k, "count": v} for k, v in sorted(vocabulary.items(), key=lambda kv: (-kv[1], kv[0]))][:30],
            "punctuation_counts": dict(sorted(Counter(c for c in text if c in '.,!?;:—…，。！？；：、“”「」『』\"').items())),
            "perspective_lexical_cues": cues, "sample_sufficiency": "SHORT_SAMPLE" if len(sentence_parts) < 5 else "DESCRIPTIVE_ONLY"}


def sample_statistics(chapters, samples, language):
    """Independent source samples with absolute raw Markdown Unicode anchors."""
    texts, measured = [], []
    for sample in samples:
        source = chapters[sample['chapter_id']].get('content', '')
        text = source[sample['start']:sample['end']]
        texts.append(text)
        local = metrics(text, language)
        locations = []
        for paragraph in paragraphs(source):
            start, end = max(sample['start'], paragraph['start']), min(sample['end'], paragraph['end'])
            if start < end:
                locations.append({'paragraph': paragraph['paragraph'], 'start': start, 'end': end,
                                  'quote': source[start:end], 'partial_paragraph': start != paragraph['start'] or end != paragraph['end']})
        measured.append({**sample, 'metrics': local, 'coordinate': 'RAW_MARKDOWN_UNICODE_CODEPOINT',
                         'paragraphs': locations[:200], 'paragraphs_truncated': len(locations) > 200,
                         'dialogue_spans': [{'start': sample['start'] + span['start'], 'end': sample['start'] + span['end']} for span in local['dialogue_spans']]})
    aggregate = metrics('', language)
    pattern = r"[A-Za-z]+(?:['’][A-Za-z]+)?" if language == 'en' else r"[\u3400-\u4dbf\u4e00-\u9fff]"
    vocabulary = Counter(unit for text in texts for unit in re.findall(pattern, text.casefold()))
    aggregate['unique_units'] = len(vocabulary)
    ordered = sorted(vocabulary.items(), key=lambda kv: (-kv[1], kv[0]))
    aggregate['frequent_units'] = [{'unit': unit, 'count': count} for unit, count in ordered[:30]]
    aggregate['repeated_units'] = [{'unit': unit, 'count': count} for unit, count in ordered if count > 1][:30]
    for key in ('characters', 'nonspace_characters', 'sentence_count', 'paragraph_count', 'dialogue_characters', 'unit_count'):
        aggregate[key] = sum(row['metrics'][key] for row in measured)
    aggregate['repeated_unit_share'] = {'numerator': aggregate['unit_count'] - len(vocabulary), 'denominator': aggregate['unit_count']}
    for key in ('punctuation_counts', 'perspective_lexical_cues'):
        combined = Counter()
        for row in measured: combined.update(row['metrics'][key])
        aggregate[key] = dict(sorted(combined.items()))
    for key in ('sentence_lengths_nonspace', 'paragraph_lengths_nonspace'):
        aggregate[key] = [value for row in measured for value in row['metrics'][key]]
    for key in ('sentence_length_mean', 'paragraph_length_mean', 'dialogue_share_nonspace'):
        aggregate[key] = {part: sum(row['metrics'][key][part] for row in measured) for part in ('numerator', 'denominator')}
    aggregate['dialogue_spans'] = []
    aggregate['dialogue_location'] = 'SOURCE_LOCAL_SAMPLE_METRICS'
    aggregate['sample_sufficiency'] = 'SHORT_SAMPLE' if aggregate['sentence_count'] < 5 else 'DESCRIPTIVE_ONLY'
    return aggregate, measured


class SourceFencedService(DomainService):
    """Only author-scoped current chapter sources; no character knowledge query."""
    def capture(self, nid, scope, chapter_ids, expected=None):
        self.novels.get(nid)
        if len(chapter_ids) > 20 or len(set(chapter_ids)) != len(chapter_ids):
            raise ValueError("select at most 20 unique chapter sources")
        available = {r["id"] for r in self.chapters.list(nid)}
        sources, chapters = {}, {}
        for cid in chapter_ids:
            chapter = self.chapters.get(cid)
            if chapter.get("novel_id") != nid or chapter.get("branch_id") != scope.get("branch_id") or cid not in available:
                raise FileNotFoundError(cid)
            if expected is not None and chapter.get("version") != expected.get(cid):
                raise StaleSourceError("source version changed; select its current version")
            policy = source_privacy_status(chapter, scope.get("branch_id"), self.store.root)
            sources[cid] = {"version": chapter["version"], "digest": content_digest(chapter),
                            "branch_id": chapter.get("branch_id"), "privacy": policy,
                            "metadata_digest": digest({k: chapter.get(k) for k in ("title", "number", "status", "archived_at")})}
            chapters[cid] = chapter
        if sum(len(row.get("content", "")) for row in chapters.values()) > MAX_CHARACTERS:
            raise ValueError("selected chapter sources exceed 100000 characters; choose fewer chapters")
        return sources, chapters

    def assert_capture(self, nid, scope, sources):
        try:
            current, _ = self.capture(nid, scope, list(sources))
        except (ValueError, FileNotFoundError, KeyError) as exc:
            raise StaleSourceError("source unavailable; select current authorized sources") from exc
        if current != sources:
            raise StaleSourceError("source content, version, branch or privacy changed")

    def chapter_catalog(self, nid, scope):
        self.novels.get(nid)
        return [{"id": row["id"], "title": row.get("title", str(row.get("number", row["id"]))),
                 "version": row["version"], "characters": len(row.get("content", ""))}
                for row in self.chapters.list(nid) if row.get("novel_id") == nid and row.get("branch_id") == scope.get("branch_id")]


class StyleAnalysisService(SourceFencedService):
    ANALYSES = "style_analyses"

    def __init__(self, store, novels, chapters, creation):
        super().__init__(store, novels, chapters)
        self.creation = creation
        self.model_coordinator = None

    def profile(self, nid, scope, rid):
        row = self.creation.get_record(nid, scope, rid)
        if row["kind"] != "STYLE":
            raise FileNotFoundError(rid)
        return row

    def catalog(self, nid, scope):
        rows = self.creation.list_records(nid, scope, "STYLE")["items"]
        return {"styles": [{k: v for k, v in row.items() if k != "history"} for row in rows],
                "chapters": self.chapter_catalog(nid, scope),
                "characters": [{"id": r["id"], "name": r.get("name", r["id"])} for r in self.novels.data_set(nid, "characters") if not r.get("branch_id") or r.get("branch_id") == scope.get("branch_id")],
                "operations": list(OPERATIONS), "model_called": False}

    def save_profile(self, nid, scope, actor, value, rid=None, reauthorize=lambda: None):
        data = (StyleProfileEditIn if rid else StyleProfileIn).model_validate(value.model_dump() if hasattr(value, "model_dump") else value)
        payload = data.model_dump(exclude={"expected_version"})
        self.capture(nid, scope, payload["chapter_ids"])
        entity_sources(self, nid, scope, {"character_ids": payload["character_ids"]})
        previous = self.profile(nid, scope, rid) if rid else {}
        body = WorkbenchRecordIn.model_validate({**{k: previous[k] for k in WorkbenchRecordIn.model_fields if k in previous}, **payload, "kind": "STYLE"})
        reauthorize()
        self.capture(nid, scope, payload["chapter_ids"])
        entity_sources(self, nid, scope, {"character_ids": payload["character_ids"]})
        return self.creation.save_record(nid, scope, actor, body, rid, getattr(data, "expected_version", None))

    def transition(self, nid, scope, actor, rid, action, version, reauthorize=lambda: None):
        row = self.profile(nid, scope, rid)
        if action not in {"approve", "archive"}:
            raise ValueError("unsupported style action")
        if action == "approve":
            self.capture(nid, scope, row["chapter_ids"], row["source_versions"])
        reauthorize()
        return self.creation.transition_record(nid, scope, actor, rid, action, version)

    def _fresh(self, nid, scope, row):
        self.assert_capture(nid, scope, row["sources"])
        profile = self.profile(nid, scope, row["style_id"])
        if digest(profile) != row["style_digest"] or profile["status"] == "ARCHIVED":
            raise StaleSourceError("style profile or its selected samples changed")

    def _public(self, nid, scope, row):
        try:
            self._fresh(nid, scope, row)
        except (ValueError, FileNotFoundError):
            return {"id": row["id"], "version": row["version"], "style_id": row["style_id"], "status": row["status"],
                    "stale": True, "privacy_level": "LOCAL_ONLY", "limitations": ["来源已变化；旧派生指标已隐藏，请重新分析。"],
                    "model_preview": None, "model_assessments": [], "model_opinion_state": "STALE",
                    "model_execution": deepcopy(row.get('model_execution'))}
        return {**deepcopy(row), "stale": False}

    def analyses(self, nid, scope):
        return [self._public(nid, scope, row) for row in self.list(nid, scope, self.ANALYSES)]

    def analysis(self, nid, scope, rid):
        return self._public(nid, scope, self.get(nid, scope, self.ANALYSES, rid))

    def record_model_result(self, ctx, previous, execution, opinions, guard):
        """Atomic annotations on the original analysis; deterministic data stays intact."""
        from .style_analysis_model import validate_style_opinions
        nid, scope, actor = ctx.novel_id, ctx.scope, ctx.actor
        if opinions is None and execution == previous.get('model_execution'):
            self._fresh(nid, scope, previous); guard()
            return self.analysis(nid, scope, previous['id'])
        with self.store.transaction(nid, scope) as state:
            row = require_row(state, self.ANALYSES, previous['id'])
            check_version({key: row[key] for key in ('id', 'version', 'status')}, previous['version'])
            self._fresh(nid, scope, row); guard()
            if row['created_by'] != actor: raise ValueError('STYLE_MODEL_ACTOR_MISMATCH')
            if row.get('model_execution') != previous.get('model_execution'): raise ValueError('STYLE_MODEL_RECEIPT_CHANGED')
            assessments = deepcopy(row.get('model_assessments', []))
            opinion_state = row.get('model_opinion_state', 'NOT_REQUESTED')
            if opinions is not None:
                if row['model_execution']['status'] in {'CANCELLED', 'FAILED', 'COMPLETED'}:
                    raise ValueError('STYLE_MODEL_NO_LONGER_ACTIVE')
                _, chapters = self.capture(nid, scope, list(row['sources']))
                values = validate_style_opinions(opinions, chapters, row['samples'])
                chosen = row['model_preview']['broker']['chosen']
                identity = {key: deepcopy(chosen[key]) for key in ('route_id', 'provider_id', 'model_id', 'fingerprint', 'identity', 'synthetic')}
                assessments = [{**opinion, 'id': str(uuid.uuid5(uuid.UUID(row['id']), 'style-opinion:' + execution['job_id'] + ':' + str(index))),
                    'origin': 'MODEL_DERIVED', 'decision': 'PENDING', 'review_history': [], 'model': identity,
                    'job_id': execution['job_id'], 'rubric': deepcopy(row['model_preview']['rubric']),
                    'independence': 'UNVERIFIED', 'quality_verification': row['model_preview']['quality_verification']}
                    for index, opinion in enumerate(values)]
                opinion_state = 'AVAILABLE' if assessments else 'ABSTAINED'
            elif execution['status'] in {'FAILED', 'CANCELLED', 'UNKNOWN'}:
                opinion_state = execution['status']
            change_row(row, actor, row['version'], lambda value: value.update(model_execution=deepcopy(execution),
                model_assessments=assessments, model_opinion_state=opinion_state, model_called=execution['model_called']))
            self._fresh(nid, scope, row); guard()
        return self.analysis(nid, scope, previous['id'])

    def review_opinion(self, nid, scope, actor, rid, opinion_id, value, guard):
        from .style_analysis_model import StyleOpinionReviewIn
        body = StyleOpinionReviewIn.model_validate(value.model_dump() if hasattr(value, 'model_dump') else value)
        with self.store.transaction(nid, scope) as state:
            row = require_row(state, self.ANALYSES, rid)
            check_version({key: row[key] for key in ('id', 'version', 'status')}, body.expected_version)
            self._fresh(nid, scope, row); guard()
            opinion = next((item for item in row.get('model_assessments', []) if item['id'] == opinion_id), None)
            if not opinion: raise FileNotFoundError(opinion_id)
            def update(current):
                opinion['decision'] = {'review': 'REVIEWED', 'ignore': 'IGNORED', 'reopen': 'PENDING'}[body.action]
                opinion['review_history'].append({'action': body.action, 'reason': body.reason, 'actor_id': actor, 'at': now()})
            change_row(row, actor, body.expected_version, update)
            self._fresh(nid, scope, row); guard()
        return self.analysis(nid, scope, rid)

    def analyze(self, nid, scope, actor, value, reauthorize=lambda: None):
        data = StyleAnalysisIn.model_validate(value.model_dump() if hasattr(value, "model_dump") else value)
        profile = self.profile(nid, scope, data.style_id)
        check_version(profile, data.expected_style_version)
        if profile["status"] == "ARCHIVED": raise ValueError("archived style cannot be analyzed")
        sample_ids = [s.chapter_id for s in data.samples]
        if not set(sample_ids).issubset(profile["chapter_ids"]):
            raise ValueError("samples must be selected in the existing STYLE record")
        expected = {s.chapter_id: s.expected_version for s in data.samples}
        if any(expected[s.chapter_id] != s.expected_version for s in data.samples):
            raise StaleSourceError("sample ranges disagree on the chapter version")
        if data.comparison:
            if data.comparison.chapter_id in expected and expected[data.comparison.chapter_id] != data.comparison.expected_version:
                raise StaleSourceError("comparison source version conflicts")
            expected[data.comparison.chapter_id] = data.comparison.expected_version
        sources, chapters = self.capture(nid, scope, list(expected), expected)
        texts, ranges, intervals = [], [], {}
        for sample in data.samples:
            text = chapters[sample.chapter_id].get("content", "")
            end = sample.end if sample.end is not None else len(text)
            if sample.start >= end or end > len(text): raise ValueError("sample range must select existing source text")
            if any(sample.start < hi and lo < end for lo, hi in intervals.get(sample.chapter_id, [])):
                raise ValueError("sample ranges must not overlap or double-count text")
            intervals.setdefault(sample.chapter_id, []).append((sample.start, end))
            texts.append(text[sample.start:end]); ranges.append({**sample.model_dump(), "end": end})
        measured, sample_metrics = sample_statistics(chapters, ranges, data.language)
        comparison = None
        if data.comparison:
            target = chapters[data.comparison.chapter_id].get("content", "")
            target_metrics = metrics(target, data.comparison.language)
            comparable = data.language == data.comparison.language
            comparison = {**data.comparison.model_dump(), "metrics": target_metrics, "comparable": comparable,
                          "difference_counts": {k: target_metrics[k] - measured[k] for k in ("sentence_count", "paragraph_count", "unit_count", "dialogue_characters")} if comparable else {},
                          "paragraphs": [{**p, "metrics": metrics(p["quote"], data.comparison.language)} for p in paragraphs(target)[:200]],
                          "paragraphs_truncated": len(paragraphs(target)) > 200,
                          "interpretation": "RAW_COUNT_DIFFERENCES_NOT_QUALITY_OR_NORMALIZED_DRIFT" if comparable else "LANGUAGE_METHODS_NOT_COMPARABLE"}
        payload = {"style_id": profile["id"], "style_version": profile["version"], "style_digest": digest(profile),
                   "sources": sources, "samples": ranges, "language": data.language, "operations": data.operations,
                   "method_version": METHOD, "metric_kind": "DETERMINISTIC_METRIC", "metrics": measured,
                   "sample_metrics": sample_metrics, "comparison": comparison, "status": "COMPLETED",
                   "model_opinion_state": "NOT_REQUESTED",
                   "unmeasured": ["DESCRIPTION_RATIO", "SENSORY_MEANING_RATIO", "NARRATIVE_DISTANCE", "EMOTIONAL_TONE", "RHYTHM", "HUMOR", "IMAGERY"],
                   "privacy_level": "LOCAL_ONLY", "model_assessments": [], "model_called": False,
                   "limitations": ["句子按语言标点切分，段落按非空行切分；长度为非空白 Unicode 字符。缩写与引号嵌套可能误分。", "英文只统计拉丁字母单词；中文统计汉字而非分词。不同语言不共用阈值。", "对白仅按成对引号近似计数；人称词频不等于叙事视角。", "少于五个句子标为短样本。无校准评分、匹配百分比或文学质量判断。", "适用任务用于本次预览范围；只有现有 STYLE instructions 会进入既有生成上下文，rules 供作者参考。"]}
        receipt_id = str(uuid.uuid5(uuid.NAMESPACE_URL, digest([METHOD, nid, scope, actor, payload])))
        with self.store.transaction(nid, scope) as state:
            self.assert_capture(nid, scope, sources)
            if digest(self.profile(nid, scope, profile["id"])) != payload["style_digest"]: raise StaleSourceError("style changed during analysis")
            reauthorize()
            existing = collection(state, self.ANALYSES).get(receipt_id)
            if existing: return self._public(nid, scope, existing)
            if len(collection(state, self.ANALYSES)) >= 200: raise ValueError("analysis receipt limit reached")
            row = new_row(nid, scope, actor, payload); row["id"] = receipt_id
            collection(state, self.ANALYSES)[row["id"]] = row
        return self._public(nid, scope, row)

    def preview(self, nid, scope, rid, value, reauthorize=lambda: None):
        data = StylePreviewIn.model_validate(value.model_dump() if hasattr(value, "model_dump") else value)
        profile = self.profile(nid, scope, rid)
        check_version(profile, data.expected_version)
        self.capture(nid, scope, profile["chapter_ids"], profile["source_versions"])
        if profile["character_ids"] and data.character_id not in profile["character_ids"]:
            raise ValueError("select one of the style's declared characters")
        if data.character_id: entity_sources(self, nid, scope, {"character_ids": [data.character_id]})
        inputs = self.creation.generation_inputs(nid, scope, rid)
        reauthorize()
        if digest(self.profile(nid, scope, rid)) != digest(profile):
            raise StaleSourceError("style changed during context preview")
        self.capture(nid, scope, profile["chapter_ids"], profile["source_versions"])
        result = {"style_id": rid, "style_version": profile["version"], "instructions": inputs["style"],
                  "rules": profile["rules"], "operation": data.operation, "character_id": data.character_id,
                  "privacy_level": profile["privacy_level"], "context_injection": "INSTRUCTIONS_ONLY",
                  "rules_usage": "REFERENCE_ONLY", "model_called": False}
        return {**result, "preview_digest": digest(result)}
