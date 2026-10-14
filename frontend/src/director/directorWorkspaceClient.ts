/**
 * Phase14-A 只读客户端。
 *
 * 只用**一个新**的只读端点：
 *   GET /api/projects/{nid}/studio/director/workspace/{rid}
 *
 * 这里没有导演意图写入、没有镜头写入、没有连续性修正：`visual_target` /
 * `director_notes` 的 authoring 仍然走既有 owner 的文档更新端点，本客户端不碰它。
 */

import { ApiError, type CollaborationContext } from '../api';
import type { StudioGraphTransport } from '../creative/studioGraphClient';
import { directorWorkspaceProjection } from './directorWorkspaceContract';
import {
  DIRECTOR_WORKSPACE_BOUNDS, DIRECTOR_WORKSPACE_ERROR_CODES, type DirectorWorkspaceClient,
} from './directorWorkspaceTypes';

/** 原 owner / 传输层真实抛出的机器码 → 有界用户文案；未登记的码保留传输层文本。 */
const DIRECTOR_FAILURES: Record<string, string> = {
  EXPERIMENTAL_NOT_FOUND: '这份文档当前不可用，可能已被归档或不在当前分支。',
  EXPERIMENTAL_SOURCE_STALE: '这份文档记录的上游来源已经变化。请重新读取原文档核对。',
  CREATIVE_PROJECT_CHANGED: '项目实例已变化，本次读取作废。请重新打开工作区。',
  CREATIVE_SCOPE_CHANGED: '项目范围已变化，本次读取作废。请重新打开工作区。',
  CREATIVE_AUTHORITY_INVALID: '当前会话无权读取这份内容。请重新核对身份与项目范围。',
  CREATIVE_AUTHORITY_CHANGED: '身份或项目范围已变化。请重新打开工作区。',
};

function refusal(reason: unknown): unknown {
  if (!(reason instanceof ApiError)) return reason;
  const problem = reason.problem;
  const message = DIRECTOR_FAILURES[problem.code]
    ?? (problem.status === 404 ? '这份文档当前不可用，可能已被归档或不在当前分支。' : undefined);
  return message ? new ApiError({ ...problem, message }) : reason;
}

const segment = encodeURIComponent;

/** 注入既有传输。构造时克隆身份：之后的导航不能把请求改指到别的项目。 */
export function createDirectorWorkspaceClient(
  projectId: string, transport: StudioGraphTransport, scope?: CollaborationContext['scope'],
): DirectorWorkspaceClient {
  if (typeof projectId !== 'string' || !projectId.trim() || projectId.length > DIRECTOR_WORKSPACE_BOUNDS.identifier) {
    throw new ApiError({
      status: 200, code: DIRECTOR_WORKSPACE_ERROR_CODES.documentRequired,
      message: '导演工作台缺少有效的项目标识，请重新打开工作区。',
    });
  }
  const capturedScope = scope ? { ...scope } : undefined;
  const base = `/api/projects/${segment(projectId)}/studio/director/workspace`;
  const foreign = () => capturedScope !== undefined && capturedScope.projectId !== projectId;
  const rejected = () => new ApiError({
    status: 403, code: DIRECTOR_WORKSPACE_ERROR_CODES.scopeMismatch,
    message: '导演工作台与当前项目或分支不一致，请重新打开工作区。',
  });

  return {
    async readDirectorWorkspace(documentId: string, signal?: AbortSignal) {
      if (foreign()) throw rejected();
      if (typeof documentId !== 'string' || !documentId.trim()
          || documentId.length > DIRECTOR_WORKSPACE_BOUNDS.identifier) {
        throw new ApiError({
          status: 200, code: DIRECTOR_WORKSPACE_ERROR_CODES.documentRequired,
          message: '导演工作台尚未选定文档，请先打开一份导演或分镜文档。',
        });
      }
      try {
        return directorWorkspaceProjection(
          await transport.json<unknown>(`${base}/${segment(documentId)}`, 'GET', undefined, signal), documentId);
      } catch (reason) { throw refusal(reason); }
    },
  };
}
