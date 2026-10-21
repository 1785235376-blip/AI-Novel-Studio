import type { FailedCanvasVideoOrigin } from './videoTaskRecovery';
import type { CanvasAssetReference, CanvasDefinition, CanvasViewRecord } from './studioCanvasViewClient';
import type { ProductionJob, ProductionRecipe, ProductionSource } from './studioProductionClient';
import type { StudioAsset } from './studioClient';
import type { CanvasReturnBinding } from './studioCanvasReturnBinding';
import { checkedCanvasVideoAudioOption } from './canvasVideoAudio';
import { checkedTimeline, type StudioVideoTimeline } from './studioTimelineTypes';

export type CanvasVideoSource = ProductionSource & { asset_kind: 'video'; reference_only?: never };
export type CanvasVideoReturnBinding = Omit<CanvasReturnBinding, 'source'> & { source: CanvasVideoSource };
export type CanvasVideoTrimParameters = { in_ms: number; out_ms: number; include_audio?: boolean };
export type CanvasVideoTaskCommand = {
  contract: 'studio-canvas-video-trim/1'; operation_id: 'm9.timeline.multitrack'; request_id: string;
  provider_id: null; model_id: null; prompt: ''; allow_cloud: false; license_note: '';
  parameters: CanvasVideoTrimParameters; source_snapshots: [CanvasVideoSource];
  timeline_snapshot: { id: string; version: number; digest: string }; canvas_return: CanvasVideoReturnBinding; derived_from?: FailedCanvasVideoOrigin;
};
export type CanvasVideoTaskPreview = {
  contract: 'studio-canvas-video-preview/1'; novel_id: string; branch_id: string | null;
  command: CanvasVideoTaskCommand; request_digest: string; preview_digest: string; execution_recipe: ProductionRecipe;
  execution_available: boolean; automatic_dispatch: false; product_acceptance: 'LOCAL_REQUIRED';
};
export type CanvasVideoTaskJob = ProductionJob & { canvas_video: CanvasVideoTaskCommand };
export type CanvasVideoTrimTaskOrigin = {
  projectId: string; canvasId: string; canvasVersion: number; canvasDigest: string; cardId: string;
  source: CanvasAssetReference; binding?: CanvasReturnBinding;
};
export type CanvasVideoTrimTaskBinding = {
  source: ProductionSource; returnBinding?: CanvasReturnBinding; isCurrent: () => boolean;
};

const object = (value: unknown): value is Record<string, unknown> => !!value && typeof value === 'object' && !Array.isArray(value);
const id = (value: unknown): value is string => typeof value === 'string' && /^[A-Za-z0-9][A-Za-z0-9_-]{0,239}$/.test(value);
const digest = (value: unknown): value is string => typeof value === 'string' && /^[a-f0-9]{64}$/.test(value);
const revision = (value: unknown): value is number => typeof value === 'number' && Number.isSafeInteger(value) && value >= 1;
const scopeKeys = ['mode', 'novel_id', 'workspace_id', 'project_id', 'storyline_id', 'branch_id'];
function invalid(): never { throw new Error('原视频卡片、截取命令或回执不完整或已改变，请重新读取核对。'); }
function exact(value: unknown, keys: readonly string[]): value is Record<string, unknown> {
  return object(value) && Object.keys(value).length === keys.length && keys.every(key => Object.hasOwn(value, key));
}
function same(left: unknown, right: unknown): boolean {
  if (left === right) return true;
  if (Array.isArray(left) || Array.isArray(right)) return Array.isArray(left) && Array.isArray(right)
    && left.length === right.length && left.every((value, index) => same(value, right[index]));
  if (!object(left) || !object(right)) return false;
  const a = Object.keys(left).sort(), b = Object.keys(right).sort();
  return a.length === b.length && a.every((key, index) => key === b[index] && same(left[key], right[key]));
}
const branchOf = (binding: CanvasVideoReturnBinding): string | null => binding.scope.mode === 'collaboration' ? binding.scope.branch_id! : null;
const canvasBranch = (canvas: CanvasViewRecord): string | null => canvas.scope.mode === 'collaboration' ? canvas.scope.branch_id : null;
function checkedSource(value: unknown): CanvasVideoSource {
  if (!exact(value, ['id', 'kind', 'asset_kind', 'version', 'digest']) || !id(value.id)
    || value.kind !== 'ASSET' || value.asset_kind !== 'video' || !revision(value.version) || !digest(value.digest)) invalid();
  return structuredClone(value) as CanvasVideoSource;
}
function checkedParameters(value: unknown): CanvasVideoTrimParameters {
  if (!object(value) || !Object.hasOwn(value,'in_ms') || !Object.hasOwn(value,'out_ms')
    || Object.keys(value).some(key => !['in_ms','out_ms','include_audio'].includes(key)) || typeof value.in_ms !== 'number' || typeof value.out_ms !== 'number'
    || !Number.isSafeInteger(value.in_ms) || !Number.isSafeInteger(value.out_ms)
    || value.in_ms < 0 || value.out_ms <= value.in_ms || value.out_ms > 36_000_000
    || value.out_ms - value.in_ms > 120_000 || value.in_ms % 40 !== 0 || value.out_ms % 40 !== 0) invalid();
  const audio = checkedCanvasVideoAudioOption(value);
  return { in_ms: value.in_ms, out_ms: value.out_ms, ...(audio === undefined ? {} : {include_audio:audio}) };
}

