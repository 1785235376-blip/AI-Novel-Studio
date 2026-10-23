// @vitest-environment jsdom
// [HERMIA-FE-20261023 M1-s3] M2 start: real novel panels in the ?uw=1 preview (mocked fetch; no network).
import {act, cleanup, fireEvent, render, screen, waitFor, within} from '@testing-library/react';
import {afterEach, beforeEach, describe, expect, it, vi} from 'vitest';
import {QueryClient, QueryClientProvider} from '@tanstack/react-query';
import {UnifiedWorkspacePreview} from '../UnifiedWorkspacePreview';
import {classifyError, createPreviewPanelRegistry, pickDefaultNovel, statusZh} from './novelPreviewPanels';
import {ApiError} from '../../api';

const NOVELS = [{id: 'e1', title: '演示：空画布工作室', genre: '', chapter_count: 0, word_count: 0, status: 'Writing'},
  {id: 'n1', title: '演示：雾港', genre: '', chapter_count: 2, word_count: 6, status: 'Writing'}];
const ch = (n: number, title: string, version = 2) => ({id: `n1:${n}`, novel_id: 'n1', number: n, title, content: '', document: null, version, word_count: 3, status: 'Draft'});
type Call = {url: string; method: string; body?: unknown};
let calls: Call[]; let renameImpl: (body: {title: string; version: number}) => Response;
const json = (v: unknown, status = 200) => new Response(JSON.stringify(v), {status, headers: {'Content-Type': 'application/json'}});

beforeEach(() => {
  localStorage.clear(); calls = [];
  renameImpl = b => json({...ch(1, b.title, b.version + 1)});
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    const method = init?.method ?? 'GET'; const body = init?.body ? JSON.parse(String(init.body)) : undefined;
    calls.push({url, method, body});
    if (url === '/api/novels') return json(NOVELS);
    if (url === '/api/novels/n1/chapters') return json([ch(1, '来信'), ch(2, '灯塔')]);
    if (url === '/api/novels/e1/chapters') return json([]);
    if (url === '/api/chapters/n1:1/rename' && method === 'POST') return renameImpl(body);
    return json({detail: 'nf'}, 404);
  }));
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

function mount() {
  const qc = new QueryClient({defaultOptions: {queries: {retry: false}}});
  return render(<QueryClientProvider client={qc}><UnifiedWorkspacePreview /></QueryClientProvider>);
}
const outline = () => screen.getByTestId('uw-outline');
async function selectCh1() {
  await waitFor(() => expect(within(outline()).getByText(/第 1 章 · 来信/)).toBeTruthy());
  fireEvent.click(within(outline()).getByText(/第 1 章 · 来信/));
  return screen.findByTestId('uw-inspector');
}

