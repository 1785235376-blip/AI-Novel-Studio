// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { ResearchLibraryPanel } from './ResearchLibraryPanel';
import { experimentalClient } from './api';
const ref = { source_id: 'source', source_version: 2, paragraph: 22, quote_sha256: 'a'.repeat(64) };
const source = { id: 'source', version: 2, title: 'Synthetic source', author: '', source: '', source_version: 'edition', usage_notes: '', access: 'PROJECT', format: 'TXT', origin: 'LOCAL_IMPORT', filename: 's.txt', accessed_at: '', extraction_status: 'TEXT_EXTRACTED', paragraph_count: 45, warnings: [], paragraphs: Array.from({ length: 45 }, (_, i) => ({ paragraph: i + 1, page: 3, text: '🌊e\u0301 duplicate', citation: { ...ref, paragraph: i + 1 } })) };
const evidence = { citation: ref, title: source.title, author: '', source: '', paragraph: 22, page: 3, text: source.paragraphs[21].text };
const reply = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
function setup(read?: () => Promise<Response>) {
  const fetch = vi.fn(async (url: string, init: RequestInit) => {
    if (url.endsWith('/sources/source')) return read ? read() : reply(source);
    if (url.endsWith('/sources')) return reply({ items: [source] });
    if (url.endsWith('/citation')) return reply(evidence);
    if (url.includes('/search?')) return reply({ items: [evidence] });
    if (url.endsWith('/notes') && init.method === 'POST') return reply({});
    return reply({ items: [] });
  });
  vi.stubGlobal('fetch', fetch);
  const client = experimentalClient('n', { sessionToken: 'synthetic' });
  const view = render(<ResearchLibraryPanel client={client} />);
  return { fetch, view, client };
}
async function trace() {
  await screen.findByRole('button', { name: '打开来源 Synthetic source' });
  fireEvent.change(screen.getByLabelText('资料检索词'), { target: { value: 'duplicate' } });
  fireEvent.click(screen.getByRole('button', { name: '检索已保存资料' }));
  fireEvent.click(await screen.findByRole('button', { name: '追溯 Synthetic source 第 22 段' }));
  await screen.findByRole('button', { name: '在原来源中定位此引用' });
}
it('locates the exact second-page original paragraph, preserves draft, and saves only explicit original-owner selection', async () => {
  const { fetch } = setup(); await trace();
  fireEvent.change(screen.getByLabelText('研究笔记标题'), { target: { value: 'My note' } });
  fireEvent.change(screen.getByLabelText('研究笔记内容'), { target: { value: 'My original draft' } });
  fireEvent.click(screen.getByRole('button', { name: '在原来源中定位此引用' }));
  const located = await screen.findByRole('region', { name: '已定位的原始段落' });
  await waitFor(() => expect(document.activeElement).toBe(located));
  expect(screen.getByText('第 2 / 3 组')).toBeTruthy();
  expect(screen.getByText('已选择 0 段引用。')).toBeTruthy();
  expect((screen.getByLabelText('研究笔记内容') as HTMLTextAreaElement).value).toBe('My original draft');
  expect(fetch.mock.calls.filter(([, init]) => init.method !== 'GET').map(([url]) => url.endsWith('/citation'))).toEqual([true]);
  fireEvent.click(within(located).getByLabelText('选择引用：第 3 页 · 第 22 段'));
  fireEvent.click(screen.getByRole('button', { name: '保存带引用的研究笔记' }));
  await waitFor(() => expect(fetch.mock.calls.some(([url, init]) => url.endsWith('/notes') && init.method === 'POST')).toBe(true));
  const sent = fetch.mock.calls.find(([url, init]) => url.endsWith('/notes') && init.method === 'POST')!;
  expect(JSON.parse(String(sent[1].body))).toEqual({ title: 'My note', text: 'My original draft', citations: [ref] });
});
it('keeps stale pin metadata without displaying or silently opening latest text', async () => {
  const { fetch } = setup(async () => reply({ ...source, version: 3 })); await trace();
  fireEvent.click(screen.getByRole('button', { name: '在原来源中定位此引用' }));
  await screen.findByText(/历史列表不提供原段落/);
  expect(screen.getByText(/固定引用 source · v2 · 第 3 页 · 第 22 段 · 引用摘要/).textContent).toContain(ref.quote_sha256);
  expect(screen.queryByRole('region', { name: '引用原文' })).toBeNull();
  expect(screen.queryByRole('region', { name: '当前研究来源' })).toBeNull();
  expect(fetch.mock.calls.some(([url]) => /history|restore/.test(url))).toBe(false);
});
it('clears prior evidence on a failed original read and permits an explicit fresh trace', async () => {
  setup(async () => reply({ detail: { code: 'UNAVAILABLE' } }, 500)); await trace();
  fireEvent.click(screen.getByRole('button', { name: '在原来源中定位此引用' }));
  await screen.findByRole('alert');
  expect(screen.queryByRole('region', { name: '引用原文' })).toBeNull();
  expect(screen.queryByRole('region', { name: '已定位的原始段落' })).toBeNull();
});
it('discards a delayed locate after scope replacement without reading unrelated sources', async () => {
  let resolve!: (r: Response) => void;
  const { view, fetch } = setup(() => new Promise(done => { resolve = done; })); await trace();
  fireEvent.click(screen.getByRole('button', { name: '在原来源中定位此引用' }));
  view.rerender(<ResearchLibraryPanel client={experimentalClient('other', { sessionToken: 'synthetic' })} />);
  resolve(reply(source));
  await waitFor(() => expect(screen.queryByRole('region', { name: '引用定位状态' })).toBeNull());
  expect(fetch.mock.calls.some(([url]) => url.includes('/other/') && url.endsWith('/sources/source'))).toBe(false);
});
it('does not steal focus while the author is composing text', async () => {
  const { fetch } = setup(); await trace();
  const input = screen.getByLabelText('研究笔记内容');
  fireEvent.compositionStart(input);
  fireEvent.click(screen.getByRole('button', { name: '在原来源中定位此引用' }));
  expect(fetch.mock.calls.some(([url]) => url.endsWith('/sources/source'))).toBe(false);
  fireEvent.compositionEnd(input);
  fireEvent.click(screen.getByRole('button', { name: '在原来源中定位此引用' }));
  await screen.findByRole('region', { name: '已定位的原始段落' });
});
it('withholds original evidence if the original-view reread changes version after inspection', async () => {
  let count = 0;
  setup(async () => reply({ ...source, version: ++count === 1 ? 2 : 3 })); await trace();
  fireEvent.click(screen.getByRole('button', { name: '在原来源中定位此引用' }));
  await screen.findByRole('region', { name: '引用定位状态' });
  await waitFor(() => expect(count).toBeGreaterThan(1));
  await waitFor(() => expect(screen.queryByRole('region', { name: '引用原文' })).toBeNull());
  expect(screen.queryByRole('region', { name: '已定位的原始段落' })).toBeNull();
});
it('invalidates an in-flight locate when a new search query is entered', async () => {
  let resolve!: (r: Response) => void;
  setup(() => new Promise(done => { resolve = done; })); await trace();
  fireEvent.click(screen.getByRole('button', { name: '在原来源中定位此引用' }));
  fireEvent.change(screen.getByLabelText('资料检索词'), { target: { value: 'new' } });
  resolve(reply(source));
  await waitFor(() => expect((screen.getByRole('button', { name: '检索已保存资料' }) as HTMLButtonElement).disabled).toBe(false));
  expect(screen.queryByRole('region', { name: '引用定位状态' })).toBeNull();
});
it('cancels and suppresses an ignored-abort response without changing selected source', async () => {
  let resolve!: (r: Response) => void;
  const { fetch } = setup(() => new Promise(done => { resolve = done; })); await trace();
  fireEvent.click(screen.getByRole('button', { name: '在原来源中定位此引用' }));
  fireEvent.click(await screen.findByRole('button', { name: '取消引用定位' }));
  const request = fetch.mock.calls.find(([url]) => url.endsWith('/sources/source'))!;
  expect(request[1].signal?.aborted).toBe(true);
  resolve(reply(source));
  await waitFor(() => expect((screen.getByRole('button', { name: '检索已保存资料' }) as HTMLButtonElement).disabled).toBe(false));
  expect(screen.queryByRole('region', { name: '引用定位状态' })).toBeNull();
  expect(screen.queryByRole('region', { name: '引用原文' })).toBeNull();
});
it('falls back to pin metadata without rendering a malformed second original response', async () => {
  let count = 0;
  setup(async () => reply(++count === 1 ? source : { ...source, paragraphs: [null] })); await trace();
  fireEvent.click(screen.getByRole('button', { name: '在原来源中定位此引用' }));
  await screen.findByRole('region', { name: '引用定位状态' });
  await waitFor(() => expect(count).toBeGreaterThan(1));
  await waitFor(() => expect(screen.queryByRole('region', { name: '引用原文' })).toBeNull());
  expect(screen.queryByRole('region', { name: '已定位的原始段落' })).toBeNull();
  expect(screen.queryByRole('region', { name: '当前研究来源' })).toBeNull();
  fireEvent.change(screen.getByLabelText('资料检索词'), { target: { value: 'changed after invalid read' } });
  expect(screen.queryByRole('region', { name: '当前研究来源' })).toBeNull();
  expect(screen.queryByRole('region', { name: '引用原文' })).toBeNull();
});
