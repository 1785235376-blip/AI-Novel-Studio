import { ApiError } from '../api';
import type { StudioAsset } from './studioClient';

export type StudioMaskInput = {
  contract: 'manual-binary-mask/1'; source_version: number; source_sha256: string;
  width: number; height: number; bitplane_base64: string; idempotency_key: string;
};
export type StudioMaskReceipt = {
  contract: 'manual-binary-mask/1'; source_asset_id: string; source_version: number; source_sha256: string;
  width: number; height: number; bitplane_sha256: string; keep_pixels: number; remove_pixels: number; mask_sha256: string;
};
export type StudioMaskResult = { asset: StudioAsset; receipt: StudioMaskReceipt };
const inputKeys = ['contract', 'source_version', 'source_sha256', 'width', 'height', 'bitplane_base64', 'idempotency_key'];
const receiptKeys = ['contract', 'source_asset_id', 'source_version', 'source_sha256', 'width', 'height', 'bitplane_sha256', 'keep_pixels', 'remove_pixels', 'mask_sha256'];
const own = (row: Record<string, unknown>, keys: string[]) => keys.every(key => Object.prototype.hasOwnProperty.call(row, key));
const exact = (row: Record<string, unknown>, keys: string[]) => own(row, keys) && Object.keys(row).length === keys.length;
const record = (value: unknown): value is Record<string, unknown> => !!value && typeof value === 'object' && !Array.isArray(value);
const positive = (value: unknown): value is number => typeof value === 'number' && Number.isSafeInteger(value) && value > 0;
const digest = (value: unknown): value is string => typeof value === 'string' && /^[a-f0-9]{64}$/.test(value);
export function maskDimension(value: unknown): value is number { return positive(value) && value >= 64 && value <= 1024 && value % 8 === 0; }
function invalid(input: boolean): never {
  throw new ApiError({ status: input ? 400 : 200, code: input ? 'STUDIO_MASK_INPUT_INVALID' : 'STUDIO_RESPONSE_INVALID',
    message: input ? '遮罩输入无效，请核对尺寸与黑白像素。' : '遮罩保存回执不完整，结果尚待核对。' });
}
export async function maskSha256(bytes: Uint8Array): Promise<string> {
  const hash = await crypto.subtle.digest('SHA-256', new Uint8Array(bytes));
  return Array.from(new Uint8Array(hash), byte => byte.toString(16).padStart(2, '0')).join('');
}
export function checkedMaskInput(value: unknown): { body: StudioMaskInput; bytes: Uint8Array; keep: number } {
  if (!record(value) || !exact(value, inputKeys) || value.contract !== 'manual-binary-mask/1'
    || !positive(value.source_version) || !digest(value.source_sha256) || !maskDimension(value.width) || !maskDimension(value.height)
    || typeof value.idempotency_key !== 'string' || !/^[A-Za-z0-9][A-Za-z0-9_-]{0,119}$/.test(value.idempotency_key) || typeof value.bitplane_base64 !== 'string'
    || value.bitplane_base64.length > 174764 || !/^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/.test(value.bitplane_base64)) invalid(true);
  let binary: string;
  try { binary = atob(value.bitplane_base64); } catch { invalid(true); }
  if (binary.length !== value.width * value.height / 8 || btoa(binary) !== value.bitplane_base64) invalid(true);
  const bytes = Uint8Array.from(binary, char => char.charCodeAt(0));
  let keep = 0;
  for (let byte of bytes) { while (byte) { keep += byte & 1; byte >>>= 1; } }
  if (keep === 0 || keep === value.width * value.height) invalid(true);
  return { body: Object.fromEntries(inputKeys.map(key => [key, value[key]])) as StudioMaskInput, bytes, keep };
}

/** Closed only for the new mask response; ordinary Asset decoding is unchanged. */
export function checkedMaskResult(value: unknown, sourceId: string, body: StudioMaskInput, bitplaneSha: string, keep: number,
  projectId: string, branch: string | null): StudioMaskResult {
  if (!record(value) || !exact(value, ['asset', 'receipt']) || !record(value.asset) || !record(value.receipt)) invalid(false);
  const asset = value.asset, receipt = value.receipt;
  if (!exact(receipt, receiptKeys) || receipt.contract !== body.contract || receipt.source_asset_id !== sourceId
    || receipt.source_version !== body.source_version || receipt.source_sha256 !== body.source_sha256
    || receipt.width !== body.width || receipt.height !== body.height || receipt.bitplane_sha256 !== bitplaneSha
    || receipt.keep_pixels !== keep || receipt.remove_pixels !== body.width * body.height - keep || !digest(receipt.mask_sha256)) invalid(false);
  if (!own(asset, ['id', 'novel_id', 'branch_id', 'kind', 'media_type', 'version', 'sha256', 'filename', 'size', 'created_at', 'updated_at', 'provenance'])
    || typeof asset.id !== 'string' || !asset.id.trim() || asset.id.length > 240 || asset.id === sourceId
    || asset.novel_id !== projectId || (asset.branch_id ?? null) !== branch || asset.kind !== 'image' || asset.media_type !== 'image/png'
    || !positive(asset.version) || asset.sha256 !== receipt.mask_sha256 || asset.deleted_at || !record(asset.provenance)
    || typeof asset.filename !== 'string' || !asset.filename.trim() || asset.filename.length > 255 || /[\u0000-\u001f\u007f]/.test(asset.filename)
    || !positive(asset.size) || asset.size > 8 * 1024 * 1024 || typeof asset.created_at !== 'string' || asset.created_at.length > 64
    || typeof asset.updated_at !== 'string' || asset.updated_at.length > 64) invalid(false);
  const proof = asset.provenance;
  if (!own(proof, ['id', 'kind', 'deleted', 'origin', 'version', 'digest', 'integrity', 'stale', 'parents', 'sources', 'generation'])
    || proof.id !== asset.id || proof.kind !== 'image' || proof.deleted !== false || proof.origin !== 'MANUAL_EDIT'
    || proof.version !== asset.version || proof.digest !== asset.sha256 || proof.integrity !== 'VERIFIED' || proof.stale !== false
    || !Array.isArray(proof.sources) || proof.sources.length || proof.generation !== null
    || !Array.isArray(proof.parents) || proof.parents.length !== 1 || !record(proof.parents[0])) invalid(false);
  if (!own(proof, ['license', 'license_verification']) || !record(proof.license)
    || !own(proof.license, ['label', 'source', 'note']) || !['label', 'source', 'note'].every(key => typeof (proof.license as Record<string, unknown>)[key] === 'string')
    || proof.license_verification !== 'AUTHOR_DECLARATION_NOT_LEGAL_VERIFICATION') invalid(false);
  const parent = proof.parents[0];
  if (!own(parent, ['id', 'version', 'digest', 'state']) || parent.id !== sourceId || parent.version !== body.source_version
    || parent.digest !== body.source_sha256 || parent.state !== 'CURRENT') invalid(false);
  if (record(proof.producer) && (proof.producer.provider_id != null || proof.producer.model_id != null)) invalid(false);
  return value as unknown as StudioMaskResult;
}
