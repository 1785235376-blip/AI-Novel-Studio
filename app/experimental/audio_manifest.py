"""Manual, non-replayable manifests for original reviewed Studio Audio results.

No execution, review, candidate promotion or new audio owner lives here.
"""
from __future__ import annotations

import copy
import hashlib
from contextlib import ExitStack
from uuid import uuid4
from pydantic import Field, field_validator

from .media import StrictModel
from .common import StaleSourceError, now
from .store import canonical
from ..creative.project_store import BINDING
from ..creative.workspace import FLAG

COLLECTION = 'studio_audio_manifests_v1'
CONTRACT = 'studio-audio-manifest/1'


def digest(value):
    return hashlib.sha256(canonical(value).encode('utf-8')).hexdigest()


class AudioManifestInput(StrictModel):
    job_id: str = Field(min_length=1, max_length=240, pattern=r'^[A-Za-z0-9][A-Za-z0-9_-]*$')
    expected_job_version: int = Field(ge=1, strict=True)
    reviewed_capture_digest: str = Field(pattern=r'^[a-f0-9]{64}$')
    request_id: str = Field(min_length=1, max_length=100, pattern=r'^[A-Za-z0-9][A-Za-z0-9_-]*$')
    confirmed: bool = Field(strict=True)

    @field_validator('confirmed')
    @classmethod
    def explicit_confirmation(cls, value):
        if not value: raise ValueError('AUDIO_MANIFEST_CONFIRMATION_REQUIRED')
        return value