describe('novel preview panels', () => {
  it('registers through PanelRegistry with honest capability status', () => {
    const r = createPreviewPanelRegistry();
    expect(r.get('outline')?.capability).toBe('connected');
    expect(r.get('inspector')?.capability).toBe('partial');
    expect(() => r.register({...r.get('outline')!})).toThrow(/duplicate/);
  });
  it('helpers: default novel 雾港, Chinese status, error classes', () => {
    expect(pickDefaultNovel(NOVELS)?.id).toBe('n1');
    expect(statusZh('Draft')).toBe('草稿'); expect(statusZh('???')).toBe('其他状态');
    expect(classifyError(new TypeError('Failed to fetch'))).toBe('not-connected');
    expect(classifyError(new ApiError({status: 502, code: 'x', message: 'x'}))).toBe('not-connected');
    expect(classifyError(new ApiError({status: 500, code: 'x', message: 'x'}))).toBe('error');
  });
  it('loads real data via GET only; outline → inspector linkage; empty state before selection', async () => {
    mount();
    expect(await screen.findByTestId('uw-inspector-empty')).toBeTruthy();
    const insp = await selectCh1();
    expect((within(insp).getByLabelText('章节标题') as HTMLInputElement).value).toBe('来信');
    expect(insp.textContent).toContain('草稿');
    expect(insp.textContent).not.toMatch(/Draft/);
    expect(calls.every(c => c.method === 'GET')).toBe(true);
  });
  it('not-connected state is honest when backend is down', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => { throw new TypeError('Failed to fetch'); }));
    mount();
    expect((await screen.findAllByText(/后端未连接/)).length).toBeGreaterThan(0);
  });
  it('redock keeps unsaved title; dirty close → confirm; cancel keeps draft; discard drops it', async () => {
    mount(); const insp = await selectCh1();
    fireEvent.change(within(insp).getByLabelText('章节标题'), {target: {value: '来信（改）'}});
    const node = within(insp).getByLabelText('章节标题');
    fireEvent.change(screen.getByLabelText('「章节属性」停靠位置'), {target: {value: 'bottom'}});
    expect(screen.getByTestId('panel-inspector').dataset.dock).toBe('bottom');
    expect(screen.getByLabelText('章节标题')).toBe(node);
    expect((screen.getByLabelText('章节标题') as HTMLInputElement).value).toBe('来信（改）');
    // switching chapter while dirty is blocked, not silently dropped
    fireEvent.click(within(outline()).getByText(/第 2 章 · 灯塔/));
    expect(screen.getByTestId('uw-outline-blocked').textContent).toMatch(/未保存/);
    expect((screen.getByLabelText('章节标题') as HTMLInputElement).value).toBe('来信（改）');
    fireEvent.click(screen.getByLabelText('关闭「章节属性」'));
    const dlg = screen.getByRole('dialog');
    fireEvent.click(within(dlg).getByRole('button', {name: '取消'}));
    expect((screen.getByLabelText('章节标题') as HTMLInputElement).value).toBe('来信（改）');
    fireEvent.click(screen.getByLabelText('关闭「章节属性」'));
    fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', {name: '放弃修改'}));
    expect(screen.queryByTestId('panel-inspector')).toBeNull();
    expect(calls.every(c => c.method === 'GET')).toBe(true);
  });
  it('clean close does not ask', async () => {
    mount(); await selectCh1();
    fireEvent.click(screen.getByLabelText('关闭「章节属性」'));
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(screen.queryByTestId('panel-inspector')).toBeNull();
  });
  it('save through registry action: success only from server response (version bump)', async () => {
    mount(); const insp = await selectCh1();
    fireEvent.change(within(insp).getByLabelText('章节标题'), {target: {value: '新标题'}});
    await act(async () => { fireEvent.click(within(insp).getByRole('button', {name: '保存标题'})); });
    expect(await screen.findByText('已保存（版本 3）')).toBeTruthy();
    const post = calls.filter(c => c.method !== 'GET');
    expect(post).toEqual([{url: '/api/chapters/n1:1/rename', method: 'POST', body: {title: '新标题', version: 2}}]);
    expect(screen.queryByTestId('uw-inspector-dirty')).toBeNull();
  });
  it('save failure (409) is reported, never shown as saved; save-and-close keeps panel open', async () => {
    renameImpl = () => json({detail: {code: 'VERSION_CONFLICT', message: 'conflict'}}, 409);
    mount(); const insp = await selectCh1();
    fireEvent.change(within(insp).getByLabelText('章节标题'), {target: {value: '新标题'}});
    fireEvent.click(screen.getByLabelText('关闭「章节属性」'));
    await act(async () => { fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', {name: '保存并关闭'})); });
    await waitFor(() => expect(screen.getAllByText(/其他地方修改/).length).toBeGreaterThan(0));
    expect(screen.getByTestId('panel-inspector')).toBeTruthy();
    expect(screen.queryByText(/已保存/)).toBeNull();
    expect((screen.getByLabelText('章节标题') as HTMLInputElement).value).toBe('新标题');
  });
  it('refresh action is GET-only and reports real result', async () => {
    mount(); await waitFor(() => within(outline()).getByText(/第 1 章/));
    const before = calls.length;
    await act(async () => { fireEvent.click(within(outline()).getByRole('button', {name: '刷新章节列表'})); });
    expect(await within(outline()).findByText('已刷新')).toBeTruthy();
    expect(calls.slice(before).map(c => `${c.method} ${c.url}`)).toEqual(['GET /api/novels/n1/chapters']);
  });
});
