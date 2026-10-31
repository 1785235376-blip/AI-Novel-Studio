// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { CanvasAssetPreview } from './CanvasAssetPreview';
import { loadCanvasAssetPreview } from './canvasAssetPreviewHelpers';
vi.mock('./canvasAssetPreviewHelpers', async original => ({ ...await original<typeof import('./canvasAssetPreviewHelpers')>(), loadCanvasAssetPreview: vi.fn() }));
// Keep this test about owner/selection admission; original AssetInspector tests cover its media element lifecycle.
vi.mock('../novel/AssetInspector', () => ({ AssetInspector: ({ asset }: any) => <output aria-label="preview asset">{asset.filename}</output> }));
afterEach(() => { cleanup(); vi.clearAllMocks(); });
function props() { return { reference: { asset_id: 'asset', version: 1, digest: 'a'.repeat(64), kind: 'image' as const }, owner: {}, client: {} as any, disabled: false, isCurrent: () => true, read: async <T,>(f: () => Promise<T>) => f() }; }
const result = { asset: { id: 'asset', filename: 'verified.png' } as any, blob: new Blob(['bytes']) };
it('does not preload; explicit action admits only one in-flight selected preview', async () => {
 let resolve!: (value: typeof result) => void; vi.mocked(loadCanvasAssetPreview).mockImplementation(() => new Promise(r => { resolve = r; })); render(<CanvasAssetPreview {...props()} />);
 expect(loadCanvasAssetPreview).not.toHaveBeenCalled(); const button = screen.getByText('核验并预览所选素材'); fireEvent.click(button); fireEvent.click(button); expect(loadCanvasAssetPreview).toHaveBeenCalledTimes(1);
 await act(async () => resolve(result)); expect(screen.getByLabelText('preview asset').textContent).toBe('verified.png');
});
it.each(['owner', 'disabled ABA', 'selection', 'unmount', 'current'])('discards a late private preview after %s', async mode => {
 let resolve!: (value: typeof result) => void; vi.mocked(loadCanvasAssetPreview).mockImplementation(() => new Promise(r => { resolve = r; })); const p = props(); let current = true; p.isCurrent = () => current; const view = render(<CanvasAssetPreview {...p} />); fireEvent.click(screen.getByText('核验并预览所选素材'));
 if (mode === 'owner') view.rerender(<CanvasAssetPreview {...p} owner={{}} />);
 if (mode === 'disabled ABA') { view.rerender(<CanvasAssetPreview {...p} disabled />); view.rerender(<CanvasAssetPreview {...p} />); }
 if (mode === 'selection') view.rerender(<CanvasAssetPreview {...p} reference={{ ...p.reference, asset_id: 'other' }} />);
 if (mode === 'unmount') view.unmount(); if (mode === 'current') current = false;
 await act(async () => resolve(result)); expect(screen.queryByLabelText('preview asset')).toBeNull();
});
it('clears an already visible preview when its owner changes', async () => { vi.mocked(loadCanvasAssetPreview).mockResolvedValue(result); const p = props(), view = render(<CanvasAssetPreview {...p} />); fireEvent.click(screen.getByText('核验并预览所选素材')); await waitFor(() => expect(screen.getByLabelText('preview asset')).toBeTruthy()); view.rerender(<CanvasAssetPreview {...p} owner={{}} />); expect(screen.queryByLabelText('preview asset')).toBeNull(); });
