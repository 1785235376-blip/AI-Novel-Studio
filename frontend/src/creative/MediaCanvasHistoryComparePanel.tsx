import { StatusMessage } from '../ui/primitives';
import { buildMediaCanvasHistoryComparison } from './mediaCanvasHistoryCompare';
import type { MediaCanvasHistoryChange, MediaCanvasHistoryComparisonInput } from './mediaCanvasHistoryCompare';
import type { CanvasAssetReference, CanvasDisplayGroup } from './studioCanvasViewClient';

export type MediaCanvasHistoryCompareProps = MediaCanvasHistoryComparisonInput & { isCurrent: () => boolean };
const detailLimit = 40;
const stateLabel = { CURRENT_METADATA: '当前元数据可用', STALE: '元数据已过期', UNAVAILABLE: '来源不可用（原 pin 未提供）' };
function pin(value?: CanvasAssetReference) {
  return value ? `${value.asset_id} · ${value.kind} · v${value.version} · digest ${value.digest}` : '来源不可用（原 pin 未提供）';
}
function position(value: { x: number; y: number }) { return `(${value.x}, ${value.y})`; }
function sequence(values: string[]) { return `${values.slice(0, 8).join('、') || '无'}${values.length > 8 ? `…（共 ${values.length} 项，列表已截断）` : ''}`; }
function group(value: CanvasDisplayGroup) {
  return `${value.name}；父分组 ${value.parent_id ?? '无'}；${value.collapsed ? '折叠' : '展开'}；成员 ${sequence(value.card_ids)}`;
}
function detail(change: MediaCanvasHistoryChange): string {
  switch (change.kind) {
    case 'card-added': return `新增卡片 ${change.cardId}：${pin(change.after.asset)}；坐标 ${position(change.after.position)}；${stateLabel[change.referenceState]}`;
    case 'card-removed': return `移除卡片 ${change.cardId}：${pin(change.before.asset)}；原坐标 ${position(change.before.position)}；${stateLabel[change.referenceState]}`;
    case 'asset-pin': return `卡片 ${change.cardId} 资产 pin：${pin(change.before)} → ${pin(change.after)}`;
    case 'position': return `卡片 ${change.cardId} 坐标：${position(change.before)} → ${position(change.after)}`;
    case 'membership': return `卡片 ${change.cardId} 所属分组：${change.before ?? '无'} → ${change.after ?? '无'}`;
    case 'reference-state': return `卡片 ${change.cardId} 引用状态：${stateLabel[change.before]} → ${stateLabel[change.after]}`;
    case 'group-added': return `新增分组 ${change.groupId}：${group(change.after)}`;
    case 'group-removed': return `移除分组 ${change.groupId}：${group(change.before)}`;
    case 'group': return `分组 ${change.groupId}：${group(change.before)} → ${group(change.after)}`;
    case 'viewport': return `视窗：${position(change.before)} / 缩放 ${change.before.zoom} → ${position(change.after)} / 缩放 ${change.after.zoom}`;
    case 'view-options': {
      const label = (value: typeof change.before) => value ? `网格${value.grid ? '开启' : '关闭'}，吸附步长 ${value.snap_step ?? '关闭'}` : '未显式记录（沿用默认显示）';
      return `显示选项：${label(change.before)} → ${label(change.after)}`;
    }
    case 'title': return `画布标题：${change.before} → ${change.after}`;
    case 'card-order': return `保留卡片顺序：${sequence(change.before)} → ${sequence(change.after)}`;
    case 'group-order': return `保留分组顺序：${sequence(change.before)} → ${sequence(change.after)}`;
  }
}

/** Read-only consumer of the original history owner. No transport, consent, or restore action. */
export function MediaCanvasHistoryCompare(props: MediaCanvasHistoryCompareProps) {
  if (!props.current || !props.isCurrent()) return <StatusMessage tone="warning">当前画布上下文已失效，旧版本对比已隐藏；请重新读取。</StatusMessage>;
  const comparison = buildMediaCanvasHistoryComparison(props);
  if (!props.isCurrent()) return <StatusMessage tone="warning">当前画布上下文已失效，旧版本对比已隐藏；请重新读取。</StatusMessage>;
  if (comparison.state !== 'ready') return <StatusMessage tone="warning">{comparison.message}</StatusMessage>;
  const c = comparison.counts;
  return <section aria-label="画布历史版本影响对比">
    <p role="status">{comparison.message}</p>
    <dl aria-label="完整影响数量">
      <dt>卡片</dt><dd>新增 {c.cardsAdded}；移除 {c.cardsRemoved}；坐标变化 {c.positionsChanged}；保留卡片顺序变化 {c.cardOrderChanged}</dd>
      <dt>保留卡片的资产 pin</dt><dd>变更 {c.assetPinsChanged}；资产 ID {c.assetIdsChanged}；kind {c.assetKindsChanged}；version {c.assetVersionsChanged}；digest {c.assetDigestsChanged}</dd>
      <dt>分组</dt><dd>新增 {c.groupsAdded}；移除 {c.groupsRemoved}；属性或成员变化 {c.groupsChanged}；卡片归属变化 {c.membershipsChanged}；保留分组顺序变化 {c.groupOrderChanged}</dd>
      <dt>画布显示</dt><dd>视窗变化 {c.viewportChanged}；显示选项变化 {c.viewOptionsChanged}；标题变化 {c.titleChanged}</dd>
      <dt>所选版本来源状态</dt><dd>当前元数据可用 {c.referencesCurrent}；过期 {c.referencesStale}；不可用 {c.referencesUnavailable}；保留卡片状态变化 {c.referenceStatesChanged}</dd>
    </dl>
    {c.totalChanges === 0 ? <p>没有已记录的布局或资产 pin 差异；恢复仍会创建新版本。</p> : <>
      <p>共 {c.totalChanges} 项变更。{c.totalChanges > detailLimit && `仅显示前 ${detailLimit} 项，另 ${c.totalChanges - detailLimit} 项明细已截断；以上数量包含全部变更。`}</p>
      <ol aria-label="差异明细">{comparison.changes.slice(0, detailLimit).map((change, index) => <li key={`${change.kind}-${index}`} style={{ overflowWrap: 'anywhere' }}>{detail(change)}</li>)}</ol>
    </>}
    {comparison.notes.map(note => <p key={note}>{note}</p>)}
  </section>;
}
