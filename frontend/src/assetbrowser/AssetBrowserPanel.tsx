import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { CollaborationContext } from '../api';
import type { StudioAsset } from '../creative/studioClient';
import type { StudioGraphTransport } from '../creative/studioGraphClient';
import { Badge, Button, EmptyState, Panel, StatusMessage } from '../ui/primitives';
import { assetBrowserList } from './assetBrowserContract';
import { createAssetBrowserClient } from './assetBrowserClient';
import { AssetDetailPanel } from './AssetDetailPanel';
import { AssetComparePanel, type AssetMediaSlot } from './AssetComparePanel';
import { AssetFilters, AssetPager } from './AssetFilters';
import { AssetGrid } from './AssetGrid';
import { AssetSendToPanel } from './AssetSendToPanel';
import { loadAssetComparisonPreview, type AssetComparisonDownload } from './assetComparisonPreview';
import { compareVersions } from './assetBrowserOps';
import {
  ASSET_BROWSER_NOTICES, ASSET_BROWSER_UNVERIFIED,
  type AssetBrowserAsset, type AssetBrowserCompareResult, type AssetBrowserReference,
  type AssetBrowserSendTarget,
} from './assetBrowserTypes';
import { useAssetBrowser } from './useAssetBrowser';
import './assetBrowser.css';

/** FROZEN MOUNT PROPS —— 组合根注入，形状不允许改动。 */
export type AssetBrowserPanelProps = {
  projectId: string;
  transport: StudioGraphTransport;
  scope?: CollaborationContext['scope'];
  identity: string;
  active: boolean;
  denied: boolean;
  busy: boolean;
  isCurrent: () => boolean;
  read: <T>(work: () => Promise<T>) => Promise<T>;
  mutate: <T>(work: () => Promise<T>) => Promise<T>;
  assets?: StudioAsset[];
  selectedId?: string;
  onSelect?: (assetId: string) => void;
  onSendTo?: (target: 'IMAGE' | 'VIDEO' | 'STORYBOARD' | 'TIMELINE',
    reference: { asset_id: string; version: number; digest: string }) => void;
  onUnavailable?: () => void;
};

/**
 * UX-03 组合根挂载点。
 *
 * 组成：过滤面 + 网格 / 列表（共用选择模型）+ 按需详情 + 版本对比 + 传参面板。
 *
 * 这个目录是**消费者**：
 * - 素材目录与详情走既有 owner 的同一组端点（`studioClient.ts` 的
 *   `assets()` / `asset()` / `relationships()` / `download()`）；
 * - 复用同一份授权与同一个关系投影，不新增素材库、不复制内容；
 * - 只读：不需要 `mutate`，因此**不会**执行目标模块、写标签或物理删除文件；
 * - `assets` 是可选注入（组合根已经读过同一份目录时可以传进来避免重复读取），
 *   未注入时本面板通过注入的传输自己读一次。
 */
