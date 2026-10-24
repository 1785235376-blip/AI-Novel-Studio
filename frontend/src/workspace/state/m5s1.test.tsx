// @vitest-environment jsdom
// [HERMIA-FE-20261024 M5-s1] state isolation + async robustness for ?uw=1.
import {act, cleanup, fireEvent, render, screen, waitFor, within} from '@testing-library/react';
import {afterEach, beforeEach, describe, expect, it, vi} from 'vitest';
import {QueryClient, QueryClientProvider} from '@tanstack/react-query';
import {UnifiedWorkspacePreview} from '../UnifiedWorkspacePreview';
import {canvasStorageKey, type CvNode} from '../../rebuild/canvas/RebuildCanvas';
import {DraftStore} from './draftStore';
import {LatestGate, withTimeout, WORKSPACE_TIMEOUTS, WorkspaceTimeoutError, READ_TIMEOUT_TEXT, WRITE_TIMEOUT_TEXT} from './async';
import {ActionRegistry} from '../../workbench/actions';
import {LifecycleTracker} from '../../workbench/lifecycle';

if (typeof window !== 'undefined' && !('PointerEvent' in window)) {
  (window as unknown as {PointerEvent: unknown}).PointerEvent = class extends MouseEvent {};
}
const NOVELS = [{id: 'n1', title: '演示：雾港', genre: '', chapter_count: 1, word_count: 0, status: 'Writing'},
  {id: 'n2', title: '演示：灯塔', genre: '', chapter_count: 1, word_count: 0, status: 'Writing'}];
const CH = (n: string, title: string, version = 1) => [{id: `${n}c1`, novel_id: n, number: 1, title, word_count: 10, status: 'Draft', version}];
type Deferred = {resolve: (r: Response) => void; reject: (e: unknown) => void};
let calls: {url: string; method: string}[];
let hold: Record<string, Deferred[]>; // url → pending deferreds (when holding)
let holding: Set<string>;
const json = (v: unknown, status = 200) => new Response(JSON.stringify(v), {status, headers: {'Content-Type': 'application/json'}});
const img: CvNode = {id: 'c1', t: 'image_generate', x: 0, y: 0, title: '雾港封面'};
const img2: CvNode = {id: 'c2', t: 'image_style', x: 0, y: 120, title: '冷色调'};
const MODEL_URL = /generat|model|llm|completion|chat|image|video|run|execute/i;
const badCalls = (from = 0) => calls.slice(from).filter(c => c.method !== 'GET' || MODEL_URL.test(c.url.replace('/experimental/workspace/tasks', '')));
beforeEach(() => {
  localStorage.clear(); calls = []; hold = {}; holding = new Set();
  localStorage.setItem(canvasStorageKey('image', 'n1'), JSON.stringify({nodes: [img, img2], edges: []}));
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    const u = String(url); calls.push({url: u, method: init?.method ?? 'GET'});
    if (holding.has(u)) return new Promise<Response>((resolve, reject) => { (hold[u] ??= []).push({resolve, reject}); });
    if (u === '/api/novels') return json(NOVELS);
    const m = /^\/api\/novels\/(n\d)\/chapters$/.exec(u); if (m) return json(CH(m[1], m[1] === 'n1' ? '雾港·第一章' : '灯塔·第一章'));
    return json({detail: 'nf'}, 404);
  }));
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); vi.useRealTimers(); WORKSPACE_TIMEOUTS.readMs = 15000; WORKSPACE_TIMEOUTS.writeMs = 20000; });
const mount = () => render(<QueryClientProvider client={new QueryClient({defaultOptions: {queries: {retry: false}}})}><UnifiedWorkspacePreview /></QueryClientProvider>);
const pick = (id: string) => { fireEvent.pointerDown(document.querySelector(`[data-node-id=${id}] .box`)!, {button: 0, clientX: 5, clientY: 5}); fireEvent.pointerUp(document.querySelector('svg.rcv-svg')!); };
const nodeInsp = () => screen.getByTestId('uw-node-inspector');
const selectChapter = async (title: string) => { fireEvent.click(await screen.findByText(title, {exact: false, selector: 'button *, button'})); await screen.findByTestId('uw-inspector'); };
const switchProject = (v: string) => fireEvent.change(screen.getByLabelText('选择作品'), {target: {value: v}});
const dockSelect = () => screen.getByLabelText('「章节属性」停靠位置') as HTMLSelectElement;
const fireUnload = () => { const e = new Event('beforeunload', {cancelable: true}) as BeforeUnloadEvent; window.dispatchEvent(e); return e.defaultPrevented; };

