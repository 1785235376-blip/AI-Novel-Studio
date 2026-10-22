// [HERMIA-FE-20261022 R7-FIX3] 后端 ALL_CAPS 错误码 → 中文可见文案；禁止把原始码直接渲到界面。
/** Known runtime / readiness / vault / plugin isolation codes → Chinese. */
const CODE_LABELS: Record<string, string> = {
  KEYRING_NOT_INSTALLED: '系统密钥库未安装',
  KEYRING_BACKEND_UNUSABLE: '系统密钥库不可用',
  VAULT_MEMORY_BACKEND: '密钥仅保存在内存',
  PROVIDERS_PARTIALLY_CONFIGURED: '部分服务商未配置完整',
  DENY_ALL: '全部拒绝',
  NOT_CONFIGURED: '未配置',
  DEGRADED: '降级',
  READY: '就绪',
  BLOCKED: '已阻断',
  PASS: '通过',
  FAIL: '失败',
  SKIP: '跳过',
  DEFERRED: '延期',
};

const ALL_CAPS = /^[A-Z][A-Z0-9_]{1,80}$/;

/** Map a backend code (or leave human text). Unknown ALL_CAPS codes become fallback, never raw. */
export function runtimeCodeLabel(code: string | null | undefined, fallback = '状态异常'): string {
  if (code == null || code === '') return fallback;
  const trimmed = String(code).trim();
  if (CODE_LABELS[trimmed]) return CODE_LABELS[trimmed];
  if (ALL_CAPS.test(trimmed)) return fallback;
  return trimmed;
}

/** Vault / keyring degraded_reason on provider cards — fixed Chinese, no raw code. */
export function vaultDegradedNote(reason?: string | null): string {
  const label = runtimeCodeLabel(reason, '系统密钥库不可用');
  return `系统凭据库不可用：${label}。当前凭据不会跨进程保留。`;
}

/** Release readiness status badge text. */
export function readinessStatusLabel(status?: string | null, error = false): string {
  if (error) return '未知';
  if (!status) return '读取中';
  if (status === 'READY') return '就绪';
  if (status === 'BLOCKED') return '已阻断';
  if (status === 'DEGRADED') return '降级';
  return runtimeCodeLabel(status, '状态未知');
}

/** Plugin runtime sandbox / isolation display. */
export function pluginRuntimeBoundaryLabel(kind: 'sandbox' | 'isolation', value?: string | null): string {
  if (!value) return kind === 'isolation' ? '全部拒绝' : '未读取';
  return runtimeCodeLabel(value, kind === 'isolation' ? '全部拒绝' : '未配置');
}
