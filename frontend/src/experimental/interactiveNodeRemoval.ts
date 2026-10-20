import type { StorySpec } from './interactiveStoryClient';

/** Local membership edit only. Source authorization and persistence remain with the original owner. */
export function previewNodeRemoval(spec: StorySpec, nodeId: string) {
  const matches = spec.nodes.filter(node => node.node_id === nodeId);
  const incoming = spec.nodes.flatMap(node => node.choices.filter(choice => choice.target === nodeId).map(choice => ({ nodeId: node.node_id, choiceId: choice.id })));
  const blockers: string[] = [];
  if (!nodeId || matches.length !== 1 || new Set(spec.nodes.map(node => node.node_id)).size !== spec.nodes.length || !spec.nodes.some(node => node.node_id === spec.entry_node_id)) blockers.push('节点或入口标识无法唯一匹配，不能移除。');
  if (spec.nodes.length <= 1) blockers.push('必须保留至少一个互动节点。');
  if (spec.entry_node_id === nodeId) blockers.push('这是故事入口。请先用「故事入口节点」明确选择其他入口。');
  if (incoming.length) blockers.push('仍有选择指向此节点。请先用原有选择控件逐一改指或移除这些选择，再预览。');
  return { spec, nodeId, node: matches.length === 1 ? matches[0] : undefined, incoming, blockers };
}

export type NodeRemovalPreview = ReturnType<typeof previewNodeRemoval>;

/** A preview is tied to the exact immutable draft; equal-looking replacement drafts are stale. */
export function applyNodeRemoval(spec: StorySpec, preview: NodeRemovalPreview): StorySpec | undefined {
  if (preview.spec !== spec || preview.blockers.length || previewNodeRemoval(spec, preview.nodeId).blockers.length) return;
  return { ...spec, nodes: spec.nodes.filter(node => node.node_id !== preview.nodeId) };
}
