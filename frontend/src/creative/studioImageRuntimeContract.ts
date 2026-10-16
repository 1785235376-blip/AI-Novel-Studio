import { ApiError } from '../api';
import type { ProductionSource, RecordedProductionSource } from './studioProductionClient';

export const IMAGE_REFERENCE_PURPOSES = ['character', 'outfit', 'environment', 'style', 'composition'] as const;
export type ImageReferencePurpose = typeof IMAGE_REFERENCE_PURPOSES[number];
export const IMAGE_REFERENCE_PURPOSE_LABELS: Record<ImageReferencePurpose, string> = { character: '角色', outfit: '服装', environment: '环境', style: '风格', composition: '构图' };
export type ImageReference = { source: ProductionSource; weight: number; purpose?: ImageReferencePurpose; source_note?: string };
export const IMAGE_RUNTIME_OPERATIONS = ['m5.image.t2i', 'm5.image.i2i', 'm5.image.reference', 'm5.image.inpaint', 'm5.image.upscale'] as const;
export type ImageRuntimeOperation = typeof IMAGE_RUNTIME_OPERATIONS[number];
const own = (row: Record<string, unknown>, keys: string[]) => Object.keys(row).length === keys.length && keys.every(key => Object.hasOwn(row, key));
const record = (value: unknown): value is Record<string, unknown> => !!value && typeof value === 'object' && !Array.isArray(value);
function invalid(input: boolean): never {
  throw new ApiError({ status: input ? 400 : 200, code: input ? 'STUDIO_IMAGE_INPUT_INVALID' : 'STUDIO_RESPONSE_INVALID',
    message: input ? '图片来源、权重或遮罩绑定无效，请核对当前素材版本。' : '图片来源或遮罩回执不完整，请读取原记录核对。' });
}
function checkedSource(value: unknown, input: boolean): ProductionSource {
  if (!record(value) || !own(value, ['id', 'kind', 'asset_kind', 'version', 'digest', ...(value.reference_only === undefined ? [] : ['reference_only'])])
    || value.reference_only !== undefined && value.reference_only !== true || value.kind !== 'ASSET' || value.asset_kind !== 'image'
    || typeof value.id !== 'string' || !/^[A-Za-z0-9][A-Za-z0-9_-]{0,239}$/.test(value.id)
    || typeof value.version !== 'number' || !Number.isSafeInteger(value.version) || value.version < 1
    || typeof value.digest !== 'string' || !/^[a-f0-9]{64}$/.test(value.digest)) invalid(input);
  return { id: value.id, kind: 'ASSET', asset_kind: 'image', version: value.version, digest: value.digest };
}
export function sameImageSource(left: ProductionSource | RecordedProductionSource, right: ProductionSource | RecordedProductionSource): boolean {
  return left.kind === 'ASSET' && right.kind === 'ASSET' && left.id === right.id && left.version === right.version
    && left.digest === right.digest && left.asset_kind === right.asset_kind;
}
export function checkedImageRecipeFields(value: Record<string, unknown>, operation: string): void {
  const keys = ['image_recipe_id', 'reference_weights', 'reference_semantics', 'mask_semantics'];
  if (!keys.some(key => Object.hasOwn(value, key))) return;
  if (!IMAGE_RUNTIME_OPERATIONS.includes(operation as ImageRuntimeOperation)
    || typeof value.image_recipe_id !== 'string' || !/^[A-Za-z0-9][A-Za-z0-9_.-]{0,239}$/.test(value.image_recipe_id)
    || !Array.isArray(value.reference_weights) || value.reference_weights.length > 6
    || value.reference_weights.some(weight => typeof weight !== 'number' || !Number.isFinite(weight) || weight <= 0 || weight > 1)
    || !['WEIGHTED_PIXEL_INITIALIZATION', 'SINGLE_IMAGE_INITIALIZATION'].includes(String(value.reference_semantics))
    || value.mask_semantics !== null && value.mask_semantics !== 'WHITE_KEEP_BLACK_REPAINT') invalid(false);
  if (operation === 'm5.image.t2i' && value.reference_weights.length || operation === 'm5.image.inpaint' && value.mask_semantics !== 'WHITE_KEEP_BLACK_REPAINT'
    || operation !== 'm5.image.inpaint' && value.mask_semantics !== null) invalid(false);
  if (operation === 'm5.image.upscale') {
    const scale = record(value.parameters) ? value.parameters.scale : undefined;
    const source = checkedImageDimensions(value.source_dimensions), target = checkedImageDimensions(value.target_dimensions);
    if (scale !== 2 && scale !== 4 || target.width !== source.width * scale || target.height !== source.height * scale
      || value.image_recipe_id !== 'comfy-upscale-model-v1' || value.reference_semantics !== 'SINGLE_IMAGE_INITIALIZATION'
      || value.reference_weights.length !== 1 || value.reference_weights[0] !== 1) invalid(false);
  } else if (value.source_dimensions !== undefined || value.target_dimensions !== undefined) invalid(false);
}
export function checkedImageReferenceMetadata(value: unknown, input = false): Pick<ImageReference, 'purpose' | 'source_note'> {
  if (!record(value)) invalid(input);
  const result: Pick<ImageReference, 'purpose' | 'source_note'> = {};
  if (value.purpose !== undefined) { if (!IMAGE_REFERENCE_PURPOSES.includes(value.purpose as ImageReferencePurpose)) invalid(input); result.purpose = value.purpose as ImageReferencePurpose; }
  if (value.source_note !== undefined) { if (typeof value.source_note !== 'string' || value.source_note.length < 1 || value.source_note.length > 500) invalid(input); result.source_note = value.source_note; }
  return result;
}
function checkedImageDimensions(value: unknown): { width: number; height: number } {
  if (!record(value) || !own(value, ['width', 'height']) || typeof value.width !== 'number' || typeof value.height !== 'number'
    || !Number.isSafeInteger(value.width) || !Number.isSafeInteger(value.height) || value.width < 1 || value.height < 1
    || value.width > 4096 || value.height > 4096 || value.width * value.height > 16777216) invalid(false);
  return value as { width: number; height: number };
}
export type ImageUpscaleProof = { contract: 'studio-image-upscale-proof/1'; source_sha256: string; source_width: number; source_height: number;
  scale: 2 | 4; output_width: number; output_height: number; output_sha256: string; output_bytes: number };
