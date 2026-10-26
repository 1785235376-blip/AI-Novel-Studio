/**
 * [HERMIA-FE-20261025 U4-M8b] Explicit review + adopt flow over EXISTING capabilities only:
 *   review  → StudioProductionClient.review(job)          (owner validates expected_version + request_digest + output digest)
 *   adopt   → canvasViews.save(id, expectedVersion, def, {expected_incarnation, expected_definition_digest, expected_card})
 * Nothing here enqueues, executes, regenerates or writes Canon. Each write needs a fresh confirmation bound to an
 * AdoptGuard captured from a live read; any drift (project, node, job version, asset version, lease) blocks.
 * A write whose response is lost becomes UNKNOWN and is NEVER re-sent automatically.
 */
import type {AdoptGuard, ScopeLease} from '../contracts';
import type {ProductionJob, StudioProductionClient} from '../../creative/studioProductionClient';
import type {CanvasDefinition, CanvasViewHistory, CanvasViewRecord} from '../../creative/studioCanvasViewClient';
import type {StudioAsset} from '../../creative/studioClient';

export interface AdoptDeps {
  production: Pick<StudioProductionClient, 'get' | 'review'>;
  asset: (id: string) => Promise<StudioAsset>;
  canvasViews: {
    get: (id: string) => Promise<CanvasViewRecord>;
    history: (id: string) => Promise<CanvasViewHistory>;
    save: (id: string, expectedVersion: number, d: CanvasDefinition, origin?: {expected_incarnation: string; expected_definition_digest: string;
      expected_card?: {card_id: string; source: NonNullable<CanvasDefinition['cards'][number]['asset']>}}) => Promise<CanvasViewRecord>;
  };
  lease: Pick<ScopeLease, 'epoch' | 'isCurrent'>;
  canMutate: () => boolean;
}
export interface AdoptTarget { projectId: string; canvasId: string; cardId: string; job: Pick<ProductionJob, 'owner' | 'id' | 'version' | 'request_digest'>; }

export type BlockReason = 'lease-retired' | 'permission' | 'project-changed' | 'node-deleted' | 'task-changed' | 'not-reviewed'
  | 'asset-mismatch' | 'work-modified' | 'in-flight' | 'read-failed';
export const BLOCK_TEXT: Record<BlockReason, string> = {
  'lease-retired': '账号、项目或客户端已切换，这个结果属于之前的上下文，已忽略。',
  permission: '你当前没有修改这个项目的权限，不能采用。',
  'project-changed': '原项目已变化（可能被删除后重建），不能采用到新项目。',
  'node-deleted': '作品里的原位置已被删除，结果没有地方可以放回。请先恢复原位置或选择新位置。',
  'task-changed': '原任务已经有了新版本，这份结果可能已过期。请重新读取原任务。',
  'not-reviewed': '这个结果还没有审核为正式素材，不能采用。',
  'asset-mismatch': '正式素材的版本或内容和审核记录不一致，不能采用。',
  'work-modified': '确认之后作品又被修改过。请重新读取并再次确认。',
  'in-flight': '上一次操作还在进行中，不会重复提交。',
  'read-failed': '读取原任务或作品失败。请检查网络后手动重试读取。',
};
export type Prepared = {ok: true; guard: AdoptGuard; definition: CanvasDefinition; canvas: CanvasViewRecord; history: CanvasViewHistory; asset: StudioAsset; job: ProductionJob}
  | {ok: false; reason: BlockReason};
export type CommitResult = {state: 'adopted'; record: CanvasViewRecord} | {state: 'blocked'; reason: BlockReason}
  | {state: 'unknown'; next: string};

