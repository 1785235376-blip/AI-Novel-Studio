"""Closed original image-node Job metadata, independent of current Canvas.

The target remains a captured request, never proof of a current saved location.
No candidate content, recipe, transport, recovery or mutation is exposed here.
"""
from copy import deepcopy

from ..experimental.common import StaleSourceError
from ..services.studio_image_execution import (IDENTITY, MAX_VERSION, STATES,
    _digest, _receipt, _require_digest, _require_version, _text)
from .production_execution_models import MediaCommand, MediaJobAction


JOB_FIELDS = ('contract', 'owner', 'id', 'novel_id', 'branch_id', 'version',
    'operation_id', 'request_id', 'status', 'request_digest', 'receipt_digest',
    'attempt', 'created_at', 'updated_at', 'error_code', 'review_state',
    'cancellation_mode', 'needs_reconciliation', 'execution_state',
    'output_candidate', 'command', 'provider', 'approved_asset_version',
    'product_acceptance', 'automatic_replay', 'remote_compute_may_continue')


def changed():
    raise StaleSourceError('STUDIO_IMAGE_NODE_JOB_OBSERVATION_CHANGED')


def _candidate(value):
    if value is None:
        return None
    if (not isinstance(value, dict) or not isinstance(value.get('id'), str)
            or not IDENTITY.fullmatch(value['id']) or value.get('kind') != 'image'):
        changed()
    _require_version(value.get('version'))
    _require_digest(value.get('digest'))
    # Extra transport/data URI fields are never part of this projection. This
    # pin records only what the original Job says, not Asset availability.
    return {key: value[key] for key in ('id', 'version', 'digest', 'kind')}


def _projection(production, row, command):
    return project_public_job(production.view(row, 'image'), command)


def project_public_job(public, command):
    """Project an original public receipt without another owner read."""
    if (public['contract'] != 'studio-production-job/1' or public['owner'] != 'image'
            or public['operation_id'] != 'm5.image.t2i' or public['status'] not in STATES
            or public['product_acceptance'] != 'LOCAL_REQUIRED' or public['automatic_replay'] is not False
            or type(public['remote_compute_may_continue']) is not bool
            or type(public['attempt']) is not int or not 0 <= public['attempt'] <= MAX_VERSION):
        changed()
    for key in ('id', 'novel_id', 'request_id', 'created_at', 'updated_at'):
        _text(public[key])
    if public['branch_id'] is not None:
        _text(public['branch_id'])
    _require_version(public['version'])
    _require_digest(public['request_digest'])
    if public['receipt_digest'] is not None:
        _require_digest(public['receipt_digest'])
    for key in ('error_code', 'review_state', 'cancellation_mode', 'execution_state'):
        if public[key] is not None:
            _text(public[key])
    if public['needs_reconciliation'] is not None and type(public['needs_reconciliation']) is not bool:
        changed()
    if public['approved_asset_version'] is not None:
        _require_version(public['approved_asset_version'])
    provider = public['provider']
    if (not isinstance(provider, dict) or provider.get('local') is not True
            or provider.get('provider_id') != command.provider_id or provider.get('model_id') != command.model_id):
        changed()
    _require_digest(provider.get('route_digest'))
    checked_command = command.model_dump()
    checked_command['parameters'] = command.parameters.model_dump(exclude_none=True)
    result = {key: public[key] for key in JOB_FIELDS}
    result['command'] = checked_command
    result['provider'] = {key: provider[key] for key in ('provider_id', 'model_id', 'local', 'route_digest')}
    result['output_candidate'] = _candidate(public['output_candidate'])
    return result


def observe(production, nid, scope, actor, jid, value, guard):
    body = MediaJobAction.model_validate(value)
    row, context = production._row(nid, scope, actor, 'image', jid, guard)
    if (row['version'], row['request_digest']) != (body.expected_version, body.expected_request_digest):
        changed()
    original_row, original_context = deepcopy(row), deepcopy(context)
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
                or context['provider_binding'].get('local') is not True):
            changed()
        if ((row.get('status') in {'AWAITING_REVIEW', 'REVIEWING', 'APPROVED'}
                or row.get('output_asset_id') is not None) and row.get('receipt_digest') is None):
            changed()
        if row.get('receipt_digest') is not None and row['receipt_digest'] != _digest(_receipt(row)):
            changed()
        job = _projection(production, row, command)
    except (KeyError, TypeError, ValueError):
        changed()
    guard()
    latest, latest_context = production._row(nid, scope, actor, 'image', jid, guard)
    if latest != original_row or latest_context != original_context:
        changed()
    guard()
    return {'contract': 'studio-image-node-job-observation/1', 'job': job,
        'target': target.model_dump(), 'incarnation': context['incarnation'],
        'canvas_read': False, 'automatic_actions': False}
