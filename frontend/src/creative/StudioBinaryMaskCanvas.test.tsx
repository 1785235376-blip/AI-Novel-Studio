// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { StudioBinaryMaskCanvas } from './StudioBinaryMaskCanvas';
import { BinaryMaskDraft } from './studioBinaryMask';

class TestPointerEvent extends MouseEvent {
  readonly pointerId: number;
  constructor(type: string, options: PointerEventInit = {}) { super(type, options); this.pointerId = options.pointerId ?? 1; }
}
const putImageData = vi.fn();
beforeEach(() => {
  vi.stubGlobal('PointerEvent', TestPointerEvent);
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue({
    createImageData: (width: number, height: number) => ({ data: new Uint8ClampedArray(width * height * 4), width, height }), putImageData,
  } as unknown as CanvasRenderingContext2D);
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); putImageData.mockClear(); });
function setup(extra: Partial<Parameters<typeof StudioBinaryMaskCanvas>[0]> = {}) {
  const mask = extra.mask ?? new BinaryMaskDraft(64, 64), onChange = vi.fn();
  const props = { mask, sourceUrl: 'blob:verified-source', readOnly: false, isCurrent: () => true, onChange, ...extra };
  const result = render(<StudioBinaryMaskCanvas {...props} />);
  const canvas = screen.getByRole('application', { name: '二值蒙版绘图区' });
  vi.spyOn(canvas, 'getBoundingClientRect').mockReturnValue({ left: 0, top: 0, width: 64, height: 64, right: 64, bottom: 64, x: 0, y: 0, toJSON: () => ({}) });
  fireEvent.change(screen.getByLabelText('笔刷半径（像素）'), { target: { value: '0' } });
  return { ...result, props, mask, onChange, canvas, rerender: (next: Partial<typeof props>) => result.rerender(<StudioBinaryMaskCanvas {...props} {...next} />) };
}
const down = (canvas: Element, x: number, y: number, pointerId = 1) => fireEvent.pointerDown(canvas, { button: 0, pointerId, clientX: x, clientY: y });
const move = (canvas: Element, x: number, y: number, pointerId = 1) => fireEvent.pointerMove(canvas, { pointerId, clientX: x, clientY: y });
const up = (canvas: Element, x: number, y: number, pointerId = 1) => fireEvent.pointerUp(canvas, { pointerId, clientX: x, clientY: y });

