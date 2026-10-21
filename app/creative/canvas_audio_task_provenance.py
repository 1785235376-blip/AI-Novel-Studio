"""Pinned task provenance over the original AudioJob and Graph owners.

No execution, queue or storage is defined here. Queued commands retain their
captured template version and local overrides even after a template is edited.
"""


def validate_task_provenance(service, nid, scope, actor, command, context, guard, *, document=None):
    body = command.model_dump()
    audio = service._audio(scope, actor)
    # Only an exact already-persisted original request may use its frozen pins.
    # A new request must validate the current template/failed parent again.
    for row in audio.list(nid, context, guard):
        captured = row.get('context', {})
        if (captured.get('request_id') == command.request_id
                and captured.get('command') == body
                and all(captured.get(k) == context[k] for k in ('actor', 'scope_key', 'incarnation'))
                and not any(captured.get(k) is not None for k in ('graph_binding', 'benchmark_binding', 'batch_binding'))):
            guard()
            return
    if command.derived_from is not None:
        pin = command.derived_from
        parent = service.get(nid, scope, actor, 'audio', pin.job_id, guard)
        previous = parent.get('command') or {}
        if (parent['status'] != 'FAILED' or parent['version'] != pin.job_version
                or parent['request_id'] != pin.request_id or parent['request_digest'] != pin.request_digest
                or parent.get('receipt_digest') != pin.receipt_digest or command.request_id == pin.request_id
                or parent['operation_id'] != 'm8.audio.trim' or parent['provider'] is not None
                or parent['execution_recipe'].get('adapter') != 'LOCAL_FFMPEG'
                or parent['execution_recipe'].get('output_profile') != 'PCM_S16LE_WAV_48000_STEREO'
                or previous.get('canvas_return') != body['canvas_return']
                or parent['sources'] != [s.model_dump(exclude={'reference_only'}, exclude_none=True) for s in command.source_snapshots]):
            raise ValueError('STUDIO_CANVAS_AUDIO_DERIVED_ORIGIN_CHANGED')
    if command.template_ref is not None:
        pin = command.template_ref
        graph_owner = getattr(service, 'graph_service', None)
        if graph_owner is None:
            raise ValueError('STUDIO_CANVAS_AUDIO_TEMPLATE_OWNER_REQUIRED')
        if document is None:
            graph = graph_owner.get(nid, scope, actor, pin.graph_id, guard)
        else:
            # The original source/asset phase is already leased by Timeline Save.
            # Reuse original owned-record and asset validators without a second phase.
            from .graph import GRAPHS
            graph = graph_owner._owned(nid, scope, actor, GRAPHS, pin.graph_id, document)
            if graph['definition']['schema_version'] != 3:
                raise ValueError('STUDIO_CANVAS_AUDIO_TEMPLATE_CHANGED')
            for ref in graph['definition']['nodes']:
                if ref['definition_id'] == 'asset_reference':
                    graph_owner.asset_inputs._read(nid, scope, ref['parameters'], guard)
            graph = {**graph, 'can_edit':True, 'reference_states':[]} # Every original asset pin was checked above.
        node = next((n for n in graph['definition']['nodes'] if n['id'] == pin.node_id), None)
        parameters = (node or {}).get('parameters', {})
        values = parameters.get('parameters', {})
        known = {'in_ms', 'out_ms', 'gain_db', 'fade_in_ms', 'fade_out_ms', 'width', 'height', 'steps', 'seed', 'cfg', 'negative_prompt', 'size', 'quality', 'duration_seconds', 'frame_rate', 'voice_id', 'speech_rate'}
        normalized = {k: v for k, v in values.items() if v is not None}
        if (graph['version'] != pin.graph_version or graph['definition_digest'] != pin.definition_digest
                or graph['execution_digest'] != pin.execution_digest or graph.get('can_edit') is not True
                or graph['definition']['schema_version'] != 3 or not node or not node['enabled']
                or node['definition_id'] != 'media_generate' or parameters.get('operation_id') != 'm8.audio.trim'
                or parameters.get('provider_id') is not None or parameters.get('model_id') is not None
                or parameters.get('allow_cloud') is not False or parameters.get('prompt') != ''
                or set(values) - known or normalized != pin.parameters.model_dump()
                or any(state['state'] != 'CURRENT' for state in graph.get('reference_states', []))):
            raise ValueError('STUDIO_CANVAS_AUDIO_TEMPLATE_CHANGED')
    guard()
