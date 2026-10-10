import type { StudioGraphCatalog, StudioGraphDefinitionId, StudioGraphModelCapabilities, StudioGraphModelRuntime, StudioGraphRecord, StudioGraphRun } from './studioGraphTypes';

export const modelDigest = 'a'.repeat(64), modelInputDigest = 'b'.repeat(64);
export const modelOwner = () => ({ project_id: 'model_project', scope: { mode: 'local' as const, novel_id: 'model_project' } });
export function modelCapabilities(): StudioGraphModelCapabilities {
  return { ...modelOwner(), schema_version: 1, contract: 'creative-graph-model/1', adapter_owner: 'TextModelNode', router_owner: 'ModelBroker',
    scheduler_owner: 'JobManager+WorkflowRun', local_only: true, automatic_fallback: false,
    api_provider: { status: 'RESERVED', execution_available: false, reason: 'API_PROVIDER_EXECUTION_NOT_ENABLED' },
    limits: { model_nodes: 1, max_output_tokens: 2048, timeout_seconds: 180 }, quality_verification: 'NOT_RUN',
    routes: [
      { route_id: 'dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd', provider_id: 'local', model_id: 'writer', display_name: '本地写作模型', available: true, synthetic: false, context_window: 8192, verification: 'ADAPTER_CONTRACT_ONLY', reasons: [] },
      { route_id: 'eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee', provider_id: 'mock', model_id: 'mock_writer', display_name: '测试写作适配器', available: true, synthetic: true, context_window: null, verification: 'SYNTHETIC_PROTOCOL_ONLY', reasons: [] },
    ] };
}
export function modelRuntime(fields: Partial<StudioGraphModelRuntime> = {}): StudioGraphModelRuntime {
  return { schema_version: 1, contract: 'creative-graph-model/1', node_id: 'generate', status: 'AWAITING_PREVIEW', preview: null, execution: null,
    quality_verification: 'NOT_RUN', automatic_retry: false, applied: false, ...fields };
}
export function modelRun(fields: Partial<StudioGraphRun> = {}): StudioGraphRun {
  return { ...modelOwner(), id: 'model_run', graph_id: 'model_graph', graph_version: 1, version: 2, status: 'RUNNING', current_node_id: 'generate',
    node_states: { input: { status: 'SUCCEEDED', output: { text: 'Author source' }, error: null }, generate: { status: 'PENDING', output: null, error: null }, review: { status: 'PENDING', output: null, error: null } },
    review: null, cache: { hits: 0, misses: 0, mode: 'SAME_GRAPH_VERSION_REVIEWED_LOCAL_ONLY' }, created_at: '2026-10-10T00:00:00Z', updated_at: '2026-10-10T00:00:00Z',
    model_called: false, external_calls: 0, applied: false, stale: false, reviewed: false, timeout_seconds: 3600, deadline_at: '2026-10-10T01:00:00Z', model_runtime: modelRuntime(), ...fields };
}
export function modelPreviewRun(synthetic = false): StudioGraphRun {
  return modelRun({ version: 3, model_runtime: modelRuntime({ status: 'PREVIEWED', preview: {
    preview_digest: modelDigest, node_id: 'generate', input_digest: modelInputDigest, prompt: 'Complete reviewed author input',
    route: { route_id: synthetic ? 'eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee' : 'dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd', provider_id: synthetic ? 'mock' : 'local', model_id: synthetic ? 'mock_writer' : 'writer', synthetic, verification: synthetic ? 'SYNTHETIC_PROTOCOL_ONLY' : 'ADAPTER_CONTRACT_ONLY' },
    execution_available: true, reasons: [], limits: { max_output_bytes: 32000, max_output_tokens: 512, timeout_seconds: 180 }, model_called: false, quality_verification: 'NOT_RUN',
  } }) });
}
export function modelAdmittedRun(synthetic = false): StudioGraphRun {
  const run = modelPreviewRun(synthetic);
  return { ...run, version: 4, model_runtime: { ...run.model_runtime!, status: 'ADMITTED', execution: { job_id: 'original_job', status: 'RUNNING', receipt_state: 'RECORDED', model_called: false,
    synthetic, usage_state: 'PENDING', failure_code: null, quality_verification: 'NOT_RUN' } } };
}
export function modelGraph(): StudioGraphRecord {
  return { ...modelOwner(), id: 'model_graph', version: 1, definition_digest: modelDigest, execution_digest: modelDigest,
    created_at: '2026-10-10T00:00:00Z', updated_at: '2026-10-10T00:00:00Z', can_edit: true, reference_states: [],
    definition: { schema_version: 2, title: 'Explicit local model graph', nodes: [
      { id: 'input', definition_id: 'text_input', definition_version: 1, enabled: true, position: { x: 0, y: 0 }, parameters: { text: 'Author source' } },
      { id: 'generate', definition_id: 'text_generate', definition_version: 1, enabled: true, position: { x: 280, y: 0 }, parameters: { instruction: 'Continue this text', max_output_tokens: 512 } },
      { id: 'review', definition_id: 'human_review', definition_version: 1, enabled: true, position: { x: 560, y: 0 }, parameters: {} },
    ], edges: [
      { id: 'input_generate', source_node_id: 'input', source_port: 'text', target_node_id: 'generate', target_port: 'text' },
      { id: 'generate_review', source_node_id: 'generate', source_port: 'draft', target_node_id: 'review', target_port: 'draft' },
    ], viewport: { x: 0, y: 0, zoom: 1 } } };
}
export function modelCatalog(enabled = true): StudioGraphCatalog {
  const ids: StudioGraphDefinitionId[] = ['text_input', 'text_reference', 'draft_prepare', 'manual_transform', 'director_note', 'human_review', 'asset_reference', ...(enabled ? ['text_generate' as const] : [])];
  return { limits: { nodes: 16, edges: 40, definition_bytes: 96000, output_bytes: 64000, graphs: 25, runs: 100, history: 20, runtime_timeout_seconds: 3600, node_timeout_seconds: 5 },
    capabilities: { local_execution: true, chapter_required: false, model_execution: enabled, ...(enabled ? { model_execution_contract: 'creative-graph-model/1' as const } : {}), external_reference_execution: false,
      external_reference_detach: false, binary_cache: false, parallel_execution: false, automatic_retry: false, actor_private: true, cache_mode: 'SAME_GRAPH_VERSION_REVIEWED_LOCAL_ONLY' },
    definitions: ids.map(id => {
      const transforming = ['draft_prepare', 'manual_transform', 'text_generate'].includes(id);
      const inputs = transforming ? [{ id: 'text', type: 'TEXT' as const, required: true, multiple: false as const }, { id: 'direction', type: 'DIRECTOR_NOTES' as const, required: false, multiple: false as const }]
        : id === 'text_reference' ? [{ id: 'text', type: 'TEXT' as const, required: true, multiple: false as const }] : id === 'human_review' ? [{ id: 'draft', type: 'DRAFT' as const, required: true, multiple: false as const }] : [];
      const outputs = id === 'human_review' ? [] : [{ id: transforming ? 'draft' : id === 'director_note' ? 'direction' : id === 'asset_reference' ? 'asset' : 'text',
        type: transforming ? 'DRAFT' as const : id === 'director_note' ? 'DIRECTOR_NOTES' as const : id === 'asset_reference' ? 'ASSET_REF' as const : 'TEXT' as const, required: false, multiple: false as const }];
      const field = id === 'text_input' ? 'text' : id === 'manual_transform' ? 'result' : id === 'director_note' ? 'note' : undefined;
      const properties: StudioGraphCatalog['definitions'][number]['parameters_schema']['properties'] = id === 'text_generate'
        ? { instruction: { type: 'string', default: '', maxLength: 4000 }, max_output_tokens: { type: 'integer', default: 512, minimum: 1, maximum: 2048 } }
        : id === 'asset_reference' ? { asset_id: { type: 'string', minLength: 1 }, version: { type: 'integer', minimum: 1 }, digest: { type: 'string' }, kind: { type: 'string', enum: ['image', 'video', 'audio'] } }
          : field ? { [field]: { type: 'string', default: '', maxLength: field === 'note' ? 4000 : 8000 } } : {};
      return { id, version: 1, inputs, outputs, parameters_schema: { type: 'object', additionalProperties: false, properties },
        default_parameters: id === 'asset_reference' ? null : id === 'text_generate' ? { instruction: '', max_output_tokens: 512 } : field ? { [field]: '' } : {},
        executable: id !== 'asset_reference', model_called: false, blockers: id === 'asset_reference' ? ['CREATIVE_GRAPH_ATOMIC_INPUT_OWNER_ADAPTER_REQUIRED'] : [] };
    }) };
}
