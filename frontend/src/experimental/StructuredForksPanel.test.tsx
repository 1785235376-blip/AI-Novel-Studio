// @vitest-environment jsdom
import { StrictMode } from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { StructuredForksPanel } from './StructuredForksPanel';
import { ProjectForksPanel } from './ProjectForksPanel';
import { experimentalClient } from './api';
const client = () => experimentalClient('p', { sessionToken: 'synthetic-host' });
const reply = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status });
const source = { key: 'characters:hero', kind: 'characters', record_id: 'hero', title: '合成人物', source_digest: 'a'.repeat(64), references: [], supported: true };
const fork = { id: 'f', version: 5, title: '结构副本', target_id: 'target', status: 'FORKED', record_count: 1, id_map: { 'characters:hero': 'characters:copy' }, provenance: { 'characters:hero': { license: 'Mine' } } };
const preview = { preview_digest: 'b'.repeat(64), can_apply: false, write_count: 0, unresolved: 1, blocked: [], records: [{ key: 'characters:hero', title: '合成人物', kind: 'characters', original_digest: 'c', fork_digest: 'd', changes: [{ id: 'name-conflict', field: 'name', kind: 'CONFLICT', reason: 'RENAME', base: '基线名称', ORIGINAL: '原稿名称', FORK: '副本名称' }] }] };
function requests(mutation?: (url: string, init: RequestInit) => Response | Promise<Response>, items = [fork]) {
  return vi.fn(async (url: string, init: RequestInit) => init.method === 'GET' ? reply(url.endsWith('/catalog') ? { available: true, records: [source] } : { items, merges: [] }) : mutation ? mutation(url, init) : reply(fork));
}
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

it('keeps structured sources behind the existing panel disclosure, with no eager extra data fetch', async () => {
  const fetch = vi.fn(async (url: string) => reply(url.endsWith('/catalog') ? { available: true, chapters: [], assets: [], limitations: [], records: [source] } : { items: [], merges: [] }));
  vi.stubGlobal('fetch', fetch); render(<ProjectForksPanel client={client()} />);
  await screen.findByRole('button', { name: '打开人物与关系分叉' });
  expect(fetch.mock.calls.some(([url]) => url.includes('/structured/'))).toBe(false);
  fireEvent.click(screen.getByRole('button', { name: '打开人物与关系分叉' })); await screen.findByLabelText('人物：合成人物');
  expect(fetch.mock.calls.some(([url]) => url.endsWith('/structured/catalog'))).toBe(true);
});

it('StrictMode is read-only; explicit selected license preflight binds exact source digest', async () => {
  const fetch = requests(undefined, []); vi.stubGlobal('fetch', fetch); render(<StrictMode><StructuredForksPanel client={client()} /></StrictMode>);
  fireEvent.click(await screen.findByLabelText('人物：合成人物')); fireEvent.change(screen.getByLabelText('结构分叉项目名称'), { target: { value: '新结构副本' } });
  fireEvent.change(screen.getByLabelText('所选结构记录的许可说明'), { target: { value: '作者原创合成资料' } });
  const button = screen.getByRole('button', { name: '仅预检结构分叉' }) as HTMLButtonElement; expect(button.disabled).toBe(true);
  fireEvent.click(screen.getByLabelText('我有权将所选结构记录复制到此本地新项目')); expect(button.disabled).toBe(false);
  expect(fetch.mock.calls.every(([, init]) => init.method === 'GET')).toBe(true); fireEvent.click(button); fireEvent.click(button);
  await waitFor(() => expect(fetch.mock.calls.filter(([url]) => url.endsWith('/preflight'))).toHaveLength(1));
  const body = JSON.parse(String(fetch.mock.calls.find(([url]) => url.endsWith('/preflight'))![1].body));
  expect(body.records).toEqual([{ kind: 'characters', record_id: 'hero', source_digest: source.source_digest, license: '作者原创合成资料', allow_local_copy: true }]);
  expect(fetch.mock.calls.some(([url]) => url.endsWith('/create'))).toBe(false);
});

it('requires every referenced record explicitly; selection changes invalidate permission', async () => {
  const fetch = requests(undefined, []); fetch.mockImplementation(async () => reply({ available: true, records: [{ ...source, references: [{ field: 'current_location', key: 'locations:harbor' }] }], items: [], merges: [] }));
  vi.stubGlobal('fetch', fetch); render(<StructuredForksPanel client={client()} />); fireEvent.click(await screen.findByLabelText('人物：合成人物'));
  expect(screen.getByText(/尚缺引用目标/)).toBeTruthy(); expect((screen.getByRole('button', { name: '仅预检结构分叉' }) as HTMLButtonElement).disabled).toBe(true);
  expect(fetch.mock.calls.every(([, init]) => init.method === 'GET')).toBe(true);
});

