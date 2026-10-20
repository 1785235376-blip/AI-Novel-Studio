import { ApiError } from '../api';
import type { RecordedProductionSource, ProductionSource } from './studioProductionClient';
import { checkedPlanningSnapshot } from './studioProductionGraphContract';
import type { ShotPin } from './studioStoryboardContract';
export const VIDEO_REFERENCE_PURPOSES = ['style', 'action', 'camera'] as const;
export type VideoReference = { source: ProductionSource; purpose: typeof VIDEO_REFERENCE_PURPOSES[number] };
export const VIDEO_FRAME_ROLES = ['FIRST', 'LAST'] as const;
/** One exact first/last image frame of an existing Asset owner, in role order. */
export type VideoFrame = { role: typeof VIDEO_FRAME_ROLES[number]; source: ProductionSource };
export type VideoFrameCapabilities = { start_frame: boolean; end_frame: boolean; multi_reference: false };
export const VIDEO_RECIPE_IDS = ['comfy-ltx095-video-v1', 'comfy-wan22-ti2v5b-v1', 'comfy-hunyuan10-t2v-v1'] as const;
export type VideoCapabilities = { recipe_id: typeof VIDEO_RECIPE_IDS[number]; operations: ('t2v' | 'i2v')[]; structural_only: true; inference_verified: false;
  reference_semantics: 'SINGLE_IMAGE_INITIALIZATION'; reference_video_execution: false; output_format: 'WEBM_VP9' };
const object = (v: unknown): v is Record<string, unknown> => !!v && typeof v === 'object' && !Array.isArray(v);
function fail(): never { throw new ApiError({ status: 200, code: 'STUDIO_RESPONSE_INVALID', message: '视频配方或参考版本不完整，请重新读取核对。' }); }
function exact(v: Record<string, unknown>, keys: string[]) { if (Object.keys(v).length !== keys.length || keys.some(k => !Object.hasOwn(v, k))) fail(); }
export function checkedStoryboardShotContext(value: unknown, sources?: RecordedProductionSource[], operation?: string): ShotPin {
  if (!object(value)) fail(); exact(value, ['document_snapshot', 'shot_id', 'shot_version', 'shot_digest']);
  const document_snapshot = checkedPlanningSnapshot(value.document_snapshot);
  if (typeof value.shot_id !== 'string' || !value.shot_id.trim() || value.shot_id.length > 240 || /[\u0000-\u001f\u007f]/.test(value.shot_id)
    || typeof value.shot_version !== 'number' || !Number.isSafeInteger(value.shot_version) || value.shot_version < 1 || typeof value.shot_digest !== 'string' || !/^[a-f0-9]{64}$/.test(value.shot_digest)) fail();
  if (sources && (!['m7.video.t2v', 'm7.video.i2v', 'm7.video.v2v'].includes(operation || '') || sources.filter(source => source.kind === 'CREATIVE_DOCUMENT' && source.id === document_snapshot.id && source.version === document_snapshot.version && source.digest === document_snapshot.digest).length !== 1)) fail();
  return { document_snapshot, shot_id: value.shot_id, shot_version: value.shot_version, shot_digest: value.shot_digest };
}
export function storyboardShotFields(value: unknown, sources: RecordedProductionSource[], operation: string): { storyboard_shot?: ShotPin } {
  return value === undefined ? {} : { storyboard_shot: checkedStoryboardShotContext(value, sources, operation) };
}
export function sameStoryboardShot(expected: { storyboard_shot?: ShotPin }, value: unknown): boolean {
  if (!object(value)) return false; try { return JSON.stringify(expected.storyboard_shot === undefined ? undefined : checkedStoryboardShotContext(expected.storyboard_shot)) === JSON.stringify(value.storyboard_shot === undefined ? undefined : checkedStoryboardShotContext(value.storyboard_shot)); } catch { return false; }
}
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
const sourceKeys = ['id', 'kind', 'version', 'digest', 'asset_kind'];
function checkedFrameSource(value: unknown): ProductionSource {
  if (!object(value)) fail();
  if (value.kind !== 'ASSET' || value.asset_kind !== 'image' || Object.keys(value).some(key => ![...sourceKeys, 'reference_only'].includes(key))
    || typeof value.id !== 'string' || !value.id || value.id.length > 240 || /[\u0000-\u001f\u007f]/.test(value.id)
    || typeof value.version !== 'number' || !Number.isSafeInteger(value.version) || value.version < 1
    || typeof value.digest !== 'string' || !/^[a-f0-9]{64}$/.test(value.digest)) fail();
  return { id: value.id, kind: 'ASSET', version: value.version, digest: value.digest, asset_kind: 'image' };
}
/** Validates the ordered first/last frame projection against the same source_snapshots. */
export function checkedVideoFrames(value: unknown, sources: RecordedProductionSource[], operation: string): { video_frames?: VideoFrame[] } {
  if (value === undefined) return {};
  if (!Array.isArray(value) || value.length < 1 || value.length > 2 || operation !== 'm7.video.i2v') fail();
  const roles = value.map(frame => object(frame) ? frame.role : undefined);
  if (roles.length === 1 ? roles[0] !== 'FIRST' : roles[0] !== 'FIRST' || roles[1] !== 'LAST') fail();
  const assets = sources.filter(source => source.kind === 'ASSET');
  if (assets.length !== value.length) fail();
  const frames = value.map((frame, index) => {
    if (!object(frame) || Object.keys(frame).some(key => !['role', 'source'].includes(key))) fail();
    const source = checkedFrameSource(frame.source);
    if (source.id !== assets[index].id || source.version !== assets[index].version || source.digest !== assets[index].digest) fail();
    return { role: frame.role as VideoFrame['role'], source };
  });
  if (new Set(frames.map(frame => frame.source.id)).size !== frames.length) fail();
  return { video_frames: frames };
}
export function sameVideoFrames(expected: { video_frames?: VideoFrame[]; source_snapshots: RecordedProductionSource[] }, value: unknown): boolean {
  if (!object(value)) return false;
  try {
    const expectedValue = checkedVideoFrames(expected.video_frames, expected.source_snapshots, 'm7.video.i2v');
    const actualValue = checkedVideoFrames(value.video_frames, expected.source_snapshots, 'm7.video.i2v');
    return JSON.stringify(expectedValue) === JSON.stringify(actualValue);
  } catch { return false; }
}
export function checkedVideoFrameCapabilities(value: unknown): VideoFrameCapabilities {
  if (!object(value)) fail(); exact(value, ['start_frame', 'end_frame', 'multi_reference']);
  if (typeof value.start_frame !== 'boolean' || typeof value.end_frame !== 'boolean' || value.multi_reference !== false) fail();
  return value as unknown as VideoFrameCapabilities;
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
