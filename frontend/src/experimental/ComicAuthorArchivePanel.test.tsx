// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { File as NodeFile, Blob as NodeBlob } from 'node:buffer';
import { createHash, webcrypto } from 'node:crypto';
import { ComicLayoutsPanel } from './ComicLayoutsPanel';
import { experimentalClient } from './api';
import type { ComicBook, ComicRecord } from './comicLayoutsClient';
import { saveOtioFile } from './timelineExchangeClient';
vi.mock('./timelineExchangeClient', async original => ({ ...await original<typeof import('./timelineExchangeClient')>(), saveOtioFile: vi.fn() }));
import { authorDisclosure } from './comicAuthorArchiveClient';
const reply = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status });
const preset = { width: 800, height: 1120, safe_area: 24, segment_height: 1120 };
const page = (): ComicRecord => ({ id: 'restored-page', version: 1, stale: false, status: 'DRAFT', history_versions: [], document: { ...preset, title: 'Editable restored page', source_mode: 'INDEPENDENT', screenplay_id: null, expected_screenplay_version: null, preset: 'PAGE', font_family: 'NOTO_SANS_SC_OFL', panels: [{ id: 'panel', shot_id: null, artwork_mode: 'BLANK', order: 1, x: 24, y: 24, width: 600, height: 300, character_ids: [], asset_id: null, expected_asset_version: null, fit: 'CONTAIN', image_brief: 'Private image brief', bubbles: [{ id: 'bubble', kind: 'DIALOGUE', text: 'Editable hidden words', character_id: null, font_size: 24, x: 40, y: 40, width: 400, height: 100 }] }], layer_stack: { schema_version: 1, items: [{ id: 'layer_art', kind: 'PANEL_ART', target_id: 'panel', name: 'Art', visible: true, opacity_percent: 100 }, { id: 'layer_frame', kind: 'PANEL_FRAME', target_id: 'panel', name: 'Frame', visible: true, opacity_percent: 100 }, { id: 'layer_shape', kind: 'BUBBLE_SHAPE', target_id: 'bubble', name: 'Shape', visible: true, opacity_percent: 100 }, { id: 'layer_text', kind: 'BUBBLE_TEXT', target_id: 'bubble', name: 'Hidden text', visible: false, opacity_percent: 100 }] } } });
const book = (): ComicBook => ({ id: 'restored-book', version: 1, stale: false, title: 'Restored author book', chapters: [{ id: 'chapter', title: 'Chapter', pages: ['restored-page'] }] });
const click = (name: string) => fireEvent.click(screen.getByRole('button', { name }));
const client = (nid = 'original') => experimentalClient(nid, { sessionToken: 'trusted' });
function harness(options: { lost?: boolean; initial?: boolean; exportBad?: boolean; completed?: boolean; pending?: 'restore' | 'download'; inspection?: (body: any) => Promise<Response> } = {}) {
  let finishPending: () => void = () => {};
  const delayed = (response: Response) => new Promise<Response>(resolve => { finishPending = () => resolve(response); });
  let pages: ComicRecord[] = options.initial ? [page()] : [], books: ComicBook[] = options.initial ? [book()] : [], attempts = 0;
  const fetch = vi.fn(async (url: string, init: RequestInit) => {
    if (init.method === 'GET') return reply(url.endsWith('/catalog') ? { screenplays: [], characters: [], assets: [], presets: { PAGE: preset, WEBTOON: preset }, renderer: { available: true }, font: { available: true } } : { items: url.endsWith('/books') ? books : pages });
    const body = JSON.parse(String(init.body));
    if (url.endsWith('/inspect')) return options.inspection ? options.inspection(body) : reply({ contract: 'comic-author-assetless-page/1', archive_sha256: body.archive_sha256, inspection_digest: 'a'.repeat(64), title: 'Imported author', page_count: 1, disclosure: authorDisclosure, coverage: 'ASSETLESS_INDEPENDENT_PAGE_ONLY', restore_status: 'NEW_UNAPPROVED_DRAFTS', receipt_capacity: 20, receipt_remaining: options.completed ? 0 : 20, completed_attempts: options.completed ? [{ request_key: 'c'.repeat(32), result_state: 'COMPLETED' }] : [] });
    if (url.endsWith('/author-archive/restore')) { attempts++; pages = [page()]; books = [book()]; if (options.lost && attempts === 1) throw new Error('Lost acknowledgement'); const response = reply({ book: books[0], pages, request_key: body.request_key, replayed: attempts > 1 }); return options.pending === 'restore' ? delayed(response) : response; }
    if (url.endsWith('/export-author-archive')) { const bytes = new TextEncoder().encode('PK' + 'x'.repeat(30)); const response = new Response(bytes, { headers: { 'Content-Type': 'application/zip', 'X-Content-SHA256': options.exportBad ? 'f'.repeat(64) : createHash('sha256').update(bytes).digest('hex'), 'X-Comic-Author-Export-Digest': 'b'.repeat(64) } }); return options.pending === 'download' ? delayed(response) : response; }
    if (url.endsWith('/author-archive-preview')) return reply({ contract: 'comic-author-assetless-page/1', export_digest: 'b'.repeat(64), book_version: 1, page_count: 1, disclosure: authorDisclosure, coverage: 'ASSETLESS_INDEPENDENT_PAGE_ONLY', conveys_approval: false, pages: [{ id: 'restored-page', version: 1 }] });
    if (url.endsWith('/records/restored-page') && init.method === 'PUT') { pages = [{ ...pages[0], version: 2, document: body }]; return reply(pages[0]); }
    throw new Error(`Unexpected ${init.method} ${url}`);
  });
  vi.stubGlobal('fetch', fetch); const view = render(<ComicLayoutsPanel client={client()} />); return { fetch, view, finish: () => finishPending() };
}
async function inspect() {
  await act(async () => { await new Promise(resolve => setTimeout(resolve, 20)); });
  await waitFor(() => expect((screen.getByLabelText('选择漫画作者 ZIP') as HTMLInputElement).disabled).toBe(false));
  fireEvent.change(screen.getByLabelText('选择漫画作者 ZIP'), { target: { files: [new NodeFile(['PK' + 'x'.repeat(30)], 'author.zip')] } });
  click('只读检查作者归档'); await screen.findByText(/待恢复：Imported author/);
}
beforeEach(() => { Object.defineProperty(navigator, 'locks', { configurable: true, value: { request: vi.fn(async (_name: string, fn: () => Promise<unknown>) => fn()) } }); localStorage.clear(); vi.clearAllMocks(); vi.stubGlobal('crypto', webcrypto); vi.stubGlobal('Blob', NodeBlob); URL.createObjectURL = vi.fn(() => 'blob:author'); URL.revokeObjectURL = vi.fn(); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });
it('mounted native owner inspects without writes, explicitly restores a book and page, and saves editable hidden text and briefs', async () => {
  const h = harness(); await inspect();
  expect(h.fetch.mock.calls.filter(([, init]) => init.method !== 'GET').map(([url]) => url.split('/').pop())).toEqual(['inspect']);
  expect((screen.getByRole('button', { name: '恢复作者归档为新草稿' }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(screen.getByLabelText('确认恢复为新的未批准草稿，并保留原书')); click('恢复作者归档为新草稿');
  await screen.findByDisplayValue('Editable hidden words');
  await screen.findByDisplayValue('Restored author book');
  expect((screen.getByLabelText('格框 1 图片简报') as HTMLTextAreaElement).value).toBe('Private image brief');
  fireEvent.change(screen.getByLabelText('格框 1 气泡 1 文字'), { target: { value: 'Edited restored text' } });
  fireEvent.change(screen.getByLabelText('格框 1 图片简报'), { target: { value: 'Edited private brief' } });
  click('保存漫画布局草稿');
  await waitFor(() => expect(h.fetch.mock.calls.some(([url, init]) => url.endsWith('/records/restored-page') && init.method === 'PUT')).toBe(true));
  const saved = JSON.parse(String(h.fetch.mock.calls.find(([, init]) => init.method === 'PUT')![1].body));
  expect(saved.expected_version).toBe(1); expect(saved.panels[0].bubbles[0].text).toBe('Edited restored text'); expect(saved.panels[0].image_brief).toBe('Edited private brief');
  expect(saved.layer_stack.items.find((l: any) => l.kind === 'BUBBLE_TEXT').visible).toBe(false);
  const restored = JSON.parse(String(h.fetch.mock.calls.find(([url]) => url.endsWith('/author-archive/restore'))![1].body));
  expect(restored.request_key).toMatch(/^[a-f0-9]{32}$/); expect(restored.acknowledge_restore_drafts).toBe(true); expect(restored.inspection_digest).toBe('a'.repeat(64));
  expect(h.fetch.mock.calls.some(([url]) => /approve|generate|execute/.test(url))).toBe(false);
});
it('lost acknowledgement retains the exact restore key across reopen and explicit reselect/retry', async () => {
  const h = harness({ lost: true }); await inspect(); fireEvent.click(screen.getByLabelText('确认恢复为新的未批准草稿，并保留原书')); click('恢复作者归档为新草稿');
  await screen.findByText(/Lost acknowledgement/); expect((screen.getByRole('button', { name: '明确开始另一份独立导入（将新增书和页面）' }) as HTMLButtonElement).disabled).toBe(true); h.view.unmount(); render(<ComicLayoutsPanel client={client()} />); await inspect(); fireEvent.click(screen.getByLabelText('确认恢复为新的未批准草稿，并保留原书')); click('恢复作者归档为新草稿'); await screen.findByDisplayValue('Editable hidden words');
  const requests = h.fetch.mock.calls.filter(([url]) => url.endsWith('/author-archive/restore')).map(([, init]) => JSON.parse(String(init.body)));
  expect(requests).toHaveLength(2); expect(requests[0]).toEqual(requests[1]);
});
it('rejects oversized files before reading or posting inspection', async () => {
  const h = harness(); await act(async () => { await new Promise(resolve => setTimeout(resolve, 20)); });
  await waitFor(() => expect((screen.getByLabelText('选择漫画作者 ZIP') as HTMLInputElement).disabled).toBe(false));
  const slice = vi.fn(); fireEvent.change(screen.getByLabelText('选择漫画作者 ZIP'), { target: { files: [{ name: 'large.zip', size: 2_000_001, slice }] } }); click('只读检查作者归档');
  await screen.findByText(/作者归档必须为/); expect(slice).not.toHaveBeenCalled(); expect(h.fetch.mock.calls.every(([, init]) => init.method === 'GET')).toBe(true);
});
it('late inspection from a retired client cannot expose content or restore controls', async () => {
  let finish: (value: Response) => void = () => {};
  const h = harness({ inspection: () => new Promise(resolve => { finish = resolve; }) });
  await act(async () => { await new Promise(resolve => setTimeout(resolve, 20)); });
  await waitFor(() => expect((screen.getByLabelText('选择漫画作者 ZIP') as HTMLInputElement).disabled).toBe(false));
  fireEvent.change(screen.getByLabelText('选择漫画作者 ZIP'), { target: { files: [new NodeFile(['x'.repeat(30)], 'author.zip')] } }); click('只读检查作者归档');
  await waitFor(() => expect(h.fetch.mock.calls.some(([url]) => url.endsWith('/inspect'))).toBe(true));
  h.view.rerender(<ComicLayoutsPanel client={client('another')} />);
  await act(async () => finish(reply({ title: 'Private late title' })));
  expect(screen.queryByText(/Private late title/)).toBeNull(); expect(screen.queryByRole('button', { name: '恢复作者归档为新草稿' })).toBeNull();
});
it('private author export needs its own acknowledgement and local page edits invalidate preview', async () => {
  const h = harness({ initial: true }); await act(async () => { await new Promise(resolve => setTimeout(resolve, 20)); }); fireEvent.click(await screen.findByRole('button', { name: '打开漫画书 Restored author book' })); click('检查当前书作者归档');
  await screen.findByText(/已检查 1 页 · 书结构 v1/);
  const download = screen.getByRole('button', { name: '下载可编辑作者归档' }) as HTMLButtonElement; expect(download.disabled).toBe(true);
  fireEvent.click(screen.getByLabelText('我确认导出包含隐藏文字和图片简述的私密作者内容')); expect(download.disabled).toBe(false);
  click('打开页面 1.1 · Editable restored page');
  fireEvent.change(screen.getByLabelText('格框 1 气泡 1 文字'), { target: { value: 'New draft' } });
  expect(screen.queryByRole('button', { name: '下载可编辑作者归档' })).toBeNull();
  expect(h.fetch.mock.calls.some(([url]) => url.endsWith('/export-author-archive'))).toBe(false);
});

it.each([false, true])('downloads explicit acknowledged author bytes only after digest validation (corrupt=%s)', async exportBad => {
  const h = harness({ initial: true, exportBad }); await act(async () => { await new Promise(resolve => setTimeout(resolve, 20)); });
  fireEvent.click(await screen.findByRole('button', { name: '打开漫画书 Restored author book' })); click('检查当前书作者归档');
  await screen.findByText(/已检查 1 页 · 书结构 v1/); fireEvent.click(screen.getByLabelText('我确认导出包含隐藏文字和图片简述的私密作者内容')); click('下载可编辑作者归档');
  if (exportBad) { await screen.findByText(/COMIC_AUTHOR_ARCHIVE_INVALID_RESPONSE/); expect(saveOtioFile).not.toHaveBeenCalled(); }
  else await waitFor(() => expect(saveOtioFile).toHaveBeenCalledWith(expect.any(Blob), 'comic-author.zip'));
  const request = JSON.parse(String(h.fetch.mock.calls.find(([url]) => url.endsWith('/export-author-archive'))![1].body));
  expect(request).toEqual({ expected_version: 1, export_digest: 'b'.repeat(64), acknowledge_author_content: true });
});
it('discovers completed restore after local identity loss and permits explicit recovery at receipt capacity', async () => {
  const h = harness({ completed: true }); await inspect();
  await screen.findByText(/已找到已有恢复标识/);
  expect(h.fetch.mock.calls.some(([url]) => url.endsWith('/author-archive/restore'))).toBe(false);
  fireEvent.click(screen.getByLabelText('确认恢复为新的未批准草稿，并保留原书')); click('恢复作者归档为新草稿'); await screen.findByDisplayValue('Editable hidden words');
  const request = JSON.parse(String(h.fetch.mock.calls.find(([url]) => url.endsWith('/author-archive/restore'))![1].body)); expect(request.request_key).toBe('c'.repeat(32));
});

it.each(['unavailable', 'quota', 'readback'])('fails closed before restore when durable admission fails: %s', async failure => {
  const h = harness(); await inspect();
  if (failure === 'unavailable') Object.defineProperty(navigator, 'locks', { configurable: true, value: undefined });
  if (failure === 'quota') vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('quota'); });
  if (failure === 'readback') vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {});
  fireEvent.click(screen.getByLabelText('确认恢复为新的未批准草稿，并保留原书')); click('恢复作者归档为新草稿');
  await screen.findByText(failure === 'unavailable' ? /不支持跨标签页恢复锁/ : /无法保存恢复标识/);
  expect(h.fetch.mock.calls.some(([url]) => url.endsWith('/author-archive/restore'))).toBe(false);
});

