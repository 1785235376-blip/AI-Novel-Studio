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
