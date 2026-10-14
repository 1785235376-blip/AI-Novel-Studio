import { ApiError, type CollaborationContext } from '../api';
import type { StudioGraphTransport } from '../creative/studioGraphClient';
import { assetBrowserAsset, assetBrowserList, assetBrowserReadTarget, assetBrowserRelationships } from './assetBrowserContract';
import {
  ASSET_BROWSER_BOUNDS, ASSET_BROWSER_ERROR_CODES,
  type AssetBrowserAsset, type AssetBrowserClient, type AssetBrowserRelationshipGraph,
} from './assetBrowserTypes';

/**
 * UX-03 客户端：注入既有 Studio 传输（形状同 `productionWorkflowClient.ts` /
 * `taskCenterClient.ts`）。它只有三个**只读**端点，正是既有 owner 的原样入口：
 *
 *   GET /api/projects/{nid}/studio/assets                        → listAssets
 *   GET /api/projects/{nid}/studio/assets/{aid}                  → readAsset
 *   GET /api/projects/{nid}/studio/relationships                 → readRelationships
 *
 * 这三条路径与 `frontend/src/creative/studioClient.ts` 的 `assets()` / `asset()` /
 * `relationships()` 完全一致（`studioClient.ts` 的 `base` 是
 * `/api/projects/{projectId}/studio`），因此这里是同一个 owner 的同一个投影，
 * 不是第二个资产 / 关系服务。本客户端**不**包含任何写操作、执行、下载、扫描或
 * 凭据查询。
 *
 * 错误映射只覆盖 owner 自己会抛的码与传输层已经写死的中文文案；未登记的码保留
 * 传输层文本，绝不把服务端正文渲染给用户。
 */

const segment = encodeURIComponent;

/**
 * 原 owner / 传输层真实抛出的机器码 → 有界的用户文案。
 * （`workspace_api.py::invoke()` / `access()` 与 `studioClient.ts::response()`。）
 */
const ASSET_BROWSER_FAILURES: Record<string, string> = {
  [ASSET_BROWSER_ERROR_CODES.authorityInvalid]: '当前会话身份不可用，素材库未读取。请重新核对身份与项目范围。',
  [ASSET_BROWSER_ERROR_CODES.authorityChanged]: '身份或项目范围已经变化，素材库未读取。请重新打开工作区。',
  [ASSET_BROWSER_ERROR_CODES.storageLowSpace]: '素材库所在磁盘可用空间不足，本次读取未完成。请释放空间后重试。',
  [ASSET_BROWSER_ERROR_CODES.storageUnavailable]: '暂时无法确认素材库存储状态，本次读取未完成。',
  [ASSET_BROWSER_ERROR_CODES.assetInUse]: '此素材仍被其他内容引用，删除未执行。请先处理引用关系。',
  [ASSET_BROWSER_ERROR_CODES.assetVersionInvalid]: '此素材的版本号不可用，请重新读取素材库。',
  [ASSET_BROWSER_ERROR_CODES.studioScopeMismatch]: '返回内容与当前项目或分支不一致，请重新读取。',
  [ASSET_BROWSER_ERROR_CODES.studioResponseInvalid]: '服务返回的素材数据不可用，请重新读取。',
};

/**
 * 状态码兜底。刻意把 401/403 与 404 分开：**拒绝读取不是空素材库**，
 * **记录不存在也不是空素材库**。
 */
function byStatus(status: number): string | undefined {
  if (status === 401 || status === 403) return '当前会话无权读取此素材库。这不是"暂无素材"，请重新核对身份与分支。';
  if (status === 404) return '此素材或素材库当前不可用（记录不存在，或功能尚未启用）。这不是"暂无素材"。';
  if (status === 409) return '素材版本或来源已经变化，请重新读取后再核对。';
  if (status === 507) return '素材库存储空间不足或不可用，本次读取未完成。请释放空间或稍后重试。';
  if (status === 413) return '请求内容超出服务端上限，本次读取未完成。';
  return undefined;
}

function refusal(reason: unknown): unknown {
  if (!(reason instanceof ApiError)) return reason;
  const problem = reason.problem;
  const message = ASSET_BROWSER_FAILURES[problem.code] ?? byStatus(problem.status);
  return message ? new ApiError({ ...problem, message }) : reason;
}

