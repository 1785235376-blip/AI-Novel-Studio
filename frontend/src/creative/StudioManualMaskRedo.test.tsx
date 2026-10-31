// @vitest-environment jsdom
import { act, cleanup, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { webcrypto } from 'node:crypto';
import { Blob as NodeBlob } from 'node:buffer';
import { useStudio } from '../store';
import { useStudioManualMask, type StudioManualMaskProps } from './useStudioManualMask';
import { maskSha256 } from './studioManualMaskContract';

let props: StudioManualMaskProps;
beforeEach(async () => {
  vi.stubGlobal('crypto', webcrypto);
  // This verifies the original controller, not native image decode or a backend.
  vi.stubGlobal('createImageBitmap', vi.fn(async () => ({ width: 64, height: 64, close: vi.fn() })));
  Object.defineProperty(URL, 'createObjectURL', { configurable: true, value: vi.fn(() => 'blob:redo-owner-source') });
  Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: vi.fn() });
  useStudio.setState({ novelId: 'redo-project', sessionToken: '', actor: undefined, scope: undefined });
  const bytes = new Uint8Array(57), data = new DataView(bytes.buffer);
  bytes.set([137, 80, 78, 71, 13, 10, 26, 10]); data.setUint32(8, 13); bytes.set([73, 72, 68, 82], 12);
  data.setUint32(16, 64); data.setUint32(20, 64); bytes[24] = 8; bytes[25] = 6;
  bytes.set([73, 68, 65, 84], 37); bytes.set([73, 69, 78, 68], 49);
  const asset = { id: 'redo-source', novel_id: 'redo-project', branch_id: null, version: 1, kind: 'image', media_type: 'image/png',
    sha256: await maskSha256(bytes), filename: 'source.png', size: bytes.length, created_at: '', updated_at: '' };
  props = { asset, client: { asset: vi.fn(async () => ({ ...asset })), download: vi.fn(async () => new NodeBlob([bytes]) as unknown as Blob), createMask: vi.fn() },
    canMutate: true, busy: false, isBusy: () => false, isCurrent: () => useStudio.getState().novelId === 'redo-project',
    read: async work => work(), mutate: async work => work(), onDirtyChange: vi.fn(), onUnavailable: vi.fn(), onSaved: vi.fn() };
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });
async function load() {
  const view = renderHook((value: StudioManualMaskProps) => useStudioManualMask(value), { initialProps: props });
  await act(async () => view.result.current.load());
  const mask = view.result.current.editor!.mask;
  act(() => { mask.paint(0, 0, 0, false); view.result.current.changed(); view.result.current.agree(true); });
  return { view, mask };
}

describe('redo remains within the original mask owner', () => {
  it('requires fresh save consent even when redo restores exactly the previously agreed pixels', async () => {
    const { view, mask } = await load(), agreed = mask.serialize(); expect(view.result.current.canSave).toBe(true);
    act(() => { mask.undo(); view.result.current.changed(); mask.redo(); view.result.current.changed(); });
    expect(mask.serialize()).toEqual(agreed); expect(view.result.current.consent).toBe(false); expect(view.result.current.canSave).toBe(false);
    await act(async () => view.result.current.save());
    expect(props.client.createMask).not.toHaveBeenCalled(); expect(props.onSaved).not.toHaveBeenCalled();
    expect(props.client.asset).toHaveBeenCalledTimes(2); expect(props.client.download).toHaveBeenCalledTimes(1);
    act(() => view.result.current.agree(true)); expect(view.result.current.canSave).toBe(true);
  });

  it.each(['discard', 'source', 'project', 'permission', 'unmount'] as const)('disposes both history directions on %s without writing an asset', async transition => {
    const { view, mask } = await load();
    act(() => { mask.paint(1, 0, 0, false); mask.undo(); view.result.current.changed(); });
    expect(mask.canUndo).toBe(true); expect(mask.canRedo).toBe(true);
    if (transition === 'discard') act(() => view.result.current.discard());
    if (transition === 'source') view.rerender({ ...props, asset: { ...props.asset, version: 2 } });
    if (transition === 'project') act(() => useStudio.setState({ novelId: 'another-project' }));
    if (transition === 'permission') view.rerender({ ...props, canMutate: false });
    if (transition === 'unmount') view.unmount();
    expect(mask.canUndo).toBe(false); expect(mask.canRedo).toBe(false); expect(() => mask.redo()).toThrow(/释放/);
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:redo-owner-source');
    expect(props.client.createMask).not.toHaveBeenCalled(); expect(props.onSaved).not.toHaveBeenCalled();
  });
});
