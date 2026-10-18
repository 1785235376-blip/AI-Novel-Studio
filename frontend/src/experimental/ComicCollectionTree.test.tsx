// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { ComicCollectionTree } from './ComicCollectionTree';
import { ComicLayoutsPanel } from './ComicLayoutsPanel';
import { experimentalClient } from './api';
import { blankComic, type ComicBook, type ComicRecord } from './comicLayoutsClient';
const settings = { width: 800, height: 1120, safe_area: 24, segment_height: 1120 };
const page = (id: string, version = 1): ComicRecord => ({ id, version, status: 'DRAFT', stale: false, document: { ...blankComic('PAGE', settings), title: `页面 ${id}` }, history_versions: [] });
const initialBook = (): ComicBook => ({ id: 'book', version: 3, stale: false, title: '测试漫画书', chapters: [{ id: 'ch1', title: '起点', pages: ['p1', 'p2'] }, { id: 'ch2', title: '终点', pages: [] }], history_versions: [1, 2] });
const reply = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status });
const client = (id = 'novel') => experimentalClient(id, { sessionToken: 'trusted' });
beforeEach(() => { URL.createObjectURL = vi.fn(() => 'blob:test'); URL.revokeObjectURL = vi.fn(); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
function harness(options: { books?: ComicBook[]; pages?: ComicRecord[]; mutate?: (url: string, init: RequestInit) => Promise<Response> | Response } = {}) {
  let books = options.books || [initialBook()], pages = options.pages || [page('p1', 4), page('p2', 6), page('free', 2)];
  const fetch = vi.fn(async (url: string, init: RequestInit) => {
    if (init.method === 'GET') {
      if (url.endsWith('/books')) return reply({ items: books });
      if (url.endsWith('/records')) return reply({ items: pages });
      if (url.endsWith('/catalog')) return reply({ screenplays: [], characters: [], assets: [], presets: { PAGE: settings, WEBTOON: settings }, renderer: { available: true }, font: { available: true } });
      return reply({}, 404);
    }
    if (options.mutate) return options.mutate(url, init);
    const body = JSON.parse(String(init.body));
    if (url.endsWith('/books')) {
      const next = { ...body, id: 'new-book', stale: false, version: 1, history_versions: [] }; books = [...books, next]; return reply(next, 201);
    }
    if (init.method === 'PUT') { const next = { ...books[0], title: body.title, chapters: body.chapters, version: books[0].version + 1 }; books = [next, ...books.slice(1)]; return reply(next); }
    if (url.endsWith('/pages')) {
      const nextPage = page(`created-${pages.length}`); pages = [...pages, nextPage];
      const next = { ...books[0], version: books[0].version + 1, chapters: books[0].chapters!.map(chapter => chapter.id === body.chapter_id ? { ...chapter, pages: [...chapter.pages, nextPage.id] } : chapter) };
      books = [next, ...books.slice(1)]; return reply({ book: next, page: nextPage }, 201);
    }
    if (url.endsWith('/restore')) { const next = { ...books[0], version: books[0].version + 1 }; books = [next, ...books.slice(1)]; return reply(next); }
    return reply({}, 404);
  });
  vi.stubGlobal('fetch', fetch);
  const props = { client: client(), records: pages, recordsReady: true, pageDirty: false, externalBusy: false, getOwnerRevision: () => 0, onActiveChange: vi.fn(), onDirtyChange: vi.fn(), onBusyChange: vi.fn(), onOpenPage: vi.fn(), onPageCreated: vi.fn() };
  return { fetch, props, writes: () => fetch.mock.calls.filter(([, init]) => init.method !== 'GET') };
}
async function openBook() { await waitFor(() => { const button = screen.getByText('打开漫画书 测试漫画书') as HTMLButtonElement; expect(button.disabled).toBe(false); fireEvent.click(button); }); await screen.findByText(/已保存结构 · v/); }
function retained(element: HTMLElement): () => void { const key = Object.keys(element).find(value => value.startsWith('__reactProps'))!; return (element as unknown as Record<string, { onClick: () => void }>)[key].onClick; }

it('reads only on mount, hides stale book and page titles, and exposes independent pages only', async () => {
  const h = harness({ books: [initialBook(), { id: 'stale-book', version: 2, stale: true, title: 'PRIVATE BOOK', chapters: [{ id: 'x', title: 'PRIVATE CHAPTER', pages: [] }] }], pages: [page('p1'), page('p2'), { ...page('private'), stale: true, document: { ...page('private').document!, title: 'PRIVATE PAGE' } }, { ...page('screenplay'), document: { ...page('screenplay').document!, source_mode: 'SCREENPLAY' } }, page('free')] });
  render(<ComicCollectionTree {...h.props} />); await openBook();
  expect(h.writes()).toHaveLength(0); expect(screen.queryByText(/PRIVATE/)).toBeNull();
  expect(screen.queryByRole('option', { name: /screenplay/ })).toBeNull();
  expect(screen.queryByRole('option', { name: /PRIVATE PAGE/ })).toBeNull();
});

it('creates an empty book only explicitly and preserves a bounded manual structure with all page-version pins', async () => {
  const h = harness(); render(<ComicCollectionTree {...h.props} />); await openBook();
  fireEvent.click(screen.getByRole('button', { name: '下移章节 1' }));
  expect((screen.getByLabelText('章节 1 名称') as HTMLInputElement).value).toBe('终点');
  fireEvent.change(screen.getByLabelText('章节 1 附加独立页面'), { target: { value: 'free' } });
  fireEvent.click(screen.getByRole('button', { name: '附加到章节 1' }));
  expect(h.writes()).toHaveLength(0); expect(h.props.onDirtyChange).toHaveBeenLastCalledWith(true);
  expect((screen.getByRole('button', { name: /打开页面 1.1/ }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(screen.getByRole('button', { name: '保存漫画书结构' }));
  await screen.findByText(/漫画书结构已保存/);
  expect(h.writes()).toHaveLength(1); expect(h.writes()[0][1].method).toBe('PUT');
  expect(JSON.parse(String(h.writes()[0][1].body))).toEqual({ expected_version: 3, expected_page_versions: { free: 2, p1: 4, p2: 6 }, title: '测试漫画书', chapters: [{ id: 'ch2', title: '终点', pages: ['free'] }, { id: 'ch1', title: '起点', pages: ['p1', 'p2'] }] });
  expect(h.props.onDirtyChange).toHaveBeenLastCalledWith(false);
});

it('moves pages across chapters and removes membership without deleting pages; restore is explicit and version-aware', async () => {
  const h = harness(); render(<ComicCollectionTree {...h.props} />); await openBook();
  fireEvent.change(screen.getByLabelText('页面 1.1 所属章节'), { target: { value: 'ch2' } });
  fireEvent.click(screen.getByRole('button', { name: '移出页面 1.1（保留布局）' }));
  fireEvent.click(screen.getByRole('button', { name: '保存漫画书结构' }));
  await screen.findByText(/漫画书结构已保存/); await waitFor(() => expect((screen.getByLabelText('恢复漫画书结构版本') as HTMLSelectElement).disabled).toBe(false));
  const save = JSON.parse(String(h.writes()[0][1].body)); expect(save.chapters.map((chapter: { pages: string[] }) => chapter.pages)).toEqual([[], ['p1']]);
  fireEvent.change(screen.getByLabelText('恢复漫画书结构版本'), { target: { value: '1' } });
  fireEvent.click(screen.getByRole('button', { name: '恢复为新的漫画书结构版本' }));
  await screen.findByText(/已新增恢复后的结构版本/);
  expect(JSON.parse(String(h.writes()[1][1].body))).toEqual({ expected_version: 4, target_version: 1 });
  expect(h.writes().every(([url, init]) => !url.includes('/records') && init.method !== 'DELETE')).toBe(true);
});

it('creates blank and duplicate pages only from a saved structure and sends exact source version once', async () => {
  const h = harness(); const view = render(<ComicCollectionTree {...h.props} />); await openBook();
  const copy = retained(screen.getByRole('button', { name: '复制页面 1.1' }));
  await act(async () => { copy(); copy(); });
  await screen.findByText(/已复制为新的待审页面/);
  expect(h.writes()).toHaveLength(1); expect(JSON.parse(String(h.writes()[0][1].body))).toEqual({ expected_version: 3, chapter_id: 'ch1', source_layout_id: 'p1', expected_source_version: 4 });
  expect(h.props.onPageCreated).toHaveBeenCalledTimes(1);
  view.rerender(<ComicCollectionTree {...h.props} records={[...h.props.records, h.props.onPageCreated.mock.calls[0][0]]} />);
  await waitFor(() => expect((screen.getByRole('button', { name: '在章节 2 新建空白页' }) as HTMLButtonElement).disabled).toBe(false));
  fireEvent.click(screen.getByRole('button', { name: '在章节 2 新建空白页' }));
  await screen.findByText(/已在章节中创建空白待审页面/);
  expect(JSON.parse(String(h.writes()[1][1].body))).toEqual({ expected_version: 4, chapter_id: 'ch2' });
  expect(h.writes().some(([url]) => /generate|approve|execute|render/.test(url))).toBe(false);
});

it('failed save keeps the local structure and requires explicit discard before navigation', async () => {
  const h = harness({ mutate: () => reply({ detail: { code: 'EXPERIMENTAL_VERSION_CONFLICT' } }, 409) }); render(<ComicCollectionTree {...h.props} />); await openBook();
  fireEvent.change(screen.getByLabelText('漫画书名称'), { target: { value: '保留本地结构' } });
  fireEvent.click(screen.getByRole('button', { name: '保存漫画书结构' })); await screen.findByText(/EXPERIMENTAL_VERSION_CONFLICT/);
  expect((screen.getByLabelText('漫画书名称') as HTMLInputElement).value).toBe('保留本地结构');
  expect((screen.getByRole('button', { name: /打开页面 1.1/ }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(screen.getByRole('button', { name: '放弃书结构修改' }));
  expect((screen.getByLabelText('漫画书名称') as HTMLInputElement).value).toBe('测试漫画书');
  expect(h.props.onDirtyChange).toHaveBeenLastCalledWith(false);
});

it('retained callbacks cannot save or open pages after a newer edit or owner revision, and cannot act after unmount', async () => {
  const h = harness(); let ownerRevision = 0; const view = render(<ComicCollectionTree {...h.props} getOwnerRevision={() => ownerRevision} />); await openBook();
  const open = retained(screen.getByRole('button', { name: /打开页面 1.1/ }));
  fireEvent.change(screen.getByLabelText('漫画书名称'), { target: { value: '最新结构' } }); act(open); expect(h.props.onOpenPage).not.toHaveBeenCalled();
  const save = retained(screen.getByRole('button', { name: '保存漫画书结构' })); ownerRevision++; act(save); expect(h.writes()).toHaveLength(0);
  view.unmount(); act(save); expect(h.writes()).toHaveLength(0);
});

it('late page creation cannot deliver a page after owner invalidation', async () => {
  let finish: (response: Response) => void = () => {}; let owner = true;
  const h = harness({ mutate: () => new Promise(resolve => { finish = resolve; }) }); render(<ComicCollectionTree {...h.props} isOwnerCurrent={() => owner} />); await openBook();
  fireEvent.click(screen.getByRole('button', { name: '在章节 1 新建空白页' })); owner = false;
  await act(async () => finish(reply({ book: { ...initialBook(), version: 4 }, page: page('late') })));
  expect(h.props.onPageCreated).not.toHaveBeenCalled(); expect(screen.queryByText(/已在章节中创建/)).toBeNull();
});

it('enforces the chapter bound and keeps all collection actions blocked by a dirty page', async () => {
  const full = { ...initialBook(), chapters: Array.from({ length: 20 }, (_, i) => ({ id: `chapter-${i}`, title: `章 ${i}`, pages: [] })) };
  const h = harness({ books: [full] }); const view = render(<ComicCollectionTree {...h.props} />); await openBook();
  expect((screen.getByText('添加漫画章节') as HTMLButtonElement).disabled).toBe(true);
  view.rerender(<ComicCollectionTree {...h.props} pageDirty />);
  expect((screen.getByText('刷新漫画书') as HTMLButtonElement).disabled).toBe(true);
  expect((screen.getByText('创建漫画书') as HTMLButtonElement).disabled).toBe(true);
  expect(h.writes()).toHaveLength(0);
});

it('enforces the page bound for blank pages, copies, and attachments', async () => {
  const full = { ...initialBook(), chapters: [{ id: 'ch1', title: '满页章节', pages: Array.from({ length: 100 }, (_, i) => `p${i}`) }] };
  const h = harness({ books: [full], pages: Array.from({ length: 101 }, (_, i) => page(`p${i}`)) }); render(<ComicCollectionTree {...h.props} />); await openBook();
  expect((screen.getByText('在章节 1 新建空白页') as HTMLButtonElement).disabled).toBe(true);
  expect((screen.getByText('复制页面 1.1') as HTMLButtonElement).disabled).toBe(true);
  expect((screen.getByText('附加到章节 1') as HTMLButtonElement).disabled).toBe(true);
  expect(h.writes()).toHaveLength(0);
});

it('integrates aggregate dirty state and explicit page and structure discard before leaving an active collection', async () => {
  const h = harness(); const onDirty = vi.fn(); render(<ComicLayoutsPanel client={h.props.client} onDirtyChange={onDirty} />); await openBook();
  fireEvent.click(screen.getByRole('button', { name: /打开页面 1.1/ })); await screen.findByLabelText('漫画布局名称');
  fireEvent.change(screen.getByLabelText('漫画布局名称'), { target: { value: '尚未保存页面' } });
  expect(onDirty).toHaveBeenLastCalledWith(true);
  expect((screen.getByRole('button', { name: '新建空白漫画页' }) as HTMLButtonElement).disabled).toBe(true);
  expect((screen.getByLabelText('漫画来源剧本') as HTMLSelectElement).disabled).toBe(true);
  expect((screen.getByRole('button', { name: '打开布局 页面 p2' }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(screen.getByRole('button', { name: '放弃当前页面修改' })); expect(onDirty).toHaveBeenLastCalledWith(false);
  fireEvent.change(screen.getByLabelText('漫画书名称'), { target: { value: '尚未保存结构' } });
  expect(onDirty).toHaveBeenLastCalledWith(true);
  expect((screen.getByRole('button', { name: '打开布局 页面 p2' }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(screen.getByRole('button', { name: '放弃书结构修改' })); expect(onDirty).toHaveBeenLastCalledWith(false);
});

it('integrates book-page completion with the existing page editor without self-invalidating its owner fence', async () => {
  const h = harness(); const onBusy = vi.fn(); render(<ComicLayoutsPanel client={h.props.client} onBusyChange={onBusy} />); await openBook();
  fireEvent.click(screen.getByRole('button', { name: '在章节 1 新建空白页' }));
  await screen.findByDisplayValue('页面 created-3');
  expect(h.writes()).toHaveLength(1); expect(onBusy).toHaveBeenCalledWith(true); expect(onBusy).toHaveBeenLastCalledWith(false);
});

it('hides every collection projection immediately when a referenced page disappears before the book refresh completes', async () => {
  const h = harness(); const view = render(<ComicCollectionTree {...h.props} />); await openBook();
  fireEvent.change(screen.getByLabelText('漫画书名称'), { target: { value: '私有本地书名' } });
  const pendingFetch = vi.fn(() => new Promise<Response>(() => {})); vi.stubGlobal('fetch', pendingFetch);
  view.rerender(<ComicCollectionTree {...h.props} records={[{ ...page('p1'), stale: true }, page('p2')]} />);
  expect(screen.queryByDisplayValue('私有本地书名')).toBeNull();
  expect(screen.queryByDisplayValue('起点')).toBeNull();
  expect(screen.queryByText(/打开漫画书 测试漫画书/)).toBeNull();
  expect(screen.queryByText(/未保存结构 · v/)).toBeNull();
  expect(screen.queryByLabelText('恢复漫画书结构版本')).toBeNull();
  expect(screen.getByRole('button', { name: '放弃书结构修改' })).toBeTruthy();
  expect(h.props.onDirtyChange).toHaveBeenLastCalledWith(true);
});

it('creates a named empty book and an explicit chapter draft without background writes', async () => {
  const h = harness({ books: [] }); render(<ComicCollectionTree {...h.props} />);
  await screen.findByText('还没有漫画书');
  fireEvent.change(screen.getByLabelText('新漫画书名称'), { target: { value: ' 新书 ' } });
  fireEvent.click(screen.getByRole('button', { name: '创建漫画书' }));
  await screen.findByText(/已创建空漫画书/);
  expect(JSON.parse(String(h.writes()[0][1].body))).toEqual({ title: '新书', chapters: [] });
  await waitFor(() => expect((screen.getByText('添加漫画章节') as HTMLButtonElement).disabled).toBe(false));
  fireEvent.click(screen.getByText('添加漫画章节'));
  expect((screen.getByLabelText('章节 1 名称') as HTMLInputElement).value).toBe('第 1 章');
  expect(h.writes()).toHaveLength(1); expect(h.props.onDirtyChange).toHaveBeenLastCalledWith(true);
});
