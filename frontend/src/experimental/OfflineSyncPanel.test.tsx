// @vitest-environment jsdom
import { StrictMode } from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { experimentalClient } from './api';
import { OfflineSyncPanel } from './OfflineSyncPanel';
import type { SyncChannel, SyncPlan, SyncRecords, SyncRow } from './offlineSyncClient';
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });
const client = (nid = 'project') => experimentalClient(nid, { sessionToken: 'synthetic-host' });
const response = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status, headers: { 'Content-Type': 'application/json' } });
const channel = (): SyncChannel => ({ id: 'channel', version: 1, status: 'ACTIVE', stream_id: 'batch', endpoint_id: 'A', peer_id: 'B', chapter_ids: ['chapter'], allow_new_chapters: true, send_cursor: 0, receive_cursor: 0 });
const row = (status = 'PENDING_REVIEW'): SyncRow => ({ id: 'message', channel_id: 'channel', version: 1, status, sequence: 1, operation: 'SNAPSHOT', target_chapter_id: 'chapter', source_version: 2, envelope_digest: 'a'.repeat(64), attempts: 0 });
const envelope = { protocol: 'AI_NOVEL_SYNC_1', stream_id: 'batch', source_endpoint: 'A', destination_endpoint: 'B', message_id: 'message', sequence: 1, source_chapter_id: 'chapter', source_version: 2, operation: 'SNAPSHOT', base: { title: 'Shared', document: { type: 'doc', content: [] } }, snapshot: { title: 'Synthetic', document: { type: 'doc', content: [] } }, privacy_level: 'LOCAL_ONLY' };
const plan = (choices = {}): SyncPlan => ({ message_id: 'message', version: 1, preview_digest: 'b'.repeat(64), base: 'baseline', current: 'local candidate🙂', incoming: 'incoming candidate', desired: 'incoming candidate', can_apply: Object.keys(choices).length > 0, unresolved: Object.keys(choices).length ? 0 : 1, choices, blocked: [], operation: 'SNAPSHOT', segments: [{ id: 'conflict', kind: 'CONFLICT', base: 'baseline', local: 'local candidate🙂', incoming: 'incoming candidate' }] });
function backend(options: { records?: SyncRecords; override?: (url: string, init: RequestInit, records: SyncRecords) => Response | Promise<Response> | undefined } = {}) {
  const records: SyncRecords = options.records || { channels: [channel()], outbox: [], inbox: [], network_enabled: false };
  return vi.fn(async (url: string, init: RequestInit) => {
    const overridden = await options.override?.(url, init, records); if (overridden) return overridden;
    if (url.endsWith('/catalog')) return response({ chapters: [{ id: 'chapter', title: 'Selected synthetic chapter', version: 2 }, { id: 'other', title: 'Unselected synthetic chapter', version: 1 }], network_enabled: false, truncated: false });
    if (url.endsWith('/records')) return response(records);
    if (url.endsWith('/selection/preview')) { const body = JSON.parse(String(init.body)); return response({ channel_id: 'channel', version: records.channels[0].version, additions: body.add_chapter_ids.map((id: string) => ({ id, title: 'Fresh baseline', version: 1, document: 'Saved original baseline🙂' })), withdraw_chapter_ids: body.withdraw_chapter_ids, preview_digest: 'd'.repeat(64), copy_boundary: 'DOWNLOADED_COPIES_AND_BACKUPS_CANNOT_BE_RECALLED' }); }
    if (url.endsWith('/selection')) {
      const body = JSON.parse(String(init.body)), current = records.channels[0]; current.version++;
      current.chapter_ids = current.chapter_ids.filter(id => !body.withdraw_chapter_ids.includes(id)).concat(body.add_chapter_ids);
      current.withdrawn_chapter_ids = (current.withdrawn_chapter_ids || []).concat(body.withdraw_chapter_ids);
      for (const item of [...records.outbox, ...records.inbox]) if (body.withdraw_chapter_ids.includes(item.chapter_id || item.target_chapter_id)) { item.selection_withdrawn = true; item.version++; if (['PENDING', 'PENDING_REVIEW'].includes(item.status)) item.status = 'SELECTION_REVOKED'; }
      return response(current);
    }
    if (url.endsWith('/queue')) { const output = row('PENDING'); records.outbox.push(output); records.channels[0].version++; return response(output); }
    if (url.endsWith('/review')) return response(plan(JSON.parse(String(init.body)).choices));
    if (url.endsWith('/apply')) { records.inbox[0].status = 'APPLIED'; records.inbox[0].version++; return response(records.inbox[0]); }
    if (url.endsWith('/outbox/message')) return response({ ...records.outbox[0], envelope });
    if (url.endsWith('/export')) { const out = records.outbox[0]; out.version++; out.status = 'UNKNOWN'; out.attempts = 1; return response({ ...out, envelope }); }
    if (url.endsWith('/revoke')) { records.channels[0].status = 'REVOKED'; records.channels[0].version++; return response(records.channels[0]); }
    if (url.endsWith('/channels')) { const value = { ...channel(), ...JSON.parse(String(init.body)) }; records.channels.push(value); return response(value, 201); }
    throw new Error('Unexpected request ' + url);
  });
}
async function select() { fireEvent.click(await screen.findByRole('button', { name: 'batch · A → B' })); }

