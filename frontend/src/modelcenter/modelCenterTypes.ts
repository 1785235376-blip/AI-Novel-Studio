/**
 * UX-07 模型中心与存储的实际可用性 —— 词表、类型与机器码。
 *
 * 这个目录是**只读消费者**：它不新增第二套模型注册表、下载器、存储系统或调度器。
 * 下面每一个字面量都来自真实原 owner；改动前请先改后端，不要在前端猜测：
 *
 * - `MODEL_CENTER_MODEL_FIELDS` / `ModelStatus` / `Capability` / `RuntimeType` /
 *   `RuntimeState` / `RuntimeManagement` 来自
 *   `app/model_center/domain.py`（`ModelStatus`、`Capability`、`RuntimeType`、
 *   `RuntimeState` 逐条转写）与 `app/model_center/service.py::model()` 写回的三个
 *   观察字段 `verified` / `historically_validated` / `hardware_profile_details`。
 * - `API_PROVIDER_EXECUTION` 抄自 `app/model_provider_contracts.py`：
 *   `ProviderAvailability.execution_available: Literal[False]`、
 *   `execution_authority: "ORIGINAL_REVIEWED_REQUEST_REQUIRED"`、
 *   `TaskMatch.execution_authority/automatic_fallback/gpu_fit_verified: Literal[False]`。
 *   因此界面永远不得把"已注册/可用"写成"可以执行"。
 * - `PROVIDER_RUNTIME_AVAILABILITY_FACTS` 抄自
 *   `app/provider_routing_policy_v2.py::evaluate_routing` 的准入合取式
 *   （`configured and installed and healthy and reachable and authorized and compatible`），
 *   以及 `app/provider_runtime_v2_model_center_snapshot_bridge.py::_availability`
 *   目前把 `authorized` / `compatible` 固定为 `False`、`trusted` / `self_hosted`
 *   固定为 `False` 的现状。也就是说：**今天没有任何路线能通过该准入**，
 *   界面必须说清是哪一个事实挡住了，而不是说"没有可用模型"。
 * - `STORAGE_ADMISSION_*` 抄自 `app/creative/storage_admission.py::view()`
 *   与 `app/creative/workspace.py::storage()`：`physical_cleanup_available: False`、
 *   `external_model_scan/automatic_cleanup/automatic_migration: False`。原 owner
 *   只测量**现有资产文件系统 + 项目配额**，既不扫描模型目录，也不做任何清理。
 * - `STORAGE_PATH_OWNERS` 抄自 `storage_admission.py` 的 `paths` 五个符号所有者。
 *   任何真实路径都不进入本模块（`studioStorageAdmissionClient.test.ts` 已经要求
 *   拒收 `raw_path` / `actual_directory` 之类的越权字段）。
 * - 凭据只暴露"存在与否"：`app/credential_vault.py::CredentialVault.status()`
 *   返回 `{provider, configured, backend, persistent, degraded, degraded_reason, secret: None}`，
 *   `secret` 恒为 `None`。本模块的 `secretState()` 因此只报告
 *   PRESENT / ABSENT / EXPIRED / UNKNOWN，且**永不携带密钥值**。
 *
 * **刻意不存在的东西**：任何"下载/准备/修复"的写操作、任何"清理/迁移/删除"的
 * 写操作、任何硬件探测、任何密钥读写。原 owner 没有这些端点，界面也不提供。
 */

import type { CollaborationContext } from '../api';
import type { StudioGraphTransport } from '../creative/studioGraphClient';

/* ------------------------------------------------------------------ 词表 */

/** `app/model_center/domain.py::ModelStatus`（逐条，顺序同源）。 */
export const MODEL_CENTER_STATUSES = [
  'NOT_FOUND', 'VALIDATION_REQUIRED', 'NOT_INSTALLED', 'DISCOVERED', 'VALIDATING',
  'READY', 'DEGRADED', 'INCOMPATIBLE', 'MISSING_COMPONENT', 'LICENSE_REQUIRED',
  'RUNTIME_REQUIRED', 'DISABLED',
] as const;
export type ModelCenterStatus = typeof MODEL_CENTER_STATUSES[number];

