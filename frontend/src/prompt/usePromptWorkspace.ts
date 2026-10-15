/**
 * R3-U3 Prompt 工作台控制器。
 *
 * 组件只负责呈现与收集输入；**所有**保存规则都在这里，并且复用已经验证过的
 * `promptClient` / `promptDraft`，不在组件里重写持久化逻辑，也不新建第二个资产 owner。
 *
 * P0-C：**读取与写入使用彼此独立的生命周期**。以前一个 `epoch` 同时服务
 * refresh / selectFamily / submit / rebase / compare，保存途中任何一次读取都会让 epoch 增加，
 * 把真正成功的回执当成过时结果丢弃，草稿永久停在 SUBMITTING。
 *
 * 现在的规则：
 * - 每个读操作有自己的序列号（library / detail / compare），只有同类读取能互相作废；
 * - 写入绑定精确的 `project|branch|actor` 身份 + `request_id`，
 *   只有身份被撤销、或那份草稿已被替换，写入结果才不予应用；
 * - 无关读取**不能**取消写入。
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { ApiError } from '../api';
import type { StudioGraphTransport } from '../creative/studioGraphClient';
import { createPromptClient, readPromptConflict } from './promptClient';
import {
  beginSubmit, canSubmit, clearDraftMarker, clearDraftSlot, confirmSaved, discardDraft,
  draftScopeKey, editDraft, hasUnconfirmedWork, isInputLocked, markConflict, markRejected,
  markUnknown, markerNotice, needsRebase, newDraft, readDraftMarker, rebaseDraft,
  reconcileStashed, rememberDraftMarker, retryUnknown, stashDraft, takeDraft,
  type Draft, type DraftContent,
} from './promptDraft';
import type { PromptEntry, PromptLibrary, PromptRevisionBody } from './promptTypes';

export type CompareSide = { assetId: string; revision: number; body: PromptRevisionBody };

export type PromptFieldProblem = { field: 'parameters' | 'seed' | 'text'; message: string };
export type ParsedDraft = { ok: true; parameters: Record<string, unknown>; seed: number | null }
  | ({ ok: false } & PromptFieldProblem);

export type PromptWorkspaceState = {
  library: PromptLibrary | null;
  detail: PromptEntry | null;
  loading: boolean;
  error: string | null;
  conflictCode: string | null;
  /** Field-level problem (invalid 参数/seed, or a baseline that cannot be revised) — blocks the write. */
  fieldError: PromptFieldProblem | null;
  draft: Draft;
  compare: { from: CompareSide | null; to: CompareSide | null; loading: boolean; error: string | null };
};

type Options = {
  projectId: string;
  branchId?: string | null;
  actor: string;
  transport: StudioGraphTransport;
  scope?: { projectId?: string } | undefined;
  onDirtyChange?: (value: boolean) => void;
};

const UNKNOWN_VALUE = 'UNKNOWN';

const newRequestId = (): string =>
  (globalThis.crypto?.randomUUID?.() ?? `req-${Date.now()}-${Math.random().toString(36).slice(2)}`);

