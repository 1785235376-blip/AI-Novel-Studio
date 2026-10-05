"""B10 bounded, opt-in local exchange. No network client, credentials or account system.

Messages are review candidates, never replication writes. Original chapter writers
and B09 rich-block diff3 remain authoritative. Public routing labels/digests are
not authentication or cryptography. Durable intent is not exactly-once execution.
"""
from __future__ import annotations

from copy import deepcopy
import re
from typing import Literal
from uuid import uuid4

from pydantic import ConfigDict, Field
from ..revision_constraints import assert_ai_locks, RevisionConstraintError
from .common import DomainService, StaleSourceError, check_version, new_row, now
from .planning import StrictModel, digest
from .project_forks import rich_document, block_merge, advance
from .reader_sources import authorized_chapter, authorized_chapter_rows
from .store import canonical

FEATURE = 'offline_sync_v2'
MAX_BYTES = 512 * 1024
MAX_CHANNEL_BYTES = 8 * 1024 * 1024
MAX_MESSAGES = 100
ID = r'^[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}$'
SHA = r'^[a-f0-9]{64}$'
LIMITS = ['MANUAL_LOCAL_EXCHANGE_ONLY', 'EXTERNAL_NETWORK_SYNC_OFF', 'PUBLIC_LABELS_NOT_AUTHENTICATION',
          'NO_END_TO_END_ENCRYPTION_OR_PRODUCTION_KEY_LIFECYCLE', 'LOCAL_PROJECT_NOT_COLLABORATION_BRANCH',
          'SELECTED_CHAPTERS_ONLY_NO_ASSETS_CREDENTIALS_MODELS_CACHE_OR_PATH_METADATA',
          'REVIEW_BEFORE_ORIGINAL_CHAPTER_CAS', 'DOWNLOADED_COPIES_AND_BACKUPS_CANNOT_BE_RECALLED',
          'TOMBSTONES_BLOCK_FUTURE_EXCHANGE_NOT_PHYSICAL_ERASURE', 'BOUNDED_JOURNAL_NO_AUTOMATIC_RETRY',
          'LOCAL_WITHDRAWAL_DOES_NOT_NOTIFY_PEER', 'NEW_SELECTION_REQUIRES_REVIEWED_IMMUTABLE_BASELINE']
# Defensive export guard. This is not a general DLP or secret scanner. Unlike
# silent redaction, rejection preserves the saved manuscript exactly.
UNSAFE_TEXT = re.compile(r'(?:[A-Za-z]:[\\/]|(?:^|[\s"\'])/(?:home|Users|workspace|tmp|var|etc|root|mnt|Volumes)/|\\\\[^\s\\]+\\|(?:sk-[A-Za-z0-9_-]{12,})|-----BEGIN [A-Z ]*PRIVATE KEY-----|(?:postgres(?:ql)?://|Bearer\s+[A-Za-z0-9._-]{12,})|(?:api[_ -]?key|password|access[_ -]?token)\s*[:=]\s*\S+)', re.I)


def safe_snapshot(value):
    result = ChapterSnapshot.model_validate(value).model_dump()
    result['document'] = rich_document(result['document'], {})  # any asset refs require a separate authorized protocol
    if len(canonical(result).encode()) > MAX_BYTES // 2: raise ValueError('SYNC_CHAPTER_SIZE_LIMIT')
    if UNSAFE_TEXT.search(canonical(result)): raise ValueError('SYNC_SENSITIVE_OR_LOCAL_PATH_TEXT_REQUIRES_REMOVAL_FROM_EXCHANGE')
    return result


class SyncInput(StrictModel):
    model_config = ConfigDict(extra='forbid', strict=True, str_strip_whitespace=False)


class ChapterSnapshot(SyncInput):
    title: str = Field(min_length=1, max_length=200)
    document: dict


class ChannelIn(SyncInput):
    stream_id: str = Field(pattern=ID)
    endpoint_id: str = Field(pattern=ID)
    peer_id: str = Field(pattern=ID)
    chapter_ids: list[str] = Field(default_factory=list, max_length=20)
    allow_new_chapters: bool = False


class VersionIn(SyncInput):
    expected_version: int = Field(ge=1)


class SelectionIn(VersionIn):
    add_chapter_ids: list[str] = Field(default_factory=list, max_length=20)
    withdraw_chapter_ids: list[str] = Field(default_factory=list, max_length=20)


class SelectionApplyIn(SelectionIn):
    preview_digest: str = Field(pattern=SHA)
    confirmed: Literal[True]


class QueueIn(VersionIn):
    chapter_id: str = Field(pattern=ID)
    request_id: str = Field(pattern=ID)
    tombstone: bool = False


class Envelope(SyncInput):
    protocol: Literal['AI_NOVEL_SYNC_1']
    stream_id: str = Field(pattern=ID)
    source_endpoint: str = Field(pattern=ID)
    destination_endpoint: str = Field(pattern=ID)
    message_id: str = Field(pattern=ID)
    sequence: int = Field(ge=1, le=1000000)
    source_chapter_id: str = Field(pattern=ID)
    source_version: int = Field(ge=1)
    operation: Literal['SNAPSHOT', 'TOMBSTONE']
    base: ChapterSnapshot
    snapshot: ChapterSnapshot | None
    privacy_level: Literal['LOCAL_ONLY']


