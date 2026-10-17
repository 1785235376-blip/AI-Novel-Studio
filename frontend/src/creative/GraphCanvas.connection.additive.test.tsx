// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { GraphCanvas, type GraphCanvasProps, type GraphCanvasPortSelection } from './GraphCanvas';
import { connectionIssue } from './graphDraft';
import { modelCatalog, modelGraph } from './studioGraphModel.testFixtures';

class TestPointerEvent extends MouseEvent {
  readonly pointerId: number;
  constructor(type: string, options: PointerEventInit = {}) { super(type, options); this.pointerId = options.pointerId ?? 1; }
}
const source: GraphCanvasPortSelection = { nodeId: 'input', portId: 'text', direction: 'output' };
const target: GraphCanvasPortSelection = { nodeId: 'generate', portId: 'text', direction: 'input' };
const viewport = () => screen.getByRole('group', { name: '节点图交互区域' });
const port = (value: GraphCanvasPortSelection) => document.querySelector(`[data-graph-node-id="${value.nodeId}"] [data-graph-port="${value.portId}"][data-graph-direction="${value.direction}"]`)!;
const wire = () => screen.queryByTestId('graph-connection-preview');
let hit: Element | null;
const down = (value = source) => fireEvent.pointerDown(port(value), { button: 0, pointerId: 1, clientX: 100, clientY: 100 });
const move = () => fireEvent.pointerMove(viewport(), { pointerId: 1, clientX: 180, clientY: 120 });
const up = (pointerId = 1) => fireEvent.pointerUp(viewport(), { pointerId, clientX: 180, clientY: 120 });
function setup(overrides: Partial<GraphCanvasProps> = {}) {
  const definition = modelGraph().definition; definition.edges = [];
  const catalog = modelCatalog();
  const props: GraphCanvasProps = { definition, nodeDefinitions: catalog.definitions, selectedNodeIds: [],
    onSelectionChange: vi.fn(), onDefinitionChange: vi.fn(), onPortSelect: vi.fn(),
    connectionScope: {}, onConnectionStage: vi.fn(() => true),
    connectionIssue: (a, b) => connectionIssue(definition, catalog.definitions, { id: 'pending',
      source_node_id: a.nodeId, source_port: a.portId, target_node_id: b.nodeId, target_port: b.portId }), ...overrides };
  const result = render(<GraphCanvas {...props} />);
  return { props, ...result, rerenderProps: (patch: Partial<GraphCanvasProps>) => result.rerender(<GraphCanvas {...props} {...patch} />) };
}
beforeEach(() => {
  vi.stubGlobal('PointerEvent', TestPointerEvent); hit = null;
  Object.defineProperty(document, 'elementFromPoint', { configurable: true, value: vi.fn(() => hit) });
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

describe('connection gesture is a guarded endpoint selection', () => {
  it.each([false, true])('previews and stages an oriented pair, reverse=%s, without mutating graph', reverse => {
    const { props } = setup(); const a = reverse ? target : source, b = reverse ? source : target;
    hit = port(a); down(a); hit = port(b); move();
    expect(wire()).toBeTruthy(); expect(port(b).getAttribute('data-connection-compatible')).toBe('true');
    expect(props.onConnectionStage).not.toHaveBeenCalled(); up();
    expect(props.onConnectionStage).toHaveBeenCalledWith(source, target, props.connectionScope);
    expect(props.onDefinitionChange).not.toHaveBeenCalled(); expect(props.onPortSelect).not.toHaveBeenCalled();
    expect(wire()).toBeNull(); expect(screen.getByText(/已选择连接端口/)).toBeTruthy();
  });
  it('uses original type mismatch explanation and preserves existing endpoint selection', () => {
    const { props } = setup(); down(); hit = port({ ...target, portId: 'direction' }); move();
    expect(screen.getByText('端口类型不匹配：TEXT → DIRECTOR_NOTES。')).toBeTruthy(); up();
    expect(props.onConnectionStage).not.toHaveBeenCalled(); expect(props.onPortSelect).not.toHaveBeenCalled();
  });
  it('rejects same-direction ports even when their identifiers could resolve as real inputs', () => {
    const { props } = setup(); down(); hit = port(source); move(); up();
    expect(screen.getByText('请选择真实的输出端口和输入端口。')).toBeTruthy();
    expect(props.onConnectionStage).not.toHaveBeenCalled();
  });
  it('re-hit-tests drop coordinates rather than trusting hover or captured event target', () => {
    const { props } = setup(); down(); hit = port(target); move(); hit = null; up();
    expect(props.onConnectionStage).not.toHaveBeenCalled(); expect(wire()).toBeNull();
  });
  it('ignores foreign viewport ports and disabled buttons', () => {
    const { props } = setup(); down(); const foreign = port(target).cloneNode(true) as HTMLButtonElement;
    document.body.append(foreign); hit = foreign; move(); up(); foreign.remove();
    expect(props.onConnectionStage).not.toHaveBeenCalled();
    down(); hit = port(target); (hit as HTMLButtonElement).disabled = true; move(); up();
    expect(props.onConnectionStage).not.toHaveBeenCalled();
  });
  it.each(['cancel', 'lost', 'blur', 'escape', 'resize', 'scroll'] as const)('cancels on %s without mutation', reason => {
    const { props } = setup(); down(); hit = port(target); move();
    if (reason === 'cancel') fireEvent.pointerCancel(viewport(), { pointerId: 1 });
    if (reason === 'lost') fireEvent.lostPointerCapture(viewport(), { pointerId: 1 });
    if (reason === 'blur') fireEvent(window, new Event('blur'));
    if (reason === 'escape') fireEvent.keyDown(screen.getByRole('button', { name: '显示网格' }), { key: 'Escape' });
    if (reason === 'resize' || reason === 'scroll') fireEvent(window, new Event(reason));
    up(); expect(wire()).toBeNull(); expect(props.onConnectionStage).not.toHaveBeenCalled(); expect(props.onDefinitionChange).not.toHaveBeenCalled();
  });
  it.each(['interactionKey', 'preferencesSource', 'definition', 'connectionScope', 'nodeDefinitions', 'busy', 'readonly'] as const)('does not resurrect a gesture after %s ABA', field => {
    const { props, rerenderProps } = setup(); down(); hit = port(target); move();
    const value = field === 'interactionKey' ? 'different' : field === 'busy' || field === 'readonly' ? true
      : field === 'definition' ? { ...props.definition, title: 'changed' }
      : field === 'nodeDefinitions' ? [] : {};
    rerenderProps({ [field]: value }); rerenderProps({}); hit = port(target); up();
    expect(props.onConnectionStage).not.toHaveBeenCalled(); expect(wire()).toBeNull();
  });
  it('keeps a gesture across equivalent catalog arrays and ignores other pointers', () => {
    const { props, rerenderProps } = setup(); down(); hit = port(target); move();
    rerenderProps({ nodeDefinitions: [...props.nodeDefinitions] }); up(2); expect(wire()).toBeTruthy();
    up(); expect(props.onConnectionStage).toHaveBeenCalledTimes(1);
  });
  it('preserves click and keyboard selection, suppressing only the physical post-drag click', () => {
    const { props } = setup(); down(); fireEvent.pointerUp(viewport(), { pointerId: 1, clientX: 100, clientY: 100 });
    fireEvent.click(port(source), { detail: 1 }); expect(props.onPortSelect).toHaveBeenCalledTimes(1);
    down(); hit = port(target); move(); up(); fireEvent.click(port(source), { detail: 1 });
    expect(props.onPortSelect).toHaveBeenCalledTimes(1);
    fireEvent.click(port(source), { detail: 0 }); expect(props.onPortSelect).toHaveBeenCalledTimes(2);
    down(); fireEvent.pointerUp(viewport(), { pointerId: 1, clientX: 100, clientY: 100 });
    fireEvent.click(port(source), { detail: 1 }); expect(props.onPortSelect).toHaveBeenCalledTimes(3);
  });
  it('releases pointer capture on unmount', () => {
    const { unmount, props } = setup(); const element = viewport();
    element.setPointerCapture = vi.fn(); element.hasPointerCapture = vi.fn(() => true); element.releasePointerCapture = vi.fn();
    down(); hit = port(target); move(); unmount();
    expect(element.releasePointerCapture).toHaveBeenCalledWith(1); expect(props.onConnectionStage).not.toHaveBeenCalled();
  });
});

it.each([
  ['duplicate', '此连接已经存在。'],
  ['occupied', '该输入端口只接受一个连接。'],
  ['cycle', '此连接会形成循环，无法保存。'],
] as const)('displays the original %s reason without staging', (kind, message) => {
  const definition = modelGraph().definition, catalog = modelCatalog();
  definition.nodes = ['a', 'b', 'c'].map((id, index) => ({ id, definition_id: 'text_reference', definition_version: 1,
    enabled: true, position: { x: index * 400, y: 0 }, parameters: {} }));
  definition.edges = [{ id: 'existing', source_node_id: kind === 'cycle' ? 'b' : kind === 'occupied' ? 'c' : 'a',
    source_port: 'text', target_node_id: kind === 'cycle' ? 'a' : 'b', target_port: 'text' }];
  const a: GraphCanvasPortSelection = { nodeId: 'a', portId: 'text', direction: 'output' };
  const b: GraphCanvasPortSelection = { nodeId: 'b', portId: 'text', direction: 'input' };
  const { props } = setup({ definition, connectionIssue: (left, right) => connectionIssue(definition, catalog.definitions,
    { id: 'pending', source_node_id: left.nodeId, source_port: left.portId, target_node_id: right.nodeId, target_port: right.portId }) });
  down(a); hit = port(b); move(); expect(screen.getByText(message)).toBeTruthy(); up();
  expect(props.onConnectionStage).not.toHaveBeenCalled(); expect(props.onDefinitionChange).not.toHaveBeenCalled();
});
it('never treats a collapsed group frame as an input port', () => {
  const definition = modelGraph().definition; definition.edges = [];
  definition.presentation = { groups: [{ id: 'g', name: 'Target', node_ids: ['generate'] }] };
  const { props } = setup({ definition });
  fireEvent.click(screen.getByRole('button', { name: '折叠分组 Target' })); expect(port(target)).toBeNull();
  down(); hit = document.querySelector('[data-graph-collapsed]'); move(); up();
  expect(props.onConnectionStage).not.toHaveBeenCalled(); expect(props.onDefinitionChange).not.toHaveBeenCalled();
});
it('cancels an unmoved gesture without accepting the subsequent physical click', () => {
  const { props } = setup(); down(); fireEvent.pointerCancel(viewport(), { pointerId: 1 });
  fireEvent.click(port(source), { detail: 1 }); expect(props.onPortSelect).not.toHaveBeenCalled();
  fireEvent.click(port(source), { detail: 0 }); expect(props.onPortSelect).toHaveBeenCalledWith(source);
});
it('keeps inverse-zoom wire geometry and blocks camera/node changes during a connection', () => {
  const definition = modelGraph().definition; definition.edges = []; definition.viewport = { x: 20, y: 30, zoom: 2 };
  const { props } = setup({ definition }); down(); hit = null; move();
  expect(wire()?.getAttribute('d')).toContain('80 45');
  fireEvent.wheel(viewport(), { ctrlKey: true, deltaY: -100 });
  fireEvent.click(screen.getByRole('button', { name: '放大节点图' }));
  fireEvent.pointerDown(viewport(), { button: 1, pointerId: 2, clientX: 0, clientY: 0 });
  expect(props.onDefinitionChange).not.toHaveBeenCalled(); expect(wire()).toBeTruthy();
  fireEvent.keyDown(viewport(), { key: 'Escape' });
  fireEvent.pointerDown(viewport(), { button: 1, pointerId: 2, clientX: 0, clientY: 0 });
  fireEvent.pointerMove(viewport(), { pointerId: 2, clientX: 40, clientY: 30 });
  fireEvent.pointerUp(viewport(), { pointerId: 2, clientX: 40, clientY: 30 });
  expect(props.onDefinitionChange).toHaveBeenCalledTimes(1);
});
it('does not create a target for an off-screen culled endpoint', () => {
  vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockReturnValue({ x: 0, y: 0, left: 0, top: 0, right: 600, bottom: 400, width: 600, height: 400, toJSON: () => ({}) });
  const definition = modelGraph().definition; definition.edges = []; definition.nodes[1].position.x = 10000;
  const { props } = setup({ definition }); expect(port(target)).toBeNull();
  down(); hit = null; move(); up(); expect(props.onConnectionStage).not.toHaveBeenCalled();
});