it('shows all three rename values and requires fresh reviewed preview before original CAS apply', async () => {
  const fetch = requests((url, init) => url.endsWith('/compare') ? reply(JSON.parse(String(init.body)).choices['name-conflict'] ? { ...preview, can_apply: true, write_count: 1, unresolved: 0, preview_digest: 'e'.repeat(64) } : preview) : reply({ ...fork, status: 'COMPLETED' }));
  vi.stubGlobal('fetch', fetch); render(<StructuredForksPanel client={client()} />);
  fireEvent.click(await screen.findByRole('button', { name: '比较结构记录三方差异' })); await screen.findByText('基线名称'); expect(screen.getByText('原稿名称')).toBeTruthy(); expect(screen.getByText('副本名称')).toBeTruthy();
  const apply = screen.getByRole('button', { name: '确认结构检查点并合并' }) as HTMLButtonElement; expect(apply.disabled).toBe(true);
  fireEvent.change(screen.getByLabelText('合成人物 名称 结构冲突选择'), { target: { value: 'FORK' } }); expect(screen.getByText(/结构冲突选择已变化/)).toBeTruthy(); expect(apply.disabled).toBe(true);
  fireEvent.click(screen.getByRole('button', { name: '更新结构合并预览' })); await waitFor(() => expect((screen.getByLabelText('已核对结构三方差异，建立检查点并合并') as HTMLInputElement).disabled).toBe(false));
  fireEvent.click(screen.getByLabelText('已核对结构三方差异，建立检查点并合并')); fireEvent.click(apply);
  await waitFor(() => expect(fetch.mock.calls.filter(([url]) => url.endsWith('/apply'))).toHaveLength(1));
  expect(JSON.parse(String(fetch.mock.calls.find(([url]) => url.endsWith('/apply'))![1].body))).toEqual({ expected_version: 5, preview_digest: 'e'.repeat(64), confirmed: true, choices: { 'name-conflict': 'FORK' } });
});

it('unmount discards late comparison; no apply after closing or navigating scope', async () => {
  let resolve!: (response: Response) => void;
  const fetch = requests(() => new Promise<Response>(done => { resolve = done; })); vi.stubGlobal('fetch', fetch);
  const view = render(<StructuredForksPanel client={client()} />); fireEvent.click(await screen.findByRole('button', { name: '比较结构记录三方差异' }));
  view.unmount(); resolve(reply(preview)); await Promise.resolve(); expect(screen.queryByText('副本名称')).toBeNull();
  expect(fetch.mock.calls.some(([url]) => url.endsWith('/apply'))).toBe(false);
});

it('stale apply clears preview, preserves candidates and never automatically retries', async () => {
  const fetch = requests(url => url.endsWith('/compare') ? reply({ ...preview, can_apply: true, write_count: 1, unresolved: 0 }) : reply({ detail: { code: 'FORK_STALE_OR_CONFLICT' } }, 409));
  vi.stubGlobal('fetch', fetch); render(<StructuredForksPanel client={client()} />);
  fireEvent.click(await screen.findByRole('button', { name: '比较结构记录三方差异' })); await screen.findByText('基线名称');
  fireEvent.click(screen.getByLabelText('已核对结构三方差异，建立检查点并合并')); fireEvent.click(screen.getByRole('button', { name: '确认结构检查点并合并' }));
  await screen.findByText(/FORK_STALE_OR_CONFLICT/); expect(screen.queryByLabelText('结构三方合并预览')).toBeNull();
  fireEvent.click(screen.getByRole('button', { name: '刷新结构分叉记录' })); await screen.findByText('结构副本');
  expect(fetch.mock.calls.filter(([url]) => url.endsWith('/apply'))).toHaveLength(1);
});

it('attaches only to a displayed owned manuscript fork with exact record version, not a project ID', async () => {
  const fetch = requests(undefined, []); vi.stubGlobal('fetch', fetch);
  render(<StructuredForksPanel client={client()} manuscriptForks={[{ id: 'manuscript-fork', version: 9, status: 'FORKED', title: '已有正文副本', target_id: 'existing-target' }]} />);
  fireEvent.click(await screen.findByLabelText('人物：合成人物'));
  fireEvent.change(screen.getByLabelText('结构记录目标'), { target: { value: 'manuscript-fork' } });
  fireEvent.change(screen.getByLabelText('结构分叉项目名称'), { target: { value: '正文与人物同一项目' } });
  fireEvent.change(screen.getByLabelText('所选结构记录的许可说明'), { target: { value: '作者原创' } });
  fireEvent.click(screen.getByLabelText('我有权将所选结构记录复制到此本地新项目'));
  fireEvent.click(screen.getByRole('button', { name: '仅预检结构分叉' }));
  await waitFor(() => expect(fetch.mock.calls.some(([url]) => url.endsWith('/preflight'))).toBe(true));
  const body = JSON.parse(String(fetch.mock.calls.find(([url]) => url.endsWith('/preflight'))![1].body));
  expect(body.manuscript_fork).toEqual({ fork_id: 'manuscript-fork', expected_version: 9 }); expect(body.target_id).toBeUndefined();
  expect(screen.getByText(/正文与结构复制分两阶段/)).toBeTruthy();
});
