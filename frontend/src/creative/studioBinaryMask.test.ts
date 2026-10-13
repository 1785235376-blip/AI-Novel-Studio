import { describe, expect, it } from 'vitest';
import { BinaryMaskDraft } from './studioBinaryMask';

const decoded = (value: string) => Uint8Array.from(atob(value), char => char.charCodeAt(0));

describe('bounded packed binary mask draft', () => {
  it.each([[0, 64], [63, 64], [65, 64], [64, 63], [64, 65], [1032, 64], [64, 1032], [NaN, 64], [Infinity, 64], [64.5, 64]])('rejects invalid dimensions %s × %s before allocation', (width, height) => {
    expect(() => new BinaryMaskDraft(width, height)).toThrow();
  });

  it('starts entirely KEEP with one packed bit per pixel at both size bounds', () => {
    for (const size of [64, 1024]) {
      const mask = new BinaryMaskDraft(size, size);
      expect(mask.width).toBe(size); expect(mask.height).toBe(size);
      expect(mask.snapshot()).toEqual(new Uint8Array(size * size / 8).fill(255));
      expect(mask.canUndo).toBe(false); expect(mask.activeStroke).toBe(false);
    }
  });

  it('serializes row-major MSB-first bits and exact counts without image encoding', () => {
    const mask = new BinaryMaskDraft(64, 64);
    mask.paint(0, 0, 0, false); mask.paint(7, 0, 0, false); mask.paint(0, 1, 0, false);
    const result = mask.serialize(), bits = decoded(result.bitplane_base64);
    expect(bits).toHaveLength(512); expect(bits[0]).toBe(0b01111110); expect(bits[8]).toBe(0b01111111);
    expect(result.keep_pixels).toBe(4093); expect(result.remove_pixels).toBe(3);
    expect(bits).toEqual(mask.snapshot());
  });

  it('allows single-color editing but rejects either single color at serialization', () => {
    const mask = new BinaryMaskDraft(64, 64);
    expect(() => mask.serialize()).toThrow(/KEEP.*REMOVE/);
    mask.clear(false); expect(() => mask.serialize()).toThrow(/KEEP.*REMOVE/);
    mask.paint(63, 63, 0, true); expect(mask.serialize().keep_pixels).toBe(1);
  });

  it('returns detached snapshots which cannot mutate the draft', () => {
    const mask = new BinaryMaskDraft(64, 64), snapshot = mask.snapshot(); snapshot.fill(0);
    expect(mask.get(0, 0)).toBe(true); expect(mask.snapshot()[0]).toBe(255);
  });

  it('paints a hard circular brush including radius zero and edge clipping', () => {
    const mask = new BinaryMaskDraft(64, 64); mask.paint(8, 8, 1, false);
    expect(mask.serialize().remove_pixels).toBe(5);
    expect(mask.get(7, 7)).toBe(true); expect(mask.get(7, 8)).toBe(false);
    mask.paint(0, 0, 1, false); expect(mask.serialize().remove_pixels).toBe(8);
    mask.paint(63, 63, 0, false); expect(mask.get(63, 63)).toBe(false);
    mask.paint(8, 8, 1, true); expect(mask.serialize().remove_pixels).toBe(4);
  });

  it.each([[-1, 0, 0], [64, 0, 0], [0, 64, 0], [0.5, 0, 0], [0, NaN, 0], [0, 0, -1], [0, 0, 33], [0, 0, 1.5], [0, 0, Infinity]])('rejects invalid brush %j without altering draft or history', (x, y, radius) => {
    const mask = new BinaryMaskDraft(64, 64), before = mask.snapshot();
    expect(() => mask.paint(x, y, radius, false)).toThrow();
    expect(mask.snapshot()).toEqual(before); expect(mask.canUndo).toBe(false);
  });

  it('interpolates a sparse longest diagonal with a bounded continuous one-pixel stroke', () => {
    const mask = new BinaryMaskDraft(1024, 1024);
    mask.beginStroke(0, 0, 0, false); mask.moveStroke(1023, 1023);
    expect(mask.activeStroke).toBe(true); expect(() => mask.serialize()).toThrow(/笔画/);
    expect(mask.commitStroke()).toBe(true); expect(mask.serialize().remove_pixels).toBe(1024);
    for (let index = 0; index < 1024; index++) expect(mask.get(index, index)).toBe(false);
    expect(mask.undo()).toBe(true); expect(mask.get(1023, 1023)).toBe(true);
    expect(mask.canUndo).toBe(false);
  });

  it('rolls back canceled strokes without consuming an undo slot', () => {
    const mask = new BinaryMaskDraft(64, 64); mask.paint(0, 0, 0, false);
    const before = mask.snapshot(); mask.beginStroke(10, 10, 2, false); mask.moveStroke(50, 50);
    expect(mask.cancelStroke()).toBe(true); expect(mask.snapshot()).toEqual(before);
    expect(mask.activeStroke).toBe(false); expect(mask.undo()).toBe(true); expect(mask.canUndo).toBe(false);
    expect(mask.cancelStroke()).toBe(false);
  });

  it('does not commit invalid move coordinates or permit overlapping edits', () => {
    const mask = new BinaryMaskDraft(64, 64); mask.beginStroke(1, 1, 0, false);
    const before = mask.snapshot();
    expect(() => mask.moveStroke(Number.MAX_SAFE_INTEGER, 1)).toThrow();
    expect(mask.snapshot()).toEqual(before);
    expect(() => mask.beginStroke(1, 1, 1, false)).toThrow();
    expect(() => mask.rectangle(1, 1, 1, 1, false)).toThrow();
    expect(() => mask.clear(false)).toThrow(); expect(() => mask.undo()).toThrow();
    mask.cancelStroke(); expect(mask.activeStroke).toBe(false);
  });

  it('keeps exactly the latest sixteen packed undo states', () => {
    const mask = new BinaryMaskDraft(64, 64);
    for (let x = 0; x < 20; x++) mask.paint(x, 0, 0, false);
    for (let count = 0; count < 16; count++) expect(mask.undo()).toBe(true);
    expect(mask.undo()).toBe(false); expect(mask.serialize().remove_pixels).toBe(4);
    expect(mask.get(3, 0)).toBe(false); expect(mask.get(4, 0)).toBe(true);
  });

  it('does not add history for no-op brush, rectangle, clear or stroke operations', () => {
    const mask = new BinaryMaskDraft(64, 64);
    expect(mask.paint(1, 1, 2, true)).toBe(false); expect(mask.rectangle(1, 1, 2, 2, true)).toBe(false);
    expect(mask.clear(true)).toBe(false); mask.beginStroke(0, 0, 0, true); mask.moveStroke(63, 63);
    expect(mask.commitStroke()).toBe(false); expect(mask.revision).toBe(0); expect(mask.canUndo).toBe(false);
  });

  it('applies exact rectangular pixels with one undo entry', () => {
    const mask = new BinaryMaskDraft(64, 64); mask.rectangle(61, 62, 3, 2, false);
    expect(mask.serialize().remove_pixels).toBe(6); expect(mask.get(60, 62)).toBe(true);
    expect(mask.get(63, 63)).toBe(false); expect(mask.get(61, 61)).toBe(true);
    mask.undo(); expect(mask.get(63, 63)).toBe(true); expect(mask.canUndo).toBe(false);
  });

  it.each([[63, 63, 2, 1], [0, 0, 65, 1], [-1, 0, 1, 1], [0, 0, 0, 1], [0, 0, 1, -1], [0, 0, 1.5, 1], [0, 0, Infinity, 1]])('rejects an invalid rectangle %j without silently clipping', (x, y, width, height) => {
    const mask = new BinaryMaskDraft(64, 64), before = mask.snapshot();
    expect(() => mask.rectangle(x, y, width, height, false)).toThrow();
    expect(mask.snapshot()).toEqual(before); expect(mask.canUndo).toBe(false);
  });

  it('releases state and permanently rejects mutation or serialization after disposal', () => {
    const mask = new BinaryMaskDraft(64, 64); mask.paint(0, 0, 0, false); mask.beginStroke(5, 5, 2, false);
    mask.dispose(); mask.dispose(); expect(mask.activeStroke).toBe(false); expect(mask.canUndo).toBe(false);
    expect(() => mask.paint(0, 0, 0, false)).toThrow(); expect(() => mask.serialize()).toThrow();
    expect(() => mask.snapshot()).toThrow(); expect(() => mask.get(0, 0)).toThrow();
  });
});
