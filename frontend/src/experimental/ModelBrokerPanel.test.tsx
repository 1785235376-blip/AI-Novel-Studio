// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { ModelBrokerPanel } from './ModelBrokerPanel';
import { ModelBenchmarkPanel } from './ModelBenchmarkPanel';
import { experimentalClient } from './api';
import { modelBrokerClient } from './modelBrokerClient';
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

it('captures actual scoped route preview and requires exact author receipt plus review before existing job dispatch', async () => {
  const fetch = transport(); vi.stubGlobal('fetch', fetch); render(panel()); await selectQuote();
  const previewCall = fetch.mock.calls.find(([url]) => url.endsWith('/model-broker/preview'))!;
  expect(JSON.parse(previewCall[1]!.body as string)).toMatchObject({ chapter_ids: ['chapter-one'], policy: 'CUSTOM', profile: 'LOCAL_ONLY', preferred_route: route.route_id, max_cost_microusd: null, allow_synthetic: true });
  expect(previewCall[1]!.headers).toMatchObject({ 'X-Session-Token': 'session-one', 'X-Branch-Id': 'b' });
  expect((screen.getByRole('button', { name: '按预览路线预占并生成' }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.change(screen.getByLabelText('本次创作要求'), { target: { value: 'Keep the gate closed' } });
  fireEvent.click(screen.getByRole('button', { name: '检查真实生成请求' }));
  await screen.findByLabelText('准确生成 Prompt');
  fireEvent.click(screen.getByLabelText('已核对准确请求、来源与模型，并授权生成这一次草稿'));
  fireEvent.click(screen.getByRole('button', { name: '按预览路线预占并生成' }));
  await screen.findByDisplayValue('Actual existing job draft');
  const sent = JSON.parse(fetch.mock.calls.find(([url]) => url.endsWith('/model-broker/generate'))![1]!.body as string);
  expect(sent).toMatchObject({ preview_id: 'quote-one', expected_version: 1, author: { novel_id: 'novel-one', chapter_id: 'chapter-one', chapter_version: 3, provider_id: 'mock', model_id: 'mock-writer', instruction: 'Keep the gate closed', preview_digest: 'c'.repeat(64) } });
  expect(sent.request_id).toBeTruthy();
});

it('clears the actual preview after policy changes and cannot dispatch stale selection', async () => {
  vi.stubGlobal('fetch', transport()); render(panel()); await selectQuote();
  fireEvent.change(screen.getByLabelText('创作隐私模式'), { target: { value: 'HYBRID' } });
  expect(screen.queryByRole('region', { name: '模型路线预览' })).toBeNull();
  expect(screen.queryByRole('button', { name: '按预览路线预占并生成' })).toBeNull();
});

it('does not restore a late private result after scope navigation', async () => {
  const base = transport(); let finish: (value: Response) => void = () => {};
  vi.stubGlobal('fetch', vi.fn((url: string, init?: RequestInit) => url.endsWith('/model-broker/preview') ? new Promise(resolve => { finish = resolve; }) : base(url, init)));
  const view = render(panel());
  await waitFor(() => expect((screen.getByRole('button', { name: '预览合法模型路线' }) as HTMLButtonElement).disabled).toBe(false));
  fireEvent.click(screen.getByRole('button', { name: '预览合法模型路线' }));
  view.rerender(<ModelBrokerPanel client={experimentalClient('novel-two', { sessionToken: 'other' })} novelId="novel-two" context={{ sessionToken: 'other' }} chapter={chapter} />);
  finish(reply(quote));
  await waitFor(() => expect(screen.queryByRole('region', { name: '模型路线预览' })).toBeNull());
});

it('keeps budget edits visible after CAS conflict and transmits the read revision', async () => {
  const base = transport(); const fetch = vi.fn((url: string, init?: RequestInit) => url.endsWith('/budget') ? Promise.resolve(reply({ detail: { code: 'EXPERIMENTAL_VERSION_CONFLICT' } }, 409)) : base(url, init));
  vi.stubGlobal('fetch', fetch); render(panel());
  const input = await screen.findByLabelText('累计预占上限（µUSD；留空不设金额上限）');
  fireEvent.change(input, { target: { value: '73' } });
  fireEvent.click(screen.getByRole('button', { name: '保存版本化项目预算' }));
  await screen.findByRole('alert');
  expect((input as HTMLInputElement).value).toBe('73');
  const sent = JSON.parse(fetch.mock.calls.find(([url]) => url.endsWith('/budget'))![1]!.body as string);
  expect(sent.expected_version).toBe(5); expect(sent.limit_microusd).toBe(73);
});

it('manages actual bounded test sets and never starts inference during page load', async () => {
  const fetch = transport(); vi.stubGlobal('fetch', fetch); render(<ModelBenchmarkPanel api={modelBrokerClient(client())} routes={[route]} />);
  await screen.findByRole('button', { name: '编辑任务集 协议样本' });
  expect(fetch.mock.calls.every(([, init]) => init?.method === 'GET')).toBe(true);
  fireEvent.change(screen.getByLabelText('评测任务集标题'), { target: { value: 'Chinese continuation' } });
  fireEvent.change(screen.getByLabelText('样本 1 合成测试输入'), { target: { value: 'A synthetic Chinese prompt' } });
  fireEvent.click(screen.getByRole('button', { name: '保存评测任务集' }));
  await waitFor(() => expect(fetch.mock.calls.some(([url, init]) => url.endsWith('/sets') && init?.method === 'POST')).toBe(true));
  const sent = JSON.parse(fetch.mock.calls.find(([url, init]) => url.endsWith('/sets') && init?.method === 'POST')![1]!.body as string);
  expect(sent).toMatchObject({ title: 'Chinese continuation', repetitions: 1, max_cost_microusd: 0, cases: [{ prompt: 'A synthetic Chinese prompt', rule: 'NONEMPTY' }] });
  fireEvent.click(screen.getByRole('button', { name: '执行下一评测样本' }));
  await waitFor(() => expect(fetch.mock.calls.filter(([url]) => url.endsWith('/step'))).toHaveLength(1));
  expect(JSON.parse(fetch.mock.calls.find(([url]) => url.endsWith('/step'))![1]!.body as string)).toEqual({ expected_version: 1 });
});

it('reading an imported result file does not send it until explicitly reviewed', async () => {
  const fetch = transport(); vi.stubGlobal('fetch', fetch); render(<ModelBenchmarkPanel api={modelBrokerClient(client())} routes={[]} />);
  const file = { size: 50, text: vi.fn().mockResolvedValue('{"provenance":"offline fixture"}') };
  fireEvent.change(screen.getByLabelText('读取评测结果 JSON 文件'), { target: { files: [file] } });
  await screen.findByDisplayValue('{"provenance":"offline fixture"}');
  expect(fetch.mock.calls.every(([, init]) => init?.method === 'GET')).toBe(true);
  fireEvent.click(screen.getByRole('button', { name: '核对并导入评测证据' }));
  await waitFor(() => expect(fetch.mock.calls.some(([url]) => url.endsWith('/evidence/import'))).toBe(true));
});


it('opens existing draft through the App authority callback and fences a late navigation response', async () => {
  const base = transport();
  vi.stubGlobal('fetch', vi.fn((url: string, init?: RequestInit) => url.endsWith('/model-broker/history') ? Promise.resolve(reply({ decisions: [], ledger: [{ id: 'ledger-one', version: 3, status: 'SETTLED', job_id: 'job-one', provider_id: 'mock', model_id: 'mock-writer', actual_microusd: 0 }] })) : base(url, init)));
  let finish: () => void = () => {};
  const open = vi.fn(() => new Promise<void>(resolve => { finish = resolve; }));
  const view = render(panel({ onOpenGeneration: open }));
  fireEvent.click(await screen.findByRole('button', { name: '查看原任务 job-one' }));
  const button = await screen.findByRole('button', { name: '在原有草稿审核中打开' });
  fireEvent.click(button);
  await waitFor(() => expect(open).toHaveBeenCalledWith('job-one', 'chapter-one'));
  expect(open).toHaveBeenCalledTimes(1);
  view.rerender(<ModelBrokerPanel client={experimentalClient('novel-two', { sessionToken: 'other' })} novelId="novel-two" context={{ sessionToken: 'other' }} chapter={chapter} onOpenGeneration={open} />);
  finish();
  await waitFor(() => expect(screen.queryByText('已核对当前权限并打开原有草稿审核；尚未采用。')).toBeNull());
  expect(screen.queryByDisplayValue('Actual existing job draft')).toBeNull();
});
