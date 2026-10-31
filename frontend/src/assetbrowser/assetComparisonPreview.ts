import { CANVAS_PREVIEW_MAX_BYTES } from '../creative/canvasAssetPreviewHelpers';
import type { AssetBrowserAsset, AssetBrowserClient } from './assetBrowserTypes';

export type AssetComparisonDownload = (asset: AssetBrowserAsset, isCurrent: () => boolean) => Promise<Blob>;

// Same bounded media formats as the existing canvas preview; never render HTML/SVG.
const mediaTypes: Record<string, readonly string[]> = {
  image: ['image/png', 'image/jpeg', 'image/webp', 'image/gif'],
  video: ['video/mp4', 'video/webm'],
  audio: ['audio/wav', 'audio/x-wav', 'audio/mpeg', 'audio/flac', 'audio/x-flac', 'audio/ogg'],
};

/** Read-only consumer of the original Asset owner. No version substitution or prefetch. */
export async function loadAssetComparisonPreview(
  client: Pick<AssetBrowserClient, 'readAsset' | 'downloadAsset'>,
  expected: AssetBrowserAsset,
  isCurrent: () => boolean,
): Promise<Blob> {
  const binding = { ...expected };
  const current = () => { if (!isCurrent()) throw new Error('stale-comparison'); };
  const check = (value: AssetBrowserAsset) => {
    if (value.deleted || value.id !== binding.id || value.version !== binding.version
        || value.digest !== binding.digest || value.kind !== binding.kind
        || value.media_type !== binding.media_type || value.size !== binding.size
        || value.branch_id !== binding.branch_id)
      throw new Error('changed-comparison');
  };
  current();
  if (binding.deleted || !Number.isSafeInteger(binding.version) || (binding.version ?? 0) < 1
      || !/^[a-f0-9]{64}$/.test(binding.digest) || !Number.isSafeInteger(binding.size)
      || binding.size < 1 || binding.size > CANVAS_PREVIEW_MAX_BYTES
      || !binding.media_kind || binding.kind !== binding.media_kind
      || !mediaTypes[binding.media_kind]?.includes(binding.media_type) || !client.downloadAsset)
    throw new Error('unsupported-comparison-preview');
  const before = await client.readAsset(binding.id); current(); check(before);
  const blob = await client.downloadAsset(binding.id); current();
  if (blob.size !== binding.size || blob.type.split(';')[0].toLowerCase() !== binding.media_type)
    throw new Error('comparison-bytes-mismatch');
  if (!globalThis.crypto?.subtle) throw new Error('comparison-digest-unavailable');
  const bytes = await blob.arrayBuffer(); current();
  const digest = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', bytes)),
    value => value.toString(16).padStart(2, '0')).join(''); current();
  if (digest !== binding.digest) throw new Error('comparison-digest-mismatch');
  const after = await client.readAsset(binding.id); current(); check(after);
  return blob;
}
