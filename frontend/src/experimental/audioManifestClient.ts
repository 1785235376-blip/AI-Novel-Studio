import type { ExperimentalClient } from './api';
import { segment } from './api';

export type AudioResult = { id: string; version: number; operation_id: string };
type Source = { id: string; kind: string; version: number; digest: string; asset_kind?: string };
export type AudioCapture = { contract: 'studio-audio-manifest-capture/1';
  job: AudioResult & { request_id: string; request_digest: string; receipt_digest: string };
  result: { review_state: 'ORIGINAL_OWNER_REVIEWED'; output_digest: string };
  asset: { id: string; version: number; digest: string; kind: 'audio' }; sources: Source[];
  environment: { state: 'UNKNOWN'; model_hash: null; runtime: null; hardware: null };
  replay: { supported: false; reason: 'NOT_IN_THIS_SLICE' } };
export type AudioPreview = { capture: AudioCapture; capture_digest: string };
export type AudioManifest = AudioPreview & { contract: 'studio-audio-manifest/1'; id: string; version: number;
  created_at: string; request_id: string; replayable: false; manifest_digest: string };
export type AudioRecord = { job_id: string; expected_job_version: number; reviewed_capture_digest: string; request_id: string; confirmed: true };

const object = (value: unknown, keys: string[]): Record<string, unknown> => {
  if (!value || typeof value !== 'object' || Array.isArray(value) || Object.keys(value).some(key => !keys.includes(key))) throw new Error('音频清单回执格式无效。');
  return value as Record<string, unknown>;
};
const id = (value: unknown): string => { if (typeof value !== 'string' || !/^[A-Za-z0-9][A-Za-z0-9_-]{0,239}$/.test(value)) throw new Error('清单标识无效。'); return value; };
const hash = (value: unknown): string => { if (typeof value !== 'string' || !/^[a-f0-9]{64}$/.test(value)) throw new Error('清单摘要无效。'); return value; };
const version = (value: unknown): number => { if (typeof value !== 'number' || !Number.isSafeInteger(value) || value < 1) throw new Error('清单版本无效。'); return value; };
const operation = (value: unknown): string => { if (typeof value !== 'string' || !/^[A-Za-z0-9][A-Za-z0-9._-]{0,119}$/.test(value)) throw new Error('音频操作标识无效。'); return value; };
const result = (raw: unknown): AudioResult => { const value = object(raw, ['id', 'version', 'operation_id']); return { id: id(value.id), version: version(value.version), operation_id: operation(value.operation_id) }; };

export function checkedAudioPreview(raw: unknown): AudioPreview {
  const root = object(raw, ['capture', 'capture_digest']), capture = object(root.capture, ['contract', 'job', 'result', 'asset', 'sources', 'environment', 'replay']);
  const job = object(capture.job, ['id', 'version', 'operation_id', 'request_id', 'request_digest', 'receipt_digest']);
  const output = object(capture.result, ['review_state', 'output_digest']), asset = object(capture.asset, ['id', 'version', 'digest', 'kind']);
  const environment = object(capture.environment, ['state', 'model_hash', 'runtime', 'hardware']), replay = object(capture.replay, ['supported', 'reason']);
  if (capture.contract !== 'studio-audio-manifest-capture/1' || output.review_state !== 'ORIGINAL_OWNER_REVIEWED' || asset.kind !== 'audio'
    || environment.state !== 'UNKNOWN' || ['model_hash', 'runtime', 'hardware'].some(key => environment[key] !== null)
    || replay.supported !== false || replay.reason !== 'NOT_IN_THIS_SLICE' || !Array.isArray(capture.sources) || capture.sources.length > 32) throw new Error('音频清单证据不匹配。');
  const sources = capture.sources.map(rawSource => {
    const source = object(rawSource, ['id', 'kind', 'version', 'digest', 'asset_kind']);
    if (!['ASSET', 'CREATIVE_DOCUMENT', 'COMIC_PANEL'].includes(String(source.kind))
      || source.asset_kind !== undefined && !['audio', 'video', 'image', 'prompt', 'model'].includes(String(source.asset_kind))) throw new Error('来源绑定无效。');
    return { id: id(source.id), kind: String(source.kind), version: version(source.version), digest: hash(source.digest), ...(source.asset_kind === undefined ? {} : { asset_kind: String(source.asset_kind) }) };
  });
  const outputDigest = hash(output.output_digest); if (hash(asset.digest) !== outputDigest) throw new Error('产物与正式资产摘要不一致。');
  return { capture_digest: hash(root.capture_digest), capture: { contract: 'studio-audio-manifest-capture/1',
    job: { id: id(job.id), version: version(job.version), operation_id: operation(job.operation_id), request_id: id(job.request_id), request_digest: hash(job.request_digest), receipt_digest: hash(job.receipt_digest) },
    result: { review_state: 'ORIGINAL_OWNER_REVIEWED', output_digest: outputDigest },
    asset: { id: id(asset.id), version: version(asset.version), digest: outputDigest, kind: 'audio' }, sources,
    environment: { state: 'UNKNOWN', model_hash: null, runtime: null, hardware: null }, replay: { supported: false, reason: 'NOT_IN_THIS_SLICE' } } };
}
export function checkedAudioManifest(raw: unknown): AudioManifest {
  const value = object(raw, ['contract', 'id', 'version', 'created_at', 'request_id', 'capture', 'capture_digest', 'replayable', 'manifest_digest']);
  if (value.contract !== 'studio-audio-manifest/1' || value.replayable !== false || typeof value.created_at !== 'string' || value.created_at.length > 64 || !Number.isFinite(Date.parse(value.created_at))) throw new Error('音频清单记录无效。');
  return { contract: 'studio-audio-manifest/1', id: id(value.id), version: version(value.version), created_at: value.created_at,
    request_id: id(value.request_id), replayable: false, manifest_digest: hash(value.manifest_digest), ...checkedAudioPreview({ capture: value.capture, capture_digest: value.capture_digest }) };
}
export function audioManifestClient(client: ExperimentalClient) {
  const root = '/production/audio-manifests';
  return {
    results: async (signal?: AbortSignal) => {
      const value = object(await client.get<unknown>(root + '/results', signal), ['contract', 'items', 'replayable']);
      if (value.contract !== 'studio-audio-manifest-results/1' || value.replayable !== false || !Array.isArray(value.items) || value.items.length > 64) throw new Error('音频结果列表无效。');
      return value.items.map(result);
    },
    preview: async (jid: string, signal?: AbortSignal) => checkedAudioPreview(await client.get(root + '/results/' + segment(id(jid)), signal)),
    list: async (signal?: AbortSignal) => {
      const value = object(await client.get<unknown>(root, signal), ['contract', 'items']);
      if (value.contract !== 'studio-audio-manifest-list/1' || !Array.isArray(value.items) || value.items.length > 64) throw new Error('音频清单列表无效。');
      return value.items.map(checkedAudioManifest);
    },
    get: async (mid: string, signal?: AbortSignal) => checkedAudioManifest(await client.get(root + '/' + segment(id(mid)), signal)),
    record: async (request: AudioRecord) => checkedAudioManifest(await client.post(root, request)),
    export: async (mid: string, signal?: AbortSignal) => checkedAudioManifest(await client.get(root + '/' + segment(id(mid)) + '/export', signal)),
  };
}
