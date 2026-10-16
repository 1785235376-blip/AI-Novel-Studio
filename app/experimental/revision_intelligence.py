"""A11/U05: exact original-document selections, reviewed partial patch adoption.

Metadata is a review journal, never a second chapter/version authority. A durable
ACCEPTING claim precedes original CAS writes. Interrupted cross-store acceptance
is uncertain and cannot replay; the author inspects original chapter history.
"""
from __future__ import annotations

from copy import deepcopy
from difflib import SequenceMatcher
import hashlib
import unicodedata
from typing import Literal

from pydantic import ConfigDict, Field, model_validator

from .common import DomainService, StaleSourceError, new_row, check_version, change_row
from .planning import StrictModel, collection, require_row, digest
from ..revision_constraints import LOCK_ATTRIBUTE, RevisionConstraintError, active_lock, at_path, node_digest, assert_ai_locks, marker_id
from ..source_privacy import source_privacy_status

FEATURE = 'revision_intelligence_v2'
SELECTION_FEATURE = 'selection_assistant_v2'
MAX_TEXT = 100_000


class SelectionIn(StrictModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=False)
    chapter_id: str = Field(min_length=1, max_length=240)
    chapter_version: int = Field(ge=1)
    from_pos: int = Field(ge=0)
    to_pos: int = Field(ge=1)
    text: str = Field(min_length=1, max_length=MAX_TEXT)


class ReplacementIn(StrictModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=False)
    anchor_id: str = Field(pattern=r'^[a-f0-9]{64}$')
    text: str = Field(max_length=MAX_TEXT)


class ExplanationIn(StrictModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=False)
    anchor_id: str = Field(pattern=r'^[a-f0-9]{64}$')
    kind: Literal['motivation', 'relationship', 'world_fact', 'foreshadowing', 'other', 'fact_added', 'fact_removed', 'character_state', 'canon', 'emotional_tone', 'plot_intent']
    explanation: str = Field(min_length=1, max_length=2000)
    before_quote: str = Field(min_length=1, max_length=2000)
    after_quote: str = Field(min_length=1, max_length=2000)
    source: Literal['AUTHOR_NOTE', 'IMPORTED_MODEL_ASSESSMENT'] = 'AUTHOR_NOTE'


class ProposalIn(StrictModel):
    selection: SelectionIn
    selection_digest: str = Field(pattern=r'^[a-f0-9]{64}$')
    replacements: list[ReplacementIn] = Field(min_length=1, max_length=50)
    explanations: list[ExplanationIn] = Field(default_factory=list, max_length=50)
    goal: str = Field(default='', max_length=1000)
    job_id: str | None = Field(default=None, min_length=1, max_length=160)


class ReviewIn(StrictModel):
    expected_version: int = Field(ge=1)
    accept_ids: list[str] = Field(default_factory=list, max_length=50)
    reject_ids: list[str] = Field(default_factory=list, max_length=50)
    preview_digest: str | None = Field(default=None, pattern=r'^[a-f0-9]{64}$')


class RebaseIn(StrictModel):
    expected_version: int = Field(ge=1)
    chapter_version: int = Field(ge=1)


class LockIn(StrictModel):
    selection: SelectionIn
    selection_digest: str = Field(pattern=r'^[a-f0-9]{64}$')
    action: Literal['lock', 'unlock']


class UnlockBlockIn(StrictModel):
    chapter_id: str = Field(min_length=1, max_length=240)
    chapter_version: int = Field(ge=1)
    path: list[int] = Field(min_length=1, max_length=64)
    document_digest: str = Field(pattern=r'^[a-f0-9]{64}$')


class MilestoneIn(StrictModel):
    chapter_id: str = Field(min_length=1, max_length=240)
    chapter_version: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=160)
    goal: str = Field(default='', max_length=1000)


class VersionCompareIn(StrictModel):
    chapter_id: str = Field(min_length=1, max_length=240)
    current_version: int = Field(ge=1)
    before_version: int = Field(ge=1)
    after_version: int = Field(ge=1)

    @model_validator(mode='after')
    def distinct(self):
        if self.before_version == self.after_version: raise ValueError('choose two distinct original versions')
        return self


class SemanticChangeIn(StrictModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=False)
    kind: Literal['FACT_ADDED', 'FACT_REMOVED', 'CHARACTER_STATE_CHANGED', 'RELATIONSHIP_CHANGED',
                  'CANON_CHANGED', 'EMOTIONAL_TONE_CHANGED', 'PLOT_INTENT_CHANGED']
    explanation: str = Field(min_length=1, max_length=2000)
    before_quote: str = Field(default='', max_length=4000)
    before_start: int = Field(default=0, ge=0)
    after_quote: str = Field(default='', max_length=4000)
    after_start: int = Field(default=0, ge=0)
    source: Literal['AUTHOR_NOTE', 'IMPORTED_MODEL_ASSESSMENT'] = 'AUTHOR_NOTE'
    model_identity: str | None = Field(default=None, min_length=1, max_length=160)

    @model_validator(mode='after')
    def evidence_shape(self):
        if not self.explanation.strip(): raise ValueError('semantic interpretation needs an explanation')
        if self.kind == 'FACT_ADDED':
            if self.before_quote or not self.after_quote: raise ValueError('added fact requires after evidence only')
        elif self.kind == 'FACT_REMOVED':
            if not self.before_quote or self.after_quote: raise ValueError('removed fact requires before evidence only')
        elif not self.before_quote or not self.after_quote:
            raise ValueError('changed state requires both original-version quotes')
        if self.source == 'IMPORTED_MODEL_ASSESSMENT' and not self.model_identity:
            raise ValueError('model-derived assessment requires a declared model identity')
        if self.source == 'AUTHOR_NOTE' and self.model_identity:
            raise ValueError('author notes must not claim model provenance')
        return self


