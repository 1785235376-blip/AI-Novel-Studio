import {audioDraftIdentity,canvasAudioDraftCommand,canvasAudioDraftFromCommand,compileCanvasAudioDraftTimeline} from './studioCanvasAudioDraft';
import type {StudioTimelineRow} from './studioTimelineTypes';
import type {AudioDraftSummary} from './audioDraftRecovery';
import { checkedCanvasAudioProvenance, type FailedCanvasAudioOrigin, type CanvasAudioWorkflowTemplateRef } from './studioCanvasAudioProvenance';
import { deriveFailedCanvasAudioCommand } from './taskRecovery';
import type { StudioGraphDraftOwner } from './studioGraphLocalDraft';
import type { StudioGraphRecord } from './studioGraphTypes';
import { canonicalExecutionImpact, type ExecutionImpactConfirmation } from '../experimental/executionImpact/executionImpact';
import { studioExecutionImpactGate, sameExecutionPreview, type StudioExecutionImpactGate, type StudioExecutionImpactInput } from './studioExecutionImpactGate';
import { sameCompositeCommand } from './studioImageCompositeContract';
import { checkedCanvasAudioTaskEnvelope } from './canvasAudioTaskEnvelope';
import { assertCanvasAudioTrimTaskCommand, canvasAudioTrimTaskJobMatches, type CanvasAudioTrimTaskBinding } from './canvasAudioTrimTask';
import { assertCanvasImageTaskCommand, canvasImageTaskJobMatches, type CanvasImageTaskBinding } from './canvasImageTask';
import { useStudioProductionLeaveRisk, type StudioProductionLeaveGuard } from './studioProductionLeaveRisk';
import { sameComicImageCommand } from './studioComicImageContract';
import { CUTOUT_WEBP_PROFILE } from './studioCutoutContract';
import { AUDIO_DENOISE_PROFILE, validDenoiseParameters } from './studioAudioDenoiseContract';
import { sameStoryboardSpeech } from './studioStoryboardSpeechContract';
import { exactHandoffAsset, type TimelineAssetHandoff } from './StudioTimelineAssetHandoff';
import { AUDIO_MP3_PROFILE, AUDIO_MP3_SAMPLE_RATES } from './studioProductionClient';
import { checkedVideoReference, type VideoReference } from './studioVideoRuntimeContract';
import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { ApiError, apiErrorView } from '../api';
import type { StudioAsset } from './studioClient';
import { eligibleCutoutMask, usableCutoutSource } from './studioCutoutContract';
import { checkedImageReferenceMetadata, checkedImageRuntimeInputs, type ImageReference, type ImageReferencePurpose } from './studioImageRuntimeContract';
import type { GraphImageOperation, GraphMediaOperation } from './studioGraphTypes';
import type { MediaCommand, RecordedMediaCommand, MediaOperation, ProductionJob, ProductionPreview, ProductionProvider, ProductionSource, StudioProductionClient } from './studioProductionClient';

export type StudioMediaExecutionProps = {
  leaveGuard?: StudioProductionLeaveGuard;
  assetHandoff?: TimelineAssetHandoff & { target?: 'IMAGE' | 'VIDEO' };
  client: StudioProductionClient; assets: StudioAsset[]; canMutate: boolean; canReview: boolean; busy: boolean; isBusy?: () => boolean;
  isCurrent: () => boolean; read: <T>(work: () => Promise<T>) => Promise<T>; mutate: <T>(work: () => Promise<T>) => Promise<T>;
  onDirtyChange: (dirty: boolean) => void; onJob?: (job: ProductionJob) => void; onUnavailable: () => void; onApproved?: (job: ProductionJob) => void | Promise<void>;
  /** Optional single-card task fence. It owns no execution, storage or queue. */
  canvasImageTask?: CanvasImageTaskBinding;
  canvasAudioTrimTask?: CanvasAudioTrimTaskBinding;
  audioWorkflowTemplates?: { owner:StudioGraphDraftOwner; list:()=>Promise<StudioGraphRecord[]>; read:(id:string)=>Promise<StudioGraphRecord> };
  /** Explicit read-only navigation; never grants review or execution authority. */
  onOpenApprovedAsset?: (job: ProductionJob) => void;
  externalJob?: ProductionJob;
  preparedCommand?: RecordedMediaCommand; preparedIsCurrent?: () => boolean; onPreparedClose?: () => void;
  cutoutExecution?: { execute: (job: ProductionJob, authorize: () => void) => Promise<ProductionJob>; control: (kind: 'read' | 'cancel', job: ProductionJob) => Promise<ProductionJob> };
};
const boundTask = (props: StudioMediaExecutionProps) => props.canvasAudioTrimTask ?? props.canvasImageTask;
const canvasTaskJobMatches = (task: CanvasImageTaskBinding, job: ProductionJob) => task.source.asset_kind==='audio'
  ? canvasAudioTrimTaskJobMatches(task,job) : canvasImageTaskJobMatches(task,job);
export const GRAPH_MEDIA_OPERATION_LABELS: Record<GraphMediaOperation, string> = {
  'm5.image.t2i': '文字生成图片', 'm5.image.i2i': '参考图片生成图片', 'm7.video.t2v': '文字生成视频',
  'm7.video.i2v': '图片生成视频', 'm7.video.v2v': '视频生成视频', 'm8.audio.speech': '语音合成',
  'm8.audio.music': '音乐生成', 'm8.audio.effects': '音效生成', 'm8.audio.trim': '本地音频截取',
};
export const GRAPH_IMAGE_OPERATION_LABELS: Record<GraphImageOperation, string> = {
  'm5.image.t2i': '文字生成图片', 'm5.image.i2i': '参考图片生成图片',
  'm5.image.reference': '多参考图生成图片', 'm5.image.inpaint': '图片局部重绘',
};
export const MEDIA_OPERATION_LABELS: Record<MediaOperation, string> = { ...GRAPH_MEDIA_OPERATION_LABELS, ...GRAPH_IMAGE_OPERATION_LABELS, 'm5.image.upscale': '本地模型图片超分', 'm5.image.cutout': '本地二值遮罩抠图', 'm5.image.composite': '本地双层 PNG 合成' };
export const MEDIA_STATUS_LABELS: Record<ProductionJob['status'], string> = {
  QUEUED: '已入队，尚未执行', RUNNING: '正在执行', SEND_RESERVED: '已记录分派意图', REMOTE_RUNNING: '远端处理中',
  RESULT_READY: '已有结果，等待本地核对', AWAITING_REVIEW: '等待人工审核', SUCCEEDED: '处理完成，需核对审核',
  REVIEWING: '审核提交待核对', APPROVED: '已审核入库', UNKNOWN: '分派结果不确定', FAILED: '执行失败', CANCELLED: '已丢弃本地结果',
};
export type MediaParameter = 'scale' | 'width' | 'height' | 'steps' | 'seed' | 'negative_prompt' | 'size' | 'quality' | 'denoising_strength' | 'duration_seconds' | 'frame_rate' | 'voice_id' | 'speech_rate' | 'in_ms' | 'out_ms' | 'gain_db' | 'sample_rate' | 'channels' | 'output_format' | 'fade_in_ms' | 'fade_out_ms' | 'target_peak_dbfs' | 'target_lufs' | 'denoise_profile' | 'cutout_output';
type MediaRoute = 'local' | 'cloud';
const routeSelectable = (operation: MediaOperation) => (operation.startsWith('m5.image.') || operation.startsWith('m7.video.')) && !['m5.image.cutout', 'm5.image.upscale', 'm5.image.composite'].includes(operation);
type Draft = { requestId?:string; derived_from?:FailedCanvasAudioOrigin; template_ref?:CanvasAudioWorkflowTemplateRef; route: MediaRoute; operation: MediaOperation; providerKey: string; prompt: string; parameters: Record<MediaParameter, string>; sources: ProductionSource[]; allowCloud: boolean; licenseNote: string;
  layerSettings?: Record<string, { visible: boolean; opacity: string }>;
  imageSource?: ProductionSource; imageReferences: { source: ProductionSource; weight: string; purpose?: ImageReferencePurpose; source_note?: string }[]; maskSource?: ProductionSource; videoReferencePurpose?: VideoReference['purpose']; lastFrame?: ProductionSource };
type Preview = { value: ProductionPreview; command: MediaCommand; input: string };
type Candidate = { url: string; kind: 'image' | 'video' | 'audio'; binding: string };
type Kind = 'DRAFT_SAVE' | 'DRAFT_GET' | 'DRAFT_LIST' | 'PREVIEW' | 'CREATE' | 'LIST' | 'GET' | 'CANDIDATE' | 'execute' | 'refresh' | 'reconcile' | 'cancel' | 'review';
type Operation = { id: number; kind: Kind; client: StudioProductionClient; controller: AbortController; canMutate: boolean; canReview: boolean };
type Creation = { requestId: string; requestDigest: string; operation: MediaOperation; input: string; uncertain: boolean };
const parameterNames: MediaParameter[] = ['scale', 'width', 'height', 'steps', 'seed', 'negative_prompt', 'size', 'quality', 'denoising_strength', 'duration_seconds', 'frame_rate', 'voice_id', 'speech_rate', 'in_ms', 'out_ms', 'gain_db', 'sample_rate', 'channels', 'output_format', 'fade_in_ms', 'fade_out_ms', 'target_peak_dbfs', 'target_lufs', 'denoise_profile', 'cutout_output'];
const parametersByOperation: Record<MediaOperation, MediaParameter[]> = {
  'm5.image.t2i': ['width', 'height', 'steps', 'seed', 'negative_prompt', 'size', 'quality'],
  'm5.image.i2i': ['width', 'height', 'steps', 'seed', 'negative_prompt', 'size', 'quality', 'denoising_strength'],
  'm5.image.reference': ['width', 'height', 'steps', 'seed', 'negative_prompt', 'size', 'quality', 'denoising_strength'],
  'm5.image.inpaint': ['width', 'height', 'steps', 'seed', 'negative_prompt', 'size', 'quality', 'denoising_strength'],
  'm5.image.composite': [], 'm5.image.cutout': ['cutout_output'], 'm5.image.upscale': ['scale'],
  'm7.video.t2v': ['width', 'height', 'seed', 'negative_prompt', 'duration_seconds', 'frame_rate'],
  'm7.video.i2v': ['width', 'height', 'seed', 'negative_prompt', 'duration_seconds', 'frame_rate'],
  'm7.video.v2v': ['width', 'height', 'seed', 'negative_prompt', 'duration_seconds', 'frame_rate'],
  'm8.audio.speech': ['voice_id', 'speech_rate'], 'm8.audio.music': ['duration_seconds', 'seed'],
  'm8.audio.effects': ['duration_seconds', 'seed'], 'm8.audio.trim': ['in_ms', 'out_ms', 'gain_db', 'sample_rate', 'channels', 'output_format', 'fade_in_ms', 'fade_out_ms', 'target_peak_dbfs', 'target_lufs', 'denoise_profile'],
};
const initialDraft = (task?: CanvasImageTaskBinding): Draft => ({ route: 'local', operation: task ? task.source.asset_kind==='audio'?'m8.audio.trim':'m5.image.i2i' : 'm5.image.t2i', providerKey: '', prompt: '',
  parameters: Object.fromEntries(parameterNames.map(name => [name, ''])) as Record<MediaParameter, string>, sources: task ? [{...task.source}] : [],
  ...(task?.source.asset_kind==='image' ? {imageSource:{...task.source}} : {}), imageReferences: [], allowCloud: false, licenseNote: '' });
const inputKey = (draft: Draft) => JSON.stringify(draft);
export const mediaProviderKey = (row: ProductionProvider) => JSON.stringify([row.operation_id, row.provider_id, row.model_id, row.route_digest]);
const jobIdentity = (job?: ProductionJob) => job ? JSON.stringify([job.owner, job.id, job.version, job.request_digest]) : '';
const actionIdentity = (job: ProductionJob, kind: string) => JSON.stringify([jobIdentity(job), kind]);
const reviewIdentity = (job?: ProductionJob) => job?.output_candidate
  ? JSON.stringify([jobIdentity(job), job.output_candidate.id, job.output_candidate.version, job.output_candidate.digest]) : '';
