// @vitest-environment jsdom
// [HERMIA-FE-20261024 M2-s1fix] 300ms double-trigger guard (fake timers), sent node inside the execution viewport,
// layout.showPanel in the palette + Mod+Alt+P, aria-disabled palette items, single task GET on mount (StrictMode),
// focus moves to the task panel after Mod+Alt+T.
import {StrictMode} from 'react';
import {act, cleanup, fireEvent, render, screen, waitFor} from '@testing-library/react';
import {afterEach, beforeEach, describe, expect, it, vi} from 'vitest';
import {QueryClient, QueryClientProvider} from '@tanstack/react-query';
import {UnifiedWorkspacePreview} from '../UnifiedWorkspacePreview';
import {ExecutionCanvasPanel, registerStudioPreviewActions, STUDIO_ACTION_IDS, STUDIO_MIN_BUSY_MS} from './studioPreviewPanels';
import {canvasStorageKey, type CvNode} from '../../rebuild/canvas/RebuildCanvas';
import {linkToExecution} from '../../rebuild/canvas/DualCanvas';
import {ActionRegistry} from '../../workbench/actions';
import {LifecycleTracker} from '../../workbench/lifecycle';
import {DEFAULT_LAYOUT_SHORTCUTS, LAYOUT_ACTION_IDS, layoutActionDefinitions, ShortcutTable} from '../actions/layoutActions';
import {TaskCenterPanel} from '../../taskcenter/TaskCenter';

if (typeof window !== 'undefined' && !('PointerEvent' in window)) {
  (window as unknown as {PointerEvent: unknown}).PointerEvent = class extends MouseEvent {};
}
const NOVELS = [{id: 'n1', title: '演示：雾港', genre: '', chapter_count: 0, word_count: 0, status: 'Writing'}];
let calls: {url: string; method: string}[];
const json = (v: unknown, status = 200) => new Response(JSON.stringify(v), {status, headers: {'Content-Type': 'application/json'}});
beforeEach(() => {
  localStorage.clear(); calls = [];
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    calls.push({url: String(url), method: init?.method ?? 'GET'});
    if (url === '/api/novels') return json(NOVELS);
    if (url === '/api/novels/n1/chapters') return json([]);
    return json({detail: 'nf'}, 404);
  }));
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.useRealTimers(); });
const node: CvNode = {id: 'a1', t: 'image_generate', x: 0, y: 0, title: '雾港封面'};

describe('300ms double-trigger guard (fake timers, production STUDIO_MIN_BUSY_MS)', () => {
  function setup() {
    const tracker = new LifecycleTracker(); const reg = new ActionRegistry(tracker); const table = new ShortcutTable();
    const linked: CvNode[] = []; const shown: string[] = [];
    reg.register({id: 'layout.showPanel', label: 'x', surfaces: ['toolbar'], run: async () => null});
    registerStudioPreviewActions(reg, table, {getNovelId: () => 'n1', getSelectedNode: () => node, onLinked: n => linked.push(n),
      showPanel: async id => { shown.push(id); return id; }});
    const ctx = () => ({token: tracker.current(), targetId: null, targetVersion: null, permissions: new Set<string>()});
    return {reg, ctx, linked, shown};
  }
  it('uses 300ms by default', () => expect(STUDIO_MIN_BUSY_MS).toBe(300));
  it('two triggers 100ms apart run once (second is duplicate)', async () => {
    vi.useFakeTimers(); const s = setup();
    const a = s.reg.execute(STUDIO_ACTION_IDS.sendToExecution, s.ctx());
    await vi.advanceTimersByTimeAsync(100);
    const b = await s.reg.execute(STUDIO_ACTION_IDS.sendToExecution, s.ctx());
    expect(b.status).toBe('duplicate');
    await vi.advanceTimersByTimeAsync(300);
    expect((await a).status).toBe('done');
    expect(s.linked).toHaveLength(1);
    const c = s.reg.execute(STUDIO_ACTION_IDS.openTasks, s.ctx());
    await vi.advanceTimersByTimeAsync(100);
    expect((await s.reg.execute(STUDIO_ACTION_IDS.openTasks, s.ctx())).status).toBe('duplicate');
    await vi.advanceTimersByTimeAsync(300); await c;
    expect(s.shown).toEqual(['tasks']);
  });
  it('two triggers 350ms apart run twice', async () => {
    vi.useFakeTimers(); const s = setup();
    const a = s.reg.execute(STUDIO_ACTION_IDS.sendToExecution, s.ctx());
    await vi.advanceTimersByTimeAsync(350);
    expect((await a).status).toBe('done');
    const b = s.reg.execute(STUDIO_ACTION_IDS.sendToExecution, s.ctx());
    await vi.advanceTimersByTimeAsync(350);
    expect((await b).status).toBe('done');
    expect(s.linked).toHaveLength(2);
  });
});