export function checkedImageUpscaleProof(value: unknown, command: { source_snapshots: RecordedProductionSource[]; parameters: Record<string, unknown> }, candidate: { digest: string; kind: string } | null): ImageUpscaleProof {
  if (!record(value) || !own(value, ['contract', 'source_sha256', 'source_width', 'source_height', 'scale', 'output_width', 'output_height', 'output_sha256', 'output_bytes'])
    || value.contract !== 'studio-image-upscale-proof/1' || value.scale !== 2 && value.scale !== 4 || command.parameters.scale !== value.scale
    || typeof value.output_sha256 !== 'string' || !/^[a-f0-9]{64}$/.test(value.output_sha256)
    || value.source_sha256 !== command.source_snapshots.find(source => source.kind === 'ASSET')?.digest
    || typeof value.output_bytes !== 'number' || !Number.isSafeInteger(value.output_bytes) || value.output_bytes < 1 || value.output_bytes > 25 * 1024 * 1024) invalid(false);
  const source = checkedImageDimensions({ width: value.source_width, height: value.source_height }), output = checkedImageDimensions({ width: value.output_width, height: value.output_height });
  if (output.width !== source.width * value.scale || output.height !== source.height * value.scale
    || candidate && (candidate.kind !== 'image' || candidate.digest !== value.output_sha256)) invalid(false);
  return value as ImageUpscaleProof;
}
export function checkedImageRecipeCommand(value: Record<string, unknown>, command: { image_source?: ProductionSource; image_references?: ImageReference[]; mask_source?: ProductionSource }): void {
  if (!Object.hasOwn(value, 'image_recipe_id')) return;
  const expected = [...(command.image_source ? [1] : []), ...(command.image_references?.map(reference => reference.weight) || [])];
  if (!Array.isArray(value.reference_weights) || value.reference_weights.length !== expected.length
    || value.reference_weights.some((weight, index) => weight !== expected[index])
    || (value.mask_semantics === 'WHITE_KEEP_BLACK_REPAINT') !== (command.mask_source !== undefined)) invalid(false);
}
/** Optional additions are omitted for legacy commands; checking never creates defaults. */
export function checkedImageRuntimeInputs(value: unknown, snapshots: RecordedProductionSource[], operation: string, input = false): {
  image_source?: ProductionSource; image_references?: ImageReference[]; mask_source?: ProductionSource;
} {
  if (!record(value)) invalid(input);
  const imageSnapshots = snapshots.filter(snapshot => snapshot.kind === 'ASSET');
  if (value.image_source === undefined && value.image_references === undefined && value.mask_source === undefined) {
    if (operation === 'm5.image.inpaint' || operation === 'm5.image.reference' || operation === 'm5.image.upscale') invalid(input);
    return {};
  }
  if (!IMAGE_RUNTIME_OPERATIONS.includes(operation as ImageRuntimeOperation)) invalid(input);
  if (operation === 'm5.image.t2i') invalid(input);
  const result: { image_source?: ProductionSource; image_references?: ImageReference[]; mask_source?: ProductionSource } = {};
  if (value.image_source !== undefined) {
    if (operation !== 'm5.image.i2i' && operation !== 'm5.image.inpaint' && operation !== 'm5.image.upscale') invalid(input);
    const base = checkedSource(value.image_source, input);
    if (!snapshots.some(snapshot => sameImageSource(base, snapshot))) invalid(input);
    result.image_source = base;
  } else if (operation === 'm5.image.i2i' || operation === 'm5.image.inpaint' || operation === 'm5.image.upscale') invalid(input);
  if (value.image_references !== undefined) {
    if (!Array.isArray(value.image_references) || value.image_references.length < 1 || value.image_references.length > 5) invalid(input);
    const seen = new Set<string>();
    result.image_references = value.image_references.map(reference => {
      if (!record(reference) || !own(reference, ['source', 'weight', ...(reference.purpose === undefined ? [] : ['purpose']), ...(reference.source_note === undefined ? [] : ['source_note'])]) || typeof reference.weight !== 'number'
        || !Number.isFinite(reference.weight) || reference.weight <= 0 || reference.weight > 1) invalid(input);
      const source = checkedSource(reference.source, input);
      if (seen.has(source.id) || source.id === result.image_source?.id || !snapshots.some(snapshot => sameImageSource(source, snapshot))) invalid(input);
      seen.add(source.id); return { source, weight: reference.weight, ...checkedImageReferenceMetadata(reference, input) };
    });
  }
  if (value.mask_source !== undefined) {
    if (operation !== 'm5.image.inpaint') invalid(input);
    const mask = checkedSource(value.mask_source, input);
    if (!snapshots.some(snapshot => sameImageSource(mask, snapshot)) || mask.id === result.image_source?.id
      || result.image_references?.some(reference => reference.source.id === mask.id)) invalid(input);
    result.mask_source = mask;
  } else if (operation === 'm5.image.inpaint') invalid(input);
  if (operation === 'm5.image.reference' && !result.image_references || operation === 'm5.image.inpaint' && result.image_references !== undefined
    || operation === 'm5.image.i2i' && (result.image_references?.length || 0) > 4 || operation === 'm5.image.upscale' && (result.image_references !== undefined || result.mask_source !== undefined)) invalid(input);
  const ordered = [result.image_source, ...(result.image_references?.map(reference => reference.source) || []), result.mask_source]
    .filter((source): source is ProductionSource => !!source);
  const unique: ProductionSource[] = [];
  for (const source of ordered) {
    const previous = unique.find(value => value.id === source.id);
    if (previous && !sameImageSource(previous, source)) invalid(input);
    if (!previous) unique.push(source);
  }
  if (imageSnapshots.length !== unique.length || imageSnapshots.some((source, index) => !sameImageSource(source, unique[index]))) invalid(input);
  return result;
}
export function sameImageRuntimeInputs(expected: { image_source?: ProductionSource; image_references?: ImageReference[]; mask_source?: ProductionSource }, value: unknown): boolean {
  if (!record(value)) return false;
  if (expected.image_source === undefined ? value.image_source !== undefined : !record(value.image_source)
    || !sameImageSource(expected.image_source, value.image_source as ProductionSource)) return false;
  const refs = value.image_references;
  if (expected.image_references === undefined ? refs !== undefined : !Array.isArray(refs) || refs.length !== expected.image_references.length
    || refs.some((ref, index) => !record(ref) || ref.weight !== expected.image_references![index].weight || ref.purpose !== expected.image_references![index].purpose || ref.source_note !== expected.image_references![index].source_note
      || !record(ref.source) || !sameImageSource(expected.image_references![index].source, ref.source as ProductionSource))) return false;
  return expected.mask_source === undefined ? value.mask_source === undefined : record(value.mask_source)
    && sameImageSource(expected.mask_source, value.mask_source as ProductionSource);
}
