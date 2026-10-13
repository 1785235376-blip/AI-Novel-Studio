import { checkedVideoReference, checkedVideoRecipe, checkedVideoCapabilities, sameVideoReference, storyboardShotFields, sameStoryboardShot, type VideoReference, type VideoCapabilities } from './studioVideoRuntimeContract';
import type { ShotPin } from './studioStoryboardContract';
import { checkedCutoutProof, type CutoutProcessingProof } from './studioCutoutContract';
import { checkedImageUpscaleProof, type ImageUpscaleProof, checkedImageRecipeCommand, checkedImageRecipeFields, checkedImageRuntimeInputs, sameImageRuntimeInputs, type ImageReference } from './studioImageRuntimeContract';
import { maskDimension } from './studioManualMaskContract';
import { ApiError, type CollaborationContext } from '../api';
import { studioTransport } from './studioClient';
import { checkedTimeline, checkedTimelineRow, type StudioTimeline, type StudioTimelineRow } from './studioTimelineTypes';
import { checkedTimelineTransferInput, checkedTimelineTransferPreview, timelineTransferInputDigest, type TimelineTransferInput, type TimelineTransferPreview } from './studioTimelineTransferTypes';
import { checkedTimelineExportPreview, checkedTimelineExportProfile, type TimelineExportProfile } from './studioTimelineExportTypes';
import { checkedTimelinePlayback, type TimelinePlayback } from './studioTimelinePlaybackTypes';

export type ProductionOwner = 'image' | 'audio' | 'video' | 'timeline';
export type MediaOperation = 'm5.image.t2i' | 'm5.image.i2i' | 'm5.image.reference' | 'm5.image.inpaint' | 'm5.image.upscale' | 'm5.image.cutout' | 'm7.video.t2v' | 'm7.video.i2v' | 'm7.video.v2v' | 'm8.audio.speech' | 'm8.audio.music' | 'm8.audio.effects' | 'm8.audio.trim';
export type ProductionSource = { id: string; kind: 'ASSET'; version: number; digest: string; asset_kind: 'image' | 'video' | 'audio'; reference_only?: true };
export type MediaCommand = { operation_id: MediaOperation; request_id: string; provider_id?: string | null; model_id?: string | null; prompt: string;
  parameters: Record<string, string | number>; source_snapshots: RecordedProductionSource[]; allow_cloud: boolean; license_note: string;
  image_source?: ProductionSource; image_references?: ImageReference[]; mask_source?: ProductionSource; video_reference?: VideoReference; storyboard_shot?: ShotPin };
export type RecordedProductionSource = ProductionSource | { id: string; kind: 'CREATIVE_DOCUMENT'; version: number; digest: string; reference_only?: true };
export type RecordedMediaCommand = Omit<MediaCommand, 'source_snapshots'> & { source_snapshots: RecordedProductionSource[] };
export type ProductionProvider = { operation_id: MediaOperation; provider_id: string; model_id: string; local: boolean; route_digest: string; capability: string; supported_parameters: string[]; readiness: 'CONFIGURED_NOT_VERIFIED'; video_capabilities?: VideoCapabilities;
  image_capabilities?: { recipe_id: string; reference_limit: number; reference_semantics: 'WEIGHTED_PIXEL_INITIALIZATION' | 'SINGLE_IMAGE_INITIALIZATION';
    mask_semantics: 'WHITE_KEEP_BLACK_REPAINT' | null; structural_only: true; inference_verified: false; upscaling?: { scales: [2, 4]; output_format: 'PNG'; output_size_limit: 4096; output_pixel_limit: 16777216 } } };
export type ProductionPreview = { contract: 'studio-production-preview/1'; novel_id: string; branch_id: string | null; request_id: string; operation_id: MediaOperation;
  preview_digest: string; request_digest: string; command: MediaCommand; provider: { provider_id: string; model_id: string; local: boolean; route_digest: string } | null;
  sources?: { snapshot: RecordedProductionSource; measured: Record<string, unknown> }[];
  execution_recipe: ProductionRecipe; product_acceptance: 'LOCAL_REQUIRED'; execution_available: true; automatic_dispatch: false; output_policy: 'PRIVATE_CANDIDATE_THEN_EXPLICIT_REVIEW' };
export type ProductionRecipe = { contract: 'studio-execution-recipe/1'; operation_id: string; adapter: string; recipe_digest: string; automatic_fallback: false; [key: string]: unknown };
// Shared receipt projection retains the existing timeline consumer type name.
// The decoder validates the two owners independently; WAV fields are trim-only.
export type TimelineMediaMeasurement = { duration_ms?: number; byte_count?: number; width?: number; height?: number; fps?: number;
  video_codec?: string; audio_codec?: string; sample_rate?: number; channels?: number; container?: 'mp4' | 'webm' | 'wav';
  profile_validation?: 'NATIVE_FFPROBE_EXACT' | 'PCM_DECODED'; render_profile?: string; export_profile?: TimelineExportProfile;
  sample_width?: 2; output_sha256?: string };
export type AudioWavMeasurement = { duration_ms: number; byte_count: number; sample_rate: number; channels: 1 | 2; sample_width: 2;
  container: 'wav'; audio_codec: 'pcm_s16le'; profile_validation: 'PCM_DECODED'; output_sha256: string };
export type ProductionJob = { contract: 'studio-production-job/1'; owner: ProductionOwner; id: string; novel_id: string; branch_id: string | null; version: number;
  operation_id: string; request_id: string; status: 'QUEUED' | 'RUNNING' | 'SEND_RESERVED' | 'REMOTE_RUNNING' | 'RESULT_READY' | 'AWAITING_REVIEW' | 'SUCCEEDED' | 'REVIEWING' | 'APPROVED' | 'UNKNOWN' | 'FAILED' | 'CANCELLED';
  request_digest: string; receipt_digest: string | null; output_candidate: { id: string; version: number; digest: string; kind: 'image' | 'video' | 'audio' } | null;
  error_code?: string | null; review_state?: string | null; cancellation_mode?: string | null; product_acceptance: 'LOCAL_REQUIRED'; automatic_replay: false; remote_compute_may_continue: boolean;
  timeline_snapshot: { id: string; version: number; digest: string } | null;
  sources: RecordedProductionSource[];
  command: RecordedMediaCommand | null;
  provider: { provider_id: string; model_id: string; local: boolean; route_digest: string } | null;
  execution_recipe: ProductionRecipe; approved_asset_version: number | null;
  media_measurement?: TimelineMediaMeasurement | null; processing_proof?: CutoutProcessingProof | ImageUpscaleProof | null;
  needs_reconciliation?: boolean; execution_state?: string; created_at: string; updated_at: string };
export type ProductionAction = { expected_version: number; expected_request_digest: string };

