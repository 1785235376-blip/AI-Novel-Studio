"""The one branch manuscript owner, inside the existing scope transaction.

Mainline ChapterRepository remains authoritative for local manuscripts. A
collaboration branch starts empty and only an explicit fork copies a source.
No lookup by chapter number, implicit parent fallback or mainline alias exists.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from uuid import UUID, uuid4

from ..document import document_to_markdown, markdown_to_document
from ..experimental.common import now
from ..experimental.store import canonical
from ..revision_constraints import preserve_revision_constraints
from .chapter_repository import VersionConflict

COLLECTION = 'branch_manuscripts'
OWNER = 'BRANCH_MANUSCRIPT_V1'
MAX_DOCUMENT_BYTES = 2_000_000
MAX_CHAPTER_IDENTITIES = 2000  # Includes tombstones; identities are never recycled.
MAX_HISTORY_PER_CHAPTER = 500
MAX_OPERATION_RECEIPTS = 5000
MAX_AUDIT_ENTRIES = 20000
MAX_MANUSCRIPT_BYTES = 64 * 1024 * 1024
RECOVERY_RESERVE_BYTES = 4 * 1024 * 1024
RECOVERY_HISTORY_RESERVE = 20


def is_branch_chapter_id(novel_id, chapter_id):
    """Recognize only this project's canonical, disjoint branch UUID token."""
    if not isinstance(novel_id, str) or not novel_id or not isinstance(chapter_id, str): return False
    prefix = novel_id + ':~b'
    if not chapter_id.startswith(prefix): return False
    token = chapter_id[len(prefix):]
    try: return str(UUID(token)) == token
    except (ValueError, AttributeError): return False


def document_digest(document):
    return sha256(canonical(document).encode()).hexdigest()


def validated_document(document):
    value = deepcopy(document)
    if not isinstance(value, dict) or value.get('type') != 'doc':
        raise ValueError('BRANCH_RICH_DOCUMENT_REQUIRED')
    if len(canonical(value).encode()) > MAX_DOCUMENT_BYTES:
        raise ValueError('BRANCH_DOCUMENT_LIMIT')
    document_to_markdown(value)  # Validate, never round-trip through Markdown.
    return value


def branch_scope(scope):
    if not isinstance(scope, dict) or scope.get('mode') != 'collaboration':
        raise ValueError('BRANCH_SCOPE_REQUIRED')
    keys = ('novel_id', 'workspace_id', 'storyline_id', 'branch_id')
    if any(not isinstance(scope.get(key), str) or not scope[key] for key in keys):
        raise ValueError('BRANCH_SCOPE_REQUIRED')
    if set(scope) != {'mode', *keys}:
        raise ValueError('BRANCH_SCOPE_INVALID')
    return deepcopy(scope)


