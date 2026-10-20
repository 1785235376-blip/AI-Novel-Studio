import { ApiError } from '../api';
import type { CreativeClient } from './client';
import type { StudioClient, StudioAsset } from './studioClient';
import { checkCanvasPreviewAsset } from './canvasAssetPreviewHelpers';
import { checkedStoryboardReceipt, type StoryboardReceipt, type StoryboardShot } from './studioStoryboardContract';
import { documentInput, type CreativeDocument } from './types';
import { inspectStoryboardRaster } from './storyboardImageRaster';

export const STORYBOARD_IMAGE_BYTES = 8 * 1024 * 1024;
export const STORYBOARD_IMAGE_WINDOW = 6;
export const STORYBOARD_IMAGE_READ_TIMEOUT_MS = 30000;
export type StoryboardImageAccess = {
  projectId: string; branchId: string | null; document: CreativeDocument;
  client: Pick<CreativeClient, 'get' | 'storyboardGet'>;
  studio: Pick<StudioClient, 'asset' | 'downloadBounded'>;
  available: boolean; isCurrent: () => boolean;
  read: <T>(work: () => Promise<T>) => Promise<T>; onDenied: () => void;
};
export class StoryboardImageError extends Error {
  constructor(public readonly code: 'SOURCE_CHANGED' | 'ASSET_CHANGED' | 'UNSUPPORTED' | 'INTEGRITY' | 'TIMEOUT', message: string) { super(message); }
}
const sourceChanged = (): never => { throw new StoryboardImageError('SOURCE_CHANGED', '已保存分镜或来源已经变化，请重新读取后比较。'); };
const canonical = (value: unknown): string => JSON.stringify(value, (_key, item: unknown) =>
  item && typeof item === 'object' && !Array.isArray(item) ? Object.fromEntries(Object.entries(item).sort(([a], [b]) => a < b ? -1 : a > b ? 1 : 0)) : item);
const original = (document: CreativeDocument) => canonical([documentInput(document), document.source_documents ?? {}, document.source_evidence]);
export const storyboardImageKey = (row: StoryboardShot) => JSON.stringify(row.image_asset);
export function assertStoryboardImageCurrent(current: () => boolean, signal: AbortSignal) {
  if (signal.aborted || !current()) throw new DOMException('分镜图片读取已取消。', 'AbortError');
}
/** Network waits are bounded independently of native decoding. A late network result
 * cannot resume its abandoned operation or publish a rendition. */
