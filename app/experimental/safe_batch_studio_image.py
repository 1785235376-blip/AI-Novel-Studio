"""U16 bridge to the original Studio Host invoker and ImageJob owner.

Bindings are server-only; no public media command can supply one. This module
owns neither a queue nor an image algorithm. Host requests are context-local
and are never persisted with the batch or job.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
import re

from pydantic import Field, model_validator
from fastapi.routing import APIRoute
from fastapi import HTTPException
from .common import StaleSourceError
from .planning import StrictModel
from ..creative.production_contracts import ProductionSourceSnapshot
from ..creative.production_execution_models import MediaCommand, MediaCreate, MediaJobAction, MediaReview

from .planning import digest

CONTRACT = 'studio-image-safe-batch/1'
_request = ContextVar('studio_image_batch_request', default=None)


class StudioImageSelection(StrictModel):
    image: ProductionSourceSnapshot
    mask: ProductionSourceSnapshot
    request_id: str = Field(min_length=1, max_length=100, pattern=r'^[A-Za-z0-9][A-Za-z0-9_-]*$')
    license_note: str = Field(default='', max_length=2000)

    @model_validator(mode='after')
    def assets_only(self):
        if (self.image.kind != 'ASSET' or self.mask.kind != 'ASSET'
                or self.image.asset_kind != 'image' or self.mask.asset_kind != 'image'
                or self.image.id == self.mask.id):
            raise ValueError('BATCH_SAVED_IMAGE_AND_MASK_REQUIRED')
        return self

    def command(self):
        return MediaCommand.model_validate({'operation_id': 'm5.image.cutout', 'request_id': self.request_id,
            'provider_id': None, 'model_id': None, 'prompt': '', 'parameters': {}, 'allow_cloud': False,
            'license_note': self.license_note, 'source_snapshots': [self.image.model_dump(exclude_none=True), self.mask.model_dump(exclude_none=True)]})


@contextmanager
def request_context(request):
    token = _request.set(request)
    try:
        yield
    finally:
        _request.reset(token)


class StudioImageRequestRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()
        async def checked(request):
            with request_context(request):
                return await handler(request)
        return checked


def validate_binding(value, context):
    if value is None:
        return None
    fields = {'contract', 'batch_id', 'item_index', 'actor', 'scope_key',
              'incarnation', 'snapshot_digest', 'request_id'}
    if (not isinstance(value, dict) or set(value) != fields
            or value['contract'] != CONTRACT
            or not isinstance(value['batch_id'], str) or not 1 <= len(value['batch_id']) <= 240
            or type(value['item_index']) is not int or not 0 <= value['item_index'] < 20
            or any(value[k] != context.get(k) for k in ('actor', 'scope_key', 'incarnation', 'request_id'))
            or not isinstance(value['snapshot_digest'], str)
            or not re.fullmatch(r'[a-f0-9]{64}', value['snapshot_digest'])
            or context.get('operation_id') != 'm5.image.cutout'
            or context.get('graph_binding') is not None or context.get('benchmark_binding') is not None):
        raise ValueError('BATCH_STUDIO_IMAGE_BINDING_INVALID')
    return deepcopy(value)


class BatchStudioImageAuthority:
    def __init__(self, batches, production, invoke):
        self.batches, self.production, self.invoke = batches, production, invoke

    def call(self, ctx, permission, callback):
        request = _request.get()
        if request is None:
            raise ValueError('BATCH_STUDIO_HOST_INVOKER_REQUIRED')
        def operation(actor, scope, guard):
            if (actor, scope) != (ctx.actor, ctx.scope):
                raise ValueError('BATCH_STUDIO_AUTHORITY_CHANGED')
            return callback(guard)
        try:
            return self.invoke(request, ctx.novel_id, ctx.token, ctx.branch, permission, operation)
        except HTTPException as exc:
            # Preserve the original batch owner's per-record stale projection;
            # the original Studio invoker maps these domain errors to HTTP.
            code = exc.detail.get('code') if isinstance(exc.detail, dict) else None
            if exc.status_code == 409 and code == 'EXPERIMENTAL_SOURCE_STALE':
                message = exc.detail.get('message')
                reason = message if isinstance(message, str) and re.fullmatch(r'[A-Z][A-Z0-9_]{1,95}', message) else 'BATCH_STUDIO_IMAGE_SOURCE_CHANGED'
                raise StaleSourceError(reason) from None
            raise

    def reject_closed_audio_preflight(self, ctx, guard):
        """Check original host authority only to refuse a closed audio write."""
        request = _request.get()
        reject = getattr(self.invoke, 'reject_closed_audio_batch', None)
        if request is None or not callable(reject):
            raise ValueError('BATCH_STUDIO_HOST_INVOKER_REQUIRED')
        return reject(request, ctx.novel_id, ctx.token, ctx.branch, ctx.actor, ctx.scope, guard)

    def catalog(self, ctx):
        def read(guard):
            guard()
            rows = self.production.workspace.list_assets(ctx.novel_id, ctx.scope)['items']
            assets = [{'id': a['id'], 'title': a.get('title') or a.get('filename') or a['id'],
                'snapshot': {'id': a['id'], 'kind': 'ASSET', 'asset_kind': 'image', 'version': a['version'], 'digest': a['sha256']}}
                for a in rows if a.get('kind') == 'image' and not a.get('deleted_at')][:200]
            guard()
            return {'contract': CONTRACT, 'operation_id': 'm5.image.cutout', 'assets': assets,
                'concurrency': 1, 'max_items': 20, 'known_cost_microusd': 0, 'model': 'NONE',
                'verification': 'ORIGINAL_CPU_CUTOUT_NOT_AI', 'automatic_dispatch': False}
        return self.call(ctx, 'domain.read', read)

    def visible_sources(self, ctx, selection):
        def read(guard):
            for source in (selection.image, selection.mask):
                guard()
                self.production.workspace.asset(ctx.novel_id, ctx.scope, source.id)
            guard()
        self.call(ctx, 'domain.read', read)

    def snapshot(self, ctx, selection):
        def read(guard):
            preview, context, _ = self.production.preview(ctx.novel_id, ctx.scope, ctx.actor, selection.command(), guard)
            return {'incarnation': context['incarnation'], **preview}
        return self.call(ctx, 'domain.read', read)

    @staticmethod
    def binding(row, index, scope_key):
        config = row['snapshot']['steps'][index]['configuration']
        return {'contract': CONTRACT, 'batch_id': row['id'], 'item_index': index, 'actor': row['created_by'],
            'scope_key': scope_key, 'incarnation': config['incarnation'],
            'snapshot_digest': row['snapshot_digest'], 'request_id': config['command']['request_id']}

    def _binding(self, ctx, row, index, guard):
        scope_key = self.production._base(ctx.novel_id, ctx.scope, ctx.actor, guard)['scope_key']
        return self.binding(row, index, scope_key)

    @staticmethod
    def result(job):
        return {'image_job': deepcopy(job), 'verification': 'ORIGINAL_CPU_CUTOUT_NOT_AI'}

    def dispatch(self, ctx, row, index, guard):
        config = row['snapshot']['steps'][index]['configuration']
        def run(host_guard):
            # Full-batch preflight stays outside original queue/asset phases.
            # Within them production's metadata-only batch guard + exact source
            # guard fence stop, scope, claim and pixels without nested leases.
            host_guard(); guard()
            binding = self._binding(ctx, row, index, host_guard)
            preview = self.production.preview(ctx.novel_id, ctx.scope, ctx.actor,
                MediaCommand.model_validate(config['command']), host_guard, batch_binding=binding)[0]
            if any(preview[k] != config[k] for k in ('command', 'sources', 'execution_recipe')):
                raise ValueError('BATCH_STUDIO_IMAGE_PREVIEW_CHANGED')
            # Claim/intention precede the original create. An absent response
            # is UNKNOWN, never evidence that this key may be sent again.
            with self.batches.store.transaction(ctx.novel_id, ctx.scope) as state:
                host_guard(); guard()
                item = state['collections'][self.batches.BATCHES][row['id']]['items'][index]
                if item.get('image_create_intent') or item.get('image_job_id'):
                    raise ValueError('BATCH_STUDIO_IMAGE_ALREADY_SENT')
                item['image_create_intent'] = True
            job = self.production.create(ctx.novel_id, ctx.scope, ctx.actor,
                MediaCreate(command=MediaCommand.model_validate(config['command']), reviewed_preview_digest=preview['preview_digest']),
                host_guard, batch_binding=binding)
            with self.batches.store.transaction(ctx.novel_id, ctx.scope) as state:
                host_guard(); guard()
                item = state['collections'][self.batches.BATCHES][row['id']]['items'][index]
                item.update(image_job_id=job['id'], task_id=job['id'])
                self.batches._receipt(item, task_id=job['id'], cost_state='KNOWN_ZERO_LOCAL')
            done = self.production.execute(ctx.novel_id, ctx.scope, ctx.actor, 'image', job['id'],
                MediaJobAction(expected_version=job['version'], expected_request_digest=job['request_digest']), host_guard, batch_binding=binding)
            if done['status'] not in {'AWAITING_REVIEW', 'APPROVED'}:
                raise ValueError('BATCH_STUDIO_IMAGE_ORIGINAL_RECEIPT_REQUIRED')
            host_guard(); guard()
            return self.result(done)
        return self.call(ctx, 'domain.write', run)

    def job(self, ctx, row, index):
        def read(guard):
            binding = self._binding(ctx, row, index, guard)
            jid = row['items'][index].get('image_job_id')
            if jid:
                return self.production.get(ctx.novel_id, ctx.scope, ctx.actor, 'image', jid, guard, batch_binding=binding)
            rows = self.production.list(ctx.novel_id, ctx.scope, ctx.actor, guard, batch_binding=binding)['items']
            rows = [j for j in rows if j['owner'] == 'image' and j['request_id'] == binding['request_id']]
            if len(rows) > 1:
                raise ValueError('BATCH_STUDIO_IMAGE_AMBIGUOUS_JOB')
            return rows[0] if rows else None
        return self.call(ctx, 'domain.read', read)

    def candidate(self, ctx, row, index, reauthorize):
        def read(host_guard):
            host_guard(); reauthorize()
            item = row['items'][index]
            result = self.production.candidate(ctx.novel_id, ctx.scope, ctx.actor, 'image', item['image_job_id'], host_guard,
                batch_binding=self._binding(ctx, row, index, host_guard))
            host_guard(); reauthorize()
            return result
        return self.call(ctx, 'domain.read', read)

    def approve(self, ctx, row, index, action, reauthorize):
        def review(host_guard):
            host_guard(); reauthorize()
            result = self.production.review(ctx.novel_id, ctx.scope, ctx.actor, 'image', row['items'][index]['image_job_id'],
                MediaReview(expected_version=action.expected_job_version, expected_request_digest=action.expected_request_digest,
                    reviewed_output_digest=action.reviewed_output_digest), host_guard,
                batch_binding=self._binding(ctx, row, index, host_guard))
            host_guard(); reauthorize()
            return result
        return self.call(ctx, 'domain.review', review)

    def guard_binding(self, nid, scope, actor, context, jid=None, *, phase='read'):
        """Metadata only under queue/asset locks; never recursively read a job.

        Original production source guards retain pixel/pin authority. U16's
        outer guard rechecks its full snapshot before/after each owner call.
        """
        binding = validate_binding(context.get('batch_binding'), context)
        if binding is None:
            raise ValueError('BATCH_STUDIO_IMAGE_BINDING_REQUIRED')
        self.batches.flag_check('safe_batches_v2')
        row = self.batches.get(nid, scope, self.batches.BATCHES, binding['batch_id'])
        index = binding['item_index']
        if (row.get('created_by') != actor or row.get('scope') != scope
                or row.get('snapshot_digest') != binding['snapshot_digest']
                or digest(row['snapshot']) != binding['snapshot_digest']
                or index >= len(row['items']) or index >= len(row['snapshot']['steps'])):
            raise FileNotFoundError('batch job unavailable')
        step, item = row['snapshot']['steps'][index], row['items'][index]
        config = step.get('configuration') or {}
        if (step['input']['kind'] != 'STUDIO_IMAGE' or config.get('incarnation') != binding['incarnation']
                or config.get('command', {}).get('request_id') != binding['request_id']
                or config.get('command', {}).get('operation_id') != 'm5.image.cutout'
                or jid is not None and item.get('image_job_id') not in (None, jid)):
            raise FileNotFoundError('batch job unavailable')
        if phase in {'create', 'execute'}:
            from .safe_batches import ACTIVE
            if (not row.get('confirmed') or row['status'] != 'RUNNING' or item['status'] != 'RUNNING'
                    or item.get('claim') not in ACTIVE
                    or phase == 'create' and item.get('image_job_id') is not None
                    or phase == 'execute' and item.get('image_job_id') != jid):
                raise ValueError('BATCH_STUDIO_IMAGE_DISPATCH_FENCED')
        elif phase in {'review', 'candidate'}:
            if (not row.get('confirmed') or row['status'] in {'PREFLIGHT', 'CANCELLED', 'UNKNOWN'}
                    or item['status'] != 'COMPLETED' or item.get('image_job_id') != jid):
                raise ValueError('BATCH_STUDIO_IMAGE_REVIEW_FENCED')
        elif phase not in {'read', 'cancel', 'reconcile'}:
            raise ValueError('BATCH_STUDIO_IMAGE_PHASE_INVALID')
        return row
