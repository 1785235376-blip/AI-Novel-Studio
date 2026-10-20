import { checkedBailianPresets, type BailianPresetCatalog } from './bailianPresetContract';
/**
 * UX-07 只读客户端。
 *
 * 只走**已存在的端点**，且只走注入的 `StudioGraphTransport`（它已经携带捕获的
 * 会话/分支身份）：
 * - `GET /api/model-center/models`  —— 模型注册表读取（`app/model_center/api.py::models`）
 * - `GET /api/model-center/runtimes` —— 运行时状态读取（同文件 `runtimes`）
 * - `GET /api/model-center/runtimes/{id}/capabilities` —— 唯一能把声明证成观测的快照
 * - `GET /api/projects/{id}/studio/storage` —— 项目存储 + 准入
 * - `GET /api/credentials/{provider}` —— 只读凭据"存在与否"
 *
 * **没有**下载、准备、修复、清理、迁移、删除、启动、停止、配置写入、密钥读写。
 * 原 owner 没有这些端点，本客户端也不发明它们；`mutate` 在控制器里只用于
 * 统一的上层状态包装，从不包任何写操作。
 */

import { ApiError, type CollaborationContext } from '../api';
import type { StudioGraphTransport } from '../creative/studioGraphClient';
import {
  modelCenterCatalog, modelCenterCredential, modelCenterHardware, modelCenterRuntimeCapabilitySnapshot,
  modelCenterStorage,
} from './modelCenterContract';
import {
  MODEL_CENTER_BOUNDS, MODEL_CENTER_CODES,
  type ModelCenterCatalogPayload, type ModelCenterCredentialState, type ModelCenterHardwareFact,
  type ModelCenterRuntimeCapabilitySnapshot, type ModelCenterStoragePayload,
} from './modelCenterTypes';

export type ModelCenterSourceName = 'catalog' | 'storage';
export type ModelCenterSourceStatus =
  | { state: 'READY' } | { state: 'EMPTY' } | { state: 'UNAVAILABLE'; code: string }
  | { state: 'DENIED'; code: string } | { state: 'FAILED'; code: string };

/** 控制器读取一次的完整结果。每个来源各自成败，绝不互相掩盖。 */
export type ModelCenterReadResult = {
  catalog?: ModelCenterCatalogPayload;
  storage?: ModelCenterStoragePayload;
  credentials: readonly ModelCenterCredentialState[];
  status: { catalog: ModelCenterSourceStatus; storage: ModelCenterSourceStatus };
};

export type ModelCenterClient = {
  bailianPresets: (signal?: AbortSignal) => Promise<BailianPresetCatalog>;
  read: (signal?: AbortSignal) => Promise<ModelCenterReadResult>;
  /** 只读凭据状态；**不**改动任何密钥，也永不返回值。 */
  credential: (provider: string, signal?: AbortSignal) => Promise<ModelCenterCredentialState | undefined>;
  decodeHardware: (value: unknown) => ModelCenterHardwareFact;
};

function failure(error: unknown, deniedCode: string, failedCode: string): ModelCenterSourceStatus {
  if (error instanceof ApiError && (error.status === 401 || error.status === 403)) return { state: 'DENIED', code: deniedCode };
  if (error instanceof ApiError && error.status === 404) return { state: 'UNAVAILABLE', code: error.problem.code || failedCode };
  return { state: 'FAILED', code: error instanceof ApiError ? error.problem.code : failedCode };
}

/** 单个模型的失败不拖垮整个目录：能力快照缺失就是"没有观测证据"。 */
const SNAPSHOT_LIMIT = 12;