/** `app/model_center/domain.py::Capability`。 */
export const MODEL_CENTER_CAPABILITIES = [
  'TEXT', 'IMAGE', 'VIDEO', 'VISION', 'TTS', 'AUDIO', 'EMBEDDING', 'RERANK',
  'RESTORATION', 'INTERPOLATION',
] as const;
export type ModelCenterCapability = typeof MODEL_CENTER_CAPABILITIES[number];

/**
 * 呈现用的四种模态。`VISION`/`EMBEDDING`/`RERANK`/`RESTORATION`/`INTERPOLATION`
 * 都属于"其它"，但仍以原 owner 的能力码原样显示，绝不折叠掉。
 */
export const MODEL_CENTER_MODALITIES = ['text', 'image', 'video', 'audio'] as const;
export type ModelCenterModality = typeof MODEL_CENTER_MODALITIES[number];

/** 能力码 → 呈现模态。纯呈现映射，不改变能力本身。 */
export const MODEL_CENTER_MODALITY_OF: Readonly<Record<ModelCenterCapability, ModelCenterModality>> = Object.freeze({
  TEXT: 'text', IMAGE: 'image', VIDEO: 'video', VISION: 'image',
  TTS: 'audio', AUDIO: 'audio', EMBEDDING: 'text', RERANK: 'text',
  RESTORATION: 'image', INTERPOLATION: 'video',
});

/** `app/model_center/domain.py::RuntimeType`。 */
export const MODEL_CENTER_RUNTIME_TYPES = [
  'OLLAMA', 'AUTOMATIC1111', 'LLAMA_CPP', 'COMFYUI', 'OPENAI_COMPATIBLE_LOCAL',
  'CUSTOM_HTTP', 'WHISPER_CPP',
] as const;
export type ModelCenterRuntimeType = typeof MODEL_CENTER_RUNTIME_TYPES[number];

/** `app/model_center/domain.py::RuntimeState`。 */
export const MODEL_CENTER_RUNTIME_STATES = ['STOPPED', 'STARTING', 'RUNNING', 'DEGRADED', 'FAILED', 'EXTERNAL'] as const;
export type ModelCenterRuntimeState = typeof MODEL_CENTER_RUNTIME_STATES[number];

/** `app/model_center/domain.py::RuntimeManagement`。 */
export const MODEL_CENTER_RUNTIME_MANAGEMENTS = ['MANAGED', 'EXTERNAL'] as const;
export type ModelCenterRuntimeManagement = typeof MODEL_CENTER_RUNTIME_MANAGEMENTS[number];

/**
 * 能力的两条来源。`declared` = 模型定义自己声明的；`verified` = 运行时被真实
 * 探测到、或原 owner 的校验记录在当前指纹下仍然有效。两者永不互相提升。
 */
export const MODEL_CENTER_CAPABILITY_ORIGINS = ['declared', 'verified'] as const;
export type ModelCenterCapabilityOrigin = typeof MODEL_CENTER_CAPABILITY_ORIGINS[number];

/** `model_provider_contracts.py::ProviderCapability.verification` 的取值。 */
export const MODEL_CENTER_VERIFICATIONS = ['NOT_VERIFIED', 'REGISTERED_ADAPTER_CONTRACT_ONLY'] as const;
export type ModelCenterVerification = typeof MODEL_CENTER_VERIFICATIONS[number];

/** `model_provider_contracts.py::ProviderAvailability.status`。 */
export const MODEL_CENTER_PROVIDER_STATUSES = ['REGISTERED', 'UNAVAILABLE', 'RESERVED'] as const;
export type ModelCenterProviderStatus = typeof MODEL_CENTER_PROVIDER_STATUSES[number];

