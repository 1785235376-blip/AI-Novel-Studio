import type { CanvasAssetReference, CanvasDefinition, CanvasViewRecord } from './studioCanvasViewClient';
import type { MediaCommand, ProductionJob, ProductionSource, RecordedMediaCommand } from './studioProductionClient';
import type { StudioAsset } from './studioClient';
import { checkedCanvasReturnBinding, sameCanvasReturn, type CanvasReturnBinding } from './studioCanvasReturnBinding';

/** Presentation over the immutable return intent kept by the original AudioJob. */
export type CanvasAudioTrimTaskOrigin = {
  projectId: string; canvasId: string; canvasVersion: number; canvasDigest: string;
  cardId: string; source: CanvasAssetReference; binding?: CanvasReturnBinding;
};
export type CanvasAudioTrimTaskBinding = {
  source: ProductionSource; returnBinding?: CanvasReturnBinding; isCurrent: () => boolean;
};
export type CanvasAudioTrimTaskSession = {
  id: string; origin: CanvasAudioTrimTaskOrigin; asset: StudioAsset;
  isOriginCurrent: () => boolean; resumeJob?: ProductionJob;
};

const WAV_PROFILE = 'PCM_S16LE_WAV_48000_STEREO';
const commandKeys = new Set(['operation_id', 'request_id', 'provider_id', 'model_id', 'prompt',
  'parameters', 'source_snapshots', 'allow_cloud', 'license_note', 'canvas_return']);
const object = (v: unknown): v is Record<string, unknown> => !!v && typeof v === 'object' && !Array.isArray(v);
const canonical = (value: unknown) => JSON.stringify(value, (_key, v) => object(v)
  ? Object.fromEntries(Object.entries(v).sort(([a], [b]) => a.localeCompare(b))) : v);
const same = (a: unknown, b: unknown) => canonical(a) === canonical(b);
const exactSource = (sources: RecordedMediaCommand['source_snapshots'], source: ProductionSource) =>
  source.kind === 'ASSET' && source.asset_kind === 'audio' && sources.length === 1
  && sources[0].kind === 'ASSET' && sources[0].asset_kind === 'audio'
  && sources[0].id === source.id && sources[0].version === source.version && sources[0].digest === source.digest;

function trimCommandMatches(task: CanvasAudioTrimTaskBinding, command: RecordedMediaCommand): boolean {
  const p = command.parameters;
  if (command.operation_id !== 'm8.audio.trim' || command.prompt !== '' || command.provider_id != null
    || command.model_id != null || command.allow_cloud !== false
    || Object.keys(command).some(key => !commandKeys.has(key))
    || !object(p) || Object.keys(p).length !== 2 || !Object.hasOwn(p, 'in_ms') || !Object.hasOwn(p, 'out_ms')
    || !Number.isSafeInteger(p.in_ms) || !Number.isSafeInteger(p.out_ms)
    || (p.in_ms as number) < 0 || (p.out_ms as number) <= (p.in_ms as number)
    || (p.out_ms as number) - (p.in_ms as number) > 120_000
    || !exactSource(command.source_snapshots, task.source)) return false;
  if (!task.returnBinding) return command.canvas_return === undefined;
  return sameCanvasReturn({ ...command, canvas_return: task.returnBinding }, command);
}

export function canvasAudioTrimTaskSource(reference: CanvasAssetReference): ProductionSource {
  if (reference.kind !== 'audio') throw new Error('本片仅接受已保存的音频卡片。');
  return { id: reference.asset_id, kind: 'ASSET', version: reference.version, digest: reference.digest, asset_kind: 'audio' };
}

export function captureCanvasAudioTrimTask(canvas: CanvasViewRecord, cardId: string, asset: StudioAsset,
  incarnation?: string): CanvasAudioTrimTaskOrigin {
  const card = canvas.definition.cards.find(row => row.id === cardId);
  const state = canvas.reference_states.find(row => row.card_id === cardId);
  if (!card?.asset || state?.state !== 'CURRENT_METADATA' || card.asset.kind !== 'audio' || asset.kind !== 'audio'
    || asset.deleted_at || asset.novel_id !== canvas.project_id
    || (asset.branch_id ?? null) !== (canvas.scope.branch_id ?? null)
    || asset.id !== card.asset.asset_id || asset.version !== card.asset.version || asset.sha256 !== card.asset.digest) {
    throw new Error('原卡片音频版本不可用，请重新读取。');
  }
  const binding = incarnation === undefined ? undefined : checkedCanvasReturnBinding({
    contract: 'studio-canvas-return/1', project_id: canvas.project_id, scope: canvas.scope, incarnation,
    canvas_id: canvas.id, canvas_version: canvas.version, canvas_digest: canvas.definition_digest,
    card_id: cardId, source: canvasAudioTrimTaskSource(card.asset),
  });
  return { projectId: canvas.project_id, canvasId: canvas.id, canvasVersion: canvas.version,
    canvasDigest: canvas.definition_digest, cardId, source: { ...card.asset }, ...(binding ? { binding } : {}) };
}

