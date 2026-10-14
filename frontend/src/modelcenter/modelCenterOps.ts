/**
 * UX-07 纯函数层：所有结论都是给定事实的确定性函数。
 *
 * 这一层不做任何 I/O：不读取端点、不调用模型、不探测硬件、不下载、不删除、不移动、
 * 不接触密钥。每个返回值都带**来源 owner 事实**，因为界面的职责是把原 owner 的
 * 事实摆清楚，而不是替它下结论。
 *
 * 三条永不违反的机械保证（由 `modelCenterOps.test.ts` 逐条断言）：
 * - `capabilityMatrix().rows[*].promoted_declared_to_verified === false`：
 *   声明能力永远不会被提升为已验证能力。
 * - `readinessNotice().starts_download === false` 且 `read_only === true`：
 *   准备状态说明永不启动下载。
 * - `storageReport().physical_delete === false`、`orphanCandidates().mutates === false`：
 *   存储与孤儿报告永远是只读的。
 */

import { MODALITY_LABELS } from './CapabilityMatrix';
import {
  API_PROVIDER_EXECUTION, MODEL_CENTER_BOUNDS, MODEL_CENTER_MODALITIES, MODEL_CENTER_MODALITY_OF,
  MODEL_CENTER_READINESS_LABELS, ORPHAN_REASON_LABELS,
  type CapabilityMatrix, type CapabilityMatrixCell, type CapabilityMatrixRow,
  type CompatibilityGuidance, type ModelCenterCapability, type ModelCenterCatalogPayload,
  type ModelCenterCredentialState, type ModelCenterHardwareFact, type ModelCenterModel,
  type ModelCenterModality, type ModelCenterProjectContext, type ModelCenterRuntime,
  type ModelCenterRuntimeCapabilitySnapshot, type ModelCenterSecretState,
  type ModelCenterStoragePayload, type OrphanCandidate, type OrphanEvidenceRow, type OrphanReport,
  type OrphanReasonCode, type ReadinessNotice, type RouteVerdict, type RoutingBlocker,
  type RoutingBlockerCode, type RoutingExplanation, type SecretStateView, type StorageReport,
} from './modelCenterTypes';

/* ------------------------------------------------------------------ 小工具 */

const text = (value: string | undefined): string => value === undefined || value === '' ? '未提供' : value;
const mib = (value: number): string => `${value} MiB`;

/** 该模型在目录里对应的运行时：声明 `runtime_type` 与已注册运行时类型一致。 */
function runtimesFor(model: ModelCenterModel, catalog: ModelCenterCatalogPayload): readonly ModelCenterRuntime[] {
  return catalog.runtimes.filter(item => item.runtime_type === model.runtime_type);
}

function snapshotFor(runtimeId: string, catalog: ModelCenterCatalogPayload): ModelCenterRuntimeCapabilitySnapshot | undefined {
  return catalog.capability_snapshots.find(item => item.runtime_id === runtimeId);
}

/**
 * 一个能力是否被**真实观测**证实。必须同时满足两条 owner 事实：
 * - 原 owner 的校验投影 `model.verified === true`（当前指纹下仍然有效的校验记录），
 *   或 `hardware_profile.tested === true`（被测试过的档位）；
 * - 该模型对应运行时的 `capabilities` 快照真实列出了这个能力码。
 * 任一缺失即 `false`——声明绝不会被当作已验证。
 */
function capabilityVerified(model: ModelCenterModel, capability: ModelCenterCapability, runtime: ModelCenterRuntime | undefined, catalog: ModelCenterCatalogPayload): boolean {
  if (!runtime) return false;
  const snapshot = snapshotFor(runtime.id, catalog);
  if (!snapshot) return false;
  const observed = snapshot.capabilities.includes(capability);
  const ownerValidated = model.verified === true || model.hardware_profile?.tested === true;
  return observed && ownerValidated;
}

/* ------------------------------------------------------------------ 能力矩阵 */