describe('M5-s1 (a) project switch isolation + stale responses', () => {
  it('out-of-order chapter responses: the previous project’s late response never shows in the new project', async () => {
    holding.add('/api/novels/n1/chapters'); holding.add('/api/novels/n2/chapters');
    mount(); await waitFor(() => expect(hold['/api/novels/n1/chapters']?.length).toBe(1));
    switchProject('n2');
    await waitFor(() => expect(hold['/api/novels/n2/chapters']?.length).toBe(1));
    // n2 resolves first, then n1's stale response arrives late
    await act(async () => { hold['/api/novels/n2/chapters'][0].resolve(json(CH('n2', '灯塔·第一章'))); });
    await screen.findByText(/灯塔·第一章/);
    await act(async () => { hold['/api/novels/n1/chapters'][0].resolve(json(CH('n1', '雾港·第一章'))); });
    await act(async () => {});
    expect(screen.queryByText(/雾港·第一章/)).toBeNull();
    expect((screen.getByLabelText('选择作品') as HTMLSelectElement).value).toBe('n2');
    expect(badCalls()).toEqual([]);
  });
  it('switch resets chapter selection, canvas selection and node inspector to the new project', async () => {
    mount(); await selectChapter('雾港·第一章');
    pick('c1'); await waitFor(() => expect(nodeInsp().dataset.nodeId).toBe('c1'));
    switchProject('n2');
    await waitFor(() => expect(screen.queryByTestId('uw-node-inspector')).toBeNull());
    expect(screen.queryByTestId('uw-inspector')).toBeNull(); // no chapter carried over
    await screen.findByText(/灯塔·第一章/);
    expect((screen.getByRole('button', {name: '送到执行画布'}) as HTMLButtonElement).disabled).toBe(true);
  });
  it('an in-flight save from the previous project resolves as stale (lifecycle epoch bumped on switch)', async () => {
    const tr = new LifecycleTracker(); tr.update({projectId: 'n1'});
    const reg = new ActionRegistry(tr); let release!: () => void;
    reg.register({id: 'x', label: 'x', surfaces: [], run: () => new Promise(r => { release = () => r('ok'); })});
    const p = reg.execute('x', {token: tr.current(), targetId: null, targetVersion: null, permissions: new Set()});
    tr.update({projectId: 'n2'}); release();
    expect((await p).status).toBe('stale');
  });
});

