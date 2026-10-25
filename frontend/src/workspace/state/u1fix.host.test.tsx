// @vitest-environment jsdom
// [HERMIA-FE-20261025 U1fix] MUST-FIX 1/2/3 on the real ?uw=1 host (StrictMode, existing bootstrap). mock fetch, jsdom.
import {StrictMode} from 'react';
import {act, cleanup, fireEvent, render, screen, waitFor, within} from '@testing-library/react';
import {afterEach, beforeEach, describe, expect, it, vi} from 'vitest';
import {QueryClient, QueryClientProvider} from '@tanstack/react-query';
import {UnifiedWorkspacePreviewHost} from './identityBootstrap';
import {useStudio} from '../../store';
import {viewPrefsKey} from './viewPreferences';
import {canvasStorageKey, type CvNode} from '../../rebuild/canvas/RebuildCanvas';

if (typeof window !== 'undefined' && !('PointerEvent' in window)) (window as unknown as {PointerEvent: unknown}).PointerEvent = class extends MouseEvent {};
let size = {w: 0, h: 0};
const rect = (w: number, h: number) => ({left: 0, top: 0, width: w, height: h, right: w, bottom: h, x: 0, y: 0, toJSON: () => ({})}) as DOMRect;
class FakeRO { observe() {} unobserve() {} disconnect() {} }
const img: CvNode = {id: 'c1', t: 'image_generate', x: 0, y: 0, title: '雾港封面'};
const NOVELS = [{id: 'n1', title: '演示：雾港', genre: '', chapter_count: 0, word_count: 0, status: 'Writing'}];
const COLLAB = {workspaceId: 'ws1', projectId: 'n1', storylineId: 's1', branchId: 'b1'};
const A = {userId: 'actor-1', projectId: 'n1', projectInstanceId: 'ws1/s1/b1'};
const json = (v: unknown, status = 200) => new Response(JSON.stringify(v), {status, headers: {'Content-Type': 'application/json'}});
const BOOT = {actor: {actor_id: 'actor-1', session_id: 's', client_id: 'c'}, scope: {workspace_id: 'ws1', project_id: 'n1', storyline_id: 's1', branch_id: 'b1'}, capabilities: {}};
const fetchMock = () => vi.fn(async (url: string, _init?: RequestInit) => url === '/api/novels' ? json(NOVELS) : /\/bootstrap$/.test(url) ? json(BOOT) : /chapters$/.test(url) ? json([]) : json({detail: 'nf'}, 404));
beforeEach(() => {
  localStorage.clear(); size = {w: 750, h: 449};
  vi.stubGlobal('ResizeObserver', FakeRO);
  vi.spyOn(Element.prototype, 'getBoundingClientRect').mockImplementation(function (this: Element) { return this.tagName.toLowerCase() === 'svg' ? rect(size.w, size.h) : rect(0, 0); });
  vi.stubGlobal('fetch', fetchMock());
  localStorage.setItem(canvasStorageKey('image', 'n1'), JSON.stringify({nodes: [img], edges: []}));
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); useStudio.setState({sessionToken: '', scope: undefined, actor: undefined}); });
const mount = () => render(<StrictMode><QueryClientProvider client={new QueryClient({defaultOptions: {queries: {retry: false}}})}><UnifiedWorkspacePreviewHost /></QueryClientProvider></StrictMode>);
const tf = () => screen.getByTestId('uw-creative-canvas').querySelector('svg g[transform]')!.getAttribute('transform')!;
const pan = (dx: number) => { const svg = within(screen.getByTestId('uw-creative-canvas')).getByRole('application');
  fireEvent.pointerDown(svg, {button: 0, clientX: 600, clientY: 300}); fireEvent.pointerMove(svg, {clientX: 600 + dx, clientY: 300}); fireEvent.pointerUp(svg); };
const saveWorkset = async (name: string) => {
  fireEvent.click(screen.getByTestId('uw-open-views'));
  const dlg = await screen.findByTestId('uw-views');
  fireEvent.change(within(dlg).getByLabelText('视图名称'), {target: {value: name}});
  fireEvent.submit(within(dlg).getByLabelText('视图名称').closest('form')!);
  return dlg;
};
const nonGet = () => (fetch as unknown as {mock: {calls: [string, RequestInit?][]}}).mock.calls.filter(([, i]) => (i?.method ?? 'GET').toUpperCase() !== 'GET');

