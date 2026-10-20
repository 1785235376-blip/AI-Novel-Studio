// @vitest-environment jsdom
import { webcrypto } from 'node:crypto';
import { Blob as NativeBlob } from 'node:buffer';
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { ComicCollectionTree } from './ComicCollectionTree';
import { StudioComicPanel } from '../creative/StudioComicPanel';
import { experimentalClient } from './api';
import { blankComic, type ComicBook, type ComicPageArchiveOptions, type ComicPageArchivePreflight, type ComicRecord } from './comicLayoutsClient';
import { saveOtioFile } from './timelineExchangeClient';

vi.mock('./timelineExchangeClient', () => ({ saveOtioFile: vi.fn() }));
const settings = { width: 400, height: 560, safe_area: 24, segment_height: 560 };
const page = (id: string, version: number): ComicRecord => ({ id, version, status: 'APPROVED', stale: false, document: { ...blankComic('PAGE', settings), title: `页面 ${id}` } });
const book = (): ComicBook => ({ id: 'book', version: 3, stale: false, title: '格式测试书', chapters: [{ id: 'ch1', title: '第一章', pages: ['p2'] }, { id: 'ch2', title: '第二章', pages: ['p1'] }] });
const jpeg: ComicPageArchiveOptions = { image_format: 'JPEG', loss_mode: 'LOSSY', quality: 100 };
const webp: ComicPageArchiveOptions = { image_format: 'WEBP', loss_mode: 'LOSSY', quality: 80 };
const lossless: ComicPageArchiveOptions = { image_format: 'WEBP', loss_mode: 'LOSSLESS', quality: null };
const report = (options: ComicPageArchiveOptions = jpeg): ComicPageArchivePreflight => ({ ...options, format: 'comic-page-archive-v1', book_version: 3, reading_direction: 'RTL', pages: [{ id: 'p2', version: 6, review_digest: 'b'.repeat(64) }, { id: 'p1', version: 4, review_digest: 'a'.repeat(64) }], publication_digest: 'c'.repeat(64), page_count: 2,
  losses: ['FLATTENED_RGB_RASTER_PAGES', 'NO_EDITABLE_LAYERS_OR_TEXT', 'DIRECTION_METADATA_DOES_NOT_REORDER_PAGES_OR_PANELS', 'NO_COLOR_PROFILE_OR_PRINT_FIDELITY', 'SOURCE_IMAGE_RIGHTS_NOT_VERIFIED', 'EXTERNAL_READER_VALIDATION_NOT_RUN', options.loss_mode === 'LOSSLESS' ? 'PIXEL_EXACT_FLATTENED_RGB_ONLY' : 'LOSSY_PIXELS_INCLUDING_QUALITY_100'],
  page_archive_limits: { max_total_page_pixels: 1048576, max_pages: 8, max_side_pixels: 2048, max_codec_work_bytes: 536870912, max_output_bytes: 67108864, total_page_pixels: 448000, reserved_codec_work_bytes: 131465216, reserved_output_bytes: 7909376 },
});
const reply = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status });
async function archive() {
  const bytes = new TextEncoder().encode('test-page-archive');
  const sha = Array.from(new Uint8Array(await webcrypto.subtle.digest('SHA-256', bytes)), byte => byte.toString(16).padStart(2, '0')).join('');
  return new Response(bytes, { headers: { 'Content-Type': 'application/zip', 'X-Comic-Publication-Digest': 'c'.repeat(64), 'X-Content-SHA256': sha } });
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
    if (url.endsWith('/page-archive-preflight')) {
      const { image_format, loss_mode, quality, reading_direction } = JSON.parse(String(init.body));
      return reply({ ...report({ image_format, loss_mode, quality }), reading_direction });
    }
    if (url.endsWith('/export-page-archive')) return archive();
    return reply({}, 404);
  });
  vi.stubGlobal('fetch', fetch);
  const props = { client: experimentalClient('novel', { sessionToken: 'trusted', scope: { workspaceId: 'w', projectId: 'novel', storylineId: 's', branchId: 'branch' } }), records: pages, recordsReady: true, pageDirty: false, externalBusy: false, getOwnerRevision: () => 0, onActiveChange: vi.fn(), onDirtyChange: vi.fn(), onBusyChange: vi.fn(), onOpenPage: vi.fn(), onPageCreated: vi.fn() };
  return { fetch, props, posts: () => fetch.mock.calls.filter(([, init]) => init.method === 'POST') };
}
async function openBook() {
  await waitFor(() => { const button = screen.getByRole('button', { name: '打开漫画书 格式测试书' }) as HTMLButtonElement; expect(button.disabled).toBe(false); fireEvent.click(button); expect(screen.getByRole('region', { name: '漫画书 CBZ 导出' })).toBeTruthy(); });
}
const change = (label: string, value: string) => fireEvent.change(screen.getByLabelText(label), { target: { value } });
const check = () => screen.getByRole('button', { name: '检查当前漫画书出版副本' }) as HTMLButtonElement;
const download = (format = 'JPEG') => screen.getByRole('button', { name: `下载已核对的 ${format} ZIP` }) as HTMLButtonElement;
const ack = () => fireEvent.click(screen.getByRole('checkbox', { name: '已核对以上已保存页面顺序、阅读方向、编码格式、损失模式、质量与 ZIP 阅读副本限制' }));
function choose(options: ComicPageArchiveOptions = jpeg) {
  change('出版副本格式', options.image_format);
  change(`${options.image_format} 阅读方向`, 'RTL');
  if (options.image_format === 'WEBP') change('WebP 编码模式', options.loss_mode);
  if (options.loss_mode === 'LOSSY') change(`${options.image_format} 有损质量`, String(options.quality));
}
async function preflight(options: ComicPageArchiveOptions = jpeg) { choose(options); fireEvent.click(check()); await screen.findByText('已检查 2 页 · RTL · 书结构 v3'); }
function retained(element: HTMLElement): () => void { const key = Object.keys(element).find(value => value.startsWith('__reactProps'))!; return (element as unknown as Record<string, { onClick: () => void }>)[key].onClick; }

