"""A bounded metadata observation of one original image-node target.

No generation, candidate recovery, approval or Canvas mutation is performed.
The original Job read finishes before each original Canvas metadata phase.
"""
from copy import deepcopy

from ..experimental.common import StaleSourceError
from .production_execution_models import MediaCommand, MediaJobAction


def changed():
    raise StaleSourceError('STUDIO_IMAGE_NODE_TARGET_OBSERVATION_CHANGED')


def observe(production, nid, scope, actor, jid, value, guard):
    body = MediaJobAction.model_validate(value)
    row, context = production._row(nid, scope, actor, 'image', jid, guard)
    if (row['version'], row['request_digest']) != (body.expected_version, body.expected_request_digest):
        changed()
    captured_context = deepcopy(context)
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
        if row.get('receipt_digest') is not None:
            from ..services.studio_image_execution import _digest, _receipt
            if row['receipt_digest'] != _digest(_receipt(row)):
                changed()
        original_job = production.view(row, 'image')
    except (KeyError, TypeError, ValueError):
        changed()

    graph = getattr(production, 'graph_service', None)
    if graph is None:
        changed()
    # These reads use the original scope/asset-metadata/project phases. Never
    # carry an original Job lock into them or fetch an Asset payload here.
    guard()
    canvas = graph.canvas_views.get(nid, scope, actor, target.canvas_id, guard)
    guard()
    history = graph.canvas_views.history(nid, scope, actor, target.canvas_id, guard)
    guard()
    try:
        if (canvas['id'] != target.canvas_id or canvas['project_id'] != nid or canvas['scope'] != scope
                or type(canvas['version']) is not int or canvas['version'] < 1
                or canvas['execution_authority'] is not False or canvas['binary_content_verified'] is not False
                or history['id'] != canvas['id'] or history['project_id'] != nid or history['scope'] != scope
                or history['incarnation'] != context['incarnation']
                or history['current_version'] != canvas['version']
                or history['current_definition_digest'] != canvas['definition_digest']
                or history['execution_authority'] is not False or history['binary_content_verified'] is not False):
            changed()
        matches = [entry for entry in history['items'] if entry['version'] == target.canvas_version]
        if (len(matches) != 1 or matches[0]['definition_digest'] != target.canvas_digest
                or matches[0]['definition']['cards'] != [] or 'image_node_origin' in matches[0]['definition']):
            changed()
        canvas_summary = {'id': canvas['id'], 'project_id': nid, 'scope': deepcopy(scope),
            'version': canvas['version'], 'definition_digest': canvas['definition_digest'],
            'title': canvas['definition']['title'], 'card_count': len(canvas['definition']['cards']),
            'execution_authority': False, 'binary_content_verified': False}
        history_summary = {'incarnation': history['incarnation'], 'current_version': canvas['version'],
            'current_definition_digest': canvas['definition_digest'], 'target_version': target.canvas_version,
            'target_definition_digest': target.canvas_digest, 'target_empty': True}
    except (KeyError, TypeError, ValueError):
        changed()

    # Re-read the original owner after releasing the Canvas phases. A changed
    # public receipt or captured execution context cannot inherit this result.
    latest, latest_context = production._row(nid, scope, actor, 'image', jid, guard)
    if latest_context != captured_context or production.view(latest, 'image') != original_job:
        changed()
    guard()
    return {'contract': 'studio-image-node-target-observation/1', 'job': original_job,
        'target': target.model_dump(), 'incarnation': context['incarnation'],
        'canvas': canvas_summary, 'history': history_summary,
        'comparison': 'CURRENT_MATCH' if (canvas['version'], canvas['definition_digest']) ==
            (target.canvas_version, target.canvas_digest) else 'CURRENT_CHANGED',
        'automatic_actions': False}
