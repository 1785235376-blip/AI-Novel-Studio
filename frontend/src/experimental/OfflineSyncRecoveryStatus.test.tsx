// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { experimentalClient } from './api';
import { OfflineSyncPanel } from './OfflineSyncPanel';
import { OfflineSyncRecoveryStatus } from './OfflineSyncRecoveryStatus';
import type { SyncRecovery, SyncRow } from './offlineSyncClient';

afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });
const row = (): SyncRow => ({ id: 'message', channel_id: 'channel', version: 1, status: 'UNKNOWN', sequence: 1,
  operation: 'SNAPSHOT', target_chapter_id: 'chapter', source_version: 2, envelope_digest: 'a'.repeat(64) });
const recovery = (state = 'MATCHES_INTENT_UNCONFIRMED'): SyncRecovery => ({ id: 'message', version: 1, status: 'UNKNOWN',
  observations: [{ chapter_id: 'chapter', version: 7, state, document: 'CURRENT_BODY_NOT_PRESENTED' }], can_adopt: true,
  retry_allowed: false, preview_digest: 'd'.repeat(64) });
const matchLabel = '当前内容符合预期，但不能证明本次写入已经执行（也可能原本相同）';

it.each([
  ['CHECKPOINT_UNCHANGED', '原检查点仍在'],
  ['MATCHES_INTENT_UNCONFIRMED', matchLabel],
  ['DIVERGED_OR_PARTIAL', '当前状态已分歧或只完成了一部分'],
])('renders original %s with only the authorized current version', (state, label) => {
  render(<OfflineSyncRecoveryStatus row={row()} recovery={recovery(state)} />);
  expect(screen.getByText(label)).toBeTruthy(); expect(screen.getByText('当前章节 chapter · v7')).toBeTruthy();
  expect(screen.queryByText('CURRENT_BODY_NOT_PRESENTED')).toBeNull();
});

it('keeps a possible no-op inconclusive without inventing a both-match observation', () => {
  render(<OfflineSyncRecoveryStatus row={row()} recovery={recovery()} />);
  expect(screen.getByText(matchLabel)).toBeTruthy();
  expect(screen.getByText(/未另行区分它是否也与检查点一致/)).toBeTruthy();
  expect(screen.queryByText('原检查点仍在')).toBeNull();
});

it.each(['unavailable', 'different-target', 'future-state', 'old-row', 'other-message'])('keeps %s generic', mode => {
  const result = recovery();
  if (mode === 'unavailable') result.observations = [];
  if (mode === 'different-target') result.observations[0].chapter_id = 'unrelated';
  if (mode === 'future-state') result.observations[0].state = 'UNRECOGNIZED';
  if (mode === 'old-row') result.version = 2;
  if (mode === 'other-message') result.id = 'other';
  render(<OfflineSyncRecoveryStatus row={row()} recovery={result} />);
  expect(screen.getByText(/目前无法核实/)).toBeTruthy(); expect(screen.queryByText(/当前章节/)).toBeNull();
});

it.each(['row-withdrawn', 'recovery-withdrawn', 'already-selected'])('does not present a comparison for %s', mode => {
  const input = row(), result = recovery();
  if (mode === 'row-withdrawn') input.selection_withdrawn = true;
  if (mode === 'recovery-withdrawn') result.selection_withdrawn = true;
  if (mode === 'already-selected') result.target_already_selected = true;
  render(<OfflineSyncRecoveryStatus row={input} recovery={result} />);
  expect(screen.getByText(/目前无法核实/)).toBeTruthy(); expect(screen.queryByText(matchLabel)).toBeNull();
  expect(screen.queryByText(/当前章节/)).toBeNull();
});

it.each([false, true])('keeps unknown create unbound with readable candidate=%s', candidate => {
  const input = row(); delete input.target_chapter_id; const result = recovery(); if (!candidate) result.observations = [];
  render(<OfflineSyncRecoveryStatus row={input} recovery={result} />);
  expect(screen.getByText(/新增请求尚未绑定原章节，写入结果仍未知/)).toBeTruthy();
  expect(screen.queryByText(matchLabel)).toBeNull();
  expect(!!screen.queryByText('当前可读候选 chapter · v7')).toBe(candidate);
});