describe('M5-s1fix host-level stale + listener lifecycle  [HERMIA-FE-20261024 M5-s1fix]', () => {
  it('host: refresh started in project A, switch to B, A’s late result is stale and not applied', async () => {
    mount(); await screen.findByText(/雾港·第一章/);
    holding.add('/api/novels/n1/chapters');
    fireEvent.click(screen.getByRole('button', {name: '刷新章节列表'}));
    await waitFor(() => expect(hold['/api/novels/n1/chapters']?.length).toBe(1));
    switchProject('n2'); await screen.findByText(/灯塔·第一章/);
    await act(async () => { hold['/api/novels/n1/chapters'][0].resolve(json(CH('n1', '雾港·STALE'))); });
    await act(async () => { await new Promise(r => setTimeout(r, 20)); });
    expect(screen.queryByText('已刷新')).toBeNull();
    expect(screen.queryByText('刷新失败，请重试')).toBeNull();
    expect(screen.queryByText(/STALE/)).toBeNull();
    expect((screen.getByLabelText('选择作品') as HTMLSelectElement).value).toBe('n2');
  });
  it('beforeunload listener is attached only while dirty and removed after discard', async () => {
    const add = vi.spyOn(window, 'addEventListener'); const rem = vi.spyOn(window, 'removeEventListener');
    const live = () => add.mock.calls.filter(c => c[0] === 'beforeunload').length - rem.mock.calls.filter(c => c[0] === 'beforeunload').length;
    mount(); await selectChapter('雾港·第一章');
    const base = live();
    fireEvent.change(screen.getByLabelText('章节标题'), {target: {value: '脏'}});
    await waitFor(() => expect(live()).toBe(base + 1));
    fireEvent.click(screen.getByRole('button', {name: /放弃/}));
    await waitFor(() => expect(live()).toBe(base));
    expect(fireUnload()).toBe(false);
  });
  it('node save keeps a newer draft typed while the save is running (conditional clear)', async () => {
    mount(); await screen.findByTestId('uw-creative-canvas');
    pick('c1'); await waitFor(() => expect(nodeInsp().dataset.nodeId).toBe('c1'));
    fireEvent.change(screen.getByLabelText('节点标题'), {target: {value: 'X'}});
    const orig = Storage.prototype.setItem; let once = true;
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(function (this: Storage, k: string, v: string) {
      orig.call(this, k, v);
      if (once) { once = false; fireEvent.change(screen.getByLabelText('节点标题'), {target: {value: 'XY'}}); }
    });
    fireEvent.click(within(nodeInsp()).getByRole('button', {name: '保存'}));
    await within(nodeInsp()).findByText('已保存到本机草稿（未同步服务端）');
    expect((screen.getByLabelText('节点标题') as HTMLInputElement).value).toBe('XY');
    expect((within(nodeInsp()).getByRole('button', {name: '保存'}) as HTMLButtonElement).disabled).toBe(false);
  });
  it('read timeout: no 「还没有章节。」 next to the timeout message', async () => {
    WORKSPACE_TIMEOUTS.readMs = 30; holding.add('/api/novels/n1/chapters'); mount();
    await within(await screen.findByTestId('uw-outline')).findByText(READ_TIMEOUT_TEXT, {}, {timeout: 2000});
    expect(screen.queryByText('还没有章节。')).toBeNull();
  });
});

describe('M5-s1 (b) rapid switching last-wins', () => {
  it('rapid canvas picks → inspector shows the last one; rapid project A→B→A shows A data only', async () => {
    mount(); await screen.findByTestId('uw-creative-canvas');
    pick('c1'); pick('c2'); pick('c1'); pick('c2');
    await waitFor(() => expect(nodeInsp().dataset.nodeId).toBe('c2'));
    expect((screen.getByLabelText('节点标题') as HTMLInputElement).value).toBe('冷色调');
    holding.add('/api/novels/n2/chapters');
    switchProject('n2'); switchProject('n1');
    await screen.findByText(/雾港·第一章/);
    await act(async () => { hold['/api/novels/n2/chapters']?.[0]?.resolve(json(CH('n2', '灯塔·第一章'))); });
    await act(async () => {});
    expect(screen.queryByText(/灯塔·第一章/)).toBeNull();
  });
  it('LatestGate: only the newest token is latest; begin() aborts the previous signal', () => {
    const g = new LatestGate(); const a = g.begin(); const b = g.begin();
    expect(a.signal.aborted).toBe(true); expect(g.isLatest(a)).toBe(false); expect(g.isLatest(b)).toBe(true);
    g.cancel(); expect(g.isLatest(b)).toBe(false); expect(b.signal.aborted).toBe(true);
  });
});

