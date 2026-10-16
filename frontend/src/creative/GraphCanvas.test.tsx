// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { useEffect, useState } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { GraphCanvas } from './GraphCanvas';
import type { GraphCanvasProps, GraphCanvasNodeDefinition } from './GraphCanvas';
import type { StudioGraphDefinition } from './studioGraphTypes';

const nodeDefinitions: GraphCanvasNodeDefinition[] = [
  { id: 'text_input', label: '文本输入', inputs: [], outputs: [{ id: 'text', type: 'TEXT' }] },
  { id: 'draft_prepare', label: '草稿整理', inputs: [{ id: 'text', type: 'TEXT', required: true }, { id: 'direction', type: 'DIRECTOR_NOTES' }], outputs: [{ id: 'draft', type: 'DRAFT' }] },
];
const initial = (): StudioGraphDefinition => ({ schema_version: 1, title: '我的节点图', nodes: [
  { id: 'source', definition_id: 'text_input', definition_version: 1, enabled: true, position: { x: 24, y: 24 }, parameters: { text: '文本' } },
  { id: 'prepare', definition_id: 'draft_prepare', definition_version: 1, enabled: true, position: { x: 480, y: 144 }, parameters: {} },
], edges: [{ id: 'edge', source_node_id: 'source', source_port: 'text', target_node_id: 'prepare', target_port: 'text' }], viewport: { x: 0, y: 0, zoom: 1 } });

class TestPointerEvent extends MouseEvent {
  readonly pointerId: number;
  constructor(type: string, options: PointerEventInit = {}) { super(type, options); this.pointerId = options.pointerId ?? 1; }
}

function setup(options: Partial<GraphCanvasProps> = {}) {
  const changes = vi.fn(), selections = vi.fn();
  function Harness(props: Partial<GraphCanvasProps>) {
    const [definition, setDefinition] = useState(props.definition || initial());
    const [selected, setSelected] = useState<readonly string[]>(props.selectedNodeIds || []);
    useEffect(() => { if (props.definition) setDefinition(props.definition); }, [props.definition]);
    useEffect(() => { if (props.selectedNodeIds) setSelected(props.selectedNodeIds); }, [props.selectedNodeIds]);
    return <GraphCanvas {...props} definition={definition} nodeDefinitions={nodeDefinitions} selectedNodeIds={selected}
      onDefinitionChange={(next, record) => { changes(next, record); setDefinition(next); }}
      onSelectionChange={ids => { selections(ids); setSelected(ids); }} />;
  }
  const result = render(<Harness {...options} />);
  const rerender = (next: Partial<GraphCanvasProps>) => result.rerender(<Harness {...options} {...next} />);
  return { ...result, rerender, changes, selections };
}
const viewport = () => screen.getByRole('group', { name: '节点图交互区域' });
const source = () => screen.getByRole('button', { name: '选择节点 文本输入 · source' });
const prepare = () => screen.getByRole('button', { name: '选择节点 草稿整理 · prepare' });
const down = (target: Element, x: number, y: number, extra: PointerEventInit = {}) => fireEvent.pointerDown(target, { pointerId: 1, button: 0, clientX: x, clientY: y, ...extra });
const move = (x: number, y: number, extra: PointerEventInit = {}) => fireEvent.pointerMove(viewport(), { pointerId: 1, clientX: x, clientY: y, ...extra });
const up = (x = 0, y = 0, extra: PointerEventInit = {}) => fireEvent.pointerUp(viewport(), { pointerId: 1, clientX: x, clientY: y, ...extra });
const position = (id: string) => (document.querySelector(`[data-graph-node-id="${id}"]`) as HTMLElement).style;
const edgePath = () => document.querySelector('[data-graph-edge-id="edge"]')!.getAttribute('d');

beforeEach(() => { vi.stubGlobal('PointerEvent', TestPointerEvent); });
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