it('never reads or renders bodies, hidden snapshots, titles or fingerprints', () => {
  const result = recovery();
  for (const key of ['checkpoint', 'intent', 'title', 'digest', 'length']) Object.defineProperty(result, key, { get() { throw new Error('private field read'); } });
  Object.defineProperty(result.observations[0], 'document', { get() { throw new Error('body read'); } });
  render(<OfflineSyncRecoveryStatus row={row()} recovery={result} />);
  expect(screen.getByText(matchLabel)).toBeTruthy(); expect(screen.queryByText('d'.repeat(64))).toBeNull();
});

function mounted(result: SyncRecovery, input = row()) {
  const channel = { id: 'channel', version: 1, status: 'ACTIVE', stream_id: 'batch', endpoint_id: 'A', peer_id: 'B',
    chapter_ids: ['chapter'], allow_new_chapters: true, send_cursor: 0, receive_cursor: 0 };
  const response = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status, headers: { 'Content-Type': 'application/json' } });
  const fetch = vi.fn(async (url: string, init: RequestInit) => {
    if (url.endsWith('/catalog')) return response({ chapters: [{ id: 'chapter', title: 'Visible current title', version: 7 }], truncated: false, network_enabled: false });
    if (url.endsWith('/records')) return response({ channels: [channel], outbox: [], inbox: [input], network_enabled: false });
    if (url.endsWith('/recovery')) return response(result);
    throw new Error('Unexpected request: ' + url);
  });
  vi.stubGlobal('fetch', fetch);
  return { fetch, ...render(<OfflineSyncPanel client={experimentalClient('project', { sessionToken: 'synthetic-host' })} />) };
}
async function inspect() {
  fireEvent.click(await screen.findByRole('button', { name: 'batch · A → B' }));
  fireEvent.click(screen.getByRole('button', { name: '核对未知写入结果' }));
  return screen.findByRole('region', { name: '未知写入状态比较' });
}

it.each(['adopt', 'close'] as const)('mounted %s keeps the exact original request and digest', async action => {
  const result = recovery(action === 'adopt' ? 'MATCHES_INTENT_UNCONFIRMED' : 'DIVERGED_OR_PARTIAL'); result.can_adopt = action === 'adopt';
  const state = mounted(result); await inspect();
  expect(state.fetch.mock.calls.filter(([, init]) => init.method === 'POST')).toHaveLength(1);
  const adopt = screen.getByRole('button', { name: '确认采用完全匹配的已有结果' });
  expect((adopt as HTMLButtonElement).disabled).toBe(!result.can_adopt);
  fireEvent.click(action === 'adopt' ? adopt : screen.getByRole('button', { name: '保留所有候选并关闭此未知记录' }));
  await waitFor(() => expect(state.fetch.mock.calls.filter(([url]) => url.endsWith('/recovery'))).toHaveLength(2));
  const calls = state.fetch.mock.calls.filter(([url]) => url.endsWith('/recovery'));
  expect(JSON.parse(String(calls[1][1].body))).toEqual({ expected_version: 1, adopt_matching_result: action === 'adopt',
    close_without_replay: action === 'close', preview_digest: result.preview_digest });
  expect(state.fetch.mock.calls.every(([url, init]) => init.method === 'GET' || url.endsWith('/recovery'))).toBe(true);
  expect(screen.queryByText('CURRENT_BODY_NOT_PRESENTED')).toBeNull();
});

it('mounted unknown create remains uncertain while server can_adopt stays authoritative', async () => {
  const input = row(); delete input.target_chapter_id; mounted(recovery(), input); await inspect();
  expect(screen.getByText(/新增请求尚未绑定原章节，写入结果仍未知/)).toBeTruthy();
  expect((screen.getByRole('button', { name: '确认采用完全匹配的已有结果' }) as HTMLButtonElement).disabled).toBe(false);
});