class AudioManifestService:
    MAX_MANIFESTS = 64

    def __init__(self, production):
        self.production, self.store, self.workspace = production, production.store, production.workspace

    def _context(self, nid, scope, actor, guard):
        return self.production._base(nid, scope, actor, guard)

    @staticmethod
    def _source_pin(source):
        return {key: copy.deepcopy(source[key]) for key in ('id', 'kind', 'asset_kind', 'version', 'digest') if key in source}

    def _capture(self, nid, scope, actor, jid, guard):
        job = self.production.get(nid, scope, actor, 'audio', jid, guard)
        if job.get('status') != 'APPROVED' or job.get('review_state') != 'ORIGINAL_OWNER_REVIEWED':
            raise ValueError('AUDIO_MANIFEST_REVIEWED_RESULT_REQUIRED')
        # Original candidate read verifies formal promotion provenance, exact
        # asset version, current incarnation, output bytes and current authority.
        asset, _ = self.production.candidate(nid, scope, actor, 'audio', jid, guard)
        for snapshot in job['sources']:
            self.production.source(nid, scope, snapshot, guard)
        latest = self.production.get(nid, scope, actor, 'audio', jid, guard)
        if latest != job or asset.get('kind') != 'audio' or asset.get('deleted_at'):
            raise StaleSourceError('AUDIO_MANIFEST_RESULT_CHANGED')
        output = job.get('output_candidate') or {}
        if (asset['id'], asset['version'], asset['sha256']) != (output.get('id'), job.get('approved_asset_version'), output.get('digest')):
            raise StaleSourceError('AUDIO_MANIFEST_FORMAL_ASSET_CHANGED')
        capture = {
            'contract': 'studio-audio-manifest-capture/1',
            'job': {key: copy.deepcopy(job[key]) for key in ('id', 'version', 'request_id', 'request_digest', 'receipt_digest', 'operation_id')},
            'result': {'review_state': 'ORIGINAL_OWNER_REVIEWED', 'output_digest': output['digest']},
            'asset': {'id': asset['id'], 'version': asset['version'], 'digest': asset['sha256'], 'kind': 'audio'},
            'sources': [self._source_pin(source) for source in job['sources']],
            'environment': {'state': 'UNKNOWN', 'model_hash': None, 'runtime': None, 'hardware': None},
            'replay': {'supported': False, 'reason': 'NOT_IN_THIS_SLICE'},
        }
        guard()
        return {'capture': capture, 'capture_digest': digest(capture)}

    def results(self, nid, scope, actor, guard):
        with self.store.existing_owner_only():
            rows = self.production.list(nid, scope, actor, guard)['items']
            items = [{'id': row['id'], 'version': row['version'], 'operation_id': row['operation_id']}
                     for row in rows if row['owner'] == 'audio' and row['status'] == 'APPROVED'
                     and row['review_state'] == 'ORIGINAL_OWNER_REVIEWED']
            guard()
            return {'contract': 'studio-audio-manifest-results/1', 'items': items[:64], 'replayable': False}

    def preview(self, nid, scope, actor, jid, guard):
        with self.store.existing_owner_only():
            return self._capture(nid, scope, actor, jid, guard)

    @staticmethod
    def _owned(row, context):
        return isinstance(row, dict) and all(row.get(key) == expected for key, expected in (
            ('_actor', context['actor']), ('_scope', context['scope_key']), (BINDING, context['incarnation'])))

    @staticmethod
    def _public(row):
        value = {key: copy.deepcopy(row[key]) for key in (
            'contract', 'id', 'version', 'created_at', 'request_id', 'capture', 'capture_digest', 'replayable')}
        return {**value, 'manifest_digest': digest(value)}

    def _validate(self, nid, scope, actor, row, guard):
        if row.get('contract') != CONTRACT or row.get('manifest_digest') != self._public(row)['manifest_digest']:
            raise ValueError('AUDIO_MANIFEST_RECORD_INVALID')
        current = self._capture(nid, scope, actor, row['capture']['job']['id'], guard)
        if current != {'capture': row['capture'], 'capture_digest': row['capture_digest']}:
            raise StaleSourceError('AUDIO_MANIFEST_SOURCE_CHANGED')
        return self._public(row)

    def list(self, nid, scope, actor, guard):
        with self.store.existing_owner_only():
            context = self._context(nid, scope, actor, guard)
            records = self.store.read(nid, scope)['collections'].get(COLLECTION, {})
            rows = [row for row in records.values() if self._owned(row, context)]
            if len(rows) > self.MAX_MANIFESTS:
                raise ValueError('AUDIO_MANIFEST_STORAGE_LIMIT')
            items = [self._validate(nid, scope, actor, row, guard) for row in rows]
            guard()
            return {'contract': 'studio-audio-manifest-list/1', 'items': sorted(items, key=lambda row: (row['created_at'], row['id']), reverse=True)}

    def get(self, nid, scope, actor, mid, guard):
        with self.store.existing_owner_only():
            context = self._context(nid, scope, actor, guard)
            row = self.store.read(nid, scope)['collections'].get(COLLECTION, {}).get(mid)
            if not self._owned(row, context):
                raise FileNotFoundError('AUDIO_MANIFEST_UNAVAILABLE')
            result = self._validate(nid, scope, actor, row, guard)
            guard()
            return result

    def record(self, nid, scope, actor, value, guard):
        body = AudioManifestInput.model_validate(value)
        with self.store.existing_owner_only():
            context = self._context(nid, scope, actor, guard)
            preview = self._capture(nid, scope, actor, body.job_id, guard)
            capture = preview['capture']
            if body.expected_job_version != capture['job']['version'] or body.reviewed_capture_digest != preview['capture_digest']:
                raise StaleSourceError('AUDIO_MANIFEST_PREVIEW_CHANGED')
            audio = self.production._audio(scope, actor)
            # Original queue -> scope -> asset -> project lock order. Keep the
            # asset/project leases through the existing scope's atomic commit.
            # This new collection explicitly filters its own incarnation; no
            # shared collection registry or authorization core is changed.
            with audio.store._lock:
                with ExitStack() as lifecycle:
                    with self.store.store.transaction(nid, scope) as document:
                        raw_job, job_context = self.production._row(nid, scope, actor, 'audio', body.job_id, guard)
                        job = self.production.view(raw_job, 'audio')
                        if any(job.get(key) != capture['job'][key] for key in capture['job']) or job.get('status') != 'APPROVED':
                            raise StaleSourceError('AUDIO_MANIFEST_JOB_CHANGED')
                        # Creative-document sources are fenced by the scope
                        # transaction; final asset source checks follow below.
                        for source in job['sources']:
                            if source['kind'] != 'ASSET':
                                self.production.source(nid, scope, source, guard)
                        lifecycle.enter_context(self.workspace._asset_scope(nid, scope))
                        if self.store.incarnation(nid) != context['incarnation']:
                            raise StaleSourceError('AUDIO_MANIFEST_OWNER_CHANGED')
                        for pin in [capture['asset'], *[source for source in capture['sources'] if source['kind'] == 'ASSET']]:
                            asset = self.workspace._row(nid, scope, pin['id'])
                            kind = pin.get('asset_kind', 'audio')
                            if (asset['version'], asset['sha256'], asset['kind']) != (pin['version'], pin['digest'], kind):
                                raise StaleSourceError('AUDIO_MANIFEST_ASSET_CHANGED')
                            data = self.workspace.assets.content(asset['id'], branch_id=scope.get('branch_id'))
                            if hashlib.sha256(data).hexdigest() != pin['digest']:
                                raise StaleSourceError('AUDIO_MANIFEST_BYTES_CHANGED')
                            if pin is capture['asset'] and (
                                asset.get('_owner_actor_id') is not None or asset.get('source_job_id') != body.job_id
                                or asset.get('_required_features') != [FLAG]
                                or asset.get('_origin_provenance') != self.production._approved_media_provenance(raw_job, 'audio', actor)
                                or asset.get('_studio_result_origin') != self.production._media_result_origin(job_context, body.job_id)
                                or asset.get('_project_binding') != {'novel_id': nid, 'branch_id': scope.get('branch_id'),
                                    'scope_key': context['scope_key'], 'incarnation': context['incarnation']}):
                                raise StaleSourceError('AUDIO_MANIFEST_FORMAL_PROOF_CHANGED')
                        records = document['collections'].setdefault(COLLECTION, {})
                        owned = [row for row in records.values() if self._owned(row, context)]
                        prior = next((row for row in owned if row['request_id'] == body.request_id), None)
                        request_digest = digest(body.model_dump())
                        if prior is not None:
                            if prior['_request_digest'] != request_digest or prior['capture'] != capture:
                                raise ValueError('AUDIO_MANIFEST_IDEMPOTENCY_CONFLICT')
                            result = self._public(prior)
                        else:
                            if len(owned) >= self.MAX_MANIFESTS:
                                raise ValueError('AUDIO_MANIFEST_STORAGE_LIMIT')
                            row = {'contract': CONTRACT, 'id': str(uuid4()), 'version': 1, 'created_at': now(),
                                   'request_id': body.request_id, **preview, 'replayable': False,
                                   '_actor': actor, '_scope': context['scope_key'], BINDING: context['incarnation'],
                                   '_request_digest': request_digest}
                            row['manifest_digest'] = self._public(row)['manifest_digest']
                            records[row['id']] = row
                            result = self._public(row)
                        guard()
                    # Authority is checked by the route again before projection.
            guard()
            return result
