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
 * R3-U1 修复的核心不变量：**提交的是一份不可变快照（`pending`）**。
 * SUBMITTING / UNKNOWN 期间禁止修改待提交快照（UI 据此禁用输入），
 * `confirmSaved` 只在被回执确认的就是那份快照时才置为 SAVED —— 因此
 * “提交途中输入的新文本”永远不会被显示成“已保存”。
 *
 * request_id 规则：
 *   UNKNOWN 且内容与快照完全一致 → 允许用户显式重试，复用原 request_id
 *   被拒绝（CONFLICT）或已完成（SAVED）→ 立即作废该标识；必须重新基准后才能申请新的标识
 *
 * 关于本地持久化：仓库既有 `studioWorkspaceResume` 明确声明
 * “No drafts, prompts, outputs, tokens, credentials or execution receipts are stored.”
 * 因此这里**不把 Prompt 正文写入 localStorage**。只持久化一个**不含内容**的标记，
 * 刷新后据此明确告知用户草稿存在但**内容无法恢复** —— 检测到草稿不等于恢复草稿。
 */

import { PROMPT_BOUNDS } from './promptTypes';

export type DraftState = 'DIRTY' | 'SUBMITTING' | 'SAVED' | 'UNKNOWN' | 'CONFLICT' | 'REJECTED' | 'CLEAN';

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
  /** 用户正在编辑的内容。 */
  content: DraftContent;
  /** 已提交、不可变的快照。非 SUBMITTING/UNKNOWN 时为 null。 */
  pending: DraftContent | null;
  state: DraftState;
  /** 只有 SUBMITTING / UNKNOWN 期间有意义。 */
  requestId: string | null;
  conflictCode: string | null;
  /** A definite server refusal (4xx). Distinct from an unresolved conflict. */
  rejectionCode: string | null;
  message: string | null;
};

export const emptyContent = (): DraftContent => ({
  text: '', negativePrompt: '', purpose: 'IMAGE', modelReference: '', parameters: '',
  seed: '', characterIds: [], sceneIds: [], shotIds: [], referenceAssetIds: [],
  changeNote: '', changeReason: '',
});

/**
 * 深拷贝草稿内容。
 *
 * 只做 `{ ...content }` 会共享数组引用：外部对原数组 push/splice，或组件闭包复用同一个数组，
 * 都会在提交之后悄悄改变“已发出的请求”的含义。因此快照与写入都必须复制数组。
 */
export function cloneContent(content: DraftContent): DraftContent {
  return {
    ...content,
    characterIds: [...content.characterIds],
    sceneIds: [...content.sceneIds],
    shotIds: [...content.shotIds],
    referenceAssetIds: [...content.referenceAssetIds],
  };
}

export function newDraft(key: string): Draft {
  return { key, familyId: null, baseAssetId: null, baseRevision: null, content: emptyContent(),
    pending: null, state: 'CLEAN', requestId: null, conflictCode: null, rejectionCode: null,
    message: null };
}

/** 本地是否有尚未确认保存的内容。 */
export function hasUnconfirmedWork(draft: Draft): boolean {
  return draft.state === 'DIRTY' || draft.state === 'SUBMITTING'
    || draft.state === 'UNKNOWN' || draft.state === 'CONFLICT' || draft.state === 'REJECTED';
}

/** 提交途中（含结果未知）输入必须被锁定：此刻改动内容会与已发出的请求不一致。 */
export function isInputLocked(draft: Draft): boolean {
  return draft.state === 'SUBMITTING' || draft.state === 'UNKNOWN';
}

/** 待提交快照与当前内容是否一致。 */
export function pendingMatchesContent(draft: Draft): boolean {
  if (!draft.pending) return false;
  const a = draft.pending;
  const b = draft.content;
  return a.text === b.text && a.negativePrompt === b.negativePrompt && a.purpose === b.purpose
    && a.modelReference === b.modelReference && a.parameters === b.parameters && a.seed === b.seed
    && a.changeNote === b.changeNote && a.changeReason === b.changeReason
    && sameList(a.characterIds, b.characterIds) && sameList(a.sceneIds, b.sceneIds)
    && sameList(a.shotIds, b.shotIds) && sameList(a.referenceAssetIds, b.referenceAssetIds);
}

const sameList = (a: readonly string[], b: readonly string[]): boolean =>
  a.length === b.length && a.every((value, index) => value === b[index]);

