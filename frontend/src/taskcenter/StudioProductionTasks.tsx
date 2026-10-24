import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { ApiError } from '../api';
import type { MediaOperation, StudioProductionClient } from '../creative/studioProductionClient';
import { MEDIA_OPERATION_LABELS, MEDIA_STATUS_LABELS } from '../creative/useStudioMediaExecution';
import { Badge, Button, EmptyState, Panel, StatusMessage } from '../ui/primitives';
import { exactStudioProductionTask, studioProductionTaskRows, type StudioProductionTask } from './studioProductionTask';
import './taskCenter.css';

export type StudioProductionTasksProps = {
  projectId: string; branchId: string | null; identity: string;
  client: Pick<StudioProductionClient, 'list' | 'get'>;
  active: boolean; denied: boolean; busy: boolean; isBusy?: () => boolean; isCurrent: () => boolean;
  read: <T>(work: () => Promise<T>, signal?: AbortSignal) => Promise<T>;
  /** The host rechecks the lease if its existing dirty-navigation confirmation delays opening. */
  onOpen: (job: StudioProductionTask, isSelectionCurrent: () => boolean) => void;
  /** Selection only; the protected observation owner must verify it before displaying a result. */
  onInspectCanvasTarget?: (job: StudioProductionTask, isSelectionCurrent: () => boolean) => void;
  onInspectImageNodeJob?: (job: StudioProductionTask, isSelectionCurrent: () => boolean) => void;
  onPrepareImageNodeDiscard?: (job: StudioProductionTask, isSelectionCurrent: () => boolean) => void;
  canPrepareImageNodeDiscard?: boolean;
  /** Retire a sibling metadata view immediately when this exact selection changes. */
  onSelectionRetired?: () => void;
  onUnavailable: () => void;
};
type View = { generation: number; rows?: StudioProductionTask[]; message?: string; denied?: boolean };
type Request = { generation: number; ticket: number; controller: AbortController; kind: 'LIST' | 'GET' | 'TARGET' | 'DETAIL' | 'DISCARD' };

