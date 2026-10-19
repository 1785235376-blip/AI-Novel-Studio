import { checkedStudioGraphDraft } from './studioGraphClient';
import { checkedPlanningDocument, checkedPlanningSnapshot, type PlanningDocument } from './studioProductionGraphContract';
import type { StudioGraphDefinition } from './studioGraphTypes';
import { checkedStoryboardReceipt, type StoryboardReceipt } from './studioStoryboardContract';

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

/** All directly bound Shot nodes for this source, including disabled references. */
export function planningStoryboardShotReferences(draft: StudioGraphDefinition, nodeId: string) {
  if (draft.schema_version !== 5 || draft.nodes.find(node => node.id === nodeId)?.definition_id !== 'storyboard_plan') return [];
  const parents = new Set(planningSourceReferences(draft, nodeId).map(reference => reference.nodeId));
  const targets = new Set(draft.edges.filter(edge => parents.has(edge.source_node_id)
    && edge.source_port === 'storyboard' && edge.target_port === 'storyboard').map(edge => edge.target_node_id));
  return draft.nodes.filter(node => node.definition_id === 'storyboard_shot' && targets.has(node.id));
}

/** A coupled author-only fork; never invent shot versions or inherit approval. */
export function planningStoryboardSourceFork(draft: StudioGraphDefinition, nodeId: string, document: PlanningDocument,
  value: StoryboardReceipt, nodeIds: readonly string[]) {
  if (draft.schema_version !== 5 || draft.nodes.find(node => node.id === nodeId)?.definition_id !== 'storyboard_plan')
    throw new Error('请选择原 v5 分镜来源节点。');
  const receipt = checkedStoryboardReceipt(value, document.id), current = checkedPlanningDocument(document);
  if (current.mode !== 'STORYBOARD' || !receipt.approved || receipt.document_snapshot.version !== current.version
    || receipt.document_snapshot.digest !== current.digest) throw new Error('新分镜版本或审核回执不一致，请重新核对。');
  const references = planningSourceReferences(draft, nodeId);
  if (references.some(reference => reference.snapshot.version > current.version
    || reference.snapshot.version === current.version && reference.snapshot.digest !== current.digest))
    throw new Error('图中同来源版本与本次回执冲突，未准备新图。');
  const old = references.filter(reference => reference.snapshot.version < current.version);
  if (nodeIds.length !== old.length || old.some(reference => !nodeIds.includes(reference.nodeId)))
    throw new Error('须一并更新这份分镜的全部旧引用，不能遗留旧镜头来源。');
  const parentIds = new Set(nodeIds), shots = planningStoryboardShotReferences(draft, nodeId).filter(shot =>
    draft.edges.some(edge => parentIds.has(edge.source_node_id) && edge.target_node_id === shot.id && edge.target_port === 'storyboard'));
  if (!shots.length || shots.length > 4) throw new Error('本次只支持 1–4 个已连接的原镜头节点，不会自动截断。');
  const next = planningSourceFork(draft, nodeId, current, nodeIds);
  const changes = shots.map(node => {
    const shot = receipt.shots.find(shot => shot.shot_id === node.parameters.shot_id);
    if (!shot) throw new Error('原镜头已从新分镜移除；请重新选择分镜链，不能猜测替代镜头。');
    const target = next.nodes.find(target => target.id === node.id)!;
    target.parameters = { ...target.parameters, shot_version: shot.shot_version, shot_digest: shot.shot_digest };
    return { nodeId: node.id, shotId: shot.shot_id, number: shot.shot.number,
      before: { version: node.parameters.shot_version!, digest: node.parameters.shot_digest! },
      after: { version: shot.shot_version, digest: shot.shot_digest } };
  });
  checkedStudioGraphDraft(next);
  return { definition: next, documents: old.map(reference => ({ nodeId: reference.nodeId, before: reference.snapshot,
    after: { ...receipt.document_snapshot } })), shots: changes };
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