describe('sent node lands inside the execution viewport', () => {
  // [HERMIA-FE-20261024 M2-s1fix2] spec change (Vera M2-s1fix medium): later sends now go to further grid columns so they
  // never overlap; only the first column (first 3 sends) is guaranteed inside the 320×280 minimum view. Overlap + the
  // 750px-wide real-panel case are covered in m2s1fix2.test.tsx.
  it('linkToExecution places the first column (3 sends) inside the default view of a 320×280 (minimum) execution panel', () => {
    for (let i = 0; i < 7; i++) linkToExecution('n1', {...node, id: `a${i}`});
    render(<ExecutionCanvasPanel novelId="n1" revision={1} />);
    const vpm = /translate\(([-\d.]+),([-\d.]+)\) scale\(([-\d.]+)\)/.exec(document.querySelector('svg g[transform]')!.getAttribute('transform')!)!;
    const [vx, vy, k] = vpm.slice(1).map(Number);
    const nodes = [...document.querySelectorAll('[data-node-id]')];
    expect(nodes).toHaveLength(7);
    for (const el of nodes.slice(0, 3)) {
      const [, x, y] = /translate\(([-\d.]+),([-\d.]+)\)/.exec(el.getAttribute('transform')!)!.map(Number);
      const sx = vx + x * k, sy = vy + y * k;
      expect(sx).toBeGreaterThanOrEqual(0); expect(sx + 180 * k).toBeLessThanOrEqual(320);
      expect(sy).toBeGreaterThanOrEqual(0); expect(sy + 60 * k).toBeLessThanOrEqual(280);
    }
  });
});

describe('layout.showPanel without input (palette / Mod+Alt+P)', () => {
  it('claims a free shortcut; targets first closed panel, else rotates main tabs; disabled with reason otherwise', () => {
    expect(DEFAULT_LAYOUT_SHORTCUTS['layout.showPanel']).toBe('Mod+Alt+P');
    const others = Object.entries(DEFAULT_LAYOUT_SHORTCUTS).filter(([k]) => k !== 'layout.showPanel').map(([, v]) => v);
    expect(others).not.toContain('Mod+Alt+P');
    let frames: Record<string, {id: string; dock: string; order: number; open: boolean; collapsed: boolean}> = {
      a: {id: 'a', dock: 'main', order: 0, open: true, collapsed: false},
      b: {id: 'b', dock: 'main', order: 1, open: true, collapsed: false},
      c: {id: 'c', dock: 'right', order: 0, open: false, collapsed: false},
    };
    const host = {specs: [{id: 'a'}, {id: 'b'}, {id: 'c'}], getState: () => ({frames, focusId: null}), dispatch: () => {}} as never;
    const show = layoutActionDefinitions(host).find(d => d.id === LAYOUT_ACTION_IDS.show)!;
    expect(show.surfaces).toContain('commandSearch'); expect(show.shortcut).toBe('Mod+Alt+P');
    const ctx = {token: {} as never, targetId: null, targetVersion: null, permissions: new Set<string>()};
    expect(show.available!(ctx)).toEqual({enabled: true});
    frames = {...frames, c: {...frames.c, open: true}};
    expect(show.available!(ctx)).toEqual({enabled: true});
    frames = {a: frames.a};
    expect(show.available!(ctx)).toEqual({enabled: false, reason: '没有可切换的面板'});
    expect(show.available!({...ctx, input: 'zzz'})).toEqual({enabled: false, reason: '没有这个面板'});
  });
});

