/**
 * R3-U 草稿状态机。
 *
 * 必须区分四种状态（指令 §2.4）：
 *   DIRTY       本地未保存草稿
 *   SUBMITTING  请求已提交，仍在等待
 *   SAVED       已确认保存（服务器已回执）
 *   UNKNOWN     结果未知（超时/断网/响应丢失）——**绝不自动重发**
 *   CONFLICT    409 冲突，草稿保留
 *
 * 关于本地持久化：仓库既有的 `studioWorkspaceResume` 明确声明
 * “No drafts, prompts, outputs, tokens, credentials or execution receipts are stored.”
 * 因此这里**不把 Prompt 正文写入 localStorage**。刷新后正文无法恢复，但也不允许
 * “无提示”地消失：只持久化一个**不含内容**的标记（家族、基准修订、是否存在草稿），
 * 刷新后据此明确告知用户草稿存在但内容无法恢复。
 */

import { PROMPT_BOUNDS } from './promptTypes';

export type DraftState = 'DIRTY' | 'SUBMITTING' | 'SAVED' | 'UNKNOWN' | 'CONFLICT' | 'CLEAN';

export type DraftContent = {
  text: string;
  negativePrompt: string;
  purpose: 'IMAGE' | 'VIDEO' | 'AUDIO' | 'TEXT';
  modelReference: string;
  parameters: string;
  seed: string;
  characterIds: string[];
  sceneIds: string[];
  shotIds: string[];
  referenceAssetIds: string[];
  changeNote: string;
  changeReason: string;
};

export type Draft = {
  key: string;
  /** 家族；新建时为 null。 */
  familyId: string | null;
  /** 编辑所依据的修订身份（新建时为 null）。 */
  baseAssetId: string | null;
  baseRevision: number | null;
  content: DraftContent;
  state: DraftState;
  /** 只有 SUBMITTING / UNKNOWN 期间有意义；同一份草稿必须复用同一个标识。 */
  requestId: string | null;
  conflictCode: string | null;
  message: string | null;
};

export const emptyContent = (): DraftContent => ({
  text: '', negativePrompt: '', purpose: 'IMAGE', modelReference: '', parameters: '',
  seed: '', characterIds: [], sceneIds: [], shotIds: [], referenceAssetIds: [],
  changeNote: '', changeReason: '',
});

export function newDraft(key: string): Draft {
  return { key, familyId: null, baseAssetId: null, baseRevision: null, content: emptyContent(),
    state: 'CLEAN', requestId: null, conflictCode: null, message: null };
}

/** 本地是否有尚未确认保存的内容。SAVED/CLEAN 之外的任何状态都算。 */
export function hasUnconfirmedWork(draft: Draft): boolean {
  return draft.state === 'DIRTY' || draft.state === 'SUBMITTING'
    || draft.state === 'UNKNOWN' || draft.state === 'CONFLICT';
}

/** 正文是否真的变化过（与服务器上的基准比较）。 */
export function isModified(draft: Draft, base: { text: string; negativePrompt: string }): boolean {
  return draft.content.text !== base.text || draft.content.negativePrompt !== base.negativePrompt;
}

export function editDraft(draft: Draft, patch: Partial<DraftContent>): Draft {
  // 结果未知时的输入先被拒绝：必须由用户决定重试还是放弃，不能悄悄改掉待确认内容。
  if (draft.state === 'UNKNOWN') return draft;
  return { ...draft, content: { ...draft.content, ...patch },
    state: draft.state === 'SUBMITTING' ? 'SUBMITTING' : 'DIRTY', message: null };
}

/**
 * 提交。`allocate` 只在**第一次**提交时调用；重试必须复用同一个 request_id，
 * 这样服务端 R3-W 的幂等才能把它识别为同一次请求。
 */
export function beginSubmit(draft: Draft, allocate: () => string): Draft {
  if (draft.state === 'SUBMITTING') return draft;
  const requestId = draft.requestId ?? allocate();
  return { ...draft, state: 'SUBMITTING', requestId, conflictCode: null, message: null };
}

export function confirmSaved(draft: Draft, saved: {
  familyId: string; assetId: string; revision: number; idempotentReplay: boolean;
}): Draft {
  return { ...draft, familyId: saved.familyId, baseAssetId: saved.assetId,
    baseRevision: saved.revision, state: 'SAVED', requestId: null, conflictCode: null,
    message: saved.idempotentReplay ? '这次提交与服务器上已有的修订一致，没有重复创建。' : null };
}

/** 409：保留草稿与 request_id，让用户重新加载后再决定。 */
export function markConflict(draft: Draft, code: string, message: string): Draft {
  return { ...draft, state: 'CONFLICT', conflictCode: code, message };
}

