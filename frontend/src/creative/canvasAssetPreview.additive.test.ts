import { webcrypto } from 'node:crypto';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { CANVAS_PREVIEW_MAX_BYTES, loadCanvasAssetPreview } from './canvasAssetPreview';
import type { CanvasAssetReference } from './studioCanvasViewClient';
beforeEach(() => vi.stubGlobal('crypto', webcrypto)); afterEach(() => vi.unstubAllGlobals());
async function fixture() { const bytes = new Uint8Array([137, 80, 78, 71]), digest = Buffer.from(await webcrypto.subtle.digest('SHA-256', bytes)).toString('hex');
 const reference: CanvasAssetReference = { asset_id: 'asset', version: 1, digest, kind: 'image' };
 const asset: any = { id: 'asset', version: 1, sha256: digest, kind: 'image', size: 4, media_type: 'image/png' };
 const client = { asset: vi.fn().mockResolvedValue(asset), download: vi.fn().mockResolvedValue(new Blob([bytes], { type: 'image/png' })) }; return { reference, asset, client }; }
it('verifies actual bytes between two original metadata reads without extra binary owners', async () => { const { reference, asset, client } = await fixture(); const result = await loadCanvasAssetPreview(client, reference, () => true); expect(result.asset).toEqual(asset); expect(result.blob.size).toBe(4); expect(client.asset).toHaveBeenCalledTimes(2); expect(client.download).toHaveBeenCalledTimes(1); });
it.each(['version', 'deleted', 'oversize', 'svg'])('refuses %s before any download', async mode => { const { reference, asset, client } = await fixture(); if (mode === 'version') asset.version = 2; if (mode === 'deleted') asset.deleted_at = 'deleted'; if (mode === 'oversize') asset.size = CANVAS_PREVIEW_MAX_BYTES + 1; if (mode === 'svg') asset.media_type = 'image/svg+xml'; await expect(loadCanvasAssetPreview(client, reference, () => true)).rejects.toThrow(); expect(client.download).not.toHaveBeenCalled(); });
it.each(['digest', 'mime', 'size', 'late version', 'authority'])('refuses %s after download without exposing a verified result', async mode => { const { reference, asset, client } = await fixture(); let current = true;
 if (mode === 'digest') client.download.mockResolvedValue(new Blob([new Uint8Array([0, 0, 0, 0])], { type: 'image/png' }));
 if (mode === 'mime') client.download.mockResolvedValue(new Blob([new Uint8Array([137, 80, 78, 71])], { type: 'image/svg+xml' }));
 if (mode === 'size') client.download.mockResolvedValue(new Blob([new Uint8Array([0])], { type: 'image/png' }));
 if (mode === 'late version') client.asset.mockResolvedValueOnce(asset).mockResolvedValue({ ...asset, version: 2 });
 if (mode === 'authority') client.download.mockImplementation(async () => { current = false; return new Blob([new Uint8Array([137, 80, 78, 71])], { type: 'image/png' }); });
 await expect(loadCanvasAssetPreview(client, reference, () => current)).rejects.toThrow();
});