export function usePromptWorkspace(options: Options) {
  const { projectId, branchId = null, actor, transport, scope, onDirtyChange } = options;

  /**
   * The host builds `studioTransport({...})` inline, so a NEW object arrives on every
   * render. Depending on that identity rebuilds `client` -> `refresh` -> the mount effect,
   * and each render starts another GET: a real-browser run showed the library pinned at
   * "正在读取…". Holding the transport in a ref keeps the client stable for a given
   * project/scope — the dependency that actually matters — while still calling the LATEST
   * transport, so nothing stale or revoked is retained.
   */
  const transportRef = useRef(transport);
  transportRef.current = transport;
  const stableTransport = useMemo<StudioGraphTransport>(() => ({
    json: (url, method, body, signal, idempotencyKey) =>
      transportRef.current.json(url, method, body, signal, idempotencyKey),
  }), []);
  const client = useMemo(
    () => createPromptClient(projectId, stableTransport, scope as never),
    [projectId, stableTransport, scope]);

  // Independent read lifetimes. A write is never identified by these.
  const libraryEpoch = useRef(0);
  const detailEpoch = useRef(0);
  const compareEpoch = useRef(0);
  const alive = useRef(true);
  const submitRef = useRef(false);
  const identity = draftScopeKey(projectId, branchId, actor);
  const identityRef = useRef(identity);
  identityRef.current = identity;

  useEffect(() => () => { alive.current = false; }, []);
  // A different identity invalidates in-flight reads; it must never inherit the previous
  // author's private text, and an old write must not be applied to the new identity.
  useEffect(() => {
    libraryEpoch.current += 1;
    detailEpoch.current += 1;
    compareEpoch.current += 1;
  }, [projectId, branchId, actor]);

  const [state, setState] = useState<PromptWorkspaceState>(() => ({
    library: null, detail: null, loading: false, error: null, conflictCode: null, fieldError: null,
    // A draft found in SUBMITTING has no request behind it any more (P0-C item 8): it is
    // reconciled to "outcome to be verified" rather than hanging forever.
    draft: reconcileStashed(takeDraft(projectId, branchId, actor, 'new') ?? newDraft('new')),
    compare: { from: null, to: null, loading: false, error: null },
  }));

  /**
   * §1-A: the content-free marker finally drives the UI.
   *
   * The marker never holds prompt text, so it can only ever say "an unsaved draft existed
   * and cannot be restored" — the wording must never read as a recovery. Reading it once on
   * mount is what turns a silent loss into a stated one.
   */
  const [restoreNotice, setRestoreNotice] = useState<string | null>(
    () => markerNotice(readDraftMarker(projectId)));

  useEffect(() => {
    stashDraft(projectId, branchId, actor, state.draft);
    onDirtyChange?.(hasUnconfirmedWork(state.draft));
    // Keep the marker in step with reality: present while work is unconfirmed, cleared as
    // soon as the server has confirmed it.
    if (hasUnconfirmedWork(state.draft)) {
      rememberDraftMarker(projectId, {
        familyId: state.draft.familyId,
        baseRevision: state.draft.baseRevision,
        requestId: state.draft.requestId,
      });
    } else {
      clearDraftMarker();
      setRestoreNotice(null);
    }
  }, [projectId, branchId, actor, state.draft, onDirtyChange]);

  const message = (reason: unknown, fallback: string): string => {
    if (reason instanceof ApiError) return reason.problem.message || fallback;
    return reason instanceof Error ? reason.message : fallback;
  };

  const refresh = useCallback(async () => {
    const mine = ++libraryEpoch.current;
    setState(prev => ({ ...prev, loading: true, error: null }));
    try {
      const library = await client.readLibrary();
      if (!alive.current || mine !== libraryEpoch.current) return;
      setState(prev => ({ ...prev, library, loading: false }));
    } catch (reason) {
      if (!alive.current || mine !== libraryEpoch.current) return;
      // A failed list read must never touch the draft: a confirmed save stays confirmed.
      setState(prev => ({ ...prev, loading: false, error: message(reason, '读取 Prompt 失败。') }));
    }
  }, [client]);

  const selectFamily = useCallback(async (familyId: string) => {
    const mine = ++detailEpoch.current;
    setState(prev => ({ ...prev, loading: true, error: null }));
    try {
      const detail = await client.readFamily(familyId);
      if (!alive.current || mine !== detailEpoch.current) return;
      setState(prev => {
        const existing = takeDraft(projectId, branchId, actor, familyId);
        const draft = existing ? reconcileStashed(existing) : {
          ...newDraft(familyId), familyId,
          baseAssetId: detail.headAssetId, baseRevision: detail.revision,
          content: fromEntry(detail),
        };
        return { ...prev, detail, draft, loading: false, conflictCode: null };
      });
    } catch (reason) {
      if (!alive.current || mine !== detailEpoch.current) return;
      setState(prev => ({ ...prev, loading: false, error: message(reason, '读取该 Prompt 失败。') }));
    }
  }, [client, projectId, branchId, actor]);

  const edit = useCallback((patch: Partial<DraftContent>) => {
    setState(prev => ({ ...prev, draft: editDraft(prev.draft, patch), conflictCode: null,
      fieldError: null }));
  }, []);

  const startNew = useCallback(() => {
    // P0-B: always a genuinely fresh slot. Reusing the "new" key would resurrect the family
    // created a moment ago and silently turn the next save into a revision of it.
    clearDraftSlot(projectId, branchId, actor, 'new');
    setState(prev => ({ ...prev, detail: null, conflictCode: null, fieldError: null,
      draft: newDraft('new') }));
  }, [projectId, branchId, actor]);

  /** P0-D: a revision may only be built on a complete, verified, fully-read baseline. */
  const baselineEditable = (detail: PromptEntry | null): boolean =>
    !!detail && detail.body.state === 'COMPLETE' && !!detail.body.digest
    && detail.readComplete && detail.historyComplete;

  /** P0-A: build the request only from valid input; never silently substitute defaults. */
  const buildRequest = (content: DraftContent, requestId: string) => {
    const parsed = parseContent(content);
    if (!parsed.ok) return parsed;
    return { ok: true as const, body: {
      text: content.text,
      negative_prompt: content.negativePrompt,
      purpose: content.purpose,
      origin: 'MANUAL' as const,
      model_reference: content.modelReference,
      parameters: parsed.parameters,
      seed: parsed.seed,
      character_ids: [...content.characterIds],
      scene_ids: [...content.sceneIds],
      shot_ids: [...content.shotIds],
      reference_asset_ids: [...content.referenceAssetIds],
      change_note: content.changeNote,
      change_reason: content.changeReason,
      redacted: false,
      request_id: requestId,
    } };
  };

  /**
   * Perform the write for an already-frozen snapshot. Never allocates a new request id.
   *
   * P0-C: the result is routed by **identity + request id**, never by an epoch. A refresh,
   * a comparison or a host re-render cannot cancel it; only losing the identity or
   * replacing that draft can.
   */
  const submit = useCallback(async (submitted: Draft) => {
    if (submitted.state !== 'SUBMITTING' || !submitted.requestId) return;
    const requestId = submitted.requestId;
    const capturedIdentity = identityRef.current;
    const built = buildRequest(submitted.content, requestId);
    if (!built.ok) {
      setState(prev => ({ ...prev, draft: markRejected(prev.draft, built.field, built.message),
        fieldError: { field: built.field, message: built.message } }));
      return;
    }
    const isRevision = submitted.familyId !== null && submitted.baseAssetId !== null;
    try {
      const receipt = isRevision
        ? await client.saveRevision(submitted.familyId!, {
            ...built.body,
            expected_previous_asset_id: submitted.baseAssetId!,
            expected_revision: submitted.baseRevision!,
          })
        : await client.createPrompt(built.body);
      if (!alive.current) return;
      // The identity was revoked or replaced while the write was in flight: the result must
      // not be shown to whoever is looking now.
      if (identityRef.current !== capturedIdentity) return;
      setState(prev => {
        // The user moved to another draft: never misapply this receipt to it.
        if (prev.draft.requestId !== requestId) return prev;
        return { ...prev, draft: confirmSaved(prev.draft, receipt), fieldError: null };
      });
      // Re-read the authorised family so the panel shows server truth. A failure here only
      // surfaces a list error; it must not undo the confirmed save.
      await refresh();
    } catch (reason) {
      if (!alive.current || identityRef.current !== capturedIdentity) return;
      const status = reason instanceof ApiError ? reason.problem.status : null;
      const conflict = reason instanceof ApiError ? readPromptConflict(reason) : null;
      setState(prev => {
        if (prev.draft.requestId !== requestId) return prev;
        if (conflict) {
          return { ...prev, draft: markConflict(prev.draft, conflict.code,
            message(reason, '这个 Prompt 已被他人更新。')), conflictCode: conflict.code };
        }
        // P0-F: a definite 4xx refusal is NOT an unknown outcome. Only 5xx / no status /
        // a transport failure leave the result genuinely unknown.
        if (status !== null && status >= 400 && status < 500) {
          // Bounded, actionable Chinese text — an unrecognised upstream code must not
          // surface as a raw message.
          return { ...prev, draft: markRejected(prev.draft, `HTTP_${status}`,
            `服务器明确拒绝了这次保存（HTTP ${status}）。你的草稿已保留，修正后可以重新提交。`),
            fieldError: null };
        }
        return { ...prev, draft: markUnknown(prev.draft,
          message(reason, '保存结果未知，请核对后再决定是否重试。')) };
      });
    }
  }, [client, refresh]);

  const save = useCallback(() => {
    // Compute the snapshot OUTSIDE setState: a state updater is not guaranteed to run
    // synchronously, so reading a value out of it would silently skip the write.
    const isRevision = state.draft.familyId !== null && state.draft.baseAssetId !== null;
    if (isRevision && !baselineEditable(state.detail)) {
      // P0-D: never grow a revision from a preview, a redaction or an incomplete history.
      setState(prev => ({ ...prev, fieldError: { field: 'text',
        message: '服务器上这一修订的正文不是完整可编辑版本（预览／脱敏／不可读或历史不完整），'
          + '不能据此保存新修订。请改为新建一份独立 Prompt。' } }));
      return;
    }
    // P0-H: one synchronous lease per event batch — a double click must not allocate two ids.
    if (submitRef.current) return;
    const built = buildRequest(state.draft.content, 'validate');
    if (!built.ok) {
      // P0-A: refuse instead of silently replacing invalid input with defaults.
      setState(prev => ({ ...prev, fieldError: { field: built.field, message: built.message } }));
      return;
    }
    const submitted = beginSubmit(state.draft, newRequestId);
    if (submitted.state !== 'SUBMITTING' || !submitted.requestId) return;
    submitRef.current = true;
    setState(prev => ({ ...prev, draft: submitted, error: null, conflictCode: null, fieldError: null }));
    void submit(submitted).finally(() => { submitRef.current = false; });
  }, [state.draft, state.detail, submit]);

  const retry = useCallback(() => {
    // Reuses the original request id and the original snapshot — never a new one.
    const next = retryUnknown(state.draft);
    if (next.state !== 'SUBMITTING') return;
    if (submitRef.current) return;
    submitRef.current = true;
    setState(prev => ({ ...prev, draft: next }));
    void submit(next).finally(() => { submitRef.current = false; });
  }, [state.draft, submit]);

  /**
   * P0-E: rebasing must re-read the **server's current head**, not reuse the detail that was
   * already stale when the 409 arrived. The local edit is preserved; on failure nothing is
   * marked as rebased.
   */
  const rebase = useCallback(async (familyId: string) => {
    const mine = ++detailEpoch.current;
    try {
      const fresh = await client.readFamily(familyId);
      if (!alive.current || mine !== detailEpoch.current) return;
      setState(prev => ({
        ...prev, detail: fresh, conflictCode: null, fieldError: null,
        draft: rebaseDraft(prev.draft, {
          assetId: fresh.headAssetId, revision: fresh.revision, familyId: fresh.familyId,
        }),
      }));
    } catch (reason) {
      if (!alive.current || mine !== detailEpoch.current) return;
      setState(prev => ({ ...prev, error: message(reason, '无法读取服务器上的最新修订，尚未重新基准。') }));
    }
  }, [client]);

  const discard = useCallback(() => {
    setState(prev => ({ ...prev, draft: discardDraft(prev.draft), conflictCode: null,
      fieldError: null }));
  }, []);

  const compare = useCallback(async (familyId: string, fromId: string, toId: string) => {
    const mine = ++compareEpoch.current;
    setState(prev => ({ ...prev, compare: { ...prev.compare, loading: true, error: null } }));
    try {
      const [from, to] = await Promise.all([
        client.readRevisionBody(familyId, fromId),
        client.readRevisionBody(familyId, toId),
      ]);
      if (!alive.current || mine !== compareEpoch.current) return;
      setState(prev => ({ ...prev, compare: {
        loading: false, error: null,
        from: { assetId: fromId, revision: from.revision, body: from },
        to: { assetId: toId, revision: to.revision, body: to },
      } }));
    } catch (reason) {
      if (!alive.current || mine !== compareEpoch.current) return;
      setState(prev => ({ ...prev, compare: {
        ...prev.compare, loading: false, error: message(reason, '无法读取该修订的正文。') } }));
    }
  }, [client]);

  return {
    state, refresh, selectFamily, startNew, edit, save, retry, rebase, discard, compare,
    locked: isInputLocked(state.draft), canSave: canSubmit(state.draft),
    restoreNotice,
    scopeKey: draftScopeKey(projectId, branchId, actor),
  };
}