class VersionComparisonSaveIn(StrictModel):
    comparison: VersionCompareIn
    preview_digest: str = Field(pattern=r'^[a-f0-9]{64}$')
    title: str = Field(min_length=1, max_length=160)
    changes: list[SemanticChangeIn] = Field(default_factory=list, max_length=50)


class VersionComparisonEditIn(StrictModel):
    expected_version: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=160)
    changes: list[SemanticChangeIn] = Field(default_factory=list, max_length=50)


class VersionComparisonReviewIn(StrictModel):
    expected_version: int = Field(ge=1)
    action: Literal['acknowledge', 'archive', 'reopen']


def utf16_size(text):
    try: return len(text.encode('utf-16-le')) // 2
    except UnicodeEncodeError: raise ValueError('invalid Unicode surrogate') from None


def codepoint_offset(text, offset):
    size = 0
    for index, character in enumerate(text):
        if size == offset: return index
        size += utf16_size(character)
        if size > offset: raise ValueError('selection splits an emoji/surrogate pair')
    if size == offset: return len(text)
    raise ValueError('selection offset outside saved text')


def check_boundary(text, index):
    """Conservative Unicode cluster fence; rejects uncertain cluster boundaries.

    No normalization is performed: decomposed text remains decomposed. Surrogates
    are checked separately. Unsupported cluster boundaries are rejected, not
    rounded to another user's text.
    """
    if index == 0 or index == len(text): return
    before, after = text[index - 1], text[index]
    value = ord(after)
    if (unicodedata.category(after).startswith('M') or unicodedata.combining(before)
        or before == '\u200d' or after == '\u200d' or (before == '\r' and after == '\n')
        or 0x1F3FB <= value <= 0x1F3FF or 0xFE00 <= value <= 0xFE0F
        or 0xE0020 <= value <= 0xE007F or 0xE0100 <= value <= 0xE01EF
        or 0x1100 <= ord(before) <= 0x11FF or 0x1100 <= value <= 0x11FF):
        raise ValueError('selection splits or may split a Unicode cluster')
    if 0x1F1E6 <= value <= 0x1F1FF:
        count = 0
        for c in reversed(text[:index]):
            if not 0x1F1E6 <= ord(c) <= 0x1F1FF: break
            count += 1
        if count % 2: raise ValueError('selection splits a flag emoji')


def text_blocks(document):
    """PM positions are UTF-16 node sizes, NOT offsets into Markdown or text."""
    if not isinstance(document, dict) or document.get('type') != 'doc':
        raise ValueError('saved rich document unavailable')
    result, count = [], 0
    def size(node):
        kind = node.get('type')
        if kind == 'text': return utf16_size(node.get('text', ''))
        if not node.get('content'): return 2 if kind in {'paragraph', 'heading', 'codeBlock', 'blockquote', 'bulletList', 'orderedList', 'listItem'} else 1
        return 2 + sum(size(child) for child in node['content'])
    def walk(node, path, start):
        nonlocal count
        count += 1
        if count > 20_000: raise ValueError('document node limit exceeded')
        kind = node.get('type')
        if kind in {'paragraph', 'heading', 'codeBlock'}:
            children = node.get('content', [])
            supported = all(child.get('type') in {'text', 'hardBreak'} for child in children)
            text = ''.join(child.get('text', '') if child.get('type') == 'text' else '\n' if child.get('type') == 'hardBreak' else '\ufffc' for child in children)
            result.append({'path': list(path), 'start': start + 1, 'end': start + size(node) - 1, 'text': text, 'node': node, 'supported': supported})
            return
        if kind not in {'blockquote', 'bulletList', 'orderedList', 'listItem'}:
            result.append({'path': list(path), 'start': start, 'end': start + size(node), 'text': '\ufffc', 'node': node, 'supported': False})
            return
        child_start = start + 1
        for index, child in enumerate(node.get('content', [])):
            walk(child, (*path, index), child_start)
            child_start += size(child)
    offset = 0
    for index, node in enumerate(document.get('content', [])):
        walk(node, (index,), offset)
        offset += size(node)
    if sum(len(row['text']) for row in result) > MAX_TEXT:
        raise ValueError('chapter exceeds bounded revision limit')
    return result


def slice_inline(node, start, end):
    output, offset = [], 0
    for child in node.get('content', []):
        text = child.get('text', '') if child['type'] == 'text' else '\n'
        left, right = max(start - offset, 0), min(end - offset, len(text))
        if right > left:
            copied = deepcopy(child)
            if child['type'] == 'text': copied['text'] = text[left:right]
            output.append(copied)
        offset += len(text)
    return output


def replacement_node(node, start, end, text):
    selected = slice_inline(node, start, end)
    marks = [item.get('marks', []) for item in selected if item['type'] == 'text']
    if marks and any(item != marks[0] for item in marks):
        raise ValueError('mixed selected formatting cannot be mapped to a plain-text candidate; narrow selection')
    mark = deepcopy(marks[0]) if marks else []
    def run(value): return {'type': 'text', 'text': value, **({'marks': mark} if mark else {})}
    middle = []
    if node['type'] == 'codeBlock':
        if text: middle.append(run(text))
    else:
        for index, line in enumerate(text.split('\n')):
            if index: middle.append({'type': 'hardBreak'})
            if line: middle.append(run(line))
    result = deepcopy(node)
    length = sum(len(c.get('text', '')) if c['type'] == 'text' else 1 for c in node.get('content', []))
    children = slice_inline(node, 0, start) + middle + slice_inline(node, end, length)
    if children: result['content'] = children
    else: result.pop('content', None)
    return result


