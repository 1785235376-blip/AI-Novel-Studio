import { ApiError } from '../api';
import type { StudioAsset } from './studioClient';
import { maskSha256 } from './studioManualMaskContract';

export const VIDEO_REFERENCE_PREVIEW = 'studio-video-reference-preview/1' as const;
export const VIDEO_REFERENCE_ASSET = 'studio-video-reference-asset/1' as const;
export type VideoReferenceWindow = { in_ms: number; out_ms: number; sample_count: number };
export type VideoReferenceRational = { num: number; den: number };
export type VideoReferenceFrame = {
  index: number; requested_ms: number; source_frame_index: number; pts: number;
  time_ms: VideoReferenceRational; width: number; height: number; png_sha256: string; content_base64: string;
};
export type VideoReferencePreview = VideoReferenceWindow & {
  contract: typeof VIDEO_REFERENCE_PREVIEW; novel_id: string; branch_id: string | null;
  source: { id: string; version: number; sha256: string };
  media: { duration_ms: number; width: number; height: number; time_base: VideoReferenceRational; frame_count: number;
    timing_policy: 'MONOTONIC_ZERO_ORIGIN_PTS'; orientation: 'UNROTATED_SQUARE_PIXELS' };
  frames: VideoReferenceFrame[]; model_called: false; semantic_analysis: false; preview_digest: string;
};
export type VideoReferenceOrigin = VideoReferenceWindow & {
  contract: typeof VIDEO_REFERENCE_ASSET; source_asset_id: string; source_version: number; source_sha256: string;
  selected_index: number; source_frame_index: number; pts: number; time_base: VideoReferenceRational; time_ms: VideoReferenceRational;
  width: number; height: number; png_sha256: string; preview_digest: string; model_called: false; semantic_analysis: false;
};
export type VideoReferenceSaved = { asset: StudioAsset; receipt: VideoReferenceOrigin & { replayed: boolean; asset_created: boolean } };
const PNG_MAX = 512 * 1024;
function invalid(input = false): never {
  throw new ApiError({ status: input ? 422 : 200, code: input ? 'STUDIO_VIDEO_REFERENCE_INPUT_INVALID' : 'STUDIO_RESPONSE_INVALID',
    message: input ? '请选择有效视频版本、整数毫秒区间（最多 10 秒）和 1 至 8 帧。' : '视频参考的来源、时间戳或图片校验未通过，请重新明确预览；保存结果须核对素材库。' });
}
function record(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) invalid();
  return value as Record<string, unknown>;
}
function exact(value: unknown, keys: string[]): Record<string, unknown> {
  const row = record(value);
  if (Object.keys(row).length !== keys.length || keys.some(key => !Object.hasOwn(row, key))) invalid();
  return row;
}
function integer(value: unknown, min: number, max = Number.MAX_SAFE_INTEGER): number {
  if (typeof value !== 'number' || !Number.isSafeInteger(value) || value < min || value > max) invalid();
  return value;
}
function digest(value: unknown): string { if (typeof value !== 'string' || !/^[a-f0-9]{64}$/.test(value)) invalid(); return value; }
function rational(value: unknown, positive = false): VideoReferenceRational {
  const row = exact(value, ['num', 'den']), num = integer(row.num, positive ? 1 : 0), den = integer(row.den, 1);
  let a = BigInt(num), b = BigInt(den); while (b) { const next = a % b; a = b; b = next; }
  if (a !== 1n) invalid(); return { num, den };
}
/** Exact sorted JSON wire digest; the response contains integer numbers only. */
export function canonicalVideoReference(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(canonicalVideoReference).join(',')}]`;
  if (value && typeof value === 'object') return `{${Object.keys(value).sort().map(key => `${JSON.stringify(key)}:${canonicalVideoReference((value as Record<string, unknown>)[key])}`).join(',')}}`;
  return JSON.stringify(value);
}
export function checkedVideoReferenceWindow(value: VideoReferenceWindow): VideoReferenceWindow {
  if (!value || ![value.in_ms, value.out_ms, value.sample_count].every(Number.isSafeInteger)
    || value.in_ms < 0 || value.out_ms > 60000 || value.out_ms <= value.in_ms || value.out_ms - value.in_ms > 10000
    || value.sample_count < 1 || value.sample_count > 8) invalid(true);
  return { in_ms: value.in_ms, out_ms: value.out_ms, sample_count: value.sample_count };
}
export function checkedVideoReferenceSource(asset: StudioAsset): StudioAsset {
  if (!asset || asset.kind !== 'video' || asset.deleted_at || typeof asset.id !== 'string' || !asset.id.trim()
    || typeof asset.novel_id !== 'string' || !asset.novel_id.trim() || !Number.isSafeInteger(asset.version) || asset.version < 1
    || !Number.isSafeInteger(asset.size) || asset.size < 1 || asset.size > 25 * 1024 * 1024
    || typeof asset.sha256 !== 'string' || !/^[a-f0-9]{64}$/.test(asset.sha256)) invalid(true);
  return structuredClone(asset);
}
function pngBytes(frame: VideoReferenceFrame): Uint8Array {
  if (typeof frame.content_base64 !== 'string' || frame.content_base64.length > 4 * Math.ceil(PNG_MAX / 3)) invalid();
  let binary: string; try { binary = atob(frame.content_base64); } catch { invalid(); }
  if (binary.length < 45 || binary.length > PNG_MAX || btoa(binary) !== frame.content_base64) invalid();
  const bytes = Uint8Array.from(binary, char => char.charCodeAt(0)), view = new DataView(bytes.buffer);
  if ([137, 80, 78, 71, 13, 10, 26, 10].some((byte, index) => bytes[index] !== byte)
    || view.getUint32(8) !== 13 || String.fromCharCode(...bytes.slice(12, 16)) !== 'IHDR'
    || view.getUint32(16) !== frame.width || view.getUint32(20) !== frame.height
    || bytes[24] !== 8 || bytes[25] !== 2 || bytes[26] !== 0 || bytes[27] !== 0 || bytes[28] !== 0) invalid();
  return bytes;
}
export async function checkedVideoReferencePreview(value: unknown, inputAsset: StudioAsset, inputWindow: VideoReferenceWindow): Promise<VideoReferencePreview> {
  const asset = checkedVideoReferenceSource(inputAsset), window = checkedVideoReferenceWindow(inputWindow);
  // Detach before any asynchronous hashing. Callers cannot change reviewed bytes in flight.
  const detached = structuredClone(value), root = exact(detached, ['contract', 'novel_id', 'branch_id', 'source', 'in_ms', 'out_ms', 'sample_count', 'media', 'frames', 'model_called', 'semantic_analysis', 'preview_digest']);
  const source = exact(root.source, ['id', 'version', 'sha256']);
  if (root.contract !== VIDEO_REFERENCE_PREVIEW || root.novel_id !== asset.novel_id || root.branch_id !== (asset.branch_id ?? null)
    || source.id !== asset.id || source.version !== asset.version || source.sha256 !== asset.sha256
    || root.in_ms !== window.in_ms || root.out_ms !== window.out_ms || root.sample_count !== window.sample_count
    || root.model_called !== false || root.semantic_analysis !== false) invalid();
  const media = exact(root.media, ['duration_ms', 'width', 'height', 'time_base', 'frame_count', 'timing_policy', 'orientation']);
  const duration = integer(media.duration_ms, 1, 60000), width = integer(media.width, 1, 4096), height = integer(media.height, 1, 4096);
  const frameCount = integer(media.frame_count, 1, 4096), base = rational(media.time_base, true);
  if (window.out_ms > duration || media.timing_policy !== 'MONOTONIC_ZERO_ORIGIN_PTS' || media.orientation !== 'UNROTATED_SQUARE_PIXELS'
    || !Array.isArray(root.frames) || root.frames.length !== window.sample_count) invalid();
  const longest = Math.max(width, height), outputWidth = Math.max(1, Math.floor(width * Math.min(longest, 320) / longest)), outputHeight = Math.max(1, Math.floor(height * Math.min(longest, 320) / longest));
  let previous: VideoReferenceFrame | undefined;
  for (const [index, entry] of root.frames.entries()) {
    const row = exact(entry, ['index', 'requested_ms', 'source_frame_index', 'pts', 'time_ms', 'width', 'height', 'png_sha256', 'content_base64']);
    const requested = window.in_ms + Math.floor((window.out_ms - window.in_ms) * index / window.sample_count);
    if (row.index !== index || row.requested_ms !== requested) invalid();
    const sourceIndex = integer(row.source_frame_index, 0, frameCount - 1), pts = integer(row.pts, 0), time = rational(row.time_ms);
    const fw = integer(row.width, 1, Math.min(width, 320)), fh = integer(row.height, 1, Math.min(height, 320));
    // Rational comparisons avoid guessing a constant FPS or rounding timestamps into the window.
    if (BigInt(time.num) * BigInt(base.den) !== BigInt(pts) * BigInt(base.num) * 1000n * BigInt(time.den)
      || BigInt(time.num) < BigInt(requested) * BigInt(time.den) || BigInt(time.num) >= BigInt(window.out_ms) * BigInt(time.den)
      || sourceIndex === 0 && pts !== 0 || sourceIndex > 0 && pts === 0
      || previous && (pts < previous.pts || sourceIndex < previous.source_frame_index
        || (pts === previous.pts) !== (sourceIndex === previous.source_frame_index))
      || fw !== outputWidth || fh !== outputHeight) invalid();
    const frame = row as unknown as VideoReferenceFrame;
    digest(frame.png_sha256); if (await maskSha256(pngBytes(frame)) !== frame.png_sha256) invalid();
    if (previous && sourceIndex === previous.source_frame_index && (frame.png_sha256 !== previous.png_sha256 || fw !== previous.width || fh !== previous.height)) invalid();
    previous = frame;
  }
  const claimed = digest(root.preview_digest), payload = { ...root }; delete payload.preview_digest;
  if (await maskSha256(new TextEncoder().encode(canonicalVideoReference(payload))) !== claimed) invalid();
  return detached as VideoReferencePreview;
}
export function videoReferenceFrameBlob(frame: VideoReferenceFrame): Blob { return new Blob([pngBytes(frame)], { type: 'image/png' }); }
export function videoReferenceOrigin(review: VideoReferencePreview, selectedIndex: number): VideoReferenceOrigin {
  integer(selectedIndex, 0, review.frames.length - 1); const frame = review.frames[selectedIndex];
  return { contract: VIDEO_REFERENCE_ASSET, source_asset_id: review.source.id, source_version: review.source.version, source_sha256: review.source.sha256,
    in_ms: review.in_ms, out_ms: review.out_ms, sample_count: review.sample_count, selected_index: selectedIndex, source_frame_index: frame.source_frame_index,
    pts: frame.pts, time_base: { ...review.media.time_base }, time_ms: { ...frame.time_ms }, width: frame.width, height: frame.height,
    png_sha256: frame.png_sha256, preview_digest: review.preview_digest, model_called: false, semantic_analysis: false };
}
export function checkedVideoReferenceSaved(value: unknown, source: StudioAsset, review: VideoReferencePreview, selectedIndex: number): VideoReferenceSaved {
  const detached = structuredClone(value), root = exact(detached, ['asset', 'receipt']), asset = record(root.asset), expected = videoReferenceOrigin(review, selectedIndex);
  if (expected.source_asset_id !== source.id || expected.source_version !== source.version || expected.source_sha256 !== source.sha256) invalid();
  const origin = exact(asset.video_reference, Object.keys(expected)), receipt = exact(root.receipt, [...Object.keys(expected), 'replayed', 'asset_created']);
  const { replayed, asset_created, ...receiptOrigin } = receipt;
  if (canonicalVideoReference(origin) !== canonicalVideoReference(expected) || canonicalVideoReference(receiptOrigin) !== canonicalVideoReference(expected)
    || typeof replayed !== 'boolean' || typeof asset_created !== 'boolean' || replayed === asset_created) invalid();
  if (typeof asset.id !== 'string' || !asset.id.trim() || asset.id === source.id || asset.novel_id !== source.novel_id
    || (asset.branch_id ?? null) !== (source.branch_id ?? null) || asset.kind !== 'image' || asset.media_type !== 'image/png' || asset.deleted_at
    || asset.sha256 !== expected.png_sha256 || asset.source_job_id != null || asset.provider_id != null || asset.model_id != null || asset.approved_at != null
    || !Array.isArray(asset.source_asset_ids) || asset.source_asset_ids.length !== 1 || asset.source_asset_ids[0] !== source.id) invalid();
  integer(asset.version, 1); if (asset.size !== pngBytes(review.frames[selectedIndex]).byteLength) invalid();
  const provenance = record(asset.provenance);
  if (provenance.origin !== 'MANUAL_EDIT' || provenance.integrity !== 'VERIFIED' || provenance.stale !== false || provenance.generation != null
    || !Array.isArray(provenance.parents) || provenance.parents.length !== 1) invalid();
  if (provenance.producer != null) { const producer = record(provenance.producer); if (producer.provider_id != null || producer.model_id != null) invalid(); }
  if (provenance.source_task_id != null) invalid();
  const parent = record(provenance.parents[0]);
  if (parent.id !== source.id || parent.version !== source.version || parent.digest !== source.sha256 || parent.state !== 'CURRENT'
    || JSON.stringify(detached).includes('"_video_reference_origin"')) invalid();
  return detached as VideoReferenceSaved;
}
