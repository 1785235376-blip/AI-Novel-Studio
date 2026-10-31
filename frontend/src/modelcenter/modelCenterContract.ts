/**
 * UX-07 严格解码器。
 *
 * 三条铁律，全部由测试证明：
 * 1. **未知键一律拒绝**：`/api/model-center/{models,runtimes}`、`studio/storage`
 *    与 `/api/credentials/{provider}` 的信封都按白名单校验，多一个键就整包拒绝。
 * 2. **缺失就保持缺失**：原 owner 没给的字段绝不补默认值（不补 `status: 'READY'`、
 *    不补 `verified: true`、不补 `available_import_bytes: 0`）。零容量与"无法测量"
 *    是两个不同的事实。
 * 3. **凭据永不携带值**：凭据响应只接受
 *    `{provider, configured, backend, persistent, degraded, degraded_reason}`
 *    （`app/credential_vault.py::status()` 的真实形状，其中 `secret` 恒为 `None`），
 *    并且**递归**扫描任何 `secret` / `token` / `api_key` 之类的键名，一旦出现即整包
 *    拒绝（把越权回传变成一次明确的读取失败，而不是一次静默泄漏）。
 */

import { ApiError } from '../api';
import {
  MODEL_CENTER_BOUNDS, MODEL_CENTER_CAPABILITIES, MODEL_CENTER_CODES, MODEL_CENTER_CREDENTIAL_KEYS,
  MODEL_CENTER_FORBIDDEN_SECRET_KEYS, MODEL_CENTER_RUNTIME_MANAGEMENTS, MODEL_CENTER_RUNTIME_STATES,
  MODEL_CENTER_RUNTIME_TYPES, MODEL_CENTER_STATUSES, MODEL_CENTER_VAULT_BACKENDS,
  STORAGE_ADMISSION_STATES, STORAGE_MEASUREMENT, STORAGE_PATH_OWNERS, STORAGE_PATH_OWNER_VALUES,
  type ModelCenterCapability, type ModelCenterCatalogPayload, type ModelCenterCredentialState,
  type ModelCenterHardwareFact, type ModelCenterModel, type ModelCenterRuntime,
  type ModelCenterRuntimeCapabilitySnapshot, type ModelCenterRuntimeType, type ModelCenterScope,
  type ModelCenterStoragePayload, type StoragePathOwner,
} from './modelCenterTypes';

type Family = 'catalog' | 'storage' | 'credential' | 'hardware';
class ShapeViolation { constructor(readonly family: Family, readonly kind: 'invalid' | 'mismatch' | 'secret') {} }

function invalid(): never { throw new ShapeViolation('catalog', 'invalid'); }
function mismatch(): never { throw new ShapeViolation('catalog', 'mismatch'); }
function secretLeak(family: Family): never { throw new ShapeViolation(family, 'secret'); }

const FAMILY_MESSAGES: Record<Family, { invalid: string; mismatch: string; secret: string }> = {
  catalog: {
    invalid: MODEL_CENTER_CODES.catalogInvalid.message,
    mismatch: MODEL_CENTER_CODES.catalogScopeMismatch.message,
    secret: MODEL_CENTER_CODES.secretValueRejected.message,
  },
  storage: {
    invalid: MODEL_CENTER_CODES.storageInvalid.message,
    mismatch: MODEL_CENTER_CODES.storageScopeMismatch.message,
    secret: MODEL_CENTER_CODES.secretValueRejected.message,
  },
  credential: {
    invalid: MODEL_CENTER_CODES.credentialInvalid.message,
    mismatch: MODEL_CENTER_CODES.credentialInvalid.message,
    secret: MODEL_CENTER_CODES.secretValueRejected.message,
  },
  hardware: {
    invalid: MODEL_CENTER_CODES.hardwareInvalid.message,
    mismatch: MODEL_CENTER_CODES.hardwareInvalid.message,
    secret: MODEL_CENTER_CODES.secretValueRejected.message,
  },
};
const FAMILY_CODES: Record<Family, { invalid: string; mismatch: string; secret: string }> = {
  catalog: {
    invalid: MODEL_CENTER_CODES.catalogInvalid.code,
    mismatch: MODEL_CENTER_CODES.catalogScopeMismatch.code,
    secret: MODEL_CENTER_CODES.secretValueRejected.code,
  },
  storage: {
    invalid: MODEL_CENTER_CODES.storageInvalid.code,
    mismatch: MODEL_CENTER_CODES.storageScopeMismatch.code,
    secret: MODEL_CENTER_CODES.secretValueRejected.code,
  },
  credential: {
    invalid: MODEL_CENTER_CODES.credentialInvalid.code,
    mismatch: MODEL_CENTER_CODES.credentialInvalid.code,
    secret: MODEL_CENTER_CODES.secretValueRejected.code,
  },
  hardware: {
    invalid: MODEL_CENTER_CODES.hardwareInvalid.code,
    mismatch: MODEL_CENTER_CODES.hardwareInvalid.code,
    secret: MODEL_CENTER_CODES.secretValueRejected.code,
  },
};