async function boundedStoryboardRead<T>(access: StoryboardImageAccess, work: (signal: AbortSignal) => Promise<T>, current: () => boolean, signal: AbortSignal): Promise<T> {
  assertStoryboardImageCurrent(current, signal);
  const controller = new AbortController();
  let timeout: ReturnType<typeof setTimeout> | undefined;
  let aborted: () => void = () => undefined;
  const stopped = new Promise<never>((_resolve, reject) => {
    aborted = () => { controller.abort(); reject(new DOMException('分镜图片读取已取消。', 'AbortError')); };
    signal.addEventListener('abort', aborted, { once: true });
    timeout = setTimeout(() => { reject(new StoryboardImageError('TIMEOUT', '图片或来源读取超过 30 秒，预览已停止。请明确重新读取。')); controller.abort(); }, STORYBOARD_IMAGE_READ_TIMEOUT_MS);
  });
  try {
    const result = await Promise.race([access.read(() => work(controller.signal)), stopped]);
    assertStoryboardImageCurrent(current, signal); return result;
  } finally { if (timeout !== undefined) clearTimeout(timeout); signal.removeEventListener('abort', aborted); controller.abort(); }
}
export async function verifyStoryboardImageDocument(access: StoryboardImageAccess, current: () => boolean, signal: AbortSignal) {
  assertStoryboardImageCurrent(current, signal);
  const row = await boundedStoryboardRead(access, child => access.client.get(access.document.id, child), current, signal);
  assertStoryboardImageCurrent(current, signal);
  if (!row || row.id !== access.document.id || row.version !== access.document.version || row.mode !== 'STORYBOARD' || row.status === 'ARCHIVED') sourceChanged();
  try { if (original(row) !== original(access.document)) sourceChanged(); }
  catch (reason) { if (reason instanceof StoryboardImageError) throw reason; sourceChanged(); }
}
export async function readStoryboardImageReceipt(access: StoryboardImageAccess, current: () => boolean, signal: AbortSignal) {
  await verifyStoryboardImageDocument(access, current, signal);
  const receipt = checkedStoryboardReceipt(await boundedStoryboardRead(access, child => access.client.storyboardGet(access.document.id, child), current, signal), access.document.id);
  assertStoryboardImageCurrent(current, signal);
  if (receipt.document_snapshot.version !== access.document.version || canonical([...receipt.shots].map(row => row.shot).sort((a, b) => a.id.localeCompare(b.id)))
    !== canonical([...access.document.shots].sort((a, b) => a.id.localeCompare(b.id)))) sourceChanged();
  await verifyStoryboardImageDocument(access, current, signal);
  return receipt;
}
function exactAsset(asset: StudioAsset, row: StoryboardShot, access: StoryboardImageAccess) {
  if (!row.image_asset || asset?.novel_id !== access.projectId || (asset.branch_id ?? null) !== access.branchId) throw new StoryboardImageError('ASSET_CHANGED', '正式图片不在当前项目或分支，未显示预览。');
  try { checkCanvasPreviewAsset(asset, row.image_asset); }
  catch { throw new StoryboardImageError('ASSET_CHANGED', '正式图片版本已变化、已删除或不可预览，请在原素材面板核对。'); }
  if (asset.size > STORYBOARD_IMAGE_BYTES || !['image/png', 'image/jpeg', 'image/webp'].includes(asset.media_type)) throw new StoryboardImageError('UNSUPPORTED', '本预览只读取不超过 8 MiB 的受支持静态 PNG、JPEG、WebP。原图未改变。');
  return asset;
}
/** One ephemeral render pipeline, also across an unmount/remount while native decoding settles.
 * No task, provider, persistent cache, or alternate media owner is created. */
