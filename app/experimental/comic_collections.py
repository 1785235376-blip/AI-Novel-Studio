"""Bounded, manual book structure over the original Comic page owner.

Structure snapshots retain membership only. Pages, source bindings, approval,
assets and per-page content history remain owned by comic_layouts_v2.
"""
from __future__ import annotations
import copy
from typing import Annotated
from pydantic import Field, model_validator
from .common import new_id, new_row, change_row, check_version
from .media import StrictModel
from .store import canonical


class ComicChapterIn(StrictModel):
    id: str = Field(pattern=r'^[A-Za-z0-9_-]{1,80}$')
    title: str = Field(min_length=1, max_length=240)
    pages: list[str] = Field(default_factory=list, max_length=100)


class ComicBookIn(StrictModel):
    title: str = Field(min_length=1, max_length=240)
    chapters: list[ComicChapterIn] = Field(default_factory=list, max_length=20)
    expected_page_versions: dict[str, Annotated[int, Field(ge=1, strict=True)]] = Field(default_factory=dict, max_length=100)

    @model_validator(mode='after')
    def bounded(self):
        pages = [p for c in self.chapters for p in c.pages]
        if len(pages) > 100 or len(set(pages)) != len(pages):
            raise ValueError('COMIC_BOOK_PAGE_LIMIT_OR_DUPLICATE')
        if len({c.id for c in self.chapters}) != len(self.chapters):
            raise ValueError('COMIC_BOOK_DUPLICATE_CHAPTER')
        if any(not isinstance(p, str) or not 1 <= len(p) <= 80 for p in pages):
            raise ValueError('COMIC_BOOK_PAGE_ID_INVALID')
        if any(not 1 <= len(k) <= 80 or type(v) is not int or v < 1 for k, v in self.expected_page_versions.items()):
            raise ValueError('COMIC_BOOK_PAGE_VERSION_INVALID')
        if set(self.expected_page_versions) - set(pages):
            raise ValueError('COMIC_BOOK_UNREFERENCED_PAGE_VERSION')
        for title in [self.title, *(c.title for c in self.chapters)]:
            if not title.strip() or any(ord(c) < 32 or 0xD800 <= ord(c) <= 0xDFFF for c in title):
                raise ValueError('COMIC_BOOK_PLAIN_TITLE_REQUIRED')
        return self


class ComicBookEdit(ComicBookIn):
    expected_version: int = Field(ge=1, strict=True)


class ComicBookPageIn(StrictModel):
    expected_version: int = Field(ge=1, strict=True)
    chapter_id: str = Field(pattern=r'^[A-Za-z0-9_-]{1,80}$')
    source_layout_id: str | None = Field(default=None, min_length=1, max_length=80)
    expected_source_version: int | None = Field(default=None, ge=1, strict=True)

    @model_validator(mode='after')
    def paired(self):
        if (self.source_layout_id is None) != (self.expected_source_version is None):
            raise ValueError('COMIC_BOOK_COPY_VERSION_REQUIRED')
        return self


