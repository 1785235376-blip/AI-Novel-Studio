import { Blob as NodeBlob } from 'node:buffer';
import { createHash, webcrypto } from 'node:crypto';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { CANVAS_PREVIEW_MAX_BYTES } from '../creative/canvasAssetPreviewHelpers';
import { decodeRow } from './assetBrowserFixtures';
import { loadAssetComparisonPreview } from './assetComparisonPreview';
import type { AssetBrowserAsset } from './assetBrowserTypes';

const bytes = 'verified original owner bytes';
const digest = createHash('sha256').update(bytes).digest('hex');
const asset = () => decodeRow({ size: bytes.length, sha256: digest });
const blob = (value = bytes, type = 'image/png') => new NodeBlob([value], { type }) as Blob;
const fixture = () => ({ readAsset: vi.fn(async () => asset()), downloadAsset: vi.fn(async () => blob()) });
beforeEach(() => { vi.stubGlobal('crypto', webcrypto); });
afterEach(() => { vi.unstubAllGlobals(); });

describe('comparison preview bound to original owner snapshot', () => {
  it('checks metadata before and after digest-verified bytes', async () => {
    const client = fixture();
    expect(await loadAssetComparisonPreview(client, asset(), () => true)).toBeInstanceOf(NodeBlob);
    expect(client.readAsset.mock.calls).toHaveLength(2);
    expect(client.downloadAsset).toHaveBeenCalledTimes(1); expect(client.downloadAsset).toHaveBeenCalledWith('asset-a');
  });
  it.each([
    { version: null }, { digest: '' }, { deleted: true }, { size: 0 }, { size: CANVAS_PREVIEW_MAX_BYTES + 1 },
    { media_type: 'image/svg+xml' }, { kind: 'audio' }, { media_kind: null },
  ] satisfies Partial<AssetBrowserAsset>[] )('rejects unsupported snapshots before any reads: %j', async patch => {
    const client = fixture();
    await expect(loadAssetComparisonPreview(client, { ...asset(), ...patch }, () => true)).rejects.toThrow();
    expect(client.readAsset).not.toHaveBeenCalled(); expect(client.downloadAsset).not.toHaveBeenCalled();
  });
  it.each([{ id: 'asset-foreign' }, { branch_id: 'other-branch' }, { version: 4 }, { deleted: true }, { digest: 'c'.repeat(64) }])(
    'rejects substituted owner metadata before bytes: %j', async patch => {
      const client = fixture(); client.readAsset.mockResolvedValue({ ...asset(), ...patch });
      await expect(loadAssetComparisonPreview(client, asset(), () => true)).rejects.toThrow();
      expect(client.downloadAsset).not.toHaveBeenCalled();
    });
  it.each([blob('short'), blob(bytes, 'text/html'), blob('x'.repeat(bytes.length))])('rejects wrong byte size/type/digest', async payload => {
    const client = fixture(); client.downloadAsset.mockResolvedValue(payload);
    await expect(loadAssetComparisonPreview(client, asset(), () => true)).rejects.toThrow();
    expect(client.readAsset).toHaveBeenCalledTimes(1);
  });
  it('rejects metadata changed after the download', async () => {
    const client = fixture(); client.readAsset.mockResolvedValueOnce(asset()).mockResolvedValueOnce({ ...asset(), version: 4 });
    await expect(loadAssetComparisonPreview(client, asset(), () => true)).rejects.toThrow('changed-comparison');
  });
  it('does not advance to bytes after authority changes during metadata read', async () => {
    const client = fixture(); let current = true;
    client.readAsset.mockImplementation(async () => { current = false; return asset(); });
    await expect(loadAssetComparisonPreview(client, asset(), () => current)).rejects.toThrow('stale-comparison');
    expect(client.downloadAsset).not.toHaveBeenCalled();
  });
  it('does not advance to the final metadata read after authority changes during bytes', async () => {
    const client = fixture(); let current = true;
    client.downloadAsset.mockImplementation(async () => { current = false; return blob(); });
    await expect(loadAssetComparisonPreview(client, asset(), () => current)).rejects.toThrow('stale-comparison');
    expect(client.readAsset).toHaveBeenCalledTimes(1);
  });
  it('fails closed when digest verification is unavailable', async () => {
    vi.stubGlobal('crypto', {});
    await expect(loadAssetComparisonPreview(fixture(), asset(), () => true)).rejects.toThrow('comparison-digest-unavailable');
  });
});
