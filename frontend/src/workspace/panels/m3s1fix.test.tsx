// @vitest-environment jsdom
// [HERMIA-FE-20261024 M3-s1fix] last sent node revealed (pan only, zoom kept) at the 1366 panel size; viewport memory
// keyed per project; inspector title / dirty notices name the node; re-click of the selected creative node switches back;
// the blocked-pick notice is visible from the execution tab.
import {cleanup, fireEvent, render, screen, waitFor, within} from '@testing-library/react';
import {afterEach, beforeEach, describe, expect, it, vi} from 'vitest';
import {QueryClient, QueryClientProvider} from '@tanstack/react-query';
import {UnifiedWorkspacePreview} from '../UnifiedWorkspacePreview';
import {ExecutionCanvasPanel} from './studioPreviewPanels';
import {canvasStorageKey, type CvNode} from '../../rebuild/canvas/RebuildCanvas';
import {linkToExecution} from '../../rebuild/canvas/DualCanvas';

if (typeof window !== 'undefined' && !('PointerEvent' in window)) {
  (window as unknown as {PointerEvent: unknown}).PointerEvent = class extends MouseEvent {};
}
const PW = 750, PH = 449; // execution svg at 1366 (m2s1fix-browser.json)
const W = 186, H = 60;
const rect = (w: number, h: number) => ({left: 0, top: 0, width: w, height: h, right: w, bottom: h, x: 0, y: 0, toJSON: () => ({})}) as DOMRect;
const NOVELS = [{id: 'n1', title: '演示：雾港', genre: '', chapter_count: 0, word_count: 0, status: 'Writing'},
  {id: 'n2', title: '演示：灯塔', genre: '', chapter_count: 0, word_count: 0, status: 'Writing'}];
const json = (v: unknown, status = 200) => new Response(JSON.stringify(v), {status, headers: {'Content-Type': 'application/json'}});
const img: CvNode = {id: 'c1', t: 'image_generate', x: 0, y: 0, title: '雾港封面'};
const vid: CvNode = {id: 'v1', t: 'storyboard_shot', x: 0, y: 0, title: '开场镜头'};
beforeEach(() => {
  localStorage.clear();
  vi.spyOn(Element.prototype, 'getBoundingClientRect').mockImplementation(function (this: Element) { return this.tagName.toLowerCase() === 'svg' ? rect(PW, PH) : rect(0, 0); });
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    if (url === '/api/novels') return json(NOVELS);
    if (/^\/api\/novels\/n\d\/chapters$/.test(url)) return json([]);
    return json({detail: 'nf'}, 404);
  }));
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });
const execTf = () => within(screen.getByTestId('uw-execution-canvas')).getByRole('application').querySelector('g[transform]')!.getAttribute('transform')!;
const parse = (tf: string) => { const [, x, y, k] = /translate\(([-\d.]+),([-\d.]+)\) scale\(([-\d.]+)\)/.exec(tf)!.map(Number); return {x, y, k}; };
const lastBox = (root: Element) => {
  const {x: vx, y: vy, k} = parse(root.querySelector('svg g[transform]')!.getAttribute('transform')!);
  const els = [...root.querySelectorAll('[data-node-id]')]; const [, x, y] = /translate\(([-\d.]+),([-\d.]+)\)/.exec(els.at(-1)!.getAttribute('transform')!)!.map(Number);
  return {l: vx + x * k, t: vy + y * k, r: vx + (x + W) * k, b: vy + (y + H) * k, k};
};
const inView = (b: ReturnType<typeof lastBox>) => b.l >= 0 && b.t >= 0 && b.r <= PW && b.b <= PH;

describe('reveal the last sent node (1366 panel 750×449)', () => {
  it('after 12 sends the last node is outside the default view; revealLast pans it in, zoom kept', () => {
    for (let i = 0; i < 12; i++) linkToExecution('n1', {...img, id: `a${i}`});
    const a = render(<ExecutionCanvasPanel novelId="n1" revision={1} />);
    expect(inView(lastBox(a.container))).toBe(false); // premise: grid grows past the panel
    a.unmount();
    const b = render(<ExecutionCanvasPanel novelId="n1" revision={2} revealLast viewport={{x: 40, y: 40, k: 1}} />);
    const box = lastBox(b.container);
    expect(inView(box)).toBe(true); expect(box.k).toBe(1);
  });
  it('host: send with 11 nodes already there → execution canvas opens with the new (12th) node in view', async () => {
    localStorage.setItem(canvasStorageKey('image', 'n1'), JSON.stringify({nodes: [img], edges: []}));
    for (let i = 0; i < 11; i++) linkToExecution('n1', {...img, id: `a${i}`});
    render(<QueryClientProvider client={new QueryClient({defaultOptions: {queries: {retry: false}}})}><UnifiedWorkspacePreview /></QueryClientProvider>);
    await screen.findByTestId('uw-creative-canvas');
    fireEvent.pointerDown(document.querySelector('[data-node-id=c1] .box')!, {button: 0, clientX: 5, clientY: 5}); fireEvent.pointerUp(document.querySelector('svg.rcv-svg')!);
    const send = screen.getByRole('button', {name: '送到执行画布'}) as HTMLButtonElement;
    await waitFor(() => expect(send.disabled).toBe(false)); fireEvent.click(send);
    await screen.findByText(/已把「雾港封面」送到执行画布/, {}, {timeout: 2000});
    fireEvent.click(screen.getByTestId('uw-open-execution'));
    const ex = await screen.findByTestId('uw-execution-canvas');
    await waitFor(() => expect(ex.querySelectorAll('[data-node-id]').length).toBe(12));
    expect(inView(lastBox(ex))).toBe(true);
  });
});