export function assertCanvasAudioTrimTaskTarget(origin: CanvasAudioTrimTaskOrigin, canvas: CanvasViewRecord) {
  const binding = origin.binding && checkedCanvasReturnBinding(origin.binding);
  if (origin.source.kind !== 'audio' || canvas.project_id !== origin.projectId || canvas.id !== origin.canvasId
    || canvas.version !== origin.canvasVersion || canvas.definition_digest !== origin.canvasDigest
    || binding && (binding.project_id !== origin.projectId || binding.canvas_id !== origin.canvasId
      || binding.canvas_version !== origin.canvasVersion || binding.canvas_digest !== origin.canvasDigest
      || binding.card_id !== origin.cardId || !same(binding.source, canvasAudioTrimTaskSource(origin.source))
      || !same(canvas.scope, binding.scope))
    || canvas.reference_states.find(row => row.card_id === origin.cardId)?.state !== 'CURRENT_METADATA'
    || !same(canvas.definition.cards.find(row => row.id === origin.cardId)?.asset, origin.source)) {
    throw new Error('原画布、卡片或音频版本已改变；不会回填当前选中的其他位置。');
  }
}

export function assertCanvasAudioTrimTaskCommand(task: CanvasAudioTrimTaskBinding, command: MediaCommand) {
  if (!task.isCurrent()) throw new Error('原作品位置已改变，请返回创作画布重新建立任务。');
  if (!trimCommandMatches(task, command)) {
    throw new Error('此卡片任务仅支持原音频的本地 WAV 截取，请核对开始与结束时间。');
  }
}

export function canvasAudioTrimTaskJobMatches(task: CanvasAudioTrimTaskBinding, job: ProductionJob): boolean {
  try {
    return job.owner === 'audio' && job.operation_id === 'm8.audio.trim' && job.provider === null
      && !!job.command && trimCommandMatches(task, job.command) && exactSource(job.sources, task.source)
      && job.execution_recipe.contract === 'studio-execution-recipe/1'
      && job.execution_recipe.operation_id === 'm8.audio.trim' && job.execution_recipe.adapter === 'LOCAL_FFMPEG'
      && job.execution_recipe.automatic_fallback === false && job.execution_recipe.output_profile === WAV_PROFILE
      && same(job.execution_recipe.parameters, job.command.parameters);
  } catch {
    return false;
  }
}

export function replaceCanvasAudioTrimTaskResult(origin: CanvasAudioTrimTaskOrigin, canvas: CanvasViewRecord,
  job: ProductionJob, asset: StudioAsset): CanvasDefinition {
  assertCanvasAudioTrimTaskTarget(origin, canvas);
  if (job.novel_id !== origin.projectId || (job.branch_id ?? null) !== (canvas.scope.branch_id ?? null)
    || job.status !== 'APPROVED' || !canvasAudioTrimTaskJobMatches({
      source: canvasAudioTrimTaskSource(origin.source), returnBinding: origin.binding, isCurrent: () => true,
    }, job) || !job.output_candidate || job.output_candidate.kind !== 'audio'
    || asset.id !== job.output_candidate.id || asset.version !== job.approved_asset_version
    || asset.sha256 !== job.output_candidate.digest || asset.kind !== 'audio' || asset.media_type !== 'audio/wav'
    || asset.deleted_at || asset.novel_id !== origin.projectId
    || (asset.branch_id ?? null) !== (canvas.scope.branch_id ?? null)) {
    throw new Error('正式审核结果、原音频任务来源或素材版本未通过核验，未改变作品位置。');
  }
  return { ...canvas.definition, cards: canvas.definition.cards.map(card => card.id === origin.cardId
    ? { ...card, asset: { asset_id: asset.id, version: asset.version, digest: asset.sha256, kind: 'audio' as const } } : card) };
}
