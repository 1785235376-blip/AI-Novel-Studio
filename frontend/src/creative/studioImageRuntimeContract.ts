import { ApiError } from '../api';
import type { ProductionSource, RecordedProductionSource } from './studioProductionClient';

export type ImageReference = { source: ProductionSource; weight: number };
export const IMAGE_RUNTIME_OPERATIONS = ['m5.image.t2i', 'm5.image.i2i', 'm5.image.reference', 'm5.image.inpaint'] as const;
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
  if (value.image_source === undefined && value.image_references === undefined && value.mask_source === undefined) {
    if (operation === 'm5.image.inpaint' || operation === 'm5.image.reference') invalid(input);
    return {};
  }
  if (!IMAGE_RUNTIME_OPERATIONS.includes(operation as ImageRuntimeOperation)) invalid(input);
  if (operation === 'm5.image.t2i') invalid(input);
  const result: { image_source?: ProductionSource; image_references?: ImageReference[]; mask_source?: ProductionSource } = {};
  if (value.image_source !== undefined) {
    if (operation !== 'm5.image.i2i' && operation !== 'm5.image.inpaint') invalid(input);
    const base = checkedSource(value.image_source, input);
    if (!snapshots.some(snapshot => sameImageSource(base, snapshot))) invalid(input);
    result.image_source = base;
  } else if (operation === 'm5.image.i2i' || operation === 'm5.image.inpaint') invalid(input);
  if (value.image_references !== undefined) {
    if (!Array.isArray(value.image_references) || value.image_references.length < 1 || value.image_references.length > 5) invalid(input);
    const seen = new Set<string>();
    result.image_references = value.image_references.map(reference => {
      if (!record(reference) || !own(reference, ['source', 'weight']) || typeof reference.weight !== 'number'
        || !Number.isFinite(reference.weight) || reference.weight <= 0 || reference.weight > 1) invalid(input);
      const source = checkedSource(reference.source, input);
      if (seen.has(source.id) || source.id === result.image_source?.id || !snapshots.some(snapshot => sameImageSource(source, snapshot))) invalid(input);
      seen.add(source.id); return { source, weight: reference.weight };
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
    || operation === 'm5.image.i2i' && (result.image_references?.length || 0) > 4) invalid(input);
  const ordered = [result.image_source, ...(result.image_references?.map(reference => reference.source) || []), result.mask_source]
    .filter((source): source is ProductionSource => !!source);
  const unique: ProductionSource[] = [];
  for (const source of ordered) {
    const previous = unique.find(value => value.id === source.id);
    if (previous && !sameImageSource(previous, source)) invalid(input);
    if (!previous) unique.push(source);
  }
  if (snapshots.length !== unique.length || snapshots.some((source, index) => !sameImageSource(source, unique[index]))) invalid(input);
  return result;
}
export function sameImageRuntimeInputs(expected: { image_source?: ProductionSource; image_references?: ImageReference[]; mask_source?: ProductionSource }, value: unknown): boolean {
  if (!record(value)) return false;
  if (expected.image_source === undefined ? value.image_source !== undefined : !record(value.image_source)
    || !sameImageSource(expected.image_source, value.image_source as ProductionSource)) return false;
  const refs = value.image_references;
  if (expected.image_references === undefined ? refs !== undefined : !Array.isArray(refs) || refs.length !== expected.image_references.length
    || refs.some((ref, index) => !record(ref) || ref.weight !== expected.image_references![index].weight
      || !record(ref.source) || !sameImageSource(expected.image_references![index].source, ref.source as ProductionSource))) return false;
  return expected.mask_source === undefined ? value.mask_source === undefined : record(value.mask_source)
    && sameImageSource(expected.mask_source, value.mask_source as ProductionSource);
}