describe('M5-s1 (c) unsaved edits', () => {
  it('chapter title draft survives redock + collapse/expand and is guarded on project switch + window close', async () => {
    mount(); await selectChapter('雾港·第一章');
    expect(fireUnload()).toBe(false); // clean → no prompt
    fireEvent.change(screen.getByLabelText('章节标题'), {target: {value: '雾港·改'}});
    fireEvent.change(dockSelect(), {target: {value: 'bottom'}});
    fireEvent.change(dockSelect(), {target: {value: 'left'}});
    const sec = screen.getByTestId('panel-inspector');
    fireEvent.click(within(sec).getByRole('button', {name: '折叠'}));
    fireEvent.click(await within(sec).findByRole('button', {name: '展开'}));
    expect((await screen.findByLabelText('章节标题') as HTMLInputElement).value).toBe('雾港·改');
    expect(screen.getByTestId('uw-inspector-dirty')).toBeTruthy();
    expect(fireUnload()).toBe(true);
    switchProject('n2');
    expect(screen.getByTestId('uw-outline-blocked').textContent).toContain('未保存');
    expect((screen.getByLabelText('选择作品') as HTMLSelectElement).value).toBe('n1');
    fireEvent.click(screen.getByRole('button', {name: '放弃修改'}));
    expect(fireUnload()).toBe(false);
    switchProject('n2'); await screen.findByText(/灯塔·第一章/);
    expect(badCalls()).toEqual([]);
  });
  it('node title draft survives redock and main-tab switch; window close guarded', async () => {
    mount(); await screen.findByTestId('uw-creative-canvas');
    pick('c1'); await waitFor(() => expect(nodeInsp().dataset.nodeId).toBe('c1'));
    fireEvent.change(screen.getByLabelText('节点标题'), {target: {value: '夜雾'}});
    fireEvent.change(dockSelect(), {target: {value: 'bottom'}});
    fireEvent.click(screen.getByTestId('uw-open-execution')); await screen.findByTestId('uw-execution-canvas');
    fireEvent.click(screen.getByTestId('uw-main-tabs').querySelector('[data-panel-tab=creative]')!); await screen.findByTestId('uw-creative-canvas');
    expect((screen.getByLabelText('节点标题') as HTMLInputElement).value).toBe('夜雾');
    expect(fireUnload()).toBe(true);
    pick('c2'); expect(nodeInsp().dataset.nodeId).toBe('c1');
  });
  it('concurrent save + switch: switch refused while the save is in flight; after confirmed save the switch works', async () => {
    mount(); await selectChapter('雾港·第一章');
    holding.add('/api/chapters/n1c1/rename');
    fireEvent.change(screen.getByLabelText('章节标题'), {target: {value: '雾港·新'}});
    fireEvent.click(screen.getByRole('button', {name: '保存标题'}));
    await waitFor(() => expect(hold['/api/chapters/n1c1/rename']?.length).toBe(1));
    switchProject('n2');
    expect(screen.getByTestId('uw-outline-blocked')).toBeTruthy();
    expect(fireUnload()).toBe(true);
    await act(async () => { hold['/api/chapters/n1c1/rename'][0].resolve(json({...CH('n1', '雾港·新', 2)[0]})); });
    await screen.findByText('已保存（版本 2）');
    expect(fireUnload()).toBe(false);
    switchProject('n2'); await screen.findByText(/灯塔·第一章/);
  });
  it('typing during an in-flight save keeps the newer text dirty (not silently dropped)', async () => {
    mount(); await selectChapter('雾港·第一章');
    holding.add('/api/chapters/n1c1/rename');
    fireEvent.change(screen.getByLabelText('章节标题'), {target: {value: 'A'}});
    fireEvent.click(screen.getByRole('button', {name: '保存标题'}));
    await waitFor(() => expect(hold['/api/chapters/n1c1/rename']?.length).toBe(1));
    fireEvent.change(screen.getByLabelText('章节标题'), {target: {value: 'AB'}});
    await act(async () => { hold['/api/chapters/n1c1/rename'][0].resolve(json({...CH('n1', 'A', 2)[0]})); });
    await screen.findByText('已保存（版本 2）');
    expect((screen.getByLabelText('章节标题') as HTMLInputElement).value).toBe('AB');
    expect(screen.getByTestId('uw-inspector-dirty')).toBeTruthy();
  });
  it('DraftStore: equal-to-base is not dirty; clear by prefix', () => {
    const s = new DraftStore(); s.set('a', {value: 'x', base: 'x'}); expect(s.anyDirty()).toBe(false);
    s.set('chapter:n1:c', {value: 'y', base: 'x'}); s.set('node:n2:image:c1', {value: 'z', base: 'x'});
    s.clear('chapter:'); expect(s.dirtyKeys()).toEqual(['node:n2:image:c1']);
  });
});