describe('binary mask display and accessible editing', () => {
  it('keeps the blob source outside the display-only canvas and renders binary pixel values', () => {
    const { mask } = setup();
    expect(screen.getByAltText('蒙版来源预览').getAttribute('src')).toBe('blob:verified-source');
    expect(putImageData).toHaveBeenCalled();
    const pixels = putImageData.mock.lastCall![0].data as Uint8ClampedArray;
    expect(Array.from(pixels.slice(0, 4))).toEqual([255, 255, 255, 144]);
    expect(mask.canUndo).toBe(false);
  });

  it.each(['https://example.test/image.png', 'data:image/png;base64,AAAA', 'javascript:alert(1)', ''])('never loads or edits with a non-blob source %s', sourceUrl => {
    const { canvas, mask, onChange } = setup({ sourceUrl });
    expect(screen.queryByAltText('蒙版来源预览')).toBeNull();
    down(canvas, 0, 0); up(canvas, 0, 0); fireEvent.keyDown(canvas, { key: ' ' });
    expect(mask.get(0, 0)).toBe(true); expect(onChange).not.toHaveBeenCalled();
  });

  it('commits a sparse continuous gesture as one undo entry', () => {
    const { canvas, mask, onChange } = setup(); down(canvas, 0, 0); move(canvas, 20, 0);
    expect(mask.activeStroke).toBe(true); expect(mask.get(10, 0)).toBe(false);
    up(canvas, 21, 0); expect(mask.activeStroke).toBe(false); expect(mask.serialize().remove_pixels).toBe(22);
    expect(onChange).toHaveBeenCalledTimes(2);
    fireEvent.click(screen.getByRole('button', { name: '撤销蒙版编辑' }));
    expect(mask.get(0, 0)).toBe(true); expect(mask.canUndo).toBe(false);
  });

  it.each(['pointerCancel', 'lostPointerCapture'] as const)('rolls back %s and ignores late pointer-up', eventName => {
    const { canvas, mask } = setup(); down(canvas, 2, 2); move(canvas, 20, 2);
    fireEvent[eventName](canvas, { pointerId: 1 }); up(canvas, 20, 2);
    expect(mask.activeStroke).toBe(false); expect(mask.get(2, 2)).toBe(true); expect(mask.canUndo).toBe(false);
  });

  it('ignores unrelated pointers and bounds captured movement to the mask edge', () => {
    const { canvas, mask } = setup(); down(canvas, 0, 0); move(canvas, 30, 0, 2); up(canvas, 30, 0, 2);
    expect(mask.get(30, 0)).toBe(true); expect(mask.activeStroke).toBe(true);
    move(canvas, 1e9, 0); up(canvas, 1e9, 0);
    expect(mask.serialize().remove_pixels).toBe(64); expect(mask.get(63, 0)).toBe(false);
  });

  it('bounds radius-32 interpolation even with extreme scaled pointer coordinates', () => {
    const { canvas, mask } = setup();
    vi.mocked(canvas.getBoundingClientRect).mockReturnValue({ left: 0, top: 0, width: 128, height: 128, right: 128, bottom: 128, x: 0, y: 0, toJSON: () => ({}) });
    fireEvent.change(screen.getByLabelText('笔刷半径（像素）'), { target: { value: '32' } });
    down(canvas, 0, 0); move(canvas, 1e308, 0); up(canvas, 1e308, 0);
    expect(mask.serialize().remove_pixels).toBe(64 * 33);
    expect(mask.get(63, 32)).toBe(false); expect(mask.get(63, 33)).toBe(true);
  });

  it('maps CSS-scaled pointer positions to original pixels', () => {
    const { canvas, mask } = setup();
    vi.mocked(canvas.getBoundingClientRect).mockReturnValue({ left: 16, top: 32, width: 128, height: 128, right: 144, bottom: 160, x: 16, y: 32, toJSON: () => ({}) });
    down(canvas, 142, 158); up(canvas, 142, 158);
    expect(mask.get(63, 63)).toBe(false); expect(mask.serialize().remove_pixels).toBe(1);
  });

  it('supports keyboard arrows, space painting, KEEP erasing and Escape undo', () => {
    const { canvas, mask } = setup(); fireEvent.keyDown(canvas, { key: 'ArrowRight' }); fireEvent.keyDown(canvas, { key: 'ArrowDown' });
    fireEvent.keyDown(canvas, { key: ' ' }); expect(mask.get(1, 1)).toBe(false);
    fireEvent.click(screen.getByRole('button', { name: '白色 KEEP · 保留' }));
    fireEvent.keyDown(canvas, { key: ' ' }); expect(mask.get(1, 1)).toBe(true);
    fireEvent.keyDown(canvas, { key: 'Escape' }); expect(mask.get(1, 1)).toBe(false);
    fireEvent.keyDown(canvas, { key: 'Escape' }); expect(mask.get(1, 1)).toBe(true);
  });

  it('uses Escape to cancel the current gesture without undoing an earlier committed edit', () => {
    const { canvas, mask } = setup(); fireEvent.keyDown(canvas, { key: ' ' }); down(canvas, 20, 20);
    fireEvent.keyDown(canvas, { key: 'Escape' }); up(canvas, 20, 20);
    expect(mask.get(0, 0)).toBe(false); expect(mask.get(20, 20)).toBe(true); expect(mask.canUndo).toBe(true);
  });

  it('requires an explicit exact rectangle action and rejects out-of-bounds values without clipping', () => {
    const { mask } = setup();
    for (const [label, value] of [['矩形 X', '63'], ['矩形 Y', '62'], ['矩形宽度', '2'], ['矩形高度', '2']]) {
      fireEvent.change(screen.getByLabelText(label), { target: { value } });
    }
    expect(mask.canUndo).toBe(false); fireEvent.click(screen.getByRole('button', { name: '应用精确矩形' }));
    expect(screen.getByRole('alert').textContent).toContain('不会自动裁剪'); expect(mask.get(63, 62)).toBe(true);
    fireEvent.change(screen.getByLabelText('矩形宽度'), { target: { value: '1' } });
    fireEvent.click(screen.getByRole('button', { name: '应用精确矩形' }));
    expect(mask.serialize().remove_pixels).toBe(2); expect(mask.get(62, 62)).toBe(true);
  });

  it('rejects oversized numeric strings including leading zeros without truncation', () => {
    const { mask, canvas } = setup();
    fireEvent.change(screen.getByLabelText('矩形宽度'), { target: { value: `${'0'.repeat(10000)}1` } });
    fireEvent.click(screen.getByRole('button', { name: '应用精确矩形' }));
    expect(screen.getByRole('alert').textContent).toContain('最多 4 位'); expect(mask.canUndo).toBe(false);
    fireEvent.change(screen.getByLabelText('笔刷半径（像素）'), { target: { value: '0'.repeat(10000) } });
    down(canvas, 0, 0); up(canvas, 0, 0);
    expect(mask.get(0, 0)).toBe(true); expect(mask.activeStroke).toBe(false);
  });

  it('fences mutation and rolls back when current ownership expires without a render', () => {
    let current = true;
    const { canvas, mask, onChange } = setup({ isCurrent: () => current }); down(canvas, 4, 4); current = false;
    move(canvas, 30, 30); up(canvas, 30, 30); fireEvent.keyDown(canvas, { key: ' ' });
    expect(mask.activeStroke).toBe(false); expect(mask.get(4, 4)).toBe(true); expect(mask.canUndo).toBe(false);
    expect(onChange).toHaveBeenCalledTimes(1);
    expect(screen.queryByAltText('蒙版来源预览')).toBeNull();
  });

  it('hides blob source pixels after a mounted ownership transition and uses the shared focus ring', () => {
    const { canvas, rerender } = setup(); fireEvent.focus(canvas);
    expect((canvas as HTMLCanvasElement).style.outline).toBe('var(--border-strong)');
    expect((canvas as HTMLCanvasElement).style.boxShadow).toBe('var(--focus-ring)');
    rerender({ isCurrent: () => false }); expect(screen.queryByAltText('蒙版来源预览')).toBeNull();
    fireEvent.blur(canvas); expect((canvas as HTMLCanvasElement).style.boxShadow).toBe('');
  });

  it('rolls back on read-only transition, source change, blur and unmount', () => {
    const { canvas, mask, rerender, unmount } = setup(); down(canvas, 1, 1); rerender({ readOnly: true });
    expect(mask.get(1, 1)).toBe(true); expect(mask.activeStroke).toBe(false);
    rerender({ readOnly: false }); down(canvas, 2, 2); rerender({ sourceUrl: 'blob:new-source' });
    expect(mask.get(2, 2)).toBe(true); expect(mask.activeStroke).toBe(false);
    down(canvas, 3, 3); fireEvent.blur(window); expect(mask.get(3, 3)).toBe(true);
    down(canvas, 4, 4); unmount(); expect(mask.get(4, 4)).toBe(true); expect(mask.activeStroke).toBe(false);
  });

  it('never edits read-only drafts from either input route or rectangle controls', () => {
    const { canvas, mask, onChange } = setup({ readOnly: true }); down(canvas, 0, 0); up(canvas, 0, 0);
    fireEvent.keyDown(canvas, { key: ' ' }); fireEvent.click(screen.getByRole('button', { name: '应用精确矩形' }));
    expect(mask.canUndo).toBe(false); expect(onChange).not.toHaveBeenCalled();
  });

  it('rolls back a gesture if the source preview fails', () => {
    const { canvas, mask } = setup(); down(canvas, 5, 5); fireEvent.error(screen.getByAltText('蒙版来源预览'));
    up(canvas, 5, 5); expect(mask.get(5, 5)).toBe(true); expect(mask.activeStroke).toBe(false);
    expect(screen.getByRole('alert').textContent).toContain('来源预览');
  });
});