it.each([jpeg, webp, lossless])('reviews ordered $image_format/$loss_mode/$quality and saves one verified ZIP with exact pins', async options => {
  const h = harness(); render(<ComicCollectionTree {...h.props} />); await openBook();
  expect(h.posts()).toHaveLength(0); choose(options); expect(h.posts()).toHaveLength(0);
  expect(screen.getByText(/JPEG 始终有损，质量 100 仍会改变像素/)).toBeTruthy();
  expect(screen.getByText(/不保留原色彩配置文件，不保证色彩或印刷保真/)).toBeTruthy();
  expect(screen.getByText(/总页面像素最多 1,048,576/)).toBeTruthy();
  if (options.loss_mode === 'LOSSLESS') expect(screen.queryByLabelText('WEBP 有损质量')).toBeNull();
  await preflight(options);
  expect(within(screen.getByRole('list', { name: `${options.image_format} 已保存页面顺序` })).getAllByRole('listitem').map(item => item.textContent)).toEqual(['1.1 · 第一章 · 页面 p2 · v6', '2.1 · 第二章 · 页面 p1 · v4']);
  expect(within(screen.getByRole('list', { name: `${options.image_format} 导出限制` })).getAllByRole('listitem')).toHaveLength(7);
  expect(download(options.image_format).disabled).toBe(true); ack(); const click = retained(download(options.image_format));
  await act(async () => { click(); click(); }); await screen.findByText(`已校验并下载 ${options.image_format} 页面 ZIP 阅读副本。`);
  expect(h.posts().map(([url]) => url.split('/').pop())).toEqual(['page-archive-preflight', 'export-page-archive']);
  expect(JSON.parse(String(h.posts()[0][1].body))).toEqual({ expected_version: 3, reading_direction: 'RTL', ...options });
  expect(JSON.parse(String(h.posts()[1][1].body))).toEqual({ expected_version: 3, reading_direction: 'RTL', ...options, pages: report().pages, publication_digest: report().publication_digest });
  expect(saveOtioFile).toHaveBeenCalledTimes(1); expect(saveOtioFile).toHaveBeenCalledWith(expect.objectContaining({ type: 'application/zip' }), `comic-book-${options.image_format.toLowerCase()}.zip`);
  expect(h.props.onDirtyChange).not.toHaveBeenCalledWith(true); expect(h.props.onBusyChange).toHaveBeenLastCalledWith(false);
});

