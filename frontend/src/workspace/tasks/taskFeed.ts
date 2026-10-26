/**
 * [HERMIA-FE-20261025 U3-M3] Task feed: explicit, bounded, read-only reads bound to a ScopeLease.
 * - Reads only on explicit refresh()/activation; no polling, no timers, no retries.
 * - Late-response isolation: every read gets a sequence number AND is bound to the lease that issued it; a response
 *   from an older sequence or a retired lease (identity/project/client/permission switch, A→B→A) is dropped.
 * - Revoked (401/403) clears rows; it never shows the previous project's list.
 */
import type {ProductionJob, ProductionOwner} from '../../creative/studioProductionClient';
import type {TaskCenterClient} from '../../taskcenter/taskCenterTypes';
import type {ScopeLease, TaskPanelState, TaskRef} from '../contracts';
import {failureState, fromProductionJob, fromTaskCenter} from './taskSources';

export interface TaskReaders {
  taskCenter?: Pick<TaskCenterClient, 'readTasks'>;
  production?: {list(signal?: AbortSignal): Promise<ProductionJob[]>; get(owner: ProductionOwner, id: string, signal?: AbortSignal): Promise<ProductionJob>};
}
export const NOT_CONNECTED_GAP = '任务列表未接通：当前没有真实登录身份或项目范围，不会显示示例任务。';

export class TaskFeed {
  private seq = 0;
  private listeners = new Set<(s: TaskPanelState) => void>();
  state: TaskPanelState;
  constructor(private readers: TaskReaders | null, private lease: ScopeLease | null) {
    this.state = readers && lease ? {kind: 'loading'} : {kind: 'not-connected', gap: NOT_CONNECTED_GAP};
  }
  subscribe(fn: (s: TaskPanelState) => void) { this.listeners.add(fn); return () => { this.listeners.delete(fn); }; }
  private set(s: TaskPanelState) { this.state = s; for (const l of this.listeners) l(s); }

  async refresh(): Promise<void> {
    const {readers, lease} = this;
    if (!readers || !lease) { this.set({kind: 'not-connected', gap: NOT_CONNECTED_GAP}); return; }
    if (!lease.isCurrent()) return;
    const mine = ++this.seq;
    const fresh = () => mine === this.seq && lease.isCurrent();
    this.set({kind: 'loading'});
    try {
      const [tc, jobs] = await Promise.all([
        readers.taskCenter ? readers.taskCenter.readTasks({q: '', failed_only: false}, lease.signal) : Promise.resolve(null),
        readers.production ? readers.production.list(lease.signal) : Promise.resolve(null),
      ]);
      if (!fresh()) return; // late response from an older read or a retired scope — dropped
      const items: TaskRef[] = [...(jobs ?? []).map(fromProductionJob), ...(tc?.items ?? []).map(fromTaskCenter)];
      this.set(items.length ? {kind: 'ready', items, truncated: tc?.truncated === true || (jobs?.length ?? 0) >= 1000} : {kind: 'empty'});
    } catch (reason) {
      if (!fresh()) return;
      this.set(failureState(reason));
    }
  }

  /** Detail re-read. Production jobs re-read via get(); task-center has no detail endpoint (G-U3-3) → row as listed. */
  async detail(ref: TaskRef): Promise<{ref: TaskRef; job: ProductionJob | null; gone: boolean} | null> {
    const {readers, lease} = this;
    if (!readers || !lease || !lease.isCurrent()) return null;
    if (ref.source !== 'production-job' || !readers.production) return {ref, job: null, gone: false};
    const [owner, ...rest] = ref.id.split(':');
    try {
      const job = await readers.production.get(owner as ProductionOwner, rest.join(':'), lease.signal);
      if (!lease.isCurrent()) return null;
      return {ref: fromProductionJob(job), job, gone: false};
    } catch (reason) {
      if (!lease.isCurrent()) return null;
      const st = failureState(reason);
      if (st.kind === 'revoked') { this.seq++; this.set(st); return null; }
      return {ref: {...ref, stale: true}, job: null, gone: true};
    }
  }
}
