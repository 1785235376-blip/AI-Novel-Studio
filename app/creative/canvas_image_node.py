"""Metadata-only formal result proof for the original saved CanvasView owner.

This module creates no jobs, approvals, assets or storage. Queue reads finish
before the Canvas owner acquires its original scope -> asset -> project phase.
"""
from copy import deepcopy

from ..experimental.common import StaleSourceError
from .canvas_view_models import CanvasImageNodeOrigin
from .production_execution_models import MediaCommand
from .workspace import FLAG


def changed():
    raise StaleSourceError('CREATIVE_CANVAS_IMAGE_NODE_SOURCE_CHANGED')


def capture(canvas, nid, scope, actor, value, guard):
    """Read exact original APPROVED Job metadata, without inspecting a result."""
    origin = CanvasImageNodeOrigin.model_validate(value)
    runtime = canvas.graph.media_runtime
    if runtime is None:
        changed()
    production = runtime.production
    target = origin.target
    if (target.project_id != nid or target.scope != scope
            or target.incarnation != canvas.store.incarnation(nid)):
        changed()
    guard()
    row, context = production._row(nid, scope, actor, 'image', origin.job_id, guard)
    try:
        from ..services.studio_image_execution import _receipt, _digest
        command = MediaCommand.model_validate(context.get('command'))
        if (row.get('status') != 'APPROVED' or command.operation_id != 'm5.image.t2i'
                or command.canvas_image_node is None or command.canvas_image_node != target
                or command.allow_cloud or command.source_snapshots
                or (row.get('version'), row.get('request_digest')) != (origin.job_version, origin.job_request_digest)
                or context.get('request_digest') != origin.job_request_digest
                or context.get('actor') != actor or context.get('scope_key') != canvas.store.key(nid, scope)
                or context.get('incarnation') != target.incarnation
                or any(context.get(key) is not None for key in ('graph_binding', 'benchmark_binding', 'batch_binding'))
                or not isinstance(context.get('provider_binding'), dict) or not context['provider_binding'].get('local')
                or type(row.get('candidate_asset_version')) is not int or row['candidate_asset_version'] < 1
                or type(row.get('output_asset_version')) is not int
                or row['output_asset_version'] != row['candidate_asset_version'] + 1
                or (row.get('output_asset_id'), row['output_asset_version'], row.get('output_digest')) !=
                    (origin.asset.asset_id, origin.asset.version, origin.asset.digest)
                or not row.get('receipt_digest') or row['receipt_digest'] != _digest(_receipt(row))):
            changed()
        proof = {'origin': origin.model_dump(),
            'result_origin': production._media_result_origin(context, row['id']),
            'review_origin': production._approved_media_provenance(row, 'image', actor)}
    except (KeyError, TypeError, ValueError):
        changed()
    guard()
    return deepcopy(proof)


def current_asset(canvas, nid, scope, actor, proof, guard):
    """Check raw original Asset metadata only, inside the existing phase."""
    if not canvas.graph.asset_inputs.in_phase(nid, scope, actor):
        raise ValueError('CREATIVE_CANVAS_ASSET_PHASE_REQUIRED')
    origin = proof['origin']; target = origin['target']; pin = origin['asset']
    guard()
    try:
        row = canvas.workspace._row(nid, scope, pin['asset_id'])
        if (row.get('_owner_actor_id') is not None or row.get('deleted_at') or row.get('kind') != 'image'
                or (row.get('version'), row.get('sha256')) != (pin['version'], pin['digest'])
                or row.get('source_job_id') != origin['job_id'] or row.get('_required_features') != [FLAG]
                or row.get('_studio_result_origin') != proof['result_origin']
                or row.get('_origin_provenance') != proof['review_origin']
                or row.get('_project_binding') != {'novel_id': nid, 'branch_id': scope.get('branch_id'),
                    'scope_key': canvas.store.key(nid, scope), 'incarnation': target['incarnation']}
                or canvas.store.incarnation(nid) != target['incarnation']):
            changed()
    except (FileNotFoundError, ValueError, KeyError):
        changed()
    guard()
