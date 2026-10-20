import { ApiError } from '../api';

/** Closed wire contract for the transfer owner; registry entries confer no download authority. */
export const MODEL_TRANSFER_STATES = ['TRANSFERRING', 'PAUSING', 'PAUSED', 'CANCELLING', 'VERIFYING', 'COMPLETED', 'CANCELLED', 'FAILED', 'INTERRUPTED', 'CLEANED'] as const;
export type ModelTransferState = typeof MODEL_TRANSFER_STATES[number];
export type ModelTransferSource = {
  id: string; model_id: string; display_name: string; publisher: string; license_name: string;
  license_url: string; model_card_url: string; url: string; revision: string; size_bytes: number; sha256: string;
};
export type ModelTransferTask = {
  id: string; source_id: string; model_id: string; display_name: string; state: ModelTransferState;
  version: number; bytes_received: number; total_bytes: number; error_code: string | null; can_resume: boolean;
};
export type ModelTransferCatalog = {
  contract: 'studio-model-transfers/1'; configured: boolean; platform_supported: boolean;
  blockers: string[]; sources: ModelTransferSource[]; items: ModelTransferTask[];
};
export type ModelTransferPreview = {
  contract: 'studio-model-transfer-preview/1'; preview_id: string; preview_digest: string; expires_at: number;
  source: ModelTransferSource; destination: string; required_bytes: number; available_bytes: number; reserve_bytes: number;
};
export type ModelTransferCleanupPreview = {
  contract: 'studio-model-transfer-cleanup/1'; preview_id: string; preview_digest: string; expires_at: number;
  task_id: string; version: number; bytes: number;
};
export function invalidModelTransfer(input = false): never {
  throw new ApiError({ status: input ? 400 : 200, code: input ? 'MODEL_TRANSFER_INPUT_INVALID' : 'STUDIO_RESPONSE_INVALID',
    message: input ? '传输操作输入无效，请重新读取并核对。' : '传输回执格式或身份无效，操作已停用；请重新读取。' });
}
function exact(value: unknown, fields: readonly string[]): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) invalidModelTransfer();
  const row = value as Record<string, unknown>;
  if (Object.keys(row).length !== fields.length || fields.some(key => !Object.hasOwn(row, key))) invalidModelTransfer();
  return row;
}
function text(value: unknown, max = 256): string {
  if (typeof value !== 'string' || !value.trim() || value.length > max || /[\u0000-\u001f\u007f]/.test(value)) invalidModelTransfer();
  return value;
}
export function modelTransferId(value: unknown): string {
  const id = text(value, 200);
  if (!/^[A-Za-z0-9][A-Za-z0-9._:-]{0,199}$/.test(id)) invalidModelTransfer();
  return id;
}
function bytes(value: unknown, positive = false): number {
  if (typeof value !== 'number' || !Number.isSafeInteger(value) || value < (positive ? 1 : 0)) invalidModelTransfer();
  return value;
}
function digest(value: unknown): string {
  if (typeof value !== 'string' || !/^[a-f0-9]{64}$/.test(value)) invalidModelTransfer();
  return value;
}
function expiry(value: unknown): number {
  if (typeof value !== 'number' || !Number.isFinite(value) || value <= 0 || value > 253402300799) invalidModelTransfer();
  return value;
}
function https(value: unknown): string {
  const result = text(value, 4096);
  try {
    const url = new URL(result);
    if (!result.startsWith('https://') || url.protocol !== 'https:' || !url.hostname || url.username || url.password || url.search || url.hash || (url.port && url.port !== '443')
      || /[\s\\%]|[^\x21-\x7e]/.test(result) || result.slice('https://'.length).split('/').slice(1).includes('..')) invalidModelTransfer();
  } catch { invalidModelTransfer(); }
  // Source review, DNS, redirects and network restrictions belong to the owner.
  return result;
}
export function checkedModelTransferSource(value: unknown): ModelTransferSource {
  const row = exact(value, ['id', 'model_id', 'display_name', 'publisher', 'license_name', 'license_url', 'model_card_url', 'url', 'revision', 'size_bytes', 'sha256']);
  return { id: modelTransferId(row.id), model_id: text(row.model_id), display_name: text(row.display_name), publisher: text(row.publisher),
    license_name: text(row.license_name), license_url: https(row.license_url), model_card_url: https(row.model_card_url), url: https(row.url),
    revision: text(row.revision), size_bytes: bytes(row.size_bytes, true), sha256: digest(row.sha256) };
}
export function sameModelTransferSource(a: ModelTransferSource, b: ModelTransferSource): boolean {
  return Object.keys(a).every(key => a[key as keyof ModelTransferSource] === b[key as keyof ModelTransferSource]);
}
export function checkedModelTransferTask(value: unknown, expected?: Pick<ModelTransferTask, 'id' | 'source_id' | 'model_id' | 'total_bytes'>): ModelTransferTask {
  const row = exact(value, ['id', 'source_id', 'model_id', 'display_name', 'state', 'version', 'bytes_received', 'total_bytes', 'error_code', 'can_resume']);
  if (!MODEL_TRANSFER_STATES.includes(row.state as ModelTransferState) || typeof row.can_resume !== 'boolean') invalidModelTransfer();
  const task: ModelTransferTask = { id: modelTransferId(row.id), source_id: modelTransferId(row.source_id), model_id: text(row.model_id), display_name: text(row.display_name),
    state: row.state as ModelTransferState, version: bytes(row.version, true), bytes_received: bytes(row.bytes_received), total_bytes: bytes(row.total_bytes, true),
    error_code: row.error_code === null ? null : modelTransferId(row.error_code), can_resume: row.can_resume };
  if (task.bytes_received > task.total_bytes || (task.state === 'COMPLETED' && task.bytes_received !== task.total_bytes)
    || (task.can_resume && !['PAUSED', 'FAILED', 'INTERRUPTED'].includes(task.state))) invalidModelTransfer();
  if (expected && (task.id !== expected.id || task.source_id !== expected.source_id || task.model_id !== expected.model_id || task.total_bytes !== expected.total_bytes)) invalidModelTransfer();
  return task;
}
export function checkedModelTransferCatalog(value: unknown): ModelTransferCatalog {
  const row = exact(value, ['contract', 'configured', 'platform_supported', 'blockers', 'sources', 'items']);
  if (row.contract !== 'studio-model-transfers/1' || typeof row.configured !== 'boolean' || typeof row.platform_supported !== 'boolean'
    || !Array.isArray(row.blockers) || row.blockers.length > 64 || !Array.isArray(row.sources) || row.sources.length > 256 || !Array.isArray(row.items) || row.items.length > 1000) invalidModelTransfer();
  const sources = row.sources.map(checkedModelTransferSource), items = row.items.map(value => checkedModelTransferTask(value));
  if (new Set(sources.map(source => source.id)).size !== sources.length || new Set(items.map(task => task.id)).size !== items.length) invalidModelTransfer();
  for (const task of items) {
    const source = sources.find(candidate => candidate.id === task.source_id);
    if (source && (source.model_id !== task.model_id || source.size_bytes !== task.total_bytes)) invalidModelTransfer();
  }
  return { contract: row.contract, configured: row.configured, platform_supported: row.platform_supported, blockers: row.blockers.map(value => text(value, 400)), sources, items };
}
export function checkedModelTransferPreview(value: unknown, source: ModelTransferSource): ModelTransferPreview {
  const row = exact(value, ['contract', 'preview_id', 'preview_digest', 'expires_at', 'source', 'destination', 'required_bytes', 'available_bytes', 'reserve_bytes']);
  if (row.contract !== 'studio-model-transfer-preview/1') invalidModelTransfer();
  const preview: ModelTransferPreview = { contract: row.contract, preview_id: modelTransferId(row.preview_id), preview_digest: digest(row.preview_digest), expires_at: expiry(row.expires_at),
    source: checkedModelTransferSource(row.source), destination: text(row.destination, 4096), required_bytes: bytes(row.required_bytes), available_bytes: bytes(row.available_bytes), reserve_bytes: bytes(row.reserve_bytes) };
  if (!sameModelTransferSource(source, preview.source) || preview.required_bytes < source.size_bytes) invalidModelTransfer();
  return preview;
}
export function checkedModelTransferCleanupPreview(value: unknown, task: ModelTransferTask): ModelTransferCleanupPreview {
  const row = exact(value, ['contract', 'preview_id', 'preview_digest', 'expires_at', 'task_id', 'version', 'bytes']);
  if (row.contract !== 'studio-model-transfer-cleanup/1') invalidModelTransfer();
  const preview: ModelTransferCleanupPreview = { contract: row.contract, preview_id: modelTransferId(row.preview_id), preview_digest: digest(row.preview_digest), expires_at: expiry(row.expires_at),
    task_id: modelTransferId(row.task_id), version: bytes(row.version, true), bytes: bytes(row.bytes) };
  if (preview.task_id !== task.id || preview.version !== task.version || preview.bytes > task.total_bytes) invalidModelTransfer();
  return preview;
}