def selection_snapshot(document, value):
    if value.to_pos <= value.from_pos: raise ValueError('selection must be nonempty')
    blocks = text_blocks(document)
    start_blocks = [b for b in blocks if b['start'] <= value.from_pos <= b['end']]
    end_blocks = [b for b in blocks if b['start'] <= value.to_pos <= b['end']]
    if len(start_blocks) != 1 or len(end_blocks) != 1:
        raise ValueError('selection boundaries are not representable text positions')
    first, last = blocks.index(start_blocks[0]), blocks.index(end_blocks[0])
    if last < first: raise ValueError('selection order is invalid')
    chosen, quote = [], []
    for block in blocks[first:last + 1]:
        if not block['supported']: raise ValueError('selection contains unsupported inline objects')
        a = codepoint_offset(block['text'], max(value.from_pos, block['start']) - block['start'])
        b = codepoint_offset(block['text'], min(value.to_pos, block['end']) - block['start'])
        check_boundary(block['text'], a); check_boundary(block['text'], b)
        text = block['text'][a:b]
        quote.append(text)
        if a == b: continue
        item = {'path': block['path'], 'block_digest': node_digest(block['node']), 'start': a, 'end': b,
                'from_pos': block['start'] + utf16_size(block['text'][:a]), 'to_pos': block['start'] + utf16_size(block['text'][:b]), 'before': text}
        item['anchor_id'] = digest(item)
        marker = (block['node'].get('attrs') or {}).get(LOCK_ATTRIBUTE)
        item['lock_state'] = 'UNLOCKED' if marker is None or not active_lock(marker) else 'LOCKED' if isinstance(marker, dict) and marker.get('digest') == node_digest(block['node']) else 'STALE'
        chosen.append(item)
    if '\n'.join(quote) != value.text or not chosen:
        raise ValueError('exact saved selection does not match PM positions; reselect saved text')
    if len(chosen) > 50: raise ValueError('select at most 50 text blocks')
    return {'selection': value.model_dump(), 'document_digest': digest(document), 'blocks': chosen,
            'selection_digest': digest({'selection': value.model_dump(), 'document': digest(document), 'anchors': [b['anchor_id'] for b in chosen]})}


def inline_diff(before, after):
    if len(before) + len(after) > 8_000:
        return [{'kind': 'replace', 'before': before, 'after': after}], 'BOUNDED_BLOCK_REPLACEMENT'
    return [{'kind': tag, 'before': before[a:b], 'after': after[c:d]}
            for tag, a, b, c, d in SequenceMatcher(None, before, after, autojunk=False).get_opcodes()], 'EXACT_CODEPOINT_DIFF'


