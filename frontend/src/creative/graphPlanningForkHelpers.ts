import { checkedStudioGraphDraft } from './studioGraphClient';
import { checkedPlanningDocument, checkedPlanningSnapshot, type PlanningDocument } from './studioProductionGraphContract';
import type { StudioGraphDefinition } from './studioGraphTypes';

export type PlanningSourceReference = { nodeId: string; snapshot: ReturnType<typeof checkedPlanningSnapshot> };
export function planningSourceReferences(draft: StudioGraphDefinition, nodeId: string): PlanningSourceReference[] {
  const selected = draft.nodes.find(value => value.id === nodeId);
  if (!selected || !['director_plan', 'storyboard_plan'].includes(selected.definition_id)) return [];
  const source = checkedPlanningSnapshot(selected.parameters.document_snapshot, true);
  return draft.nodes.filter(value => value.definition_id === selected.definition_id).flatMap(value => {
    const snapshot = checkedPlanningSnapshot(value.parameters.document_snapshot, true);
    return snapshot.id === source.id ? [{ nodeId: value.id, snapshot }] : [];
  });
}

/** A new author draft only. Saved graph pins, history and execution stay untouched. */
export function planningSourceFork(draft: StudioGraphDefinition, nodeId: string, document: PlanningDocument, nodeIds: readonly string[] = [nodeId]): StudioGraphDefinition {
  checkedStudioGraphDraft(draft);
  const node = draft.nodes.find(value => value.id === nodeId);
  if (!node || !['director_plan', 'storyboard_plan'].includes(node.definition_id)) throw new Error('请选择导演或分镜来源节点。');
  const previous = checkedPlanningSnapshot(node.parameters.document_snapshot, true);
  const next = checkedPlanningDocument(document);
  const mode = node.definition_id === 'director_plan' ? 'DIRECTOR' : 'STORYBOARD';
  if (next.id !== previous.id || next.mode !== mode || next.version <= previous.version || next.digest === previous.digest) {
    throw new Error('未找到同一来源的更新版本；原图与草稿保持不变。');
  }
  if (!Array.isArray(nodeIds) || !nodeIds.length || new Set(nodeIds).size !== nodeIds.length || !nodeIds.includes(nodeId)) {
    throw new Error('更新节点范围无效，原图与草稿保持不变。');
  }
  const references = planningSourceReferences(draft, nodeId);
  for (const id of nodeIds) {
    const reference = references.find(value => value.nodeId === id);
    if (!reference || reference.snapshot.version >= next.version || reference.snapshot.digest === next.digest) {
      throw new Error('所选节点不是同一来源的旧版本，未准备新图。');
    }
  }
  const value = structuredClone(draft);
  for (const id of nodeIds) value.nodes.find(item => item.id === id)!.parameters.document_snapshot = {
      id: next.id, version: next.version, digest: next.digest,
    };
  checkedStudioGraphDraft(value);
  return value;
}
