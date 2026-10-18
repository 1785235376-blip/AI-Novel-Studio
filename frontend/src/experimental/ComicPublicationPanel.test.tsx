// @vitest-environment jsdom
import { webcrypto } from 'node:crypto';
import { Blob as NativeBlob } from 'node:buffer';
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { ComicCollectionTree } from './ComicCollectionTree';
import { ComicLayoutsPanel } from './ComicLayoutsPanel';
import { StudioComicPanel } from '../creative/StudioComicPanel';
import { experimentalClient } from './api';
import { blankComic, type ComicBook, type ComicPublicationPreflight, type ComicRecord } from './comicLayoutsClient';
import { saveOtioFile } from './timelineExchangeClient';

vi.mock('./timelineExchangeClient', () => ({ saveOtioFile: vi.fn() }));
const settings = { width: 800, height: 1120, safe_area: 24, segment_height: 1120 };
const page = (id: string, version: number): ComicRecord => ({ id, version, status: 'APPROVED', stale: false, document: { ...blankComic('PAGE', settings), title: `页面 ${id}` } });
const initialBook = (): ComicBook => ({ id: 'book', version: 3, stale: false, title: '出版测试书', chapters: [{ id: 'ch1', title: '第一章', pages: ['p2'] }, { id: 'ch2', title: '第二章', pages: ['p1'] }] });
const initialReport = (): ComicPublicationPreflight => ({ book_version: 3, reading_direction: 'RTL', pages: [{ id: 'p2', version: 6, review_digest: 'b'.repeat(64) }, { id: 'p1', version: 4, review_digest: 'a'.repeat(64) }], publication_digest: 'c'.repeat(64), page_count: 2, losses: ['FLATTENED_RGB_PNG_PAGES', 'NO_EDITABLE_LAYERS_OR_TEXT', 'DIRECTION_METADATA_DOES_NOT_REORDER_PAGES_OR_PANELS', 'NO_DPI_BLEED_OR_PRINT_CONFORMANCE', 'EXTERNAL_READER_VALIDATION_NOT_RUN'] });
const reply = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status });
async function archive() {
  const bytes = new TextEncoder().encode('test-cbz-bytes');
  const sha = Array.from(new Uint8Array(await webcrypto.subtle.digest('SHA-256', bytes)), byte => byte.toString(16).padStart(2, '0')).join('');
  return new Response(bytes, { headers: { 'Content-Type': 'application/vnd.comicbook+zip', 'X-Comic-Publication-Digest': 'c'.repeat(64), 'X-Content-SHA256': sha } });
}
beforeEach(() => { vi.stubGlobal('crypto', webcrypto); vi.stubGlobal('Blob', NativeBlob); vi.mocked(saveOtioFile).mockClear(); URL.createObjectURL = vi.fn(() => 'blob:test'); URL.revokeObjectURL = vi.fn(); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
function harness(options: { pages?: ComicRecord[]; book?: ComicBook; mutate?: (url: string, init: RequestInit) => Promise<Response> | Response } = {}) {
  const pages = options.pages || [page('p1', 4), page('p2', 6)], book = options.book || initialBook();
  const fetch = vi.fn(async (url: string, init: RequestInit) => {
    if (init.method === 'GET') {
      if (url.endsWith('/books')) return reply({ items: [book] });
      if (url.endsWith('/records')) return reply({ items: pages });
      if (url.endsWith('/catalog')) return reply({ screenplays: [], characters: [], assets: [], presets: { PAGE: settings, WEBTOON: settings }, renderer: { available: true }, font: { available: true } });
    }
    if (options.mutate) return options.mutate(url, init);
    if (url.endsWith('/publication-preflight')) return reply(initialReport());
    if (url.endsWith('/export-cbz')) return archive();
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
