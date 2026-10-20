import type { StudioAsset } from '../../creative/studioClient';
import type { ProductionJob } from '../../creative/studioProductionClient';

export type ExecutionSelection = {
  projectId: string; branchId: string | null; identity: string;
  job: Pick<ProductionJob, 'owner' | 'id' | 'version' | 'request_id' | 'request_digest'>;
};
export type ExecutionAssetPin = { id: string; version: number; digest: string; kind: string };
export type ExecutionProjection = {
  jobId: string; requestId: string; version: number; status: ProductionJob['status']; operationId: string;
  requestDigest: string; receiptDigest: string | null;
  provider: { providerId: string; modelId: string; local: boolean; routeDigest: string } | null;
  parameters: { name: string; value: string }[];
  sources: { id: string; kind: string; version: number; digest: string }[];
  candidate: ExecutionAssetPin | null; approvedAssetVersion: number | null;
  executionKind: string; recoveryReason: string; remoteComputeMayContinue: boolean; errorCode: string | null;
};

const credential = /(?:^(?:sk[-_]|bearer|api[-_]?key|secret[-_]|token[-_])|[?=&\s\\]|:\/\/)/i;
export const isExecutionIdentifier = (value: unknown): value is string => typeof value === 'string'
  && /^[A-Za-z0-9][A-Za-z0-9_-]{0,239}$/.test(value) && !credential.test(value);
const id = isExecutionIdentifier;
const digest = (value: unknown): value is string => typeof value === 'string' && /^[a-f0-9]{64}$/.test(value);
const version = (value: unknown): value is number => Number.isSafeInteger(value) && Number(value) > 0;
const routeId = (value: unknown): value is string => typeof value === 'string'
  && /^[A-Za-z0-9][A-Za-z0-9_./-]{0,239}$/.test(value) && !credential.test(value);
const states: readonly string[] = ['QUEUED', 'RUNNING', 'SEND_RESERVED', 'REMOTE_RUNNING', 'RESULT_READY', 'AWAITING_REVIEW', 'SUCCEEDED', 'REVIEWING', 'APPROVED', 'UNKNOWN', 'FAILED', 'CANCELLED'];
const owners: readonly string[] = ['image', 'audio', 'video', 'timeline'];
const fail = (): never => { throw new Error('原任务或素材来源不完整、版本已退回或范围不匹配，请重新读取核对。'); };

function validJob(job: ProductionJob) {
  if (!job || job.contract !== 'studio-production-job/1' || !id(job.id) || !id(job.request_id)
    || !id(job.novel_id) || job.branch_id !== null && !id(job.branch_id) || !version(job.version)
    || !owners.includes(job.owner) || !states.includes(job.status) || !digest(job.request_digest)
    || job.receipt_digest !== null && !digest(job.receipt_digest) || job.automatic_replay !== false
    || !Array.isArray(job.sources) || job.sources.length > 30) fail();
}

/** Read freshness only. A newer Job version never grants an execution or adoption action. */
export function assertExecutionJob(job: ProductionJob, selection: ExecutionSelection): void {
  validJob(job);
  const expected = selection.job;
  if (!selection.identity || !id(selection.projectId) || selection.branchId !== null && !id(selection.branchId)
    || !expected || !id(expected.id) || !id(expected.request_id) || !version(expected.version) || !digest(expected.request_digest)
    || job.novel_id !== selection.projectId || job.branch_id !== selection.branchId || job.owner !== expected.owner
    || job.id !== expected.id || job.request_id !== expected.request_id || job.request_digest !== expected.request_digest
    || job.version < expected.version) fail();
}

const numericParameters = new Set(['scale', 'width', 'height', 'steps', 'seed', 'cfg', 'denoising_strength',
  'duration_seconds', 'frame_rate', 'speech_rate', 'in_ms', 'out_ms', 'gain_db', 'sample_rate', 'channels',
  'fade_in_ms', 'fade_out_ms', 'target_peak_dbfs', 'target_lufs']);
const enumParameters: Record<string, readonly string[]> = {
  size: ['auto', '1024x1024', '1536x1024', '1024x1536'],
  quality: ['auto', 'low', 'medium', 'high', 'standard', 'hd'],
  output_format: ['PNG', 'JPEG', 'WEBP', 'WAV', 'FLAC', 'MP3'],
  cutout_output: ['WEBP_LOSSLESS_V1'],
  denoise_profile: ['STATIONARY_FFT_V1'],
};

