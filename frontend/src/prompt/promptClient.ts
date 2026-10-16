/**
 * R3-U Prompt Workspace 客户端。
 *
 * 读：复用 Round 3 的只读投影。
 * 写：复用 R3-W 已冻结的写入契约（白名单冲突体、request_id 幂等）。
 *
 * 这一层**不做**任何本地“乐观”改写：保存结果未知时绝不重发创建请求。
 */

import { ApiError, type CollaborationContext } from '../api';
import type { StudioGraphTransport } from '../creative/studioGraphClient';
import { promptEntry, promptInvalid, promptLibrary, promptReceipt, promptRevisionBody } from './promptContract';
import {
  PROMPT_BOUNDS, PROMPT_ERROR_CODES,
  type PromptConflict, type PromptCreateRequest, type PromptLibrary, type PromptEntry,
  type PromptReceipt, type PromptRevisionBody, type PromptRevisionRequest,
  type PromptWorkspaceClient,
} from './promptTypes';

/** 后端机器码 → 有界用户文案。 */
const PROMPT_FAILURES: Record<string, string> = {
  EXPERIMENTAL_NOT_FOUND: '这个项目当前不可用，可能已被归档或不在当前分支。',
  CREATIVE_AUTHORITY_INVALID: '当前会话无权访问这个项目。请重新核对身份与项目范围。',
  CREATIVE_AUTHORITY_CHANGED: '身份或项目范围已变化。请重新打开工作区。',
  EXPERIMENTAL_INVALID: '这次提交没有通过校验，请检查内容后重试。',
  PROMPT_REVISION_STALE: '这个 Prompt 已经有人保存了更新的修订。你的草稿已保留，请重新加载后再保存。',
  PROMPT_REQUEST_ID_REUSED: '这次提交的请求标识已经用于另一份内容。请以新的请求标识重新提交。',
  PROMPT_REVISION_CONFLICT: '另一个保存同时发生了。你的内容已保留为冲突修订，请重新加载后处理。',
  PROMPT_ASSET_VERSION_CONFLICT: '这个 Prompt 在保存过程中被别人改动了。请重新加载后再保存。',
};

const segment = encodeURIComponent;

function refusal(reason: unknown): unknown {
  if (!(reason instanceof ApiError)) return reason;
  const problem = reason.problem;
  const message = PROMPT_FAILURES[problem.code];
  if (message) return new ApiError({ ...problem, message });
  if (problem.status === 404) {
    return new ApiError({ ...problem, message: '这个 Prompt 当前不可用，可能已被删除或不在当前分支。' });
  }
  return reason;
}

/** 409 的白名单冲突体。字段缺失一律按“未知”处理，绝不猜。 */
export function readPromptConflict(reason: unknown): PromptConflict | null {
  if (!(reason instanceof ApiError) || reason.problem.status !== 409) return null;
  const payload = reason.problem.details;
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) return null;
  const row = payload as Record<string, unknown>;
  const code = typeof row.code === 'string' ? row.code : '';
  // 只有 R3-W 白名单内的错误码才算 Prompt 冲突。
  if (!Object.hasOwn(PROMPT_FAILURES, code)) return null;
  const numeric = (value: unknown): number | null =>
    typeof value === 'number' && Number.isInteger(value) && value >= 0 ? value : null;
  const text = (value: unknown): string | null =>
    typeof value === 'string' && value.length > 0 && value.length <= PROMPT_BOUNDS.identifier ? value : null;
  return {
    code,
    familyId: text(row.family_id),
    revision: numeric(row.revision),
    expectedRevision: numeric(row.expected_revision),
    currentRevision: numeric(row.current_revision),
    retryable: row.retryable === true,
  };
}

