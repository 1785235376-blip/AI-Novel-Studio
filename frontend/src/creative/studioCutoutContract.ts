import { ApiError } from '../api';
import type { StudioAsset } from './studioClient';
import { maskDimension, type StudioMaskReceipt } from './studioManualMaskContract';
import type { RecordedProductionSource } from './studioProductionClient';

export const CUTOUT_WEBP_PROFILE = 'WEBP_LOSSLESS_V1';
export const CUTOUT_WEBP_OUTPUT = 'WEBP_RGBA8_LOSSLESS_EXACT_V1';
type CutoutPixels = { width: number; height: number; source_sha256: string; mask_sha256: string;
  output_sha256: string; output_bytes: number; keep_pixels: number; remove_pixels: number };
export type CutoutProcessingProof = CutoutPixels & ({ contract: 'cpu-binary-mask-cutout/1' }
  | { contract: 'cpu-binary-mask-cutout-webp/1'; rgba_sha256: string });
const record = (value: unknown): value is Record<string, unknown> => !!value && typeof value === 'object' && !Array.isArray(value);
const hex = (value: unknown): value is string => typeof value === 'string' && /^[a-f0-9]{64}$/.test(value);
const positive = (value: unknown): value is number => typeof value === 'number' && Number.isSafeInteger(value) && value > 0;
const exact = (row: Record<string, unknown>, keys: string[]) => Object.keys(row).length === keys.length && keys.every(key => Object.hasOwn(row, key));
export function validCutoutParameters(value: unknown): value is Record<string, unknown> {
  return record(value) && (Object.keys(value).length === 0 || exact(value, ['cutout_output']) && value.cutout_output === CUTOUT_WEBP_PROFILE);
}
export function usableCutoutSource(asset: StudioAsset): boolean {
  return asset.kind === 'image' && asset.media_type === 'image/png' && !asset.deleted_at && positive(asset.version)
    && hex(asset.sha256) && positive(asset.size) && asset.size <= 8 * 1024 * 1024;
}
/** Advisory eligibility comes only from the original authored-mask marker projection. */
export function eligibleCutoutMask(asset: StudioAsset, source: StudioAsset): boolean {
  const value: unknown = asset.manual_mask, proof: unknown = asset.provenance;
  if (!usableCutoutSource(source) || !usableCutoutSource(asset) || asset.id === source.id
    || asset.novel_id !== source.novel_id || (asset.branch_id ?? null) !== (source.branch_id ?? null) || !record(value)
    || !exact(value, ['contract', 'source_asset_id', 'source_version', 'source_sha256', 'width', 'height', 'bitplane_sha256', 'keep_pixels', 'remove_pixels', 'mask_sha256'])
    || value.contract !== 'manual-binary-mask/1' || value.source_asset_id !== source.id || value.source_version !== source.version
    || value.source_sha256 !== source.sha256 || value.mask_sha256 !== asset.sha256 || !hex(value.bitplane_sha256)
    || !maskDimension(value.width) || !maskDimension(value.height) || !positive(value.keep_pixels) || !positive(value.remove_pixels)
    || value.keep_pixels + value.remove_pixels !== value.width * value.height) return false;
  return record(proof) && proof.id === asset.id && proof.kind === 'image' && proof.version === asset.version && proof.digest === asset.sha256
    && proof.deleted === false && proof.origin === 'MANUAL_EDIT' && proof.integrity === 'VERIFIED' && proof.stale === false
    && proof.generation === null && Array.isArray(proof.sources) && proof.sources.length === 0 && Array.isArray(proof.parents)
    && proof.parents.length === 1 && record(proof.parents[0]) && proof.parents[0].id === source.id && proof.parents[0].version === source.version
    && proof.parents[0].digest === source.sha256 && proof.parents[0].state === 'CURRENT';
}
export function checkedCutoutProof(value: unknown, sources: RecordedProductionSource[], candidate: { digest: string } | null, profile?: unknown): CutoutProcessingProof | null {
  if (value === null && candidate === null) return null;
  const webp = profile === CUTOUT_WEBP_PROFILE;
  if (profile !== undefined && !webp || !record(value) || !exact(value, ['contract', 'width', 'height', 'source_sha256', 'mask_sha256', 'output_sha256', 'output_bytes', 'keep_pixels', 'remove_pixels', ...(webp ? ['rgba_sha256'] : [])])
    || value.contract !== (webp ? 'cpu-binary-mask-cutout-webp/1' : 'cpu-binary-mask-cutout/1') || !maskDimension(value.width) || !maskDimension(value.height)
    || value.source_sha256 !== sources[0]?.digest || value.mask_sha256 !== sources[1]?.digest || !hex(value.output_sha256)
    || candidate !== null && value.output_sha256 !== candidate.digest || !positive(value.output_bytes) || value.output_bytes > (webp ? 8 * 1024 * 1024 : 4195716)
    || (webp ? value.output_bytes < 25 || !hex(value.rgba_sha256) : value.output_bytes !== value.height * (value.width * 4 + 1) + 5 * Math.ceil(value.height * (value.width * 4 + 1) / 65535) + 63)
    || !positive(value.keep_pixels) || !positive(value.remove_pixels) || value.keep_pixels + value.remove_pixels !== value.width * value.height) {
    throw new ApiError({ status: 200, code: 'STUDIO_RESPONSE_INVALID', message: '本地抠图回执不完整，请读取原任务核对。' });
  }
  return value as CutoutProcessingProof;
}
export type { StudioMaskReceipt };