/** 内部原语先抛族内标记，由这里包成 owner 家族对应的 `ApiError`。 */
function scope<T>(family: Family, run: () => T): T {
  try {
    return run();
  } catch (reason) {
    if (!(reason instanceof ShapeViolation)) throw reason;
    const status = reason.kind === 'mismatch' ? 403 : 200;
    throw new ApiError({ status, code: FAMILY_CODES[family][reason.kind], message: FAMILY_MESSAGES[family][reason.kind] });
  }
}

/* ------------------------------------------------------------------ 原语 */

/** 只接受这些键的对象；多一个键就是拒绝读取。 */
function object(value: unknown, allowed: readonly string[], family: Family): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) invalidIn(family);
  const row = value as Record<string, unknown>;
  for (const key of Object.keys(row)) {
    // 越权的密钥键名 → 明确的泄漏拒绝；其它未知键 → 形状非法。
    if (forbiddenKey(key)) secretLeak(family);
    if (!allowed.includes(key)) invalidIn(family);
  }
  return row;
}
/**
 * 精确 + 后缀匹配，绝不做子串匹配：`max_tokens` 属于 `max_tokens`，
 * 而 `token` / `refresh_token` / `client_secret` 属于密钥键名。
 */
function forbiddenKey(key: string): boolean {
  const normalized = key.toLowerCase().replace(/[^a-z_]/g, '');
  return MODEL_CENTER_FORBIDDEN_SECRET_KEYS.some(banned => normalized === banned || normalized.endsWith(`_${banned}`));
}
/** 递归扫描已解码的载荷：任何越权密钥键名都必须已经让这次读取失败。 */
function scanForSecrets(value: unknown, depth = 0): void {
  if (depth > 8 || value === null || typeof value !== 'object') return;
  if (Array.isArray(value)) { for (const item of value) scanForSecrets(item, depth + 1); return; }
  for (const [key, item] of Object.entries(value as Record<string, unknown>)) {
    if (forbiddenKey(key)) secretLeak('credential');
    scanForSecrets(item, depth + 1);
  }
}
function text(value: unknown, maximum: number, family: Family): string {
  if (typeof value !== 'string' || !value.trim() || value.length > maximum || /[\u0000-\u001f\u007f]/.test(value)) invalidIn(family);
  return value;
}
function optionalText(value: unknown, maximum: number, family: Family): string | undefined {
  if (value === undefined || value === null) return undefined;
  return text(value, maximum, family);
}
function bounded(value: unknown, maximum: number, family: Family): string | undefined {
  if (value === undefined || value === null) return undefined;
  if (typeof value !== 'string' || value.length > maximum || /[\u0000-\u001f\u007f]/.test(value)) invalidIn(family);
  return value;
}
function boolean(value: unknown, family: Family): boolean {
  if (typeof value !== 'boolean') invalidIn(family);
  return value;
}
function optionalBoolean(value: unknown, family: Family): boolean | undefined {
  if (value === undefined || value === null) return undefined;
  return boolean(value, family);
}
function integer(value: unknown, maximum: number, family: Family): number {
  if (typeof value !== 'number' || !Number.isSafeInteger(value) || value < 0 || value > maximum) invalidIn(family);
  return value;
}
function optionalInteger(value: unknown, maximum: number, family: Family): number | undefined {
  if (value === undefined || value === null) return undefined;
  return integer(value, maximum, family);
}
function enumerated<T extends string>(value: unknown, allowed: readonly T[], family: Family): T {
  if (typeof value !== 'string' || !allowed.includes(value as T)) invalidIn(family);
  return value as T;
}
function optionalEnumerated<T extends string>(value: unknown, allowed: readonly T[], family: Family): T | undefined {
  if (value === undefined || value === null) return undefined;
  return enumerated(value, allowed, family);
}
function invalidIn(family: Family): never { throw new ShapeViolation(family, 'invalid'); }
function list(value: unknown, maximum: number, family: Family): unknown[] {
  if (!Array.isArray(value) || value.length > maximum) invalidIn(family);
  return value;
}
function strings(value: unknown, maximumItems: number, maximumLength: number, family: Family): string[] {
  return list(value, maximumItems, family).map(item => text(item, maximumLength, family));
}
/** `file:<uuid4>` / `postgres:<id>` 这类有界 owner 身份 token，绝不是原始路径。 */
function identityToken(value: unknown, family: Family): string {
  const token = text(value, MODEL_CENTER_BOUNDS.id, family);
  if (!/^[A-Za-z0-9][A-Za-z0-9:._-]*$/.test(token)) invalidIn(family);
  return token;
}
function uuid(value: unknown, family: Family): string {
  const item = text(value, 40, family);
  if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(item)) invalidIn(family);
  return item;
}

