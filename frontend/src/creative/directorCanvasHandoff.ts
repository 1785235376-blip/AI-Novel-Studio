import type { CreativeDocument } from './types';
import { checkedPlanningSnapshot, type PlanningSnapshot } from './studioProductionGraphContract';

/** Ephemeral UI authority only. Neither this token nor review provenance is Graph data. */
export type ReviewedDirectorCanvasHandoff = {
  scope: object;
  verificationScope: object;
  isVerificationCurrent: () => boolean;
  available: boolean;
  insert: (pin: PlanningSnapshot, scope: object) => boolean;
};
export type ReviewedDirectorReceipt = Pick<CreativeDocument, 'id' | 'version'>;

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