export function capabilityMatrix(catalog: ModelCenterCatalogPayload): CapabilityMatrix {
  const runtimeObservationAvailable = catalog.capability_snapshots.length > 0;
  const rows: CapabilityMatrixRow[] = catalog.models.map(model => {
    const candidates = runtimesFor(model, catalog);
    const runtime = candidates.length === 1 ? candidates[0] : undefined;
    const verified = model.capabilities.filter(capability => capabilityVerified(model, capability, runtime, catalog));
    const cells: CapabilityMatrixCell[] = MODEL_CENTER_MODALITIES.map(modality => {
      const declaredForModality = model.capabilities.filter(capability => MODEL_CENTER_MODALITY_OF[capability] === modality);
      const verifiedForModality = verified.filter(capability => MODEL_CENTER_MODALITY_OF[capability] === modality);
      if (!declaredForModality.length) {
        return {
          modality, declared: false, verified: false, state: 'undeclared' as const,
          evidence: `model.capabilities 未声明 ${modality} 能力（原 owner 的 Capability 词表）`,
        };
      }
      if (verifiedForModality.length) {
        return {
          modality, declared: true, verified: true, state: 'verified' as const,
          evidence: `model.verified/hardware_profile.tested 且运行时 ${runtime?.id} 的 capabilities 快照列出 ${verifiedForModality.join('、')}`,
        };
      }
      return {
        modality, declared: true, verified: false, state: 'declared_only' as const,
        evidence: runtimeObservationAvailable && runtime
          ? `仅 model.capabilities 声明 ${declaredForModality.join('、')}；运行时 ${runtime.id} 的能力快照或原 owner 校验记录未证实`
          : `仅 model.capabilities 声明 ${declaredForModality.join('、')}；没有运行时能力快照，无法证实`,
      };
    });
    const row: CapabilityMatrixRow = {
      model_id: model.id, display_name: model.display_name,
      declared_capabilities: model.capabilities, verified_capabilities: verified,
      cells, promoted_declared_to_verified: false,
    };
    if (candidates.length > 1) row.unknown_reason = `状态与运行时 ${model.runtime_type} 匹配到 ${candidates.length} 个实例，原 owner 的 snapshot bridge 对这种情况 fail-closed，因此不做关联`;
    else if (!candidates.length) row.unknown_reason = `没有注册的 ${model.runtime_type} 运行时，无法把声明证成观测`;
    else if (!runtimeObservationAvailable) row.unknown_reason = '没有读取到任何运行时能力快照，全部按"声明但未验证"呈现';
    return row;
  });
  return {
    rows, modalities: MODEL_CENTER_MODALITIES,
    runtime_observation_available: runtimeObservationAvailable,
    sources: catalog.sources,
  };
}

/* ------------------------------------------------------------------ 路线解释 */

const BLOCKER_DETAIL: Readonly<Record<RoutingBlockerCode, (detail: string) => string>> = Object.freeze({
  MODEL_STATUS_UNKNOWN: value => `原 owner 未声明模型状态（model.status 缺失），不能当作 READY：${value}`,
  MODEL_STATUS_NOT_READY: value => `模型状态不是 READY：${value}；路由要求 model.status == READY`,
  API_PROVIDER_EXECUTION_NOT_ENABLED: value => `API Provider 执行未开启：${value}`,
  LICENSE_VALIDATION_REQUIRED: value => `许可仍是待验证状态：${value}`,
  RUNTIME_STATE_UNKNOWN: value => `运行时状态缺失：${value}`,
  RUNTIME_NOT_RUNNING: value => `运行时实例不在运行：${value}`,
  RUNTIME_HTTP_UNREACHABLE: value => `运行时不可连接：${value}`,
  CAPABILITY_NOT_DECLARED: value => `模型未声明所需模态：${value}`,
  CAPABILITY_NOT_VERIFIED: value => `所需模态只有声明、没有观测证据：${value}`,
  HOST_HARDWARE_UNKNOWN: value => `缺少主机硬件事实：${value}`,
  HOST_VRAM_INSUFFICIENT: value => `显存不足以满足模型档位要求：${value}`,
  HOST_RAM_INSUFFICIENT: value => `内存不足以满足模型档位要求：${value}`,
  PROVIDER_KEY_ABSENT: value => `Provider 密钥不存在：${value}`,
  PROVIDER_KEY_EXPIRED: value => `Provider 密钥已过期：${value}`,
  PROVIDER_KEY_UNKNOWN: value => `Provider 密钥状态未知：${value}`,
});

function blocker(code: RoutingBlockerCode, ownerFact: string, detail: string, unknown = false): RoutingBlocker & { unknown: boolean } {
  return { code, owner_fact: ownerFact, detail: BLOCKER_DETAIL[code](detail), unknown };
}

