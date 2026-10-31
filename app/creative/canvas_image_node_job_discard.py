"""Explicit discard of one unexecuted original formal image-node Job.

All source validation runs before the original queue CAS. Only the original
cancel owner writes; no Canvas, Asset, provider or execution path is entered.
"""
from copy import deepcopy

from ..experimental.common import StaleSourceError
from .canvas_image_node_job_observation import project_public_job
from .production_execution_models import CanvasImageNodeJobDiscard, MediaCommand


# These fields are written by the original image owner's claim, dispatch,
# publication, review, interruption and cancellation transitions. A fresh
# QUEUED admission has none of them (or an explicit null), not stale evidence.
NO_EXECUTION_FIELDS = ('receipt_digest', 'output_candidate', 'output_asset_id',
    'output_asset_version', 'output_digest', 'candidate_asset_version', 'approved_asset_version',
    'execution_token', 'dispatch_started', 'dispatch_intent_at', 'publication_ready',
    'processing_proof', 'review_token', 'review_from_version', 'review_state',
    'recovery_state', 'review_reconciled_at', 'local_result_discarded',
    'cancellation_mode', 'remote_cancel_confirmed', 'cancelled_at', 'error_code')


def changed():
    raise StaleSourceError('STUDIO_IMAGE_NODE_JOB_DISCARD_CHANGED')


def discard(production, nid, scope, actor, jid, value, guard):
    body = CanvasImageNodeJobDiscard.model_validate(value)
    row, context = production._row(nid, scope, actor, 'image', jid, guard)
    if (row['version'], row['request_digest']) != (body.expected_version, body.expected_request_digest):
        changed()
    snapshot = deepcopy(row)
    try:
        command = MediaCommand.model_validate(context.get('command'))
        target = command.canvas_image_node
        if (command.operation_id != 'm5.image.t2i' or target is None
                or command.allow_cloud or command.source_snapshots or context.get('sources') != []
                or context.get('request_id') != command.request_id
                or context.get('request_digest') != body.expected_request_digest
                or target.project_id != nid or target.scope != scope
                or target.incarnation != context['incarnation']
                or any(context.get(key) is not None for key in ('graph_binding', 'benchmark_binding', 'batch_binding'))
                or not isinstance(context.get('provider_binding'), dict)
                or context['provider_binding'].get('local') is not True
                or row['status'] != 'QUEUED' or type(row.get('attempt')) is not int or row['attempt'] != 0
                or any(row.get(key) is not None for key in NO_EXECUTION_FIELDS)):
            changed()
        # This is the original preview's digest formula, using its already
        # captured recipe/configuration metadata. Do not resolve a provider or
        # recompute a new recipe when validating an existing request.
        from .production_execution import digest
        preview_context = {key: deepcopy(value) for key, value in context.items()
            if key not in {'command', 'request_digest'}}
        if digest({'context': preview_context, 'command': command.model_dump()}) != body.expected_request_digest:
            changed()
        original = project_public_job(production.view(row, 'image'), command)
    except (KeyError, TypeError, ValueError):
        changed()
    guard()
    # The original cancel owner compares this raw snapshot inside its own CAS;
    # there is no outer queue fence spanning project or authority checks.
    public = production.cancel(nid, scope, actor, 'image', jid, body, guard, expected_snapshot=snapshot)
    guard()
    try:
        returned_command = MediaCommand.model_validate(public.get('command'))
        if returned_command.model_dump() != command.model_dump():
            changed()
        job = project_public_job(public, returned_command)
        allowed_changes = {'version', 'status', 'updated_at', 'error_code', 'cancellation_mode', 'remote_compute_may_continue'}
        if (any(job[key] != original[key] for key in original if key not in allowed_changes)
                or job['version'] != body.expected_version + 1 or job['status'] != 'CANCELLED'
                or job['attempt'] != 0 or job['output_candidate'] is not None or job['receipt_digest'] is not None
                or job['approved_asset_version'] is not None or job['error_code'] is not None
                or job['cancellation_mode'] != 'LOCAL_RESULT_DISCARD' or job['remote_compute_may_continue'] is not True):
            changed()
    except (KeyError, TypeError, ValueError):
        # Cancellation may already be committed. A failed acknowledgement is
        # not a rollback and must be recovered by reading the original Job.
        changed()
    guard()
    return {'contract': 'studio-image-node-job-discard/1', 'job': job,
        'target': target.model_dump(), 'incarnation': context['incarnation'],
        'canvas_read': False, 'automatic_actions': False,
        'local_result_discarded': True, 'remote_stop_confirmed': False}
