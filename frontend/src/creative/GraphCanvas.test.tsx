// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
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
  it('creates, selects, drags, renames and removes persisted groups while retaining annotation', () => {
    const definition = { ...initial(), presentation: { comment: 'Keep' } };
    const { changes, selections } = setup({ definition, selectedNodeIds: ['source', 'prepare'] });
    fireEvent.change(screen.getByLabelText('分组名称'), { target: { value: '场景 🎬' } });
    fireEvent.click(screen.getByRole('button', { name: '用所选节点创建分组' }));
    const groups = [{ id: 'group_1', name: '场景 🎬', node_ids: ['source', 'prepare'] }];
    expect(changes).toHaveBeenLastCalledWith({ ...definition, presentation: { comment: 'Keep', groups } }, true);
    fireEvent.change(screen.getByLabelText('视觉分组'), { target: { value: 'group_1' } });
    fireEvent.click(screen.getByRole('button', { name: '选择分组成员' }));
    expect(selections).toHaveBeenLastCalledWith(['source', 'prepare']);
    down(source(), 40, 40); move(72, 56); up(72, 56);
    const moved = changes.mock.calls.at(-1)![0];
    expect(moved.nodes[0].position).toEqual({ x: 56, y: 40 });
    expect(moved.nodes[1].position).toEqual({ x: 512, y: 160 });
    expect(moved.presentation.groups).toEqual(groups);
    fireEvent.change(screen.getByLabelText('视觉分组'), { target: { value: 'group_1' } });
    fireEvent.change(screen.getByLabelText('分组名称'), { target: { value: '新名称' } });
    fireEvent.click(screen.getByRole('button', { name: '重命名分组' }));
    expect(changes.mock.calls.at(-1)![0].presentation.groups[0].name).toBe('新名称');
    fireEvent.change(screen.getByLabelText('画布说明'), { target: { value: 'Edited note' } });
    expect(changes.mock.calls.at(-1)![0].presentation.groups[0].name).toBe('新名称');
    fireEvent.click(screen.getByRole('button', { name: '移除画布说明' }));
    expect(changes.mock.calls.at(-1)![0].presentation.groups).toHaveLength(1);
    fireEvent.change(screen.getByLabelText('视觉分组'), { target: { value: 'group_1' } });
    fireEvent.click(screen.getByRole('button', { name: '移除分组（保留节点）' }));
    expect(changes.mock.calls.at(-1)![0]).toEqual({ ...definition, nodes: moved.nodes, presentation: undefined });
  });

  it('rejects overlap, resets pending names on owner changes and enforces Unicode name limits', () => {
    const definition = { ...initial(), presentation: { groups: [{ id: 'g', name: 'Old', node_ids: ['source'] }] } };
    const { changes, rerender } = setup({ definition, selectedNodeIds: ['source', 'prepare'] });
    fireEvent.change(screen.getByLabelText('分组名称'), { target: { value: 'New' } });
    expect((screen.getByRole('button', { name: '用所选节点创建分组' }) as HTMLButtonElement).disabled).toBe(true);
    rerender({ selectedNodeIds: ['prepare'] });
    fireEvent.change(screen.getByLabelText('分组名称'), { target: { value: '🎬'.repeat(81) } });
    expect(screen.getByRole('alert').textContent).toContain('80');
    fireEvent.click(screen.getByRole('button', { name: '用所选节点创建分组' })); expect(changes).not.toHaveBeenCalled();
    fireEvent.change(screen.getByLabelText('分组名称'), { target: { value: '🎬'.repeat(80) } });
    fireEvent.click(screen.getByRole('button', { name: '用所选节点创建分组' })); expect(changes).toHaveBeenCalledTimes(1);
    fireEvent.change(screen.getByLabelText('分组名称'), { target: { value: 'Pending private name' } });
    rerender({ interactionKey: 'other' }); expect((screen.getByLabelText('分组名称') as HTMLInputElement).value).toBe('');
  });

  it.each([{ readonly: true }, { busy: true }])('blocks all group actions: %j', props => {
    const { changes, selections } = setup({ ...props, selectedNodeIds: ['source'] });
    expect((screen.getByLabelText('分组名称') as HTMLInputElement).disabled).toBe(true);
    fireEvent.click(screen.getByRole('button', { name: '用所选节点创建分组' }));
    expect(changes).not.toHaveBeenCalled(); expect(selections).not.toHaveBeenCalled();
  });

  it('edits and removes plain graph annotations without changing node geometry, pins or selection', () => {
    const definition = initial(), { changes, selections, rerender } = setup({ definition, selectedNodeIds: ['source'] });
    const text = '场景说明\n<script>plain text</script>';
    fireEvent.change(screen.getByLabelText('画布说明'), { target: { value: text } });
    expect(changes).toHaveBeenLastCalledWith({ ...definition, presentation: { comment: text } }, true);
    expect((screen.getByLabelText('画布说明') as HTMLTextAreaElement).maxLength).toBe(4000);
    fireEvent.keyDown(screen.getByLabelText('画布说明'), { key: 'Delete' });
    fireEvent.keyDown(screen.getByLabelText('画布说明'), { key: 'ArrowRight' });
    expect(changes).toHaveBeenCalledTimes(1); expect(selections).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: '移除画布说明' }));
    expect(changes).toHaveBeenLastCalledWith(definition, true);
    rerender({ definition: { ...initial(), presentation: { comment: 'Other owner' } }, interactionKey: 'other' });
    expect((screen.getByLabelText('画布说明') as HTMLTextAreaElement).value).toBe('Other owner');
  });

  it('preserves 2000 supplementary characters and rejects overflow without dropping existing text', () => {
    const { changes } = setup();
    const text = '🎬'.repeat(2000);
    fireEvent.change(screen.getByLabelText('画布说明'), { target: { value: text } });
    expect(changes.mock.calls.at(-1)![0].presentation.comment).toBe(text);
    fireEvent.change(screen.getByLabelText('画布说明'), { target: { value: text + '尾' } });
    expect(changes).toHaveBeenCalledTimes(1);
    expect((screen.getByLabelText('画布说明') as HTMLTextAreaElement).value).toBe(text);
    expect(screen.getByRole('alert').textContent).toContain('原有说明已保留');
    const mixed = '字'.repeat(1999) + '🎬';
    fireEvent.change(screen.getByLabelText('画布说明'), { target: { value: mixed } });
    expect(changes.mock.calls.at(-1)![0].presentation.comment).toBe(mixed);
    fireEvent.change(screen.getByLabelText('画布说明'), { target: { value: '新增' + mixed } });
    expect(changes).toHaveBeenCalledTimes(2);
    expect((screen.getByLabelText('画布说明') as HTMLTextAreaElement).value).toBe(mixed);
  });

  it.each([{ readonly: true }, { busy: true }])('blocks annotation mutations when owner is blocked: %j', props => {
    const { changes } = setup({ ...props, definition: { ...initial(), presentation: { comment: 'Keep' } } });
    expect((screen.getByLabelText('画布说明') as HTMLTextAreaElement).disabled).toBe(true);
    fireEvent.change(screen.getByLabelText('画布说明'), { target: { value: 'No' } });
    fireEvent.click(screen.getByRole('button', { name: '移除画布说明' }));
    expect(changes).not.toHaveBeenCalled();
  });

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