it.each(['JPEG', 'WEBP'])('requires explicit %s encoding choices before any POST', async format => {
  const h = harness(); render(<ComicCollectionTree {...h.props} />); await openBook(); change('出版副本格式', format); change(`${format} 阅读方向`, 'RTL');
  expect(check().disabled).toBe(true); act(retained(check())); expect(h.posts()).toHaveLength(0);
  if (format === 'WEBP') { change('WebP 编码模式', 'LOSSY'); expect(check().disabled).toBe(true); act(retained(check())); }
  expect((screen.getByLabelText(`${format} 有损质量`) as HTMLSelectElement).value).toBe('');
  change(`${format} 有损质量`, '60'); expect(check().disabled).toBe(false); expect(h.posts()).toHaveLength(0);
});

it.each(['format', 'quality', 'mode', 'direction'])('invalidates acknowledged archive review and retained callbacks after %s changes', async field => {
  const h = harness(); render(<ComicCollectionTree {...h.props} />); await openBook(); await preflight(webp); ack(); const oldDownload = retained(download('WEBP'));
  if (field === 'format') change('出版副本格式', 'JPEG');
  if (field === 'quality') change('WEBP 有损质量', '95');
  if (field === 'mode') change('WebP 编码模式', 'LOSSLESS');
  if (field === 'direction') change('WEBP 阅读方向', 'LTR');
  act(oldDownload); expect(h.posts()).toHaveLength(1); expect(screen.queryByRole('button', { name: '下载已核对的 WEBP ZIP' })).toBeNull();
  await preflight(webp); expect(download('WEBP').disabled).toBe(true); act(oldDownload); expect(h.posts()).toHaveLength(2); expect(saveOtioFile).not.toHaveBeenCalled();
});

it('does not revive lossy quality or approval after a WebP lossless round trip', async () => {
  const h = harness(); render(<ComicCollectionTree {...h.props} />); await openBook(); await preflight(webp); ack(); const oldDownload = retained(download('WEBP'));
  change('WebP 编码模式', 'LOSSLESS'); change('WebP 编码模式', 'LOSSY');
  expect((screen.getByLabelText('WEBP 有损质量') as HTMLSelectElement).value).toBe(''); expect(check().disabled).toBe(true);
  act(oldDownload); expect(h.posts()).toHaveLength(1); expect(saveOtioFile).not.toHaveBeenCalled();
});

