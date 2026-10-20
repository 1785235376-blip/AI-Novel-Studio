import { checkedStudioGraphDraft } from './studioGraphClient';
import { graphCatalogForSchema, graphId } from './graphDraft';
import type { StudioGraphCatalog, StudioGraphDefinition, StudioGraphNode } from './studioGraphTypes';
import type { CanvasAssetReference } from './studioCanvasViewClient';
import type { StudioAsset } from './studioClient';
export type CanvasGraphAssetHandoff = { scope: object; available: boolean; isCurrent: () => boolean; insert: (reference: CanvasAssetReference, scope: object) => boolean };
export function verifyCanvasGraphAsset(asset: StudioAsset, reference: CanvasAssetReference): CanvasAssetReference {
  if (!asset || asset.deleted_at || asset.id !== reference.asset_id || asset.version !== reference.version || asset.sha256 !== reference.digest || asset.kind !== reference.kind) throw new Error('素材版本或访问状态已改变。');
  return { ...reference };
}
/** Original asset-reference node only; no schema upgrade, edges, provider or execution. */
export function appendCanvasAssetNode(draft: StudioGraphDefinition, catalog: StudioGraphCatalog, reference: CanvasAssetReference, makeId = graphId) {
  if (draft.schema_version < 3 || !graphCatalogForSchema(catalog.definitions, draft.schema_version).some(row => row.id === 'asset_reference')) throw new Error('请先选择支持素材引用的媒体图。');
  if (draft.nodes.length >= (catalog.media_limits?.nodes || 24)) throw new Error('执行图节点容量已满。');
  if (draft.schema_version === 4 && reference.kind !== 'image') throw new Error('图片图只能接收图片引用。');
  const node: StudioGraphNode = { id: makeId('asset'), definition_id: 'asset_reference', definition_version: 1, enabled: true,
    position: { x: 24 + draft.nodes.length % 4 * 280, y: 24 + Math.floor(draft.nodes.length / 4) * 180 }, parameters: { ...reference } };
  // Validate the new closed node without rejecting unrelated, unfinished model
  // settings already in the local author draft. Original save validates the whole graph.
  const checked = checkedStudioGraphDraft({ schema_version: draft.schema_version, title: 'Asset input', nodes: [node], edges: [], viewport: { x: 0, y: 0, zoom: 1 } }).nodes[0];
  if (draft.nodes.some(row => row.id === checked.id)) throw new Error('节点标识冲突。');
  return { definition: { ...structuredClone(draft), nodes: [...structuredClone(draft.nodes), checked] }, nodeId: checked.id };
}
