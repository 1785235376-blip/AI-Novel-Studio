// @vitest-environment jsdom
// [HERMIA-FE-20261024 M3-s1] dual canvas ↔ inspector linkage in ?uw=1: per-canvas selection shows node properties,
// edits go through the registry action with read-back verification, selection/canvas/project switches make no model
// calls and no writes, canvases stay isolated.
import {act, cleanup, fireEvent, render, screen, waitFor, within} from '@testing-library/react';
import {afterEach, beforeEach, describe, expect, it, vi} from 'vitest';
import {QueryClient, QueryClientProvider} from '@tanstack/react-query';
import {UnifiedWorkspacePreview} from '../UnifiedWorkspacePreview';
import {canvasStorageKey, type CvNode} from '../../rebuild/canvas/RebuildCanvas';
import {renameCanvasNode, registerCanvasNodeActions, CANVAS_NODE_ACTION_ID} from './canvasInspector';
import {ActionRegistry} from '../../workbench/actions';
import {LifecycleTracker} from '../../workbench/lifecycle';

if (typeof window !== 'undefined' && !('PointerEvent' in window)) {
  (window as unknown as {PointerEvent: unknown}).PointerEvent = class extends MouseEvent {};
}
const NOVELS = [{id: 'n1', title: '演示：雾港', genre: '', chapter_count: 0, word_count: 0, status: 'Writing'},
  {id: 'n2', title: '演示：灯塔', genre: '', chapter_count: 0, word_count: 0, status: 'Writing'}];
const MODEL_URL = /generat|model|llm|completion|chat|image|video|run|execute/i;
let calls: {url: string; method: string}[];
const json = (v: unknown, status = 200) => new Response(JSON.stringify(v), {status, headers: {'Content-Type': 'application/json'}});
const img: CvNode = {id: 'c1', t: 'image_generate', x: 0, y: 0, title: '雾港封面'};
const img2: CvNode = {id: 'c2', t: 'image_style', x: 0, y: 120, title: '冷色调'};
const vid: CvNode = {id: 'v1', t: 'storyboard_shot', x: 0, y: 0, title: '开场镜头'};
beforeEach(() => {
  localStorage.clear(); calls = [];
  localStorage.setItem(canvasStorageKey('image', 'n1'), JSON.stringify({nodes: [img, img2], edges: [{id: 'e1', a: 'c2', b: 'c1'}]}));
  localStorage.setItem(canvasStorageKey('video', 'n1'), JSON.stringify({nodes: [vid], edges: []}));
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    calls.push({url: String(url), method: init?.method ?? 'GET'});
    if (url === '/api/novels') return json(NOVELS);
    if (/^\/api\/novels\/n\d\/chapters$/.test(url)) return json([]);
    return json({detail: 'nf'}, 404);
  }));
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });
const mount = () => render(<QueryClientProvider client={new QueryClient({defaultOptions: {queries: {retry: false}}})}><UnifiedWorkspacePreview /></QueryClientProvider>);
const pick = (id: string) => { fireEvent.pointerDown(document.querySelector(`[data-node-id=${id}] .box`)!, {button: 0, clientX: 5, clientY: 5}); fireEvent.pointerUp(document.querySelector('svg.rcv-svg')!); };
const insp = () => screen.getByTestId('uw-node-inspector');
const badCalls = (from: number) => calls.slice(from).filter(c => c.method !== 'GET' || MODEL_URL.test(c.url.replace('/experimental/workspace/tasks', '')));
const showExec = async () => { fireEvent.click(screen.getByTestId('uw-open-execution')); await screen.findByTestId('uw-execution-canvas'); };
const showCreative = async () => { fireEvent.click(screen.getByTestId('uw-main-tabs').querySelector('[data-panel-tab=creative]')!); await screen.findByTestId('uw-creative-canvas'); };