const uncertainFailure = (error: unknown) => !(error instanceof ApiError) || error.status === 0 || error.status >= 500 || [408, 409, 425, 429].includes(error.status) || error.problem.code === 'STUDIO_RESPONSE_INVALID';
const invalid = (message: string) => new ApiError({ status: 200, code: 'STUDIO_RESPONSE_INVALID', message });
function sourceKind(operation: MediaOperation): 'image' | 'video' | 'audio' | undefined {
  return ({ 'm5.image.i2i': 'image', 'm5.image.reference': 'image', 'm5.image.inpaint': 'image', 'm5.image.upscale': 'image', 'm5.image.cutout': 'image', 'm5.image.composite': 'image', 'm7.video.i2v': 'image', 'm7.video.v2v': 'video', 'm8.audio.trim': 'audio' } as Partial<Record<MediaOperation, 'image' | 'video' | 'audio'>>)[operation];
}
function usableAsset(row: StudioAsset, kind: string) {
  return row.kind === kind && !row.deleted_at && Number.isSafeInteger(row.version) && row.version >= 1 && /^[a-f0-9]{64}$/.test(row.sha256);
}
const imageSnapshot = (row: StudioAsset): ProductionSource => ({ id: row.id, kind: 'ASSET', version: row.version, digest: row.sha256, asset_kind: 'image' });
function imageSources(draft: Draft): ProductionSource[] {
  const inputs = [draft.imageSource, ...draft.imageReferences.map(reference => reference.source), draft.maskSource].filter((row): row is ProductionSource => !!row);
  return inputs.filter((row, index) => inputs.findIndex(value => value.id === row.id) === index);
}
// Shared insertion policy for the original reference picker and explicit asset handoff.
function appendImageReference(old: Draft, asset: StudioAsset, provider?: ProductionProvider, handoff = false): Draft {
  if (!provider?.image_capabilities) throw new Error('请明确选择支持当前图片参考操作的服务商配置。');
  if (handoff && (provider.operation_id !== old.operation || mediaProviderKey(provider) !== old.providerKey
    || provider.capability !== 'IMAGE' || provider.local !== (old.route === 'local'))) throw new Error('请明确选择支持当前图片参考操作的服务商配置。');
  if (!usableAsset(asset, 'image') || asset.manual_mask) throw new Error('参考素材不可用，请重新读取素材。');
  if (asset.id === old.imageSource?.id) throw new Error('基础图不能同时作为辅助参考，请选择不同素材。');
  if (handoff && (old.maskSource || old.operation === 'm5.image.reference' && old.imageSource)) throw new Error('已有基础图或遮罩绑定；请先用原输入控件调整。');
  if (handoff && (old.sources.some(source => source.id === asset.id) || old.imageReferences.some(reference => reference.source.id === asset.id))) throw new Error('此素材已绑定；请使用原输入控件明确移除或调整，不会覆盖已有绑定。');
  if (handoff && JSON.stringify(old.sources) !== JSON.stringify(imageSources(old))) throw new Error('当前输入无法安全追加；请先用原输入控件调整。');
  const limit = old.operation === 'm5.image.i2i' ? Math.min(4, Math.max(0, provider.image_capabilities.reference_limit - 1)) : handoff ? Math.min(5, provider.image_capabilities.reference_limit) : provider.image_capabilities.reference_limit;
  if ((handoff && !Number.isSafeInteger(limit)) || old.imageReferences.length >= limit) throw new Error('参考图数量超过当前路线的上限。');
  const next = { ...old, imageReferences: [...old.imageReferences, { source: imageSnapshot(asset), weight: '1' }], allowCloud: false };
  return { ...next, sources: imageSources(next) };
}
function sourcesCurrent(originalSources: (ProductionSource | RecordedMediaCommand['source_snapshots'][number])[], assets: StudioAsset[], operation?: string) {
  const sources = originalSources.filter((source): source is ProductionSource => source.kind === 'ASSET');
  if (operation === 'm5.image.cutout') {
    const source = assets.find(row => row.id === sources[0]?.id), mask = assets.find(row => row.id === sources[1]?.id);
    if (sources.length !== 2 || !source || !mask || !eligibleCutoutMask(mask, source)) return false;
  }
  if (operation === 'm5.image.inpaint') {
    const base = assets.find(row => row.id === sources[0]?.id), mask = assets.find(row => row.id === sources[1]?.id);
    if (sources.length !== 2 || !base || !mask || !eligibleCutoutMask(mask, base)) return false;
  }
  return sources.every(source => assets.some(row => usableAsset(row, source.asset_kind) && row.id === source.id && row.version === source.version && row.sha256 === source.digest));
}
function parameters(draft: Draft): MediaCommand['parameters'] {
  const result: MediaCommand['parameters'] = {};
  const ranges: Partial<Record<MediaParameter, [number, number]>> = { width: [64, 2048], height: [64, 2048], steps: [1, 150], seed: [0, 2147483647], duration_seconds: [1, 600], frame_rate: [1, 60], in_ms: [0, 600000], out_ms: [1, 600000], sample_rate: [8000, 96000], channels: [1, 2], fade_in_ms: [0, 120000], fade_out_ms: [0, 120000] };
  for (const name of parametersByOperation[draft.operation]) {
    const value = draft.parameters[name]; if (value === '') continue;
    if (name === 'cutout_output') { if (value !== CUTOUT_WEBP_PROFILE) throw new Error('请选择已有的无损 WebP 配方。'); result[name] = value; }
    else if (name === 'denoise_profile') { if (value !== AUDIO_DENOISE_PROFILE) throw new Error('请选择已有的本地降噪配方。'); result[name] = value; }
    else if (name === 'output_format') { if (value !== 'FLAC' && value !== 'MP3') throw new Error('独立音频格式请选择 FLAC 或 MP3，或留空保留默认 WAV。'); result[name] = value; }
    else if (name === 'negative_prompt') { if (value.length > 8000) throw new Error('负向提示超过长度限制。'); result[name] = value; }
    else if (name === 'voice_id') { if (value.length > 240 || !value.trim() || /[\x00-\x1f\x7f]/.test(value)) throw new Error('请填写有效的语音标识。'); result[name] = value; }
    else if (name === 'size') { if (!['auto', '1024x1024', '1536x1024', '1024x1536'].includes(value)) throw new Error('图片规格不受支持。'); result[name] = value; }
    else if (name === 'quality') { if (!['auto', 'low', 'medium', 'high', 'standard', 'hd'].includes(value)) throw new Error('图片质量不受支持。'); result[name] = value; }
    else if (name === 'scale') { if (value !== '2' && value !== '4') throw new Error('超分倍率须明确选择 2 或 4。'); result[name] = Number(value); }
    else if (name === 'target_lufs') {
      const number = Number(value); if (!/^-?(?:\d+(?:\.\d+)?|\.\d+)$/.test(value) || !Number.isFinite(number) || number < -30 || number > -14) throw new Error('目标综合响度须为 -30 至 -14 LUFS。'); result[name] = number;
    }
    else if (name === 'target_peak_dbfs') {
      const number = Number(value); if (!/^-?(?:\d+(?:\.\d+)?|\.\d+)$/.test(value) || !Number.isFinite(number) || number < -24 || number > -1) throw new Error('目标采样峰值须为 -24 至 -1 dBFS。'); result[name] = number;
    }
    else if (name === 'gain_db') {
      const number = Number(value); if (!/^-?(?:\d+(?:\.\d+)?|\.\d+)$/.test(value) || !Number.isFinite(number) || number < -60 || number > 12) throw new Error('增益须为 -60 至 12 dB 之间的有限数值。'); result[name] = number;
    }
    else if (name === 'denoising_strength') {
      const number = Number(value); if (!/^(?:\d+(?:\.\d+)?|\.\d+)$/.test(value) || !Number.isFinite(number) || number <= 0 || number > 1) throw new Error('重绘强度须大于 0 且不超过 1。'); result[name] = number;
    }
    else if (name === 'speech_rate') {
      const number = Number(value); if (!/^(?:\d+(?:\.\d+)?|\.\d+)$/.test(value) || !Number.isFinite(number) || number < 0.5 || number > 2) throw new Error('语速须在 0.5 至 2 之间。'); result[name] = number;
    } else {
      const number = Number(value), range = ranges[name];
      if (!/^\d+$/.test(value) || !Number.isSafeInteger(number) || !range || number < range[0] || number > range[1]) throw new Error('请核对参数范围并填写有限整数。');
      if (draft.operation.startsWith('m5.') && ['width', 'height'].includes(name) && number % 8 !== 0) throw new Error('图片宽高须为 8 的倍数。');
      result[name] = number;
    }
  }
  if (result.denoise_profile !== undefined && !validDenoiseParameters(result)) throw new Error('降噪须为至少 1 秒的 PCM16 WAV，不能同时设置格式转换、归一化、非零增益或淡入淡出。');
  if (result.target_lufs !== undefined && (Number(result.out_ms) - Number(result.in_ms) < 3000 || result.target_peak_dbfs !== undefined
    || result.output_format !== undefined || ['gain_db', 'fade_in_ms', 'fade_out_ms'].some(key => Number(result[key] ?? 0) !== 0))) throw new Error('响度匹配须为至少 3 秒的 PCM16 WAV，不能同时设置峰值目标、非零手动增益或淡入淡出。');
  if (result.target_peak_dbfs !== undefined) {
    if (result.output_format !== undefined) throw new Error('峰值归一化目前仅支持 PCM16 WAV 输出。');
    if (Number(result.target_peak_dbfs) + Number(result.gain_db ?? 0) > -1) throw new Error('目标采样峰值加手动增益须不高于 -1 dBFS。');
  }
  if ((result.width === undefined) !== (result.height === undefined)) throw new Error('宽高需同时填写或同时留空。');
  if (draft.operation === 'm5.image.upscale' && result.scale !== 2 && result.scale !== 4) throw new Error('先明确选择 2 倍或 4 倍超分。');
  if (draft.operation === 'm8.audio.trim' && (typeof result.in_ms !== 'number' || typeof result.out_ms !== 'number' || result.out_ms <= result.in_ms || result.out_ms - result.in_ms > 120000)) throw new Error('截取需填写起止毫秒，终点须大于起点，片段最长 120 秒。');
  if (draft.operation === 'm8.audio.trim' && Number(result.fade_in_ms ?? 0) + Number(result.fade_out_ms ?? 0) > Number(result.out_ms) - Number(result.in_ms)) throw new Error('淡入与淡出时长之和不能超过截取片段时长。');
  if (draft.operation === 'm8.audio.trim' && Math.ceil(((result.out_ms as number) - (result.in_ms as number)) * Number(result.sample_rate ?? 48000) / 1000) * Number(result.channels ?? 2) * 2 + 4096 > 25 * 1024 * 1024) throw new Error('所选时长、采样率和声道预计超过 25 MiB 输出上限，请调整后重新预览。');
  if (result.output_format === 'MP3' && Number(result.out_ms) - Number(result.in_ms) < 10) throw new Error('MP3 片段至少 10 毫秒，以保留准确的解码时长。');
  if (result.output_format === 'MP3' && !AUDIO_MP3_SAMPLE_RATES.includes(Number(result.sample_rate ?? 48000))) throw new Error('MP3 采样率仅支持 8000、11025、12000、16000、22050、24000、32000、44100、48000 Hz；请明确修改，不会自动重采样。');
  return result;
}
function commandFor(draft: Draft, providers: ProductionProvider[], assets: StudioAsset[], requestId: string, task?: CanvasImageTaskBinding): MediaCommand {
  const cutout = draft.operation === 'm5.image.cutout', localTrim = draft.operation === 'm8.audio.trim' || cutout || draft.operation === 'm5.image.composite';
  const provider = providers.find(row => mediaProviderKey(row) === draft.providerKey && row.operation_id === draft.operation);
  if (provider && routeSelectable(draft.operation) && provider.local !== (draft.route === 'local')) throw new Error('请在所选本地或云端路线中明确选择配置。');
  if (!localTrim && !provider) throw new Error('请选择当前配置中的服务商和模型。');
  if (provider && parametersByOperation[draft.operation].some(name => draft.parameters[name] !== '' && !provider.supported_parameters.includes(name))) throw new Error('所选配置不支持部分已填写参数，请明确清空这些参数或恢复原选择。');
  const upscale = draft.operation === 'm5.image.upscale';
  if (!localTrim && !upscale && (!draft.prompt.trim() || draft.prompt.length > 16000)) throw new Error('请填写本次提示词，最多 16000 字符。');
  if (upscale && provider?.local !== true) throw new Error('超分需要当前明确启用的本地服务。');
  if (provider && !provider.local && !draft.allowCloud) throw new Error('使用云端服务前，请明确确认本次发送提示词与参考素材。');
  const kind = sourceKind(draft.operation), baseSources = draft.sources;
  if (draft.lastFrame) {
    if (draft.operation !== 'm7.video.i2v') throw new Error('只有图片生成视频可绑定首帧与尾帧。');
    if (!provider?.video_frame_capabilities?.end_frame) throw new Error('当前配置不支持尾帧；请选择支持首尾帧的配置，不会静默丢弃尾帧或降级为单图。');
    if (!baseSources.length) throw new Error('请先选择首帧，再选择尾帧。');
    if (baseSources[0].id === draft.lastFrame.id) throw new Error('首帧与尾帧不能是同一张图片。');
  }
  const sources = draft.operation === 'm7.video.i2v' && draft.lastFrame ? [baseSources[0], draft.lastFrame] : baseSources;
  const frameCount = draft.operation === 'm7.video.i2v' ? (draft.lastFrame ? 2 : 1) : undefined;
  if (cutout && sources.length !== 2) throw new Error('请先选择一张 PNG 来源，再明确选择为该版本绘制的二值遮罩。');
  if (!sourcesCurrent(sources, assets, draft.operation)) throw new Error('来源素材版本已变化，请重新选取当前版本。');
  const rich = upscale || draft.operation === 'm5.image.reference' || draft.operation === 'm5.image.inpaint' || draft.imageSource !== undefined || draft.imageReferences.length > 0;
  if (kind && (!sources.length || sources.some(source => source.asset_kind !== kind) || (draft.operation === 'm5.image.i2i' ? sources.length > 5
    : draft.operation === 'm5.image.reference' ? sources.length > 5 : sources.length !== (frameCount ?? (cutout || draft.operation === 'm5.image.composite' || draft.operation === 'm5.image.inpaint' ? 2 : 1))))) throw new Error(kind === 'image' ? '请选取对应数量的图片来源。' : '请选取一个对应类型的来源素材。');
  if (!kind && sources.length) throw new Error('本操作不接收素材参考。');
  if (draft.licenseNote.length > 2000) throw new Error('来源与授权说明超过长度限制。');
  let image: { image_source?: ProductionSource; image_references?: ImageReference[]; mask_source?: ProductionSource } = {};
  if (rich) {
    if (!provider?.image_capabilities) throw new Error('当前路线没有已核对的图片输入契约，请明确选择支持对应操作的配置。');
    if (draft.imageReferences.length + (draft.imageSource ? 1 : 0) > provider.image_capabilities.reference_limit) throw new Error('基础图与参考图的总数超过当前路线的上限。');
    const references = draft.imageReferences.map(reference => {
      const weight = Number(reference.weight);
      if (!/^(?:\d+(?:\.\d+)?|\.\d+)$/.test(reference.weight) || !Number.isFinite(weight) || weight <= 0 || weight > 1) throw new Error('参考图权重须大于 0 且不超过 1。');
      return { source: reference.source, weight, ...checkedImageReferenceMetadata(reference, true) };
    });
    image = checkedImageRuntimeInputs({ ...(draft.imageSource ? { image_source: draft.imageSource } : {}),
      ...(references.length ? { image_references: references } : {}), ...(draft.maskSource ? { mask_source: draft.maskSource } : {}) }, sources, draft.operation, true);
    if (draft.operation === 'm5.image.inpaint' && provider.image_capabilities.mask_semantics !== 'WHITE_KEEP_BLACK_REPAINT') throw new Error('当前路线未提供本手绘遮罩的保留／重绘契约。');
  }
  const chosenParameters = parameters(draft);
  const command: MediaCommand = { operation_id: draft.operation, request_id: requestId, provider_id: localTrim ? null : provider!.provider_id,
    model_id: localTrim ? null : provider!.model_id, prompt: localTrim || upscale ? '' : draft.prompt, parameters: chosenParameters,
    ...(draft.operation === 'm8.audio.trim' && chosenParameters.output_format === 'MP3' ? { audio_profile: AUDIO_MP3_PROFILE } : {}),
    ...(draft.operation === 'm5.image.composite' ? { image_layers: sources.map(source => {
      const control = draft.layerSettings?.[source.id] ?? { visible: true, opacity: '255' };
      if (!/^\d+$/.test(control.opacity) || !Number.isSafeInteger(Number(control.opacity)) || Number(control.opacity) > 255) throw new Error('层透明度须为 0–255 整数。');
      const asset = assets.find(row => row.id === source.id);
      if (!asset || !usableCutoutSource(asset)) throw new Error('叠层仅接受每张不超过 8 MiB 的已保存 PNG。');
      return { source: { ...source }, visible: control.visible, opacity: Number(control.opacity) };
    }) } : {}),
    source_snapshots: sources.map(source => ({ ...source })), allow_cloud: localTrim || upscale ? false : draft.allowCloud, license_note: draft.licenseNote, ...image,
    ...(draft.operation === 'm7.video.i2v' && draft.lastFrame ? { video_frames: [
      { role: 'FIRST' as const, source: { ...sources[0] } },
      { role: 'LAST' as const, source: { ...sources[1] } },
    ] } : {}),
    ...checkedVideoReference(draft.videoReferencePurpose ? { source: sources[0], purpose: draft.videoReferencePurpose } : undefined, sources, draft.operation) };
  if(task?.returnBinding)command.canvas_return=structuredClone(task.returnBinding);
  if(draft.derived_from)command.derived_from=structuredClone(draft.derived_from);
  if(draft.template_ref)command.template_ref=structuredClone(draft.template_ref);
  if(task){if(task.source.asset_kind==='audio')assertCanvasAudioTrimTaskCommand(task,command);else assertCanvasImageTaskCommand(task,command,provider);}
  return command;
}