describe('measured viewport rendering', () => {
  const measure = () => vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockReturnValue({ x: 0, y: 0, left: 0, top: 0, right: 800, bottom: 400, width: 800, height: 400, toJSON: () => ({}) });
  const distant = () => { const graph = initial(); graph.nodes[1].position = { x: 5000, y: 144 }; return graph; };
  it('culls cards, retains crossing edges and recovers unchanged nodes after pan', () => {
    measure(); const definition = distant(), original = JSON.stringify(definition);
    const { changes } = setup({ definition });
    expect(screen.queryByRole('button', { name: '选择节点 草稿整理 · prepare' })).toBeNull();
    expect(edgePath()).toBeTruthy();
    down(viewport(), 0, 0, { altKey: true }); move(-4800, 0); up(-4800, 0);
    expect(prepare()).toBeTruthy(); expect(screen.queryByRole('button', { name: '选择节点 文本输入 · source' })).toBeNull();
    expect(changes.mock.calls[0][0].nodes).toBe(definition.nodes); expect(JSON.stringify(definition)).toBe(original);
  });
  it('retains selected nodes and controller-owned connection anchors without changing graph data', () => {
    measure(); const { changes, rerender } = setup({ definition: distant(), selectedNodeIds: ['prepare'] });
    expect(prepare()).toBeTruthy(); rerender({ selectedNodeIds: [], connectionNodeIds: ['prepare'] }); expect(prepare()).toBeTruthy();
    rerender({ selectedNodeIds: [], connectionNodeIds: [] }); expect(screen.queryByRole('button', { name: '选择节点 草稿整理 · prepare' })).toBeNull();
    expect(changes).not.toHaveBeenCalled();
  });
  it('preserves a focused port while zoom/pan moves its card offscreen and releases it after blur', () => {
    measure(); const definition = initial(), onPortSelect = vi.fn(); const { rerender } = setup({ definition, onPortSelect });
    const port = screen.getByRole('button', { name: '草稿整理 prepare 输入端口 text · TEXT · 必需' });
    act(() => port.focus());
    rerender({ definition: { ...definition, viewport: { x: -5000, y: 0, zoom: 1 } } });
    expect(document.activeElement).toBe(port); fireEvent.click(port); expect(onPortSelect).toHaveBeenCalledTimes(1);
    act(() => viewport().focus());
    expect(screen.queryByRole('button', { name: '选择节点 草稿整理 · prepare' })).toBeNull();
  });
  it('offers keyboard-native selection of every offscreen node and centers via existing controlled viewport', () => {
    measure(); const { changes } = setup({ definition: distant() });
    const navigator = screen.getByRole('combobox', { name: '选择图节点' });
    fireEvent.change(navigator, { target: { value: 'prepare' } });
    expect(prepare().getAttribute('aria-pressed')).toBe('true');
    expect(changes.mock.calls[0][0].viewport.x).toBe(-4760);
    expect(changes.mock.calls[0][0].nodes[1].position.x).toBe(5000);
    fireEvent.keyDown(navigator, { key: 'Delete' }); expect(changes).toHaveBeenCalledTimes(1);
  });
  it('keeps readonly navigation selection nonmutating and disables the directory while busy', () => {
    measure(); const { changes, selections, rerender } = setup({ definition: distant(), readonly: true });
    fireEvent.change(screen.getByRole('combobox', { name: '选择图节点' }), { target: { value: 'prepare' } });
    expect(selections).toHaveBeenCalledWith(['prepare']); expect(changes).not.toHaveBeenCalled();
    rerender({ busy: true }); expect((screen.getByRole('combobox', { name: '选择图节点' }) as HTMLSelectElement).disabled).toBe(true);
  });
  it('selects all offscreen cards and preserves a dragged card until cancellation', () => {
    measure(); const { changes } = setup({ definition: distant() });
    fireEvent.keyDown(viewport(), { key: 'a', ctrlKey: true }); expect(prepare().getAttribute('aria-pressed')).toBe('true');
    down(source(), 30, 30); move(-5000, -5000); expect(source()).toBeTruthy(); expect(prepare()).toBeTruthy();
    fireEvent.keyDown(viewport(), { key: 'Escape' }); expect(position('source').left).toBe('24px'); expect(changes).not.toHaveBeenCalled();
  });
  it('drops focus retention when the interaction owner changes', () => {
    measure(); const definition = initial(); const { rerender } = setup({ definition, interactionKey: 'one', onPortSelect: vi.fn() });
    act(() => screen.getByRole('button', { name: '草稿整理 prepare 输入端口 text · TEXT · 必需' }).focus());
    rerender({ definition: { ...definition, viewport: { x: -5000, y: 0, zoom: 1 } }, interactionKey: 'two' });
    expect(screen.queryByRole('button', { name: '选择节点 草稿整理 · prepare' })).toBeNull();
  });
  it('responds to ResizeObserver and disconnects it on unmount', () => {
    const bounds = measure(); let notify = () => {}; const disconnect = vi.fn();
    vi.stubGlobal('ResizeObserver', class { constructor(callback: () => void) { notify = callback; } observe() {} disconnect = disconnect; });
    const { unmount } = setup({ definition: distant() }); expect(screen.queryByRole('button', { name: '选择节点 草稿整理 · prepare' })).toBeNull();
    bounds.mockReturnValue({ x: 0, y: 0, left: 0, top: 0, right: 6000, bottom: 400, width: 6000, height: 400, toJSON: () => ({}) });
    act(() => notify()); expect(prepare()).toBeTruthy(); unmount(); expect(disconnect).toHaveBeenCalledOnce();
  });
});

