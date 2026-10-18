import type { CreativeDocument } from './types';
import { validStoryboardDocument } from './storyboardEditorHandoff';
import { checkedPlanningSnapshot, type PlanningSnapshot } from './studioProductionGraphContract';

/** Exact original-owner readback. A Director review never approves this new draft. */
export function storyboardCanvasSnapshot(document: CreativeDocument, digest: string, source: PlanningSnapshot,
  currentSource: CreativeDocument, currentDigest: string, expected?: PlanningSnapshot): PlanningSnapshot {
  checkedPlanningSnapshot(source);
  const ancestry = document.source_documents?.[source.id];
  if (!validStoryboardDocument(document) || document.status !== 'DRAFT' || document.id === source.id
    || ancestry?.version !== source.version || ancestry.digest !== source.digest
    || currentSource.mode !== 'DIRECTOR' || currentSource.id !== source.id || currentSource.version !== source.version || currentDigest !== source.digest) {
    throw new Error('分镜草稿或导演来源已变化，请重新核对；未添加图节点。');
  }
  const pin = checkedPlanningSnapshot({ id: document.id, version: document.version, digest });
  if (expected && (pin.id !== expected.id || pin.version !== expected.version || pin.digest !== expected.digest)) {
    throw new Error('分镜版本或摘要不匹配，请重新读取原文档；未更换绑定。');
  }
  return pin;
}