function mount(strict = false) {
  const qc = new QueryClient({defaultOptions: {queries: {retry: false}}});
  const tree = <QueryClientProvider client={qc}><UnifiedWorkspacePreview /></QueryClientProvider>;
  return render(strict ? <StrictMode>{tree}</StrictMode> : tree);
}

describe('uw preview integration', () => {
  it('palette: 显示面板 listed; disabled items carry aria-disabled + reason; enabled ones do not', async () => {
    mount();
    await screen.findByTestId('uw-creative-canvas');
    fireEvent.click(screen.getByRole('button', {name: /搜索功能/}));
    const send = await screen.findByRole('option', {name: '送到执行画布'});
    expect(send.getAttribute('aria-disabled')).toBe('true');
    expect(send.getAttribute('title')).toBe('先在创作画布选中一个节点');
    const showOpt = screen.getByRole('option', {name: /显示面板/});
    expect(showOpt.getAttribute('aria-disabled')).toBeNull();
    expect(screen.getByRole('option', {name: '打开任务'}).getAttribute('aria-disabled')).toBeNull();
  });
  it('Mod+Alt+P via the shared table brings the hindmost main tab to the front', async () => {
    mount();
    await screen.findByTestId('uw-creative-canvas');
    const pressed = () => screen.getByTestId('uw-main-tabs').querySelector('[aria-pressed=true]')!.getAttribute('data-panel-tab');
    const first = pressed();
    fireEvent.keyDown(window, {key: 'p', code: 'KeyP', ctrlKey: true, altKey: true});
    await waitFor(() => expect(pressed()).not.toBe(first));
  });
  it('Mod+Alt+T moves DOM focus into the task panel', async () => {
    mount();
    await screen.findByTestId('uw-creative-canvas');
    (screen.getByTestId('uw-open-execution') as HTMLElement).focus();
    fireEvent.keyDown(window, {key: 't', code: 'KeyT', ctrlKey: true, altKey: true});
    await waitFor(() => expect(document.activeElement?.getAttribute('data-panel-id')).toBe('tasks'), {timeout: 2000});
  });
  it('task center reads tasks exactly once on mount, even under StrictMode', async () => {
    mount(true);
    await screen.findByTestId('uw-tasks');
    await waitFor(() => expect(calls.some(c => c.url.includes('/experimental/workspace/tasks'))).toBe(true));
    await act(() => new Promise(r => setTimeout(r, 50)));
    expect(calls.filter(c => c.url.includes('/experimental/workspace/tasks'))).toHaveLength(1);
    expect(calls.every(c => c.method === 'GET')).toBe(true);
  });
  it('TaskCenterPanel alone under StrictMode: one read', async () => {
    const list = vi.fn(async () => json({items: [], next_cursor: null}));
    vi.stubGlobal('fetch', list);
    const {studioTransport} = await import('../../creative/studioClient');
    render(<StrictMode><TaskCenterPanel projectId="n1" transport={studioTransport({sessionToken: ''})} identity="t:n1" active denied={false} busy={false}
      isCurrent={() => true} read={w => w()} mutate={w => w()} /></StrictMode>);
    await waitFor(() => expect(list).toHaveBeenCalled());
    await act(() => new Promise(r => setTimeout(r, 50)));
    expect(list).toHaveBeenCalledTimes(1);
  });
});