it.each(['format', 'image_format', 'loss_mode', 'quality', 'missing_quality', 'missing_loss', 'missing_limits', 'max_pixels', 'max_pages', 'max_side', 'max_work', 'max_output', 'total_pixels', 'reserved_work', 'reserved_output', 'page_order', 'page_version', 'book_version', 'reading_direction', 'publication_digest'])('fails closed on archive preflight %s', async field => {
  const receipt = report();
  if (field === 'format') (receipt as { format: string }).format = 'comic-pdf-raster-v1';
  if (field === 'image_format') receipt.image_format = 'WEBP';
  if (field === 'loss_mode') (receipt as { loss_mode: string }).loss_mode = 'LOSSLESS';
  if (field === 'quality') receipt.quality = 80;
  if (field === 'missing_quality') delete (receipt as Partial<ComicPageArchivePreflight>).quality;
  if (field === 'missing_loss') receipt.losses.pop();
  if (field === 'missing_limits') delete (receipt as Partial<ComicPageArchivePreflight>).page_archive_limits;
  if (field === 'max_pixels') receipt.page_archive_limits.max_total_page_pixels++;
  if (field === 'max_pages') receipt.page_archive_limits.max_pages++;
  if (field === 'max_side') receipt.page_archive_limits.max_side_pixels++;
  if (field === 'max_work') receipt.page_archive_limits.max_codec_work_bytes++;
  if (field === 'max_output') receipt.page_archive_limits.max_output_bytes++;
  if (field === 'total_pixels') receipt.page_archive_limits.total_page_pixels++;
  if (field === 'reserved_work') receipt.page_archive_limits.reserved_codec_work_bytes++;
  if (field === 'reserved_output') receipt.page_archive_limits.reserved_output_bytes++;
  if (field === 'page_order') receipt.pages.reverse();
  if (field === 'page_version') receipt.pages[0].version++;
  if (field === 'book_version') receipt.book_version++;
  if (field === 'reading_direction') receipt.reading_direction = 'LTR';
  if (field === 'publication_digest') receipt.publication_digest = '';
  const h = harness({ mutate: () => reply(receipt) }); render(<ComicCollectionTree {...h.props} />); await openBook(); choose(); fireEvent.click(check());
  await screen.findByText(/COMIC_PUBLICATION_INVALID_RESPONSE/); expect(screen.queryByRole('button', { name: '下载已核对的 JPEG ZIP' })).toBeNull(); expect(saveOtioFile).not.toHaveBeenCalled();
});

it.each(['DRAFT', 'WEBTOON', 'pixels', 'side', 'pages'])('blocks inadmissible archive %s before POST, including retained handlers', async reason => {
  const pages = [page('p1', 4), page('p2', 6)], currentBook = book();
  if (reason === 'DRAFT') pages[0].status = 'DRAFT';
  if (reason === 'WEBTOON') pages[0].document!.preset = 'WEBTOON';
  if (reason === 'pixels') pages.forEach(item => { item.document!.width = 800; item.document!.height = 1120; });
  if (reason === 'side') { pages[0].document!.width = 2049; pages[0].document!.height = 100; }
  if (reason === 'pages') { for (let i = 3; i <= 9; i++) { pages.push(page(`p${i}`, 1)); currentBook.chapters![0].pages.push(`p${i}`); } pages.forEach(item => { item.document!.width = 100; item.document!.height = 100; }); }
  const h = harness({ pages, books: [currentBook] }); render(<ComicCollectionTree {...h.props} />); await openBook(); choose(); expect(check().disabled).toBe(true); act(retained(check())); expect(h.posts()).toHaveLength(0);
});

it.each(['owner', 'revision', 'records', 'dirty', 'external_busy', 'unmount', 'client'])('suppresses late archive exports after %s invalidation', async reason => {
  let owner = true, revision = 0, finish: (response: Response) => void = () => {};
  const h = harness({ mutate: url => url.endsWith('/page-archive-preflight') ? reply(report()) : new Promise(resolve => { finish = resolve; }) });
  const props = { ...h.props, isOwnerCurrent: () => owner, getOwnerRevision: () => revision };
  const view = render(<ComicCollectionTree {...props} />); await openBook(); await preflight(); ack(); fireEvent.click(download());
  if (reason === 'owner') owner = false;
  if (reason === 'revision') revision++;
  if (reason === 'records') view.rerender(<ComicCollectionTree {...props} records={[page('p1', 5), page('p2', 6)]} />);
  if (reason === 'dirty') view.rerender(<ComicCollectionTree {...props} pageDirty />);
  if (reason === 'external_busy') view.rerender(<ComicCollectionTree {...props} externalBusy />);
  if (reason === 'unmount') view.unmount();
  if (reason === 'client') view.rerender(<ComicCollectionTree {...props} client={experimentalClient('other', { sessionToken: 'other', scope: { workspaceId: 'w', projectId: 'other', storylineId: 's', branchId: 'other' } })} />);
  await act(async () => finish(await archive())); expect(saveOtioFile).not.toHaveBeenCalled(); expect(screen.queryByText('已校验并下载 JPEG 页面 ZIP 阅读副本。')).toBeNull();
});