/* ------------------------------------------------------------------ 模型目录 */

const MODEL_ALLOWED = [
  'id', 'display_name', 'family', 'variant', 'version', 'capabilities', 'runtime_type',
  'model_format', 'quantization', 'precision', 'source', 'license', 'components',
  'hardware_profiles', 'hardware_profile_details', 'compatibility', 'status', 'metadata',
  'identity_id', 'historically_validated', 'verified', 'license_status',
] as const;
const METADATA_ALLOWED = [
  'sha256', 'installed', 'local_discovery', 'license_status',
  'vram_required_mib', 'ram_required_mib', 'source_url',
] as const;
const PROFILE_ALLOWED = [
  'id', 'model_id', 'gpu_name', 'vram_required', 'vram_recommended', 'ram_required',
  'ram_recommended', 'context', 'resolution', 'frames', 'fps', 'offload_mode', 'tested',
  'verified_at', 'benchmark', 'profile_kind',
] as const;

function capabilities(value: unknown): ModelCenterCapability[] {
  const declared = list(value, MODEL_CENTER_BOUNDS.capabilities, 'catalog');
  if (!declared.length) invalid();
  const mapped = declared.map(item => enumerated(item, MODEL_CENTER_CAPABILITIES, 'catalog'));
  if (new Set(mapped).size !== mapped.length) invalid();
  return mapped;
}

function metadata(value: unknown): ModelCenterModel['metadata'] {
  if (value === undefined || value === null) return undefined;
  const row = object(value, METADATA_ALLOWED, 'catalog');
  const sha = optionalText(row.sha256, MODEL_CENTER_BOUNDS.digest, 'catalog');
  if (sha !== undefined && !/^[a-f0-9]{64}$/.test(sha)) invalid();
  const result: NonNullable<ModelCenterModel['metadata']> = {};
  if (sha !== undefined) result.sha256 = sha;
  const installed = optionalBoolean(row.installed, 'catalog');
  if (installed !== undefined) result.installed = installed;
  const discovery = optionalBoolean(row.local_discovery, 'catalog');
  if (discovery !== undefined) result.local_discovery = discovery;
  const licenseStatus = optionalText(row.license_status, MODEL_CENTER_BOUNDS.code, 'catalog');
  if (licenseStatus !== undefined) result.license_status = licenseStatus;
  const vram = optionalInteger(row.vram_required_mib, Number.MAX_SAFE_INTEGER, 'catalog');
  if (vram !== undefined) result.vram_required_mib = vram;
  const ram = optionalInteger(row.ram_required_mib, Number.MAX_SAFE_INTEGER, 'catalog');
  if (ram !== undefined) result.ram_required_mib = ram;
  return result;
}

