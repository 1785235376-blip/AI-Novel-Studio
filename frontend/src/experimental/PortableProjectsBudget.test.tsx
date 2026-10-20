// @vitest-environment jsdom
import { StrictMode } from 'react';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { PortableProjectsPanel } from './PortableProjectsPanel';
import { experimentalClient } from './api';

const reply = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });
const client = (nid = 'fixture') => experimentalClient(nid, { sessionToken: 'host', scope: { branchId: 'branch' } as any });
const consentLabel = '已核对当前预览，只清理列出的可重建缓存';
const inputLabel = '导出缓存预算上限（字节，留空为未配置）';
const cleanupButton = () => screen.getByRole('button', { name: '确认清理预览中的缓存' }) as HTMLButtonElement;
const saveButton = () => screen.getByRole('button', { name: '保存导出缓存预算' }) as HTMLButtonElement;
function preview(version = 1, digest = 'a'.repeat(64)) {
  return {
    categories: [{ kind: 'REPRODUCIBLE_CACHE', bytes: 100, cleanable: true, measurement: 'VERIFIED_PORTABLE_EXPORT_CACHE_ONLY' }],
    eligible: [{ id: 'old', version: 1, bytes: 40, sha256: 'b'.repeat(64) }, { id: 'new', version: 1, bytes: 60, sha256: 'c'.repeat(64) }],
    preview_digest: digest,
    cache_budget: {
      policy: { version, limit_bytes: 60 as number | null },
      scope: 'CURRENT_AUTHOR_SCOPE_REPRODUCIBLE_PORTABLE_EXPORTS_ONLY', advisory_only: true, automatic_cleanup: false,
      state: 'OVER_BUDGET', excess_bytes: 40 as number | null,
      measurement: { state: 'MEASURED', bytes: 100 as number | null, verified_reproducible_bytes: 100, unmeasured_records: 0 },
      plan: { record_ids: ['old'], reclaim_bytes: 40, remaining_excess_bytes: 0 as number | null, complete: true },
    },
  };
}
function fixture(mutation: (url: string, init: RequestInit) => Response | Promise<Response> = () => reply({})) {
  let current = preview();
  const fetch = vi.fn(async (url: string, init: RequestInit) => {
    if (init.method !== 'GET') return mutation(url, init);
    if (url.endsWith('/storage')) return reply(current);
    if (url.endsWith('/catalog')) return reply({ chapters: [], missing: [], restore_available: true, limitations: [] });
    return reply({ items: [] });
  });
  vi.stubGlobal('fetch', fetch);
  return { fetch, setPreview: (value: ReturnType<typeof preview>) => { current = value; }, writes: () => fetch.mock.calls.filter(([, init]) => init.method !== 'GET') };
}
function retainedClick(element: HTMLElement) {
  const key = Object.keys(element).find(key => key.startsWith('__reactProps$'))!;
  return (element as any)[key].onClick as () => void;
}
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

it('renders measured advisory budget without writes and adopts only the explicit original-owner plan', async () => {
  const f = fixture(); render(<StrictMode><PortableProjectsPanel client={client()} /></StrictMode>);
  await screen.findByLabelText(inputLabel);
  expect(screen.getByText(/占用：100 字节 · 超额：40 字节/)).toBeTruthy();
  expect(f.writes()).toHaveLength(0);
  fireEvent.click(screen.getByRole('button', { name: '采用预算回收计划（尚不清理）' }));
  expect(f.writes()).toHaveLength(0); expect(cleanupButton().disabled).toBe(true);
  fireEvent.click(screen.getByLabelText(consentLabel)); fireEvent.click(cleanupButton());
  await waitFor(() => expect(f.writes()).toHaveLength(1));
  const [url, init] = f.writes()[0]; expect(url).toMatch(/\/portable-projects\/cleanup$/);
  expect(JSON.parse(String(init.body))).toEqual({ record_ids: ['old'], preview_digest: 'a'.repeat(64), confirmed: true });
  expect(init.headers).toMatchObject({ 'X-Session-Token': 'host', 'X-Branch-Id': 'branch' });
});

it('editing retires cleanup consent, saves exact CAS policy, and never automatically cleans', async () => {
  const f = fixture(() => { f.setPreview({ ...preview(2, 'd'.repeat(64)), cache_budget: { ...preview(2).cache_budget, policy: { version: 2, limit_bytes: 0 }, excess_bytes: 100, plan: { record_ids: ['old', 'new'], reclaim_bytes: 100, remaining_excess_bytes: 0, complete: true } } }); return reply({ version: 2, limit_bytes: 0 }); });
  render(<PortableProjectsPanel client={client()} />); await screen.findByLabelText(inputLabel);
  fireEvent.click(screen.getByLabelText(consentLabel)); expect(cleanupButton().disabled).toBe(false);
  fireEvent.change(screen.getByLabelText(inputLabel), { target: { value: '0' } });
  expect(cleanupButton().disabled).toBe(true); expect((screen.getByLabelText(consentLabel) as HTMLInputElement).checked).toBe(false);
  fireEvent.click(saveButton()); await screen.findByText(/策略 v2 · 上限：0 字节/);
  expect(f.writes()).toHaveLength(1); const [url, init] = f.writes()[0];
  expect(url).toMatch(/\/cache-policy$/); expect(init.method).toBe('PUT');
  expect(JSON.parse(String(init.body))).toEqual({ expected_version: 1, limit_bytes: 0 });
  expect(cleanupButton().disabled).toBe(true);
});

