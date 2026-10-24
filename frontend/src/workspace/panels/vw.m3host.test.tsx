// @vitest-environment jsdom
// [HERMIA-FE-20261024 VW-M3] host viewport via view-prefs adapter (session-only: preview has no real scope). jsdom only.
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


describe('[VW-M3] preview host viewport prefs', () => {
  it('pan → tab remount keeps view; reset returns to default; zero view-pref writes (novel isolation: adapter tests)', async () => {
    const NV2 = [...NOVELS, {...NOVELS[0], id: 'n2', title: '第二部'}];
    vi.stubGlobal('fetch', vi.fn(async (url: string) => url === '/api/novels' ? json(NV2) : /chapters$/.test(url) ? json([]) : json({detail: 'nf'}, 404)));
    const setSpy = vi.spyOn(Storage.prototype, 'setItem');
    localStorage.setItem(canvasStorageKey('image', 'n1'), JSON.stringify({nodes: [img], edges: []}));
    size = {w: 750, h: 449};
    render(<QueryClientProvider client={new QueryClient({defaultOptions: {queries: {retry: false}}})}><UnifiedWorkspacePreview /></QueryClientProvider>);
    let cv = await screen.findByTestId('uw-creative-canvas');
    expect(document.activeElement).toBe(document.body); // M4: mount / prefs load never steals focus
    const def = tf(cv);
    pan(within(cv).getByRole('application'), -300); const panned = tf(cv); expect(panned).not.toBe(def);
    fireEvent.change(screen.getByLabelText('分屏方式'), {target: {value: 'single'}});
    fireEvent.click(screen.getByTestId('uw-main-tabs').querySelector('[data-panel-tab=execution]')!);
    await waitFor(() => expect(screen.queryByTestId('uw-creative-canvas')).toBeNull());
    fireEvent.click(screen.getByTestId('uw-main-tabs').querySelector('[data-panel-tab=creative]')!);
    cv = await screen.findByTestId('uw-creative-canvas'); expect(tf(cv)).toBe(panned);
    fireEvent.click(screen.getByTestId('uw-reset-vp-image'));
    await waitFor(() => expect(tf(screen.getByTestId('uw-creative-canvas'))).toBe(def));
    expect(screen.getByTestId('uw-vp-status').textContent).toMatch(/仅本次会话/);
    expect(setSpy.mock.calls.filter(([k]) => String(k).includes('viewprefs'))).toEqual([]);
    expect(Object.keys(localStorage).filter(k => k.includes('viewprefs'))).toEqual([]);
    // view operations issue no backend writes (GET-only fetches)
    const calls = (fetch as unknown as {mock: {calls: [string, RequestInit?][]}}).mock.calls;
    expect(calls.filter(([, i]) => (i?.method ?? 'GET').toUpperCase() !== 'GET')).toEqual([]);
  });
  it('[VW-fix1] true remount: pan A → switch to B (fresh canvas, default view) → back to A restores A\'s pan', async () => {
    const NV2 = [...NOVELS, {...NOVELS[0], id: 'n2', title: '第二部'}];
    vi.stubGlobal('fetch', vi.fn(async (url: string) => url === '/api/novels' ? json(NV2) : /chapters$/.test(url) ? json([]) : json({detail: 'nf'}, 404)));
    localStorage.setItem(canvasStorageKey('image', 'n1'), JSON.stringify({nodes: [img], edges: []}));
    localStorage.setItem(canvasStorageKey('image', 'n2'), JSON.stringify({nodes: [img], edges: []}));
    size = {w: 750, h: 449};
    render(<QueryClientProvider client={new QueryClient({defaultOptions: {queries: {retry: false}}})}><UnifiedWorkspacePreview /></QueryClientProvider>);
    const cv1 = await screen.findByTestId('uw-creative-canvas');
    await waitFor(() => expect(cv1.querySelector('[data-node-id]')).toBeTruthy());
    const def = tf(cv1);
    pan(within(cv1).getByRole('application'), -300); const pannedA = tf(screen.getByTestId('uw-creative-canvas'));
    expect(pannedA).not.toBe(def);
    const sel = screen.getByLabelText('选择作品') as HTMLSelectElement;
    const svgBefore = screen.getByTestId('uw-creative-canvas').querySelector('svg');
    fireEvent.change(sel, {target: {value: 'n2'}});
    await waitFor(() => expect(screen.getByTestId('uw-creative-canvas').querySelector('svg')).not.toBe(svgBefore)); // really remounted
    expect(tf(screen.getByTestId('uw-creative-canvas'))).toBe(def); // B does not inherit A's pan
    const svgB = screen.getByTestId('uw-creative-canvas').querySelector('svg');
    fireEvent.change(sel, {target: {value: 'n1'}});
    await waitFor(() => expect(screen.getByTestId('uw-creative-canvas').querySelector('svg')).not.toBe(svgB));
    expect(tf(screen.getByTestId('uw-creative-canvas'))).toBe(pannedA); // A's view came back from the adapter
    expect(Object.keys(localStorage).filter(k => k.includes('viewprefs'))).toEqual([]);
  });
});
