/**
 * Round2-B 只读客户端。
 *
 * 只用**一个**只读端点：
 *   GET /api/projects/{nid}/studio/bible
 *
 * 这里没有角色/场景/资产写入，也没有编辑或保存入口：authoring 仍然走既有
 * `WorldService` 记录路径，本客户端不碰它。
 */

import { ApiError, type CollaborationContext } from '../api';
import type { StudioGraphTransport } from '../creative/studioGraphClient';
import { bibleProjection } from './bibleContract';
import { BIBLE_BOUNDS, BIBLE_ERROR_CODES, type BibleClient } from './bibleTypes';

/** 原 owner / 传输层真实抛出的机器码 → 有界用户文案。 */
const BIBLE_FAILURES: Record<string, string> = {
  EXPERIMENTAL_NOT_FOUND: '这个项目当前不可用，可能已被归档或不在当前分支。',
  EXPERIMENTAL_SOURCE_STALE: '这个项目记录的上游来源已经变化。请重新读取后核对。',
  CREATIVE_AUTHORITY_INVALID: '当前会话无权读取这个项目。请重新核对身份与项目范围。',
  CREATIVE_AUTHORITY_CHANGED: '身份或项目范围已变化。请重新打开工作区。',
};

function refusal(reason: unknown): unknown {
  if (!(reason instanceof ApiError)) return reason;
  const problem = reason.problem;
  const message = BIBLE_FAILURES[problem.code]
    ?? (problem.status === 404 ? '这个项目当前不可用，可能已被归档或不在当前分支。' : undefined);
  return message ? new ApiError({ ...problem, message }) : reason;
}

const segment = encodeURIComponent;

/** 注入既有传输。构造时克隆身份：之后的导航不能把请求改指到别的项目。 */
export function createBibleClient(
  projectId: string, transport: StudioGraphTransport, scope?: CollaborationContext['scope'],
): BibleClient {
  if (typeof projectId !== 'string' || !projectId.trim() || projectId.length > BIBLE_BOUNDS.identifier) {
    throw new ApiError({
      status: 200, code: BIBLE_ERROR_CODES.scopeMismatch,
      message: '角色与场景圣经缺少有效的项目标识，请重新打开工作区。',
    });
  }
  const capturedScope = scope ? { ...scope } : undefined;
  const target = `/api/projects/${segment(projectId)}/studio/bible`;
  const foreign = () => capturedScope !== undefined && capturedScope.projectId !== projectId;

  return {
    async readBible(signal?: AbortSignal) {
      if (foreign()) {
        throw new ApiError({
          status: 403, code: BIBLE_ERROR_CODES.scopeMismatch,
          message: '角色与场景圣经与当前项目或分支不一致，请重新打开工作区。',
        });
      }
      try {
        return bibleProjection(await transport.json<unknown>(target, 'GET', undefined, signal), projectId);
      } catch (reason) { throw refusal(reason); }
    },
  };
}