describe('mounted MiniMap navigation', () => {
  const map = () => screen.getByRole('button', { name: '小地图导航' }) as HTMLButtonElement;
  function measure() {
    vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockImplementation(function (this: HTMLElement) {
      return { x: 0, y: 0, left: 0, top: 0, right: 800, bottom: 400, width: this.classList.contains('graph-canvas__minimap') ? 200 : 800, height: this.classList.contains('graph-canvas__minimap') ? 120 : 400, toJSON: () => ({}) };
    });
  }
  it('uses one camera history update per click or arrow without moving selected nodes or changing zoom', () => {
    measure(); const definition = initial(); definition.viewport.zoom = 2.5;
    const { changes, selections } = setup({ definition, selectedNodeIds: ['source'] });
    map().focus(); fireEvent.keyDown(map(), { key: 'ArrowRight' });
    expect(changes).toHaveBeenCalledTimes(1);
    const next = changes.mock.calls[0][0]; expect(next.viewport).toEqual({ x: -200, y: 0, zoom: 2.5 });
    expect(next.nodes).toBe(definition.nodes); expect(next.edges).toBe(definition.edges); expect(changes.mock.calls[0][1]).toBe(true);
    expect(document.activeElement).toBe(map()); expect(selections).not.toHaveBeenCalled();
    fireEvent.click(map(), { detail: 1, clientX: 150, clientY: 80 });
    expect(changes).toHaveBeenCalledTimes(2); expect(changes.mock.calls[1][0].viewport.zoom).toBe(2.5);
    expect(document.querySelector('.graph-canvas__minimap-selected')?.getAttribute('d')).not.toBe('');
    fireEvent.keyDown(map(), { key: 'Delete' }); expect(changes).toHaveBeenCalledTimes(2);
  });
  it('hides and restores overview without history changes and blocks read-only, busy and unmeasured navigation', () => {
    const { changes, rerender } = setup(); expect(map().disabled).toBe(true);
    fireEvent.click(screen.getByRole('button', { name: '显示小地图' })); expect(screen.queryByRole('button', { name: '小地图导航' })).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: '显示小地图' }));
    measure(); fireEvent(window, new Event('resize')); expect(map().disabled).toBe(false);
    rerender({ readonly: true }); expect(map().disabled).toBe(true); fireEvent.keyDown(map(), { key: 'ArrowRight' });
    rerender({ busy: true }); expect(map().disabled).toBe(true); fireEvent.click(map());
    expect(changes).not.toHaveBeenCalled();
  });
  it('tracks resize and replacement, clamps camera and ignores composition and active gestures', () => {
    measure(); const definition = initial(); definition.viewport = { x: -100000, y: 100000, zoom: 0.35 };
    const { changes, rerender } = setup({ definition });
    fireEvent.keyDown(map(), { key: 'ArrowRight' }); expect(changes).not.toHaveBeenCalled();
    fireEvent.keyDown(map(), { key: 'ArrowLeft', isComposing: true }); expect(changes).not.toHaveBeenCalled();
    down(viewport(), 5, 5); fireEvent.click(map()); expect(changes).not.toHaveBeenCalled(); up();
    fireEvent.keyDown(map(), { key: 'ArrowLeft', shiftKey: true }); expect(changes.mock.calls[0][0].viewport.x).toBe(-99200);
    const replacement = initial(); replacement.nodes = []; replacement.edges = [];
    rerender({ definition: replacement, interactionKey: 'other' }); expect(map().disabled).toBe(true);
    expect(document.querySelector('.graph-canvas__minimap-nodes')?.getAttribute('d')).toBe('');
  });
});