function requiredModalities(project: ModelCenterProjectContext | undefined): readonly ModelCenterModality[] {
  return project?.required_modalities ?? [];
}

/**
 * 说明某个模型为什么可选／不可选。**只读**：不调用模型、不改状态、不派发。
 *
 * 结论规则（保守、fail-closed）：
 * - 任何必需的 owner 事实缺失 → `UNKNOWN`，并把缺失项列进 `blockers`；
 * - 有任一确定性的阻塞事实 → `NOT_SELECTABLE`；
 * - 全部必需事实都存在且为真 → `SELECTABLE`，但仍然 `model_called: false`
 *   且执行权威仍是 `ORIGINAL_REVIEWED_REQUEST_REQUIRED`
 *   （`model_provider_contracts.py::ProviderAvailability.execution_available: Literal[False]`）。
 */
export function routingExplanation(
  catalog: ModelCenterCatalogPayload,
  modelId: string,
  hardware?: ModelCenterHardwareFact,
  credentials?: readonly ModelCenterCredentialState[],
  project?: ModelCenterProjectContext,
): RoutingExplanation | undefined {
  const model = catalog.models.find(item => item.id === modelId);
  if (!model) return undefined;
  const candidates = runtimesFor(model, catalog);
  const runtime = candidates.length === 1 ? candidates[0] : undefined;
  const instance = runtime?.instance;
  const blockers: (RoutingBlocker & { unknown: boolean })[] = [];

  if (model.status === undefined) {
    blockers.push(blocker('MODEL_STATUS_UNKNOWN', 'model.status', '字段缺失', true));
  } else if (model.status !== 'READY') {
    blockers.push(blocker('MODEL_STATUS_NOT_READY', 'model.status', model.status));
  }

  const licenseState = model.license_status ?? model.metadata?.license_status;
  if (model.status === 'LICENSE_REQUIRED' || (licenseState !== undefined && !/^(APPROVED|VALID|VALIDATED|VERIFIED)$/.test(licenseState))) {
    blockers.push(blocker('LICENSE_VALIDATION_REQUIRED', 'model.status / model.metadata.license_status',
      [model.status === 'LICENSE_REQUIRED' ? 'LICENSE_REQUIRED' : null, licenseState !== undefined ? `metadata.license_status=${licenseState}` : null]
        .filter(Boolean).join(' · ')));
  }

  if (candidates.length > 1) {
    blockers.push(blocker('RUNTIME_STATE_UNKNOWN', 'model_center.runtimes', `匹配到 ${candidates.length} 个 ${model.runtime_type} 运行时`, true));
  } else if (!runtime) {
    blockers.push(blocker('RUNTIME_STATE_UNKNOWN', 'model_center.runtimes', `没有注册的 ${model.runtime_type} 运行时`, true));
  } else if (!instance || instance.state === undefined) {
    blockers.push(blocker('RUNTIME_STATE_UNKNOWN', 'runtime.instance.state', `运行时 ${runtime.id} 没有实例记录`, true));
  } else if (instance.state === 'STOPPED' || instance.state === 'FAILED' || instance.state === 'DEGRADED') {
    blockers.push(blocker('RUNTIME_NOT_RUNNING', 'runtime.instance.state', `${runtime.id} = ${instance.state}`));
  } else if (instance.http_reachable !== true) {
    blockers.push(blocker('RUNTIME_HTTP_UNREACHABLE', 'runtime.instance.http_reachable', `${runtime.id} = ${String(instance.http_reachable)}`));
  }

  // 原 owner 的准入事实快照。`authorized` / `compatible` 抄自
  // `provider_runtime_v2_model_center_snapshot_bridge._availability`：该 bridge
  // 今天把这两项固定为 False（"没有当前 Host 事实能证明这一对 model/runtime 兼容"，
  // 而"缺少否定证据"不等于"肯定断言"）。因此这不是本模块的猜测，而是 owner 的事实，
  // 且它是一项**确定性阻塞**：七项准入合取式今天永远不可能为真。
  const availability = {
    configured: runtime?.status !== undefined && /^(CONFIGURED|READY|RUNNING)$/.test(runtime.status),
    installed: model.status === undefined ? false
      : ['READY', 'DEGRADED', 'DISABLED', 'INCOMPATIBLE'].includes(model.status),
    healthy: instance?.state === 'RUNNING',
    reachable: instance?.http_reachable === true,
    authorized: false,
    compatible: false,
  };
  if (!availability.authorized) {
    // bridge 把授权固定为 False 并不等于"这个模型被拒绝"，而是"没有授权权威来源"：
    // 因此这一项属于"事实缺失"，单凭它不应被渲染成一个确定的失败结论。
    blockers.push(blocker('RUNTIME_STATE_UNKNOWN', 'provider_runtime_v2_snapshot.availability.authorized', 'False（bridge 把授权固定为 False，没有权威来源）', true));
  }
  if (!availability.compatible) {
    blockers.push(blocker('CAPABILITY_NOT_VERIFIED', 'provider_runtime_v2_snapshot.availability.compatible', 'False（没有任何 Host 事实证明这一对 model/runtime 兼容）', true));
  }

  const required = requiredModalities(project);
  const declaredModalities = new Set(model.capabilities.map(capability => MODEL_CENTER_MODALITY_OF[capability]));
  for (const modality of required) {
    if (!declaredModalities.has(modality)) {
      blockers.push(blocker('CAPABILITY_NOT_DECLARED', 'model.capabilities', `项目需要 ${MODALITY_LABELS[modality]}（${modality}）`));
      continue;
    }
    if (runtime && !snapshotFor(runtime.id, catalog)) {
      blockers.push(blocker('CAPABILITY_NOT_VERIFIED', 'model_center.runtimes/{id}/capabilities', `${modality} 没有运行时能力快照`, true));
    } else if (runtime && !model.capabilities.some(capability =>
      MODEL_CENTER_MODALITY_OF[capability] === modality && capabilityVerified(model, capability, runtime, catalog))) {
      blockers.push(blocker('CAPABILITY_NOT_VERIFIED', 'model.verified / runtime capabilities', `${modality} 只有声明，没有观测证据`));
    }
  }

  const wantVram = model.hardware_profile?.vram_required_mib ?? model.metadata?.vram_required_mib;
  const wantRam = model.hardware_profile?.ram_required_mib ?? model.metadata?.ram_required_mib;
  if (wantVram !== undefined || wantRam !== undefined) {
    if (!hardware || hardware.state !== 'HOST_TOTAL_CAPACITY') {
      blockers.push(blocker('HOST_HARDWARE_UNKNOWN', 'host_hardware_inventory', '没有 HOST_TOTAL_CAPACITY 事实', true));
    } else {
      if (wantVram !== undefined) {
        if (hardware.vram_mib === undefined) {
          blockers.push(blocker('HOST_HARDWARE_UNKNOWN', 'serialize_host_hardware_snapshot.vram_mib', '显存事实缺失', true));
        } else if (hardware.vram_mib < wantVram) {
          blockers.push(blocker('HOST_VRAM_INSUFFICIENT', 'serialize_host_hardware_snapshot.vram_mib',
            `${mib(hardware.vram_mib)} < 档位要求 ${mib(wantVram)}`));
        }
      }
      if (wantRam !== undefined) {
        if (hardware.ram_mib < wantRam) {
          blockers.push(blocker('HOST_RAM_INSUFFICIENT', 'serialize_host_hardware_snapshot.ram_mib',
            `${mib(hardware.ram_mib)} < 档位要求 ${mib(wantRam)}`));
        }
      }
    }
  }

  // Provider 密钥只按"存在/不存在/过期/未知"参与判断，永不涉及值。
  const providerKey = credentials?.find(item => item.provider === model.runtime_type)
    ?? credentials?.find(item => item.provider === runtime?.id);
  if (model.source !== undefined && /^(CLOUD|API|REMOTE)$/.test(model.source)) {
    if (!providerKey) {
      blockers.push(blocker('PROVIDER_KEY_UNKNOWN', 'credential_vault.status', `${text(model.source)} 来源没有凭据状态`, true));
    } else if (providerKey.expired === true) {
      blockers.push(blocker('PROVIDER_KEY_EXPIRED', 'credential_vault.status', providerKey.provider));
    } else if (!providerKey.configured) {
      blockers.push(blocker('PROVIDER_KEY_ABSENT', 'credential_vault.status', providerKey.provider));
    }
  }

  const hard = blockers.filter(item => !item.unknown);
  const missing = blockers.some(item => item.unknown);
  // 只要存在任何**确定性**的阻塞事实（状态不足、许可未验证、运行时未运行、
  // 显存不足、密钥不存在，或 owner 的 authorized/compatible 固定为 False），
  // 结论就是 NOT_SELECTABLE；只有在阻塞项全部是"事实缺失"时才是 UNKNOWN。
  const finalVerdict: RouteVerdict = hard.length ? 'NOT_SELECTABLE' : (missing ? 'UNKNOWN' : 'SELECTABLE');
  const publicBlockers: RoutingBlocker[] = blockers.map(({ code, owner_fact, detail }) => ({ code, owner_fact, detail }));
  return {
    model_id: model.id, display_name: model.display_name, verdict: finalVerdict, blockers: publicBlockers,
    availability, declared_capabilities: model.capabilities,
    verified_capabilities: model.capabilities.filter(capability => capabilityVerified(model, capability, runtime, catalog)),
    ...(runtime ? { runtime_id: runtime.id } : {}),
    model_called: false,
    execution_authority: API_PROVIDER_EXECUTION.execution_authority,
  };
}