class ComicCollectionsMixin:
    # A subordinate collection in the SAME scope document, never a new store or
    # CreativeProjectStore registry. Raw scope commit is atomic with page rows.
    BOOKS = 'comic_page_collections_v1'

    def _book_identity(self, nid, row):
        if not row.get('project_incarnation') or row['project_incarnation'] != self._independent_identity(nid):
            raise FileNotFoundError('comic book owner unavailable')

    def _book_row(self, nid, scope, actor, rid, state=None):
        row = (state['collections'].get(self.BOOKS, {}).get(rid) if state is not None
               else self.get(nid, scope, self.BOOKS, rid))
        if row is None or row.get('novel_id') != nid or row.get('scope') != scope or row.get('created_by') != actor:
            raise FileNotFoundError('comic book unavailable')
        self._book_identity(nid, row)
        if self._source_free_access.get():
            for snapshot in [row, *row.get('history', [])]:
                for pid in self._book_pages(snapshot['document']):
                    self._book_page(nid, scope, actor, pid, state)
        return row

    def _book_page(self, nid, scope, actor, rid, state=None):
        row = (state['collections'].get(self.RECORDS, {}).get(rid) if state is not None
               else self._row(nid, scope, actor, rid))
        if (row is None or row.get('novel_id') != nid or row.get('scope') != scope
                or row.get('created_by') != actor or not self._independent(row)):
            raise FileNotFoundError('comic page unavailable')
        self._check_independent_identity(nid, row)
        self._current(nid, scope, actor, row)
        return row

    @staticmethod
    def _book_pages(document):
        return [p for c in document['chapters'] for p in c['pages']]

    def _book_view(self, nid, scope, actor, row, state):
        safe = {k: row[k] for k in ('id', 'version', 'status')}
        try:
            self._book_identity(nid, row)
            for rid in self._book_pages(row['document']):
                self._book_page(nid, scope, actor, rid, state)
            self._book_identity(nid, row)
        except (FileNotFoundError, ValueError):
            # No private page count, chapter titles, references or history IDs.
            return {**safe, 'stale': True}
        return {**safe, 'stale': False, **copy.deepcopy(row['document']),
                'history_versions': [h['version'] for h in row['history']],
                'snapshot_scope': 'STRUCTURE_ONLY', 'automatic_generation': False}

    def books(self, nid, scope, actor):
        # Avoid opening a write-capable raw transaction for a missing scope. Once
        # records exist, projection reuses the original locks without changing it.
        if not self.list(nid, scope, self.BOOKS): return {'items': []}
        items = []
        try:
            with self._independent_transaction(nid, scope) as state:
                for rid in state['collections'].get(self.BOOKS, {}):
                    try: row = self._book_row(nid, scope, actor, rid, state)
                    except (FileNotFoundError, ValueError): continue
                    items.append(self._book_view(nid, scope, actor, row, state))
        except (FileNotFoundError, ValueError):
            # No marker creation, epoch ID leak, or old-owner count on reads.
            return {'items': []}
        return {'items': items}

    def _book_owner_rows(self, nid, actor, state):
        identity = self._independent_identity(nid)
        return {rid: row for rid, row in state['collections'].get(self.BOOKS, {}).items()
                if row.get('created_by') == actor and row.get('project_incarnation') == identity}

    def _book_bound(self, nid, actor, state, row=None):
        if row is not None and len(row['history']) >= 100:
            raise ValueError('COMIC_BOOK_REVISION_LIMIT')
        # Retained previous owners and other actors do not consume this author's
        # logical quota. Their archived bytes are never rewritten or removed.
        if len(canonical(self._book_owner_rows(nid, actor, state)).encode('utf-8')) > 8_000_000:
            raise ValueError('COMIC_BOOK_STORAGE_LIMIT')

    def save_book(self, nid, scope, actor, value, guard=lambda: None, rid=None, expected_version=None):
        body = ComicBookIn.model_validate(value)
        document = body.model_dump(exclude={'expected_page_versions'})
        # Validate attached pages and pins BEFORE an explicit create can provision
        # the original marker. No observational or invalid-create identity writes.
        for pid in self._book_pages(document):
            page = self._book_page(nid, scope, actor, pid)
            if pid not in body.expected_page_versions: raise ValueError('COMIC_BOOK_PAGE_VERSION_REQUIRED')
            check_version(page, body.expected_page_versions[pid])
        if rid: self._book_row(nid, scope, actor, rid)
        guard()
        with self._independent_transaction(nid, scope, create=rid is None) as state:
            guard()
            current = self._book_row(nid, scope, actor, rid, state) if rid else None
            if current is not None:
                check_version(current, expected_version); self._book_bound(nid, actor, state, current)
            elif len(self._book_owner_rows(nid, actor, state)) >= 20:
                raise ValueError('COMIC_BOOK_COUNT_LIMIT')
            for pid in self._book_pages(document):
                page = self._book_page(nid, scope, actor, pid, state)
                check_version(page, body.expected_page_versions[pid])
            payload = {'document': document, 'project_incarnation': self._independent_identity(nid),
                       'status': 'DRAFT', 'snapshot_scope': 'STRUCTURE_ONLY'}
            if current is None:
                saved = new_row(nid, scope, actor, payload)
                state['collections'].setdefault(self.BOOKS, {})[saved['id']] = saved
            else:
                saved = change_row(current, actor, expected_version, lambda row: row.update(payload))
            self._book_bound(nid, actor, state)
            result = self._book_view(nid, scope, actor, saved, state); guard()
        return result

    def book_page(self, nid, scope, actor, rid, value, guard=lambda: None):
        body = ComicBookPageIn.model_validate(value)
        self._book_row(nid, scope, actor, rid); guard()
        with self._independent_transaction(nid, scope) as state:
            guard(); book = self._book_row(nid, scope, actor, rid, state)
            check_version(book, body.expected_version); self._book_bound(nid, actor, state, book)
            document = copy.deepcopy(book['document'])
            chapter = next((c for c in document['chapters'] if c['id'] == body.chapter_id), None)
            if chapter is None: raise FileNotFoundError('comic chapter unavailable')
            if len(self._book_pages(document)) >= 100: raise ValueError('COMIC_BOOK_PAGE_LIMIT')
            # Validate entire resulting structure, not merely the newly selected
            # page. Mutations never make a stale/unauthorized subtree look current.
            for pid in self._book_pages(document): self._book_page(nid, scope, actor, pid, state)
            if body.source_layout_id:
                source = self._book_page(nid, scope, actor, body.source_layout_id, state)
                check_version(source, body.expected_source_version)
                page_document = copy.deepcopy(source['document'])
                remap = {}
                for panel in page_document['panels']:
                    old_id = panel['id']; panel['id'] = new_id(); remap[('PANEL', old_id)] = panel['id']
                    for bubble in panel['bubbles']:
                        old_id = bubble['id']; bubble['id'] = new_id(); remap[('BUBBLE', old_id)] = bubble['id']
                for item in page_document.get('layer_stack', {}).get('items', []):
                    item['id'] = 'layer_' + new_id()
                    if item['kind'] != 'RASTER':
                        item['target_id'] = remap[(item['kind'].split('_')[0], item['target_id'])]
            else:
                page_document = {'title': '空白漫画页', 'source_mode': 'INDEPENDENT', 'panels': []}
            payload = self._payload(nid, scope, actor, page_document)
            self._current(nid, scope, actor, payload)
            page = new_row(nid, scope, actor, payload)
            state['collections'].setdefault(self.RECORDS, {})[page['id']] = page
            chapter['pages'].append(page['id'])
            change_row(book, actor, body.expected_version, lambda row: row.update(document=document))
            self._book_bound(nid, actor, state)
            result = {'book': self._book_view(nid, scope, actor, book, state), 'page': self._view(nid, scope, actor, page)}
            guard()
        return result

    def restore_book(self, nid, scope, actor, rid, expected_version, target_version, guard=lambda: None):
        self._book_row(nid, scope, actor, rid); guard()
        with self._independent_transaction(nid, scope) as state:
            guard(); book = self._book_row(nid, scope, actor, rid, state)
            check_version(book, expected_version); self._book_bound(nid, actor, state, book)
            target = next((h for h in book['history'] if h['version'] == target_version), None)
            if target is None: raise FileNotFoundError('comic book revision unavailable')
            self._book_identity(nid, target)
            # Historical membership references CURRENT pages; never roll back page
            # contents or approval, nor expose old/private source information.
            document = ComicBookIn.model_validate(target['document']).model_dump(exclude={'expected_page_versions'})
            for pid in self._book_pages(document): self._book_page(nid, scope, actor, pid, state)
            change_row(book, actor, expected_version, lambda row: row.update(document=document))
            self._book_bound(nid, actor, state)
            result = self._book_view(nid, scope, actor, book, state); guard()
        return result
