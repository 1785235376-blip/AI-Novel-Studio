// @vitest-environment jsdom
import { StrictMode } from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { ResearchLibraryPanel } from './ResearchLibraryPanel';
import { experimentalClient } from './api';

const ref = { source_id: 'source', source_version: 1, paragraph: 1, quote_sha256: 'a'.repeat(64) };
const source = { id: 'source', version: 1, title: '潮汐参考', author: '合成作者', source: '合成来源', source_version: '第一版', usage_notes: '写作参考', access: 'PRIVATE', format: 'TXT', origin: 'LOCAL_IMPORT', filename: 'tide.txt', accessed_at: '2026-10-05', extraction_status: 'TEXT_EXTRACTED', paragraph_count: 1, warnings: [], paragraphs: [{ paragraph: 1, page: null, text: '暮色中的港口关闭潮门。', citation: ref }] };
const evidence = { citation: ref, title: source.title, text: source.paragraphs[0].text, paragraph: 1, page: null, source: source.source, author: source.author };
const reply = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status });
const client = (id = 'novel') => experimentalClient(id, { sessionToken: 'trusted-session' });
const fetcher = (mutate?: (url: string, init: RequestInit) => Response | Promise<Response>) => vi.fn(async (url: string, init: RequestInit) => {
  if (mutate && init.method !== 'GET') return mutate(url, init);
  if (url.endsWith('/sources/source')) return reply(source);
  if (url.endsWith('/sources')) return reply({ items: [source], total: 1, adapters: {} });
  if (url.includes('/search?')) return reply({ items: [evidence], truncated: false });
  return reply({ items: [] });
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

it('only reads saved local sources on mount; no fetch, parse, search or model execution', async () => {
  const fetch = fetcher(); vi.stubGlobal('fetch', fetch);
  render(<StrictMode><ResearchLibraryPanel client={client()} /></StrictMode>);
  await screen.findByRole('button', { name: '打开来源 潮汐参考' });
  expect(fetch.mock.calls.every(([url, init]) => init.method === 'GET' && !/fetch-webpage|search\?|generate|import/.test(url))).toBe(true);
  expect(screen.getByText(/向量、OCR 与视觉解析当前未配置/)).toBeTruthy();
  expect((screen.getByRole('button', { name: '抓取这个网页一次' }) as HTMLButtonElement).disabled).toBe(true);
});

it('imports selected actual local bytes only after explicit action and sends captured headers', async () => {
  const fetch = fetcher(() => reply(source, 201)); vi.stubGlobal('fetch', fetch);
  render(<ResearchLibraryPanel client={client()} />);
  await screen.findByRole('button', { name: '打开来源 潮汐参考' });
  fireEvent.change(screen.getByLabelText('资料标题'), { target: { value: '潮汐新资料' } });
  fireEvent.change(screen.getByLabelText('选择本地资料文件'), { target: { files: [new File(['潮汐'], 'source.txt', { type: 'text/plain' })] } });
  expect(fetch.mock.calls.some(([, init]) => init.method === 'POST')).toBe(false);
  fireEvent.click(screen.getByRole('button', { name: '导入所选本地文件' }));
  await waitFor(() => expect(fetch.mock.calls.some(([url]) => url.endsWith('/sources/import'))).toBe(true));
  const [, init] = fetch.mock.calls.find(([url]) => url.endsWith('/sources/import'))!;
  expect(JSON.parse(String(init.body))).toMatchObject({ filename: 'source.txt', content_base64: '5r2u5rGQ', title: '潮汐新资料', access: 'PRIVATE' });
  expect((init.headers as Record<string, string>)['X-Session-Token']).toBe('trusted-session');
});

it('requires explicit webpage approval and resets it when URL changes', async () => {
  const fetch = fetcher(() => reply(source, 201)); vi.stubGlobal('fetch', fetch);
  render(<ResearchLibraryPanel client={client()} />);
  await screen.findByRole('button', { name: '打开来源 潮汐参考' });
  fireEvent.change(screen.getByLabelText('资料标题'), { target: { value: '公开来源' } });
  fireEvent.change(screen.getByLabelText('明确选择的网页网址'), { target: { value: 'https://example.org/tide' } });
  const button = screen.getByRole('button', { name: '抓取这个网页一次' }) as HTMLButtonElement;
  expect(button.disabled).toBe(true);
  fireEvent.click(screen.getByLabelText(/我允许本次访问此公开网页/)); expect(button.disabled).toBe(false);
  fireEvent.change(screen.getByLabelText('明确选择的网页网址'), { target: { value: 'https://example.org/new' } }); expect(button.disabled).toBe(true);
  fireEvent.click(screen.getByLabelText(/我允许本次访问此公开网页/)); fireEvent.click(button); fireEvent.click(button);
  await waitFor(() => expect(fetch.mock.calls.filter(([url]) => url.endsWith('/fetch-webpage'))).toHaveLength(1));
  expect(JSON.parse(String(fetch.mock.calls.find(([url]) => url.endsWith('/fetch-webpage'))![1].body))).toMatchObject({ confirm_fetch: true, url: 'https://example.org/new' });
});

it('traces original paragraph and writes notes from exact reviewed citation versions', async () => {
  const fetch = fetcher((url) => reply(url.endsWith('/citation') ? evidence : {})); vi.stubGlobal('fetch', fetch);
  render(<ResearchLibraryPanel client={client()} />);
  fireEvent.click(await screen.findByRole('button', { name: '打开来源 潮汐参考' }));
  fireEvent.click(await screen.findByLabelText('选择引用：第 1 段'));
  fireEvent.click(screen.getByRole('button', { name: '核对原段落 1' }));
  await screen.findByRole('region', { name: '引用原文' });
  fireEvent.change(screen.getByLabelText('研究笔记标题'), { target: { value: '我的笔记' } });
  fireEvent.change(screen.getByLabelText('研究笔记内容'), { target: { value: '在故事里改成夜航。' } });
  fireEvent.click(screen.getByRole('button', { name: '保存带引用的研究笔记' }));
  await waitFor(() => expect(fetch.mock.calls.some(([url, init]) => url.endsWith('/notes') && init.method === 'POST')).toBe(true));
  const sent = JSON.parse(String(fetch.mock.calls.find(([url, init]) => url.endsWith('/notes') && init.method === 'POST')![1].body));
  expect(sent).toEqual({ title: '我的笔记', text: '在故事里改成夜航。', citations: [ref] });
});

it('keeps original input on stale-source conflict and requires fresh citation selection', async () => {
  const fetch = fetcher(() => reply({ detail: { code: 'EXPERIMENTAL_SOURCE_STALE' } }, 409)); vi.stubGlobal('fetch', fetch);
  render(<ResearchLibraryPanel client={client()} />);
  fireEvent.click(await screen.findByRole('button', { name: '打开来源 潮汐参考' }));
  fireEvent.click(await screen.findByLabelText('选择引用：第 1 段'));
  fireEvent.change(screen.getByLabelText('原创设定草稿标题'), { target: { value: '蓝灯潮门' } });
  fireEvent.change(screen.getByLabelText('原创设定内容'), { target: { value: '潮门只听从蓝灯召唤。' } });
  fireEvent.click(screen.getByLabelText('已写成原创虚构设定，并核对所选参考引用'));
  fireEvent.click(screen.getByRole('button', { name: '采用为原创设定草稿' }));
  await screen.findByText(/版本或引用已变化/);
  expect((screen.getByLabelText('原创设定内容') as HTMLTextAreaElement).value).toBe('潮门只听从蓝灯召唤。');
  fireEvent.click(screen.getByRole('button', { name: '刷新资料与权限（保留输入）' }));
  await screen.findByRole('button', { name: '打开来源 潮汐参考' });
  expect((screen.getByRole('button', { name: '采用为原创设定草稿' }) as HTMLButtonElement).disabled).toBe(true);
});

it('hides private prior titles after a revoked-authority response; retained input is not submitted', async () => {
  const fetch = fetcher(() => reply({ detail: { code: 'FORBIDDEN' } }, 403)); vi.stubGlobal('fetch', fetch);
  render(<ResearchLibraryPanel client={client()} />);
  fireEvent.click(await screen.findByRole('button', { name: '打开来源 潮汐参考' }));
  fireEvent.click(await screen.findByRole('button', { name: '核对原段落 1' }));
  await screen.findByRole('alert');
  expect(screen.queryByRole('button', { name: '打开来源 潮汐参考' })).toBeNull();
  expect(screen.queryByText('暮色中的港口关闭潮门。')).toBeNull();
});

it('source deletion sends current version only after explicit acknowledgement', async () => {
  const fetch = fetcher(() => reply({ status: 'DELETED' })); vi.stubGlobal('fetch', fetch);
  render(<ResearchLibraryPanel client={client()} />);
  fireEvent.click(await screen.findByRole('button', { name: '打开来源 潮汐参考' }));
  const button = await screen.findByRole('button', { name: '删除资料来源' }) as HTMLButtonElement;
  expect(button.disabled).toBe(true);
  fireEvent.click(screen.getByLabelText(/我知道撤销或删除会使关联检索/)); fireEvent.click(button);
  await waitFor(() => expect(fetch.mock.calls.some(([url]) => url.endsWith('/source/delete'))).toBe(true));
  expect(JSON.parse(String(fetch.mock.calls.find(([url]) => url.endsWith('/source/delete'))![1].body))).toEqual({ expected_version: 1 });
});

it('ignores delayed old-scope citation results after switching project', async () => {
  let finish!: (value: Response) => void;
  const fetch = fetcher(() => new Promise(resolve => { finish = resolve; })); vi.stubGlobal('fetch', fetch);
  const view = render(<ResearchLibraryPanel client={client()} />);
  fireEvent.click(await screen.findByRole('button', { name: '打开来源 潮汐参考' }));
  fireEvent.click(await screen.findByRole('button', { name: '核对原段落 1' }));
  view.rerender(<ResearchLibraryPanel client={client('other')} />);
  finish(reply({ ...evidence, text: '旧项目私密段落' }));
  await waitFor(() => expect(screen.queryByText('旧项目私密段落')).toBeNull());
  expect(screen.queryByRole('region', { name: '引用原文' })).toBeNull();
});

it('allows deliberate current-version recovery while keeping edited metadata text', async () => {
  let version = 1;
  const fetch = vi.fn(async (url: string, init: RequestInit) => {
    if (init.method === 'PUT') { version = 2; return reply({ detail: { code: 'EXPERIMENTAL_VERSION_CONFLICT' } }, 409); }
    const current = { ...source, version, title: version === 1 ? source.title : '服务器已改标题' };
    return reply(url.endsWith('/sources/source') ? current : url.endsWith('/sources') ? { items: [current] } : { items: [] });
  });
  vi.stubGlobal('fetch', fetch); render(<ResearchLibraryPanel client={client()} />);
  fireEvent.click(await screen.findByRole('button', { name: '打开来源 潮汐参考' }));
  fireEvent.click(await screen.findByRole('button', { name: '编辑来源元数据' }));
  fireEvent.change(screen.getByLabelText('资料标题'), { target: { value: '保留我的修改' } });
  fireEvent.click(screen.getByRole('button', { name: '保存资料元数据' }));
  await screen.findByText(/版本或引用已变化/);
  fireEvent.click(screen.getByRole('button', { name: '刷新资料与权限（保留输入）' }));
  const recover = await screen.findByRole('button', { name: '已核对当前版本，保留输入继续编辑' });
  expect((screen.getByLabelText('资料标题') as HTMLInputElement).value).toBe('保留我的修改');
  fireEvent.click(recover); fireEvent.click(screen.getByRole('button', { name: '保存资料元数据' }));
  await waitFor(() => expect(fetch.mock.calls.filter(([, init]) => init.method === 'PUT')).toHaveLength(2));
  expect(JSON.parse(String(fetch.mock.calls.filter(([, init]) => init.method === 'PUT')[1][1].body))).toMatchObject({ expected_version: 2, title: '保留我的修改' });
});

it('shows image page-only citation without inventing extraction or rendering active markup', async () => {
  const pageRef = { ...ref, paragraph: 0, page: 1 };
  const image = { ...source, format: 'IMAGE', extraction_status: 'OCR_NOT_CONFIGURED', paragraph_count: 0, paragraphs: [], page_citations: [pageRef], warnings: ['图像内容没有被解析。'] };
  vi.stubGlobal('fetch', vi.fn(async (url: string) => reply(url.endsWith('/sources/source') ? image : url.endsWith('/sources') ? { items: [image] } : url.endsWith('/citation') ? { ...evidence, citation: pageRef, paragraph: 0, page: 1, text: '', not_understood: true } : { items: [] })));
  render(<ResearchLibraryPanel client={client()} />);
  fireEvent.click(await screen.findByRole('button', { name: '打开来源 潮汐参考' }));
  fireEvent.click(await screen.findByLabelText('选择仅页面引用：第 1 页（未解析内容）'));
  fireEvent.click(screen.getByRole('button', { name: '核对页面引用 1' }));
  await screen.findByText('仅原始页面引用。OCR 与视觉理解未配置，没有提取或理解这页内容。');
  expect(screen.queryByText('暮色中的港口关闭潮门。')).toBeNull();
  expect(document.querySelectorAll('iframe, img, script')).toHaveLength(0);
});