const operations: MediaOperation[] = ['m5.image.t2i', 'm5.image.i2i', 'm5.image.reference', 'm5.image.inpaint', 'm5.image.upscale', 'm5.image.cutout', 'm7.video.t2v', 'm7.video.i2v', 'm7.video.v2v', 'm8.audio.speech', 'm8.audio.music', 'm8.audio.effects', 'm8.audio.trim'];
const owners: ProductionOwner[] = ['image', 'audio', 'video', 'timeline'];
const states = ['QUEUED', 'RUNNING', 'SEND_RESERVED', 'REMOTE_RUNNING', 'RESULT_READY', 'AWAITING_REVIEW', 'SUCCEEDED', 'REVIEWING', 'APPROVED', 'UNKNOWN', 'FAILED', 'CANCELLED'];
const parameterKeys = ['scale', 'width', 'height', 'steps', 'seed', 'negative_prompt', 'size', 'quality', 'denoising_strength', 'duration_seconds', 'frame_rate', 'voice_id', 'speech_rate', 'in_ms', 'out_ms', 'gain_db', 'sample_rate', 'channels'];
const trimControlKeys = ['gain_db', 'sample_rate', 'channels'];
const record = (v: unknown): v is Record<string, unknown> => !!v && typeof v === 'object' && !Array.isArray(v);
const hex = (v: unknown): v is string => typeof v === 'string' && /^[a-f0-9]{64}$/.test(v);
const identifier = (v: unknown): v is string => typeof v === 'string' && /^[A-Za-z0-9][A-Za-z0-9_-]{0,239}$/.test(v);
const revision = (v: unknown): v is number => typeof v === 'number' && Number.isSafeInteger(v) && v >= 1;
function invalid(): never { throw new ApiError({ status: 200, code: 'STUDIO_RESPONSE_INVALID', message: '服务回执不完整。请重新读取核对，勿重复发送。' }); }
function sources(v: unknown, limit: number): asserts v is RecordedProductionSource[] {
  if (!Array.isArray(v) || v.length > limit || v.some(s => !record(s) || !identifier(s.id) || !revision(s.version) || !hex(s.digest)
    || !['ASSET', 'CREATIVE_DOCUMENT'].includes(String(s.kind)) || s.reference_only !== undefined && s.reference_only !== true
    || Object.keys(s).some(k => !['id', 'kind', 'version', 'digest', 'asset_kind', 'reference_only'].includes(k))
    || (s.kind === 'ASSET' ? !['image', 'video', 'audio'].includes(String(s.asset_kind)) : s.asset_kind != null))) invalid();
}
function cutoutCommand(v: unknown, recorded = false): asserts v is MediaCommand {
  const keys = ['operation_id', 'request_id', 'provider_id', 'model_id', 'prompt', 'parameters', 'source_snapshots', 'allow_cloud', 'license_note'];
  if (!record(v) || Object.keys(v).length !== keys.length || keys.some(key => !Object.hasOwn(v, key)) || v.operation_id !== 'm5.image.cutout'
    || v.provider_id !== null || v.model_id !== null || v.prompt !== '' || v.allow_cloud !== false || !record(v.parameters) || Object.keys(v.parameters).length
    || typeof v.request_id !== 'string' || !/^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$/.test(v.request_id)
    || typeof v.license_note !== 'string' || v.license_note.length > 2000) invalid();
  sources(v.source_snapshots, 2);
  if (v.source_snapshots.length !== 2 || v.source_snapshots[0].id === v.source_snapshots[1].id
    || v.source_snapshots.some(source => source.kind !== 'ASSET' || source.asset_kind !== 'image' || !recorded && source.reference_only !== undefined)) invalid();
}
function sameCutoutCommand(expected: RecordedMediaCommand, value: RecordedMediaCommand | null) {
  return !!value && ['operation_id', 'request_id', 'provider_id', 'model_id', 'prompt', 'allow_cloud', 'license_note'].every(key =>
    expected[key as keyof RecordedMediaCommand] === value[key as keyof RecordedMediaCommand])
    && value.source_snapshots.length === expected.source_snapshots.length && value.source_snapshots.every((source, index) =>
      ['id', 'kind', 'version', 'digest', 'asset_kind'].every(key => (source as Record<string, unknown>)[key]
        === (expected.source_snapshots[index] as Record<string, unknown>)[key]));
}
function trimParameters(v: unknown, projected = false): Record<string, number> {
  if (!record(v)) invalid();
  const result: Record<string, number> = {};
  for (const [key, value] of Object.entries(v)) {
    // Original preview projections include known null defaults. Never treat
    // those placeholders as requested controls or synthesize default values.
    if (projected && value === null && parameterKeys.includes(key)) continue;
    if (!['in_ms', 'out_ms', ...trimControlKeys].includes(key) || typeof value !== 'number' || !Number.isFinite(value)) invalid();
    if (key === 'gain_db' ? value < -60 || value > 12 : !Number.isSafeInteger(value)) invalid();
    if (key === 'sample_rate' && (value < 8000 || value > 96000) || key === 'channels' && value !== 1 && value !== 2) invalid();
    result[key] = value;
  }
  if (!Number.isSafeInteger(result.in_ms) || !Number.isSafeInteger(result.out_ms)
    || result.in_ms < 0 || result.out_ms > 600000 || result.out_ms <= result.in_ms || result.out_ms - result.in_ms > 120000) invalid();
  return result;
}
function sameTrimParameters(a: Record<string, number>, b: Record<string, number>) {
  return Object.keys(a).length === Object.keys(b).length && Object.entries(a).every(([key, value]) => b[key] === value);
}
function trimCommand(v: unknown, projected = false): asserts v is MediaCommand {
  if (!record(v) || v.operation_id !== 'm8.audio.trim' || v.provider_id != null || v.model_id != null || v.prompt !== '' || v.allow_cloud !== false
    || typeof v.request_id !== 'string' || !/^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$/.test(v.request_id)
    || typeof v.license_note !== 'string' || v.license_note.length > 2000
    || Object.keys(v).some(key => !['operation_id', 'request_id', 'provider_id', 'model_id', 'prompt', 'parameters', 'source_snapshots', 'allow_cloud', 'license_note'].includes(key))) invalid();
  trimParameters(v.parameters, projected);
  sources(v.source_snapshots, 1);
  if (v.source_snapshots.length !== 1 || v.source_snapshots[0].kind !== 'ASSET' || v.source_snapshots[0].asset_kind !== 'audio'
    || !projected && v.source_snapshots[0].reference_only !== undefined) invalid();
}
function trimRecipe(v: ProductionRecipe, command: unknown) {
  trimCommand(command, true);
  const parameters = trimParameters(command.parameters, true), keys = ['contract', 'operation_id', 'adapter', 'parameters', 'automatic_fallback', 'recipe_digest', 'output_profile'];
  if (Object.keys(v).length !== keys.length || keys.some(key => !Object.hasOwn(v, key)) || v.adapter !== 'LOCAL_FFMPEG'
    || v.output_profile !== `PCM_S16LE_WAV_${parameters.sample_rate ?? 48000}_${parameters.channels === 1 ? 'MONO' : 'STEREO'}`
    || !sameTrimParameters(parameters, trimParameters(v.parameters))) invalid();
  return parameters;
}
function sameTrimCommand(expected: RecordedMediaCommand, value: RecordedMediaCommand | null) {
  return !!value && sameCutoutCommand({ ...expected, provider_id: expected.provider_id ?? null, model_id: expected.model_id ?? null },
    { ...value, provider_id: value.provider_id ?? null, model_id: value.model_id ?? null }) && sameTrimParameters(trimParameters(expected.parameters, true), trimParameters(value.parameters, true));
}
function commandScope(command: MediaCommand) {
  checkedVideoReference(command.video_reference, command.source_snapshots, command.operation_id);
  storyboardShotFields(command.storyboard_shot, command.source_snapshots, command.operation_id);
  checkedImageRuntimeInputs(command, command.source_snapshots, command.operation_id, true);
  if (command.operation_id === 'm5.image.upscale' ? command.prompt !== '' || command.allow_cloud || Object.keys(command.parameters).length !== 1 || ![2, 4].includes(command.parameters.scale as number) : command.parameters.scale !== undefined) invalid();
  if (command.parameters.denoising_strength !== undefined && (!['m5.image.i2i', 'm5.image.reference', 'm5.image.inpaint'].includes(command.operation_id)
    || typeof command.parameters.denoising_strength !== 'number' || !Number.isFinite(command.parameters.denoising_strength)
    || command.parameters.denoising_strength <= 0 || command.parameters.denoising_strength > 1)) invalid();
  if (command.operation_id === 'm8.audio.trim') trimCommand(command);
  else if (Object.keys(command.parameters).some(key => trimControlKeys.includes(key))) invalid();
}
function audioMeasurement(v: unknown, executionRecipe: ProductionRecipe, command: unknown, candidate: unknown): AudioWavMeasurement {
  const keys = ['duration_ms', 'byte_count', 'sample_rate', 'channels', 'sample_width', 'container', 'audio_codec', 'profile_validation', 'output_sha256'];
  if (!record(v) || Object.keys(v).length !== keys.length || keys.some(key => !Object.hasOwn(v, key))
    || v.profile_validation !== 'PCM_DECODED' || v.container !== 'wav' || v.audio_codec !== 'pcm_s16le' || v.sample_width !== 2
    || !hex(v.output_sha256)) invalid();
  const parameters = trimRecipe(executionRecipe, command);
  if (typeof v.duration_ms !== 'number' || !Number.isSafeInteger(v.duration_ms) || v.duration_ms < 1
    || Math.abs(v.duration_ms - (parameters.out_ms - parameters.in_ms)) > 2
    || typeof v.byte_count !== 'number' || !Number.isSafeInteger(v.byte_count) || v.byte_count < 1 || v.byte_count > 25 * 1024 * 1024
    || v.sample_rate !== (parameters.sample_rate ?? 48000) || v.channels !== (parameters.channels ?? 2)
    || candidate !== null && (!record(candidate) || candidate.kind !== 'audio' || candidate.digest !== v.output_sha256)) invalid();
  return v as AudioWavMeasurement;
}
function recipe(v: unknown, operation: unknown): ProductionRecipe {
  if (operation === 'm5.image.cutout') {
    const keys = ['contract', 'operation_id', 'adapter', 'recipe_digest', 'automatic_fallback', 'parameters', 'output_profile', 'mask_policy'];
    if (!record(v) || Object.keys(v).length !== keys.length || keys.some(key => !Object.hasOwn(v, key))
      || v.contract !== 'studio-execution-recipe/1' || v.operation_id !== operation || !hex(v.recipe_digest)
      || v.adapter !== 'LOCAL_CPU_MASK' || v.automatic_fallback !== false || v.output_profile !== 'PNG_RGBA8_STORED_DEFLATE'
      || v.mask_policy !== 'WHITE_KEEP_BLACK_TRANSPARENT_ZERO' || !record(v.parameters) || Object.keys(v.parameters).length) invalid();
    return v as ProductionRecipe;
  }
  if (!record(v) || v.contract !== 'studio-execution-recipe/1' || v.operation_id !== operation || !hex(v.recipe_digest)
    || v.automatic_fallback !== false || !['ORIGINAL_HTTP_PROVIDER', 'COMFYUI_BUILTIN_IMAGE', 'AUTOMATIC1111_IMAGE', 'LOCAL_FFMPEG', 'COMFYUI_BUILTIN_VIDEO'].includes(String(v.adapter))
    || Object.keys(v).some(k => !['contract', 'operation_id', 'adapter', 'recipe_digest', 'automatic_fallback', 'parameters', 'workflow', 'defaults', 'denoising_strength', 'output_profile', 'timeline', 'export_profile', 'image_recipe_id', 'reference_weights', 'reference_semantics', 'mask_semantics', 'video_recipe_id', 'timing', 'structural_only', 'inference_verified', 'reference_video_execution', ...(operation === 'm5.image.upscale' ? ['source_dimensions', 'target_dimensions'] : [])].includes(k))
    || JSON.stringify(v).length > 131072) invalid();
  checkedImageRecipeFields(v, String(operation)); checkedVideoRecipe(v, String(operation));
  return v as ProductionRecipe;
}
function measurement(v: unknown, owner: unknown, executionRecipe: ProductionRecipe, operation: unknown, command: unknown, candidate: unknown): TimelineMediaMeasurement | null | undefined {
  if (v === undefined || v === null) return v;
  if (owner === 'audio' && operation === 'm8.audio.trim') return audioMeasurement(v, executionRecipe, command, candidate);
  if (owner !== 'timeline' || !record(v) || Object.keys(v).some(key => !['duration_ms', 'byte_count', 'width', 'height', 'fps', 'video_codec', 'audio_codec',
    'sample_rate', 'channels', 'container', 'profile_validation', 'render_profile', 'export_profile'].includes(key))) invalid();
  const bounds: Record<string, [number, number]> = { duration_ms: [1, 36000000], byte_count: [1, 25 * 1024 * 1024], width: [16, 1920], height: [16, 1080], sample_rate: [1, 384000], channels: [1, 32] };
  if (Object.entries(bounds).some(([key, [min, max]]) => key in v && (typeof v[key] !== 'number' || !Number.isSafeInteger(v[key]) || v[key] < min || v[key] > max))
    || 'fps' in v && (typeof v.fps !== 'number' || !Number.isFinite(v.fps) || v.fps <= 0 || v.fps > 60.001)
    || ['video_codec', 'audio_codec'].some(key => key in v && (typeof v[key] !== 'string' || !/^[A-Za-z0-9_.-]{1,64}$/.test(v[key])))
    || 'container' in v && !['mp4', 'webm'].includes(String(v.container))
    || 'profile_validation' in v && v.profile_validation !== 'NATIVE_FFPROBE_EXACT'
    || 'render_profile' in v && !['STUDIO_MULTITRACK_LOCAL_FFMPEG', 'STUDIO_MULTITRACK_LOCAL_FFMPEG_REVIEW_MP4', 'STUDIO_MULTITRACK_LOCAL_FFMPEG_DELIVERY_H264_MP4', 'STUDIO_MULTITRACK_LOCAL_FFMPEG_DELIVERY_VP9_WEBM'].includes(String(v.render_profile))) invalid();
  if ('export_profile' in v) {
    try {
      const profile = checkedTimelineExportProfile(v.export_profile), expected = checkedTimelineExportProfile(executionRecipe.export_profile);
      if (JSON.stringify(profile) !== JSON.stringify(expected) || executionRecipe.output_profile !== profile.preset) invalid();
    } catch { return invalid(); }
  }
  if (v.profile_validation === 'NATIVE_FFPROBE_EXACT') {
    if (['duration_ms', 'byte_count', 'width', 'height', 'fps', 'video_codec', 'audio_codec', 'sample_rate', 'channels', 'container', 'render_profile'].some(key => !(key in v))) invalid();
    const preset = (v.export_profile as TimelineExportProfile | undefined)?.preset ?? 'REVIEW_MP4';
    const expected = preset === 'DELIVERY_VP9_WEBM' ? ['vp9', 'opus', 'webm'] : [preset === 'DELIVERY_H264_MP4' ? 'h264' : 'mpeg4', 'aac', 'mp4'];
    if (v.video_codec !== expected[0] || v.audio_codec !== expected[1] || v.container !== expected[2] || v.sample_rate !== 48000 || v.channels !== 2) invalid();
    try {
      const timeline = checkedTimeline(executionRecipe.timeline);
      if (v.width !== timeline.width || v.height !== timeline.height || Math.abs((v.fps as number) - timeline.fps) > 0.001
        || Math.abs((v.duration_ms as number) - timeline.duration_ms) > Math.max(100, Math.ceil(2000 / timeline.fps))) invalid();
    } catch { return invalid(); }
  }
  return v as TimelineMediaMeasurement;
}

