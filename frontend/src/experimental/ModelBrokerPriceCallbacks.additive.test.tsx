// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import type { Chapter } from '../api';
import { experimentalClient } from './api';
import { ModelBrokerPanel } from './ModelBrokerPanel';
import { modelBrokerPriceDraft } from './modelBrokerPriceDraft';

const context = { sessionToken: 'isolated-review-context', scope: { workspaceId: 'review', projectId: 'review-price', storylineId: 'story', branchId: 'branch' } };
const local = { route_id: 'review-local', provider_id: 'review-local', model_id: 'no-runtime-model', display_name: '本地审查夹具',
  capability: 'TEXT', available: true, cloud: false, synthetic: false, fingerprint: 'a'.repeat(64), reasons: [], context_window: null,
  verification: 'ADAPTER_CONTRACT_ONLY', identity: {} };
const cloud = { ...local, route_id: 'review-cloud', provider_id: 'review-cloud', display_name: '云端审查夹具', cloud: true, fingerprint: 'b'.repeat(64) };
const priceA = { id: 'price-a', version: 7, route_id: local.route_id, route_fingerprint: local.fingerprint, currency: 'USD',
  reserve_microusd: 0, input_per_million_microusd: 0, output_per_million_microusd: null, source: 'LOCAL_RECORD_A',
  as_of: '2026-10-01T00:00:00Z', expires_at: '2099-07-08T15:16:17.123456+05:30', applicability: 'per_request' };
const priceB = { ...priceA, id: 'price-b', route_id: cloud.route_id, route_fingerprint: cloud.fingerprint,
  reserve_microusd: 90, input_per_million_microusd: null, output_per_million_microusd: 300, source: 'CLOUD_RECORD_B',
  expires_at: '2099-08-09T10:11:12.654321Z' };
const budget = { version: 1, limit_microusd: 100, max_inflight: 1, require_known_estimate: true, committed_microusd: 0, inflight: 0, unknown_count: 0, overrun_count: 0 };
const labels = ['每请求保守预占（µUSD）', '价格依据（来源或报价说明）', '价格有效至', '输入费率（每百万 Token 的 µUSD；可空）', '输出费率（每百万 Token 的 µUSD；可空）'];
const field = (label: string) => screen.getByLabelText(label) as HTMLInputElement;
const values = () => labels.map(label => field(label).value);
const click = (name: string) => fireEvent.click(screen.getByRole('button', { name }));
const retained = (name: string) => { const button = screen.getByRole('button', { name }); return (button as any)[Object.keys(button).find(key => key.startsWith('__reactProps$'))!].onClick as () => void; };
function setup() {
  let prices: any[] = structuredClone([priceA, priceB]);
  const requests: { url: string; method: string; body?: any; response?: number }[] = [];
  const fetcher = vi.fn(async (url: string, init?: RequestInit) => {
    const call = { url, method: init?.method || 'GET', body: init?.body ? JSON.parse(String(init.body)) : undefined, response: 200 };
    requests.push(call);
    if (url.endsWith('/model-broker/status')) return new Response(JSON.stringify({ candidates: [local, cloud], prices, budget, author_execution_available: false }));
    if (url.endsWith('/model-broker/history')) return new Response(JSON.stringify({ decisions: [], ledger: [] }));
    if (url.endsWith('/model-broker/price')) {
      const old = prices.find(row => row.route_id === call.body.route_id);
      if (call.body.expected_version !== old.version) { call.response = 409; return new Response(JSON.stringify({ detail: { code: 'EXPERIMENTAL_VERSION_CONFLICT' } }), { status: 409 }); }
      const next = { ...old, ...call.body, version: old.version + 1 }; prices = prices.map(row => row === old ? next : row);
      return new Response(JSON.stringify(next));
    }
    throw new Error(`Unapproved synthetic request ${call.method} ${url}`);
  });
  vi.stubGlobal('fetch', fetcher);
  const view = render(<ModelBrokerPanel client={experimentalClient('review-price', context)} novelId="review-price" context={context}
    chapter={{ id: 'review-chapter', version: 1, title: 'Isolated price review' } as Chapter} />);
  return { requests, view, replace: (next: any[]) => { prices = structuredClone(next); }, puts: () => requests.filter(row => row.url.endsWith('/model-broker/price')) };
}
async function choose(route = local.route_id) { await screen.findByLabelText('价格适用路线'); fireEvent.change(field('价格适用路线'), { target: { value: route } }); }
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

