// @vitest-environment jsdom
// [HERMIA-FE-20261024 M2-s1] Real creative/execution/tasks panels in the ?uw=1 preview + their registry actions.
import {act, cleanup, fireEvent, render, screen, waitFor, within} from '@testing-library/react';
import {afterEach, beforeEach, describe, expect, it, vi} from 'vitest';
import {QueryClient, QueryClientProvider} from '@tanstack/react-query';
import {UnifiedWorkspacePreview} from '../UnifiedWorkspacePreview';
import {registerStudioPreviewActions, STUDIO_ACTION_IDS, STUDIO_PREVIEW_PANELS} from './studioPreviewPanels';
import {canvasStorageKey, type CvNode} from '../../rebuild/canvas/RebuildCanvas';
import {ActionRegistry} from '../../workbench/actions';
import {LifecycleTracker} from '../../workbench/lifecycle';
import {ShortcutTable} from '../actions/layoutActions';

if (typeof window !== 'undefined' && !('PointerEvent' in window)) {
  (window as unknown as {PointerEvent: unknown}).PointerEvent = class extends MouseEvent {};
}
const NOVELS = [{id: 'n1', title: '演示：雾港', genre: '', chapter_count: 0, word_count: 0, status: 'Writing'}];
type Call = {url: string; method: string};
let calls: Call[];
const json = (v: unknown, status = 200) => new Response(JSON.stringify(v), {status, headers: {'Content-Type': 'application/json'}});
beforeEach(() => {
  localStorage.clear(); calls = [];
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    const method = init?.method ?? 'GET'; calls.push({url: String(url), method});
    if (url === '/api/novels') return json(NOVELS);
    if (url === '/api/novels/n1/chapters') return json([]);
    return json({detail: 'nf'}, 404);
  }));
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.useRealTimers(); });

function mount() {
  const qc = new QueryClient({defaultOptions: {queries: {retry: false}}});
  return render(<QueryClientProvider client={qc}><UnifiedWorkspacePreview /></QueryClientProvider>);
}
const MODEL_URL = /generat|model|llm|completion|chat|image|video|run|execute/i;
const node: CvNode = {id: 'a1', t: 'image_generate', x: 0, y: 0, title: '雾港封面'};