describe('selected-node alignment preview', () => {
  it('previews live geometry and edges, cancels without writes, then applies once', () => {
    const { changes } = setup({ selectedNodeIds: ['source', 'prepare'] });
    const beforePath = edgePath();
    fireEvent.click(screen.getByText('预览左对齐'));
    expect(position('prepare').left).toBe('24px'); expect(edgePath()).not.toBe(beforePath);
    expect(changes).not.toHaveBeenCalled();
    fireEvent.click(screen.getByText('取消对齐预览'));
    expect(position('prepare').left).toBe('480px'); expect(edgePath()).toBe(beforePath);
    fireEvent.click(screen.getByText('预览顶对齐'));
    fireEvent.click(screen.getByText('应用所选节点对齐'));
    expect(changes).toHaveBeenCalledTimes(1); expect(changes.mock.calls[0][1]).toBe(true);
    expect(changes.mock.calls[0][0].nodes[1].position).toEqual({ x: 480, y: 24 });
    fireEvent.click(screen.getByText('预览顶对齐'));
    expect((screen.getByText('应用所选节点对齐') as HTMLButtonElement).disabled).toBe(true);
  });
  it.each(['selection', 'definition', 'owner', 'readonly', 'busy'])('invalidates a preview on %s changes without resurrecting it', change => {
    const options = { selectedNodeIds: ['source', 'prepare'], interactionKey: 'owner' };
    const { changes, rerender } = setup(options);
    fireEvent.click(screen.getByText('预览左对齐'));
    rerender(change === 'selection' ? { selectedNodeIds: ['source'] } : change === 'definition' ? { definition: initial() }
      : change === 'owner' ? { interactionKey: 'new' } : { [change]: true });
    expect(screen.queryByText('应用所选节点对齐')).toBeNull();
    rerender(options); expect(screen.queryByText('应用所选节点对齐')).toBeNull(); expect(changes).not.toHaveBeenCalled();
  });
  it('keeps control keys from nudging or deleting selected nodes; escape cancels preview', () => {
    const { changes, selections } = setup({ selectedNodeIds: ['source', 'prepare'] });
    const toggle = screen.getByRole('button', { name: '显示小地图' });
    for (const key of ['ArrowRight', 'Delete', 'Backspace', 'Escape']) fireEvent.keyDown(toggle, { key });
    fireEvent.click(screen.getByText('预览左对齐'));
    const apply = screen.getByText('应用所选节点对齐');
    for (const key of ['ArrowDown', 'Delete', 'Backspace']) fireEvent.keyDown(apply, { key });
    expect(changes).not.toHaveBeenCalled(); expect(selections).not.toHaveBeenCalled();
    fireEvent.keyDown(apply, { key: 'Escape' });
    expect(screen.queryByText('应用所选节点对齐')).toBeNull(); expect(position('prepare').left).toBe('480px');
  });
  it.each([{ readonly: true }, { busy: true }])('does not offer mutation when blocked %j', options => {
    setup({ ...options, selectedNodeIds: ['source', 'prepare'] });
    expect((screen.getByText('预览左对齐') as HTMLButtonElement).disabled).toBe(true);
  });
});


