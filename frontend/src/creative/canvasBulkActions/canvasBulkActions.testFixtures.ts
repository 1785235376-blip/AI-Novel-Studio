import type { CanvasDefinition, CanvasViewRecord } from '../studioCanvasViewClient';
import type { StudioGraphDraftOwner } from '../studioGraphLocalDraft';
import type { CanvasBulkActionInput } from './planCanvasBulkAction';

export const owner = (): StudioGraphDraftOwner => ({ projectId: 'Project', incarnation: 'file:original', actorId: 'Author', actorWorkspaceId: '', mode: 'local', workspaceId: '', storylineId: '', branchId: '' });
export function definition(): CanvasDefinition {
  return { schema_version: 1, title: '原媒体画布', viewport: { x: 12, y: -24, zoom: 1.25 }, view_options: { grid: true, snap_step: 16 },
    cards: [0, 100, 260].map((x, index) => ({ id: `Card${index}`, position: { x, y: 80 - index * 40 },
      asset: { asset_id: `Asset${index}`, kind: index === 1 ? 'audio' : 'image', version: 1, digest: String(index + 1).repeat(64) } })),
    groups: [{ id: 'Parent', name: '原父分组', card_ids: ['Card2'], collapsed: false },
      { id: 'Child', name: '原子分组', card_ids: ['Card0', 'Card1'], parent_id: 'Parent', collapsed: true }] };
}
export const base = (draft = definition()): CanvasViewRecord => ({ project_id: 'Project', scope: { mode: 'local', novel_id: 'Project' }, id: 'Canvas', version: 2,
  definition: structuredClone(draft), definition_digest: 'a'.repeat(64), created_at: '2026-10-21T00:00:00Z', updated_at: '2026-10-21T00:00:00Z',
  reference_states: draft.cards.map((card, index) => ({ card_id: card.id, state: !card.asset ? 'UNAVAILABLE' : index === 1 ? 'STALE' : 'CURRENT_METADATA',
    ...(!card.asset || index === 1 ? {} : { filename: `原素材${index}.png` }) })), execution_authority: false, binary_content_verified: false, capacity: { history_used: 1, record_bytes: 1000 } });
export function input(): CanvasBulkActionInput {
  const draft = definition();
  return { definition: draft, base: base(draft), selectedIds: ['Card0', 'Card1'], operation: 'REMOVE_CARDS', owner: owner(), current: true };
}
