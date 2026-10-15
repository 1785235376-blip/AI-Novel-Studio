/**
 * R3-U3 Prompt 工作台控制器。
 *
 * 组件只负责呈现与收集输入；**所有**保存规则都在这里，并且复用已经验证过的
 * `promptClient` / `promptDraft`，不在组件里重写持久化逻辑，也不新建第二个资产 owner。
 *
 * 关键约定：
 * - 只有 `readFamily` 拿到的 head 才是 rebase 的依据；
 * - 过期异步结果不得覆盖新项目／新选择（按 epoch 丢弃）；
 * - UNKNOWN 绝不自动重发；409 必须显式 rebase 后才能申请新的 request_id。
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { ApiError } from '../api';
import type { StudioGraphTransport } from '../creative/studioGraphClient';
import { createPromptClient, readPromptConflict } from './promptClient';
import {
  beginSubmit, canSubmit, confirmSaved, discardDraft, draftScopeKey, editDraft, hasUnconfirmedWork,
  isInputLocked, markConflict, markUnknown, needsRebase, newDraft, rebaseDraft, retryUnknown,
  stashDraft, takeDraft, type Draft, type DraftContent,
} from './promptDraft';
import type { PromptEntry, PromptLibrary, PromptRevisionBody } from './promptTypes';

export type CompareSide = { assetId: string; revision: number; body: PromptRevisionBody };

export type PromptWorkspaceState = {
  library: PromptLibrary | null;
  detail: PromptEntry | null;
  loading: boolean;
  error: string | null;
  conflictCode: string | null;
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

const newRequestId = (): string =>
  (globalThis.crypto?.randomUUID?.() ?? `req-${Date.now()}-${Math.random().toString(36).slice(2)}`);

export function usePromptWorkspace(options: Options) {
  const { projectId, branchId = null, actor, transport, scope, onDirtyChange } = options;
  const client = useMemo(
    () => createPromptClient(projectId, transport, scope as never), [projectId, transport, scope]);

  const epoch = useRef(0);
  const alive = useRef(true);
  useEffect(() => () => { alive.current = false; }, []);
  // A different identity must never show the previous one's private text.
  useEffect(() => { epoch.current += 1; }, [projectId, branchId, actor]);

  const [state, setState] = useState<PromptWorkspaceState>(() => ({
    library: null, detail: null, loading: false, error: null, conflictCode: null,
    draft: takeDraft(projectId, branchId, actor, 'new') ?? newDraft('new'),
    compare: { from: null, to: null, loading: false, error: null },
  }));

  // Persist the in-session draft, scoped by project|branch|actor.
  useEffect(() => {
    stashDraft(projectId, branchId, actor, state.draft);
    onDirtyChange?.(hasUnconfirmedWork(state.draft));
  }, [projectId, branchId, actor, state.draft, onDirtyChange]);

  const message = (reason: unknown, fallback: string): string => {
    if (reason instanceof ApiError) {
      const conflict = readPromptConflict(reason);
      if (conflict) return reason.problem.message || fallback;
      return reason.problem.message || fallback;
    }
    return reason instanceof Error ? reason.message : fallback;
  };

  const refresh = useCallback(async () => {
    const mine = ++epoch.current;
    setState(prev => ({ ...prev, loading: true, error: null }));
    try {
      const library = await client.readLibrary();
      if (!alive.current || mine !== epoch.current) return;
      setState(prev => ({ ...prev, library, loading: false }));
    } catch (reason) {
      if (!alive.current || mine !== epoch.current) return;
      setState(prev => ({ ...prev, loading: false, error: message(reason, '读取 Prompt 失败。') }));
    }
  }, [client]);

  const selectFamily = useCallback(async (familyId: string) => {
    const mine = ++epoch.current;
    setState(prev => ({ ...prev, loading: true, error: null }));
    try {
      const detail = await client.readFamily(familyId);
      if (!alive.current || mine !== epoch.current) return;
      setState(prev => {
        const existing = takeDraft(projectId, branchId, actor, familyId);
        // A brand-new family starts from the server head; the user's unsaved work is kept.
        const draft = existing ?? {
          ...newDraft(familyId), familyId,
          baseAssetId: detail.headAssetId, baseRevision: detail.revision,
          content: fromEntry(detail),
        };
        return { ...prev, detail, draft, loading: false, conflictCode: null };
      });
    } catch (reason) {
      if (!alive.current || mine !== epoch.current) return;
      setState(prev => ({ ...prev, loading: false, error: message(reason, '读取该 Prompt 失败。') }));
    }
  }, [client, projectId, branchId, actor]);

  const edit = useCallback((patch: Partial<DraftContent>) => {
    setState(prev => ({ ...prev, draft: editDraft(prev.draft, patch), conflictCode: null }));
  }, []);

  const startNew = useCallback(() => {
    setState(prev => ({ ...prev, detail: null, conflictCode: null,
      draft: takeDraft(projectId, branchId, actor, 'new') ?? newDraft('new') }));
  }, [projectId, branchId, actor]);

  /** Perform the write for an already-frozen snapshot. Never allocates a new request id. */
  const submit = useCallback(async (submitted: Draft) => {
    if (submitted.state !== 'SUBMITTING' || !submitted.requestId) return;
    const mine = ++epoch.current;
    const isRevision = submitted.familyId !== null && submitted.baseAssetId !== null;
    try {
      const receipt = isRevision
        ? await client.saveRevision(submitted.familyId!, {
            ...toRequest(submitted.content, submitted.requestId),
            expected_previous_asset_id: submitted.baseAssetId!,
            expected_revision: submitted.baseRevision!,
          })
        : await client.createPrompt(toRequest(submitted.content, submitted.requestId));
      if (!alive.current || mine !== epoch.current) return;
      setState(prev => ({ ...prev, draft: confirmSaved(prev.draft, receipt) }));
      // Re-read the authorised family so the panel shows server truth, not our optimism.
      await refresh();
    } catch (reason) {
      if (!alive.current || mine !== epoch.current) return;
      const conflict = reason instanceof ApiError ? readPromptConflict(reason) : null;
      setState(prev => conflict
        ? { ...prev, draft: markConflict(prev.draft, conflict.code,
            message(reason, '这个 Prompt 已被他人更新。')), conflictCode: conflict.code }
        : { ...prev, draft: markUnknown(prev.draft,
            message(reason, '保存结果未知，请稍后核对后重试。')), error: null });
    }
  }, [client, refresh]);

  const save = useCallback(() => {
    // Compute the snapshot OUTSIDE setState: a state updater is not guaranteed to run
    // synchronously, so reading a value out of it would silently skip the write.
    // Only an explicit click reaches here — nothing auto-creates or auto-revises.
    const submitted = beginSubmit(state.draft, newRequestId);
    if (submitted.state !== 'SUBMITTING' || !submitted.requestId) return;
    setState(prev => ({ ...prev, draft: submitted, error: null, conflictCode: null }));
    void submit(submitted);
  }, [state.draft, submit]);

  const retry = useCallback(() => {
    // Reuses the original request id and the original snapshot — never a new one.
    const next = retryUnknown(state.draft);
    if (next.state !== 'SUBMITTING') return;
    setState(prev => ({ ...prev, draft: next }));
    void submit(next);
  }, [state.draft, submit]);

  const rebase = useCallback(() => {
    setState(prev => {
      if (!prev.detail) return prev;
      return { ...prev, conflictCode: null,
        draft: rebaseDraft(prev.draft, {
          assetId: prev.detail.headAssetId, revision: prev.detail.revision,
          familyId: prev.detail.familyId,
        }) };
    });
  }, []);

  const discard = useCallback(() => {
    setState(prev => ({ ...prev, draft: discardDraft(prev.draft), conflictCode: null }));
  }, []);

  const compare = useCallback(async (familyId: string, fromId: string, toId: string) => {
    const mine = ++epoch.current;
    setState(prev => ({ ...prev, compare: { ...prev.compare, loading: true, error: null } }));
    try {
      const [from, to] = await Promise.all([
        client.readRevisionBody(familyId, fromId),
        client.readRevisionBody(familyId, toId),
      ]);
      if (!alive.current || mine !== epoch.current) return;
      setState(prev => ({ ...prev, compare: {
        loading: false, error: null,
        from: { assetId: fromId, revision: from.revision, body: from },
        to: { assetId: toId, revision: to.revision, body: to },
      } }));
    } catch (reason) {
      if (!alive.current || mine !== epoch.current) return;
      setState(prev => ({ ...prev, compare: {
        ...prev.compare, loading: false, error: message(reason, '无法读取该修订的正文。') } }));
    }
  }, [client]);

  return {
    state, refresh, selectFamily, startNew, edit, save, retry, rebase, discard, compare,
    locked: isInputLocked(state.draft), canSave: canSubmit(state.draft),
    scopeKey: draftScopeKey(projectId, branchId, actor),
  };
}

