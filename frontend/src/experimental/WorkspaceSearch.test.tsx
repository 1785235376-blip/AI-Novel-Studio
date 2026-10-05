// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { WorkspaceToolsPanel } from './WorkspaceToolsPanel';
import { experimentalClient } from './api';
const response = (data: unknown, status = 200) => new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } });
const row = { kind: 'chapter', id: 'other:1', novel_id: 'other', branch_id: null, title: '灯塔来源', version: 2, revision: 'a'.repeat(64), feature: 'editor', offset: 2, snippet: '可读合成正文', aliases: [] };
const result = { items: [row], mode: 'LITERAL_LEXICAL', match_count: 1, next_offset: null, truncated: false, index_truncated: false, suggestions: ['灯塔来源'], updated_documents: 1, branch_sources_available: true };
function setup(extra?: (url: string, init?: RequestInit) => Promise<Response> | Response | undefined) {
  const fetch = vi.fn(async (url: string, init?: RequestInit) => extra?.(url, init) || response(url.endsWith('/resume') ? { item: null, availability: 'EMPTY' } : url.includes('/search?') || url.endsWith('/search/rebuild') ? result : {}));
  vi.stubGlobal('fetch', fetch);
  const client = experimentalClient('origin', { sessionToken: 'synthetic-session' });
  const navigate = vi.fn();
  const view = render(<WorkspaceToolsPanel client={client} initialSection="search" onNavigate={navigate} />);
  return { fetch, navigate, view };
}
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

it('sends scoped filters, pages and a safe rebuild through the captured client', async () => {
  const { fetch } = setup(url => url.includes('/search?') ? response({ ...result, next_offset: 50, match_count: 80 }) : undefined);
  await screen.findByText('灯塔来源', { selector: 'h3' });
  fireEvent.change(screen.getByLabelText('搜索范围'), { target: { value: 'authorized' } });
  fireEvent.change(screen.getByLabelText('标签（精确匹配）'), { target: { value: '主角' } });
  fireEvent.change(screen.getByLabelText('最近修改'), { target: { value: '7' } });
  fireEvent.click(screen.getByLabelText('只看未解决'));
  fireEvent.click(screen.getByLabelText('只匹配正文'));
  await waitFor(() => expect(fetch.mock.calls.some(([url]) => url.includes('scope=authorized') && url.includes('tag=%E4%B8%BB%E8%A7%92') && url.includes('unresolved=true') && url.includes('fulltext=true'))).toBe(true));
  await screen.findByText('灯塔来源', { selector: 'h3' });
  fireEvent.click(screen.getByRole('button', { name: '下一页' }));
  await waitFor(() => expect(fetch.mock.calls.some(([url]) => url.includes('offset=50'))).toBe(true));
  await screen.findByText('灯塔来源', { selector: 'h3' });
  fireEvent.click(screen.getByRole('button', { name: '重建索引' }));
  await waitFor(() => expect(fetch.mock.calls.some(([url]) => url.endsWith('/search/rebuild'))).toBe(true));
  const call = fetch.mock.calls.find(([url]) => url.endsWith('/search/rebuild'))!;
  expect(JSON.parse(String(call[1]?.body))).toMatchObject({ scope: 'authorized', tag: '主角', recent_days: 7, unresolved: true, fulltext: true });
  expect((call[1]?.headers as Record<string, string>)['X-Session-Token']).toBe('synthetic-session');
});