describe('transient world-grid controls', () => {
  it('toggles grid/snap without moving nodes or saving, and aligns grid to the camera', () => {
    const definition = initial(); definition.viewport = { x: -13, y: 29, zoom: 2 };
    const { changes, rerender } = setup({ definition, interactionKey: 'owner-a', selectedNodeIds: ['source'] });
    expect(viewport().style.backgroundSize).toBe('48px 48px');
    expect(viewport().style.backgroundPosition).toBe('-37px 5px');
    fireEvent.click(screen.getByRole('button', { name: '拖拽吸附' }));
    fireEvent.change(screen.getByLabelText('网格间距'), { target: { value: '16' } });
    expect(viewport().style.backgroundSize).toBe('32px 32px');
    fireEvent.click(screen.getByRole('button', { name: '显示网格' }));
    expect(viewport().style.backgroundImage).toBe('none');
    for (const target of [screen.getByRole('button', { name: '拖拽吸附' }), screen.getByLabelText('网格间距')]) {
      fireEvent.keyDown(target, { key: 'ArrowRight' }); fireEvent.keyDown(target, { key: 'Delete' });
    }
    fireEvent.keyDown(viewport(), { key: 'ArrowRight', isComposing: true });
    expect(changes).not.toHaveBeenCalled();
    rerender({ interactionKey: 'owner-b' });
    expect(screen.getByRole('button', { name: '拖拽吸附' }).getAttribute('aria-pressed')).toBe('false');
    expect((screen.getByLabelText('网格间距') as HTMLSelectElement).value).toBe('24');
  });
  it('snaps a multi-drag once using the grabbed node, supports cancellation and free placement', () => {
    const definition = initial(); definition.viewport.zoom = 2;
    definition.nodes[1].position = { x: 481, y: 147 };
    const { changes } = setup({ definition, selectedNodeIds: ['source', 'prepare'] });
    fireEvent.click(screen.getByRole('button', { name: '拖拽吸附' }));
    down(prepare(), 100, 100); move(140, 140);
    expect(position('prepare').left).toBe('504px'); expect(position('source').left).toBe('47px');
    expect(changes).not.toHaveBeenCalled();
    fireEvent.pointerCancel(viewport(), { pointerId: 1 }); expect(position('prepare').left).toBe('481px');
    down(prepare(), 100, 100); move(140, 140); up();
    expect(changes).toHaveBeenCalledTimes(1); expect(changes.mock.calls[0][1]).toBe(true);
    fireEvent.click(screen.getByRole('button', { name: '拖拽吸附' }));
    down(prepare(), 100, 100); move(102, 102); up();
    expect(position('prepare').left).toBe('505px'); expect(changes).toHaveBeenCalledTimes(2);
  });
  it('preserves keyboard screen-distance nudges when snap is enabled and avoids no-op undo', () => {
    const definition = initial(); definition.viewport.zoom = 2;
    const { changes } = setup({ definition, selectedNodeIds: ['source'] });
    fireEvent.click(screen.getByRole('button', { name: '拖拽吸附' }));
    down(source(), 100, 100); move(101, 101); up(); expect(changes).not.toHaveBeenCalled();
    fireEvent.keyDown(viewport(), { key: 'ArrowRight' }); expect(position('source').left).toBe('28px');
    fireEvent.keyDown(viewport(), { key: 'ArrowRight', shiftKey: true }); expect(position('source').left).toBe('44px');
  });
});


