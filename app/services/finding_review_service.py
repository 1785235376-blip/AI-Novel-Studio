"""Versioned human feedback in the existing continuity/narrative finding owners.

Review is advisory. It never edits prose or Canon. Suppression is valid only for
one rule fingerprint AND one exact source snapshot, and is rechecked on reads.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
from hashlib import sha256
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ..experimental.common import now
from ..manuscript_sources import scoped_chapters
from ..source_privacy import content_digest

MAX_HISTORY = 100
MAX_FINDINGS = 500
OWNER = 'FINDING_REVIEW_V1'


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), default=str).encode()).hexdigest()


class FindingReviewConflict(ValueError):
    def __init__(self, code, current=None):
        self.code, self.current = code, current
        super().__init__(code)


class FindingCheckIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    chapter_id: str = Field(min_length=1, max_length=200)
    expected_source_version: int = Field(ge=1)
    # Explicit author-supplied observations remain distinguishable from stored facts.
    facts: dict = Field(default_factory=dict)


class FindingDecisionIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expected_version: int = Field(ge=1)
    source_digest: str = Field(pattern='^[a-f0-9]{64}$')
    finding_fingerprint: str = Field(pattern='^[a-f0-9]{64}$')
    action: Literal['resolve', 'intentional', 'reopen', 'feedback']
    reason: str = Field(min_length=1, max_length=2000)
    operation_id: str = Field(min_length=1, max_length=120)
    confirmed: Literal[True]


def checkpoint(row, actor, action, reason):
    history = row.setdefault('review_history', [])
    if len(history) >= MAX_HISTORY:
        raise ValueError('FINDING_HISTORY_LIMIT: retained history is full; existing review remains readable')
    history.append({'version': row['review_version'], 'status': row['status'], 'action': action,
                    'reason': reason, 'actor_id': actor, 'timestamp': now(),
                    'source_digest': row['source_digest'], 'finding_fingerprint': row['finding_fingerprint']})
    row['review_version'] += 1
    row['updated_at'] = now()


class FindingReviewService:
    def __init__(self, continuity, narrative, chapters, novels):
        self.continuity, self.narrative = continuity, narrative
        self.chapters, self.novels = chapters, novels

    def _repository(self, kind):
        if kind not in {'continuity', 'narrative'}: raise ValueError('FINDING_KIND_INVALID')
        return self.continuity.repository if kind == 'continuity' else self.narrative.repository

    def _scope(self, nid, scope):
        if not isinstance(scope, dict) or scope.get('novel_id') != nid or scope.get('mode') not in {'local', 'collaboration'}:
            raise ValueError('FINDING_SCOPE_REQUIRED')
        if scope['mode'] == 'collaboration' and any(not scope.get(k) for k in ('workspace_id', 'storyline_id', 'branch_id')):
            raise ValueError('FINDING_SCOPE_REQUIRED')
        self.novels.get(nid)

    def _source(self, nid, scope, cid):
        chapter = scoped_chapters(self.chapters, scope).get(cid)
        if chapter.get('novel_id') != nid or chapter.get('is_archived'): raise FileNotFoundError(cid)
        return {'chapter_id': cid, 'version': chapter['version'], 'digest': content_digest(chapter),
                'scope': deepcopy(scope)}, chapter

    def _owned(self, row, nid, scope):
        return row.get('project_id') == nid and row.get('review_owner') == OWNER and row.get('scope') == scope

    def _raw(self, kind, nid, fid):
        repo = self._repository(kind)
        try:
            return repo.get_by_id('findings', fid) if kind == 'continuity' else repo.get(nid, 'findings', fid)
        except KeyError as exc: raise FileNotFoundError(fid) from exc

    def _public(self, row, nid, scope):
        if not self._owned(row, nid, scope): raise FileNotFoundError(row.get('id'))
        out = deepcopy(row)
        try:
            current, chapter = self._source(nid, scope, row['source']['chapter_id'])
            stale = current != row['source']
            if row.get('provenance') == 'STORED_CONTINUITY_FACTS':
                stale = stale or digest(self._stored_continuity_facts(nid)) != row['context_digest']
            if row.get('provenance') == 'STORED_NARRATIVE_FACTS':
                stale = stale or digest(self._stored_narrative_facts(nid, chapter)) != row['context_digest']
        except (FileNotFoundError, KeyError):
            stale = True
        out['stale_source'] = stale
        out['effective_status'] = 'REVIEW_REQUIRED' if stale else row['status']
        out['suppression_active'] = not stale and row['status'] == 'INTENTIONAL'
        out['allowed_actions'] = ['reopen', 'feedback'] if stale else ['resolve', 'intentional', 'reopen', 'feedback']
        out['navigation'] = {'module': 'write', 'chapter_id': row['source']['chapter_id'],
                             'chapter_version': row['source']['version'], 'source_digest': row['source']['digest'],
                             'scope': deepcopy(scope), 'exact': True}
        # Receipts are bounded audit data, not additional user content.
        out.pop('review_receipts', None)
        return out

    def list(self, nid, scope, kind):
        self._scope(nid, scope)
        repo = self._repository(kind)
        rows = repo.list_by_project('findings', nid) if kind == 'continuity' else repo.list(nid, 'findings')
        return {'items': [self._public(row, nid, scope) for row in rows if self._owned(row, nid, scope)],
                'owner': OWNER, 'model_called': False, 'status': 'CONTRACT_VERIFIED'}

    def get(self, nid, scope, kind, fid):
        self._scope(nid, scope)
        return self._public(self._raw(kind, nid, fid), nid, scope)

    def _stored_continuity_facts(self, nid):
        repo = self._repository("continuity")
        return {key: repo.list_by_project(collection, nid) for key, collection in
                [("events", "timeline"), ("locations", "locations"), ("knowledge", "knowledge"), ("relationships", "relationships")]}

    def _stored_narrative_facts(self, nid, chapter):
        repo = self._repository('narrative')
        facts = {'current_chapter': int(chapter.get('number') or 1)}
        for kind in ('expectations', 'mysteries', 'character_goals'):
            facts[kind] = repo.list(nid, kind)
        facts['narrative_events'] = repo.list(nid, 'events')
        # Preserve the original explicit progress semantics, rather than guessing
        # progress from words in the manuscript or promoting Research into Canon.
        return facts

    def _facts(self, nid, scope, kind, facts):
        if len(json.dumps(facts, default=str).encode()) > 200_000: raise ValueError('FINDING_FACTS_LIMIT')
        if kind == 'continuity':
            from ..lore.continuity import TimelineEvent, CharacterLocationState, CharacterKnowledge, RelationshipState
            from ..lore.continuity_engine import ContinuityRuleContext, registry
            allowed = {'events', 'locations', 'knowledge', 'relationships', 'used_subject_ids', 'canon_facts', 'asserted_facts',
                       'evidence_required_subjects', 'evidence_present_subjects'}
            if set(facts) - allowed: raise ValueError('FINDING_FACTS_INVALID')
            context = {}
            for key, model in [('events', TimelineEvent), ('locations', CharacterLocationState), ('knowledge', CharacterKnowledge), ('relationships', RelationshipState)]:
                values = facts.get(key, [])
                if not isinstance(values, list) or len(values) > 500: raise ValueError('FINDING_FACTS_LIMIT')
                if any(not isinstance(value, dict) for value in values): raise ValueError('FINDING_FACTS_INVALID')
                parsed = [model.model_validate({**value, 'id': value.get('id') or digest([key, i, value])}) for i, value in enumerate(values)]
                if any(item.project_id != nid for item in parsed): raise ValueError('FINDING_FACT_PROJECT_MISMATCH')
                context[key] = parsed
            for key in ('used_subject_ids', 'evidence_required_subjects', 'evidence_present_subjects'):
                value = facts.get(key, [])
                if not isinstance(value, list) or len(value) > 500 or any(not isinstance(x, str) for x in value): raise ValueError('FINDING_FACTS_INVALID')
                context[key] = set(value)
            for key in ('canon_facts', 'asserted_facts'):
                value = facts.get(key, {})
                if not isinstance(value, dict) or len(value) > 500: raise ValueError('FINDING_FACTS_INVALID')
                context[key] = value
            return [f.model_dump(mode='json') for f in registry.evaluate(ContinuityRuleContext(project_id=nid, **context))]
        if kind == 'narrative':
            from ..narrative_detection import NarrativeExpectation, NarrativeRuleContext, registry
            allowed = {'current_chapter', 'expectations', 'thread_last_progress', 'foreshadowing_payoff_chapter', 'mysteries', 'character_goals', 'narrative_events'}
            if set(facts) - allowed: raise ValueError('FINDING_FACTS_INVALID')
            current = facts.get('current_chapter')
            if type(current) is not int or current < 1: raise ValueError('CURRENT_CHAPTER_REQUIRED')
            expectations = facts.get('expectations', [])
            if not isinstance(expectations, list) or len(expectations) > 500: raise ValueError('FINDING_FACTS_LIMIT')
            if any(not isinstance(row, dict) or type(row.get('deadline_chapter')) is not int or row['deadline_chapter'] < 1 for row in expectations): raise ValueError('FINDING_EXPECTATION_INVALID')
            parsed = [NarrativeExpectation(**row) for row in expectations]
            if any(e.project_id != nid for e in parsed): raise ValueError('FINDING_FACT_PROJECT_MISMATCH')
            for key in ('thread_last_progress', 'foreshadowing_payoff_chapter'):
                value = facts.get(key, {})
                if not isinstance(value, dict) or len(value) > 500 or any(type(x) is not int or x < 0 for x in value.values()): raise ValueError('FINDING_FACTS_INVALID')
            for key in ('mysteries', 'character_goals', 'narrative_events'):
                value = facts.get(key, [])
                if not isinstance(value, list) or len(value) > 500 or any(not isinstance(x, dict) or x.get('project_id') != nid for x in value): raise ValueError('FINDING_FACTS_INVALID')
            kwargs = {k: v for k, v in facts.items() if k not in {'current_chapter', 'expectations'}}
            ctx = NarrativeRuleContext(nid, current, parsed, **kwargs, storyline_id=scope.get('storyline_id'), branch_id=scope.get('branch_id'))
            # Fail the operation rather than interpreting failed rules as absent findings.
            return [asdict(f) for f in registry.evaluate(ctx)]
        raise ValueError('FINDING_KIND_INVALID')

    def check(self, nid, scope, actor, kind, body, check=lambda: None):
        self._scope(nid, scope); check()
        source, chapter = self._source(nid, scope, body.chapter_id)
        if source['version'] != body.expected_source_version: raise FindingReviewConflict('FINDING_SOURCE_STALE')
        facts = deepcopy(body.facts)
        provenance = 'AUTHOR_SUPPLIED_FACTS'
        if not facts and kind == 'continuity':
            # Only the original local project owner supplies implicit facts. A
            # branch must provide explicit observations; it never borrows mainline.
            if scope['mode'] != 'local': raise ValueError('BRANCH_FACTS_REQUIRED')
            provenance = 'STORED_CONTINUITY_FACTS'
            facts = self._stored_continuity_facts(nid)
        elif not facts and kind == 'narrative':
            if scope['mode'] != 'local': raise ValueError('BRANCH_FACTS_REQUIRED')
            provenance = 'STORED_NARRATIVE_FACTS'
            facts = self._stored_narrative_facts(nid, chapter)
        findings = self._facts(nid, scope, kind, facts)
        if len(findings) > MAX_FINDINGS: raise ValueError('FINDING_RESULT_LIMIT')
        context_digest = digest(facts)
        source_digest = digest({'source': source, 'context_digest': context_digest})
        repo = self._repository(kind)
        result = []
        for finding in findings:
            check()
            current, _ = self._source(nid, scope, body.chapter_id)
            if current != source: raise FindingReviewConflict('FINDING_SOURCE_STALE')
            identity = digest({'scope': scope, 'kind': kind, 'chapter_id': body.chapter_id, 'original_id': finding['id']})
            fingerprint = digest({k: finding.get(k) for k in ('finding_type', 'rule_id', 'subject_type', 'subject_id', 'description', 'evidence_ids')})
            def observe(old):
                check()
                if old and not self._owned(old, nid, scope): raise FileNotFoundError(identity)
                if old and old['source_digest'] == source_digest and old['finding_fingerprint'] == fingerprint:
                    return old
                row = deepcopy(old) if old else {**finding, 'id': identity, 'review_version': 1,
                       'review_owner': OWNER, 'scope': deepcopy(scope), 'review_history': [], 'review_receipts': {}, 'created_at': now()}
                if old: checkpoint(row, actor, 'SOURCE_RECHECKED', 'New evidence invalidates prior resolution or intentional suppression')
                row.update({k: v for k, v in finding.items() if k not in {'id', 'created_at', 'status'}})
                row.update(status='OPEN', source=deepcopy(source), source_digest=source_digest, context_digest=context_digest,
                           finding_fingerprint=fingerprint, provenance=provenance, updated_at=now(), feedback_reason='')
                check()
                return row
            saved = repo.mutate_finding(nid, identity, observe)
            result.append(self._public(saved, nid, scope))
        check()
        return {'items': result, 'status': 'COMPLETED', 'owner': OWNER, 'model_called': False,
                'source': source, 'source_digest': source_digest, 'provenance': provenance,
                'recovery': 'Repeat the same source check safely; identical findings retain review decisions.'}

    def review(self, nid, scope, actor, kind, fid, body, check=lambda: None):
        self._scope(nid, scope)
        request_digest = digest({**body.model_dump(), 'actor_id': actor})
        def decide(row):
            check()
            if row is None or not self._owned(row, nid, scope): raise FileNotFoundError(fid)
            previous = row.get('review_receipts', {}).get(body.operation_id)
            if previous:
                if previous['digest'] != request_digest: raise FindingReviewConflict('FINDING_OPERATION_REUSED')
                return row
            if row['review_version'] != body.expected_version:
                raise FindingReviewConflict('FINDING_VERSION_CONFLICT', {'id': fid, 'review_version': row['review_version']})
            if row['source_digest'] != body.source_digest or row['finding_fingerprint'] != body.finding_fingerprint:
                raise FindingReviewConflict('FINDING_EVIDENCE_CONFLICT')
            if not body.reason.strip(): raise ValueError('FINDING_REASON_REQUIRED')
            public = self._public(row, nid, scope)
            if public['stale_source'] and body.action in {'resolve', 'intentional'}: raise FindingReviewConflict('FINDING_SOURCE_STALE')
            checkpoint(row, actor, body.action.upper(), body.reason.strip())
            if body.action != 'feedback': row['status'] = {'resolve': 'RESOLVED', 'intentional': 'INTENTIONAL', 'reopen': 'OPEN'}[body.action]
            row['feedback_reason'] = body.reason.strip()
            row.setdefault('review_receipts', {})[body.operation_id] = {'digest': request_digest, 'version': row['review_version']}
            check()
            return row
        saved = self._repository(kind).mutate_finding(nid, fid, decide)
        return self._public(saved, nid, scope)

    def evidence(self, nid, scope, kind, fid):
        row = self.get(nid, scope, kind, fid)
        cid, version = row['source']['chapter_id'], row['source']['version']
        view = scoped_chapters(self.chapters, scope)
        _, current = self._source(nid, scope, cid)
        if current['version'] == version and content_digest(current) == row['source']['digest']:
            selected = current
        else:
            selected = next((r for r in view.history(cid) if r.get('version') == version), None)
            if selected is None: raise FileNotFoundError('FINDING_SOURCE_VERSION_UNAVAILABLE')
            # History uses rich document snapshots. Derive its content through the
            # same owner projection, then verify the captured digest.
            from ..document import document_to_markdown
            selected = {**current, **selected}
            if selected.get('document') is not None: selected['content'] = document_to_markdown(selected['document'])
            if content_digest(selected) != row['source']['digest']: raise FindingReviewConflict('FINDING_EVIDENCE_UNAVAILABLE')
        return {'navigation': row['navigation'], 'stale_source': row['stale_source'],
                'chapter': {'id': cid, 'version': version, 'document': selected.get('document'), 'content': selected.get('content', '')},
                'evidence_ids': row.get('evidence_ids', []), 'provenance': row['provenance']}
