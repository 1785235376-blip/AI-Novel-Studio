// @vitest-environment jsdom
import { StrictMode } from 'react';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { experimentalClient } from './api';
import { OfflineSyncPanel } from './OfflineSyncPanel';
import { OfflineSyncReceive } from './OfflineSyncReceive';
import { offlineSyncClient, type SyncCatalog, type SyncChannel } from './offlineSyncClient';
import * as fileReader from './offlineSyncFile';

afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });
const channel = (): SyncChannel => ({ id: 'channel', version: 1, status: 'ACTIVE', stream_id: 'batch', endpoint_id: 'A', peer_id: 'B', chapter_ids: ['chapter', 'second'], withdrawn_chapter_ids: [], allow_new_chapters: true, send_cursor: 0, receive_cursor: 0 });
const catalog: SyncCatalog = { chapters: [{ id: 'chapter', title: 'First', version: 1 }, { id: 'second', title: 'Second', version: 1 }], truncated: false, network_enabled: false };
const envelope = { protocol: 'AI_NOVEL_SYNC_1', stream_id: 'batch', message_id: 'synthetic', snapshot: { title: '合成输入🙂é', document: { type: 'doc', content: [] } } };
const original = JSON.stringify({ kept: '原输入🙂' });
const textarea = () => screen.getByLabelText('收到的同步消息 JSON') as HTMLTextAreaElement;
const target = () => screen.getByLabelText('收到章节的本机目标') as HTMLSelectElement;
const choose = (file = new File([JSON.stringify(envelope)], 'exchange.json')) => fireEvent.change(screen.getByLabelText('选择本地同步 JSON 文件'), { target: { files: [file] } });
const paste = (text = original) => fireEvent.change(textarea(), { target: { value: text } });
const pickTarget = (id = 'chapter') => fireEvent.change(target(), { target: { value: id } });
function setup() {
  const api = offlineSyncClient(experimentalClient('project', { sessionToken: 'synthetic-host' }));
  const receive = vi.spyOn(api, 'receive').mockResolvedValue({ id: 'saved', channel_id: 'channel', version: 1, status: 'PENDING_REVIEW', sequence: 1, operation: 'SNAPSHOT', source_version: 1, envelope_digest: '', receipt: { message_id: 'synthetic' }, duplicate: false });
  const apply = vi.spyOn(api, 'apply');
  const props = { api, channel: channel(), catalog, blocked: false, reload: vi.fn() };
  const view = render(<StrictMode><OfflineSyncReceive {...props} /></StrictMode>);
  return { ...view, props, receive, apply };
}
function deferredRead() {
  const calls: { signal?: AbortSignal; resolve: (text: string) => void; reject: (error: unknown) => void }[] = [];
  vi.spyOn(fileReader, 'readOfflineSyncFile').mockImplementation((_file, signal) => new Promise((resolve, reject) => { calls.push({ signal, resolve, reject }); }));
  return calls;
}
function retained(element: HTMLElement, name = 'onClick') {
  const key = Object.keys(element).find(value => value.startsWith('__reactProps'))!;
  return (element as unknown as Record<string, Record<string, (event?: { target: { value: string } }) => void>>)[key][name];
}

it('loads into the same editable text, requires explicit preview and receive, and never auto applies', async () => {
  const { receive, apply } = setup(); paste(); pickTarget(); choose();
  await screen.findByText(/本地文件已载入文本框/);
  expect(textarea().value).toBe(JSON.stringify(envelope));
  expect(screen.queryByText('待接收信封预览')).toBeNull(); expect(receive).not.toHaveBeenCalled();
  const edited = JSON.stringify({ ...envelope, note: 'manual edit' }); paste(edited);
  fireEvent.click(screen.getByRole('button', { name: '预览待接收消息' }));
  expect(receive).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: '接收到待审核收件箱' }));
  await screen.findByText(/候选已保存至本机收件箱/);
  expect(receive).toHaveBeenCalledTimes(1);
  expect(receive).toHaveBeenCalledWith(expect.objectContaining({ id: 'channel', version: 1 }), JSON.parse(edited), 'chapter', false);
  expect(apply).not.toHaveBeenCalled(); expect(textarea().value).toBe(edited);
});

