// @vitest-environment jsdom
// Extracted additions and migrated variants; protected baseline suite stays byte-identical.
// Migrated variants preserve newer assertions and are not counted as unique new capabilities.
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { ModelBrokerPanel } from './ModelBrokerPanel';

import { experimentalClient } from './api';

import type { Chapter } from '../api';

const chapter = { id: 'chapter-one', title: '测试章', version: 3 } as Chapter;
const context = { sessionToken: 'session-one', scope: { workspaceId: 'w', projectId: 'novel-one', storylineId: 's', branchId: 'b' } };
const route = { route_id: 'a'.repeat(64), provider_id: 'mock', model_id: 'mock-writer', display_name: '真实注册的合成 Adapter', capability: 'TEXT', available: true, cloud: false, synthetic: true, fingerprint: 'b'.repeat(64), reasons: [], context_window: 8192, verification: 'SYNTHETIC_PROTOCOL_ONLY', identity: {} };
const quote = { id: 'quote-one', version: 1, status: 'PREVIEW', chosen: { ...route, cost_state: 'KNOWN_SYNTHETIC_ZERO', price: { reserve_microusd: 0, source: 'builtin' } }, candidates: [{ ...route, eligible: true, cost_state: 'KNOWN_SYNTHETIC_ZERO', price: { reserve_microusd: 0 } }], decision_reason: 'CURRENT_ELIGIBLE_ROUTE_WITH_POLICY_ORDER', warnings: [], will_send: { source_chapter_ids: ['chapter-one'], target: 'local' } };
const status = { candidates: [route], budget: { version: 5, limit_microusd: 100, max_inflight: 1, require_known_estimate: true, committed_microusd: 0, inflight: 0, unknown_count: 0, overrun_count: 0 }, prices: [], author_execution_available: true };
const authorPreview = { contract: 'AUTHOR_REQUEST_V1', preview_digest: 'c'.repeat(64), chapter_id: chapter.id, chapter_version: 3, target: 'local', provider_id: 'mock', model_id: 'mock-writer', prompt_characters: 12, source_characters: 12, source_strategy: 'LAST_2000_SAVED_CHARACTERS', truncation: 'SOURCE_TAIL_2000', token_count: null, context_sections: [], privacy_omissions: [], creation_records: [], request: { prompt: 'Exact synthetic author prompt', context: {}, parameters: {}, system_instruction: null } };
const testSet = { id: 'set-one', version: 2, title: '协议样本', cases: [{ title: '中文', kind: 'CHINESE_CONTINUATION', prompt: 'synthetic input', rule: 'NONEMPTY', expected: [] }], repetitions: 1, max_output_tokens: 128, timeout_seconds: 30, max_cost_microusd: 0 };
const run = { id: 'run-one', version: 1, status: 'READY', completed: 0, total: 1, results: [] };
const reply = (body: unknown, code = 200) => new Response(JSON.stringify(body), { status: code });
function transport() {
  return vi.fn(async (url: string, init?: RequestInit) => {
    if (url.endsWith('/model-broker/status')) return reply(status);
    if (url.endsWith('/model-broker/history')) return reply({ decisions: [], ledger: [] });
    if (url.endsWith('/model-broker/preview')) return reply(quote);
    if (url.endsWith('/author-context/preview')) return reply(authorPreview);
    if (url.endsWith('/model-broker/generate')) return reply({ job_id: 'job-one', reservation_id: 'ledger-one', status: 'QUEUED' }, 202);
    if (url.endsWith('/jobs/ledger-one')) return reply({ ledger: { id: 'ledger-one', version: 3, status: 'SETTLED', actual_microusd: 0 }, job: { id: 'job-one', chapter_id: 'chapter-one', status: 'COMPLETED', output: 'Actual existing job draft' }, recovery: null });
    if (url.endsWith('/model-benchmarks/status')) return reply({ sets: [testSet], runs: [run], evidence: [] });
    if (url.endsWith('/model-benchmarks/sets') && init?.method === 'POST') return reply({ ...testSet, ...JSON.parse(init.body as string) }, 201);
    if (url.endsWith('/model-benchmarks/runs')) return reply(run, 201);
    if (url.endsWith('/step')) return reply({ ...run, status: 'COMPLETED', completed: 1 });
    return reply({});
  });
}
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
const client = () => experimentalClient('novel-one', context);
function panel(extra = {}) { return <ModelBrokerPanel client={client()} novelId="novel-one" context={context} chapter={chapter} {...extra} />; }
async function selectQuote() {
  await screen.findByLabelText('调度策略');
  fireEvent.click(screen.getByLabelText('明确允许内置合成协议测试（不代表真实模型质量）'));
  fireEvent.change(screen.getByLabelText('调度策略'), { target: { value: 'CUSTOM' } });
  fireEvent.change(screen.getByLabelText('偏好模型路线'), { target: { value: route.route_id } });
  await waitFor(() => expect((screen.getByRole('button', { name: '预览合法模型路线' }) as HTMLButtonElement).disabled).toBe(false));
  fireEvent.click(screen.getByRole('button', { name: '预览合法模型路线' }));
  await screen.findByRole('region', { name: '模型路线预览' });
}

