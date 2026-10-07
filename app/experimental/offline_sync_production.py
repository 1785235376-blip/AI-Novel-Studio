"""Bounded production-sync engineering under the existing OfflineSyncService.

Manifests/deltas are durable immutable evidence, not another document owner.
Transfers reference the original reviewed outbox/inbox and never auto-apply a
manuscript. Only an injected local synthetic transport can deliver. No cloud
endpoint, credential lifecycle, production encryption or background retry exists.
"""
from __future__ import annotations

from copy import deepcopy
from threading import RLock
from time import time
from uuid import uuid4
from typing import Literal, Protocol

from pydantic import Field

from .common import check_version, new_row, StaleSourceError
from .offline_sync import ID, SHA, SyncInput, safe_snapshot, MAX_BYTES
from .planning import digest
from .project_forks import advance
from .store import canonical

FEATURE = 'production_sync_v1'
MAX_JOURNAL_BYTES = 8 * 1024 * 1024


class DeviceIn(SyncInput):
    device_id: str = Field(pattern=ID)
    label: str = Field(min_length=1, max_length=100)


class VersionIn(SyncInput):
    expected_version: int = Field(ge=1)


class ManifestIn(SyncInput):
    channel_id: str = Field(pattern=ID)
    channel_version: int = Field(ge=1)
    device_id: str = Field(pattern=ID)
    request_id: str = Field(pattern=ID)
    base_manifest_id: str | None = Field(default=None, pattern=ID)


class TransferIn(SyncInput):
    manifest_id: str = Field(pattern=ID)
    message_ids: list[str] = Field(min_length=1, max_length=20)
    request_id: str = Field(pattern=ID)
    acknowledge_copy_boundary: Literal[True]


class TransferActionIn(VersionIn):
    action: Literal['dispatch', 'resume', 'cancel']


class EncryptionAdapter(Protocol):
    """Production implementation must authenticate scope, peer and sequence.

    The adapter owns secure key material outside this metadata store. This API
    accepts only a non-secret key reference. No built-in production cipher exists.
    """
    name: str
    production_verified: bool
    def seal(self, payload: bytes, *, associated_data: bytes, key_reference: str) -> bytes: ...
    def open(self, payload: bytes, *, associated_data: bytes, key_reference: str) -> bytes: ...
    def revoke(self, key_reference: str) -> None: ...


class SyntheticPlaintextEncryption:
    """Contract fixture ONLY. Digest consistency is not authentication or encryption."""
    name = 'SYNTHETIC_PLAINTEXT_NOT_ENCRYPTION'
    production_verified = False

    def __init__(self): self.revoked = set()

    def seal(self, payload, *, associated_data, key_reference):
        if key_reference in self.revoked: raise ValueError('SYNC_KEY_REFERENCE_REVOKED')
        if len(payload) > MAX_BYTES: raise ValueError('SYNC_ENCRYPTION_PAYLOAD_LIMIT')
        return canonical({'payload_hex': payload.hex(), 'aad_digest': digest(associated_data.hex()), 'key_reference': key_reference}).encode()

    def open(self, payload, *, associated_data, key_reference):
        import json
        if key_reference in self.revoked: raise ValueError('SYNC_KEY_REFERENCE_REVOKED')
        if len(payload) > 2 * MAX_BYTES + 4096: raise ValueError('SYNC_ENCRYPTION_PAYLOAD_LIMIT')
        value = json.loads(payload)
        if value.get('aad_digest') != digest(associated_data.hex()) or value.get('key_reference') != key_reference:
            raise ValueError('SYNC_ENCRYPTION_ASSOCIATED_DATA_MISMATCH')
        return bytes.fromhex(value['payload_hex'])

    def revoke(self, key_reference): self.revoked.add(key_reference)