it('discarded JPEG preflight cannot replace a newer lossless WebP check or release its busy guard', async () => {
  const finishes: ((response: Response) => void)[] = [];
  const h = harness({ mutate: () => new Promise(resolve => { finishes.push(resolve); }) }); render(<ComicCollectionTree {...h.props} />); await openBook(); choose(); fireEvent.click(check());
  expect((screen.getByLabelText('JPEG 有损质量') as HTMLSelectElement).disabled).toBe(true);
  expect((screen.getByLabelText('出版副本格式') as HTMLSelectElement).disabled).toBe(true);
  fireEvent.click(screen.getByRole('button', { name: '放弃本次出版结果' })); choose(lossless); fireEvent.click(check());
  await act(async () => finishes[0](reply(report()))); expect(screen.queryByText('已检查 2 页 · RTL · 书结构 v3')).toBeNull(); expect(h.props.onBusyChange).toHaveBeenLastCalledWith(true);
  await act(async () => finishes[1](reply(report(lossless)))); await screen.findByText('已检查 2 页 · RTL · 书结构 v3'); expect(download('WEBP').disabled).toBe(true); expect(h.props.onBusyChange).toHaveBeenLastCalledWith(false);
});

it('downloads lossless WebP through the original mounted IMAGE owner with captured scope', async () => {
  const h = harness(); const onBusy = vi.fn();
  render(<StudioComicPanel projectId="novel" context={{ sessionToken: 'mounted-session', scope: { workspaceId: 'w', projectId: 'novel', storylineId: 's', branchId: 'mounted-branch' } }} isCurrent={() => true} onDirtyChange={vi.fn()} onBusyChange={onBusy} />);
  await openBook(); await preflight(lossless); ack(); fireEvent.click(download('WEBP')); await screen.findByText('已校验并下载 WEBP 页面 ZIP 阅读副本。');
  expect(h.posts()[1][1].headers).toMatchObject({ 'X-Session-Token': 'mounted-session', 'X-Branch-Id': 'mounted-branch' }); expect(saveOtioFile).toHaveBeenCalledTimes(1); expect(onBusy).toHaveBeenLastCalledWith(false);
});

it.each([401, 403])('removes private projections after mounted archive export permission denial %s', async status => {
  const h = harness({ mutate: url => url.endsWith('/page-archive-preflight') ? reply(report()) : reply({ code: 'FORBIDDEN' }, status) });
  render(<StudioComicPanel projectId="novel" context={{ sessionToken: 'mounted-session' }} isCurrent={() => true} onDirtyChange={vi.fn()} onBusyChange={vi.fn()} />);
  await openBook(); await preflight(); ack(); fireEvent.click(download()); await screen.findByText(/当前身份或分支没有漫画访问权限/);
  expect(screen.queryByRole('region', { name: '漫画书 JPEG 导出' })).toBeNull(); expect(screen.queryByText(/格式测试书/)).toBeNull(); expect(saveOtioFile).not.toHaveBeenCalled(); expect(h.posts()).toHaveLength(2);
});

it('requires new archive review after conflict without losing the saved book', async () => {
  const h = harness({ mutate: url => url.endsWith('/page-archive-preflight') ? reply(report()) : reply({ code: 'COMIC_PUBLICATION_CHANGED' }, 409) });
  render(<ComicCollectionTree {...h.props} />); await openBook(); await preflight(); ack(); fireEvent.click(download()); await screen.findByText(/COMIC_PUBLICATION_CHANGED/);
  expect(screen.queryByRole('button', { name: '下载已核对的 JPEG ZIP' })).toBeNull(); expect((screen.getByLabelText('漫画书名称') as HTMLInputElement).value).toBe('格式测试书'); expect(saveOtioFile).not.toHaveBeenCalled();
});