/**
 * 原 owner 的准入事实（`provider_routing_policy_v2.py::evaluate_routing` 要求六项
 * 全为真才可能入选）。`bridge` 目前把 `authorized`/`compatible` 写死为 `False`，
 * 所以界面必须逐项显示，而不是汇总成一句"不可用"。
 */
export const PROVIDER_RUNTIME_AVAILABILITY_FACTS = [
  ['configured', '已配置'],
  ['installed', '已安装'],
  ['healthy', '健康'],
  ['reachable', '可连接'],
  ['authorized', '已授权'],
  ['compatible', '已验证兼容'],
] as const;
export type ProviderRuntimeAvailabilityFact = typeof PROVIDER_RUNTIME_AVAILABILITY_FACTS[number][0];

/** 原 owner 的执行权威常数；三者都只能是 `false`。 */
export const API_PROVIDER_EXECUTION = Object.freeze({
  execution_available: false,
  execution_authority: 'ORIGINAL_REVIEWED_REQUEST_REQUIRED',
  automatic_fallback: false,
  gpu_fit_verified: false,
} as const);

/** `modelCenterOps.readinessNotice()` 的五种下载/准备状态。**不可写**。 */
export const MODEL_CENTER_READINESS_STATES = ['NOT_DOWNLOADED', 'PREPARING', 'READY', 'FAILED', 'UNKNOWN'] as const;
export type ModelCenterReadinessState = typeof MODEL_CENTER_READINESS_STATES[number];

export const MODEL_CENTER_READINESS_LABELS: Readonly<Record<ModelCenterReadinessState, string>> = Object.freeze({
  NOT_DOWNLOADED: '未下载', PREPARING: '准备中', READY: '就绪', FAILED: '失败', UNKNOWN: '状态未知',
});

/** 界面状态机的显式取值。读取失败永不渲染成"没有可用模型"。 */
export const MODEL_CENTER_SURFACE_STATES = ['IDLE', 'LOADING', 'READY', 'EMPTY', 'DENIED', 'FAILED'] as const;
export type ModelCenterSurfaceState = typeof MODEL_CENTER_SURFACE_STATES[number];

/** 凭据的三态；`expired` 只能来自 owner 自己声明的过期事实。 */
export const MODEL_CENTER_SECRET_STATES = ['PRESENT', 'ABSENT', 'EXPIRED', 'UNKNOWN'] as const;
export type ModelCenterSecretState = typeof MODEL_CENTER_SECRET_STATES[number];

/** `app/credential_vault.py` 支持的落盘后端。 */
export const MODEL_CENTER_VAULT_BACKENDS = ['windows', 'keyring', 'memory'] as const;
export type ModelCenterVaultBackend = typeof MODEL_CENTER_VAULT_BACKENDS[number];

/** `storage_admission.py::view()::state` 的三态。 */
export const STORAGE_ADMISSION_STATES = ['READY', 'LOW_SPACE_OR_QUOTA', 'UNAVAILABLE'] as const;
export type StorageAdmissionState = typeof STORAGE_ADMISSION_STATES[number];

/** `storage_admission.py` 的五个符号路径所有者；真实路径永不进入前端。 */
export const STORAGE_PATH_OWNERS = ['project', 'assets', 'models', 'cache', 'exports'] as const;
export type StoragePathOwner = typeof STORAGE_PATH_OWNERS[number];

export const STORAGE_PATH_OWNER_VALUES: Readonly<Record<StoragePathOwner, string>> = Object.freeze({
  project: 'EXISTING_PROJECT_OWNER', assets: 'EXISTING_ASSET_LIBRARY',
  models: 'MODEL_CENTER_REFERENCES_ONLY', cache: 'EXISTING_CACHE_OWNER', exports: 'USER_SELECTED_DOWNLOAD',
});

/** 独占的测量口径；原 owner 只测量现有资产文件系统与项目配额。 */
export const STORAGE_MEASUREMENT = 'CURRENT_ORIGINAL_ASSET_FILESYSTEM_AND_PROJECT_QUOTA' as const;