/* ------------------------------------------------------------------ 准备状态 */

/**
 * 下载/准备/修复状态的说明。**纯函数，永不启动下载、准备或修复**：
 * `starts_download` 恒为 `false`，`read_only` 恒为 `true`。
 * 原 owner 没有下载端点，所以界面只能说明状态，不能推进状态。
 */
export function readinessNotice(model: ModelCenterModel, hardware?: ModelCenterHardwareFact, admission?: ModelCenterStoragePayload['admission']): ReadinessNotice {
  const requiredBytes = model.metadata?.vram_required_mib !== undefined ? model.metadata.vram_required_mib * 1024 * 1024
    : model.hardware_profile?.vram_required_mib !== undefined ? model.hardware_profile.vram_required_mib * 1024 * 1024
      : model.hardware_profile?.ram_required_mib !== undefined ? model.hardware_profile.ram_required_mib * 1024 * 1024 : null;
  const availableBytes = admission && admission.state !== 'UNAVAILABLE' ? admission.available_import_bytes : null;
  const shared = {
    required_bytes: requiredBytes, available_bytes: availableBytes,
    starts_download: false as const, read_only: true as const,
  };
  const status = model.status;
  if (status === undefined) {
    return { state: 'UNKNOWN', label: MODEL_CENTER_READINESS_LABELS.UNKNOWN, ...shared,
      detail: '原 owner 未声明 model.status，无法判断下载或准备状态；不做猜测。' };
  }
  switch (status) {
    case 'NOT_FOUND':
      return { state: 'NOT_DOWNLOADED', label: MODEL_CENTER_READINESS_LABELS.NOT_DOWNLOADED, ...shared,
        detail: 'model.status = NOT_FOUND：原 owner 没有找到该模型的任何文件记录。本界面不提供下载。' };
    case 'NOT_INSTALLED':
      return { state: 'NOT_DOWNLOADED', label: MODEL_CENTER_READINESS_LABELS.NOT_DOWNLOADED, ...shared,
        detail: `model.status = NOT_INSTALLED：${model.metadata?.installed === true ? 'metadata.installed=true 与状态冲突，以状态为准。' : '未安装。'}本界面不提供下载。` };
    case 'DISCOVERED':
      return { state: 'NOT_DOWNLOADED', label: MODEL_CENTER_READINESS_LABELS.NOT_DOWNLOADED, ...shared,
        detail: 'model.status = DISCOVERED：只被发现，尚未安装或校验。本界面不提供准备操作。' };
    case 'VALIDATING':
      return { state: 'PREPARING', label: MODEL_CENTER_READINESS_LABELS.PREPARING, ...shared,
        detail: 'model.status = VALIDATING：原 owner 正在校验。界面只显示进度事实，不重试、不推进。' };
    case 'VALIDATION_REQUIRED':
      return { state: 'PREPARING', label: MODEL_CENTER_READINESS_LABELS.PREPARING, ...shared,
        detail: 'model.status = VALIDATION_REQUIRED：等待原 owner 的校验记录。界面不自动触发校验。' };
    case 'READY':
      if (hardware?.state === 'HOST_TOTAL_CAPACITY' && requiredBytes !== null
        && (hardware.vram_mib ?? 0) * 1024 * 1024 < requiredBytes && model.hardware_profile?.vram_required_mib !== undefined) {
        return { state: 'READY', label: MODEL_CENTER_READINESS_LABELS.READY, ...shared,
          detail: `model.status = READY，但当前主机总显存 ${mib(hardware.vram_mib ?? 0)} 低于档位要求 ${mib(model.hardware_profile.vram_required_mib)}：文件已就绪，适配性未知（原 owner 的 gpu_fit_verified 恒为 false）。` };
      }
      return { state: 'READY', label: MODEL_CENTER_READINESS_LABELS.READY, ...shared,
        detail: 'model.status = READY：原 owner 声明已就绪。这不代表适配已核实（gpu_fit_verified 恒为 false）。' };
    case 'DEGRADED':
      return { state: 'READY', label: MODEL_CENTER_READINESS_LABELS.READY, ...shared,
        detail: 'model.status = DEGRADED：已安装但被原 owner 标记为降级。可用性以运行时事实为准。' };
    case 'DISABLED':
      return { state: 'READY', label: MODEL_CENTER_READINESS_LABELS.READY, ...shared,
        detail: 'model.status = DISABLED：文件已安装，但原 owner 已停用。界面不重新启用。' };
    case 'MISSING_COMPONENT':
    case 'INCOMPATIBLE':
      return { state: 'FAILED', label: MODEL_CENTER_READINESS_LABELS.FAILED, ...shared,
        detail: `model.status = ${status}：原 owner 判定为缺失/不兼容。界面不提供修复操作。` };
    case 'LICENSE_REQUIRED':
      return { state: 'FAILED', label: MODEL_CENTER_READINESS_LABELS.FAILED, ...shared,
        detail: `model.status = LICENSE_REQUIRED：许可待验证（metadata.license_status=${text(model.metadata?.license_status ?? model.license_status)}）。界面不代替用户接受许可。` };
    case 'RUNTIME_REQUIRED':
      return { state: 'FAILED', label: MODEL_CENTER_READINESS_LABELS.FAILED, ...shared,
        detail: 'model.status = RUNTIME_REQUIRED：缺少所需运行时。界面不启动运行时。' };
    default:
      return { state: 'UNKNOWN', label: MODEL_CENTER_READINESS_LABELS.UNKNOWN, ...shared,
        detail: `model.status = ${String(status)} 不在原 owner 的 ModelStatus 词表内，按未知处理。` };
  }
}

