import type { StudioGraphDefinitionId } from './studioGraphTypes';

export const GRAPH_NODE_LABELS: Record<StudioGraphDefinitionId, string> = {
  text_input: '文本输入', text_reference: '文本引用', draft_prepare: '本地草稿整理',
  manual_transform: '手工处理', director_note: '导演备注', human_review: '人工审核', asset_reference: '资产引用',
};
export const GRAPH_STATUS_LABELS: Record<string, string> = {
  QUEUED: '待执行', RUNNING: '执行中', WAITING_APPROVAL: '等待审核', PAUSED: '已暂停',
  SUCCEEDED: '已完成', FAILED: '失败', CANCELLED: '已取消', REJECTED: '已驳回',
};
