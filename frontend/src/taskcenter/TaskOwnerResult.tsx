import { useEffect, useRef, useState } from 'react';
import { ApiError, type CollaborationContext } from '../api';
import type { StudioGraphTransport } from '../creative/studioGraphClient';
import { Button, Panel, StatusMessage } from '../ui/primitives';
import type { TaskCenterNavigationTarget } from './taskCenterTypes';

/** These are routes already owned by experimental MediaService, not Studio jobs. */
export function mediaOwnerRoute(target: TaskCenterNavigationTarget): 'tasks' | 'proposals' | null {
  if (target.queue === 'REVIEW') return target.domain === 'media' && Number.isSafeInteger(target.version) && target.version > 0 ? 'proposals' : null;
  const source = target.source;
  return target.authority === 'media' && target.feature === 'cover_storyboard_generation'
    && source?.kind === 'feature' && source.task_authority === 'media'
    && source.feature === target.feature && source.id === target.task_id ? 'tasks' : null;
}
const record = (value: unknown): value is Record<string, unknown> => !!value && typeof value === 'object' && !Array.isArray(value);
export function exactMediaOwnerRecord(value: unknown, target: TaskCenterNavigationTarget, projectId: string, scope?: CollaborationContext['scope']): Record<string, unknown> {
  if (!mediaOwnerRoute(target) || !record(value) || !Array.isArray(value.items) || value.items.length > 500) throw new Error('INVALID');
  const id = target.queue === 'TASKS' ? target.task_id : target.item_id;
  const matches = value.items.filter(row => record(row) && row.id === id);
  if (matches.length !== 1) throw new Error('UNAVAILABLE');
  const row = matches[0];
  if (JSON.stringify(row).length > 64_000) throw new Error('INVALID');
  if (!record(row) || !Number.isSafeInteger(row.version) || Number(row.version) < 1 || typeof row.status !== 'string') throw new Error('INVALID');
  const expected = scope ? { mode: 'collaboration', novel_id: projectId, workspace_id: scope.workspaceId, storyline_id: scope.storylineId, branch_id: scope.branchId } : { mode: 'local', novel_id: projectId };
  if (row.novel_id !== projectId || !record(row.scope) || Object.keys(row.scope).length !== Object.keys(expected).length
    || Object.entries(expected).some(([key, value]) => (row.scope as Record<string, unknown>)[key] !== value)) throw new Error('INVALID');
  if (target.queue === 'REVIEW' && (row.version !== target.version || row.task_id !== target.source)) throw new Error('CHANGED');
  return row;
}

/** Read only: reopening never means retry, approval, adoption, or media dispatch. */
export function TaskOwnerResult(props: {
  projectId: string; scope?: CollaborationContext['scope']; identity: string; target: TaskCenterNavigationTarget; transport: StudioGraphTransport;
  busy: boolean; isCurrent: () => boolean; read: <T>(work: () => Promise<T>, signal?: AbortSignal) => Promise<T>; onClose: () => void;
}) {
  const key = JSON.stringify([props.projectId, props.scope, props.identity, props.target, props.isCurrent()]);
  const scope = useRef({ key, transport: props.transport, busy: props.busy, generation: 0 });
  if (scope.current.key !== key || scope.current.transport !== props.transport || scope.current.busy !== props.busy) {
    scope.current = { key, transport: props.transport, busy: props.busy, generation: scope.current.generation + 1 };
  }
  const latest = useRef(props); latest.current = props;
  const alive = useRef(true), running = useRef(false), controller = useRef<AbortController>();
  const [result, setResult] = useState<{ generation: number; row?: Record<string, unknown>; message?: string }>();
  const [pending, setPending] = useState(false);
  const route = mediaOwnerRoute(props.target);
  async function load() {
    const origin = latest.current, generation = scope.current.generation;
    const selectedRoute = mediaOwnerRoute(origin.target);
    if (!selectedRoute || running.current || origin.busy || !origin.isCurrent()) return;
    const abort = new AbortController(); controller.current = abort;
    running.current = true; setPending(true); setResult(undefined);
    const valid = () => alive.current && !abort.signal.aborted && generation === scope.current.generation && latest.current.isCurrent();
    try {
      const response = await origin.read(() => origin.transport.json<unknown>(`/api/novels/${encodeURIComponent(origin.projectId)}/experimental/media/${selectedRoute}`, 'GET', undefined, abort.signal), abort.signal);
      if (!valid()) return;
      setResult({ generation, row: exactMediaOwnerRecord(response, origin.target, origin.projectId, origin.scope) });
    } catch (reason) {
      if (valid()) setResult({ generation, message: reason instanceof ApiError && [401, 403].includes(reason.status)
        ? '原媒体服务拒绝读取；没有改用其它接口。'
        : reason instanceof Error && reason.message === 'CHANGED'
          ? '原候选版本或来源已变化，未显示为所选版本。请重新读取审核队列。'
          : '原记录当前不可读、已移除或回执无效。请核对后明确重读。' });
    } finally { running.current = false; if (alive.current) setPending(false); }
  }
  useEffect(() => { alive.current = true; return () => { alive.current = false; controller.current?.abort(); }; }, []);
  // One read follows an explicit open. Busy/identity changes invalidate it, never replay it.
  useEffect(() => () => { controller.current?.abort(); }, [key, props.transport, props.busy]);
  useEffect(() => {
    // StrictMode rehearses mount/cleanup before this microtask. Only the live
    // explicit-open instance starts a read; an aborted read is never replayed.
    let cancelled = false;
    queueMicrotask(() => { if (!cancelled) void load(); });
    return () => { cancelled = true; };
  }, []);
  const visible = result?.generation === scope.current.generation && props.isCurrent() ? result : undefined;
  const id = props.target.queue === 'TASKS' ? props.target.task_id : props.target.item_id;
  return <Panel title="原任务与候选记录" aria-label="原任务与候选记录">
    <p>{props.target.queue === 'TASKS' ? props.target.authority : props.target.domain} · {id}</p>
    <p>只按原服务读取所选记录。重读不会重试任务、批准候选或生成媒体。</p>
    {!route && <StatusMessage tone="warning">此来源没有接入当前工作区的精确打开入口。请在原功能中查找；没有跳转到无关制作任务或素材。</StatusMessage>}
    {route && <Button disabled={props.busy || pending} onClick={() => void load()}>重新读取原记录</Button>}
    <Button onClick={props.onClose}>关闭原记录</Button>
    {pending && <StatusMessage>正在读取原媒体服务…</StatusMessage>}
    {visible?.message && <StatusMessage tone="warning">{visible.message}</StatusMessage>}
    {visible?.row && <section aria-label="已核对原媒体记录">
      {visible.row.stale === true && <StatusMessage tone="warning">原服务报告来源已过期；请在原功能核对来源后再决定。</StatusMessage>}
      <p>原记录 {String(visible.row.id)} · v{String(visible.row.version)} · {String(visible.row.status)}</p>
      <details open><summary>原记录内容与来源</summary><pre>{JSON.stringify(visible.row, null, 2)}</pre></details>
      <p>这是当前读取的原记录；候选的后续决定仍需原审核流程。</p>
    </section>}
  </Panel>;
}
