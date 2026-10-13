import { ApiError } from '../api';
import type { RecordedProductionSource, ProductionSource } from './studioProductionClient';
export const VIDEO_REFERENCE_PURPOSES = ['style', 'action', 'camera'] as const;
export type VideoReference = { source: ProductionSource; purpose: typeof VIDEO_REFERENCE_PURPOSES[number] };
export const VIDEO_RECIPE_IDS = ['comfy-ltx095-video-v1', 'comfy-wan22-ti2v5b-v1', 'comfy-hunyuan10-t2v-v1'] as const;
export type VideoCapabilities = { recipe_id: typeof VIDEO_RECIPE_IDS[number]; operations: ('t2v' | 'i2v')[]; structural_only: true; inference_verified: false;
  reference_semantics: 'SINGLE_IMAGE_INITIALIZATION'; reference_video_execution: false; output_format: 'WEBM_VP9' };
const object = (v: unknown): v is Record<string, unknown> => !!v && typeof v === 'object' && !Array.isArray(v);
function fail(): never { throw new ApiError({ status: 200, code: 'STUDIO_RESPONSE_INVALID', message: '视频配方或参考版本不完整，请重新读取核对。' }); }
function exact(v: Record<string, unknown>, keys: string[]) { if (Object.keys(v).length !== keys.length || keys.some(k => !Object.hasOwn(v, k))) fail(); }
export function checkedVideoReference(value: unknown, sources: RecordedProductionSource[], operation: string): { video_reference?: VideoReference } {
  if (value === undefined) return {};
  if (!object(value)) fail(); exact(value, ['source', 'purpose']);
  if (operation !== 'm7.video.v2v' || !VIDEO_REFERENCE_PURPOSES.includes(value.purpose as VideoReference['purpose']) || !object(value.source)) fail();
  const source = value.source, assets = sources.filter(source => source.kind === 'ASSET');
  if (source.kind !== 'ASSET' || source.asset_kind !== 'video' || source.reference_only !== undefined && source.reference_only !== true
    || Object.keys(source).some(key => !['id', 'kind', 'asset_kind', 'version', 'digest', 'reference_only'].includes(key))
    || assets.length !== 1 || ['id', 'kind', 'asset_kind', 'version', 'digest'].some(key => source[key] !== (assets[0] as Record<string, unknown>)[key])) fail();
  return { video_reference: { source: { id: assets[0].id, kind: 'ASSET', asset_kind: 'video', version: assets[0].version, digest: assets[0].digest }, purpose: value.purpose as VideoReference['purpose'] } };
}
export function sameVideoReference(expected: { video_reference?: VideoReference }, value: unknown) {
  if (!object(value)) return false;
  try { return JSON.stringify(checkedVideoReference(expected.video_reference, expected.video_reference ? [expected.video_reference.source] : [], 'm7.video.v2v'))
    === JSON.stringify(checkedVideoReference(value.video_reference, expected.video_reference ? [expected.video_reference.source] : [], 'm7.video.v2v')); } catch { return false; }
}
export function checkedVideoCapabilities(value: unknown, operation: string): VideoCapabilities {
  if (!object(value)) fail(); exact(value, ['recipe_id', 'operations', 'structural_only', 'inference_verified', 'reference_semantics', 'reference_video_execution', 'output_format']);
  if (!VIDEO_RECIPE_IDS.includes(value.recipe_id as VideoCapabilities['recipe_id']) || !Array.isArray(value.operations)
    || value.operations.length < 1 || value.operations.length > 2 || value.operations[0] !== 't2v' || value.operations.length === 2 && value.operations[1] !== 'i2v'
    || !value.operations.includes(operation.slice('m7.video.'.length)) || value.structural_only !== true || value.inference_verified !== false
    || value.reference_semantics !== 'SINGLE_IMAGE_INITIALIZATION' || value.reference_video_execution !== false || value.output_format !== 'WEBM_VP9') fail();
  if (value.recipe_id === 'comfy-hunyuan10-t2v-v1' && (operation !== 'm7.video.t2v' || value.operations.length !== 1)) fail();
  return value as unknown as VideoCapabilities;
}
export function checkedVideoRecipe(value: Record<string, unknown>, operation: string): void {
  if (value.adapter !== 'COMFYUI_BUILTIN_VIDEO' && ['video_recipe_id', 'timing', 'structural_only', 'inference_verified', 'reference_video_execution'].every(key => value[key] === undefined)) return;
  if (!['m7.video.t2v', 'm7.video.i2v'].includes(operation) || value.adapter !== 'COMFYUI_BUILTIN_VIDEO' || !VIDEO_RECIPE_IDS.includes(value.video_recipe_id as VideoCapabilities['recipe_id'])
    || value.structural_only !== true || value.inference_verified !== false || value.reference_video_execution !== false || !object(value.timing) || !object(value.parameters) || !object(value.workflow)) fail();
  if (value.video_recipe_id === 'comfy-hunyuan10-t2v-v1' && (operation !== 'm7.video.t2v' || value.parameters.negative_prompt != null)) fail();
  const t = value.timing, p = value.parameters; exact(t, ['width', 'height', 'frames', 'frame_rate', 'duration_ms']);
  const width = p.width ?? 512, height = p.height ?? 512, seconds = p.duration_seconds ?? 4, fps = p.frame_rate ?? 24;
  const stride = value.video_recipe_id === 'comfy-ltx095-video-v1' ? 8 : 4;
  if ([width, height, seconds, fps].some(v => typeof v !== 'number' || !Number.isSafeInteger(v)) || Number(width) < 64 || Number(width) > 1024 || Number(height) < 64 || Number(height) > 1024
    || Number(width) % 32 || Number(height) % 32 || Number(seconds) < 1 || Number(seconds) > 10 || Number(fps) < 1 || Number(fps) > 30) fail();
  const frames = Math.ceil((Number(seconds) * Number(fps) - 1) / stride) * stride + 1;
  if (frames < 9 || frames > 241 || Number(width) * Number(height) * frames > 268435456 || t.width !== width || t.height !== height || t.frames !== frames || t.frame_rate !== fps
    || typeof t.duration_ms !== 'number' || Math.abs(t.duration_ms - frames * 1000 / Number(fps)) > 0.5) fail();
}
