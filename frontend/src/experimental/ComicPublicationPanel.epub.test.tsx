// @vitest-environment jsdom
import { webcrypto } from 'node:crypto';
import { Blob as NativeBlob } from 'node:buffer';
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { ComicCollectionTree } from './ComicCollectionTree';
import { ComicLayoutsPanel } from './ComicLayoutsPanel';
import { StudioComicPanel } from '../creative/StudioComicPanel';
import { experimentalClient } from './api';
import { blankComic, type ComicBook, type ComicEpubPublicationPreflight, type ComicRecord } from './comicLayoutsClient';
import { saveOtioFile } from './timelineExchangeClient';

vi.mock('./timelineExchangeClient', () => ({ saveOtioFile: vi.fn() }));
const settings = { width: 400, height: 560, safe_area: 24, segment_height: 560 };
const page = (id: string, version: number): ComicRecord => ({ id, version, status: 'APPROVED', stale: false, document: { ...blankComic('PAGE', settings), title: `页面 ${id}` } });
const book = (): ComicBook => ({ id: 'book', version: 3, stale: false, title: '格式测试书', chapters: [{ id: 'ch1', title: '第一章', pages: ['p2'] }, { id: 'ch2', title: '第二章', pages: ['p1'] }] });
const report = (): ComicEpubPublicationPreflight => ({ format: 'comic-epub-fixed-raster-v1', language: 'und', book_version: 3, reading_direction: 'RTL', pages: [{ id: 'p2', version: 6, review_digest: 'b'.repeat(64) }, { id: 'p1', version: 4, review_digest: 'a'.repeat(64) }], publication_digest: 'c'.repeat(64), page_count: 2,
  losses: ['FLATTENED_RGB_PNG_PAGES', 'NO_EDITABLE_OR_SEARCHABLE_TEXT', 'RASTER_ONLY_LIMITED_ACCESSIBILITY_NO_TEXT_ALTERNATIVE', 'DIRECTION_METADATA_DOES_NOT_REORDER_PAGES_OR_PANELS', 'NO_DPI_BLEED_COLOR_PROFILE_OR_PRINT_CONFORMANCE', 'SOURCE_IMAGE_RIGHTS_NOT_VERIFIED', 'LANGUAGE_UNSPECIFIED_UND', 'EPUBCHECK_NOT_RUN', 'EXTERNAL_READER_VALIDATION_NOT_RUN'],
  page_dimensions: [{ width_pixels: 400, height_pixels: 560 }, { width_pixels: 400, height_pixels: 560 }],
  epub_limits: { max_metadata_bytes: 1048576, max_output_bytes: 67108864, total_page_pixels: 448000, reserved_metadata_bytes: 24846, reserved_output_bytes: 2013454 },
});
const reply = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status });
async function archive() {
  const bytes = new TextEncoder().encode('test-epub-fixed-layout');
  const sha = Array.from(new Uint8Array(await webcrypto.subtle.digest('SHA-256', bytes)), byte => byte.toString(16).padStart(2, '0')).join('');
  return new Response(bytes, { headers: { 'Content-Type': 'application/epub+zip', 'X-Comic-Publication-Digest': 'c'.repeat(64), 'X-Content-SHA256': sha } });
}
beforeEach(() => { vi.stubGlobal('crypto', webcrypto); vi.stubGlobal('Blob', NativeBlob); vi.mocked(saveOtioFile).mockClear(); URL.createObjectURL = vi.fn(() => 'blob:test'); URL.revokeObjectURL = vi.fn(); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
function harness(options: { pages?: ComicRecord[]; books?: ComicBook[]; mutate?: (url: string, init: RequestInit) => Promise<Response> | Response } = {}) {
  const pages = options.pages || [page('p1', 4), page('p2', 6)];
  const fetch = vi.fn(async (url: string, init: RequestInit) => {
    if (init.method === 'GET') {
      if (url.endsWith('/books')) return reply({ items: options.books || [book()] });
      if (url.endsWith('/records')) return reply({ items: pages });
      if (url.endsWith('/catalog')) return reply({ screenplays: [], characters: [], assets: [], presets: { PAGE: settings, WEBTOON: settings }, renderer: { available: true }, font: { available: true } });
    }
    if (options.mutate) return options.mutate(url, init);
    if (url.endsWith('/epub-publication-preflight')) return reply({ ...report(), reading_direction: JSON.parse(String(init.body)).reading_direction });
    if (url.endsWith('/export-epub')) return archive();
    return reply({}, 404);
  });
  vi.stubGlobal('fetch', fetch);
  const props = { client: experimentalClient('novel', { sessionToken: 'trusted', scope: { workspaceId: 'w', projectId: 'novel', storylineId: 's', branchId: 'branch' } }), records: pages, recordsReady: true, pageDirty: false, externalBusy: false, getOwnerRevision: () => 0, onActiveChange: vi.fn(), onDirtyChange: vi.fn(), onBusyChange: vi.fn(), onOpenPage: vi.fn(), onPageCreated: vi.fn() };
  return { fetch, props, posts: () => fetch.mock.calls.filter(([, init]) => init.method === 'POST') };
}
async function openBook() { await waitFor(() => { const button = screen.getByRole('button', { name: '打开漫画书 格式测试书' }) as HTMLButtonElement; expect(button.disabled).toBe(false); fireEvent.click(button); expect(screen.getByRole('region', { name: '漫画书 CBZ 导出' })).toBeTruthy(); }); }
const change = (label: string, value: string) => fireEvent.change(screen.getByLabelText(label), { target: { value } });
const check = () => screen.getByRole('button', { name: '检查当前漫画书出版副本' }) as HTMLButtonElement;
const download = () => screen.getByRole('button', { name: '下载已核对的 EPUB' }) as HTMLButtonElement;
const languageLabel = 'EPUB 内容语言（需明确选择）';
const ack = () => fireEvent.click(screen.getByRole('checkbox', { name: '已核对以上已保存页面顺序、阅读方向、未指定语言、固定版式尺寸及 EPUB 栅格与无障碍限制' }));
function choose(direction = 'RTL') { change('出版副本格式', 'EPUB'); change('EPUB 阅读方向', direction); change(languageLabel, 'und'); }
async function preflight(direction = 'RTL') { choose(direction); fireEvent.click(check()); await screen.findByText(`已检查 2 页 · ${direction} · 书结构 v3`); }
function retained(element: HTMLElement): () => void { const key = Object.keys(element).find(value => value.startsWith('__reactProps'))!; return (element as unknown as Record<string, { onClick: () => void }>)[key].onClick; }

it.each(['LTR', 'RTL'])('requires explicit EPUB language, %s direction and current review; saves one verified file for duplicate clicks', async direction => {
  const h = harness(); render(<ComicCollectionTree {...h.props} />); await openBook();
  expect(h.posts()).toHaveLength(0); change('出版副本格式', 'EPUB');
  expect(screen.getByText(/文字无法搜索或编辑；无文字替代内容，无障碍支持有限/)).toBeTruthy();
  expect(screen.getByText(/独立 EPUBCheck 验收：NOT_RUN；外部阅读器验收：NOT_RUN/)).toBeTruthy();
  expect(screen.getByText(/总页面像素 × 4 字节 \+ 每页 65,536 字节 \+ 元数据预留 \+ 65,536 字节/)).toBeTruthy();
  expect(screen.getByText(/100 页书结构上限不保证可导出 100 张高分辨率页面/)).toBeTruthy();
  expect((screen.getByLabelText(languageLabel) as HTMLSelectElement).value).toBe('');
  expect(check().disabled).toBe(true); act(retained(check()));
  change('EPUB 阅读方向', direction); expect(check().disabled).toBe(true); act(retained(check())); expect(h.posts()).toHaveLength(0);
  change(languageLabel, 'und'); expect(check().disabled).toBe(false);
  const checkTwice = retained(check()); await act(async () => { checkTwice(); checkTwice(); }); await screen.findByText(`已检查 2 页 · ${direction} · 书结构 v3`);
  expect(h.posts()).toHaveLength(1);
  expect(within(screen.getByRole('list', { name: 'EPUB 已保存页面顺序' })).getAllByRole('listitem').map(item => item.textContent)).toEqual(['1.1 · 第一章 · 页面 p2 · v6', '2.1 · 第二章 · 页面 p1 · v4']);
  expect(within(screen.getByRole('list', { name: 'EPUB 已检查页面尺寸' })).getAllByRole('listitem')).toHaveLength(2);
  expect(within(screen.getByRole('list', { name: 'EPUB 导出限制' })).getAllByRole('listitem')).toHaveLength(9);
  expect(download().disabled).toBe(true); ack(); const clickTwice = retained(download());
  await act(async () => { clickTwice(); clickTwice(); }); await screen.findByText('已校验并下载 EPUB 合成图片副本。');
  expect(h.posts().map(([url]) => url.split('/').pop())).toEqual(['epub-publication-preflight', 'export-epub']);
  expect(JSON.parse(String(h.posts()[0][1].body))).toEqual({ expected_version: 3, reading_direction: direction, format: 'comic-epub-fixed-raster-v1', language: 'und' });
  expect(JSON.parse(String(h.posts()[1][1].body))).toEqual({ expected_version: 3, reading_direction: direction, format: 'comic-epub-fixed-raster-v1', language: 'und', pages: report().pages, publication_digest: report().publication_digest });
  expect(saveOtioFile).toHaveBeenCalledOnce(); expect(saveOtioFile).toHaveBeenCalledWith(expect.objectContaining({ type: 'application/epub+zip' }), 'comic-book.epub');
  expect(h.props.onDirtyChange).not.toHaveBeenCalledWith(true); expect(h.props.onBusyChange).toHaveBeenLastCalledWith(false);
});

it.each(['format', 'language', 'direction', 'dirty', 'book'])('cannot revive an EPUB review or retained download after %s A–B–A', async field => {
  const h = harness({ books: [book(), { ...book(), id: 'other', title: '另一本书' }] }); const view = render(<ComicCollectionTree {...h.props} />); await openBook(); await preflight(); ack(); const old = retained(download());
  if (field === 'format') { change('出版副本格式', 'PDF'); change('出版副本格式', 'EPUB'); expect((screen.getByLabelText(languageLabel) as HTMLSelectElement).value).toBe(''); }
  if (field === 'language') { change(languageLabel, ''); change(languageLabel, 'und'); }
  if (field === 'direction') { change('EPUB 阅读方向', 'LTR'); change('EPUB 阅读方向', 'RTL'); }
  if (field === 'dirty') { view.rerender(<ComicCollectionTree {...h.props} pageDirty />); view.rerender(<ComicCollectionTree {...h.props} />); }
  if (field === 'book') { fireEvent.click(screen.getByRole('button', { name: '打开漫画书 另一本书' })); fireEvent.click(screen.getByRole('button', { name: '打开漫画书 格式测试书' })); }
  act(old); expect(h.posts()).toHaveLength(1); expect(screen.queryByRole('button', { name: '下载已核对的 EPUB' })).toBeNull();
  await preflight(); expect(download().disabled).toBe(true); ack(); act(old); expect(h.posts()).toHaveLength(2); expect(saveOtioFile).not.toHaveBeenCalled();
});

it.each(['format', 'language', 'missing_language', 'losses', 'dimensions', 'width', 'height', 'zero_dimension', 'missing_limits', 'max_metadata', 'max_output', 'total_pixels', 'reserved_metadata', 'oversized_metadata', 'reserved_output', 'oversized_output', 'page_order', 'page_version', 'book_version', 'reading_direction', 'publication_digest'])('fails closed on EPUB preflight %s drift', async field => {
  const receipt = report();
  if (field === 'format') (receipt as { format: string }).format = 'comic-pdf-raster-v1';
  if (field === 'language') (receipt as { language: string }).language = 'en';
  if (field === 'missing_language') delete (receipt as Partial<ComicEpubPublicationPreflight>).language;
  if (field === 'losses') receipt.losses.pop();
  if (field === 'dimensions') receipt.page_dimensions.pop();
  if (field === 'width') receipt.page_dimensions[0].width_pixels++;
  if (field === 'height') receipt.page_dimensions[0].height_pixels++;
  if (field === 'zero_dimension') receipt.page_dimensions[0].width_pixels = 0;
  if (field === 'missing_limits') delete (receipt as Partial<ComicEpubPublicationPreflight>).epub_limits;
  if (field === 'max_metadata') receipt.epub_limits.max_metadata_bytes++;
  if (field === 'max_output') receipt.epub_limits.max_output_bytes++;
  if (field === 'total_pixels') receipt.epub_limits.total_page_pixels++;
  if (field === 'reserved_metadata') receipt.epub_limits.reserved_metadata_bytes = 0;
  if (field === 'oversized_metadata') receipt.epub_limits.reserved_metadata_bytes = 1048577;
  if (field === 'reserved_output') receipt.epub_limits.reserved_output_bytes++;
  if (field === 'oversized_output') receipt.epub_limits.reserved_output_bytes = 67108865;
  if (field === 'page_order') receipt.pages.reverse();
  if (field === 'page_version') receipt.pages[0].version++;
  if (field === 'book_version') receipt.book_version++;
  if (field === 'reading_direction') receipt.reading_direction = 'LTR';
  if (field === 'publication_digest') receipt.publication_digest = '';
  const h = harness({ mutate: () => reply(receipt) }); render(<ComicCollectionTree {...h.props} />); await openBook(); choose(); fireEvent.click(check());
  await screen.findByText(/COMIC_PUBLICATION_INVALID_RESPONSE/); expect(screen.queryByRole('button', { name: '下载已核对的 EPUB' })).toBeNull(); expect(saveOtioFile).not.toHaveBeenCalled();
});

it.each(['DRAFT', 'WEBTOON', 'stale', 'empty'])('blocks unpublishable EPUB %s before any POST', async reason => {
  const pages = [page('p1', 4), page('p2', 6)], currentBook = book();
  if (reason === 'DRAFT') pages[0].status = 'DRAFT';
  if (reason === 'WEBTOON') pages[0].document!.preset = 'WEBTOON';
  if (reason === 'stale') pages[0].stale = true;
  if (reason === 'empty') currentBook.chapters = [];
  const h = harness({ pages, books: [currentBook] }); render(<ComicCollectionTree {...h.props} />);
  if (reason === 'stale') { await screen.findByText('漫画书或引用页面不可用，标题与结构已隐藏。'); expect(screen.queryByLabelText('出版副本格式')).toBeNull(); expect(h.posts()).toHaveLength(0); return; }
  await openBook(); choose(); expect(check().disabled).toBe(true); act(retained(check())); expect(h.posts()).toHaveLength(0);
});

it.each(['owner', 'revision', 'records', 'dirty', 'external_busy', 'unmount', 'client', 'discard'])('suppresses late EPUB exports after %s invalidation', async reason => {
  let owner = true, revision = 0, finish: (response: Response) => void = () => {};
  const h = harness({ mutate: url => url.endsWith('/epub-publication-preflight') ? reply(report()) : new Promise(resolve => { finish = resolve; }) });
  const props = { ...h.props, isOwnerCurrent: () => owner, getOwnerRevision: () => revision };
  const view = render(<ComicCollectionTree {...props} />); await openBook(); await preflight(); ack(); fireEvent.click(download());
  if (reason === 'owner') owner = false;
  if (reason === 'revision') revision++;
  if (reason === 'records') view.rerender(<ComicCollectionTree {...props} records={[page('p1', 5), page('p2', 6)]} />);
  if (reason === 'dirty') view.rerender(<ComicCollectionTree {...props} pageDirty />);
  if (reason === 'external_busy') view.rerender(<ComicCollectionTree {...props} externalBusy />);
  if (reason === 'unmount') view.unmount();
  if (reason === 'client') view.rerender(<ComicCollectionTree {...props} client={experimentalClient('other', { sessionToken: 'other' })} />);
  if (reason === 'discard') fireEvent.click(screen.getByRole('button', { name: '放弃本次出版结果' }));
  await act(async () => finish(await archive())); expect(saveOtioFile).not.toHaveBeenCalled(); expect(screen.queryByText('已校验并下载 EPUB 合成图片副本。')).toBeNull();
});

it('discarded EPUB preflight cannot replace a newer direction check or release its busy guard', async () => {
  const finishes: ((response: Response) => void)[] = [];
  const h = harness({ mutate: () => new Promise(resolve => { finishes.push(resolve); }) }); render(<ComicCollectionTree {...h.props} />); await openBook(); choose(); fireEvent.click(check());
  expect((screen.getByLabelText(languageLabel) as HTMLSelectElement).disabled).toBe(true);
  expect((screen.getByLabelText('出版副本格式') as HTMLSelectElement).disabled).toBe(true);
  fireEvent.click(screen.getByRole('button', { name: '放弃本次出版结果' })); change('EPUB 阅读方向', 'LTR'); fireEvent.click(check());
  await act(async () => finishes[0](reply(report()))); expect(screen.queryByText('已检查 2 页 · RTL · 书结构 v3')).toBeNull(); expect(h.props.onBusyChange).toHaveBeenLastCalledWith(true);
  await act(async () => finishes[1](reply({ ...report(), reading_direction: 'LTR' }))); await screen.findByText('已检查 2 页 · LTR · 书结构 v3'); expect(download().disabled).toBe(true); expect(h.props.onBusyChange).toHaveBeenLastCalledWith(false);
});

it('keeps the original editor busy during EPUB checks and survives its own owner revision', async () => {
  let finish: (response: Response) => void = () => {};
  const h = harness({ mutate: url => url.endsWith('/epub-publication-preflight') ? new Promise(resolve => { finish = resolve; }) : archive() });
  const onBusy = vi.fn(); render(<ComicLayoutsPanel client={h.props.client} onBusyChange={onBusy} />); await openBook(); choose(); fireEvent.click(check());
  expect((screen.getByRole('button', { name: '新建空白漫画页' }) as HTMLButtonElement).disabled).toBe(true);
  expect((screen.getByRole('button', { name: '刷新漫画书' }) as HTMLButtonElement).disabled).toBe(true);
  await act(async () => finish(reply(report()))); await screen.findByText('已检查 2 页 · RTL · 书结构 v3'); ack(); fireEvent.click(download());
  await screen.findByText('已校验并下载 EPUB 合成图片副本。'); expect(saveOtioFile).toHaveBeenCalledOnce(); expect(onBusy).toHaveBeenLastCalledWith(false);
});

it('downloads EPUB through the mounted IMAGE owner with the captured session and branch', async () => {
  const h = harness(), onBusy = vi.fn();
  render(<StudioComicPanel projectId="novel" context={{ sessionToken: 'mounted-session', scope: { workspaceId: 'w', projectId: 'novel', storylineId: 's', branchId: 'mounted-branch' } }} isCurrent={() => true} onDirtyChange={vi.fn()} onBusyChange={onBusy} />);
  await openBook(); await preflight(); ack(); fireEvent.click(download()); await screen.findByText('已校验并下载 EPUB 合成图片副本。');
  expect(h.posts()[1][1].headers).toMatchObject({ 'X-Session-Token': 'mounted-session', 'X-Branch-Id': 'mounted-branch' }); expect(saveOtioFile).toHaveBeenCalledOnce(); expect(onBusy).toHaveBeenLastCalledWith(false);
});

it.each([401, 403])('removes private projections after mounted EPUB permission denial %s', async status => {
  const h = harness({ mutate: url => url.endsWith('/epub-publication-preflight') ? reply(report()) : reply({ code: 'FORBIDDEN' }, status) });
  render(<StudioComicPanel projectId="novel" context={{ sessionToken: 'mounted-session' }} isCurrent={() => true} onDirtyChange={vi.fn()} onBusyChange={vi.fn()} />);
  await openBook(); await preflight(); ack(); fireEvent.click(download()); await screen.findByText(/当前身份或分支没有漫画访问权限/);
  expect(screen.queryByRole('region', { name: '漫画书 EPUB 导出' })).toBeNull(); expect(screen.queryByText(/格式测试书/)).toBeNull(); expect(saveOtioFile).not.toHaveBeenCalled(); expect(h.posts()).toHaveLength(2);
});

it('requires new EPUB preflight after conflict without losing the saved book', async () => {
  const h = harness({ mutate: url => url.endsWith('/epub-publication-preflight') ? reply(report()) : reply({ code: 'COMIC_PUBLICATION_CHANGED' }, 409) });
  render(<ComicCollectionTree {...h.props} />); await openBook(); await preflight(); ack(); fireEvent.click(download()); await screen.findByText(/COMIC_PUBLICATION_CHANGED/);
  expect(screen.queryByRole('button', { name: '下载已核对的 EPUB' })).toBeNull(); expect((screen.getByLabelText('漫画书名称') as HTMLInputElement).value).toBe('格式测试书'); expect(saveOtioFile).not.toHaveBeenCalled();
});

it('revokes EPUB acknowledgement before retained downloads and keeps same-value controls as no-ops', async () => {
  const h = harness(); render(<ComicCollectionTree {...h.props} />); await openBook(); await preflight(); ack();
  change('出版副本格式', 'EPUB'); change('EPUB 阅读方向', 'RTL'); change(languageLabel, 'und'); expect(download().disabled).toBe(false);
  const old = retained(download()); ack(); act(old); expect(download().disabled).toBe(true); expect(h.posts()).toHaveLength(1); expect(saveOtioFile).not.toHaveBeenCalled();
});

it.each(['owner', 'revision', 'records', 'dirty', 'external_busy', 'unmount', 'client'])('ignores late EPUB preflight after %s invalidation', async reason => {
  let owner = true, revision = 0, finish: (response: Response) => void = () => {};
  const h = harness({ mutate: () => new Promise(resolve => { finish = resolve; }) });
  const props = { ...h.props, isOwnerCurrent: () => owner, getOwnerRevision: () => revision };
  const view = render(<ComicCollectionTree {...props} />); await openBook(); choose(); fireEvent.click(check());
  if (reason === 'owner') owner = false;
  if (reason === 'revision') revision++;
  if (reason === 'records') view.rerender(<ComicCollectionTree {...props} records={[page('p1', 5), page('p2', 6)]} />);
  if (reason === 'dirty') view.rerender(<ComicCollectionTree {...props} pageDirty />);
  if (reason === 'external_busy') view.rerender(<ComicCollectionTree {...props} externalBusy />);
  if (reason === 'unmount') view.unmount();
  if (reason === 'client') view.rerender(<ComicCollectionTree {...props} client={experimentalClient('other', { sessionToken: 'other' })} />);
  await act(async () => finish(reply(report())));
  expect(screen.queryByRole('button', { name: '下载已核对的 EPUB' })).toBeNull(); expect(screen.queryByText('已检查 2 页 · RTL · 书结构 v3')).toBeNull(); expect(saveOtioFile).not.toHaveBeenCalled();
});
