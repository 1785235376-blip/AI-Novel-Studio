import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ApiError, apiErrorView } from '../api';
import { assetBrowserQuery } from './assetBrowserContract';
import {
  ASSET_BROWSER_BOUNDS, ASSET_BROWSER_EMPTY_FILTERS, ASSET_BROWSER_ERROR_CODES, ASSET_BROWSER_NOTICES,
  type AssetBrowserAsset, type AssetBrowserClient, type AssetBrowserCompareResult, type AssetBrowserCreatedBucket,
  type AssetBrowserDeleteImpact, type AssetBrowserFacets, type AssetBrowserFilters, type AssetBrowserImpact,
  type AssetBrowserMediaKind, type AssetBrowserProblem, type AssetBrowserReferenceFilter,
  type AssetBrowserReferencedBy, type AssetBrowserReviewState, type AssetBrowserRow,
  type AssetBrowserSendTarget, type AssetBrowserSurfaceState, type AssetBrowserTag, type AssetBrowserViewMode,
} from './assetBrowserTypes';
import {
  applyFacet, assetBrowserRows, assetDeleteImpact, boundPageSize, checkSendTo, clearFilters, compareVersions,
  countActiveFilters, EMPTY_SELECTION, facets as buildFacets, filterRows, hasMoreRows, referenceIndex,
  selectAsset, sourceVersionImpact, visibleRows as sliceRows, withQuery, withReferenceCounts,
  type AssetBrowserSelection, type AssetBrowserSendCheck,
} from './assetBrowserOps';

/** FROZEN MOUNT PROPS（组合根注入；本控制器只读，不需要写权限）。 */
export type AssetBrowserControllerProps = {
  projectId: string;
  client: AssetBrowserClient;
  /** 稳定的工作区 / 分支标识；变化会丢弃此前读到的全部值。 */
  identity: string;
  /** 视图在屏幕上。关闭的视图永远不发读取。 */
  active: boolean;
  denied: boolean;
  busy: boolean;
  isCurrent: () => boolean;
  read: <T>(work: () => Promise<T>) => Promise<T>;
  /** 组合根注入的原始 `identity + 项目 + 分支` 三元组，用于回传 `onUnavailable`。 */
  scopeKey: string;
  /** 调用方已经拿到的目录（例如工作区自己的 `assets()` 结果）；仍然会做严格解码。 */
  assets?: AssetBrowserAsset[];
  /** 调用方控制的选中项（网格 / 列表共用一个）。 */
  selectedId?: string;
  onSelect?: (assetId: string) => void;
  onSendTo?: (target: AssetBrowserSendTarget, reference: { asset_id: string; version: number; digest: string }) => void;
  onUnavailable?: () => void;
};

export const ASSET_BROWSER_DEFAULT_PAGE_SIZE = ASSET_BROWSER_BOUNDS.page_size_default;

function problemOf(reason: unknown, fallback: string): AssetBrowserProblem {
  // 只渲染传输层自己写死的有界文案；未知的本地异常绝不原样回显。
  return reason instanceof ApiError && reason.problem.message
    ? { code: reason.problem.code, message: apiErrorView(reason, fallback).message }
    : { code: ASSET_BROWSER_ERROR_CODES.studioRequestFailed, message: fallback };
}

/**
 * 素材浏览器控制器。
 *
 * 有界的读取策略：
 * 1. **一次**列表读取（`GET …/studio/assets`），响应本身有界（≤ `list_items`）。
 * 2. 引用关系**按需**读取，且失败不会清空列表：引用计数保持 `null`（未核实）。
 * 3. 详情（版本、来源、参数）只在选中某一行时**按需**读取 —— 绝不为整库加载
 *    高清内容，也不预取缩略图。
 * 4. 渲染分页：`visible` 由 `page_size` 界定，`loadMore()` 只增加可见行数
 *    （不再发请求），因此列表永远不可能无界增长。
 *
 * 状态语义：`EMPTY` 只表示"读成功且真的没有素材"。读取失败（含 401/403/404）
 * 永远落到 `DENIED` / `FAILED`，绝不会变成"暂无数据"。
 */