it('defaults to no selection, no mutation or external transport, and explicit selected chapter queue', async () => {
  const fetch = backend(); vi.stubGlobal('fetch', fetch); render(<OfflineSyncPanel client={client()} />); await select();
  expect((screen.getByRole('button', { name: '保存到本机发件箱' }) as HTMLButtonElement).disabled).toBe(true);
  expect((screen.getByLabelText('同步范围：Selected synthetic chapter · v2') as HTMLInputElement).checked).toBe(false);
  expect(fetch.mock.calls.every(([, init]) => init.method === 'GET')).toBe(true);
  fireEvent.change(screen.getByLabelText('加入发件箱的已选章节'), { target: { value: 'chapter' } }); fireEvent.click(screen.getByRole('button', { name: '保存到本机发件箱' }));
  await screen.findByText(/当前保存版本已进入持久发件箱/);
  const call = fetch.mock.calls.find(([url]) => url.endsWith('/queue'))!;
  expect(JSON.parse(String(call[1].body))).toMatchObject({ expected_version: 1, chapter_id: 'chapter', tombstone: false });
  expect(new Headers(call[1].headers).get('X-Session-Token')).toBe('synthetic-host');
  expect(fetch.mock.calls.every(([url]) => url.startsWith('/api/novels/project/experimental/offline-sync'))).toBe(true);
});