function hardwareProfile(value: unknown): NonNullable<ModelCenterModel['hardware_profile']> {
  const row = object(value, PROFILE_ALLOWED, 'catalog');
  const result: NonNullable<ModelCenterModel['hardware_profile']> = {
    id: text(row.id, MODEL_CENTER_BOUNDS.id, 'catalog'),
    gpu_name: text(row.gpu_name, MODEL_CENTER_BOUNDS.gpu, 'catalog'),
    profile_kind: text(row.profile_kind, MODEL_CENTER_BOUNDS.token, 'catalog'),
  };
  const tested = optionalBoolean(row.tested, 'catalog');
  if (tested !== undefined) result.tested = tested;
  for (const [source, target] of [['vram_required', 'vram_required_mib'], ['vram_recommended', 'vram_recommended_mib'],
    ['ram_required', 'ram_required_mib'], ['ram_recommended', 'ram_recommended_mib']] as const) {
    const parsed = optionalInteger(row[source], Number.MAX_SAFE_INTEGER, 'catalog');
    if (parsed !== undefined) result[target] = parsed;
  }
  return result;
}

function model(value: unknown): ModelCenterModel {
  const row = object(value, MODEL_ALLOWED, 'catalog');
  const decoded: ModelCenterModel = {
    id: text(row.id, MODEL_CENTER_BOUNDS.id, 'catalog'),
    display_name: text(row.display_name, MODEL_CENTER_BOUNDS.label, 'catalog'),
    family: text(row.family, MODEL_CENTER_BOUNDS.label, 'catalog'),
    variant: text(row.variant, MODEL_CENTER_BOUNDS.label, 'catalog'),
    version: text(row.version, MODEL_CENTER_BOUNDS.version, 'catalog'),
    capabilities: capabilities(row.capabilities),
    runtime_type: enumerated(row.runtime_type, MODEL_CENTER_RUNTIME_TYPES, 'catalog'),
    model_format: text(row.model_format, MODEL_CENTER_BOUNDS.label, 'catalog'),
  };
  const status = optionalEnumerated(row.status, MODEL_CENTER_STATUSES, 'catalog');
  if (status !== undefined) decoded.status = status;
  for (const [source, target] of [['quantization', 'quantization'], ['precision', 'precision'],
    ['source', 'source'], ['license', 'license'], ['license_status', 'license_status']] as const) {
    const parsed = optionalText(row[source], MODEL_CENTER_BOUNDS.label, 'catalog');
    if (parsed !== undefined) decoded[target] = parsed;
  }
  const verified = optionalBoolean(row.verified, 'catalog');
  if (verified !== undefined) decoded.verified = verified;
  const historical = optionalBoolean(row.historically_validated, 'catalog');
  if (historical !== undefined) decoded.historically_validated = historical;
  decoded.metadata = metadata(row.metadata);
  if (row.identity_id !== undefined && row.identity_id !== null) uuid(row.identity_id, 'catalog');
  if (row.hardware_profile_details !== undefined && row.hardware_profile_details !== null) {
    const profiles = list(row.hardware_profile_details, MODEL_CENTER_BOUNDS.profiles, 'catalog').map(hardwareProfile);
    if (new Set(profiles.map(item => item.id)).size !== profiles.length) invalid();
    // 只保留界面真正要用的第一条；多档位时以 owner 给出的顺序取第一个非空项。
    const first = profiles[0];
    if (first) decoded.hardware_profile = first;
  }
  return decoded;
}

const RUNTIME_ALLOWED = ['id', 'runtime_type', 'status', 'management', 'capabilities', 'instance', 'discovery', 'base_url', 'port', 'health_endpoint'] as const;
const INSTANCE_ALLOWED = ['state', 'process_alive', 'http_reachable', 'loaded_models', 'version', 'safe_error_code', 'runtime_id', 'process_id'] as const;

function runtime(value: unknown): ModelCenterRuntime {
  const row = object(value, RUNTIME_ALLOWED, 'catalog');
  const decoded: ModelCenterRuntime = { id: identityToken(row.id, 'catalog'), capabilities: [] };
  const type = optionalEnumerated(row.runtime_type, MODEL_CENTER_RUNTIME_TYPES, 'catalog');
  if (type !== undefined) decoded.runtime_type = type;
  const status = optionalText(row.status, MODEL_CENTER_BOUNDS.code, 'catalog');
  if (status !== undefined) decoded.status = status;
  const management = optionalEnumerated(row.management, MODEL_CENTER_RUNTIME_MANAGEMENTS, 'catalog');
  if (management !== undefined) decoded.management = management;
  if (row.capabilities !== undefined && row.capabilities !== null) {
    decoded.capabilities = list(row.capabilities, MODEL_CENTER_BOUNDS.capabilities, 'catalog')
      .map(item => enumerated(item, MODEL_CENTER_CAPABILITIES, 'catalog'));
  }
  if (row.instance !== undefined && row.instance !== null) decoded.instance = instance(row.instance);
  if (row.discovery !== undefined && row.discovery !== null) {
    const discovery = object(row.discovery, ['path_exists', 'executable_exists', 'version', 'security_warning'] as const, 'catalog');
    decoded.discovery = {
      path_exists: optionalBoolean(discovery.path_exists, 'catalog'),
      executable_exists: optionalBoolean(discovery.executable_exists, 'catalog'),
    };
  }
  return decoded;
}