describe('controlled typed graph canvas', () => {
  it('uses accessible node buttons, explicit typed port labels and edge descriptions', () => {
    const onPortSelect = vi.fn(); setup({ onPortSelect });
    expect(source().getAttribute('aria-pressed')).toBe('false');
    fireEvent.click(source()); expect(source().getAttribute('aria-pressed')).toBe('true');
    const port = screen.getByRole('button', { name: '草稿整理 prepare 输入端口 text · TEXT · 必需' });
    fireEvent.click(port); expect(onPortSelect).toHaveBeenCalledWith({ nodeId: 'prepare', portId: 'text', direction: 'input' });
    expect(screen.getByLabelText('节点图连接').textContent).toContain('source 输出 text 连接至 prepare 输入 text');
    expect(screen.getByText('DIRECTOR_NOTES')).toBeTruthy(); expect(edgePath()).toMatch(/^M 344 112 C /);
  });

  it('previews inverse-zoom movement and live edges then commits once per drag', () => {
    const definition = initial(); definition.viewport.zoom = 2;
    const { changes } = setup({ definition });
    const originalPath = edgePath();
    down(source(), 80, 80); move(120, 100); move(160, 120);
    expect(position('source').left).toBe('64px'); expect(position('source').top).toBe('44px');
    expect(edgePath()).not.toBe(originalPath); expect(changes).not.toHaveBeenCalled();
    up(160, 120);
    expect(changes).toHaveBeenCalledTimes(1);
    expect(changes.mock.calls[0][0].nodes[0].position).toEqual({ x: 64, y: 44 });
    expect(changes.mock.calls[0][1]).toBe(true);
    expect(definition.nodes[0].position).toEqual({ x: 24, y: 24 });
  });

  it('moves all selected nodes together and preserves their relative layout', () => {
    const { changes } = setup(); fireEvent.click(source()); fireEvent.click(prepare(), { shiftKey: true });
    down(source(), 50, 50); move(66, 74); up(66, 74);
    const nodes = changes.mock.calls[0][0].nodes;
    expect(nodes[0].position).toEqual({ x: 40, y: 48 }); expect(nodes[1].position).toEqual({ x: 496, y: 168 });
  });

  it('pans in screen coordinates regardless of zoom', () => {
    const definition = initial(); definition.viewport = { x: 20, y: -10, zoom: 2 };
    const { changes } = setup({ definition });
    down(viewport(), 200, 150, { altKey: true }); move(260, 190);
    expect(changes).not.toHaveBeenCalled(); expect(document.querySelector('.graph-canvas__world')!.getAttribute('style')).toContain('translate(80px, 30px) scale(2)');
    up(260, 190); expect(changes.mock.calls[0][0].viewport).toEqual({ x: 80, y: 30, zoom: 2 });
  });

  it('supports the visible hand tool and middle-button pan', () => {
    const { changes } = setup(); fireEvent.click(screen.getByRole('button', { name: '平移画布' }));
    down(source(), 10, 10); move(42, 26); up(42, 26);
    expect(changes.mock.calls[0][0].viewport).toEqual({ x: 32, y: 16, zoom: 1 });
    fireEvent.click(screen.getByRole('button', { name: '选择节点' }));
    down(viewport(), 20, 20, { button: 1 }); move(28, 28); up(28, 28);
    expect(changes.mock.calls[1][0].viewport).toEqual({ x: 40, y: 24, zoom: 1 });
  });

  it('marquee-selects in scaled and panned space including reverse drags', () => {
    const definition = initial(); definition.viewport = { x: 100, y: 80, zoom: 0.5 };
    const { changes } = setup({ definition });
    down(viewport(), 290, 155); move(105, 85); up(105, 85);
    expect(source().getAttribute('aria-pressed')).toBe('true'); expect(prepare().getAttribute('aria-pressed')).toBe('false');
    expect(changes).not.toHaveBeenCalled();
    down(viewport(), 335, 150, { shiftKey: true }); move(510, 240); up(510, 240);
    expect(prepare().getAttribute('aria-pressed')).toBe('true'); expect(source().getAttribute('aria-pressed')).toBe('true');
  });

  it.each(['pointerCancel', 'lostPointerCapture'] as const)('discards an interrupted gesture after %s', eventName => {
    const { changes } = setup(); down(source(), 50, 50); move(90, 90);
    expect(position('source').left).toBe('64px');
    fireEvent[eventName](viewport(), { pointerId: 1 }); up(90, 90);
    expect(position('source').left).toBe('24px'); expect(changes).not.toHaveBeenCalled();
    down(source(), 50, 50); move(58, 58); up(58, 58); expect(changes).toHaveBeenCalledTimes(1);
  });

  it('ignores other pointers and never commits a click-only gesture', () => {
    const { changes } = setup(); down(source(), 50, 50); move(90, 90, { pointerId: 2 }); up(90, 90, { pointerId: 2 });
    expect(position('source').left).toBe('24px'); up(50, 50); expect(changes).not.toHaveBeenCalled();
  });

  it('cancels on Escape or window blur without leaving stale drag state', () => {
    const { changes } = setup(); down(source(), 50, 50); move(90, 90);
    fireEvent.keyDown(viewport(), { key: 'Escape' }); up(90, 90); expect(position('source').left).toBe('24px');
    down(source(), 50, 50); move(90, 90); fireEvent.blur(window); up(90, 90); expect(changes).not.toHaveBeenCalled();
  });

  it.each([{ busy: true }, { readonly: true }, { interactionKey: 'new-owner' }])('fences late pointer-up after an authority or activity change: %j', next => {
    const { changes, rerender } = setup({ interactionKey: 'owner' }); down(source(), 50, 50); move(90, 90);
    rerender(next); up(90, 90); expect(position('source').left).toBe('24px'); expect(changes).not.toHaveBeenCalled();
  });

  it('discards a gesture when a different controlled definition arrives', () => {
    const { changes, rerender } = setup(); down(source(), 50, 50); move(90, 90);
    const updated = initial(); updated.nodes[0].position.x = 120;
    rerender({ definition: updated }); up(90, 90); expect(position('source').left).toBe('120px'); expect(changes).not.toHaveBeenCalled();
  });

  it('selects from keyboard activation and applies zoom-scaled arrow movement', () => {
    const definition = initial(); definition.viewport.zoom = 2;
    const { changes } = setup({ definition }); fireEvent.click(source(), { detail: 0 });
    fireEvent.keyDown(source(), { key: 'ArrowRight', shiftKey: true });
    expect(changes.mock.calls[0][0].nodes[0].position).toEqual({ x: 40, y: 24 });
    fireEvent.keyDown(viewport(), { key: 'a', ctrlKey: true }); expect(prepare().getAttribute('aria-pressed')).toBe('true');
  });

  it('removes selected nodes and incident edges in one controlled update', () => {
    const { changes } = setup(); fireEvent.click(source()); fireEvent.keyDown(viewport(), { key: 'Delete' });
    expect(changes).toHaveBeenCalledTimes(1); expect(changes.mock.calls[0][0].nodes.map((node: { id: string }) => node.id)).toEqual(['prepare']);
    expect(changes.mock.calls[0][0].edges).toEqual([]); expect(document.querySelector('[data-graph-edge-id="edge"]')).toBeNull();
  });

  it('preserves protected saved references when deleting a mixed selection', () => {
    const { changes } = setup({ protectedNodeIds: ['source'] }); fireEvent.click(source()); fireEvent.click(prepare(), { shiftKey: true });
    fireEvent.keyDown(viewport(), { key: 'Delete' });
    expect(changes.mock.calls[0][0].nodes.map((node: { id: string }) => node.id)).toEqual(['source']);
    expect(source().getAttribute('aria-pressed')).toBe('true');
    expect((screen.getByRole('button', { name: '删除所选图节点' }) as HTMLButtonElement).disabled).toBe(true);
  });

  it.each(['input', 'textarea', 'select', 'contenteditable'])('ignores Delete, Backspace and arrow shortcuts inside %s', kind => {
    const { changes } = setup(); fireEvent.click(source());
    const editor = document.createElement(kind === 'contenteditable' ? 'div' : kind);
    if (kind === 'contenteditable') editor.setAttribute('contenteditable', 'true');
    const target = kind === 'contenteditable' ? editor.appendChild(document.createElement('span')) : editor;
    viewport().appendChild(editor);
    for (const key of ['Delete', 'Backspace', 'ArrowRight']) fireEvent.keyDown(target, { key });
    expect(changes).not.toHaveBeenCalled(); expect(source()).toBeTruthy();
  });

  it.each([{ readonly: true }, { busy: true }])('blocks modifications and port changes while %j', mode => {
    const onPortSelect = vi.fn(), { changes } = setup({ ...mode, selectedNodeIds: ['source'], onPortSelect });
    fireEvent.keyDown(viewport(), { key: 'Delete' }); fireEvent.keyDown(viewport(), { key: 'ArrowRight' });
    down(source(), 50, 50); move(90, 90); up(90, 90);
    fireEvent.click(screen.getByRole('button', { name: '放大节点图' }));
    fireEvent.wheel(viewport(), { ctrlKey: true, deltaY: -100 });
    fireEvent.click(screen.getByRole('button', { name: '草稿整理 prepare 输入端口 text · TEXT · 必需' }));
    expect(changes).not.toHaveBeenCalled(); expect(onPortSelect).not.toHaveBeenCalled();
  });

  it('zooms at the wheel anchor and records a burst only once', () => {
    const { changes } = setup(); vi.spyOn(Date, 'now').mockReturnValue(1000);
    fireEvent.wheel(viewport(), { ctrlKey: true, deltaY: -100, clientX: 200, clientY: 100 });
    const next = changes.mock.calls[0][0].viewport;
    expect((200 - next.x) / next.zoom).toBeCloseTo(200); expect((100 - next.y) / next.zoom).toBeCloseTo(100);
    fireEvent.wheel(viewport(), { ctrlKey: true, deltaY: -100, clientX: 200, clientY: 100 });
    expect(changes.mock.calls.map(call => call[1])).toEqual([true, false]);
    vi.mocked(Date.now).mockReturnValue(1200);
    fireEvent.wheel(viewport(), { ctrlKey: true, deltaY: -100 }); expect(changes.mock.calls[2][1]).toBe(true);
  });

  it('leaves ordinary scrolling alone and uses the shared zoom controls', () => {
    const { changes } = setup(); fireEvent.wheel(viewport(), { deltaY: 100 }); expect(changes).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: '放大节点图' })); expect(screen.getByLabelText('节点图缩放').textContent).toBe('120%');
    fireEvent.click(screen.getByRole('button', { name: '缩小节点图' })); expect(screen.getByLabelText('节点图缩放').textContent).toBe('100%');
  });
});
