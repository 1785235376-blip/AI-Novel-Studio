import { describe, expect, it } from 'vitest';
import { BINARY_MASK_UNDO_LIMIT, BinaryMaskDraft } from './studioBinaryMask';

const triangle = [{ x: 8, y: 8 }, { x: 16, y: 8 }, { x: 8, y: 16 }];
// Inspect retained buffers only to verify the memory bound and zero-on-release contract.
const retained = (mask: BinaryMaskDraft) => mask as unknown as { bits: Uint8Array; history: Uint8Array[]; future: Uint8Array[]; stroke: { before: Uint8Array } | null };

describe('bounded, bit-exact local binary mask redo', () => {
  it('starts without redo and empty undo/redo do not advance revision', () => {
    const mask = new BinaryMaskDraft(64, 64);
    expect(mask.canRedo).toBe(false); expect(mask.redo()).toBe(false); expect(mask.undo()).toBe(false);
    expect(mask.revision).toBe(0);
  });

  it.each([64, 1024])('round-trips mixed edits at %i pixels without copying or changing packed bits', size => {
    const mask = new BinaryMaskDraft(size, size), states = [mask.snapshot()];
    const edits = [
      () => { mask.beginStroke(0, 0, 0, false); mask.moveStroke(size - 1, size - 1); mask.commitStroke(); },
      () => mask.rectangle(size - 4, 0, 4, 3, false),
      () => mask.polygon(triangle, false),
      () => mask.clear(false),
      () => mask.paint(size - 1, size - 1, 0, true),
      () => mask.clear(true),
    ];
    for (const edit of edits) { edit(); states.push(mask.snapshot()); }
    let revision = mask.revision;
    for (let index = states.length - 2; index >= 0; index--) {
      const current = retained(mask).bits;
      expect(mask.undo()).toBe(true); expect(mask.revision).toBe(++revision);
      expect(retained(mask).future.at(-1)).toBe(current); expect(mask.snapshot()).toEqual(states[index]);
    }
    expect(mask.canUndo).toBe(false); expect(mask.undo()).toBe(false); expect(mask.revision).toBe(revision);
    for (let index = 1; index < states.length; index++) {
      const current = retained(mask).bits;
      expect(mask.redo()).toBe(true); expect(mask.revision).toBe(++revision);
      expect(retained(mask).history.at(-1)).toBe(current); expect(mask.snapshot()).toEqual(states[index]);
    }
    expect(mask.canRedo).toBe(false); expect(mask.redo()).toBe(false); expect(mask.revision).toBe(revision);
  });

  it('preserves the original sixteen-state total through repeated undo/redo and new edits', () => {
    const mask = new BinaryMaskDraft(1024, 1024), initial = mask.snapshot();
    const bound = () => {
      const { history, future, bits } = retained(mask), buffers = [...history, ...future];
      expect(buffers.length).toBeLessThanOrEqual(BINARY_MASK_UNDO_LIMIT);
      expect(new Set([...buffers, bits]).size).toBe(buffers.length + 1);
      expect(buffers.reduce((total, state) => total + state.byteLength, 0)).toBeLessThanOrEqual(2 * 1024 * 1024);
    };
    mask.paint(0, 0, 0, false); const evicted = retained(mask).history[0];
    for (let x = 1; x < 20; x++) { mask.paint(x, 0, 0, false); bound(); }
    expect(evicted.every(byte => byte === 0)).toBe(true);
    for (let cycle = 0; cycle < 3; cycle++) {
      for (let count = 0; count < BINARY_MASK_UNDO_LIMIT; count++) { expect(mask.undo()).toBe(true); bound(); }
      expect(mask.undo()).toBe(false); expect(mask.serialize().remove_pixels).toBe(4);
      for (let count = 0; count < BINARY_MASK_UNDO_LIMIT; count++) { expect(mask.redo()).toBe(true); bound(); }
      expect(mask.redo()).toBe(false); expect(mask.serialize().remove_pixels).toBe(20);
    }
    mask.undo(); mask.undo(); mask.paint(40, 0, 0, false); bound();
    expect(mask.canRedo).toBe(false); expect(mask.serialize().remove_pixels).toBe(19);
    expect(initial.every(byte => byte === 255)).toBe(true);
  });

  it.each(['brush', 'stroke', 'rectangle', 'polygon', 'clear'] as const)('clears and zeroes abandoned redo only when %s commits changed pixels', kind => {
    const mask = new BinaryMaskDraft(64, 64);
    mask.paint(0, 0, 0, false); mask.paint(1, 0, 0, false); mask.undo(); mask.undo();
    const abandoned = [...retained(mask).future];
    if (kind === 'brush') mask.paint(63, 63, 0, false);
    if (kind === 'stroke') { mask.beginStroke(20, 20, 0, false); mask.moveStroke(22, 20); mask.commitStroke(); }
    if (kind === 'rectangle') mask.rectangle(20, 20, 2, 2, false);
    if (kind === 'polygon') mask.polygon(triangle, false);
    if (kind === 'clear') mask.clear(false);
    const branched = mask.snapshot();
    expect(mask.canRedo).toBe(false); expect(mask.redo()).toBe(false);
    expect(abandoned.every(state => state.every(byte => byte === 0))).toBe(true);
    mask.undo(); expect(mask.snapshot().every(byte => byte === 255)).toBe(true);
    mask.redo(); expect(mask.snapshot()).toEqual(branched);
  });

  it('retains redo after no-op edits, preview, rejected input and cancelled strokes', () => {
    const mask = new BinaryMaskDraft(64, 64); mask.paint(1, 1, 0, false);
    const edited = mask.snapshot(); mask.undo(); const revision = mask.revision;
    expect(mask.paint(1, 1, 0, true)).toBe(false); expect(mask.rectangle(1, 1, 2, 2, true)).toBe(false);
    expect(mask.polygon(triangle, true)).toBe(false); expect(mask.clear(true)).toBe(false);
    mask.previewPolygon(triangle); expect(() => mask.rectangle(63, 63, 2, 2, false)).toThrow();
    expect(mask.revision).toBe(revision); expect(mask.canRedo).toBe(true);
    mask.beginStroke(20, 20, 0, false); mask.moveStroke(22, 20);
    expect(mask.canRedo).toBe(true); expect(() => mask.redo()).toThrow(/笔画/);
    mask.cancelStroke(); expect(mask.canRedo).toBe(true); mask.redo(); expect(mask.snapshot()).toEqual(edited);
  });

  it('keeps serialization detached and exact after redo and continues to require mixed pixels', () => {
    const mask = new BinaryMaskDraft(64, 64); mask.rectangle(0, 0, 7, 3, false);
    const serialized = mask.serialize(), snapshot = mask.snapshot(); mask.undo();
    expect(() => mask.serialize()).toThrow(/KEEP.*REMOVE/); mask.redo();
    snapshot.fill(0); expect(mask.serialize()).toEqual(serialized);
    mask.clear(false); mask.undo(); mask.redo(); expect(() => mask.serialize()).toThrow(/KEEP.*REMOVE/);
  });

  it('disposal zeroes current, undo, redo and pending stroke buffers and permanently rejects redo', () => {
    const mask = new BinaryMaskDraft(64, 64); mask.paint(0, 0, 0, false); mask.paint(1, 0, 0, false); mask.undo();
    mask.beginStroke(2, 0, 0, false);
    const state = retained(mask), buffers = [state.bits, ...state.history, ...state.future, state.stroke!.before];
    mask.dispose(); mask.dispose();
    expect(buffers.every(buffer => buffer.every(byte => byte === 0))).toBe(true);
    expect(mask.canUndo).toBe(false); expect(mask.canRedo).toBe(false); expect(mask.activeStroke).toBe(false);
    expect(() => mask.redo()).toThrow(/释放/); expect(() => mask.undo()).toThrow(/释放/);
    expect(retained(mask).history).toHaveLength(0); expect(retained(mask).future).toHaveLength(0);
  });
});
