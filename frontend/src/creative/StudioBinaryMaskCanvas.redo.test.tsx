// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { StudioBinaryMaskCanvas, type StudioBinaryMaskCanvasProps } from './StudioBinaryMaskCanvas';
import { BinaryMaskDraft } from './studioBinaryMask';

beforeEach(() => {
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue({
    createImageData: (width: number, height: number) => ({ data: new Uint8ClampedArray(width * height * 4), width, height }), putImageData: vi.fn(),
  } as unknown as CanvasRenderingContext2D);
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); });
const button = (name: string) => screen.getByRole('button', { name }) as HTMLButtonElement;
const redo = () => button('重做蒙版编辑'), undo = () => button('撤销蒙版编辑');
const clickHandler = (element: Element) => (element as unknown as Record<string, { onClick: () => void }>)[Object.keys(element).find(key => key.startsWith('__reactProps$'))!].onClick;
function setup(extra: Partial<StudioBinaryMaskCanvasProps> = {}) {
  const props = { mask: new BinaryMaskDraft(64, 64), sourceUrl: 'blob:source-a', readOnly: false, isCurrent: () => true, onChange: vi.fn(), ...extra };
  const view = render(<StudioBinaryMaskCanvas {...props} />);
  return { ...view, ...props, rerender: (next: Partial<StudioBinaryMaskCanvasProps> = {}) => view.rerender(<StudioBinaryMaskCanvas {...props} {...next} />) };
}
function undone() {
  const mask = new BinaryMaskDraft(64, 64); mask.paint(0, 0, 0, false); mask.undo(); return mask;
}

describe('explicit local mask redo control', () => {
  it('enables after undo, restores exact pixels, notifies once and stops at the end of history', () => {
    const view = setup(); expect(redo().disabled).toBe(true);
    fireEvent.click(button('应用精确矩形')); const snapshot = view.mask.snapshot();
    fireEvent.click(undo()); expect(redo().disabled).toBe(false); expect(undo().disabled).toBe(true);
    vi.mocked(view.onChange).mockClear(); fireEvent.click(redo());
    expect(view.mask.snapshot()).toEqual(snapshot); expect(view.onChange).toHaveBeenCalledTimes(1);
    expect(redo().disabled).toBe(true); expect(undo().disabled).toBe(false);
    fireEvent.click(redo()); expect(view.onChange).toHaveBeenCalledTimes(1);
    fireEvent.click(undo()); fireEvent.click(button('全部设为黑色 REMOVE'));
    expect(redo().disabled).toBe(true); expect(view.mask.canRedo).toBe(false);
  });

  it.each(['readonly', 'authority', 'source', 'mask', 'dimensions'] as const)('rejects current and retired callbacks after %s changes, including rendered ABA', transition => {
    const view = setup({ mask: undone() }), oldRedo = clickHandler(redo());
    const replacement = new BinaryMaskDraft(transition === 'dimensions' ? 72 : 64, 64);
    const change = transition === 'readonly' ? { readOnly: true } : transition === 'authority' ? { isCurrent: () => false }
      : transition === 'source' ? { sourceUrl: 'blob:source-b' } : { mask: replacement };
    view.rerender(change); act(oldRedo);
    expect(view.mask.get(0, 0)).toBe(true); expect(view.onChange).not.toHaveBeenCalled();
    view.rerender(); act(oldRedo);
    expect(view.mask.get(0, 0)).toBe(true); expect(view.onChange).not.toHaveBeenCalled();
    fireEvent.click(redo()); expect(view.mask.get(0, 0)).toBe(false); expect(view.onChange).toHaveBeenCalledTimes(1);
  });

  it('rechecks authority/busy ownership synchronously without requiring a render', () => {
    let available = true; const view = setup({ mask: undone(), isCurrent: () => available });
    available = false; fireEvent.click(redo());
    expect(view.mask.canRedo).toBe(true); expect(view.mask.get(0, 0)).toBe(true); expect(view.onChange).not.toHaveBeenCalled();
    available = true; fireEvent.click(redo()); expect(view.mask.get(0, 0)).toBe(false);
  });

  it('disables redo for active strokes, source failure and unsafe source previews', () => {
    const view = setup({ mask: undone() });
    view.mask.beginStroke(5, 5, 0, false); view.rerender(); expect(redo().disabled).toBe(true);
    fireEvent.click(redo()); view.mask.cancelStroke(); view.rerender(); expect(redo().disabled).toBe(false);
    fireEvent.error(screen.getByAltText('蒙版来源预览')); expect(redo().disabled).toBe(true);
    fireEvent.click(redo()); expect(view.mask.canRedo).toBe(true); expect(view.onChange).not.toHaveBeenCalled();
    view.rerender({ sourceUrl: 'https://example.test/source.png' }); expect(redo().disabled).toBe(true);
    expect(screen.queryByAltText('蒙版来源预览')).toBeNull();
  });

  it('rejects stale revision and unmounted redo callbacks without mutation or notification', () => {
    const view = setup({ mask: undone() }), oldRedo = clickHandler(redo());
    view.mask.redo(); view.mask.undo(); act(oldRedo);
    expect(view.mask.canRedo).toBe(true); expect(view.onChange).not.toHaveBeenCalled();
    view.rerender(); const afterUnmount = clickHandler(redo()); view.unmount(); act(afterUnmount);
    expect(view.mask.canRedo).toBe(true); expect(view.onChange).not.toHaveBeenCalled();
  });

  it('retires polygon preview when restoring history, so an old fill cannot branch the restored mask', () => {
    const view = setup({ mask: undone() }); fireEvent.click(button('多边形选区'));
    for (const [x, y] of [[0, 0], [4, 0], [0, 4]]) {
      fireEvent.change(screen.getByLabelText('多边形顶点 X'), { target: { value: String(x) } });
      fireEvent.change(screen.getByLabelText('多边形顶点 Y'), { target: { value: String(y) } });
      fireEvent.click(button('添加坐标顶点'));
    }
    fireEvent.click(button('预览多边形选区')); const oldFill = clickHandler(button('填充选区为黑色 REMOVE'));
    fireEvent.click(redo()); act(oldFill);
    expect(view.mask.serialize().remove_pixels).toBe(1); expect(view.onChange).toHaveBeenCalledTimes(1);
    expect(screen.queryByText(/已预览/)).toBeNull(); expect(button('填充选区为黑色 REMOVE').disabled).toBe(true);
  });

  it('does not add keyboard shortcuts or intercept IME and numeric text input', () => {
    const view = setup({ mask: undone() }), canvas = screen.getByRole('application'), input = screen.getByLabelText('矩形 X');
    for (const target of [canvas, input]) for (const event of [
      { key: 'z', ctrlKey: true }, { key: 'z', ctrlKey: true, shiftKey: true }, { key: 'y', ctrlKey: true },
      { key: 'z', metaKey: true, shiftKey: true }, { key: ' ', isComposing: true }, { key: 'Escape', isComposing: true },
    ]) expect(fireEvent.keyDown(target, event)).toBe(true);
    fireEvent.keyDown(input, { key: 'Escape' }); fireEvent.change(input, { target: { value: '12' } });
    expect((input as HTMLInputElement).value).toBe('12'); expect(view.mask.canRedo).toBe(true);
    expect(view.onChange).not.toHaveBeenCalled(); expect(canvas.getAttribute('aria-keyshortcuts')).toBe('ArrowUp ArrowDown ArrowLeft ArrowRight Space Escape');
    fireEvent.click(redo()); fireEvent.keyDown(canvas, { key: 'Escape' }); expect(view.mask.canRedo).toBe(true);
  });
});