export function studioProductionClient(projectId: string, context: CollaborationContext) {
  const capturedScope = context.scope ? { ...context.scope } : undefined;
  const original = studioTransport({ ...context, scope: capturedScope });
  function admitted() {
    if (capturedScope && capturedScope.projectId !== projectId) throw new ApiError({ status: 403,
      code: 'STUDIO_RESPONSE_SCOPE_MISMATCH', message: '制作任务与当前项目或分支不一致，请重新打开。' });
  }
  const transport = {
    json<T>(...args: Parameters<typeof original.json>) { admitted(); return original.json<T>(...args); },
    blob(...args: Parameters<typeof original.blob>) { admitted(); return original.blob(...args); },
  };
  const base = `/api/projects/${encodeURIComponent(projectId)}/studio/production`;
  const branch = context.scope?.branchId ?? null;
  const jobUrl = (owner: ProductionOwner, id: string) => `${base}/jobs/${owner}/${encodeURIComponent(id)}`;
  function scoped(v: Record<string, unknown>) { if (v.novel_id !== projectId || (v.branch_id ?? null) !== branch) invalid(); }
  function job(v: unknown): ProductionJob {
    if (!record(v)) invalid(); scoped(v);
    if (Object.keys(v).some(key => !['contract', 'owner', 'id', 'novel_id', 'branch_id', 'version', 'status', 'request_digest', 'receipt_digest',
      'attempt', 'created_at', 'updated_at', 'error_code', 'review_state', 'cancellation_mode', 'needs_reconciliation', 'execution_state', 'operation_id',
      'output_candidate', 'timeline_snapshot', 'sources', 'command', 'provider', 'execution_recipe', 'approved_asset_version', 'request_id',
      'product_acceptance', 'automatic_replay', 'remote_compute_may_continue', 'media_measurement', 'processing_proof'].includes(key))) invalid();
    if (v.contract !== 'studio-production-job/1' || !owners.includes(v.owner as ProductionOwner) || !identifier(v.id) || !revision(v.version)
      || !states.includes(String(v.status)) || !hex(v.request_digest) || (v.receipt_digest !== null && !hex(v.receipt_digest))
      || typeof v.request_id !== 'string' || !/^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$/.test(v.request_id)
      || typeof v.operation_id !== 'string' || ![...operations, 'm9.timeline.multitrack'].includes(v.operation_id as MediaOperation)
      || v.product_acceptance !== 'LOCAL_REQUIRED' || v.automatic_replay !== false || typeof v.remote_compute_may_continue !== 'boolean') invalid();
    const expectedOwner = v.operation_id.startsWith('m5.') ? 'image' : v.operation_id.startsWith('m7.') ? 'video' : v.operation_id.startsWith('m8.') ? 'audio' : 'timeline';
    if (v.owner !== expectedOwner || typeof v.created_at !== 'string' || typeof v.updated_at !== 'string') invalid();
    if (v.cancellation_mode !== undefined && v.cancellation_mode !== null && (typeof v.cancellation_mode !== 'string' || !/^[A-Z_]{1,80}$/.test(v.cancellation_mode))) invalid();
    if (v.owner === 'timeline' && (v.remote_compute_may_continue !== false || v.cancellation_mode !== undefined && v.cancellation_mode !== null
      && !['LOCAL_RENDER_PROCESS_STOP_REQUESTED', 'LOCAL_RESULT_DISCARD'].includes(String(v.cancellation_mode)))) invalid();
    if (v.output_candidate !== null) {
      const c = v.output_candidate;
      if (!record(c) || !identifier(c.id) || !revision(c.version) || !hex(c.digest) || !['image', 'video', 'audio'].includes(String(c.kind))) invalid();
    }
    sources(v.sources, 30);
    if (v.owner === 'timeline') {
      const s = v.timeline_snapshot;
      if (!record(s) || !identifier(s.id) || !revision(s.version) || !hex(s.digest) || v.operation_id !== 'm9.timeline.multitrack') invalid();
    } else if (v.timeline_snapshot !== null) invalid();
    const executionRecipe = recipe(v.execution_recipe, v.operation_id);
    measurement(v.media_measurement, v.owner, executionRecipe, v.operation_id, v.command, v.output_candidate);
    if (v.approved_asset_version !== null && !revision(v.approved_asset_version)) invalid();
    if (v.owner === 'timeline') { if (v.command !== null || v.provider !== null) invalid(); }
    else {
      const c = v.command;
      if (!record(c) || c.operation_id !== v.operation_id || c.request_id !== v.request_id || typeof c.prompt !== 'string' || c.prompt.length > 16000
        || !record(c.parameters) || !Array.isArray(c.source_snapshots) || typeof c.allow_cloud !== 'boolean' || typeof c.license_note !== 'string' || c.license_note.length > 2000) invalid();
      if (Object.keys(c).some(key => !['operation_id', 'request_id', 'provider_id', 'model_id', 'prompt', 'parameters', 'source_snapshots', 'allow_cloud', 'license_note', 'image_source', 'image_references', 'mask_source', 'video_reference', 'storyboard_shot'].includes(key))
        || Object.entries(c.parameters).some(([key, value]) => !parameterKeys.includes(key) || c.operation_id !== 'm8.audio.trim' && trimControlKeys.includes(key)
          || (typeof value === 'number' ? !Number.isFinite(value) : typeof value !== 'string' || value.length > 8000))) invalid();
      sources(c.source_snapshots, 8);
      checkedVideoReference(c.video_reference, c.source_snapshots, String(c.operation_id));
      storyboardShotFields(c.storyboard_shot, c.source_snapshots, String(c.operation_id));
      checkedImageRuntimeInputs(c, c.source_snapshots, String(c.operation_id));
      checkedImageRecipeCommand(executionRecipe, c);
      if (c.operation_id === 'm5.image.upscale' ? c.prompt !== '' || c.allow_cloud || Object.keys(c.parameters).length !== 1 || ![2, 4].includes(c.parameters.scale as number) : c.parameters.scale !== undefined) invalid();
      if (c.operation_id === 'm5.image.upscale') {
        if (v.output_candidate !== null && v.processing_proof == null) invalid();
        if (v.processing_proof != null) checkedImageUpscaleProof(v.processing_proof, c as unknown as RecordedMediaCommand, v.output_candidate as { digest: string; kind: string } | null);
      }
      if (c.parameters.denoising_strength !== undefined && c.parameters.denoising_strength !== null && (!['m5.image.i2i', 'm5.image.reference', 'm5.image.inpaint'].includes(String(c.operation_id))
        || typeof c.parameters.denoising_strength !== 'number' || !Number.isFinite(c.parameters.denoising_strength) || c.parameters.denoising_strength <= 0 || c.parameters.denoising_strength > 1)) invalid();
      if (c.source_snapshots.length !== v.sources.length || c.source_snapshots.some((s, index) => ['id', 'kind', 'version', 'digest', 'asset_kind'].some(key =>
        (s as Record<string, unknown>)[key] !== (v.sources as Array<Record<string, unknown>>)[index][key]))) invalid();
      if (c.operation_id === 'm5.image.cutout') {
        cutoutCommand(c, true);
        if (v.sources.some(source => source.reference_only !== undefined)) invalid();
        if (['SEND_RESERVED', 'REMOTE_RUNNING', 'RESULT_READY'].includes(String(v.status)) || v.provider !== null || v.remote_compute_may_continue !== false || v.media_measurement != null
          || v.cancellation_mode != null && !['COOPERATIVE_LOCAL_CANCEL', 'LOCAL_RESULT_DISCARD'].includes(String(v.cancellation_mode))) invalid();
        if (v.output_candidate !== null && (v.output_candidate as Record<string, unknown>).kind !== 'image') invalid();
        checkedCutoutProof(v.processing_proof, v.sources, v.output_candidate as { digest: string } | null);
      }
      else if (c.operation_id === 'm8.audio.trim') {
        trimRecipe(executionRecipe, c);
        if (v.media_measurement != null && (v.status === 'QUEUED'
          || ['AWAITING_REVIEW', 'SUCCEEDED', 'REVIEWING', 'APPROVED'].includes(String(v.status)) && v.output_candidate === null)) invalid();
        if (v.provider !== null || v.output_candidate !== null && (v.output_candidate as Record<string, unknown>).kind !== 'audio'
          || Object.keys(c.parameters).some(key => trimControlKeys.includes(key)) && v.media_measurement == null
            && (v.output_candidate !== null || ['AWAITING_REVIEW', 'SUCCEEDED', 'REVIEWING', 'APPROVED'].includes(String(v.status)))) invalid();
      }
      else if (!record(v.provider) || typeof c.provider_id !== 'string' || !c.provider_id || typeof c.model_id !== 'string' || !c.model_id
        || v.provider.provider_id !== c.provider_id || v.provider.model_id !== c.model_id || !hex(v.provider.route_digest) || typeof v.provider.local !== 'boolean'
        || Object.keys(v.provider).some(key => !['provider_id', 'model_id', 'route_digest', 'local'].includes(key))) invalid();
    }
    if (!['m5.image.cutout', 'm5.image.upscale'].includes(String(v.operation_id)) && v.processing_proof != null) invalid();
    return v as unknown as ProductionJob;
  }
  function timeline(v: unknown): StudioTimelineRow {
    if (!record(v)) invalid(); scoped(v);
    if (!identifier(v.id) || !revision(v.version) || !hex(v.timeline_digest) || typeof v.title !== 'string' || v.title.length > 240 || !record(v.timeline)
      || !Array.isArray(v.timeline.tracks) || v.timeline.tracks.length > 8 || !Array.isArray(v.timeline.captions) || v.timeline.captions.length > 500) invalid();
    return checkedTimelineRow(v);
  }
  async function action(owner: ProductionOwner, id: string, operation: 'execute' | 'refresh' | 'cancel' | 'reconcile' | 'review', body: ProductionAction & { reviewed_output_digest?: string }, expected?: ProductionJob) {
    const result = job(await transport.json<unknown>(`${jobUrl(owner, id)}/${operation}`, 'POST', body));
    if (result.owner !== owner || result.id !== id || result.request_digest !== body.expected_request_digest) invalid();
    if (expected?.command && (!sameVideoReference(expected.command, result.command) || !sameStoryboardShot(expected.command, result.command))) invalid();
    if (expected?.command && (expected.command.image_source !== undefined || expected.command.image_references !== undefined || expected.command.mask_source !== undefined)
      && (result.version < expected.version || !sameImageRuntimeInputs(expected.command, result.command)
        || result.execution_recipe.recipe_digest !== expected.execution_recipe.recipe_digest)) invalid();
    if (expected?.operation_id === 'm5.image.cutout' && (result.version < expected.version || !expected.command
      || !sameCutoutCommand(expected.command, result.command) || result.execution_recipe.recipe_digest !== expected.execution_recipe.recipe_digest)) invalid();
    if (expected?.operation_id === 'm8.audio.trim' && (result.version < expected.version || !expected.command
      || !sameTrimCommand(expected.command, result.command) || result.execution_recipe.recipe_digest !== expected.execution_recipe.recipe_digest)) invalid();
    return result;
  }
  return {
    async providers(signal?: AbortSignal): Promise<ProductionProvider[]> {
      const v = await transport.json<unknown>(`${base}/providers`, 'GET', undefined, signal);
      if (!record(v) || !Array.isArray(v.items) || v.items.length > 200 || v.health_probed !== false || v.credentials_read !== false) invalid();
      return v.items.map(row => {
        if (!record(row) || row.operation_id === 'm5.image.cutout' || !operations.includes(row.operation_id as MediaOperation) || typeof row.provider_id !== 'string' || !row.provider_id || row.provider_id.length > 240
          || typeof row.model_id !== 'string' || !row.model_id || row.model_id.length > 240 || typeof row.local !== 'boolean' || !hex(row.route_digest) || row.readiness !== 'CONFIGURED_NOT_VERIFIED'
          || !Array.isArray(row.supported_parameters) || row.supported_parameters.length > 14 || row.supported_parameters.some(p => typeof p !== 'string'
            || !['scale', 'width', 'height', 'steps', 'seed', 'negative_prompt', 'size', 'quality', 'denoising_strength', 'duration_seconds', 'frame_rate', 'voice_id', 'speech_rate', 'in_ms', 'out_ms'].includes(p))) invalid();
        if (row.image_capabilities !== undefined) {
          const image = row.image_capabilities;
          const keys = ['recipe_id', 'reference_limit', 'reference_semantics', 'mask_semantics', 'structural_only', 'inference_verified', ...(row.operation_id === 'm5.image.upscale' ? ['upscaling'] : [])];
          if (!String(row.operation_id).startsWith('m5.image.') || !record(image) || Object.keys(image).length !== keys.length || keys.some(key => !Object.hasOwn(image, key))
            || typeof image.recipe_id !== 'string' || !image.recipe_id.trim() || image.recipe_id.length > 240 || /[\x00-\x1f\x7f]/.test(image.recipe_id)
            || typeof image.reference_limit !== 'number' || !Number.isSafeInteger(image.reference_limit) || image.reference_limit < 0 || image.reference_limit > 5
            || !['WEIGHTED_PIXEL_INITIALIZATION', 'SINGLE_IMAGE_INITIALIZATION'].includes(String(image.reference_semantics))
            || image.mask_semantics !== null && image.mask_semantics !== 'WHITE_KEEP_BLACK_REPAINT' || image.structural_only !== true || image.inference_verified !== false) invalid();
        }
        if (row.operation_id === 'm5.image.upscale') {
          const capability = record(row.image_capabilities) ? row.image_capabilities : invalid(), upscaling = record(capability.upscaling) ? capability.upscaling : invalid();
          if (row.local !== true || capability.reference_limit !== 1 || capability.reference_semantics !== 'SINGLE_IMAGE_INITIALIZATION' || capability.mask_semantics !== null
            || Object.keys(upscaling).length !== 4 || JSON.stringify(upscaling.scales) !== '[2,4]' || upscaling.output_format !== 'PNG' || upscaling.output_size_limit !== 4096 || upscaling.output_pixel_limit !== 16777216
            || JSON.stringify(row.supported_parameters) !== '["scale"]') invalid();
        }
        if (row.video_capabilities !== undefined) { checkedVideoCapabilities(row.video_capabilities, String(row.operation_id)); if (row.local !== true) invalid(); }
        return row as unknown as ProductionProvider;
      });
    },
    async preview(command: MediaCommand): Promise<ProductionPreview> {
      commandScope(command);
      if (command.operation_id === 'm5.image.cutout') cutoutCommand(command);
      const v = await transport.json<unknown>(`${base}/preview`, 'POST', command);
      if (!record(v)) invalid(); scoped(v);
      recipe(v.execution_recipe, command.operation_id);
      if (v.contract !== 'studio-production-preview/1' || !hex(v.preview_digest) || !hex(v.request_digest) || v.request_id !== command.request_id || v.operation_id !== command.operation_id
        || v.product_acceptance !== 'LOCAL_REQUIRED' || v.execution_available !== true || v.automatic_dispatch !== false || v.output_policy !== 'PRIVATE_CANDIDATE_THEN_EXPLICIT_REVIEW'
        || !record(v.command) || v.command.prompt !== command.prompt || v.command.operation_id !== command.operation_id || v.command.request_id !== command.request_id
        || (v.command.provider_id ?? null) !== (command.provider_id ?? null) || (v.command.model_id ?? null) !== (command.model_id ?? null)
        || v.command.allow_cloud !== command.allow_cloud || v.command.license_note !== command.license_note || !record(v.command.parameters)
        || Object.entries(command.parameters).some(([key, value]) => (v.command as Record<string, unknown>).parameters && ((v.command as Record<string, unknown>).parameters as Record<string, unknown>)[key] !== value)
        || !Array.isArray(v.command.source_snapshots) || v.command.source_snapshots.length !== command.source_snapshots.length
        || v.command.source_snapshots.some((s, index) => !record(s) || ['id', 'kind', 'version', 'digest', 'asset_kind'].some(key => (s[key] ?? null) !== ((command.source_snapshots[index] as unknown as Record<string, unknown>)[key] ?? null)))) invalid();
      checkedImageRuntimeInputs(v.command, v.command.source_snapshots as RecordedProductionSource[], command.operation_id);
      if (!sameImageRuntimeInputs(command, v.command) || !sameVideoReference(command, v.command) || !sameStoryboardShot(command, v.command)) invalid();
      checkedImageRecipeCommand(v.execution_recipe as Record<string, unknown>, command);
      if (command.operation_id === 'm8.audio.trim') {
        const keys = ['contract', 'novel_id', 'branch_id', 'operation_id', 'request_id', 'request_digest', 'provider', 'sources', 'execution_recipe',
          'command', 'product_acceptance', 'execution_available', 'automatic_dispatch', 'output_policy', 'preview_digest'];
        if (Object.keys(v).length !== keys.length || keys.some(key => !Object.hasOwn(v, key))) invalid();
        trimCommand(v.command, true);
        trimRecipe(recipe(v.execution_recipe, command.operation_id), v.command);
        if (v.provider !== null || !sameTrimCommand(command, v.command)) invalid();
      }
      if (command.operation_id === 'm5.image.cutout') {
        cutoutCommand(v.command, true);
        const keys = ['contract', 'novel_id', 'branch_id', 'operation_id', 'request_id', 'request_digest', 'provider', 'sources', 'execution_recipe',
          'command', 'product_acceptance', 'execution_available', 'automatic_dispatch', 'output_policy', 'preview_digest'];
        if (v.provider !== null || Object.keys(v).length !== keys.length || keys.some(key => !Object.hasOwn(v, key))
          || !Array.isArray(v.sources) || v.sources.length !== 2) invalid();
        const dimensions = v.sources.map((row, index) => {
          if (!record(row) || Object.keys(row).length !== 2 || !Object.hasOwn(row, 'snapshot') || !record(row.measured)) invalid();
          sources([row.snapshot], 1);
          if (!record(row.snapshot) || ['id', 'kind', 'version', 'digest', 'asset_kind'].some(key => row.snapshot && (row.snapshot as Record<string, unknown>)[key] !== (command.source_snapshots[index] as unknown as Record<string, unknown>)[key])
            || row.snapshot.reference_only !== undefined || Object.keys(row.measured).length !== 5
            || !['media_type', 'extension', 'width', 'height', 'validation'].every(key => Object.hasOwn(row.measured as object, key))
            || row.measured.media_type !== 'image/png' || row.measured.extension !== 'png' || row.measured.validation !== 'DECODED'
            || !maskDimension(row.measured.width) || !maskDimension(row.measured.height)) invalid();
          return [row.measured.width, row.measured.height];
        });
        if (dimensions[0][0] !== dimensions[1][0] || dimensions[0][1] !== dimensions[1][1]) invalid();
      }
      if (v.provider !== null && (!record(v.provider) || v.provider.provider_id !== command.provider_id || v.provider.model_id !== command.model_id || !hex(v.provider.route_digest) || typeof v.provider.local !== 'boolean')) invalid();
      return v as unknown as ProductionPreview;
    },
    async create(command: MediaCommand, reviewed_preview_digest: string) {
      commandScope(command);
      if (command.operation_id === 'm5.image.cutout') cutoutCommand(command);
      const v = job(await transport.json<unknown>(`${base}/jobs`, 'POST', { command, reviewed_preview_digest }, undefined, command.request_id));
      if (v.request_id !== command.request_id || v.operation_id !== command.operation_id
        || !sameImageRuntimeInputs(command, v.command) || !sameVideoReference(command, v.command) || !sameStoryboardShot(command, v.command)
        || command.operation_id === 'm5.image.cutout' && !sameCutoutCommand(command, v.command)
        || command.operation_id === 'm8.audio.trim' && !sameTrimCommand(command, v.command)) invalid(); return v;
    },
    async list(signal?: AbortSignal) {
      const v = await transport.json<unknown>(`${base}/jobs`, 'GET', undefined, signal);
      if (!record(v) || !Array.isArray(v.items) || v.items.length > 1000) invalid(); return v.items.map(job);
    },
    async get(owner: ProductionOwner, id: string, signal?: AbortSignal) {
      const v = job(await transport.json<unknown>(jobUrl(owner, id), 'GET', undefined, signal)); if (v.owner !== owner || v.id !== id) invalid(); return v;
    },
    execute: (j: ProductionJob) => action(j.owner, j.id, 'execute', { expected_version: j.version, expected_request_digest: j.request_digest }, j),
    refresh: (j: ProductionJob) => action(j.owner, j.id, 'refresh', { expected_version: j.version, expected_request_digest: j.request_digest }, j),
    cancel: (j: ProductionJob) => action(j.owner, j.id, 'cancel', { expected_version: j.version, expected_request_digest: j.request_digest }, j),
    reconcile: (j: ProductionJob) => action(j.owner, j.id, 'reconcile', { expected_version: j.version, expected_request_digest: j.request_digest }, j),
    review: (j: ProductionJob) => action(j.owner, j.id, 'review', { expected_version: j.version, expected_request_digest: j.request_digest, reviewed_output_digest: j.output_candidate?.digest }, j),
    candidate: (j: ProductionJob) => transport.blob(`${jobUrl(j.owner, j.id)}/candidate`),
    async timelineList(signal?: AbortSignal) {
      const v = await transport.json<unknown>(`${base}/timelines`, 'GET', undefined, signal); if (!record(v) || !Array.isArray(v.items) || v.items.length > 25) invalid(); return { items: v.items.map(timeline) };
    },
    async timelineGet(id: string, signal?: AbortSignal) { return timeline(await transport.json<unknown>(`${base}/timelines/${encodeURIComponent(id)}`, 'GET', undefined, signal)); },
    async timelineSave(id: string | undefined, body: { title: string; timeline: StudioTimeline; expected_version: number }) {
      return timeline(await transport.json<unknown>(id ? `${base}/timelines/${encodeURIComponent(id)}` : `${base}/timelines`, id ? 'PUT' : 'POST', body));
    },
    async timelineRender(id: string, body: { expected_version: number; reviewed_timeline_digest: string; request_id: string }) {
      return job(await transport.json<unknown>(`${base}/timelines/${encodeURIComponent(id)}/render`, 'POST', body, undefined, body.request_id));
    },
    async timelinePlaybackPreview(source: StudioTimelineRow, signal?: AbortSignal): Promise<TimelinePlayback> {
      const raw = await transport.json<unknown>(`${base}/timelines/${encodeURIComponent(source.id)}/playback-preview`, 'POST', {
        expected_version: source.version, reviewed_timeline_digest: source.timeline_digest }, signal);
      return checkedTimelinePlayback(raw, source, job, { novelId: projectId, branchId: branch });
    },
    async timelinePlaybackBuild(source: StudioTimelineRow, preview: TimelinePlayback): Promise<TimelinePlayback> {
      const checked = checkedTimelinePlayback(preview, source, job, { novelId: projectId, branchId: branch });
      const raw = await transport.json<unknown>(`${base}/timelines/${encodeURIComponent(source.id)}/playback-build`, 'POST', {
        expected_version: source.version, reviewed_timeline_digest: source.timeline_digest,
        reviewed_playback_digest: checked.playback_digest }, undefined, checked.request_id);
      const result = checkedTimelinePlayback(raw, source, job, { novelId: projectId, branchId: branch });
      if (result.cache_key !== checked.cache_key || result.playback_digest !== checked.playback_digest || !result.job) invalid();
      return result;
    },
    async timelinePlaybackAttestation(source: StudioTimelineRow, preview: TimelinePlayback) {
      const checked = checkedTimelinePlayback(preview, source, job, { novelId: projectId, branchId: branch }), expected = checked.job;
      if (!expected?.output_candidate || !['SUCCEEDED', 'AWAITING_REVIEW', 'APPROVED'].includes(expected.status)) invalid();
      const proof = await transport.json<unknown>(`${base}/timelines/${encodeURIComponent(source.id)}/playback-attestation`, 'POST', {
        expected_version: source.version, reviewed_timeline_digest: source.timeline_digest, reviewed_playback_digest: checked.playback_digest,
        expected_job_version: expected.version, expected_request_digest: expected.request_digest });
      if (!record(proof) || Object.keys(proof).some(key => !['contract', 'cache_key', 'playback_digest', 'job_id', 'job_version', 'request_digest',
        'asset_version', 'sha256', 'byte_count', 'media_type', 'product_acceptance'].includes(key))
        || proof.contract !== 'studio-timeline-playback-attestation/1' || proof.cache_key !== checked.cache_key || proof.playback_digest !== checked.playback_digest
        || proof.job_id !== expected.id || proof.job_version !== expected.version || proof.request_digest !== expected.request_digest
        || proof.asset_version !== (expected.status === 'APPROVED' ? expected.approved_asset_version : expected.output_candidate.version)
        || proof.sha256 !== expected.output_candidate.digest || proof.byte_count !== expected.media_measurement?.byte_count
        || typeof proof.byte_count !== 'number' || !Number.isSafeInteger(proof.byte_count) || proof.byte_count < 1 || proof.byte_count > 25 * 1024 * 1024
        || proof.media_type !== 'video/mp4' || proof.product_acceptance !== 'LOCAL_REQUIRED') invalid();
      return { sha256: proof.sha256 as string, byte_count: proof.byte_count, asset_version: proof.asset_version as number };
    },
    async timelineExportPreview(source: StudioTimelineRow, profile: TimelineExportProfile) {
      const normalized = checkedTimelineExportProfile(profile);
      const raw = await transport.json<unknown>(`${base}/timelines/${encodeURIComponent(source.id)}/export-preview`, 'POST', {
        expected_version: source.version, reviewed_timeline_digest: source.timeline_digest, export_profile: normalized });
      const result = checkedTimelineExportPreview(raw, source, normalized), executionRecipe = recipe(result.execution_recipe, 'm9.timeline.multitrack');
      if (executionRecipe.adapter !== 'LOCAL_FFMPEG' || executionRecipe.output_profile !== normalized.preset
        || Object.keys(executionRecipe).some(key => !['contract', 'operation_id', 'adapter', 'output_profile', 'timeline', 'export_profile', 'automatic_fallback', 'recipe_digest'].includes(key))
        || JSON.stringify(checkedTimeline(executionRecipe.timeline)) !== JSON.stringify(checkedTimeline(source.timeline))
        || JSON.stringify(checkedTimelineExportProfile(executionRecipe.export_profile)) !== JSON.stringify(normalized)) invalid();
      return result;
    },
    async timelineExport(source: StudioTimelineRow, profile: TimelineExportProfile, requestId: string, reviewedExportDigest: string) {
      const result = job(await transport.json<unknown>(`${base}/timelines/${encodeURIComponent(source.id)}/export`, 'POST', {
        expected_version: source.version, reviewed_timeline_digest: source.timeline_digest, export_profile: checkedTimelineExportProfile(profile),
        request_id: requestId, reviewed_export_digest: reviewedExportDigest }, undefined, requestId));
      if (result.owner !== 'timeline' || result.request_id !== requestId || result.operation_id !== 'm9.timeline.multitrack'
        || result.timeline_snapshot?.id !== source.id || result.timeline_snapshot.version !== source.version || result.timeline_snapshot.digest !== source.timeline_digest) invalid();
      return result;
    },
    async timelineTransferPreview(source: StudioTimelineRow, body: TimelineTransferInput, signal?: AbortSignal): Promise<TimelineTransferPreview> {
      const input = checkedTimelineTransferInput(body), inputDigest = await timelineTransferInputDigest(input);
      if (input.expected_version !== source.version || input.reviewed_timeline_digest !== source.timeline_digest) invalid();
      const raw = await transport.json<unknown>(`${base}/timelines/${encodeURIComponent(source.id)}/transfer-preview`, 'POST', input, signal);
      return checkedTimelineTransferPreview(raw, source, input, inputDigest);
    },
    async timelineTransferImport(source: StudioTimelineRow, body: TimelineTransferInput, preview: TimelineTransferPreview, requestId: string, acknowledgeLosses: boolean): Promise<StudioTimelineRow> {
      const input = checkedTimelineTransferInput(body), inputDigest = await timelineTransferInputDigest(input);
      const checked = checkedTimelineTransferPreview(preview, source, input, inputDigest);
      if (input.direction !== 'IMPORT' || !/^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$/.test(requestId) || checked.requires_loss_acknowledgment && !acknowledgeLosses) invalid();
      return timeline(await transport.json<unknown>(`${base}/timelines/${encodeURIComponent(source.id)}/transfer-import`, 'POST',
        { ...input, request_id: requestId, reviewed_preview_digest: checked.preview_digest, acknowledge_losses: acknowledgeLosses }, undefined, requestId));
    },
    async timelineTransferAttachment(source: StudioTimelineRow, body: TimelineTransferInput, preview: TimelineTransferPreview, acknowledgeLosses: boolean, signal?: AbortSignal): Promise<Blob> {
      const input = checkedTimelineTransferInput(body), inputDigest = await timelineTransferInputDigest(input);
      const checked = checkedTimelineTransferPreview(preview, source, input, inputDigest);
      if (input.direction !== 'EXPORT' || checked.requires_loss_acknowledgment && !acknowledgeLosses) invalid();
      const blob = await transport.blob(`${base}/timelines/${encodeURIComponent(source.id)}/transfer-attachment`, 'POST',
        { ...input, reviewed_preview_digest: checked.preview_digest, acknowledge_losses: acknowledgeLosses }, signal);
      if (blob.size !== checked.output_bytes || blob.size > (input.format === 'OTIO' ? 2 * 1024 * 1024 : 192000)) invalid();
      const hash = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', await blob.arrayBuffer())), value => value.toString(16).padStart(2, '0')).join('');
      if (hash !== checked.output_sha256) invalid();
      return blob;
    },
    async timelineTrackLock(source: StudioTimelineRow, trackId: string, locked: boolean, requestId: string): Promise<StudioTimelineRow> {
      if (!identifier(trackId) || typeof locked !== 'boolean' || !/^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$/.test(requestId)) invalid();
      return timeline(await transport.json<unknown>(`${base}/timelines/${encodeURIComponent(source.id)}/edit`, 'POST', {
        expected_version: source.version, reviewed_timeline_digest: source.timeline_digest, request_id: requestId,
        operations: [{ op: 'track.update', track_id: trackId, changes: { locked } }],
      }, undefined, requestId));
    },
  };
}
type CompleteProductionClient = ReturnType<typeof studioProductionClient>;
type TimelineExportMethods = 'timelineExportPreview' | 'timelineExport' | 'timelineTransferPreview' | 'timelineTransferImport' | 'timelineTransferAttachment' | 'timelineTrackLock' | 'timelinePlaybackPreview' | 'timelinePlaybackBuild' | 'timelinePlaybackAttestation';
// Existing embedded clients keep their original media/render surface. Export
// controls require both additive methods before becoming available.
export type StudioProductionClient = Omit<CompleteProductionClient, TimelineExportMethods> & Partial<Pick<CompleteProductionClient, TimelineExportMethods>>;
