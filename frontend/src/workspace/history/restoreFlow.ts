/**
 * [HERMIA-FE-20261025 U4-M9c] Explicit restore via the EXISTING owner (canvasViews.restore). The owner itself fences
 * expected_version / digest / incarnation and appends a new version. We add: lease guard, single-flight, fresh history
 * read before write, and UNKNOWN (no auto resend) when the response is lost.
 */
import type {ScopeLease} from '../contracts';
import type {CanvasViewHistory, CanvasViewRecord} from '../../creative/studioCanvasViewClient';

export interface RestoreDeps {
  canvasViews: {history: (id: string) => Promise<CanvasViewHistory>; restore: (h: CanvasViewHistory, v: number) => Promise<CanvasViewRecord>};
  lease: Pick<ScopeLease, 'epoch' | 'isCurrent'>;
  canMutate: () => boolean;
}
export type RestoreResult = {state: 'restored'; record: CanvasViewRecord} | {state: 'blocked'; text: string} | {state: 'unknown'; next: string};

export function createRestoreFlow(deps: RestoreDeps) {
  let inFlight = false;
  /** `seen` = the history the user confirmed against. */
  return async function restore(canvasId: string, seen: CanvasViewHistory, version: number): Promise<RestoreResult> {
    if (inFlight) return {state: 'blocked', text: '上一次恢复还在进行，不会重复提交。'};
    if (!deps.canMutate()) return {state: 'blocked', text: '你当前没有修改这个项目的权限。'};
    const epoch = deps.lease.epoch, live = () => deps.lease.isCurrent() && deps.lease.epoch === epoch;
    inFlight = true;
    try {
      let fresh: CanvasViewHistory;
      try { fresh = await deps.canvasViews.history(canvasId); } catch { return {state: 'blocked', text: '读取历史失败，请检查网络后重新读取。'}; }
      if (!live()) return {state: 'blocked', text: '账号或项目已切换，已取消这次恢复。'};
      if (fresh.incarnation !== seen.incarnation) return {state: 'blocked', text: '这个作品已被删除后重建，旧历史不能恢复到新作品。'};
      if (fresh.current_version !== seen.current_version || fresh.current_definition_digest !== seen.current_definition_digest)
        return {state: 'blocked', text: '确认之后作品又被修改过。请重新查看差异再确认。'};
      try {
        const record = await deps.canvasViews.restore(fresh, version);
        if (!live()) return {state: 'blocked', text: '账号或项目已切换，结果已忽略。'};
        return {state: 'restored', record};
      } catch (e) {
        const s = (e as {status?: number})?.status;
        if (s === 409 || s === 412 || s === 422) return {state: 'blocked', text: '作品版本已变化，恢复没有执行。请重新读取历史。'};
        if (s === 403) return {state: 'blocked', text: '你当前没有修改这个项目的权限。'};
        return {state: 'unknown', next: '没收到恢复结果，不确定是否已恢复。请点「重新读取历史」核对；不会自动重新提交。'};
      }
    } finally { inFlight = false; }
  };
}
