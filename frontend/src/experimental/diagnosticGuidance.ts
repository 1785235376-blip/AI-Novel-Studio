// Explanations for codes registered by the original workspace diagnostics owner
// (app/experimental/ux.py SAFE_CODES). These are advice, never a retry policy.
const guidance: Record<string, string> = {
  TIMEOUT: '等待超时不代表任务未执行。先在原任务工具核对结果与费用，再决定是否重新提交。',
  CANCELLED: '原服务报告已取消。先核对已有结果；取消不保证撤回已完成的输出或退回费用。',
  PERMISSION_DENIED: '当前身份没有所需权限。核对工作区、项目与分支，并请项目管理员确认授权；不要反复提交。',
  VERSION_CONFLICT: '保留当前草稿，在原工具读取最新版本并比较差异，再决定如何处理冲突。',
  EXPERIMENTAL_VERSION_CONFLICT: '保留当前草稿，在原工具读取最新版本并比较差异，再决定如何处理冲突。',
  SOURCE_STALE: '来源已经变化。在原工具核对来源版本并重新预览影响，原批准不应直接用于新来源。',
  EXPERIMENTAL_SOURCE_STALE: '来源已经变化。在原工具核对来源版本并重新预览影响，原批准不应直接用于新来源。',
  ADAPTER_REQUIRED: '原流程缺少所需适配器。查看原工具的兼容说明；诊断不会安装适配器或切换服务。',
  PROVIDER_UNAVAILABLE: '原服务报告提供方不可用。检查所选路线的配置与状态；此处没有验证模型服务，也不会切换到云端。',
  NETWORK_ERROR: '通信失败时结果可能未知。先核对原任务状态，避免重复提交；诊断不会修改网络设置。',
  MEDIA_TASK_TRANSITION_INVALID: '原任务当前阶段不接受该操作。刷新原任务，核对阶段与可用操作后再决定。',
};

export function diagnosticGuidance(code: string): string {
  return Object.prototype.hasOwnProperty.call(guidance, code)
    ? guidance[code]
    : '未提供可确认的错误分类，无法仅凭诊断包判断原因。请在原任务工具核对状态与来源；不要自动重试或提交原始日志。';
}