function recoveryReason(job: ProductionJob): string {
  if (job.status === 'UNKNOWN') return 'UNKNOWN：执行结果不确定，只允许重新读取与诊断，禁止重放。远端任务可能继续。';
  if (job.status === 'FAILED') return '原 Job 没有安全的失败重试契约；此处仅重新读取与诊断，不能重放或创建替代任务。';
  if (job.status === 'CANCELLED') return '取消记录保留；此处没有恢复或重试契约，只能重新读取与诊断。';
  if (job.status === 'APPROVED') return '原审核已完成；正式资产仍需精确读取核验，采用到作品位置须在原入口另行确认。';
  if (job.output_candidate) return '候选记录不代表正式审核或已采用；请在原任务核对审核，本面板只读取与诊断。';
  return '仅重新读取原 Job 与诊断；执行、审核和采用仍由原入口明确确认，此处不会自动重试。';
}

/** Explicit allowlist: never serialize the command, recipe workflow, prompt, credentials or raw diagnostics. */
export function projectExecution(job: ProductionJob): ExecutionProjection {
  validJob(job);
  const parameters: ExecutionProjection['parameters'] = [];
  for (const [name, value] of Object.entries(job.command?.parameters ?? {})) {
    if (numericParameters.has(name) && typeof value === 'number' && Number.isFinite(value)
      || Object.hasOwn(enumParameters, name) && typeof value === 'string' && enumParameters[name].includes(value)) {
      parameters.push({ name, value: String(value) });
    }
  }
  const sources = job.sources.map(source => {
    if (!id(source.id) || !version(source.version) || !digest(source.digest)
      || !['ASSET', 'CREATIVE_DOCUMENT', 'COMIC_PANEL'].includes(source.kind)) fail();
    return { id: source.id, kind: source.kind, version: source.version, digest: source.digest };
  });
  let candidate: ExecutionAssetPin | null = null;
  if (job.output_candidate) {
    const pin = job.output_candidate;
    if (!id(pin.id) || !version(pin.version) || !digest(pin.digest) || !['image', 'video', 'audio'].includes(pin.kind)) fail();
    candidate = { id: pin.id, version: pin.version, digest: pin.digest, kind: pin.kind };
  }
  const provider = job.provider && routeId(job.provider.provider_id) && routeId(job.provider.model_id)
    && digest(job.provider.route_digest) && typeof job.provider.local === 'boolean'
    ? { providerId: job.provider.provider_id, modelId: job.provider.model_id, local: job.provider.local, routeDigest: job.provider.route_digest } : null;
  const executionKind = job.provider?.local === false || job.execution_recipe?.adapter === 'ORIGINAL_HTTP_PROVIDER'
    ? '服务接口调用；云端内部节点不可见。接口记录不等于真实模型推理验证。'
    : job.provider?.local === true ? '原记录声明本地执行；配方声明不等于真实模型推理验证。'
      : ['LOCAL_CPU_MASK', 'LOCAL_FFMPEG', 'LOCAL_CPU_COMPOSITE'].includes(job.execution_recipe?.adapter)
        ? '原记录声明本地媒体处理；该路线不使用生成模型。'
      : '原回执未提供可确认的模型路线；不会补造来源或内部节点。';
  return {
    jobId: job.id, requestId: job.request_id, version: job.version, status: job.status,
    operationId: /^m[0-9]+\.[a-z]+\.[a-z0-9]+$/.test(job.operation_id) ? job.operation_id : '未提供可显示的操作标识',
    requestDigest: job.request_digest, receiptDigest: job.receipt_digest,
    provider, parameters, sources, candidate,
    approvedAssetVersion: job.status === 'APPROVED' && version(job.approved_asset_version) ? job.approved_asset_version : null,
    executionKind, recoveryReason: recoveryReason(job), remoteComputeMayContinue: job.remote_compute_may_continue === true,
    errorCode: typeof job.error_code === 'string' && /^[A-Z][A-Z0-9_]{0,99}$/.test(job.error_code) ? job.error_code : null,
  };
}

/** Job review is the approval authority; the Asset type has no independent approval flag. */
export function inspectApprovedAsset(job: ProductionJob, asset: StudioAsset, selection: ExecutionSelection): ExecutionAssetPin {
  assertExecutionJob(job, selection);
  const pin = job.output_candidate;
  if (job.status !== 'APPROVED' || !pin || !version(job.approved_asset_version)
    || !id(pin.id) || !version(pin.version) || !digest(pin.digest) || !['image', 'video', 'audio'].includes(pin.kind)
    || !asset || asset.novel_id !== selection.projectId || (asset.branch_id ?? null) !== selection.branchId
    || asset.id !== pin.id || asset.version !== job.approved_asset_version || asset.sha256 !== pin.digest
    || asset.kind !== pin.kind || asset.deleted_at || !id(asset.id) || !digest(asset.sha256)) fail();
  return { id: asset.id, version: asset.version, digest: asset.sha256, kind: asset.kind };
}
