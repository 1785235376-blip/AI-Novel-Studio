// @vitest-environment jsdom
// Extracted additions and migrated variants; protected baseline suite stays byte-identical.
// Migrated variants preserve newer assertions and are not counted as unique new capabilities.

import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { experimentalClient } from './api';
import { WriterRoomPanel } from './WriterRoomPanel';
import type { RoomTask, RoomConflict } from './writerRoomClient';
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });
const client = (id = 'n') => experimentalClient(id, { sessionToken: 'trusted', scope: { branchId: 'branch' } as any });
const reply = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status, headers: { 'Content-Type': 'application/json' } });
const task = (): RoomTask => ({ id: 'task', version: 1, title: 'Gate review', description: 'Server original', assignee: 'writer', reviewer: 'writer', created_by: 'writer', status: 'ASSIGNED', source_state: 'CURRENT', participants_current: true, chapter: null, review_target: null, events: [] });
const catalog = { chapters: [{ id: 'chapter', title: 'Gate chapter', version: 1, revision: 'a'.repeat(64) }], chapter_state: 'AVAILABLE', assets: [{ id: 'asset', filename: 'selected.png', sha256: 'b'.repeat(64), size: 3 }], asset_state: 'AVAILABLE', review_targets: [], truncated: false };
function backend(options: { row?: RoomTask; readonly?: boolean; branchUnavailable?: boolean; override?: (url: string, init: RequestInit, row: RoomTask, conflicts: RoomConflict[]) => Response | Promise<Response> | undefined } = {}) {
  const row = options.row || task(), conflicts: RoomConflict[] = [];
  return vi.fn(async (url: string, init: RequestInit) => {
    const override = await options.override?.(url, init, row, conflicts); if (override) return override;
    if (url.endsWith('/catalog')) return reply(options.branchUnavailable ? { ...catalog, chapters: [], chapter_state: 'BRANCH_SOURCE_UNAVAILABLE' } : catalog);
    if (url.includes('/chapters/')) return reply({ title: 'Gate chapter', version: 1, text: 'Read-only synthetic chapter 🙂', mode: 'READ_ONLY' });
    if (url.endsWith('/conflicts')) return reply({ items: conflicts });
    if (url.endsWith('/notices')) return reply({ items: [{ id: 'task:1', title: 'Gate review', status: 'ASSIGNED' }] });
    if (url.endsWith('/comments')) return reply({ items: [], source_state: 'AVAILABLE' });
    if (url.includes('/index')) return reply({ items: [row] });
    if (url.endsWith('/writer-room')) return reply({ items: [row], actor: 'writer', members: [{ id: 'writer', name: 'Synthetic writer', can_write: true, can_review: true }], can_write: !options.readonly, can_review: !options.readonly, truncated: false, copy_warning: '已下载副本无法远程收回' });
    const body = JSON.parse(String(init.body));
    if (url.endsWith('/tasks')) return reply({ ...row, ...body }, 201);
    if (init.method === 'PUT') { Object.assign(row, body, { version: row.version + 1 }); return reply(row); }
    if (url.endsWith('/transition')) { row.status = body.action === 'start' ? 'IN_PROGRESS' : body.action === 'submit' ? 'READY_FOR_REVIEW' : body.action === 'request_changes' ? 'CHANGES_REQUESTED' : 'CLOSED'; row.version++; row.events.push({ action: body.action, actor: 'writer', at: '', note: body.note }); return reply(row); }
    throw new Error('Unexpected request ' + url);
  });
}
async function select() { fireEvent.click(await screen.findByRole('button', { name: 'Gate review' })); }

it('reads the task-pinned chapter digest only on demand and exposes exact review identity and event time', async () => {
  const row = { ...task(), chapter: { id: 'chapter', revision: 'd'.repeat(64) }, review_target: { domain: 'canon', id: 'review-exact', version: 7 }, events: [{ action: 'start', actor: 'writer', at: '2026-10-16T12:00:00Z', note: 'Checked source' }] };
  const fetch = backend({ row }); vi.stubGlobal('fetch', fetch); render(<WriterRoomPanel client={client()} />); await select();
  expect(fetch.mock.calls.some(([url]) => url.includes('/chapters/'))).toBe(false);
  fireEvent.click(screen.getByText('任务绑定来源与版本'));
  expect(screen.getByText('审核项 ID：review-exact · 绑定版本 v7')).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: '读取任务绑定章节版本' }));
  await screen.findByText('Read-only synthetic chapter 🙂');
  expect(fetch.mock.calls.filter(([url]) => url.includes('/chapters/')).map(([url]) => url.split('?')[1])).toEqual(['revision=' + 'd'.repeat(64)]);
  fireEvent.click(screen.getByText('任务处理历史（1）'));
  expect(screen.getByText('2026-10-16T12:00:00Z').getAttribute('datetime')).toBe('2026-10-16T12:00:00Z');
  expect(fetch.mock.calls.every(([, init]) => init.method === 'GET')).toBe(true);
});