/* ------------------------------------------------------------------ 存储 */

/**
 * 存储报告。**只读**，并且对"不可逆动作"说实话：
 * `physical_delete` 恒为 `false`（抄自 `physical_cleanup_available: false`），
 * `disk_actions_available` 恒为 `false`，清理"会触及"的只是符号所有者标签。
 */
export function storageReport(storage: ModelCenterStoragePayload | undefined): StorageReport {
  if (!storage) {
    return {
      used_bytes: 0, used_count: 0, trash_bytes: 0, trash_count: 0,
      quota_bytes: 0, quota_items: 0, free_bytes: null, free_state: null,
      physical_delete: false, cleanup_would_touch: [], requires_explicit_user_confirmation: [],
      automatic_cleanup: false, automatic_migration: false, external_model_scan: false,
      disk_actions_available: false,
      notices: ['没有读取到项目存储投影：用量与配额保持未知，不当作 0 显示为"充足"。'],
    };
  }
  const admission = storage.admission;
  const usedBytes = storage.assets.bytes + storage.trash.bytes;
  const notices: string[] = [];
  if (admission === undefined) {
    notices.push('原 owner 未回传 admission：可用空间未知，零容量与"无法测量"不可互换。');
  } else if (admission.state === 'UNAVAILABLE') {
    notices.push('admission.state = UNAVAILABLE：原 owner 无法测量可用空间（assets 文件系统不可访问）。');
  } else if (admission.state === 'LOW_SPACE_OR_QUOTA' && admission.available_import_bytes === 0) {
    notices.push('admission.state = LOW_SPACE_OR_QUOTA 且 available_import_bytes = 0：当前不能导入任何新资产。');
  } else {
    notices.push(`admission.available_import_bytes = ${admission.available_import_bytes} 字节（已扣除 reserve_bytes = ${admission.reserve_bytes}）。`);
  }
  notices.push('清理会触及的所有者：项目资产库、缓存、导出目录均由各自原 owner 持有；模型目录只被引用（MODEL_CENTER_REFERENCES_ONLY），本界面不扫描也不改动。');
  return {
    used_bytes: usedBytes, used_count: storage.assets.count + storage.trash.count,
    trash_bytes: storage.trash.bytes, trash_count: storage.trash.count,
    quota_bytes: storage.limits.project_asset_bytes, quota_items: storage.limits.project_assets,
    free_bytes: admission && admission.state !== 'UNAVAILABLE' ? admission.available_import_bytes : null,
    free_state: admission?.state ?? null,
    physical_delete: false,
    cleanup_would_touch: ['assets', 'cache', 'exports'],
    requires_explicit_user_confirmation: [],
    automatic_cleanup: false, automatic_migration: false, external_model_scan: false,
    disk_actions_available: false, notices,
  };
}

