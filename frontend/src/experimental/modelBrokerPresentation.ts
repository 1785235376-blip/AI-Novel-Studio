/** Presentation of existing broker evidence only: never probes or grants a route. */
export const brokerCost = (value: number | null | undefined) => value == null || !Number.isFinite(value)
  ? '未知（不能当作免费）' : `${value / 1_000_000} USD（${value} µUSD）`;
const reasons: Record<string, string> = {
  VISION_MODEL_ADMISSION_NOT_CONFIGURED: '视觉/OCR 的真实任务执行链尚未接通；模型声明不代表可运行',
  MODEL_DISABLED: '模型未启用；请在原模型配置中核对',
  PROVIDER_NOT_CONFIGURED: 'Provider 尚未配置；请在 AI 主控中心核对配置',
  PROVIDER_UNAVAILABLE: 'Provider 当前不可用；请在原配置入口核对状态',
  CREDENTIAL_UNAVAILABLE: '缺少可用凭据；请在 AI 主控中心核对，勿把密钥写入创作要求',
  HOST_CLOUD_DISABLED: '服务器未允许云端；此处不会更改服务器设置',
  EXPLICIT_MODEL_CENTER_ENABLE_REQUIRED: '需要在 Model Center 明确启用本地模型',
  LOCAL_ONLY_POLICY: '当前仅本地隐私模式排除云端；如需云端请自行核对并选择隐私模式',
  LOCAL_TO_CLOUD_FALLBACK_NOT_APPROVED: '尚未允许本地优先策略提出云端候选；不会自动回退',
  CURRENT_SOURCE_PRIVACY_BLOCKS_CLOUD: '当前来源隐私不允许外发；不会绕过来源授权',
  HOST_CAPACITY_UNKNOWN_OR_INSUFFICIENT: '主机容量未知或不足；不能据此断言机器无法运行模型',
  CONTEXT_CAPACITY_UNKNOWN_OR_INSUFFICIENT: '上下文容量未知或不满足本次要求',
  LATENCY_EVIDENCE_UNKNOWN_OR_OVER_LIMIT: '缺少当前延迟证据或超过本次限制',
  PRICE_ESTIMATE_REQUIRED: '缺少有效价格估计；请核对下方项目预算与价格来源',
  TASK_BUDGET_EXCEEDED: '估计超过本次预占上限',
  PROJECT_BUDGET_EXCEEDED: '估计超过项目剩余预算',
  SYNTHETIC_NOT_REQUESTED: '合成协议测试未被明确选择',
  CUSTOM_ROUTE_NOT_SELECTED: '未被选为本次指定路线',
};
export const brokerReason = (code: string) => reasons[code] ? `${reasons[code]}（${code}）` : code;
export const brokerVerification = (code: string) => code === 'SYNTHETIC_PROTOCOL_ONLY'
  ? '仅合成协议测试，不代表真实模型能力或连接'
  : '连接未验证；这里只读取注册 / Adapter 声明，不代表实时可达或生成质量';
