// @vitest-environment jsdom
// [HERMIA-FE-20261024 M3-s1fix2] reveal request stays pending while the svg is 0×0 (Chrome tab-switch mount), runs once
// when a non-zero size first appears (ResizeObserver / rAF fallback), then never again (manual pan, resize, tab switch).
import {act, cleanup, fireEvent, render, screen, waitFor, within} from '@testing-library/react';
import {afterEach, beforeEach, describe, expect, it, vi} from 'vitest';
import {QueryClient, QueryClientProvider} from '@tanstack/react-query';
import {UnifiedWorkspacePreview} from '../UnifiedWorkspacePreview';
import {ExecutionCanvasPanel} from './studioPreviewPanels';
import {canvasStorageKey, type CvNode} from '../../rebuild/canvas/RebuildCanvas';
import {linkToExecution} from '../../rebuild/canvas/DualCanvas';

if (typeof window !== 'undefined' && !('PointerEvent' in window)) (window as unknown as {PointerEvent: unknown}).PointerEvent = class extends MouseEvent {};
const W = 186, H = 60; let size = {w: 0, h: 0};
const rect = (w: number, h: number) => ({left: 0, top: 0, width: w, height: h, right: w, bottom: h, x: 0, y: 0, toJSON: () => ({})}) as DOMRect;
const ros: Array<{cb: ResizeObserverCallback; on: boolean}> = [];
class FakeRO { e: {cb: ResizeObserverCallback; on: boolean}; constructor(cb: ResizeObserverCallback) { this.e = {cb, on: false}; ros.push(this.e); } observe() { this.e.on = true; } unobserve() {} disconnect() { this.e.on = false; } }
const fireResize = () => act(() => { ros.filter(r => r.on).forEach(r => r.cb([], r as unknown as ResizeObserver)); });
const img: CvNode = {id: 'c1', t: 'image_generate', x: 0, y: 0, title: '雾港封面'};
const NOVELS = [{id: 'n1', title: '演示：雾港', genre: '', chapter_count: 0, word_count: 0, status: 'Writing'}];
const json = (v: unknown, status = 200) => new Response(JSON.stringify(v), {status, headers: {'Content-Type': 'application/json'}});
beforeEach(() => {
  localStorage.clear(); ros.length = 0; size = {w: 0, h: 0};
  vi.stubGlobal('ResizeObserver', FakeRO);
  vi.spyOn(Element.prototype, 'getBoundingClientRect').mockImplementation(function (this: Element) { return this.tagName.toLowerCase() === 'svg' ? rect(size.w, size.h) : rect(0, 0); });
  vi.stubGlobal('fetch', vi.fn(async (url: string) => url === '/api/novels' ? json(NOVELS) : /chapters$/.test(url) ? json([]) : json({detail: 'nf'}, 404)));
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });
const tf = (root: Element) => root.querySelector('svg g[transform]')!.getAttribute('transform')!;
const lastBox = (root: Element) => {
  const [, vx, vy, k] = /translate\(([-\d.]+),([-\d.]+)\) scale\(([-\d.]+)\)/.exec(tf(root))!.map(Number);
  const [, x, y] = /translate\(([-\d.]+),([-\d.]+)\)/.exec([...root.querySelectorAll('[data-node-id]')].at(-1)!.getAttribute('transform')!)!.map(Number);
  return {l: vx + x * k, t: vy + y * k, r: vx + (x + W) * k, b: vy + (y + H) * k, k};
};
const inView = (root: Element, w = size.w, h = size.h) => { const b = lastBox(root); return b.l >= 0 && b.t >= 0 && b.r <= w && b.b <= h; };
const pan = (svg: Element, dx: number) => { fireEvent.pointerDown(svg, {button: 0, clientX: 600, clientY: 300}); fireEvent.pointerMove(svg, {clientX: 600 + dx, clientY: 300}); fireEvent.pointerUp(svg); };

