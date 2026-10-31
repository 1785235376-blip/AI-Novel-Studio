import { createHash } from 'node:crypto';
import { deflateSync } from 'node:zlib';
import type { StudioAsset } from './studioClient';
import type { VideoReferenceOrigin, VideoReferencePreview, VideoReferenceSaved, VideoReferenceWindow } from './studioVideoReferenceContract';
const sha = (bytes: Uint8Array | string) => createHash('sha256').update(bytes).digest('hex');
function sorted(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(sorted);
  if (value && typeof value === 'object') return Object.fromEntries(Object.entries(value).sort(([a], [b]) => a < b ? -1 : a > b ? 1 : 0).map(([key, entry]) => [key, sorted(entry)]));
  return value;
}
export function resealVideoPreview(value: VideoReferencePreview): VideoReferencePreview {
  const { preview_digest: _digest, ...body } = value;
  return { ...body, preview_digest: sha(JSON.stringify(sorted(body))) };
}
function chunk(name: string, bytes: Buffer) {
  const content = Buffer.concat([Buffer.from(name), bytes]), length = Buffer.alloc(4), crc = Buffer.alloc(4); length.writeUInt32BE(bytes.length);
  let sum = 0xffffffff; for (const byte of content) { sum ^= byte; for (let i = 0; i < 8; i++) sum = (sum >>> 1) ^ ((sum & 1) ? 0xedb88320 : 0); } crc.writeUInt32BE((sum ^ 0xffffffff) >>> 0);
  return Buffer.concat([length, content, crc]);
}
function png(index: number) {
  const header = Buffer.alloc(13); header.writeUInt32BE(16); header.writeUInt32BE(8, 4); header[8] = 8; header[9] = 2;
  const pixels = Buffer.alloc((16 * 3 + 1) * 8, index * 24); for (let y = 0; y < 8; y++) pixels[y * 49] = 0;
  return Buffer.concat([Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]), chunk('IHDR', header), chunk('IDAT', deflateSync(pixels)), chunk('IEND', Buffer.alloc(0))]);
}
export const videoReferenceSource: StudioAsset = {
  id: 'source-video', novel_id: 'project', branch_id: null, filename: 'sample.mp4', kind: 'video', media_type: 'video/mp4',
  size: 2048, sha256: 'a'.repeat(64), version: 1, created_at: '2026-10-18T00:00:00Z', updated_at: '2026-10-18T00:00:00Z',
};
export function videoReferencePreview(source = videoReferenceSource, window: VideoReferenceWindow = { in_ms: 0, out_ms: 1000, sample_count: 4 }): VideoReferencePreview {
  const frames = Array.from({ length: window.sample_count }, (_, index) => {
    const requested = window.in_ms + Math.floor((window.out_ms - window.in_ms) * index / window.sample_count), sourceIndex = Math.ceil(requested / 250), bytes = png(sourceIndex);
    return { index, requested_ms: requested, source_frame_index: sourceIndex, pts: sourceIndex, time_ms: { num: sourceIndex * 250, den: 1 }, width: 16, height: 8, png_sha256: sha(bytes), content_base64: bytes.toString('base64') };
  });
  return resealVideoPreview({ contract: 'studio-video-reference-preview/1', novel_id: source.novel_id, branch_id: source.branch_id ?? null,
    source: { id: source.id, version: source.version, sha256: source.sha256 }, ...window,
    media: { duration_ms: 2000, width: 16, height: 8, time_base: { num: 1, den: 4 }, frame_count: 8, timing_policy: 'MONOTONIC_ZERO_ORIGIN_PTS', orientation: 'UNROTATED_SQUARE_PIXELS' },
    frames, model_called: false, semantic_analysis: false, preview_digest: '' });
}
export function videoReferenceSaved(source = videoReferenceSource, review = videoReferencePreview(source), selectedIndex = 0): VideoReferenceSaved {
  const frame = review.frames[selectedIndex];
  const origin: VideoReferenceOrigin = { contract: 'studio-video-reference-asset/1', source_asset_id: source.id, source_version: source.version, source_sha256: source.sha256,
    in_ms: review.in_ms, out_ms: review.out_ms, sample_count: review.sample_count, selected_index: selectedIndex,
    source_frame_index: frame.source_frame_index, pts: frame.pts, time_base: { ...review.media.time_base }, time_ms: { ...frame.time_ms }, width: frame.width, height: frame.height,
    png_sha256: frame.png_sha256, preview_digest: review.preview_digest, model_called: false, semantic_analysis: false };
  const asset = { id: 'reference-image', novel_id: source.novel_id, branch_id: source.branch_id ?? null, filename: 'reference.png', kind: 'image', media_type: 'image/png',
    size: Buffer.from(frame.content_base64, 'base64').length, sha256: frame.png_sha256, version: 1, created_at: source.created_at, updated_at: source.updated_at,
    source_asset_ids: [source.id], video_reference: origin, provenance: { origin: 'MANUAL_EDIT', version: 1, digest: frame.png_sha256, integrity: 'VERIFIED',
      license: { label: 'UNSPECIFIED', source: '', note: '' }, license_verification: 'AUTHOR_DECLARATION_NOT_LEGAL_VERIFICATION',
      parents: [{ id: source.id, version: source.version, digest: source.sha256, state: 'CURRENT' }], sources: [], stale: false } };
  return { asset, receipt: { ...origin, replayed: false, asset_created: true } };
}
