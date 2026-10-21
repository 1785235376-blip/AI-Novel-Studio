import type { StudioGraphDraftOwner } from '../studioGraphLocalDraft';
import type { StudioGraphRecord } from '../studioGraphTypes';
export const templateOwner: StudioGraphDraftOwner = { projectId: 'audio-project', incarnation: 'file:original-instance', actorId: 'author',
  actorWorkspaceId: '', mode: 'local', workspaceId: '', storylineId: '', branchId: '' };
export const templateGraph = (): StudioGraphRecord => ({ project_id: templateOwner.projectId,
  scope: { mode: 'local', novel_id: templateOwner.projectId }, id: 'graph-audio-template', version: 3,
  definition_digest: 'a'.repeat(64), execution_digest: 'b'.repeat(64), can_edit: true,
  created_at: '2026-10-21T00:00:00Z', updated_at: '2026-10-21T00:00:00Z',
  reference_states: [{ node_id: 'source', state: 'CURRENT' }],
  definition: { schema_version: 3, title: 'Saved audio template', viewport: { x: 0, y: 0, zoom: 1 }, nodes: [
    { id: 'source', definition_id: 'asset_reference', definition_version: 1, enabled: true, position: { x: 0, y: 0 },
      parameters: { asset_id: 'original-audio', version: 2, digest: 'c'.repeat(64), kind: 'audio' } },
    { id: 'trim', definition_id: 'media_generate', definition_version: 1, enabled: true, position: { x: 280, y: 0 },
      parameters: { operation_id: 'm8.audio.trim', provider_id: null, model_id: null, prompt: '',
        parameters: { in_ms: 100, out_ms: 900 }, allow_cloud: false, license_note: '' } },
    { id: 'trim_other', definition_id: 'media_generate', definition_version: 1, enabled: true, position: { x: 280, y: 160 },
      parameters: { operation_id: 'm8.audio.trim', parameters: { in_ms: 200, out_ms: 800 } } },
  ], edges: [{ id: 'source_trim', source_node_id: 'source', source_port: 'asset', target_node_id: 'trim', target_port: 'source' }] } });
