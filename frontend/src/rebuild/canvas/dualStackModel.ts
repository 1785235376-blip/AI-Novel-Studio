// [HERMIA-FE-20261026 DUAL] Pure model for the stacked dual canvas (上画布 = 主线, 下画布 = 丰富创作).
// - Two independent graphs: the upper keeps the existing main-canvas storage (canvasStorageKey(kind, novelId), so the
//   inspector / tasks that already read it keep working); the lower has its OWN key, scoped by workspace identity.
// - Real identity → localStorage key with user/project/instance; no identity → memory only (「仅本次会话」), never a
//   made-up user id. Nothing here talks to the backend.
// - The lower feeds the upper ONLY through feedToUpper(), called from an explicit, confirmed user click. It returns a
//   NEW upper graph with a snapshot copy of one lower node; neither input graph is mutated, and no link stays alive.
import type {WorkspaceIdentity} from '../../workspace/contracts';
import {NODE_TYPES, type CanvasKind, type CvGraph, type CvNode, type NodeType} from './RebuildCanvas';

export const LOWER_KEY_PREFIX = 'poemseed.dualcv.lower.v1';
export function lowerCanvasStore(kind: CanvasKind, id: WorkspaceIdentity): {key: string; persist: 'local' | 'session'} {
  if (id.kind === 'real') return {key: `${LOWER_KEY_PREFIX}::${kind}::${id.scope.userId}::${id.scope.projectId}::${id.scope.projectInstanceId}`, persist: 'local'};
  return {key: `${LOWER_KEY_PREFIX}::${kind}::${id.key}`, persist: 'session'};
}
const relabel = (kind: CanvasKind, id: NodeType['id'], label: string): NodeType => ({...NODE_TYPES[kind].find(t => t.id === id)!, label});
/** Lower palette = enrichment only (references / style / variation / notes). Every id also exists in the upper palette,
 *  so a node copied up renders there with its normal type; generation nodes are deliberately absent. */
export const LOWER_TYPES: Record<CanvasKind, NodeType[]> = {
  image: [relabel('image', 'image_reference', '参考图'), relabel('image', 'asset_reference', '资产引用'), relabel('image', 'image_style', '风格'),
    relabel('image', 'image_prompt', '变体提示词'), relabel('image', 'text_input', '灵感 / 细节文本')],
  video: [relabel('video', 'image_reference', '参考图'), relabel('video', 'director_note', '导演备注 / 风格'),
    relabel('video', 'storyboard_prompt', '变体镜头提示词'), relabel('video', 'text_input', '灵感 / 细节文本')],
};
let seq = 0;
/** Snapshot-copy one lower node into a NEW upper graph (to the right of the upper's rightmost node). Pure. */
export function feedToUpper(upper: CvGraph, node: CvNode): {graph: CvGraph; id: string} {
  const id = `fed${Date.now().toString(36)}${(seq++).toString(36)}`;
  const maxX = upper.nodes.length ? Math.max(...upper.nodes.map(n => n.x)) : -200;
  const minY = upper.nodes.length ? Math.min(...upper.nodes.map(n => n.y)) : 0;
  const copy: CvNode = {id, t: node.t, x: Math.round((maxX + 220) / 10) * 10, y: minY, title: `↑${node.title}`,
    ...(node.assetId ? {assetId: node.assetId} : {}),
    ...(node.assetSha256 ? {assetSha256: node.assetSha256} : {}),
    ...(node.assetVersion != null ? {assetVersion: node.assetVersion} : {})};
  return {graph: {nodes: [...upper.nodes, copy], edges: [...upper.edges]}, id};
}