it('cancels server work, drops late bodies/counts/suggestions, and permits retry', async () => {
  let finish: (r: Response) => void = () => {}; let count = 0;
  const { fetch } = setup(url => url.includes('/search?') && count++ === 0 ? new Promise<Response>(resolve => { finish = resolve; }) : undefined);
  await waitFor(() => expect(fetch.mock.calls.some(([url]) => url.includes('/search?'))).toBe(true));
  const call = fetch.mock.calls.find(([url]) => url.includes('/search?'))!;
  const requestId = new URL(call[0], 'http://test').searchParams.get('request_id');
  fireEvent.click(screen.getByRole('button', { name: '取消搜索' }));
  await screen.findByText('搜索已取消；不会展示迟到的结果。可重新搜索。');
  expect(call[1]?.signal?.aborted).toBe(true);
  expect(JSON.parse(String(fetch.mock.calls.find(([url]) => url.endsWith('/search/cancel'))![1]?.body))).toEqual({ request_id: requestId });
  await act(async () => finish(response(result)));
  expect(screen.queryByText('灯塔来源')).toBeNull(); expect(screen.queryByText(/当前可读匹配/)).toBeNull();
  fireEvent.click(screen.getByRole('button', { name: '刷新来源' }));
  await screen.findByText('灯塔来源', { selector: 'h3' });
});

it('withholds source text and autocomplete after a revoked refresh or resolve', async () => {
  let denied = false;
  const { navigate } = setup(url => denied && (url.includes('/search?') || url.endsWith('/search/resolve')) ? response({ detail: { code: 'FORBIDDEN' } }, 403) : undefined);
  await screen.findByText('灯塔来源', { selector: 'h3' });
  denied = true;
  fireEvent.click(screen.getByRole('button', { name: '打开章节位置' }));
  await screen.findByRole('alert');
  expect(screen.queryByText('灯塔来源')).toBeNull(); expect(navigate).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: '刷新来源' }));
  await waitFor(() => expect(screen.getAllByRole('alert').length).toBeGreaterThan(0));
  expect(screen.queryByText('可读合成正文')).toBeNull();
  expect(document.querySelector('datalist option')).toBeNull();
});

it('does not search unfinished IME composition and submits the completed Chinese text', async () => {
  const { fetch } = setup(); await screen.findByText('灯塔来源', { selector: 'h3' });
  const initial = fetch.mock.calls.filter(([url]) => url.includes('/search?')).length;
  const input = screen.getByLabelText('搜索中文名称、别名或正文');
  fireEvent.compositionStart(input); fireEvent.change(input, { target: { value: 'deng' } });
  await act(async () => { await new Promise(resolve => setTimeout(resolve, 220)); });
  expect(fetch.mock.calls.filter(([url]) => url.includes('/search?'))).toHaveLength(initial);
  expect(screen.queryByText('灯塔来源')).toBeNull();
  fireEvent.change(input, { target: { value: '灯塔' } }); fireEvent.compositionEnd(input);
  await waitFor(() => expect(fetch.mock.calls.some(([url]) => url.includes('q=%E7%81%AF%E5%A1%94'))).toBe(true));
});

it('invalidates a pending cross-project source jump on filter change', async () => {
  let finish: (r: Response) => void = () => {};
  const { navigate } = setup(url => url.endsWith('/search/resolve') ? new Promise<Response>(resolve => { finish = resolve; }) : undefined);
  await screen.findByText('灯塔来源', { selector: 'h3' });
  fireEvent.click(screen.getByRole('button', { name: '打开章节位置' }));
  fireEvent.change(screen.getByLabelText('搜索范围'), { target: { value: 'authorized' } });
  await act(async () => finish(response({ kind: 'chapter', id: row.id, novel_id: row.novel_id, version: 2 })));
  expect(navigate).not.toHaveBeenCalled();
});

it('revalidates the exact cross-project source identity and provides an abortable jump', async () => {
  const { fetch, navigate } = setup(url => url.endsWith('/search/resolve') ? response({ kind: 'chapter', id: row.id, novel_id: row.novel_id, branch_id: null, version: 2 }) : undefined);
  await screen.findByText('灯塔来源', { selector: 'h3' });
  fireEvent.click(screen.getByRole('button', { name: '打开章节位置' }));
  await waitFor(() => expect(navigate).toHaveBeenCalledWith(expect.objectContaining({ id: row.id, novel_id: 'other', signal: expect.any(AbortSignal) })));
  const body = JSON.parse(String(fetch.mock.calls.find(([url]) => url.endsWith('/search/resolve'))![1]?.body));
  expect(body).toMatchObject({ novel_id: 'other', branch_id: null, id: row.id, revision: row.revision });
});
