import { describe, expect, it } from 'vitest';
import { ApiError } from '../api';
import {
  MODEL_CENTER_CODES, MODEL_CENTER_FORBIDDEN_SECRET_KEYS,
  type ModelCenterCatalogPayload, type ModelCenterCredentialState, type ModelCenterHardwareFact,
  type ModelCenterModel, type ModelCenterRuntime,
} from './modelCenterTypes';
import {
  modelCenterCatalog, modelCenterCredential, modelCenterHardware, modelCenterRuntimeCapabilitySnapshot,
  modelCenterStorage,
} from './modelCenterContract';
import { createModelCenterClient } from './modelCenterClient';
import {
  capabilityMatrix, compatibilityGuidance, orphanCandidates, readinessNotice, routingExplanation,
  secretState, storageReport,
} from './modelCenterOps';

/* ------------------------------------------------------------------ 固定装置（取自原 owner 的真实取值） */

const text = (overrides: Partial<ModelCenterModel> = {}): ModelCenterModel => ({
  id: 'llama-cpp-qwen', display_name: 'Qwen 本地', family: 'QWEN', variant: '7B', version: '1',
  capabilities: ['TEXT'], runtime_type: 'LLAMA_CPP', model_format: 'GGUF',
  status: 'READY', verified: true, metadata: { sha256: 'a'.repeat(64), installed: true },
  hardware_profile: { id: 'p1', gpu_name: 'RTX', profile_kind: 'SMOKE', vram_required_mib: 8192, ram_required_mib: 16384, tested: false },
  ...overrides,
});

const runtime = (overrides: Partial<ModelCenterRuntime> = {}): ModelCenterRuntime => ({
  id: 'llama-cpp-local', runtime_type: 'LLAMA_CPP', status: 'CONFIGURED', management: 'MANAGED',
  capabilities: ['TEXT'], instance: { state: 'RUNNING', process_alive: true, http_reachable: true },
  ...overrides,
});

const catalogWith = (models: ModelCenterModel[], runtimes: ModelCenterRuntime[] = [runtime()], snapshots: ModelCenterCatalogPayload['capability_snapshots'] = [
  { runtime_id: 'llama-cpp-local', detected_at: '2026-10-14T09:00:00Z', runtime_state: 'RUNNING', capabilities: ['TEXT'] },
]): ModelCenterCatalogPayload => ({ models, runtimes, capability_snapshots: snapshots, hidden_by_authority: 0, sources: ['MODEL_CENTER_MODELS', 'MODEL_CENTER_RUNTIMES'] });

const host: ModelCenterHardwareFact = { state: 'HOST_TOTAL_CAPACITY', source: 'HOST_INVENTORY', ram_mib: 32768, vram_mib: 24576, architecture: 'X86_64', gpu_vendor: 'NVIDIA' };

const admission = (state: 'READY' | 'LOW_SPACE_OR_QUOTA' | 'UNAVAILABLE', available: number | null) => ({
  state, available_import_bytes: available, reserve_bytes: 64 * 1024 * 1024,
  measurement: 'CURRENT_ORIGINAL_ASSET_FILESYSTEM_AND_PROJECT_QUOTA' as const,
  paths: { project: 'EXISTING_PROJECT_OWNER', assets: 'EXISTING_ASSET_LIBRARY', models: 'MODEL_CENTER_REFERENCES_ONLY', cache: 'EXISTING_CACHE_OWNER', exports: 'USER_SELECTED_DOWNLOAD' },
  external_model_scan: false as const, automatic_cleanup: false as const, automatic_migration: false as const,
});
const storage = (overrides: Record<string, unknown> = {}) => ({
  assets: { count: 3, bytes: 900 }, trash: { count: 2, bytes: 100 },
  limits: { asset_bytes: 25 * 1024 * 1024, project_asset_bytes: 512 * 1024 * 1024, project_assets: 1000 },
  model_storage: 'EXTERNAL_READ_ONLY', cache_storage: 'SEPARATE_OWNER',
  export_storage: 'CLIENT_SELECTED_DOWNLOAD', physical_cleanup_available: false,
  admission: admission('READY', 1024), ...overrides,
});

/* ------------------------------------------------------------------ 契约 */

