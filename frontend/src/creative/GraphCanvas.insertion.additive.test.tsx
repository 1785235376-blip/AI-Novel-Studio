// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { GraphCanvas, type GraphCanvasProps } from './GraphCanvas';
import { modelCatalog, modelGraph } from './studioGraphModel.testFixtures';
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });
const area = () => screen.getByRole('group', { name: '节点图交互区域' });
function setup(patch: Partial<GraphCanvasProps> = {}) {
  const definition = modelGraph().definition; definition.viewport = { x: 80, y: -40, zoom: 2 };
  const props: GraphCanvasProps = { definition, nodeDefinitions: modelCatalog().definitions, selectedNodeIds: [],
    onSelectionChange: vi.fn(), onDefinitionChange: vi.fn(), onPortSelect: vi.fn(), insertionScope: {}, onRequestInsertion: vi.fn(() => true), ...patch };
  const view = render(<GraphCanvas {...props}/>);
  vi.spyOn(area(), 'getBoundingClientRect').mockReturnValue({ left: 100, top: 50, width: 800, height: 400, right: 900, bottom: 450, x: 100, y: 50, toJSON: () => ({}) });
  return { props, ...view };
}
it('captures a rect-relative pan/zoom point without graph or selection changes', () => {
  const { props } = setup();
  fireEvent.contextMenu(area(), { clientX: 340, clientY: 170 });
  expect(props.onRequestInsertion).toHaveBeenCalledWith({ x: 80, y: 80 }, props.insertionScope, expect.any(Function));
  expect(props.onDefinitionChange).not.toHaveBeenCalled(); expect(props.onSelectionChange).not.toHaveBeenCalled();
});
it('supports keyboard center only on the viewport, excluding IME, repeats and descendants', () => {
  const { props } = setup(); area().focus();
  fireEvent.keyDown(area(), { key: 'F10', shiftKey: true });
  expect(props.onRequestInsertion).toHaveBeenLastCalledWith({ x: 160, y: 120 }, props.insertionScope, expect.any(Function));
  fireEvent.keyDown(area(), { key: 'ContextMenu', isComposing: true });
  fireEvent.keyDown(area(), { key: 'ContextMenu', keyCode: 229 });
  fireEvent.keyDown(area(), { key: 'ContextMenu', repeat: true });
  fireEvent.keyDown(screen.getByRole('button', { name: '放大节点图' }), { key: 'F10', shiftKey: true });
  expect(props.onRequestInsertion).toHaveBeenCalledTimes(1);
});
it('leaves node, port and toolbar context menus alone', () => {
  const { props } = setup();
  fireEvent.contextMenu(document.querySelector('[data-graph-node-id]')!);
  fireEvent.contextMenu(document.querySelector('[data-graph-port]')!);
  fireEvent.contextMenu(screen.getByRole('button', { name: '放大节点图' }));
  expect(props.onRequestInsertion).not.toHaveBeenCalled();
});
it.each([{ busy: true }, { readonly: true }, { insertionScope: undefined }, { onRequestInsertion: undefined }])('does not open without current editable authority: %j', patch => {
  const { props } = setup(patch); fireEvent.contextMenu(area(), { clientX: 300, clientY: 200 });
  if (props.onRequestInsertion) expect(props.onRequestInsertion).not.toHaveBeenCalled();
});
it('does not interfere with pointer capture for a live marquee', () => {
  class Pointer extends MouseEvent { pointerId: number; constructor(type: string, init: PointerEventInit) { super(type, init); this.pointerId = init.pointerId ?? 1; } }
  vi.stubGlobal('PointerEvent', Pointer);
  const { props } = setup(); const release = vi.fn(); Object.defineProperty(area(), 'setPointerCapture', { value: vi.fn() });
  Object.defineProperty(area(), 'hasPointerCapture', { value: () => true }); Object.defineProperty(area(), 'releasePointerCapture', { value: release });
  fireEvent.pointerDown(area(), { button: 0, pointerId: 1, clientX: 200, clientY: 100 });
  fireEvent.contextMenu(area(), { clientX: 300, clientY: 200 });
  expect(props.onRequestInsertion).not.toHaveBeenCalled(); expect(release).not.toHaveBeenCalled();
  fireEvent.pointerCancel(area(), { pointerId: 1 }); expect(release).toHaveBeenCalledWith(1);
});
it('clamps extreme world coordinates and refuses nonfinite geometry', () => {
  const { props } = setup(); fireEvent.contextMenu(area(), { clientX: 1e8, clientY: -1e8 });
  expect(props.onRequestInsertion).toHaveBeenLastCalledWith({ x: 100000, y: -100000 }, props.insertionScope, expect.any(Function));
  vi.mocked(area().getBoundingClientRect).mockReturnValue({ left: NaN, top: 0, width: 800, height: 400 } as DOMRect);
  fireEvent.contextMenu(area(), { clientX: 300, clientY: 200 }); expect(props.onRequestInsertion).toHaveBeenCalledTimes(1);
});
it('restores focus only while the original viewport owner still exists', () => {
  const { props, rerender } = setup({ interactionKey: 'A' }); fireEvent.contextMenu(area(), { clientX: 300, clientY: 200 });
  const restore = vi.mocked(props.onRequestInsertion!).mock.calls[0][2];
  screen.getByRole('button', { name: '放大节点图' }).focus(); restore(); expect(document.activeElement).toBe(area());
  rerender(<GraphCanvas {...props} interactionKey="B"/>); const button = screen.getByRole('button', { name: '放大节点图' }); button.focus(); restore(); expect(document.activeElement).toBe(button);
});