/** 孤儿候选的原因码。`UNVERIFIABLE` 表示"载荷里没有可核对的删除记录"。 */
export const ORPHAN_REASON_CODES = [
  'SOFT_DELETED_ASSET', 'SUPERSEDED_REVISION', 'NO_OWNER_RECORD', 'UNVERIFIABLE',
] as const;
export type OrphanReasonCode = typeof ORPHAN_REASON_CODES[number];

/** 原因码 → 中文说明（只说事实，不说"可安全删除"）。 */
export const ORPHAN_REASON_LABELS: Readonly<Record<OrphanReasonCode, string>> = Object.freeze({
  SOFT_DELETED_ASSET: '该资产已被软删除，仍占用磁盘与项目配额。',
  SUPERSEDED_REVISION: '该记录被同一资产的更新版本取代，仅作为历史保留。',
  NO_OWNER_RECORD: '没有任何资产记录或关系指向此字节，来源不可核对。',
  UNVERIFIABLE: '原 owner 的只读投影里没有可核对的删除记录，因此无法判定。',
});

/** `modelCenterOps.capabilityMatrix()` 的逐格结论。 */
export const CAPABILITY_MATRIX_STATES = ['declared_only', 'verified', 'undeclared', 'unknown'] as const;
export type CapabilityMatrixState = typeof CAPABILITY_MATRIX_STATES[number];

/** `routingExplanation()` 的结论。`UNKNOWN` 只在必需的 owner 事实上缺失时出现。 */
export const ROUTE_VERDICTS = ['SELECTABLE', 'NOT_SELECTABLE', 'UNKNOWN'] as const;
export type RouteVerdict = typeof ROUTE_VERDICTS[number];

/* ------------------------------------------------------------------ 机器码 */

/**
 * 稳定机器码 + 中文用户文案。`code` 只用于日志/测试与 `ApiError.problem.code`；
 * 界面渲染 `message`。任何一条都不得把 owner 的内部路径、端点或密钥写进文案。
 */
export const MODEL_CENTER_CODES = Object.freeze({
  catalogInvalid: { code: 'MODEL_CENTER_CATALOG_INVALID', message: '模型目录数据不可用或不是原服务声明的形状，请重新读取。' },
  runtimeInvalid: { code: 'MODEL_CENTER_RUNTIME_INVALID', message: '运行时状态数据不可用或不是原服务声明的形状，请重新读取。' },
  catalogScopeMismatch: { code: 'MODEL_CENTER_CATALOG_SCOPE_MISMATCH', message: '模型目录与当前项目或分支不一致，请重新打开。' },
  storageInvalid: { code: 'MODEL_CENTER_STORAGE_INVALID', message: '存储数据不可用或不是原服务声明的形状，请重新读取。' },
  storageScopeMismatch: { code: 'MODEL_CENTER_STORAGE_SCOPE_MISMATCH', message: '存储数据与当前项目或分支不一致，请重新打开。' },
  credentialInvalid: { code: 'MODEL_CENTER_CREDENTIAL_INVALID', message: '凭据状态不可用或原服务回传了本不该暴露的字段，请重新读取。' },
  hardwareInvalid: { code: 'MODEL_CENTER_HARDWARE_INVALID', message: '主机硬件事实不可用或不是原服务声明的形状。' },
  catalogUnavailable: { code: 'MODEL_CENTER_CATALOG_UNAVAILABLE', message: '当前服务未提供模型目录读取，界面按"未知"呈现。' },
  runtimeUnavailable: { code: 'MODEL_CENTER_RUNTIME_UNAVAILABLE', message: '当前服务未提供运行时状态读取，界面按"未知"呈现。' },
  credentialUnavailable: { code: 'MODEL_CENTER_CREDENTIAL_UNAVAILABLE', message: '当前服务未提供凭据状态读取，界面只显示"未知"。' },
  hardwareUnavailable: { code: 'MODEL_CENTER_HARDWARE_UNAVAILABLE', message: '当前服务未提供主机硬件事实，界面不猜测显存与内存。' },
  readDenied: { code: 'MODEL_CENTER_READ_DENIED', message: '当前会话无权读取模型中心，请重新核对身份与分支。' },
  readFailed: { code: 'MODEL_CENTER_READ_FAILED', message: '模型中心读取失败，请稍后重新核对。' },
  cleanupUnavailable: { code: 'MODEL_CENTER_CLEANUP_UNAVAILABLE', message: '原 owner 声明 physical_cleanup_available=false：本界面不提供清理、迁移或删除操作。' },
  downloadUnavailable: { code: 'MODEL_CENTER_DOWNLOAD_UNAVAILABLE', message: '原 owner 没有下载端点：本界面不提供下载、准备或修复操作。' },
  routeBlocked: { code: 'MODEL_CENTER_ROUTE_BLOCKED', message: '当前没有可执行的模型路线；下方列出阻塞该模型的每一项事实。' },
  routeUnknown: { code: 'MODEL_CENTER_ROUTE_UNKNOWN', message: '缺少判断是否可选所需的原 owner 事实，按"未知"处理，不当作可选。' },
  secretValueRejected: { code: 'MODEL_CENTER_SECRET_VALUE_REJECTED', message: '服务返回了本不该暴露的凭据字段，已拒绝该响应。' },
  orphanUnverifiable: { code: 'MODEL_CENTER_ORPHAN_UNVERIFIABLE', message: '原 owner 的只读投影未提供逐条删除记录，无法产生孤儿候选。' },
} as const);