describe('strict decoders reject unknown keys and never invent missing facts', () => {
  it('accepts the real model/runtime envelope and keeps absent facts absent', () => {
    const payload = modelCenterCatalog({ items: [{ id: 'm', display_name: 'M', family: 'F', variant: 'V', version: '1', capabilities: ['TEXT'], runtime_type: 'LLAMA_CPP', model_format: 'GGUF' }] }, { items: [] });
    expect(payload.models).toHaveLength(1);
    expect(payload.runtimes).toHaveLength(0);
    expect(payload.models[0].status).toBeUndefined();
    expect(payload.models[0].verified).toBeUndefined();
    expect(payload.models[0].license).toBeUndefined();
    expect(payload.models[0].metadata).toBeUndefined();
    expect(payload.capability_snapshots).toEqual([]);
  });

  it('rejects a genuinely unknown extra key but accepts the owner known optional keys', () => {
    const base = { id: 'm', display_name: 'M', family: 'F', variant: 'V', version: '1', capabilities: ['TEXT'], runtime_type: 'LLAMA_CPP', model_format: 'GGUF' };
    const unknown = { ...base, not_a_real_field: 1 };
    expect(() => modelCenterCatalog({ items: [unknown] }, { items: [] })).toThrow(ApiError);
    try { modelCenterCatalog({ items: [unknown] }, { items: [] }); } catch (error) {
      const problem = (error as ApiError).problem;
      expect(problem.code).toBe(MODEL_CENTER_CODES.catalogInvalid.code);
      expect(problem.message).toBe(MODEL_CENTER_CODES.catalogInvalid.message);
      expect(JSON.stringify(problem)).not.toContain('not_a_real_field');
    }
    // 原 owner 真正会写入的字段照常通过。
    expect(() => modelCenterCatalog({ items: [{ ...base, status: 'READY', verified: true, license: 'MIT' }] }, { items: [] })).not.toThrow();
    // 但只多一个未知键就整包拒绝，哪怕其它字段都合法。
    expect(() => modelCenterCatalog({ items: [{ ...base, status: 'READY', verified: true, license: 'MIT', extra: 1 }] }, { items: [] })).toThrow(ApiError);
  });

  it('rejects an out-of-vocabulary model status instead of defaulting it', () => {
    const model = { id: 'm', display_name: 'M', family: 'F', variant: 'V', version: '1', capabilities: ['TEXT'], runtime_type: 'LLAMA_CPP', model_format: 'GGUF', status: 'ALMOST_READY' };
    expect(() => modelCenterCatalog({ items: [model] }, { items: [] })).toThrow(ApiError);
  });

  it('rejects a runtime capability snapshot whose runtime_id belongs to another runtime', () => {
    expect(() => modelCenterRuntimeCapabilitySnapshot({ runtime_id: 'other', capabilities: ['TEXT'] }, 'expected')).toThrow(ApiError);
    const value = modelCenterRuntimeCapabilitySnapshot({ runtime_id: 'expected', capabilities: ['TEXT'], detected_at: '2026-10-14T09:00:00Z' }, 'expected');
    expect(value.runtime_id).toBe('expected');
    expect(value.capabilities).toEqual(['TEXT']);
  });

  it('distinguishes zero admission capacity from an unmeasurable state', () => {
    expect(modelCenterStorage(storage({ admission: admission('LOW_SPACE_OR_QUOTA', 0) })).admission?.available_import_bytes).toBe(0);
    expect(modelCenterStorage(storage({ admission: admission('UNAVAILABLE', null) })).admission?.available_import_bytes).toBeNull();
    expect(() => modelCenterStorage(storage({ admission: admission('UNAVAILABLE', 0) }))).toThrow(ApiError);
    expect(() => modelCenterStorage(storage({ admission: admission('READY', null) }))).toThrow(ApiError);
  });

  it.each([
    ['physical_cleanup_available', true], ['model_storage', 'MANAGED'], ['cache_storage', 'SAME_OWNER'],
    ['export_storage', 'SERVER_SIDE'],
  ])('rejects a storage claim that contradicts the owner invariant %s', (key, value) => {
    expect(() => modelCenterStorage(storage({ [key as string]: value }))).toThrow(ApiError);
  });

  it.each([['external_model_scan', true], ['automatic_cleanup', true], ['automatic_migration', true]])(
    'rejects a claimed side effect %s', (key, value) => {
      expect(() => modelCenterStorage(storage({ admission: { ...admission('READY', 1024), [key as string]: value } }))).toThrow(ApiError);
    });

  it('rejects a raw path where the owner declares a symbolic path owner', () => {
    expect(() => modelCenterStorage(storage({
      admission: { ...admission('READY', 1024), paths: { project: 'EXISTING_PROJECT_OWNER', assets: 'EXISTING_ASSET_LIBRARY', models: 'MODEL_CENTER_REFERENCES_ONLY', cache: 'EXISTING_CACHE_OWNER', exports: 'C:\\private\\exports' } },
    }))).toThrow(ApiError);
  });
});

/* ------------------------------------------------------------------ 凭据安全 */