/** A video-specific additive origin parser. The old image/audio parser remains closed. */
export function checkedCanvasVideoReturnBinding(value: unknown): CanvasVideoReturnBinding {
  if (!exact(value, ['contract', 'project_id', 'scope', 'incarnation', 'canvas_id', 'canvas_version', 'canvas_digest', 'card_id', 'source'])
    || value.contract !== 'studio-canvas-return/1' || !id(value.project_id) || !id(value.canvas_id) || !id(value.card_id)
    || !revision(value.canvas_version) || !digest(value.canvas_digest) || typeof value.incarnation !== 'string'
    || !/^(?:file|postgres):[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/.test(value.incarnation)) invalid();
  const scope = value.scope;
  if (!object(scope) || Object.keys(scope).some(key => !scopeKeys.includes(key)) || scope.novel_id !== value.project_id
    || !['local', 'collaboration'].includes(String(scope.mode))
    || Object.values(scope).some(v => v !== null && (typeof v !== 'string' || !v.trim() || v.length > 240 || /[\x00-\x1f\x7f]/.test(v)))
    || scope.mode === 'collaboration' && !['workspace_id', 'storyline_id', 'branch_id'].every(key => id(scope[key]))) invalid();
  return { ...structuredClone(value), source: checkedSource(value.source) } as CanvasVideoReturnBinding;
}

/** Compile one real video clip with an explicit optional source-audio choice; no task or execution is created here. */
export function compileCanvasVideoTimeline(source: ProductionSource, parameters: CanvasVideoTrimParameters): StudioVideoTimeline {
  const pin = checkedSource(source), range = checkedParameters(parameters);
  return checkedTimeline({ schema_version: 2, duration_ms: range.out_ms - range.in_ms, width: 640, height: 360, fps: 25,
    tracks: [{ id: 'canvas-video-track', kind: 'VIDEO', order: 0, role: 'PRIMARY', muted: false, gain_db: 0,
      clips: [{ id: 'canvas-video-clip', source_snapshot: pin, start_ms: 0, ...range, x: 0, y: 0, width: 640, height: 360,
        speed_num: 1, speed_den: 1, muted: false, gain_db: 0, fade_in_ms: 0, fade_out_ms: 0, opacity: 1, include_audio: range.include_audio === true }] }],
    captions: [] }) as StudioVideoTimeline;
}

export function checkedCanvasVideoTaskCommand(value: unknown): CanvasVideoTaskCommand {
  if (!exact(value, ['contract', 'operation_id', 'request_id', 'provider_id', 'model_id', 'prompt', 'allow_cloud', 'license_note',
    'parameters', 'source_snapshots', 'timeline_snapshot', 'canvas_return', ...(object(value)&&Object.hasOwn(value,'derived_from')?['derived_from']:[])]) || value.contract !== 'studio-canvas-video-trim/1'
    || value.operation_id !== 'm9.timeline.multitrack' || typeof value.request_id !== 'string' || !/^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$/.test(value.request_id)
    || value.provider_id !== null || value.model_id !== null || value.prompt !== '' || value.allow_cloud !== false || value.license_note !== '') invalid();
  if(Object.hasOwn(value,'derived_from')){
    const parent=value.derived_from;
    if(!exact(parent,['owner','job_id','job_version','request_id','request_digest','receipt_digest'])||parent.owner!=='timeline'
      ||!id(parent.job_id)||!revision(parent.job_version)||typeof parent.request_id!=='string'||!/^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$/.test(parent.request_id)
      ||parent.request_id===value.request_id||!digest(parent.request_digest)||parent.receipt_digest!==null&&!digest(parent.receipt_digest))invalid();
  }
  const origin = checkedCanvasVideoReturnBinding(value.canvas_return), parameters = checkedParameters(value.parameters);
  if (!Array.isArray(value.source_snapshots) || value.source_snapshots.length !== 1) invalid();
  const source = checkedSource(value.source_snapshots[0]), snapshot = value.timeline_snapshot;
  if (!same(source, origin.source) || !exact(snapshot, ['id', 'version', 'digest']) || !id(snapshot.id)
    || !revision(snapshot.version) || !digest(snapshot.digest)) invalid();
  return { ...structuredClone(value), canvas_return: origin, parameters, source_snapshots: [source] } as CanvasVideoTaskCommand;
}

function checkedRecipe(value: unknown, command: CanvasVideoTaskCommand): ProductionRecipe {
  if (!exact(value, ['contract', 'operation_id', 'adapter', 'output_profile', 'timeline', 'export_profile', 'automatic_fallback', 'recipe_digest'])
    || value.contract !== 'studio-execution-recipe/1' || value.operation_id !== command.operation_id || value.adapter !== 'LOCAL_FFMPEG'
    || value.output_profile !== 'DELIVERY_H264_MP4' || value.automatic_fallback !== false || !digest(value.recipe_digest)
    || !exact(value.export_profile, ['preset', 'video_bitrate_kbps', 'audio_bitrate_kbps', 'crf'])
    || value.export_profile.preset !== 'DELIVERY_H264_MP4' || value.export_profile.video_bitrate_kbps !== 400
    || value.export_profile.audio_bitrate_kbps !== 96 || value.export_profile.crf !== 23
    || !same(value.timeline, compileCanvasVideoTimeline(command.source_snapshots[0], command.parameters))) invalid();
  return structuredClone(value) as ProductionRecipe;
}

export function checkedCanvasVideoTaskPreview(value: unknown, expectedCommand: CanvasVideoTaskCommand): CanvasVideoTaskPreview {
  const expected = checkedCanvasVideoTaskCommand(expectedCommand);
  if (!exact(value, ['contract', 'novel_id', 'branch_id', 'command', 'request_digest', 'preview_digest', 'execution_recipe',
    'execution_available', 'automatic_dispatch', 'product_acceptance']) || value.contract !== 'studio-canvas-video-preview/1'
    || value.novel_id !== expected.canvas_return.project_id || value.branch_id !== branchOf(expected.canvas_return)
    || !digest(value.request_digest) || !digest(value.preview_digest) || typeof value.execution_available !== 'boolean'
    || value.automatic_dispatch !== false || value.product_acceptance !== 'LOCAL_REQUIRED') invalid();
  const command = checkedCanvasVideoTaskCommand(value.command);
  if (!same(command, expected)) invalid();
  return { ...structuredClone(value), command, execution_recipe: checkedRecipe(value.execution_recipe, command) } as CanvasVideoTaskPreview;
}

/** Additional congruence checks over the original Job projection, not another client. */
export function checkedCanvasVideoTaskJob(value: unknown): CanvasVideoTaskJob {
  if (!object(value) || value.contract !== 'studio-production-job/1' || value.owner !== 'timeline'
    || value.operation_id !== 'm9.timeline.multitrack' || value.command !== null || value.provider !== null
    || !id(value.id) || !revision(value.version) || !digest(value.request_digest)
    || value.receipt_digest !== null && !digest(value.receipt_digest)
    || typeof value.created_at !== 'string' || typeof value.updated_at !== 'string'
    || value.product_acceptance !== 'LOCAL_REQUIRED' || value.automatic_replay !== false || value.remote_compute_may_continue !== false
    || typeof value.status !== 'string' || !['QUEUED', 'RUNNING', 'SUCCEEDED', 'REVIEWING',
      'APPROVED', 'UNKNOWN', 'FAILED', 'CANCELLED'].includes(value.status)) invalid();
  const command = checkedCanvasVideoTaskCommand(value.canvas_video);
  if (value.request_id !== command.request_id || value.novel_id !== command.canvas_return.project_id
    || value.branch_id !== branchOf(command.canvas_return) || !same(value.timeline_snapshot, command.timeline_snapshot)
    || !same(value.sources, command.source_snapshots)) invalid();
  checkedRecipe(value.execution_recipe, command);
  const candidate = value.output_candidate, measurement = value.media_measurement;
  if (candidate !== null && (!exact(candidate, ['id', 'version', 'digest', 'kind']) || !id(candidate.id)
    || !revision(candidate.version) || !digest(candidate.digest) || candidate.kind !== 'video')) invalid();
  if (value.status === 'QUEUED' && (candidate !== null || measurement !== null)) invalid();
  if (['SUCCEEDED', 'APPROVED'].includes(value.status) && candidate === null) invalid();
  if (candidate !== null || measurement !== null) {
    if (!object(measurement) || measurement.duration_ms !== command.parameters.out_ms - command.parameters.in_ms
      || measurement.width !== 640 || measurement.height !== 360 || measurement.fps !== 25 || measurement.video_codec !== 'h264'
      || measurement.audio_codec !== 'aac' || measurement.container !== 'mp4' || measurement.sample_rate !== 48000 || measurement.channels !== 2
      || measurement.profile_validation !== 'NATIVE_FFPROBE_EXACT' || measurement.render_profile !== 'STUDIO_MULTITRACK_LOCAL_FFMPEG_DELIVERY_H264_MP4'
      || !revision(measurement.byte_count) || !same(measurement.export_profile,
        { preset: 'DELIVERY_H264_MP4', video_bitrate_kbps: 400, audio_bitrate_kbps: 96, crf: 23 })) invalid();
  }
  if (value.approved_asset_version !== null && !revision(value.approved_asset_version)
    || value.status === 'APPROVED' && (!revision(value.approved_asset_version) || !object(candidate)
      || value.approved_asset_version <= Number(candidate.version))) invalid();
  return structuredClone(value) as CanvasVideoTaskJob;
}

export function canvasVideoTrimTaskSource(reference: CanvasAssetReference): CanvasVideoSource {
  if (reference.kind !== 'video') invalid();
  return checkedSource({ id: reference.asset_id, kind: 'ASSET', asset_kind: 'video', version: reference.version, digest: reference.digest });
}

export function captureCanvasVideoTrimTask(canvas: CanvasViewRecord, cardId: string, asset: StudioAsset,
  incarnation?: string): CanvasVideoTrimTaskOrigin & { binding?: CanvasVideoReturnBinding } {
  const card = canvas.definition.cards.find(row => row.id === cardId), state = canvas.reference_states.find(row => row.card_id === cardId);
  if (!card?.asset || state?.state !== 'CURRENT_METADATA' || card.asset.kind !== 'video' || asset.kind !== 'video' || asset.deleted_at
    || asset.novel_id !== canvas.project_id || (asset.branch_id ?? null) !== canvasBranch(canvas) || asset.id !== card.asset.asset_id
    || asset.version !== card.asset.version || asset.sha256 !== card.asset.digest) invalid();
  const binding = incarnation === undefined ? undefined : checkedCanvasVideoReturnBinding({ contract: 'studio-canvas-return/1',
    project_id: canvas.project_id, scope: canvas.scope, incarnation, canvas_id: canvas.id, canvas_version: canvas.version,
    canvas_digest: canvas.definition_digest, card_id: cardId, source: canvasVideoTrimTaskSource(card.asset) });
  return { projectId: canvas.project_id, canvasId: canvas.id, canvasVersion: canvas.version, canvasDigest: canvas.definition_digest,
    cardId, source: { ...card.asset }, ...(binding ? { binding } : {}) };
}

export function assertCanvasVideoTrimTaskTarget(origin: CanvasVideoTrimTaskOrigin, canvas: CanvasViewRecord, incarnation?: string) {
  const binding = origin.binding && checkedCanvasVideoReturnBinding(origin.binding);
  if (!binding || incarnation !== undefined && binding.incarnation !== incarnation
    || origin.source.kind !== 'video' || origin.projectId !== canvas.project_id || origin.canvasId !== canvas.id
    || origin.canvasVersion !== canvas.version || origin.canvasDigest !== canvas.definition_digest
    || !same(canvas.definition.cards.find(card => card.id === origin.cardId)?.asset, origin.source)
    || canvas.reference_states.find(row => row.card_id === origin.cardId)?.state !== 'CURRENT_METADATA'
    || binding && (binding.project_id !== origin.projectId || binding.canvas_id !== origin.canvasId
      || binding.canvas_version !== origin.canvasVersion || binding.canvas_digest !== origin.canvasDigest || binding.card_id !== origin.cardId
      || !same(binding.source, canvasVideoTrimTaskSource(origin.source)) || !same(binding.scope, canvas.scope))) invalid();
}

export function canvasVideoTaskJobMatches(task: CanvasVideoTrimTaskBinding, value: ProductionJob): boolean {
  try {
    if (!task.isCurrent()) return false;
    const job = checkedCanvasVideoTaskJob(value);
    return !!task.returnBinding && same(checkedSource(task.source), job.canvas_video.source_snapshots[0])
      && same(checkedCanvasVideoReturnBinding(task.returnBinding), job.canvas_video.canvas_return);
  } catch { return false; }
}

export function replaceCanvasVideoTrimTaskResult(origin: CanvasVideoTrimTaskOrigin, canvas: CanvasViewRecord,
  value: ProductionJob, asset: StudioAsset, incarnation?: string): CanvasDefinition {
  assertCanvasVideoTrimTaskTarget(origin, canvas, incarnation);
  const job = checkedCanvasVideoTaskJob(value);
  if (!canvasVideoTaskJobMatches({ source: canvasVideoTrimTaskSource(origin.source), returnBinding: origin.binding, isCurrent: () => true }, job)
    || job.status !== 'APPROVED' || !job.output_candidate || job.novel_id !== origin.projectId || job.branch_id !== canvasBranch(canvas)
    || asset.id !== job.output_candidate.id || asset.version !== job.approved_asset_version || asset.sha256 !== job.output_candidate.digest
    || asset.kind !== 'video' || asset.media_type !== 'video/mp4' || asset.deleted_at || asset.novel_id !== origin.projectId
    || (asset.branch_id ?? null) !== canvasBranch(canvas)) invalid();
  return { ...canvas.definition, cards: canvas.definition.cards.map(card => card.id === origin.cardId
    ? { ...card, asset: { asset_id: asset.id, version: asset.version, digest: asset.sha256, kind: 'video' as const } } : card) };
}
