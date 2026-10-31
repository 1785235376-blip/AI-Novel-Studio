// @vitest-environment jsdom
import { webcrypto } from 'node:crypto';
import { Blob as NativeBlob } from 'node:buffer';
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { ComicCollectionTree } from './ComicCollectionTree';
import { ComicLayoutsPanel } from './ComicLayoutsPanel';
import { StudioComicPanel } from '../creative/StudioComicPanel';
import { experimentalClient } from './api';
import { blankComic, type ComicBook, type ComicPdfPublicationPreflight, type ComicPublicationPreflight, type ComicRecord } from './comicLayoutsClient';
import { saveOtioFile } from './timelineExchangeClient';

vi.mock('./timelineExchangeClient', () => ({ saveOtioFile: vi.fn() }));
const settings = { width: 800, height: 1120, safe_area: 24, segment_height: 1120 };
const page = (id: string, version: number): ComicRecord => ({ id, version, status: 'APPROVED', stale: false, document: { ...blankComic('PAGE', settings), title: `页面 ${id}` } });
const initialBook = (): ComicBook => ({ id: 'book', version: 3, stale: false, title: '出版测试书', chapters: [{ id: 'ch1', title: '第一章', pages: ['p2'] }, { id: 'ch2', title: '第二章', pages: ['p1'] }] });
const initialReport = (): ComicPublicationPreflight => ({ book_version: 3, reading_direction: 'RTL', pages: [{ id: 'p2', version: 6, review_digest: 'b'.repeat(64) }, { id: 'p1', version: 4, review_digest: 'a'.repeat(64) }], publication_digest: 'c'.repeat(64), page_count: 2, losses: ['FLATTENED_RGB_PNG_PAGES', 'NO_EDITABLE_LAYERS_OR_TEXT', 'DIRECTION_METADATA_DOES_NOT_REORDER_PAGES_OR_PANELS', 'NO_DPI_BLEED_OR_PRINT_CONFORMANCE', 'EXTERNAL_READER_VALIDATION_NOT_RUN'] });
const initialPdfReport = (dpi = 144): ComicPdfPublicationPreflight => ({ ...initialReport(), format: 'comic-pdf-raster-v1', dpi,
  page_dimensions: [1, 2].map(() => ({ width_pixels: 800, height_pixels: 1120, width_points: 800 * 72 / dpi, height_points: 1120 * 72 / dpi })),
  losses: ['FLATTENED_RGB_RASTER_PAGES', 'NO_EDITABLE_LAYERS_OR_TEXT', 'DIRECTION_METADATA_DOES_NOT_REORDER_PAGES_OR_PANELS', 'CALLER_SELECTED_DPI_NOT_PRINT_QUALITY', 'NO_BLEED_OR_PDF_A_PDF_X_CONFORMANCE', 'SOURCE_IMAGE_RIGHTS_NOT_VERIFIED', 'EXTERNAL_READER_VALIDATION_NOT_RUN'],
});
const reply = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status });
async function archive(format: 'CBZ' | 'PDF' = 'CBZ') {
  const bytes = new TextEncoder().encode(format === 'PDF' ? '%PDF-1.4 test bytes' : 'test-cbz-bytes');
  const sha = Array.from(new Uint8Array(await webcrypto.subtle.digest('SHA-256', bytes)), byte => byte.toString(16).padStart(2, '0')).join('');
  return new Response(bytes, { headers: { 'Content-Type': format === 'PDF' ? 'application/pdf' : 'application/vnd.comicbook+zip', 'X-Comic-Publication-Digest': 'c'.repeat(64), 'X-Content-SHA256': sha } });
}
beforeEach(() => { vi.stubGlobal('crypto', webcrypto); vi.stubGlobal('Blob', NativeBlob); vi.mocked(saveOtioFile).mockClear(); URL.createObjectURL = vi.fn(() => 'blob:test'); URL.revokeObjectURL = vi.fn(); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
function harness(options: { pages?: ComicRecord[]; book?: ComicBook; books?: ComicBook[]; mutate?: (url: string, init: RequestInit) => Promise<Response> | Response } = {}) {
  const pages = options.pages || [page('p1', 4), page('p2', 6)], book = options.book || initialBook();
  const fetch = vi.fn(async (url: string, init: RequestInit) => {
    if (init.method === 'GET') {
      if (url.endsWith('/books')) return reply({ items: options.books || [book] });
      if (url.endsWith('/records')) return reply({ items: pages });
      if (url.endsWith('/catalog')) return reply({ screenplays: [], characters: [], assets: [], presets: { PAGE: settings, WEBTOON: settings }, renderer: { available: true }, font: { available: true } });
    }
    if (options.mutate) return options.mutate(url, init);
    if (url.endsWith('/publication-preflight')) return reply(initialReport());
    if (url.endsWith('/pdf-publication-preflight')) return reply(initialPdfReport(JSON.parse(String(init.body)).dpi));
    if (url.endsWith('/export-cbz')) return archive();
    if (url.endsWith('/export-pdf')) return archive('PDF');
    return reply({}, 404);
  });
  vi.stubGlobal('fetch', fetch);
  const props = { client: experimentalClient('novel', { sessionToken: 'trusted', scope: { workspaceId: 'w', projectId: 'novel', storylineId: 's', branchId: 'branch' } }), records: pages, recordsReady: true, pageDirty: false, externalBusy: false, getOwnerRevision: () => 0, onActiveChange: vi.fn(), onDirtyChange: vi.fn(), onBusyChange: vi.fn(), onOpenPage: vi.fn(), onPageCreated: vi.fn() };
  return { fetch, props, posts: () => fetch.mock.calls.filter(([, init]) => init.method === 'POST') };
}
async function openBook() {
  await waitFor(() => {
    const button = screen.getByRole('button', { name: '打开漫画书 出版测试书' }) as HTMLButtonElement;
    expect(button.disabled).toBe(false); fireEvent.click(button);
    expect(screen.getByRole('region', { name: '漫画书 CBZ 导出' })).toBeTruthy();
  });
}
async function preflight() {
  fireEvent.change(screen.getByLabelText('CBZ 阅读方向'), { target: { value: 'RTL' } });
  fireEvent.click(screen.getByRole('button', { name: '检查当前漫画书出版副本' }));
  await screen.findByText('已检查 2 页 · RTL · 书结构 v3');
}
const ack = () => fireEvent.click(screen.getByRole('checkbox', { name: '已核对以上已保存页面顺序、阅读方向与合成图片限制' }));
const download = () => screen.getByRole('button', { name: '下载已核对的 CBZ' }) as HTMLButtonElement;
const choosePdf = () => fireEvent.change(screen.getByLabelText('出版副本格式'), { target: { value: 'PDF' } });
const setDpi = (value: string) => fireEvent.change(screen.getByLabelText('PDF DPI（36–600 整数，需明确填写）'), { target: { value } });
const pdfAck = () => fireEvent.click(screen.getByRole('checkbox', { name: '已核对以上已保存页面顺序、阅读方向、DPI、页面尺寸与合成图片限制' }));
const pdfDownload = () => screen.getByRole('button', { name: '下载已核对的 PDF' }) as HTMLButtonElement;
async function pdfPreflight(dpi = '144') {
  choosePdf(); setDpi(dpi);
  fireEvent.change(screen.getByLabelText('PDF 阅读方向'), { target: { value: 'RTL' } });
  fireEvent.click(screen.getByRole('button', { name: '检查当前漫画书出版副本' }));
  await screen.findByText(`已核对 PDF · ${dpi} DPI`);
}
function retained(element: HTMLElement): () => void { const key = Object.keys(element).find(value => value.startsWith('__reactProps'))!; return (element as unknown as Record<string, { onClick: () => void }>)[key].onClick; }

it('mounts below the original tree, makes no implicit posts, and requires an explicit direction and saved-order review', async () => {
  const h = harness(); render(<ComicCollectionTree {...h.props} />); await openBook();
  expect(h.posts()).toHaveLength(0);
  expect((screen.getByRole('button', { name: '检查当前漫画书出版副本' }) as HTMLButtonElement).disabled).toBe(true);
  const order = within(screen.getByRole('list', { name: 'CBZ 已保存页面顺序' })).getAllByRole('listitem').map(item => item.textContent);
  expect(order).toEqual(['1.1 · 第一章 · 页面 p2 · v6', '2.1 · 第二章 · 页面 p1 · v4']);
  await preflight(); expect(download().disabled).toBe(true); ack();
  const click = retained(download()); await act(async () => { click(); click(); });
  await screen.findByText('已校验并下载 CBZ 合成图片副本。');
  expect(h.posts()).toHaveLength(2);
  expect(JSON.parse(String(h.posts()[0][1].body))).toEqual({ expected_version: 3, reading_direction: 'RTL' });
  expect(JSON.parse(String(h.posts()[1][1].body))).toEqual({ expected_version: 3, reading_direction: 'RTL', pages: initialReport().pages, publication_digest: 'c'.repeat(64) });
  expect(saveOtioFile).toHaveBeenCalledTimes(1); expect(saveOtioFile).toHaveBeenCalledWith(expect.anything(), 'comic-book.cbz');
  expect(h.props.onDirtyChange).not.toHaveBeenCalledWith(true);
  expect(h.props.onBusyChange).toHaveBeenLastCalledWith(false);
});

it('survives its own aggregate busy revision and blocks the original page editor during publication work', async () => {
  let finish: (response: Response) => void = () => {};
  const h = harness({ mutate: url => url.endsWith('/publication-preflight') ? new Promise(resolve => { finish = resolve; }) : archive() });
  const onBusy = vi.fn(); render(<ComicLayoutsPanel client={h.props.client} onBusyChange={onBusy} />); await openBook();
  fireEvent.change(screen.getByLabelText('CBZ 阅读方向'), { target: { value: 'RTL' } });
  fireEvent.click(screen.getByRole('button', { name: '检查当前漫画书出版副本' }));
  expect((screen.getByRole('button', { name: '新建空白漫画页' }) as HTMLButtonElement).disabled).toBe(true);
  expect((screen.getByRole('button', { name: '刷新漫画书' }) as HTMLButtonElement).disabled).toBe(true);
  await act(async () => finish(reply(initialReport())));
  await screen.findByText('已检查 2 页 · RTL · 书结构 v3'); ack(); fireEvent.click(download());
  await screen.findByText('已校验并下载 CBZ 合成图片副本。');
  expect(saveOtioFile).toHaveBeenCalledTimes(1); expect(onBusy).toHaveBeenLastCalledWith(false);
});

it.each(['DRAFT', 'WEBTOON', 'empty'])('blocks unpublishable %s collections before any POST', async state => {
  const pages = [page('p1', 4), page('p2', 6)];
  if (state === 'DRAFT') pages[0].status = 'DRAFT';
  if (state === 'WEBTOON') pages[0].document!.preset = 'WEBTOON';
  const h = harness({ pages, ...(state === 'empty' ? { book: { ...initialBook(), chapters: [] } } : {}) }); render(<ComicCollectionTree {...h.props} />); await openBook();
  fireEvent.change(screen.getByLabelText('CBZ 阅读方向'), { target: { value: 'RTL' } });
  const button = screen.getByRole('button', { name: '检查当前漫画书出版副本' }) as HTMLButtonElement;
  expect(button.disabled).toBe(true); act(retained(button)); expect(h.posts()).toHaveLength(0);
});

it('invalidates the review on direction changes and requires a fresh explicit review after cancellation', async () => {
  const h = harness(); render(<ComicCollectionTree {...h.props} />); await openBook(); await preflight(); ack(); const oldDownload = retained(download());
  fireEvent.change(screen.getByLabelText('CBZ 阅读方向'), { target: { value: 'LTR' } });
  act(oldDownload); expect(screen.queryByRole('button', { name: '下载已核对的 CBZ' })).toBeNull(); expect(h.posts()).toHaveLength(1);
  await preflight(); ack(); fireEvent.click(screen.getByRole('button', { name: '放弃本次出版结果' }));
  expect(screen.queryByRole('button', { name: '下载已核对的 CBZ' })).toBeNull(); expect(saveOtioFile).not.toHaveBeenCalled();
});

it('blocks dirty tree and dirty page state and does not restore an old review after discarding edits', async () => {
  const h = harness(); const view = render(<ComicCollectionTree {...h.props} />); await openBook(); await preflight(); ack(); const oldDownload = retained(download());
  fireEvent.change(screen.getByLabelText('漫画书名称'), { target: { value: '未保存书名' } });
  act(oldDownload); expect(screen.queryByRole('button', { name: '下载已核对的 CBZ' })).toBeNull();
  expect((screen.getByRole('button', { name: '检查当前漫画书出版副本' }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(screen.getByRole('button', { name: '放弃书结构修改' }));
  expect(screen.queryByRole('button', { name: '下载已核对的 CBZ' })).toBeNull();
  view.rerender(<ComicCollectionTree {...h.props} pageDirty />);
  expect((screen.getByRole('button', { name: '检查当前漫画书出版副本' }) as HTMLButtonElement).disabled).toBe(true);
  expect(h.posts()).toHaveLength(1);
});

it.each(['book_version', 'reading_direction', 'page_order', 'page_version', 'page_count', 'review_digest', 'publication_digest'])('rejects a preflight with mismatched %s', async field => {
  const report = initialReport();
  if (field === 'book_version') report.book_version++;
  if (field === 'reading_direction') report.reading_direction = 'LTR';
  if (field === 'page_order') report.pages.reverse();
  if (field === 'page_version') report.pages[0].version++;
  if (field === 'page_count') report.page_count++;
  if (field === 'review_digest') report.pages[0].review_digest = '';
  if (field === 'publication_digest') report.publication_digest = '';
  const h = harness({ mutate: () => reply(report) }); render(<ComicCollectionTree {...h.props} />); await openBook();
  fireEvent.change(screen.getByLabelText('CBZ 阅读方向'), { target: { value: 'RTL' } }); fireEvent.click(screen.getByRole('button', { name: '检查当前漫画书出版副本' }));
  await screen.findByText(/COMIC_PUBLICATION_INVALID_RESPONSE/); expect(screen.queryByRole('button', { name: '下载已核对的 CBZ' })).toBeNull(); expect(saveOtioFile).not.toHaveBeenCalled();
});

it('retained downloads cannot act after owner revision changes or unmount', async () => {
  let owner = 0; const h = harness(); const view = render(<ComicCollectionTree {...h.props} getOwnerRevision={() => owner} />); await openBook(); await preflight(); ack(); const oldDownload = retained(download());
  owner++; act(oldDownload); expect(h.posts()).toHaveLength(1); view.unmount(); act(oldDownload); expect(h.posts()).toHaveLength(1);
});

it.each(['owner', 'revision', 'records', 'dirty', 'external_busy', 'unmount'])('suppresses late exports after %s invalidation', async reason => {
  let owner = true, revision = 0, finish: (response: Response) => void = () => {};
  const h = harness({ mutate: url => url.endsWith('/publication-preflight') ? reply(initialReport()) : new Promise(resolve => { finish = resolve; }) });
  const props = { ...h.props, isOwnerCurrent: () => owner, getOwnerRevision: () => revision };
  const view = render(<ComicCollectionTree {...props} />); await openBook(); await preflight(); ack(); fireEvent.click(download());
  if (reason === 'owner') owner = false;
  if (reason === 'revision') revision++;
  if (reason === 'records') view.rerender(<ComicCollectionTree {...props} records={[page('p1', 5), page('p2', 6)]} />);
  if (reason === 'dirty') view.rerender(<ComicCollectionTree {...props} pageDirty />);
  if (reason === 'external_busy') view.rerender(<ComicCollectionTree {...props} externalBusy />);
  if (reason === 'unmount') view.unmount();
  await act(async () => finish(await archive()));
  expect(saveOtioFile).not.toHaveBeenCalled(); expect(screen.queryByText('已校验并下载 CBZ 合成图片副本。')).toBeNull();
});

it('cancelled preflight completion cannot replace a newer check or release its busy guard', async () => {
  const finishes: ((response: Response) => void)[] = [];
  const h = harness({ mutate: () => new Promise(resolve => { finishes.push(resolve); }) }); render(<ComicCollectionTree {...h.props} />); await openBook();
  fireEvent.change(screen.getByLabelText('CBZ 阅读方向'), { target: { value: 'RTL' } });
  fireEvent.click(screen.getByRole('button', { name: '检查当前漫画书出版副本' })); fireEvent.click(screen.getByRole('button', { name: '放弃本次出版结果' }));
  fireEvent.click(screen.getByRole('button', { name: '检查当前漫画书出版副本' }));
  await act(async () => finishes[0](reply(initialReport())));
  expect(screen.queryByText('已检查 2 页 · RTL · 书结构 v3')).toBeNull(); expect(h.props.onBusyChange).toHaveBeenLastCalledWith(true);
  await act(async () => finishes[1](reply(initialReport())));
  await screen.findByText('已检查 2 页 · RTL · 书结构 v3'); expect(h.props.onBusyChange).toHaveBeenLastCalledWith(false);
});

it('preserves saved content after a server conflict and requires new preflight', async () => {
  const h = harness({ mutate: url => url.endsWith('/publication-preflight') ? reply(initialReport()) : reply({ code: 'COMIC_PUBLICATION_CHANGED' }, 409) });
  render(<ComicCollectionTree {...h.props} />); await openBook(); await preflight(); ack(); fireEvent.click(download());
  await screen.findByText(/COMIC_PUBLICATION_CHANGED/); expect(screen.queryByRole('button', { name: '下载已核对的 CBZ' })).toBeNull();
  expect((screen.getByLabelText('漫画书名称') as HTMLInputElement).value).toBe('出版测试书'); expect(saveOtioFile).not.toHaveBeenCalled();
});

it('downloads through the real mounted IMAGE adapter with the original captured collaboration headers', async () => {
  const h = harness(); const onBusy = vi.fn();
  render(<StudioComicPanel projectId="novel" context={{ sessionToken: 'mounted-session', scope: { workspaceId: 'w', projectId: 'novel', storylineId: 's', branchId: 'mounted-branch' } }} isCurrent={() => true} onDirtyChange={vi.fn()} onBusyChange={onBusy} />);
  await openBook(); await preflight(); ack(); fireEvent.click(download());
  await screen.findByText('已校验并下载 CBZ 合成图片副本。');
  expect(saveOtioFile).toHaveBeenCalledTimes(1);
  expect(h.posts()).toHaveLength(2);
  expect(h.posts()[1][1].headers).toMatchObject({ 'X-Session-Token': 'mounted-session', 'X-Branch-Id': 'mounted-branch' });
  expect(onBusy).toHaveBeenLastCalledWith(false);
});

it('a mounted IMAGE export permission denial removes all private book projections', async () => {
  const h = harness({ mutate: url => url.endsWith('/publication-preflight') ? reply(initialReport()) : reply({ code: 'FORBIDDEN' }, 403) });
  render(<StudioComicPanel projectId="novel" context={{ sessionToken: 'mounted-session' }} isCurrent={() => true} onDirtyChange={vi.fn()} onBusyChange={vi.fn()} />);
  await openBook(); await preflight(); ack(); fireEvent.click(download());
  await screen.findByText(/当前身份或分支没有漫画访问权限/);
  expect(screen.queryByRole('region', { name: '漫画书 CBZ 导出' })).toBeNull(); expect(screen.queryByText(/出版测试书/)).toBeNull();
  expect(saveOtioFile).not.toHaveBeenCalled();
});

it('an acknowledgement removed before a retained click prevents downloading', async () => {
  const h = harness(); render(<ComicCollectionTree {...h.props} />); await openBook(); await preflight(); ack(); const oldDownload = retained(download());
  ack(); act(oldDownload); expect(h.posts()).toHaveLength(1); expect(download().disabled).toBe(true);
});

it('a late preflight cannot reveal review controls after page dirtiness changes', async () => {
  let finish: (response: Response) => void = () => {};
  const h = harness({ mutate: () => new Promise(resolve => { finish = resolve; }) }); const view = render(<ComicCollectionTree {...h.props} />); await openBook();
  fireEvent.change(screen.getByLabelText('CBZ 阅读方向'), { target: { value: 'RTL' } }); fireEvent.click(screen.getByRole('button', { name: '检查当前漫画书出版副本' }));
  view.rerender(<ComicCollectionTree {...h.props} pageDirty />); await act(async () => finish(reply(initialReport())));
  expect(screen.queryByText('已检查 2 页 · RTL · 书结构 v3')).toBeNull(); expect(screen.queryByRole('button', { name: '下载已核对的 CBZ' })).toBeNull();
  expect(h.props.onBusyChange).toHaveBeenLastCalledWith(false);
});

it('requires explicit PDF DPI and reviews ordered physical dimensions and limitations before a single verified download', async () => {
  const pages = [page('p1', 4), page('p2', 6)]; pages[0].document!.width = 1000; pages[0].document!.height = 1200;
  const report = initialPdfReport(); report.page_dimensions[1] = { width_pixels: 1000, height_pixels: 1200, width_points: 500, height_points: 600 };
  const h = harness({ pages, mutate: url => url.endsWith('/pdf-publication-preflight') ? reply(report) : archive('PDF') });
  render(<ComicCollectionTree {...h.props} />); await openBook(); choosePdf();
  expect(h.posts()).toHaveLength(0);
  expect((screen.getByLabelText('PDF DPI（36–600 整数，需明确填写）') as HTMLInputElement).value).toBe('');
  fireEvent.change(screen.getByLabelText('PDF 阅读方向'), { target: { value: 'RTL' } });
  const check = screen.getByRole('button', { name: '检查当前漫画书出版副本' }) as HTMLButtonElement;
  expect(check.disabled).toBe(true); act(retained(check)); expect(h.posts()).toHaveLength(0);
  setDpi('144'); fireEvent.click(check); await screen.findByText('已核对 PDF · 144 DPI');
  expect(within(screen.getByRole('list', { name: 'PDF 已保存页面顺序' })).getAllByRole('listitem').map(item => item.textContent)).toEqual(['1.1 · 第一章 · 页面 p2 · v6', '2.1 · 第二章 · 页面 p1 · v4']);
  expect(within(screen.getByRole('list', { name: 'PDF 已检查页面尺寸' })).getAllByRole('listitem').map(item => item.textContent)).toEqual(['第 1 页 · 800 × 1120 px · 400.000 × 560.000 pt', '第 2 页 · 1000 × 1200 px · 500.000 × 600.000 pt']);
  expect(within(screen.getByRole('list', { name: 'PDF 导出限制' })).getAllByRole('listitem')).toHaveLength(7);
  expect(screen.getByText('DPI 由你选择，仅确定页面尺寸，不代表印刷质量')).toBeTruthy();
  expect(pdfDownload().disabled).toBe(true); pdfAck(); const click = retained(pdfDownload());
  await act(async () => { click(); click(); }); await screen.findByText('已校验并下载 PDF 合成图片副本。');
  expect(h.posts().map(([url]) => url.split('/').pop())).toEqual(['pdf-publication-preflight', 'export-pdf']);
  expect(JSON.parse(String(h.posts()[0][1].body))).toEqual({ expected_version: 3, reading_direction: 'RTL', dpi: 144 });
  expect(JSON.parse(String(h.posts()[1][1].body))).toEqual({ expected_version: 3, reading_direction: 'RTL', dpi: 144, pages: report.pages, publication_digest: report.publication_digest });
  expect(saveOtioFile).toHaveBeenCalledTimes(1); expect(saveOtioFile).toHaveBeenCalledWith(expect.anything(), 'comic-book.pdf');
  expect(h.props.onDirtyChange).not.toHaveBeenCalledWith(true); expect(h.props.onBusyChange).toHaveBeenLastCalledWith(false);
});

it.each(['', '35', '601', '144.5', '-72', '3e2'])('blocks invalid PDF DPI "%s", including retained check handlers, before POST', async value => {
  const h = harness(); render(<ComicCollectionTree {...h.props} />); await openBook(); choosePdf();
  fireEvent.change(screen.getByLabelText('PDF 阅读方向'), { target: { value: 'RTL' } }); setDpi(value);
  const button = screen.getByRole('button', { name: '检查当前漫画书出版副本' }) as HTMLButtonElement;
  expect(button.disabled).toBe(true); act(retained(button)); expect(h.posts()).toHaveLength(0);
});

it.each(['format', 'dpi', 'direction'])('invalidates acknowledged PDF review and retained callbacks after %s changes', async field => {
  const h = harness(); render(<ComicCollectionTree {...h.props} />); await openBook(); await pdfPreflight(); pdfAck(); const oldDownload = retained(pdfDownload());
  if (field === 'format') fireEvent.change(screen.getByLabelText('出版副本格式'), { target: { value: 'CBZ' } });
  if (field === 'dpi') setDpi('72');
  if (field === 'direction') fireEvent.change(screen.getByLabelText('PDF 阅读方向'), { target: { value: 'LTR' } });
  act(oldDownload); expect(h.posts()).toHaveLength(1); expect(screen.queryByRole('button', { name: '下载已核对的 PDF' })).toBeNull();
  await pdfPreflight(); expect(pdfDownload().disabled).toBe(true); act(oldDownload); expect(h.posts()).toHaveLength(2);
  expect(saveOtioFile).not.toHaveBeenCalled();
});

it('invalidates the existing CBZ review when choosing PDF and cannot restore it by switching back', async () => {
  const h = harness(); render(<ComicCollectionTree {...h.props} />); await openBook(); await preflight(); ack(); const oldDownload = retained(download());
  choosePdf(); act(oldDownload); fireEvent.change(screen.getByLabelText('出版副本格式'), { target: { value: 'CBZ' } }); act(oldDownload);
  expect(screen.queryByRole('button', { name: '下载已核对的 CBZ' })).toBeNull(); expect(h.posts()).toHaveLength(1); expect(saveOtioFile).not.toHaveBeenCalled();
});

it.each(['format', 'dpi', 'missing_dimensions', 'dimension_count', 'pixel_width', 'pixel_height', 'point_width', 'point_height', 'non_numeric', 'missing_loss', 'page_order', 'page_version', 'book_version', 'publication_digest'])('fails closed on invalid PDF preflight %s', async field => {
  const report = initialPdfReport();
  if (field === 'format') (report as { format: string }).format = 'comic-cbz-v1';
  if (field === 'dpi') report.dpi = 72;
  if (field === 'missing_dimensions') delete (report as Partial<ComicPdfPublicationPreflight>).page_dimensions;
  if (field === 'dimension_count') report.page_dimensions.pop();
  if (field === 'pixel_width') report.page_dimensions[0].width_pixels++;
  if (field === 'pixel_height') report.page_dimensions[0].height_pixels++;
  if (field === 'point_width') report.page_dimensions[0].width_points++;
  if (field === 'point_height') report.page_dimensions[0].height_points = -1;
  if (field === 'non_numeric') (report.page_dimensions[0] as unknown as { width_points: string }).width_points = '400';
  if (field === 'missing_loss') report.losses.pop();
  if (field === 'page_order') report.pages.reverse();
  if (field === 'page_version') report.pages[0].version++;
  if (field === 'book_version') report.book_version++;
  if (field === 'publication_digest') report.publication_digest = '';
  const h = harness({ mutate: () => reply(report) }); render(<ComicCollectionTree {...h.props} />); await openBook(); choosePdf(); setDpi('144');
  fireEvent.change(screen.getByLabelText('PDF 阅读方向'), { target: { value: 'RTL' } }); fireEvent.click(screen.getByRole('button', { name: '检查当前漫画书出版副本' }));
  await screen.findByText(/COMIC_PUBLICATION_INVALID_RESPONSE/);
  expect(screen.queryByRole('button', { name: '下载已核对的 PDF' })).toBeNull(); expect(saveOtioFile).not.toHaveBeenCalled();
});

it.each(['owner', 'revision', 'records', 'dirty', 'external_busy', 'unmount', 'client'])('suppresses late PDF exports after %s invalidation', async reason => {
  let owner = true, revision = 0, finish: (response: Response) => void = () => {};
  const h = harness({ mutate: url => url.endsWith('/pdf-publication-preflight') ? reply(initialPdfReport()) : new Promise(resolve => { finish = resolve; }) });
  const props = { ...h.props, isOwnerCurrent: () => owner, getOwnerRevision: () => revision };
  const view = render(<ComicCollectionTree {...props} />); await openBook(); await pdfPreflight(); pdfAck(); fireEvent.click(pdfDownload());
  if (reason === 'owner') owner = false;
  if (reason === 'revision') revision++;
  if (reason === 'records') view.rerender(<ComicCollectionTree {...props} records={[page('p1', 5), page('p2', 6)]} />);
  if (reason === 'dirty') view.rerender(<ComicCollectionTree {...props} pageDirty />);
  if (reason === 'external_busy') view.rerender(<ComicCollectionTree {...props} externalBusy />);
  if (reason === 'unmount') view.unmount();
  if (reason === 'client') view.rerender(<ComicCollectionTree {...props} client={experimentalClient('other-novel', { sessionToken: 'other-session', scope: { workspaceId: 'w', projectId: 'other-novel', storylineId: 's', branchId: 'other-branch' } })} />);
  await act(async () => finish(await archive('PDF')));
  expect(saveOtioFile).not.toHaveBeenCalled(); expect(screen.queryByText('已校验并下载 PDF 合成图片副本。')).toBeNull();
});

it('discarded PDF preflight cannot replace a newer CBZ check or release its busy guard', async () => {
  const finishes: ((response: Response) => void)[] = [];
  const h = harness({ mutate: () => new Promise(resolve => { finishes.push(resolve); }) }); render(<ComicCollectionTree {...h.props} />); await openBook(); choosePdf(); setDpi('144');
  fireEvent.change(screen.getByLabelText('PDF 阅读方向'), { target: { value: 'RTL' } }); fireEvent.click(screen.getByRole('button', { name: '检查当前漫画书出版副本' }));
  expect((screen.getByLabelText('出版副本格式') as HTMLSelectElement).disabled).toBe(true);
  expect((screen.getByLabelText('PDF DPI（36–600 整数，需明确填写）') as HTMLInputElement).disabled).toBe(true);
  fireEvent.click(screen.getByRole('button', { name: '放弃本次出版结果' }));
  fireEvent.change(screen.getByLabelText('出版副本格式'), { target: { value: 'CBZ' } }); fireEvent.click(screen.getByRole('button', { name: '检查当前漫画书出版副本' }));
  await act(async () => finishes[0](reply(initialPdfReport())));
  expect(screen.queryByText('已检查 2 页 · RTL · 书结构 v3')).toBeNull(); expect(h.props.onBusyChange).toHaveBeenLastCalledWith(true);
  await act(async () => finishes[1](reply(initialReport())));
  await screen.findByText('已检查 2 页 · RTL · 书结构 v3'); expect(download().disabled).toBe(true); expect(h.props.onBusyChange).toHaveBeenLastCalledWith(false);
});

it('downloads PDF through the original mounted IMAGE owner with captured collaboration headers', async () => {
  const h = harness(); const onBusy = vi.fn();
  render(<StudioComicPanel projectId="novel" context={{ sessionToken: 'pdf-mounted-session', scope: { workspaceId: 'w', projectId: 'novel', storylineId: 's', branchId: 'pdf-mounted-branch' } }} isCurrent={() => true} onDirtyChange={vi.fn()} onBusyChange={onBusy} />);
  await openBook(); await pdfPreflight(); pdfAck(); fireEvent.click(pdfDownload());
  await screen.findByText('已校验并下载 PDF 合成图片副本。'); expect(saveOtioFile).toHaveBeenCalledTimes(1);
  expect(h.posts()[1][1].headers).toMatchObject({ 'X-Session-Token': 'pdf-mounted-session', 'X-Branch-Id': 'pdf-mounted-branch' });
  expect(onBusy).toHaveBeenLastCalledWith(false);
});

it.each([401, 403])('clears private book projections after mounted PDF export permission denial %s', async status => {
  const h = harness({ mutate: url => url.endsWith('/pdf-publication-preflight') ? reply(initialPdfReport()) : reply({ code: 'FORBIDDEN' }, status) });
  render(<StudioComicPanel projectId="novel" context={{ sessionToken: 'pdf-mounted-session' }} isCurrent={() => true} onDirtyChange={vi.fn()} onBusyChange={vi.fn()} />);
  await openBook(); await pdfPreflight(); pdfAck(); fireEvent.click(pdfDownload());
  await screen.findByText(/当前身份或分支没有漫画访问权限/);
  expect(screen.queryByRole('region', { name: '漫画书 PDF 导出' })).toBeNull(); expect(screen.queryByText(/出版测试书/)).toBeNull(); expect(saveOtioFile).not.toHaveBeenCalled();
});

it('cannot revive a PDF review or retained download after a book selection A–B–A round trip', async () => {
  const h = harness({ books: [initialBook(), { ...initialBook(), id: 'other-book', title: '另一本书' }] });
  render(<ComicCollectionTree {...h.props} />); await openBook(); await pdfPreflight(); pdfAck(); const oldDownload = retained(pdfDownload());
  fireEvent.click(screen.getByRole('button', { name: '打开漫画书 另一本书' })); act(oldDownload);
  fireEvent.click(screen.getByRole('button', { name: '打开漫画书 出版测试书' })); act(oldDownload); choosePdf();
  expect((screen.getByLabelText('PDF DPI（36–600 整数，需明确填写）') as HTMLInputElement).value).toBe('');
  expect(screen.queryByRole('button', { name: '下载已核对的 PDF' })).toBeNull(); expect(h.posts()).toHaveLength(1);
  await pdfPreflight(); pdfAck(); act(oldDownload); expect(h.posts()).toHaveLength(2); expect(saveOtioFile).not.toHaveBeenCalled();
});

it.each(['tree', 'page'])('cannot revive a PDF review after dirty %s state returns to clean', async kind => {
  const h = harness(); const view = render(<ComicCollectionTree {...h.props} />); await openBook(); await pdfPreflight(); pdfAck(); const oldDownload = retained(pdfDownload());
  if (kind === 'tree') fireEvent.change(screen.getByLabelText('漫画书名称'), { target: { value: '未保存书名' } });
  else view.rerender(<ComicCollectionTree {...h.props} pageDirty />);
  act(oldDownload); expect(screen.queryByRole('button', { name: '下载已核对的 PDF' })).toBeNull();
  if (kind === 'tree') fireEvent.click(screen.getByRole('button', { name: '放弃书结构修改' }));
  else view.rerender(<ComicCollectionTree {...h.props} />);
  act(oldDownload); expect(screen.queryByRole('button', { name: '下载已核对的 PDF' })).toBeNull(); expect(h.posts()).toHaveLength(1);
  await pdfPreflight(); expect(pdfDownload().disabled).toBe(true); expect(saveOtioFile).not.toHaveBeenCalled();
});

it('suppresses a late PDF preflight after page dirtiness returns to clean', async () => {
  let finish: (response: Response) => void = () => {};
  const h = harness({ mutate: () => new Promise(resolve => { finish = resolve; }) }); const view = render(<ComicCollectionTree {...h.props} />); await openBook(); choosePdf(); setDpi('144');
  fireEvent.change(screen.getByLabelText('PDF 阅读方向'), { target: { value: 'RTL' } }); fireEvent.click(screen.getByRole('button', { name: '检查当前漫画书出版副本' }));
  view.rerender(<ComicCollectionTree {...h.props} pageDirty />); view.rerender(<ComicCollectionTree {...h.props} />);
  await act(async () => finish(reply(initialPdfReport())));
  expect(screen.queryByRole('button', { name: '下载已核对的 PDF' })).toBeNull(); expect(screen.queryByText('已核对 PDF · 144 DPI')).toBeNull();
  expect(h.props.onBusyChange).toHaveBeenLastCalledWith(false);
});

it('requires a new PDF preflight after a server conflict while preserving saved book content', async () => {
  const h = harness({ mutate: url => url.endsWith('/pdf-publication-preflight') ? reply(initialPdfReport()) : reply({ code: 'COMIC_PUBLICATION_CHANGED' }, 409) });
  render(<ComicCollectionTree {...h.props} />); await openBook(); await pdfPreflight(); pdfAck(); fireEvent.click(pdfDownload());
  await screen.findByText(/COMIC_PUBLICATION_CHANGED/); expect(screen.queryByRole('button', { name: '下载已核对的 PDF' })).toBeNull();
  expect((screen.getByLabelText('漫画书名称') as HTMLInputElement).value).toBe('出版测试书'); expect(saveOtioFile).not.toHaveBeenCalled();
});

it.each(['DRAFT', 'WEBTOON', 'empty'])('blocks PDF %s collections before any publication POST', async state => {
  const pages = [page('p1', 4), page('p2', 6)];
  if (state === 'DRAFT') pages[0].status = 'DRAFT';
  if (state === 'WEBTOON') pages[0].document!.preset = 'WEBTOON';
  const h = harness({ pages, ...(state === 'empty' ? { book: { ...initialBook(), chapters: [] } } : {}) }); render(<ComicCollectionTree {...h.props} />); await openBook(); choosePdf(); setDpi('144');
  fireEvent.change(screen.getByLabelText('PDF 阅读方向'), { target: { value: 'RTL' } });
  const button = screen.getByRole('button', { name: '检查当前漫画书出版副本' }) as HTMLButtonElement;
  expect(button.disabled).toBe(true); act(retained(button)); expect(h.posts()).toHaveLength(0);
});

it('does not infer download permission from a removed PDF acknowledgement', async () => {
  const h = harness(); render(<ComicCollectionTree {...h.props} />); await openBook(); await pdfPreflight(); pdfAck(); const oldDownload = retained(pdfDownload());
  pdfAck(); act(oldDownload); expect(pdfDownload().disabled).toBe(true); expect(h.posts()).toHaveLength(1); expect(saveOtioFile).not.toHaveBeenCalled();
});