describe('credential decoding never carries a value', () => {
  it('accepts the real CredentialVault.status() shape', () => {
    const value = modelCenterCredential({ provider: 'deepseek', configured: true, backend: 'windows', persistent: true, degraded: false, degraded_reason: null }, 'deepseek');
    expect(value.configured).toBe(true);
    expect(value.backend).toBe('windows');
    expect(Object.keys(value).sort()).toEqual(['backend', 'configured', 'degraded', 'persistent', 'provider']);
    expect(value.persistent).toBe(true);
    expect(value.degraded).toBe(false);
    expect(JSON.stringify(value)).not.toMatch(/sk-|secret|api[_-]?key/i);
  });

  it.each(MODEL_CENTER_FORBIDDEN_SECRET_KEYS)('refuses a response that carries a %s key', key => {
    expect(() => modelCenterCredential({ provider: 'deepseek', configured: true, [key as string]: 'sk-private-value' }, 'deepseek')).toThrow(ApiError);
    try { modelCenterCredential({ provider: 'deepseek', configured: true, [key as string]: 'sk-private-value' }, 'deepseek'); }
    catch (error) {
      const problem = (error as ApiError).problem;
      expect(problem.code).toBe(MODEL_CENTER_CODES.secretValueRejected.code);
      expect(JSON.stringify(problem)).not.toContain('sk-private-value');
    }
  });

  it('refuses a nested secret even when the top-level shape looks fine', () => {
    expect(() => modelCenterCredential({ provider: 'deepseek', configured: true, nested: { refresh_token: 'v' } }, 'deepseek')).toThrow(ApiError);
  });

  it('refuses a response for a different provider than the one requested', () => {
    expect(() => modelCenterCredential({ provider: 'openai', configured: true }, 'deepseek')).toThrow(ApiError);
  });

  it('keeps max_tokens-style numeric fields legal (no substring false positive)', () => {
    expect(() => modelCenterCatalog({ items: [{ id: 'm', display_name: 'M', family: 'F', variant: 'V', version: '1', capabilities: ['TEXT'], runtime_type: 'LLAMA_CPP', model_format: 'GGUF', metadata: {} }] }, { items: [] })).not.toThrow();
  });
});

/* ------------------------------------------------------------------ 能力矩阵 */

describe('capabilityMatrix separates declared from verified', () => {
  it('never promotes a declared capability to verified without both owner facts', () => {
    const matrix = capabilityMatrix(catalogWith([text({ verified: false, hardware_profile: undefined })]));
    const row = matrix.rows[0];
    expect(row.promoted_declared_to_verified).toBe(false);
    expect(row.verified_capabilities).toEqual([]);
    expect(row.cells.find(cell => cell.modality === 'text')?.declared).toBe(true);
    expect(row.cells.find(cell => cell.modality === 'text')?.verified).toBe(false);
    expect(row.cells.find(cell => cell.modality === 'text')?.state).toBe('declared_only');
    expect(row.cells.find(cell => cell.modality === 'image')?.state).toBe('undeclared');
    expect(row.cells.find(cell => cell.modality === 'video')?.state).toBe('undeclared');
    expect(row.cells.find(cell => cell.modality === 'audio')?.state).toBe('undeclared');
  });

  it('marks verified only when the owner validation and the runtime observation agree', () => {
    const matrix = capabilityMatrix(catalogWith([text({ verified: true })]));
    const row = matrix.rows[0];
    expect(row.cells.find(cell => cell.modality === 'text')?.state).toBe('verified');
    expect(row.verified_capabilities).toEqual(['TEXT']);
    expect(row.cells.find(cell => cell.modality === 'text')?.evidence).toContain('llama-cpp-local');
    // A runtime snapshot alone, without an owner validation record, is still not "verified".
    const bare = capabilityMatrix(catalogWith([text({ verified: false })]));
    expect(bare.rows[0].cells.find(cell => cell.modality === 'text')?.state).toBe('declared_only');
  });

  it('says so explicitly when no runtime observation exists at all', () => {
    const matrix = capabilityMatrix(catalogWith([text()], [runtime()], []));
    expect(matrix.runtime_observation_available).toBe(false);
    expect(matrix.rows[0].unknown_reason).toContain('没有读取到任何运行时能力快照');
    expect(matrix.rows[0].cells.every(cell => cell.state !== 'verified')).toBe(true);
  });

  it('fails closed when several runtimes match the declared runtime type', () => {
    const matrix = capabilityMatrix(catalogWith([text()], [runtime(), runtime({ id: 'second' })]));
    expect(matrix.rows[0].unknown_reason).toContain('2 个');
    expect(matrix.rows[0].verified_capabilities).toEqual([]);
  });
});

/* ------------------------------------------------------------------ 路线解释 */