describe('studio preview panels (real components)', () => {
  it('no placeholder left: creative + execution are RebuildCanvas, tasks is TaskCenterPanel; capability honest', async () => {
    mount();
    await screen.findByTestId('uw-creative-canvas');
    expect(document.querySelector('[data-state="not-connected"]')).toBeNull();
    expect(screen.getByRole('application', {name: '图片无限画布'})).toBeTruthy();
    expect(screen.getByTestId('uw-tasks')).toBeTruthy();
    expect(Object.fromEntries(STUDIO_PREVIEW_PANELS.map(p => [p.id, p.capability]))).toEqual({creative: 'local-only', execution: 'local-only', tasks: 'partial'});
    // load path: GET only, no model/generation endpoint
    await waitFor(() => expect(calls.some(c => c.url.includes('/experimental/workspace/tasks'))).toBe(true));
    expect(calls.every(c => c.method === 'GET')).toBe(true);
    expect(calls.filter(c => MODEL_URL.test(c.url.replace('/experimental/workspace/tasks', '')))).toEqual([]);
  });
  it('送到执行画布: disabled with reason until a node is selected; then writes the local execution draft; no POST', async () => {
    localStorage.setItem(canvasStorageKey('image', 'n1'), JSON.stringify({nodes: [node], edges: []}));
    mount();
    expect((await screen.findByTestId('uw-send-reason')).textContent).toBe('还没有选中作品');
    await screen.findByTestId('uw-creative-canvas');
    const btn = screen.getByRole('button', {name: '送到执行画布'});
    expect((btn as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByTestId('uw-send-reason').textContent).toBe('先在创作画布选中一个节点');
    fireEvent.pointerDown(document.querySelector('[data-node-id=a1] .box')!, {button: 0, clientX: 5, clientY: 5});
    fireEvent.pointerUp(window);
    await waitFor(() => expect((btn as HTMLButtonElement).disabled).toBe(false));
    fireEvent.click(btn); fireEvent.click(btn); // double trigger
    expect(await screen.findByTestId('uw-studio-status', {}, {timeout: 2000})).toBeTruthy();
    const exec = JSON.parse(localStorage.getItem(canvasStorageKey('video', 'n1'))!);
    expect(exec.nodes).toHaveLength(1);
    expect(exec.nodes[0]).toMatchObject({t: 'image_reference', title: '参考 · 雾港封面'});
    expect(calls.every(c => c.method === 'GET')).toBe(true);
  });
  it('N5: toolbar 执行画布 button + tab bring the execution canvas to front; panel switch triggers no model call', async () => {
    mount();
    await screen.findByTestId('uw-creative-canvas');
    const before = calls.length;
    fireEvent.click(screen.getByTestId('uw-open-execution'));
    await waitFor(() => expect(screen.getByTestId('uw-execution-canvas')).toBeTruthy());
    expect(within(screen.getByTestId('uw-execution-canvas')).getByRole('application', {name: '视频无限画布'})).toBeTruthy();
    expect(screen.getByTestId('uw-main-tabs').querySelector('[data-panel-tab=execution]')!.getAttribute('aria-selected')).toBe('true');
    expect(calls.slice(before).filter(c => c.method !== 'GET' || MODEL_URL.test(c.url.replace('/experimental/workspace/tasks', '')))).toEqual([]);
  });
  it('N5: Mod+Alt+E opens the execution canvas even after it was closed', async () => {
    mount();
    await screen.findByTestId('uw-creative-canvas');
    const close = screen.queryByLabelText('关闭「执行画布」');
    if (close) { fireEvent.click(close); await waitFor(() => expect(screen.queryByTestId('panel-execution')).toBeNull()); }
    fireEvent.keyDown(window, {key: 'e', code: 'KeyE', ctrlKey: true, altKey: true});
    await waitFor(() => expect(screen.getByTestId('uw-execution-canvas')).toBeTruthy());
  });
});

describe('registerStudioPreviewActions', () => {
  function setup(over: Partial<Parameters<typeof registerStudioPreviewActions>[2]> = {}) {
    const tracker = new LifecycleTracker(); const reg = new ActionRegistry(tracker); const table = new ShortcutTable();
    const shown: string[] = []; const linked: CvNode[] = [];
    let novel: string | null = 'n1'; let sel: CvNode | null = null;
    reg.register({id: 'layout.showPanel', label: 'x', surfaces: ['toolbar'], run: async () => null});
    const r = registerStudioPreviewActions(reg, table, {getNovelId: () => novel, getSelectedNode: () => sel, onLinked: n => linked.push(n),
      showPanel: async id => { shown.push(id); return id; }, ...over}, 30);
    const ctx = () => ({token: tracker.current(), targetId: null, targetVersion: null, permissions: new Set<string>()});
    return {reg, table, r, shown, linked, ctx, setNovel: (v: string | null) => { novel = v; }, setSel: (v: CvNode | null) => { sel = v; }};
  }
  it('disabled reasons: no novel / no selection', () => {
    const s = setup();
    expect(s.reg.availability(STUDIO_ACTION_IDS.sendToExecution, s.ctx())).toEqual({enabled: false, reason: '先在创作画布选中一个节点'});
    s.setNovel(null);
    expect(s.reg.availability(STUDIO_ACTION_IDS.sendToExecution, s.ctx())).toEqual({enabled: false, reason: '还没有选中作品'});
  });
  it('shortcuts claimed in the shared table; conflicts reported, not stolen; dispose releases', () => {
    const s = setup();
    expect(s.r.conflicts).toEqual([]);
    expect(s.reg.get(STUDIO_ACTION_IDS.openExecution)?.shortcut).toBe('Mod+Alt+E');
    expect(s.table.claim('Mod+Alt+E', 'other')).toEqual({ok: false, conflictWith: STUDIO_ACTION_IDS.openExecution});
    s.r.dispose();
    expect(s.reg.get(STUDIO_ACTION_IDS.openExecution)).toBeUndefined();
    expect(s.table.claim('Mod+Alt+E', 'other')).toEqual({ok: true});
    const tracker = new LifecycleTracker(); const reg = new ActionRegistry(tracker); const table = new ShortcutTable();
    table.claim('Mod+Alt+T', 'someone');
    const r2 = registerStudioPreviewActions(reg, table, {getNovelId: () => null, getSelectedNode: () => null, onLinked: () => {}, showPanel: async () => null});
    expect(r2.conflicts).toEqual([{actionId: STUDIO_ACTION_IDS.openTasks, shortcut: 'Mod+Alt+T', conflictWith: 'someone'}]);
    expect(reg.get(STUDIO_ACTION_IDS.openTasks)?.shortcut).toBeUndefined();
  });
  it('double trigger: second execute while pending is duplicate; link + show run once', async () => {
    const s = setup(); s.setSel(node);
    const [a, b] = await act(() => Promise.all([s.reg.execute(STUDIO_ACTION_IDS.sendToExecution, s.ctx()), s.reg.execute(STUDIO_ACTION_IDS.sendToExecution, s.ctx())]));
    expect([a.status, b.status]).toEqual(['done', 'duplicate']);
    expect(s.linked).toHaveLength(1);
    const [c, d] = await act(() => Promise.all([s.reg.execute(STUDIO_ACTION_IDS.openExecution, s.ctx()), s.reg.execute(STUDIO_ACTION_IDS.openExecution, s.ctx())]));
    expect([c.status, d.status]).toEqual(['done', 'duplicate']);
    expect(s.shown).toEqual(['execution']);
  });
  it('open actions are disabled with a reason when the layout action is missing', () => {
    const tracker = new LifecycleTracker(); const reg = new ActionRegistry(tracker);
    registerStudioPreviewActions(reg, new ShortcutTable(), {getNovelId: () => 'n1', getSelectedNode: () => null, onLinked: () => {}, showPanel: async () => null});
    expect(reg.availability(STUDIO_ACTION_IDS.openExecution, {token: tracker.current(), targetId: null, targetVersion: null, permissions: new Set()})).toEqual({enabled: false, reason: '布局还没有准备好'});
  });
});
