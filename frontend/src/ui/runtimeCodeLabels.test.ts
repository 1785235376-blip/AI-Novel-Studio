// @vitest-environment node
// [HERMIA-FE-20261022 R7-FIX3]
import { describe, expect, it } from 'vitest';
import { runtimeCodeLabel, vaultDegradedNote, readinessStatusLabel, pluginRuntimeBoundaryLabel } from './runtimeCodeLabels';

describe('runtimeCodeLabels', () => {
  it('maps known ALL_CAPS codes to Chinese', () => {
    expect(runtimeCodeLabel('KEYRING_NOT_INSTALLED')).toBe('系统密钥库未安装');
    expect(runtimeCodeLabel('KEYRING_BACKEND_UNUSABLE')).toBe('系统密钥库不可用');
    expect(runtimeCodeLabel('VAULT_MEMORY_BACKEND')).toBe('密钥仅保存在内存');
    expect(runtimeCodeLabel('PROVIDERS_PARTIALLY_CONFIGURED')).toBe('部分服务商未配置完整');
    expect(runtimeCodeLabel('DENY_ALL')).toBe('全部拒绝');
    expect(runtimeCodeLabel('NOT_CONFIGURED')).toBe('未配置');
    expect(runtimeCodeLabel('DEGRADED')).toBe('降级');
  });

  it('never returns unknown ALL_CAPS codes as-is', () => {
    expect(runtimeCodeLabel('SOME_UNKNOWN_CODE')).toBe('状态异常');
    expect(runtimeCodeLabel('SOME_UNKNOWN_CODE', '发布警告')).toBe('发布警告');
  });

  it('passes through already-human Chinese or mixed text', () => {
    expect(runtimeCodeLabel('本地仅进程')).toBe('本地仅进程');
  });

  it('builds vault note and readiness / plugin boundary labels', () => {
    expect(vaultDegradedNote('KEYRING_NOT_INSTALLED')).toContain('系统密钥库未安装');
    expect(vaultDegradedNote('KEYRING_NOT_INSTALLED')).not.toContain('KEYRING');
    expect(readinessStatusLabel('DEGRADED')).toBe('降级');
    expect(readinessStatusLabel(null, true)).toBe('未知');
    expect(pluginRuntimeBoundaryLabel('isolation', 'DENY_ALL')).toBe('全部拒绝');
    expect(pluginRuntimeBoundaryLabel('sandbox', 'NOT_CONFIGURED')).toBe('未配置');
    expect(pluginRuntimeBoundaryLabel('isolation', undefined)).toBe('全部拒绝');
  });
});
