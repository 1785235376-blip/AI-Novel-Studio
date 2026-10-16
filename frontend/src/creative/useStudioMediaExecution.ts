import { AUDIO_MP3_SAMPLE_RATES } from './studioProductionClient';
import { checkedVideoReference, type VideoReference } from './studioVideoRuntimeContract';
import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { ApiError, apiErrorView } from '../api';
import type { StudioAsset } from './studioClient';
import { eligibleCutoutMask, usableCutoutSource } from './studioCutoutContract';
import { checkedImageReferenceMetadata, checkedImageRuntimeInputs, type ImageReference, type ImageReferencePurpose } from './studioImageRuntimeContract';
import type { GraphImageOperation, GraphMediaOperation } from './studioGraphTypes';
import type { MediaCommand, RecordedMediaCommand, MediaOperation, ProductionJob, ProductionPreview, ProductionProvider, ProductionSource, StudioProductionClient } from './studioProductionClient';

export type StudioMediaExecutionProps = {
  client: StudioProductionClient; assets: StudioAsset[]; canMutate: boolean; canReview: boolean; busy: boolean; isBusy?: () => boolean;
  isCurrent: () => boolean; read: <T>(work: () => Promise<T>) => Promise<T>; mutate: <T>(work: () => Promise<T>) => Promise<T>;
  onDirtyChange: (dirty: boolean) => void; onJob?: (job: ProductionJob) => void; onUnavailable: () => void; onApproved?: () => void | Promise<void>;
  /** Explicit read-only navigation; never grants review or execution authority. */
  onOpenApprovedAsset?: (job: ProductionJob) => void;
  externalJob?: ProductionJob;
  preparedCommand?: RecordedMediaCommand; preparedIsCurrent?: () => boolean; onPreparedClose?: () => void;
  cutoutExecution?: { execute: (job: ProductionJob) => Promise<ProductionJob>; control: (kind: 'read' | 'cancel', job: ProductionJob) => Promise<ProductionJob> };
};
export const GRAPH_MEDIA_OPERATION_LABELS: Record<GraphMediaOperation, string> = {
  'm5.image.t2i': '文字生成图片', 'm5.image.i2i': '参考图片生成图片', 'm7.video.t2v': '文字生成视频',
  'm7.video.i2v': '图片生成视频', 'm7.video.v2v': '视频生成视频', 'm8.audio.speech': '语音合成',
  'm8.audio.music': '音乐生成', 'm8.audio.effects': '音效生成', 'm8.audio.trim': '本地音频截取',
};
export const GRAPH_IMAGE_OPERATION_LABELS: Record<GraphImageOperation, string> = {
  'm5.image.t2i': '文字生成图片', 'm5.image.i2i': '参考图片生成图片',
  'm5.image.reference': '多参考图生成图片', 'm5.image.inpaint': '图片局部重绘',
};
export const MEDIA_OPERATION_LABELS: Record<MediaOperation, string> = { ...GRAPH_MEDIA_OPERATION_LABELS, ...GRAPH_IMAGE_OPERATION_LABELS, 'm5.image.upscale': '本地模型图片超分', 'm5.image.cutout': '本地二值遮罩抠图' };
export const MEDIA_STATUS_LABELS: Record<ProductionJob['status'], string> = {
  QUEUED: '已入队，尚未执行', RUNNING: '正在执行', SEND_RESERVED: '已记录分派意图', REMOTE_RUNNING: '远端处理中',
  RESULT_READY: '已有结果，等待本地核对', AWAITING_REVIEW: '等待人工审核', SUCCEEDED: '处理完成，需核对审核',
  REVIEWING: '审核提交待核对', APPROVED: '已审核入库', UNKNOWN: '分派结果不确定', FAILED: '执行失败', CANCELLED: '已丢弃本地结果',
};
export type MediaParameter = 'scale' | 'width' | 'height' | 'steps' | 'seed' | 'negative_prompt' | 'size' | 'quality' | 'denoising_strength' | 'duration_seconds' | 'frame_rate' | 'voice_id' | 'speech_rate' | 'in_ms' | 'out_ms' | 'gain_db' | 'sample_rate' | 'channels' | 'output_format';
type MediaRoute = 'local' | 'cloud';
const routeSelectable = (operation: MediaOperation) => (operation.startsWith('m5.image.') || operation.startsWith('m7.video.')) && !['m5.image.cutout', 'm5.image.upscale'].includes(operation);
type Draft = { route: MediaRoute; operation: MediaOperation; providerKey: string; prompt: string; parameters: Record<MediaParameter, string>; sources: ProductionSource[]; allowCloud: boolean; licenseNote: string;
  imageSource?: ProductionSource; imageReferences: { source: ProductionSource; weight: string; purpose?: ImageReferencePurpose; source_note?: string }[]; maskSource?: ProductionSource; videoReferencePurpose?: VideoReference['purpose'] };