/* ------------------------------------------------------------------ 孤儿候选 */

const REASON_CODES: readonly OrphanReasonCode[] = ['SOFT_DELETED_ASSET', 'SUPERSEDED_REVISION', 'NO_OWNER_RECORD'];

/**
 * 孤儿候选的**只读报告**。永不删除、永不移动、永不清理。
 *
 * 事实边界：原 owner 的 `studio/storage` 投影只有 `trash.count` / `trash.bytes`
 * 这类聚合计数，没有逐条删除记录。因此没有显式行时，报告明确说"不可核对"
 * （`available: false`），而不是按字节数编造候选身份。
 */
export function orphanCandidates(rows: readonly OrphanEvidenceRow[] | undefined, storage?: ModelCenterStoragePayload): OrphanReport {
  if (!rows || rows.length === 0) {
    const trashBytes = storage?.trash.bytes ?? null;
    const trashCount = storage?.trash.count ?? null;
    return {
      available: false, candidates: [], mutates: false, physical_delete: false, total_bytes: null,
      detail: trashCount === null
        ? '原 owner 的只读投影未提供逐条删除记录，也无法读取 trash 计数，无法产生孤儿候选。'
        : `原 owner 的只读投影只有聚合计数（trash.count = ${trashCount}，trash.bytes = ${String(trashBytes)}），没有逐条删除记录：无法核对身份，因此不产生候选。`,
    };
  }
  const candidates: OrphanCandidate[] = [];
  const seen = new Set<string>();
  for (const row of rows) {
    if (!REASON_CODES.includes(row.reason_code)) {
      return {
        available: false, candidates: [], mutates: false, physical_delete: false, total_bytes: null,
        detail: `只读投影里出现了未知的 reason_code（${String(row.reason_code)}），按不可核对处理，不产生候选。`,
      };
    }
    const key = row.asset_id ?? `${row.reason_code}:${row.label}`;
    if (seen.has(key)) continue;
    seen.add(key);
    const bytes = typeof row.bytes === 'number' && Number.isSafeInteger(row.bytes) && row.bytes >= 0 ? row.bytes : null;
    candidates.push({
      asset_id: typeof row.asset_id === 'string' && row.asset_id.trim() && row.asset_id.length <= MODEL_CENTER_BOUNDS.id ? row.asset_id : null,
      label: typeof row.label === 'string' && row.label.trim() ? row.label.slice(0, MODEL_CENTER_BOUNDS.label) : '未命名记录',
      bytes, reason_code: row.reason_code, reason: ORPHAN_REASON_LABELS[row.reason_code], deletion_available: false,
    });
  }
  const known = candidates.map(item => item.bytes).filter((value): value is number => value !== null);
  return {
    available: true, candidates, mutates: false, physical_delete: false,
    total_bytes: known.length === candidates.length ? known.reduce((sum, value) => sum + value, 0) : null,
    detail: `只读候选 ${candidates.length} 条。原 owner 声明 physical_cleanup_available = false，因此这里没有任何删除或移动动作。`,
  };
}

