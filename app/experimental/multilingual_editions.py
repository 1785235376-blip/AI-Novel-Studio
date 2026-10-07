"""B05 independent, reviewed language editions over original paragraph authorities.

This is local authoring over independent editions, not a manuscript branch.
Optional explicit translation composes the original author/model runtime. Source
prose is read through its current authority and never copied into this edition
collection. Manual edition operations write no legacy manuscript or asset record.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import html
import json
import re
from typing import Literal

from pydantic import ConfigDict, Field, field_validator, model_validator

from .common import StaleSourceError, change_row, new_id, new_row, now
from .planning import StrictModel, collection, require_row, digest
from .revision_intelligence import RevisionIntelligenceService, text_blocks, utf16_size
from ..revision_constraints import node_digest
from ..services.v1_capability_service import CapabilityVersionConflict

FEATURE = 'multilingual_editions_v2'
MAX_SEGMENTS = 500
MAX_TARGET_TEXT = 250_000
MAX_MEMORY_EDITION_SCAN = 200


def language_code(value):
    # Bounded BCP-47-shaped tags, not an assertion of linguistic support.
    if not re.fullmatch(r'[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8}){0,7}', value):
        raise ValueError('use a bounded language tag such as zh-Hant, en or ar')
    return value


def valid_text(value):
    utf16_size(value)
    if any(ord(c) < 32 and c not in '\n\t\r' for c in value):
        raise ValueError('unsupported control character')
    return value


class SourceIn(StrictModel):
    chapter_id: str = Field(min_length=1, max_length=240)
    chapter_version: int = Field(ge=1)


class EditionIn(StrictModel):
    title: str = Field(min_length=1, max_length=160)
    source_language: str = Field(min_length=2, max_length=64)
    target_language: str = Field(min_length=2, max_length=64)
    direction: Literal['auto', 'ltr', 'rtl'] = 'auto'
    font: Literal['serif', 'sans-serif', 'monospace'] = 'serif'
    style_note: str = Field(default='', max_length=2000)
    chapters: list[SourceIn] = Field(min_length=1, max_length=20)
    _languages = field_validator('source_language', 'target_language')(language_code)
    _text = field_validator('title', 'style_note')(valid_text)


class VersionIn(StrictModel):
    expected_version: int = Field(ge=1)


class SegmentIn(VersionIn):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=False)
    text: str = Field(max_length=20_000)
    note: str = Field(default='', max_length=1000)
    _text = field_validator('text', 'note')(valid_text)


class ReviewIn(VersionIn):
    action: Literal['submit', 'accept', 'reject', 'reopen']
    preview_digest: str | None = Field(default=None, pattern=r'^[a-f0-9]{64}$')


class RuleIn(VersionIn):
    source_term: str = Field(min_length=1, max_length=160)
    source_aliases: list[str] = Field(default_factory=list, max_length=20)
    preferred: str = Field(min_length=1, max_length=160)
    target_aliases: list[str] = Field(default_factory=list, max_length=20)
    forbidden: list[str] = Field(default_factory=list, max_length=20)
    category: Literal['term', 'character', 'title', 'place', 'world'] = 'term'
    strategy: Literal['meaning', 'transliteration', 'preserve'] = 'meaning'
    match: Literal['substring', 'word'] = 'substring'
    note: str = Field(default='', max_length=1000)

    @model_validator(mode='after')
    def terms(self):
        for value in [self.source_term, self.preferred, self.note, *self.source_aliases, *self.target_aliases, *self.forbidden]:
            valid_text(value)
        for values in [self.source_aliases, self.target_aliases, self.forbidden]:
            if any(not s.strip() or len(s) > 160 for s in values) or len(set(values)) != len(values):
                raise ValueError('term variants must be unique, nonempty and bounded')
        if set([self.preferred, *self.target_aliases]) & set(self.forbidden):
            raise ValueError('approved and forbidden target variants overlap')
        if self.strategy == 'preserve' and (self.preferred != self.source_term or self.source_aliases or self.target_aliases):
            raise ValueError('preserve strategy requires an exact source term without alternate spellings')
        return self


class RuleReviewIn(VersionIn):
    action: Literal['approve', 'revoke', 'lock', 'unlock']


class MemoryAdoptIn(VersionIn):
    source_edition_id: str = Field(min_length=1, max_length=240)
    source_segment_id: str = Field(min_length=1, max_length=240)
    preview_digest: str = Field(pattern=r'^[a-f0-9]{64}$')


class RestoreSegmentIn(VersionIn):
    restore_version: int = Field(ge=1)
    preview_digest: str = Field(pattern=r'^[a-f0-9]{64}$')


class RefreshIn(VersionIn):
    preview_digest: str | None = Field(default=None, pattern=r'^[a-f0-9]{64}$')


class ExportIn(VersionIn):
    format: Literal['txt', 'html', 'json'] = 'txt'
    preview_digest: str | None = Field(default=None, pattern=r'^[a-f0-9]{64}$')


def contains(text, term, mode):
    if mode == 'substring': return term in text
    # Unicode letters and digits, no regex supplied by the user; literal exact
    # case-sensitive matching, without changing saved normalization or offsets.
    start = 0
    while (index := text.find(term, start)) >= 0:
        end = index + len(term)
        if (not index or not (text[index - 1].isalnum() or text[index - 1] == '_')) and (end == len(text) or not (text[end].isalnum() or text[end] == '_')):
            return True
        start = index + 1
    return False


def locked_variant_present(text, preferred, alias, mode):
    """A shorter alias inside an exact preferred occurrence is not name drift.

    Retain the same literal, case-sensitive, Unicode-boundary match policy as
    contains. Ordered spans avoid quadratic rescanning for repeated short terms.
    """
    def spans(term):
        if not term: return
        start = 0
        while (index := text.find(term, start)) >= 0:
            end = index + len(term)
            if mode == 'substring' or ((not index or not (text[index - 1].isalnum() or text[index - 1] == '_')) and (end == len(text) or not (text[end].isalnum() or text[end] == '_'))):
                yield index, end
            start = index + 1
    preferred_spans = list(spans(preferred)); current = -1
    for start, end in spans(alias):
        while current + 1 < len(preferred_spans) and preferred_spans[current + 1][0] <= start:
            current += 1
        if current < 0 or preferred_spans[current][1] < end:
            return True
    return False


def terminology_issues(source, target, rules):
    approved = [r for r in rules if r['status'] == 'APPROVED']
    relevant = [r for r in approved if any(contains(source, t, r['match']) for t in [r['source_term'], *r['source_aliases']])]
    issues = []
    for rule in relevant:
        key = {'rule_id': rule['id'], 'rule_version': rule['version'], 'term': rule['source_term']}
        allowed = [rule['preferred']] if rule.get('locked', False) else [rule['preferred'], *rule['target_aliases']]
        if not any(contains(target, t, rule['match']) for t in allowed):
            issues.append({**key, 'code': 'TERM_REQUIRED', 'expected': rule['preferred']})
        if rule.get('locked', False):
            for alias in rule['target_aliases']:
                if locked_variant_present(target, rule['preferred'], alias, rule['match']):
                    issues.append({**key, 'code': 'LOCKED_TERM_VARIANT', 'found': alias, 'expected': rule['preferred']})
        for forbidden in rule['forbidden']:
            if contains(target, forbidden, rule['match']): issues.append({**key, 'code': 'TERM_FORBIDDEN', 'found': forbidden})
    for index, first in enumerate(relevant):
        for second in relevant[index + 1:]:
            if set([first['source_term'], *first['source_aliases']]) & set([second['source_term'], *second['source_aliases']]) and not set([first['preferred'], *first['target_aliases']]) & set([second['preferred'], *second['target_aliases']]):
                issues.append({'code': 'RULE_CONFLICT', 'rule_id': first['id'], 'other_rule_id': second['id']})
    return issues


class MultilingualEditionsService(RevisionIntelligenceService):
    COLLECTION = 'language_editions'

    def capture(self, nid, scope, cid, expected=None):
        chapter, source = super().capture(nid, scope, cid, expected)
        if chapter.get('hidden') or chapter.get('secret') or str(chapter.get('visibility', '')).upper() in {'PRIVATE', 'SECRET', 'DENIED'}:
            raise FileNotFoundError(cid)
        return chapter, source

    def catalog(self, nid, scope):
        self.novels.get(nid)
        rows = []
        for chapter in self.chapters_for(scope).list(nid):
            if chapter.get('branch_id') != scope.get('branch_id'): continue
            try: current, _ = self.capture(nid, scope, chapter['id'])
            except (FileNotFoundError, ValueError): continue
            rows.append({'id': current['id'], 'title': current.get('title', current['id']), 'version': current['version']})
        return {'chapters': rows, 'branch_sources_available': bool(rows) or scope.get('branch_id') is None,
                'translation': {'available': bool(getattr(self, 'translation_coordinator', None)),
                                'reason': 'EXACT_SEGMENT_MODEL_PREFLIGHT_REQUIRED' if getattr(self, 'translation_coordinator', None) else 'TRANSLATION_ORIGINAL_EXECUTOR_UNAVAILABLE',
                                'execution_authorized': False, 'model_called': False},
                'limits': {'chapters': 20, 'segments': MAX_SEGMENTS, 'target_characters': MAX_TARGET_TEXT},
                'language_validation': 'BCP47_SHAPED_TAGS_NOT_LANGUAGE_QUALITY', 'font_policy': 'SYSTEM_GENERIC_FALLBACK_GLYPHS_NOT_GUARANTEED'}

    def _owned(self, nid, scope, actor, eid):
        row = self.get(nid, scope, self.COLLECTION, eid)
        if row['created_by'] != actor: raise FileNotFoundError(eid)
        return row

    @staticmethod
    def _version(row, expected):
        # Never put target prose, rules or history in a stale-CAS error body.
        if row['version'] != expected:
            raise CapabilityVersionConflict({'id': row['id'], 'version': row['version'], 'status': row['status']})

    def _capture_all(self, nid, scope, chapters):
        sources, segments = {}, []
        if len({c.chapter_id for c in chapters}) != len(chapters): raise ValueError('duplicate source chapter')
        for item in chapters:
            chapter, source = self.capture(nid, scope, item.chapter_id, item.chapter_version)
            sources[item.chapter_id] = source
            for block in text_blocks(chapter['document']):
                if not block['supported']: raise ValueError('unsupported source object; use plain text paragraphs or retain it outside this edition')
                if not block['text'].strip(): continue
                segments.append({'id': new_id(), 'chapter_id': item.chapter_id, 'source_version': item.chapter_version,
                    'path': block['path'], 'node_digest': node_digest(block['node']), 'from_pos': block['start'], 'to_pos': block['end'],
                    'target_text': '', 'note': '', 'status': 'DRAFT', 'accepted_term_revision': None})
        if not segments or len(segments) > MAX_SEGMENTS: raise ValueError('edition requires 1 to 500 nonempty source paragraphs')
        return sources, segments

    def _current(self, nid, scope, row):
        source_text = {}
        for cid, expected in row['sources'].items():
            chapter, current = self.capture(nid, scope, cid, expected['version'])
            if current != expected: raise StaleSourceError('source version, document or privacy changed; explicitly refresh alignment')
            by_path = {tuple(b['path']): b for b in text_blocks(chapter['document'])}
            for segment in row['segments']:
                if segment['chapter_id'] != cid: continue
                block = by_path.get(tuple(segment['path']))
                if not block or node_digest(block['node']) != segment['node_digest'] or not block['supported']:
                    raise StaleSourceError('source paragraph anchor changed')
                source_text[segment['id']] = block['text']
        return source_text

    def _view(self, nid, scope, row):
        try: texts = self._current(nid, scope, row)
        except (FileNotFoundError, ValueError):
            return {k: deepcopy(row[k]) for k in ['id', 'version', 'status', 'target_language', 'direction', 'created_at']} | {
                'stale': True, 'content_withheld': True, 'segment_count': len(row['segments']),
                'recovery': 'REFRESH_EXACT_UNCHANGED_ANCHORS_OR_RESTORE_SOURCE'}
        result = {k: deepcopy(v) for k, v in row.items() if k != 'history'}
        for segment in result['segments']:
            segment['source_text'] = texts[segment['id']]
            segment['issues'] = terminology_issues(segment['source_text'], segment['target_text'], row['rules'])
        result.update(stale=False, content_withheld=False, checks=self._checks(row, texts), model_called=any(s.get('translation_provenance') for s in row['segments']))
        return result

    def editions(self, nid, scope, actor):
        rows = [r for r in self.list(nid, scope, self.COLLECTION) if r['created_by'] == actor]
        return {'items': [self._view(nid, scope, r) for r in rows[-50:]], 'truncated': len(rows) > 50}

    def edition(self, nid, scope, actor, eid):
        return self._view(nid, scope, self._owned(nid, scope, actor, eid))

    def create_edition(self, nid, scope, actor, value, *, reauthorize=lambda: None):
        data = EditionIn.model_validate(value)
        sources, segments = self._capture_all(nid, scope, data.chapters)
        direction = data.direction
        if direction == 'auto':
            parts = data.target_language.lower().split('-')
            direction = 'rtl' if parts[0] in {'ar', 'he', 'fa', 'ur', 'ps', 'dv', 'yi'} or 'arab' in parts or 'hebr' in parts else 'ltr'
        row = new_row(nid, scope, actor, {**data.model_dump(exclude={'chapters'}), 'direction': direction,
            'sources': sources, 'segments': segments, 'archived_segments': [], 'rules': [], 'term_revision': 0,
            'storage_contract': 'INDEPENDENT_LANGUAGE_EDITION_NOT_MANUSCRIPT_BRANCH', 'privacy_level': 'LOCAL_ONLY', 'model_called': False})
        reauthorize()
        with self.store.transaction(nid, scope) as doc:
            self._current(nid, scope, row); reauthorize()
            collection(doc, self.COLLECTION)[row['id']] = row
        return self._view(nid, scope, row)

    def _mutate(self, nid, scope, actor, eid, expected, callback, reauthorize, *, stale_ok=False):
        reauthorize()
        with self.store.transaction(nid, scope) as doc:
            row = require_row(doc, self.COLLECTION, eid)
            if row['created_by'] != actor: raise FileNotFoundError(eid)
            self._version(row, expected)
            texts = {} if stale_ok else self._current(nid, scope, row)
            reauthorize()
            change_row(row, actor, expected, lambda current: callback(current, texts))
            # The last source/authorization check stays inside the atomic store
            # transaction so a revoked action cannot leave a committed edition.
            self._current(nid, scope, row); reauthorize()
            result = deepcopy(row)
        return self._view(nid, scope, result)

    @staticmethod
    def _segment(row, sid):
        found = next((s for s in row['segments'] if s['id'] == sid), None)
        if found is None: raise FileNotFoundError(sid)
        return found

    def save_segment(self, nid, scope, actor, eid, sid, value, *, reauthorize=lambda: None):
        data = SegmentIn.model_validate(value)
        def update(row, texts):
            segment = self._segment(row, sid)
            if sum(len(s['target_text']) for s in row['segments'] if s['id'] != sid) + len(data.text) > MAX_TARGET_TEXT:
                raise ValueError('edition target character limit exceeded')
            segment.update(target_text=data.text, note=data.note, status='DRAFT', accepted_term_revision=None)
            segment.pop('reviewed_by', None); segment.pop('reviewed_at', None)
            segment.pop('memory_provenance', None); segment.pop('translation_provenance', None)
            row['status'] = 'DRAFT'
        return self._mutate(nid, scope, actor, eid, data.expected_version, update, reauthorize)

    def _receipt(self, row, sid, texts):
        segment = self._segment(row, sid)
        issues = terminology_issues(texts[sid], segment['target_text'], row['rules'])
        if not segment['target_text'].strip(): issues.insert(0, {'code': 'TRANSLATION_MISSING'})
        payload = {'edition_id': row['id'], 'edition_version': row['version'], 'segment_id': sid,
                   'segment': segment, 'sources': row['sources'], 'term_revision': row['term_revision'], 'rules': row['rules']}
        return {'preview_digest': digest(payload), 'issues': issues, 'can_accept': not issues and segment['status'] == 'REVIEW',
                'model_called': False, 'quality': 'EXACT_TERMINOLOGY_CHECK_NOT_TRANSLATION_QUALITY'}

    def preview_segment(self, nid, scope, actor, eid, sid, value, *, reauthorize=lambda: None):
        data = VersionIn.model_validate(value); row = self._owned(nid, scope, actor, eid)
        self._version(row, data.expected_version); result = self._receipt(row, sid, self._current(nid, scope, row)); reauthorize()
        return result

    def review_segment(self, nid, scope, actor, eid, sid, value, *, reauthorize=lambda: None):
        data = ReviewIn.model_validate(value)
        def update(row, texts):
            segment = self._segment(row, sid)
            if data.action == 'submit':
                if segment['status'] not in {'DRAFT', 'REJECTED'} or not segment['target_text'].strip(): raise ValueError('submit a nonempty draft first')
                segment['status'] = 'REVIEW'
            elif data.action == 'accept':
                receipt = self._receipt(row, sid, texts)
                if not receipt['can_accept']: raise ValueError('reviewed nonempty translation with no terminology conflict required')
                if data.preview_digest != receipt['preview_digest']: raise StaleSourceError('translation review preview changed')
                segment.update(status='ACCEPTED', accepted_term_revision=row['term_revision'], reviewed_by=actor, reviewed_at=now())
            elif data.action == 'reject':
                if segment['status'] != 'REVIEW': raise ValueError('only a review draft can be rejected')
                segment.update(status='REJECTED', accepted_term_revision=None)
            else:
                if segment['status'] not in {'ACCEPTED', 'REJECTED'}: raise ValueError('only accepted/rejected text can be reopened')
                segment.update(status='DRAFT', accepted_term_revision=None)
            row['status'] = 'ACCEPTED' if all(s['status'] == 'ACCEPTED' for s in row['segments']) else 'DRAFT'
        return self._mutate(nid, scope, actor, eid, data.expected_version, update, reauthorize)

    def add_rule(self, nid, scope, actor, eid, value, *, reauthorize=lambda: None):
        data = RuleIn.model_validate(value)
        def update(row, texts):
            if len(row['rules']) >= 100: raise ValueError('edition supports at most 100 terminology rules')
            row['rules'].append({'id': new_id(), 'version': 1, 'status': 'DRAFT', 'created_by': actor,
                                 **data.model_dump(exclude={'expected_version'})})
        return self._mutate(nid, scope, actor, eid, data.expected_version, update, reauthorize)

    def review_rule(self, nid, scope, actor, eid, rid, value, *, reauthorize=lambda: None):
        data = RuleReviewIn.model_validate(value)
        def update(row, texts):
            rule = next((r for r in row['rules'] if r['id'] == rid), None)
            if rule is None: raise FileNotFoundError(rid)
            if (data.action == 'approve' and rule['status'] != 'DRAFT') or (data.action == 'revoke' and rule['status'] != 'APPROVED'):
                raise ValueError('rule transition requires a current draft or approval')
            if data.action in {'lock', 'unlock'}:
                if rule['status'] != 'APPROVED' or bool(rule.get('locked', False)) == (data.action == 'lock'):
                    raise ValueError('lock transition requires a current approved rule and changed lock state')
                rule['locked'] = data.action == 'lock'
            else:
                if rule.get('locked', False): raise ValueError('unlock this term explicitly before revoking it')
                rule['status'] = 'APPROVED' if data.action == 'approve' else 'REVOKED'
            rule.update(version=rule['version'] + 1, reviewed_by=actor, reviewed_at=now())
            row['term_revision'] += 1
            # A rule decision never silently blesses old translations.
            for segment in row['segments']:
                if segment['status'] == 'ACCEPTED': segment.update(status='REVIEW', accepted_term_revision=None)
            row['status'] = 'DRAFT'
        return self._mutate(nid, scope, actor, eid, data.expected_version, update, reauthorize)

    def _memory_candidates(self, nid, scope, actor, row, sid, state=None):
        """Exact-match projection of accepted owner records, never another text store."""
        texts = self._current(nid, scope, row); self._segment(row, sid)
        candidates = []
        rows = collection(state, self.COLLECTION).values() if state is not None else self.list(nid, scope, self.COLLECTION)
        eligible = [r for r in rows if r['created_by'] == actor and r['source_language'] == row['source_language'] and r['target_language'] == row['target_language']]
        for original in eligible[-MAX_MEMORY_EDITION_SCAN:]:
            try: source_texts = self._current(nid, scope, original)
            except (FileNotFoundError, ValueError): continue
            for segment in original['segments']:
                if original['id'] == row['id'] and segment['id'] == sid: continue
                if segment['status'] != 'ACCEPTED' or segment.get('accepted_term_revision') != original['term_revision']: continue
                if source_texts[segment['id']] != texts[sid] or not segment['target_text'].strip(): continue
                issues = terminology_issues(texts[sid], segment['target_text'], row['rules'])
                receipt = digest([row['id'], row['version'], sid, row['sources'], row['rules'], row['style_note'],
                                  original['id'], original['version'], segment, original['sources'], original['rules']])
                candidates.append({'source_edition_id': original['id'], 'source_edition_version': original['version'],
                    'source_segment_id': segment['id'], 'source_chapter_id': segment['chapter_id'],
                    'source_version': segment['source_version'], 'source_digest': digest(texts[sid]),
                    'target_text': segment['target_text'], 'target_digest': digest(segment['target_text']),
                    'style_matches': original['style_note'] == row['style_note'], 'issues': issues,
                    'can_adopt': not issues, 'preview_digest': receipt, 'match': 'EXACT_SOURCE_TEXT'})
        return candidates

    def translation_memory(self, nid, scope, actor, eid, sid, value, *, reauthorize=lambda: None):
        data = VersionIn.model_validate(value); row = self._owned(nid, scope, actor, eid)
        self._version(row, data.expected_version); reauthorize()
        result = self._memory_candidates(nid, scope, actor, row, sid)
        eligible_count = sum(r['created_by'] == actor and r['source_language'] == row['source_language'] and r['target_language'] == row['target_language'] for r in self.list(nid, scope, self.COLLECTION))
        reauthorize()
        return {'items': result[:100], 'truncated': len(result) > 100 or eligible_count > MAX_MEMORY_EDITION_SCAN, 'edition_scan_limit': MAX_MEMORY_EDITION_SCAN, 'storage': 'ACCEPTED_EDITION_SEGMENTS',
                'quality': 'EXACT_MATCH_NOT_TRANSLATION_QUALITY', 'automatic_reuse': False, 'model_called': False}

    def adopt_memory(self, nid, scope, actor, eid, sid, value, *, reauthorize=lambda: None):
        data = MemoryAdoptIn.model_validate(value); reauthorize()
        with self.store.transaction(nid, scope) as state:
            row = require_row(state, self.COLLECTION, eid)
            if row['created_by'] != actor: raise FileNotFoundError(eid)
            self._version(row, data.expected_version)
            candidates = self._memory_candidates(nid, scope, actor, row, sid, state)
            candidate = next((c for c in candidates if c['source_edition_id'] == data.source_edition_id and c['source_segment_id'] == data.source_segment_id), None)
            if not candidate or candidate['preview_digest'] != data.preview_digest: raise StaleSourceError('translation memory source or destination changed')
            if not candidate['can_adopt']: raise ValueError('resolve locked terminology before using memory')
            if sum(len(s['target_text']) for s in row['segments'] if s['id'] != sid) + len(candidate['target_text']) > MAX_TARGET_TEXT:
                raise ValueError('edition target character limit exceeded')
            def update(current):
                segment = self._segment(current, sid)
                segment.update(target_text=candidate['target_text'], status='DRAFT', accepted_term_revision=None,
                    memory_provenance={k: deepcopy(v) for k, v in candidate.items() if k not in {'target_text', 'issues', 'can_adopt'}})
                for key in ('reviewed_by', 'reviewed_at', 'translation_provenance'): segment.pop(key, None)
                current['status'] = 'DRAFT'
            change_row(row, actor, data.expected_version, update)
            self._current(nid, scope, row)
            self._current(nid, scope, require_row(state, self.COLLECTION, data.source_edition_id)); reauthorize()
            result = deepcopy(row)
        return self._view(nid, scope, result)

    def segment_history(self, nid, scope, actor, eid, sid, value, *, reauthorize=lambda: None):
        data = VersionIn.model_validate(value); row = self._owned(nid, scope, actor, eid)
        self._version(row, data.expected_version); self._current(nid, scope, row)
        segment = self._segment(row, sid); items = []
        for old in row.get('history', []):
            prior = next((s for s in old['segments'] if s['id'] == sid), None)
            if not prior or any(prior[k] != segment[k] for k in ('chapter_id', 'source_version', 'path', 'node_digest')): continue
            try: self._current(nid, scope, old)
            except (FileNotFoundError, ValueError): continue
            items.append({'version': old['version'], 'target_text': prior['target_text'], 'note': prior['note'], 'status': prior['status'],
                'preview_digest': digest([eid, row['version'], sid, old['version'], prior, row['sources']])})
        reauthorize(); return {'items': items[-100:], 'truncated': len(items) > 100, 'restore_as': 'NEW_DRAFT'}

    def restore_segment(self, nid, scope, actor, eid, sid, value, *, reauthorize=lambda: None):
        data = RestoreSegmentIn.model_validate(value)
        def update(row, texts):
            segment = self._segment(row, sid)
            old = next((h for h in row.get('history', []) if h['version'] == data.restore_version), None)
            if old is None: raise FileNotFoundError('translation revision')
            self._current(nid, scope, old); prior = self._segment(old, sid)
            if any(prior[k] != segment[k] for k in ('chapter_id', 'source_version', 'path', 'node_digest')): raise StaleSourceError('translation historical anchor changed')
            if data.preview_digest != digest([eid, row['version'], sid, old['version'], prior, row['sources']]): raise StaleSourceError('translation restore preview changed')
            if sum(len(s['target_text']) for s in row['segments'] if s['id'] != sid) + len(prior['target_text']) > MAX_TARGET_TEXT: raise ValueError('edition target character limit exceeded')
            segment.update(target_text=prior['target_text'], note=prior['note'], status='DRAFT', accepted_term_revision=None, restored_from_version=old['version'])
            for key in ('reviewed_by', 'reviewed_at', 'translation_provenance', 'memory_provenance'): segment.pop(key, None)
            row['status'] = 'DRAFT'
        return self._mutate(nid, scope, actor, eid, data.expected_version, update, reauthorize)

    def _refresh_plan(self, nid, scope, row):
        chapters = [SourceIn(chapter_id=cid, chapter_version=self.capture(nid, scope, cid)[0]['version']) for cid in row['sources']]
        sources, fresh = self._capture_all(nid, scope, chapters)
        previous = {(s['chapter_id'], tuple(s['path']), s['node_digest']): s for s in row['segments']}
        retained = 0
        for segment in fresh:
            old = previous.get((segment['chapter_id'], tuple(segment['path']), segment['node_digest']))
            if old:
                retained += 1
                segment.update(id=old['id'], target_text=old['target_text'], note=old['note'], status='DRAFT')
        # IDs for new paragraphs are not part of the deterministic preview.
        stable = [{k: v for k, v in s.items() if k != 'id'} for s in fresh]
        receipt = digest({'edition_id': row['id'], 'version': row['version'], 'sources': sources, 'segments': stable})
        return sources, fresh, {'preview_digest': receipt, 'retained_exact': retained, 'new_or_changed': len(fresh) - retained,
                               'archived_old': len(row['segments']) - retained, 'requires_review': len(fresh)}

    def refresh_preview(self, nid, scope, actor, eid, value, *, reauthorize=lambda: None):
        data = VersionIn.model_validate(value); row = self._owned(nid, scope, actor, eid); self._version(row, data.expected_version)
        _, _, result = self._refresh_plan(nid, scope, row); reauthorize(); return result

    def refresh_sources(self, nid, scope, actor, eid, value, *, reauthorize=lambda: None):
        data = RefreshIn.model_validate(value)
        def update(row, texts):
            sources, fresh, receipt = self._refresh_plan(nid, scope, row)
            if data.preview_digest != receipt['preview_digest']: raise StaleSourceError('alignment preview changed')
            retained = {s['id'] for s in fresh}
            archived = deepcopy(row.get('archived_segments', []))
            for old in row['segments']:
                if old['id'] not in retained and old['target_text']:
                    archived.append({k: deepcopy(old[k]) for k in ['chapter_id', 'source_version', 'path', 'target_text', 'note']})
            if len(archived) > 2000: raise ValueError('archived translation limit reached; retain this edition and create a new edition')
            row.update(sources=sources, segments=fresh, archived_segments=archived, status='DRAFT', refresh_receipt=receipt)
        return self._mutate(nid, scope, actor, eid, data.expected_version, update, reauthorize, stale_ok=True)

    @staticmethod
    def _checks(row, texts):
        missing = [s['id'] for s in row['segments'] if not s['target_text'].strip()]
        pending = [s['id'] for s in row['segments'] if s['status'] != 'ACCEPTED' or s['accepted_term_revision'] != row['term_revision']]
        conflicts = [{'segment_id': s['id'], **issue} for s in row['segments'] for issue in terminology_issues(texts[s['id']], s['target_text'], row['rules'])]
        return {'missing': missing, 'pending': pending, 'terminology': conflicts, 'aligned': len(texts) == len(row['segments']),
                'can_export': not (missing or pending or conflicts) and len(texts) == len(row['segments'])}

    def _export_receipt(self, row, texts, format):
        checks = self._checks(row, texts)
        return {'checks': checks, 'can_export': checks['can_export'], 'format': format, 'encoding': 'UTF-8',
                'preview_digest': digest({'id': row['id'], 'version': row['version'], 'sources': row['sources'],
                                          'segments': row['segments'], 'rules': row['rules'], 'format': format})}

    def export_preview(self, nid, scope, actor, eid, value, *, reauthorize=lambda: None):
        data = ExportIn.model_validate(value); row = self._owned(nid, scope, actor, eid); self._version(row, data.expected_version)
        result = self._export_receipt(row, self._current(nid, scope, row), data.format); reauthorize(); return result

    def export(self, nid, scope, actor, eid, value, *, reauthorize=lambda: None):
        data = ExportIn.model_validate(value); row = self._owned(nid, scope, actor, eid); self._version(row, data.expected_version)
        texts = self._current(nid, scope, row); receipt = self._export_receipt(row, texts, data.format)
        if data.preview_digest != receipt['preview_digest']: raise StaleSourceError('export preview changed')
        if not receipt['can_export']: raise ValueError('resolve missing, unreviewed or conflicting paragraphs before export')
        targets = [s['target_text'] for s in row['segments']]
        if data.format == 'txt': content, mime = '\n\n'.join(targets) + '\n', 'text/plain'
        elif data.format == 'html':
            content = '<!doctype html>\n<html lang="' + html.escape(row['target_language'], quote=True) + '" dir="' + row['direction'] + '"><head><meta charset="utf-8"><title>' + html.escape(row['title']) + '</title><style>body{font-family:' + row['font'] + ';}p{white-space:pre-wrap;unicode-bidi:plaintext;}</style></head><body>' + ''.join('<p>' + html.escape(t) + '</p>' for t in targets) + '</body></html>\n'
            mime = 'text/html'
        else:
            content = json.dumps({'schema': 'language-edition-export-v1', 'title': row['title'], 'language': row['target_language'], 'direction': row['direction'], 'font': row['font'], 'encoding': 'UTF-8', 'segments': [{'chapter_id': s['chapter_id'], 'source_version': s['source_version'], 'path': s['path'], 'text': s['target_text']} for s in row['segments']], 'terminology_revision': row['term_revision']}, ensure_ascii=False, indent=2) + '\n'
            mime = 'application/json'
        latest = self._owned(nid, scope, actor, eid)
        self._version(latest, data.expected_version)
        self._current(nid, scope, latest); reauthorize()
        return {'filename': f"edition-{row['id']}-{row['target_language']}.{data.format}", 'mime': mime + '; charset=utf-8',
                'encoding': 'UTF-8', 'content': content, 'sha256': hashlib.sha256(content.encode('utf-8')).hexdigest(),
                'model_called': False, 'published': False}