class ReceiveIn(VersionIn):
    envelope: Envelope
    target_chapter_id: str | None = Field(default=None, pattern=ID)
    create_new: bool = False


class ReviewIn(VersionIn):
    choices: dict[str, Literal['LOCAL', 'INCOMING']] = Field(default_factory=dict, max_length=1000)


class ApplyIn(ReviewIn):
    preview_digest: str = Field(pattern=SHA)
    confirmed: Literal[True]


class ExportIn(VersionIn):
    envelope_digest: str = Field(pattern=SHA)
    acknowledge_copy_boundary: Literal[True]


class DeliveryIn(VersionIn):
    state: Literal['FAILED', 'UNKNOWN', 'ACKNOWLEDGED']
    receipt: dict | None = None


class RecoverIn(VersionIn):
    adopt_matching_result: bool = False
    close_without_replay: bool = False
    preview_digest: str | None = Field(default=None, pattern=SHA)


class OfflineSyncService(DomainService):
    CHANNELS = 'offline_sync_channels_v1'
    OUTBOX = 'offline_sync_outbox_v1'
    INBOX = 'offline_sync_inbox_v1'

    def __init__(self, store, novels, chapters, *, sources):
        super().__init__(store, novels, chapters)
        self.source_reader = sources

    @staticmethod
    def _local(ctx):
        if ctx.scope != {'mode': 'local', 'novel_id': ctx.novel_id} or ctx.branch:
            raise ValueError('SYNC_COLLABORATION_BRANCH_WRITER_UNAVAILABLE')

    def _owned(self, ctx, collection, rid):
        self._local(ctx)
        row = self.get(ctx.novel_id, ctx.scope, collection, rid)
        if row.get('created_by') != ctx.actor: raise FileNotFoundError('sync record unavailable')
        return row

    def _channel(self, ctx, rid, active=True):
        row = self._owned(ctx, self.CHANNELS, rid)
        if active and row['status'] != 'ACTIVE': raise ValueError('SYNC_CHANNEL_REVOKED')
        return row

    def _chapter(self, ctx, cid):
        self._local(ctx)
        row = authorized_chapter(ctx, self.source_reader, self.chapters, cid, include_archived=True)
        snapshot = safe_snapshot({'title': row['title'], 'document': row['document']})
        return {'id': cid, 'version': row['version'], 'archived': bool(row.get('is_archived')), **snapshot}

    @staticmethod
    def _snapshot(chapter): return {k: deepcopy(chapter[k]) for k in ('title', 'document')}

    @staticmethod
    def _summary(row):
        omit = {'history', 'baseline', 'envelope', 'checkpoint', 'intent', 'created_ids', 'scope'}
        return {k: deepcopy(v) for k, v in row.items() if k not in omit}

    def _bounded(self, state, channel_id):
        rows = [r for name in (self.CHANNELS, self.OUTBOX, self.INBOX)
                for r in state['collections'].get(name, {}).values() if r.get('channel_id', r['id']) == channel_id]
        if len(rows) > 2 * MAX_MESSAGES + 1 or len(canonical(rows).encode()) > MAX_CHANNEL_BYTES:
            raise ValueError('SYNC_CHANNEL_CAPACITY_REACHED_EXPORT_REVIEW_AND_START_NEW_CHANNEL')

    def catalog(self, ctx):
        self._local(ctx)
        rows = authorized_chapter_rows(ctx, self.source_reader, self.chapters)
        return {'chapters': [{'id': r['id'], 'title': r['title'], 'version': r['version']} for r in rows[:100]],
                'truncated': len(rows) > 100, 'network_enabled': False, 'limitations': LIMITS}

    def records(self, ctx):
        self._local(ctx)
        channels = [r for r in self.list(ctx.novel_id, ctx.scope, self.CHANNELS) if r['created_by'] == ctx.actor]
        return {'channels': [self._summary(r) for r in channels],
                'outbox': [self._summary(r) for r in self.list(ctx.novel_id, ctx.scope, self.OUTBOX) if r['created_by'] == ctx.actor],
                'inbox': [self._summary(r) for r in self.list(ctx.novel_id, ctx.scope, self.INBOX) if r['created_by'] == ctx.actor],
                'network_enabled': False, 'limitations': LIMITS}

    def open_channel(self, ctx, body, reauthorize=lambda: None):
        self._local(ctx); value = ChannelIn.model_validate(body)
        if value.endpoint_id == value.peer_id or len(set(value.chapter_ids)) != len(value.chapter_ids): raise ValueError('SYNC_PAIR_OR_SELECTION_INVALID')
        if not value.chapter_ids and not value.allow_new_chapters: raise ValueError('SYNC_EXPLICIT_SCOPE_REQUIRED')
        baseline = {}
        for cid in value.chapter_ids:
            chapter = self._chapter(ctx, cid)
            if chapter['archived']: raise ValueError('SYNC_ARCHIVED_SOURCE_UNAVAILABLE')
            baseline[cid] = self._snapshot(chapter)
        reauthorize()
        with self.store.transaction(ctx.novel_id, ctx.scope) as state:
            channels = state['collections'].setdefault(self.CHANNELS, {})
            if len(channels) >= 20: raise ValueError('SYNC_CHANNEL_LIMIT')
            if any(r['created_by'] == ctx.actor and r['stream_id'] == value.stream_id for r in channels.values()):
                raise ValueError('SYNC_STREAM_ALREADY_REGISTERED_USE_NEW_STREAM_AFTER_REVOCATION')
            row = new_row(ctx.novel_id, ctx.scope, ctx.actor, {**value.model_dump(), 'baseline': baseline,
                'status': 'ACTIVE', 'send_cursor': 0, 'receive_cursor': 0, 'bindings': {}, 'tombstones': [], 'sent_tombstones': [],
                'withdrawn_chapter_ids': [], 'withdrawn_source_ids': []})
            channels[row['id']] = row; self._bounded(state, row['id']); reauthorize()
            return self._summary(row)

    def revoke(self, ctx, rid, body, reauthorize=lambda: None):
        value = VersionIn.model_validate(body); self._channel(ctx, rid); reauthorize()
        with self.store.transaction(ctx.novel_id, ctx.scope) as state:
            row = state['collections'][self.CHANNELS][rid]
            advance(row, ctx.actor, value.expected_version, lambda r: r.update(status='REVOKED'))
            reauthorize(); return self._summary(row)

    @staticmethod
    def _selection_guard(channel, cid=None, remote_id=None):
        if channel['status'] != 'ACTIVE': raise ValueError('SYNC_CHANNEL_REVOKED')
        if (cid and cid in channel.get('withdrawn_chapter_ids', [])
                or remote_id and remote_id in channel.get('withdrawn_source_ids', [])):
            raise ValueError('SYNC_SELECTION_REVOKED_NEW_CHANNEL_REQUIRED')
        if cid and cid not in channel['chapter_ids']: raise ValueError('SYNC_TARGET_NOT_SELECTED')

    def _selection_plan(self, ctx, channel, value):
        check_version(channel, value.expected_version)
        added, withdrawn = value.add_chapter_ids, value.withdraw_chapter_ids
        if (not added and not withdrawn or len(set(added)) != len(added) or len(set(withdrawn)) != len(withdrawn)
                or set(added) & set(withdrawn)):
            raise ValueError('SYNC_SELECTION_CHANGE_INVALID')
        if any(cid not in channel['chapter_ids'] for cid in withdrawn): raise ValueError('SYNC_CHAPTER_NOT_SELECTED')
        if any(cid in channel.get('withdrawn_chapter_ids', []) for cid in added):
            raise ValueError('SYNC_SELECTION_REVOKED_NEW_CHANNEL_REQUIRED')
        if any(cid in channel['baseline'] for cid in added): raise ValueError('SYNC_BASELINE_ALREADY_REGISTERED')
        # Immutable historical baselines also count toward the bounded channel.
        reserved = sum(r['channel_id'] == channel['id'] and r['target_chapter_id'] is None
                       for r in self.list(ctx.novel_id, ctx.scope, self.INBOX))
        if len(channel['baseline']) + reserved + len(added) > 20: raise ValueError('SYNC_SELECTION_LIMIT_NEW_CHANNEL_REQUIRED')
        chapters = [self._chapter(ctx, cid) for cid in added]
        if any(c['archived'] for c in chapters): raise ValueError('SYNC_ARCHIVED_SOURCE_UNAVAILABLE')
        result = {'channel_id': channel['id'], 'version': channel['version'], 'additions': chapters,
                  'withdraw_chapter_ids': withdrawn, 'baseline_policy': 'FRESH_IMMUTABLE_BASELINE_FOR_NEW_SELECTIONS',
                  'copy_boundary': 'DOWNLOADED_COPIES_AND_BACKUPS_CANNOT_BE_RECALLED'}
        result['preview_digest'] = digest(result)
        return result

    def preview_selection(self, ctx, rid, body, reauthorize=lambda: None):
        value = SelectionIn.model_validate(body); channel = self._channel(ctx, rid)
        result = self._selection_plan(ctx, channel, value); reauthorize(); return result

    def change_selection(self, ctx, rid, body, reauthorize=lambda: None):
        value = SelectionApplyIn.model_validate(body); self._channel(ctx, rid); reauthorize()
        with self.store.transaction(ctx.novel_id, ctx.scope) as state:
            channel = state['collections'][self.CHANNELS][rid]; self._selection_guard(channel)
            plan = self._selection_plan(ctx, channel, value)
            if plan['preview_digest'] != value.preview_digest: raise StaleSourceError('SYNC_SELECTION_REVIEW_CHANGED')
            withdrawn = set(value.withdraw_chapter_ids)
            remote_ids = {key for key, binding in channel['bindings'].items() if binding['chapter_id'] in withdrawn}
            remote_ids.update(r['envelope']['source_chapter_id'] for r in state['collections'].get(self.INBOX, {}).values()
                              if r['channel_id'] == rid and r['target_chapter_id'] in withdrawn)
            def change(row):
                row['chapter_ids'] = [cid for cid in row['chapter_ids'] if cid not in withdrawn] + value.add_chapter_ids
                row['withdrawn_chapter_ids'] = sorted(set(row.get('withdrawn_chapter_ids', [])) | withdrawn)
                row['withdrawn_source_ids'] = sorted(set(row.get('withdrawn_source_ids', [])) | remote_ids)
                for chapter in plan['additions']: row['baseline'][chapter['id']] = self._snapshot(chapter)
            advance(channel, ctx.actor, value.expected_version, change)
            for collection, key in [(self.OUTBOX, 'chapter_id'), (self.INBOX, 'target_chapter_id')]:
                for row in state['collections'].get(collection, {}).values():
                    if row['channel_id'] != rid or row[key] not in withdrawn: continue
                    def invalidate(item):
                        item['selection_withdrawn'] = True
                        if item['status'] in {'PENDING', 'FAILED', 'PENDING_REVIEW'}: item['status'] = 'SELECTION_REVOKED'
                    advance(row, ctx.actor, row['version'], invalidate)
            self._bounded(state, rid); reauthorize(); return self._summary(channel)

    def queue(self, ctx, rid, body, reauthorize=lambda: None):
        value = QueueIn.model_validate(body); channel = self._channel(ctx, rid)
        if value.chapter_id not in channel['chapter_ids']: raise ValueError('SYNC_CHAPTER_NOT_SELECTED')
        current = self._chapter(ctx, value.chapter_id)
        if current['archived'] != value.tombstone: raise ValueError('SYNC_TOMBSTONE_REQUIRES_CURRENT_ARCHIVE')
        signature = digest(value.model_dump(exclude={'expected_version'})); reauthorize()
        with self.store.transaction(ctx.novel_id, ctx.scope) as state:
            channel = state['collections'][self.CHANNELS][rid]; self._selection_guard(channel, value.chapter_id)
            rows = state['collections'].setdefault(self.OUTBOX, {})
            prior = next((r for r in rows.values() if r['channel_id'] == rid and r['request_id'] == value.request_id), None)
            if prior:
                if prior['request_digest'] != signature: raise ValueError('SYNC_IDEMPOTENCY_KEY_REUSED')
                return self._summary(prior)
            check_version(channel, value.expected_version)
            if value.chapter_id in channel['sent_tombstones']: raise ValueError('SYNC_SOURCE_TOMBSTONED_NEW_CHANNEL_REQUIRED')
            if sum(r['channel_id'] == rid for r in rows.values()) >= MAX_MESSAGES: raise ValueError('SYNC_OUTBOX_LIMIT')
            if channel['status'] != 'ACTIVE': raise ValueError('SYNC_CHANNEL_REVOKED')
            if self._chapter(ctx, value.chapter_id) != current: raise StaleSourceError('SYNC_SOURCE_CHANGED')
            mid = str(uuid4()); sequence = channel['send_cursor'] + 1
            envelope = Envelope(protocol='AI_NOVEL_SYNC_1', stream_id=channel['stream_id'], source_endpoint=channel['endpoint_id'],
                destination_endpoint=channel['peer_id'], message_id=mid, sequence=sequence, source_chapter_id=value.chapter_id,
                source_version=current['version'], operation='TOMBSTONE' if value.tombstone else 'SNAPSHOT',
                base=channel['baseline'][value.chapter_id], snapshot=None if value.tombstone else self._snapshot(current), privacy_level='LOCAL_ONLY').model_dump()
            row = new_row(ctx.novel_id, ctx.scope, ctx.actor, {'channel_id': rid, 'request_id': value.request_id, 'request_digest': signature,
                'envelope': envelope, 'envelope_digest': digest(envelope), 'chapter_id': value.chapter_id, 'source_version': current['version'],
                'sequence': sequence, 'operation': envelope['operation'], 'status': 'PENDING', 'attempts': 0})
            row['id'] = mid; rows[mid] = row
            advance(channel, ctx.actor, value.expected_version, lambda r: r.update(send_cursor=sequence))
            if value.tombstone: channel['sent_tombstones'].append(value.chapter_id)
            self._bounded(state, rid); reauthorize(); return self._summary(row)

    def _dispatch_guard(self, ctx, row):
        channel = self._channel(ctx, row['channel_id']); self._selection_guard(channel, row['chapter_id'])
        current = self._chapter(ctx, row['chapter_id']); envelope = row['envelope']
        if envelope['operation'] != 'TOMBSTONE' and row['chapter_id'] in channel['sent_tombstones']: raise ValueError('SYNC_SOURCE_TOMBSTONED')
        if (current['version'] != envelope['source_version'] or current['archived'] != (envelope['operation'] == 'TOMBSTONE')
                or not current['archived'] and self._snapshot(current) != envelope['snapshot']):
            raise StaleSourceError('SYNC_QUEUED_SOURCE_CHANGED_REQUEUE_CURRENT_SAVED_VERSION')
        return channel

    def inspect_outbox(self, ctx, mid):
        row = self._owned(ctx, self.OUTBOX, mid); self._dispatch_guard(ctx, row)
        return {**self._summary(row), 'envelope': row['envelope'], 'limitations': LIMITS}

    def export(self, ctx, mid, body, reauthorize=lambda: None):
        value = ExportIn.model_validate(body); row = self._owned(ctx, self.OUTBOX, mid)
        if value.envelope_digest != row['envelope_digest']: raise StaleSourceError('SYNC_ENVELOPE_CHANGED')
        self._dispatch_guard(ctx, row); reauthorize()
        with self.store.transaction(ctx.novel_id, ctx.scope) as state:
            row = state['collections'][self.OUTBOX][mid]; check_version(row, value.expected_version)
            if row['status'] == 'ACKNOWLEDGED' or row['attempts'] >= 8: raise ValueError('SYNC_RETRY_LIMIT_OR_ALREADY_ACKNOWLEDGED')
            self._dispatch_guard(ctx, row); reauthorize()
            advance(row, ctx.actor, value.expected_version, lambda r: r.update(status='UNKNOWN', attempts=r['attempts'] + 1, last_dispatch_at=now()))
            # No HTTP, socket, timer or background job is started here.
            return {**self._summary(row), 'envelope': deepcopy(row['envelope']), 'limitations': LIMITS}

    @staticmethod
    def _receipt(row):
        e = row['envelope']
        return {'protocol': 'AI_NOVEL_SYNC_RECEIPT_1', 'message_id': e['message_id'], 'envelope_digest': row['envelope_digest'],
                'stream_id': e['stream_id'], 'source_endpoint': e['source_endpoint'], 'destination_endpoint': e['destination_endpoint'],
                'sequence': e['sequence'], 'status': 'RECEIVED'}

    def delivery(self, ctx, mid, body, reauthorize=lambda: None):
        value = DeliveryIn.model_validate(body); row = self._owned(ctx, self.OUTBOX, mid); self._channel(ctx, row['channel_id']); reauthorize()
        with self.store.transaction(ctx.novel_id, ctx.scope) as state:
            row = state['collections'][self.OUTBOX][mid]
            if row['status'] == 'ACKNOWLEDGED' or not row['attempts']: raise ValueError('SYNC_DELIVERY_STATE_INVALID')
            if value.state == 'ACKNOWLEDGED' and value.receipt != self._receipt(row): raise ValueError('SYNC_RECEIPT_MISMATCH')
            advance(row, ctx.actor, value.expected_version, lambda r: r.update(status=value.state))
            reauthorize(); return self._summary(row)

    def receive(self, ctx, rid, body, reauthorize=lambda: None):
        value = ReceiveIn.model_validate(body); channel = self._channel(ctx, rid); envelope = value.envelope.model_dump()
        envelope['base'] = safe_snapshot(envelope['base'])
        if envelope['snapshot'] is not None: envelope['snapshot'] = safe_snapshot(envelope['snapshot'])
        if (envelope['operation'] == 'TOMBSTONE') != (envelope['snapshot'] is None): raise ValueError('SYNC_OPERATION_INVALID')
        if (envelope['stream_id'], envelope['source_endpoint'], envelope['destination_endpoint']) != (channel['stream_id'], channel['peer_id'], channel['endpoint_id']):
            raise ValueError('SYNC_ENVELOPE_WRONG_PEER_OR_STREAM')
        if len(canonical(envelope).encode()) > MAX_BYTES: raise ValueError('SYNC_ENVELOPE_LIMIT')
        remote_id = envelope['source_chapter_id']; fingerprint = digest(envelope)
        request_digest = digest(value.model_dump(exclude={'expected_version'})); reauthorize()
        with self.store.transaction(ctx.novel_id, ctx.scope) as state:
            channel = state['collections'][self.CHANNELS][rid]; self._selection_guard(channel, remote_id=remote_id)
            rows = state['collections'].setdefault(self.INBOX, {})
            prior = rows.get(envelope['message_id'])
            if prior:
                if prior['channel_id'] != rid or prior['envelope_digest'] != fingerprint or prior['receive_request_digest'] != request_digest: raise ValueError('SYNC_IDEMPOTENCY_KEY_REUSED')
                self._selection_guard(channel, prior['target_chapter_id'], remote_id)
                return {**self._summary(prior), 'receipt': self._receipt(prior), 'duplicate': True}
            check_version(channel, value.expected_version)
            if envelope['sequence'] <= channel['receive_cursor']: raise ValueError('SYNC_OLD_OR_OUT_OF_ORDER_SEQUENCE')
            if remote_id in channel['tombstones']: raise ValueError('SYNC_REMOTE_CHAPTER_TOMBSTONED')
            if sum(r['channel_id'] == rid for r in rows.values()) >= MAX_MESSAGES: raise ValueError('SYNC_INBOX_LIMIT')
            same_source = [r for r in rows.values() if r['channel_id'] == rid and r['envelope']['source_chapter_id'] == remote_id]
            if any(r['status'] in {'CLAIMED', 'UNKNOWN'} for r in same_source): raise ValueError('SYNC_PENDING_OUTCOME_RECONCILIATION_REQUIRED')
            binding = channel['bindings'].get(remote_id)
            if binding:
                if value.create_new or value.target_chapter_id not in {None, binding['chapter_id']} or binding['base_digest'] != digest(envelope['base']):
                    raise ValueError('SYNC_EXISTING_BINDING_OR_BASE_CHANGED')
                target_id = binding['chapter_id']
                self._selection_guard(channel, target_id, remote_id)
            else:
                target_id = value.target_chapter_id
                if value.create_new:
                    if target_id or not channel['allow_new_chapters'] or envelope['operation'] == 'TOMBSTONE' or len(channel['baseline']) + sum(r['channel_id'] == rid and r['target_chapter_id'] is None for r in rows.values()) >= 20: raise ValueError('SYNC_NEW_CHAPTER_NOT_APPROVED')
                    # A second message cannot create another copy while an add is pending.
                    if any(r['channel_id'] == rid and r['envelope']['source_chapter_id'] == remote_id for r in rows.values()):
                        raise ValueError('SYNC_PENDING_NEW_CHAPTER_REVIEW_REQUIRED')
                else:
                    self._selection_guard(channel, target_id, remote_id)
                    if not target_id: raise ValueError('SYNC_TARGET_NOT_SELECTED')
                    if channel['baseline'][target_id] != envelope['base']: raise ValueError('SYNC_INITIAL_BASE_MISMATCH_USE_NEW_CHAPTER')
                    self._chapter(ctx, target_id)
                    if any(b['chapter_id'] == target_id for b in channel['bindings'].values()): raise ValueError('SYNC_TARGET_ALREADY_BOUND')
                    channel['bindings'][remote_id] = {'chapter_id': target_id, 'base_digest': digest(envelope['base'])}
            row = new_row(ctx.novel_id, ctx.scope, ctx.actor, {'channel_id': rid, 'envelope': envelope, 'envelope_digest': fingerprint,
                'target_chapter_id': target_id, 'receive_request_digest': request_digest, 'sequence': envelope['sequence'], 'operation': envelope['operation'],
                'source_version': envelope['source_version'], 'status': 'PENDING_REVIEW', 'journal': []})
            for older in same_source:
                if older['status'] == 'PENDING_REVIEW': advance(older, ctx.actor, older['version'], lambda r: r.update(status='SUPERSEDED'))
            row['id'] = envelope['message_id']; rows[row['id']] = row
            advance(channel, ctx.actor, value.expected_version, lambda r: r.update(receive_cursor=envelope['sequence']))
            if envelope['operation'] == 'TOMBSTONE': channel['tombstones'].append(remote_id)
            self._bounded(state, rid); reauthorize()
            return {**self._summary(row), 'receipt': self._receipt(row), 'duplicate': False}

    def _review(self, ctx, row, choices):
        channel = self._channel(ctx, row['channel_id']); envelope = row['envelope']; cid = row['target_chapter_id']
        self._selection_guard(channel, cid, envelope['source_chapter_id'])
        if row['status'] != 'PENDING_REVIEW': raise ValueError('SYNC_MESSAGE_NOT_PENDING_REVIEW')
        if envelope['operation'] != 'TOMBSTONE' and envelope['source_chapter_id'] in channel['tombstones']: raise ValueError('SYNC_REMOTE_CHAPTER_TOMBSTONED')
        current = self._chapter(ctx, cid) if cid else None
        if cid and cid not in channel['chapter_ids']: raise ValueError('SYNC_TARGET_NOT_SELECTED')
        if not cid and not channel['allow_new_chapters']: raise ValueError('SYNC_NEW_CHAPTER_NOT_APPROVED')
        base, incoming = envelope['base'], envelope['snapshot']; segments = []; used = set(); unresolved = 0; blocked = []
        if current is None:
            if len(channel['baseline']) >= 20: blocked.append('SYNC_SELECTION_LIMIT_NEW_CHANNEL_REQUIRED')
            desired = deepcopy(incoming)
            segments = [{'kind': 'NEW_CHAPTER', 'incoming': incoming}]
        elif envelope['operation'] == 'TOMBSTONE' or current['archived']:
            key = digest(['archive', row['id'], current, incoming]); choice = choices.get(key); used.add(key)
            segments = [{'id': key, 'kind': 'CONFLICT', 'reason': 'DELETE_MODIFY_OR_ARCHIVE', 'base': base, 'local': self._snapshot(current), 'incoming': incoming, 'choice': choice}]
            if not choice: unresolved += 1
            desired = deepcopy(incoming) if choice == 'INCOMING' else self._snapshot(current)
            if current['archived'] and desired is not None: blocked.append('SYNC_ARCHIVED_TARGET_RESTORE_IN_ORIGINAL_EDITOR_FIRST')
        else:
            raw = block_merge(base['document'].get('content', []), current['document'].get('content', []), incoming['document'].get('content', [])); nodes = []
            for index, segment in enumerate(raw):
                if segment['kind'] == 'UNCHANGED': nodes.extend(segment['nodes']); segments.append(segment); continue
                key = digest([row['id'], index, segment]); segment['id'] = key
                segment['local'] = segment.pop('ORIGINAL'); segment['incoming'] = segment.pop('FORK')
                if segment['kind'] == 'CONFLICT':
                    used.add(key); choice = choices.get(key); segment['choice'] = choice
                    if not choice: unresolved += 1
                    nodes.extend(segment['incoming'] if choice == 'INCOMING' else segment['local'])
                else: nodes.extend(segment['incoming'] if segment['kind'] in {'FORK_ONLY', 'BOTH_SAME'} else segment['local'])
                segments.append(segment)
            desired = {'title': incoming['title'], 'document': {'type': 'doc', 'content': nodes}}
        if set(choices) - used: raise ValueError('SYNC_UNKNOWN_OR_STALE_CONFLICT_CHOICE')
        if current:
            try: assert_ai_locks(current['document'], desired['document'] if desired else {'type': 'doc', 'content': []})
            except RevisionConstraintError: blocked.append('SYNC_REVISION_LOCKED')
        plan = {'message_id': row['id'], 'current': current, 'base': base, 'incoming': incoming, 'desired': desired,
                'segments': segments, 'choices': choices, 'unresolved': unresolved, 'blocked': blocked,
                'can_apply': not unresolved and not blocked, 'operation': envelope['operation']}
        plan['preview_digest'] = digest(plan)
        return plan

    def review(self, ctx, mid, body, reauthorize=lambda: None):
        value = ReviewIn.model_validate(body); row = self._owned(ctx, self.INBOX, mid); check_version(row, value.expected_version)
        if row['status'] != 'PENDING_REVIEW': raise ValueError('SYNC_MESSAGE_NOT_PENDING_REVIEW')
        result = self._review(ctx, row, value.choices); reauthorize()
        return {**result, 'version': row['version'], 'limitations': LIMITS}

    def _mark_unknown(self, ctx, mid):
        with self.store.transaction(ctx.novel_id, ctx.scope) as state:
            row = state['collections'][self.INBOX][mid]
            if row['status'] not in {'CLAIMED', 'UNKNOWN'}: return
            advance(row, ctx.actor, row['version'], lambda r: r.update(status='UNKNOWN', error_code='SYNC_WRITE_OUTCOME_UNKNOWN_NO_AUTOMATIC_RETRY'))
            self._bounded(state, row['channel_id'])

    def apply(self, ctx, mid, body, reauthorize=lambda: None, *, save_document=None, archive_chapter=None, create_chapter=None):
        value = ApplyIn.model_validate(body); row = self._owned(ctx, self.INBOX, mid); check_version(row, value.expected_version)
        if row['status'] != 'PENDING_REVIEW': raise ValueError('SYNC_MESSAGE_ALREADY_CLAIMED_NO_AUTOMATIC_RETRY')
        plan = self._review(ctx, row, value.choices)
        if plan['preview_digest'] != value.preview_digest: raise StaleSourceError('SYNC_REVIEW_CHANGED')
        if not plan['can_apply']: raise ValueError('SYNC_UNRESOLVED_OR_BLOCKED')
        old, desired = plan['current'], plan['desired']; cid = row['target_chapter_id']
        kind = 'CREATE' if not old else 'ARCHIVE' if desired is None else 'SAVE'
        if not {'CREATE': create_chapter, 'ARCHIVE': archive_chapter, 'SAVE': save_document}[kind]: raise ValueError('SYNC_ORIGINAL_WRITER_REQUIRED')
        reauthorize()
        with self.store.transaction(ctx.novel_id, ctx.scope) as state:
            stored = state['collections'][self.INBOX][mid]; check_version(stored, value.expected_version)
            if self._review(ctx, stored, value.choices)['preview_digest'] != value.preview_digest: raise StaleSourceError('SYNC_REVIEW_CHANGED')
            created_ids = [r['id'] for r in authorized_chapter_rows(ctx, self.source_reader, self.chapters)] if not old else []
            advance(stored, ctx.actor, value.expected_version, lambda r: r.update(status='CLAIMED', checkpoint=old, intent=desired,
                created_ids=created_ids, journal=[{'kind': kind, 'status': 'CLAIMED', 'at': now()}]))
            self._bounded(state, row['channel_id']); reauthorize()
        try:
            with self.store.transaction(ctx.novel_id, ctx.scope) as state:
                stored = state['collections'][self.INBOX][mid]
                channel = self._channel(ctx, row['channel_id'])
                self._selection_guard(channel, cid, row['envelope']['source_chapter_id'])
                check_version(stored, value.expected_version + 1)
                if stored['status'] != 'CLAIMED': raise ValueError('SYNC_MESSAGE_ALREADY_RESOLVED_NO_REPLAY')
                reauthorize()
                if old and self._chapter(ctx, cid) != old: raise StaleSourceError('SYNC_FINAL_SOURCE_CHANGED')
                if old: assert_ai_locks(old['document'], desired['document'] if desired else {'type': 'doc', 'content': []})
                if kind == 'CREATE': result = create_chapter(ctx.novel_id, desired['title'], deepcopy(desired['document']))
                elif kind == 'ARCHIVE': result = archive_chapter(cid, old['version'])
                else: result = save_document(cid, deepcopy(desired['document']), old['version'], 'OFFLINE_SYNC_REVIEW')
                self._channel(ctx, row['channel_id']); reauthorize()
                new_cid = result['id']; actual = self._chapter(ctx, new_cid)
                if not self._matches(actual, desired): raise ValueError('SYNC_WRITER_RECEIPT_MISMATCH')
                return self._finish_row(ctx, state, stored, new_cid, actual['version'], True, value.expected_version + 1, reauthorize)
        except Exception:
            self._mark_unknown(ctx, mid)
            raise

    @staticmethod
    def _matches(current, desired):
        return current['archived'] if desired is None else not current['archived'] and current['document'] == desired['document']

    def _finish(self, ctx, mid, cid, version, confirmed, expected_version, reauthorize):
        with self.store.transaction(ctx.novel_id, ctx.scope) as state:
            row = state['collections'][self.INBOX][mid]
            return self._finish_row(ctx, state, row, cid, version, confirmed, expected_version, reauthorize)

    def _finish_row(self, ctx, state, row, cid, version, confirmed, expected_version, reauthorize):
        channel = state['collections'][self.CHANNELS][row['channel_id']]
        check_version(row, expected_version)
        if row['status'] not in {'CLAIMED', 'UNKNOWN'}: raise ValueError('SYNC_RECOVERY_ALREADY_RESOLVED')
        self._selection_guard(channel, row['target_chapter_id'], row['envelope']['source_chapter_id'])
        actual = self._chapter(ctx, cid)
        if actual['version'] != version or not self._matches(actual, row['intent']): raise StaleSourceError('SYNC_FINAL_RECEIPT_CHANGED')
        reauthorize()
        if row['target_chapter_id'] is None:
            if cid in channel['baseline'] or cid in row['created_ids'] or len(channel['baseline']) >= 20:
                raise ValueError('SYNC_NEW_TARGET_ALREADY_SELECTED_OR_LIMIT_MANUAL_CLOSE_REQUIRED')
            channel['chapter_ids'].append(cid); channel['baseline'][cid] = row['envelope']['base']
            channel['bindings'][row['envelope']['source_chapter_id']] = {'chapter_id': cid, 'base_digest': digest(row['envelope']['base'])}
            advance(channel, ctx.actor, channel['version'], lambda r: None)
        advance(row, ctx.actor, row['version'], lambda r: r.update(status='APPLIED' if confirmed else 'RECONCILED', target_chapter_id=cid,
            result_version=version, journal=[{**r['journal'][0], 'status': 'RECEIPT_CONFIRMED' if confirmed else 'MANUALLY_ADOPTED'}]))
        self._bounded(state, row['channel_id']); reauthorize(); return self._summary(row)

    def recover(self, ctx, mid, body, reauthorize=lambda: None):
        value = RecoverIn.model_validate(body); row = self._owned(ctx, self.INBOX, mid); check_version(row, value.expected_version)
        self._channel(ctx, row['channel_id'])
        if row['status'] not in {'CLAIMED', 'UNKNOWN'}: raise ValueError('SYNC_RECOVERY_NOT_REQUIRED')
        cid = row['target_chapter_id']; observations = []
        ids = [cid] if cid else [r['id'] for r in authorized_chapter_rows(ctx, self.source_reader, self.chapters) if r['id'] not in row['created_ids']]
        for key in ids:
            try: current = self._chapter(ctx, key)
            except FileNotFoundError: continue
            match = self._matches(current, row['intent'])
            state = 'MATCHES_INTENT_UNCONFIRMED' if match else 'CHECKPOINT_UNCHANGED' if current == row['checkpoint'] else 'DIVERGED_OR_PARTIAL'
            observations.append({'chapter_id': key, 'version': current['version'], 'state': state, 'document': current['document']})
        result = {'id': mid, 'version': row['version'], 'status': row['status'], 'observations': observations,
                  'can_adopt': len(observations) == 1 and observations[0]['state'] == 'MATCHES_INTENT_UNCONFIRMED',
                  'retry_allowed': False, 'recovery': 'Inspect original editor/history. Partial additions are retained. Never replay an uncertain create or save.'}
        try: self._selection_guard(self._channel(ctx, row['channel_id']), cid, row['envelope']['source_chapter_id'])
        except ValueError:
            result['can_adopt'] = False; result['selection_withdrawn'] = True
        if not cid and any(item['chapter_id'] in self._channel(ctx, row['channel_id'])['baseline'] for item in observations):
            result['can_adopt'] = False; result['target_already_selected'] = True
        result['preview_digest'] = digest(result); reauthorize()
        if value.adopt_matching_result and value.close_without_replay: raise ValueError('SYNC_ONE_RECOVERY_ACTION_REQUIRED')
        if value.close_without_replay:
            if value.preview_digest != result['preview_digest']: raise StaleSourceError('SYNC_RECOVERY_CHANGED')
            # An explicit resolution, not proof that no write happened. Retain
            # candidates/checkpoint/partial additions. A fresh message gets a
            # fresh current-source review; this message can never run again.
            with self.store.transaction(ctx.novel_id, ctx.scope) as state:
                stored = state['collections'][self.INBOX][mid]; check_version(stored, value.expected_version)
                self._channel(ctx, stored['channel_id']); reauthorize()
                advance(stored, ctx.actor, value.expected_version, lambda r: r.update(status='CLOSED_WITHOUT_REPLAY'))
                return self._summary(stored)
        if value.adopt_matching_result:
            if not result['can_adopt'] or value.preview_digest != result['preview_digest']: raise StaleSourceError('SYNC_RECOVERY_CHANGED_OR_NOT_EXACT')
            item = observations[0]; return self._finish(ctx, mid, item['chapter_id'], item['version'], confirmed=False, expected_version=value.expected_version, reauthorize=reauthorize)
        return result