it('defaults to local and allows explicit cloud then local selection without changing privacy or dispatching', async () => {
  const cloud = { ...route, route_id: 'cloud-route', display_name: 'Cloud text fixture', provider_id: 'cloud-fixture', cloud: true, synthetic: false, verification: 'ADAPTER_CONTRACT_ONLY', reasons: ['CREDENTIAL_UNAVAILABLE'], available: false };
  const base = transport();
  const fetch = vi.fn((url: string, init?: RequestInit) => url.endsWith('/model-broker/status') ? Promise.resolve(reply({ ...status, candidates: [route, cloud] })) : base(url, init));
  vi.stubGlobal('fetch', fetch); render(panel());
  await screen.findByRole('button', { name: '明确指定云端路线 Cloud text fixture' });
  expect((screen.getByLabelText('调度策略') as HTMLSelectElement).value).toBe('LOCAL_FIRST');
  expect((screen.getByLabelText('创作隐私模式') as HTMLSelectElement).value).toBe('LOCAL_ONLY');
  expect(screen.getByText(/缺少可用凭据；请在 AI 主控中心核对/)).toBeTruthy();
  expect(screen.getByText(/连接未验证；这里只读取注册/)).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: '明确指定云端路线 Cloud text fixture' }));
  expect((screen.getByLabelText('偏好模型路线') as HTMLSelectElement).value).toBe('cloud-route');
  expect((screen.getByLabelText('调度策略') as HTMLSelectElement).value).toBe('CUSTOM');
  expect((screen.getByLabelText('创作隐私模式') as HTMLSelectElement).value).toBe('LOCAL_ONLY');
  fireEvent.click(screen.getByRole('button', { name: `明确指定本地路线 ${route.display_name}` }));
  expect((screen.getByLabelText('偏好模型路线') as HTMLSelectElement).value).toBe(route.route_id);
  expect(fetch.mock.calls.every(([, init]) => init?.method === 'GET')).toBe(true);
});

