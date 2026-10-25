/**
 * [HERMIA-FE-20261025 U3-M4] Read-only task → detail → source node → execution canvas → back navigation.
 * Pure bookkeeping: it NEVER calls a writer (no generate/adopt/cancel/enqueue). The host supplies `hasNode` (reads the
 * local canvas draft) and applies the returned instructions (select / show panel / restore viewport & focus).
 * Missing relation or missing node ⇒ plain-language message, never a fabricated node.
 */
import type {NavReturnPoint, ScopeLease, TaskRef} from '../contracts';

export type LocateResult =
  | {kind: 'located'; canvas: 'creative' | 'execution'; nodeId: string}
  | {kind: 'missing'; text: string};

export const NAV_TEXT = {
  noLink: '这个任务没有记录它来自哪个作品节点，无法定位。可以在创作画布里手动查找。',
  noNode: '它记录的来源节点已不在当前画布（可能被删除，或画布是另一台设备的本机草稿）。没有创建替代节点。',
  stale: '项目或账号已经切换，这次定位已作废。',
} as const;

export class TaskNavigator {
  private back: NavReturnPoint | null = null;
  constructor(private lease: ScopeLease) {}
  /** Remember where the user was (selection, focus, viewport) BEFORE leaving. Only the first call per trip counts. */
  remember(rp: NavReturnPoint) { if (!this.back) this.back = {...rp, nodeIds: [...rp.nodeIds], viewport: rp.viewport ? {...rp.viewport} : null}; }
  locate(ref: TaskRef, hasNode: (canvas: 'creative' | 'execution', id: string) => boolean): LocateResult {
    if (!this.lease.isCurrent()) return {kind: 'missing', text: NAV_TEXT.stale};
    if (!ref.link || !ref.link.nodeId) return {kind: 'missing', text: NAV_TEXT.noLink};
    if (!hasNode(ref.link.canvas, ref.link.nodeId)) return {kind: 'missing', text: NAV_TEXT.noNode};
    return {kind: 'located', canvas: ref.link.canvas, nodeId: ref.link.nodeId};
  }
  canReturn() { return !!this.back && this.lease.isCurrent(); }
  /** Returns the saved point exactly once; a retired lease (project switched mid-trip) returns null. */
  takeReturn(): NavReturnPoint | null {
    const rp = this.back; this.back = null;
    return rp && this.lease.isCurrent() ? rp : null;
  }
}
