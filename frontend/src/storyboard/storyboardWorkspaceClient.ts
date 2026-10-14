/**
 * UX-05 客户端：注入既有 `StudioGraphTransport`，只使用**既有**的分镜/文档端点。
 *
 * 真实绝对 URL 前缀与既有消费者一致（`creative/studioGraphClient.ts` 的
 * `videoStoryboard`、`creative/client.ts` 的 `base`）：
 *   GET /api/novels/{nid}/experimental/creative/documents/{rid}/storyboard
 *   GET /api/novels/{nid}/experimental/creative/documents/{rid}/director-advice
 *
 * 这里没有 approval / image-binding / video-binding / timeline-draft 的写入口：
 * 那四类写入仍然由原 `creative/studioStoryboardClient.ts` 与
 * `useStoryboardProductionController.ts` 负责。本客户端只读，并复用它们的解码器。
 */

import { ApiError, type CollaborationContext } from '../api';
import type { StudioGraphTransport } from '../creative/studioGraphClient';
import { workspaceDirectorAdvice, workspaceReceipt } from './storyboardWorkspaceContract';
import {
  STORYBOARD_WORKSPACE_BOUNDS, STORYBOARD_WORKSPACE_CAPACITY_CODES, STORYBOARD_WORKSPACE_ERROR_CODES,
  type StoryboardWorkspaceClient,
} from './storyboardWorkspaceTypes';

/** 原 owner / 传输层真实抛出的机器码 → 有界用户文案；未登记的码保留传输层文本。 */
const STORYBOARD_FAILURES: Record<string, string> = {
  CREATIVE_STORYBOARD_MODE_REQUIRED: '这份文档不是分镜文档，请打开原分镜文档。',
  CREATIVE_DIRECTOR_MODE_REQUIRED: '这份文档不是导演文档，无法读取导演调度建议。',
  CREATIVE_STORYBOARD_SHOT_CHANGED: '镜头在原文档里已经变化，本次读取作废。请重新读取原分镜。',
  CREATIVE_STORYBOARD_APPROVAL_CHANGED: '原分镜的批准记录与当前内容不一致。请在原分镜界面重新核对。',
  CREATIVE_STORYBOARD_IMAGE_BINDING_CHANGED: '已绑定的正式图片与镜头版本不一致。请读取原文档核对后再操作。',
  CREATIVE_STORYBOARD_VIDEO_BINDING_CHANGED: '已绑定的正式视频与镜头版本不一致。请读取原文档核对后再操作。',
  CREATIVE_STORYBOARD_VIDEO_SOURCE_CHANGED: '视频所依据的原分镜快照已变化。请在原生产界面重新核对来源。',
  CREATIVE_STORYBOARD_ASSET_OWNER_REQUIRED: '素材 owner 当前不可用，无法核对绑定素材。请稍后重试。',
  CREATIVE_STORYBOARD_TIMELINE_OWNER_REQUIRED: '时间线 owner 当前不可用。请稍后重试或在原模块操作。',
  CREATIVE_STORYBOARD_VIDEO_OWNER_REQUIRED: '视频 owner 当前不可用。请稍后重试或在原模块操作。',
  CREATIVE_SOURCE_DOCUMENT_CHANGED: '这份分镜记下的上游文档已经变化。请重新读取原文档核对。',
  CREATIVE_SOURCE_DOCUMENT_UNAVAILABLE: '这份分镜记下的上游文档当前读不到。请稍后重试。',
  CREATIVE_STORAGE_LOW_SPACE: '项目所在磁盘可用空间不足，本次读取未完成。请释放空间后重试。',
  CREATIVE_STORAGE_UNAVAILABLE: '暂时无法确认项目存储状态，本次读取未完成。',
  CREATIVE_AUTHORITY_INVALID: '当前会话无权读取这份内容。请重新核对身份与项目范围。',
  CREATIVE_AUTHORITY_CHANGED: '身份或项目范围已变化。请重新打开工作区。',
};
const CAPACITY_FAILURE = '项目存储空间不足或不可用，本次读取未完成。请释放空间或稍后重试。';

function refusal(reason: unknown): unknown {
  if (!(reason instanceof ApiError)) return reason;
  const problem = reason.problem;
  const message = STORYBOARD_FAILURES[problem.code]
    ?? (problem.status === 507 || STORYBOARD_WORKSPACE_CAPACITY_CODES.includes(problem.code)
      ? CAPACITY_FAILURE
      : problem.status === 404 ? '这份文档当前不可用，可能已被归档或不在当前分支。' : undefined);
  return message ? new ApiError({ ...problem, message }) : reason;
}

const segment = encodeURIComponent;

/**
 * 注入既有传输。构造时克隆身份：之后的导航不能把请求改指到别的项目。
 * `scope.projectId` 与 `projectId` 不同时，一开始就拒绝——不发请求。
 */
export function createStoryboardWorkspaceClient(
  projectId: string, transport: StudioGraphTransport, scope?: CollaborationContext['scope'],
): StoryboardWorkspaceClient {
  if (typeof projectId !== 'string' || !projectId.trim() || projectId.length > STORYBOARD_WORKSPACE_BOUNDS.identifier) {
    throw new ApiError({
      status: 200, code: STORYBOARD_WORKSPACE_ERROR_CODES.scopeMismatch,
      message: '分镜工作区缺少有效的项目标识，请重新打开工作区。',
    });
  }
  const capturedScope = scope ? { ...scope } : undefined;
  const base = `/api/novels/${segment(projectId)}/experimental/creative/documents`;
  const foreign = () => capturedScope !== undefined && capturedScope.projectId !== projectId;
  const documentId = (id: string): string => {
    if (typeof id !== 'string' || !id.trim() || id.length > STORYBOARD_WORKSPACE_BOUNDS.identifier) {
      throw new ApiError({
        status: 200, code: STORYBOARD_WORKSPACE_ERROR_CODES.responseInvalid,
        message: '分镜文档标识不可用，请重新读取原文档。',
      });
    }
    return segment(id);
  };
  const rejected = () => new ApiError({
    status: 403, code: STORYBOARD_WORKSPACE_ERROR_CODES.scopeMismatch,
    message: '分镜工作区与当前项目或分支不一致，请重新打开工作区。',
  });

  return {
    async readStoryboard(id: string, signal?: AbortSignal) {
      if (foreign()) throw rejected();
      const target = `${base}/${documentId(id)}/storyboard`;
      try {
        return workspaceReceipt(await transport.json<unknown>(target, 'GET', undefined, signal), id);
      } catch (reason) { throw refusal(reason); }
    },
    async readDirectorAdvice(id: string, signal?: AbortSignal) {
      if (foreign()) throw rejected();
      const target = `${base}/${documentId(id)}/director-advice`;
      try {
        return workspaceDirectorAdvice(await transport.json<unknown>(target, 'GET', undefined, signal), id);
      } catch (reason) { throw refusal(reason); }
    },
  };
}