/** 冲突未解决前不允许提交：必须先重新基准。明确拒绝（REJECTED）不属于冲突。 */
export function needsRebase(draft: Draft): boolean {
  return draft.state === 'CONFLICT';
}

/**
 * 是否允许发起一次新的提交（会申请新的 request_id）。
 *
 * REJECTED 允许直接再提交（例如存储不足、参数被服务端否决后用户已修正），
 * 但 SUBMITTING/UNKNOWN 绝不允许——那会制造第二个请求。
 */
export function canSubmit(draft: Draft): boolean {
  return (draft.state === 'CLEAN' || draft.state === 'DIRTY' || draft.state === 'REJECTED')
    // An unresolved conflict still requires an explicit rebase before a new request id.
    && draft.conflictCode === null && draft.requestId === null;
}

export function editDraft(draft: Draft, patch: Partial<DraftContent>): Draft {
  // SUBMITTING / UNKNOWN：不得改动待提交快照，否则“已保存”的可能是另一份内容。
  if (isInputLocked(draft)) return draft;
  return { ...draft, content: cloneContent({ ...draft.content, ...patch }), state: 'DIRTY',
    // 冲突标记保留到显式重新基准为止；明确拒绝的原因在用户开始修改后即可清除。
    conflictCode: draft.state === 'CONFLICT' ? draft.conflictCode : null,
    rejectionCode: null,
    message: null };
}

/**
 * 提交。第一次提交时冻结快照并申请 request_id；已在途则原样返回。
 */
export function beginSubmit(draft: Draft, allocate: () => string): Draft {
  if (draft.state === 'SUBMITTING') return draft;
  if (!canSubmit(draft)) return draft;
  return { ...draft, state: 'SUBMITTING', pending: cloneContent(draft.content),
    requestId: allocate(), conflictCode: null, message: null };
}

/**
 * 服务器回执。**只有被确认的就是那份快照时才置为 SAVED。**
 *
 * 若内容与快照不一致（防御性分支：锁定生效前的历史状态），则保持 DIRTY，
 * 让未提交的改动继续显示为“未保存”，而不是冒充已保存。
 */
export function confirmSaved(draft: Draft, saved: {
  familyId: string; assetId: string; revision: number; idempotentReplay: boolean;
}): Draft {
  const matched = draft.pending !== null && pendingMatchesContent(draft);
  // P0-B: a create that started in the "new" slot must **adopt the new family as its key**.
  // Otherwise the "new" slot keeps pointing at the family just created, and the next
  // "新建 Prompt" silently turns into a revision of it.
  const key = draft.familyId === null ? saved.familyId : draft.key;
  const base = {
    ...draft, key, familyId: saved.familyId, baseAssetId: saved.assetId, baseRevision: saved.revision,
    requestId: null, conflictCode: null, rejectionCode: null, pending: null,
  };
  if (!matched) {
    return { ...base, state: 'DIRTY',
      message: '服务器已保存的是提交时的内容；此后的改动仍未保存。' };
  }
  return { ...base, state: 'SAVED',
    message: saved.idempotentReplay ? '这次提交与服务器上已有的修订一致，没有重复创建。' : null };
}

/** 409：保留草稿；该请求标识已被终局拒绝，立即作废。 */
export function markConflict(draft: Draft, code: string, message: string): Draft {
  return { ...draft, state: 'CONFLICT', conflictCode: code, rejectionCode: null, message,
    requestId: null, pending: null };
}

/**
 * 服务端**明确拒绝**（4xx，非 409）：草稿保留、可以修正后重交，但**不是**“结果未知”。
 *
 * 这里作废 request_id 是安全的：明确的拒绝意味着这次写入没有发生，因此下一次提交用新标识
 * 不会产生第二份修订。把 422/403 当成 UNKNOWN 会让界面永久停在“可能已保存、不能改标识”。
 */
export function markRejected(draft: Draft, code: string, message: string): Draft {
  return { ...draft, state: 'REJECTED', conflictCode: null, rejectionCode: code, message,
    requestId: null, pending: null };
}

/**
 * 网络/超时/响应丢失：结果**未知**。
 *
 * 保留 requestId 与快照，并且不自动重试。
 */
export function markUnknown(draft: Draft, message: string): Draft {
  return { ...draft, state: 'UNKNOWN', message };
}

/**
 * 用户在“结果未知”后显式重试。
 *
 * 只有内容与快照**完全一致**时才允许复用原 request_id —— 换新标识会真的创建第二份修订，
 * 而内容若已改变则原标识代表的已不是同一份请求。
 */