/** Read-only projection of the original Studio production owner. No queue or action owner. */
export function StudioProductionTasksPanel(props: StudioProductionTasksProps) {
  const current = props.isCurrent();
  const key = JSON.stringify([props.projectId, props.branchId, props.identity, props.active, props.denied, props.busy, current]);
  const scope = useRef({ key, client: props.client, generation: 0 });
  if (scope.current.key !== key || scope.current.client !== props.client) {
    scope.current = { key, client: props.client, generation: scope.current.generation + 1 };
  }
  const latest = useRef(props); latest.current = props;
  const alive = useRef(false), revoked = useRef(false), ticket = useRef(0), running = useRef<Request>();
  const [view, setView] = useState<View>(), [pending, setPending] = useState<Request>();
  const visibleSnapshot = useRef<View>();
  const generation = scope.current.generation, renderTicket = ticket.current;
  function show(value: View | undefined) { visibleSnapshot.current = value; setView(value); }
  const available = () => alive.current && !revoked.current && latest.current.active && !latest.current.denied
    && !latest.current.busy && !latest.current.isBusy?.() && latest.current.isCurrent();
  function begin(kind: Request['kind']) {
    if (!available() || running.current) return;
    const request = { generation: scope.current.generation, ticket: ++ticket.current, controller: new AbortController(), kind };
    running.current = request; latest.current.onSelectionRetired?.(); setPending(request);
    return request;
  }
  const valid = (request: Request) => available() && !request.controller.signal.aborted
    && request.generation === scope.current.generation && request.ticket === ticket.current;
  function finish(request: Request) {
    if (running.current !== request) return;
    running.current = undefined;
    if (alive.current) setPending(undefined);
  }
  function failure(request: Request, reason: unknown) {
    if (!valid(request)) return;
    const denied = reason instanceof ApiError && [401, 403].includes(reason.status);
    if (denied) revoked.current = true;
    const message = denied ? '原 Studio 制作服务拒绝读取，请重新核对项目与身份。'
      : reason instanceof ApiError && reason.problem.code === 'STUDIO_TASK_RECEIPT_CHANGED'
        ? '所选制作回执已变化，未用最新版本替代。请重新读取列表后明确选择。'
        : reason instanceof ApiError && reason.status === 404
          ? '所选原制作任务已移除或当前不可读。请重新读取列表核对。'
          : '原 Studio 制作回执读取失败或无效。请明确重新读取；不会自动重试。';
    // A failed open never leaves the old selection available for another handoff.
    show({ generation: request.generation, message, denied });
    if (denied) latest.current.onUnavailable();
  }
  async function load() {
    if (generation !== scope.current.generation || renderTicket !== ticket.current) return;
    const request = begin('LIST'); if (!request) return;
    const origin = latest.current;
    show(undefined);
    try {
      const jobs = await origin.read(() => origin.client.list(request.controller.signal), request.controller.signal);
      if (!valid(request)) return;
      const rows = studioProductionTaskRows(jobs, origin.projectId, origin.branchId);
      show({ generation: request.generation, rows });
    } catch (reason) { failure(request, reason); }
    finally { finish(request); }
  }
  const hasCanvasTarget = (job: StudioProductionTask) => job.owner === 'image' && job.operation_id === 'm5.image.t2i'
    && !!job.command && Object.hasOwn(job.command, 'canvas_image_node');
  const discardEligible = (job: StudioProductionTask) => hasCanvasTarget(job) && job.status === 'QUEUED'
    && (job as StudioProductionTask & { attempt?: unknown }).attempt === 0 && job.output_candidate === null
    && job.receipt_digest === null && job.approved_asset_version === null;
  async function open(selected: StudioProductionTask) {
    if (renderTicket !== ticket.current || view !== visibleSnapshot.current
      || view?.generation !== scope.current.generation || !view.rows?.includes(selected)) return;
    const request = begin('GET'); if (!request) return;
    const origin = latest.current, expected = structuredClone(selected);
    try {
      const result = await origin.read(() => {
        if (!valid(request)) throw new DOMException('原任务读取入口已退役。', 'AbortError');
        return origin.client.get(expected.owner, expected.id, request.controller.signal);
      }, request.controller.signal);
      if (!valid(request)) return;
      const exact = exactStudioProductionTask(result, expected, origin.projectId, origin.branchId);
      if (valid(request)) origin.onOpen(exact, () => valid(request));
    } catch (reason) { failure(request, reason); }
    finally { finish(request); }
  }
  function inspectTarget(selected: StudioProductionTask) {
    if (renderTicket !== ticket.current || view !== visibleSnapshot.current
      || view?.generation !== scope.current.generation || !view.rows?.includes(selected)
      || !latest.current.onInspectCanvasTarget || !hasCanvasTarget(selected)) return;
    const request = begin('TARGET'); if (!request) return;
    // Capture a selection only. The protected original-owner observation POST
    // performs fresh verification; an ordinary GET here could provision a marker.
    const origin = latest.current, expected = structuredClone(selected);
    try { if (valid(request)) origin.onInspectCanvasTarget?.(expected, () => valid(request)); }
    catch (reason) { latest.current.onSelectionRetired?.(); failure(request, reason); }
    finally { finish(request); }
  }
  function inspectImageNodeJob(selected: StudioProductionTask) {
    if (renderTicket !== ticket.current || view !== visibleSnapshot.current
      || view?.generation !== scope.current.generation || !view.rows?.includes(selected)
      || !latest.current.onInspectImageNodeJob || !hasCanvasTarget(selected)) return;
    const request = begin('DETAIL'); if (!request) return;
    // This selection grants no authority. Only the protected Job-only POST
    // may verify it, without ordinary GET or any Canvas-dependent read.
    const origin = latest.current, expected = structuredClone(selected);
    try { if (valid(request)) origin.onInspectImageNodeJob?.(expected, () => valid(request)); }
    catch (reason) { latest.current.onSelectionRetired?.(); failure(request, reason); }
    finally { finish(request); }
  }
  function prepareImageNodeDiscard(selected: StudioProductionTask) {
    if (renderTicket !== ticket.current || view !== visibleSnapshot.current
      || view?.generation !== scope.current.generation || !view.rows?.includes(selected)
      || !latest.current.onPrepareImageNodeDiscard || latest.current.canPrepareImageNodeDiscard !== true || !discardEligible(selected)) return;
    const request = begin('DISCARD'); if (!request) return;
    const origin = latest.current, expected = structuredClone(selected);
    // Preparing performs no mutation or ordinary GET. A separate protected
    // read and explicit confirmation are required in the dedicated consumer.
    try { if (valid(request)) origin.onPrepareImageNodeDiscard?.(expected, () => valid(request)); }
    catch (reason) { latest.current.onSelectionRetired?.(); failure(request, reason); }
    finally { finish(request); }
  }
  useLayoutEffect(() => {
    alive.current = true;
    return () => { alive.current = false; running.current?.controller.abort(); running.current = undefined; latest.current.onSelectionRetired?.(); };
  }, []);
  useLayoutEffect(() => {
    latest.current.onSelectionRetired?.();
    const request = running.current;
    if (request && request.generation !== generation) { request.controller.abort(); running.current = undefined; setPending(undefined); }
  }, [generation]);
  useEffect(() => {
    // StrictMode mount rehearsal must not strand an aborted initial read.
    let cancelled = false;
    queueMicrotask(() => { if (!cancelled) void load(); });
    return () => { cancelled = true; };
  }, []);

  const visible = view?.generation === generation && current && props.active && !props.denied ? view : undefined;
  const blocked = !current || !props.active || props.denied || props.busy || !!props.isBusy?.() || revoked.current;
  const waiting = pending?.generation === generation ? pending : undefined;
  return <Panel title="Studio 图片与视频任务" aria-label="Studio 图片与视频任务" className="task-center"
    actions={<Button disabled={blocked || !!waiting} loading={waiting?.kind === 'LIST'} onClick={() => void load()}>重新读取 Studio 制作任务</Button>}>
    <p>读取当前项目的原图片、视频制作回执。打开会先核对所选版本，再进入原制作面板；不会执行任务、审核候选或替换制作输入。</p>
    {waiting && <StatusMessage>{waiting.kind === 'LIST' ? '正在读取原 Studio 制作任务…' : '正在核对所选原制作回执…'}</StatusMessage>}
    {visible?.message && <StatusMessage tone={visible.denied ? 'warning' : 'error'}>{visible.message}</StatusMessage>}
    {(props.denied || !current) && <StatusMessage tone="warning">当前项目或身份不可用，先前制作回执已隐藏。</StatusMessage>}
    {!visible && !waiting && !blocked && <EmptyState title="尚未读取 Studio 制作任务" detail="请明确重新读取当前项目；读取不会创建或执行任务。" />}
    {visible?.rows?.length === 0 && <EmptyState title="当前项目没有图片或视频制作任务" detail="原 Studio 服务返回的记录中没有可显示的图片、视频任务。" />}
    {!!visible?.rows?.length && <ul className="task-center-list">{visible.rows.map(job => <li key={`${job.owner}:${job.id}`}>
      <article className="task-center-task" aria-label={`Studio ${job.owner} ${job.id}`}>
        <header><h4>{MEDIA_OPERATION_LABELS[job.operation_id as MediaOperation]}</h4><Badge>{MEDIA_STATUS_LABELS[job.status]}</Badge></header>
        <dl>
          <div><dt>原任务</dt><dd className="task-center-task__code">{job.owner === 'image' ? '图片' : '视频'} · {job.id} · v{job.version}</dd></div>
          <div><dt>原请求摘要</dt><dd className="task-center-task__code">{job.request_digest}</dd></div>
        </dl>
        {job.remote_compute_may_continue && <StatusMessage tone="warning">原服务提示远端计算可能仍在继续；本地状态不代表远端已经停止。</StatusMessage>}
        <Button disabled={blocked || !!waiting} onClick={() => void open(job)} aria-label={`打开原制作任务 ${job.id} v${job.version}`}>打开原制作任务</Button>
        {props.onInspectCanvasTarget && hasCanvasTarget(job) && <Button disabled={blocked || !!waiting} onClick={() => inspectTarget(job)}
          aria-label={`核对原保存位置 ${job.id} v${job.version}`}>核对原保存位置</Button>}
        {props.onInspectImageNodeJob && hasCanvasTarget(job) && <Button disabled={blocked || !!waiting} onClick={() => inspectImageNodeJob(job)}
          aria-label={`只读查看原节点任务 ${job.id} v${job.version}`}>只读查看原节点任务</Button>}
        {props.onPrepareImageNodeDiscard && discardEligible(job) && <Button disabled={blocked || !!waiting || props.canPrepareImageNodeDiscard !== true}
          onClick={() => prepareImageNodeDiscard(job)} aria-label={`放弃此排队任务的本地采用 ${job.id} v${job.version}`}>放弃此排队任务的本地采用</Button>}
      </article>
    </li>)}</ul>}
  </Panel>;
}