/** Draft, exact receipts and private media lifetime remain independent of rendering. */
export function useStudioMediaExecution(props: StudioMediaExecutionProps) {
  const [handoffAsset, setHandoffAsset] = useState<{ asset: StudioAsset; request: TimelineAssetHandoff; revision: number }>();
  const [handoffPending, setHandoffPending] = useState(false), [handoffNotice, setHandoffNotice] = useState('');
  const handoffFlight = useRef(false), handoffConsumed = useRef<TimelineAssetHandoff>();
  const handoffRevision = useRef(0), handoffStamp = useRef(''), handoffRequest = useRef(props.assetHandoff);
  const [savedAudioDraft,setSavedAudioDraft]=useState<{row:StudioTimelineRow;input:string}>();
  const audioSaveUnknown=useRef(false);
  const audioInputRevision=useRef(0);
  const audioReadSet=useRef<{authority:object;stamp:string;revision:number;methods:unknown[];entries:Map<string,{summary:string;draft:string}>}>();
  const audioMethods=useRef<{list:()=>Promise<AudioDraftSummary[]>;resume:(v:AudioDraftSummary)=>Promise<void>;current:()=>boolean}>();
  const audioCallbacks=useRef({onList:()=>audioMethods.current!.list(),onResume:(v:AudioDraftSummary)=>audioMethods.current!.resume(v),isCurrent:()=>audioMethods.current!.current()});
  const [draft, setDraft] = useState<Draft>(()=>initialDraft(boundTask(props))), [providers, setProviders] = useState<ProductionProvider[]>([]);
  const [providerLoading, setProviderLoading] = useState(false), [jobs, setJobs] = useState<ProductionJob[]>([]), [selected, setSelected] = useState<ProductionJob>();
  const [preview, setPreview] = useState<Preview>(), [previewConsent, setPreviewConsent] = useState(''), [reviewConsent, setReviewConsent] = useState('');
  const [candidate, setCandidate] = useState<Candidate>(), [pending, setPending] = useState<Kind>(), [uncertain, setUncertain] = useState(false);
  const [runningControl, setRunningControl] = useState<'read' | 'cancel'>();
  const runningControlRef = useRef<'read' | 'cancel'>(), executingCutout = useRef<ProductionJob>(), controlFence = useRef(0);
  const [denied, setDenied] = useState(false), [error, setError] = useState(''), [notice, setNotice] = useState('');
  const latest = useRef(props); latest.current = props;
  const alive = useRef(true), revoked = useRef(false), owner = useRef(props.client), epoch = useRef(0), slot = useRef<Operation>();
  const providerHandoffLoading = useRef(false);
  const providerEpoch = useRef(0), providerRead = useRef<AbortController>(), candidateRef = useRef<Candidate>();
  const draftRef = useRef(draft), selectedRef = useRef(selected), previewRef = useRef(preview), uncertainRef = useRef(uncertain);
  const previewConsentRef = useRef(previewConsent), reviewConsentRef = useRef(reviewConsent), providersRef = useRef(providers);
  const creation = useRef<Creation>(), baseline = useRef(inputKey(initialDraft(boundTask(props))));
  const sentActions = useRef(new Set<string>()), consumedExternal = useRef('');
  const impactState = useRef<{ stamp: string; client: StudioProductionClient; methods: unknown[]; canMutate: boolean; canReview: boolean; gate?: StudioExecutionImpactGate }>();
  const impactReadRevision = useRef(0);
  const executionPreview = useRef<{ jobId: string; preview: ProductionPreview }>();
  const [, updateImpact] = useState(0);
  const receiptDownload = useRef<string>(), receiptTimer = useRef<ReturnType<typeof setTimeout>>();
  draftRef.current = draft; selectedRef.current = selected; previewRef.current = preview; uncertainRef.current = uncertain;
  previewConsentRef.current = previewConsent; reviewConsentRef.current = reviewConsent; providersRef.current = providers;
  const preparedOwner = useRef(JSON.stringify(props.preparedCommand));
  const preparedCurrent = () => preparedOwner.current === JSON.stringify(latest.current.preparedCommand) && (!latest.current.preparedCommand || latest.current.preparedIsCurrent?.() === true);
  const current = () => preparedCurrent() && alive.current && !revoked.current && owner.current === latest.current.client && latest.current.isCurrent();
  const busy = () => !!slot.current || !!runningControlRef.current || latest.current.busy || !!latest.current.isBusy?.() || !current();
  const owns = preparedCurrent() && !denied && owner.current === props.client && props.isCurrent();
  const input = inputKey(draft);
  const materialSources = draft.operation === 'm7.video.i2v' && draft.lastFrame ? [draft.sources[0], draft.lastFrame].filter(Boolean) : draft.sources;
  const freshSources = sourcesCurrent(materialSources, props.assets, draft.operation);
  const sourceState = JSON.stringify(materialSources.map(source => { const row = props.assets.find(asset => asset.id === source.id); return [source.id, row?.version, row?.sha256, row?.deleted_at, row?.kind, row?.manual_mask, row?.provenance]; }));
  const jobSources = selected?.sources.filter((source): source is ProductionSource => source.kind === 'ASSET') || [];
  const jobSourcesFresh = sourcesCurrent(jobSources, props.assets, selected?.operation_id);
  const jobSourceState = JSON.stringify(jobSources.map(source => { const row = props.assets.find(asset => asset.id === source.id); return [source.id, row?.version, row?.sha256, row?.deleted_at, row?.kind, row?.manual_mask, row?.provenance]; }));
  const provider = providers.find(row => mediaProviderKey(row) === draft.providerKey && row.operation_id === draft.operation);
  const unsupportedParameters = provider ? parametersByOperation[draft.operation].filter(name => draft.parameters[name] !== '' && !provider.supported_parameters.includes(name)) : [];
  const previewBinding = preview && preview.input === input && freshSources ? JSON.stringify([input, preview.value.preview_digest, preview.value.request_digest]) : '';
  const reviewBinding = reviewIdentity(selected), candidateVisible = owns && candidate?.binding === reviewBinding && jobSourcesFresh ? candidate : undefined;
  const repeatBlocked = !!selected && ['execute', 'refresh', 'reconcile', 'cancel', 'review'].some(kind => sentActions.current.has(actionIdentity(selected, kind)));
  const dirty = owns && (input !== baseline.current || uncertain || repeatBlocked || !!pending && ['CREATE', 'DRAFT_SAVE', 'review', 'execute', 'refresh', 'reconcile', 'cancel'].includes(pending));
  const locked = !owns || props.busy || !!runningControl || !!pending || !!props.isBusy?.();
  const canEdit = !locked && props.canMutate && !uncertain && !creation.current?.uncertain;
  const incomingAsset = props.assets.find(row => row.id === props.assetHandoff?.reference.asset_id);
  const incomingAssetState = incomingAsset && [incomingAsset.id, incomingAsset.version, incomingAsset.sha256, incomingAsset.kind, incomingAsset.deleted_at, incomingAsset.manual_mask, incomingAsset.provenance];
  const nextHandoffStamp = JSON.stringify([incomingAssetState, input, canEdit, props.canMutate, props.canReview, owns, providerLoading, providers, sourceState, jobIdentity(selected), pending, props.preparedCommand]);
  if (handoffStamp.current !== nextHandoffStamp || handoffRequest.current !== props.assetHandoff) {
    handoffStamp.current = nextHandoffStamp; handoffRequest.current = props.assetHandoff; handoffRevision.current++;
  }
  const canClosePrepared = canEdit && (!selected || !['UNKNOWN', 'RUNNING', 'SEND_RESERVED', 'REMOTE_RUNNING', 'RESULT_READY', 'REVIEWING'].includes(selected.status));
  let inputError = ''; try { if (!props.preparedCommand) commandFor(draft, providers, props.assets, draft.requestId ?? (draft.derived_from?.request_id==='shape_check'?'shape_check_2':'shape_check'),boundTask(props)); } catch (reason) { inputError = reason instanceof Error ? reason.message : '请核对输入。'; }

  // Single-use confirmation for original, explicitly bound media-card tasks.
  const impactRequired = () => !!boundTask(latest.current) || !!previewRef.current?.command.canvas_return || !!selectedRef.current?.command?.canvas_return;
  function impactInput(): StudioExecutionImpactInput | undefined {
    const task = boundTask(latest.current), binding = task?.returnBinding, saved = previewRef.current, job = selectedRef.current;
    if (!task || !binding) return;
    const scope = { novel_id: binding.project_id, branch_id: binding.scope.mode === 'collaboration' ? binding.scope.branch_id : null, incarnation: binding.incarnation };
    if (saved && saved.input === inputKey(draftRef.current)) return { scope, command: saved.command, recipe: saved.value.execution_recipe,
      ...(job ? { previousJob: job } : {}), editScope: 'TASK', boundary: {kind:'CREATE'}, preview: saved.value };
    const stored = executionPreview.current;
    if (job?.status === 'QUEUED' && job.command && stored?.jobId === job.id && sameExecutionPreview(job, stored.preview)) return {
      scope, command: job.command, recipe: job.execution_recipe, previousJob: job, editScope:'TASK',
      boundary:{kind:'EXECUTE',job:{id:job.id,owner:job.owner,version:job.version,request_digest:job.request_digest}}, preview:stored.preview };
  }
  function impactStamp() {
    return canonicalExecutionImpact({revision:impactReadRevision.current,input:impactInput() ?? null,draft:draftRef.current,task:boundTask(latest.current)?.returnBinding ?? null,
      assets:latest.current.assets,providers:providersRef.current});
  }
  function impactAuthority() {
    const task = boundTask(latest.current);
    return current() && latest.current.canMutate && !uncertainRef.current
      && !['UNKNOWN','SEND_RESERVED','RUNNING','REMOTE_RUNNING','REVIEWING'].includes(selectedRef.current?.status ?? '') && !!task?.isCurrent()
      && sourcesCurrent(draftRef.current.sources,latest.current.assets,draftRef.current.operation);
  }
  let stamp = ''; try { stamp = impactStamp(); } catch { /* Invalid inputs remain blocked. */ }
  const impactMethods = () => [latest.current.client.preview,latest.current.client.create,latest.current.client.execute,latest.current.client.get];
  const oldImpact = impactState.current;
  if (!oldImpact || oldImpact.stamp !== stamp || oldImpact.client !== props.client || oldImpact.methods.some((v,i)=>v!==impactMethods()[i]) || oldImpact.canMutate !== props.canMutate || oldImpact.canReview !== props.canReview) {
    oldImpact?.gate?.retire();
    const value = {stamp,client:props.client,methods:impactMethods(),canMutate:props.canMutate,canReview:props.canReview,gate:undefined as StudioExecutionImpactGate|undefined};
    impactState.current = value;
    const target = impactInput();
    if (target && stamp) value.gate = studioExecutionImpactGate(target,impactInput,()=> impactState.current===value
      && latest.current.client===value.client && value.methods.every((v,i)=>v===impactMethods()[i]) && latest.current.canMutate===value.canMutate && latest.current.canReview===value.canReview
      && impactAuthority() && impactStamp()===value.stamp);
  }
  const impact = impactState.current?.gate;
  async function confirmImpact(gate: StudioExecutionImpactGate, proof: ExecutionImpactConfirmation) {
    if (impactState.current?.gate !== gate || busy()) return;
    if (await gate.confirm(proof)) { if (impactState.current?.gate===gate) updateImpact(v=>v+1); }
  }
  function impactReady(kind:'CREATE'|'EXECUTE') {
    if (!impactRequired()) return true;
    const gate = impactState.current?.gate; return gate?.input.boundary.kind===kind && gate.ready();
  }
  function consumeImpact(kind:'CREATE'|'EXECUTE',gate?:StudioExecutionImpactGate) {
    if (!impactRequired() && !gate) return;
    if (!impactRequired() || !gate || impactState.current?.gate!==gate || gate.input.boundary.kind!==kind || !gate.consume()) {
      throw new ApiError({status:422,code:'STUDIO_EXECUTION_IMPACT_RETIRED',message:'本次输入核对已失效或已使用，请重新读取预览并明确确认；没有再次派发。'});
    }
  }

  const leaveGuard = useStudioProductionLeaveRisk(props.leaveGuard, () => {
    const attempt = creation.current, job = selectedRef.current;
    const unknown = !!attempt?.uncertain || uncertainRef.current || job?.status === 'UNKNOWN'
      || !!slot.current && ['CREATE', 'execute', 'refresh', 'reconcile', 'cancel', 'review'].includes(slot.current.kind);
    return { unknown, requests: !unknown ? [] : [
      ...(attempt?.uncertain ? [{ requestId: attempt.requestId, owner: attempt.operation.startsWith('m5.') ? 'image' : attempt.operation.startsWith('m7.') ? 'video' : 'audio', operationId: attempt.operation }] : []),
      ...(job ? [{ requestId: job.request_id, owner: job.owner, operationId: job.operation_id }] : []),
    ] };
  });

  function clearReceiptDownload() { if (receiptTimer.current !== undefined) clearTimeout(receiptTimer.current); receiptTimer.current = undefined;
    if (receiptDownload.current) URL.revokeObjectURL(receiptDownload.current); receiptDownload.current = undefined; }
  function clearCandidate() { clearReceiptDownload(); if (candidateRef.current) URL.revokeObjectURL(candidateRef.current.url); candidateRef.current = undefined; setCandidate(undefined); reviewConsentRef.current = ''; setReviewConsent(''); }
  function clearPreview() { previewRef.current = undefined; previewConsentRef.current = ''; setPreview(undefined); setPreviewConsent(''); }
  function markUncertain(value: boolean) { handoffRevision.current++; uncertainRef.current = value; setUncertain(value); }
  function unavailable() {
    leaveGuard?.capture();
    if (!alive.current) return;
    revoked.current = true; epoch.current++; providerEpoch.current++; slot.current?.controller.abort(); slot.current = undefined; providerRead.current?.abort();
    clearCandidate(); clearPreview(); selectedRef.current = undefined; setSelected(undefined); setJobs([]); setProviders([]); setPending(undefined); providerHandoffLoading.current = false; setProviderLoading(false);
    const empty = initialDraft(boundTask(latest.current)); audioInputRevision.current++; draftRef.current = empty; setDraft(empty); creation.current = undefined; baseline.current = inputKey(empty);
    setDenied(true); setError('身份、权限或项目入口已经变化，请重新打开当前项目。'); latest.current.onDirtyChange(false); latest.current.onUnavailable();
  }
  function failure(reason: unknown, fallback: string, mutation = false) {
    if (reason instanceof ApiError && [401, 403, 404, 410, 501].includes(reason.status)) { unavailable(); return; }
    setError(apiErrorView(reason, fallback).message);
    if (mutation && uncertainFailure(reason)) { markUncertain(true); clearCandidate(); clearPreview(); }
  }
  function begin(kind: Kind): Operation | undefined {
    if (busy()) return;
    handoffRevision.current++;
    const value = { id: ++epoch.current, kind, client: latest.current.client, controller: new AbortController(), canMutate: latest.current.canMutate, canReview: latest.current.canReview };
    slot.current = value; setPending(kind); setError(''); setNotice(''); return value;
  }
  const live = (value: Operation) => current() && slot.current?.id === value.id && epoch.current === value.id && value.client === latest.current.client
    && value.canMutate === latest.current.canMutate && value.canReview === latest.current.canReview && !value.controller.signal.aborted;
  function finish(value: Operation) { if (slot.current?.id === value.id) { slot.current = undefined; if (alive.current) setPending(undefined); } }
  function adoptJob(value: ProductionJob) {
    if (jobIdentity(value) !== jobIdentity(selectedRef.current)) clearCandidate();
    selectedRef.current = value; setSelected(value); setJobs(rows => [value, ...rows.filter(row => row.owner !== value.owner || row.id !== value.id)]);
    reviewConsentRef.current = ''; setReviewConsent('');
    try { latest.current.onJob?.(value); } catch { setError('已读取原任务回执，关联视图刷新未完成。'); }
  }
  function edit(next: Draft) {
    if (latest.current.preparedCommand || !current() || busy() || !latest.current.canMutate || uncertainRef.current || creation.current?.uncertain) return;
    handoffRevision.current++; audioInputRevision.current++; draftRef.current = next; setDraft(next); clearPreview(); if (!creation.current?.uncertain) creation.current = undefined; setError(''); setNotice('');
  }
  function prepareFailedAudio(command:MediaCommand) {
    const task=latest.current.canvasAudioTrimTask,job=selectedRef.current;
    if(!task||!job||!canClosePrepared||!current()||busy()||!latest.current.canMutate||uncertainRef.current||creation.current?.uncertain)return;
    // The module's callback carries no authority; recompute against the selected original receipt.
    const expected=deriveFailedCanvasAudioCommand(job,task,command.request_id);
    if(canonicalExecutionImpact(expected)!==canonicalExecutionImpact(command))throw invalid('失败派生输入已改变。');
    const next=initialDraft(task);
    for(const [key,value] of Object.entries(command.parameters))next.parameters[key as MediaParameter]=String(value);
    next.licenseNote=command.license_note;next.requestId=command.request_id;
    next.derived_from=structuredClone(command.derived_from!);if(command.template_ref)next.template_ref=structuredClone(command.template_ref);
    edit(next);setSavedAudioDraft(undefined);clearCandidate();selectedRef.current=undefined;setSelected(undefined);
    setNotice('已准备新身份的派生草稿，保留原失败记录；仍需重新预览、逐阶段确认和人工审核。');
  }
  // These callbacks only recover inputs. Every create/execute still uses the original proof gate.
  function audioDraftCurrent(){const p=latest.current;let valid=false;try{valid=current()&&!!p.canvasAudioTrimTask&&p.canvasAudioTrimTask.isCurrent()&&!p.preparedCommand;}catch{}if(!valid){audioAuthority.current.retired=true;audioReadSet.current=undefined;}return valid;}
  const audioAuthorityValues=[props.client,props.client.timelineList,props.client.timelineGet,props.client.timelineSave,props.read,props.mutate,props.isCurrent,props.canMutate,props.busy,props.canvasAudioTrimTask,JSON.stringify(props.canvasAudioTrimTask)];
  const audioAuthority=useRef({values:audioAuthorityValues,retired:false});
  if(audioAuthorityValues.some((v,i)=>!Object.is(v,audioAuthority.current.values[i]))){audioAuthority.current.retired=true;audioAuthority.current={values:audioAuthorityValues,retired:false};}
  function audioStateStamp(){const p=latest.current,t=p.canvasAudioTrimTask;return audioDraftIdentity([inputKey(draftRef.current),t?.source,t?.returnBinding,
    t&&p.assets.filter(a=>a.id===t.source.id).map(a=>[a.id,a.version,a.sha256,a.deleted_at,a.kind])]);}
  function audioCapture(op:Operation){return {op,authority:audioAuthority.current,stamp:audioStateStamp(),revision:audioInputRevision.current,
    methods:[op.client.timelineList,op.client.timelineGet,op.client.timelineSave,latest.current.read,latest.current.mutate]};}
  function audioLive(c:ReturnType<typeof audioCapture>){const p=latest.current;const m=[p.client.timelineList,p.client.timelineGet,p.client.timelineSave,p.read,p.mutate];
    return live(c.op)&&audioDraftCurrent()&&!p.busy&&!p.isBusy?.()&&c.authority===audioAuthority.current&&!c.authority.retired&&c.stamp===audioStateStamp()&&c.revision===audioInputRevision.current&&c.methods.every((v,i)=>v===m[i]);}
  function audioSummary(row:StudioTimelineRow):AudioDraftSummary|undefined{
    const d=row.canvas_audio_draft,t=latest.current.canvasAudioTrimTask;if(!d||!t||!row.canvas_audio_draft_digest||d.timeline_snapshot.id!==row.id||d.timeline_snapshot.version!==row.version||d.timeline_snapshot.digest!==row.timeline_digest
      ||audioDraftIdentity(d.canvas_return)!==audioDraftIdentity(t.returnBinding))return;
    const v=d.parameters;
    return {id:row.id,title:row.title,version:row.version,timelineDigest:row.timeline_digest,draftDigest:row.canvas_audio_draft_digest,requestId:d.request_id,
      sourceId:d.source_snapshots[0].id,sourceVersion:d.source_snapshots[0].version,canvasId:d.canvas_return.canvas_id,canvasVersion:d.canvas_return.canvas_version,cardId:d.canvas_return.card_id,inMs:v.in_ms,outMs:v.out_ms,
      ...(v.gain_db!==undefined?{gainDb:v.gain_db}:{}),...(v.fade_in_ms!==undefined?{fadeInMs:v.fade_in_ms}:{}),...(v.fade_out_ms!==undefined?{fadeOutMs:v.fade_out_ms}:{}),
      ...(d.template_ref?{templateGraphId:d.template_ref.graph_id,templateVersion:d.template_ref.graph_version}:{}),...(d.derived_from?{parentJobId:d.derived_from.job_id,parentJobVersion:d.derived_from.job_version}:{})};
  }
  async function listAudioDrafts():Promise<AudioDraftSummary[]>{
    if(!audioDraftCurrent()||busy()||providerHandoffLoading.current)return [];if(audioAuthority.current.retired)audioAuthority.current={values:audioAuthorityValues,retired:false};const op=begin('DRAFT_LIST');if(!op)return [];const captured=audioCapture(op);
    try{const rows=await latest.current.read(()=>op.client.timelineList(op.controller.signal));if(!audioLive(captured))return [];
      const summaries=rows.items.map(audioSummary).filter((v):v is AudioDraftSummary=>!!v);
      if(new Set(summaries.map(v=>v.id)).size!==summaries.length)throw invalid('音频草稿列表存在重复记录。');
      audioReadSet.current={authority:captured.authority,stamp:captured.stamp,revision:captured.revision,methods:captured.methods,entries:new Map(summaries.map(summary=>[summary.id,{summary:audioDraftIdentity(summary),draft:audioDraftIdentity(rows.items.find(row=>row.id===summary.id)!.canvas_audio_draft)}]))};
      return summaries;
    }catch(reason){if(audioLive(captured))failure(reason,'已保存音频草稿读取失败。');throw reason;}finally{finish(op);}
  }
  async function saveAudioDraft(){
    if(!audioDraftCurrent()||busy()||!latest.current.canMutate||selectedRef.current||uncertainRef.current||creation.current?.uncertain||!sourcesCurrent(draftRef.current.sources,latest.current.assets,'m8.audio.trim'))return;
    const task=latest.current.canvasAudioTrimTask!;
    let value;try{const request=draftRef.current.requestId??crypto.randomUUID();const command=commandFor(draftRef.current,providersRef.current,latest.current.assets,request,task);value=canvasAudioDraftFromCommand(command);
      edit({...draftRef.current,requestId:request});}catch(reason){failure(reason,'当前仅支持已应用的截取、增益与淡入淡出输入草稿。');return;}
    if(audioAuthority.current.retired)audioAuthority.current={values:audioAuthorityValues,retired:false};
    const op=begin('DRAFT_SAVE');if(!op)return;const captured=audioCapture(op),before=savedAudioDraft;
    try{const row=await latest.current.mutate(()=>op.client.timelineSave(before?.row.id,{title:before?.row.title??'音频卡片任务草稿',timeline:compileCanvasAudioDraftTimeline(value),expected_version:before?.row.version??0,canvas_audio_draft:value}));
      if(!audioLive(captured))return;if(!audioSummary(row))throw invalid('保存回执与原音频卡片不一致。');
      clearPreview();clearCandidate();creation.current=undefined;baseline.current=inputKey(draftRef.current);setSavedAudioDraft({row,input:baseline.current});audioSaveUnknown.current=false;setNotice('已保存本次已应用输入及来源版本；未保存执行确认，也没有入队或处理音频。');
    }catch(reason){if(audioLive(captured)){if(uncertainFailure(reason))audioSaveUnknown.current=true;failure(reason,'音频草稿保存未确认；保留当前输入，读取原记录核对。',true);}}finally{finish(op);}
  }
  async function resumeAudioDraft(summary:AudioDraftSummary){
    if(!audioDraftCurrent()||busy()||!latest.current.canMutate||selectedRef.current||creation.current?.uncertain||uncertainRef.current&&!audioSaveUnknown.current)return;
    const expected=audioDraftIdentity(summary),listed=audioReadSet.current,entry=listed?.entries.get(summary.id);
    if(!listed||listed.authority!==audioAuthority.current||audioAuthority.current.retired||!listed.methods.every((v,i)=>v===[latest.current.client.timelineList,latest.current.client.timelineGet,latest.current.client.timelineSave,latest.current.read,latest.current.mutate][i])||listed.stamp!==audioStateStamp()||listed.revision!==audioInputRevision.current||entry?.summary!==expected){audioReadSet.current=undefined;return;}
    const op=begin('DRAFT_GET');if(!op)return;const captured=audioCapture(op);
    try{const row=await latest.current.read(()=>op.client.timelineGet(summary.id,op.controller.signal));if(!audioLive(captured))return;
      if(audioDraftIdentity(audioSummary(row))!==expected||!row.canvas_audio_draft||audioDraftIdentity(row.canvas_audio_draft)!==entry.draft)throw invalid('已保存草稿版本、输入或原卡片已变化。');
      const command=canvasAudioDraftCommand(row.canvas_audio_draft),task=latest.current.canvasAudioTrimTask!;assertCanvasAudioTrimTaskCommand(task,command);
      const next=initialDraft(task);next.requestId=command.request_id;next.licenseNote=command.license_note;
      for(const [key,value] of Object.entries(command.parameters))next.parameters[key as MediaParameter]=String(value);
      if(command.template_ref)next.template_ref=structuredClone(command.template_ref);if(command.derived_from)next.derived_from=structuredClone(command.derived_from);
      handoffRevision.current++;audioInputRevision.current++;draftRef.current=next;setDraft(next);clearPreview();clearCandidate();creation.current=undefined;executionPreview.current=undefined;impactState.current=undefined;
      selectedRef.current=undefined;setSelected(undefined);markUncertain(false);audioSaveUnknown.current=false;baseline.current=inputKey(next);setSavedAudioDraft({row,input:baseline.current});
      setNotice('已恢复输入草稿并重新核对原来源；旧执行确认已退役。请重新预览、逐阶段确认，未入队、执行或采用。');
    }catch(reason){if(audioLive(captured))failure(reason,'音频草稿恢复未确认；当前会话输入保持。');throw reason;}finally{finish(op);}
  }
  audioMethods.current={list:listAudioDrafts,resume:resumeAudioDraft,current:audioDraftCurrent};
  function applyAudioTemplate(ref:CanvasAudioWorkflowTemplateRef) {
    const task=latest.current.canvasAudioTrimTask;
    if(!task||!latest.current.audioWorkflowTemplates||!!selectedRef.current||!canClosePrepared||!current()||busy()||!latest.current.canMutate||uncertainRef.current||creation.current?.uncertain||!task.isCurrent())return;
    const next={...draftRef.current,parameters:{...draftRef.current.parameters,...Object.fromEntries(Object.entries(ref.parameters).map(([key,value])=>[key,String(value)]))},template_ref:structuredClone(ref),requestId:undefined};
    checkedCanvasAudioProvenance({operation_id:'m8.audio.trim',canvas_return:task.returnBinding,template_ref:ref});
    edit(next);setSavedAudioDraft(undefined);clearCandidate();selectedRef.current=undefined;setSelected(undefined);
    setNotice('已将模板版本明确提供的参数复制为本次任务草稿；后续局部覆盖不修改模板或原入队任务。');
  }
  function changeOperation(operation: MediaOperation) {
    const task=boundTask(latest.current);
    if(task&&!(task.source.asset_kind==='audio'?operation==='m8.audio.trim':['m5.image.i2i','m5.image.cutout','m5.image.composite'].includes(operation)))return;
    if(Object.hasOwn(MEDIA_OPERATION_LABELS,operation)){
      const next={...initialDraft(task),operation,licenseNote:draftRef.current.licenseNote};
      if(['m5.image.cutout','m5.image.composite'].includes(operation))delete next.imageSource;
      edit(next);
    }
  }
  function changeRoute(route: MediaRoute) {
    const old = draftRef.current;
    if (!routeSelectable(old.operation) || !['local', 'cloud'].includes(route) || route === old.route) return;
    const chosen = providersRef.current.find(row => mediaProviderKey(row) === old.providerKey && row.operation_id === old.operation);
    edit({ ...old, route, providerKey: chosen?.local === (route === 'local') ? old.providerKey : '', allowCloud: false });
  }
  function changeField(field: 'prompt' | 'licenseNote' | 'allowCloud' | 'providerKey' | 'videoReferencePurpose', value: string | boolean) {
    const next = { ...draftRef.current };
    if (field === 'providerKey') {
      if (typeof value !== 'string' || providerHandoffLoading.current) return;
      const matches = providersRef.current.filter(row => mediaProviderKey(row) === value && row.operation_id === next.operation);
      const selectedProvider = matches.length === 1 ? matches[0] : undefined;
      if (value && !selectedProvider) return;
      // The reference workflow keeps its explicit cross-route configuration choice.
      // Selecting a row chooses its route, never permission to upload or execute.
      if (selectedProvider && next.operation === 'm5.image.reference') next.route = selectedProvider.local ? 'local' : 'cloud';
      else if (selectedProvider && routeSelectable(next.operation) && selectedProvider.local !== (next.route === 'local')) return;
      edit({ ...next, providerKey: value, allowCloud: false }); return;
    }
    if (field === 'videoReferencePurpose') { if (typeof value !== 'string' || value !== '' && !['style', 'action', 'camera'].includes(value)) return; if (value === '') delete next.videoReferencePurpose; else next.videoReferencePurpose = value as VideoReference['purpose']; next.allowCloud = false; edit(next); return; }
    if (field === 'allowCloud') { if (typeof value !== 'boolean') return; next.allowCloud = value; }
    else { if (typeof value !== 'string') return; next[field] = value; if (field === 'prompt' && (next.imageSource || next.imageReferences.length || ['m5.image.reference', 'm5.image.inpaint'].includes(next.operation))) next.allowCloud = false; }
    edit(next);
  }
  function changeLayer(id: string, field: 'visible' | 'opacity', value: boolean | string) {
    const old = draftRef.current;
    if (old.operation !== 'm5.image.composite' || !old.sources.some(source => source.id === id)
      || (field === 'visible' ? typeof value !== 'boolean' : typeof value !== 'string')) return;
    const entry = old.layerSettings?.[id] ?? { visible: true, opacity: '255' };
    edit({ ...old, layerSettings: { ...old.layerSettings, [id]: { ...entry, [field]: value } } });
  }
  function swapLayers() {
    const old = draftRef.current;
    if (old.operation === 'm5.image.composite' && old.sources.length === 2) edit({ ...old, sources: [...old.sources].reverse() });
  }
  function changeParameter(name: MediaParameter, value: string) { if (parameterNames.includes(name)) edit({ ...draftRef.current, parameters: { ...draftRef.current.parameters, [name]: value } }); }
  function clearUnsupportedParameters() {
    const old = draftRef.current, selectedProvider = providersRef.current.find(row => mediaProviderKey(row) === old.providerKey && row.operation_id === old.operation);
    if (!selectedProvider) return;
    const next = { ...old.parameters };
    for (const name of parametersByOperation[old.operation]) if (!selectedProvider.supported_parameters.includes(name)) next[name] = '';
    edit({ ...old, parameters: next });
  }
  const handoffOperation = (operation: MediaOperation) => latest.current.assetHandoff?.target === 'VIDEO'
    ? operation === 'm7.video.i2v' || operation === 'm7.video.v2v' : operation === 'm5.image.i2i' || operation === 'm5.image.reference';
  // Metadata-only handoff. The existing controller remains the sole draft owner.
  async function readHandoff(apply: boolean) {
    const request = latest.current.assetHandoff;
    const editable = () => current() && !busy() && latest.current.canMutate && !latest.current.preparedCommand
      && !providerHandoffLoading.current && !uncertainRef.current && !creation.current?.uncertain
      && !['UNKNOWN', 'RUNNING', 'SEND_RESERVED', 'REMOTE_RUNNING', 'RESULT_READY', 'REVIEWING'].includes(selectedRef.current?.status || '');
    if (!request || handoffFlight.current || handoffConsumed.current === request || !editable() || !handoffOperation(draftRef.current.operation)) return;
    const revision = handoffRevision.current, sourceClient = latest.current.client, kind = sourceKind(draftRef.current.operation);
    const video = request.target === 'VIDEO';
    if (apply && (handoffAsset?.request !== request || handoffAsset.revision !== revision)) return;
    handoffFlight.current = true; setHandoffPending(true); setHandoffNotice('');
    try {
      const asset = await request.readAsset();
      if (!current() || sourceClient !== latest.current.client || request !== latest.current.assetHandoff) return;
      if (!exactHandoffAsset(asset, request.reference) || asset.kind !== kind || asset.manual_mask) {
        setHandoffAsset(undefined); setHandoffNotice('来源类型、版本或摘要已变化，或已删除；不会替换为最新版本。'); return;
      }
      if (!editable() || handoffRevision.current !== revision) {
        setHandoffAsset(undefined); setHandoffNotice('草稿、服务配置或编辑状态已变化；请重新核对。'); return;
      }
      const old = draftRef.current;
      if (!apply && old.operation !== 'm5.image.reference') { setHandoffAsset({ asset, request, revision }); return; }
      const listed = latest.current.assets.find(row => row.id === asset.id);
      if (!listed || !exactHandoffAsset(listed, request.reference) || listed.kind !== kind || listed.manual_mask) {
        setHandoffAsset(undefined); setHandoffNotice('当前素材列表尚未核对同一版本；请明确读取当前素材版本后重试。'); return;
      }
      const chosen = providersRef.current.find(row => mediaProviderKey(row) === old.providerKey && row.operation_id === old.operation);
      if (old.operation === 'm5.image.reference') {
        let next: Draft;
        try { next = appendImageReference(old, asset, chosen, true); }
        catch (reason) { setHandoffAsset(undefined); setHandoffNotice(reason instanceof Error ? reason.message : '当前输入无法安全追加。'); return; }
        if (!apply) { setHandoffAsset({ asset, request, revision }); return; }
        edit(next);
      } else {
        if (old.sources.some(row => row.id === asset.id)) { setHandoffNotice('此素材已绑定；请使用原输入控件明确移除或调整，不会覆盖已有绑定。'); return; }
        if (video) {
          if (old.sources.length || old.imageSource || old.imageReferences.length || old.maskSource) {
            setHandoffNotice('已有来源绑定；请先用原输入控件移除，不会覆盖已有来源。'); return;
          }
          edit({ ...old, sources: [{ id: asset.id, kind: 'ASSET', asset_kind: kind as 'image' | 'video', version: asset.version, digest: asset.sha256 }], allowCloud: false });
        } else if (chosen?.image_capabilities) {
          if (old.imageSource || old.sources.length !== old.imageReferences.length || old.imageReferences.length + 1 > chosen.image_capabilities.reference_limit) {
            setHandoffNotice('已有基础图或超过当前路线输入上限；请先用原输入控件调整。'); return;
          }
          const next = { ...old, imageSource: imageSnapshot(asset), allowCloud: false };
          edit({ ...next, sources: imageSources(next) });
        } else {
          if (old.sources.length >= 5 || old.imageSource || old.imageReferences.length || old.maskSource) { setHandoffNotice('当前输入无法安全追加；请先用原输入控件调整。'); return; }
          edit({ ...old, sources: [...old.sources, imageSnapshot(asset)], allowCloud: false });
        }
      }
      handoffConsumed.current = request; setHandoffAsset(undefined);
      setHandoffNotice(`已加入原${video ? '视频' : '图片'}制作草稿；旧制作预览与云端确认已清除。尚未预检、入队或执行。`);
    } catch (reason) {
      if (current() && request === latest.current.assetHandoff) { setHandoffAsset(undefined); setHandoffNotice(apiErrorView(reason, '交接素材读取失败；草稿未改变。').message); }
    } finally { handoffFlight.current = false; if (alive.current) setHandoffPending(false); }
  }
  function selectSource(id: string, checked: boolean) {
    const task=latest.current.canvasImageTask;
    if(task&&(draftRef.current.operation!=='m5.image.composite'||id===task.source.id))return;
    const old = draftRef.current, kind = sourceKind(old.operation); if (!kind) return;
    const row = latest.current.assets.find(asset => asset.id === id && usableAsset(asset, kind) && (!['m5.image.cutout','m5.image.composite'].includes(old.operation) || usableCutoutSource(asset)));
    if (old.operation === 'm5.image.cutout') {
      if (checked && !row) { setError('PNG 来源不可用，请重新读取素材。'); return; }
      edit({ ...old, sources: checked && row ? [{ id: row.id, kind: 'ASSET', version: row.version, digest: row.sha256, asset_kind: 'image' }] : [] }); return;
    }
    const selectedProvider = providersRef.current.find(provider => mediaProviderKey(provider) === old.providerKey && provider.operation_id === old.operation);
    if (old.operation === 'm7.video.i2v') {
      if (checked && !row) { setError('首帧来源不可用，请重新读取素材。'); return; }
      const next = checked && row
        ? { ...old, sources: [{ id: row.id, kind: 'ASSET' as const, version: row.version, digest: row.sha256, asset_kind: 'image' as const }],
            lastFrame: old.lastFrame?.id === row.id ? undefined : old.lastFrame }
        : { ...old, sources: [], lastFrame: undefined };
      edit(next); return;
    }
    if (old.operation === 'm5.image.upscale' || old.operation === 'm5.image.inpaint' || old.operation === 'm5.image.i2i' && !!selectedProvider?.image_capabilities) {
      if (checked && (!row || old.operation === 'm5.image.inpaint' && !usableCutoutSource(row))) { setError('图片来源不可用，请重新读取素材。'); return; }
      if (checked && old.imageReferences.some(reference => reference.source.id === id)) { setError('参考素材已绑定为辅助输入，请明确移除该参考后再选择基础图。'); return; }
      const next = { ...old, imageSource: checked && row ? imageSnapshot(row) : undefined, maskSource: undefined, allowCloud: false };
      edit({ ...next, sources: imageSources(next) }); return;
    }
    if (checked && !row) { setError('来源不可用，请重新读取素材。'); return; }
    let sources = old.sources.filter(source => source.id !== id);
    if (checked && row) {
      if (!['m5.image.i2i', 'm5.image.composite'].includes(old.operation)) sources = [];
      if (sources.length >= (old.operation === 'm5.image.composite' ? 2 : 5)) { setError(old.operation === 'm5.image.composite' ? '双层合成最多选取两张图片。' : '最多选取五张参考图片。'); return; }
      sources.push({ id: row.id, kind: 'ASSET', version: row.version, digest: row.sha256, asset_kind: kind });
    }
    edit({ ...old, sources });
  }
  function selectEndFrame(id: string) {
    const old = draftRef.current;
    if (old.operation !== 'm7.video.i2v') return;
    if (!id) { edit({ ...old, lastFrame: undefined }); return; }
    const selectedProvider = providersRef.current.find(provider => mediaProviderKey(provider) === old.providerKey && provider.operation_id === old.operation);
    if (!selectedProvider?.video_frame_capabilities?.end_frame) { setError('当前配置不支持尾帧；请选择支持首尾帧的配置。'); return; }
    const row = latest.current.assets.find(asset => asset.id === id && usableAsset(asset, 'image'));
    const first = old.sources[0];
    if (!row) { setError('尾帧来源不可用，请重新读取素材。'); return; }
    if (!first) { setError('请先选择首帧，再选择尾帧。'); return; }
    if (first.id === row.id) { setError('首帧与尾帧不能是同一张图片。'); return; }
    edit({ ...old, lastFrame: { id: row.id, kind: 'ASSET', version: row.version, digest: row.sha256, asset_kind: 'image' }, allowCloud: false });
  }
  function selectMask(id: string) {
    const old = draftRef.current, source = latest.current.assets.find(asset => asset.id === old.sources[0]?.id);
    if (!['m5.image.cutout', 'm5.image.inpaint'].includes(old.operation) || !source || source.version !== old.sources[0]?.version || source.sha256 !== old.sources[0]?.digest) return;
    if (old.operation === 'm5.image.inpaint') {
      const mask = id ? latest.current.assets.find(asset => asset.id === id && eligibleCutoutMask(asset, source)) : undefined;
      if (id && !mask) { setError('遮罩与当前来源版本不匹配，请重新读取素材。'); return; }
      const next = { ...old, maskSource: mask ? imageSnapshot(mask) : undefined, allowCloud: false }; edit({ ...next, sources: imageSources(next) }); return;
    }
    if (!id) { edit({ ...old, sources: old.sources.slice(0, 1) }); return; }
    const mask = latest.current.assets.find(asset => asset.id === id && eligibleCutoutMask(asset, source));
    if (!mask) { setError('遮罩与当前来源版本不匹配，请重新读取素材。'); return; }
    edit({ ...old, sources: [old.sources[0], { id: mask.id, kind: 'ASSET', version: mask.version, digest: mask.sha256, asset_kind: 'image' }] });
  }
  function refreshSources() {
    if(latest.current.canvasImageTask)return;
    const old = draftRef.current, kind = sourceKind(old.operation); if (!kind) return;
    const sources: ProductionSource[] = [];
    for (const source of ['m5.image.cutout', 'm5.image.inpaint'].includes(old.operation) ? old.sources.slice(0, 1) : old.sources) {
      const row = latest.current.assets.find(asset => asset.id === source.id && usableAsset(asset, kind));
      if (!row) { setError('已选来源已删除或不可用，请先移除该来源。'); return; }
      sources.push({ id: row.id, kind: 'ASSET', version: row.version, digest: row.sha256, asset_kind: kind });
    }
    let lastFrame = old.lastFrame;
    if (lastFrame) {
      const row = latest.current.assets.find(asset => asset.id === lastFrame!.id && usableAsset(asset, 'image'));
      if (!row) { setError('尾帧来源已删除或不可用，请先移除尾帧。'); return; }
      lastFrame = { id: row.id, kind: 'ASSET', version: row.version, digest: row.sha256, asset_kind: 'image' };
    }
    if (old.imageSource || old.imageReferences.length || old.operation === 'm5.image.inpaint') {
      const next = { ...old, allowCloud: false, imageSource: old.imageSource ? sources.find(row => row.id === old.imageSource!.id) : undefined,
        imageReferences: old.imageReferences.map(reference => ({ ...reference, source: sources.find(row => row.id === reference.source.id)! })), maskSource: undefined };
      edit({ ...next, sources: imageSources(next) });
    } else edit({ ...old, sources, lastFrame });
  }
  function selectReference(id: string, checked: boolean) {
    const old = draftRef.current;
    if (!['m5.image.reference', 'm5.image.i2i'].includes(old.operation)) return;
    const provider = providersRef.current.find(row => mediaProviderKey(row) === old.providerKey && row.operation_id === old.operation);
    if (!provider?.image_capabilities) return;
    const asset = latest.current.assets.find(row => row.id === id && usableAsset(row, 'image') && !row.manual_mask);
    if (checked && !asset) { setError('参考素材不可用，请重新读取素材。'); return; }
    const next = { ...old, imageReferences: old.imageReferences.filter(reference => reference.source.id !== id), allowCloud: false };
    const without = { ...next, sources: imageSources(next) };
    if (!checked || !asset) { edit(without); return; }
    try { edit(appendImageReference(without, asset, provider)); }
    catch (reason) { setError(reason instanceof Error ? reason.message : '参考素材不可用，请重新读取素材。'); }
  }

  function changeReferenceWeight(id: string, weight: string) {
    const old = draftRef.current;
    const next = { ...old, imageReferences: old.imageReferences.map(reference => reference.source.id === id ? { ...reference, weight } : reference), allowCloud: false };
    edit(next);
  }
  function changeReferenceMetadata(id: string, key: 'purpose' | 'source_note', value: string) {
    const old = draftRef.current; if (key === 'source_note' && value.length > 500) return;
    const refs = old.imageReferences.map(reference => { if (reference.source.id !== id) return reference; const next = { ...reference };
      if (value === '') delete next[key]; else { const metadata = checkedImageReferenceMetadata({ [key]: value }, true); Object.assign(next, metadata); } return next; });
    edit({ ...old, imageReferences: refs, allowCloud: false });
  }
  function clearSources() { if(latest.current.canvasImageTask)return;edit({ ...draftRef.current, sources: [], lastFrame: undefined, imageSource: undefined, imageReferences: [], maskSource: undefined,
    allowCloud: draftRef.current.imageSource || draftRef.current.imageReferences.length || ['m5.image.reference', 'm5.image.inpaint'].includes(draftRef.current.operation) ? false : draftRef.current.allowCloud }); }
  function clearInputs() { if (!current() || busy() || !latest.current.canMutate || uncertainRef.current || creation.current?.uncertain) return;
    if (latest.current.preparedCommand) { if (selectedRef.current && ['UNKNOWN', 'RUNNING', 'SEND_RESERVED', 'REMOTE_RUNNING', 'RESULT_READY', 'REVIEWING'].includes(selectedRef.current.status)) return; latest.current.onPreparedClose?.(); return; }
    edit(initialDraft(boundTask(latest.current))); baseline.current = inputKey(initialDraft(boundTask(latest.current))); clearCandidate(); }

  async function loadProviders() {
    if (!current() || busy()) return;
    handoffRevision.current++;
    const client = latest.current.client, id = ++providerEpoch.current, controller = new AbortController(); providerRead.current?.abort(); providerRead.current = controller;
    providerHandoffLoading.current = true; setProviderLoading(true); clearPreview();
    try {
      const rows = await latest.current.read(() => client.providers(controller.signal));
      if (!current() || controller.signal.aborted || providerEpoch.current !== id || client !== latest.current.client) return;
      providersRef.current = rows; setProviders(rows);
    } catch (reason) { if (current() && !controller.signal.aborted && providerEpoch.current === id) failure(reason, '服务商配置读取失败。'); }
    finally { if (alive.current && providerEpoch.current === id) { providerHandoffLoading.current = false; setProviderLoading(false); } }
  }
  async function inspect() {
    if (!latest.current.canMutate || uncertainRef.current || creation.current?.uncertain || providerLoading) return;
    const value = begin('PREVIEW'); if (!value) return;
    const captured = inputKey(draftRef.current); clearPreview();
    try {
      const command = latest.current.preparedCommand ? structuredClone(latest.current.preparedCommand) as MediaCommand : commandFor(draftRef.current, providersRef.current, latest.current.assets, draftRef.current.requestId ?? crypto.randomUUID(),boundTask(latest.current));
      const result = await latest.current.read(() => value.client.preview(command));
      if (!live(value) || captured !== inputKey(draftRef.current) || !sourcesCurrent(command.source_snapshots, latest.current.assets, command.operation_id)) return;
      const chosen = providersRef.current.find(row => latest.current.preparedCommand ? row.operation_id === command.operation_id && row.provider_id === command.provider_id && row.model_id === command.model_id : mediaProviderKey(row) === draftRef.current.providerKey);
      if (command.operation_id === 'm5.image.composite' && !sameCompositeCommand(command, result.command)) throw invalid('叠层配方或来源已变化。');
      if (!['m8.audio.trim', 'm5.image.cutout', 'm5.image.composite'].includes(command.operation_id) && (!chosen || !result.provider || result.provider.route_digest !== chosen.route_digest || result.provider.local !== chosen.local)) throw invalid('服务商路线已变化，请重新读取配置并预览。');
      impactReadRevision.current++;
      const next = { value: result, command, input: captured }; previewRef.current = next; setPreview(next);
      setNotice('预览已读取；尚未创建任务，也未执行媒体处理。');
    } catch (reason) { if (live(value)) failure(reason, '制作预览未完成。'); } finally { finish(value); }
  }
  function confirmPreview(checked: boolean) { if (!current() || busy()) return; const key = previewRef.current && previewRef.current.input === inputKey(draftRef.current) && sourcesCurrent(draftRef.current.sources, latest.current.assets, draftRef.current.operation)
    ? JSON.stringify([previewRef.current.input, previewRef.current.value.preview_digest, previewRef.current.value.request_digest]) : ''; previewConsentRef.current = checked ? key : ''; setPreviewConsent(previewConsentRef.current); }
  async function create() {
    if (impactRequired() && !impactReady('CREATE')) return;
    const saved = previewRef.current;
    if (!current() || !latest.current.canMutate || uncertainRef.current || creation.current || !saved || saved.input !== inputKey(draftRef.current) || !sourcesCurrent(saved.command.source_snapshots, latest.current.assets, saved.command.operation_id)) return;
    const binding = JSON.stringify([saved.input, saved.value.preview_digest, saved.value.request_digest]); if (previewConsentRef.current !== binding || !impactReady('CREATE')) return;
    const impactGate = impactState.current?.gate;
    const value = begin('CREATE'); if (!value) return;
    creation.current = { requestId: saved.command.request_id, requestDigest: saved.value.request_digest, operation: saved.command.operation_id, input: saved.input, uncertain: true };
    try {
      const result = await latest.current.mutate(() => {
        if ((impactGate || impactRequired()) && (!live(value) || saved !== previewRef.current || previewConsentRef.current!==binding)) throw new ApiError({status:422,code:'STUDIO_EXECUTION_IMPACT_RETIRED',message:'原预览或任务范围已改变，未创建任务。'});
        consumeImpact('CREATE',impactGate); return value.client.create(saved.command, saved.value.preview_digest);
      });
      if (!live(value)) return;
      if (result.request_digest !== saved.value.request_digest || result.status !== 'QUEUED') throw invalid('入队回执与预览不一致，请读取任务核对。');
      if (impactRequired() && !sameExecutionPreview(result,saved.value)) throw invalid('入队命令、路线或配方与原预览不一致，请读取核对，不能执行。');
      executionPreview.current={jobId:result.id,preview:structuredClone(saved.value)};
      creation.current = { ...creation.current!, uncertain: false }; baseline.current = saved.input;
      adoptJob(result); clearPreview(); markUncertain(false); setNotice('任务已保存入队。执行仍需单独点击。');
    } catch (reason) { if (live(value)) { if (!uncertainFailure(reason)) creation.current = undefined; failure(reason, '任务入队未完成，请读取核对。', true); } } finally { finish(value); }
  }
  async function listJobs() {
    const value = begin('LIST'); if (!value) return;
    try {
      const rows = await latest.current.read(() => value.client.list(value.controller.signal)); if (!live(value)) return;
      const visibleRows = latest.current.preparedCommand ? rows.filter(row => row.request_id === latest.current.preparedCommand!.request_id && row.operation_id === latest.current.preparedCommand!.operation_id) : rows;
      if (latest.current.preparedCommand && visibleRows.some(row => !sameComicImageCommand(latest.current.preparedCommand!, row.command))) throw invalid('原图片任务与当前漫画格框请求不一致，请读取原回执核对。');
      if (latest.current.preparedCommand?.storyboard_speech && visibleRows.some(row => !sameStoryboardSpeech(latest.current.preparedCommand!, row.command))) throw invalid('原语音任务与当前分镜对白请求不一致，请读取原回执核对。');
      setJobs(visibleRows);
      if (creation.current?.uncertain) {
        const attempt = creation.current, match = visibleRows.find(row => row.request_id === attempt.requestId && row.operation_id === attempt.operation && row.request_digest === attempt.requestDigest);
        if (match) { creation.current = { ...attempt, uncertain: false }; baseline.current = attempt.input; adoptJob(match); markUncertain(false); setNotice('已找到原请求的保存记录；不会重新创建或执行。'); }
        else setNotice('尚未找到原请求回执。保留不确定状态，请勿重复发送。');
      } else if (selectedRef.current) {
        const old = selectedRef.current, match = visibleRows.find(row => row.owner === old.owner && row.id === old.id);
        if (match) { adoptJob(match); markUncertain(false); } else { clearCandidate(); selectedRef.current = undefined; setSelected(undefined); }
      }
    } catch (reason) { if (live(value)) failure(reason, '任务列表读取失败。'); } finally { finish(value); }
  }
  async function openJob(job: ProductionJob) {
    const prepared = latest.current.preparedCommand; if (prepared && (job.request_id !== prepared.request_id || job.operation_id !== prepared.operation_id)) return;
    const value = begin('GET'); if (!value) return; clearCandidate();
    try {
      const result = await latest.current.read(() => value.client.get(job.owner, job.id, value.controller.signal)); if (!live(value)) return;
      if (prepared && (result.request_id !== prepared.request_id || result.operation_id !== prepared.operation_id || !sameComicImageCommand(prepared, result.command) || prepared.storyboard_speech && !sameStoryboardSpeech(prepared, result.command))) throw invalid('原任务与当前分镜请求不一致，请读取该请求回执。');
      adoptJob(result); if (!creation.current?.uncertain) markUncertain(false); setNotice('已读取当前任务版本；未重新执行。');
    } catch (reason) { if (live(value)) failure(reason, '任务读取失败。'); } finally { finish(value); }
  }
  async function inspectExecution() {
    const job = selectedRef.current;
    if (!impactRequired() || !job?.command || job.status!=='QUEUED' || !latest.current.canMutate || uncertainRef.current
      || !boundTask(latest.current)?.isCurrent() || !canvasTaskJobMatches(boundTask(latest.current)!,job)
      || !sourcesCurrent(job.sources,latest.current.assets,job.operation_id)) return;
    const value=begin('PREVIEW');if(!value)return;clearPreview();
    const captured=impactStamp(),identity=jobIdentity(job);
    try {
      const command=structuredClone(job.command!) as MediaCommand;
      if(boundTask(latest.current)?.source.asset_kind==='audio'){
        // Re-preview the already matched original AudioJob; projection-only markers are not fresh inputs.
        const parameters=checkedCanvasAudioTaskEnvelope(job.command!.parameters,true);
        if(!parameters)throw invalid('原入队音频参数不符合本次卡片处理范围，不能重新预览执行。');
        command.parameters=parameters;
        command.source_snapshots=[{...boundTask(latest.current)!.source}];
        delete command.source_snapshots[0].reference_only;
      }
      if(['m5.image.cutout','m5.image.composite'].includes(command.operation_id)){
        // Re-preview the exact original ordered image inputs, not recorded-only markers.
        command.source_snapshots=command.source_snapshots.map(source=>{const value={...source};delete value.reference_only;return value;});
      }
      const result=await latest.current.read(()=>value.client.preview(command));
      if(!live(value)||jobIdentity(selectedRef.current)!==identity||impactStamp()!==captured)return;
      if(!sameExecutionPreview(job,result))throw invalid('重新读取的预览与原入队命令、路线或配方不一致，不能执行。');
      impactReadRevision.current++;executionPreview.current={jobId:job.id,preview:result};updateImpact(v=>v+1);setNotice('已核对原入队任务预览；仍需单独确认本次执行输入，没有派发。');
    }catch(reason){if(live(value))failure(reason,'原入队任务预览核对失败。');}finally{finish(value);}
  }
  function canAction(kind: 'execute' | 'refresh' | 'reconcile' | 'cancel' | 'review') {
    if (kind==='execute' && impactRequired() && !impactReady('EXECUTE')) return false;
    const task = boundTask(latest.current), originalJob = selectedRef.current;
    if(task && (kind==='execute'||kind==='review') && (!originalJob||!canvasTaskJobMatches(task,originalJob)||kind==='execute'&&!task.isCurrent()))return false;
    const job = selectedRef.current;
    if (!job || busy() || uncertainRef.current || creation.current?.uncertain || sentActions.current.has(actionIdentity(job, kind))) return false;
    const assetSources = job.sources.filter((source): source is ProductionSource => source.kind === 'ASSET');
    const fresh = sourcesCurrent(assetSources, latest.current.assets, job.operation_id);
    if (kind === 'review') return latest.current.canReview && fresh && ['AWAITING_REVIEW', 'SUCCEEDED', 'REVIEWING'].includes(job.status)
      && !!job.output_candidate && candidateRef.current?.binding === reviewIdentity(job) && reviewConsentRef.current === reviewIdentity(job);
    if (!latest.current.canMutate) return false;
    if (kind === 'execute') return job.owner !== 'timeline' && job.status === 'QUEUED' && fresh && impactReady('EXECUTE');
    if (kind === 'refresh') return job.owner === 'video' && ['REMOTE_RUNNING', 'RESULT_READY', 'UNKNOWN'].includes(job.status);
    if (kind === 'reconcile') return ['m5.image.cutout', 'm5.image.composite'].includes(job.operation_id) && job.status === 'CANCELLED' ? !!job.processing_proof && !job.output_candidate : job.owner === 'timeline' ? ['RUNNING', 'UNKNOWN', 'REVIEWING'].includes(job.status)
      : job.owner === 'video' ? ['RUNNING', 'SEND_RESERVED', 'UNKNOWN', 'RESULT_READY', 'REVIEWING'].includes(job.status)
      : ['RUNNING', 'UNKNOWN', 'REVIEWING'].includes(job.status);
    return ['m5.image.cutout', 'm5.image.composite'].includes(job.operation_id) ? ['QUEUED', 'RUNNING', 'UNKNOWN', 'AWAITING_REVIEW'].includes(job.status)
      : job.owner === 'timeline' ? ['RUNNING', 'UNKNOWN', 'SUCCEEDED', 'AWAITING_REVIEW'].includes(job.status)
      : ['QUEUED', 'AWAITING_REVIEW', 'UNKNOWN', 'REMOTE_RUNNING', 'RESULT_READY'].includes(job.status);
  }
  async function action(kind: 'execute' | 'refresh' | 'reconcile' | 'cancel' | 'review') {
    if (!canAction(kind)) return; const job = selectedRef.current!, impactGate=impactState.current?.gate;
    const value = begin(kind); if (!value) return; clearCandidate();
    const sentKey = actionIdentity(job, kind); sentActions.current.add(sentKey);
    const localExecution = kind === 'execute' && ['m5.image.cutout', 'm5.image.composite'].includes(job.operation_id) && latest.current.cutoutExecution;
    if (localExecution) executingCutout.current = job;
    const responseFence = controlFence.current;
    try {
      const authorize=()=>{
        if(kind==='execute' && (impactGate || impactRequired())) {
          if(!live(value)||jobIdentity(selectedRef.current)!==jobIdentity(job))throw new ApiError({status:422,code:'STUDIO_EXECUTION_IMPACT_RETIRED',message:'原任务范围或版本已改变，未派发执行。'});
          consumeImpact('EXECUTE',impactGate);
        }
      };
      // The original workspace invokes authorization inside its mutation lease,
      // immediately before transport; pending CPU control keeps the same owner.
      const result = await (localExecution ? localExecution.execute(job,authorize) : latest.current.mutate(() => {
        authorize();return value.client[kind](job);
      })); if (!live(value)) return;
      if (localExecution && responseFence !== controlFence.current) {
        if (runningControlRef.current || uncertainRef.current || selectedRef.current?.version && result.version <= selectedRef.current.version) return;
        if (selectedRef.current?.status === 'CANCELLED') return;
      }
      if (result.version < job.version || result.request_digest !== job.request_digest || result.id !== job.id || result.operation_id !== job.operation_id) throw invalid('原任务响应版本或身份不一致，请重新读取。');
      adoptJob(result); markUncertain(false);
      setNotice(kind === 'cancel' ? result.owner === 'timeline'
        ? result.cancellation_mode === 'LOCAL_RENDER_PROCESS_STOP_REQUESTED' ? '已记录停止本地渲染进程的请求；请重新读取原任务核对。已有回执与候选保留，不能继续采用。' : '已取消此未审核时间线结果的采用权限，原回执与候选保留。'
        : ['m5.image.cutout', 'm5.image.composite'].includes(result.operation_id) ? '已记录本地取消并撤销候选采用权限；请读取原任务核对。不会自动重试。' : '已丢弃本地结果的采用权限；远端计算可能继续。'
        : kind === 'review' ? '已保存审核回执，请核对当前素材库。' : kind === 'reconcile' ? '已核对本地中断状态，未重新提交媒体生成。' : '已收到任务回执，请核对状态与候选结果。');
      if (kind === 'review' && result.status === 'APPROVED') {
        const approved = jobIdentity(result);
        try { void Promise.resolve(latest.current.onApproved?.(result)).catch(() => {
          if (current() && jobIdentity(selectedRef.current) === approved) setError('审核已经保存，但素材列表刷新未完成，请重新读取。');
        }); } catch { setError('审核已经保存，但素材列表刷新未完成，请重新读取。'); }
      }
    } catch (reason) { if (live(value)) { if (localExecution && responseFence !== controlFence.current && selectedRef.current?.status === 'CANCELLED' && !uncertainRef.current) return; if (!uncertainFailure(reason)) sentActions.current.delete(sentKey); failure(reason, '操作结果未确认，请读取任务核对。', true); } } finally { if (localExecution && executingCutout.current === job) executingCutout.current = undefined; finish(value); }
  }
  async function controlRunningCutout(kind: 'read' | 'cancel') {
    const original = executingCutout.current, active = slot.current, method = latest.current.cutoutExecution?.control;
    if (!current() || !latest.current.canMutate || !original || !active || active.kind !== 'execute' || !method || runningControlRef.current) return;
    const expected = selectedRef.current;
    if (!expected || expected.id !== original.id || expected.request_digest !== original.request_digest || expected.operation_id !== original.operation_id || !['m5.image.cutout', 'm5.image.composite'].includes(expected.operation_id)) return;
    if (kind === 'cancel' && (uncertainRef.current || sentActions.current.has(actionIdentity(expected, 'cancel')))) return;
    if (kind === 'cancel') sentActions.current.add(actionIdentity(expected, 'cancel'));
    const fence = ++controlFence.current; runningControlRef.current = kind; setRunningControl(kind); clearCandidate();
    try {
      const result = await method(kind, expected);
      if (!live(active) || controlFence.current !== fence) return;
      if (result.id !== original.id || result.owner !== 'image' || result.operation_id !== original.operation_id || result.request_digest !== original.request_digest
        || result.request_id !== original.request_id || result.version < expected.version || result.version < (selectedRef.current?.version || 0)) throw invalid('原抠图任务回执不一致，请重新读取。');
      adoptJob(result); markUncertain(false);
      setNotice(result.status === 'CANCELLED' ? '原任务已记录取消；本地处理和候选采用已被围栏阻止。不会自动重试。' : '已读取原本地抠图任务状态；未重新执行。');
    } catch (reason) { if (live(active) && controlFence.current === fence) failure(reason, '原本地任务控制结果未确认，请等待执行返回后读取核对。', true); }
    finally { if (controlFence.current === fence) { runningControlRef.current = undefined; if (alive.current) setRunningControl(undefined); } }
  }
  async function loadCandidate() {
    const job = selectedRef.current; if (!job?.output_candidate || uncertainRef.current || creation.current?.uncertain || !sourcesCurrent(job.sources.filter((source): source is ProductionSource => source.kind === 'ASSET'), latest.current.assets, job.operation_id)) return;
    const sourceAuthority = () => JSON.stringify(job.sources.filter((source): source is ProductionSource => source.kind === 'ASSET').map(source => {
      const row = latest.current.assets.find(asset => asset.id === source.id); return [source.id, row?.version, row?.sha256, row?.deleted_at, row?.kind, row?.manual_mask, row?.provenance];
    }));
    const capturedSource = sourceAuthority();
    const value = begin('CANDIDATE'); if (!value) return; clearCandidate(); const binding = reviewIdentity(job);
    const stillBound = () => live(value) && binding === reviewIdentity(selectedRef.current) && capturedSource === sourceAuthority();
    try {
      const blob = await latest.current.read(() => value.client.candidate(job));
      if (!stillBound()) return;
      if (!blob.size || blob.size > 25 * 1024 * 1024 || !blob.type.startsWith(job.output_candidate.kind + '/')) throw invalid('候选媒体类型或大小不正确，请读取任务核对。');
      const digest = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', await blob.arrayBuffer())), byte => byte.toString(16).padStart(2, '0')).join('');
      if (!stillBound()) return;
      if (['m5.image.cutout', 'm5.image.composite'].includes(job.operation_id) && (blob.type !== (job.command?.parameters.cutout_output === CUTOUT_WEBP_PROFILE ? 'image/webp' : 'image/png') || blob.size !== job.processing_proof?.output_bytes)) throw invalid('本地抠图候选与处理证明不一致，不可审核。');
      if (job.owner === 'timeline' && job.execution_recipe.output_profile === 'AUDIO_WAV_PCM16'
        && (job.output_candidate.kind !== 'audio' || blob.type !== 'audio/wav' || blob.size !== job.media_measurement?.byte_count))
        throw invalid('音频时间线 WAV 候选与绑定的输出配置或实际测量不一致，不可审核。');
      if (job.operation_id === 'm8.audio.trim' && job.media_measurement?.profile_validation === 'PCM_DECODED'
        && (blob.size !== job.media_measurement.byte_count || !['audio/wav', 'audio/x-wav', 'audio/wave'].includes(blob.type))) throw invalid('本地 WAV 候选与实际输出测量不一致，不可审核。');
      if (job.operation_id === 'm8.audio.trim' && job.media_measurement?.profile_validation === 'FLAC_STREAMINFO_PCM_VERIFIED'
        && (blob.size !== job.media_measurement.byte_count || !['audio/flac', 'audio/x-flac'].includes(blob.type))) throw invalid('本地 FLAC 候选与实际输出测量不一致，不可审核。');
      if (job.operation_id === 'm8.audio.trim' && job.media_measurement?.profile_validation === 'MP3_GAPLESS_PCM_VERIFIED'
        && (blob.size !== job.media_measurement.byte_count || blob.type !== 'audio/mpeg')) throw invalid('本地 MP3 候选与实际输出测量不一致，不可审核。');
      if (digest !== job.output_candidate.digest) throw invalid('候选字节摘要与任务回执不符，不可审核。');
      const next = { url: URL.createObjectURL(blob), kind: job.output_candidate.kind, binding }; candidateRef.current = next; setCandidate(next);
    } catch (reason) { if (live(value)) failure(reason, '候选媒体读取失败。', true); } finally { finish(value); }
  }
  function confirmReview(checked: boolean) { if (!current() || busy() || !latest.current.canReview || uncertainRef.current) return;
    const key = reviewIdentity(selectedRef.current); reviewConsentRef.current = checked && key && candidateRef.current?.binding === key ? key : ''; setReviewConsent(reviewConsentRef.current); }
  function mediaFailed(binding: string) { if (!current() || candidateRef.current?.binding !== binding) return;
    clearCandidate(); markUncertain(true); setError('候选媒体无法显示或播放。请读取原任务核对，当前不可审核。'); }
  function downloadReceipt() {
    const job = selectedRef.current; if (!job || !current() || busy()) return;
    clearReceiptDownload();
    // Serialize the last checked original public projection, without inferred
    // provider calls, invented output or an upgraded acceptance status.
    const url = URL.createObjectURL(new Blob([JSON.stringify(job, null, 2)], { type: 'application/json;charset=utf-8' }));
    receiptDownload.current = url;
    const link = document.createElement('a'); link.href = url; link.download = `studio-${job.owner}-${job.id}-v${job.version}.json`;
    try { document.body.appendChild(link); link.click(); setNotice(`已下载刚读取的原任务 v${job.version} 公共回执；这不是新的执行或验收结果。`); }
    catch { setError('本地回执下载未完成，请重新读取任务后再下载。'); }
    finally { link.remove(); receiptTimer.current = setTimeout(() => { if (receiptDownload.current === url) clearReceiptDownload(); }, 0); }
  }

  useLayoutEffect(() => {
    alive.current = true;
    return () => { alive.current = false; controlFence.current++; executingCutout.current = undefined; runningControlRef.current = undefined; epoch.current++; providerEpoch.current++; slot.current?.controller.abort(); providerRead.current?.abort();
      if (candidateRef.current) URL.revokeObjectURL(candidateRef.current.url); candidateRef.current = undefined; clearReceiptDownload(); latest.current.onDirtyChange(false); };
  }, []);
  useLayoutEffect(() => {
    epoch.current++; providerEpoch.current++; slot.current?.controller.abort(); slot.current = undefined; providerRead.current?.abort();
    controlFence.current++; executingCutout.current = undefined; runningControlRef.current = undefined; setRunningControl(undefined);
    clearCandidate(); clearPreview(); owner.current = props.client; revoked.current = false; setDenied(false); setPending(undefined); setProviders([]); setJobs([]);
    const empty = initialDraft(boundTask(latest.current)); audioInputRevision.current++; draftRef.current = empty; setDraft(empty); baseline.current = inputKey(empty); selectedRef.current = undefined; setSelected(undefined);
    creation.current = undefined; sentActions.current.clear(); consumedExternal.current = ''; markUncertain(false); setError(''); setNotice('');
  }, [props.client]);
  useLayoutEffect(() => {
    clearCandidate(); clearPreview(); controlFence.current++; executingCutout.current = undefined; runningControlRef.current = undefined; setRunningControl(undefined);
    const running = slot.current;
    if (running) { running.controller.abort(); epoch.current++; slot.current = undefined; setPending(undefined);
      if (['CREATE', 'execute', 'refresh', 'reconcile', 'cancel', 'review'].includes(running.kind)) markUncertain(true); }
  }, [props.canMutate, props.canReview, owns]);
  useEffect(() => { clearPreview(); }, [sourceState]);
  useLayoutEffect(() => { clearCandidate(); }, [jobSourceState]);
  useEffect(() => { void loadProviders(); return () => { providerEpoch.current++; providerRead.current?.abort(); }; }, [props.client]);
  useEffect(() => { props.onDirtyChange(dirty); }, [dirty, props.onDirtyChange]);
  const external = jobIdentity(props.externalJob);
  useLayoutEffect(() => {
    if (!props.externalJob || busy() || !current() || external === consumedExternal.current) return;
    consumedExternal.current = external;
    if (external === jobIdentity(selectedRef.current)) return;
    if (selectedRef.current?.id === props.externalJob.id && selectedRef.current.owner === props.externalJob.owner && selectedRef.current.version > props.externalJob.version) return;
    adoptJob(props.externalJob); // A returned owner row only; never a GET/action or draft overwrite.
  }, [external, pending, props.busy, props.client]);

  const cutoutSource = ['m5.image.cutout', 'm5.image.inpaint'].includes(draft.operation) ? props.assets.find(row => row.id === draft.sources[0]?.id && row.version === draft.sources[0]?.version && row.sha256 === draft.sources[0]?.digest) : undefined;
  const eligibleMasks = owns && cutoutSource ? props.assets.filter(row => eligibleCutoutMask(row, cutoutSource)) : [];
  function cancelHandoff() {
    handoffRevision.current++; handoffConsumed.current = latest.current.assetHandoff; setHandoffAsset(undefined); setHandoffNotice('已取消素材交接；草稿未改变。');
  }
  return { changeLayer, swapLayers, cancelHandoff, canHandoff: canClosePrepared && !providerLoading && !props.preparedCommand && handoffOperation(draft.operation), handoffAsset: handoffAsset && handoffAsset.request === props.assetHandoff && handoffAsset.revision === handoffRevision.current ? handoffAsset.asset : undefined, handoffPending, handoffNotice, readHandoff, handoffDone: handoffConsumed.current === props.assetHandoff,
    runningControl, controlRunningCutout, canCancelRunning: !uncertain && !!selected && !sentActions.current.has(actionIdentity(selected, 'cancel')), canControlRunning: owns && props.canMutate && !!props.cutoutExecution && !!executingCutout.current && pending === 'execute' && !runningControl, eligibleMasks, draft: owns ? draft : initialDraft(), providers: owns ? providers : [], provider: owns ? provider : undefined, providerLoading, jobs: owns ? jobs : [], selected: owns ? selected : undefined,
    preview: owns && previewBinding ? preview?.value : undefined, previewReviewed: !!previewBinding && previewConsent === previewBinding,
    candidate: candidateVisible, outputReviewed: !!candidateVisible && reviewConsent === reviewBinding,
    pending, uncertain, repeatBlocked, error: owns ? error : '当前身份或项目范围待核对。', notice: owns ? notice : '', denied, dirty, locked, canEdit, canClosePrepared, inputError, freshSources, jobSourcesFresh, requiredSourceKind: owns ? sourceKind(draft.operation) : undefined,
    parameterNames: !owns ? [] : props.canvasAudioTrimTask ? ['in_ms','out_ms','gain_db','fade_in_ms','fade_out_ms'] as MediaParameter[] : draft.operation === 'm8.audio.trim' ? parametersByOperation[draft.operation] : provider ? parametersByOperation[draft.operation].filter(name => provider.supported_parameters.includes(name)) : [],
    unsupportedParameters: owns ? unsupportedParameters : [], creationUncertain: owns && !!creation.current?.uncertain,
    uncertainRequestId: owns && creation.current?.uncertain ? creation.current.requestId : undefined,
    canInspect: canEdit && !providerLoading && !inputError, canCreate: canEdit && !creation.current && !!previewBinding && previewConsent === previewBinding && impactReady('CREATE'),
    canRead: !locked, canLoadCandidate: !locked && !uncertain && !creation.current?.uncertain && jobSourcesFresh && !!selected?.output_candidate,
    imageInputs: !!provider?.image_capabilities && ['m5.image.i2i', 'm5.image.reference', 'm5.image.inpaint', 'm5.image.upscale'].includes(draft.operation),
    endFrameSource: draft.lastFrame, videoFrameCapabilities: provider?.video_frame_capabilities, selectEndFrame,
    routeSelectable: routeSelectable(draft.operation), changeRoute, changeOperation, changeField, changeParameter, clearUnsupportedParameters, selectSource, selectMask, selectReference, changeReferenceWeight, changeReferenceMetadata, clearSources, refreshSources, clearInputs, loadProviders, inspect, confirmPreview,
    audioDraft:{saved:owns?savedAudioDraft?.row:undefined,savedCurrent:!!savedAudioDraft&&savedAudioDraft.input===input,
      saveUnknown:audioSaveUnknown.current,canSave:canEdit&&!providerLoading&&!selected&&!!props.canvasAudioTrimTask&&!inputError&&freshSources,
      save:saveAudioDraft,...audioCallbacks.current,sessionInputKey:input},
    impact, confirmImpact, impactRequired:impactRequired(), inspectExecution, prepareFailedAudio, applyAudioTemplate,
    create, listJobs, openJob, canAction, action, loadCandidate, confirmReview, mediaFailed, downloadReceipt };
}
export type StudioMediaExecutionController = ReturnType<typeof useStudioMediaExecution>;