/**
 * 本地拒绝：请求在离开客户端之前就被有界校验挡住，并使用自己的稳定机器码。
 * 同时把传输层/解码器的异常统一收口，绝不让原始文本泄漏出去。
 */
async function read<T>(run: () => Promise<T>, local: () => void): Promise<T> {
  local();
  try {
    return await run();
  } catch (reason) {
    throw refusal(reason);
  }
}

export function createAssetBrowserClient(
  projectId: string, transport: StudioGraphTransport, scope?: CollaborationContext['scope'],
): AssetBrowserClient {
  // 构造时克隆范围；之后的任何导航都不能把请求改指到别的项目。
  const capturedScope = scope ? { ...scope } : undefined;
  const base = `/api/projects/${segment(projectId)}/studio`;
  const foreign = () => capturedScope !== undefined && capturedScope.projectId !== projectId;
  const rejected = (): never => {
    throw new ApiError({
      status: 403, code: ASSET_BROWSER_ERROR_CODES.scopeMismatch,
      message: '素材浏览器与当前项目或分支不一致，请重新打开。',
    });
  };
  const local = () => {
    if (foreign()) rejected();
    assetBrowserReadTarget(projectId);
    if (!transport || typeof transport.json !== 'function') rejected();
  };

  return {
    async listAssets(signal?: AbortSignal): Promise<AssetBrowserAsset[]> {
      return read(() => transport.json<unknown>(`${base}/assets`, 'GET', undefined, signal)
        .then(value => assetBrowserList(value, projectId)), local);
    },
    async readAsset(assetIdValue: string, signal?: AbortSignal): Promise<AssetBrowserAsset> {
      // 资产标识在有界校验通过之前不会进入 URL；拒绝使用同一个机器码收口。
      try {
        return read(() => {
          const target = assetBrowserReadTarget(projectId, assetIdValue).asset_id as string;
          return transport.json<unknown>(`${base}/assets/${segment(target)}`, 'GET', undefined, signal)
            .then(value => assetBrowserAsset(value, projectId));
        }, local);
      } catch (reason) {
        throw refusal(reason);
      }
    },
    async readRelationships(signal?: AbortSignal): Promise<AssetBrowserRelationshipGraph> {
      return read(() => transport.json<unknown>(`${base}/relationships`, 'GET', undefined, signal)
        .then(assetBrowserRelationships), local);
    },
    /**
     * 按需读取一个资产的原始字节（缩略图 / 预览）。走既有 owner 的同一个下载入口：
     * 绝不预取整库，也绝不因为调用方想显示缩略图就放宽授权。
     */
    async downloadAsset(assetIdValue: string, _signal?: AbortSignal): Promise<Blob> {
      // 先做本地标识校验（形状问题不该被伪装成"传输不支持"）。
      try {
        assetBrowserReadTarget(projectId, assetIdValue);
      } catch (reason) {
        throw refusal(reason);
      }
      if (typeof transport.blob !== 'function') {
        throw new ApiError({
          status: 0, code: ASSET_BROWSER_ERROR_CODES.studioResponseInvalid,
          message: '当前传输不支持按需读取素材内容，缩略图与预览不可用。',
        });
      }
      try {
        return await read(() => {
          const target = assetBrowserReadTarget(projectId, assetIdValue).asset_id as string;
          // `StudioGraphTransport.blob` 只接受 URL（与既有传输形状一致）。
          return transport.blob!(`${base}/assets/${segment(target)}/download`);
        }, local);
      } catch (reason) {
        throw refusal(reason);
      }
    },
  };
}

/** 客户端只读的有界事实，供界面文案复用（不做任何请求）。 */
export const ASSET_BROWSER_CLIENT_FACTS = Object.freeze({
  read_only: true,
  endpoints: Object.freeze({
    list: 'GET /api/projects/{nid}/studio/assets',
    detail: 'GET /api/projects/{nid}/studio/assets/{aid}',
    relationships: 'GET /api/projects/{nid}/studio/relationships',
  }),
  /** 一次读取最多接受的行数（超出即拒绝，不静默截断）。 */
  list_limit: ASSET_BROWSER_BOUNDS.list_items,
  /** 从不下载内容、从不扫描磁盘、从不执行任务。 */
  downloads_content: false,
  scans_disk: false,
  executes_work: false,
} as const);