it('preserves the original API, project route, authorization header and version check', async () => {
  const response = (value: unknown) => new Response(JSON.stringify(value), { status: 200, headers: { 'Content-Type': 'application/json' } });
  const fetch = vi.fn(async (url: string, init: RequestInit) => {
    if (url.endsWith('/catalog')) return response(catalog);
    if (url.endsWith('/records')) return response({ channels: [channel()], outbox: [], inbox: [], network_enabled: false });
    if (url.endsWith('/receive')) return response({ receipt: { message_id: 'synthetic' }, duplicate: false });
    throw new Error('Unexpected request ' + init.method);
  });
  vi.stubGlobal('fetch', fetch);
  render(<OfflineSyncPanel client={experimentalClient('original-project', { sessionToken: 'synthetic-session' })} />);
  fireEvent.click(await screen.findByRole('button', { name: 'batch · A → B' })); choose();
  await screen.findByText(/本地文件已载入文本框/);
  expect(fetch.mock.calls.every(([, init]) => init.method === 'GET')).toBe(true);
  pickTarget('__NEW__'); fireEvent.click(screen.getByRole('button', { name: '预览待接收消息' }));
  expect(fetch.mock.calls.every(([, init]) => init.method === 'GET')).toBe(true);
  fireEvent.click(screen.getByRole('button', { name: '接收到待审核收件箱' }));
  await screen.findByLabelText('可复制给发送端的接收回执');
  const call = fetch.mock.calls.find(([url]) => url.endsWith('/receive'))!;
  expect(call[0]).toBe('/api/novels/original-project/experimental/offline-sync/channels/channel/receive');
  expect(new Headers(call[1].headers).get('X-Session-Token')).toBe('synthetic-session');
  expect(JSON.parse(String(call[1].body))).toEqual({ expected_version: 1, envelope, target_chapter_id: null, create_new: true });
  expect(fetch.mock.calls.filter(([, init]) => init.method !== 'GET')).toHaveLength(1);
});

it.each([
  ['malformed JSON', new File(['{"private":"secret",broken}'], 'invalid.json'), /有效的 JSON/],
  ['invalid UTF-8', new File([new Uint8Array([0xff])], 'invalid.json'), /UTF-8 文本/],
  ['oversized bytes', new File([new Uint8Array(fileReader.MAX_OFFLINE_SYNC_BYTES + 1)], 'large.json'), /512 KiB，请选择/],
] as const)('keeps prior input and clears obsolete preview after a %s file', async (_label, file, message) => {
  const { receive } = setup(); paste(); pickTarget(); fireEvent.click(screen.getByRole('button', { name: '预览待接收消息' }));
  expect(screen.getByText('待接收信封预览')).toBeTruthy(); choose(file);
  await screen.findByRole('alert'); expect(screen.getByRole('alert').textContent).toMatch(message);
  expect(screen.getByRole('alert').textContent).not.toContain('secret');
  expect(textarea().value).toBe(original); expect(target().value).toBe('chapter');
  expect(screen.queryByText('待接收信封预览')).toBeNull(); expect(receive).not.toHaveBeenCalled();
});

it('preserves input after native abort and permits selecting the same file again', async () => {
  const calls = deferredRead(); setup(); paste(); const file = new File(['{}'], 'same.json'); choose(file);
  await act(async () => { calls[0].reject(new DOMException('abort', 'AbortError')); });
  expect(screen.getByText('文件读取已取消，原输入已保留。')).toBeTruthy(); expect(textarea().value).toBe(original);
  expect((screen.getByLabelText('选择本地同步 JSON 文件') as HTMLInputElement).value).toBe('');
  choose(file); await act(async () => { calls[1].resolve('{}'); }); expect(textarea().value).toBe('{}');
});

