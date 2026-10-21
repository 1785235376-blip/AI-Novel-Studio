import { canvasReturnInCommand, sameCanvasReturn } from './studioCanvasReturnBinding';
import { ApiError } from '../api';
import type { MediaCommand, ProductionRecipe, ProductionSource, RecordedMediaCommand } from './studioProductionClient';
export const IMAGE_COMPOSITE_OPERATION = 'm5.image.composite' as const;
export const IMAGE_COMPOSITE_ALGORITHM = 'ENCODED_RGBA8_STRAIGHT_SOURCE_OVER_HALF_UP_V1';
export const IMAGE_COMPOSITE_OUTPUT = 'PNG_RGBA8_STORED_DEFLATE_ZERO_ALPHA_RGB';
export type ImageCompositeLayer = { source: ProductionSource; visible: boolean; opacity: number };
export type ImageCompositeProof = { contract: 'cpu-two-layer-composite/1'; algorithm: typeof IMAGE_COMPOSITE_ALGORITHM;
  width: number; height: number; source_sha256: string[]; layers_digest: string; output_sha256: string; rgba_sha256: string; output_bytes: number };
const object = (v: unknown): v is Record<string, unknown> => !!v && typeof v === 'object' && !Array.isArray(v);
function fail(): never { throw new ApiError({ status: 200, code: 'STUDIO_RESPONSE_INVALID', message: '叠层输入、配方或处理证明不一致，请重新核对原任务。' }); }
const hex = (v: unknown): v is string => typeof v === 'string' && /^[a-f0-9]{64}$/.test(v);
const closed = (v: Record<string, unknown>, keys: string[]) => Object.keys(v).length === keys.length && keys.every(k => Object.hasOwn(v, k));
function source(v: unknown): ProductionSource {
  if (!object(v) || Object.keys(v).some(k => !['id', 'kind', 'asset_kind', 'version', 'digest', 'reference_only'].includes(k))
    || typeof v.id !== 'string' || !v.id || v.id.length > 240 || v.kind !== 'ASSET' || v.asset_kind !== 'image'
    || !Number.isSafeInteger(v.version) || Number(v.version) < 1 || !hex(v.digest)
    || v.reference_only !== undefined && v.reference_only !== true) fail();
  return { id: v.id as string, kind: 'ASSET', asset_kind: 'image', version: v.version as number, digest: v.digest as string };
}
export function checkedCompositeLayers(v: unknown): ImageCompositeLayer[] {
  if (!Array.isArray(v) || v.length !== 2) fail();
  const result = v.map(item => {
    if (!object(item) || !closed(item, ['source', 'visible', 'opacity']) || typeof item.visible !== 'boolean'
      || !Number.isSafeInteger(item.opacity) || Number(item.opacity) < 0 || Number(item.opacity) > 255) fail();
    return { source: source(item.source), visible: item.visible as boolean, opacity: item.opacity as number };
  });
  if (result[0].source.id === result[1].source.id) fail(); return result;
}
export function checkedCompositeCommand(v: unknown): ImageCompositeLayer[] {
  const keys = ['operation_id', 'request_id', 'provider_id', 'model_id', 'prompt', 'parameters', 'source_snapshots', 'allow_cloud', 'license_note', 'image_layers', ...(object(v)&&Object.hasOwn(v,'canvas_return')?['canvas_return']:[])];
  if (!object(v) || !closed(v, keys) || v.operation_id !== IMAGE_COMPOSITE_OPERATION || v.provider_id !== null || v.model_id !== null
    || v.prompt !== '' || v.allow_cloud !== false || typeof v.request_id !== 'string' || !/^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$/.test(v.request_id)
    || typeof v.license_note !== 'string' || v.license_note.length > 2000 || !object(v.parameters) || Object.keys(v.parameters).length
    || !Array.isArray(v.source_snapshots) || v.source_snapshots.length !== 2) fail();
  canvasReturnInCommand(v);
  const layers = checkedCompositeLayers(v.image_layers);
  if (JSON.stringify(layers.map(l => l.source)) !== JSON.stringify(v.source_snapshots.map(source))) fail(); return layers;
}
export function sameCompositeCommand(a: MediaCommand | RecordedMediaCommand, b: MediaCommand | RecordedMediaCommand | null) {
  if (a.operation_id !== IMAGE_COMPOSITE_OPERATION) return b?.image_layers === undefined;
  if (!b || b.operation_id !== a.operation_id || a.request_id !== b.request_id || a.license_note !== b.license_note) return false;
  try { return sameCanvasReturn(a,b) && JSON.stringify(checkedCompositeCommand(a)) === JSON.stringify(checkedCompositeCommand(b)); } catch { return false; }
}
export function checkedCompositeRecipe(v: unknown, command?: MediaCommand | RecordedMediaCommand): ProductionRecipe {
  const keys = ['contract', 'operation_id', 'adapter', 'recipe_digest', 'automatic_fallback', 'parameters', 'layers', 'algorithm', 'output_profile'];
  if (!object(v) || !closed(v, keys) || v.contract !== 'studio-execution-recipe/1' || v.operation_id !== IMAGE_COMPOSITE_OPERATION
    || v.adapter !== 'LOCAL_CPU_COMPOSITE' || !hex(v.recipe_digest) || v.automatic_fallback !== false
    || v.algorithm !== IMAGE_COMPOSITE_ALGORITHM || v.output_profile !== IMAGE_COMPOSITE_OUTPUT
    || !object(v.parameters) || Object.keys(v.parameters).length) fail();
  const layers = checkedCompositeLayers(v.layers);
  if (command && JSON.stringify(layers) !== JSON.stringify(checkedCompositeCommand(command))) fail();
  return v as ProductionRecipe;
}
export function checkedCompositeProof(v: unknown, command: MediaCommand | RecordedMediaCommand, candidate: { digest: string } | null): ImageCompositeProof | null {
  if (v == null) { if (candidate) fail(); return null; }
  const keys = ['contract', 'algorithm', 'width', 'height', 'source_sha256', 'layers_digest', 'output_sha256', 'rgba_sha256', 'output_bytes'];
  const layers = checkedCompositeCommand(command);
  if (!object(v) || !closed(v, keys) || v.contract !== 'cpu-two-layer-composite/1' || v.algorithm !== IMAGE_COMPOSITE_ALGORITHM
    || ['width', 'height'].some(k => !Number.isSafeInteger(v[k]) || Number(v[k]) < 64 || Number(v[k]) > 1024 || Number(v[k]) % 8 !== 0)
    || !hex(v.layers_digest) || !hex(v.output_sha256) || !hex(v.rgba_sha256) || !Number.isSafeInteger(v.output_bytes)
    || Number(v.output_bytes) < 57 || Number(v.output_bytes) > 4195716
    || JSON.stringify(v.source_sha256) !== JSON.stringify(layers.map(l => l.source.digest))
    || candidate && candidate.digest !== v.output_sha256) fail();
  return v as ImageCompositeProof;
}