export type ModelCenterCode = typeof MODEL_CENTER_CODES[keyof typeof MODEL_CENTER_CODES]['code'];

/* ------------------------------------------------------------------ 有界限值 */

/** 所有文本框的上界；越界即拒绝读取。 */
export const MODEL_CENTER_BOUNDS = Object.freeze({
  id: 200, label: 200, version: 120, token: 120, code: 120, revision: 120,
  items: 512, capabilities: 32, reasons: 64, checks: 32, profiles: 64,
  notes: 2000, gpu: 200, url: 300, text: 400, timestamp: 40, digest: 128,
} as const);

/**
 * 凭据响应的**白名单**。白名单之外任何键都让整个响应被拒；这是"永不携带密钥值"
 * 的机械保证：`secret`、`api_key`、`token` 之类的键在 `credential_vault.status()`
 * 里就不存在，一旦出现即视为越权回传。
 */
export const MODEL_CENTER_CREDENTIAL_KEYS = [
  'provider', 'configured', 'backend', 'persistent', 'degraded', 'degraded_reason',
] as const;

/**
 * 任何载荷里出现这些键名即整包拒绝（大小写不敏感，精确匹配或 `*_` 后缀匹配）。
 * 刻意不含孤立的 `token`：`max_tokens` / `context_tokens` 是普通数字字段。
 */
export const MODEL_CENTER_FORBIDDEN_SECRET_KEYS = [
  'secret', 'client_secret', 'api_key', 'apikey', 'password', 'passwd',
  'access_token', 'refresh_token', 'bearer_token', 'auth_token', 'access_key',
  'private_key', 'credential_value', 'secret_value',
] as const;

/* ------------------------------------------------------------------ 类型 */

export type ModelCenterSource =
  | 'MODEL_CENTER_MODELS' | 'MODEL_CENTER_RUNTIMES' | 'STUDIO_STORAGE' | 'CREDENTIAL_STATUS';

export type ModelCenterScope = {
  mode: 'local' | 'collaboration';
  novel_id: string;
  workspace_id?: string | null;
  project_id?: string | null;
  storyline_id?: string | null;
  branch_id?: string | null;
};