/** Library entry → editable content. Hand-written drafts are MANUAL and never claimed as AI. */
export function fromEntry(entry: PromptEntry): DraftContent {
  const field = (name: string): unknown => entry.fields.find(row => row.field === name)?.value;
  const asText = (value: unknown): string =>
    (typeof value === 'string' && value !== UNKNOWN_VALUE ? value : '');
  const list = (values: string[]): string[] => [...values];
  return {
    // A preview or a redaction is NOT an editable full body (P0-D): only COMPLETE prefills.
    text: entry.body.state === 'COMPLETE' ? (entry.body.value ?? '') : '',
    negativePrompt: asText(field('negative_prompt')),
    purpose: (['IMAGE', 'VIDEO', 'AUDIO', 'TEXT'] as const)
      .find(value => value === entry.purpose) ?? 'IMAGE',
    modelReference: asText(field('model_reference')),
    parameters: (() => {
      const value = field('parameters');
      return value && typeof value === 'object' && !Array.isArray(value)
        ? JSON.stringify(value) : '';
    })(),
    seed: (() => { const value = field('seed'); return typeof value === 'number' ? String(value) : ''; })(),
    characterIds: list(entry.bindings.characters.map(row => row.id)),
    sceneIds: list(entry.bindings.scenes.map(row => row.id)),
    shotIds: list(entry.bindings.shots.map(row => row.id)),
    referenceAssetIds: list(entry.referenceAssetIds),
    changeNote: '',
    changeReason: '',
  };
}