it('preserves an uncertain submission and explicitly retries the identical owner request without a new id', async () => {
  const base = transport(); let attempts = 0;
  const fetch = vi.fn((url: string, init?: RequestInit) => {
    if (url.endsWith('/model-broker/generate') && ++attempts === 1) return Promise.reject(new TypeError('connection lost'));
    return base(url, init);
  });
  vi.stubGlobal('fetch', fetch); render(panel()); await selectQuote();
  fireEvent.change(screen.getByLabelText('本次创作要求'), { target: { value: 'Preserve my draft request' } });
  fireEvent.click(screen.getByRole('button', { name: '检查真实生成请求' }));
  await screen.findByLabelText('准确生成 Prompt');
  fireEvent.click(screen.getByLabelText('已核对准确请求、来源与模型，并授权生成这一次草稿'));
  fireEvent.click(screen.getByRole('button', { name: '按预览路线预占并生成' }));
  const retry = await screen.findByRole('button', { name: '用同一请求重新确认提交' });
  expect(screen.getByText(/网络错误不代表任务未启动/)).toBeTruthy();
  expect((screen.getByLabelText('本次创作要求') as HTMLTextAreaElement).value).toBe('Preserve my draft request');
  expect(screen.getByLabelText('本次创作要求').closest('fieldset')?.disabled).toBe(false);
  fireEvent.change(screen.getByLabelText('本次创作要求'), { target: { value: 'Next draft, not the pending request' } });
  expect((screen.getByRole('button', { name: '按预览路线预占并生成' }) as HTMLButtonElement).disabled).toBe(true);
  expect(screen.getByLabelText('偏好模型路线').closest('fieldset')?.disabled).toBe(false);
  fireEvent.change(screen.getByLabelText('创作隐私模式'), { target: { value: 'HYBRID' } });
  fireEvent.change(screen.getByLabelText('偏好模型路线'), { target: { value: '' } });
  expect(screen.queryByRole('region', { name: '模型路线预览' })).toBeNull();
  fireEvent.click(retry);
  await screen.findByDisplayValue('Actual existing job draft');
  const sends = fetch.mock.calls.filter(([url]) => url.endsWith('/model-broker/generate'));
  expect(sends).toHaveLength(2);
  expect(sends[1][1]?.body).toBe(sends[0][1]?.body);
  expect(screen.queryByRole('button', { name: '用同一请求重新确认提交' })).toBeNull();
  expect(screen.getByLabelText('偏好模型路线').closest('fieldset')?.disabled).toBe(false);
  expect(screen.getByText(/原任务 ID：job-one · 账本 ID：ledger-one/)).toBeTruthy();
});

it('requires saved chapter edits before exact preview or generation', async () => {
  const fetch = transport(); vi.stubGlobal('fetch', fetch); render(panel({ saved: false })); await selectQuote();
  expect((screen.getByRole('button', { name: '检查真实生成请求' }) as HTMLButtonElement).disabled).toBe(true);
  expect((screen.getByRole('button', { name: '按预览路线预占并生成' }) as HTMLButtonElement).disabled).toBe(true);
  expect(fetch.mock.calls.some(([url]) => url.endsWith('/author-context/preview') || url.endsWith('/generate'))).toBe(false);
});

it.each([false, true])('only unlocks an explicit pre-dispatch rejection on the first attempt (prior ambiguous send: %s)', async priorUnknown => {
  const base = transport(); let attempt = 0;
  const fetch = vi.fn((url: string, init?: RequestInit) => {
    if (url.endsWith('/model-broker/generate')) {
      if (priorUnknown && ++attempt === 1) return Promise.reject(new TypeError('lost reply'));
      return Promise.resolve(reply({ detail: { code: 'AUTHOR_PREVIEW_STALE' } }, 409));
    }
    return base(url, init);
  });
  vi.stubGlobal('fetch', fetch); render(panel()); await selectQuote();
  fireEvent.change(screen.getByLabelText('本次创作要求'), { target: { value: 'Keep this instruction' } });
  fireEvent.click(screen.getByRole('button', { name: '检查真实生成请求' }));
  await screen.findByLabelText('准确生成 Prompt');
  fireEvent.click(screen.getByLabelText('已核对准确请求、来源与模型，并授权生成这一次草稿'));
  fireEvent.click(screen.getByRole('button', { name: '按预览路线预占并生成' }));
  if (priorUnknown) fireEvent.click(await screen.findByRole('button', { name: '用同一请求重新确认提交' }));
  await screen.findByText(/AUTHOR_PREVIEW_STALE/);
  if (priorUnknown) {
    expect(screen.getByRole('button', { name: '用同一请求重新确认提交' })).toBeTruthy();
    expect((screen.getByRole('button', { name: '按预览路线预占并生成' }) as HTMLButtonElement).disabled).toBe(true);
  } else {
    expect(screen.queryByRole('button', { name: '用同一请求重新确认提交' })).toBeNull();
    expect(screen.queryByRole('region', { name: '模型路线预览' })).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: '预览合法模型路线' }));
    await screen.findByRole('region', { name: '模型路线预览' });
    expect((screen.getByLabelText('本次创作要求') as HTMLTextAreaElement).value).toBe('Keep this instruction');
  }
});