/**
 * 网络/超时/响应丢失：结果**未知**。
 *
 * 关键点：这里保留 `requestId`，并且不自动重试。用户下一次显式提交会复用同一个
 * request_id，服务端据此返回同一次修订（或者明确告知该标识已用于别的内容），
 * 所以不会产生第二份修订。
 */
export function markUnknown(draft: Draft, message: string): Draft {
  return { ...draft, state: 'UNKNOWN', message };
}

/**
 * 用户在“结果未知”后显式重试。
 *
 * 复用同一个 request_id 是**唯一**安全的做法：换新标识就会真的创建第二份修订。
 */
export function retryUnknown(draft: Draft): Draft {
  if (draft.state !== 'UNKNOWN' || !draft.requestId) return draft;
  return { ...draft, state: 'SUBMITTING', message: null };
}

/** 用户明确放弃本地内容（必须由用户操作触发）。 */
export function discardDraft(draft: Draft): Draft {
  return { ...draft, content: emptyContent(), state: 'CLEAN', requestId: null,
    conflictCode: null, message: null };
}

// ---------------------------------------------------------- 刷新标记 --

const markerKey = 'studio.prompt-draft-marker.v1:local-author:file';
const markerFields = ['schema', 'mode', 'actor', 'project_id', 'family_id', 'base_revision', 'request_id'];

export type DraftMarker = { state: 'EMPTY' | 'INVALID' | 'UNAVAILABLE' }
  | { state: 'EXISTS'; familyId: string | null; baseRevision: number | null; requestId: string | null };

const validId = (value: unknown): value is string => typeof value === 'string' && !!value.trim()
  && value.length <= PROMPT_BOUNDS.identifier && !/[\u0000-\u001f\u007f]/.test(value);

/** 只读、无内容的标记读取。不含正文，因此刷新后不能恢复内容。 */
export function readDraftMarker(projectId: string,
  storage?: Pick<Storage, 'getItem'>): DraftMarker {
  if (!validId(projectId)) return { state: 'INVALID' };
  try {
    const raw = (storage ?? globalThis.localStorage).getItem(markerKey);
    if (!raw) return { state: 'EMPTY' };
    if (raw.length > 2048) return { state: 'INVALID' };
    const parsed: unknown = JSON.parse(raw);
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return { state: 'INVALID' };
    const row = parsed as Record<string, unknown>;
    if (Object.keys(row).some(field => !markerFields.includes(field)) || row.schema !== 1
      || row.mode !== 'local' || row.actor !== 'local-author' || !validId(row.project_id)) {
      return { state: 'INVALID' };
    }
    if (row.project_id !== projectId) return { state: 'EMPTY' };
    return {
      state: 'EXISTS',
      familyId: validId(row.family_id) ? row.family_id : null,
      baseRevision: typeof row.base_revision === 'number' && Number.isInteger(row.base_revision)
        ? row.base_revision : null,
      requestId: validId(row.request_id) ? row.request_id : null,
    };
  } catch { return { state: 'UNAVAILABLE' }; }
}

/** 写入**不含正文**的标记。正文永远不进入浏览器存储。 */
export function rememberDraftMarker(projectId: string, marker: {
  familyId: string | null; baseRevision: number | null; requestId: string | null;
}, storage?: Pick<Storage, 'setItem'>): boolean {
  if (!validId(projectId)) return false;
  try {
    (storage ?? globalThis.localStorage).setItem(markerKey, JSON.stringify({
      schema: 1, mode: 'local', actor: 'local-author', project_id: projectId,
      ...(validId(marker.familyId) ? { family_id: marker.familyId } : {}),
      ...(marker.baseRevision === null ? {} : { base_revision: marker.baseRevision }),
      ...(validId(marker.requestId) ? { request_id: marker.requestId } : {}),
    }));
    return true;
  } catch { return false; }
}

export function clearDraftMarker(storage?: Pick<Storage, 'removeItem'>): void {
  try { (storage ?? globalThis.localStorage).removeItem(markerKey); } catch { /* storage may be blocked */ }
}

/** 刷新后给用户的说明：明确说明内容**无法**恢复，而不是假装恢复了。 */
export function markerNotice(marker: DraftMarker): string | null {
  if (marker.state !== 'EXISTS') return null;
  const where = marker.familyId ? '这个家族的' : '新建 Prompt 的';
  return `检测到${where}未保存草稿。出于安全考虑，正文不会写入浏览器存储，因此刷新后无法恢复；`
    + '请重新编辑，或先加载服务器上的已授权版本。';
}