function instance(value: unknown): NonNullable<ModelCenterRuntime['instance']> {
  const row = object(value, INSTANCE_ALLOWED, 'catalog');
  const decoded: NonNullable<ModelCenterRuntime['instance']> = {};
  const state = optionalEnumerated(row.state, MODEL_CENTER_RUNTIME_STATES, 'catalog');
  if (state !== undefined) decoded.state = state;
  const alive = optionalBoolean(row.process_alive, 'catalog');
  if (alive !== undefined) decoded.process_alive = alive;
  const reachable = optionalBoolean(row.http_reachable, 'catalog');
  if (reachable !== undefined) decoded.http_reachable = reachable;
  if (row.loaded_models !== undefined && row.loaded_models !== null) {
    decoded.loaded_models = strings(row.loaded_models, MODEL_CENTER_BOUNDS.items, MODEL_CENTER_BOUNDS.id, 'catalog');
  }
  const version = optionalText(row.version, MODEL_CENTER_BOUNDS.version, 'catalog');
  if (version !== undefined) decoded.version = version;
  // `safe_error_code` 是 owner 自己的安全码；原始 `error` 文本永不进入前端。
  const safe = optionalText(row.safe_error_code, MODEL_CENTER_BOUNDS.code, 'catalog');
  if (safe !== undefined) decoded.safe_error_code = safe;
  return decoded;
}

const SNAPSHOT_ALLOWED = ['runtime_id', 'runtime_version', 'detected_at', 'runtime_state', 'capabilities', 'available_models', 'adapters', 'node_classes', 'warnings'] as const;

/** `/api/model-center/runtimes/{id}/capabilities`：唯一能把声明证成"真实探测到"的来源。 */
export function modelCenterRuntimeCapabilitySnapshot(value: unknown, expectedRuntimeId: string): ModelCenterRuntimeCapabilitySnapshot {
  return scope('catalog', () => {
    const row = object(value, SNAPSHOT_ALLOWED, 'catalog');
    const runtimeId = identityToken(row.runtime_id, 'catalog');
    if (runtimeId !== expectedRuntimeId) mismatch();
    const decoded: ModelCenterRuntimeCapabilitySnapshot = {
      runtime_id: runtimeId,
      capabilities: strings(row.capabilities, MODEL_CENTER_BOUNDS.capabilities, MODEL_CENTER_BOUNDS.token, 'catalog'),
    };
    const detected = optionalText(row.detected_at, MODEL_CENTER_BOUNDS.timestamp, 'catalog');
    if (detected !== undefined) decoded.detected_at = detected;
    const state = optionalText(row.runtime_state, MODEL_CENTER_BOUNDS.code, 'catalog');
    if (state !== undefined) decoded.runtime_state = state;
    if (row.available_models !== undefined && row.available_models !== null) {
      decoded.available_models = strings(row.available_models, MODEL_CENTER_BOUNDS.items, MODEL_CENTER_BOUNDS.id, 'catalog');
    }
    if (row.node_classes !== undefined && row.node_classes !== null) {
      decoded.node_classes = strings(row.node_classes, MODEL_CENTER_BOUNDS.items, MODEL_CENTER_BOUNDS.token, 'catalog');
    }
    if (row.warnings !== undefined && row.warnings !== null) {
      decoded.warnings = strings(row.warnings, MODEL_CENTER_BOUNDS.reasons, MODEL_CENTER_BOUNDS.text, 'catalog');
    }
    return decoded;
  });
}

/**
 * `/api/model-center/models` + `/api/model-center/runtimes` 的合并投影。
 *
 * 端点本身没有项目身份字段（它是全局注册表读取），因此这里**不做**伪造的
 * scope 校验；身份一致性由 `createModelCenterClient` 负责（调用方捕获的 scope
 * 与外来的 projectId 不一致时直接拒绝）。
 */
