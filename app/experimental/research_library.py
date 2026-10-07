"""A10 extends Research metadata with native scoped, cited local sources.

Legacy research is projected live in local scope, never copied or migrated.
New native records use ExperimentalStore; the legacy metadata-only sidecar keeps
its old contract. Research never becomes manuscript, Canon or character input.
"""
from __future__ import annotations

import base64
import copy
import hashlib
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..import_parsers import decode_base64
from .common import DomainService, StaleSourceError, new_row, now, check_version, change_row, snapshot
from .planning import collection, require_row, digest
from .research_extract import MAX_BYTES, extract_document, fetch_webpage, _paragraphs
from .world import WorldRecordIn

SOURCES = 'research_sources'
NOTES = 'research_notes'
MAX_SOURCE_REVISIONS = 20
MAX_SOURCES = 100
MAX_STORED_BYTES = 32 * 1024 * 1024


class StrictInput(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class MetadataIn(StrictInput):
    title: str = Field(min_length=1, max_length=240)
    author: str = Field(default='', max_length=160)
    source: str = Field(default='', max_length=2000)
    source_version: str = Field(default='', max_length=160)
    usage_notes: str = Field(default='', max_length=4000)
    access: Literal['PRIVATE', 'PROJECT'] = 'PRIVATE'


class FileIn(MetadataIn):
    filename: str = Field(min_length=1, max_length=240)
    content_base64: str = Field(min_length=4, max_length=((MAX_BYTES + 2) // 3) * 4)


class ReplaceFileIn(FileIn):
    expected_version: int = Field(ge=1)


class RestoreSourceIn(StrictInput):
    expected_version: int = Field(ge=1)
    restore_version: int = Field(ge=1)


class WebIn(MetadataIn):
    url: str = Field(min_length=1, max_length=2000)
    confirm_fetch: Literal[True]


class EditIn(MetadataIn):
    expected_version: int = Field(ge=1)


class CitationIn(StrictInput):
    source_id: str = Field(min_length=1, max_length=200)
    source_version: int = Field(ge=1)
    paragraph: int = Field(ge=0, le=5000)
    page: int | None = Field(default=None, ge=1, le=1000)
    quote_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')

    @model_validator(mode='after')
    def location(self):
        if (self.paragraph == 0) != (self.page is not None):
            raise ValueError('page-only citation requires paragraph 0 and a page')
        return self


class NoteIn(StrictInput):
    title: str = Field(min_length=1, max_length=240)
    text: str = Field(min_length=1, max_length=8000)
    citations: list[CitationIn] = Field(min_length=1, max_length=20)


class EditNoteIn(NoteIn):
    expected_version: int = Field(ge=1)


class AdoptIn(StrictInput):
    title: str = Field(min_length=1, max_length=240)
    original_setting: str = Field(min_length=1, max_length=8000)
    citations: list[CitationIn] = Field(min_length=1, max_length=20)
    confirm_original: Literal[True]


class ResearchLibraryService(DomainService):
    def __init__(self, store, novels, chapters, *, legacy=None, world=None):
        super().__init__(store, novels, chapters)
        self.legacy, self.world = legacy, world
        self.vision_provider = None

    @staticmethod
    def _visible(row, actor):
        return row.get('status') == 'ACTIVE' and (row.get('access') == 'PROJECT' or row.get('created_by') == actor)

    @staticmethod
    def _public(row, details=False):
        excluded = {'content_base64', 'history', 'paragraphs'}
        value = {key: copy.deepcopy(item) for key, item in row.items() if key not in excluded}
        if details: value['paragraphs'] = [{**copy.deepcopy(paragraph), 'citation': ResearchLibraryService._cite(row, paragraph)} for paragraph in row.get('paragraphs', [])]
        value['page_citations'] = [ResearchLibraryService._page_cite(row, page) for page in row.get('unread_pages', [])] if details else []
        value['layer'] = 'RESEARCH'
        value['paragraph_count'] = len(row.get('paragraphs', []))
        return value

    def _legacy_sources(self, nid, scope):
        if self.legacy is None or scope.get('mode') != 'local': return []
        projected = []
        for source in self.legacy.list_research(nid)['items']:
            if source.get('status') != 'ACTIVE': continue
            text = source.get('excerpt') or ''
            projected.append({**source, 'id': 'legacy:' + source['id'], 'access': 'PROJECT',
                'format': 'LEGACY_NOTE', 'origin': 'LEGACY_LIVE', 'storage': 'durable_sidecar',
                'source': source.get('url') or source.get('citation', ''), 'source_version': str(source['version']),
                'usage_notes': source.get('notes', ''), 'accessed_at': source.get('updated_at'),
                'extraction_status': 'TEXT_EXTRACTED' if text else 'NO_TEXT',
                'paragraphs': _paragraphs([(None, text)]), 'warnings': ['Existing metadata; URLs are not fetched.'],
                'content_sha256': hashlib.sha256(text.encode()).hexdigest(), 'privacy_level': 'LOCAL_ONLY'})
        return projected

    def _sources(self, nid, scope, actor, state=None):
        self.novels.get(nid)
        state = state or self.store.read(nid, scope)
        rows = []
        for rid in collection(state, SOURCES):
            row = require_row(state, SOURCES, rid)
            if self._visible(row, actor): rows.append(copy.deepcopy(row))
        return rows + self._legacy_sources(nid, scope)

    def _source(self, nid, scope, actor, rid, state=None):
        row = next((row for row in self._sources(nid, scope, actor, state) if row['id'] == rid), None)
        if row is None: raise FileNotFoundError(rid)
        return row

    def sources(self, nid, scope, actor):
        rows = [self._public(row) for row in self._sources(nid, scope, actor)]
        return {'items': rows, 'total': len(rows), 'storage': self.store.storage_mode,
                'adapters': {'ocr': 'NOT_CONFIGURED', 'vector': 'NOT_CONFIGURED', 'vision': 'NOT_CONFIGURED'},
                'external_fetch': False, 'context_injection': False}

    def source(self, nid, scope, actor, rid):
        return self._public(self._source(nid, scope, actor, rid), True)

    def original(self, nid, scope, actor, rid):
        row = self._source(nid, scope, actor, rid)
        if not row.get('content_base64'): raise FileNotFoundError(rid)
        return base64.b64decode(row['content_base64']), row['filename']

    def _save_source(self, nid, scope, actor, meta, extraction, *, filename='', encoded='', guard):
        self.novels.get(nid)
        payload = {**meta, **extraction, 'filename': filename, 'content_base64': encoded,
                   'origin': 'LOCAL_IMPORT' if encoded else 'EXPLICIT_WEB_FETCH',
                   'status': 'ACTIVE', 'accessed_at': now(), 'privacy_level': 'LOCAL_ONLY'}
        with self.store.transaction(nid, scope) as state:
            guard()
            rows = collection(state, SOURCES)
            if len(rows) >= MAX_SOURCES: raise ValueError('RESEARCH_SOURCE_LIMIT')
            if sum(len(row.get('content_base64', '')) + sum(len(p['text']) for p in row.get('paragraphs', [])) for row in rows.values()) + len(encoded) + sum(len(p['text']) for p in extraction['paragraphs']) > MAX_STORED_BYTES:
                raise ValueError('RESEARCH_STORAGE_LIMIT')
            row = new_row(nid, scope, actor, payload)
            rows[row['id']] = row
            self._storage_limit(state)
            guard()
            return self._public(row, True)

    def import_file(self, nid, scope, actor, value, *, guard):
        body = FileIn.model_validate(value)
        guard()
        try: raw = decode_base64(body.content_base64)
        except ValueError as exc: raise ValueError('RESEARCH_BASE64_INVALID') from exc
        extraction = extract_document(body.filename, raw)
        guard()
        meta = MetadataIn.model_validate(body.model_dump(exclude={'filename', 'content_base64'})).model_dump()
        return self._save_source(nid, scope, actor, meta, extraction, filename=body.filename, encoded=body.content_base64, guard=guard)

    def import_web(self, nid, scope, actor, value, *, guard):
        body = WebIn.model_validate(value)
        guard()
        extraction = fetch_webpage(body.url, guard=guard)
        guard()
        meta = MetadataIn.model_validate(body.model_dump(exclude={'url', 'confirm_fetch'})).model_dump()
        meta['source'] = extraction['final_url']
        return self._save_source(nid, scope, actor, meta, extraction, guard=guard)

    def edit_source(self, nid, scope, actor, rid, value, *, guard):
        body = EditIn.model_validate(value)
        with self.store.transaction(nid, scope) as state:
            guard()
            row = self._source(nid, scope, actor, rid, state)
            if row.get('origin') == 'LEGACY_LIVE': raise ValueError('RESEARCH_LEGACY_USE_EXISTING_EDITOR')
            if row['created_by'] != actor: raise FileNotFoundError(rid)
            check_version(self._public(row), body.expected_version)
            target = require_row(state, SOURCES, rid)
            self._change_source(state, target, actor, body.expected_version, body.model_dump(exclude={'expected_version'}))
            self._invalidate(state, rid)
            guard()
            return self._public(target, True)

    @staticmethod
    def _storage_limit(state):
        from .store import canonical
        # Include retained versions and UTF-8 bytes; quotas cannot be bypassed
        # through repeated edits or multibyte text.
        if len(canonical(collection(state, SOURCES)).encode()) > MAX_STORED_BYTES:
            raise ValueError('RESEARCH_STORAGE_LIMIT')

    def _change_source(self, state, row, actor, version, values):
        stopping = values.get('status') in {'REVOKED', 'DELETED'}
        if not stopping and len(row.get('history', [])) >= MAX_SOURCE_REVISIONS:
            raise ValueError('RESEARCH_REVISION_LIMIT')
        change_row(row, actor, version, lambda target: target.update(values))
        if not stopping: self._storage_limit(state)

    def _owned_source(self, nid, scope, actor, rid, state):
        self.novels.get(nid)
        row = require_row(state, SOURCES, rid)
        if row.get('created_by') != actor or row.get('novel_id') != nid or row.get('scope') != scope:
            raise FileNotFoundError(rid)
        return row

    def archived_sources(self, nid, scope, actor):
        self.novels.get(nid)
        state = self.store.read(nid, scope)
        rows = [self._public(row) for row in collection(state, SOURCES).values()
                if row.get('created_by') == actor and row.get('status') in {'REVOKED', 'DELETED'}]
        return {'items': rows, 'total': len(rows), 'restoration_requires_review': True}

    def source_history(self, nid, scope, actor, rid):
        state = self.store.read(nid, scope)
        row = self._owned_source(nid, scope, actor, rid, state)
        # Current visibility never grants access to older private revisions.
        return {'items': [self._public(value) for value in [*row.get('history', []), snapshot(row)]],
                'current_version': row['version'], 'restore_creates_new_version': True}

    def historical_original(self, nid, scope, actor, rid, version):
        state = self.store.read(nid, scope)
        row = self._owned_source(nid, scope, actor, rid, state)
        revision = next((item for item in [*row.get('history', []), snapshot(row)] if item['version'] == version), None)
        if not revision or not revision.get('content_base64'): raise FileNotFoundError(rid)
        return base64.b64decode(revision['content_base64']), revision['filename']

    def replace_file(self, nid, scope, actor, rid, value, *, guard):
        body = ReplaceFileIn.model_validate(value)
        guard()
        extraction = extract_document(body.filename, decode_base64(body.content_base64))
        with self.store.transaction(nid, scope) as state:
            guard()
            row = self._owned_source(nid, scope, actor, rid, state)
            if row['status'] != 'ACTIVE': raise ValueError('RESEARCH_SOURCE_INACTIVE')
            check_version(self._public(row), body.expected_version)
            values = {**body.model_dump(exclude={'expected_version'}), **extraction,
                      'origin': 'LOCAL_IMPORT', 'accessed_at': now()}
            self._change_source(state, row, actor, body.expected_version, values)
            self._invalidate(state, rid)
            guard()
            return self._public(row, True)

    def restore_source(self, nid, scope, actor, rid, value, *, guard):
        body = RestoreSourceIn.model_validate(value)
        with self.store.transaction(nid, scope) as state:
            guard()
            row = self._owned_source(nid, scope, actor, rid, state)
            check_version(self._public(row), body.expected_version)
            original = next((revision for revision in row.get('history', [])
                if revision['version'] == body.restore_version and revision['status'] == 'ACTIVE'), None)
            if original is None: raise ValueError('RESEARCH_ACTIVE_REVISION_REQUIRED')
            protected = {'id', 'novel_id', 'scope', 'version', 'history', 'created_by', 'created_at', 'updated_by', 'updated_at'}
            values = {k: copy.deepcopy(v) for k, v in original.items() if k not in protected}
            # Restoring historical access must never republish private content.
            values.update(access='PRIVATE', restored_from_version=body.restore_version)
            self._change_source(state, row, actor, body.expected_version, values)
            self._invalidate(state, rid)
            guard()
            return self._public(row, True)

    @staticmethod
    def _invalidate(state, rid):
        # Native derived caches are erased atomically. Notes/drafts keep the
        # author's work but cannot be returned or reused without current proof.
        for name in ('research_index', 'research_contexts', 'research_summaries', 'research_vectors'):
            rows = collection(state, name)
            for key in list(rows):
                if rid in rows[key].get('source_ids', []): del rows[key]
        # Real vectors share the original embedding authority, including in-flight
        # builds: source revision invalidates the execution token atomically.
        for row in collection(state, 'embedding_indexes').values():
            if row.get('status') == 'REMOVED': continue
            if any(ref.get('entity_type') == 'RESEARCH' and ref.get('entity_id') == rid for ref in row.get('entities', [])):
                change_row(row, 'research-source-invalidation', row['version'], lambda target: target.update(
                    status='INVALIDATED', execution_token=None, error_code='EMBEDDING_RESEARCH_SOURCE_CHANGED'))
                for vector in collection(state, 'embedding_vectors').values():
                    if vector.get('index_id') == row['id']: vector.update(status='INVALIDATED', vector=[])
        for job in collection(state, 'research_analysis_jobs').values():
            if job.get('request', {}).get('source_id') == rid:
                from .review_adapter_jobs import invalidate_receipt
                invalidate_receipt(job)
        for name in (NOTES, 'world_records'):
            for row in collection(state, name).values():
                refs = row.get('citations', row.get('research_sources', []))
                if any(ref['source_id'] == rid for ref in refs): row['research_stale'] = True

    def transition_source(self, nid, scope, actor, rid, expected_version, action, *, guard):
        if action not in {'revoke', 'delete'}: raise ValueError('invalid source action')
        with self.store.transaction(nid, scope) as state:
            guard()
            row = self._source(nid, scope, actor, rid, state)
            if row.get('origin') == 'LEGACY_LIVE': raise ValueError('RESEARCH_LEGACY_USE_EXISTING_EDITOR')
            if row['created_by'] != actor: raise FileNotFoundError(rid)
            check_version(self._public(row), expected_version)
            target = require_row(state, SOURCES, rid)
            self._change_source(state, target, actor, expected_version, {'status': 'REVOKED' if action == 'revoke' else 'DELETED'})
            self._invalidate(state, rid)
            guard()
            return {'id': rid, 'version': target['version'], 'status': target['status'], 'derived_context_invalidated': True}

    @staticmethod
    def _cite(row, paragraph):
        return {'source_id': row['id'], 'source_version': row['version'], 'paragraph': paragraph['paragraph'],
                'quote_sha256': hashlib.sha256(paragraph['text'].encode()).hexdigest()}

    @staticmethod
    def _page_cite(row, page):
        return {'source_id': row['id'], 'source_version': row['version'], 'paragraph': 0, 'page': page, 'quote_sha256': row['content_sha256']}

    def resolve(self, nid, scope, actor, value, state=None):
        ref = CitationIn.model_validate(value).model_dump(exclude_none=True)
        row = self._source(nid, scope, actor, ref['source_id'], state)
        if row['version'] != ref['source_version']: raise StaleSourceError('RESEARCH_SOURCE_VERSION_CHANGED')
        if ref['paragraph'] == 0:
            if ref['page'] not in row.get('unread_pages', []) or self._page_cite(row, ref['page']) != ref:
                raise StaleSourceError('RESEARCH_PAGE_CITATION_CHANGED')
            return {'citation': ref, 'title': row['title'], 'author': row.get('author', ''), 'source': row.get('source', ''),
                    'page': ref['page'], 'paragraph': 0, 'text': '', 'layer': 'RESEARCH', 'not_understood': True,
                    'warning': 'Page reference only; OCR and visual understanding are not configured.'}
        paragraph = next((p for p in row['paragraphs'] if p['paragraph'] == ref['paragraph']), None)
        if paragraph is None or self._cite(row, paragraph) != ref: raise StaleSourceError('RESEARCH_CITATION_CHANGED')
        return self._evidence(row, paragraph)

    @staticmethod
    def _evidence(row, paragraph):
        return {'citation': ResearchLibraryService._cite(row, paragraph), 'title': row['title'], 'author': row.get('author', ''), 'source': row.get('source', ''),
                'page': paragraph['page'], 'paragraph': paragraph['paragraph'], 'text': paragraph['text'],
                'accessed_at': row.get('accessed_at'), 'imported_at': row.get('created_at'), 'source_digest': row.get('content_sha256'), 'source_version_label': row.get('source_version', ''), 'layer': 'RESEARCH'}

    def search(self, nid, scope, actor, query, limit=30):
        if not query.strip() or len(query) > 200 or not 1 <= limit <= 100: raise ValueError('RESEARCH_QUERY_INVALID')
        words = re.findall(r'\S+', query.casefold())
        items = []
        for row in self._sources(nid, scope, actor):
            for paragraph in row['paragraphs']:
                text = paragraph['text'].casefold()
                if all(word in text for word in words):
                    items.append(self._evidence(row, paragraph))
                    if len(items) >= limit: return {'items': items, 'limit': limit, 'method': 'LOCAL_LITERAL', 'truncated': True}
        return {'items': items, 'limit': limit, 'method': 'LOCAL_LITERAL', 'truncated': False}

    def _validate_refs(self, nid, scope, actor, refs, state=None):
        if not refs: raise ValueError('RESEARCH_CITATION_REQUIRED')
        return [self.resolve(nid, scope, actor, ref, state) for ref in refs]

    def context(self, nid, scope, actor, refs):
        evidence = self._validate_refs(nid, scope, actor, refs)
        return {'items': evidence, 'layer': 'RESEARCH', 'privacy_level': 'LOCAL_ONLY', 'untrusted_data': True,
                'instructions_allowed': False, 'automatic_injection': False, 'model_called': False}

    def create_note(self, nid, scope, actor, value, *, guard):
        payload = NoteIn.model_validate(value).model_dump(exclude_none=True)
        with self.store.transaction(nid, scope) as state:
            guard(); self._validate_refs(nid, scope, actor, payload['citations'], state)
            if len(collection(state, NOTES)) >= 1000: raise ValueError('RESEARCH_NOTE_LIMIT')
            row = new_row(nid, scope, actor, {**payload, 'status': 'ACTIVE', 'layer': 'RESEARCH_NOTE'})
            collection(state, NOTES)[row['id']] = row
            guard()
            return copy.deepcopy(row)

    def notes(self, nid, scope, actor):
        state = self.store.read(nid, scope)
        rows = []
        for row in collection(state, NOTES).values():
            if row['created_by'] != actor or row.get('status') != 'ACTIVE': continue
            try: evidence = self._validate_refs(nid, scope, actor, row['citations'], state)
            except (FileNotFoundError, StaleSourceError): continue
            rows.append({**{k: copy.deepcopy(v) for k, v in row.items() if k != 'history'}, 'evidence': evidence})
        return {'items': rows, 'total': len(rows)}

    def note_repairs(self, nid, scope, actor):
        self.novels.get(nid)
        state = self.store.read(nid, scope)
        rows = []
        for row in collection(state, NOTES).values():
            if row['created_by'] != actor or row['status'] != 'ACTIVE': continue
            try: self._validate_refs(nid, scope, actor, row['citations'], state)
            except StaleSourceError:
                # Only the author's own currently active sources permit draft
                # recovery. Revoked/private third-party citations stay hidden.
                sources = [collection(state, SOURCES).get(ref['source_id']) for ref in row['citations']]
                if sources and all(source and source['created_by'] == actor and source['status'] == 'ACTIVE' for source in sources):
                    rows.append({k: copy.deepcopy(row[k]) for k in ('id', 'version', 'title', 'text') } | {'status': 'CITATIONS_NEED_REVIEW', 'citations': []})
            except FileNotFoundError: continue
        return {'items': rows, 'automatic_rebind': False}

    def edit_note(self, nid, scope, actor, rid, value, *, guard):
        body = EditNoteIn.model_validate(value)
        with self.store.transaction(nid, scope) as state:
            guard()
            row = require_row(state, NOTES, rid)
            if row['created_by'] != actor or row['status'] != 'ACTIVE': raise FileNotFoundError(rid)
            # An unavailable old citation is not authorization to reveal its
            # source. Replacement references must all be currently visible.
            self._validate_refs(nid, scope, actor, body.model_dump()['citations'], state)
            check_version({k: v for k, v in row.items() if k != 'history'}, body.expected_version)
            if len(row.get('history', [])) >= 20: raise ValueError('RESEARCH_REVISION_LIMIT')
            change_row(row, actor, body.expected_version, lambda target: target.update(
                **body.model_dump(exclude={'expected_version'}, exclude_none=True), research_stale=False))
            guard()
            return {k: copy.deepcopy(v) for k, v in row.items() if k != 'history'}

    def delete_note(self, nid, scope, actor, rid, expected_version, *, guard):
        with self.store.transaction(nid, scope) as state:
            guard()
            row = require_row(state, NOTES, rid)
            if row['created_by'] != actor or row['status'] != 'ACTIVE': raise FileNotFoundError(rid)
            check_version({'id': rid, 'version': row['version']}, expected_version)
            change_row(row, actor, expected_version, lambda target: target.update(status='DELETED'))
            guard()
            return {'id': rid, 'version': row['version'], 'status': row['status']}

    def note_history(self, nid, scope, actor, rid):
        state = self.store.read(nid, scope)
        row = require_row(state, NOTES, rid)
        if row['created_by'] != actor: raise FileNotFoundError(rid)
        items = []
        for revision in [*row.get('history', []), snapshot(row)]:
            try: self._validate_refs(nid, scope, actor, revision['citations'], state)
            except (FileNotFoundError, StaleSourceError): continue
            items.append(copy.deepcopy(revision))
        return {'items': items, 'current_version': row['version'], 'unavailable_revisions_hidden': True}

    def adopt(self, nid, scope, actor, value, *, guard):
        body = AdoptIn.model_validate(value)
        if self.world is None: raise ValueError('RESEARCH_WORLD_NOT_CONFIGURED')
        refs = [ref.model_dump(exclude_none=True) for ref in body.citations]
        # A new author-written setting, never a verbatim adoption of a source.
        evidence = self._validate_refs(nid, scope, actor, refs)
        if any(body.original_setting.strip() == item['text'].strip() for item in evidence):
            raise ValueError('RESEARCH_ORIGINAL_SETTING_REQUIRED')
        payload = WorldRecordIn(kind='ABILITY', title=body.title, data={'name': body.title, 'description': body.original_setting})
        return self.world.create_research_draft(nid, scope, actor, payload, refs, guard=guard,
            validate=lambda state: self._validate_refs(nid, scope, actor, refs, state))

    def drafts(self, nid, scope, actor):
        state = self.store.read(nid, scope)
        rows = []
        for row in collection(state, 'world_records').values():
            if not row.get('research_sources') or row['created_by'] != actor: continue
            try: evidence = self._validate_refs(nid, scope, actor, row['research_sources'], state)
            except (FileNotFoundError, StaleSourceError): continue
            rows.append({**copy.deepcopy(row), 'evidence': evidence, 'layer': 'SETTING_DRAFT', 'canon_promotion_available': False})
        return {'items': rows, 'total': len(rows)}

    def review_draft(self, nid, scope, actor, rid, expected_version, action, *, guard):
        if action not in {'review', 'reopen'}: raise ValueError('RESEARCH_DRAFT_ACTION_INVALID')
        with self.store.transaction(nid, scope) as state:
            guard()
            row = require_row(state, 'world_records', rid)
            if not row.get('research_sources') or row['created_by'] != actor: raise FileNotFoundError(rid)
            self._validate_refs(nid, scope, actor, row['research_sources'], state)
            check_version(row, expected_version)
            if (action == 'review' and row['status'] != 'REVIEW') or (action == 'reopen' and row['status'] != 'RESEARCH_REVIEWED'):
                raise ValueError('RESEARCH_DRAFT_TRANSITION_INVALID')
            change_row(row, actor, expected_version, lambda target: target.update(
                status='RESEARCH_REVIEWED' if action == 'review' else 'REVIEW', canon_state='CANDIDATE'))
            guard()
            return {**copy.deepcopy(row), 'layer': 'SETTING_DRAFT', 'canon_promotion_available': False}

    def backrefs(self, nid, scope, actor, rid):
        self._source(nid, scope, actor, rid)
        result = []
        for kind, rows in [('NOTE', self.notes(nid, scope, actor)['items']), ('SETTING_DRAFT', self.drafts(nid, scope, actor)['items'])]:
            for row in rows:
                if any(ref['source_id'] == rid for ref in row.get('citations', row.get('research_sources', []))):
                    result.append({'kind': kind, 'id': row['id'], 'title': row['title'], 'version': row['version']})
        return {'items': result, 'total': len(result)}

    def analysis_status(self, nid, scope, actor):
        self.novels.get(nid)
        from .research_vision import ResearchVisionCapability
        capability = ResearchVisionCapability.model_validate(self.vision_provider.capability).model_dump() if self.vision_provider else None
        return {'status': 'CONFIGURED' if capability and capability['verification'] == 'MOCK_ONLY' and capability['local'] else 'NOT_CONFIGURED', 'capability': capability,
                'runtime_admission': 'NOT_CONFIGURED', 'durable_worker': False,
                'model_quality': 'NOT_RUN', 'automatic_canon': False, 'review_required': True,
                'operations': ['OCR', 'SCAN_PDF_VISION', 'IMAGE_UNDERSTANDING', 'CHART_UNDERSTANDING', 'TABLE_UNDERSTANDING']}

    def analysis_jobs(self, nid, scope, actor):
        from .research_vision import research_analysis_jobs
        return research_analysis_jobs(self).list(nid, scope, actor)

    def analysis_job(self, nid, scope, actor, rid):
        from .research_vision import research_analysis_jobs
        return research_analysis_jobs(self).get(nid, scope, actor, rid)

    def create_analysis(self, nid, scope, actor, value, *, guard):
        from .research_vision import ResearchAnalysisIn, research_analysis_jobs
        return research_analysis_jobs(self).create(nid, scope, actor, ResearchAnalysisIn.model_validate(value).model_dump(), guard)

    def analysis_action(self, nid, scope, actor, rid, action, expected_version, *, guard):
        from .research_vision import research_analysis_jobs
        return research_analysis_jobs(self).action(nid, scope, actor, rid, action, expected_version, guard)