/** 模型声明里必然存在的字段（`ModelDefinition` 的非默认字段）。 */
export type ModelCenterModelDeclared = {
  id: string;
  display_name: string;
  family: string;
  variant: string;
  version: string;
  capabilities: readonly ModelCenterCapability[];
  runtime_type: ModelCenterRuntimeType;
  model_format: string;
};

/**
 * 原 owner 回传的观察与可选事实。**缺失就保持缺失**（`undefined` / `null`），
 * 绝不补一个"看起来更好"的默认值。
 */
export type ModelCenterModelObservation = {
  status?: ModelCenterStatus;
  quantization?: string;
  precision?: string;
  source?: string;
  license?: string;
  license_status?: string;
  verified?: boolean;
  historically_validated?: boolean;
  metadata?: {
    sha256?: string;
    installed?: boolean;
    local_discovery?: boolean;
    license_status?: string;
    vram_required_mib?: number;
    ram_required_mib?: number;
  };
  hardware_profile?: {
    id: string;
    gpu_name: string;
    profile_kind: string;
    vram_required_mib?: number;
    vram_recommended_mib?: number;
    ram_required_mib?: number;
    ram_recommended_mib?: number;
    tested?: boolean;
  };
};

export type ModelCenterModel = ModelCenterModelDeclared & ModelCenterModelObservation;

/** 运行时实例：原 owner 的真实探测结果。缺失即"没有实例"。 */
export type ModelCenterRuntimeInstance = {
  state?: ModelCenterRuntimeState;
  process_alive?: boolean;
  http_reachable?: boolean;
  loaded_models?: readonly string[];
  version?: string;
  safe_error_code?: string;
};

export type ModelCenterRuntimeDiscovery = { path_exists?: boolean; executable_exists?: boolean };

export type ModelCenterRuntime = {
  id: string;
  runtime_type?: ModelCenterRuntimeType;
  status?: string;
  management?: ModelCenterRuntimeManagement;
  capabilities: readonly ModelCenterCapability[];
  instance?: ModelCenterRuntimeInstance;
  discovery?: ModelCenterRuntimeDiscovery;
};

/**
 * `/api/model-center/runtimes/{id}/capabilities` 的只读投影：唯一能把
 * 声明能力变成"运行时真实探测到"的来源。`detected_at` 缺失即视为未知。
 */
export type ModelCenterRuntimeCapabilitySnapshot = {
  runtime_id: string;
  detected_at?: string;
  runtime_state?: string;
  capabilities: readonly string[];
  available_models?: readonly string[];
  node_classes?: readonly string[];
  warnings?: readonly string[];
};

export type ModelCenterCatalogPayload = {
  models: readonly ModelCenterModel[];
  runtimes: readonly ModelCenterRuntime[];
  capability_snapshots: readonly ModelCenterRuntimeCapabilitySnapshot[];
  /** 读取时被原 owner 按会话权限隐藏的模型数量（只计数，不含身份）。 */
  hidden_by_authority: number;
  sources: readonly ModelCenterSource[];
};

/** 项目存储的只读投影（`studio/storage`）。 */
export type ModelCenterStoragePayload = {
  assets: { count: number; bytes: number };
  trash: { count: number; bytes: number };
  limits: { asset_bytes: number; project_asset_bytes: number; project_assets: number };
  model_storage: 'EXTERNAL_READ_ONLY';
  cache_storage: 'SEPARATE_OWNER';
  export_storage: 'CLIENT_SELECTED_DOWNLOAD';
  physical_cleanup_available: false;
  admission?: {
    state: StorageAdmissionState;
    available_import_bytes: number | null;
    reserve_bytes: number;
    measurement: typeof STORAGE_MEASUREMENT;
    paths: Record<StoragePathOwner, string>;
    external_model_scan: false;
    automatic_cleanup: false;
    automatic_migration: false;
  };
};

/** 凭据只读状态：只有"存在与否"，没有值。 */
export type ModelCenterCredentialState = {
  provider: string;
  configured: boolean;
  backend?: ModelCenterVaultBackend;
  persistent?: boolean;
  degraded?: boolean;
  degraded_reason?: string;
  /** 过期只能来自 owner 的事实；没有该事实时保持未知。 */
  expired?: boolean;
};