describe('M3-s1 dual canvas ↔ inspector', () => {
  it('selecting in either canvas shows that node; selections are isolated; switching makes no model call / write', async () => {
    mount(); await screen.findByTestId('uw-creative-canvas');
    const before = calls.length; const snap = JSON.stringify({...localStorage});
    expect(screen.queryByTestId('uw-node-inspector')).toBeNull(); // chapter inspector by default
    pick('c1');
    await waitFor(() => expect(insp().dataset.nodeId).toBe('c1'));
    expect(insp().dataset.canvas).toBe('image');
    expect(screen.getByTestId('uw-node-inspector-title').textContent).toContain('创作画布');
    expect(screen.getByTestId('uw-node-type').textContent).toBe('生成图片');
    expect((screen.getByLabelText('节点标题') as HTMLInputElement).value).toBe('雾港封面');
    expect(insp().textContent).toContain('入 1 · 出 0');
    await showExec(); pick('v1');
    await waitFor(() => expect(insp().dataset.nodeId).toBe('v1'));
    expect(insp().dataset.canvas).toBe('video');
    expect(screen.getByTestId('uw-node-type').textContent).toBe('镜头');
    // creative selection untouched by the execution pick: send still uses c1
    await showCreative();
    const send = screen.getByRole('button', {name: '送到执行画布'}) as HTMLButtonElement;
    await waitFor(() => expect(send.disabled).toBe(false));
    expect(document.querySelector('[data-node-id=c1]')!.getAttribute('data-sel')).toBe('true'); // tab remount kept it
    expect(insp().dataset.nodeId).toBe('v1'); // remounting the creative canvas did not steal the inspector
    const execBefore = JSON.parse(localStorage.getItem(canvasStorageKey('video', 'n1'))!).nodes.length;
    fireEvent.click(send);
    await screen.findByText(/已把「雾港封面」送到执行画布/, {}, {timeout: 2000});
    const ex = JSON.parse(localStorage.getItem(canvasStorageKey('video', 'n1'))!);
    expect(ex.nodes).toHaveLength(execBefore + 1); expect(ex.nodes.at(-1).title).toBe('参考 · 雾港封面');
    expect(badCalls(before)).toEqual([]);
    expect(localStorage.getItem(canvasStorageKey('image', 'n1'))).toBe(JSON.parse(snap)[canvasStorageKey('image', 'n1')]);
  });
  it('edit title: saved via registry, read back, canvas shows it, selection kept; other canvas untouched; no network write', async () => {
    mount(); await screen.findByTestId('uw-creative-canvas');
    const before = calls.length; const vidRaw = localStorage.getItem(canvasStorageKey('video', 'n1'));
    pick('c1'); await waitFor(() => expect(insp().dataset.nodeId).toBe('c1'));
    fireEvent.change(screen.getByLabelText('节点标题'), {target: {value: '雾港封面·夜'}});
    fireEvent.click(within(insp()).getByRole('button', {name: '保存'}));
    await waitFor(() => expect(screen.getByTestId('uw-node-msg').textContent).toBe('已保存到本机草稿（未同步服务端）'));
    expect(JSON.parse(localStorage.getItem(canvasStorageKey('image', 'n1'))!).nodes.find((n: CvNode) => n.id === 'c1').title).toBe('雾港封面·夜');
    await waitFor(() => expect(document.querySelector('[data-node-id=c1] .ttl')!.textContent).toContain('雾港封面·夜'));
    expect(insp().dataset.nodeId).toBe('c1');
    expect(localStorage.getItem(canvasStorageKey('video', 'n1'))).toBe(vidRaw);
    expect(badCalls(before)).toEqual([]);
  });
  it('honest failure: storage write throws → alert, no success, draft kept', async () => {
    mount(); await screen.findByTestId('uw-creative-canvas');
    pick('c1'); await waitFor(() => expect(insp().dataset.nodeId).toBe('c1'));
    fireEvent.change(screen.getByLabelText('节点标题'), {target: {value: '新名'}});
    const orig = Storage.prototype.setItem;
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(function (this: Storage, k: string, v: string) {
      if (k.startsWith('poemseed.rebuild.canvas.')) throw new Error('quota'); return orig.call(this, k, v);
    });
    fireEvent.click(within(insp()).getByRole('button', {name: '保存'}));
    const m = await screen.findByTestId('uw-node-msg');
    expect(m.getAttribute('role')).toBe('alert'); expect(m.textContent).toContain('写入本机草稿失败');
    expect((screen.getByLabelText('节点标题') as HTMLInputElement).value).toBe('新名');
    expect(JSON.parse(localStorage.getItem(canvasStorageKey('image', 'n1'))!).nodes[0].title).toBe('雾港封面');
  });
  it('unsaved draft pins the inspector: another pick and project switch are refused', async () => {
    mount(); await screen.findByTestId('uw-creative-canvas');
    pick('c1'); await waitFor(() => expect(insp().dataset.nodeId).toBe('c1'));
    fireEvent.change(screen.getByLabelText('节点标题'), {target: {value: '草稿'}});
    pick('c2');
    expect(insp().dataset.nodeId).toBe('c1');
    expect(screen.getByTestId('uw-studio-status').textContent).toContain('未保存的修改');
    fireEvent.change(screen.getByLabelText('选择作品'), {target: {value: 'n2'}});
    expect(screen.getByTestId('uw-outline-blocked')).toBeTruthy();
    expect(insp().dataset.nodeId).toBe('c1');
    // canvas already highlights c2; discarding the draft follows the latest pick
    fireEvent.click(within(insp()).getByRole('button', {name: '放弃'}));
    await waitFor(() => expect(insp().dataset.nodeId).toBe('c2'));
  });
  it('project switch clears both selections and returns to chapter properties; no model call', async () => {
    mount(); await screen.findByTestId('uw-creative-canvas');
    pick('c1'); await waitFor(() => expect(insp().dataset.nodeId).toBe('c1'));
    const before = calls.length;
    fireEvent.change(screen.getByLabelText('选择作品'), {target: {value: 'n2'}});
    await waitFor(() => expect(screen.queryByTestId('uw-node-inspector')).toBeNull());
    expect((screen.getByRole('button', {name: '送到执行画布'}) as HTMLButtonElement).disabled).toBe(true);
    await act(async () => {});
    expect(badCalls(before)).toEqual([]);
  });
  it('blank click in the same canvas returns to chapter properties; viewport survives the post-save remount', async () => {
    mount(); await screen.findByTestId('uw-creative-canvas');
    const svg = () => document.querySelector('svg.rcv-svg')!;
    fireEvent.wheel(svg(), {deltaY: -100, clientX: 0, clientY: 0});
    const tf = document.querySelector('svg g[transform]')!.getAttribute('transform');
    expect(tf).not.toBe('translate(40,40) scale(1)');
    pick('c1'); await waitFor(() => expect(insp().dataset.nodeId).toBe('c1'));
    fireEvent.change(screen.getByLabelText('节点标题'), {target: {value: 'X'}});
    fireEvent.click(within(insp()).getByRole('button', {name: '保存'}));
    await screen.findByText('已保存到本机草稿（未同步服务端）');
    expect(document.querySelector('svg g[transform]')!.getAttribute('transform')).toBe(tf);
    fireEvent.pointerDown(svg(), {button: 0, clientX: 900, clientY: 900}); fireEvent.pointerUp(svg());
    await waitFor(() => expect(screen.queryByTestId('uw-node-inspector')).toBeNull());
  });
});

describe('renameCanvasNode / action', () => {
  it('rejects empty title, missing node, and reports done only after read-back', async () => {
    expect(() => renameCanvasNode({kind: 'image', scope: 'n1', id: 'c1', title: '  '})).toThrow('标题不能为空');
    expect(() => renameCanvasNode({kind: 'image', scope: 'n1', id: 'zz', title: 'a'})).toThrow('节点已不存在');
    expect(() => renameCanvasNode({kind: 'video', scope: 'nX', id: 'v1', title: 'a'})).toThrow('读不到');
    const tr = new LifecycleTracker(); const reg = new ActionRegistry(tr); registerCanvasNodeActions(reg);
    const ctx = (input: unknown) => ({token: tr.current(), targetId: null, targetVersion: null, permissions: new Set<string>(), input});
    const orig = Storage.prototype.setItem;
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(function (this: Storage, k: string, v: string) {
      return orig.call(this, k, v.replace('"新"', '"别的"')); // silently corrupts the write
    });
    const r = await reg.execute(CANVAS_NODE_ACTION_ID, ctx({kind: 'video', scope: 'n1', id: 'v1', title: '新'}));
    expect(r.status).toBe('error');
    expect(String((r as {error: Error}).error.message)).toContain('读回不一致');
  });
});