export function retryUnknown(draft: Draft): Draft {
  if (draft.state !== 'UNKNOWN' || !draft.requestId) return draft;
  if (!pendingMatchesContent(draft)) return draft;
  return { ...draft, state: 'SUBMITTING', message: null };
}

/**
 * 用户显式把草稿重新基准到服务器上的某个修订（解决冲突后的必要一步）。
 * 这是唯一允许在冲突之后申请新 request_id 的入口。
 */
export function rebaseDraft(draft: Draft, base: {
  assetId: string; revision: number; content?: DraftContent; familyId?: string | null;
}): Draft {
  return {
    ...draft,
    familyId: base.familyId === undefined ? draft.familyId : base.familyId,
    baseAssetId: base.assetId,
    baseRevision: base.revision,
    content: base.content ?? draft.content,
    state: 'DIRTY',
    pending: null,
    requestId: null,
    conflictCode: null,
    message: '已重新基准到服务器上的最新修订。请核对后再次保存。',
  };
}

/** 用户明确放弃本地内容（必须由用户操作触发）。 */
export function discardDraft(draft: Draft): Draft {
  return { ...draft, content: emptyContent(), pending: null, state: 'CLEAN', requestId: null,
    conflictCode: null, rejectionCode: null, message: null };
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

/**
 * 刷新后给用户的说明。
 *
 * 措辞必须准确：这是**检测到**曾经有草稿，不是**恢复**了草稿。正文没有进入浏览器存储，
 * 因此无法恢复。绝不能把“检测到草稿”说成“已恢复草稿”。
 */
export function markerNotice(marker: DraftMarker): string | null {
  if (marker.state !== 'EXISTS') return null;
  const where = marker.familyId ? '这个家族的' : '新建 Prompt 的';
  return `检测到${where}未保存草稿。出于安全考虑，正文不会写入浏览器存储，因此刷新后无法恢复；`
    + '请重新编辑，或先加载服务器上的已授权版本。';
}

// ------------------------------------------------- 会话内草稿隔离 --

/**
 * 同一会话内的内存草稿存储。
 *
 * 指令 §6 要求：项目/分支/身份切换时绝不能把上一个人的私有正文显示给下一个人。
 * 因此草稿按 `project|branch|actor` 三元组隔离，切换身份只会取到属于自己的草稿。
 */
const inMemoryDrafts = new Map<string, Draft>();

export function draftScopeKey(projectId: string, branchId: string | null, actor: string): string {
  return `${projectId}\u0000${branchId ?? ''}\u0000${actor}`;
}

function storageKey(scope: string, key: string): string {
  return `${scope}\u0000${key}`;
}

/** 会话内读写：跨模块跳转保留，跨项目/身份不串台。存入与取出都复制，避免共享可变对象。 */
export function stashDraft(projectId: string, branchId: string | null, actor: string, draft: Draft): void {
  inMemoryDrafts.set(storageKey(draftScopeKey(projectId, branchId, actor), draft.key), {
    ...draft,
    content: cloneContent(draft.content),
    pending: draft.pending ? cloneContent(draft.pending) : null,
  });
}

export function takeDraft(projectId: string, branchId: string | null, actor: string,
  key: string): Draft | null {
  const stored = inMemoryDrafts.get(storageKey(draftScopeKey(projectId, branchId, actor), key));
  if (!stored) return null;
  // 返回副本：旧组件保留上一次取到的对象时，不能继续污染 store 里的草稿。
  return { ...stored, content: cloneContent(stored.content),
    pending: stored.pending ? cloneContent(stored.pending) : null };
}

export function dropStashedDrafts(projectId: string, branchId: string | null, actor: string): void {
  const scope = draftScopeKey(projectId, branchId, actor);
  for (const stored of [...inMemoryDrafts.keys()]) {
    if (stored.startsWith(`${scope}\u0000`)) inMemoryDrafts.delete(stored);
  }
}

/** Remove one slot. Used when a "new prompt" slot has been promoted to a family. */
export function clearDraftSlot(projectId: string, branchId: string | null, actor: string,
  key: string): void {
  inMemoryDrafts.delete(storageKey(draftScopeKey(projectId, branchId, actor), key));
}

/** 仅测试与登出使用：清空全部内存草稿。 */
export function clearAllStashedDrafts(): void {
  inMemoryDrafts.clear();
}