describe('M5-s1 (d) honest network errors and timeouts', () => {
  it('network failure on save: real error text, no success, draft kept', async () => {
    mount(); await selectChapter('雾港·第一章');
    (fetch as unknown as {mockImplementationOnce: (f: () => Promise<never>) => void}).mockImplementationOnce(async () => { throw new TypeError('Failed to fetch'); });
    fireEvent.change(screen.getByLabelText('章节标题'), {target: {value: '断网'}});
    fireEvent.click(screen.getByRole('button', {name: '保存标题'}));
    const al = await within(screen.getByTestId('uw-inspector')).findByRole('alert');
    expect(al.textContent).toBe('保存失败：网络错误。修改还在面板里。');
    expect(screen.queryByText(/^已保存/)).toBeNull();
    expect((screen.getByLabelText('章节标题') as HTMLInputElement).value).toBe('断网');
  });
  it('save timeout: unknown-result text, never "已保存"; draft kept', async () => {
    WORKSPACE_TIMEOUTS.writeMs = 30;
    mount(); await selectChapter('雾港·第一章');
    holding.add('/api/chapters/n1c1/rename');
    fireEvent.change(screen.getByLabelText('章节标题'), {target: {value: '超时'}});
    fireEvent.click(screen.getByRole('button', {name: '保存标题'}));
    const al = await within(screen.getByTestId('uw-inspector')).findByRole('alert', {}, {timeout: 2000});
    expect(al.textContent).toBe(WRITE_TIMEOUT_TEXT);
    // late success after the timeout is ignored (no fake success, draft still there)
    await act(async () => { hold['/api/chapters/n1c1/rename'][0].resolve(json({...CH('n1', '超时', 2)[0]})); });
    expect(screen.queryByText(/^已保存/)).toBeNull();
    expect(screen.getByTestId('uw-inspector-dirty')).toBeTruthy();
  });
  it('read timeout: outline shows 读取超时 instead of endless loading', async () => {
    WORKSPACE_TIMEOUTS.readMs = 30;
    holding.add('/api/novels/n1/chapters');
    mount();
    const a = within(await screen.findByTestId('uw-outline')).findByText(READ_TIMEOUT_TEXT, {}, {timeout: 2000});
    expect((await a).getAttribute('data-state')).toBe('timeout');
    expect(screen.queryByText('正在读取章节…')).toBeNull();
  });
  it('withTimeout: resolves in time; rejects with WorkspaceTimeoutError; late rejection after timeout ignored', async () => {
    await expect(withTimeout(Promise.resolve(1), 50, 'read')).resolves.toBe(1);
    let rej!: (e: unknown) => void; const p = new Promise((_, r) => { rej = r; });
    const t = withTimeout(p, 10, 'write');
    await expect(t).rejects.toBeInstanceOf(WorkspaceTimeoutError);
    rej(new Error('late'));
    let res!: (v: number) => void; const q = new Promise<number>(r => { res = r; });
    const seen: unknown[] = []; const t2 = withTimeout(q, 10, 'read').then(v => seen.push(v), e => seen.push(e));
    await new Promise(r => setTimeout(r, 30)); res(7); await t2; await Promise.resolve();
    expect(seen).toHaveLength(1); expect(seen[0]).toBeInstanceOf(WorkspaceTimeoutError);
  });
});