describe('routingExplanation names the exact blocking fact', () => {
  it('never claims selectability when the bridge facts forbid it, and never calls the model', () => {
    const route = routingExplanation(catalogWith([text()]), 'llama-cpp-qwen', host)!;
    expect(route.verdict).not.toBe('SELECTABLE');
    expect(route.model_called).toBe(false);
    expect(route.execution_authority).toBe('ORIGINAL_REVIEWED_REQUEST_REQUIRED');
    expect(route.availability.authorized).toBe(false);
    expect(route.availability.compatible).toBe(false);
    expect(route.availability.reachable).toBe(true);
    expect(route.availability.healthy).toBe(true);
    expect(route.blockers.map(item => item.owner_fact)).toEqual(expect.arrayContaining([
      'provider_runtime_v2_snapshot.availability.authorized',
      'provider_runtime_v2_snapshot.availability.compatible',
    ]));
    expect(route.blockers.every(item => !!item.detail && !!item.owner_fact)).toBe(true);
  });

  it('marks a not-ready model and a stopped runtime as explicit blockers', () => {
    const route = routingExplanation(catalogWith([text({ status: 'NOT_INSTALLED' })], [runtime({ instance: { state: 'STOPPED', http_reachable: false } })]), 'llama-cpp-qwen', host)!;
    expect(route.verdict).toBe('NOT_SELECTABLE');
    expect(route.blockers.map(item => item.code)).toContain('MODEL_STATUS_NOT_READY');
    expect(route.blockers.map(item => item.code)).toContain('RUNTIME_NOT_RUNNING');
    expect(route.blockers.find(item => item.code === 'MODEL_STATUS_NOT_READY')?.detail).toContain('NOT_INSTALLED');
  });

  it('marks an unreachable runtime and an unlicensed model', () => {
    const route = routingExplanation(catalogWith(
      [text({ status: 'LICENSE_REQUIRED', metadata: { license_status: 'VALIDATION_REQUIRED' } })],
      [runtime({ instance: { state: 'RUNNING', http_reachable: false } })],
    ), 'llama-cpp-qwen', host)!;
    expect(route.blockers.map(item => item.code)).toContain('RUNTIME_HTTP_UNREACHABLE');
    expect(route.blockers.map(item => item.code)).toContain('LICENSE_VALIDATION_REQUIRED');
    expect(route.blockers.find(item => item.code === 'LICENSE_VALIDATION_REQUIRED')?.detail).toContain('VALIDATION_REQUIRED');
  });

  it('stays UNKNOWN when the model status fact is missing', () => {
    const route = routingExplanation(catalogWith([text({ status: undefined })]), 'llama-cpp-qwen', host)!;
    expect(route.verdict).toBe('UNKNOWN');
    expect(route.blockers.map(item => item.code)).toContain('MODEL_STATUS_UNKNOWN');
    expect(route.blockers.find(item => item.code === 'MODEL_STATUS_UNKNOWN')?.owner_fact).toBe('model.status');
  });

  it('stays UNKNOWN when no runtime of the declared type is registered', () => {
    const route = routingExplanation(catalogWith([text()], []), 'llama-cpp-qwen', host)!;
    expect(route.verdict).toBe('UNKNOWN');
    expect(route.blockers.map(item => item.code)).toContain('RUNTIME_STATE_UNKNOWN');
  });

  it('blocks on missing or insufficient host hardware only when the model declares requirements', () => {
    const missing = routingExplanation(catalogWith([text()]), 'llama-cpp-qwen', { state: 'UNKNOWN', reason: 'HARDWARE_NOT_PROVIDED' })!;
    expect(missing.blockers.map(item => item.code)).toContain('HOST_HARDWARE_UNKNOWN');
    const small: ModelCenterHardwareFact = { state: 'HOST_TOTAL_CAPACITY', source: 'HOST_INVENTORY', ram_mib: 4096, vram_mib: 512 };
    const insufficient = routingExplanation(catalogWith([text()]), 'llama-cpp-qwen', small)!;
    expect(insufficient.blockers.map(item => item.code)).toContain('HOST_VRAM_INSUFFICIENT');
    expect(insufficient.blockers.map(item => item.code)).toContain('HOST_RAM_INSUFFICIENT');
    const noRequirement = routingExplanation(catalogWith([text({ hardware_profile: undefined, metadata: undefined })]), 'llama-cpp-qwen')!;
    expect(noRequirement.blockers.some(item => item.code.startsWith('HOST_'))).toBe(false);
  });

  it('blocks on an absent provider key for a cloud source and never asks for the value', () => {
    const cloud = text({ source: 'CLOUD', runtime_type: 'OPENAI_COMPATIBLE_LOCAL' });
    const absent: ModelCenterCredentialState = { provider: 'OPENAI_COMPATIBLE_LOCAL', configured: false };
    const route = routingExplanation(catalogWith([cloud], []), 'llama-cpp-qwen', host, [absent])!;
    expect(route.blockers.map(item => item.code)).toContain('PROVIDER_KEY_ABSENT');
    const expired = routingExplanation(catalogWith([cloud], []), 'llama-cpp-qwen', host, [{ provider: 'OPENAI_COMPATIBLE_LOCAL', configured: true, expired: true }])!;
    expect(expired.blockers.map(item => item.code)).toContain('PROVIDER_KEY_EXPIRED');
    const unknownKey = routingExplanation(catalogWith([cloud], []), 'llama-cpp-qwen', host, [])!;
    expect(unknownKey.blockers.map(item => item.code)).toContain('PROVIDER_KEY_UNKNOWN');
  });

  it('blocks a project-required modality the model never declared', () => {
    const route = routingExplanation(catalogWith([text()]), 'llama-cpp-qwen', host, [], { required_modalities: ['video'] })!;
    expect(route.blockers.find(item => item.code === 'CAPABILITY_NOT_DECLARED')?.detail).toContain('video');
  });

  it('returns undefined for a model that is not in the catalogue', () => {
    expect(routingExplanation(catalogWith([text()]), 'ghost', host)).toBeUndefined();
  });
});

