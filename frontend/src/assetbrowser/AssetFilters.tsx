import { useMemo } from 'react';
import { Badge, Button } from '../ui/primitives';
import {
  ASSET_BROWSER_CREATED_BUCKET_LABELS, ASSET_BROWSER_EMPTY_FILTERS, ASSET_BROWSER_MEDIA_KIND_LABELS,
  ASSET_BROWSER_MEDIA_KINDS, ASSET_BROWSER_NOTICES, ASSET_BROWSER_REFERENCE_FILTER_LABELS,
  ASSET_BROWSER_REFERENCE_FILTERS, ASSET_BROWSER_REVIEW_LABELS, ASSET_BROWSER_REVIEW_STATES,
  ASSET_BROWSER_TAG_LABELS, ASSET_BROWSER_TAGS,
  type AssetBrowserCreatedBucket, type AssetBrowserFacets, type AssetBrowserFilters,
  type AssetBrowserMediaKind, type AssetBrowserReferenceFilter, type AssetBrowserReviewState,
  type AssetBrowserTag,
} from './assetBrowserTypes';
import { boundPageSize } from './assetBrowserOps';

const ALL = '' as const;

/** 可选页大小：全部落在 `ASSET_BROWSER_BOUNDS` 内，并且都经过 `boundPageSize()`。 */
export const ASSET_BROWSER_PAGE_SIZES: readonly number[] = Object.freeze(
  [8, 24, 48, 96].map(boundPageSize),
);

/**
 * 过滤面。每个面都显示**当前已读取行集合**里的真实计数（含 0），并且引用面把
 * "未核实"单列一项 —— 引用情况不可读时绝不让它伪装成"未被引用"。
 */