/* ------------------------------------------------------------------ 凭据 */

/**
 * 只报告凭据的"存在与否"。`secret_value` 恒为 `null`：本模块从不持有、
 * 从不渲染、也从不转发密钥值。`expired` 只能来自 owner 自己的事实。
 */
export function secretState(credential: ModelCenterCredentialState | undefined): SecretStateView {
  if (!credential) {
    return {
      provider: '未读取', state: 'UNKNOWN', label: '未知', degraded: false, secret_value: null, read_only: true,
    };
  }
  const state: ModelCenterSecretState = credential.expired === true ? 'EXPIRED' : credential.configured ? 'PRESENT' : 'ABSENT';
  const label = state === 'PRESENT' ? '存在' : state === 'ABSENT' ? '不存在' : state === 'EXPIRED' ? '已过期' : '未知';
  return {
    provider: credential.provider, state, label,
    ...(credential.backend !== undefined ? { backend: credential.backend } : {}),
    ...(credential.persistent !== undefined ? { persistent: credential.persistent } : {}),
    degraded: credential.degraded === true,
    ...(credential.degraded_reason !== undefined ? { degraded_reason: credential.degraded_reason } : {}),
    secret_value: null, read_only: true,
  };
}

/* ------------------------------------------------------------------ 兼容性说明 */

