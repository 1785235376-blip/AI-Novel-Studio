// @vitest-environment jsdom
import { StrictMode } from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { SafeBatchesPanel } from './SafeBatchesPanel';
import { experimentalClient } from './api';
const reply = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });
const catalog = { chapters: [{ id: 'c1', title: '合成章节', version: 3 }], briefs: [], formats: ['txt', 'docx'], unsupported: [], concurrency: 1, known_cost_microusd: 0 };
const row = { id: 'batch', version: 1, status: 'PREFLIGHT', snapshot_digest: 'f'.repeat(64), confirmed: false, budget: { state: 'DISABLED', known_cost_microusd: 0 }, items: [{ index: 0, kind: 'PROOF', status: 'PENDING', attempts: 0, chapter_ids: ['c1'], permission: 'domain.write', known_cost_microusd: 0 }] };
const client = (nid = 'n1') => experimentalClient(nid, { sessionToken: 'trusted' });
function requests(items: any[] = [row], mutation?: (url: string, init: RequestInit) => Response | Promise<Response>) {
  return vi.fn(async (url: string, init: RequestInit) => {
    if (init.method !== 'GET') return mutation ? mutation(url, init) : reply(row);
    return reply(url.endsWith('/catalog') ? catalog : { items });
  });
}
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });
it('mount and preflight never execute and request exact chosen chapter with hard zero budget', async () => {
  const fetch = requests([]); vi.stubGlobal('fetch', fetch); render(<StrictMode><SafeBatchesPanel client={client()} /></StrictMode>);
  await screen.findByLabelText('合成章节 · v3'); expect(fetch.mock.calls.every(([, init]) => init.method === 'GET')).toBe(true);
  fireEvent.click(screen.getByLabelText('合成章节 · v3')); fireEvent.click(screen.getByRole('button', { name: '仅预检所选批次' }));
  await waitFor(() => expect(fetch.mock.calls.some(([url]) => url.endsWith('/preflight'))).toBe(true));
  expect(JSON.parse(String(fetch.mock.calls.find(([url]) => url.endsWith('/preflight'))![1].body))).toEqual({ items: [{ kind: 'PROOF', chapter_ids: ['c1'] }], concurrency: 1, budget_microusd: 0, skip_satisfied: true });
  expect(fetch.mock.calls.some(([url]) => /dispatch|confirm/.test(url))).toBe(false);
});
it('confirmation binds snapshot but does not dispatch, double click cannot duplicate', async () => {
  let resolve!: (v: Response) => void; const fetch = requests([row], () => new Promise<Response>(done => { resolve = done; })); vi.stubGlobal('fetch', fetch);
  render(<SafeBatchesPanel client={client()} />); const button = await screen.findByRole('button', { name: '确认此批次快照与预算' }) as HTMLButtonElement;
  expect(button.disabled).toBe(true); fireEvent.click(screen.getByLabelText('已核对本批次来源版本、权限、资源与 0 USD 预算')); fireEvent.click(button); fireEvent.click(button);
  await waitFor(() => expect(fetch.mock.calls.filter(([url]) => url.endsWith('/confirm')).length).toBe(1));
  const call = fetch.mock.calls.find(([url]) => url.endsWith('/confirm'))!;
  expect(JSON.parse(String(call[1].body))).toEqual({ expected_version: 1, snapshot_digest: row.snapshot_digest, confirmed: true, budget_microusd: 0 });
  resolve(reply({ ...row, status: 'READY', version: 2 })); await waitFor(() => expect(fetch.mock.calls.some(([url]) => url.endsWith('/dispatch-next'))).toBe(false));
});
it('one stage only, errors retain checked inputs and do not run next stage', async () => {
  const ready = { ...row, status: 'READY', confirmed: true }; const fetch = requests([ready], () => reply({ detail: { code: 'FORBIDDEN' } }, 403)); vi.stubGlobal('fetch', fetch);
  render(<SafeBatchesPanel client={client()} />); await screen.findByRole('button', { name: '执行下一阶段' });
  fireEvent.click(screen.getByLabelText('合成章节 · v3')); fireEvent.click(screen.getByRole('button', { name: '执行下一阶段' }));
  await screen.findByText(/FORBIDDEN/); expect((screen.getByLabelText('合成章节 · v3') as HTMLInputElement).checked).toBe(true);
  expect(fetch.mock.calls.filter(([url]) => url.endsWith('/dispatch-next')).length).toBe(1);
});
it('only failed retry is offered; unknown outcomes expose no replay button', async () => {
  const failed = { ...row, status: 'PARTIAL', items: [{ ...row.items[0], status: 'FAILED' }] }; let fetch = requests([failed]); vi.stubGlobal('fetch', fetch);
  const view = render(<SafeBatchesPanel client={client()} />); fireEvent.click(await screen.findByRole('button', { name: '仅预检失败项重试' }));
  await waitFor(() => expect(fetch.mock.calls.some(([url]) => url.endsWith('/retry-failed'))).toBe(true));
  view.unmount(); fetch = requests([{ ...row, status: 'UNKNOWN', items: [{ ...row.items[0], status: 'UNKNOWN' }] }]); vi.stubGlobal('fetch', fetch);
  render(<SafeBatchesPanel client={client()} />); await screen.findByText(/原执行结果未知/);
  expect(screen.queryByRole('button', { name: '仅预检失败项重试' })).toBeNull(); expect(screen.queryByRole('button', { name: '执行下一阶段' })).toBeNull();
});
it('stop fetches current version and scope switch removes previous batch content', async () => {
  const running = { ...row, status: 'RUNNING', version: 4 }; const fetch = requests([running]); vi.stubGlobal('fetch', fetch);
  const view = render(<SafeBatchesPanel client={client()} />); fireEvent.click(await screen.findByRole('button', { name: '停止此批次后续阶段' }));
  await waitFor(() => expect(fetch.mock.calls.some(([url]) => url.endsWith('/stop'))).toBe(true));
  expect(JSON.parse(String(fetch.mock.calls.find(([url]) => url.endsWith('/stop'))![1].body))).toEqual({ expected_version: 4 });
  vi.stubGlobal('fetch', vi.fn(() => new Promise<Response>(() => {}))); view.rerender(<SafeBatchesPanel client={client('other')} />);
  expect(screen.queryByText('批次 batch')).toBeNull(); expect(screen.queryByLabelText('合成章节 · v3')).toBeNull();
});
it('binds the original B01 preset version and keeps preset parameters read-only', async () => {
  const withPreset = { ...catalog, presets: [{ id: 'preset-1', version: 4, title: '合成导出参数', content: { proof: true, export_format: 'docx', skip_satisfied: true } }] };
  const fetch = vi.fn(async (url: string, init: RequestInit) => reply(init.method === 'GET' ? url.endsWith('/catalog') ? withPreset : { items: [] } : row)); vi.stubGlobal('fetch', fetch);
  render(<SafeBatchesPanel client={client()} />); await screen.findByLabelText('合成章节 · v3');
  fireEvent.change(screen.getByLabelText('本项目批处理参数模板'), { target: { value: 'preset-1' } }); fireEvent.click(screen.getByLabelText('合成章节 · v3'));
  expect((screen.getByLabelText('批次导出格式') as HTMLSelectElement).disabled).toBe(true);
  fireEvent.click(screen.getByRole('button', { name: '仅预检所选批次' }));
  await waitFor(() => expect(fetch.mock.calls.some(([url]) => url.endsWith('/preflight'))).toBe(true));
  const body = JSON.parse(String(fetch.mock.calls.find(([url]) => url.endsWith('/preflight'))![1].body));
  expect(body.preset_id).toBe('preset-1'); expect(body.expected_preset_version).toBe(4);
  expect(body.items).toEqual([{ kind: 'PROOF', chapter_ids: ['c1'] }, { kind: 'EXPORT', chapter_ids: ['c1'], format: 'docx' }]);
});
it('selects exact registered media admission and never sends at preflight', async () => {
  const withMedia = { ...catalog, briefs: [{ id: 'brief', title: '合成分镜来源', version: 2, kind: 'COVER' }], broker_previews: [{ id: 'original-broker', version: 3, adapter_id: 'registered-fixture', capability: 'IMAGE', source_ids: ['c1'], cost_state: 'ZERO_ESTIMATE_NOT_INVOICE' }] };
  const fetch = vi.fn(async (url: string, init: RequestInit) => reply(init.method === 'GET' ? url.endsWith('/catalog') ? withMedia : { items: [] } : row)); vi.stubGlobal('fetch', fetch);
  render(<SafeBatchesPanel client={client()} />); await screen.findByLabelText('媒体来源简报');
  fireEvent.change(screen.getByLabelText('媒体来源简报'), { target: { value: 'brief' } });
  fireEvent.change(screen.getByLabelText('原 Broker 媒体准入预检'), { target: { value: 'original-broker' } });
  fireEvent.click(screen.getByRole('button', { name: '仅预检所选批次' }));
  await waitFor(() => expect(fetch.mock.calls.some(([url]) => url.endsWith('/preflight'))).toBe(true));
  const body = JSON.parse(String(fetch.mock.calls.find(([url]) => url.endsWith('/preflight'))![1].body));
  expect(body.items).toEqual([{ kind: 'REGISTERED_MEDIA', brief_id: 'brief', expected_brief_version: 2, adapter_id: 'registered-fixture', broker_preview_id: 'original-broker', expected_broker_version: 3 }]);
  expect(fetch.mock.calls.some(([url]) => /dispatch|confirm/.test(url))).toBe(false);
});
it('keeps unknown attempt receipts and only queries the original terminal state', async () => {
  const unknown = { ...row, status: 'UNKNOWN', items: [{ ...row.items[0], status: 'UNKNOWN', receipts: [{ attempt: 1, status: 'UNKNOWN', task_id: 'original-task', reservation_id: 'original-cost-hold', cost_state: 'UNKNOWN_UPSTREAM' }] }] };
  const fetch = requests([unknown]); vi.stubGlobal('fetch', fetch); render(<SafeBatchesPanel client={client()} />);
  fireEvent.click(await screen.findByText('查看历次尝试、原任务与成本回执')); await screen.findByText(/original-cost-hold/);
  fireEvent.click(screen.getByRole('button', { name: '仅查询原任务终态回执' }));
  await waitFor(() => expect(fetch.mock.calls.some(([url]) => url.endsWith('/reconcile'))).toBe(true));
  expect(fetch.mock.calls.some(([url]) => /dispatch-next|retry-failed|approve-media/.test(url))).toBe(false);
});
it('selects only a matching original approved voice task and its AUDIO broker receipt', async () => {
  const withVoice = { ...catalog, voice_jobs: [{ id: 'audio-original', chapter_id: 'c1', segment_id: '段落一', provider_id: 'local-fixture', model_id: 'tts', request_digest: 'a'.repeat(64), status: 'QUEUED', approval_status: 'PENDING' }], broker_previews: [{ id: 'audio-broker', version: 2, audio_provider_id: 'local-fixture', model_id: 'tts', capability: 'AUDIO', source_ids: ['c1'], cost_state: 'ZERO_ESTIMATE_NOT_INVOICE' }] };
  const fetch = vi.fn(async (url: string, init: RequestInit) => reply(init.method === 'GET' ? url.endsWith('/catalog') ? withVoice : { items: [] } : row)); vi.stubGlobal('fetch', fetch);
  render(<SafeBatchesPanel client={client()} />); await screen.findByLabelText('原 Broker 语音准入预检');
  fireEvent.change(screen.getByLabelText('原 Broker 语音准入预检'), { target: { value: 'audio-broker' } });
  fireEvent.click(await screen.findByLabelText('段落一 · QUEUED · PENDING')); fireEvent.click(screen.getByRole('button', { name: '仅预检所选批次' }));
  await waitFor(() => expect(fetch.mock.calls.some(([url]) => url.endsWith('/preflight'))).toBe(true));
  const body = JSON.parse(String(fetch.mock.calls.find(([url]) => url.endsWith('/preflight'))![1].body));
  expect(body.items).toEqual([{ kind: 'VOICE_REDO', voice_job_id: 'audio-original', expected_voice_digest: 'a'.repeat(64), broker_preview_id: 'audio-broker', expected_broker_version: 2 }]);
});
it('voice result needs a real preview and separate review before original asset acceptance', async () => {
  const voice = { job_id: 'job', asset_id: 'asset', asset_version: 2, approval_status: 'PENDING', duration_ms: 400, media_type: 'audio/wav', verification: 'ORIGINAL_AUDIO_DECODER_NOT_VOICE_QUALITY' };
  const completed = { ...row, status: 'COMPLETED', confirmed: true, version: 4, items: [{ ...row.items[0], kind: 'VOICE_REDO', status: 'COMPLETED', voice_result: voice }] };
  const create = vi.fn(() => 'blob:synthetic-voice-preview'); const BrowserURL = URL; vi.stubGlobal('URL', class extends BrowserURL { static createObjectURL = create; static revokeObjectURL = vi.fn(); });
  const fetch = vi.fn(async (url: string, init: RequestInit) => url.endsWith('/audio') ? new Response(new Uint8Array([82, 73, 70, 70]), { headers: { 'Content-Type': 'audio/wav' } }) : reply(init.method === 'GET' ? url.endsWith('/catalog') ? catalog : { items: [completed] } : completed));
  vi.stubGlobal('fetch', fetch); render(<SafeBatchesPanel client={client()} />);
  const accept = await screen.findByRole('button', { name: '确认接受此语音段' }) as HTMLButtonElement;
  expect(accept.disabled).toBe(true); fireEvent.click(screen.getByLabelText('已试听并确认此语音段')); expect(accept.disabled).toBe(true);
  fireEvent.click(screen.getByRole('button', { name: '试听阶段 1 语音' })); await screen.findByLabelText('阶段 1 语音试听');
  fireEvent.click(accept); await waitFor(() => expect(fetch.mock.calls.some(([url]) => url.endsWith('/approve-voice'))).toBe(true));
  expect(JSON.parse(String(fetch.mock.calls.find(([url]) => url.endsWith('/approve-voice'))![1].body))).toEqual({ expected_version: 4, snapshot_digest: row.snapshot_digest, confirmed: true, budget_microusd: 0, item_index: 0, expected_asset_version: 2 });
  expect(fetch.mock.calls.some(([url]) => url.endsWith('/dispatch-next'))).toBe(false);
});