it('does not substitute the catalog chapter when the task-pinned revision is stale', async () => {
  const row = { ...task(), status: 'READY_FOR_REVIEW', source_state: 'STALE', chapter: { id: 'chapter', revision: 'd'.repeat(64) } };
  const fetch = backend({ row, override: url => url.includes('/chapters/') ? reply({ detail: { code: 'SOURCE_STALE' } }, 409) : undefined });
  vi.stubGlobal('fetch', fetch); render(<WriterRoomPanel client={client()} />); await select();
  expect((screen.getByRole('button', { name: '完成协作任务' }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(screen.getByText('任务绑定来源与版本')); fireEvent.click(screen.getByRole('button', { name: '读取任务绑定章节版本' }));
  await screen.findByText(/绑定版本暂不可读取/);
  expect(fetch.mock.calls.filter(([url]) => url.includes('/chapters/'))).toHaveLength(1);
  expect(screen.queryByText('Read-only synthetic chapter 🙂')).toBeNull();
});

it('preserves note-only drafts across task switches and clears a note after a confirmed transition', async () => {
  const first = task(), second = { ...task(), id: 'second', title: 'Other review' };
  const fetch = backend({ row: first, override: url => url.endsWith('/writer-room') ? reply({ items: [first, second], actor: 'writer', members: [], can_write: true, can_review: true }) : url.includes('/index') ? reply({ items: [first, second] }) : undefined });
  vi.stubGlobal('fetch', fetch); render(<WriterRoomPanel client={client()} />); await select();
  fireEvent.change(screen.getByLabelText('处理记录或修改理由'), { target: { value: '待处理理由 🙂' } });
  fireEvent.click(screen.getByRole('button', { name: 'Other review' }));
  expect((screen.getByLabelText('处理记录或修改理由') as HTMLTextAreaElement).value).toBe('');
  const pending = new Event('beforeunload', { cancelable: true }); window.dispatchEvent(pending); expect(pending.defaultPrevented).toBe(true);
  fireEvent.click(screen.getByRole('button', { name: 'Gate review' }));
  expect((screen.getByLabelText('处理记录或修改理由') as HTMLTextAreaElement).value).toBe('待处理理由 🙂');
  fireEvent.click(screen.getByRole('button', { name: '开始处理' })); await screen.findByRole('button', { name: '提交责任人审阅' });
  expect((screen.getByLabelText('处理记录或修改理由') as HTMLTextAreaElement).value).toBe('');
  const clean = new Event('beforeunload', { cancelable: true }); window.dispatchEvent(clean); expect(clean.defaultPrevented).toBe(false);
  expect(JSON.parse(String(fetch.mock.calls.find(([url]) => url.endsWith('/transition'))![1].body))).toMatchObject({ expected_version: 1, note: '待处理理由 🙂' });
});

it('retains decision notes after an unknown outcome without replaying the transition', async () => {
  const fetch = backend({ override: url => url.endsWith('/transition') ? Promise.reject(new Error('connection lost')) : undefined });
  vi.stubGlobal('fetch', fetch); render(<WriterRoomPanel client={client()} />); await select();
  fireEvent.change(screen.getByLabelText('处理记录或修改理由'), { target: { value: 'Keep until receipt verified' } });
  fireEvent.click(screen.getByRole('button', { name: '开始处理' }));
  await screen.findByText('读取或操作失败，请重试。');
  expect((screen.getByLabelText('处理记录或修改理由') as HTMLTextAreaElement).value).toBe('Keep until receipt verified');
  expect(fetch.mock.calls.filter(([url]) => url.endsWith('/transition'))).toHaveLength(1);
});

it('drops delayed task context when the reader switches tasks and invalidates loaded context on refresh', async () => {
  const first = { ...task(), chapter: { id: 'chapter', revision: 'd'.repeat(64) } }, second = { ...task(), id: 'second', title: 'Other review' };
  let finish: (value: Response) => void = () => {};
  const fetch = backend({ row: first, override: url => url.includes('/chapters/') ? new Promise<Response>(resolve => { finish = resolve; }) : url.endsWith('/writer-room') ? reply({ items: [first, second], actor: 'writer', members: [], can_write: true, can_review: true }) : url.includes('/index') ? reply({ items: [first, second] }) : undefined });
  vi.stubGlobal('fetch', fetch); render(<WriterRoomPanel client={client()} />); await select();
  fireEvent.click(screen.getByText('任务绑定来源与版本')); fireEvent.click(screen.getByRole('button', { name: '读取任务绑定章节版本' }));
  await waitFor(() => expect(fetch.mock.calls.some(([url]) => url.includes('/chapters/'))).toBe(true));
  const signal = fetch.mock.calls.find(([url]) => url.includes('/chapters/'))![1].signal;
  fireEvent.click(screen.getByRole('button', { name: 'Other review' }));
  expect(signal?.aborted).toBe(true);
  finish(reply({ title: 'Delayed chapter', version: 1, text: 'Delayed source must not leak', mode: 'READ_ONLY' }));
  fireEvent.click(screen.getByRole('button', { name: 'Gate review' }));
  expect(screen.queryByText('Delayed source must not leak')).toBeNull();
  fireEvent.click(screen.getByText('任务绑定来源与版本')); fireEvent.click(screen.getByRole('button', { name: '读取任务绑定章节版本' }));
  await waitFor(() => expect(fetch.mock.calls.filter(([url]) => url.includes('/chapters/'))).toHaveLength(2));
  finish(reply({ title: 'Current source', version: 1, text: 'Verified pinned text', mode: 'READ_ONLY' }));
  await screen.findByText('Verified pinned text');
  fireEvent.click(screen.getByRole('button', { name: '刷新团队当前权限与任务' }));
  await screen.findByRole('button', { name: 'Gate review' });
  expect(screen.queryByText('Verified pinned text')).toBeNull();
  expect(fetch.mock.calls.filter(([url]) => url.includes('/chapters/'))).toHaveLength(2);
});