it('outbox preview requires copy acknowledgement, reuses same envelope and cleans up local file on revocation', async () => {
  const make = vi.fn(() => 'blob:sync'), revoke = vi.fn(); vi.stubGlobal('URL', class extends URL { static createObjectURL = make; static revokeObjectURL = revoke; });
  const fetch = backend({ records: { channels: [channel()], outbox: [row('PENDING')], inbox: [], network_enabled: false } });
  vi.stubGlobal('fetch', fetch); render(<OfflineSyncPanel client={client()} />); await select();
  fireEvent.click(screen.getByRole('button', { name: '预览此消息内容' }));
  const exportButton = await screen.findByRole('button', { name: '生成手动交换文件' }); expect((exportButton as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(screen.getByLabelText('我了解导出的本地副本无法远程撤回')); fireEvent.click(exportButton); await screen.findByRole('link', { name: '下载本地同步消息' });
  expect(make).toHaveBeenCalledTimes(1); expect(JSON.parse(String(fetch.mock.calls.find(([url]) => url.endsWith('/export'))![1].body))).toMatchObject({ acknowledge_copy_boundary: true, envelope_digest: 'a'.repeat(64) });
  fireEvent.click(screen.getByLabelText('停止此范围后续交换，已有下载和备份仍可能存在')); fireEvent.click(screen.getByRole('button', { name: '撤销此交换范围' }));
  await screen.findByText(/后续导出、接收和应用已停止/); expect(screen.queryByRole('link', { name: '下载本地同步消息' })).toBeNull(); expect(revoke).toHaveBeenCalledWith('blob:sync');
});

it('keeps Unicode pasted input after failed receive, never auto applies, and invalidates preview when target changes', async () => {
  const fetch = backend({ override: url => url.endsWith('/receive') ? response({ code: 'SYNC_TEST_DISCONNECT' }, 503) : undefined }); vi.stubGlobal('fetch', fetch); render(<OfflineSyncPanel client={client()} />); await select();
  const text = JSON.stringify({ ...envelope, note: '合成输入🙂é' }); fireEvent.change(screen.getByLabelText('收到的同步消息 JSON'), { target: { value: text } });
  fireEvent.change(screen.getByLabelText('收到章节的本机目标'), { target: { value: 'chapter' } }); fireEvent.click(screen.getByRole('button', { name: '预览待接收消息' }));
  fireEvent.click(await screen.findByRole('button', { name: '接收到待审核收件箱' })); await screen.findByText(/SYNC_TEST_DISCONNECT/);
  expect((screen.getByLabelText('收到的同步消息 JSON') as HTMLTextAreaElement).value).toBe(text);
  expect(fetch.mock.calls.some(([url]) => url.endsWith('/apply'))).toBe(false);
  fireEvent.change(screen.getByLabelText('收到章节的本机目标'), { target: { value: '__NEW__' } }); expect(screen.queryByRole('button', { name: '接收到待审核收件箱' })).toBeNull();
});

it('shows three-way conflict, requires renewed preview and acknowledgement before original apply', async () => {
  const fetch = backend({ records: { channels: [channel()], outbox: [], inbox: [row()], network_enabled: false } }); vi.stubGlobal('fetch', fetch); render(<OfflineSyncPanel client={client()} />); await select();
  fireEvent.click(screen.getByRole('button', { name: '读取当前三方差异' })); await screen.findByLabelText('冲突选择 1');
  expect((screen.getByRole('button', { name: '应用已核对的候选' }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.change(screen.getByLabelText('冲突选择 1'), { target: { value: 'INCOMING' } });
  expect((screen.getByRole('button', { name: '应用已核对的候选' }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(screen.getByRole('button', { name: '读取当前三方差异' }));
  const ack = screen.getByLabelText('已核对差异，允许通过原章节权限与版本检查应用'); await waitFor(() => expect((ack as HTMLInputElement).disabled).toBe(false));
  fireEvent.click(ack); fireEvent.click(screen.getByRole('button', { name: '应用已核对的候选' })); await screen.findByText(/原章节写入已确认/);
  expect(JSON.parse(String(fetch.mock.calls.find(([url]) => url.endsWith('/apply'))![1].body))).toMatchObject({ expected_version: 1, preview_digest: 'b'.repeat(64), choices: { conflict: 'INCOMING' }, confirmed: true });
});

it('unknown write offers observation/adoption or explicit close, with no automatic retry or apply', async () => {
  const fetch = backend({ records: { channels: [channel()], outbox: [], inbox: [row('UNKNOWN')], network_enabled: false }, override: (url, init) => url.endsWith('/recovery') ? response({ id: 'message', version: 1, status: 'UNKNOWN', observations: [{ chapter_id: 'chapter', version: 2, state: 'DIVERGED_OR_PARTIAL', document: 'retained' }], can_adopt: false, retry_allowed: false, preview_digest: 'c'.repeat(64) }) : undefined });
  vi.stubGlobal('fetch', fetch); render(<OfflineSyncPanel client={client()} />); await select();
  expect(screen.queryByRole('button', { name: '应用已核对的候选' })).toBeNull(); fireEvent.click(screen.getByRole('button', { name: '核对未知写入结果' }));
  const adopt = await screen.findByRole('button', { name: '确认采用完全匹配的已有结果' }); expect((adopt as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(screen.getByRole('button', { name: '保留所有候选并关闭此未知记录' })); await screen.findByText(/该未知记录已人工关闭/);
  const requests = fetch.mock.calls.filter(([url]) => url.endsWith('/recovery')); expect(JSON.parse(String(requests[1][1].body))).toMatchObject({ close_without_replay: true, adopt_matching_result: false, preview_digest: 'c'.repeat(64) });
  expect(fetch.mock.calls.some(([url]) => url.endsWith('/apply'))).toBe(false);
});

it('refresh denial hides cached pending content and all exchange actions', async () => {
  let denied = false; const fetch = backend({ records: { channels: [channel()], outbox: [row('PENDING')], inbox: [], network_enabled: false }, override: () => denied ? response({ code: 'SYNC_MEMBERSHIP_REVOKED' }, 403) : undefined });
  vi.stubGlobal('fetch', fetch); render(<OfflineSyncPanel client={client()} />); await select(); denied = true;
  fireEvent.click(screen.getByRole('button', { name: '刷新本机同步状态与权限' })); await screen.findByText(/SYNC_MEMBERSHIP_REVOKED/);
  expect(screen.queryByRole('button', { name: '预览此消息内容' })).toBeNull(); expect(screen.queryByRole('button', { name: '保存到本机发件箱' })).toBeNull();
});

it('StrictMode delayed old-scope channel result cannot repopulate another project', async () => {
  let finish: (r: Response) => void = () => {};
  const fetch = backend({ override: (url, init) => url.includes('/other/') && url.endsWith('/records') ? response({ channels: [], outbox: [], inbox: [], network_enabled: false }) : url.endsWith('/channels') && init.method === 'POST' ? new Promise<Response>(resolve => { finish = resolve; }) : undefined });
  vi.stubGlobal('fetch', fetch); const view = render(<StrictMode><OfflineSyncPanel client={client()} /></StrictMode>);
  fireEvent.change(await screen.findByLabelText('交换批次标签'), { target: { value: 'old-scope' } }); fireEvent.change(screen.getByLabelText('本端标签'), { target: { value: 'A' } }); fireEvent.change(screen.getByLabelText('对端标签'), { target: { value: 'B' } });
  fireEvent.click(screen.getByLabelText('同步范围：Selected synthetic chapter · v2')); fireEvent.click(screen.getByRole('button', { name: '保存选定交换范围' }));
  await waitFor(() => expect(fetch.mock.calls.some(([url]) => url.endsWith('/channels'))).toBe(true));
  view.rerender(<StrictMode><OfflineSyncPanel client={client('other')} /></StrictMode>); finish(response({ ...channel(), stream_id: 'old-scope' }));
  await waitFor(() => expect((screen.getByLabelText('交换批次标签') as HTMLInputElement).value).toBe(''));
  expect(screen.queryByRole('button', { name: 'old-scope · A → B' })).toBeNull();
});

it('can discard obsolete conflict choices after source drift without discarding the incoming candidate', async () => {
  let changed = false;
  const fetch = backend({ records: { channels: [channel()], outbox: [], inbox: [row()], network_enabled: false }, override: (url, init) => {
    if (!url.endsWith('/review') || !changed) return undefined;
    const choices = JSON.parse(String(init.body)).choices;
    if (Object.keys(choices).length) return response({ code: 'SYNC_UNKNOWN_OR_STALE_CONFLICT_CHOICE' }, 422);
    return response({ ...plan(), segments: [{ id: 'fresh-conflict', kind: 'CONFLICT', local: 'fresh local', incoming: 'same incoming' }] });
  } });
  vi.stubGlobal('fetch', fetch); render(<OfflineSyncPanel client={client()} />); await select();
  fireEvent.click(screen.getByRole('button', { name: '读取当前三方差异' })); fireEvent.change(await screen.findByLabelText('冲突选择 1'), { target: { value: 'INCOMING' } }); changed = true;
  fireEvent.click(screen.getByRole('button', { name: '读取当前三方差异' })); await screen.findByText(/SYNC_UNKNOWN_OR_STALE_CONFLICT_CHOICE/);
  fireEvent.click(screen.getByRole('button', { name: '清除旧选择并重新读取' })); await screen.findByText(/已丢弃旧选择并读取最新差异/);
  expect((screen.getByLabelText('冲突选择 1') as HTMLSelectElement).value).toBe('');
  expect((screen.getByRole('button', { name: '应用已核对的候选' }) as HTMLButtonElement).disabled).toBe(true);
  const requests = fetch.mock.calls.filter(([url]) => url.endsWith('/review')); expect(JSON.parse(String(requests[requests.length - 1][1].body)).choices).toEqual({});
});


it('withdraws one chapter only after versioned preview, clears cached file and blocks its pending review', async () => {
  const make = vi.fn(() => 'blob:withdrawn'), revoke = vi.fn(); vi.stubGlobal('URL', class extends URL { static createObjectURL = make; static revokeObjectURL = revoke; });
  const fetch = backend({ records: { channels: [channel()], outbox: [{ ...row('PENDING'), chapter_id: 'chapter' }], inbox: [row()], network_enabled: false } });
  vi.stubGlobal('fetch', fetch); render(<OfflineSyncPanel client={client()} />); await select();
  fireEvent.click(screen.getByRole('button', { name: '预览此消息内容' })); await screen.findByRole('button', { name: '生成手动交换文件' });
  fireEvent.click(screen.getByLabelText('我了解导出的本地副本无法远程撤回')); fireEvent.click(screen.getByRole('button', { name: '生成手动交换文件' })); await screen.findByRole('link', { name: '下载本地同步消息' });
  fireEvent.click(screen.getByRole('button', { name: '读取当前三方差异' })); await screen.findByLabelText('冲突选择 1');
  fireEvent.click(screen.getByLabelText('撤回章节：Selected synthetic chapter')); fireEvent.click(screen.getByRole('button', { name: '预览章节范围变更' }));
  const commit = await screen.findByRole('button', { name: '确认章节范围变更' }); expect((commit as HTMLButtonElement).disabled).toBe(true);
  expect(fetch.mock.calls.some(([url]) => url.endsWith('/selection'))).toBe(false);
  fireEvent.click(screen.getByLabelText('已核对新增基线和撤回范围，理解已有副本无法收回')); fireEvent.click(commit);
  await screen.findByText('此批次没有当前已选章节。');
  expect(screen.queryByRole('link', { name: '下载本地同步消息' })).toBeNull(); expect(revoke).toHaveBeenCalledWith('blob:withdrawn');
  expect(screen.queryByRole('button', { name: '应用已核对的候选' })).toBeNull(); expect(screen.queryByLabelText('新增范围：Selected synthetic chapter · v2')).toBeNull();
  expect(screen.getByRole('button', { name: 'batch · A → B' })).toBeTruthy();
  expect(JSON.parse(String(fetch.mock.calls.find(([url]) => url.endsWith('/selection'))![1].body))).toMatchObject({ expected_version: 1, withdraw_chapter_ids: ['chapter'], add_chapter_ids: [], confirmed: true, preview_digest: 'd'.repeat(64) });
  expect(fetch.mock.calls.some(([url]) => url.endsWith('/apply') || url.endsWith('/revoke'))).toBe(false);
});

it('adds only a freshly reviewed baseline and invalidates preview when selection changes', async () => {
  const fetch = backend(); vi.stubGlobal('fetch', fetch); render(<OfflineSyncPanel client={client()} />); await select();
  expect((screen.getByLabelText('新增范围：Unselected synthetic chapter · v1') as HTMLInputElement).checked).toBe(false);
  fireEvent.click(screen.getByLabelText('新增范围：Unselected synthetic chapter · v1')); fireEvent.click(screen.getByRole('button', { name: '预览章节范围变更' }));
  await screen.findByText(/Saved original baseline🙂/); fireEvent.click(screen.getByLabelText('已核对新增基线和撤回范围，理解已有副本无法收回'));
  fireEvent.click(screen.getByLabelText('撤回章节：Selected synthetic chapter')); expect(screen.queryByRole('button', { name: '确认章节范围变更' })).toBeNull();
  fireEvent.click(screen.getByLabelText('撤回章节：Selected synthetic chapter')); fireEvent.click(screen.getByRole('button', { name: '预览章节范围变更' }));
  const commit = await screen.findByRole('button', { name: '确认章节范围变更' }); expect((commit as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(screen.getByLabelText('已核对新增基线和撤回范围，理解已有副本无法收回')); fireEvent.click(commit);
  await screen.findByLabelText('撤回章节：Unselected synthetic chapter');
  expect(JSON.parse(String(fetch.mock.calls.find(([url]) => url.endsWith('/selection'))![1].body))).toMatchObject({ expected_version: 1, add_chapter_ids: ['other'], withdraw_chapter_ids: [], confirmed: true });
  expect(fetch.mock.calls.some(([url]) => url.endsWith('/queue') || url.endsWith('/apply'))).toBe(false);
});

it('preserves pasted input but invalidates cached target and preview when that chapter is withdrawn elsewhere', async () => {
  const records = { channels: [channel()], outbox: [], inbox: [], network_enabled: false as const }; const fetch = backend({ records });
  vi.stubGlobal('fetch', fetch); render(<OfflineSyncPanel client={client()} />); await select();
  const text = JSON.stringify(envelope); fireEvent.change(screen.getByLabelText('收到的同步消息 JSON'), { target: { value: text } });
  fireEvent.change(screen.getByLabelText('收到章节的本机目标'), { target: { value: 'chapter' } }); fireEvent.click(screen.getByRole('button', { name: '预览待接收消息' }));
  await screen.findByRole('button', { name: '接收到待审核收件箱' });
  records.channels[0] = { ...records.channels[0], version: 2, chapter_ids: [], withdrawn_chapter_ids: ['chapter'] };
  fireEvent.click(screen.getByRole('button', { name: '刷新本机同步状态与权限' })); await screen.findByText('此批次没有当前已选章节。');
  expect((screen.getByLabelText('收到的同步消息 JSON') as HTMLTextAreaElement).value).toBe(text);
  expect((screen.getByLabelText('收到章节的本机目标') as HTMLSelectElement).value).toBe('');
  expect(screen.queryByRole('button', { name: '接收到待审核收件箱' })).toBeNull();
  expect(fetch.mock.calls.some(([url]) => url.endsWith('/receive'))).toBe(false);
});