class BranchManuscriptRepository:
    """Scope-bound repository over File atomic replace / PostgreSQL row lock.

    In-document writes are exposed only for other owners already holding this
    exact ExperimentalStore transaction (realtime and offline reconciliation).
    The same manuscript, versions and operation receipts are used in both paths.
    """
    def __init__(self, store, scope):
        self.store, self.scope = store, branch_scope(scope)
        self.nid = scope['novel_id']

    def _state(self, state):
        self.store.validate(state, self.nid, self.scope)
        row = state['collections'].get(COLLECTION, {}).get(self.scope['branch_id'])
        if row is None:
            return {'owner': OWNER, 'scope': deepcopy(self.scope), 'revision': 0,
                    'next_number': 1, 'chapters': {}, 'receipts': {}, 'audit': []}
        if row.get('owner') != OWNER or row.get('scope') != self.scope:
            raise ValueError('BRANCH_MANUSCRIPT_OWNER_MISMATCH')
        numbers = set()
        for cid, chapter in row.get('chapters', {}).items():
            if (not isinstance(chapter, dict) or chapter.get('id') != cid
                    or not is_branch_chapter_id(self.nid, cid) or chapter.get('scope') != self.scope
                    or chapter.get('novel_id') != self.nid or chapter.get('branch_id') != self.scope['branch_id']
                    or type(chapter.get('version')) is not int or chapter['version'] < 1
                    or type(chapter.get('number')) is not int or chapter['number'] < 1
                    or chapter['number'] in numbers or chapter.get('authority') != OWNER):
                raise ValueError('BRANCH_MANUSCRIPT_IDENTITY_CORRUPT')
            numbers.add(chapter['number'])
            history = chapter.get('history')
            if (not isinstance(history, list) or any(not isinstance(h, dict) or h.get('scope') != self.scope
                    or type(h.get('version')) is not int or not 1 <= h['version'] < chapter['version'] for h in history)
                    or len({h['version'] for h in history}) != len(history)):
                raise ValueError('BRANCH_MANUSCRIPT_HISTORY_CORRUPT')
        if type(row.get('next_number')) is not int or row['next_number'] <= max(numbers, default=0):
            raise ValueError('BRANCH_MANUSCRIPT_ALLOCATION_CORRUPT')
        if any(receipt.get('scope') != self.scope or receipt.get('operation_id') != key
               for key, receipt in row.get('receipts', {}).items()):
            raise ValueError('BRANCH_MANUSCRIPT_RECEIPT_CORRUPT')
        return deepcopy(row)

    def _put(self, state, manuscript):
        state['collections'].setdefault(COLLECTION, {})[self.scope['branch_id']] = manuscript

    def manifest(self):
        row = self._state(self.store.read(self.nid, self.scope))
        return {'owner': OWNER, 'scope': deepcopy(self.scope), 'revision': row['revision'],
                'chapter_count': sum(not c.get('deleted') for c in row['chapters'].values()),
                'tombstone_count': sum(bool(c.get('deleted')) for c in row['chapters'].values()),
                'initialized': row['revision'] > 0, 'mainline_fallback': False,
                'capacity': {'used_bytes': len(canonical(row).encode()),
                             'max_bytes': MAX_MANUSCRIPT_BYTES, 'normal_write_max_bytes': MAX_MANUSCRIPT_BYTES - RECOVERY_RESERVE_BYTES,
                             'max_chapter_identities': MAX_CHAPTER_IDENTITIES,
                             'max_history_per_chapter': MAX_HISTORY_PER_CHAPTER,
                             'recovery_history_reserve': RECOVERY_HISTORY_RESERVE,
                             'max_operation_receipts': MAX_OPERATION_RECEIPTS,
                             'max_audit_entries': MAX_AUDIT_ENTRIES, 'automatic_pruning': False}}

    def _chapter(self, manuscript, cid, include_deleted=False):
        chapter = manuscript['chapters'].get(cid)
        if (chapter is None or chapter.get('id') != cid or chapter.get('scope') != self.scope
                or chapter.get('novel_id') != self.nid or chapter.get('branch_id') != self.scope['branch_id']
                or chapter.get('deleted') and not include_deleted):
            raise FileNotFoundError(cid)
        return chapter

    @staticmethod
    def external(chapter):
        return deepcopy({k: v for k, v in chapter.items() if k not in {'history', 'base_document'}})

    def list(self, nid, *, archived=False):
        if nid != self.nid: raise FileNotFoundError(nid)
        row = self._state(self.store.read(self.nid, self.scope))
        return [self.external(c) for c in sorted(row['chapters'].values(), key=lambda c: (c['sort_order'], c['number']))
                if not c.get('deleted') and bool(c.get('is_archived')) == archived]

    def list_archived(self, nid): return self.list(nid, archived=True)

    def get(self, cid):
        return self.external(self._chapter(self._state(self.store.read(self.nid, self.scope)), cid))

    def history(self, cid):
        chapter = self._chapter(self._state(self.store.read(self.nid, self.scope)), cid)
        return deepcopy(list(reversed(chapter['history'])))

    def lineage(self, cid):
        chapter = self._chapter(self._state(self.store.read(self.nid, self.scope)), cid)
        return deepcopy({'origin': chapter.get('origin'), 'base_document': chapter.get('base_document')})

    @staticmethod
    def _cas(chapter, expected):
        if type(expected) is not int or expected < 1: raise ValueError('BRANCH_EXPECTED_VERSION_REQUIRED')
        if chapter['version'] != expected:
            raise VersionConflict(BranchManuscriptRepository.external(chapter),
                                  resource_id=chapter['id'], expected_version=expected)

    @staticmethod
    def _checkpoint(chapter, actor, source):
        limit = MAX_HISTORY_PER_CHAPTER + (RECOVERY_HISTORY_RESERVE if source in {'RESTORE', 'RESTORE_ARCHIVE'} else 0)
        if len(chapter['history']) >= limit: raise ValueError('BRANCH_CAPACITY_HISTORY_REVIEW_REQUIRED')
        chapter['history'].append({'version': chapter['version'], 'document': deepcopy(chapter['document']),
            'title': chapter['title'], 'is_archived': chapter['is_archived'], 'source': source,
            'operator': actor, 'actor_id': actor, 'timestamp': chapter['updated_at'], 'reason': source,
            'scope': deepcopy(chapter['scope'])})

    def _write(self, operation, check=None, state=None, *, recovery=False):
        check = check or (lambda: None)
        def apply(doc):
            check()
            manuscript = self._state(doc)
            result = operation(manuscript)
            limit = MAX_MANUSCRIPT_BYTES if recovery else MAX_MANUSCRIPT_BYTES - RECOVERY_RESERVE_BYTES
            if (len(canonical(manuscript).encode()) > limit or len(manuscript['receipts']) > MAX_OPERATION_RECEIPTS
                    or len(manuscript['audit']) > MAX_AUDIT_ENTRIES):
                raise ValueError('BRANCH_CAPACITY_REVIEW_REQUIRED')
            check()  # Revoke / feature OFF before the authority changes.
            self._put(doc, manuscript)
            return deepcopy(result)
        if state is not None: return apply(state)
        with self.store.transaction(self.nid, self.scope) as doc:
            return apply(doc)

    def create(self, nid, payload, actor='local-author', *, check=None, state=None, origin=None):
        if nid != self.nid: raise FileNotFoundError(nid)
        title = payload.get('title', 'Untitled chapter')
        if not isinstance(title, str) or not title or len(title) > 300: raise ValueError('BRANCH_TITLE_INVALID')
        document = validated_document(payload['document'] if 'document' in payload else
            markdown_to_document(f"# {title}\n\n{payload.get('content', '')}"))
        def add(manuscript):
            if len(manuscript['chapters']) >= MAX_CHAPTER_IDENTITIES: raise ValueError('BRANCH_CHAPTER_LIMIT')
            cid = self.nid + ':~b' + str(uuid4())
            if cid in manuscript['chapters']: raise ValueError('BRANCH_IDENTITY_COLLISION')
            number = manuscript['next_number']; manuscript['next_number'] += 1
            stamp = now(); content = document_to_markdown(document)
            row = {'id': cid, 'novel_id': self.nid, 'scope': deepcopy(self.scope),
                   'branch_id': self.scope['branch_id'], 'authority': OWNER, 'number': number,
                   'sort_order': max((c['sort_order'] for c in manuscript['chapters'].values()), default=0) + 1,
                   'title': title, 'volume': 1, 'version': 1, 'document': document,
                   'document_digest': document_digest(document), 'content': content,
                   'word_count': len(''.join(content.split())), 'status': 'Draft', 'privacy_status': 'UNREVIEWED',
                   'is_archived': False, 'deleted': False, 'created_at': stamp, 'updated_at': stamp,
                   'created_by': actor, 'updated_by': actor, 'history': []}
            if origin:
                row['origin'] = deepcopy({k: v for k, v in origin.items() if k != 'document'})
                row['base_document'] = validated_document(origin['document'])
            manuscript['chapters'][cid] = row
            manuscript['revision'] += 1
            manuscript['audit'].append({'action': 'CHAPTER_CREATED', 'chapter_id': cid, 'actor_id': actor,
                                        'version': 1, 'timestamp': stamp})
            return self.external(row)
        return self._write(add, check, state)

    def save(self, cid, document, expected_version, source='MANUAL_SAVE', actor='local-author', *,
             operation_id=None, check=None, state=None):
        document = validated_document(document)
        if operation_id is not None and (not isinstance(operation_id, str) or not 1 <= len(operation_id) <= 200):
            raise ValueError('BRANCH_OPERATION_ID_INVALID')
        request = document_digest({'chapter_id': cid, 'expected_version': expected_version,
                                   'document': document, 'source': source, 'actor_id': actor})
        def update(manuscript):
            if operation_id and operation_id in manuscript['receipts']:
                receipt = manuscript['receipts'][operation_id]
                if receipt['request_digest'] != request: raise ValueError('BRANCH_OPERATION_REUSED')
                return receipt
            row = self._chapter(manuscript, cid); self._cas(row, expected_version)
            if row['is_archived']: raise ValueError('BRANCH_CHAPTER_ARCHIVED')
            prepared = preserve_revision_constraints(row['document'], document, source)
            content = document_to_markdown(prepared)
            self._checkpoint(row, actor, source)
            title = row['title']
            if prepared.get('content') and prepared['content'][0].get('type') == 'heading':
                title = ''.join(n.get('text', '') for n in prepared['content'][0].get('content', []))
            row.update(document=prepared, content=content, document_digest=document_digest(prepared),
                       title=title, word_count=len(''.join(content.split())), version=row['version'] + 1,
                       updated_at=now(), updated_by=actor)
            manuscript['revision'] += 1
            receipt = {'operation_id': operation_id, 'chapter_id': cid, 'before_version': expected_version,
                       'after_version': row['version'], 'document_digest': row['document_digest'],
                       'request_digest': request, 'chapter': self.external(row), 'scope': deepcopy(self.scope)}
            if operation_id: manuscript['receipts'][operation_id] = deepcopy(receipt)
            manuscript['audit'].append({'action': 'CHAPTER_SAVED', 'chapter_id': cid, 'actor_id': actor,
                'version': row['version'], 'source': source, 'operation_id': operation_id, 'timestamp': row['updated_at']})
            return receipt if operation_id else self.external(row)
        return self._write(update, check, state, recovery=source == 'RESTORE')

    def receipt(self, operation_id):
        row = self._state(self.store.read(self.nid, self.scope))['receipts'].get(operation_id)
        if row is None: raise FileNotFoundError(operation_id)
        return deepcopy(row)

    def restore(self, cid, version, expected_version, actor='local-author', *, check=None):
        def restore_in_state(state):
            chapter = self._chapter(self._state(state), cid)
            snapshot = next((h for h in chapter['history'] if h['version'] == version), None)
            if snapshot is None: raise FileNotFoundError(version)
            return self.save(cid, snapshot['document'], expected_version, 'RESTORE', actor, check=check, state=state)
        with self.store.transaction(self.nid, self.scope) as state:
            return restore_in_state(state)

    def set_archived(self, cid, archived, expected_version, actor='local-author', *, check=None):
        def update(manuscript):
            row = self._chapter(manuscript, cid); self._cas(row, expected_version)
            if row['is_archived'] != archived:
                self._checkpoint(row, actor, 'ARCHIVE' if archived else 'RESTORE_ARCHIVE')
                row.update(is_archived=archived, version=row['version'] + 1, updated_at=now(), updated_by=actor)
                manuscript['revision'] += 1
            return self.external(row)
        return self._write(update, check, recovery=not archived)

    def delete(self, cid, expected_version, actor='local-author', *, check=None):
        def remove(manuscript):
            row = self._chapter(manuscript, cid); self._cas(row, expected_version)
            if not row['is_archived']: raise ValueError('BRANCH_ARCHIVE_REQUIRED')
            self._checkpoint(row, actor, 'DELETE')
            row.update(deleted=True, version=row['version'] + 1, updated_at=now(), updated_by=actor)
            manuscript['revision'] += 1
            return {'id': cid, 'version': row['version'], 'state': 'DELETED', 'identity_reusable': False}
        return self._write(remove, check)

    def move(self, cid, direction, expected_revision, *, check=None):
        if direction not in {'up', 'down'}: raise ValueError('BRANCH_MOVE_INVALID')
        def move(manuscript):
            if manuscript['revision'] != expected_revision:
                raise VersionConflict({'id': self.scope['branch_id'], 'version': manuscript['revision']}, expected_version=expected_revision)
            self._chapter(manuscript, cid)
            order = sorted((c for c in manuscript['chapters'].values() if not c['deleted']), key=lambda c: c['sort_order'])
            index = next(i for i, c in enumerate(order) if c['id'] == cid)
            other = index + (-1 if direction == 'up' else 1)
            if 0 <= other < len(order):
                order[index], order[other] = order[other], order[index]
                for i, chapter in enumerate(order, 1): chapter['sort_order'] = i
                manuscript['revision'] += 1
            return {'revision': manuscript['revision'], 'order': [c['id'] for c in order]}
        return self._write(move, check)