/** 请求体只包含用户有权提供的字段；服务端事实不在这里出现。 */
export function promptCreateBody(body: PromptCreateRequest): Record<string, unknown> {
  return {
    text: body.text,
    negative_prompt: body.negative_prompt,
    purpose: body.purpose,
    origin: body.origin,
    model_reference: body.model_reference,
    parameters: body.parameters,
    seed: body.seed,
    character_ids: [...body.character_ids],
    scene_ids: [...body.scene_ids],
    shot_ids: [...body.shot_ids],
    reference_asset_ids: [...body.reference_asset_ids],
    change_note: body.change_note,
    change_reason: body.change_reason,
    redacted: body.redacted,
    request_id: body.request_id,
  };
}

/** 修订请求体：在创建请求体之上加上“预期上一版本”身份。 */
export function promptRevisionRequest(body: PromptRevisionRequest): Record<string, unknown> {
  return {
    ...promptCreateBody(body),
    expected_previous_asset_id: body.expected_previous_asset_id,
    expected_revision: body.expected_revision,
  };
}

export function createPromptClient(
  projectId: string, transport: StudioGraphTransport, scope?: CollaborationContext['scope'],
): PromptWorkspaceClient {
  if (typeof projectId !== 'string' || !projectId.trim() || projectId.length > PROMPT_BOUNDS.identifier) {
    throw new ApiError({
      status: 200, code: PROMPT_ERROR_CODES.scopeMismatch,
      message: 'Prompt 工作区缺少有效的项目标识，请重新打开工作区。',
    });
  }
  const capturedScope = scope ? { ...scope } : undefined;
  const root = `/api/projects/${segment(projectId)}/studio/prompts`;
  const foreign = () => capturedScope !== undefined && capturedScope.projectId !== projectId;

  function requireOwnProject(): void {
    if (foreign()) {
      throw new ApiError({
        status: 403, code: PROMPT_ERROR_CODES.scopeMismatch,
        message: 'Prompt 工作区与当前项目或分支不一致，请重新打开工作区。',
      });
    }
  }

  return {
    async readLibrary(signal) {
      requireOwnProject();
      try {
        return promptLibrary(await transport.json<unknown>(root, 'GET', undefined, signal));
      } catch (reason) { throw refusal(reason); }
    },
    async readFamily(familyId, signal) {
      requireOwnProject();
      try {
        return promptEntry(await transport.json<unknown>(
          `${root}/${segment(familyId)}`, 'GET', undefined, signal));
      } catch (reason) { throw refusal(reason); }
    },
    async readRevisionBody(familyId, assetId, signal) {
      requireOwnProject();
      if (!familyId.trim() || !assetId.trim()) promptInvalid();
      try {
        // R3-U2：家族与资产必须同时指名，服务端会核对二者一致、并在调用者自己的 actor
        // 下读取。这里**不**改用 generic asset download，也不放宽历史 GET。
        return promptRevisionBody(await transport.json<unknown>(
          `${root}/${segment(familyId)}/revisions/${segment(assetId)}/body`,
          'GET', undefined, signal));
      } catch (reason) { throw refusal(reason); }
    },
    async createPrompt(body) {
      requireOwnProject();
      try {
        return promptReceipt(await transport.json<unknown>(
          root, 'POST', promptCreateBody(body), undefined, body.request_id));
      } catch (reason) { throw refusal(reason); }
    },
    async saveRevision(familyId, body) {
      requireOwnProject();
      try {
        return promptReceipt(await transport.json<unknown>(
          `${root}/${segment(familyId)}/revisions`, 'POST', promptRevisionRequest(body), undefined,
          body.request_id));
      } catch (reason) { throw refusal(reason); }
    },
    async approveRevision(familyId, assetId, expectedVersion) {
      requireOwnProject();
      if (!Number.isInteger(expectedVersion) || expectedVersion < 1) promptInvalid();
      try {
        return await transport.json<unknown>(
          `${root}/${segment(familyId)}/revisions/${segment(assetId)}/approve`
          + `?expected_version=${expectedVersion}`, 'POST', {});
      } catch (reason) { throw refusal(reason); }
    },
  };
}

export type { PromptEntry, PromptLibrary, PromptReceipt };