let rendering: Promise<unknown> = Promise.resolve();
export function serializeStoryboardImage<T>(work: () => Promise<T>): Promise<T> {
  const result = rendering.then(work, work); rendering = result.catch(() => undefined); return result;
}
export async function renderStoryboardImage(blob: Blob, dimensions: { width: number; height: number }, size: 320 | 1024,
  current: () => boolean, signal: AbortSignal): Promise<Blob> {
  if (typeof createImageBitmap !== 'function') throw new StoryboardImageError('UNSUPPORTED', '当前浏览器不能安全解码此图片，预览未打开。');
  assertStoryboardImageCurrent(current, signal);
  const bitmap = await createImageBitmap(blob);
  let canvas: HTMLCanvasElement | undefined;
  try {
    assertStoryboardImageCurrent(current, signal);
    if (bitmap.width !== dimensions.width || bitmap.height !== dimensions.height) throw new StoryboardImageError('INTEGRITY', '图片解码尺寸与已核验内容不一致，未显示预览。');
    const scale = Math.min(1, size / bitmap.width, size / bitmap.height);
    canvas = document.createElement('canvas'); canvas.width = Math.max(1, Math.floor(bitmap.width * scale)); canvas.height = Math.max(1, Math.floor(bitmap.height * scale));
    const context = canvas.getContext('2d'); if (!context) throw new StoryboardImageError('UNSUPPORTED', '当前浏览器不能创建有界图片预览。');
    context.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
    const rendered = await new Promise<Blob>((resolve, reject) => {
      const timeout = setTimeout(() => reject(new StoryboardImageError('UNSUPPORTED', '图片预览编码未完成，请稍后重新读取。')), 15000);
      try {
        canvas!.toBlob(value => { clearTimeout(timeout); if (value) resolve(value); else reject(new StoryboardImageError('UNSUPPORTED', '图片预览编码失败，原图未改变。')); }, 'image/png');
      } catch (reason) { clearTimeout(timeout); reject(reason); }
    });
    assertStoryboardImageCurrent(current, signal);
    if (!rendered.size || rendered.size > (size === 320 ? 512 * 1024 : 5 * 1024 * 1024) || rendered.type !== 'image/png') throw new StoryboardImageError('INTEGRITY', '缩放预览超出安全范围，未显示图片。');
    return rendered;
  } finally { bitmap.close(); if (canvas) { canvas.width = 0; canvas.height = 0; } }
}
/** Caller serializes this whole operation; only a bounded derived rendition escapes. */
export async function loadStoryboardImage(access: StoryboardImageAccess, receipt: StoryboardReceipt, row: StoryboardShot, size: 320 | 1024,
  current: () => boolean, signal: AbortSignal): Promise<Blob> {
  const same = receipt.shots.find(item => item.shot_id === row.shot_id);
  if (receipt.document_snapshot.id !== access.document.id || receipt.document_snapshot.version !== access.document.version || !same || !same.image_asset || canonical(same) !== canonical(row)) return sourceChanged();
  const image = same.image_asset;
  await verifyStoryboardImageDocument(access, current, signal);
  const first = exactAsset(await boundedStoryboardRead(access, child => access.studio.asset(image.asset_id, child), current, signal), same, access);
  assertStoryboardImageCurrent(current, signal);
  const blob = await boundedStoryboardRead(access, child => access.studio.downloadBounded(image.asset_id, STORYBOARD_IMAGE_BYTES, child), current, signal);
  assertStoryboardImageCurrent(current, signal);
  if (blob.size !== first.size || blob.type.toLowerCase() !== first.media_type) throw new StoryboardImageError('INTEGRITY', '图片字节数或格式与原资产不一致，未显示预览。');
  const bytes = new Uint8Array(await blob.arrayBuffer()); assertStoryboardImageCurrent(current, signal);
  if (!globalThis.crypto?.subtle) throw new StoryboardImageError('UNSUPPORTED', '当前浏览器无法核验图片内容摘要，预览已停止。');
  const digest = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', bytes)), value => value.toString(16).padStart(2, '0')).join('');
  assertStoryboardImageCurrent(current, signal);
  if (digest !== image.digest) throw new StoryboardImageError('INTEGRITY', '图片内容摘要不一致，未显示预览。');
  let dimensions: { width: number; height: number };
  try { dimensions = inspectStoryboardRaster(bytes, first.media_type); }
  catch { throw new StoryboardImageError('UNSUPPORTED', '图片不符合静态安全预览范围（每边最多 4096、总计 4,194,304 像素；动画、部分元数据和编码不支持）。没有转换或修改原图。'); }
  const rendered = await renderStoryboardImage(blob, dimensions, size, current, signal);
  const second = exactAsset(await boundedStoryboardRead(access, child => access.studio.asset(image.asset_id, child), current, signal), same, access);
  assertStoryboardImageCurrent(current, signal);
  if (second.size !== first.size || second.media_type !== first.media_type) throw new StoryboardImageError('ASSET_CHANGED', '正式图片元数据已变化，请重新读取。');
  await verifyStoryboardImageDocument(access, current, signal);
  return rendered;
}
export function storyboardImageProblem(reason: unknown): string {
  if (reason instanceof StoryboardImageError) return reason.message;
  if (reason instanceof ApiError && [401, 403].includes(reason.status)) return '当前会话无权读取此图片，预览已关闭。';
  if (reason instanceof ApiError && reason.status === 404) return '正式图片当前不可用或无权访问；这不等于没有绑定图片。';
  if (reason instanceof ApiError && reason.status === 409) return '来源版本已经变化，请重新读取原分镜与素材。';
  return '图片读取或解码失败，未显示未经核验的内容。可明确重新读取。';
}
