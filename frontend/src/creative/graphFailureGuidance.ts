/** Advice only: codes remain the original owner's facts, never retry authority. */
export function graphFailureGuidance(code?: string): string {
  switch (code) {
    case 'CREATIVE_GRAPH_REQUIRED_INPUT_MISSING':
    case 'CREATIVE_GRAPH_UPSTREAM_OUTPUT_MISSING':
      return '检查此节点的必需输入连接与上游审核回执；未确认来源前不要提交新任务。';
    case 'CREATIVE_GRAPH_TEXT_REQUIRED':
      return '在节点检查器补充作者文本，明确保存后重新核对运行范围。';
    case 'CREATIVE_GRAPH_DISABLED_DEPENDENCY':
      return '检查此节点或上游节点是否停用；由作者决定启用或调整连接，保存后重新预检。';
    case 'CREATIVE_GRAPH_EXTERNAL_REFERENCE_CHANGED':
      return '重新核对原资产的权限、版本和内容；更新引用需明确保存并重新预检。';
    case 'CREATIVE_GRAPH_ATOMIC_INPUT_OWNER_ADAPTER_REQUIRED':
      return '检查当前图 schema 与原资产输入适配支持；不能仅凭此提示执行或绕过原能力限制。';
    case 'CREATIVE_GRAPH_MEDIA_RUNTIME_UNAVAILABLE':
      return '当前入口缺少所需原处理能力。请检查原模块配置，不能仅凭此提示执行。';
    default:
      return '先重新读取当前运行，核对原任务回执与节点输入。结果未知时保留原请求身份，不要重复提交；此提示不代表可以重试。';
  }
}
