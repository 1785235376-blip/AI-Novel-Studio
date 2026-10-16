import { createHash } from 'node:crypto';
import { deflateSync } from 'node:zlib';
import type { StudioAsset } from './studioClient';
import type { MediaCommand, ProductionJob, ProductionPreview, ProductionRecipe, ProductionSource } from './studioProductionClient';
export const cutoutProject = 'cutout-project';
// Real bounded PNG bytes for candidate hash/size tests; jsdom does not decode images.
function fixturePng(): Uint8Array {
  function chunk(kind: string, body: Buffer) {
    const payload = Buffer.concat([Buffer.from(kind), body]); let crc = 0xffffffff;
    for (const byte of payload) { crc ^= byte; for (let bit = 0; bit < 8; bit++) crc = (crc >>> 1) ^ (crc & 1 ? 0xedb88320 : 0); }
    const header = Buffer.alloc(4), trailer = Buffer.alloc(4); header.writeUInt32BE(body.length); trailer.writeUInt32BE((crc ^ 0xffffffff) >>> 0);
    return Buffer.concat([header, payload, trailer]);
  }
  const header = Buffer.alloc(13); header.writeUInt32BE(64, 0); header.writeUInt32BE(64, 4); header[8] = 8; header[9] = 6;
  const raw = Buffer.alloc(64 * 257);
  for (let y = 0; y < 64; y++) for (let x = 0; x < 32; x++) raw.set([40, 80, 120, 255], y * 257 + 1 + x * 4);
  return new Uint8Array(Buffer.concat([Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]), chunk('IHDR', header), chunk('IDAT', deflateSync(raw, { level: 0 })), chunk('IEND', Buffer.alloc(0))]));
}
export const cutoutBytes = fixturePng();
export const cutoutHash = createHash('sha256').update(cutoutBytes).digest('hex');
export const cutoutAssets = (): StudioAsset[] => {
  const source: StudioAsset = { id: 'source', novel_id: cutoutProject, branch_id: null, version: 2, kind: 'image', media_type: 'image/png',
    filename: 'source.png', sha256: 'a'.repeat(64), size: 100, created_at: '', updated_at: '' };
  const mask = { ...source, id: 'mask', version: 1, filename: 'authored-mask.png', sha256: 'b'.repeat(64),
    manual_mask: { contract: 'manual-binary-mask/1', source_asset_id: source.id, source_version: source.version, source_sha256: source.sha256,
      width: 64, height: 64, bitplane_sha256: 'c'.repeat(64), keep_pixels: 2048, remove_pixels: 2048, mask_sha256: 'b'.repeat(64) },
    provenance: { id: 'mask', kind: 'image', deleted: false, origin: 'MANUAL_EDIT', version: 1, digest: 'b'.repeat(64), integrity: 'VERIFIED', stale: false,
      generation: null, sources: [], parents: [{ id: source.id, version: source.version, digest: source.sha256, state: 'CURRENT' }],
      license: { label: 'UNSPECIFIED', source: '', note: '' }, license_verification: 'AUTHOR_DECLARATION_NOT_LEGAL_VERIFICATION' } } as StudioAsset;
  return [source, mask];
};
export const cutoutSources = (): ProductionSource[] => cutoutAssets().map(row => ({ id: row.id, kind: 'ASSET', asset_kind: 'image', version: row.version, digest: row.sha256 }));
export const cutoutCommand = (requestId = 'cutout-request'): MediaCommand => ({ operation_id: 'm5.image.cutout', request_id: requestId, provider_id: null,
  model_id: null, prompt: '', parameters: {}, source_snapshots: cutoutSources(), allow_cloud: false, license_note: '' });
export const cutoutRecipe = (): ProductionRecipe => ({ contract: 'studio-execution-recipe/1', operation_id: 'm5.image.cutout', adapter: 'LOCAL_CPU_MASK',
  parameters: {}, output_profile: 'PNG_RGBA8_STORED_DEFLATE', mask_policy: 'WHITE_KEEP_BLACK_TRANSPARENT_ZERO', automatic_fallback: false, recipe_digest: 'd'.repeat(64) });
export const cutoutPreview = (command = cutoutCommand()): ProductionPreview => ({ contract: 'studio-production-preview/1', novel_id: cutoutProject,
  branch_id: null, operation_id: 'm5.image.cutout', request_id: command.request_id, command, preview_digest: 'e'.repeat(64), request_digest: 'f'.repeat(64),
  sources: command.source_snapshots.map(snapshot => ({ snapshot, measured: { media_type: 'image/png', extension: 'png', width: 64, height: 64, validation: 'DECODED' } })),
  provider: null, execution_recipe: cutoutRecipe(), product_acceptance: 'LOCAL_REQUIRED', execution_available: true, automatic_dispatch: false,
  output_policy: 'PRIVATE_CANDIDATE_THEN_EXPLICIT_REVIEW' });
export const cutoutJob = (status: ProductionJob['status'] = 'QUEUED', version = 1, command = cutoutCommand()): ProductionJob => {
  const rendered = ['AWAITING_REVIEW', 'APPROVED'].includes(status);
  return { contract: 'studio-production-job/1', owner: 'image', id: 'cutout-job', novel_id: cutoutProject, branch_id: null, version,
    operation_id: 'm5.image.cutout', request_id: command.request_id, status, request_digest: 'f'.repeat(64), receipt_digest: rendered ? 'd'.repeat(64) : null,
    output_candidate: rendered ? { id: 'candidate', version: 1, digest: cutoutHash, kind: 'image' } : null,
    product_acceptance: 'LOCAL_REQUIRED', automatic_replay: false, remote_compute_may_continue: false, timeline_snapshot: null,
    sources: command.source_snapshots, command, provider: null, execution_recipe: cutoutRecipe(), approved_asset_version: status === 'APPROVED' ? 2 : null,
    processing_proof: rendered ? { contract: 'cpu-binary-mask-cutout/1', width: 64, height: 64, source_sha256: 'a'.repeat(64), mask_sha256: 'b'.repeat(64),
      output_sha256: cutoutHash, output_bytes: cutoutBytes.length, keep_pixels: 2048, remove_pixels: 2048 } : null,
    created_at: '', updated_at: '' };
};