it('a newer file wins even when the old reader ignores abort and settles later', async () => {
  const calls = deferredRead(); const { receive } = setup(); paste(); choose(); choose(new File(['{"newer":true}'], 'newer.json'));
  expect(calls[0].signal?.aborted).toBe(true);
  await act(async () => { calls[1].resolve('{"newer":true}'); });
  await act(async () => { calls[0].resolve('{"late":true}'); });
  expect(textarea().value).toBe('{"newer":true}'); expect(receive).not.toHaveBeenCalled();
});

it('a stale file failure cannot overwrite the newer success notice', async () => {
  const calls = deferredRead(); setup(); choose(); choose();
  await act(async () => { calls[1].resolve('{}'); calls[0].reject(new Error('old error')); });
  expect(screen.getByText(/本地文件已载入文本框/)).toBeTruthy(); expect(screen.queryByRole('alert')).toBeNull();
});

it.each(['manual edit', 'target change', 'empty selection', 'explicit cancel'] as const)('invalidates a pending local read on %s without losing prior input', async change => {
  const calls = deferredRead(); const { receive } = setup(); paste(); pickTarget(); choose();
  expect((screen.getByRole('button', { name: '预览待接收消息' }) as HTMLButtonElement).disabled).toBe(true);
  if (change === 'manual edit') paste('{"manual":"new"}');
  if (change === 'target change') pickTarget('second');
  if (change === 'empty selection') fireEvent.change(screen.getByLabelText('选择本地同步 JSON 文件'), { target: { files: [] } });
  if (change === 'explicit cancel') fireEvent.click(screen.getByRole('button', { name: '取消文件读取' }));
  expect(calls[0].signal?.aborted).toBe(true);
  await act(async () => { calls[0].resolve('{"late":true}'); });
  expect(textarea().value).toBe(change === 'manual edit' ? '{"manual":"new"}' : original);
  expect(screen.queryByText(/本地文件已载入文本框/)).toBeNull(); expect(receive).not.toHaveBeenCalled();
});

it.each(['channel version', 'channel identity', 'selection withdrawal', 'new target revoked', 'channel revoked', 'permission blocked', 'client changed'] as const)('rejects late reads and invalidates preview after %s', async change => {
  const calls = deferredRead(); const { props, rerender, receive } = setup(); paste(); pickTarget(change === 'new target revoked' ? '__NEW__' : 'chapter');
  fireEvent.click(screen.getByRole('button', { name: '预览待接收消息' })); choose();
  const next = { ...props, channel: { ...props.channel } };
  if (change === 'channel version') next.channel.version++;
  if (change === 'channel identity') next.channel.id = 'other-channel';
  if (change === 'selection withdrawal') { next.channel.chapter_ids = ['second']; next.channel.withdrawn_chapter_ids = ['chapter']; }
  if (change === 'new target revoked') next.channel.allow_new_chapters = false;
  if (change === 'channel revoked') next.channel.status = 'REVOKED';
  if (change === 'permission blocked') next.blocked = true;
  if (change === 'client changed') next.api = offlineSyncClient(experimentalClient('other-project', { sessionToken: 'new-session' }));
  rerender(<StrictMode><OfflineSyncReceive {...next} /></StrictMode>);
  expect(calls[0].signal?.aborted).toBe(true);
  await act(async () => { calls[0].resolve('{"late":true}'); });
  expect(textarea().value).toBe(original); expect(screen.queryByText('待接收信封预览')).toBeNull();
  expect(screen.queryByText(/本地文件已载入文本框/)).toBeNull(); expect(receive).not.toHaveBeenCalled();
  if (change === 'selection withdrawal' || change === 'new target revoked') expect(target().value).toBe('');
  if (change === 'permission blocked' || change === 'channel revoked') expect((screen.getByLabelText('选择本地同步 JSON 文件') as HTMLInputElement).disabled).toBe(true);
});

