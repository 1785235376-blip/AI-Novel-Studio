import { describe, expect, it } from 'vitest';
import { BINARY_MASK_UNDO_LIMIT, BinaryMaskDraft, type BinaryMaskPoint } from './studioBinaryMask';

const points = (...pairs: [number, number][]): BinaryMaskPoint[] => pairs.map(([x, y]) => ({ x, y }));
const concave = points([8, 8], [40, 8], [40, 24], [24, 24], [24, 40], [8, 40]);

describe('bounded simple polygon binary mask selection', () => {
  it('previews without mutation, fills a concave polygon and undoes the whole apply once', () => {
    const mask = new BinaryMaskDraft(64, 64), before = mask.snapshot();
    const preview = mask.previewPolygon(concave);
    expect(preview.selected_pixels).toBe(768);
    expect(Object.isFrozen(preview.vertices)).toBe(true);
    expect(Object.isFrozen(preview.vertices[0])).toBe(true);
    expect(mask.snapshot()).toEqual(before); expect(mask.revision).toBe(0); expect(mask.canUndo).toBe(false);
    expect(mask.polygon(preview.vertices, false)).toBe(true);
    expect(mask.revision).toBe(1);
    expect(mask.serialize()).toMatchObject({ keep_pixels: 3328, remove_pixels: 768 });
    for (let y = 0; y < 64; y++) for (let x = 0; x < 64; x++) {
      expect(mask.get(x, y)).toBe(!(x >= 8 && x < 40 && y >= 8 && y < 24 || x >= 8 && x < 24 && y >= 24 && y < 40));
    }
    expect(mask.undo()).toBe(true); expect(mask.snapshot()).toEqual(before); expect(mask.canUndo).toBe(false);
  });

  it('includes pixel centers on diagonal boundaries and is independent of winding', () => {
    const triangle = points([0, 0], [4, 0], [0, 4]), forward = new BinaryMaskDraft(64, 64), reverse = new BinaryMaskDraft(64, 64);
    forward.polygon(triangle, false); reverse.polygon([...triangle].reverse(), false);
    expect(forward.serialize().remove_pixels).toBe(10); expect(reverse.snapshot()).toEqual(forward.snapshot());
    for (let y = 0; y < 5; y++) for (let x = 0; x < 5; x++) expect(forward.get(x, y)).toBe(x + y > 3);
  });

  it('matches an integer cross-product oracle for slanted triangular edges', () => {
    for (const [width, height] of [[31, 17], [49, 63], [9, 15], [63, 21]]) {
      const mask = new BinaryMaskDraft(64, 64);
      mask.polygon(points([0, 0], [width, 0], [0, height]), false);
      for (let y = 0; y < 64; y++) for (let x = 0; x < 64; x++) {
        expect(mask.get(x, y), `${width},${height}:${x},${y}`).toBe((2 * x + 1) * height + (2 * y + 1) * width > 2 * width * height);
      }
    }
  });

  it('admits outer grid corners at original maximum dimensions, but still requires both colors to save', () => {
    const mask = new BinaryMaskDraft(1024, 1024), full = points([0, 0], [1024, 0], [1024, 1024], [0, 1024]);
    expect(mask.previewPolygon(full).selected_pixels).toBe(1024 ** 2);
    mask.polygon(full, false); expect(() => mask.serialize()).toThrow(/KEEP.*REMOVE/);
    mask.polygon(points([1023, 1023], [1024, 1023], [1024, 1024], [1023, 1024]), true);
    expect(mask.serialize()).toMatchObject({ keep_pixels: 1, remove_pixels: 1024 ** 2 - 1 });
    expect(mask.snapshot()).toHaveLength(1024 ** 2 / 8);
  });

  it.each([
    points([0, 0], [3, 3]),
    points([0, 0], [5, 5], [0, 5], [5, 0]),
    points([0, 0], [4, 0], [4, 4], [2, 0], [0, 4]),
    points([0, 0], [4, 0], [0, 4], [0, 0]),
    points([0, 0], [4, 0], [2, 0], [2, 4], [0, 4]),
    points([0, 0], [2, 2], [4, 4]),
    points([-1, 0], [4, 0], [0, 4]),
    points([0, 0], [65, 0], [0, 4]),
    points([0, 0], [4, 0], [0, 64.5]),
    points([0, 0], [NaN, 0], [0, 4]),
    Array.from({ length: 33 }, (_, x) => ({ x, y: x % 2 })),
  ].map(polygon => [polygon]))('rejects invalid/degenerate/outside polygon %# without changing packed pixels or history', polygon => {
    const mask = new BinaryMaskDraft(64, 64), before = mask.snapshot();
    expect(() => mask.previewPolygon(polygon)).toThrow(); expect(() => mask.polygon(polygon, false)).toThrow();
    expect(mask.snapshot()).toEqual(before); expect(mask.canUndo).toBe(false); expect(mask.revision).toBe(0);
  });

  it('keeps the original history capacity, treats repeated/no-op fills as no undo, and retires disposed drafts', () => {
    const mask = new BinaryMaskDraft(64, 64), one = points([0, 0], [1, 0], [1, 1], [0, 1]);
    expect(mask.polygon(one, true)).toBe(false); expect(mask.canUndo).toBe(false);
    for (let i = 0; i < 20; i++) mask.polygon(one, i % 2 !== 0);
    const revision = mask.revision; expect(mask.polygon(one, true)).toBe(false); expect(mask.revision).toBe(revision);
    let undos = 0; while (mask.undo()) undos++;
    expect(undos).toBe(BINARY_MASK_UNDO_LIMIT);
    mask.beginStroke(4, 4, 0, false);
    expect(() => mask.previewPolygon(one)).toThrow(); expect(() => mask.polygon(one, false)).toThrow();
    mask.cancelStroke(); expect(() => mask.polygon(one, 0 as unknown as boolean)).toThrow();
    mask.dispose(); expect(() => mask.previewPolygon(one)).toThrow(); expect(() => mask.polygon(one, false)).toThrow();
  });
});