/**
 * 用中文说明"为什么这个模型不能满足这个项目"，每一条都带来源 owner 事实。
 * 不提供"强制执行"这类语义：`force_execution_available` 恒为 `false`。
 */
export function compatibilityGuidance(
  model: ModelCenterModel, project: ModelCenterProjectContext | undefined,
  catalog: ModelCenterCatalogPayload, hardware?: ModelCenterHardwareFact,
): CompatibilityGuidance {
  const details: { owner_fact: string; text: string }[] = [];
  const required = requiredModalities(project);
  const declared = new Set(model.capabilities.map(capability => MODEL_CENTER_MODALITY_OF[capability]));
  const missing = required.filter(modality => !declared.has(modality));
  for (const modality of required) {
    if (declared.has(modality)) details.push({ owner_fact: 'model.capabilities', text: `声明支持项目需要的 ${modality}。` });
    else details.push({ owner_fact: 'model.capabilities', text: `未声明项目需要的 ${modality}，该模态的节点不能路由到此模型。` });
  }
  const requiredSet = new Set(required);
  const extra = model.capabilities.filter(capability => !requiredSet.has(MODEL_CENTER_MODALITY_OF[capability]));
  if (required.length && extra.length) {
    details.push({ owner_fact: 'model.capabilities', text: `该模型额外声明了 ${extra.join('、')}：本项目当前不需要，但也不构成阻塞。` });
  }
  const wantVram = model.hardware_profile?.vram_required_mib ?? model.metadata?.vram_required_mib;
  if (hardware?.state === 'HOST_TOTAL_CAPACITY') {
    if (wantVram !== undefined && hardware.vram_mib !== undefined) {
      details.push({ owner_fact: 'host_hardware_inventory.vram_mib', text: hardware.vram_mib < wantVram
        ? `主机总显存 ${mib(hardware.vram_mib)} 低于该档位要求 ${mib(wantVram)}：可以保留文件，但不应指望它达到宣称速度。`
        : `主机总显存 ${mib(hardware.vram_mib)} 满足该档位要求 ${mib(wantVram)}（仍不是实测适配：gpu_fit_verified 恒为 false）。` });
    } else if (wantVram !== undefined) {
      details.push({ owner_fact: 'host_hardware_inventory.vram_mib', text: '该模型声明了显存档位，但主机显存事实缺失：不做结论。' });
    }
  } else if (wantVram !== undefined) {
    details.push({ owner_fact: 'host_hardware_inventory', text: '没有主机硬件事实，无法比较档位要求；按未知处理。' });
  }
  const degraded = model.status === 'DEGRADED' || model.status === 'DISABLED' || model.status === 'INCOMPATIBLE' || model.status === 'MISSING_COMPONENT';
  const downgrade = degraded
    ? `这不是"兼容性下降"的推断，而是原 owner 的状态：model.status = ${model.status}。文件可能仍在，但不应作为默认路线。`
    : null;
  const compatible = missing.length ? false : (model.status === undefined || !required.length) ? null : !degraded;
  const headline = missing.length
    ? `不满足项目需求：缺少 ${missing.map(modality => `${MODALITY_LABELS[modality]}（${modality}）`).join('、')}。`
    : downgrade ?? '没有发现声明层面的不兼容；适配仍需原 owner 的校验记录（NOT_RUN）。';
  return {
    model_id: model.id, project_id: project?.labels?.[0] ?? 'current', compatible, headline, details,
    downgrade_explanation: downgrade, force_execution_available: false,
  };
}
