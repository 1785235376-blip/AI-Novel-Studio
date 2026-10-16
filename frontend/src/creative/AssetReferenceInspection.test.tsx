// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { AssetReferenceInspection } from './AssetReferenceInspection';
import type { StudioReference } from './studioClient';
const pin = { kind: 'ASSET' as const, id: 'original', version: 2, digest: 'a'.repeat(64) };
const row = { ...pin, label: '原图', deleted: false };
const response = (items: StudioReference[] = [row]) => ({ items, read_only: true as const, content_copied: false as const });
function setup() {
  const client = { references: vi.fn(async () => response()) }, onOpenAsset = vi.fn();
  const props = { expected: pin, client, onOpenAsset, busy: false, isCurrent: () => true, read: async <T,>(operation: () => Promise<T>) => operation() };
  return { ...render(<AssetReferenceInspection {...props} />), props, client, onOpenAsset };
}
const inspect = () => fireEvent.click(screen.getByRole('button', { name: '核对原来源版本' }));
const open = () => screen.getByRole('button', { name: '打开核对的原资产' }) as HTMLButtonElement;
afterEach(cleanup);
describe('saved asset reference inspection', () => {
  it('reads only explicitly, compares exact pin and opens only on a second explicit action', async () => {
    const { client, onOpenAsset } = setup(); expect(client.references).not.toHaveBeenCalled(); expect(open().disabled).toBe(true);
    inspect(); await waitFor(() => expect(open().disabled).toBe(false));
    expect(onOpenAsset).not.toHaveBeenCalled(); fireEvent.click(open()); expect(onOpenAsset).toHaveBeenCalledWith(pin);
  });
  it.each([{ version: 3 }, { digest: 'b'.repeat(64) }])('does not upgrade changed pins %j', async change => {
    const { client, onOpenAsset } = setup(); client.references.mockResolvedValue(response([{ ...row, ...change }]));
    inspect(); await screen.findByText(/来源版本或摘要已变化/); expect(open().disabled).toBe(true); expect(onOpenAsset).not.toHaveBeenCalled();
    expect(screen.getByText(/关联时 ASSET/).textContent).toContain(pin.digest);
  });
  it.each([{ items: [] }, { items: [{ ...row, deleted: true }] }, { items: [row, row] }])('blocks missing, deleted and ambiguous source rows', async ({ items }) => {
    const { client } = setup(); client.references.mockResolvedValue(response(items)); inspect(); await screen.findByText(/来源缺失/); expect(open().disabled).toBe(true);
  });
  it('clears prior current metadata and permission to open after a failed reread', async () => {
    const { client } = setup(); inspect(); await waitFor(() => expect(open().disabled).toBe(false));
    client.references.mockRejectedValue(new Error('private failure')); inspect(); await screen.findByText(/来源核对失败/);
    expect(screen.queryByText(/当前可读 原图/)).toBeNull(); expect(screen.queryByText(/private failure/)).toBeNull(); expect(open().disabled).toBe(true);
  });
  it('aborts and rejects a delayed read across client ABA', async () => {
    const { props, client, rerender } = setup(); let finish!: (value: ReturnType<typeof response>) => void;
    client.references.mockImplementation(() => new Promise(resolve => { finish = resolve; })); inspect();
    rerender(<AssetReferenceInspection {...props} client={{ references: vi.fn() }} />); rerender(<AssetReferenceInspection {...props} />);
    await act(async () => finish(response())); expect(screen.queryByText(/当前可读 原图/)).toBeNull(); expect(open().disabled).toBe(true);
  });
  it('invalidates exact inspection across busy ABA and target version changes', async () => {
    const { props, rerender } = setup(); inspect(); await waitFor(() => expect(open().disabled).toBe(false));
    rerender(<AssetReferenceInspection {...props} busy />); rerender(<AssetReferenceInspection {...props} />); expect(open().disabled).toBe(true);
    inspect(); await waitFor(() => expect(open().disabled).toBe(false)); rerender(<AssetReferenceInspection {...props} expected={{ ...pin, version: 3 }} />); expect(open().disabled).toBe(true);
  });
  it('keeps chapter inspection metadata-only', async () => {
    const { props, client, rerender, onOpenAsset } = setup(); rerender(<AssetReferenceInspection {...props} expected={{ ...pin, kind: 'CHAPTER' }} />);
    client.references.mockResolvedValue(response([{ ...row, kind: 'CHAPTER' }])); inspect(); await screen.findByText(/当前可读 原图/);
    expect(screen.queryByRole('button', { name: '打开核对的原资产' })).toBeNull(); expect(onOpenAsset).not.toHaveBeenCalled();
  });
  it('ignores a late result after original owner is no longer current', async () => {
    const { props, client, rerender } = setup(); let active = true, finish!: (value: ReturnType<typeof response>) => void;
    rerender(<AssetReferenceInspection {...props} isCurrent={() => active} />);
    client.references.mockImplementation(() => new Promise(resolve => { finish = resolve; })); inspect(); active = false;
    await act(async () => finish(response())); expect(screen.queryByText(/当前可读 原图/)).toBeNull(); expect(open().disabled).toBe(true);
  });
  it('rejects a retained exact-open handler after a failed reread and busy ABA', async () => {
    const { props, client, rerender, onOpenAsset } = setup(); inspect(); await waitFor(() => expect(open().disabled).toBe(false));
    const button = open(), reactProps = Object.keys(button).find(key => key.startsWith('__reactProps$'))!;
    const retained = (button as unknown as Record<string, { onClick: () => void }>)[reactProps].onClick;
    client.references.mockRejectedValue(new Error('offline')); inspect(); await screen.findByText(/来源核对失败/);
    act(() => retained()); expect(onOpenAsset).not.toHaveBeenCalled();
    client.references.mockResolvedValue(response()); inspect(); await waitFor(() => expect(open().disabled).toBe(false));
    rerender(<AssetReferenceInspection {...props} busy />); rerender(<AssetReferenceInspection {...props} />);
    act(() => retained()); expect(onOpenAsset).not.toHaveBeenCalled();
  });

});