type Preview = { value: ProductionPreview; command: MediaCommand; input: string };
type Candidate = { url: string; kind: 'image' | 'video' | 'audio'; binding: string };
type Kind = 'PREVIEW' | 'CREATE' | 'LIST' | 'GET' | 'CANDIDATE' | 'execute' | 'refresh' | 'reconcile' | 'cancel' | 'review';
type Operation = { id: number; kind: Kind; client: StudioProductionClient; controller: AbortController; canMutate: boolean; canReview: boolean };
type Creation = { requestId: string; requestDigest: string; operation: MediaOperation; input: string; uncertain: boolean };
const parameterNames: MediaParameter[] = ['scale', 'width', 'height', 'steps', 'seed', 'negative_prompt', 'size', 'quality', 'denoising_strength', 'duration_seconds', 'frame_rate', 'voice_id', 'speech_rate', 'in_ms', 'out_ms', 'gain_db', 'sample_rate', 'channels', 'output_format'];
const parametersByOperation: Record<MediaOperation, MediaParameter[]> = {
  'm5.image.t2i': ['width', 'height', 'steps', 'seed', 'negative_prompt', 'size', 'quality'],
  'm5.image.i2i': ['width', 'height', 'steps', 'seed', 'negative_prompt', 'size', 'quality', 'denoising_strength'],
  'm5.image.reference': ['width', 'height', 'steps', 'seed', 'negative_prompt', 'size', 'quality', 'denoising_strength'],
  'm5.image.inpaint': ['width', 'height', 'steps', 'seed', 'negative_prompt', 'size', 'quality', 'denoising_strength'],
  'm5.image.cutout': [], 'm5.image.upscale': ['scale'],
  'm7.video.t2v': ['width', 'height', 'seed', 'negative_prompt', 'duration_seconds', 'frame_rate'],
  'm7.video.i2v': ['width', 'height', 'seed', 'negative_prompt', 'duration_seconds', 'frame_rate'],
  'm7.video.v2v': ['width', 'height', 'seed', 'negative_prompt', 'duration_seconds', 'frame_rate'],
  'm8.audio.speech': ['voice_id', 'speech_rate'], 'm8.audio.music': ['duration_seconds', 'seed'],
  'm8.audio.effects': ['duration_seconds', 'seed'], 'm8.audio.trim': ['in_ms', 'out_ms', 'gain_db', 'sample_rate', 'channels', 'output_format'],
};
const initialDraft = (): Draft => ({ route: 'local', operation: 'm5.image.t2i', providerKey: '', prompt: '',
  parameters: Object.fromEntries(parameterNames.map(name => [name, ''])) as Record<MediaParameter, string>, sources: [], imageReferences: [], allowCloud: false, licenseNote: '' });
const inputKey = (draft: Draft) => JSON.stringify(draft);
export const mediaProviderKey = (row: ProductionProvider) => JSON.stringify([row.operation_id, row.provider_id, row.model_id, row.route_digest]);
const jobIdentity = (job?: ProductionJob) => job ? JSON.stringify([job.owner, job.id, job.version, job.request_digest]) : '';
const actionIdentity = (job: ProductionJob, kind: string) => JSON.stringify([jobIdentity(job), kind]);
const reviewIdentity = (job?: ProductionJob) => job?.output_candidate
  ? JSON.stringify([jobIdentity(job), job.output_candidate.id, job.output_candidate.version, job.output_candidate.digest]) : '';