describe('host M3-s1fix', () => {
  beforeEach(() => {
    localStorage.setItem(canvasStorageKey('image', 'n1'), JSON.stringify({nodes: [img], edges: []}));
    localStorage.setItem(canvasStorageKey('video', 'n1'), JSON.stringify({nodes: [vid], edges: []}));
  });
  const mount = () => render(<QueryClientProvider client={new QueryClient({defaultOptions: {queries: {retry: false}}})}><UnifiedWorkspacePreview /></QueryClientProvider>);
  const pick = (id: string) => { fireEvent.pointerDown(document.querySelector(`[data-node-id=${id}] .box`)!, {button: 0, clientX: 5, clientY: 5}); fireEvent.pointerUp(document.querySelector(`[data-node-id=${id}]`)!.closest('svg')!); };
  const showExec = async () => { fireEvent.click(screen.getByTestId('uw-open-execution')); await screen.findByTestId('uw-execution-canvas'); };
  const showCreative = async () => { fireEvent.click(screen.getByTestId('uw-main-tabs').querySelector('[data-panel-tab=creative]')!); await screen.findByTestId('uw-creative-canvas'); };
  const insp = () => screen.getByTestId('uw-node-inspector');

  it('MUST-FIX: pan exec in A, switch to B → default viewport; back to A → A restored', async () => {
    mount(); await screen.findByTestId('uw-creative-canvas'); await showExec();
    const svg = within(screen.getByTestId('uw-execution-canvas')).getByRole('application');
    fireEvent.pointerDown(svg, {button: 0, clientX: 600, clientY: 400}); fireEvent.pointerMove(svg, {clientX: 200, clientY: 400}); fireEvent.pointerUp(svg);
    const panned = execTf(); expect(panned).toBe('translate(-360,40) scale(1)');
    fireEvent.change(screen.getByLabelText('选择作品'), {target: {value: 'n2'}});
    await waitFor(() => expect(execTf()).toBe('translate(40,40) scale(1)'));
    fireEvent.change(screen.getByLabelText('选择作品'), {target: {value: 'n1'}});
    await waitFor(() => expect(execTf()).toBe(panned));
  });
  it('inspector title names the node; dirty block notices name the node and show on the execution tab', async () => {
    mount(); await screen.findByTestId('uw-creative-canvas');
    pick('c1'); await waitFor(() => expect(insp().dataset.nodeId).toBe('c1'));
    expect(screen.getByRole('region', {name: '节点「雾港封面」属性'})).toBeTruthy();
    expect(screen.queryByRole('region', {name: '章节属性'})).toBeNull();
    fireEvent.change(screen.getByLabelText('节点标题'), {target: {value: '草稿'}});
    fireEvent.change(screen.getByLabelText('选择作品'), {target: {value: 'n2'}});
    expect(screen.getByTestId('uw-outline-blocked').textContent).toContain('节点「雾港封面」');
    expect(screen.getByTestId('uw-outline-blocked').textContent).not.toContain('章节属性');
    await showExec(); pick('v1');
    expect(insp().dataset.nodeId).toBe('c1');
    expect(screen.getByTestId('uw-inspector-blocked').textContent).toContain('节点「雾港封面」有未保存的修改');
    fireEvent.click(within(insp()).getByRole('button', {name: '放弃'}));
    await waitFor(() => expect(insp().dataset.nodeId).toBe('v1'));
    expect(screen.queryByTestId('uw-inspector-blocked')).toBeNull();
    expect(screen.getByRole('region', {name: '节点「开场镜头」属性'})).toBeTruthy();
  });
  it('re-clicking the already-selected creative node while the exec node is shown switches back', async () => {
    mount(); await screen.findByTestId('uw-creative-canvas');
    pick('c1'); await waitFor(() => expect(insp().dataset.nodeId).toBe('c1'));
    await showExec(); pick('v1'); await waitFor(() => expect(insp().dataset.nodeId).toBe('v1'));
    await showCreative();
    expect(document.querySelector('[data-node-id=c1]')!.getAttribute('data-sel')).toBe('true');
    expect(insp().dataset.nodeId).toBe('v1');
    pick('c1'); await waitFor(() => expect(insp().dataset.nodeId).toBe('c1'));
  });
});
