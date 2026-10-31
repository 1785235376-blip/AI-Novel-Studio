import { useLayoutEffect, useMemo, useRef, useState, useSyncExternalStore } from 'react';
import { getCollaborationEpoch, subscribeCollaborationContext } from '../../api';
import { useStudio } from '../../store';
import { useLocalHostSession } from '../../localHostSession';
import { studioClient, type StudioOverview } from '../../creative/studioClient';
import { studioProductionClient } from '../../creative/studioProductionClient';
import { studioGraphDraftOwner } from '../../creative/studioGraphLocalDraft';
import { CanvasImageNodeTask } from '../../creative/CanvasImageNodeTask';
import { Button, StatusMessage } from '../../ui/primitives';
import { ConfirmDialog } from '../../ui/ConfirmDialog';
import { useTz } from '../../i18n';
import type { CvNode } from '../canvas/RebuildCanvas';

/** One explicit selection enters the original owners; the browser graph is never uploaded. */
export function RebuildFormalImageNode(props: { projectId: string; node: CvNode; sourceRevision?: number; isSourceCurrent?: () => boolean }) {
  const state = useStudio(), host = useLocalHostSession();
  const apiEpoch = useSyncExternalStore(subscribeCollaborationContext, getCollaborationEpoch);
  const context = useMemo(() => ({ sessionToken: state.sessionToken, actor: state.actor ? { ...state.actor } : undefined,
    scope: state.scope ? { ...state.scope } : undefined, localHostToken: host.token }),
  [state.sessionToken, state.actor?.id, state.actor?.workspaceId, state.scope?.workspaceId, state.scope?.projectId,
    state.scope?.storylineId, state.scope?.branchId, host.token, host.epoch, apiEpoch]);
  const identity = JSON.stringify([props.projectId, props.node, props.sourceRevision, context, host.epoch, apiEpoch]);
  const clients = useMemo(() => ({ client: studioClient(props.projectId, context), production: studioProductionClient(props.projectId, context) }), [props.projectId, context]);
  return <FormalSelection key={identity} {...props} {...clients} context={context} host={host} epoch={apiEpoch} />;
}