describe('U1fix host', () => {
  it('MUST-FIX 2: session mode (no token) — save keeps the workset in memory, says 仅本次会话, writes nothing, no bootstrap call', async () => {
    mount();
    await screen.findByTestId('uw-creative-canvas');
    expect(screen.getByTestId('uw-identity').dataset.identity).toBe('session');
    const dlg = await saveWorkset('写作');
    await waitFor(() => expect(within(dlg).getByTestId('uw-views-msg').textContent).toBe('已保存视图「写作」（仅本次会话有效，关闭页面后不保留）。'));
    expect(within(dlg).getByRole('list', {name: '已保存的视图'}).textContent).toContain('写作');
    expect(Object.keys(localStorage).filter(k => k.includes('viewprefs'))).toEqual([]);
    expect((fetch as unknown as {mock: {calls: [string][]}}).mock.calls.filter(([u]) => /bootstrap/.test(u))).toEqual([]);
    expect(nonGet()).toEqual([]);
  });
  it('MUST-FIX 3: existing bootstrap gives the real actor; stored viewport (-160,70) is applied after identity arrives', async () => {
    localStorage.setItem(viewPrefsKey(A), JSON.stringify({version: 1, viewports: {image: {x: -160, y: 70, zoom: 1}}, worksets: []}));
    // Bootstrap answers only AFTER the canvas has mounted with the session (default) viewport — the real-world order.
    let release!: () => void; const gate = new Promise<void>(r => { release = r; });
    const base = fetchMock();
    vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => { if (/\/bootstrap$/.test(url)) await gate; return base(url); }));
    useStudio.setState({sessionToken: 'tok', scope: COLLAB, actor: undefined});
    mount();
    await screen.findByTestId('uw-creative-canvas');
    expect(screen.getByTestId('uw-identity').dataset.identity).toBe('session');
    const before = tf();
    expect(before).not.toBe('translate(-160,70) scale(1)');
    await act(async () => { release(); });
    await waitFor(() => expect(screen.getByTestId('uw-identity').dataset.identity).toBe('real'));
    await waitFor(() => expect(tf()).toBe('translate(-160,70) scale(1)'));
    expect(useStudio.getState().actor?.id).toBe('actor-1'); // from the server bootstrap response, not invented
    expect(nonGet()).toEqual([]);
  });
  it('MUST-FIX 1: real identity — save workset → pan → cold reopen keeps the workset and the pan', async () => {
    useStudio.setState({sessionToken: 'tok', scope: COLLAB, actor: undefined});
    const v = mount();
    await waitFor(() => expect(screen.getByTestId('uw-identity').dataset.identity).toBe('real'));
    await screen.findByTestId('uw-creative-canvas');
    const dlg = await saveWorkset('工作W1');
    await waitFor(() => expect(within(dlg).getByTestId('uw-views-msg').textContent).toBe('已保存视图「工作W1」。'));
    fireEvent.click(within(dlg).getByText('关闭'));
    await act(async () => { pan(-300); });
    const panned = tf();
    const doc = JSON.parse(localStorage.getItem(viewPrefsKey(A))!);
    expect(doc.worksets.map((w: {name: string}) => w.name)).toEqual(['工作W1']);
    expect(doc.viewports.image).toBeTruthy();
    v.unmount(); useStudio.setState({actor: undefined});
    mount(); // cold reopen
    await waitFor(() => expect(screen.getByTestId('uw-identity').dataset.identity).toBe('real'));
    await waitFor(() => expect(tf()).toBe(panned));
    fireEvent.click(screen.getByTestId('uw-open-views'));
    const dlg2 = await screen.findByTestId('uw-views');
    expect(within(dlg2).getByRole('list', {name: '已保存的视图'}).textContent).toContain('工作W1');
    expect(nonGet()).toEqual([]);
  });
});
