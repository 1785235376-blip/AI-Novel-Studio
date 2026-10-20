/**
 * UX-05 控制器。
 *
 * 只有三件事：按需读取（没有任何轮询定时器）、镜头选择（列表与详情共用同一个
 * `selectedShotId`）、以及**本地**显示顺序草稿。它没有执行器、没有队列，也不写
 * 原文档：重排只把结果留在内存里，并明确标成"尚未保存"。
 *
 * 读取失败永远不会变成"暂无分镜"：`FAILED` 与 `EMPTY` 是两个不同的状态。
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ApiError, apiErrorView } from '../api';
import type { CreativeDocument } from '../creative/types';
import { directorGoalView, directorProposalSuggestion } from './storyboardWorkspaceContract';
import {
  bindDraftToReceipt, continuityOf, neighbourOf, orderDraft as orderDraftView, orderShots, renumberShots,
  sendToDraft, shotSummary, sourceStaleness, toSendToDraft, type ShotMoveInput, type ShotStalenessFacts,
} from './storyboardOps';
import {
  STORYBOARD_WORKSPACE_ERROR_CODES,
  type BoundShotTargetDraft, type DirectorGoal, type DirectorProposalStatus, type DirectorVisualTargetValue,
  type SendTarget, type ShotOrderDraft, type ShotTargetDraft, type StoryboardProblem,
  type StoryboardShot, type StoryboardShotRow, type StoryboardSurfaceState,
  type StoryboardWorkspaceClient,
} from './storyboardWorkspaceTypes';
import type { ShotPin, StoryboardReceipt } from '../creative/studioStoryboardContract';

const { readFailed } = STORYBOARD_WORKSPACE_ERROR_CODES;

export type StoryboardWorkspaceControllerProps = {
  /** 稳定工作区/分支身份；变化会丢弃此前读到的一切。 */
  identity: string;
  /** 视图在屏幕上。不可见时永不发起读取。 */
  active: boolean;
  denied: boolean;
  busy: boolean;
  isCurrent: () => boolean;
  /** 原工作区的共享只读闸门。 */
  read: <T>(work: () => Promise<T>) => Promise<T>;
  client: StoryboardWorkspaceClient;
  /** 要读的分镜文档；缺省时回退到身份里的 `project|document` 组合。 */
  documentId?: string;
  /** 导演文档。只有调用方明确知道时才读，这里绝不猜。 */
  directorDocumentId?: string | null;
  /** 原 `GET /documents/{rid}`；没有提供就不读导演文档。 */
  getDocument?: (documentId: string, signal?: AbortSignal) => Promise<CreativeDocument>;
  /** 原 `GET /director-proposals`；没有提供就不读待审建议。 */
  listProposals?: (signal?: AbortSignal) => Promise<{ items: unknown[] }>;
  onUnavailable?: () => void;
};

/** 待审建议在界面上只以"建议"形式出现：这里连备注正文都不暴露。 */
export type StoryboardProposalView = {
  id: string; status: DirectorProposalStatus; output_digest: string | null;
  quality_verification: 'HUMAN_REVIEW_REQUIRED' | null; model_called: boolean;
  visual_target: DirectorVisualTargetValue | null; note_count: number;
};

function problemOf(reason: unknown, fallback: string, fallbackCode: string): StoryboardProblem {
  // 只渲染传输层自己的有界文案；本地异常绝不原样回显。
  return reason instanceof ApiError
    ? { code: reason.problem.code, message: apiErrorView(reason, fallback).message }
    : { code: fallbackCode, message: fallback };
}

const READ_FAILURE = '分镜读取失败。这里不会显示"暂无分镜"；请重新读取原文档核对。';

const surfaceOf = (items: number, unavailable: number): StoryboardSurfaceState =>
  items > 0 ? 'READY' : unavailable > 0 ? 'DENIED' : 'EMPTY';

/** 身份允许是 `projectId|documentId`：前半段是项目，后半段是文档。 */
function identityParts(identity: string): { project: string; document: string } {
  const index = identity.indexOf('|');
  return index < 0 ? { project: identity, document: '' } : { project: identity.slice(0, index), document: identity.slice(index + 1) };
}

