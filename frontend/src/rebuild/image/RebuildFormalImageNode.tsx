import { useLayoutEffect, useMemo, useRef, useState, useSyncExternalStore } from 'react';
import { getCollaborationEpoch, subscribeCollaborationContext } from '../../api';
import { useStudio } from '../../store';
import { useLocalHostSession } from '../../localHostSession';
import { studioClient, type StudioOverview } from '../../creative/studioClient';
import { studioProductionClient } from '../../creative/studioProductionClient';
import { studioGraphDraftOwner } from '../../creative/studioGraphLocalDraft';
import { CanvasImageNodeTask } from '../../creative/CanvasImageNodeTask';
import { Button, StatusMessage } from '../../ui/primitives';
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
    catch (reason) { if (current()) setError(reason instanceof Error ? reason.message : '正式工作区暂不可用。'); }
    finally { running.current = false; if (alive.current) setBusy(false); }
  }
  const owner = overview && studioGraphDraftOwner(props.projectId, overview.project.incarnation, props.context, props.host);
  return <section aria-label="所选节点的正式生产与服务端保存">
    <Button disabled={busy || !!overview || !current()} onClick={() => void open()}>打开正式生成与服务端保存</Button>
    <p>仅关联这个节点的位置与正式结果。提示词、连线和其他节点仍是浏览器草稿；每一步都需单独确认。</p>
    {error && <StatusMessage tone="warning">{error}</StatusMessage>}
    {overview && !owner && <StatusMessage tone="warning">缺少可核实的项目代次或作者身份，不能建立服务端节点目标。</StatusMessage>}
    {overview && owner && <CanvasImageNodeTask projectId={props.projectId} node={{ ...props.node, prompt: props.node.prompt || '' }} client={props.client}
      production={props.production} owner={owner} canMutate={overview.capabilities.can_mutate}
      canReview={overview.capabilities.can_review === true} isCurrent={current} read={run} mutate={run} />}
  </section>;
}
