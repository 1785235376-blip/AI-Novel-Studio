// @vitest-environment jsdom
import { StrictMode } from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { ProjectForksPanel } from './ProjectForksPanel';
import { experimentalClient } from './api';
import type { ForkComparison, ForkRecord } from './projectForksClient';
const reply = (data: unknown, status = 200) => new Response(JSON.stringify(data), { status });
const client = (nid = 'n1') => experimentalClient(nid, { sessionToken: 'host' });
const catalog = { available: true, chapters: [{ id: 'n1:1', title: '合成海港', version: 2, asset_ids: [] }], assets: [], limitations: [] };
const fork: ForkRecord = { id: 'f1', version: 8, title: '合成分叉', target_id: 'fork-project', status: 'FORKED', chapter_count: 1, id_map: { chapters: { 'n1:1': 'fork-project:1' }, assets: {} } };
const node = (text: string) => ({ type: 'paragraph', content: [{ type: 'text', text, marks: [{ type: 'bold' }] }] });
const conflict: ForkComparison = { fork_id: 'f1', expected_version: 8, preview_digest: 'b'.repeat(64), can_apply: false, unresolved: 1, write_count: 0, blocked: [], chapters: [{ chapter_id: 'n1:1', fork_chapter_id: 'fork-project:1', title: '合成海港', original_version: 3, fork_version: 3, segments: [{ id: 'choice-one', kind: 'CONFLICT', reason: 'RICH_BLOCK_OVERLAP', base: [node('基线段落')], ORIGINAL: [node('原稿改文')], FORK: [node('副本改文')] }] }] };
function requests(items: ForkRecord[] = [fork], mutation?: (url: string, init: RequestInit) => Response | Promise<Response>, merges: ForkRecord[] = []) {
  return vi.fn(async (url: string, init: RequestInit) => {
    if (init.method !== 'GET') return mutation ? mutation(url, init) : reply(fork);
    if (url.endsWith('/catalog')) return reply(catalog);
    return reply({ items, merges });
  });
}
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

it('StrictMode reads only; selected preflight never creates without a separate exact confirmation', async () => {
  const pre: ForkRecord = { ...fork, status: 'PREFLIGHT', version: 1, preview_digest: 'a'.repeat(64) };
  const fetch = requests([pre]); vi.stubGlobal('fetch', fetch);
  render(<StrictMode><ProjectForksPanel client={client()} /></StrictMode>);
  await screen.findByText('合成分叉'); expect(fetch.mock.calls.every(([, init]) => init.method === 'GET')).toBe(true);
  const create = screen.getByRole('button', { name: '确认创建新项目分叉' }) as HTMLButtonElement;
  expect(create.disabled).toBe(true);
  fireEvent.click(screen.getByLabelText('已核对所选章节与媒体许可，创建此新项目分叉')); fireEvent.click(create); fireEvent.click(create);
  await waitFor(() => expect(fetch.mock.calls.filter(([url]) => url.endsWith('/create'))).toHaveLength(1));
  const [, init] = fetch.mock.calls.find(([url]) => url.endsWith('/create'))!;
  expect(JSON.parse(String(init.body))).toEqual({ expected_version: 1, preview_digest: pre.preview_digest, confirmed: true });
  expect(init.headers).toMatchObject({ 'X-Session-Token': 'host' });
});

it('shows all three rich versions, requires each conflict choice then refreshed preview and separate apply', async () => {
  const fetch = requests([fork], (url, init) => {
    if (url.endsWith('/compare')) { const body = JSON.parse(String(init.body)); return reply(body.choices['choice-one'] ? { ...conflict, preview_digest: 'c'.repeat(64), unresolved: 0, can_apply: true, write_count: 1 } : conflict); }
    return reply({ id: 'merge', version: 4, status: 'COMPLETED' });
  }); vi.stubGlobal('fetch', fetch); render(<ProjectForksPanel client={client()} />);
  fireEvent.click(await screen.findByRole('button', { name: '比较基线、原稿与副本' }));
  await screen.findByText('基线段落'); expect(screen.getByText('原稿改文').closest('strong')).toBeTruthy(); expect(screen.getByText('副本改文')).toBeTruthy();
  const apply = screen.getByRole('button', { name: '确认检查点并合并' }) as HTMLButtonElement; expect(apply.disabled).toBe(true);
  fireEvent.change(screen.getByLabelText('合成海港 冲突 1 选择'), { target: { value: 'FORK' } });
  expect(apply.disabled).toBe(true); expect(screen.getByText(/选择已改变/)).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: '更新合并预览' })); await waitFor(() => expect((screen.getByLabelText('已逐项核对三方差异，建立检查点并合并回原稿') as HTMLInputElement).disabled).toBe(false));
  expect(apply.disabled).toBe(true); fireEvent.click(screen.getByLabelText('已逐项核对三方差异，建立检查点并合并回原稿')); fireEvent.click(apply);
  await waitFor(() => expect(fetch.mock.calls.some(([url]) => url.endsWith('/apply'))).toBe(true));
  const [, init] = fetch.mock.calls.find(([url]) => url.endsWith('/apply'))!;
  expect(JSON.parse(String(init.body))).toEqual({ expected_version: 8, preview_digest: 'c'.repeat(64), choices: { 'choice-one': 'FORK' }, confirmed: true });
});

