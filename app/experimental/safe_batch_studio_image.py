"""U16 bridge to the original Studio Host invoker and ImageJob owner.

Bindings are server-only; no public media command can supply one. This module
owns neither a queue nor an image algorithm. Host requests are context-local
and are never persisted with the batch or job.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
import re

from .planning import digest

CONTRACT = 'studio-image-safe-batch/1'
_request = ContextVar('studio_image_batch_request', default=None)


@contextmanager
def request_context(request):
    token = _request.set(request)
    try:
        yield
    finally:
        _request.reset(token)


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
        return self.invoke(request, ctx.novel_id, ctx.token, ctx.branch, permission, operation)

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
