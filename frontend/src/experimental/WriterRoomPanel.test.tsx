// @vitest-environment jsdom
import { StrictMode } from 'react';
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

it('renders actual task progress and responsible change-request round trip without domain approval', async () => {
  const fetch = backend(); vi.stubGlobal('fetch', fetch); render(<WriterRoomPanel client={client()} />); await select();
  fireEvent.click(screen.getByRole('button', { name: '开始处理' }));
  fireEvent.click(await screen.findByRole('button', { name: '提交责任人审阅' }));
  const requestChanges = await screen.findByRole('button', { name: '请求修改并保留理由' }); expect((requestChanges as HTMLButtonElement).disabled).toBe(true);
  fireEvent.change(screen.getByLabelText('处理记录或修改理由'), { target: { value: '请补充人物动机🙂' } }); fireEvent.click(requestChanges);
  await waitFor(() => expect(screen.getAllByText(/需要修改/).length).toBeGreaterThan(0));
  const transitions = fetch.mock.calls.filter(([url]) => url.endsWith('/transition')).map(([, init]) => JSON.parse(String(init.body)));
  expect(transitions.map(v => v.expected_version)).toEqual([1, 2, 3]); expect(transitions[2].note).toBe('请补充人物动机🙂');
  expect(fetch.mock.calls.some(([url]) => /\/approve|\/accept|\/generate|\/invites/.test(url))).toBe(false);
});

it('preserves current Unicode edit on 409 and resolves persisted candidates against fresh expected version', async () => {
  let failed = false;
  const fetch = backend({ override: (_url, init, row, conflicts) => {
    if (init.method === 'PUT' && !failed) { failed = true; const submitted = JSON.parse(String(init.body)); row.description = 'Remote client preserved'; row.version = 2; conflicts.push({ id: 'conflict', version: 1, status: 'OPEN', target: { kind: 'task', id: row.id }, current_candidate: { ...row }, submitted_candidate: submitted }); return reply({ detail: { code: 'WRITER_ROOM_VERSION_CONFLICT' } }, 409); }
  } });
  vi.stubGlobal('fetch', fetch); render(<WriterRoomPanel client={client()} />); await select();
  fireEvent.change(screen.getByLabelText('当前任务说明'), { target: { value: '本机候选不能丢失🙂é' } });
  fireEvent.click(screen.getByRole('button', { name: '保存任务修改' }));
  await screen.findByText(/WRITER_ROOM_VERSION_CONFLICT/); await screen.findByText(/服务端已有较新版本/);
  expect((screen.getByLabelText('当前任务说明') as HTMLTextAreaElement).value).toBe('本机候选不能丢失🙂é');
  fireEvent.click(screen.getByRole('button', { name: '核对后采用提交候选' })); await screen.findByText('协作任务已保存。');
  const saves = fetch.mock.calls.filter(([, init]) => init.method === 'PUT');
  expect(JSON.parse(String(saves[1][1].body))).toMatchObject({ description: '本机候选不能丢失🙂é', expected_version: 2, resolve_conflict_id: 'conflict' });
});

it('read-only role can read a selected chapter but cannot create tasks or comments', async () => {
  const fetch = backend({ readonly: true }); vi.stubGlobal('fetch', fetch); render(<WriterRoomPanel client={client()} />);
  await screen.findByText('只读审阅权限'); expect(screen.queryByRole('button', { name: '创建协作任务' })).toBeNull();
  fireEvent.change(screen.getByLabelText('只读审阅章节'), { target: { value: 'chapter' } }); await screen.findByText('Read-only synthetic chapter 🙂');
  expect(screen.queryByRole('button', { name: '保存版本批注' })).toBeNull();
  expect(fetch.mock.calls.every(([, init]) => init.method === 'GET')).toBe(true);
});

it('branch source unavailable is explicit and never fetches base manuscript', async () => {
  const fetch = backend({ branchUnavailable: true }); vi.stubGlobal('fetch', fetch); render(<WriterRoomPanel client={client()} />);
  await screen.findByText(/原章节仓库尚未提供分支正文权限来源/);
  expect(screen.queryByText('Gate chapter')).toBeNull(); expect(fetch.mock.calls.some(([url]) => url.includes('/chapters/'))).toBe(false);
});