it('stale apply clears old preview; refresh does not replay a write', async () => {
  const fetch = requests([fork], url => url.endsWith('/compare') ? reply({ ...conflict, unresolved: 0, can_apply: true, write_count: 1 }) : reply({ detail: { code: 'FORK_STALE_OR_CONFLICT' } }, 409));
  vi.stubGlobal('fetch', fetch); render(<ProjectForksPanel client={client()} />);
  fireEvent.click(await screen.findByRole('button', { name: '比较基线、原稿与副本' })); await screen.findByText('基线段落');
  fireEvent.click(screen.getByLabelText('已逐项核对三方差异，建立检查点并合并回原稿')); fireEvent.click(screen.getByRole('button', { name: '确认检查点并合并' }));
  await waitFor(() => expect(fetch.mock.calls.filter(([url]) => url.endsWith('/apply'))).toHaveLength(1));
  await waitFor(() => expect(screen.queryByLabelText('三方合并预览')).toBeNull());
  expect(await screen.findByText(/FORK_STALE_OR_CONFLICT/)).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: '刷新分叉与合并记录' }));
  await screen.findByText('合成分叉'); expect(fetch.mock.calls.filter(([url]) => url.endsWith('/apply'))).toHaveLength(1);
});

it('media copy requires per-asset license and permission; input stays local until explicit preflight', async () => {
  const fetch = requests([], (_url, init) => reply(JSON.parse(String(init.body))));
  const media = { id: 'a1', filename: 'test.wav', version: 4, sha256: 'd'.repeat(64) };
  fetch.mockImplementation(async (url, init) => init.method !== 'GET' ? reply(fork) : url.endsWith('/catalog') ? reply({ ...catalog, chapters: [{ ...catalog.chapters[0], asset_ids: ['a1'] }], assets: [media] }) : reply({ items: [], merges: [] }));
  vi.stubGlobal('fetch', fetch); render(<ProjectForksPanel client={client()} />);
  fireEvent.change(screen.getByLabelText('新分叉项目名称'), { target: { value: '有许可的分叉' } }); fireEvent.click(await screen.findByLabelText('合成海港 · v2'));
  const button = screen.getByRole('button', { name: '仅预检所选分叉' }) as HTMLButtonElement; expect(button.disabled).toBe(true);
  fireEvent.change(screen.getByLabelText('媒体许可说明：test.wav'), { target: { value: '作者原创合成媒体' } }); expect(button.disabled).toBe(true);
  fireEvent.click(screen.getByLabelText('我有权将 test.wav 复制到此本地分叉')); expect(button.disabled).toBe(false);
  expect(fetch.mock.calls.every(([, init]) => init.method === 'GET')).toBe(true); fireEvent.click(button);
  await waitFor(() => expect(fetch.mock.calls.some(([url]) => url.endsWith('/preflight'))).toBe(true));
  const body = JSON.parse(String(fetch.mock.calls.find(([url]) => url.endsWith('/preflight'))![1].body));
  expect(body.asset_permissions).toEqual([{ asset_id: 'a1', version: 4, sha256: media.sha256, license: '作者原创合成媒体', allow_local_copy: true }]);
  expect(fetch.mock.calls.some(([url]) => url.endsWith('/create'))).toBe(false);
});

it('unknown journal never auto-retries; checkpoint restore is separately confirmed', async () => {
  const merge: ForkRecord = { id: 'm1', version: 5, target_id: 'fork-project', fork_id: fork.id, status: 'RECOVERY_REQUIRED', kind: 'MERGE' };
  const recovery = { id: 'm1', expected_version: 5, preview_digest: 'e'.repeat(64), can_restore: true, blocked: [], journal: [{ status: 'CLAIMED' }], checkpoint: { 'n1:1': { document: { type: 'doc', content: [node('检查点内容')] } } }, current: { 'n1:1': { document: { type: 'doc', content: [node('当前未知结果')] } } }, observations: [{ chapter_id: 'n1:1', checkpoint_version: 2, current_version: 3, state: 'MATCHES_INTENT_UNCONFIRMED' }] };
  const fetch = requests([{ ...fork, active_merge: merge.id }], url => url.endsWith('/recovery') ? reply(recovery) : reply({ ...merge, status: 'RESTORED' }), [merge]);
  vi.stubGlobal('fetch', fetch); render(<ProjectForksPanel client={client()} />);
  fireEvent.click(await screen.findByRole('button', { name: '核对检查点与当前结果' })); await screen.findByText('检查点内容'); expect(screen.getByText('当前未知结果')).toBeTruthy();
  const button = screen.getByRole('button', { name: '确认恢复检查点' }) as HTMLButtonElement; expect(button.disabled).toBe(true);
  expect(fetch.mock.calls.some(([url]) => url.endsWith('/apply'))).toBe(false);
  fireEvent.click(screen.getByLabelText('已核对当前内容，明确恢复此合并前检查点为新版本')); fireEvent.click(button);
  await waitFor(() => expect(fetch.mock.calls.some(([url]) => url.endsWith('/restore'))).toBe(true));
  expect(JSON.parse(String(fetch.mock.calls.find(([url]) => url.endsWith('/restore'))![1].body))).toEqual({ expected_version: 5, preview_digest: recovery.preview_digest, confirmed: true });
});

it('scope replacement removes previews and ignores the old late comparison', async () => {
  let resolve!: (response: Response) => void;
  const fetch = requests([fork], () => new Promise<Response>(done => { resolve = done; })); vi.stubGlobal('fetch', fetch);
  const view = render(<ProjectForksPanel client={client()} />);
  fireEvent.click(await screen.findByRole('button', { name: '比较基线、原稿与副本' }));
  vi.stubGlobal('fetch', vi.fn(() => new Promise<Response>(() => {}))); view.rerender(<ProjectForksPanel client={client('different-project')} />);
  resolve(reply(conflict)); await Promise.resolve(); await Promise.resolve();
  expect(screen.queryByText('基线段落')).toBeNull(); expect(screen.queryByText('合成分叉')).toBeNull();
  expect(fetch.mock.calls.some(([url]) => url.endsWith('/apply') || url.endsWith('/create'))).toBe(false);
});
