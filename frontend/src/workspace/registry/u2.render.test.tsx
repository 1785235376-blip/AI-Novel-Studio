// @vitest-environment jsdom
// [HERMIA-FE-20261025 U2] render tests (jsdom = mock evidence) + bounded-loading measurements
import {afterEach, describe, expect, it, vi} from 'vitest';
import {cleanup, fireEvent, render, screen} from '@testing-library/react';
import {CanvasSelectionLayer} from './CanvasSelectionLayer';
import {ContextNavBar} from './ContextNavBar';
import {INITIAL_NAV, openTask} from './contextNav';
import {multiEditSurface, selectBox, EMPTY_SELECTION, type CanvasSelection} from './selection';
import {capabilityStates} from './workspaceRegistry';
import {windowRange} from './boundedList';

afterEach(cleanup);
// jsdom has no PointerEvent; MouseEvent carries button/ctrlKey/shiftKey/clientX the same way.
if (typeof window !== 'undefined' && !('PointerEvent' in window)) (window as unknown as {PointerEvent: typeof MouseEvent}).PointerEvent = class extends MouseEvent {};
const RAW = /node-secret-\d|task-raw-\d/;

function Nodes() {
  return <svg>{[0, 1, 2].map(i => <g key={i} data-node-id={`node-secret-${i}`} data-testid={`n${i}`}><rect /></g>)}</svg>;
}
function rects() {
  vi.spyOn(Element.prototype, 'getBoundingClientRect').mockImplementation(function (this: Element) {
    const id = this.getAttribute('data-node-id'); const i = id ? Number(id.slice(-1)) : -1;
    return (i >= 0 ? {left: i * 200, top: 0, width: 180, height: 60} : {left: 0, top: 0, width: 1000, height: 600}) as DOMRect;
  });
}

describe('CanvasSelectionLayer', () => {
  it('Ctrl+click toggles, plain click passes through, Shift+drag box-selects, Esc clears', () => {
    rects(); let sel: CanvasSelection = EMPTY_SELECTION; const onChange = vi.fn((s: CanvasSelection) => { sel = s; });
    const plain = vi.fn();
    const r = render(<CanvasSelectionLayer canvas="image" selection={sel} onChange={onChange}><div onPointerDown={plain}><Nodes /></div></CanvasSelectionLayer>);
    fireEvent.pointerDown(screen.getByTestId('n0'), {button: 0}); expect(plain).toHaveBeenCalledTimes(1); expect(onChange).not.toHaveBeenCalled();
    fireEvent.pointerDown(screen.getByTestId('n1'), {button: 0, ctrlKey: true}); expect(sel).toEqual({canvas: 'image', ids: ['node-secret-1']}); expect(plain).toHaveBeenCalledTimes(1);
    const layer = screen.getByTestId('uw-sel-layer-image');
    fireEvent.pointerDown(layer, {button: 0, shiftKey: true, clientX: 10, clientY: 10});
    fireEvent.pointerMove(layer, {clientX: 390, clientY: 50}); expect(screen.getByTestId('uw-sel-box')).toBeTruthy();
    fireEvent.pointerUp(layer, {clientX: 390, clientY: 50});
    expect(sel).toEqual({canvas: 'image', ids: ['node-secret-0', 'node-secret-1']});
    r.rerender(<CanvasSelectionLayer canvas="image" selection={sel} onChange={onChange}><Nodes /></CanvasSelectionLayer>);
    expect(screen.getAllByTestId('uw-sel-outline')).toHaveLength(2);
    expect(layer.textContent).not.toMatch(RAW);
    (screen.getByTestId('n0') as unknown as HTMLElement).focus?.();
    layer.setAttribute('tabindex', '-1'); layer.focus();
    fireEvent.keyDown(document, {key: 'Escape'}); expect(sel).toEqual({canvas: 'image', ids: []});
    vi.restoreAllMocks();
  });
});

describe('ContextNavBar', () => {
  it('shows step, actionable notice, safe multi-edit, details; never raw ids in visible text', () => {
    const nav = openTask(INITIAL_NAV, {source: 'task-center', id: 'task-raw-1', owner: 'image', status: 'failed', revision: 1, title: '封面', link: {canvas: 'execution', documentId: null, nodeId: 'node-secret-9'}, stale: false},
      {nodeExists: () => false, capture: () => ({panelId: 'creative', canvas: 'creative', nodeIds: ['node-secret-1'], focusTestId: 'x', viewport: null})}).state;
    const sel = {canvas: 'image' as const, ids: ['node-secret-1', 'node-secret-2']};
    const multi = multiEditSurface('image', [{id: 'node-secret-1', t: 'image_prompt', x: 0, y: 0, title: 'A'}, {id: 'node-secret-2', t: 'image_prompt', x: 0, y: 0, title: 'B'}]);
    const onReturn = vi.fn(), onCompare = vi.fn(), onClear = vi.fn();
    render(<ContextNavBar nav={nav} selection={sel} multi={multi} capabilities={capabilityStates({hasProject: true})} canReturn onReturn={onReturn} onCompare={onCompare} onClearSelection={onClear} />);
    const bar = screen.getByTestId('uw-ctxbar');
    expect(bar.textContent).not.toMatch(RAW);
    expect(screen.getByTestId('uw-ctx-next').textContent).toContain('下一步');
    expect(screen.getByTestId('uw-multi').textContent).not.toContain('批量生成：可');
    fireEvent.click(bar.querySelector('[data-action-id="nav.returnToOrigin"]')!); expect(onReturn).toHaveBeenCalled();
    fireEvent.click(bar.querySelector('[data-action-id="nav.compare"]')!); expect(onCompare).toHaveBeenCalled();
    expect(screen.getByTestId('uw-ctx-details')).toBeTruthy();
  });
});

describe('measurements (jsdom, mock evidence)', () => {
  it('5000-row windowed render keeps DOM bounded; selectBox over 10k nodes', () => {
    const rows = Array.from({length: 5000}, (_, i) => `任务 ${i}`);
    const t0 = performance.now(); const {start, end} = windowRange(rows.length, 28 * 2500, 28, 560);
    const {container} = render(<ul>{rows.slice(start, end).map(r => <li key={r}>{r}</li>)}</ul>);
    const t1 = performance.now(); const li = container.querySelectorAll('li').length;
    const nodes = Array.from({length: 10000}, (_, i) => ({id: `n${i}`, rect: {x: (i % 100) * 200, y: Math.floor(i / 100) * 80, w: 180, h: 60}}));
    const t2 = performance.now(); const s = selectBox(EMPTY_SELECTION, 'image', {x: 0, y: 0, w: 1000, h: 400}, nodes); const t3 = performance.now();
    console.log(`[U2-MEASURE jsdom] rows=5000 domLi=${li} renderMs=${(t1 - t0).toFixed(2)} | nodes=10000 boxHits=${s.ids.length} selectBoxMs=${(t3 - t2).toFixed(2)}`);
    expect(li).toBeLessThanOrEqual(40); expect(s.ids.length).toBe(25);
  });
});
