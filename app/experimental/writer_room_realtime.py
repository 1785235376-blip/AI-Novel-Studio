"""Writer-room realtime engineering adapter, not a deployed co-editing server.

Synthetic push is actual in-process subscription delivery. HTTP reads are only
snapshots. The existing chapter owner remains authoritative; branch commits can
share the existing scope transaction, while mainline writes use conservative
CLAIMED/UNKNOWN recovery and are never automatically replayed.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from threading import RLock
from time import time
from typing import Callable, Literal, Protocol
from uuid import uuid4

from fastapi import HTTPException
from pydantic import Field, model_validator

from ..revision_constraints import assert_ai_locks
from .common import check_version, new_row, StaleSourceError
from .planning import digest
from .project_forks import advance
from .offline_sync import SyncInput
from .reader_sources import authorized_chapter_rows
from .store import canonical

FEATURE = 'realtime_collaboration_v1'
MAX_PARTICIPANTS = 100
MAX_OPERATIONS = 200
MAX_SCOPE_BYTES = 8 * 1024 * 1024
LEASE_SECONDS = 60
SHA = r'^[a-f0-9]{64}$'
ID = r'^[A-Za-z0-9][A-Za-z0-9_.:~\-]{0,239}$'


class JoinIn(SyncInput):
    device_id: str = Field(pattern=ID)
    chapter_id: str = Field(pattern=ID)
    document_version: int = Field(ge=1)


class ParticipantActionIn(SyncInput):
    expected_version: int = Field(ge=1)
    action: Literal['heartbeat', 'disconnect', 'reconnect', 'leave', 'revoke']
    document_version: int | None = Field(default=None, ge=1)


class Position(SyncInput):
    # Indexes through successive rich-document `content` arrays; offsets are
    # Unicode code points, not UTF-16 code units or ambiguous flat text offsets.
    path: list[int] = Field(min_length=1, max_length=30)
    offset: int = Field(ge=0, le=512000)

    @model_validator(mode='after')
    def nonnegative_path(self):
        if any(i < 0 for i in self.path): raise ValueError('negative document path')
        return self


class CursorIn(SyncInput):
    expected_version: int = Field(ge=1)
    document_version: int = Field(ge=1)
    anchor: Position
    focus: Position


class TextEdit(SyncInput):
    path: list[int] = Field(min_length=1, max_length=30)
    start: int = Field(ge=0, le=512000)
    end: int = Field(ge=0, le=512000)
    text: str = Field(max_length=64000)

    @model_validator(mode='after')
    def valid_range(self):
        if self.end < self.start or any(i < 0 for i in self.path): raise ValueError('invalid edit range')
        return self


class EditIn(SyncInput):
    participant_id: str = Field(pattern=ID)
    participant_version: int = Field(ge=1)
    request_id: str = Field(pattern=ID)
    document_version: int = Field(ge=1)
    document_digest: str = Field(pattern=SHA)
    edits: list[TextEdit] = Field(min_length=1, max_length=64)


class OperationIn(SyncInput):
    expected_version: int = Field(ge=1)
    action: Literal['apply', 'cancel', 'inspect_recovery', 'adopt', 'close_without_replay']
    recovery_digest: str | None = Field(default=None, pattern=SHA)


class DocumentAdapter(Protocol):
    """Only an authoritative owner can implement this interface."""
    atomic_scope: bool
    def read(self, ctx, chapter_id: str) -> dict: ...
    def commit(self, ctx, chapter_id: str, expected_version: int, document: dict,
               operation_id: str, check: Callable, state: dict | None = None) -> dict: ...


class MainlineDocumentAdapter:
    atomic_scope = False

    def __init__(self, owner): self.owner = owner

    def read(self, ctx, chapter_id):
        if ctx.scope != {'mode': 'local', 'novel_id': ctx.novel_id} or ctx.branch:
            raise ValueError('REALTIME_BRANCH_AUTHORITY_NOT_CONFIGURED')
        row = next((r for r in authorized_chapter_rows(ctx, self.owner.sources, self.owner.chapters) if r['id'] == chapter_id), None)
        if row is None: raise FileNotFoundError(chapter_id)
        return row

    def commit(self, ctx, chapter_id, expected_version, document, operation_id, check, state=None):
        old = self.read(ctx, chapter_id)
        if old['version'] != expected_version: raise StaleSourceError('REALTIME_DOCUMENT_CHANGED')
        assert_ai_locks(old['document'], document); check()
        row = self.owner.chapters.save(chapter_id, {'version': expected_version, 'document': deepcopy(document), 'source': 'REALTIME_REVIEWED_EDIT'})
        check()
        return {'chapter': row, 'operation_id': operation_id, 'before_version': expected_version,
                'after_version': row['version'], 'document_digest': digest(row['document'])}


class BranchDocumentAdapter:
    atomic_scope = True

    def __init__(self, service): self.service = service

    def read(self, ctx, chapter_id):
        row = self.service.read(ctx, chapter_id)
        if (row.get('novel_id') != ctx.novel_id or row.get('branch_id') != ctx.scope.get('branch_id')
                or row.get('is_archived') or row.get('hidden') or row.get('secret')
                or str(row.get('visibility', '')).upper() in {'PRIVATE', 'SECRET', 'DENIED'}):
            raise FileNotFoundError(chapter_id)
        return row

    def commit(self, ctx, chapter_id, expected_version, document, operation_id, check, state=None):
        old = self.read(ctx, chapter_id)
        assert_ai_locks(old['document'], document)
        return self.service.commit(ctx, chapter_id, expected_version, document, operation_id, check, state=state,
                                   source='REALTIME_REVIEWED_EDIT')


class SyntheticRealtimeTransport:
    """Bounded synchronous push adapter. No polling, socket, external delivery.

    Authorization is checked immediately before EVERY callback. A denied or
    failed subscriber is dropped. Subscribers are process-local, never restored.
    """
    name = 'SYNTHETIC_IN_PROCESS_PUSH'

    def __init__(self):
        self._lock = RLock()
        self._subscribers = {}

    def subscribe(self, scope_key, participant_id, guard, receive):
        guard()
        with self._lock:
            if len(self._subscribers) >= 1000: raise ValueError('REALTIME_SUBSCRIBER_LIMIT')
            self._subscribers[(scope_key, participant_id)] = (guard, receive)
        return lambda: self.unsubscribe(scope_key, participant_id)

    def unsubscribe(self, scope_key, participant_id):
        with self._lock: self._subscribers.pop((scope_key, participant_id), None)

    def publish(self, scope_key, event):
        with self._lock: targets = list(self._subscribers.items())
        for key, (guard, receive) in targets:
            if key[0] != scope_key: continue
            try:
                guard()
                receive(deepcopy(event))
            except Exception:
                self.unsubscribe(*key)


class RealtimeCollaboration:
    """An extension owned by WriterRoomService and its scoped metadata store."""
    PARTICIPANTS = 'writer_room_realtime_participants_v1'
    OPERATIONS = 'writer_room_realtime_operations_v1'

    def __init__(self, owner, *, transport=None, clock=time):
        self.owner, self.clock = owner, clock
        self.transport = transport or SyntheticRealtimeTransport()
        self.epoch = uuid4().hex
        self._lease_guards = {}

    @property
    def store(self): return self.owner.store

    def _adapter(self, ctx):
        if ctx.scope.get('mode') == 'local': return MainlineDocumentAdapter(self.owner)
        adapter = getattr(self.owner, 'branch_documents', None)
        if adapter is None: raise ValueError('REALTIME_BRANCH_AUTHORITY_NOT_CONFIGURED')
        return adapter if hasattr(adapter, 'atomic_scope') else BranchDocumentAdapter(adapter)

    def _guard(self, ctx, check, permission='domain.read'):
        check(); self.owner.novels.get(ctx.novel_id)
        self.store.key(ctx.novel_id, ctx.scope)
        if ctx.scope['mode'] == 'collaboration' and ctx.branch != ctx.scope['branch_id']:
            raise ValueError('REALTIME_BRANCH_SCOPE_MISMATCH')
        if not self.owner._permission(ctx, ctx.actor, permission):
            raise HTTPException(403, {'code': 'REALTIME_CURRENT_PERMISSION_REQUIRED'})

    @staticmethod
    def _session(ctx):
        if ctx.scope['mode'] != 'local' and not ctx.token:
            raise HTTPException(401, {'code': 'REALTIME_TRUSTED_SESSION_REQUIRED'})
        return sha256((ctx.actor + '\0' + (ctx.token or 'local-author-session')).encode()).hexdigest()

    def _row(self, ctx, collection, rid, state=None):
        source = state if state is not None else self.store.read(ctx.novel_id, ctx.scope)
        row = source['collections'].get(collection, {}).get(rid)
        if row is None or row.get('scope') != ctx.scope or row.get('novel_id') != ctx.novel_id:
            raise FileNotFoundError(rid)
        return row

    def _state(self, ctx, row):
        if row['status'] != 'ACTIVE': return row['status']
        if row['server_epoch'] != self.epoch: return 'DISCONNECTED'
        if row['lease_until'] <= self.clock(): return 'EXPIRED'
        session_guard = self._lease_guards.get((self.store.key(ctx.novel_id, ctx.scope), row['id']))
        if session_guard is not None:
            try: session_guard()
            except Exception: return 'REVOKED'
        if not self.owner._permission(ctx, row['created_by'], 'domain.read'): return 'REVOKED'
        return 'ACTIVE'

    def _participant(self, ctx, rid, *, state=None, active=True):
        row = self._row(ctx, self.PARTICIPANTS, rid, state)
        if row['created_by'] != ctx.actor or row['session_digest'] != self._session(ctx): raise FileNotFoundError(rid)
        if active and self._state(ctx, row) != 'ACTIVE': raise ValueError('REALTIME_PARTICIPANT_NOT_ACTIVE')
        return row

    def _public_participant(self, ctx, row):
        return {**{k: deepcopy(row[k]) for k in ('id', 'device_id', 'chapter_id', 'version', 'document_version', 'cursor', 'lease_until', 'created_by')},
                'status': self._state(ctx, row)}

    @staticmethod
    def _public_operation(row):
        return {k: deepcopy(v) for k, v in row.items() if k not in {'history', 'scope', 'base_document', 'desired_document', 'session_digest'}}

    def _bounded(self, state):
        collections = state['collections']
        if len(collections.get(self.PARTICIPANTS, {})) > MAX_PARTICIPANTS or len(collections.get(self.OPERATIONS, {})) > MAX_OPERATIONS:
            raise ValueError('REALTIME_JOURNAL_CAPACITY_REACHED')
        if len(canonical({k: collections.get(k, {}) for k in (self.PARTICIPANTS, self.OPERATIONS)}).encode()) > MAX_SCOPE_BYTES:
            raise ValueError('REALTIME_SCOPE_BYTES_LIMIT')

    def _emit(self, ctx, kind, row):
        event = {'schema': 'writer-room-realtime-event/1', 'kind': kind, 'id': row['id'], 'version': row['version'],
                 'chapter_id': row['chapter_id'], 'document_version': row.get('result_version', row.get('document_version'))}
        if kind == 'CURSOR_CHANGED': event['cursor'] = deepcopy(row['cursor'])
        if kind == 'DOCUMENT_COMMITTED':
            event.update(base_version=row['base_version'], edits=deepcopy(row['edits']), document_digest=digest(row['desired_document']))
        self.transport.publish(self.store.key(ctx.novel_id, ctx.scope), event)

    def contract(self, ctx, check=lambda: None):
        self._guard(ctx, check)
        configured = ctx.scope['mode'] == 'local' or getattr(self.owner, 'branch_documents', None) is not None
        return {'schema': 'writer-room-realtime/1', 'state': 'PARTIAL', 'transport': self.transport.name,
                'production_server': 'NOT_CONFIGURED', 'document_adapter': 'AVAILABLE' if configured else 'NOT_CONFIGURED',
                'scope': deepcopy(ctx.scope), 'polling_is_realtime': False, 'http_reads': 'SNAPSHOT_ONLY',
                'push_delivery': 'SYNTHETIC_IN_PROCESS_ONLY', 'conflict_policy': 'STRICT_CAS_NO_OT_OR_CRDT',
                'coordinate_system': 'RICH_CONTENT_PATH_UNICODE_CODE_POINT', 'lease_seconds': LEASE_SECONDS,
                'restart': 'DISCONNECT_ALL_REQUIRE_CURRENT_VERSION_RECONNECT', 'unknown_write': 'NO_AUTOMATIC_REPLAY',
                'feature': FEATURE, 'review': 'EXPLICIT_PREPARE_AND_APPLY', 'permissions': ['domain.read', 'domain.write', 'domain.review_FOR_OTHER_PARTICIPANT_REVOKE'],
                'limits': {'participants': MAX_PARTICIPANTS, 'operations': MAX_OPERATIONS, 'scope_bytes': MAX_SCOPE_BYTES}}

    def presence(self, ctx, check=lambda: None):
        self._guard(ctx, check)
        rows = self.owner.list(ctx.novel_id, ctx.scope, self.PARTICIPANTS)
        result = []
        for row in rows:
            try: self._adapter(ctx).read(ctx, row['chapter_id'])
            except FileNotFoundError: continue
            result.append(self._public_participant(ctx, row))
        self._guard(ctx, check)
        return {'state': 'PARTIAL', 'items': result, 'polling_is_realtime': False}

    def join(self, ctx, body, check=lambda: None):
        value = JoinIn.model_validate(body); self._guard(ctx, check)
        chapter = self._adapter(ctx).read(ctx, value.chapter_id)
        if chapter['version'] != value.document_version: raise StaleSourceError('REALTIME_DOCUMENT_CHANGED')
        with self.store.transaction(ctx.novel_id, ctx.scope) as state:
            self._guard(ctx, check)
            rows = state['collections'].setdefault(self.PARTICIPANTS, {})
            old = next((r for r in rows.values() if r['session_digest'] == self._session(ctx) and r['device_id'] == value.device_id and r['chapter_id'] == value.chapter_id), None)
            if old:
                if self._state(ctx, old) != 'ACTIVE': raise ValueError('REALTIME_RECONNECT_REQUIRED_OR_REVOKED')
                return self._public_participant(ctx, old)
            if self._adapter(ctx).read(ctx, value.chapter_id)['version'] != value.document_version: raise StaleSourceError('REALTIME_DOCUMENT_CHANGED')
            row = new_row(ctx.novel_id, ctx.scope, ctx.actor, {**value.model_dump(), 'status': 'ACTIVE',
                'session_digest': self._session(ctx), 'server_epoch': self.epoch, 'lease_until': self.clock() + LEASE_SECONDS, 'cursor': None})
            rows[row['id']] = row; self._bounded(state); self._guard(ctx, check)
        self._lease_guards[(self.store.key(ctx.novel_id, ctx.scope), row['id'])] = check
        self._emit(ctx, 'PARTICIPANT_JOINED', row)
        return self._public_participant(ctx, row)

    def transition(self, ctx, rid, body, check=lambda: None):
        value = ParticipantActionIn.model_validate(body); self._guard(ctx, check)
        with self.store.transaction(ctx.novel_id, ctx.scope) as state:
            row = self._row(ctx, self.PARTICIPANTS, rid, state)
            if value.action == 'revoke':
                if row['created_by'] != ctx.actor: self._guard(ctx, check, 'domain.review')
            else: self._participant(ctx, rid, state=state, active=False)
            check_version(row, value.expected_version)
            status = self._state(ctx, row)
            if status in {'LEFT', 'REVOKED'}: raise ValueError('REALTIME_PARTICIPANT_TERMINAL')
            next_state = {'heartbeat': 'ACTIVE', 'reconnect': 'ACTIVE', 'disconnect': 'DISCONNECTED', 'leave': 'LEFT', 'revoke': 'REVOKED'}[value.action]
            if value.action == 'heartbeat' and status != 'ACTIVE': raise ValueError('REALTIME_RECONNECT_REQUIRED')
            if value.action in {'heartbeat', 'reconnect'}:
                current = self._adapter(ctx).read(ctx, row['chapter_id'])
                if current['version'] != value.document_version: raise StaleSourceError('REALTIME_RECONNECT_DOCUMENT_CHANGED')
            advance(row, ctx.actor, value.expected_version, lambda r: r.update(status=next_state, server_epoch=self.epoch,
                lease_until=self.clock() + LEASE_SECONDS if next_state == 'ACTIVE' else 0,
                document_version=value.document_version if next_state == 'ACTIVE' else r['document_version'], cursor=None))
            self._guard(ctx, check); self._bounded(state)
        key = (self.store.key(ctx.novel_id, ctx.scope), rid)
        if next_state != 'ACTIVE':
            self.transport.unsubscribe(*key)
            self._lease_guards.pop(key, None)
        else: self._lease_guards[key] = check
        self._emit(ctx, 'PARTICIPANT_' + next_state, row)
        return self._public_participant(ctx, row)

    @staticmethod
    def _node(document, path):
        node = document
        for index in path:
            if not isinstance(node, dict) or not isinstance(node.get('content'), list) or index < 0 or index >= len(node['content']):
                raise ValueError('REALTIME_DOCUMENT_POSITION_INVALID')
            node = node['content'][index]
        if node.get('type') != 'text' or not isinstance(node.get('text'), str): raise ValueError('REALTIME_TEXT_NODE_REQUIRED')
        return node

    def cursor(self, ctx, rid, body, check=lambda: None):
        value = CursorIn.model_validate(body); self._guard(ctx, check)
        with self.store.transaction(ctx.novel_id, ctx.scope) as state:
            row = self._participant(ctx, rid, state=state); check_version(row, value.expected_version)
            current = self._adapter(ctx).read(ctx, row['chapter_id'])
            if current['version'] != value.document_version: raise StaleSourceError('REALTIME_CURSOR_DOCUMENT_CHANGED')
            for position in (value.anchor, value.focus):
                if position.offset > len(self._node(current['document'], position.path)['text']): raise ValueError('REALTIME_DOCUMENT_POSITION_INVALID')
            advance(row, ctx.actor, value.expected_version, lambda r: r.update(document_version=value.document_version,
                cursor={'anchor': value.anchor.model_dump(), 'focus': value.focus.model_dump()}, lease_until=self.clock() + LEASE_SECONDS))
            self._guard(ctx, check); self._bounded(state)
        self._emit(ctx, 'CURSOR_CHANGED', row)
        return self._public_participant(ctx, row)

    def prepare(self, ctx, body, check=lambda: None):
        value = EditIn.model_validate(body); self._guard(ctx, check, 'domain.write')
        fingerprint = digest(value.model_dump())
        with self.store.transaction(ctx.novel_id, ctx.scope) as state:
            participant = self._participant(ctx, value.participant_id, state=state)
            rows = state['collections'].setdefault(self.OPERATIONS, {})
            existing = next((r for r in rows.values() if r['session_digest'] == self._session(ctx) and r['request_id'] == value.request_id), None)
            if existing:
                if existing['request_digest'] != fingerprint: raise ValueError('REALTIME_IDEMPOTENCY_CONTENT_CHANGED')
                return self._public_operation(existing)
            check_version(participant, value.participant_version)
            current = self._adapter(ctx).read(ctx, participant['chapter_id'])
            conflict = current['version'] != value.document_version or digest(current['document']) != value.document_digest
            desired = deepcopy(current['document'])
            if not conflict:
                for edit in value.edits:
                    node = self._node(desired, edit.path)
                    if edit.end > len(node['text']): raise ValueError('REALTIME_DOCUMENT_POSITION_INVALID')
                    node['text'] = node['text'][:edit.start] + edit.text + node['text'][edit.end:]
                assert_ai_locks(current['document'], desired)
                if len(canonical(desired).encode()) > 512 * 1024: raise ValueError('REALTIME_DOCUMENT_SIZE_LIMIT')
            row = new_row(ctx.novel_id, ctx.scope, ctx.actor, {**value.model_dump(), 'request_digest': fingerprint,
                'chapter_id': participant['chapter_id'], 'session_digest': self._session(ctx), 'status': 'CONFLICT' if conflict else 'PREPARED',
                'base_document': deepcopy(current['document']), 'base_version': current['version'],
                'desired_document': None if conflict else desired, 'current_digest': digest(current['document']),
                'candidates_preserved': True, 'retry_allowed': False})
            rows[row['id']] = row; self._bounded(state); self._guard(ctx, check, 'domain.write')
        self._emit(ctx, 'EDIT_' + row['status'], row)
        return self._public_operation(row)

    def operation(self, ctx, rid, check=lambda: None):
        self._guard(ctx, check)
        row = self._row(ctx, self.OPERATIONS, rid)
        # Operations may contain submitted text. Re-resolve source visibility,
        # and only return another actor's edit after current review permission.
        self._adapter(ctx).read(ctx, row['chapter_id'])
        if row['created_by'] != ctx.actor: self._guard(ctx, check, 'domain.review')
        result = self._public_operation(row)
        if row['status'] == 'CONFLICT': result['current_document'] = deepcopy(row['base_document'])
        self._guard(ctx, check)
        return result

    def _owned_operation(self, ctx, rid, state=None, *, require_session=True):
        row = self._row(ctx, self.OPERATIONS, rid, state)
        if row['created_by'] != ctx.actor or require_session and row['session_digest'] != self._session(ctx): raise FileNotFoundError(rid)
        return row

    def _apply_guard(self, ctx, row, state, check):
        self._guard(ctx, check, 'domain.write')
        self._participant(ctx, row['participant_id'], state=state)
        current = self._adapter(ctx).read(ctx, row['chapter_id'])
        if current['version'] != row['base_version'] or digest(current['document']) != row['current_digest']:
            raise StaleSourceError('REALTIME_EDIT_BASE_CHANGED')
        assert_ai_locks(current['document'], row['desired_document'])

    def act(self, ctx, rid, body, check=lambda: None):
        value = OperationIn.model_validate(body); self._guard(ctx, check, 'domain.write')
        if value.action in {'inspect_recovery', 'adopt', 'close_without_replay'}:
            return self.recover(ctx, rid, value, check)
        if value.action == 'cancel':
            with self.store.transaction(ctx.novel_id, ctx.scope) as state:
                row = self._owned_operation(ctx, rid, state, require_session=False); check_version(row, value.expected_version)
                if row['status'] not in {'PREPARED', 'CONFLICT'}: raise ValueError('REALTIME_CANCEL_UNAVAILABLE')
                advance(row, ctx.actor, row['version'], lambda r: r.update(status='CANCELLED'))
                self._guard(ctx, check, 'domain.write')
            return self._public_operation(row)
        adapter = self._adapter(ctx)
        with self.store.transaction(ctx.novel_id, ctx.scope) as state:
            row = self._owned_operation(ctx, rid, state); check_version(row, value.expected_version)
            if row['status'] != 'PREPARED': raise ValueError('REALTIME_OPERATION_NOT_PREPARED_NO_REPLAY')
            self._apply_guard(ctx, row, state, check)
            if adapter.atomic_scope:
                receipt = adapter.commit(ctx, row['chapter_id'], row['base_version'], deepcopy(row['desired_document']), rid, check, state=state)
                self._finish(ctx, row, receipt, check)
                self._bounded(state)
            else:
                advance(row, ctx.actor, row['version'], lambda r: r.update(status='CLAIMED'))
                self._guard(ctx, check, 'domain.write')
        if adapter.atomic_scope:
            self._emit(ctx, 'DOCUMENT_COMMITTED', row)
            return self._public_operation(row)
        try:
            with self.store.transaction(ctx.novel_id, ctx.scope) as state:
                row = self._owned_operation(ctx, rid, state)
                if row['status'] != 'CLAIMED': raise ValueError('REALTIME_OPERATION_NO_REPLAY')
                self._apply_guard(ctx, row, state, check)
                receipt = adapter.commit(ctx, row['chapter_id'], row['base_version'], deepcopy(row['desired_document']), rid, check)
                self._finish(ctx, row, receipt, check); self._bounded(state)
        except Exception:
            with self.store.transaction(ctx.novel_id, ctx.scope) as state:
                row = self._owned_operation(ctx, rid, state)
                if row['status'] == 'CLAIMED': advance(row, ctx.actor, row['version'], lambda r: r.update(status='UNKNOWN'))
            raise
        self._emit(ctx, 'DOCUMENT_COMMITTED', row)
        return self._public_operation(row)

    def _finish(self, ctx, row, receipt, check):
        actual = self._adapter(ctx).read(ctx, row['chapter_id'])
        if (receipt.get('operation_id') != row['id'] or receipt.get('before_version') != row['base_version']
                or receipt.get('after_version') != row['base_version'] + 1 or actual['version'] != receipt['after_version']
                or digest(actual['document']) != digest(row['desired_document']) or receipt.get('document_digest') != digest(actual['document'])):
            raise ValueError('REALTIME_RECEIPT_MISMATCH')
        self._guard(ctx, check, 'domain.write')
        advance(row, ctx.actor, row['version'], lambda r: r.update(status='APPLIED', result_version=actual['version']))

    def recover(self, ctx, rid, value, check):
        with self.store.transaction(ctx.novel_id, ctx.scope) as state:
            row = self._owned_operation(ctx, rid, state, require_session=False); check_version(row, value.expected_version)
            if row['status'] not in {'CLAIMED', 'UNKNOWN'}: raise ValueError('REALTIME_RECOVERY_NOT_REQUIRED')
            actual = self._adapter(ctx).read(ctx, row['chapter_id'])
            match = actual['version'] == row['base_version'] + 1 and digest(actual['document']) == digest(row['desired_document'])
            unchanged = actual['version'] == row['base_version'] and digest(actual['document']) == row['current_digest']
            result = {'id': rid, 'version': row['version'], 'status': row['status'], 'current_version': actual['version'],
                      'observation': 'MATCHES_INTENT_UNCONFIRMED' if match else 'BASE_UNCHANGED' if unchanged else 'DIVERGED',
                      'can_adopt': match, 'retry_allowed': False}
            result['recovery_digest'] = digest(result); self._guard(ctx, check, 'domain.write')
            if value.action == 'inspect_recovery': return result
            if value.recovery_digest != result['recovery_digest']: raise StaleSourceError('REALTIME_RECOVERY_CHANGED')
            if value.action == 'adopt' and not match: raise ValueError('REALTIME_RECOVERY_NOT_EXACT')
            advance(row, ctx.actor, row['version'], lambda r: r.update(status='ADOPTED' if value.action == 'adopt' else 'CLOSED_WITHOUT_REPLAY', result_version=actual['version']))
            return self._public_operation(row)

    def subscribe(self, ctx, participant_id, receive, check=lambda: None):
        def guard():
            self._guard(ctx, check)
            row = self._participant(ctx, participant_id)
            self._adapter(ctx).read(ctx, row['chapter_id'])
        chapter_id = self._participant(ctx, participant_id)['chapter_id']
        def scoped_receive(event):
            if event['chapter_id'] == chapter_id: receive(event)
        return self.transport.subscribe(self.store.key(ctx.novel_id, ctx.scope), participant_id, guard, scoped_receive)