/** Library entry → editable content. Hand-written drafts are MANUAL and never claimed as AI. */
export function fromEntry(entry: PromptEntry): DraftContent {
  const field = (name: string): unknown => entry.fields.find(row => row.field === name)?.value;
  const asText = (value: unknown): string => (typeof value === 'string' && value !== 'UNKNOWN' ? value : '');
  const list = (values: string[]): string[] => [...values];
  return {
    text: entry.body.state === 'COMPLETE' || entry.body.state === 'TRUNCATED'
      ? (entry.body.value ?? '') : '',
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

export type PromptFieldProblem = { field: 'parameters' | 'seed'; message: string };
export type ParsedDraft = { ok: true; parameters: Record<string, unknown>; seed: number | null }
  | ({ ok: false } & PromptFieldProblem);

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
    if (!Number.isInteger(parsed) || parsed < 0) {
      return { ok: false, field: 'seed',
        message: 'Seed 必须是非负整数；当前输入已保留，未提交。' };
    }
    seed = parsed;
  }
  return { ok: true, parameters, seed };
}

/** Build the R3-W request body. `origin` defaults to MANUAL — a hand-written draft. */
function toRequest(content: DraftContent, requestId: string) {
  const parsed = parseContent(content);
  const parameters = parsed.ok ? parsed.parameters : {};
  const seed = parsed.ok ? parsed.seed : null;
  return {
    text: content.text,
    negative_prompt: content.negativePrompt,
    purpose: content.purpose,
    origin: 'MANUAL' as const,
    model_reference: content.modelReference,
    parameters,
    seed,
    character_ids: [...content.characterIds],
    scene_ids: [...content.sceneIds],
    shot_ids: [...content.shotIds],
    reference_asset_ids: [...content.referenceAssetIds],
    change_note: content.changeNote,
    change_reason: content.changeReason,
    redacted: false,
    request_id: requestId,
  };
}

export { needsRebase };