it('price1 explicit current load preserves zero/null rates and full timezone/microsecond expiry through only the original local price PUT', async () => {
  const f = setup(); await choose();
  click('载入此路线已有价格依据'); expect(values().slice(0, 2)).toEqual(['0', priceA.source]);
  expect(values().slice(3)).toEqual(['0', '']); expect(f.requests.every(row => row.method === 'GET')).toBe(true);
  const draft = modelBrokerPriceDraft(priceA, local)!;
  expect(draft.sourceExpiry).toBe(priceA.expires_at); expect(new Date(draft.expiry).getTime()).toBe(new Date(priceA.expires_at).getTime());
  expect(modelBrokerPriceDraft({ ...priceA, expires_at: '2099-07-08T15:16:17' }, local)).toBeUndefined();
  expect(modelBrokerPriceDraft({ ...priceA, route_fingerprint: 'c'.repeat(64) }, local)).toBeUndefined();
  click('保存路线价格依据'); await waitFor(() => expect(f.puts()).toHaveLength(1));
  expect(f.puts()[0].body).toMatchObject({ route_id: local.route_id, route_fingerprint: local.fingerprint, expected_version: 7,
    source: priceA.source, expires_at: priceA.expires_at, reserve_microusd: 0, input_per_million_microusd: 0, output_per_million_microusd: null });
  expect(f.requests.filter(row => row.method !== 'GET').map(row => row.url.endsWith('/model-broker/price'))).toEqual([true]);
  expect(f.requests.some(row => /credential|preview|generate|execute|https?:/.test(row.url))).toBe(false);
});

it('price2 old local Load must not replace a freshly loaded cloud record or feed it into the cloud price PUT', async () => {
  const f = setup(); await choose(); click('载入此路线已有价格依据'); const oldLoad = retained('载入此路线已有价格依据');
  await choose(cloud.route_id); expect(values()).toEqual(['', '', '', '', '']);
  click('载入此路线已有价格依据'); const before = values();
  act(() => oldLoad()); const after = values();
  expect(field('价格适用路线').value).toBe(cloud.route_id);
  click('保存路线价格依据'); await waitFor(() => expect(f.puts()).toHaveLength(1));
  console.info(JSON.stringify({ scenario: 'route-switch', route: field('价格适用路线').value, before, after,
    captured_mock_price_PUT: f.puts()[0], real_network: false }));
  expect(f.puts()[0].body.source).toBe(priceB.source);
});

it('price3 same-ID price-version refresh must retire old Load while keeping original version conflicts authoritative', async () => {
  const f = setup(); await choose(); click('载入此路线已有价格依据'); const oldLoad = retained('载入此路线已有价格依据');
  const newer = { ...priceA, version: 8, reserve_microusd: 77, source: 'LOCAL_RECORD_V8', expires_at: '2099-10-11T12:13:14.111222Z' };
  f.replace([newer, priceB]); click('重新读取当前注册状态');
  await waitFor(() => expect(f.requests.filter(row => row.url.endsWith('/model-broker/status'))).toHaveLength(2));
  await waitFor(() => expect((screen.getByRole('button', { name: '载入此路线已有价格依据' }) as HTMLButtonElement).disabled).toBe(false));
  click('载入此路线已有价格依据'); expect(field(labels[1]).value).toBe(newer.source);
  act(() => oldLoad()); const after = values();
  click('保存路线价格依据'); await waitFor(() => expect(f.puts()).toHaveLength(1));
  console.info(JSON.stringify({ scenario: 'same-route-new-version', after, captured_mock_price_PUT: f.puts()[0], real_network: false }));
  expect(f.puts()[0].body.expected_version).toBe(8); expect(f.puts()[0].body.source).toBe(newer.source);
});


it.each(['route-aba', 'version', 'draft-edit', 'unmount'])('price-intent4 retires retained Save after %s while a current intent remains usable', async change => {
  const f = setup(); await choose(); click('载入此路线已有价格依据');
  const oldSave = retained('保存路线价格依据');
  if (change === 'route-aba') {
    await choose(cloud.route_id); await choose(local.route_id); click('载入此路线已有价格依据');
  } else if (change === 'version') {
    f.replace([{ ...priceA, version: 8, source: 'CURRENT_V8' }, priceB]); click('重新读取当前注册状态');
    await waitFor(() => expect(f.requests.filter(row => row.url.endsWith('/model-broker/status'))).toHaveLength(2));
    await waitFor(() => expect((screen.getByRole('button', { name: '载入此路线已有价格依据' }) as HTMLButtonElement).disabled).toBe(false));
    click('载入此路线已有价格依据');
  } else if (change === 'draft-edit') {
    fireEvent.change(field(labels[1]), { target: { value: 'CURRENT_USER_EDIT' } });
  } else f.view.unmount();
  await act(async () => oldSave());
  expect(f.puts()).toHaveLength(0);
  if (change !== 'unmount') {
    const currentSource = field(labels[1]).value;
    click('保存路线价格依据'); await waitFor(() => expect(f.puts()).toHaveLength(1));
    expect(f.puts()[0].body.source).toBe(currentSource);
    expect(f.puts()[0].body.expected_version).toBe(change === 'version' ? 8 : 7);
  }
});
