/**
 * [HERMIA-FE-20261025 U4-M8a] Result standing projection (candidate / reviewed asset / adopted).
 * Pure projection of EXISTING owner data: ProductionJob (studioProductionClient) + CanvasViewRecord (studioCanvasViewClient).
 * No second state system: standing is recomputed from the live read every time, never stored.
 */
import type {ResultStanding} from '../contracts';
import type {ProductionJob} from '../../creative/studioProductionClient';
import type {CanvasViewRecord} from '../../creative/studioCanvasViewClient';

export interface ResultView {
  standing: ResultStanding | 'pending' | 'failed' | 'unknown';
  /** Human text only (no raw ids/codes). */
  label: string;
  detail: string;
  jobVersion: number;
  /** asset version the owner approved (null while only a candidate) */
  assetVersion: number | null;
  sourceLabel: string;
  /** data-* only */
  errorCode: string | null;
}

const OWNER_LABEL: Record<string, string> = {image: '图像生成', video: '视频生成', audio: '音频生成', timeline: '时间线导出'};

/** Is the job's approved asset what the canvas card currently shows? Only then is it "adopted". */
export function isAdoptedOn(job: ProductionJob, canvas: CanvasViewRecord | null, cardId: string): boolean {
  if (!canvas || !job.output_candidate || job.status !== 'APPROVED' || job.approved_asset_version == null) return false;
  const card = canvas.definition.cards.find(c => c.id === cardId);
  return !!card?.asset && card.asset.asset_id === job.output_candidate.id && card.asset.version === job.approved_asset_version
    && card.asset.digest === job.output_candidate.digest;
}

export function projectResult(job: ProductionJob, canvas: CanvasViewRecord | null, cardId: string): ResultView {
  const base = {jobVersion: job.version, sourceLabel: `${OWNER_LABEL[job.owner] ?? '生产任务'} · 第 ${job.version} 版任务记录`, errorCode: job.error_code ?? null};
  if (isAdoptedOn(job, canvas, cardId)) return {...base, standing: 'adopted', assetVersion: job.approved_asset_version, label: '当前采用',
    detail: '作品原位置正在使用这份已审核素材。'};
  if (job.status === 'APPROVED' && job.output_candidate && job.approved_asset_version != null) return {...base, standing: 'reviewed-asset',
    assetVersion: job.approved_asset_version, label: '已审核素材（未采用）', detail: '已通过审核，但作品原位置还没有换成它。采用需要你确认。'};
  if (job.status === 'UNKNOWN' || job.needs_reconciliation) return {...base, standing: 'unknown', assetVersion: null, label: '结果未知',
    detail: '没能确认这次执行的结果。请先「重新读取原任务」，系统不会自动重跑。'};
  if (job.status === 'FAILED' || job.status === 'CANCELLED') return {...base, standing: 'failed', assetVersion: null,
    label: job.status === 'FAILED' ? '执行失败' : '已取消', detail: '没有可用结果。需要的话请回到原生产入口重新发起。'};
  if (job.output_candidate && ['RESULT_READY', 'AWAITING_REVIEW', 'SUCCEEDED', 'REVIEWING'].includes(job.status)) return {...base,
    standing: 'candidate', assetVersion: null, label: '候选结果（未审核）', detail: '生成成功不等于审核通过；它不会自动进入作品或设定。'};
  return {...base, standing: 'pending', assetVersion: null, label: '仍在处理', detail: '还没有返回候选。可以稍后手动刷新。'};
}

/** Actions and whether the EXISTING capability supports them here. Unsupported → reason, never a fake success. */
export type ResultAction = 'review' | 'adopt' | 'compare' | 'canon';
export function actionAvailability(view: ResultView, opts: {canMutate: boolean; compareTargetIsAsset: boolean}): Record<ResultAction, {ok: boolean; reason?: string}> {
  const noPerm = '你当前没有修改这个项目的权限。';
  return {
    review: view.standing !== 'candidate' ? {ok: false, reason: '只有未审核的候选才能审核。'} : opts.canMutate ? {ok: true} : {ok: false, reason: noPerm},
    adopt: view.standing !== 'reviewed-asset' ? {ok: false, reason: view.standing === 'adopted' ? '已经是当前采用。' : '必须先审核为正式素材，才能采用到作品。'}
      : opts.canMutate ? {ok: true} : {ok: false, reason: noPerm},
    compare: opts.compareTargetIsAsset && view.assetVersion != null ? {ok: true}
      : {ok: false, reason: '对照只支持两份正式素材；候选需先审核。'},
    canon: {ok: false, reason: '结果不会写入设定（Canon）。设定修改请在小说设定里手动进行。'},
  };
}