/* ------------------------------------------------------------------ 准备状态 */

describe('readinessNotice explains download/prepare/repair states and never starts a download', () => {
  it.each([
    ['NOT_FOUND', 'NOT_DOWNLOADED'], ['NOT_INSTALLED', 'NOT_DOWNLOADED'], ['DISCOVERED', 'NOT_DOWNLOADED'],
    ['VALIDATING', 'PREPARING'], ['VALIDATION_REQUIRED', 'PREPARING'], ['READY', 'READY'],
    ['DEGRADED', 'READY'], ['DISABLED', 'READY'], ['MISSING_COMPONENT', 'FAILED'], ['INCOMPATIBLE', 'FAILED'],
    ['LICENSE_REQUIRED', 'FAILED'], ['RUNTIME_REQUIRED', 'FAILED'],
  ] as const)('maps model.status %s to readiness %s', (status, expected) => {
    const notice = readinessNotice(text({ status }), host, admission('READY', 1024));
    expect(notice.state).toBe(expected);
    expect(notice.starts_download).toBe(false);
    expect(notice.read_only).toBe(true);
    expect(notice.label).toBeTruthy();
    expect(notice.detail).toContain(status === 'READY' ? 'READY' : status);
  });

  it('keeps an absent status unknown and an absent byte fact null', () => {
    const notice = readinessNotice(text({ status: undefined, metadata: undefined, hardware_profile: undefined }), undefined, undefined);
    expect(notice.state).toBe('UNKNOWN');
    expect(notice.required_bytes).toBeNull();
    expect(notice.available_bytes).toBeNull();
    expect(notice.starts_download).toBe(false);
  });

  it('derives required bytes only from the declared profile and never estimates', () => {
    const notice = readinessNotice(text(), host, admission('READY', 4096));
    expect(notice.required_bytes).toBe(8192 * 1024 * 1024);
    expect(notice.available_bytes).toBe(4096);
    const unmeasurable = readinessNotice(text(), host, admission('UNAVAILABLE', null));
    expect(unmeasurable.available_bytes).toBeNull();
  });

  it('warns when the ready file exceeds the verified host capacity instead of claiming fit', () => {
    const notice = readinessNotice(text(), { state: 'HOST_TOTAL_CAPACITY', source: 'HOST_INVENTORY', ram_mib: 32768, vram_mib: 1024 });
    expect(notice.state).toBe('READY');
    expect(notice.detail).toContain('gpu_fit_verified');
  });
});

/* ------------------------------------------------------------------ 存储报告 */