export function useStoryboardWorkspace(props: StoryboardWorkspaceControllerProps) {
  const [receipt, setReceipt] = useState<StoryboardReceipt>();
  const [document, setDocument] = useState<CreativeDocument>();
  const [goals, setGoals] = useState<DirectorGoal[]>([]);
  const [visualTarget, setVisualTarget] = useState<DirectorVisualTargetValue | null>(null);
  const [proposals, setProposals] = useState<StoryboardProposalView[]>([]);
  const [state, setState] = useState<StoryboardSurfaceState>('IDLE');
  const [problem, setProblem] = useState<StoryboardProblem>();
  const [selectedShotId, setSelectedShotId] = useState('');
  const [moves, setMoves] = useState<ShotMoveInput[]>([]);
  const [notice, setNotice] = useState('');
  const [loading, setLoading] = useState(false);

  const alive = useRef(true), epoch = useRef(0), revoked = useRef(false), running = useRef(false);
  const abort = useRef<AbortController>();
  const loadedFor = useRef('');
  const latest = useRef(props);
  latest.current = props;

  useEffect(() => {
    alive.current = true;
    return () => { alive.current = false; epoch.current++; abort.current?.abort(); };
  }, []);

  const admit = useCallback(() => alive.current && !revoked.current && latest.current.active
    && !latest.current.denied && latest.current.isCurrent(), []);

  const revoke = useCallback(() => {
    revoked.current = true;
    setReceipt(undefined); setDocument(undefined); setGoals([]); setVisualTarget(null);
    setProposals([]); setSelectedShotId(''); setMoves([]); setNotice('');
    setProblem(undefined); setState('DENIED');
    latest.current.onUnavailable?.();
  }, []);

  const load = useCallback(async () => {
    const captured = latest.current;
    const identity = captured.identity;
    if (!admit() || running.current || captured.busy) return;
    const documentId = captured.documentId ?? identityParts(identity).document;
    if (!documentId) {
      setProblem({ code: readFailed, message: '还没有选择要读取的分镜文档。' });
      setState('FAILED');
      return;
    }
    const controller = new AbortController();
    abort.current?.abort(); abort.current = controller;
    const request = ++epoch.current;
    running.current = true; setLoading(true); setProblem(undefined); setState('LOADING');
    try {
      const next = await captured.read(() => captured.client.readStoryboard(documentId, controller.signal));
      if (request !== epoch.current || !admit()) return;
      setReceipt(next); setMoves([]);
      setSelectedShotId(next.shots[0]?.shot_id ?? '');
      setState(surfaceOf(next.shots.length, 0));
      setNotice('');
      // 导演文档与待审建议是**次要**读取：失败只影响那一张卡，绝不影响分镜事实。
      const directorId = captured.directorDocumentId
        ?? (next.director_sources.length === 1 ? next.director_sources[0].id : undefined);
      setGoals([]); setVisualTarget(null); setProposals([]); setDocument(undefined);
      if (directorId && captured.getDocument) {
        try {
          const raw = await captured.getDocument(directorId, controller.signal);
          if (request !== epoch.current || !admit()) return;
          const view = directorGoalView(raw as unknown as Record<string, unknown>,
            identityParts(identity).project, directorId, null);
          setDocument(raw); setGoals(view.goals); setVisualTarget(view.visual_target);
          if (captured.listProposals) {
            const listed = await captured.listProposals(controller.signal);
            if (request !== epoch.current || !admit()) return;
            setProposals(listed.items
              .filter((item): item is Record<string, unknown> =>
                (item as { source_document_id?: unknown })?.source_document_id === directorId)
              .map<StoryboardProposalView>(item => {
                const suggestion = directorProposalSuggestion(item, directorId);
                return {
                  id: suggestion.id, status: suggestion.status, output_digest: suggestion.output_digest,
                  quality_verification: suggestion.quality_verification, model_called: suggestion.model_called,
                  visual_target: suggestion.visual_target, note_count: suggestion.notes.length,
                };
              }));
          }
        } catch { /* 导演目标读取失败：分镜状态保持不变，目标区显示"未读取"。 */ }
      }
    } catch (reason) {
      if (request !== epoch.current || controller.signal.aborted || !alive.current) return;
      if (reason instanceof ApiError && [401, 403].includes(reason.status)) { revoke(); return; }
      setProblem(problemOf(reason, READ_FAILURE, readFailed));
      setState('FAILED');
    } finally {
      if (request === epoch.current) { running.current = false; if (alive.current) setLoading(false); }
    }
  }, [admit, revoke]);

  useEffect(() => {
    epoch.current++; abort.current?.abort(); running.current = false;
    revoked.current = props.denied;
    setReceipt(undefined); setDocument(undefined); setGoals([]); setVisualTarget(null);
    setProposals([]); setSelectedShotId(''); setMoves([]); setNotice(''); setProblem(undefined);
    setState(props.denied ? 'DENIED' : 'IDLE');
    loadedFor.current = '';
  }, [props.identity, props.denied]);

  // 按需读取：身份第一次出现且视图可见时读一次；没有任何轮询定时器。
  useEffect(() => {
    if (!props.active || props.denied) return;
    if (loadedFor.current === props.identity) return;
    loadedFor.current = props.identity;
    void load();
  }, [props.active, props.denied, props.identity, load]);

  const orderState = useMemo(() => (receipt ? orderShots(receipt.shots, moves) : undefined), [receipt, moves]);
  const displayShots = useMemo<StoryboardShot[]>(
    () => (receipt && orderState ? renumberShots(receipt.shots, orderState) : []),
    [receipt, orderState],
  );
  /**
   * 来源陈旧性只由 owner 记下的版本针对比我们真实读到的版本。
   * 导演文档读不到时，它就是一个"读不到"的证据，而不是一句"没问题"。
   * 返回的永远是对象（即使没有上游来源）：否则"已绑定视频来自快门版本"这类
   * 只依赖镜头自身的证据也会被漏掉。
   */
  const stalenessFacts = useMemo<ShotStalenessFacts>(() => {
    const sources: Record<string, { version: number; digest: string }> = {};
    for (const source of receipt?.director_sources ?? []) {
      sources[source.id] = { version: source.version, digest: source.digest };
    }
    const knownDocuments: Record<string, { version: number; digest: string }> = {};
    // 只有"回执自己声明的那份上游文档"才参与比较；别的文档不猜。
    if (document && Object.hasOwn(sources, document.id)) {
      knownDocuments[document.id] = { version: document.version, digest: sources[document.id].digest };
    }
    return { sources, knownDocuments };
  }, [receipt, document]);
  const rows = useMemo<StoryboardShotRow[]>(
    () => displayShots.map(shot => {
      const staleness = sourceStaleness(shot, stalenessFacts);
      return { shot, summary: { ...shotSummary(shot), staleness }, staleness };
    }),
    [displayShots, stalenessFacts],
  );
  const orderDraft: ShotOrderDraft | undefined = useMemo(
    () => (receipt && orderState ? orderDraftView(receipt.shots, orderState) : undefined),
    [receipt, orderState],
  );
  const selected = useMemo(() => rows.find(row => row.shot.shot_id === selectedShotId), [rows, selectedShotId]);
  const selectedShot: StoryboardShot | undefined = selected?.shot;
  const selectedGoal = useMemo(
    () => (selectedShot ? goals.find(goal => (selectedShot.shot.director_note_ids ?? []).includes(goal.note_id)) : undefined),
    [goals, selectedShot],
  );

  const canRead = state === 'READY' || state === 'EMPTY';
  const locked = !admit() || props.busy || loading;

  const chooseShot = useCallback((shotId: string) => {
    if (!alive.current || !latest.current.active || latest.current.denied) return;
    setSelectedShotId(shotId);
  }, []);

  /** 本地顺序草稿：只改内存。 */
  const reorder = useCallback((next: readonly ShotMoveInput[]) => {
    if (!alive.current || !latest.current.active || latest.current.denied) return;
    try { setMoves([...next]); setNotice(''); }
    catch (reason) { setNotice(problemOf(reason, '顺序调整无效。', STORYBOARD_WORKSPACE_ERROR_CODES.orderLocalInvalid).message); }
  }, []);

  const resetOrder = useCallback(() => {
    if (!alive.current) return;
    setMoves([]);
    setNotice('显示顺序草稿已重置为原文档顺序（没有写入任何内容）。');
  }, []);

  const clearNotice = useCallback(() => { if (alive.current) setNotice(''); }, []);
  const toast = useCallback((message: string) => { if (alive.current) setNotice(message); }, []);

  /**
   * 形成草稿。只产出卡片：不写回文档、不入队、不调用模型。
   * 文档版本来自已核对的原回执；不一致就报错，不猜。
   */
  const prepareDraft = useCallback((target: SendTarget): BoundShotTargetDraft | null => {
    if (!receipt || !selectedShot || !admit() || loading || props.busy) return null;
    try {
      const draft: ShotTargetDraft = sendToDraft(target, selectedShot);
      const bound = bindDraftToReceipt(draft, receipt, displayShots.map(row => row.shot_id));
      setNotice(`${target} 草稿已形成：只引用列出的原版本，尚未保存或派发。`);
      return bound;
    } catch (reason) {
      setNotice(problemOf(reason, '无法形成草稿，请重新读取原分镜。', STORYBOARD_WORKSPACE_ERROR_CODES.sendLocalInvalid).message);
      return null;
    }
  }, [admit, displayShots, loading, props.busy, receipt, selectedShot]);

  /** 当前显示顺序对应的原版本针；交给原界面去保存时使用，本工作区自己不保存。 */
  const pinsForOrder = useCallback((): ShotPin[] => {
    if (!receipt || !orderState) return [];
    return renumberShots(receipt.shots, orderState).map(shot => ({
      document_snapshot: receipt.document_snapshot, shot_id: shot.shot_id,
      shot_version: shot.shot_version, shot_digest: shot.shot_digest,
    }));
  }, [orderState, receipt]);

  const neighboursOf = useCallback((direction: 'PREVIOUS' | 'NEXT') => {
    if (!selectedShot) return { neighbour: null, declared: null } as const;
    return {
      neighbour: neighbourOf(displayShots, selectedShot.shot_id, direction),
      declared: continuityOf(selectedShot, direction),
    };
  }, [displayShots, selectedShot]);

  return {
    receipt, document, goals, visualTarget, proposals,
    rows, displayShots, selected, selectedShot, selectedGoal, selectedShotId,
    orderDraft, moves, pinsForOrder,
    state, problem, loading, notice, locked, canRead,
    load, chooseShot, reorder, resetOrder, clearNotice, toast,
    prepareDraft, neighboursOf, toSendToDraft,
    /** 顺序草稿永远只在本地：本工作区没有原分镜的写入口。 */
    orderIsLocalOnly: true as const,
  };
}

export type StoryboardWorkspaceController = ReturnType<typeof useStoryboardWorkspace>;