describe('world-space visual group outlines', () => {
  const grouped = (): StudioGraphDefinition => ({ ...initial(), presentation: { groups: [{ id: 'scene', name: '场景 <b>🎬</b>', node_ids: ['source', 'prepare'] }] } });
  const label = () => screen.getByRole('button', { name: '选择视觉分组 场景 <b>🎬</b> 的 2 个成员' });
  const frame = () => document.querySelector('[data-graph-group-id="scene"]') as HTMLElement;
  it('renders bounded plain labels, selects only on explicit activation and follows drag preview without writing presentation', () => {
    const definition = grouped();
    const { changes, selections } = setup({ definition });
    expect(frame().style.left).toBe('8px'); expect(frame().style.top).toBe('-24px');
    expect(frame().style.width).toBe('808px'); expect(frame().style.height).toBe('344px');
    expect(label().querySelector('b')).toBeNull();
    down(label(), 20, 0); move(70, 30); up(70, 30);
    expect(changes).not.toHaveBeenCalled(); expect(selections).not.toHaveBeenCalled();
    fireEvent.click(label());
    expect(selections).toHaveBeenLastCalledWith(['source', 'prepare']);
    expect(label().getAttribute('aria-pressed')).toBe('true');
    fireEvent.keyDown(label(), { key: 'Delete' }); fireEvent.keyDown(label(), { key: 'ArrowRight' });
    expect(changes).not.toHaveBeenCalled();
    down(source(), 40, 40); move(72, 56);
    expect(frame().style.left).toBe('40px'); expect(frame().style.top).toBe('-8px');
    expect(changes).not.toHaveBeenCalled(); up(72, 56);
    expect(changes).toHaveBeenCalledTimes(1);
    expect(changes.mock.calls[0][0].presentation).toEqual(definition.presentation);
  });
  it('keeps readonly selection available, busy selection disabled, and replaces stale owner frames', () => {
    const { changes, selections, rerender } = setup({ definition: grouped(), readonly: true });
    fireEvent.click(label()); expect(selections).toHaveBeenLastCalledWith(['source', 'prepare']);
    expect(changes).not.toHaveBeenCalled();
    rerender({ busy: true }); expect((label() as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(label()); expect(selections).toHaveBeenCalledTimes(1);
    rerender({ definition: initial(), busy: false, interactionKey: 'other' });
    expect(document.querySelector('[data-graph-group-id]')).toBeNull();
  });
  it('culls distant frames, retains focused labels, and keeps ports and background selection independent', () => {
    vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockReturnValue({ x: 0, y: 0, left: 0, top: 0, right: 800, bottom: 400, width: 800, height: 400, toJSON: () => ({}) });
    const definition = grouped(), onPortSelect = vi.fn();
    const { changes, selections, rerender } = setup({ definition, onPortSelect });
    const port = screen.getByRole('button', { name: /文本输入 source 输出端口/ });
    down(port, 344, 112); fireEvent.click(port); up();
    expect(onPortSelect).toHaveBeenCalledTimes(1); expect(selections).not.toHaveBeenCalled();
    act(() => label().focus());
    rerender({ definition: { ...definition, viewport: { x: 0, y: -5000, zoom: 1 } } });
    expect(frame()).not.toBeNull();
    act(() => viewport().focus());
    expect(frame()).toBeNull();
    rerender({ definition }); expect(frame()).not.toBeNull();
    down(viewport(), 0, 0); move(350, 140); up(350, 140);
    expect(selections).toHaveBeenLastCalledWith(['source']);
    expect(changes).not.toHaveBeenCalled();
  });
  it('preserves pan from a group label and uses the same zoom transform as cards', () => {
    const definition = grouped(); definition.viewport = { x: 20, y: 30, zoom: 2 };
    const { changes, selections } = setup({ definition });
    expect(document.querySelector('.graph-canvas__world')!.getAttribute('style')).toContain('scale(2)');
    down(label(), 40, 40, { altKey: true }); move(72, 56); up(72, 56);
    expect(changes.mock.calls[0][0].viewport).toEqual({ x: 52, y: 46, zoom: 2 });
    expect(selections).not.toHaveBeenCalled();
  });
});


describe('session-only visual group collapse', () => {
  const grouped = (): StudioGraphDefinition => ({ ...initial(), presentation: { groups: [{ id: 'scene', name: '场景', node_ids: ['source'] }] } });
  const collapseButton = () => screen.getByRole('button', { name: '折叠分组 场景' }) as HTMLButtonElement;
  it('hides members and incident curves, reports real connections, expands without any graph or port write', () => {
    const definition = grouped(), before = JSON.stringify(definition), onPortSelect = vi.fn();
    const { changes, selections } = setup({ definition, onPortSelect });
    const path = edgePath();
    fireEvent.click(collapseButton());
    expect(screen.queryByRole('button', { name: '选择节点 文本输入 · source' })).toBeNull();
    expect(prepare()).not.toBeNull(); expect(document.querySelector('[data-graph-edge-id]')).toBeNull();
    expect(screen.getByText('场景：1 个成员 · 1 条对外连接 · 0 条内部连接（线条已隐藏）')).not.toBeNull();
    expect(screen.getByText('source 输出 text → prepare 输入 text')).not.toBeNull();
    const card = document.querySelector('[data-graph-collapsed]') as HTMLElement;
    expect(card.style.width).toBe('320px'); expect(card.querySelector('[data-graph-port]')).toBeNull();
    const expand = screen.getByRole('button', { name: '展开画布分组 场景' });
    act(() => expand.focus()); fireEvent.keyDown(expand, { key: 'Delete' }); fireEvent.keyDown(expand, { key: 'ArrowRight' });
    fireEvent.click(expand);
    expect(document.activeElement).toBe(screen.getByRole('button', { name: '选择视觉分组 场景 的 1 个成员' }));
    expect(source()).not.toBeNull(); expect(edgePath()).toBe(path);
    expect(changes).not.toHaveBeenCalled(); expect(selections).not.toHaveBeenCalled(); expect(onPortSelect).not.toHaveBeenCalled();
    expect(JSON.stringify(definition)).toBe(before);
  });
  it.each(['selected', 'connecting', 'focused'])('keeps %s members visible and explains disabled collapse', mode => {
    const { changes } = setup({ definition: grouped(), selectedNodeIds: mode === 'selected' ? ['source'] : [], connectionNodeIds: mode === 'connecting' ? ['source'] : [] });
    if (mode === 'focused') act(() => source().focus());
    expect(collapseButton().disabled).toBe(true); expect(collapseButton().title).toContain('取消成员选择');
    fireEvent.click(collapseButton()); expect(source()).not.toBeNull(); expect(changes).not.toHaveBeenCalled();
  });
  it.each(['selected', 'connecting'])('expands permanently when a hidden member becomes %s', mode => {
    const { rerender, changes } = setup({ definition: grouped() });
    fireEvent.click(collapseButton());
    rerender(mode === 'selected' ? { selectedNodeIds: ['source'] } : { connectionNodeIds: ['source'] });
    expect(source()).not.toBeNull();
    rerender({ selectedNodeIds: [], connectionNodeIds: [] });
    expect(source()).not.toBeNull(); expect(collapseButton().disabled).toBe(false); expect(changes).not.toHaveBeenCalled();
  });
  it('retains collapse on camera changes, but resets on owner/group replacement and unmount', () => {
    const definition = grouped(); const { rerender, unmount, changes } = setup({ definition, interactionKey: 'a' });
    fireEvent.click(collapseButton());
    rerender({ definition: { ...definition, viewport: { x: 100, y: 100, zoom: 2 } } });
    expect(document.querySelector('[data-graph-collapsed]')).not.toBeNull();
    rerender({ interactionKey: 'b' }); expect(source()).not.toBeNull();
    fireEvent.click(collapseButton()); rerender({ definition: grouped() }); expect(source()).not.toBeNull();
    fireEvent.click(collapseButton()); expect(changes).not.toHaveBeenCalled(); unmount();
    setup({ definition }); expect(source()).not.toBeNull();
  });
  it('allows readonly view folding, blocks busy folding, and isolates toolbar keyboard input', () => {
    const { changes, selections, rerender } = setup({ definition: grouped(), readonly: true, selectedNodeIds: ['prepare'] });
    fireEvent.keyDown(collapseButton(), { key: 'Delete' }); fireEvent.keyDown(collapseButton(), { key: 'ArrowRight' });
    fireEvent.click(collapseButton()); expect(document.querySelector('[data-graph-collapsed]')).not.toBeNull();
    rerender({ busy: true }); expect((screen.getByRole('button', { name: '展开分组 场景' }) as HTMLButtonElement).disabled).toBe(true);
    expect(changes).not.toHaveBeenCalled(); expect(selections).not.toHaveBeenCalled();
  });
});