class SyntheticSyncTransport:
    """Explicit in-process route registry. No socket, HTTP or cloud behavior.

    Receiver authorization is rerun even on duplicate delivery; original inbox
    receive owns idempotency and content equality, not this transport cache.
    """
    name = 'SYNTHETIC_IN_PROCESS_TRANSPORT'

    def __init__(self): self.routes, self._lock = {}, RLock()

    def bind(self, endpoint_id, receive, guard):
        guard()
        with self._lock:
            if len(self.routes) >= 100: raise ValueError('SYNC_SYNTHETIC_ROUTE_LIMIT')
            self.routes[endpoint_id] = (receive, guard)

    def unbind(self, endpoint_id):
        with self._lock: self.routes.pop(endpoint_id, None)

    def send(self, endpoint_id, envelope):
        with self._lock: route = self.routes.get(endpoint_id)
        if route is None: raise ConnectionError('SYNC_SYNTHETIC_PEER_DISCONNECTED')
        receive, guard = route
        guard()
        result = receive(deepcopy(envelope))
        guard()
        if not isinstance(result, dict) or not isinstance(result.get('receipt'), dict): raise ValueError('SYNC_TRANSPORT_RECEIPT_REQUIRED')
        return deepcopy(result['receipt'])


def build_delta(base, current):
    """Deterministic rich top-level block splice plus title change.

    Empty/missing content is normalized only by the existing safe_snapshot
    contract. Every reconstruction must exactly match the target digest.
    """
    if current is None:
        return {'schema': 'novel-sync-delta/1', 'kind': 'TOMBSTONE', 'base_digest': digest(base), 'target_digest': digest(None)}
    current = safe_snapshot(current)
    if base is None:
        return {'schema': 'novel-sync-delta/1', 'kind': 'SNAPSHOT', 'base_digest': digest(None), 'target_digest': digest(current), 'snapshot': current}
    base = safe_snapshot(base)
    left, right = base['document'].get('content', []), current['document'].get('content', [])
    # Preserve document-root metadata; this is an exact delta, not text flattening.
    prefix = 0
    while prefix < min(len(left), len(right)) and left[prefix] == right[prefix]: prefix += 1
    suffix = 0
    while suffix < min(len(left) - prefix, len(right) - prefix) and left[-1 - suffix] == right[-1 - suffix]: suffix += 1
    return {'schema': 'novel-sync-delta/1', 'kind': 'BLOCK_SPLICE', 'base_digest': digest(base), 'target_digest': digest(current),
            'title': current['title'], 'content_present': 'content' in current['document'], 'document_root': {k: deepcopy(v) for k, v in current['document'].items() if k != 'content'},
            'start': prefix, 'delete_count': len(left) - prefix - suffix,
            'blocks': deepcopy(right[prefix:len(right) - suffix if suffix else len(right)])}


def apply_delta(base, delta):
    if not isinstance(delta, dict) or delta.get('schema') != 'novel-sync-delta/1' or delta.get('base_digest') != digest(base):
        raise StaleSourceError('SYNC_DELTA_BASE_MISMATCH')
    if delta.get('kind') == 'TOMBSTONE': result = None
    elif delta.get('kind') == 'SNAPSHOT': result = safe_snapshot(delta['snapshot'])
    elif delta.get('kind') == 'BLOCK_SPLICE':
        base = safe_snapshot(base); blocks = deepcopy(base['document'].get('content', []))
        start, delete = delta.get('start'), delta.get('delete_count')
        if type(start) is not int or type(delete) is not int or start < 0 or delete < 0 or start + delete > len(blocks): raise ValueError('SYNC_DELTA_RANGE_INVALID')
        if not isinstance(delta.get('blocks'), list) or len(delta['blocks']) > 1000: raise ValueError('SYNC_DELTA_BLOCK_LIMIT')
        blocks[start:start + delete] = deepcopy(delta['blocks'])
        if type(delta.get('content_present')) is not bool: raise ValueError('SYNC_DELTA_ROOT_SHAPE_INVALID')
        document = deepcopy(delta['document_root'])
        if delta['content_present']: document['content'] = blocks
        elif blocks: raise ValueError('SYNC_DELTA_ROOT_SHAPE_INVALID')
        result = safe_snapshot({'title': delta['title'], 'document': document})
    else: raise ValueError('SYNC_DELTA_KIND_INVALID')
    if digest(result) != delta.get('target_digest'): raise ValueError('SYNC_DELTA_TARGET_MISMATCH')
    return result


