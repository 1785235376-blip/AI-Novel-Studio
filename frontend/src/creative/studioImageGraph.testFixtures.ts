import rawCatalog from './fixtures/imageGraph.catalog.json';
import type { StudioGraphCatalog, StudioGraphDefinition, StudioGraphRecord, StudioGraphRun } from './studioGraphTypes';

// Catalog bytes originate from the original disposable File GraphService.
// Graph/run rows below are transport fixtures, not native model evidence.
export const imageGraphCatalog = () => structuredClone(rawCatalog) as unknown as StudioGraphCatalog;
export const imageGraphProject = 'image-graph-project', imageGraphSha = 'a'.repeat(64);
export const imageGraphDefinition = (): StudioGraphDefinition => ({ schema_version: 4, title: 'Independent image graph',
  nodes: [
    { id: 'asset', definition_id: 'asset_reference', definition_version: 1, enabled: true, position: { x: 0, y: 0 }, parameters: { asset_id: 'source', version: 2, digest: imageGraphSha, kind: 'image' } },
    { id: 'references', definition_id: 'image_reference', definition_version: 1, enabled: true, position: { x: 280, y: 0 }, parameters: { bindings: [{ port: 'source_1', weight: 0.75 }] } },
    { id: 'prompt', definition_id: 'image_prompt', definition_version: 1, enabled: true, position: { x: 560, y: 0 }, parameters: { prompt: 'Independent image fixture prompt' } },
    { id: 'generate', definition_id: 'image_generate', definition_version: 1, enabled: true, position: { x: 840, y: 0 }, parameters: { operation_id: 'm5.image.reference', provider_id: 'image-provider', model_id: 'image-model', parameters: { denoising_strength: 0.5 }, allow_cloud: false, license_note: '' } },
    { id: 'review', definition_id: 'media_review', definition_version: 1, enabled: true, position: { x: 1120, y: 0 }, parameters: {} },
  ], edges: [
    { id: 'asset_references', source_node_id: 'asset', source_port: 'asset', target_node_id: 'references', target_port: 'source_1' },
    { id: 'references_prompt', source_node_id: 'references', source_port: 'references', target_node_id: 'prompt', target_port: 'references' },
    { id: 'prompt_generate', source_node_id: 'prompt', source_port: 'prompt', target_node_id: 'generate', target_port: 'prompt' },
    { id: 'generate_review', source_node_id: 'generate', source_port: 'candidate', target_node_id: 'review', target_port: 'candidate' },
  ], viewport: { x: 0, y: 0, zoom: 1 } });
export const imageGraphRecord = (): StudioGraphRecord => ({ project_id: imageGraphProject, scope: { mode: 'local', novel_id: imageGraphProject }, id: 'image-graph', version: 1,
  definition: imageGraphDefinition(), definition_digest: imageGraphSha, execution_digest: imageGraphSha, created_at: '2026-10-13T14:00:00Z', updated_at: '2026-10-13T14:00:00Z', can_edit: true,
  reference_states: [{ node_id: 'asset', state: 'CURRENT' }] });
export const imageGraphRun = (): StudioGraphRun => {
  const graph = imageGraphRecord(), asset = { asset_id: 'source', version: 2, digest: imageGraphSha, kind: 'image' as const }, references = [{ asset, weight: 0.75 }];
  return { project_id: graph.project_id, scope: graph.scope, id: 'image-run', version: 1, graph_id: graph.id, graph_version: graph.version,
    status: 'RUNNING', current_node_id: 'generate', node_states: {
      asset: { status: 'SUCCEEDED', output: { asset }, error: null }, references: { status: 'SUCCEEDED', output: { references }, error: null },
      prompt: { status: 'SUCCEEDED', output: { prompt: { prompt: graph.definition.nodes[2].parameters.prompt!, references } }, error: null },
      generate: { status: 'QUEUED', output: null, error: null }, review: { status: 'PENDING', output: null, error: null },
    }, review: null, cache: { hits: 0, misses: 0, mode: 'SAME_GRAPH_VERSION_REVIEWED_LOCAL_ONLY' }, created_at: '2026-10-13T14:00:00Z', updated_at: '2026-10-13T14:00:00Z', model_called: false,
    external_calls: 0, applied: false, stale: false, reviewed: false, timeout_seconds: 3600, deadline_at: '2026-10-13T15:00:00Z' };
};