it('late restore response after scope retirement never selects the old book or page', async () => {
  const h = harness({ pending: 'restore' }); await inspect();
  fireEvent.click(screen.getByLabelText('确认恢复为新的未批准草稿，并保留原书')); click('恢复作者归档为新草稿');
  await waitFor(() => expect(h.fetch.mock.calls.some(([url]) => url.endsWith('/author-archive/restore'))).toBe(true));
  h.view.rerender(<ComicLayoutsPanel client={client('another')} />);
  await act(async () => h.finish());
  expect(screen.queryByDisplayValue('Editable restored page')).toBeNull();
  expect(screen.queryByDisplayValue('Editable hidden words')).toBeNull();
  expect(screen.queryByDisplayValue('Restored author book')).toBeNull();
  expect(screen.queryByText(/作者归档已恢复为新草稿/)).toBeNull();
});
it('late validated download after scope retirement never saves the old author archive', async () => {
  const h = harness({ initial: true, pending: 'download' }); await act(async () => { await new Promise(resolve => setTimeout(resolve, 20)); });
  fireEvent.click(await screen.findByRole('button', { name: '打开漫画书 Restored author book' })); click('检查当前书作者归档');
  await screen.findByText(/已检查 1 页 · 书结构 v1/); fireEvent.click(screen.getByLabelText('我确认导出包含隐藏文字和图片简述的私密作者内容')); click('下载可编辑作者归档');
  await waitFor(() => expect(h.fetch.mock.calls.some(([url]) => url.endsWith('/export-author-archive'))).toBe(true));
  h.view.rerender(<ComicLayoutsPanel client={client('another')} />);
  await act(async () => { h.finish(); await new Promise(resolve => setTimeout(resolve, 20)); });
  expect(saveOtioFile).not.toHaveBeenCalled();
  expect(screen.queryByRole('button', { name: '下载可编辑作者归档' })).toBeNull();
});