/** 主机硬件事实（可选注入）。缺失即"未知"，不探测、不猜测。 */
export type ModelCenterHardwareFact =
  | { state: 'HOST_TOTAL_CAPACITY'; architecture?: string; ram_mib: number; vram_mib?: number; gpu_vendor?: string; source: 'HOST_INVENTORY' }
  | { state: 'UNKNOWN'; reason: string };

export type ModelCenterProjectContext = {
  /** 项目当前声明的模态需求；缺失即"未声明需求"。 */
  required_modalities?: readonly ModelCenterModality[];
  /** 项目风险档位等只读标签。 */
  labels?: readonly string[];
};

/* ------- 纯呈现类型（只描述界面形状，不新增任何 owner 事实） ------- */

export type CapabilityMatrixCell = {
  modality: ModelCenterModality;
  declared: boolean;
  verified: boolean;
  state: CapabilityMatrixState;
  /** 该格结论的来源说明；未知时说明缺哪个 owner 事实。 */
  evidence: string;
};

export type CapabilityMatrixRow = {
  model_id: string;
  display_name: string;
  declared_capabilities: readonly ModelCenterCapability[];
  verified_capabilities: readonly ModelCenterCapability[];
  cells: readonly CapabilityMatrixCell[];
  /** 声明被提升为已验证？恒为 `false`；这是可断言的机械保证。 */
  promoted_declared_to_verified: false;
  unknown_reason?: string;
};

export type CapabilityMatrix = {
  rows: readonly CapabilityMatrixRow[];
  modalities: readonly ModelCenterModality[];
  /** 运行时能力快照是否可用；不可用时全部按"声明但未验证"呈现。 */
  runtime_observation_available: boolean;
  sources: readonly ModelCenterSource[];
};

export type RoutingBlockerCode =
  | 'MODEL_STATUS_UNKNOWN' | 'MODEL_STATUS_NOT_READY' | 'API_PROVIDER_EXECUTION_NOT_ENABLED'
  | 'LICENSE_VALIDATION_REQUIRED' | 'RUNTIME_STATE_UNKNOWN' | 'RUNTIME_NOT_RUNNING'
  | 'RUNTIME_HTTP_UNREACHABLE' | 'CAPABILITY_NOT_DECLARED' | 'CAPABILITY_NOT_VERIFIED'
  | 'HOST_HARDWARE_UNKNOWN' | 'HOST_VRAM_INSUFFICIENT' | 'HOST_RAM_INSUFFICIENT'
  | 'PROVIDER_KEY_ABSENT' | 'PROVIDER_KEY_EXPIRED' | 'PROVIDER_KEY_UNKNOWN';

export type RoutingBlocker = {
  code: RoutingBlockerCode;
  /** 该事实来自哪个原 owner 字段，界面必须原样显示。 */
  owner_fact: string;
  detail: string;
};

export type RoutingExplanation = {
  model_id: string;
  display_name: string;
  verdict: RouteVerdict;
  blockers: readonly RoutingBlocker[];
  /** 逐项事实的原文取值（`null` = 原 owner 未提供）。 */
  availability: Readonly<Record<ProviderRuntimeAvailabilityFact, boolean>>;
  declared_capabilities: readonly ModelCenterCapability[];
  verified_capabilities: readonly ModelCenterCapability[];
  runtime_id?: string;
  /** 恒为 `false`：只读解释，永不调用模型。 */
  model_called: false;
  execution_authority: typeof API_PROVIDER_EXECUTION.execution_authority;
};