const uncertainFailure = (error: unknown) => !(error instanceof ApiError) || error.status === 0 || error.status >= 500 || [408, 409, 425, 429].includes(error.status) || error.problem.code === 'STUDIO_RESPONSE_INVALID';
const invalid = (message: string) => new ApiError({ status: 200, code: 'STUDIO_RESPONSE_INVALID', message });
function sourceKind(operation: MediaOperation): 'image' | 'video' | 'audio' | undefined {
  return ({ 'm5.image.i2i': 'image', 'm5.image.reference': 'image', 'm5.image.inpaint': 'image', 'm5.image.upscale': 'image', 'm5.image.cutout': 'image', 'm7.video.i2v': 'image', 'm7.video.v2v': 'video', 'm8.audio.trim': 'audio' } as Partial<Record<MediaOperation, 'image' | 'video' | 'audio'>>)[operation];
}
function usableAsset(row: StudioAsset, kind: string) {
  return row.kind === kind && !row.deleted_at && Number.isSafeInteger(row.version) && row.version >= 1 && /^[a-f0-9]{64}$/.test(row.sha256);
}
const imageSnapshot = (row: StudioAsset): ProductionSource => ({ id: row.id, kind: 'ASSET', version: row.version, digest: row.sha256, asset_kind: 'image' });
function imageSources(draft: Draft): ProductionSource[] {
  const inputs = [draft.imageSource, ...draft.imageReferences.map(reference => reference.source), draft.maskSource].filter((row): row is ProductionSource => !!row);
  return inputs.filter((row, index) => inputs.findIndex(value => value.id === row.id) === index);
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
  const ranges: Partial<Record<MediaParameter, [number, number]>> = { width: [64, 2048], height: [64, 2048], steps: [1, 150], seed: [0, 2147483647], duration_seconds: [1, 600], frame_rate: [1, 60], in_ms: [0, 600000], out_ms: [1, 600000], sample_rate: [8000, 96000], channels: [1, 2] };
  for (const name of parametersByOperation[draft.operation]) {
    const value = draft.parameters[name]; if (value === '') continue;
    if (name === 'output_format') { if (value !== 'FLAC' && value !== 'MP3') throw new Error('独立音频格式请选择 FLAC 或 MP3，或留空保留默认 WAV。'); result[name] = value; }
    else if (name === 'negative_prompt') { if (value.length > 8000) throw new Error('负向提示超过长度限制。'); result[name] = value; }
    else if (name === 'voice_id') { if (value.length > 240 || !value.trim() || /[\x00-\x1f\x7f]/.test(value)) throw new Error('请填写有效的语音标识。'); result[name] = value; }
    else if (name === 'size') { if (!['auto', '1024x1024', '1536x1024', '1024x1536'].includes(value)) throw new Error('图片规格不受支持。'); result[name] = value; }
    else if (name === 'quality') { if (!['auto', 'low', 'medium', 'high', 'standard', 'hd'].includes(value)) throw new Error('图片质量不受支持。'); result[name] = value; }
    else if (name === 'scale') { if (value !== '2' && value !== '4') throw new Error('超分倍率须明确选择 2 或 4。'); result[name] = Number(value); }
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
  if ((result.width === undefined) !== (result.height === undefined)) throw new Error('宽高需同时填写或同时留空。');
  if (draft.operation === 'm5.image.upscale' && result.scale !== 2 && result.scale !== 4) throw new Error('先明确选择 2 倍或 4 倍超分。');
  if (draft.operation === 'm8.audio.trim' && (typeof result.in_ms !== 'number' || typeof result.out_ms !== 'number' || result.out_ms <= result.in_ms || result.out_ms - result.in_ms > 120000)) throw new Error('截取需填写起止毫秒，终点须大于起点，片段最长 120 秒。');
  if (draft.operation === 'm8.audio.trim' && Math.ceil(((result.out_ms as number) - (result.in_ms as number)) * Number(result.sample_rate ?? 48000) / 1000) * Number(result.channels ?? 2) * 2 + 4096 > 25 * 1024 * 1024) throw new Error('所选时长、采样率和声道预计超过 25 MiB 输出上限，请调整后重新预览。');
  if (result.output_format === 'MP3' && Number(result.out_ms) - Number(result.in_ms) < 10) throw new Error('MP3 片段至少 10 毫秒，以保留准确的解码时长。');
  if (result.output_format === 'MP3' && !AUDIO_MP3_SAMPLE_RATES.includes(Number(result.sample_rate ?? 48000))) throw new Error('MP3 采样率仅支持 8000、11025、12000、16000、22050、24000、32000、44100、48000 Hz；请明确修改，不会自动重采样。');
  return result;
}
function commandFor(draft: Draft, providers: ProductionProvider[], assets: StudioAsset[], requestId: string): MediaCommand {
  const cutout = draft.operation === 'm5.image.cutout', localTrim = draft.operation === 'm8.audio.trim' || cutout;
  const provider = providers.find(row => mediaProviderKey(row) === draft.providerKey && row.operation_id === draft.operation);
  if (provider && routeSelectable(draft.operation) && provider.local !== (draft.route === 'local')) throw new Error('请在所选本地或云端路线中明确选择配置。');
  if (!localTrim && !provider) throw new Error('请选择当前配置中的服务商和模型。');
  if (provider && parametersByOperation[draft.operation].some(name => draft.parameters[name] !== '' && !provider.supported_parameters.includes(name))) throw new Error('所选配置不支持部分已填写参数，请明确清空这些参数或恢复原选择。');
  const upscale = draft.operation === 'm5.image.upscale';
  if (!localTrim && !upscale && (!draft.prompt.trim() || draft.prompt.length > 16000)) throw new Error('请填写本次提示词，最多 16000 字符。');
  if (upscale && provider?.local !== true) throw new Error('超分需要当前明确启用的本地服务。');
  if (provider && !provider.local && !draft.allowCloud) throw new Error('使用云端服务前，请明确确认本次发送提示词与参考素材。');
  const kind = sourceKind(draft.operation), sources = draft.sources;
  if (cutout && sources.length !== 2) throw new Error('请先选择一张 PNG 来源，再明确选择为该版本绘制的二值遮罩。');
  if (!sourcesCurrent(sources, assets, draft.operation)) throw new Error('来源素材版本已变化，请重新选取当前版本。');
  const rich = upscale || draft.operation === 'm5.image.reference' || draft.operation === 'm5.image.inpaint' || draft.imageSource !== undefined || draft.imageReferences.length > 0;
  if (kind && (!sources.length || sources.some(source => source.asset_kind !== kind) || (draft.operation === 'm5.image.i2i' ? sources.length > 5
    : draft.operation === 'm5.image.reference' ? sources.length > 5 : sources.length !== (cutout || draft.operation === 'm5.image.inpaint' ? 2 : 1)))) throw new Error(kind === 'image' ? '请选取对应数量的图片来源。' : '请选取一个对应类型的来源素材。');
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
  return { operation_id: draft.operation, request_id: requestId, provider_id: localTrim ? null : provider!.provider_id,
    model_id: localTrim ? null : provider!.model_id, prompt: localTrim || upscale ? '' : draft.prompt, parameters: parameters(draft),
    source_snapshots: sources.map(source => ({ ...source })), allow_cloud: localTrim || upscale ? false : draft.allowCloud, license_note: draft.licenseNote, ...image, ...checkedVideoReference(draft.videoReferencePurpose ? { source: sources[0], purpose: draft.videoReferencePurpose } : undefined, sources, draft.operation) };
}

/** Draft, exact receipts and private media lifetime remain independent of rendering. */
export function useStudioMediaExecution(props: StudioMediaExecutionProps) {
  const [draft, setDraft] = useState<Draft>(initialDraft), [providers, setProviders] = useState<ProductionProvider[]>([]);
  const [providerLoading, setProviderLoading] = useState(false), [jobs, setJobs] = useState<ProductionJob[]>([]), [selected, setSelected] = useState<ProductionJob>();
  const [preview, setPreview] = useState<Preview>(), [previewConsent, setPreviewConsent] = useState(''), [reviewConsent, setReviewConsent] = useState('');
  const [candidate, setCandidate] = useState<Candidate>(), [pending, setPending] = useState<Kind>(), [uncertain, setUncertain] = useState(false);
  const [runningControl, setRunningControl] = useState<'read' | 'cancel'>();
  const runningControlRef = useRef<'read' | 'cancel'>(), executingCutout = useRef<ProductionJob>(), controlFence = useRef(0);
  const [denied, setDenied] = useState(false), [error, setError] = useState(''), [notice, setNotice] = useState('');
  const latest = useRef(props); latest.current = props;
  const alive = useRef(true), revoked = useRef(false), owner = useRef(props.client), epoch = useRef(0), slot = useRef<Operation>();
  const providerEpoch = useRef(0), providerRead = useRef<AbortController>(), candidateRef = useRef<Candidate>();
  const draftRef = useRef(draft), selectedRef = useRef(selected), previewRef = useRef(preview), uncertainRef = useRef(uncertain);
  const previewConsentRef = useRef(previewConsent), reviewConsentRef = useRef(reviewConsent), providersRef = useRef(providers);
  const creation = useRef<Creation>(), baseline = useRef(inputKey(initialDraft()));
  const sentActions = useRef(new Set<string>()), consumedExternal = useRef('');
  const receiptDownload = useRef<string>(), receiptTimer = useRef<ReturnType<typeof setTimeout>>();
  draftRef.current = draft; selectedRef.current = selected; previewRef.current = preview; uncertainRef.current = uncertain;
  previewConsentRef.current = previewConsent; reviewConsentRef.current = reviewConsent; providersRef.current = providers;
  const preparedOwner = useRef(JSON.stringify(props.preparedCommand));
  const preparedCurrent = () => preparedOwner.current === JSON.stringify(latest.current.preparedCommand) && (!latest.current.preparedCommand || latest.current.preparedIsCurrent?.() === true);
  const current = () => preparedCurrent() && alive.current && !revoked.current && owner.current === latest.current.client && latest.current.isCurrent();
  const busy = () => !!slot.current || !!runningControlRef.current || latest.current.busy || !!latest.current.isBusy?.() || !current();
  const owns = preparedCurrent() && !denied && owner.current === props.client && props.isCurrent();
  const input = inputKey(draft), freshSources = sourcesCurrent(draft.sources, props.assets, draft.operation);
  const sourceState = JSON.stringify(draft.sources.map(source => { const row = props.assets.find(asset => asset.id === source.id); return [source.id, row?.version, row?.sha256, row?.deleted_at, row?.kind, row?.manual_mask, row?.provenance]; }));
  const jobSources = selected?.sources.filter((source): source is ProductionSource => source.kind === 'ASSET') || [];
  const jobSourcesFresh = sourcesCurrent(jobSources, props.assets, selected?.operation_id);
  const jobSourceState = JSON.stringify(jobSources.map(source => { const row = props.assets.find(asset => asset.id === source.id); return [source.id, row?.version, row?.sha256, row?.deleted_at, row?.kind, row?.manual_mask, row?.provenance]; }));
  const provider = providers.find(row => mediaProviderKey(row) === draft.providerKey && row.operation_id === draft.operation);
  const unsupportedParameters = provider ? parametersByOperation[draft.operation].filter(name => draft.parameters[name] !== '' && !provider.supported_parameters.includes(name)) : [];
  const previewBinding = preview && preview.input === input && freshSources ? JSON.stringify([input, preview.value.preview_digest, preview.value.request_digest]) : '';
  const reviewBinding = reviewIdentity(selected), candidateVisible = owns && candidate?.binding === reviewBinding && jobSourcesFresh ? candidate : undefined;
  const repeatBlocked = !!selected && ['execute', 'refresh', 'reconcile', 'cancel', 'review'].some(kind => sentActions.current.has(actionIdentity(selected, kind)));
  const dirty = owns && (input !== baseline.current || uncertain || repeatBlocked || !!pending && ['CREATE', 'review', 'execute', 'refresh', 'reconcile', 'cancel'].includes(pending));
  const locked = !owns || props.busy || !!runningControl || !!pending || !!props.isBusy?.();
  const canEdit = !locked && props.canMutate && !uncertain && !creation.current?.uncertain;
  const canClosePrepared = canEdit && (!selected || !['UNKNOWN', 'RUNNING', 'SEND_RESERVED', 'REMOTE_RUNNING', 'RESULT_READY', 'REVIEWING'].includes(selected.status));
  let inputError = ''; try { if (!props.preparedCommand) commandFor(draft, providers, props.assets, 'shape_check'); } catch (reason) { inputError = reason instanceof Error ? reason.message : '请核对输入。'; }

  function clearReceiptDownload() { if (receiptTimer.current !== undefined) clearTimeout(receiptTimer.current); receiptTimer.current = undefined;
    if (receiptDownload.current) URL.revokeObjectURL(receiptDownload.current); receiptDownload.current = undefined; }
  function clearCandidate() { clearReceiptDownload(); if (candidateRef.current) URL.revokeObjectURL(candidateRef.current.url); candidateRef.current = undefined; setCandidate(undefined); reviewConsentRef.current = ''; setReviewConsent(''); }
  function clearPreview() { previewRef.current = undefined; previewConsentRef.current = ''; setPreview(undefined); setPreviewConsent(''); }
  function markUncertain(value: boolean) { uncertainRef.current = value; setUncertain(value); }
  function unavailable() {
    if (!alive.current) return;
    revoked.current = true; epoch.current++; providerEpoch.current++; slot.current?.controller.abort(); slot.current = undefined; providerRead.current?.abort();
    clearCandidate(); clearPreview(); selectedRef.current = undefined; setSelected(undefined); setJobs([]); setProviders([]); setPending(undefined); setProviderLoading(false);
    const empty = initialDraft(); draftRef.current = empty; setDraft(empty); creation.current = undefined; baseline.current = inputKey(empty);
    setDenied(true); setError('身份、权限或项目入口已经变化，请重新打开当前项目。'); latest.current.onDirtyChange(false); latest.current.onUnavailable();
  }
  function failure(reason: unknown, fallback: string, mutation = false) {
    if (reason instanceof ApiError && [401, 403, 404, 410, 501].includes(reason.status)) { unavailable(); return; }
    setError(apiErrorView(reason, fallback).message);
    if (mutation && uncertainFailure(reason)) { markUncertain(true); clearCandidate(); clearPreview(); }
  }
  function begin(kind: Kind): Operation | undefined {
    if (busy()) return;
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
    draftRef.current = next; setDraft(next); clearPreview(); if (!creation.current?.uncertain) creation.current = undefined; setError(''); setNotice('');
  }
  function changeOperation(operation: MediaOperation) { if (Object.hasOwn(MEDIA_OPERATION_LABELS, operation)) edit({ ...initialDraft(), operation, licenseNote: draftRef.current.licenseNote }); }
  function changeRoute(route: MediaRoute) {
    const old = draftRef.current;
    if (!routeSelectable(old.operation) || !['local', 'cloud'].includes(route) || route === old.route) return;
    const chosen = providersRef.current.find(row => mediaProviderKey(row) === old.providerKey && row.operation_id === old.operation);
    edit({ ...old, route, providerKey: chosen?.local === (route === 'local') ? old.providerKey : '', allowCloud: false });
  }
  function changeField(field: 'prompt' | 'licenseNote' | 'allowCloud' | 'providerKey' | 'videoReferencePurpose', value: string | boolean) {
    const next = { ...draftRef.current };
    if (field === 'videoReferencePurpose') { if (typeof value !== 'string' || value !== '' && !['style', 'action', 'camera'].includes(value)) return; if (value === '') delete next.videoReferencePurpose; else next.videoReferencePurpose = value as VideoReference['purpose']; next.allowCloud = false; edit(next); return; }
    if (field === 'allowCloud') { if (typeof value !== 'boolean') return; next.allowCloud = value; }
    else { if (typeof value !== 'string') return; next[field] = value; if (field === 'providerKey' || field === 'prompt' && (next.imageSource || next.imageReferences.length || ['m5.image.reference', 'm5.image.inpaint'].includes(next.operation))) next.allowCloud = false; }
    edit(next);
  }
  function changeParameter(name: MediaParameter, value: string) { if (parameterNames.includes(name)) edit({ ...draftRef.current, parameters: { ...draftRef.current.parameters, [name]: value } }); }
  function clearUnsupportedParameters() {
    const old = draftRef.current, selectedProvider = providersRef.current.find(row => mediaProviderKey(row) === old.providerKey && row.operation_id === old.operation);
    if (!selectedProvider) return;
    const next = { ...old.parameters };
    for (const name of parametersByOperation[old.operation]) if (!selectedProvider.supported_parameters.includes(name)) next[name] = '';
    edit({ ...old, parameters: next });
  }
  function selectSource(id: string, checked: boolean) {
    const old = draftRef.current, kind = sourceKind(old.operation); if (!kind) return;
    const row = latest.current.assets.find(asset => asset.id === id && usableAsset(asset, kind) && (old.operation !== 'm5.image.cutout' || usableCutoutSource(asset)));
    if (old.operation === 'm5.image.cutout') {
      if (checked && !row) { setError('PNG 来源不可用，请重新读取素材。'); return; }
      edit({ ...old, sources: checked && row ? [{ id: row.id, kind: 'ASSET', version: row.version, digest: row.sha256, asset_kind: 'image' }] : [] }); return;
    }
    const selectedProvider = providersRef.current.find(provider => mediaProviderKey(provider) === old.providerKey && provider.operation_id === old.operation);
    if (old.operation === 'm5.image.upscale' || old.operation === 'm5.image.inpaint' || old.operation === 'm5.image.i2i' && !!selectedProvider?.image_capabilities) {
      if (checked && (!row || old.operation === 'm5.image.inpaint' && !usableCutoutSource(row))) { setError('图片来源不可用，请重新读取素材。'); return; }
      if (checked && old.imageReferences.some(reference => reference.source.id === id)) { setError('参考素材已绑定为辅助输入，请明确移除该参考后再选择基础图。'); return; }
      const next = { ...old, imageSource: checked && row ? imageSnapshot(row) : undefined, maskSource: undefined, allowCloud: false };
      edit({ ...next, sources: imageSources(next) }); return;
    }
    if (checked && !row) { setError('来源不可用，请重新读取素材。'); return; }
    let sources = old.sources.filter(source => source.id !== id);
    if (checked && row) {
      if (old.operation !== 'm5.image.i2i') sources = [];
      if (sources.length >= 5) { setError('最多选取五张参考图片。'); return; }
      sources.push({ id: row.id, kind: 'ASSET', version: row.version, digest: row.sha256, asset_kind: kind });
    }
    edit({ ...old, sources });
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
    const old = draftRef.current, kind = sourceKind(old.operation); if (!kind) return;
    const sources: ProductionSource[] = [];
    for (const source of ['m5.image.cutout', 'm5.image.inpaint'].includes(old.operation) ? old.sources.slice(0, 1) : old.sources) {
      const row = latest.current.assets.find(asset => asset.id === source.id && usableAsset(asset, kind));
      if (!row) { setError('已选来源已删除或不可用，请先移除该来源。'); return; }
      sources.push({ id: row.id, kind: 'ASSET', version: row.version, digest: row.sha256, asset_kind: kind });
    }
    if (old.imageSource || old.imageReferences.length || old.operation === 'm5.image.inpaint') {
      const next = { ...old, allowCloud: false, imageSource: old.imageSource ? sources.find(row => row.id === old.imageSource!.id) : undefined,
        imageReferences: old.imageReferences.map(reference => ({ ...reference, source: sources.find(row => row.id === reference.source.id)! })), maskSource: undefined };
      edit({ ...next, sources: imageSources(next) });
    } else edit({ ...old, sources });
  }
  function selectReference(id: string, checked: boolean) {
    const old = draftRef.current;
    if (!['m5.image.reference', 'm5.image.i2i'].includes(old.operation)) return;
    const provider = providersRef.current.find(row => mediaProviderKey(row) === old.providerKey && row.operation_id === old.operation);
    if (!provider?.image_capabilities) return;
    const asset = latest.current.assets.find(row => row.id === id && usableAsset(row, 'image') && !row.manual_mask);
    if (checked && !asset) { setError('参考素材不可用，请重新读取素材。'); return; }
    const references = old.imageReferences.filter(reference => reference.source.id !== id);
    if (checked && asset) {
      if (asset.id === old.imageSource?.id) { setError('基础图不能同时作为辅助参考，请选择不同素材。'); return; }
      const limit = old.operation === 'm5.image.i2i' ? Math.min(4, Math.max(0, provider.image_capabilities.reference_limit - 1)) : provider.image_capabilities.reference_limit;
      if (references.length >= limit) { setError('参考图数量超过当前路线的上限。'); return; }
      references.push({ source: imageSnapshot(asset), weight: '1' });
    }
    const next = { ...old, imageReferences: references, allowCloud: false }; edit({ ...next, sources: imageSources(next) });
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
  function clearSources() { edit({ ...draftRef.current, sources: [], imageSource: undefined, imageReferences: [], maskSource: undefined,
    allowCloud: draftRef.current.imageSource || draftRef.current.imageReferences.length || ['m5.image.reference', 'm5.image.inpaint'].includes(draftRef.current.operation) ? false : draftRef.current.allowCloud }); }
  function clearInputs() { if (!current() || busy() || !latest.current.canMutate || uncertainRef.current || creation.current?.uncertain) return;
    if (latest.current.preparedCommand) { if (selectedRef.current && ['UNKNOWN', 'RUNNING', 'SEND_RESERVED', 'REMOTE_RUNNING', 'RESULT_READY', 'REVIEWING'].includes(selectedRef.current.status)) return; latest.current.onPreparedClose?.(); return; }
    edit(initialDraft()); baseline.current = inputKey(initialDraft()); clearCandidate(); }

  async function loadProviders() {
    if (!current() || busy()) return;
    const client = latest.current.client, id = ++providerEpoch.current, controller = new AbortController(); providerRead.current?.abort(); providerRead.current = controller;
    setProviderLoading(true); clearPreview();
    try {
      const rows = await latest.current.read(() => client.providers(controller.signal));
      if (!current() || controller.signal.aborted || providerEpoch.current !== id || client !== latest.current.client) return;
      providersRef.current = rows; setProviders(rows);
    } catch (reason) { if (current() && !controller.signal.aborted && providerEpoch.current === id) failure(reason, '服务商配置读取失败。'); }
    finally { if (alive.current && providerEpoch.current === id) setProviderLoading(false); }
  }
  async function inspect() {
    if (!latest.current.canMutate || uncertainRef.current || creation.current?.uncertain || providerLoading) return;
    const value = begin('PREVIEW'); if (!value) return;
    const captured = inputKey(draftRef.current); clearPreview();
    try {
      const command = latest.current.preparedCommand ? structuredClone(latest.current.preparedCommand) as MediaCommand : commandFor(draftRef.current, providersRef.current, latest.current.assets, crypto.randomUUID());
      const result = await latest.current.read(() => value.client.preview(command));
      if (!live(value) || captured !== inputKey(draftRef.current) || !sourcesCurrent(command.source_snapshots, latest.current.assets, command.operation_id)) return;
      const chosen = providersRef.current.find(row => latest.current.preparedCommand ? row.operation_id === command.operation_id && row.provider_id === command.provider_id && row.model_id === command.model_id : mediaProviderKey(row) === draftRef.current.providerKey);
      if (!['m8.audio.trim', 'm5.image.cutout'].includes(command.operation_id) && (!chosen || !result.provider || result.provider.route_digest !== chosen.route_digest || result.provider.local !== chosen.local)) throw invalid('服务商路线已变化，请重新读取配置并预览。');
      const next = { value: result, command, input: captured }; previewRef.current = next; setPreview(next);
      setNotice('预览已读取；尚未创建任务，也未执行媒体处理。');
    } catch (reason) { if (live(value)) failure(reason, '制作预览未完成。'); } finally { finish(value); }
  }
  function confirmPreview(checked: boolean) { if (!current() || busy()) return; const key = previewRef.current && previewRef.current.input === inputKey(draftRef.current) && sourcesCurrent(draftRef.current.sources, latest.current.assets, draftRef.current.operation)
    ? JSON.stringify([previewRef.current.input, previewRef.current.value.preview_digest, previewRef.current.value.request_digest]) : ''; previewConsentRef.current = checked ? key : ''; setPreviewConsent(previewConsentRef.current); }
  async function create() {
    const saved = previewRef.current;
    if (!current() || !latest.current.canMutate || uncertainRef.current || creation.current || !saved || saved.input !== inputKey(draftRef.current) || !sourcesCurrent(saved.command.source_snapshots, latest.current.assets, saved.command.operation_id)) return;
    const binding = JSON.stringify([saved.input, saved.value.preview_digest, saved.value.request_digest]); if (previewConsentRef.current !== binding) return;
    const value = begin('CREATE'); if (!value) return;
    creation.current = { requestId: saved.command.request_id, requestDigest: saved.value.request_digest, operation: saved.command.operation_id, input: saved.input, uncertain: true };
    try {
      const result = await latest.current.mutate(() => value.client.create(saved.command, saved.value.preview_digest));
      if (!live(value)) return;
      if (result.request_digest !== saved.value.request_digest || result.status !== 'QUEUED') throw invalid('入队回执与预览不一致，请读取任务核对。');
      creation.current = { ...creation.current!, uncertain: false }; baseline.current = saved.input;
      adoptJob(result); clearPreview(); markUncertain(false); setNotice('任务已保存入队。执行仍需单独点击。');
    } catch (reason) { if (live(value)) { if (!uncertainFailure(reason)) creation.current = undefined; failure(reason, '任务入队未完成，请读取核对。', true); } } finally { finish(value); }
  }
  async function listJobs() {
    const value = begin('LIST'); if (!value) return;
    try {
      const rows = await latest.current.read(() => value.client.list(value.controller.signal)); if (!live(value)) return;
      const visibleRows = latest.current.preparedCommand ? rows.filter(row => row.request_id === latest.current.preparedCommand!.request_id && row.operation_id === latest.current.preparedCommand!.operation_id) : rows;
      setJobs(visibleRows);
      if (creation.current?.uncertain) {
        const attempt = creation.current, match = rows.find(row => row.request_id === attempt.requestId && row.operation_id === attempt.operation && row.request_digest === attempt.requestDigest);
        if (match) { creation.current = { ...attempt, uncertain: false }; baseline.current = attempt.input; adoptJob(match); markUncertain(false); setNotice('已找到原请求的保存记录；不会重新创建或执行。'); }
        else setNotice('尚未找到原请求回执。保留不确定状态，请勿重复发送。');
      } else if (selectedRef.current) {
        const old = selectedRef.current, match = rows.find(row => row.owner === old.owner && row.id === old.id);
        if (match) { adoptJob(match); markUncertain(false); } else { clearCandidate(); selectedRef.current = undefined; setSelected(undefined); }
      }
    } catch (reason) { if (live(value)) failure(reason, '任务列表读取失败。'); } finally { finish(value); }
  }
  async function openJob(job: ProductionJob) {
    const prepared = latest.current.preparedCommand; if (prepared && (job.request_id !== prepared.request_id || job.operation_id !== prepared.operation_id)) return;
    const value = begin('GET'); if (!value) return; clearCandidate();
    try {
      const result = await latest.current.read(() => value.client.get(job.owner, job.id, value.controller.signal)); if (!live(value)) return;
      if (prepared && (result.request_id !== prepared.request_id || result.operation_id !== prepared.operation_id)) throw invalid('原任务与当前分镜请求不一致，请读取该请求回执。');
      adoptJob(result); if (!creation.current?.uncertain) markUncertain(false); setNotice('已读取当前任务版本；未重新执行。');
    } catch (reason) { if (live(value)) failure(reason, '任务读取失败。'); } finally { finish(value); }
  }
  function canAction(kind: 'execute' | 'refresh' | 'reconcile' | 'cancel' | 'review') {
    const job = selectedRef.current;
    if (!job || busy() || uncertainRef.current || creation.current?.uncertain || sentActions.current.has(actionIdentity(job, kind))) return false;
    const assetSources = job.sources.filter((source): source is ProductionSource => source.kind === 'ASSET');
    const fresh = sourcesCurrent(assetSources, latest.current.assets, job.operation_id);
    if (kind === 'review') return latest.current.canReview && fresh && ['AWAITING_REVIEW', 'SUCCEEDED', 'REVIEWING'].includes(job.status)
      && !!job.output_candidate && candidateRef.current?.binding === reviewIdentity(job) && reviewConsentRef.current === reviewIdentity(job);
    if (!latest.current.canMutate) return false;
    if (kind === 'execute') return job.owner !== 'timeline' && job.status === 'QUEUED' && fresh;
    if (kind === 'refresh') return job.owner === 'video' && ['REMOTE_RUNNING', 'RESULT_READY', 'UNKNOWN'].includes(job.status);
    if (kind === 'reconcile') return job.operation_id === 'm5.image.cutout' && job.status === 'CANCELLED' ? !!job.processing_proof && !job.output_candidate : job.owner === 'timeline' ? ['RUNNING', 'UNKNOWN', 'REVIEWING'].includes(job.status)
      : job.owner === 'video' ? ['RUNNING', 'SEND_RESERVED', 'UNKNOWN', 'RESULT_READY', 'REVIEWING'].includes(job.status)
      : ['RUNNING', 'UNKNOWN', 'REVIEWING'].includes(job.status);
    return job.operation_id === 'm5.image.cutout' ? ['QUEUED', 'RUNNING', 'UNKNOWN', 'AWAITING_REVIEW'].includes(job.status)
      : job.owner === 'timeline' ? ['RUNNING', 'UNKNOWN', 'SUCCEEDED', 'AWAITING_REVIEW'].includes(job.status)
      : ['QUEUED', 'AWAITING_REVIEW', 'UNKNOWN', 'REMOTE_RUNNING', 'RESULT_READY'].includes(job.status);
  }
  async function action(kind: 'execute' | 'refresh' | 'reconcile' | 'cancel' | 'review') {
    if (!canAction(kind)) return; const job = selectedRef.current!;
    const value = begin(kind); if (!value) return; clearCandidate();
    const sentKey = actionIdentity(job, kind); sentActions.current.add(sentKey);
    const localExecution = kind === 'execute' && job.operation_id === 'm5.image.cutout' && latest.current.cutoutExecution;
    if (localExecution) executingCutout.current = job;
    const responseFence = controlFence.current;
    try {
      const result = await (localExecution ? localExecution.execute(job) : latest.current.mutate(() => value.client[kind](job))); if (!live(value)) return;
      if (localExecution && responseFence !== controlFence.current) {
        if (runningControlRef.current || uncertainRef.current || selectedRef.current?.version && result.version <= selectedRef.current.version) return;
        if (selectedRef.current?.status === 'CANCELLED') return;
      }
      if (result.version < job.version || result.request_digest !== job.request_digest || result.id !== job.id || result.operation_id !== job.operation_id) throw invalid('原任务响应版本或身份不一致，请重新读取。');
      adoptJob(result); markUncertain(false);
      setNotice(kind === 'cancel' ? result.owner === 'timeline'
        ? result.cancellation_mode === 'LOCAL_RENDER_PROCESS_STOP_REQUESTED' ? '已记录停止本地渲染进程的请求；请重新读取原任务核对。已有回执与候选保留，不能继续采用。' : '已取消此未审核时间线结果的采用权限，原回执与候选保留。'
        : result.operation_id === 'm5.image.cutout' ? '已记录本地取消并撤销候选采用权限；请读取原任务核对。不会自动重试。' : '已丢弃本地结果的采用权限；远端计算可能继续。'
        : kind === 'review' ? '已保存审核回执，请核对当前素材库。' : kind === 'reconcile' ? '已核对本地中断状态，未重新提交媒体生成。' : '已收到任务回执，请核对状态与候选结果。');
      if (kind === 'review' && result.status === 'APPROVED') {
        const approved = jobIdentity(result);
        try { void Promise.resolve(latest.current.onApproved?.()).catch(() => {
          if (current() && jobIdentity(selectedRef.current) === approved) setError('审核已经保存，但素材列表刷新未完成，请重新读取。');
        }); } catch { setError('审核已经保存，但素材列表刷新未完成，请重新读取。'); }
      }
    } catch (reason) { if (live(value)) { if (localExecution && responseFence !== controlFence.current && selectedRef.current?.status === 'CANCELLED' && !uncertainRef.current) return; if (!uncertainFailure(reason)) sentActions.current.delete(sentKey); failure(reason, '操作结果未确认，请读取任务核对。', true); } } finally { if (localExecution && executingCutout.current === job) executingCutout.current = undefined; finish(value); }
  }
  async function controlRunningCutout(kind: 'read' | 'cancel') {
    const original = executingCutout.current, active = slot.current, method = latest.current.cutoutExecution?.control;
    if (!current() || !latest.current.canMutate || !original || !active || active.kind !== 'execute' || !method || runningControlRef.current) return;
    const expected = selectedRef.current;
    if (!expected || expected.id !== original.id || expected.request_digest !== original.request_digest || expected.operation_id !== 'm5.image.cutout') return;
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
      if (job.operation_id === 'm5.image.cutout' && (blob.type !== 'image/png' || blob.size !== job.processing_proof?.output_bytes)) throw invalid('本地抠图候选与处理证明不一致，不可审核。');
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
    const empty = initialDraft(); draftRef.current = empty; setDraft(empty); baseline.current = inputKey(empty); selectedRef.current = undefined; setSelected(undefined);
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
  return { runningControl, controlRunningCutout, canCancelRunning: !uncertain && !!selected && !sentActions.current.has(actionIdentity(selected, 'cancel')), canControlRunning: owns && props.canMutate && !!props.cutoutExecution && !!executingCutout.current && pending === 'execute' && !runningControl, eligibleMasks, draft: owns ? draft : initialDraft(), providers: owns ? providers : [], provider: owns ? provider : undefined, providerLoading, jobs: owns ? jobs : [], selected: owns ? selected : undefined,
    preview: owns && previewBinding ? preview?.value : undefined, previewReviewed: !!previewBinding && previewConsent === previewBinding,
    candidate: candidateVisible, outputReviewed: !!candidateVisible && reviewConsent === reviewBinding,
    pending, uncertain, repeatBlocked, error: owns ? error : '当前身份或项目范围待核对。', notice: owns ? notice : '', denied, dirty, locked, canEdit, canClosePrepared, inputError, freshSources, jobSourcesFresh, requiredSourceKind: owns ? sourceKind(draft.operation) : undefined,
    parameterNames: !owns ? [] : draft.operation === 'm8.audio.trim' ? parametersByOperation[draft.operation] : provider ? parametersByOperation[draft.operation].filter(name => provider.supported_parameters.includes(name)) : [],
    unsupportedParameters: owns ? unsupportedParameters : [], creationUncertain: owns && !!creation.current?.uncertain,
    uncertainRequestId: owns && creation.current?.uncertain ? creation.current.requestId : undefined,
    canInspect: canEdit && !providerLoading && !inputError, canCreate: canEdit && !creation.current && !!previewBinding && previewConsent === previewBinding,
    canRead: !locked, canLoadCandidate: !locked && !uncertain && !creation.current?.uncertain && jobSourcesFresh && !!selected?.output_candidate,
    imageInputs: !!provider?.image_capabilities && ['m5.image.i2i', 'm5.image.reference', 'm5.image.inpaint', 'm5.image.upscale'].includes(draft.operation),
    routeSelectable: routeSelectable(draft.operation), changeRoute, changeOperation, changeField, changeParameter, clearUnsupportedParameters, selectSource, selectMask, selectReference, changeReferenceWeight, changeReferenceMetadata, clearSources, refreshSources, clearInputs, loadProviders, inspect, confirmPreview,
    create, listJobs, openJob, canAction, action, loadCandidate, confirmReview, mediaFailed, downloadReceipt };
}
export type StudioMediaExecutionController = ReturnType<typeof useStudioMediaExecution>;