class RevisionIntelligenceService(DomainService):
    COLLECTION = 'revision_proposals'
    MILESTONES = 'revision_milestones'
    COMPARISONS = 'revision_comparisons'

    def __init__(self, store, novels, chapters, *, save_document=None, read_job=None):
        super().__init__(store, novels, chapters)
        self.save_document, self.read_job = save_document, read_job
        self.model_coordinator = None

    def capture(self, nid, scope, cid, expected=None):
        self.novels.get(nid)
        try: chapter = self.chapters_for(scope).get(cid)
        except FileNotFoundError:
            if scope.get('mode') == 'collaboration': raise ValueError('branch-isolated chapter authority unavailable') from None
            raise
        if chapter.get('novel_id') != nid or chapter.get('is_archived') or cid not in {c['id'] for c in self.chapters_for(scope).list(nid)}:
            raise FileNotFoundError(cid)
        # Only the exact explicit scope authority can supply branch documents.
        if chapter.get('branch_id') != scope.get('branch_id'):
            raise ValueError('branch-isolated chapter authority unavailable')
        if expected is not None and chapter['version'] != expected:
            raise StaleSourceError('chapter version changed; save and select its current version')
        if not isinstance(chapter.get('document'), dict): raise ValueError('saved rich document required')
        source = {'chapter_id': cid, 'version': chapter['version'], 'document_digest': digest(chapter['document']),
                  'privacy': source_privacy_status(chapter, scope.get('branch_id'), self.store.root)}
        return chapter, source

    def assert_source(self, nid, scope, source):
        _, current = self.capture(nid, scope, source['chapter_id'], source['version'])
        if current != source: raise StaleSourceError('chapter document, privacy or version changed')

    def selection(self, nid, scope, value):
        data = SelectionIn.model_validate(value)
        chapter, source = self.capture(nid, scope, data.chapter_id, data.chapter_version)
        result = selection_snapshot(chapter['document'], data)
        result.update(source=source, model_called=False, coordinate_contract='PROSEMIRROR_UTF16_V1')
        return result

    def catalog(self, nid, scope, cid=None):
        chapters = [{'id': c['id'], 'title': c.get('title', c['id']), 'version': c['version']}
                    for c in self.chapters_for(scope).list(nid) if c.get('branch_id') == scope.get('branch_id')]
        blocks = []; document_digest = None
        if cid:
            chapter, source = self.capture(nid, scope, cid)
            document_digest = source['document_digest']
            for b in text_blocks(chapter['document']):
                marker = (b['node'].get('attrs') or {}).get(LOCK_ATTRIBUTE)
                blocks.append({'path': b['path'], 'from_pos': b['start'], 'to_pos': b['end'], 'text': b['text'], 'supported': b['supported'],
                               'lock_state': 'UNLOCKED' if marker is None or not active_lock(marker) else 'LOCKED' if isinstance(marker, dict) and marker.get('digest') == node_digest(b['node']) else 'STALE'})
        return {'chapters': chapters, 'blocks': blocks, 'document_digest': document_digest, 'branch_sources_available': scope.get('branch_id') is None or bool(chapters),
                'model_called': False, 'range_limit': 50, 'chapter_character_limit': MAX_TEXT}

    def version_catalog(self, nid, scope, cid):
        chapter, _ = self.capture(nid, scope, cid)
        versions = self._original_versions(chapter)
        return {'chapter_id': cid, 'current_version': chapter['version'], 'items': [
            {'version': version, 'document_digest': digest(row['document']),
             'current': version == chapter['version'], 'timestamp': row.get('timestamp', row.get('updated_at'))}
            for version, row in sorted(versions.items(), reverse=True)], 'authority': 'ORIGINAL_CHAPTER_HISTORY'}

    def _original_versions(self, chapter):
        history = self.chapters_for(chapter.get('scope')).history(chapter['id'])
        if len(history) > 2000: raise ValueError('original version history exceeds comparison limit')
        versions = {chapter['version']: chapter}
        for row in history:
            version = row.get('version')
            if type(version) is not int or version < 1 or not isinstance(row.get('document'), dict):
                raise ValueError('original revision history is malformed')
            if version in versions: raise ValueError('original revision history has ambiguous versions')
            versions[version] = row
        return versions

    def _comparison_pair(self, nid, scope, value, *, require_current=True):
        data = VersionCompareIn.model_validate(value)
        chapter, current = self.capture(nid, scope, data.chapter_id, data.current_version if require_current else None)
        versions = self._original_versions(chapter)
        texts, pins = {}, {}
        for side, version in [('before', data.before_version), ('after', data.after_version)]:
            if version not in versions: raise FileNotFoundError(str(version))
            document = versions[version]['document']
            blocks = text_blocks(document)
            if any(not b['supported'] for b in blocks): raise ValueError('version contains unsupported text objects')
            texts[side] = '\n'.join(b['text'] for b in blocks)
            pins[side] = {'version': version, 'document_digest': digest(document), 'text_digest': digest(texts[side])}
        policy = {key: current['privacy'][key] for key in ('privacy_level', 'reviewed_by', 'reviewed_at')}
        capture = {'chapter_id': data.chapter_id, 'versions': pins, 'privacy': policy,
                   'coordinate_contract': 'ORIGINAL_SAVED_TEXT_BLOCKS_CODEPOINT_V1'}
        return data, texts, capture

    def compare_versions(self, nid, scope, value, *, reauthorize=lambda: None):
        reauthorize()
        data, texts, capture = self._comparison_pair(nid, scope, value)
        changes, method = inline_diff(texts['before'], texts['after'])
        reauthorize()
        _, _, final_capture = self._comparison_pair(nid, scope, data)
        if capture != final_capture: raise StaleSourceError('original compared versions changed')
        return {'comparison': data.model_dump(), 'capture': capture, 'preview_digest': digest(capture),
                'before_text': texts['before'], 'after_text': texts['after'], 'diff': changes,
                'diff_method': method, 'model_called': False, 'semantic_execution': 'NOT_REQUESTED',
                'semantic_verification': 'AUTHOR_OR_IMPORTED_ASSESSMENT_REQUIRES_REVIEW'}

    @staticmethod
    def _semantic_changes(changes, texts):
        result = []
        for item in changes:
            raw = item.model_dump() if hasattr(item, 'model_dump') else item
            data = SemanticChangeIn.model_validate(raw).model_dump()
            for side in ('before', 'after'):
                quote, start = data[side + '_quote'], data[side + '_start']
                if quote and texts[side][start:start + len(quote)] != quote:
                    raise ValueError('semantic evidence must match exact original-version quote and codepoint offset')
                if not quote and start != 0: raise ValueError('absent evidence must have zero offset')
            data['interpretation'] = 'MODEL_DERIVED' if data['source'] == 'IMPORTED_MODEL_ASSESSMENT' else 'AUTHOR_INTERPRETATION'
            data['provenance_verification'] = 'DECLARED_NOT_VERIFIED' if data['source'] == 'IMPORTED_MODEL_ASSESSMENT' else 'USER_AUTHORED'
            data['evidence_verification'] = 'EXACT_QUOTE_ONLY_NOT_SEMANTIC_TRUTH'
            data['id'] = digest(data)
            if data['id'] in {row['id'] for row in result}: raise ValueError('duplicate semantic assessment')
            result.append(data)
        return result

    def save_comparison(self, nid, scope, actor, value, *, reauthorize=lambda: None):
        data = VersionComparisonSaveIn.model_validate(value)
        preview = self.compare_versions(nid, scope, data.comparison, reauthorize=reauthorize)
        if preview['preview_digest'] != data.preview_digest: raise StaleSourceError('version comparison preview changed')
        changes = self._semantic_changes(data.changes, {'before': preview['before_text'], 'after': preview['after_text']})
        with self.store.transaction(nid, scope) as state:
            reauthorize()
            current = self.compare_versions(nid, scope, data.comparison, reauthorize=reauthorize)
            if current['capture'] != preview['capture']: raise StaleSourceError('version comparison source changed')
            if len(collection(state, self.COMPARISONS)) >= 200: raise ValueError('version comparison limit reached')
            row = new_row(nid, scope, actor, {'status': 'REVIEW', 'title': data.title,
                'comparison': data.comparison.model_dump(), 'capture': preview['capture'], 'changes': changes,
                'model_called': False, 'semantic_execution': 'NOT_REQUESTED', 'manuscript_modified': False})
            collection(state, self.COMPARISONS)[row['id']] = row
            reauthorize()
        return self.comparison(nid, scope, row['id'])

    def _assert_comparison(self, nid, scope, row):
        _, texts, capture = self._comparison_pair(nid, scope, row['comparison'], require_current=False)
        if capture != row['capture']: raise StaleSourceError('original version or privacy changed; prepare a fresh comparison')
        return texts

    def comparison(self, nid, scope, rid):
        row = self.get(nid, scope, self.COMPARISONS, rid)
        try: texts = self._assert_comparison(nid, scope, row)
        except (ValueError, FileNotFoundError):
            return {'id': rid, 'version': row['version'], 'status': row['status'], 'stale': True,
                    'chapter_id': row['comparison']['chapter_id'], 'changes': [], 'history': [], 'model_called': row.get('model_called', False),
                    'model_preview': None, 'model_assessments': [], 'model_execution': deepcopy(row.get('model_execution'))}
        changes, method = inline_diff(texts['before'], texts['after'])
        row['history'] = [{key: prior.get(key) for key in ('version', 'status', 'title', 'updated_at')} for prior in row.get('history', [])]
        from .flags import enabled_flags
        if not {'revision_intelligence_v2', 'model_broker_v2', 'author_context_inspector_v2'}.issubset(enabled_flags()):
            row.pop('model_preview', None); row.pop('model_assessments', None)
            row['model_unavailable'] = True
        return {**row, 'stale': False, 'diff': changes, 'diff_method': method,
                'before_text': texts['before'], 'after_text': texts['after']}

    def record_model_result(self, ctx, previous, execution, opinions, guard):
        from .revision_intelligence_model import parse_version_opinions
        from .store import canonical
        nid, scope, actor, rid = ctx.novel_id, ctx.scope, ctx.actor, previous['id']
        if opinions is None and execution == previous.get('model_execution'):
            self._assert_comparison(nid, scope, previous); guard()
            return self.comparison(nid, scope, rid)
        with self.store.transaction(nid, scope) as state:
            row = require_row(state, self.COMPARISONS, rid)
            guard(); self._assert_comparison(nid, scope, row)
            check_version({key: row[key] for key in ('id', 'version', 'status')}, previous['version'])
            if row['created_by'] != actor or row.get('model_execution') != previous.get('model_execution'):
                raise ValueError('REVISION_MODEL_RECEIPT_CHANGED')
            if row['status'] != 'REVIEW': raise ValueError('REVISION_MODEL_REVIEW_CLOSED')
            assessments = deepcopy(row.get('model_assessments', []))
            if opinions is not None:
                texts = self._assert_comparison(nid, scope, row)
                opinions = parse_version_opinions(canonical({'opinions': opinions}), texts, row['capture'])
                route = row['model_preview']['broker']['chosen']
                identity = {key: deepcopy(route[key]) for key in ('route_id', 'provider_id', 'model_id', 'fingerprint', 'identity', 'synthetic')}
                assessments = [{**opinion, 'id': digest([execution['job_id'], index, opinion]), 'decision': 'PENDING',
                    'interpretation': 'MODEL_DERIVED', 'source': 'EXECUTED_MODEL_ASSESSMENT',
                    'provenance_verification': 'ORIGINAL_REGISTERED_LOCAL_JOB', 'model': identity,
                    'job_id': execution['job_id'], 'quality_verification': row['model_preview']['quality_verification'],
                    'evidence_verification': 'EXACT_QUOTE_ONLY_NOT_SEMANTIC_TRUTH'} for index, opinion in enumerate(opinions)]
            change_row(row, actor, row['version'], lambda target: target.update(model_execution=deepcopy(execution),
                model_assessments=assessments, model_called=execution['model_called'],
                semantic_execution='MODEL_DERIVED_REQUIRES_REVIEW' if opinions is not None else target.get('semantic_execution', 'NOT_REQUESTED')))
            self._assert_comparison(nid, scope, row); guard()
        return self.comparison(nid, scope, rid)

    def review_model_opinion(self, ctx, rid, oid, expected_version, action, guard):
        if action not in {'accept', 'ignore', 'reopen'}: raise ValueError('invalid model opinion review')
        with self.store.transaction(ctx.novel_id, ctx.scope) as state:
            row = require_row(state, self.COMPARISONS, rid)
            guard(); self._assert_comparison(ctx.novel_id, ctx.scope, row)
            check_version({key: row[key] for key in ('id', 'version', 'status')}, expected_version)
            if row['status'] != 'REVIEW': raise ValueError('reopen comparison before reviewing model opinions')
            opinion = next((item for item in row.get('model_assessments', []) if item['id'] == oid), None)
            if opinion is None: raise FileNotFoundError(oid)
            change_row(row, ctx.actor, expected_version, lambda _: opinion.update(decision={'accept': 'ACCEPTED_INTERPRETATION', 'ignore': 'IGNORED', 'reopen': 'PENDING'}[action]))
            guard()
        return self.comparison(ctx.novel_id, ctx.scope, rid)

    def comparisons(self, nid, scope):
        from .flags import enabled_flags
        models_enabled = {'revision_intelligence_v2', 'model_broker_v2', 'author_context_inspector_v2'}.issubset(enabled_flags())
        items = []
        for row in self.list(nid, scope, self.COMPARISONS):
            try: self._assert_comparison(nid, scope, row); stale = False
            except (ValueError, FileNotFoundError): stale = True
            items.append({'id': row['id'], 'version': row['version'], 'status': row['status'],
                          'title': row['title'] if not stale else '来源不可用的版本比较', 'stale': stale,
                          'comparison': row['comparison'], 'model_called': row.get('model_called', False),
                          **({'model_execution': {key: row['model_execution'].get(key) for key in ('job_id', 'status')}} if models_enabled and row.get('model_execution') else {})})
        return {'items': items}

    def edit_comparison(self, nid, scope, actor, rid, value, *, reauthorize=lambda: None):
        data = VersionComparisonEditIn.model_validate(value)
        with self.store.transaction(nid, scope) as state:
            row = require_row(state, self.COMPARISONS, rid)
            reauthorize(); check_version({key: row[key] for key in ('id', 'version', 'status')}, data.expected_version)
            if row['status'] != 'REVIEW': raise ValueError('reopen comparison before editing interpretations')
            texts = self._assert_comparison(nid, scope, row)
            changes = self._semantic_changes(data.changes, texts)
            change_row(row, actor, data.expected_version, lambda target: target.update(title=data.title, changes=changes))
            self._assert_comparison(nid, scope, row); reauthorize()
        return self.comparison(nid, scope, rid)

    def review_comparison(self, nid, scope, actor, rid, value, *, reauthorize=lambda: None):
        data = VersionComparisonReviewIn.model_validate(value)
        with self.store.transaction(nid, scope) as state:
            row = require_row(state, self.COMPARISONS, rid)
            reauthorize(); check_version({key: row[key] for key in ('id', 'version', 'status')}, data.expected_version)
            transitions = {'acknowledge': ({'REVIEW'}, 'ACKNOWLEDGED'), 'archive': ({'REVIEW', 'ACKNOWLEDGED'}, 'ARCHIVED'),
                           'reopen': ({'ACKNOWLEDGED', 'ARCHIVED'}, 'REVIEW')}
            if (row.get('model_execution') or {}).get('status') in {'ADMISSION_PENDING', 'QUEUED', 'RUNNING', 'UNKNOWN'}:
                raise ValueError('cancel or reconcile original model task before closing comparison')
            allowed, status = transitions[data.action]
            if row['status'] not in allowed: raise ValueError('invalid comparison review transition')
            if data.action != 'archive': self._assert_comparison(nid, scope, row)
            change_row(row, actor, data.expected_version, lambda target: target.update(status=status))
            reauthorize()
        return self.comparison(nid, scope, rid)

    def create_proposal(self, nid, scope, actor, value, *, reauthorize=lambda: None, job_reader=None):
        data = ProposalIn.model_validate(value)
        captured = self.selection(nid, scope, data.selection)
        if captured['selection_digest'] != data.selection_digest: raise StaleSourceError('selection digest changed')
        anchors = {b['anchor_id']: b for b in captured['blocks']}
        if len({r.anchor_id for r in data.replacements}) != len(data.replacements) or any(r.anchor_id not in anchors for r in data.replacements):
            raise ValueError('candidate anchors must be unique and within exact selection')
        if sum(len(r.text) for r in data.replacements) > MAX_TEXT: raise ValueError('candidate text exceeds limit')
        job_info = None
        if data.job_id:
            reader = job_reader or self.read_job
            if reader is None: raise ValueError('authorized generation reader unavailable')
            job = reader(data.job_id)
            if hasattr(job, 'public'): job = job.public()
            if (job.get('status') != 'COMPLETED' or job.get('novel_id') != nid or job.get('chapter_id') != data.selection.chapter_id
                or job.get('base_chapter_version') != data.selection.chapter_version or job.get('source') != data.selection.text):
                raise StaleSourceError('generated draft no longer matches this exact saved selection')
            binding = {'selection': captured['selection'], 'selection_digest': data.selection_digest}
            if not job.get('partial_revision_only') or job.get('revision_selection_binding') != binding:
                raise ValueError('generated draft lacks trusted exact-selection binding; regenerate through selection assistant')
            # A model cannot decide how extra paragraphs map back into a range.
            # Only an exact 1:1, newline-free text-block result is adoptable.
            lines = str(job.get('output', '')).split('\n')
            ordered = [r.text for b in captured['blocks'] for r in data.replacements if r.anchor_id == b['anchor_id']]
            if len(ordered) != len(captured['blocks']) or any('\n' in b['before'] for b in captured['blocks']) or lines != ordered:
                raise ValueError('generated output has unrepresentable block scope; manually select and review a bounded excerpt instead')
            job_info = {'id': data.job_id, 'provider': job.get('provider'), 'model': job.get('model'), 'output_digest': digest(job.get('output')), 'execution_mode': job.get('execution_mode', 'UNKNOWN'), 'binding_digest': digest(binding)}
        chapter, _ = self.capture(nid, scope, data.selection.chapter_id, data.selection.chapter_version)
        diffs = []
        for replacement in data.replacements:
            block = deepcopy(anchors[replacement.anchor_id])
            replacement_node(at_path(chapter['document'], block['path']), block['start'], block['end'], replacement.text)
            if block['before'] == replacement.text: continue
            block.update(after=replacement.text, status='PENDING')
            block['diff'], block['diff_method'] = inline_diff(block['before'], replacement.text)
            diffs.append(block)
        if not diffs: raise ValueError('candidate contains no text differences')
        by_anchor = {b['anchor_id']: b for b in diffs}
        for explanation in data.explanations:
            block = by_anchor.get(explanation.anchor_id)
            if not block or explanation.before_quote not in block['before'] or explanation.after_quote not in block['after']:
                raise ValueError('semantic explanation requires exact before and after quote evidence')
        reauthorize()
        with self.store.transaction(nid, scope) as doc:
            self.assert_source(nid, scope, captured['source']); reauthorize()
            row = new_row(nid, scope, actor, {'status': 'REVIEW', 'source': captured['source'], 'selection': captured['selection'],
                'selection_digest': captured['selection_digest'], 'blocks': diffs, 'explanations': [x.model_dump() for x in data.explanations],
                'goal': data.goal, 'generation': job_info, 'origin': 'GENERATED_DRAFT' if job_info else 'MANUAL_CANDIDATE',
                'model_called': False, 'verification': 'DETERMINISTIC_TEXT_DIFF_NOT_MODEL_QUALITY', 'acceptance': None})
            collection(doc, self.COLLECTION)[row['id']] = row
            return deepcopy(row)

    def _assert_generation(self, row, job_reader=None):
        if not row.get('generation'): return
        reader = job_reader or self.read_job
        if reader is None: raise ValueError('original generated-draft authorization is unavailable')
        job = reader(row['generation']['id'])
        if hasattr(job, 'public'): job = job.public()
        if (not job.get('partial_revision_only') or digest(job.get('revision_selection_binding')) != row['generation'].get('binding_digest')):
            raise StaleSourceError('generated draft selection authority changed')
        if digest(job.get('output')) != row['generation']['output_digest'] or job.get('chapter_id') != row['source']['chapter_id'] or job.get('status') != 'COMPLETED':
            raise StaleSourceError('generated draft changed or no longer available')

    def proposal(self, nid, scope, rid, job_reader=None):
        row = self.get(nid, scope, self.COLLECTION, rid)
        self._assert_generation(row, job_reader)
        try: self.assert_source(nid, scope, row['source']); stale = False
        except (ValueError, FileNotFoundError): stale = True
        row['stale'] = stale
        # Current authorization never leaks former source content after source
        # privacy/version drift. Original history remains the review authority.
        if stale:
            row = {k: v for k, v in row.items() if k not in {'blocks', 'explanations', 'selection', 'history'}}
        return row

    def proposals(self, nid, scope, job_reader=None):
        from fastapi import HTTPException
        rows = self.list(nid, scope, self.COLLECTION)
        items = []
        for row in rows[-100:]:
            try: items.append(self.proposal(nid, scope, row['id'], job_reader))
            except HTTPException as exc:
                if exc.status_code not in {401, 403, 404}: raise
                # A revoked generation does not break unrelated manual drafts,
                # nor leak its identity, title, content or hidden count.
        return {'items': items, 'truncated': len(rows) > 100}

    def _review(self, nid, scope, row, data):
        check_version(row, data.expected_version)
        if row['status'] not in {'REVIEW', 'PARTIAL'}: raise ValueError('review is closed or acceptance uncertain; inspect original chapter history')
        self.assert_source(nid, scope, row['source'])
        accept, reject = set(data.accept_ids), set(data.reject_ids)
        if len(accept) != len(data.accept_ids) or len(reject) != len(data.reject_ids) or accept & reject or not (accept | reject):
            raise ValueError('choose unique disjoint accept/reject blocks')
        blocks = {b['anchor_id']: b for b in row['blocks']}
        if any(i not in blocks or blocks[i]['status'] != 'PENDING' for i in accept | reject):
            raise ValueError('only pending blocks may be reviewed')
        chapter, _ = self.capture(nid, scope, row['source']['chapter_id'], row['source']['version'])
        candidate = deepcopy(chapter['document'])
        for key in accept:
            block = blocks[key]
            node = at_path(candidate, block['path'])
            if node_digest(node) != block['block_digest']: raise StaleSourceError('paragraph anchor changed')
            value = replacement_node(node, block['start'], block['end'], block['after'])
            parent = at_path(candidate, block['path'][:-1])
            parent['content'][block['path'][-1]] = value
        assert_ai_locks(chapter['document'], candidate)
        receipt = {'proposal_id': row['id'], 'proposal_version': row['version'], 'source': row['source'], 'accept_ids': sorted(accept), 'reject_ids': sorted(reject),
                   'before_document_digest': digest(chapter['document']), 'after_document_digest': digest(candidate), 'checkpoint_version': chapter['version']}
        return candidate, {**receipt, 'preview_digest': digest(receipt), 'creates_new_current_revision': bool(accept), 'pending_blocks': len(blocks) - len(accept | reject) - sum(b['status'] != 'PENDING' for b in blocks.values())}

    def preview(self, nid, scope, rid, value, reauthorize=lambda: None, job_reader=None):
        data = ReviewIn.model_validate(value)
        row = self.get(nid, scope, self.COLLECTION, rid)
        self._assert_generation(row, job_reader)
        _, result = self._review(nid, scope, row, data)
        reauthorize(); self.assert_source(nid, scope, row['source'])
        return result

    def apply(self, nid, scope, actor, rid, value, *, reauthorize=lambda: None, save_document=None, job_reader=None):
        data = ReviewIn.model_validate(value)
        writer = save_document or self.save_document
        if data.accept_ids and writer is None: raise ValueError('original chapter write authority unavailable')
        # Commit the journal claim BEFORE any original-authority side effect.
        with self.store.transaction(nid, scope) as doc:
            row = require_row(doc, self.COLLECTION, rid)
            self._assert_generation(row, job_reader)
            candidate, preview = self._review(nid, scope, row, data)
            if not data.preview_digest or preview['preview_digest'] != data.preview_digest:
                raise StaleSourceError('review selected-block preview before accepting')
            reauthorize()
            change_row(row, actor, row['version'], lambda r: r.update(status='ACCEPTING', acceptance=preview))
            source = deepcopy(row['source'])
            claim_version = row['version']
        saved = None
        try:
            self._assert_generation(row, job_reader)
            reauthorize(); self.assert_source(nid, scope, source)
            if data.accept_ids:
                saved = writer(source['chapter_id'], candidate, source['version'], 'AI_ACCEPT')
            reauthorize()
            with self.store.transaction(nid, scope) as doc:
                row = require_row(doc, self.COLLECTION, rid); check_version(row, claim_version)
                for block in row['blocks']:
                    if block['anchor_id'] in data.accept_ids: block['status'] = 'ACCEPTED'
                    if block['anchor_id'] in data.reject_ids: block['status'] = 'REJECTED'
                # Remaining blocks stay immutable draft evidence on their original
                # source. They require explicit rebase review before a later save.
                status = 'PARTIAL' if any(b['status'] == 'PENDING' for b in row['blocks']) else 'CLOSED'
                change_row(row, actor, row['version'], lambda r: r.update(status=status, accepted_chapter_version=saved['version'] if saved else None))
                return {'proposal': deepcopy(row), 'chapter': saved}
        except Exception:
            with self.store.transaction(nid, scope) as doc:
                row = require_row(doc, self.COLLECTION, rid)
                if row['status'] == 'ACCEPTING':
                    change_row(row, actor, row['version'], lambda r: r.update(status='ACCEPTANCE_UNCERTAIN'))
            raise

    def rebase(self, nid, scope, actor, rid, value, *, reauthorize=lambda: None, job_reader=None):
        """Re-review only the untouched remainder of OUR own successful CAS.

        No fuzzy relocation, no arbitrary external-change rebase. The original
        review remains immutable evidence; this creates a new review draft.
        """
        data = RebaseIn.model_validate(value)
        with self.store.transaction(nid, scope) as doc:
            row = require_row(doc, self.COLLECTION, rid); check_version(row, data.expected_version)
            self._assert_generation(row, job_reader)
            if row['status'] != 'PARTIAL' or not row.get('accepted_chapter_version'):
                raise ValueError('only successfully partially accepted revisions can be re-reviewed')
            chapter, source = self.capture(nid, scope, row['source']['chapter_id'], data.chapter_version)
            if (chapter['version'] != row['accepted_chapter_version']
                or digest(chapter['document']) != row['acceptance']['after_document_digest']
                or source['privacy']['privacy_level'] != row['source']['privacy']['privacy_level']):
                raise StaleSourceError('external source change requires a fresh selection and candidate')
            if row.get('remaining_review_id'):
                return deepcopy(require_row(doc, self.COLLECTION, row['remaining_review_id']))
            pending = [b for b in row['blocks'] if b['status'] == 'PENDING']
            if not pending: raise ValueError('no pending blocks remain')
            current = {tuple(b['path']): b for b in text_blocks(chapter['document'])}
            anchors = []
            for old in pending:
                block = current.get(tuple(old['path']))
                if block is None or node_digest(block['node']) != old['block_digest']:
                    raise StaleSourceError('pending paragraph anchor changed; reselect explicitly')
                chosen = SelectionIn(chapter_id=chapter['id'], chapter_version=chapter['version'],
                    from_pos=block['start'] + utf16_size(block['text'][:old['start']]),
                    to_pos=block['start'] + utf16_size(block['text'][:old['end']]), text=old['before'])
                captured = selection_snapshot(chapter['document'], chosen)['blocks'][0]
                captured.update(after=old['after'], status='PENDING', diff=old['diff'], diff_method=old['diff_method'])
                anchors.append(captured)
            reauthorize()
            fresh = new_row(nid, scope, actor, {'status': 'REVIEW', 'source': source,
                'blocks': anchors, 'explanations': [], 'goal': row['goal'], 'generation': row['generation'],
                'origin': 'EXPLICIT_REVIEW_REMAINING_BLOCKS', 'source_proposal_id': row['id'],
                'original_source': row['source'], 'model_called': False,
                'verification': 'DETERMINISTIC_UNCHANGED_ANCHORS_NEW_REVIEW_REQUIRED', 'acceptance': None})
            collection(doc, self.COLLECTION)[fresh['id']] = fresh
            change_row(row, actor, row['version'], lambda r: r.update(remaining_review_id=fresh['id']))
            return deepcopy(fresh)

    def locks(self, nid, scope, actor, value, *, reauthorize=lambda: None, save_document=None):
        data = LockIn.model_validate(value)
        captured = self.selection(nid, scope, data.selection)
        if captured['selection_digest'] != data.selection_digest: raise StaleSourceError('reselect current paragraph before changing locks')
        writer = save_document or self.save_document
        if writer is None: raise ValueError('original chapter write authority unavailable')
        chapter, _ = self.capture(nid, scope, data.selection.chapter_id, data.selection.chapter_version)
        document = deepcopy(chapter['document'])
        for block in captured['blocks']:
            node = at_path(document, block['path']); marker = (node.get('attrs') or {}).get(LOCK_ATTRIBUTE)
            if data.action == 'lock':
                if marker is not None and active_lock(marker): raise ValueError('paragraph already locked; review and unlock stale locks explicitly')
                marker = {'id': digest([data.selection.chapter_id, data.selection.chapter_version, block['path'], actor]), 'state': 'LOCKED',
                          'digest': node_digest(node), 'source_version': chapter['version'], 'created_by': actor}
            else:
                if marker is None: raise ValueError('paragraph is not locked')
                marker = {'id': marker_id(marker), 'state': 'UNLOCKED', 'unlocked_by': actor, 'source_version': chapter['version']}
            node.setdefault('attrs', {})[LOCK_ATTRIBUTE] = marker
        self.assert_source(nid, scope, captured['source']); reauthorize()
        return writer(chapter['id'], document, chapter['version'], 'EXPLICIT_CHECKPOINT')

    def unlock_block(self, nid, scope, actor, value, *, reauthorize=lambda: None, save_document=None):
        data = UnlockBlockIn.model_validate(value)
        if any(type(index) is not int or index < 0 for index in data.path): raise ValueError('invalid paragraph path')
        chapter, source = self.capture(nid, scope, data.chapter_id, data.chapter_version)
        if source['document_digest'] != data.document_digest: raise StaleSourceError('saved paragraph document changed')
        writer = save_document or self.save_document
        if writer is None: raise ValueError('original chapter write authority unavailable')
        document = deepcopy(chapter['document']); node = at_path(document, data.path)
        marker = (node.get('attrs') or {}).get(LOCK_ATTRIBUTE)
        if marker is None or not active_lock(marker): raise ValueError('paragraph is not actively locked')
        node.setdefault('attrs', {})[LOCK_ATTRIBUTE] = {'id': marker_id(marker), 'state': 'UNLOCKED', 'unlocked_by': actor, 'source_version': chapter['version']}
        self.assert_source(nid, scope, source); reauthorize()
        return writer(chapter['id'], document, chapter['version'], 'EXPLICIT_CHECKPOINT')

    def milestone(self, nid, scope, actor, value, reauthorize=lambda: None):
        data = MilestoneIn.model_validate(value)
        _, source = self.capture(nid, scope, data.chapter_id, data.chapter_version)
        with self.store.transaction(nid, scope) as doc:
            self.assert_source(nid, scope, source); reauthorize()
            row = new_row(nid, scope, actor, {**data.model_dump(), 'status': 'RECORDED', 'source': source,
                'storage': 'ORIGINAL_CHAPTER_VERSION_REFERENCE', 'copies_document': False})
            collection(doc, self.MILESTONES)[row['id']] = row
            return deepcopy(row)
