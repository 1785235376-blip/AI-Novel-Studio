// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import type { ExperimentalClient } from './api';
import { ProductionLineagePanel } from './ProductionLineagePanel';

afterEach(() => cleanup());

it.each([false, true])('preserves the existing determinism label and keeps synthetic boundaries explicit (%s)', async deterministic => {
  const manifest = {
    id: 'manifest', version: 1, status: 'RECORDED', created_at: '2026-10-06T00:00:00Z', task_id: 'original-task', task_version: 3,
    operation: 'cover_generation', input_digest: 'input', manifest_digest: 'manifest-digest', adapter_id: deterministic ? 'mock-image-v1' : 'registered-image:fixture',
    model_id: 'fixture-model', parameters: { candidate_count: 1 }, seed: { value: 7 }, environment: null, input_versions: [], outputs: [],
  };
  const api = {
    get: vi.fn(async (path: string) => ({ items: path === '/production/manifests' ? [manifest] : [] })),
    post: vi.fn(async () => ({ manifest_id: manifest.id, manifest_version: 1, ready: true, blockers: [], preflight_digest: 'preflight',
      broker_decision_id: null, broker_decision_version: null, cost: { state: 'ESTIMATE', currency: 'USD', estimate_microusd: 0 },
      states: { traceable: true, rebuildable: false, replayable: true, deterministic, byte_equal: null } })),
  } as unknown as ExperimentalClient;
  render(<ProductionLineagePanel client={api} manifestsEnabled />);
  fireEvent.click(await screen.findByRole('button', { name: '清单 cover_generation · 2026-10-06T00:00:00Z' }));
  expect(screen.getByRole('region', { name: '生产复现证据级别' }).textContent).toContain('确定性只对合成协议成立');
  expect(screen.getByText(/有 seed 也不保证真实模型逐字节一致/)).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: '检查重放条件' }));
  const quote = await screen.findByRole('region', { name: '重放预检' });
  expect(within(quote).getByText(`确定性协议可复现：${deterministic ? '是' : '否'}`)).toBeTruthy();
  expect(within(quote).getByText('输出逐字节一致：尚未比较')).toBeTruthy();
  expect(api.post).toHaveBeenCalledTimes(1);
  expect(api.post).toHaveBeenCalledWith('/production/manifests/manifest/preflight', { expected_version: 1 });
});