it('revokes an archive acknowledgement before any retained download', async () => {
  const h = harness(); render(<ComicCollectionTree {...h.props} />); await openBook(); await preflight(); ack(); const oldDownload = retained(download()); ack(); act(oldDownload);
  expect(download().disabled).toBe(true); expect(h.posts()).toHaveLength(1); expect(saveOtioFile).not.toHaveBeenCalled();
});

it('same-value controls are no-ops and preserve the current acknowledged receipt', async () => {
  const h = harness(); render(<ComicCollectionTree {...h.props} />); await openBook(); await preflight(webp); ack();
  change('出版副本格式', 'WEBP'); change('WEBP 阅读方向', 'RTL'); change('WebP 编码模式', 'LOSSY'); change('WEBP 有损质量', '80');
  expect(download('WEBP').disabled).toBe(false); expect(h.posts()).toHaveLength(1); fireEvent.click(download('WEBP')); await screen.findByText('已校验并下载 WEBP 页面 ZIP 阅读副本。'); expect(h.posts()).toHaveLength(2);
});

it.each(['format', 'quality', 'mode', 'direction', 'dirty', 'book'])('cannot revive acknowledged archive receipts or retained callbacks after %s A–B–A', async field => {
  const h = harness({ books: [book(), { ...book(), id: 'other', title: '另一本书' }] }); const view = render(<ComicCollectionTree {...h.props} />); await openBook(); await preflight(webp); ack(); const oldDownload = retained(download('WEBP'));
  if (field === 'format') { change('出版副本格式', 'JPEG'); change('出版副本格式', 'WEBP'); }
  if (field === 'quality') { change('WEBP 有损质量', '95'); change('WEBP 有损质量', '80'); }
  if (field === 'mode') { change('WebP 编码模式', 'LOSSLESS'); change('WebP 编码模式', 'LOSSY'); }
  if (field === 'direction') { change('WEBP 阅读方向', 'LTR'); change('WEBP 阅读方向', 'RTL'); }
  if (field === 'dirty') { view.rerender(<ComicCollectionTree {...h.props} pageDirty />); view.rerender(<ComicCollectionTree {...h.props} />); }
  if (field === 'book') { fireEvent.click(screen.getByRole('button', { name: '打开漫画书 另一本书' })); fireEvent.click(screen.getByRole('button', { name: '打开漫画书 格式测试书' })); }
  act(oldDownload); expect(h.posts()).toHaveLength(1); expect(screen.queryByRole('button', { name: '下载已核对的 WEBP ZIP' })).toBeNull();
  await preflight(webp); expect(download('WEBP').disabled).toBe(true); ack(); act(oldDownload); expect(h.posts()).toHaveLength(2); expect(saveOtioFile).not.toHaveBeenCalled();
});

it.each(['owner', 'revision', 'client', 'records', 'unmount'])('rejects retained archive callbacks after %s changes', async reason => {
  let owner = true, revision = 0; const h = harness(); const props = { ...h.props, isOwnerCurrent: () => owner, getOwnerRevision: () => revision };
  const view = render(<ComicCollectionTree {...props} />); await openBook(); await preflight(); ack(); const oldDownload = retained(download());
  if (reason === 'owner') owner = false;
  if (reason === 'revision') revision++;
  if (reason === 'client') view.rerender(<ComicCollectionTree {...props} client={experimentalClient('other', { sessionToken: 'other' })} />);
  if (reason === 'records') view.rerender(<ComicCollectionTree {...props} records={[page('p1', 5), page('p2', 6)]} />);
  if (reason === 'unmount') view.unmount();
  act(oldDownload); expect(h.posts()).toHaveLength(1); expect(saveOtioFile).not.toHaveBeenCalled();
});
