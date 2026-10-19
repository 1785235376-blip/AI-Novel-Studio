import type { StudioAsset, StudioClient } from './studioClient';
import type { CanvasAssetReference } from './studioCanvasViewClient';
export const CANVAS_PREVIEW_MAX_BYTES = 32 * 1024 * 1024;
const types: Record<CanvasAssetReference['kind'], string[]> = {
  image: ['image/png', 'image/jpeg', 'image/webp', 'image/gif'],
  video: ['video/mp4', 'video/webm'], audio: ['audio/wav', 'audio/x-wav', 'audio/mpeg', 'audio/flac', 'audio/x-flac', 'audio/ogg'],
};
export function checkCanvasPreviewAsset(asset: StudioAsset, reference: CanvasAssetReference): StudioAsset {
  if (asset.id !== reference.asset_id || asset.version !== reference.version || asset.sha256 !== reference.digest || asset.kind !== reference.kind || asset.deleted_at)
    throw new Error('素材版本已改变，未把新内容当作原画布绑定。');
  if (!Number.isSafeInteger(asset.size) || asset.size < 1 || asset.size > CANVAS_PREVIEW_MAX_BYTES) throw new Error('所选素材超过 32 MiB 预览上限，请在原素材面板处理。');
  if (!types[reference.kind]?.includes(asset.media_type)) throw new Error('此媒体格式不在画布安全预览范围内，请使用原素材面板。');
  return asset;
}
/** One explicitly selected original Asset; no batch preload, provider or new binary owner. */
export async function loadCanvasAssetPreview(client: Pick<StudioClient, 'asset' | 'download'>, reference: CanvasAssetReference, isCurrent: () => boolean) {
  const binding = { ...reference }, current = () => { if (!isCurrent()) throw new Error('当前画布选择已改变。'); };
  current(); const before = checkCanvasPreviewAsset(await client.asset(binding.asset_id), binding); current();
  const blob = await client.download(binding.asset_id); current();
  if (blob.size !== before.size || blob.size > CANVAS_PREVIEW_MAX_BYTES || blob.type.split(';')[0].toLowerCase() !== before.media_type) throw new Error('素材大小或媒体类型与已核对版本不一致。');
  if (!globalThis.crypto?.subtle) throw new Error('当前环境不能核对媒体摘要，预览已停止。');
  const bytes = await blob.arrayBuffer(); current();
  const digest = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', bytes)), v => v.toString(16).padStart(2, '0')).join(''); current();
  if (digest !== binding.digest) throw new Error('素材内容摘要不一致，未显示预览。');
  const asset = checkCanvasPreviewAsset(await client.asset(binding.asset_id), binding); current();
  if (asset.size !== before.size || asset.media_type !== before.media_type) throw new Error('素材元数据已改变，未显示预览。');
  return { asset, blob };
}