export function createAdoptFlow(deps: AdoptDeps) {
  let inFlight = false;
  const live = (epoch: number) => deps.lease.isCurrent() && deps.lease.epoch === epoch;

  async function prepare(t: AdoptTarget): Promise<Prepared> {
    const epoch = deps.lease.epoch;
    let job: ProductionJob, canvas: CanvasViewRecord, history: CanvasViewHistory, asset: StudioAsset;
    try {
      job = await deps.production.get(t.job.owner, t.job.id);
      if (!live(epoch)) return {ok: false, reason: 'lease-retired'};
      if (job.novel_id !== t.projectId) return {ok: false, reason: 'project-changed'};
      if (job.version !== t.job.version || job.request_digest !== t.job.request_digest) return {ok: false, reason: 'task-changed'};
      if (job.status !== 'APPROVED' || !job.output_candidate || job.approved_asset_version == null) return {ok: false, reason: 'not-reviewed'};
      asset = await deps.asset(job.output_candidate.id);
      if (!live(epoch)) return {ok: false, reason: 'lease-retired'};
      canvas = await deps.canvasViews.get(t.canvasId);
      history = await deps.canvasViews.history(t.canvasId);
      if (!live(epoch)) return {ok: false, reason: 'lease-retired'};
    } catch {
      return {ok: false, reason: live(epoch) ? 'read-failed' : 'lease-retired'};
    }
    if (!deps.canMutate()) return {ok: false, reason: 'permission'};
    if (canvas.project_id !== t.projectId) return {ok: false, reason: 'project-changed'};
    if (history.current_version !== canvas.version || history.current_definition_digest !== canvas.definition_digest) return {ok: false, reason: 'work-modified'};
    if (!canvas.definition.cards.some(c => c.id === t.cardId)) return {ok: false, reason: 'node-deleted'};
    if (asset.id !== job.output_candidate.id || asset.version !== job.approved_asset_version || asset.sha256 !== job.output_candidate.digest
      || asset.kind !== job.output_candidate.kind || asset.deleted_at) return {ok: false, reason: 'asset-mismatch'};
    const definition: CanvasDefinition = {...canvas.definition, cards: canvas.definition.cards.map(c => c.id === t.cardId
      ? {...c, asset: {asset_id: asset.id, version: asset.version, digest: asset.sha256, kind: job.output_candidate!.kind}} : c)};
    return {ok: true, definition, canvas, history, asset, job,
      guard: {projectId: t.projectId, nodeId: t.cardId, jobId: job.id, jobVersion: job.version, assetVersion: asset.version, leaseEpoch: epoch}};
  }

  /** Must be called from an explicit user confirmation of `p`. Re-verifies the guard against a fresh read before writing. */
  async function commit(t: AdoptTarget, p: Extract<Prepared, {ok: true}>): Promise<CommitResult> {
    if (inFlight) return {state: 'blocked', reason: 'in-flight'};
    if (!live(p.guard.leaseEpoch)) return {state: 'blocked', reason: 'lease-retired'};
    inFlight = true;
    try {
      const again = await prepare(t);
      if (!again.ok) return {state: 'blocked', reason: again.reason};
      const g = again.guard, o = p.guard;
      if (g.projectId !== o.projectId || g.nodeId !== o.nodeId || g.jobId !== o.jobId || g.jobVersion !== o.jobVersion) return {state: 'blocked', reason: 'task-changed'};
      if (g.assetVersion !== o.assetVersion) return {state: 'blocked', reason: 'asset-mismatch'};
      if (again.canvas.version !== p.canvas.version || again.canvas.definition_digest !== p.canvas.definition_digest) return {state: 'blocked', reason: 'work-modified'};
      const prev = p.canvas.definition.cards.find(c => c.id === t.cardId)?.asset;
      try {
        const record = await deps.canvasViews.save(t.canvasId, p.canvas.version, p.definition, {expected_incarnation: p.history.incarnation,
          expected_definition_digest: p.canvas.definition_digest, ...(prev ? {expected_card: {card_id: t.cardId, source: prev}} : {})});
        if (!live(o.leaseEpoch)) return {state: 'blocked', reason: 'lease-retired'};
        return {state: 'adopted', record};
      } catch (e) {
        const status = (e as {status?: number})?.status;
        if (status === 409 || status === 412 || status === 422) return {state: 'blocked', reason: 'work-modified'};
        if (status === 403) return {state: 'blocked', reason: 'permission'};
        return {state: 'unknown', next: '没收到保存结果，不确定是否已采用。请点「重新读取作品」核对；系统不会自动重新提交。'};
      }
    } finally { inFlight = false; }
  }

  /** Explicit review of a candidate via the original owner endpoint. Never chained into adopt. */
  async function review(job: ProductionJob): Promise<{state: 'reviewed'; job: ProductionJob} | {state: 'blocked'; reason: BlockReason} | {state: 'unknown'; next: string}> {
    if (inFlight) return {state: 'blocked', reason: 'in-flight'};
    if (!deps.canMutate()) return {state: 'blocked', reason: 'permission'};
    const epoch = deps.lease.epoch; inFlight = true;
    try {
      const next = await deps.production.review(job);
      if (!live(epoch)) return {state: 'blocked', reason: 'lease-retired'};
      return {state: 'reviewed', job: next};
    } catch (e) {
      const status = (e as {status?: number})?.status;
      if (status === 409 || status === 412 || status === 422) return {state: 'blocked', reason: 'task-changed'};
      if (status === 403) return {state: 'blocked', reason: 'permission'};
      return {state: 'unknown', next: '没收到审核结果。请重新读取原任务核对；系统不会自动重新提交。'};
    } finally { inFlight = false; }
  }
  return {prepare, commit, review};
}