it('invalidates pending insertion before starting a captured gesture', () => {
  class Pointer extends MouseEvent { pointerId: number; constructor(type: string, init: PointerEventInit) { super(type, init); this.pointerId = init.pointerId ?? 1; } }
  vi.stubGlobal('PointerEvent', Pointer); const invalidate = vi.fn(); const { props } = setup({ onInsertionInteraction: invalidate });
  Object.defineProperty(area(), 'setPointerCapture', { value: vi.fn() });
  fireEvent.contextMenu(area(), { clientX: 300, clientY: 200 }); expect(props.onRequestInsertion).toHaveBeenCalledTimes(1);
  fireEvent.pointerDown(area(), { button: 0, pointerId: 1, clientX: 200, clientY: 100 });
  expect(invalidate).toHaveBeenCalledTimes(1); expect(props.onDefinitionChange).not.toHaveBeenCalled();
});
it('does not restore focus after owner ABA even with identical identifiers', () => {
  const { props, rerender } = setup({ interactionKey: 'A' }); fireEvent.contextMenu(area(), { clientX: 300, clientY: 200 });
  const restore = vi.mocked(props.onRequestInsertion!).mock.calls[0][2];
  rerender(<GraphCanvas {...props} interactionKey="B"/>); rerender(<GraphCanvas {...props}/>);
  const button = screen.getByRole('button', { name: '放大节点图' }); button.focus(); restore(); expect(document.activeElement).toBe(button);
});

it('opens insertion with A key and reports display/exec status split', () => {
  const { props } = setup();
  area().focus();
  fireEvent.keyDown(area(), { key: 'a' });
  expect(props.onRequestInsertion).toHaveBeenCalledTimes(1);
  const status = document.querySelector('.graph-canvas__count')!;
  expect(status.getAttribute('data-budget-split')).toBe('true');
  expect(status.getAttribute('data-display-nodes')).toBeTruthy();
  expect(status.getAttribute('data-executable-nodes')).toBeTruthy();
  expect(status.textContent).toMatch(/展示|已选/);
});

it('accepts asset drop as reference payload only', () => {
  const onAssetDrop = vi.fn(() => true);
  const { props } = setup({ onAssetDrop, removalDefinitions: modelCatalog().definitions });
  const dt = { getData: (type: string) => type.includes('asset-ref') || type === 'text/plain'
    ? JSON.stringify({ asset_id: 'a1', version: 1, digest: 'd', kind: 'image' }) : '',
    types: ['application/x-poemseed-asset-ref'], dropEffect: 'none' as string };
  fireEvent.dragOver(area(), { dataTransfer: dt });
  fireEvent.drop(area(), { clientX: 300, clientY: 200, dataTransfer: dt });
  expect(onAssetDrop).toHaveBeenCalledWith(expect.objectContaining({ x: expect.any(Number), y: expect.any(Number) }),
    { asset_id: 'a1', version: 1, digest: 'd', kind: 'image' });
  expect(props.onDefinitionChange).not.toHaveBeenCalled();
});

// [HERMIA-FE-20261022] H-UX-F7-02
it('shows honest empty state with current-module scope and first-node CTA reusing H-P1-03 insertion', () => {
  const definition = { ...modelGraph().definition, nodes: [], edges: [], presentation: undefined } as GraphCanvasProps['definition'];
  const { props } = setup({ definition, scopeLabel: '视频' });
  expect(document.querySelector('[data-graph-empty]')!.textContent).toMatch(/尚无节点/);
  expect(document.querySelector('[data-graph-scope="current-module"]')!.textContent).toBe('作用域：仅当前模块（视频） · 不影响其他模块的画布');
  fireEvent.click(document.querySelector('[data-add-first-node]')!);
  expect(props.onRequestInsertion).toHaveBeenCalledWith({ x: 400, y: 200 }, props.insertionScope, expect.any(Function));
  expect(props.onDefinitionChange).not.toHaveBeenCalled();
});
it('hides first-node CTA when readonly but keeps scope note', () => {
  const definition = { ...modelGraph().definition, nodes: [], edges: [], presentation: undefined } as GraphCanvasProps['definition'];
  setup({ definition, readonly: true });
  expect(document.querySelector('[data-add-first-node]')).toBeNull();
  expect(document.querySelector('[data-graph-scope]')!.textContent).toMatch(/仅当前模块/);
});