/**
 * Parse the local draft's 参数/seed. An invalid value stays in the draft and blocks saving —
 * it is never silently coerced to `{}` or `null` and then submitted.
 */
export function parseDraft(content: DraftContent): ParsedDraft {
  return parseContent(content);
}

function parseContent(content: DraftContent): ParsedDraft {
  let parameters: Record<string, unknown> = {};
  if (content.parameters.trim()) {
    try {
      const parsed: unknown = JSON.parse(content.parameters);
      if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
        return { ok: false, field: 'parameters',
          message: '参数必须是 JSON 对象；当前输入已保留，未提交。' };
      }
      parameters = parsed as Record<string, unknown>;
    } catch {
      return { ok: false, field: 'parameters',
        message: '参数不是合法 JSON；当前输入已保留，未提交。' };
    }
  }
  let seed: number | null = null;
  if (content.seed.trim()) {
    const parsed = Number(content.seed);
    // Match the server DTO: a non-negative safe integer, never a coerced default.
    if (!Number.isSafeInteger(parsed) || parsed < 0) {
      return { ok: false, field: 'seed',
        message: 'Seed 必须是非负安全整数；当前输入已保留，未提交。' };
    }
    seed = parsed;
  }
  return { ok: true, parameters, seed };
}

export { needsRebase };
