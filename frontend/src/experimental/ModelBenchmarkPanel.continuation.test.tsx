// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { ModelBenchmarkPanel } from './ModelBenchmarkPanel';
import { modelBrokerClient } from './modelBrokerClient';
import { experimentalClient } from './api';
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
it('keeps catalog claims distinct and requires explicit bounded user-verification review', async () => {
  const fetch = vi.fn(async (url: string, init: RequestInit) => new Response(JSON.stringify(
    url.endsWith('/profiles') ? { items: [{ route_id: 'route', provider_id: 'mock', model_id: 'synthetic', evidence_tiers: ['CATALOG_CLAIM', 'CONTRACT_TESTED'], synthetic: true, user_verified: false }] } :
    url.endsWith('/status') ? { sets: [], runs: [], comparisons: [], evidence: [{ id: 'evidence', version: 2, origin: 'EXECUTED', evidence_state: 'CURRENT', verification: 'SYNTHETIC_PROTOCOL_ONLY', status: 'RECORDED', metrics: { sample_count: 1, latency_ms: 2, rule_pass_count: 1 } }] } : { id: 'review' }
  ), { status: 200 }));
  vi.stubGlobal('fetch', fetch);
  render(<ModelBenchmarkPanel api={modelBrokerClient(experimentalClient('n', { sessionToken: 'trusted' }))} routes={[]} />);
  await screen.findByText(/CATALOG_CLAIM · CONTRACT_TESTED/);
  expect(fetch.mock.calls.every(([, init]) => init.method === 'GET')).toBe(true);
  const button = screen.getByRole('button', { name: '记录本次人工验证' }) as HTMLButtonElement;
  expect(button.disabled).toBe(true);
  fireEvent.change(screen.getByLabelText('证据 evidence 的核对说明'), { target: { value: 'Only these synthetic outputs checked.' } });
  fireEvent.click(screen.getByLabelText('我已检查本次模型身份和保存的原始输出，仅确认本组样本'));
  fireEvent.click(button);
  await waitFor(() => expect(fetch.mock.calls.some(([url]) => url.endsWith('/evidence/evidence/review'))).toBe(true));
  const init = fetch.mock.calls.find(([url]) => url.endsWith('/evidence/evidence/review'))![1];
  expect(JSON.parse(String(init.body))).toEqual({ expected_version: 2, note: 'Only these synthetic outputs checked.', reviewed_identity_and_outputs: true });
  expect(fetch.mock.calls.some(([url]) => /generate|\/runs/.test(url))).toBe(false);
});
