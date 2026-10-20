// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { StudioBinaryMaskCanvas } from './StudioBinaryMaskCanvas';
import { BinaryMaskDraft } from './studioBinaryMask';

class TestPointerEvent extends MouseEvent {
  readonly pointerId: number;
  constructor(type: string, options: PointerEventInit = {}) { super(type, options); this.pointerId = options.pointerId ?? 1; }
}
beforeEach(() => {
  vi.stubGlobal('PointerEvent', TestPointerEvent);
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue({
    createImageData: (width: number, height: number) => ({ data: new Uint8ClampedArray(width * height * 4), width, height }), putImageData: vi.fn(),
  } as unknown as CanvasRenderingContext2D);
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });
const button = (name: string) => screen.getByRole('button', { name });
const handlers = (element: Element) => (element as unknown as Record<string, Record<string, (...args: never[]) => void>>)[Object.keys(element).find(key => key.startsWith('__reactProps$'))!];
function setup() {
  const props = { mask: new BinaryMaskDraft(64, 64), sourceUrl: 'blob:source-a', readOnly: false, isCurrent: () => true, onChange: vi.fn() };
  const view = render(<StudioBinaryMaskCanvas {...props} />);
  const canvas = screen.getByRole('application');
  vi.spyOn(canvas, 'getBoundingClientRect').mockReturnValue({ x: 16, y: 32, left: 16, top: 32, width: 128, height: 128, right: 144, bottom: 160, toJSON: () => ({}) });
  fireEvent.click(button('多边形选区'));
  return { ...view, ...props, canvas, rerender: (extra: Partial<typeof props> = {}) => view.rerender(<StudioBinaryMaskCanvas {...props} {...extra} />) };
}
function add(x: number, y: number) {
  fireEvent.change(screen.getByLabelText('多边形顶点 X'), { target: { value: String(x) } });
  fireEvent.change(screen.getByLabelText('多边形顶点 Y'), { target: { value: String(y) } });
  fireEvent.click(button('添加坐标顶点'));
}
function preview() {
  add(0, 0); add(4, 0); add(0, 4); fireEvent.click(button('预览多边形选区'));
}
const applyName = '填充选区为黑色 REMOVE';