export function createModelCenterClient(
  projectId: string, transport: StudioGraphTransport, scope?: CollaborationContext['scope'],
): ModelCenterClient {
  if (typeof projectId !== 'string' || !projectId.trim() || projectId.length > MODEL_CENTER_BOUNDS.id) {
    throw new ApiError({ status: 400, code: MODEL_CENTER_CODES.catalogInvalid.code, message: MODEL_CENTER_CODES.catalogInvalid.message });
  }
  const capturedScope = scope ? { ...scope } : undefined;
  const storageUrl = `/api/projects/${encodeURIComponent(projectId)}/studio/storage`;
  const foreign = () => capturedScope !== undefined && capturedScope.projectId !== projectId;
  const rejected = () => new ApiError({
    status: 403, code: MODEL_CENTER_CODES.catalogScopeMismatch.code, message: MODEL_CENTER_CODES.catalogScopeMismatch.message,
  });

  function providerCandidates(catalog: ModelCenterCatalogPayload): string[] {
    const wanted = new Set<string>();
    for (const model of catalog.models) {
      if (model.source !== undefined && /^(CLOUD|API|REMOTE)$/.test(model.source)) wanted.add(model.runtime_type);
    }
    return [...wanted].slice(0, 8);
  }

  async function readCredentials(catalog: ModelCenterCatalogPayload, signal?: AbortSignal): Promise<ModelCenterCredentialState[]> {
    const providers = providerCandidates(catalog);
    const settled = await Promise.allSettled(providers.map(provider =>
      transport.json<unknown>(`/api/credentials/${encodeURIComponent(provider)}`, 'GET', undefined, signal)
        .then(value => modelCenterCredential(value, provider))));
    // 失败与越权回传都只表现为"没有该 provider 的事实"；越权响应本身仍然被拒绝，
    // 因此绝不会有一个被渲染的密钥值。
    return settled.flatMap(result => result.status === 'fulfilled' ? [result.value] : []);
  }

  return {
    decodeHardware: modelCenterHardware,
    bailianPresets: async (signal?: AbortSignal) => {
      if (foreign()) throw rejected();
      return checkedBailianPresets(await transport.json<unknown>('/api/model-center/provider-presets/bailian-text', 'GET', undefined, signal));
    },
    credential: async (provider: string, signal?: AbortSignal): Promise<ModelCenterCredentialState | undefined> => {
      if (typeof provider !== 'string' || !provider.trim() || provider.length > MODEL_CENTER_BOUNDS.id) return undefined;
      try {
        return modelCenterCredential(
          await transport.json<unknown>(`/api/credentials/${encodeURIComponent(provider)}`, 'GET', undefined, signal), provider);
      } catch { return undefined; }
    },
    read: async (signal?: AbortSignal): Promise<ModelCenterReadResult> => {
      if (foreign()) throw rejected();
      const runtimeFailure: { value?: ModelCenterSourceStatus } = {};
      const runtimeRead = transport.json<{ items?: unknown }>('/api/model-center/runtimes', 'GET', undefined, signal)
        .catch(reason => {
          runtimeFailure.value = failure(reason, MODEL_CENTER_CODES.readDenied.code, MODEL_CENTER_CODES.runtimeUnavailable.code);
          return { items: [] };
        });
      const storageRead = transport.json<unknown>(storageUrl, 'GET', undefined, signal)
        .then(value => ({ value })).catch(reason => ({ error: reason }));
      // 每个来源各自归位：`/models` 的拒绝只记录在 `modelsOutcome.error`，
      // 绝不会被别的来源的 `.catch()` 吞掉而伪装成"运行时段读失败"。
      const modelsOutcome: { value?: unknown; error?: unknown } = await transport
        .json<unknown>('/api/model-center/models', 'GET', undefined, signal)
        .then(value => ({ value })).catch(error => ({ error }));
      const runtimes = await runtimeRead;
      const storage = await storageRead;
      let catalog: ModelCenterCatalogPayload | undefined;
      let catalogStatus: ModelCenterSourceStatus;
      if (modelsOutcome.error !== undefined) {
        catalog = undefined;
        catalogStatus = failure(modelsOutcome.error, MODEL_CENTER_CODES.readDenied.code, MODEL_CENTER_CODES.catalogInvalid.code);
      } else if (runtimeFailure.value) {
        // 运行时段读失败时也去解码模型列表：模型自身的事实仍然可用，
        // 但每格能力都只能是"声明"，因为没有任何观测证据。
        try {
          catalog = modelCenterCatalog(modelsOutcome.value, { items: [] });
        } catch { catalog = undefined; }
        catalogStatus = runtimeFailure.value;
      } else {
        try {
          const base = modelCenterCatalog(modelsOutcome.value, { items: runtimes.items ?? [] });
          const snapshots: ModelCenterRuntimeCapabilitySnapshot[] = [];
          for (const runtime of base.runtimes.slice(0, SNAPSHOT_LIMIT)) {
            try {
              snapshots.push(modelCenterRuntimeCapabilitySnapshot(
                await transport.json<unknown>(`/api/model-center/runtimes/${encodeURIComponent(runtime.id)}/capabilities`, 'GET', undefined, signal),
                runtime.id));
            } catch { /* 没有快照 = 没有观测证据，绝不因此推断为已验证。 */ }
          }
          catalog = modelCenterCatalog(modelsOutcome.value, { items: runtimes.items ?? [] }, snapshots);
          catalogStatus = catalog.models.length ? { state: 'READY' } : { state: 'EMPTY' };
        } catch (reason) {
          catalog = undefined;
          catalogStatus = failure(reason, MODEL_CENTER_CODES.readDenied.code, MODEL_CENTER_CODES.catalogInvalid.code);
        }
      }
      let storageValue: ModelCenterStoragePayload | undefined;
      let storageStatus: ModelCenterSourceStatus;
      const storageOutcome = storage as { value?: unknown; error?: unknown };
      if (storageOutcome.error !== undefined) {
        storageStatus = failure(storageOutcome.error, MODEL_CENTER_CODES.readDenied.code, MODEL_CENTER_CODES.readFailed.code);
      } else {
        try {
          storageValue = modelCenterStorage(storageOutcome.value);
          storageStatus = { state: 'READY' };
        } catch (reason) {
          storageStatus = failure(reason, MODEL_CENTER_CODES.readDenied.code, MODEL_CENTER_CODES.storageInvalid.code);
        }
      }
      const credentials = catalog ? await readCredentials(catalog, signal) : [];
      return { catalog, storage: storageValue, credentials, status: { catalog: catalogStatus, storage: storageStatus } };
    },
  };
}
