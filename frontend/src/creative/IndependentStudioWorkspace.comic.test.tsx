// @vitest-environment jsdom
// Mounted original Image + Comic components; HTTP DTOs are controlled here.
// Actual File persistence is covered separately by test_comic_independent.py.
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { useStudio } from '../store';
import { useLocalHostSession } from '../localHostSession';
import { IndependentStudioWorkspace } from './IndependentStudioWorkspace';
import type { ComicRecord } from '../experimental/comicLayoutsClient';
import emptyPromptLibrary from '../prompt/__fixtures__/empty-library.json';
const id = 'blank-comic-project', base = `/api/projects/${id}/studio`, comics = `/api/novels/${id}/experimental/comic-layouts`;
const preset = { width: 800, height: 1120, safe_area: 24, segment_height: 1120 };
const catalog = { screenplays: [], characters: [], assets: [], presets: { PAGE: preset, WEBTOON: { ...preset, height: 2400, segment_height: 1200 } }, renderer: { available: false }, font: { available: false } };
const response = (body: unknown, status = 200) => ({ ok: status < 400, status, json: async () => structuredClone(body) });
let record: ComicRecord | undefined, fetcher: ReturnType<typeof vi.fn>, denied: boolean;
function mount() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><IndependentStudioWorkspace projectId={id} context={{ sessionToken: '' }} module="IMAGE" actor="作者"
    scope={{ workspace: '本机作品', project: '独立项目', storyline: '默认故事线', branch: '主线' }} onModuleChange={vi.fn()} onProjectChoice={vi.fn()} /></QueryClientProvider>);
}
beforeEach(() => {
  URL.createObjectURL = vi.fn(() => 'blob:comic'); URL.revokeObjectURL = vi.fn();
  localStorage.clear(); record = undefined; denied = false;
  useStudio.setState({ novelId: id, chapterId: '', sessionToken: '', actor: undefined, scope: undefined });
  useLocalHostSession.setState({ token: 'original-host', actorId: 'local-author' });
  fetcher = vi.fn(async (url: string, init: RequestInit = {}) => {
    if (url === base) return response({ project: { id, title: '独立项目', entry_kind: 'NEUTRAL_STUDIO' }, preferences: { version: 1, intents: [], preset: 'BLANK', custom_intent: '' }, capabilities: { can_mutate: true, manual_import: true, manual_export: true, model_required: false, chapter_required: false, intent_is_permission: false, media_validator_configured: false, asset_kinds: ['image'] } });
    if (url.startsWith(`${base}/assets`)) return response({ items: [] });
    if (url === `${base}/prompts`) return response({ ...emptyPromptLibrary, project_id: id, scope: { mode: 'local', novel_id: id } });
    if (url.startsWith(comics) && denied) return response({ detail: { code: 'FORBIDDEN' } }, 403);
    if (url === `${comics}/catalog`) return response(catalog);
    if (url === `${comics}/records` && init.method === 'GET') return response({ items: record ? [record] : [] });
    if (url.startsWith(`${comics}/records`) && ['POST', 'PUT'].includes(init.method || '')) {
      const { expected_version, ...document } = JSON.parse(String(init.body));
      if (record && expected_version !== record.version) return response({ code: 'VERSION_CONFLICT' }, 409);
      record = { id: 'page', version: (record?.version || 0) + 1, document, status: 'DRAFT', stale: false, history_versions: record ? [record.version] : [] };
      return response(record, init.method === 'POST' ? 201 : 200);
    }
    throw new Error(`Unexpected ${init.method} ${url}`);
  });
  vi.stubGlobal('fetch', fetcher);
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
async function open() {
  fireEvent.click(await screen.findByRole('button', { name: '打开漫画制作' }));
  await waitFor(() => expect((screen.getByRole('button', { name: '新建空白漫画页' }) as HTMLButtonElement).disabled).toBe(false));
}
it('Image subview creates a source-free page, edits a bubble, saves and reopens without a model or renderer', async () => {
  const view = mount(); await open();
  expect(within(screen.getByRole('tablist', { name: '创作模块' })).getByRole('tab', { name: '图片' }).getAttribute('aria-selected')).toBe('true');
  fireEvent.click(screen.getByRole('button', { name: '新建空白漫画页' }));
  fireEvent.click(screen.getByRole('button', { name: '保存漫画布局草稿' }));
  await waitFor(() => expect(record?.version).toBe(1));
  expect(record?.document?.panels).toEqual([]);
  fireEvent.click(screen.getByRole('button', { name: '添加格框（手工定位）' }));
  fireEvent.click(screen.getByRole('button', { name: '添加格框 1 气泡' }));
  fireEvent.change(screen.getByLabelText('格框 1 气泡 1 文字'), { target: { value: '你好\nHello\nこんにちは' } });
  fireEvent.click(screen.getByRole('button', { name: '保存漫画布局草稿' }));
  await waitFor(() => expect(record?.version).toBe(2));
  expect(record?.document).toMatchObject({ source_mode: 'INDEPENDENT', screenplay_id: null, expected_screenplay_version: null, panels: [{ shot_id: null, artwork_mode: 'BLANK', bubbles: [{ text: '你好\nHello\nこんにちは' }] }] });
  view.unmount(); mount(); await open();
  fireEvent.click(await screen.findByRole('button', { name: '打开布局 空白漫画页' }));
  expect((screen.getByLabelText('格框 1 气泡 1 文字') as HTMLTextAreaElement).value).toBe('你好\nHello\nこんにちは');
  expect(fetcher.mock.calls.filter(([, init]) => init.method !== 'GET').map(([url]) => url)).toEqual([`${comics}/records`, `${comics}/records/page`]);
  expect(fetcher.mock.calls.filter(([url]) => url.startsWith(comics)).every(([, init]) => (init.headers as Record<string, string>)['X-Session-Token'] === 'original-host')).toBe(true);
});
it('denied Comic scope is explicit and does not look like an empty project', async () => {
  denied = true; mount();
  fireEvent.click(await screen.findByRole('button', { name: '打开漫画制作' }));
  await screen.findByText(/当前身份或分支没有漫画访问权限/);
  expect(screen.queryByRole('button', { name: '新建空白漫画页' })).toBeNull();
  expect(fetcher.mock.calls.every(([, init]) => init.method === 'GET')).toBe(true);
});
it('dirty comic blocks closing until the existing workspace discard confirmation', async () => {
  mount(); await open(); fireEvent.click(screen.getByRole('button', { name: '新建空白漫画页' }));
  fireEvent.click(screen.getByRole('button', { name: '关闭漫画制作' }));
  expect(screen.getByLabelText('漫画布局名称')).toBeTruthy();
  expect(screen.getAllByText(/未保存/).length).toBeGreaterThan(0);
});
