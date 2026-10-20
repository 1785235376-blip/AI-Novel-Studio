import type { StudioGraphDefinitionId } from './studioGraphTypes';

export const GRAPH_NODE_LABELS: Record<StudioGraphDefinitionId, string> = {
  local_condition: '本地条件（布尔值 / A-B）',
  text_input: '文本输入', text_reference: '文本引用', draft_prepare: '本地草稿整理',
  manual_transform: '手工处理', director_note: '导演备注', human_review: '人工审核', asset_reference: '资产引用', local_subgraph: '受限本地子调用（当前版本）',
  text_generate: '本地文字模型（需明确调用）',
  media_generate: '媒体制作（需分别确认）', media_review: '媒体审核入库',
  timeline_export: '时间线剪辑与导出（需分别确认）',
  storyboard_shot: '分镜镜头（版本绑定）', video_generate: '视频生成（需分别确认）', image_style: '图片风格', image_upscale: '图片超分（需分别确认）', director_plan: '导演节点（已保存文档）', storyboard_plan: '分镜节点（已保存文档）', storyboard_prompt: '分镜镜头提示词',
  image_reference: '图片参考与权重', image_prompt: '图片提示词', image_generate: '图片生成（需分别确认）',
};
export const GRAPH_STATUS_LABELS: Record<string, string> = {
  SKIPPED: '已跳过',
  QUEUED: '待执行', RUNNING: '执行中', WAITING_APPROVAL: '等待审核', PAUSED: '已暂停',
  SUCCEEDED: '已完成', FAILED: '失败', CANCELLED: '已取消', REJECTED: '已驳回',
};