export function AssetFilters({
  filters, facets, activeFilterCount, busy, onQuery, onMediaKind, onTag, onReviewState, onCreatedBucket,
  onReference, onReset,
}: {
  filters: AssetBrowserFilters;
  facets: AssetBrowserFacets;
  activeFilterCount: number;
  busy: boolean;
  onQuery: (value: string) => void;
  onMediaKind: (value: AssetBrowserMediaKind | null) => void;
  onTag: (value: AssetBrowserTag | null) => void;
  onReviewState: (value: AssetBrowserReviewState | null) => void;
  onCreatedBucket: (value: AssetBrowserCreatedBucket | null) => void;
  onReference: (value: AssetBrowserReferenceFilter | null) => void;
  onReset: () => void;
}) {
  const mediaOptions = useMemo(() => facets.media_kind, [facets.media_kind]);
  const tagOptions = useMemo(() => facets.tag, [facets.tag]);
  const reviewOptions = useMemo(() => facets.review_state, [facets.review_state]);
  const bucketOptions = useMemo(() => facets.created_bucket, [facets.created_bucket]);
  const referenceOptions = useMemo(() => facets.reference, [facets.reference]);
  const atDefaults = activeFilterCount === 0 && !filters.query.trim() && filters.reference === ASSET_BROWSER_EMPTY_FILTERS.reference;

  return <form className="asset-browser__filters" aria-label="素材筛选" onSubmit={event => event.preventDefault()}>
    <label className="asset-browser__field">
      <span>搜索素材</span>
      <input type="search" aria-label="搜索素材" value={filters.query} disabled={busy}
        placeholder="名称或已授权元数据" maxLength={160}
        onChange={event => onQuery(event.target.value)}/>
    </label>
    <label className="asset-browser__field">
      <span>媒体种类</span>
      <select aria-label="媒体种类" value={filters.media_kind ?? ALL} disabled={busy}
        onChange={event => onMediaKind((event.target.value || null) as AssetBrowserMediaKind | null)}>
        <option value={ALL}>全部（{facets.total}）</option>
        {mediaOptions.map(option => <option key={option.value} value={option.value}>
          {option.label}（{option.count}）
        </option>)}
      </select>
    </label>
    <label className="asset-browser__field">
      <span>用途标签</span>
      <select aria-label="用途标签" value={filters.tag ?? ALL} disabled={busy}
        onChange={event => onTag((event.target.value || null) as AssetBrowserTag | null)}>
        <option value={ALL}>全部</option>
        {tagOptions.map(option => <option key={option.value} value={option.value}>
          {option.label}（{option.count}）
        </option>)}
      </select>
    </label>
    <label className="asset-browser__field">
      <span>审核标记</span>
      <select aria-label="审核标记" value={filters.review_state ?? ALL} disabled={busy}
        onChange={event => onReviewState((event.target.value || null) as AssetBrowserReviewState | null)}>
        <option value={ALL}>全部</option>
        {reviewOptions.map(option => <option key={option.value} value={option.value}>
          {ASSET_BROWSER_REVIEW_LABELS[option.value]}（{option.count}）
        </option>)}
      </select>
    </label>
    <label className="asset-browser__field">
      <span>创建时间</span>
      <select aria-label="创建时间" value={filters.created_bucket ?? ALL} disabled={busy}
        onChange={event => onCreatedBucket((event.target.value || null) as AssetBrowserCreatedBucket | null)}>
        <option value={ALL}>全部</option>
        {bucketOptions.map(option => <option key={option.value} value={option.value}>
          {ASSET_BROWSER_CREATED_BUCKET_LABELS[option.value]}（{option.count}）
        </option>)}
      </select>
    </label>
    <label className="asset-browser__field">
      <span>引用情况</span>
      <select aria-label="引用情况" value={filters.reference ?? ALL} disabled={busy}
        onChange={event => onReference((event.target.value || null) as AssetBrowserReferenceFilter | null)}>
        <option value={ALL}>全部</option>
        {referenceOptions.map(option => <option key={option.value} value={option.value}>
          {ASSET_BROWSER_REFERENCE_FILTER_LABELS[option.value]}（{option.count}）
        </option>)}
      </select>
    </label>
    <div className="asset-browser__filter-actions">
      {activeFilterCount > 0 && <Badge tone="info">已启用 {activeFilterCount} 个筛选面</Badge>}
      <Button type="button" variant="ghost" disabled={busy || atDefaults} onClick={onReset}>清除筛选</Button>
    </div>
    <p className="asset-browser__note">
      搜索只匹配已读取的元数据（文件名、类型、标签、审核标记、引用摘要），
      不会扫描磁盘、不会打开未授权内容。{facets.reference_unverified > 0 && ` ${facets.reference_unverified} 条素材的引用情况${ASSET_BROWSER_NOTICES.unverified}。`}
    </p>
    <p className="asset-browser__note">
      标记为 {ASSET_BROWSER_TAGS.map(([id]) => ASSET_BROWSER_TAG_LABELS[id]).join(' / ')} 只是作者用途标签，
      不改变素材的媒体种类（{ASSET_BROWSER_MEDIA_KINDS.map(kind => ASSET_BROWSER_MEDIA_KIND_LABELS[kind]).join(' / ')}）。
    </p>
  </form>;
}

/**
 * 页大小选择：只在有界范围内可选。既不一次拉全库，也不允许 0。
 */
export function AssetPager({
  pageSize, visible, total, more, busy, onPageSize, onLoadMore,
}: {
  pageSize: number; visible: number; total: number; more: boolean; busy: boolean;
  onPageSize: (value: number) => void; onLoadMore: () => void;
}) {
  const options = [ASSET_BROWSER_PAGE_SIZES[0], ASSET_BROWSER_PAGE_SIZES[1], ASSET_BROWSER_PAGE_SIZES[2], ASSET_BROWSER_PAGE_SIZES[3]];
  return <div className="asset-browser__pager">
    <p className="asset-browser__note" role="status">
      显示 {Math.min(visible, total)} / {total} 条。{ASSET_BROWSER_NOTICES.pageBounded}
    </p>
    <label className="asset-browser__field">
      <span>每页条数</span>
      <select aria-label="每页条数" value={pageSize} disabled={busy}
        onChange={event => onPageSize(Number(event.target.value))}>
        {options.map(size => <option key={size} value={size}>{size} 条</option>)}
      </select>
    </label>
    {more && <Button type="button" variant="ghost" disabled={busy} onClick={onLoadMore}>继续显示下一页</Button>}
  </div>;
}
