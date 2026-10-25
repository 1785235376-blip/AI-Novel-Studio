import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { ApiError } from '../api';
import { PRODUCTION_QUERY_OPERATIONS, type MediaOperation, type ProductionJobPaging, type ProductionQueryOperation, type StudioProductionClient } from '../creative/studioProductionClient';
import { MEDIA_OPERATION_LABELS, MEDIA_STATUS_LABELS } from '../creative/useStudioMediaExecution';
import { Badge, Button, EmptyState, Panel, StatusMessage } from '../ui/primitives';
import { exactStudioProductionTask, studioProductionTaskRows, type StudioProductionTask } from './studioProductionTask';
import './taskCenter.css';

export type StudioProductionTasksProps = {
  projectId: string; branchId: string | null; identity: string;
  client: Pick<StudioProductionClient, 'list' | 'get'> & Partial<Pick<StudioProductionClient, 'listPage'>>;
  active: boolean; denied: boolean; busy: boolean; isBusy?: () => boolean; isCurrent: () => boolean;
  read: <T>(work: () => Promise<T>, signal?: AbortSignal) => Promise<T>;
  /** The host rechecks the lease if its existing dirty-navigation confirmation delays opening. */
  onOpen: (job: StudioProductionTask, isSelectionCurrent: () => boolean) => void;
  onUnavailable: () => void;
};
type View = { generation: number; rows?: StudioProductionTask[]; message?: string; denied?: boolean;
  /** [HERMIA-FE-CONTRACTS G-AUD-1] 仅在明确选择筛选后存在；loaded=已读取条数，total=本次读取匹配数。 */
  paging?: ProductionJobPaging | null; loaded?: number };
type Filter = { owner: '' | 'image' | 'video'; operation: '' | ProductionQueryOperation };
const NO_FILTER: Filter = { owner: '', operation: '' };
const PAGE_SIZE = 50;
type Request = { generation: number; ticket: number; controller: AbortController; kind: 'LIST' | 'GET' };

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
    running.current = request; setPending(request);
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
  const [filter, setFilter] = useState<Filter>(NO_FILTER);
  const filterRef = useRef(filter);
  async function load(nextFilter: Filter = filterRef.current, more = false) {
    if (generation !== scope.current.generation || renderTicket !== ticket.current) return;
    const origin = latest.current, previous = visibleSnapshot.current;
    const filtered = !!(nextFilter.owner || nextFilter.operation) && !!origin.client.listPage;
    const offset = more && previous?.paging?.has_more ? previous.loaded ?? 0 : 0;
    if (more && (!filtered || !previous?.paging?.has_more)) return;
    const request = begin('LIST'); if (!request) return;
    filterRef.current = nextFilter; setFilter(nextFilter);
    if (!more) show(undefined);
    try {
      if (!filtered) {
        // 无筛选：与原来完全一致的未分页读取。
        const jobs = await origin.read(() => origin.client.list(request.controller.signal), request.controller.signal);
        if (!valid(request)) return;
        show({ generation: request.generation, rows: studioProductionTaskRows(jobs, origin.projectId, origin.branchId) });
        return;
      }
      const page = await origin.read(() => origin.client.listPage!({ ...(nextFilter.owner ? { owner: nextFilter.owner } : {}),
        ...(nextFilter.operation ? { operation_id: nextFilter.operation } : {}), limit: PAGE_SIZE, offset }, request.controller.signal), request.controller.signal);
      if (!valid(request)) return;
      const fresh = studioProductionTaskRows(page.items, origin.projectId, origin.branchId);
      const kept = more ? previous?.rows ?? [] : [];
      const seen = new Set(kept.map(row => `${row.owner}:${row.id}`));
      const rows = [...kept, ...fresh.filter(row => !seen.has(`${row.owner}:${row.id}`))];
      show({ generation: request.generation, rows, paging: page.paging, loaded: offset + page.items.length });
    } catch (reason) {
      if (more && valid(request)) { show({ ...previous!, message: '下一页读取失败，已显示的任务保持不变。可以再点一次「加载更多制作任务」；不会自动重试。' }); return; }
      failure(request, reason);
    }
    finally { finish(request); }
  }
  async function open(selected: StudioProductionTask) {
    if (renderTicket !== ticket.current || view !== visibleSnapshot.current
      || view?.generation !== scope.current.generation || !view.rows?.includes(selected)) return;
    const request = begin('GET'); if (!request) return;
    const origin = latest.current, expected = structuredClone(selected);
    try {
      const result = await origin.read(() => origin.client.get(expected.owner, expected.id, request.controller.signal), request.controller.signal);
      if (!valid(request)) return;
      const exact = exactStudioProductionTask(result, expected, origin.projectId, origin.branchId);
      if (valid(request)) origin.onOpen(exact, () => valid(request));
    } catch (reason) { failure(request, reason); }
    finally { finish(request); }
  }
  useLayoutEffect(() => {
    alive.current = true;
    return () => { alive.current = false; running.current?.controller.abort(); running.current = undefined; };
  }, []);
  useLayoutEffect(() => {
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
    {props.client.listPage && <div className="task-center-filters" data-testid="prod-filters">
      <label>任务类型<select aria-label="任务类型" value={filter.owner} disabled={blocked || !!waiting}
        onChange={event => void load({ owner: event.target.value as Filter['owner'], operation: '' })}>
        <option value="">全部（图片与视频）</option><option value="image">图片</option><option value="video">视频</option>
      </select></label>
      <label>具体操作<select aria-label="具体操作" value={filter.operation} disabled={blocked || !!waiting}
        onChange={event => void load({ ...filter, operation: event.target.value as Filter['operation'] })}>
        <option value="">全部操作</option>
        {PRODUCTION_QUERY_OPERATIONS.filter(op => filter.owner === 'image' ? op.startsWith('m5.') : filter.owner === 'video' ? op.startsWith('m7.') : op.startsWith('m5.') || op.startsWith('m7.'))
          .map(op => <option key={op} value={op}>{MEDIA_OPERATION_LABELS[op as MediaOperation] ?? op}</option>)}
      </select></label>
    </div>}
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
      </article>
    </li>)}</ul>}
    {visible?.paging && <div className="task-center-paging" data-testid="prod-paging">
      <p>已加载 {visible.loaded ?? 0} 条 · 本次读取匹配 {visible.paging.total} 条（只是这次读取的匹配数，不是全部任务总数）</p>
      {visible.paging.has_more
        ? <Button disabled={blocked || !!waiting} onClick={() => void load(filterRef.current, true)}>加载更多制作任务</Button>
        : <p className="novel-help">这次读取范围内没有下一页；翻页期间任务增减可能让结果变化，需要时请重新读取。</p>}
    </div>}
    {visible && visible.paging === null && <p className="novel-help" data-testid="prod-paging-fallback">当前服务未返回分页信息，已按原方式显示读取结果。</p>}
  </Panel>;
}