export function AssetBrowserPanel({
  projectId, transport, scope, identity, active, denied, busy, isCurrent, read,
  assets: suppliedAssets, selectedId, onSelect, onSendTo, onUnavailable,
}: AssetBrowserPanelProps) {
  const client = useMemo(
    () => createAssetBrowserClient(projectId, transport, scope),
    // 传输与范围在构造时克隆；标识变化必须重建客户端。
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [projectId, transport, scope?.workspaceId, scope?.projectId, scope?.storylineId, scope?.branchId],
  );
  const scopeKey = useMemo(() => JSON.stringify([projectId, scope?.workspaceId ?? null, scope?.projectId ?? null,
    scope?.storylineId ?? null, scope?.branchId ?? null]), [projectId, scope]);
  const supplied = useMemo(() => suppliedAssets
    // 注入的目录与端点读取共用同一份严格解码：不合规的行会让整次读取失败，
    // 而不是被静默丢掉或补一个默认值。
    ? decodeSupplied(suppliedAssets, projectId)
    : undefined, [suppliedAssets, projectId]);

  const controller = useAssetBrowser({
    projectId, client, identity, active, denied, busy, isCurrent, read, scopeKey,
    assets: supplied, selectedId, onSelect, onSendTo, onUnavailable,
  });
  const download = useCallback((assetId: string) => client.downloadAsset
    ? client.downloadAsset(assetId)
    : Promise.reject(new Error('no-download')), [client]);

  const [otherId, setOtherId] = useState<string | null>(null);
  const [otherResult, setOtherResult] = useState<{ token: object; asset: AssetBrowserAsset }>();
  const [compareFailure, setCompareFailure] = useState<{ token: object; message: string }>();
  const [zoom, setZoom] = useState(1);
  const [activeSlot, setActiveSlot] = useState<AssetMediaSlot | null>(null);
  const [showCompare, setShowCompare] = useState(false);

  const selectedRow = controller.rows.find(row => row.id === controller.selectedId);
  const detail = controller.detail?.id === controller.selectedId ? controller.detail : undefined;

  /** 可对比的版本来自 owner 已披露的来源投影 + 同名记录；绝不发明版本历史。 */
  const candidates = useMemo(() => {
    const rows = controller.rows
      .filter(row => row.id !== controller.selectedId && row.filename === selectedRow?.filename)
      .map(row => ({ id: row.id, version: row.version, digest: row.digest, label: row.filename }));
    const parents = (detail?.provenance?.parents ?? [])
      .filter(parent => parent.id !== null && parent.id !== controller.selectedId)
      .map(parent => ({ id: parent.id as string, version: parent.version, digest: parent.digest ?? '',
        label: `来源 ${parent.label ?? parent.id}` }));
    const seen = new Set<string>();
    return [...parents, ...rows].filter(candidate => {
      if (seen.has(candidate.id)) return false;
      seen.add(candidate.id);
      return true;
    });
  }, [controller.rows, controller.selectedId, selectedRow?.filename, detail]);

  const fatal = denied || controller.state === 'DENIED';
  const authorityCurrent = isCurrent();
  const candidateKey = JSON.stringify(candidates);
  const detailKey = detail && JSON.stringify([detail.id, detail.version, detail.digest, detail.size, detail.media_type, detail.kind, detail.media_kind, detail.branch_id, detail.deleted]);
  // A -> B -> A creates a fresh token: a late result can never revive a former session.
  const compareToken = useMemo(() => ({}),
    [identity, scopeKey, client, read, active, fatal, authorityCurrent, showCompare, detailKey, candidateKey, otherId]);
  const latestCompare = useRef(compareToken), latestCurrent = useRef(isCurrent);
  latestCompare.current = compareToken; latestCurrent.current = isCurrent;
  const comparisonCurrent = useCallback(() => latestCompare.current === compareToken
    && active && !fatal && showCompare && latestCurrent.current(), [compareToken, active, fatal, showCompare]);
  const otherAsset = otherResult?.token === compareToken ? otherResult.asset : undefined;
  const compareError = compareFailure?.token === compareToken ? compareFailure.message : '';

  // Only an explicitly selected, disclosed target can be read in the current scope.
  useEffect(() => {
    const candidate = candidates.find(value => value.id === otherId);
    if (!candidate || !detail || !comparisonCurrent()) return;
    const abort = new AbortController();
    const current = () => !abort.signal.aborted && comparisonCurrent();
    void read(() => {
      if (!current()) throw new Error('stale-comparison');
      return client.readAsset(candidate.id, abort.signal);
    }).then(value => {
      if (!current()) return;
      if (value.id !== candidate.id || value.deleted || value.branch_id !== (scope?.branchId || null)
          || (candidate.version !== null && value.version !== candidate.version)
          || (candidate.digest && value.digest !== candidate.digest)) throw new Error('changed-comparison');
      setOtherResult({ token: compareToken, asset: value });
    }).catch(() => {
      if (current()) setCompareFailure({ token: compareToken,
        message: '对比版本读取失败或已变化；未显示旧预览，选择保持不变。' });
    });
    return () => abort.abort();
    // Candidate / detail snapshots are captured by compareToken, not object identity.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [compareToken, comparisonCurrent]);

  const downloadComparison = useCallback<AssetComparisonDownload>((asset, slotCurrent) => {
    const current = () => comparisonCurrent() && slotCurrent();
    return read(() => {
      if (!current() || asset.branch_id !== (scope?.branchId || null)) throw new Error('stale-comparison');
      return loadAssetComparisonPreview(client, asset, current);
    }).then(blob => {
      if (!current()) throw new Error('stale-comparison');
      return blob;
    });
  }, [client, read, comparisonCurrent, scope?.branchId]);
  useEffect(() => { setActiveSlot(null); setZoom(1); }, [compareToken]);

  const comparison: AssetBrowserCompareResult | undefined = useMemo(
    () => detail && otherAsset ? compareVersions(detail, otherAsset) : undefined,
    [detail, otherAsset]);

  const stopPlayback = useCallback((slot: AssetMediaSlot) => {
    setActiveSlot(current => current === slot ? null : current);
  }, []);

  const impact = controller.impact();
  const deleteImpact = controller.deleteImpact();

  return <div className="asset-browser" data-state={controller.state}>
    <Panel title="素材浏览器" className="asset-browser__shell"
      actions={<div className="asset-browser__actions">
        <Button type="button" variant="ghost" aria-pressed={controller.mode === 'GRID'} disabled={busy}
          onClick={() => controller.setMode('GRID')}>网格</Button>
        <Button type="button" variant="ghost" aria-pressed={controller.mode === 'LIST'} disabled={busy}
          onClick={() => controller.setMode('LIST')}>列表</Button>
        <Button type="button" variant="ghost" disabled={busy || fatal}
          onClick={() => void controller.reload()}>重新读取素材</Button>
      </div>}>

    {fatal
      ? <StatusMessage tone="error">
        <strong>{ASSET_BROWSER_NOTICES.deniedIsNotEmpty}</strong>
        <p>{controller.problem?.message ?? '当前会话无权读取此素材库。'}</p>
        {controller.problem?.code && <p className="asset-browser__meta">代码 {controller.problem.code}</p>}
      </StatusMessage>
      : <>
        <AssetFilters filters={controller.filters} facets={controller.facets}
          activeFilterCount={controller.activeFilterCount} busy={busy}
          onQuery={controller.setQuery} onMediaKind={controller.setMediaKind} onTag={controller.setTag}
          onReviewState={controller.setReviewState} onCreatedBucket={controller.setCreatedBucket}
          onReference={controller.setReferenced} onReset={controller.resetFilters}/>

        {controller.state === 'LOADING' && <StatusMessage>正在读取素材目录…</StatusMessage>}
        {controller.state === 'FAILED' && <StatusMessage tone="error">
          {controller.problem?.message ?? ASSET_BROWSER_NOTICES.readFailure}
          {controller.problem?.code && <span> · 代码 {controller.problem.code}</span>}
        </StatusMessage>}
        {controller.state === 'EMPTY' && <EmptyState title="此项目暂无素材"
          detail={ASSET_BROWSER_NOTICES.empty}/>}

        <div className="asset-browser__layout">
          <div className="asset-browser__column">
            <AssetPager pageSize={controller.pageSize} visible={controller.visible} total={controller.filtered.length}
              more={controller.more} busy={busy}
              onPageSize={controller.changePageSize} onLoadMore={controller.loadMore}/>
            <AssetGrid rows={controller.pageRows} mode={controller.mode} selectedId={controller.selectedId}
              busy={busy} download={download} onSelect={assetId => controller.select(assetId)}/>
          </div>
          <div className="asset-browser__column">
            <AssetDetailPanel row={selectedRow} detail={detail} detailState={controller.detailState}
              detailProblem={controller.detailProblem} impact={impact}
              referencesUnverified={controller.referencesUnverified}
              deleteImpact={deleteImpact}
              comparison={otherId ? { id: otherId, version: otherAsset?.version ?? null, digest: otherAsset?.digest ?? '' } : null}
              busy={busy} onReadDetail={assetId => void controller.readDetail(assetId)}
              onLoadReferences={() => void controller.loadReferences()}
              onCompare={() => setShowCompare(true)}
              onSendTo={() => setShowCompare(false)}
              onDeleteIntent={() => void controller.loadReferences()}/>
            {selectedRow && <AssetSendToPanel row={selectedRow} busy={busy}
              onSendTo={onSendTo}/>}
          </div>
        </div>

        {showCompare && active && authorityCurrent && detail && <AssetComparePanel current={detail} other={otherAsset} candidates={candidates} otherId={otherId}
          comparison={comparison} download={downloadComparison} onPick={assetId => { setOtherId(assetId || null); setActiveSlot(null); setZoom(1); }}
          onZoom={setZoom} onStartPlayback={setActiveSlot} onStopPlayback={stopPlayback}
          activeSlot={activeSlot} zoom={zoom}/>}
        {showCompare && !detail && <StatusMessage tone="warning">
          需要先按需读取当前素材的详情，才能与另一个版本对比。
        </StatusMessage>}
        {compareError && <StatusMessage tone="error">{compareError}</StatusMessage>}

        <p className="asset-browser__note">
          缩略图按需读取（{ASSET_BROWSER_NOTICES.thumbnailOnDemand}）。
          {controller.referencesUnverified && ` ${ASSET_BROWSER_NOTICES.relationshipUnreadable}`}
        </p>
        <p className="asset-browser__note">{ASSET_BROWSER_NOTICES.noAutoUpdate}</p>
        {!detail && controller.selectedId && <p className="asset-browser__note">
          当前选中 {controller.selectedId}；详情尚未读取（{ASSET_BROWSER_UNVERIFIED}）。
        </p>}
        {controller.detailState === 'FAILED' && <Badge tone="warning">详情读取失败 · 选择保持</Badge>}
      </>}
    </Panel>
  </div>;
}

/**
 * 注入的目录行就是 `studioClient.ts::StudioAsset` 的投影。这里**不**放宽校验：
 * `assets` 只是"已经读过一次的同一个 owner 数据"，仍然按同一份契约逐字段检查，
 * 任何不自洽都会拒绝整次读取，而不是被静默丢掉。
 */
function decodeSupplied(assets: readonly StudioAsset[], projectId: string): AssetBrowserAsset[] {
  return assetBrowserList({ items: assets }, projectId);
}
