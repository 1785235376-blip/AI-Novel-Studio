import { checkedStudioGraphDraft } from './studioGraphClient';
import imageCatalog from './fixtures/imageGraph.catalog.json';
import productionCatalog from './fixtures/productionGraph.catalog.json';
import videoCatalog from './fixtures/phase4.video-catalog.json';
import subgraph from './fixtures/localSubgraph.file-api.json';
import { imageGraphDefinition } from './studioImageGraph.testFixtures';
import { videoBindingGraph } from './graphSelectedVideoBinding.testFixtures';
import type { StudioGraphCatalog, StudioGraphDefinition, StudioGraphRecord } from './studioGraphTypes';
import type { StudioGraphDraftOwner, StudioGraphLocalDraft } from './studioGraphLocalDraft';
export const boundOwner: StudioGraphDraftOwner = { projectId: 'bound-recovery', incarnation: 'file:original', actorId: 'author', actorWorkspaceId: '', mode: 'local', workspaceId: '', storylineId: '', branchId: '' };
export const boundRequest = `graph_${'b'.repeat(32)}`;
export function boundDefinition(schema: 3 | 4 | 5 | 6): StudioGraphDefinition {
  if (schema === 4) return imageGraphDefinition();
  if (schema === 5) return videoBindingGraph(1);
  if (schema === 6) return structuredClone(subgraph.parent.definition) as unknown as StudioGraphDefinition;
  return { schema_version: 3, title: '未保存的媒体图', nodes: [
    { id: 'input', definition_id: 'text_input', definition_version: 1, enabled: true, position: { x: 0, y: 0 }, parameters: { text: '作者输入' } },
    { id: 'generate', definition_id: 'media_generate', definition_version: 1, enabled: true, position: { x: 240, y: 0 }, parameters: { operation_id: 'm5.image.t2i', provider_id: 'configured-local', model_id: 'configured-model', prompt: '保留原提示词', parameters: { seed: 7 }, allow_cloud: false, license_note: '保留来源说明' } },
    { id: 'review', definition_id: 'media_review', definition_version: 1, enabled: true, position: { x: 480, y: 0 }, parameters: {} }],
    edges: [{ id: 'in', source_node_id: 'input', source_port: 'text', target_node_id: 'generate', target_port: 'text' }, { id: 'review', source_node_id: 'generate', source_port: 'candidate', target_node_id: 'review', target_port: 'candidate' }], viewport: { x: 20, y: -10, zoom: 0.8 } };
}
export function boundCatalog(schema: 3 | 4 | 5 | 6, production = false): StudioGraphCatalog {
  if (schema === 6) return structuredClone(subgraph.catalog) as unknown as StudioGraphCatalog;
  if (schema === 5) return structuredClone(videoCatalog) as unknown as StudioGraphCatalog;
  if (schema === 4) return structuredClone(production ? productionCatalog : imageCatalog) as unknown as StudioGraphCatalog;
  // Unit transport fixture derived from the original captured media/image catalog.
  const value = structuredClone(imageCatalog) as unknown as StudioGraphCatalog;
  value.definitions = value.definitions.filter(n => !['image_reference', 'image_prompt', 'image_generate'].includes(n.id));
  Object.keys(value.capabilities).filter(k => k.startsWith('image_')).forEach(k => { delete (value.capabilities as unknown as Record<string, unknown>)[k]; });
  return value;
}
export function boundChild(): StudioGraphRecord { return { ...structuredClone(subgraph.child), project_id: boundOwner.projectId, scope: { mode: 'local', novel_id: boundOwner.projectId } } as unknown as StudioGraphRecord; }
export function boundSnapshot(schema: 3 | 4 | 5 | 6): StudioGraphLocalDraft { return { schema_version: 1, owner: boundOwner, saved_at: '2026-10-20T00:00:00Z', request_id: boundRequest, base: null, uncertain: false, definition: boundDefinition(schema) }; }
export function boundSaved(schema: 3 | 4 | 5 | 6): StudioGraphRecord { return { project_id: boundOwner.projectId, scope: { mode: 'local', novel_id: boundOwner.projectId }, id: `saved-${schema}`, version: 2, definition: checkedStudioGraphDraft(boundDefinition(schema)), definition_digest: 'a'.repeat(64), execution_digest: 'c'.repeat(64), can_edit: true, reference_states: [], created_at: '2026-10-20T00:00:00Z', updated_at: '2026-10-20T00:00:00Z' }; }