it('does not revive an old read after a transient permission block clears', async () => {
  const calls = deferredRead(); const { props, rerender } = setup(); paste(); choose();
  rerender(<StrictMode><OfflineSyncReceive {...props} blocked /></StrictMode>);
  rerender(<StrictMode><OfflineSyncReceive {...props} /></StrictMode>);
  await act(async () => { calls[0].resolve('{"late":true}'); }); expect(textarea().value).toBe(original);
});

it('aborts on unmount and ignores a late result across a new mounted scope', async () => {
  const calls = deferredRead(); const first = setup(); paste(); choose(); first.unmount();
  expect(calls[0].signal?.aborted).toBe(true);
  setup(); paste('{"newScope":true}');
  await act(async () => { calls[0].resolve('{"late":true}'); }); expect(textarea().value).toBe('{"newScope":true}');
});

it('invalidates an existing preview on version changes while preserving editable input', async () => {
  const { props, rerender, receive } = setup(); paste(); pickTarget(); fireEvent.click(screen.getByRole('button', { name: '预览待接收消息' }));
  rerender(<StrictMode><OfflineSyncReceive {...props} channel={{ ...props.channel, version: 2 }} /></StrictMode>);
  expect(textarea().value).toBe(original); expect(screen.queryByText('待接收信封预览')).toBeNull(); expect(receive).not.toHaveBeenCalled();
});

it('keeps manual paste and safe byte-limit validation available without choosing a file', async () => {
  const { receive } = setup(); pickTarget(); paste(JSON.stringify('中'.repeat(Math.floor(fileReader.MAX_OFFLINE_SYNC_BYTES / 3) + 1)));
  fireEvent.click(screen.getByRole('button', { name: '预览待接收消息' })); expect(screen.getByRole('alert').textContent).toMatch(/512 KiB/);
  paste('{broken private content'); fireEvent.click(screen.getByRole('button', { name: '预览待接收消息' }));
  expect(screen.getByRole('alert').textContent).toMatch(/有效的 JSON/); expect(screen.getByRole('alert').textContent).not.toContain('private');
  expect(textarea().value).toBe('{broken private content'); expect(receive).not.toHaveBeenCalled();
  paste(); fireEvent.click(screen.getByRole('button', { name: '预览待接收消息' }));
  await waitFor(() => expect(screen.getByRole('button', { name: '接收到待审核收件箱' })).toBeTruthy());
});

it.each(['text', 'target'] as const)('fences retained preview and receive callbacks in the same batch as a %s edit', change => {
  const { receive } = setup(); paste(); pickTarget();
  const oldPreview = retained(screen.getByRole('button', { name: '预览待接收消息' }));
  fireEvent.click(screen.getByRole('button', { name: '预览待接收消息' }));
  const oldReceive = retained(screen.getByRole('button', { name: '接收到待审核收件箱' }));
  const edit = retained(change === 'text' ? textarea() : target(), 'onChange');
  act(() => { edit({ target: { value: change === 'text' ? '{"new":true}' : 'second' } }); oldPreview(); oldReceive(); });
  expect(receive).not.toHaveBeenCalled(); expect(screen.queryByText('待接收信封预览')).toBeNull();
});