describe('explicit polygon mask authoring', () => {
  it('requires preview and an explicit color, changes no pixels before apply, and undoes once', () => {
    const { mask, onChange } = setup();
    expect((button(applyName) as HTMLButtonElement).disabled).toBe(true);
    preview(); expect(screen.getByText(/选中 10 个像素/)).toBeTruthy();
    expect(mask.canUndo).toBe(false); expect(onChange).not.toHaveBeenCalled();
    fireEvent.click(button(applyName)); expect(mask.serialize().remove_pixels).toBe(10); expect(onChange).toHaveBeenCalledTimes(1);
    expect(screen.queryByText(/已预览/)).toBeNull(); expect((button(applyName) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(button('撤销蒙版编辑')); expect(mask.canUndo).toBe(false); expect(mask.get(0, 0)).toBe(true);
    preview(); fireEvent.click(button(applyName)); preview(); fireEvent.click(button('填充选区为白色 KEEP'));
    expect(() => mask.serialize()).toThrow(/KEEP.*REMOVE/);
  });

  it('maps scaled pointer grid corners, supports keyboard vertices and rejects outside clicks without clipping', () => {
    const { canvas, mask } = setup();
    fireEvent.pointerDown(canvas, { button: 0, clientX: 16, clientY: 32 });
    fireEvent.pointerDown(canvas, { button: 0, clientX: 24, clientY: 32 });
    for (let i = 0; i < 4; i++) fireEvent.keyDown(canvas, { key: 'ArrowDown' });
    fireEvent.keyDown(canvas, { key: 'Enter' });
    fireEvent.pointerDown(canvas, { button: 0, clientX: 15, clientY: 32 });
    expect(screen.getByRole('list', { name: '多边形顶点顺序' }).children).toHaveLength(3);
    expect(screen.getByText(/不会自动裁剪/)).toBeTruthy();
    fireEvent.click(button('预览多边形选区')); fireEvent.click(button(applyName));
    expect(mask.serialize().remove_pixels).toBe(10);
    add(64, 64); expect(screen.getByText(/顶点 1.*64, 64/)).toBeTruthy();
    fireEvent.keyDown(canvas, { key: 'Backspace' }); expect(screen.getByRole('list').children).toHaveLength(0);
    add(1, 1); fireEvent.keyDown(canvas, { key: 'Escape' }); expect(mask.serialize().remove_pixels).toBe(10);
  });

  it('does not preview or apply a self-intersecting selection, and editing a vertex retires old apply callbacks', () => {
    const { mask, onChange } = setup();
    add(0, 0); add(4, 4); add(0, 4); add(4, 0); fireEvent.click(button('预览多边形选区'));
    expect(screen.getByText(/不能自交/)).toBeTruthy(); expect((button(applyName) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(button('取消多边形选区')); preview();
    const oldApply = handlers(button(applyName)).onClick, oldPreview = handlers(button('预览多边形选区')).onClick;
    fireEvent.change(screen.getByLabelText('多边形顶点 X'), { target: { value: '5' } });
    act(() => { oldApply(); oldPreview(); });
    expect(mask.canUndo).toBe(false); expect(onChange).not.toHaveBeenCalled(); expect(screen.queryByText(/已预览/)).toBeNull();
    expect((button(applyName) as HTMLButtonElement).disabled).toBe(true);
  });

  it.each(['source', 'readonly', 'authority', 'mask'] as const)('retires selection and old callbacks across %s transitions including ABA', transition => {
    const view = setup(); preview();
    const oldApply = handlers(button(applyName)).onClick, oldAdd = handlers(button('添加坐标顶点')).onClick;
    if (transition === 'source') { view.rerender({ sourceUrl: 'blob:b' }); view.rerender(); }
    if (transition === 'readonly') { view.rerender({ readOnly: true }); view.rerender(); }
    if (transition === 'authority') { view.rerender({ isCurrent: () => false }); view.rerender(); }
    if (transition === 'mask') { view.rerender({ mask: new BinaryMaskDraft(64, 64) }); view.rerender(); }
    act(() => { oldApply(); oldAdd(); });
    expect(view.mask.canUndo).toBe(false); expect(view.onChange).not.toHaveBeenCalled();
    expect(screen.getByRole('list').children).toHaveLength(0); expect(screen.queryByText(/已预览/)).toBeNull();
    // A fresh, current selection still works after rejecting the retired callback.
    preview(); fireEvent.click(button(applyName)); expect(view.mask.serialize().remove_pixels).toBe(10);
  });

  it('rechecks authority at the event boundary and refuses old callbacks after unmount', () => {
    let current = true; const view = setup(); view.rerender({ isCurrent: () => current }); preview();
    const oldApply = handlers(button(applyName)).onClick;
    current = false; act(() => oldApply()); current = true; view.rerender();
    expect(view.mask.canUndo).toBe(false); expect(screen.getByRole('list').children).toHaveLength(0);
    preview(); const afterUnmount = handlers(button(applyName)).onClick; view.unmount(); act(() => afterUnmount());
    expect(view.mask.canUndo).toBe(false); expect(view.onChange).not.toHaveBeenCalled();
  });

  it('retires previews on another bitmap edit, source failure, and source revision changes', () => {
    const view = setup(); preview(); const oldApply = handlers(button(applyName)).onClick;
    view.mask.paint(63, 63, 0, false); act(() => oldApply()); expect(view.mask.serialize().remove_pixels).toBe(1);
    view.rerender(); expect(screen.queryByText(/已预览/)).toBeNull();
    preview(); fireEvent.error(screen.getByAltText('蒙版来源预览'));
    expect(screen.queryByText(/已预览/)).toBeNull(); expect((button(applyName) as HTMLButtonElement).disabled).toBe(true);
    expect(view.mask.serialize().remove_pixels).toBe(1);
  });
});