export function modelCenterCatalog(
  models: unknown, runtimes: unknown,
  capabilitySnapshots: readonly ModelCenterRuntimeCapabilitySnapshot[] = [],
  hiddenByAuthority = 0,
): ModelCenterCatalogPayload {
  return scope('catalog', () => {
    const modelsEnvelope = object(models, ['items'] as const, 'catalog');
    const runtimesEnvelope = object(runtimes, ['items'] as const, 'catalog');
    const decodedModels = list(modelsEnvelope.items, MODEL_CENTER_BOUNDS.items, 'catalog').map(model);
    const decodedRuntimes = list(runtimesEnvelope.items, MODEL_CENTER_BOUNDS.items, 'catalog').map(runtime);
    if (new Set(decodedModels.map(item => item.id)).size !== decodedModels.length) invalid();
    if (new Set(decodedRuntimes.map(item => item.id)).size !== decodedRuntimes.length) invalid();
    if (!Number.isSafeInteger(hiddenByAuthority) || hiddenByAuthority < 0 || hiddenByAuthority > MODEL_CENTER_BOUNDS.items) invalid();
    const sources: ModelCenterCatalogPayload['sources'] = ['MODEL_CENTER_MODELS', 'MODEL_CENTER_RUNTIMES'];
    for (const snapshot of capabilitySnapshots) {
      if (!decodedRuntimes.some(item => item.id === snapshot.runtime_id)) invalid();
    }
    return {
      models: decodedModels, runtimes: decodedRuntimes, capability_snapshots: capabilitySnapshots,
      hidden_by_authority: hiddenByAuthority, sources,
    };
  });
}

/** Revalidate caller-injected projections; an array shape is not decoder evidence. */
export function modelCenterInjectedCatalog(value: unknown): ModelCenterCatalogPayload {
  return scope('catalog', () => {
    const root = object(value, ['models', 'runtimes', 'capability_snapshots', 'hidden_by_authority', 'sources'], 'catalog');
    if (!Array.isArray(root.models) && !Array.isArray(root.runtimes)) {
      // Preserve the original pair of raw endpoint envelopes, without accepting
      // a mixed raw/decoded projection or extra claimed observation fields.
      object(value, ['models', 'runtimes'], 'catalog');
      return modelCenterCatalog(root.models, root.runtimes);
    }
    const models = list(root.models, MODEL_CENTER_BOUNDS.items, 'catalog').map(value => {
      const item = object(value, [...MODEL_ALLOWED, 'hardware_profile'], 'catalog');
      if (item.hardware_profile === undefined) return item;
      if (item.hardware_profile_details !== undefined) invalid();
      const profile = object(item.hardware_profile, ['id', 'gpu_name', 'profile_kind', 'tested',
        'vram_required_mib', 'vram_recommended_mib', 'ram_required_mib', 'ram_recommended_mib'], 'catalog');
      const mapped: Record<string, unknown> = {};
      for (const [key, entry] of Object.entries(profile)) mapped[key.endsWith('_mib') ? key.slice(0, -4) : key] = entry;
      const { hardware_profile: _profile, ...rest } = item;
      return { ...rest, hardware_profile_details: [mapped] };
    });
    const runtimes = list(root.runtimes, MODEL_CENTER_BOUNDS.items, 'catalog');
    const snapshots = list(root.capability_snapshots, MODEL_CENTER_BOUNDS.items, 'catalog').map(value => {
      const item = object(value, SNAPSHOT_ALLOWED, 'catalog');
      return modelCenterRuntimeCapabilitySnapshot(item, identityToken(item.runtime_id, 'catalog'));
    });
    if (new Set(snapshots.map(item => item.runtime_id)).size !== snapshots.length) invalid();
    const sources = list(root.sources, 2, 'catalog');
    if (sources.length !== 2 || sources[0] !== 'MODEL_CENTER_MODELS' || sources[1] !== 'MODEL_CENTER_RUNTIMES') invalid();
    const hidden = integer(root.hidden_by_authority, MODEL_CENTER_BOUNDS.items, 'catalog');
    return modelCenterCatalog({ items: models }, { items: runtimes }, snapshots, hidden);
  });
}

/* ------------------------------------------------------------------ 存储准入 */

