import { Button, StatusMessage } from '../ui/primitives';
import type { Row } from './api';
import { Details } from './shared';

export function hasPromotionIntent(row: Row) {
  return row.status === 'APPROVING' || !!row.promotion_started_at || !!row.promotion_token || !!row.promotion_asset_id || !!row.promotion_state;
}
export function needsPromotionRecovery(row: Row) {
  return row.status === 'APPROVING' || ['RESUME_APPROVAL', 'SOURCE_CHANGED_RECONCILIATION_REQUIRED'].includes(row.recovery_state);
}
/** A checkpoint is an incomplete cross-store write, never a fresh rejectable proposal. */
export function PromotionRecovery({ row, busy, onResume, sourceUnavailable = false }: { row: Row; busy: boolean; onResume?: () => void; sourceUnavailable?: boolean }) {
  if (!needsPromotionRecovery(row)) return null;
  const stale = row.stale === true || row.recovery_state === 'SOURCE_CHANGED_RECONCILIATION_REQUIRED';
  const current = row.stale === false && !stale && !sourceUnavailable;
  const recoveryState = stale ? 'SOURCE_CHANGED_RECONCILIATION_REQUIRED' : current ? 'RESUME_APPROVAL' : 'SOURCE_FRESHNESS_UNVERIFIED';
  return <section className="experimental-record" aria-label="资产批准恢复">
    <StatusMessage tone="warning">{stale ? '批准写入已中断，且来源已变化：需要核对与协调处理。已创建的资产引用已保留，不能继续批准或改为驳回。' : current ? '批准写入尚未完成。来源仍为当前版本，可明确恢复同一次批准；不会自动重试或创建新的批准意图。' : '批准写入尚未完成，来源状态尚未确认。请刷新后核对；资产引用与批准意图已保留。'}</StatusMessage>
    <dl className="experimental-meta">
      <div><dt>已记录资产 ID</dt><dd>{row.promotion_asset_id || row.asset_id || '尚未记录，不能据此认定资产未创建'}</dd></div>
      <div><dt>已记录资产 SHA-256</dt><dd>{row.promotion_asset_digest || '尚未记录'}</dd></div>
      <div><dt>恢复状态</dt><dd>{recoveryState}</dd></div>
    </dl>
    <Details label="批准 checkpoint 与来源" value={{ promotion_state: row.promotion_state, promotion_asset_id: row.promotion_asset_id, promotion_asset_digest: row.promotion_asset_digest, candidate_content_sha256: row.content_sha256, source_digest: row.source_digest, source_versions: row.source_versions ?? row.sources, recovery_state: recoveryState }} />
    {current && onResume && <Button disabled={busy} onClick={onResume}>恢复此次资产批准</Button>}
  </section>;
}