export function useAssetBrowser(props: AssetBrowserControllerProps) {
  const [assets, setAssets] = useState<AssetBrowserAsset[]>([]);
  const [rows, setRows] = useState<AssetBrowserRow[]>([]);
  const [state, setState] = useState<AssetBrowserSurfaceState>('IDLE');
  const [problem, setProblem] = useState<AssetBrowserProblem>();
  const [filters, setFilters] = useState<AssetBrowserFilters>(ASSET_BROWSER_EMPTY_FILTERS);
  const [referenceState, setReferenceState] = useState<'IDLE' | 'LOADING' | 'READY' | 'FAILED'>('IDLE');
  const [referenceProblem, setReferenceProblem] = useState<AssetBrowserProblem>();
  const [selected, setSelected] = useState<AssetBrowserSelection>(EMPTY_SELECTION);
  const [detail, setDetail] = useState<AssetBrowserAsset>();
  const [detailState, setDetailState] = useState<'IDLE' | 'LOADING' | 'READY' | 'FAILED'>('IDLE');
  const [detailProblem, setDetailProblem] = useState<AssetBrowserProblem>();
  const [compare, setCompare] = useState<AssetBrowserAsset>();
  const [pageSize, setPageSize] = useState(boundPageSize(ASSET_BROWSER_DEFAULT_PAGE_SIZE));
  const [mode, setMode] = useState<AssetBrowserViewMode>('GRID');
  const [visible, setVisible] = useState(boundPageSize(ASSET_BROWSER_DEFAULT_PAGE_SIZE));

  const alive = useRef(true), epoch = useRef(0), pending = useRef(false);
  const abort = useRef<AbortController>(), abortDetail = useRef<AbortController>(), abortReferences = useRef<AbortController>();
  const identity = useRef(props.identity), latest = useRef(props);
  const referenceMap = useRef<Map<string, readonly AssetBrowserReferencedBy[]>>(new Map());
  const nowMs = useRef(Date.now());
  latest.current = props; identity.current = props.identity;
  useEffect(() => { alive.current = true; return () => { alive.current = false; epoch.current++; abort.current?.abort(); abortDetail.current?.abort(); abortReferences.current?.abort(); }; }, []);

  const admit = useCallback(() => alive.current && latest.current.active && !latest.current.denied
    && latest.current.isCurrent(), []);

  const reload = useCallback(async () => {
    const captured = latest.current;
    if (!admit() || pending.current || captured.busy) return;
    const controller = new AbortController();
    abort.current?.abort(); abort.current = controller;
    const request = ++epoch.current;
    pending.current = true; setProblem(undefined); setState('LOADING');
    try {
      const value = await captured.read(() => captured.client.listAssets(controller.signal));
      if (request !== epoch.current || !admit() || controller.signal.aborted) return;
      nowMs.current = Date.now();
      setAssets(value);
      // 列表读取**不**顺带读关系：引用情况按需读取，未读之前保持未核实。
      referenceMap.current = new Map();
      setRows(assetBrowserRows(value, nowMs.current));
      setReferenceState('IDLE'); setReferenceProblem(undefined);
      setState(value.length ? 'READY' : 'EMPTY');
    } catch (reason) {
      if (request !== epoch.current || !admit() || controller.signal.aborted) return;
      setProblem(problemOf(reason, ASSET_BROWSER_NOTICES.readFailure));
      setAssets([]); setRows([]); setDetail(undefined); setDetailState('IDLE');
      if (reason instanceof ApiError && [401, 403, 404].includes(reason.status)) {
        // 拒绝读取 / 记录不存在：都**不是**空素材库。
        setState('DENIED');
        latest.current.onUnavailable?.();
      } else setState('FAILED');
    } finally { if (request === epoch.current) pending.current = false; }
  }, [admit]);

  /**
   * 引用关系**按需**读取。它失败时列表保持不动，引用计数保持 `null`；界面必须
   * 显示"未核实"，绝不显示"未被引用"。
   */
  const loadReferences = useCallback(async () => {
    const captured = latest.current;
    if (!admit()) return;
    const controller = new AbortController();
    abortReferences.current?.abort(); abortReferences.current = controller;
    const request = epoch.current;
    setReferenceState('LOADING'); setReferenceProblem(undefined);
    try {
      const graph = await captured.read(() => captured.client.readRelationships(controller.signal));
      if (!admit() || request !== epoch.current || controller.signal.aborted) return;
      referenceMap.current = referenceIndex(graph);
      setRows(previous => withReferenceCounts(previous, referenceMap.current));
      setReferenceState('READY');
    } catch (reason) {
      if (!admit() || request !== epoch.current || controller.signal.aborted) return;
      referenceMap.current = new Map();
      setRows(previous => previous.map(row => ({ ...row, reference_counts: null })));
      setReferenceProblem(problemOf(reason, ASSET_BROWSER_NOTICES.relationshipUnreadable));
      setReferenceState('FAILED');
    }
  }, [admit]);

  /** 详情只在需要时读取；失败保持当前选择，并解释原因。 */
  const readDetail = useCallback(async (assetIdValue: string) => {
    const captured = latest.current;
    if (!admit() || !assetIdValue) return;
    const controller = new AbortController();
    abortDetail.current?.abort(); abortDetail.current = controller;
    const request = epoch.current;
    setDetailState('LOADING'); setDetailProblem(undefined);
    try {
      const value = await captured.read(() => captured.client.readAsset(assetIdValue, controller.signal));
      if (!admit() || request !== epoch.current || controller.signal.aborted) return;
      setDetail(value);
      setDetailState('READY');
    } catch (reason) {
      if (!admit() || request !== epoch.current || controller.signal.aborted) return;
      // 不清空 detail、不改 selection：失败的预览保留当前选择。
      setDetailProblem(problemOf(reason, ASSET_BROWSER_NOTICES.detailFailure));
      setDetailState('FAILED');
    }
  }, [admit]);

  useEffect(() => {
    epoch.current++; abort.current?.abort(); abortDetail.current?.abort(); abortReferences.current?.abort();
    pending.current = false;
    setAssets([]); setRows([]); setProblem(undefined); setDetail(undefined); setDetailProblem(undefined);
    setDetailState('IDLE'); setReferenceState('IDLE'); setReferenceProblem(undefined); setCompare(undefined);
    referenceMap.current = new Map();
    setSelected(EMPTY_SELECTION); setFilters(ASSET_BROWSER_EMPTY_FILTERS);
    setState(props.denied ? 'DENIED' : 'IDLE');
  }, [props.identity, props.denied, props.projectId]);

  // 调用方已经给了目录：直接采用它，不再重复读取同一个 owner 端点。
  const supplied = props.assets;
  useEffect(() => {
    if (!props.active || props.denied) return;
    if (supplied) {
      nowMs.current = Date.now();
      setAssets(supplied);
      setRows(assetBrowserRows(supplied, nowMs.current));
      setState(supplied.length ? 'READY' : 'EMPTY');
      setProblem(undefined);
      return;
    }
    void reload();
  }, [props.active, props.identity, props.denied, supplied, reload]);

  // 调用方控制的选中项优先；否则用控制器自己的选择。
  const selectedId = props.selectedId ?? selected.selectedId;
  const choose = useCallback((assetIdValue: string | null) => {
    if (!alive.current) return;
    setSelected(previous => selectAsset(previous, assetIdValue));
    setDetail(undefined); setDetailProblem(undefined); setDetailState('IDLE'); setCompare(undefined);
    latest.current.onSelect?.(assetIdValue ?? '');
    if (assetIdValue) void readDetail(assetIdValue);
  }, [readDetail]);

  // 外部选中项也必须触发一次按需详情读取（绝不预取整库）。同一个选中项只读一次。
  const detailFor = useRef<string | null>(null);
  useEffect(() => {
    if (!props.selectedId || !props.active || props.denied) { detailFor.current = null; return; }
    if (detail?.id === props.selectedId || detailFor.current === props.selectedId) return;
    detailFor.current = props.selectedId;
    void readDetail(props.selectedId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [props.selectedId, props.active, props.denied, detail?.id]);

  const filtered = useMemo(() => filterRows(rows, filters), [rows, filters]);
  const facetView: AssetBrowserFacets = useMemo(() => buildFacets(rows), [rows]);
  const pageRows = useMemo(() => sliceRows(filtered, visible), [filtered, visible]);
  const more = hasMoreRows(filtered, visible);

  const setQuery = useCallback((value: string) => {
    try {
      setFilters(previous => withQuery(previous, assetBrowserQuery(value)));
    } catch {
      // 搜索词不合法时不改变过滤器，也不清空已读取的素材。
    }
    setVisible(pageSize);
  }, [pageSize]);
  const setMediaKind = useCallback((value: AssetBrowserMediaKind | null) => {
    setFilters(previous => applyFacet(previous, 'media_kind', value)); setVisible(pageSize);
  }, [pageSize]);
  const setTag = useCallback((value: AssetBrowserTag | null) => {
    setFilters(previous => applyFacet(previous, 'tag', value)); setVisible(pageSize);
  }, [pageSize]);
  const setReviewState = useCallback((value: AssetBrowserReviewState | null) => {
    setFilters(previous => applyFacet(previous, 'review_state', value)); setVisible(pageSize);
  }, [pageSize]);
  const setCreatedBucket = useCallback((value: AssetBrowserCreatedBucket | null) => {
    setFilters(previous => applyFacet(previous, 'created_bucket', value)); setVisible(pageSize);
  }, [pageSize]);
  const setReferenced = useCallback((value: AssetBrowserReferenceFilter | null) => {
    setFilters(previous => applyFacet(previous, 'reference', value));
    setVisible(pageSize);
  }, [pageSize]);
  const resetFilters = useCallback(() => {
    setFilters(previous => clearFilters(previous)); setVisible(pageSize);
  }, [pageSize]);
  const changePageSize = useCallback((value: number) => {
    const size = boundPageSize(value);
    setPageSize(size); setVisible(size);
  }, []);
  const loadMore = useCallback(() => {
    // 只扩大可见窗口；不再发请求，因此永远不可能无界拉取。
    setVisible(previous => Math.min(previous + pageSize, Math.max(previous, filtered.length)));
  }, [pageSize, filtered.length]);

  const impact = useCallback((assetIdValue?: string): AssetBrowserImpact | undefined => {
    const id = assetIdValue ?? selectedId ?? undefined;
    if (!id) return undefined;
    // 引用关系尚未核实（读取失败或还没读）时返回 `undefined`：调用方必须显示
    // 未核实，绝不显示"没有被使用"。
    if (referenceState !== 'READY') return undefined;
    const row = rows.find(item => item.id === id);
    if (!row) return undefined;
    return sourceVersionImpact({ asset_id: row.id, version: row.version, digest: row.digest },
      referenceMap.current.get(row.id) ?? []);
  }, [rows, selectedId, referenceState]);

  const deleteImpact = useCallback((assetIdValue?: string): AssetBrowserDeleteImpact | undefined => {
    const id = assetIdValue ?? selectedId ?? undefined;
    if (!id) return undefined;
    if (referenceState !== 'READY') return undefined;
    const row = rows.find(item => item.id === id);
    if (!row) return undefined;
    return assetDeleteImpact(row, referenceMap.current.get(row.id) ?? []);
  }, [rows, selectedId, referenceState]);

  const compareWith = useCallback((other: AssetBrowserAsset): AssetBrowserCompareResult | undefined =>
    detail ? compareVersions(detail, other) : undefined, [detail]);

  /** 只做本地预检；**不**执行目标模块、不复制内容、不写任何东西。 */
  const sendTo = useCallback((target: AssetBrowserSendTarget, assetIdValue?: string): AssetBrowserSendCheck | undefined => {
    const id = assetIdValue ?? selectedId ?? undefined;
    if (!id) return undefined;
    const row = rows.find(item => item.id === id);
    if (!row) return undefined;
    return checkSendTo(row, target);
  }, [rows, selectedId]);

  return {
    state, problem, assets, rows, filtered, pageRows, facets: facetView, filters, mode, pageSize, visible, more,
    selectedId, detail, detailState, detailProblem, compare, setCompare,
    referenceState, referenceProblem, referenceIndex: referenceMap,
    select: choose, setMode, setQuery, setMediaKind, setTag, setReviewState, setCreatedBucket, setReferenced,
    resetFilters, changePageSize, loadMore, reload, loadReferences, readDetail, impact, deleteImpact, compareWith, sendTo,
    activeFilterCount: countActiveFilters(filters),
    /** 组合根可以据此判断是否需要发出"引用情况未核实"提示。 */
    referencesUnverified: referenceState !== 'READY',
    scopeKey: props.scopeKey,
  };
}
export type AssetBrowserController = ReturnType<typeof useAssetBrowser>;