const STORAGE_ALLOWED = ['assets', 'trash', 'limits', 'model_storage', 'cache_storage', 'export_storage', 'physical_cleanup_available', 'admission'] as const;
const ADMISSION_ALLOWED = ['state', 'available_import_bytes', 'reserve_bytes', 'measurement', 'paths', 'external_model_scan', 'automatic_cleanup', 'automatic_migration'] as const;

function counted(value: unknown, family: Family, allowed: readonly string[]): { count: number; bytes: number } {
  const row = object(value, allowed, family);
  return { count: integer(row.count, Number.MAX_SAFE_INTEGER, family), bytes: integer(row.bytes, Number.MAX_SAFE_INTEGER, family) };
}

/**
 * 项目存储 + 准入的严格解码。原 owner 自己的不变式在这也成立：
 * 每个符号所有者只能是它声明的那个标签；`physical_cleanup_available` 只能是 `false`；
 * 三个自动动作只能是 `false`；`UNAVAILABLE` 与 `0` 是不同的事实。
 */
export function modelCenterStorage(value: unknown): ModelCenterStoragePayload {
  return scope('storage', () => {
    const row = object(value, STORAGE_ALLOWED, 'storage');
    if (row.model_storage !== 'EXTERNAL_READ_ONLY' || row.cache_storage !== 'SEPARATE_OWNER'
      || row.export_storage !== 'CLIENT_SELECTED_DOWNLOAD' || row.physical_cleanup_available !== false) invalidIn('storage');
    const limits = object(row.limits, ['asset_bytes', 'project_asset_bytes', 'project_assets'] as const, 'storage');
    const decoded: ModelCenterStoragePayload = {
      assets: counted(row.assets, 'storage', ['count', 'bytes'] as const),
      trash: counted(row.trash, 'storage', ['count', 'bytes'] as const),
      limits: {
        asset_bytes: integer(limits.asset_bytes, Number.MAX_SAFE_INTEGER, 'storage'),
        project_asset_bytes: integer(limits.project_asset_bytes, Number.MAX_SAFE_INTEGER, 'storage'),
        project_assets: integer(limits.project_assets, Number.MAX_SAFE_INTEGER, 'storage'),
      },
      model_storage: 'EXTERNAL_READ_ONLY', cache_storage: 'SEPARATE_OWNER',
      export_storage: 'CLIENT_SELECTED_DOWNLOAD', physical_cleanup_available: false,
    };
    if (row.admission === undefined || row.admission === null) return decoded;
    const admission = object(row.admission, ADMISSION_ALLOWED, 'storage');
    if (admission.measurement !== STORAGE_MEASUREMENT
      || admission.external_model_scan !== false || admission.automatic_cleanup !== false || admission.automatic_migration !== false) invalidIn('storage');
    const state = enumerated(admission.state, STORAGE_ADMISSION_STATES, 'storage');
    // 零容量与"无法测量"必须可区分：UNAVAILABLE 配一个数字、或非 UNAVAILABLE 配 null，都是非法。
    const available = admission.available_import_bytes;
    if (state === 'UNAVAILABLE') {
      if (available !== null) invalidIn('storage');
    } else if (typeof available !== 'number' || !Number.isSafeInteger(available) || available < 0) invalidIn('storage');
    const paths = object(admission.paths, STORAGE_PATH_OWNERS, 'storage');
    const owners = {} as Record<StoragePathOwner, string>;
    for (const owner of STORAGE_PATH_OWNERS) {
      if (paths[owner] !== STORAGE_PATH_OWNER_VALUES[owner]) invalidIn('storage');
      owners[owner] = STORAGE_PATH_OWNER_VALUES[owner];
    }
    decoded.admission = {
      state, available_import_bytes: state === 'UNAVAILABLE' ? null : available as number,
      reserve_bytes: integer(admission.reserve_bytes, Number.MAX_SAFE_INTEGER, 'storage'),
      measurement: STORAGE_MEASUREMENT, paths: owners,
      external_model_scan: false, automatic_cleanup: false, automatic_migration: false,
    };
    return decoded;
  });
}

/* ------------------------------------------------------------------ 凭据 */

/**
 * `/api/credentials/{provider}` 的严格解码。白名单只有
 * `CredentialVault.status()` 真实返回的六个字段；`secret` 之类的键一旦出现就是
 * 一次被拒绝的读取（而不是一个被渲染的值）。
 */