it.each(['text', 'target', 'scope', 'version', 'permission', 'client', 'revocation', 'selection'] as const)('retained callbacks cannot survive %s A-to-B-to-A', change => {
  const { props, rerender, receive } = setup(); paste(); pickTarget();
  const oldPreview = retained(screen.getByRole('button', { name: '预览待接收消息' }));
  fireEvent.click(screen.getByRole('button', { name: '预览待接收消息' }));
  const oldReceive = retained(screen.getByRole('button', { name: '接收到待审核收件箱' }));
  if (change === 'text') { paste('{"other":true}'); paste(); }
  else if (change === 'target') { pickTarget('second'); pickTarget(); }
  else {
    const next = { ...props, channel: { ...props.channel } };
    if (change === 'scope') next.channel.id = 'other';
    if (change === 'version') next.channel.version = 2;
    if (change === 'permission') next.blocked = true;
    if (change === 'client') next.api = offlineSyncClient(experimentalClient('other-project', { sessionToken: 'other-session' }));
    if (change === 'revocation') next.channel.status = 'REVOKED';
    if (change === 'selection') { next.channel.chapter_ids = ['second']; next.channel.withdrawn_chapter_ids = ['chapter']; }
    rerender(<StrictMode><OfflineSyncReceive {...next} /></StrictMode>);
    rerender(<StrictMode><OfflineSyncReceive {...props} /></StrictMode>);
    if (change === 'selection') pickTarget();
  }
  act(() => { oldPreview(); oldReceive(); });
  expect(receive).not.toHaveBeenCalled(); expect(screen.queryByText('待接收信封预览')).toBeNull();
  expect(textarea().value).toBe(original);
});

it('requires the live preview identity even when text and target have not changed', () => {
  const { receive } = setup(); paste(); pickTarget();
  fireEvent.click(screen.getByRole('button', { name: '预览待接收消息' }));
  const oldReceive = retained(screen.getByRole('button', { name: '接收到待审核收件箱' }));
  fireEvent.click(screen.getByRole('button', { name: '预览待接收消息' }));
  act(() => { oldReceive(); }); expect(receive).not.toHaveBeenCalled();
});

it('consumes the candidate synchronously and rejects repeated callbacks after the request settles', async () => {
  const { receive } = setup(); paste(); pickTarget();
  const oldPreview = retained(screen.getByRole('button', { name: '预览待接收消息' }));
  fireEvent.click(screen.getByRole('button', { name: '预览待接收消息' }));
  const oldReceive = retained(screen.getByRole('button', { name: '接收到待审核收件箱' }));
  await act(async () => { oldReceive(); oldReceive(); oldPreview(); });
  expect(receive).toHaveBeenCalledTimes(1); expect(screen.queryByText('待接收信封预览')).toBeNull();
  act(() => { oldReceive(); oldPreview(); }); expect(receive).toHaveBeenCalledTimes(1);
  expect(textarea().value).toBe(original);
});

it('keeps the candidate text after an unknown receive and permits only a new explicit preview/retry', async () => {
  const { receive, apply } = setup(); receive.mockRejectedValueOnce(new Error('UNKNOWN'));
  paste(); pickTarget(); fireEvent.click(screen.getByRole('button', { name: '预览待接收消息' }));
  const oldReceive = retained(screen.getByRole('button', { name: '接收到待审核收件箱' }));
  await act(async () => { oldReceive(); }); await screen.findByRole('alert');
  expect(textarea().value).toBe(original); expect(screen.queryByText('待接收信封预览')).toBeNull();
  act(() => { oldReceive(); }); expect(receive).toHaveBeenCalledTimes(1);
  fireEvent.click(screen.getByRole('button', { name: '预览待接收消息' }));
  fireEvent.click(screen.getByRole('button', { name: '接收到待审核收件箱' }));
  await screen.findByText(/候选已保存至本机收件箱/);
  expect(receive).toHaveBeenCalledTimes(2);
  expect(receive.mock.calls[0]).toEqual(receive.mock.calls[1]); expect(apply).not.toHaveBeenCalled();
});

it('retained preview and receive callbacks cannot act after unmount', () => {
  const { receive, unmount } = setup(); paste(); pickTarget();
  const oldPreview = retained(screen.getByRole('button', { name: '预览待接收消息' }));
  fireEvent.click(screen.getByRole('button', { name: '预览待接收消息' }));
  const oldReceive = retained(screen.getByRole('button', { name: '接收到待审核收件箱' }));
  unmount(); act(() => { oldPreview(); oldReceive(); }); expect(receive).not.toHaveBeenCalled();
});