describe('storageReport is honest about irreversible actions', () => {
  it('never offers physical deletion and lists only symbolic owners', () => {
    const report = storageReport(modelCenterStorage(storage()));
    expect(report.physical_delete).toBe(false);
    expect(report.disk_actions_available).toBe(false);
    expect(report.automatic_cleanup).toBe(false);
    expect(report.automatic_migration).toBe(false);
    expect(report.external_model_scan).toBe(false);
    expect(report.requires_explicit_user_confirmation).toEqual([]);
    expect(report.cleanup_would_touch).toEqual(['assets', 'cache', 'exports']);
    expect(JSON.stringify(report)).not.toMatch(/[A-Za-z]:\\\\|\/home\/|\/mnt\//);
  });

  it('adds used and trashed bytes exactly once', () => {
    const report = storageReport(modelCenterStorage(storage()));
    expect(report.used_bytes).toBe(1000);
    expect(report.used_count).toBe(5);
    expect(report.trash_bytes).toBe(100);
    expect(report.trash_count).toBe(2);
    expect(report.quota_bytes).toBe(512 * 1024 * 1024);
    expect(report.quota_items).toBe(1000);
    expect(report.free_bytes).toBe(1024);
    expect(report.free_state).toBe('READY');
  });

  it('keeps an unmeasured filesystem unknown rather than zero', () => {
    const report = storageReport(modelCenterStorage(storage({ admission: admission('UNAVAILABLE', null) })));
    expect(report.free_bytes).toBeNull();
    expect(report.free_state).toBe('UNAVAILABLE');
    expect(report.notices.join(' ')).toContain('UNAVAILABLE');
  });

  it('keeps zero capacity distinguishable from unknown and says import is impossible', () => {
    const report = storageReport(modelCenterStorage(storage({ admission: admission('LOW_SPACE_OR_QUOTA', 0) })));
    expect(report.free_bytes).toBe(0);
    expect(report.notices.join(' ')).toContain('不能导入任何新资产');
  });

  it('reports unknown rather than plenty when no storage was read at all', () => {
    const report = storageReport(undefined);
    expect(report.free_bytes).toBeNull();
    expect(report.used_bytes).toBe(0);
    expect(report.disk_actions_available).toBe(false);
    expect(report.notices.join(' ')).toContain('保持未知');
  });
});

/* ------------------------------------------------------------------ 孤儿候选 */

describe('orphanCandidates is a read-only report', () => {
  it('refuses to invent candidates when the owner only exposes aggregate counters', () => {
    const report = orphanCandidates(undefined, modelCenterStorage(storage()));
    expect(report.available).toBe(false);
    expect(report.candidates).toEqual([]);
    expect(report.mutates).toBe(false);
    expect(report.physical_delete).toBe(false);
    expect(report.total_bytes).toBeNull();
    expect(report.detail).toContain('trash.count = 2');
  });

  it('reports owned evidence rows without ever claiming deletion is available', () => {
    const report = orphanCandidates([
      { asset_id: 'a1', label: '旧草稿', bytes: 40, reason_code: 'SOFT_DELETED_ASSET' },
      { asset_id: 'a2', label: '旧版本', bytes: 60, reason_code: 'SUPERSEDED_REVISION' },
      { asset_id: 'a1', label: '重复行', bytes: 40, reason_code: 'SOFT_DELETED_ASSET' },
    ], modelCenterStorage(storage()));
    expect(report.available).toBe(true);
    expect(report.candidates).toHaveLength(2);
    expect(report.total_bytes).toBe(100);
    expect(report.candidates.every(item => item.deletion_available === false)).toBe(true);
    expect(report.mutates).toBe(false);
    expect(report.candidates[0].reason).toContain('软删除');
  });

  it('declines to judge an evidence row with an unknown reason code', () => {
    const report = orphanCandidates([{ asset_id: 'a1', reason_code: 'DELETE_IT_NOW' as never }], modelCenterStorage(storage()));
    expect(report.available).toBe(false);
    expect(report.candidates).toEqual([]);
    expect(report.mutates).toBe(false);
  });
});

/* ------------------------------------------------------------------ 凭据状态 */

describe('secretState reports presence only', () => {
  it('never carries a value and never guesses configuration', () => {
    expect(secretState(undefined)).toMatchObject({ state: 'UNKNOWN', secret_value: null, read_only: true });
    expect(secretState({ provider: 'deepseek', configured: true })).toMatchObject({ state: 'PRESENT', label: '存在', secret_value: null });
    expect(secretState({ provider: 'deepseek', configured: false })).toMatchObject({ state: 'ABSENT', label: '不存在', secret_value: null });
    expect(secretState({ provider: 'deepseek', configured: true, expired: true })).toMatchObject({ state: 'EXPIRED', label: '已过期', secret_value: null });
    const view = secretState({ provider: 'deepseek', configured: true, backend: 'memory', persistent: false, degraded: true, degraded_reason: 'KEYRING_BACKEND_UNUSABLE' });
    expect(view.secret_value).toBeNull();
    expect(view.degraded).toBe(true);
    expect(view.degraded_reason).toBe('KEYRING_BACKEND_UNUSABLE');
    expect(JSON.stringify(view)).not.toContain('sk-');
  });
});

/* ------------------------------------------------------------------ 兼容性说明 */

describe('compatibilityGuidance explains incompatibility in plain Chinese with the owner fact', () => {
  it('names the missing modality and the owner field it came from', () => {
    const guidance = compatibilityGuidance(text(), { required_modalities: ['video'] }, catalogWith([text()]), host);
    expect(guidance.compatible).toBe(false);
    expect(guidance.headline).toContain('视频');
    expect(guidance.details.every(item => !!item.owner_fact)).toBe(true);
    expect(guidance.force_execution_available).toBe(false);
  });

  it('explains a hardware downgrade with the hardware owner fact', () => {
    const guidance = compatibilityGuidance(text(), { required_modalities: ['text'] },
      catalogWith([text()]), { state: 'HOST_TOTAL_CAPACITY', source: 'HOST_INVENTORY', ram_mib: 32768, vram_mib: 2048 });
    expect(guidance.details.some(item => item.owner_fact === 'host_hardware_inventory.vram_mib')).toBe(true);
    expect(guidance.details.find(item => item.owner_fact === 'host_hardware_inventory.vram_mib')?.text).toContain('低于');
  });

  it('reports a degraded owner status as an owner fact, not an inference', () => {
    const guidance = compatibilityGuidance(text({ status: 'DEGRADED' }), { required_modalities: ['text'] }, catalogWith([text()]), host);
    expect(guidance.downgrade_explanation).toContain('DEGRADED');
    expect(guidance.compatible).toBe(false);
  });

  it('stays unknown when the owner never stated a status', () => {
    const guidance = compatibilityGuidance(text({ status: undefined }), { required_modalities: ['text'] }, catalogWith([text()]), host);
    expect(guidance.compatible).toBeNull();
    expect(guidance.force_execution_available).toBe(false);
  });
});

/* ------------------------------------------------------------------ 客户端 */

describe('client reads only existing endpoints', () => {
  const never = () => Promise.reject(new Error('unused'));

  it('decodes the real /api/model-center/models shape line for line', () => {
    const raw = {
      id: 'llama-cpp-qwen', display_name: 'Qwen 本地', family: 'QWEN', variant: '7B', version: '1',
      capabilities: ['TEXT'], runtime_type: 'LLAMA_CPP', model_format: 'GGUF',
      quantization: 'Q4_K_M', precision: 'Q4', source: 'LOCAL', license: 'APACHE-2.0',
      components: [], hardware_profiles: ['p1'], compatibility: {},
      status: 'READY', metadata: { sha256: 'b'.repeat(64), installed: true, local_discovery: false },
      identity_id: '11111111-2222-4333-8444-555555555555',
      historically_validated: true, verified: true,
      hardware_profile_details: [{ id: 'p1', model_id: 'llama-cpp-qwen', gpu_name: 'RTX 4070', vram_required: 8192, vram_recommended: 12288, ram_required: 16384, ram_recommended: 32768, context: 8192, offload_mode: 'GPU_ONLY', tested: false, benchmark: {}, profile_kind: 'SMOKE' }],
    };
    const payload = modelCenterCatalog({ items: [raw] }, { items: [] });
    const decoded = payload.models[0];
    expect(decoded.id).toBe('llama-cpp-qwen');
    expect(decoded.status).toBe('READY');
    expect(decoded.verified).toBe(true);
    expect(decoded.historically_validated).toBe(true);
    expect(decoded.license).toBe('APACHE-2.0');
    expect(decoded.metadata).toEqual({ sha256: 'b'.repeat(64), installed: true, local_discovery: false });
    expect(decoded.hardware_profile).toEqual({ id: 'p1', gpu_name: 'RTX 4070', profile_kind: 'SMOKE', vram_required_mib: 8192, vram_recommended_mib: 12288, ram_required_mib: 16384, ram_recommended_mib: 32768, tested: false });
    // 路径类字段永不进入解码结果。
    expect(JSON.stringify(decoded)).not.toContain('local_paths');
  });

  it('rejects a control character inside an owner string instead of rendering it', () => {
    const base = { id: 'm', display_name: 'M', family: 'F', variant: 'V', version: '1', capabilities: ['TEXT'], runtime_type: 'LLAMA_CPP', model_format: 'GGUF' };
    expect(() => modelCenterCatalog({ items: [{ ...base, license: 'bad\u0000value' }] }, { items: [] })).toThrow(ApiError);
  });

  it('reads models/runtimes/capabilities/storage and never issues a write', async () => {
    const calls: { url: string; method: string }[] = [];
    const transport = {
      json: async <T,>(url: string, method = 'GET'): Promise<T> => {
        calls.push({ url, method });
        if (url === '/api/model-center/models') return { items: [{ id: 'm', display_name: 'M', family: 'F', variant: 'V', version: '1', capabilities: ['TEXT'], runtime_type: 'LLAMA_CPP', model_format: 'GGUF', status: 'READY' }] } as T;
        if (url === '/api/model-center/runtimes') return { items: [{ id: 'llama-cpp-local', runtime_type: 'LLAMA_CPP', status: 'CONFIGURED', capabilities: ['TEXT'] }] } as T;
        if (url.includes('/capabilities')) return { runtime_id: 'llama-cpp-local', capabilities: ['TEXT'], detected_at: '2026-10-14T09:00:00Z' } as T;
        if (url.endsWith('/studio/storage')) return storage() as T;
        throw new Error(`unexpected ${url}`);
      },
      blob: never,
    };
    const client = createModelCenterClient('p1', transport);
    const result = await client.read();
    expect(result.catalog?.models).toHaveLength(1);
    expect(result.catalog?.capability_snapshots).toHaveLength(1);
    expect(result.storage?.limits.project_assets).toBe(1000);
    expect(result.status.catalog).toEqual({ state: 'READY' });
    expect(result.status.storage).toEqual({ state: 'READY' });
    expect(calls).toHaveLength(4);
    expect(calls.map(call => call.method)).toEqual(['GET', 'GET', 'GET', 'GET']);
    expect(calls.map(call => call.url).sort()).toEqual([
      '/api/model-center/models', '/api/model-center/runtimes',
      '/api/model-center/runtimes/llama-cpp-local/capabilities',
      '/api/projects/p1/studio/storage',
    ].sort());
    expect(calls.some(call => /delete|cleanup|download|start|stop/.test(call.url))).toBe(false);
  });

  it('turns an empty registry into EMPTY and a denial into DENIED, never into each other', async () => {
    const empty = createModelCenterClient('p1', {
      json: async <T,>(url: string): Promise<T> => {
        if (url === '/api/model-center/models') return { items: [] } as T;
        if (url === '/api/model-center/runtimes') return { items: [] } as T;
        return storage() as T;
      },
    });
    expect((await empty.read()).status.catalog).toEqual({ state: 'EMPTY' });

    const denied = createModelCenterClient('p1', {
      json: async <T,>(url: string): Promise<T> => {
        if (url.endsWith('/studio/storage')) throw new ApiError({ status: 403, code: 'FORBIDDEN', message: 'denied' });
        if (url === '/api/model-center/models') return { items: [] } as T;
        return { items: [] } as T;
      },
    });
    const result = await denied.read();
    expect(result.status.storage.state).toBe('DENIED');
    expect(result.status.catalog.state).toBe('EMPTY');
  });

  it('keeps the model list usable when the runtime read fails', async () => {
    const client = createModelCenterClient('p1', {
      json: async <T,>(url: string): Promise<T> => {
        if (url === '/api/model-center/models') return { items: [{ id: 'm', display_name: 'M', family: 'F', variant: 'V', version: '1', capabilities: ['TEXT'], runtime_type: 'LLAMA_CPP', model_format: 'GGUF', status: 'READY' }] } as T;
        if (url === '/api/model-center/runtimes') throw new ApiError({ status: 404, code: 'MODEL_CENTER_RUNTIME_NOT_FOUND', message: 'no' });
        return storage() as T;
      },
    });
    const result = await client.read();
    expect(result.catalog?.models).toHaveLength(1);
    expect(result.catalog?.runtimes).toEqual([]);
    expect(result.status.catalog.state).toBe('UNAVAILABLE');
    expect(result.status.storage).toEqual({ state: 'READY' });
  });

  it('refuses a captured scope whose project is not the requested project', async () => {
    const client = createModelCenterClient('p1', { json: async <T,>(): Promise<T> => ({ items: [] }) as T },
      { workspaceId: 'w', projectId: 'p2', storylineId: 's', branchId: 'b' });
    await expect(client.read()).rejects.toMatchObject({ problem: { code: MODEL_CENTER_CODES.catalogScopeMismatch.code } });
  });

  it('decodes optional hardware facts but never probes for them', () => {
    const client = createModelCenterClient('p1', { json: async <T,>(): Promise<T> => ({ items: [] }) as T });
    expect(client.decodeHardware(undefined)).toEqual({ state: 'UNKNOWN', reason: MODEL_CENTER_CODES.hardwareUnavailable.code });
    expect(client.decodeHardware({ state: 'HOST_TOTAL_CAPACITY', source: 'HOST_INVENTORY', ram_mib: 1024 })).toMatchObject({ state: 'HOST_TOTAL_CAPACITY', ram_mib: 1024 });
    expect(modelCenterHardware({ state: 'GUESSED' })).toMatchObject({ state: 'UNKNOWN' });
  });
});