export function modelCenterCredential(value: unknown, expectedProvider: string): ModelCenterCredentialState {
  return scope('credential', () => {
    scanForSecrets(value);
    const row = object(value, MODEL_CENTER_CREDENTIAL_KEYS, 'credential');
    const provider = text(row.provider, MODEL_CENTER_BOUNDS.id, 'credential');
    if (provider !== expectedProvider) invalidIn('credential');
    const decoded: ModelCenterCredentialState = {
      provider, configured: boolean(row.configured, 'credential'),
    };
    const backend = optionalEnumerated(row.backend, MODEL_CENTER_VAULT_BACKENDS, 'credential');
    if (backend !== undefined) decoded.backend = backend;
    const persistent = optionalBoolean(row.persistent, 'credential');
    if (persistent !== undefined) decoded.persistent = persistent;
    const degraded = optionalBoolean(row.degraded, 'credential');
    if (degraded !== undefined) decoded.degraded = degraded;
    const reason = optionalText(row.degraded_reason, MODEL_CENTER_BOUNDS.code, 'credential');
    if (reason !== undefined) decoded.degraded_reason = reason;
    return decoded;
  });
}

/* ------------------------------------------------------------------ 硬件（可选注入） */

const HARDWARE_ALLOWED = ['state', 'architecture', 'ram_mib', 'vram_mib', 'gpu_vendor', 'reason', 'source'] as const;

/**
 * 可选注入的主机硬件事实。缺失、未知或形状不符时返回 `UNKNOWN` 事实而不是抛错：
 * 硬件不是本面板的读取权威，界面据 `UNKNOWN` 显示"未提供硬件事实"。
 */
export function modelCenterHardware(value: unknown): ModelCenterHardwareFact {
  try {
    if (!value || typeof value !== 'object' || Array.isArray(value)) return { state: 'UNKNOWN', reason: MODEL_CENTER_CODES.hardwareUnavailable.code };
    const row = object(value, HARDWARE_ALLOWED, 'hardware');
    if (row.state !== 'HOST_TOTAL_CAPACITY' || row.source !== 'HOST_INVENTORY') {
      return { state: 'UNKNOWN', reason: MODEL_CENTER_CODES.hardwareUnavailable.code };
    }
    const fact: ModelCenterHardwareFact = {
      state: 'HOST_TOTAL_CAPACITY', source: 'HOST_INVENTORY',
      ram_mib: integer(row.ram_mib, Number.MAX_SAFE_INTEGER, 'hardware'),
    };
    const vram = optionalInteger(row.vram_mib, Number.MAX_SAFE_INTEGER, 'hardware');
    if (vram !== undefined) fact.vram_mib = vram;
    const architecture = optionalText(row.architecture, MODEL_CENTER_BOUNDS.token, 'hardware');
    if (architecture !== undefined) fact.architecture = architecture;
    const vendor = optionalText(row.gpu_vendor, MODEL_CENTER_BOUNDS.token, 'hardware');
    if (vendor !== undefined) fact.gpu_vendor = vendor;
    return fact;
  } catch { return { state: 'UNKNOWN', reason: MODEL_CENTER_CODES.hardwareUnavailable.code }; }
}

/* ------------------------------------------------------------------ scope */

/**
 * 捕获的协作 scope 与外来的 projectId 必须一致；不一致直接拒绝，绝不借用身份。
 * 这个函数不是解码器入口，因此它直接抛 `ApiError`（不会把内部形状标记泄漏出去）。
 */
export function modelCenterExpectedScope(projectId: string, scope?: ModelCenterScope): ModelCenterScope {
  if (typeof projectId !== 'string' || !projectId.trim() || projectId.length > MODEL_CENTER_BOUNDS.id) {
    throw new ApiError({ status: 400, code: MODEL_CENTER_CODES.catalogInvalid.code, message: MODEL_CENTER_CODES.catalogInvalid.message });
  }
  if (scope && scope.novel_id !== projectId) {
    throw new ApiError({ status: 403, code: MODEL_CENTER_CODES.catalogScopeMismatch.code, message: MODEL_CENTER_CODES.catalogScopeMismatch.message });
  }
  return scope ? { ...scope } : { mode: 'local', novel_id: projectId };
}