function FormalSelection(props: Parameters<typeof RebuildFormalImageNode>[0] & {
  client: ReturnType<typeof studioClient>; production: ReturnType<typeof studioProductionClient>;
  context: Parameters<typeof studioClient>[1]; host: { token: string; actorId: string; epoch: number }; epoch: number;
}) {
  const [overview, setOverview] = useState<StudioOverview>(), [busy, setBusy] = useState(false), [error, setError] = useState('');
  const alive = useRef(true), retired = useRef(false), running = useRef(false), live = useRef(props); live.current = props;
  useLayoutEffect(() => {
    alive.current = true;
    const initial = useStudio.getState();
    const unsubscribe = useStudio.subscribe(state => {
      if (state.novelId !== initial.novelId || state.sessionToken !== initial.sessionToken || state.actor !== initial.actor || state.scope !== initial.scope) retired.current = true;
    });
    return () => { alive.current = false; unsubscribe(); };
  }, []);
  const current = () => alive.current && !retired.current && getCollaborationEpoch() === props.epoch
    && useLocalHostSession.getState().epoch === props.host.epoch && useStudio.getState().novelId === props.projectId
    && (live.current.isSourceCurrent?.() ?? false);
  async function run<T,>(work: () => Promise<T>): Promise<T> {
    if (!current()) throw new Error('原节点或工作区身份已改变，请取消选择后重新选择节点并打开入口。');
    const value = await work();
    if (!current()) throw new Error('原节点读取已退役；结果不会应用到新的选择。');
    return value;
  }
  async function open() {
    if (running.current || !current()) return;
    running.current = true; setBusy(true); setError('');
    try { const row = await run(() => props.client.overview()); if (current()) setOverview(row); }
    catch (reason) { if (current()) setError(reason instanceof Error ? reason.message : t('正式工作区暂不可用。')); }
    finally { running.current = false; if (alive.current) setBusy(false); }
  }
  // [HERMIA-FE-20261031 ACT] 显示条件：项目概览读取成功（200）且 entry_kind==='LEGACY'（本项目尚未启用独立工作室；
  // 未启用时制作服务会以 422 STUDIO_NEUTRAL_PROJECT_ACTIVATION_REQUIRED 拒绝）。不区分本地/远程；概览读取失败（含 422）
  // 只显示通用错误、不显示入口。入口唯一、显式、需确认；不自动启用，不在启用前挂载正式面板。
  const [askActivate, setAskActivate] = useState(false), activating = useRef(false);
  // [HERMIA-FE-20261031 VERA-P3b] 确认后入口按钮会消失或被禁用，焦点需显式交给结果（成功）或入口（失败），不落到 BODY
  const [activated, setActivated] = useState(false), t = useTz(), [focusTo, setFocusTo] = useState<'' | 'done' | 'entry'>(''), doneRef = useRef<HTMLParagraphElement>(null), entryRef = useRef<HTMLButtonElement>(null);
  useLayoutEffect(() => { if (!focusTo || busy) return; (focusTo === 'done' ? doneRef : entryRef).current?.focus(); setFocusTo(''); }, [focusTo, busy]);
  async function activate() {
    if (activating.current || !current()) return;
    activating.current = true; setBusy(true); setError(''); setAskActivate(false);
    try {
      await run(() => props.client.activate());
      const row = await run(() => props.client.overview()); if (current()) { setOverview(row); setActivated(true); setFocusTo('done'); }
    } catch (reason) { if (current()) { setError(`${t('启用失败：')}${reason instanceof Error ? reason.message : t('请稍后重试。')}`); setFocusTo('entry'); } }
    finally { activating.current = false; if (alive.current) setBusy(false); }
  }
  const legacy = overview?.project.entry_kind === 'LEGACY';
  const owner = !legacy && overview && studioGraphDraftOwner(props.projectId, overview.project.incarnation, props.context, props.host);
  return <section aria-label={t('所选节点的正式生产与服务端保存')}>
    <Button disabled={busy || !!overview || !current()} onClick={() => void open()}>{t('打开正式生成与服务端保存')}</Button>
    <p>{t('仅关联这个节点的位置与正式结果。提示词、连线和其他节点仍是浏览器草稿；每一步都需单独确认。')}</p>
    {error && <StatusMessage tone="warning">{error}</StatusMessage>}
    {legacy && <div data-studio-activation="required">
      <StatusMessage tone="warning">{t('项目概览显示这个项目还没启用独立工作室；正式生成需要先启用。')}</StatusMessage>
      <Button ref={entryRef} disabled={busy || !current()} onClick={() => setAskActivate(true)}>{t('启用独立工作室…')}</Button>
    </div>}
    {askActivate && <ConfirmDialog title={t('为这个项目启用独立工作室？')} confirmLabel={t('确认启用')} cancelLabel={t('取消')} initialFocus="cancel"
      onConfirm={() => void activate()} onCancel={() => setAskActivate(false)}>
      <p>{t('只在服务端保存一条「独立工作室入口」记录，让图片、视频、音频等正式生产可以使用。不会改动正文、章节、权限或项目类型，也不会生成、执行或采用任何内容。')}</p>
      <p>{t('启用后，图片仍在当前图片页里使用正式节点；视频、音频、剪辑和资产页会改用工作室界面。目前界面里没有撤销入口。')}</p>
    </ConfirmDialog>}
    {activated && !legacy && <p ref={doneRef} tabIndex={-1} role="status" data-studio-activation="done">{t('已启用独立工作室。下面是此节点的正式任务，每一步仍需单独确认。')}</p>}
    {overview && !legacy && !owner && <StatusMessage tone="warning">{t('缺少可核实的项目代次或作者身份，不能建立服务端节点目标。')}</StatusMessage>}
    {overview && owner && <CanvasImageNodeTask projectId={props.projectId} node={{ ...props.node, prompt: props.node.prompt || '' }} client={props.client}
      production={props.production} owner={owner} canMutate={overview.capabilities.can_mutate}
      canReview={overview.capabilities.can_review === true} isCurrent={current} read={run} mutate={run} />}
  </section>;
}