export type ReadinessNotice = {
  state: ModelCenterReadinessState;
  label: string;
  /** 为什么是这个状态；引用原 owner 的字段与取值。 */
  detail: string;
  /** 需要多少字节？原 owner 未提供时保持 `null`，绝不估算。 */
  required_bytes: number | null;
  /** 可用多少字节？来自准入事实，缺失即 `null`。 */
  available_bytes: number | null;
  /** 恒为 `false`：本函数是纯函数，从不启动下载或准备。 */
  starts_download: false;
  /** 恒为 `true`：界面只做说明。 */
  read_only: true;
};

export type StorageReport = {
  used_bytes: number;
  used_count: number;
  trash_bytes: number;
  trash_count: number;
  quota_bytes: number;
  quota_items: number;
  free_bytes: number | null;
  free_state: StorageAdmissionState | null;
  /** 恒为 `false`：原 owner 声明 `physical_cleanup_available: false`。 */
  physical_delete: false;
  /** 清理"会触及"的所有者标签（不是路径）。 */
  cleanup_would_touch: readonly StoragePathOwner[];
  /** 需要用户显式确认之后才可能发生的动作；当前为空。 */
  requires_explicit_user_confirmation: readonly string[];
  automatic_cleanup: false;
  automatic_migration: false;
  external_model_scan: false;
  /** 诚实声明：本界面没有任何可触发的磁盘动作。 */
  disk_actions_available: false;
  notices: readonly string[];
};

/**
 * 孤儿报告的可选只读证据行。原 owner 的 `studio/storage` 只回传聚合计数，
 * 因此调用方只有在原 owner 真正给出逐条记录时才注入它；缺失即"不可核对"。
 */
export type OrphanEvidenceRow = {
  asset_id?: string;
  label?: string;
  bytes?: number;
  reason_code: OrphanReasonCode;
};

export type OrphanCandidate = {
  /** 只有 owner 提供了身份时才存在；否则为 `null`（不编造 id）。 */
  asset_id: string | null;
  label: string;
  bytes: number | null;
  reason_code: OrphanReasonCode;
  reason: string;
  /** 恒为 `false`：候选只是报告，不代表可以删除。 */
  deletion_available: false;
};

export type OrphanReport = {
  available: boolean;
  candidates: readonly OrphanCandidate[];
  /** 为什么没有候选（或有候选但仍不可删）。 */
  detail: string;
  /** 恒为 `false` / `true`：只读报告。 */
  mutates: false;
  physical_delete: false;
  total_bytes: number | null;
};

export type SecretStateView = {
  provider: string;
  state: ModelCenterSecretState;
  label: string;
  backend?: ModelCenterVaultBackend;
  persistent?: boolean;
  degraded: boolean;
  degraded_reason?: string;
  /** 恒为 `null`：本模块从不持有、也从不渲染密钥值。 */
  secret_value: null;
  /** 恒为 `true`：只读。 */
  read_only: true;
};

export type CompatibilityGuidance = {
  model_id: string;
  project_id: string;
  compatible: boolean | null;
  headline: string;
  /** 每一条都带来源 owner 事实。 */
  details: readonly { owner_fact: string; text: string }[];
  downgrade_explanation: string | null;
  /** 恒为 `false`：不提供"仍然执行"的按钮语义。 */
  force_execution_available: false;
};

/* ------------------------------------------------------------------ 挂载契约 */

/**
 * 冻结的挂载属性。`active` 为假时永不读取；`denied` 时进入 DENIED 而不是 EMPTY；
 * 三个可选的 `unknown` 载荷是调用方（Lead）注入的**已经解码**的只读事实，
 * 缺失即未知。
 */
export type ModelCenterPanelProps = {
  projectId: string;
  transport: StudioGraphTransport;
  scope?: CollaborationContext['scope'];
  identity: string;
  active: boolean;
  denied: boolean;
  busy: boolean;
  isCurrent: () => boolean;
  read: <T>(w: () => Promise<T>) => Promise<T>;
  mutate: <T>(w: () => Promise<T>) => Promise<T>;
  catalog?: unknown;
  storage?: unknown;
  hardware?: unknown;
  onUnavailable?: () => void;
};