it('requires explicit selected-only preview and copy acknowledgment, and revokes stale Blob URLs', async () => {
  const createObjectURL = vi.fn(() => 'blob:review'), revokeObjectURL = vi.fn();
  vi.stubGlobal('URL', class extends URL { static createObjectURL = createObjectURL; static revokeObjectURL = revokeObjectURL; });
  const fetch = backend({ override: (url) => url.endsWith('/packages/preview') ? reply({ preview_digest: 'c'.repeat(64), selected_bytes: 3, manifest: { chapters: [{ title: 'Gate chapter', version: 1 }], assets: [], copy_warning: '无法远程收回' } }) : url.endsWith('/packages/download') ? reply({ filename: 'restricted-review.zip', mime: 'application/zip', content_base64: btoa('zip') }) : undefined });
  vi.stubGlobal('fetch', fetch); const view = render(<WriterRoomPanel client={client()} />); await screen.findByText('当前身份：writer');
  expect((screen.getByRole('button', { name: '预览受限审阅包' }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(screen.getByLabelText('章节：Gate chapter · v1')); fireEvent.click(screen.getByRole('button', { name: '预览受限审阅包' }));
  const download = await screen.findByRole('button', { name: '生成选定内容下载' }); expect((download as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(screen.getByLabelText('我了解下载副本无法远程撤回')); fireEvent.click(download); await screen.findByRole('link', { name: '下载受限审阅包' });
  const call = fetch.mock.calls.find(([url]) => url.endsWith('/packages/download'))!; expect(JSON.parse(String(call[1].body))).toMatchObject({ chapters: [{ id: 'chapter', revision: 'a'.repeat(64) }], asset_ids: [], acknowledge_copy_boundary: true });
  fireEvent.click(screen.getByLabelText('资产：selected.png · 3 bytes')); await waitFor(() => expect(screen.queryByRole('link', { name: '下载受限审阅包' })).toBeNull());
  expect(revokeObjectURL).toHaveBeenCalledWith('blob:review'); view.unmount();
});

it('hides cached content when current membership is revoked on refresh', async () => {
  let revoked = false;
  const fetch = backend({ override: () => revoked ? reply({ detail: { code: 'MEMBERSHIP_REVOKED' } }, 403) : undefined });
  vi.stubGlobal('fetch', fetch); render(<WriterRoomPanel client={client()} />); await select();
  revoked = true; fireEvent.click(screen.getByRole('button', { name: '刷新团队当前权限与任务' }));
  await screen.findAllByText(/MEMBERSHIP_REVOKED/); expect(screen.queryByRole('button', { name: 'Gate review' })).toBeNull();
  expect(screen.queryByRole('textbox', { name: '当前任务说明' })).toBeNull();
});

it('StrictMode create keeps trusted scope and ignores delayed result after scope change', async () => {
  let finish: (r: Response) => void = () => {};
  const fetch = backend({ override: (url, init) => url.includes('/other/') ? reply(url.endsWith('/writer-room') ? { items: [], actor: 'other', members: [], can_write: false, can_review: false } : url.endsWith('/catalog') ? { ...catalog, chapters: [] } : { items: [] }) : url.endsWith('/tasks') && init.method === 'POST' ? new Promise<Response>(resolve => { finish = resolve; }) : undefined });
  vi.stubGlobal('fetch', fetch); const view = render(<StrictMode><WriterRoomPanel client={client()} /></StrictMode>);
  const input = await screen.findByLabelText('新任务标题'); fireEvent.change(input, { target: { value: 'Old scope pending' } }); fireEvent.click(screen.getByRole('button', { name: '创建协作任务' }));
  await waitFor(() => expect(fetch.mock.calls.some(([url]) => url.endsWith('/tasks'))).toBe(true));
  const request = fetch.mock.calls.find(([url]) => url.endsWith('/tasks'))!; expect(new Headers(request[1].headers).get('X-Session-Token')).toBe('trusted'); expect(new Headers(request[1].headers).get('X-Branch-Id')).toBe('branch');
  view.rerender(<StrictMode><WriterRoomPanel client={client('other')} /></StrictMode>); finish(reply({ ...task(), title: 'Old scope pending' }, 201));
  await screen.findByText('当前身份：other'); expect(screen.queryByDisplayValue('Old scope pending')).toBeNull();
});

it('retains unsaved task candidates across task switching and warns before unloading', async () => {
  const first = task(), second = { ...task(), id: 'second', title: 'Other review', description: 'Other server' };
  const fetch = backend({ override: (url) => url.endsWith('/writer-room') ? reply({ items: [first, second], actor: 'writer', members: [{ id: 'writer', name: 'Writer', can_write: true, can_review: true }], can_write: true, can_review: true }) : url.includes('/index') ? reply({ items: [first, second] }) : undefined });
  vi.stubGlobal('fetch', fetch); const view = render(<WriterRoomPanel client={client()} />); await select();
  fireEvent.change(screen.getByLabelText('当前任务说明'), { target: { value: 'Unsaved task one 🙂' } });
  fireEvent.click(screen.getByRole('button', { name: 'Other review' }));
  expect((screen.getByLabelText('当前任务说明') as HTMLTextAreaElement).value).toBe('Other server');
  const event = new Event('beforeunload', { cancelable: true }); window.dispatchEvent(event); expect(event.defaultPrevented).toBe(true);
  fireEvent.click(screen.getByRole('button', { name: 'Gate review' }));
  expect((screen.getByLabelText('当前任务说明') as HTMLTextAreaElement).value).toBe('Unsaved task one 🙂');
  view.unmount(); const clean = new Event('beforeunload', { cancelable: true }); window.dispatchEvent(clean); expect(clean.defaultPrevented).toBe(false);
});

it('passes the verified original inbox feature identity to the shared navigation contract', async () => {
  vi.stubGlobal('fetch', backend()); const navigate = vi.fn(); render(<WriterRoomPanel client={client()} onNavigate={navigate} />);
  const button = await screen.findByRole('button', { name: '打开统一审核收件箱' }); fireEvent.click(button);
  expect(navigate).toHaveBeenCalledWith({ kind: 'feature', id: 'unified_review_inbox', feature: 'unified_review_inbox' });
});