it('a late recovery response cannot populate a newly selected project', async () => {
  const state = mounted(recovery());
  const original = state.fetch.getMockImplementation()!; let finish!: (response: Response) => void;
  state.fetch.mockImplementation((url, init) => url.endsWith('/recovery') ? new Promise(resolve => { finish = resolve; }) : original(url, init));
  fireEvent.click(await screen.findByRole('button', { name: 'batch · A → B' }));
  fireEvent.click(screen.getByRole('button', { name: '核对未知写入结果' }));
  state.rerender(<OfflineSyncPanel client={experimentalClient('other-project', { sessionToken: 'different-host' })} />);
  await act(async () => finish(new Response(JSON.stringify(recovery()), { status: 200 })));
  expect(screen.queryByRole('region', { name: '未知写入状态比较' })).toBeNull();
});

it.each([401, 403])('retires prior recovery and actions when an explicit reread returns %s', async status => {
  const state = mounted(recovery()); await inspect();
  const original = state.fetch.getMockImplementation()!;
  state.fetch.mockImplementation((url, init) => url.endsWith('/recovery')
    ? Promise.resolve(new Response(JSON.stringify({ code: 'REREAD_DENIED' }), { status })) : original(url, init));
  fireEvent.click(screen.getByRole('button', { name: '核对未知写入结果' }));
  await screen.findByText(/REREAD_DENIED/);
  expect(screen.queryByRole('region', { name: '未知写入状态比较' })).toBeNull();
  expect(screen.queryByRole('button', { name: '确认采用完全匹配的已有结果' })).toBeNull();
  expect(screen.queryByRole('button', { name: '保留所有候选并关闭此未知记录' })).toBeNull();
});

it('retires the prior observation as soon as a new check starts', async () => {
  const state = mounted(recovery()); await inspect(); const original = state.fetch.getMockImplementation()!;
  let finish!: (response: Response) => void;
  state.fetch.mockImplementation((url, init) => url.endsWith('/recovery') ? new Promise(resolve => { finish = resolve; }) : original(url, init));
  fireEvent.click(screen.getByRole('button', { name: '核对未知写入结果' }));
  expect(screen.queryByRole('region', { name: '未知写入状态比较' })).toBeNull();
  expect(screen.queryByRole('button', { name: '确认采用完全匹配的已有结果' })).toBeNull();
  await act(async () => finish(new Response(JSON.stringify({ code: 'REREAD_FAILED' }), { status: 503 })));
  await screen.findByText(/REREAD_FAILED/);
  expect(screen.queryByRole('button', { name: '保留所有候选并关闭此未知记录' })).toBeNull();
});

it.each(['id', 'version'] as const)('does not install a response for another record %s', async field => {
  const result = recovery(); if (field === 'id') result.id = 'other'; else result.version = 2;
  mounted(result);
  fireEvent.click(await screen.findByRole('button', { name: 'batch · A → B' }));
  fireEvent.click(screen.getByRole('button', { name: '核对未知写入结果' }));
  await screen.findByText(/已读取原章节实际状态/);
  expect(screen.queryByRole('region', { name: '未知写入状态比较' })).toBeNull();
  expect(screen.queryByRole('button', { name: '确认采用完全匹配的已有结果' })).toBeNull();
});

it('retires a late recovery after the selected record changes or is withdrawn', async () => {
  const input = row(), state = mounted(recovery(), input), original = state.fetch.getMockImplementation()!;
  let finish!: (response: Response) => void;
  state.fetch.mockImplementation((url, init) => url.endsWith('/recovery') ? new Promise(resolve => { finish = resolve; }) : original(url, init));
  fireEvent.click(await screen.findByRole('button', { name: 'batch · A → B' }));
  fireEvent.click(screen.getByRole('button', { name: '核对未知写入结果' }));
  input.version = 2; input.selection_withdrawn = true;
  fireEvent.click(screen.getByRole('button', { name: '刷新本机同步状态与权限' }));
  await screen.findByText(/此章节已撤回，历史候选和未知结果保留/);
  await act(async () => finish(new Response(JSON.stringify(recovery()), { status: 200 })));
  expect(screen.queryByRole('region', { name: '未知写入状态比较' })).toBeNull();
  expect(screen.queryByRole('button', { name: '确认采用完全匹配的已有结果' })).toBeNull();
});
