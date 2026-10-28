"""Closed proof for an explicit single image leaf rerun.

This never copies media outputs or sends jobs. Local inputs are reconstructed
under the original owner; every paid operation still stops at its normal gate.
"""
from datetime import datetime, timezone
from copy import deepcopy
from pydantic import Field
from .graph_models import Digest, Id, RequestId, Strict
from .graph_execution import digest
from ..experimental.common import StaleSourceError, check_version

CONTRACT = 'creative-graph-image-leaf-rerun/1'
LOCAL = {'text_input', 'text_reference', 'image_prompt', 'image_style'}

def check_deadline(row):
    """Fence execution/adoption without blocking observation of expired runs."""
    proof = row.get('rerun_proof')
    if proof is None:
        return
    try:
        expires = datetime.fromisoformat(proof['expires_at'])
        if expires.tzinfo is None:
            raise ValueError('timezone required')
    except (KeyError, TypeError, ValueError) as error:
        raise StaleSourceError('CREATIVE_GRAPH_RERUN_DEADLINE_INVALID') from error
    if datetime.now(timezone.utc) >= expires:
        raise StaleSourceError('CREATIVE_GRAPH_RERUN_PREVIEW_EXPIRED')


class ImageLeafRerunPreview(Strict):
    expected_version: int = Field(ge=1, strict=True)
    expected_graph_version: int = Field(ge=1, strict=True)
    node_id: Id

class ImageLeafRerunCreate(ImageLeafRerunPreview):
    reviewed_impact_digest: Digest
    request_id: RequestId


def plan(executor, nid, scope, actor, source, graph, body, guard, state, *, deadline=True, check_assets=True):
    """Check immutable source, original receipts and the finite selected branch."""
    check_version(source, body.expected_version)
    check_version(graph, body.expected_graph_version)
    if (source.get('graph_id') != graph['id'] or source.get('graph_schema_version') != 4
            or graph['definition'].get('schema_version') != 4 or source.get('status') != 'SUCCEEDED'
            or source.get('rerun_proof') is not None):
        raise ValueError('CREATIVE_GRAPH_RERUN_COMPLETED_IMAGE_SOURCE_REQUIRED')
    # Restrict the entire source run, not just the new closure. Planning
    # documents and other node families need their own publication-race proof.
    if any(node.get('definition_id') not in LOCAL | {'asset_reference', 'image_generate', 'media_review'}
           for node in source.get('typed_nodes', [])):
        raise ValueError('CREATIVE_GRAPH_RERUN_SOURCE_NODE_UNSUPPORTED')
    executor._current(nid, scope, actor, source, guard, state, check_assets=check_assets)
    if deadline and datetime.now(timezone.utc) >= datetime.fromisoformat(executor._timing(source)):
        raise StaleSourceError('CREATIVE_GRAPH_RERUN_PREVIEW_EXPIRED')
    executions = source.get('media_executions', {})
    if not executions or any(not isinstance(x, dict) or x.get('status') != 'APPROVED'
                             or x.get('review_state') != 'APPROVED' for x in executions.values()):
        raise ValueError('CREATIVE_GRAPH_RERUN_UNKNOWN_OR_UNREVIEWED_DENIED')
    nodes = {n['id']: n for n in graph['definition']['nodes']}
    edges = graph['definition']['edges']
    node = nodes.get(body.node_id)
    if (not node or node['definition_id'] != 'image_generate'
            or node['parameters'].get('operation_id') != 'm5.image.t2i'
            or body.node_id not in executions):
        raise ValueError('CREATIVE_GRAPH_RERUN_IMAGE_T2I_REQUIRED')
    outgoing = [e for e in edges if e['source_node_id'] == body.node_id]
    if (len(outgoing) != 1 or nodes[outgoing[0]['target_node_id']]['definition_id'] != 'media_review'
            or any(e['source_node_id'] == outgoing[0]['target_node_id'] for e in edges)):
        raise ValueError('CREATIVE_GRAPH_RERUN_LEAF_REVIEW_REQUIRED')
    review = outgoing[0]['target_node_id']
    ancestors, pending = set(), [body.node_id]
    while pending:
        current = pending.pop()
        for edge in edges:
            if edge['target_node_id'] == current and edge['source_node_id'] not in ancestors:
                ancestors.add(edge['source_node_id']); pending.append(edge['source_node_id'])
    if any(nodes[x]['definition_id'] not in LOCAL for x in ancestors):
        raise ValueError('CREATIVE_GRAPH_RERUN_LOCAL_INPUTS_REQUIRED')
    if any(source.get('node_states', {}).get(x, {}).get('status') != 'SUCCEEDED'
           or x not in source.get('typed_outputs', {}) for x in ancestors):
        raise ValueError('CREATIVE_GRAPH_RERUN_LOCAL_PROOF_REQUIRED')
    target = [body.node_id, review]
    preflight = executor.service._preflight(graph, {'expected_version': graph['version'],
        'target_node_ids': target}, actor, guard=guard, state=state, check_assets=check_assets)
    if not check_assets:
        # This branch has no asset or planning inputs. At publication, the
        # original owner already holds the asset lease; re-create its full
        # preflight digest without attempting to acquire that lease again.
        preflight.pop('source_check')
        preflight.pop('preflight_digest')
        preflight['preflight_digest'] = digest([graph['id'], graph['project_incarnation'], graph['scope'], actor, preflight])
    if not preflight['executable']:
        raise ValueError('CREATIVE_GRAPH_EXECUTION_BLOCKED')
    expected = ancestors | set(target)
    if set(preflight['selected_closure']) != expected:
        raise ValueError('CREATIVE_GRAPH_RERUN_CLOSURE_CHANGED')
    proof = {'contract': CONTRACT, 'source_run_id': source['id'], 'source_run_version': source['version'],
        'source_graph_id': graph['id'], 'source_graph_version': graph['version'], 'source_graph_digest': graph['definition_digest'],
        'source_node_id': body.node_id, 'review_node_id': review,
        'source_receipt_digest': digest(executions[body.node_id]),
        'local_inputs_digest': digest({x: source['typed_outputs'][x] for x in sorted(ancestors)}),
        'affected_node_ids': target, 'selected_closure': preflight['selected_closure'],
        'preflight_digest': preflight['preflight_digest'], 'expires_at': executor._timing(source)}
    proof['impact_digest'] = digest([CONTRACT, nid, scope, actor, source['project_incarnation'], proof])
    guard()
    return proof