it('CAS conflict retains local draft and refreshing a changed policy requires explicit discard', async () => {
  const f = fixture(() => reply({ detail: { code: 'VERSION_CONFLICT' } }, 409));
  render(<PortableProjectsPanel client={client()} />); await screen.findByLabelText(inputLabel);
  fireEvent.change(screen.getByLabelText(inputLabel), { target: { value: '120' } }); fireEvent.click(saveButton());
  await screen.findByText(/VERSION_CONFLICT/); expect((screen.getByLabelText(inputLabel) as HTMLInputElement).value).toBe('120');
  f.setPreview(preview(2, 'd'.repeat(64))); fireEvent.click(screen.getByRole('button', { name: '刷新便携与存储状态' }));
  await screen.findByText(/预算策略已改变，本地输入已保留/);
  expect(saveButton().disabled).toBe(true); expect((screen.getByLabelText(inputLabel) as HTMLInputElement).value).toBe('120');
  fireEvent.click(screen.getByRole('button', { name: '放弃预算输入并载入当前策略' }));
  expect((screen.getByLabelText(inputLabel) as HTMLInputElement).value).toBe('60'); expect(saveButton().disabled).toBe(true);
  expect(f.writes()).toHaveLength(1);
});

it('a source/digest refresh retires old consent and retained callbacks cannot reuse a prior consent object', async () => {
  const f = fixture(); render(<PortableProjectsPanel client={client()} />); await screen.findByLabelText(inputLabel);
  fireEvent.click(screen.getByLabelText(consentLabel)); const oldClick = retainedClick(cleanupButton());
  fireEvent.click(screen.getByLabelText(consentLabel)); fireEvent.click(screen.getByLabelText(consentLabel));
  act(oldClick); expect(f.writes()).toHaveLength(0);
  f.setPreview(preview(1, 'e'.repeat(64))); fireEvent.click(screen.getByRole('button', { name: '刷新便携与存储状态' }));
  await waitFor(() => expect(screen.getByLabelText(consentLabel)).toBeTruthy());
  expect((screen.getByLabelText(consentLabel) as HTMLInputElement).checked).toBe(false);
  act(oldClick); expect(f.writes()).toHaveLength(0); expect(cleanupButton().disabled).toBe(true);
});

it('unknown occupancy is shown as unknown, keeps the verified subset and produces no budget plan', async () => {
  const f = fixture(), value = preview();
  value.cache_budget.state = 'UNKNOWN'; value.cache_budget.excess_bytes = null;
  value.cache_budget.measurement = { state: 'UNKNOWN', bytes: null, verified_reproducible_bytes: 100, unmeasured_records: 1 };
  value.cache_budget.plan = { record_ids: [], reclaim_bytes: 0, remaining_excess_bytes: null, complete: false }; f.setPreview(value);
  render(<PortableProjectsPanel client={client()} />); await screen.findByText(/不能将未知占用视为零/);
  expect(screen.getByText(/占用：未知 · 超额：未确定/)).toBeTruthy(); expect(screen.getByText(/已核实部分为 100 字节/)).toBeTruthy();
  expect((screen.getByRole('button', { name: '采用预算回收计划（尚不清理）' }) as HTMLButtonElement).disabled).toBe(true);
  expect(f.writes()).toHaveLength(0);
});

it('unverifiable budget plan disables cleanup without any mutation', async () => {
  const f = fixture(), value = preview(); value.cache_budget.plan.record_ids = ['outside-owner']; f.setPreview(value);
  render(<PortableProjectsPanel client={client()} />); await screen.findByText(/预算或回收计划无法核实/);
  expect((screen.getByLabelText(consentLabel) as HTMLInputElement).disabled).toBe(true); expect(cleanupButton().disabled).toBe(true);
  expect(f.writes()).toHaveLength(0);
});

it('blank saves unconfigured policy and unsafe integer input issues no request', async () => {
  const f = fixture(() => reply({ version: 2, limit_bytes: null })); render(<PortableProjectsPanel client={client()} />);
  await screen.findByLabelText(inputLabel); fireEvent.change(screen.getByLabelText(inputLabel), { target: { value: '9007199254740992' } }); fireEvent.click(saveButton());
  await screen.findByText(/INVALID_CACHE_BUDGET/); expect(f.writes()).toHaveLength(0);
  fireEvent.change(screen.getByLabelText(inputLabel), { target: { value: '' } }); fireEvent.click(saveButton());
  await waitFor(() => expect(f.writes()).toHaveLength(1)); expect(JSON.parse(String(f.writes()[0][1].body))).toEqual({ expected_version: 1, limit_bytes: null });
});

it('switching scope removes draft and late policy completion cannot update the next scope', async () => {
  let finish!: (response: Response) => void; const f = fixture(() => new Promise<Response>(resolve => { finish = resolve; }));
  const view = render(<PortableProjectsPanel client={client()} />); await screen.findByLabelText(inputLabel);
  fireEvent.change(screen.getByLabelText(inputLabel), { target: { value: '0' } }); fireEvent.click(saveButton());
  await waitFor(() => expect(f.writes()).toHaveLength(1)); view.rerender(<PortableProjectsPanel client={client('next')} />);
  await screen.findByLabelText(inputLabel); await act(async () => { finish(reply({ version: 2, limit_bytes: 0 })); await Promise.resolve(); });
  expect((screen.getByLabelText(inputLabel) as HTMLInputElement).value).toBe('60'); expect(screen.queryByText(/预算已保存/)).toBeNull();
  expect(f.writes()).toHaveLength(1); expect(f.writes()[0][0]).toContain('/fixture/');
});