describe('pending reveal (unit)', () => {
  beforeEach(() => { for (let i = 0; i < 12; i++) linkToExecution('n1', {...img, id: `a${i}`}); });
  it('rect 0×0 at mount → no pan; first non-zero size → reveals once (zoom kept), onRevealed once', () => {
    const done = vi.fn();
    const {container} = render(<ExecutionCanvasPanel novelId="n1" revealLast onRevealed={done} viewport={{x: -1200, y: 40, k: 1.1}} />);
    expect(tf(container)).toBe('translate(-1200,40) scale(1.1)'); expect(inView(container, 750, 449)).toBe(false); expect(done).not.toHaveBeenCalled();
    size = {w: 750, h: 449}; fireResize();
    expect(inView(container)).toBe(true); expect(lastBox(container).k).toBe(1.1); expect(done).toHaveBeenCalledTimes(1);
    pan(container.querySelector('svg')!, -900); const after = tf(container); expect(inView(container)).toBe(false);
    size = {w: 1310, h: 700}; fireResize(); size = {w: 750, h: 449}; fireResize();
    expect(tf(container)).toBe(after); expect(done).toHaveBeenCalledTimes(1);
  });
  it('fallback without ResizeObserver: rAF polling reveals once size appears', async () => {
    vi.stubGlobal('ResizeObserver', undefined);
    const {container} = render(<ExecutionCanvasPanel novelId="n1" revealLast viewport={{x: -1200, y: 40, k: 1}} />);
    expect(tf(container)).toBe('translate(-1200,40) scale(1)'); expect(inView(container, 750, 449)).toBe(false);
    size = {w: 750, h: 449};
    await waitFor(() => expect(inView(container)).toBe(true));
  });
});

describe('host: tab switch / remount after manual pan does not re-reveal', () => {
  it('send (0×0 mount) → reveal on size; pan away; creative and back, and close+reopen (remount) → stays where the user panned', async () => {
    localStorage.setItem(canvasStorageKey('image', 'n1'), JSON.stringify({nodes: [img], edges: []}));
    for (let i = 0; i < 12; i++) linkToExecution('n1', {...img, id: `a${i}`});
    render(<QueryClientProvider client={new QueryClient({defaultOptions: {queries: {retry: false}}})}><UnifiedWorkspacePreview /></QueryClientProvider>);
    await screen.findByTestId('uw-creative-canvas');
    fireEvent.change(screen.getByLabelText('分屏方式'), {target: {value: 'single'}}); // one main panel at a time → tab switch remounts (as in Chrome)
    await waitFor(() => expect(screen.getByTestId('main-zone').dataset.split).toBe('single'));
    fireEvent.pointerDown(document.querySelector('[data-node-id=c1] .box')!, {button: 0, clientX: 5, clientY: 5}); fireEvent.pointerUp(document.querySelector('svg.rcv-svg')!);
    const send = screen.getByRole('button', {name: '送到执行画布'}) as HTMLButtonElement;
    await waitFor(() => expect(send.disabled).toBe(false)); fireEvent.click(send);
    await screen.findByText(/已把「雾港封面」送到执行画布/, {}, {timeout: 2000});
    fireEvent.click(screen.getByTestId('uw-open-execution'));
    let ex = await screen.findByTestId('uw-execution-canvas');
    await waitFor(() => expect(ex.querySelectorAll('[data-node-id]').length).toBe(13));
    expect(inView(ex)).toBe(false); // still 0×0
    size = {w: 750, h: 449}; fireResize(); expect(inView(ex)).toBe(true);
    pan(within(ex).getByRole('application'), -900); const after = tf(ex);
    fireEvent.click(screen.getByTestId('uw-main-tabs').querySelector('[data-panel-tab=creative]')!); await screen.findByTestId('uw-creative-canvas');
    await waitFor(() => expect(screen.queryByTestId('uw-execution-canvas')).toBeNull()); // really unmounted
    size = {w: 0, h: 0};
    await waitFor(() => { fireEvent.click(screen.getByTestId('uw-main-tabs').querySelector('[data-panel-tab=execution]')!); expect(screen.getByTestId('uw-execution-canvas')).toBeTruthy(); }); ex = screen.getByTestId('uw-execution-canvas');
    size = {w: 750, h: 449}; fireResize();
    expect(tf(ex)).toBe(after);
    // close + reopen the execution panel (fresh RebuildCanvas mount) → still no re-reveal: the host request was consumed
    fireEvent.click(screen.getByRole('button', {name: '关闭「执行画布」'}));
    await waitFor(() => expect(screen.queryByTestId('uw-execution-canvas')).toBeNull());
    size = {w: 0, h: 0};
    fireEvent.change(screen.getByLabelText('重新打开面板'), {target: {value: 'execution'}});
    await waitFor(() => { fireEvent.click(screen.getByTestId('uw-main-tabs').querySelector('[data-panel-tab=execution]')!); expect(screen.getByTestId('uw-execution-canvas')).toBeTruthy(); });
    size = {w: 750, h: 449}; fireResize();
    expect(tf(screen.getByTestId('uw-execution-canvas'))).toBe(after);
  });
});
