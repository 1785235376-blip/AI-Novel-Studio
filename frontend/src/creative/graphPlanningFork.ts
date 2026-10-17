import { checkedStudioGraphDraft } from './studioGraphClient';
import { checkedPlanningDocument, checkedPlanningSnapshot, type PlanningDocument } from './studioProductionGraphContract';
import type { StudioGraphDefinition } from './studioGraphTypes';

/** A new author draft only. Saved graph pins, history and execution stay untouched. */
export function planningSourceFork(draft: StudioGraphDefinition, nodeId: string, document: PlanningDocument): StudioGraphDefinition {
  checkedStudioGraphDraft(draft);
  const node = draft.nodes.find(value => value.id === nodeId);
  if (!node || !['director_plan', 'storyboard_plan'].includes(node.definition_id)) throw new Error('请选择导演或分镜来源节点。');
  const previous = checkedPlanningSnapshot(node.parameters.document_snapshot, true);
  const next = checkedPlanningDocument(document);
  const mode = node.definition_id === 'director_plan' ? 'DIRECTOR' : 'STORYBOARD';
  if (next.id !== previous.id || next.mode !== mode || next.version <= previous.version || next.digest === previous.digest) {
    throw new Error('未找到同一来源的更新版本；原图与草稿保持不变。');
  }
  const value = structuredClone(draft);
  value.nodes.find(item => item.id === nodeId)!.parameters.document_snapshot = {
    id: next.id, version: next.version, digest: next.digest,
  };
  checkedStudioGraphDraft(value);
  return value;
}