class ProductionSync:
    DEVICES = 'offline_sync_devices_v1'
    MANIFESTS = 'offline_sync_manifests_v1'
    TRANSFERS = 'offline_sync_transfers_v1'

    def __init__(self, owner, *, transport=None, encryption=None, clock=time):
        self.owner, self.transport, self.encryption, self.clock = owner, transport, encryption, clock

    @property
    def store(self): return self.owner.store

    def _guard(self, ctx, check):
        self.owner._local(ctx)
        self.owner.novels.get(ctx.novel_id); check()

    def _row(self, ctx, collection, rid, state=None):
        row = (state or self.store.read(ctx.novel_id, ctx.scope))['collections'].get(collection, {}).get(rid)
        if row is None or row.get('scope') != ctx.scope or row.get('novel_id') != ctx.novel_id or row.get('created_by') != ctx.actor:
            raise FileNotFoundError(rid)
        return row

    def _device(self, ctx, device_id, state=None):
        rows = (state or self.store.read(ctx.novel_id, ctx.scope))['collections'].get(self.DEVICES, {}).values()
        row = next((r for r in rows if r.get('created_by') == ctx.actor and r['device_id'] == device_id), None)
        if row is None: raise FileNotFoundError(device_id)
        self._row(ctx, self.DEVICES, row['id'], state)
        if row['status'] != 'ACTIVE': raise ValueError('SYNC_DEVICE_REVOKED')
        return row

    def _bounded(self, state):
        names = (self.DEVICES, self.MANIFESTS, self.TRANSFERS)
        if len(state['collections'].get(self.DEVICES, {})) > 20 or any(len(state['collections'].get(n, {})) > 100 for n in names[1:]):
            raise ValueError('SYNC_PRODUCTION_JOURNAL_CAPACITY')
        if len(canonical({n: state['collections'].get(n, {}) for n in names}).encode()) > MAX_JOURNAL_BYTES:
            raise ValueError('SYNC_PRODUCTION_JOURNAL_BYTES_LIMIT')

    @staticmethod
    def _public(row):
        return {k: deepcopy(v) for k, v in row.items() if k not in {'history', 'scope', 'snapshots', 'worker_token', 'change_set'}}

    def contract(self, ctx, check=lambda: None):
        self._guard(ctx, check)
        return {'schema': 'novel-production-sync/1', 'state': 'PARTIAL', 'cloud': 'NOT_CONFIGURED',
                'transport': self.transport.name if self.transport else 'NOT_CONFIGURED',
                'encryption': 'NOT_CONFIGURED' if self.encryption is None else 'MOCK_ONLY',
                'network_enabled': False, 'automatic_apply': False, 'automatic_retry': False,
                'transport_confidentiality': 'PLAINTEXT_LOCAL_ONLY', 'encryption_applied_to_transfers': False,
                'encryption_interface': 'SEAL_OPEN_ASSOCIATED_DATA_KEY_REFERENCE_REVOKE',
                'delta': 'EXACT_RICH_BLOCK_SPLICE_CONTRACT', 'wire_payload': 'EXISTING_REVIEWED_SNAPSHOT_V1',
                'scope': 'EXPLICIT_LOCAL_CHANNEL_SELECTION', 'branch_sync': 'NOT_CONFIGURED',
                'device_identity': 'PUBLIC_LOCAL_ROUTING_ID_NOT_AUTHENTICATION',
                'revocation': 'PREVENT_FUTURE_DELIVERY_CANNOT_RECALL_COPIES',
                'restart': 'EXPLICIT_RESUME_AFTER_WORKER_LEASE_FROM_DURABLE_RECEIPT_CHECKPOINT',
                'reconciliation': 'ORIGINAL_INBOX_REVIEW_DIFF3_AND_CHAPTER_CAS', 'feature': FEATURE}

    def records(self, ctx, check=lambda: None):
        self._guard(ctx, check)
        state = self.store.read(ctx.novel_id, ctx.scope)
        for name in (self.DEVICES, self.MANIFESTS, self.TRANSFERS):
            if any(r.get('scope') != ctx.scope or r.get('novel_id') != ctx.novel_id for r in state['collections'].get(name, {}).values()):
                raise ValueError('SYNC_RECORD_SCOPE_MISMATCH')
        result = {label: [self._public(r) for r in state['collections'].get(name, {}).values() if r['created_by'] == ctx.actor]
                  for label, name in [('devices', self.DEVICES), ('manifests', self.MANIFESTS), ('transfers', self.TRANSFERS)]}
        check(); return result

    def register_device(self, ctx, body, check=lambda: None):
        value = DeviceIn.model_validate(body); self._guard(ctx, check)
        with self.store.transaction(ctx.novel_id, ctx.scope) as state:
            rows = state['collections'].setdefault(self.DEVICES, {})
            old = next((r for r in rows.values() if r['device_id'] == value.device_id and r['created_by'] == ctx.actor), None)
            if old:
                if old['status'] != 'ACTIVE': raise ValueError('SYNC_DEVICE_REVOKED_USE_NEW_ID')
                if old['label'] != value.label: raise ValueError('SYNC_DEVICE_IDENTITY_CHANGED')
                return self._public(old)
            row = new_row(ctx.novel_id, ctx.scope, ctx.actor, {**value.model_dump(), 'status': 'ACTIVE', 'identity_epoch': 1})
            rows[row['id']] = row; self._bounded(state); check()
            return self._public(row)

    def revoke_device(self, ctx, rid, body, check=lambda: None):
        value = VersionIn.model_validate(body); self._guard(ctx, check)
        with self.store.transaction(ctx.novel_id, ctx.scope) as state:
            row = self._row(ctx, self.DEVICES, rid, state); check_version(row, value.expected_version)
            if row['status'] != 'ACTIVE': raise ValueError('SYNC_DEVICE_ALREADY_REVOKED')
            advance(row, ctx.actor, row['version'], lambda r: r.update(status='REVOKED', identity_epoch=r['identity_epoch'] + 1))
            for transfer in state['collections'].get(self.TRANSFERS, {}).values():
                if transfer['device_id'] == row['device_id'] and transfer['created_by'] == ctx.actor and transfer['status'] not in {'COMPLETED', 'CANCELLED', 'REVOKED'}:
                    advance(transfer, ctx.actor, transfer['version'], lambda r: r.update(status='REVOKED'))
            check(); return self._public(row)

    def manifest(self, ctx, body, check=lambda: None):
        value = ManifestIn.model_validate(body); self._guard(ctx, check)
        request_digest = digest(value.model_dump())
        with self.store.transaction(ctx.novel_id, ctx.scope) as state:
            device = self._device(ctx, value.device_id, state)
            channel = self.owner._channel(ctx, value.channel_id); check_version(channel, value.channel_version)
            rows = state['collections'].setdefault(self.MANIFESTS, {})
            old = next((r for r in rows.values() if r['request_id'] == value.request_id and r['created_by'] == ctx.actor), None)
            if old:
                if old['request_digest'] != request_digest: raise ValueError('SYNC_MANIFEST_IDEMPOTENCY_MISMATCH')
                return self.manifest_detail(ctx, old['id'], check)
            base = self._row(ctx, self.MANIFESTS, value.base_manifest_id, state) if value.base_manifest_id else None
            if base:
                self._manifest_integrity(ctx, base)
                if base['channel_id'] != channel['id'] or base['device_id'] != device['device_id']: raise ValueError('SYNC_MANIFEST_SCOPE_MISMATCH')
            snapshots, objects, changes = {}, [], []
            for cid in channel['chapter_ids']:
                current = self.owner._chapter(ctx, cid)
                snapshot = None if current['archived'] else self.owner._snapshot(current)
                previous = base['snapshots'].get(cid) if base else channel['baseline'].get(cid)
                delta = build_delta(previous, snapshot)
                if apply_delta(previous, delta) != snapshot: raise ValueError('SYNC_DELTA_RECONSTRUCTION_MISMATCH')
                snapshots[cid] = snapshot
                metadata = {'object_id': cid, 'kind': 'CHAPTER', 'version': current['version'], 'digest': digest(snapshot),
                            'bytes': len(canonical(snapshot).encode()), 'tombstone': snapshot is None, 'privacy_level': 'LOCAL_ONLY'}
                objects.append(metadata)
                if digest(previous) != digest(snapshot): changes.append({'object_id': cid, 'source_version': current['version'], 'delta': delta})
            row = new_row(ctx.novel_id, ctx.scope, ctx.actor, {**value.model_dump(), 'status': 'SEALED', 'schema': 'novel-sync-manifest/1',
                'request_digest': request_digest, 'device_epoch': device['identity_epoch'], 'scope_digest': self.store.key(ctx.novel_id, ctx.scope),
                'objects': objects, 'change_set': changes, 'snapshots': snapshots, 'manifest_version': base['manifest_version'] + 1 if base else 1})
            row['manifest_digest'] = digest({k: row[k] for k in ('schema', 'channel_id', 'device_id', 'device_epoch', 'scope_digest', 'objects', 'change_set', 'manifest_version')})
            rows[row['id']] = row; self._bounded(state); check()
            return self.manifest_detail(ctx, row['id'], check)

    def manifest_detail(self, ctx, rid, check=lambda: None):
        self._guard(ctx, check)
        row = self._row(ctx, self.MANIFESTS, rid)
        self._manifest_integrity(ctx, row)
        stale = False
        for obj in row['objects']:
            current = self.owner._chapter(ctx, obj['object_id'])
            current_snapshot = None if current['archived'] else self.owner._snapshot(current)
            stale = stale or current['version'] != obj['version'] or digest(current_snapshot) != obj['digest']
        check()
        return {**self._public(row), 'change_set': deepcopy(row['change_set']), 'source_state': 'STALE' if stale else 'CURRENT'}

    def _manifest_integrity(self, ctx, manifest):
        expected = digest({k: manifest[k] for k in ('schema', 'channel_id', 'device_id', 'device_epoch', 'scope_digest', 'objects', 'change_set', 'manifest_version')})
        if manifest['manifest_digest'] != expected or manifest['scope_digest'] != self.store.key(ctx.novel_id, ctx.scope):
            raise ValueError('SYNC_MANIFEST_INTEGRITY_MISMATCH')
        if any(obj['digest'] != digest(manifest['snapshots'].get(obj['object_id'])) for obj in manifest['objects']):
            raise ValueError('SYNC_MANIFEST_SNAPSHOT_INTEGRITY_MISMATCH')

    def _validate_manifest(self, ctx, manifest, state):
        self._manifest_integrity(ctx, manifest)
        device = self._device(ctx, manifest['device_id'], state)
        if device['identity_epoch'] != manifest['device_epoch']: raise ValueError('SYNC_DEVICE_EPOCH_CHANGED')
        channel = self.owner._channel(ctx, manifest['channel_id'])
        if set(channel['chapter_ids']) != {r['object_id'] for r in manifest['objects']}: raise StaleSourceError('SYNC_MANIFEST_SELECTION_CHANGED')
        for item in manifest['objects']:
            current = self.owner._chapter(ctx, item['object_id'])
            snapshot = None if current['archived'] else self.owner._snapshot(current)
            if current['version'] != item['version'] or digest(snapshot) != item['digest']: raise StaleSourceError('SYNC_MANIFEST_SOURCE_CHANGED')
        return channel

    def prepare_transfer(self, ctx, body, check=lambda: None):
        value = TransferIn.model_validate(body); self._guard(ctx, check)
        if len(set(value.message_ids)) != len(value.message_ids): raise ValueError('SYNC_DUPLICATE_TRANSFER_MESSAGE')
        fingerprint = digest(value.model_dump())
        with self.store.transaction(ctx.novel_id, ctx.scope) as state:
            rows = state['collections'].setdefault(self.TRANSFERS, {})
            old = next((r for r in rows.values() if r['created_by'] == ctx.actor and r['request_id'] == value.request_id), None)
            if old:
                if old['request_digest'] != fingerprint: raise ValueError('SYNC_TRANSFER_IDEMPOTENCY_MISMATCH')
                return self._public(old)
            manifest = self._row(ctx, self.MANIFESTS, value.manifest_id, state)
            channel = self._validate_manifest(ctx, manifest, state)
            messages = []
            for mid in value.message_ids:
                message = self.owner._owned(ctx, self.owner.OUTBOX, mid)
                if message['channel_id'] != channel['id']: raise ValueError('SYNC_TRANSFER_CHANNEL_MISMATCH')
                obj = next((r for r in manifest['objects'] if r['object_id'] == message['envelope']['source_chapter_id']), None)
                if obj is None or obj['version'] != message['envelope']['source_version'] or obj['digest'] != digest(message['envelope']['snapshot']):
                    raise StaleSourceError('SYNC_TRANSFER_MANIFEST_MISMATCH')
                if message['status'] not in {'PENDING', 'FAILED', 'UNKNOWN', 'ACKNOWLEDGED'}: raise ValueError('SYNC_TRANSFER_MESSAGE_UNAVAILABLE')
                messages.append(message)
            ordered = [r['id'] for r in sorted(messages, key=lambda r: r['envelope']['sequence'])]
            row = new_row(ctx.novel_id, ctx.scope, ctx.actor, {**value.model_dump(), 'status': 'PREPARED', 'message_ids': ordered,
                'request_digest': fingerprint, 'device_id': manifest['device_id'], 'channel_id': channel['id'],
                'manifest_digest': manifest['manifest_digest'], 'checkpoint': {'completed_ids': [], 'receipts': {}, 'next_index': 0},
                'attempts': 0, 'error_code': None, 'worker_token': None, 'lease_until': 0})
            rows[row['id']] = row; self._bounded(state); check()
            return self._public(row)

    def _transfer_guard(self, ctx, rid, check, worker_token=None):
        self._guard(ctx, check)
        state = self.store.read(ctx.novel_id, ctx.scope)
        row = self._row(ctx, self.TRANSFERS, rid, state)
        if row['status'] != 'RUNNING': raise ValueError('SYNC_TRANSFER_NOT_RUNNING')
        if worker_token is not None and (row['worker_token'] != worker_token or row['lease_until'] <= self.clock()):
            raise ValueError('SYNC_TRANSFER_WORKER_LEASE_LOST')
        manifest = self._row(ctx, self.MANIFESTS, row['manifest_id'], state)
        self._validate_manifest(ctx, manifest, state)
        check(); return row

    def action(self, ctx, rid, body, check=lambda: None):
        value = TransferActionIn.model_validate(body); self._guard(ctx, check)
        with self.store.transaction(ctx.novel_id, ctx.scope) as state:
            row = self._row(ctx, self.TRANSFERS, rid, state); check_version(row, value.expected_version)
            if row['status'] in {'COMPLETED', 'CANCELLED', 'REVOKED'}: raise ValueError('SYNC_TRANSFER_TERMINAL')
            if value.action == 'cancel':
                advance(row, ctx.actor, row['version'], lambda r: r.update(status='CANCELLED'))
                check(); return self._public(row)
            if value.action == 'dispatch' and row['status'] != 'PREPARED': raise ValueError('SYNC_EXPLICIT_RESUME_REQUIRED')
            if value.action == 'resume' and row['status'] not in {'RUNNING', 'PAUSED'}: raise ValueError('SYNC_TRANSFER_NOT_RESUMABLE')
            if row['status'] == 'RUNNING' and row['lease_until'] > self.clock(): raise ValueError('SYNC_TRANSFER_WORKER_LEASE_ACTIVE')
            if self.transport is None: raise ValueError('SYNC_PRODUCTION_TRANSPORT_NOT_CONFIGURED')
            if row['attempts'] >= 8: raise ValueError('SYNC_TRANSFER_RETRY_LIMIT')
            self._validate_manifest(ctx, self._row(ctx, self.MANIFESTS, row['manifest_id'], state), state)
            worker_token = uuid4().hex
            advance(row, ctx.actor, row['version'], lambda r: r.update(status='RUNNING', attempts=r['attempts'] + 1, error_code=None,
                worker_token=worker_token, lease_until=self.clock() + 30))
            check()
        try:
            for mid in row['message_ids']:
                active = self._transfer_guard(ctx, rid, check, worker_token)
                if mid in active['checkpoint']['completed_ids']: continue
                message = self.owner._owned(ctx, self.owner.OUTBOX, mid)
                if message['status'] != 'ACKNOWLEDGED':
                    exported = self.owner.export(ctx, mid, {'expected_version': message['version'], 'envelope_digest': message['envelope_digest'], 'acknowledge_copy_boundary': True},
                                                 lambda: self._transfer_guard(ctx, rid, check, worker_token))
                    self._transfer_guard(ctx, rid, check, worker_token)
                    receipt = self.transport.send(exported['envelope']['destination_endpoint'], exported['envelope'])
                    self._transfer_guard(ctx, rid, check, worker_token)
                    message = self.owner.delivery(ctx, mid, {'expected_version': exported['version'], 'state': 'ACKNOWLEDGED', 'receipt': receipt},
                                                  lambda: self._transfer_guard(ctx, rid, check, worker_token))
                # Original outbox ACK is durable. A restart before this secondary
                # checkpoint adopts the ACK without exporting/delivering again.
                original = self.owner._owned(ctx, self.owner.OUTBOX, mid)
                with self.store.transaction(ctx.novel_id, ctx.scope) as state:
                    current = self._row(ctx, self.TRANSFERS, rid, state)
                    self._transfer_guard(ctx, rid, check, worker_token)
                    checkpoint = deepcopy(current['checkpoint'])
                    checkpoint['completed_ids'].append(mid)
                    checkpoint['receipts'][mid] = self.owner._receipt(original)
                    checkpoint['next_index'] = len(checkpoint['completed_ids'])
                    advance(current, ctx.actor, current['version'], lambda r: r.update(checkpoint=checkpoint))
                    self._bounded(state); check()
            with self.store.transaction(ctx.novel_id, ctx.scope) as state:
                row = self._row(ctx, self.TRANSFERS, rid, state); self._transfer_guard(ctx, rid, check, worker_token)
                advance(row, ctx.actor, row['version'], lambda r: r.update(status='COMPLETED')); check()
                return self._public(row)
        except Exception:
            with self.store.transaction(ctx.novel_id, ctx.scope) as state:
                row = self._row(ctx, self.TRANSFERS, rid, state)
                if row['status'] == 'RUNNING' and row['worker_token'] == worker_token:
                    advance(row, ctx.actor, row['version'], lambda r: r.update(status='PAUSED', error_code='SYNC_TRANSFER_INTERRUPTED_EXPLICIT_RESUME_REQUIRED'))
            raise
