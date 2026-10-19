import { checkedDirectorSceneScopeResult, sameDirectorSceneScopeContent } from './directorSceneScope';
import { documentInput, type CreativeDocument } from './types';
import { checkedPlanningSnapshot, type PlanningSnapshot } from './studioProductionGraphContract';

/** Ephemeral UI authority only. Neither this token nor review provenance is Graph data. */
export type PlanningCanvasHandoff = {
  scope: object;
  verificationScope: object;
  isVerificationCurrent: () => boolean;
  available: boolean;
  insert: (pin: PlanningSnapshot, scope: object) => boolean;
};
export type ReviewedDirectorCanvasHandoff = PlanningCanvasHandoff;
export type ReviewedDirectorReceipt = Pick<CreativeDocument, 'id' | 'version'> & { expectedSnapshot?: PlanningSnapshot };

export function reviewedDirectorSnapshot(receipt: ReviewedDirectorReceipt, document: CreativeDocument, digest: string, expected?: PlanningSnapshot): PlanningSnapshot {
  if (document.mode !== 'DIRECTOR' || document.status !== 'DRAFT'
    || document.id !== receipt.id || document.version !== receipt.version) {
    throw new Error('审核后的导演草稿已变化，请重新读取原建议状态；不会采用其它版本。');
  }
  const pin = checkedPlanningSnapshot({ id: document.id, version: document.version, digest });
  if (expected && (pin.id !== expected.id || pin.version !== expected.version || pin.digest !== expected.digest)) {
    throw new Error('同一审核版本的摘要不匹配，请核对原文档；不会更换绑定。');
  }
  return pin;
}

/** Explicit author derivation is not an AI-review approval or execution grant. */
export type SceneDirectorCanvasReceipt = {
  document: CreativeDocument; source: CreativeDocument; snapshot: PlanningSnapshot;
  responsibility: string; sceneIds: string[];
};
export function checkedSceneDirectorSource(receipt: SceneDirectorCanvasReceipt, document: CreativeDocument, digest: string): void {
  if (document.mode !== 'DIRECTOR' || document.status === 'ARCHIVED' || document.id !== receipt.snapshot.id
    || document.version !== receipt.snapshot.version || digest !== receipt.snapshot.digest
    || !sameDirectorSceneScopeContent(documentInput(document), documentInput(receipt.source)))
    throw new Error('子导演的原来源已变化，请重新核对；未更换来源或添加节点。');
}
export function sceneDirectorSnapshot(receipt: SceneDirectorCanvasReceipt, document: CreativeDocument, digest: string): PlanningSnapshot {
  checkedDirectorSceneScopeResult(receipt.document, receipt.source, receipt.snapshot, receipt.responsibility, receipt.sceneIds);
  checkedDirectorSceneScopeResult(document, receipt.source, receipt.snapshot, receipt.responsibility, receipt.sceneIds);
  if (document.id !== receipt.document.id || document.version !== receipt.document.version
    || !sameDirectorSceneScopeContent(documentInput(document), documentInput(receipt.document)))
    throw new Error('子导演回读不是刚创建的精确版本，请核对原目录；未添加节点。');
  return checkedPlanningSnapshot({ id: document.id, version: document.version, digest });
}
