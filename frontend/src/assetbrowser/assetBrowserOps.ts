import {
  ASSET_BROWSER_BOUNDS, ASSET_BROWSER_COMPARE_FIELDS, ASSET_BROWSER_COMPARE_FIELD_LABELS,
  ASSET_BROWSER_CREATED_BUCKET_LABELS, ASSET_BROWSER_CREATED_BUCKETS, ASSET_BROWSER_DAY_MS,
  ASSET_BROWSER_EMPTY_FILTERS, ASSET_BROWSER_IMPACT_GROUPS, ASSET_BROWSER_IMPACT_GROUP_LABELS,
  ASSET_BROWSER_MEDIA_KINDS, ASSET_BROWSER_MEDIA_KIND_LABELS, ASSET_BROWSER_REFERENCE_FILTER_LABELS,
  ASSET_BROWSER_REFERENCE_KINDS, ASSET_BROWSER_REFERENCE_KIND_LABELS, ASSET_BROWSER_REFERENCE_STATES,
  ASSET_BROWSER_RELATIONSHIP_LABELS, ASSET_BROWSER_REVIEW_LABELS,
  ASSET_BROWSER_REVIEW_STATES, ASSET_BROWSER_SEND_TARGET_KINDS, ASSET_BROWSER_SEND_TARGET_LABELS,
  ASSET_BROWSER_SOURCE_STATE_LABELS, ASSET_BROWSER_TAG_LABELS, ASSET_BROWSER_TAGS,
  ASSET_BROWSER_UNVERIFIED,
  type AssetBrowserAsset, type AssetBrowserCompareEntry, type AssetBrowserCompareField,
  type AssetBrowserCompareResult, type AssetBrowserCreatedBucket, type AssetBrowserDeleteImpact,
  type AssetBrowserFacets,
  type AssetBrowserFacetOption, type AssetBrowserFilters, type AssetBrowserImpact,
  type AssetBrowserImpactEntry, type AssetBrowserImpactGroup, type AssetBrowserImpactGroupView,
  type AssetBrowserMediaKind, type AssetBrowserReference, type AssetBrowserReferenceCounts,
  type AssetBrowserReferenceFilter, type AssetBrowserReferenceKind, type AssetBrowserReferenceState,
  type AssetBrowserReferencedBy, type AssetBrowserRelationshipGraph, type AssetBrowserRelationshipType,
  type AssetBrowserReviewState, type AssetBrowserRow, type AssetBrowserSendTarget,
} from './assetBrowserTypes';

/**
 * UX-03 的**纯函数**层。
 *
 * 这里没有任何 I/O：不读磁盘、不下载、不解码内容、不查凭据、不触发目标模块。
 * 所有输入都是 owner 已经投影出来的可授权元数据，因此"搜索"永远不可能越过
 * 授权范围去扫描或打开别的内容。
 */

/* -------------------------------------------------------------- 行投影 / 分桶 */

/** 由 owner 自己写出的时间戳算出时间桶；解析不了就是 `UNRECORDED`，绝不当作 0。 */
export function createdBucket(createdAt: string, nowMs: number): AssetBrowserCreatedBucket {
  const at = Date.parse(createdAt);
  if (!Number.isFinite(at) || !Number.isFinite(nowMs)) return 'UNRECORDED';
  const age = nowMs - at;
  // 未来时间戳（时钟偏移）不算"今天"，仍然是未记录 —— 不猜。
  if (age < 0) return 'UNRECORDED';
  if (age < ASSET_BROWSER_DAY_MS) return 'TODAY';
  if (age < 7 * ASSET_BROWSER_DAY_MS) return 'LAST_7_DAYS';
  if (age < 30 * ASSET_BROWSER_DAY_MS) return 'LAST_30_DAYS';
  return 'OLDER';
}

/**
 * 单资产 → 一行。
 *
 * `reference_counts` 初始为 `null`：引用情况**尚未读取**，不是"0 个引用"。
 * 只有 `withReferenceCounts()` 真的算出来之后才会变成数字。
 */
export function assetBrowserRow(asset: AssetBrowserAsset, nowMs: number): AssetBrowserRow {
  const at = Date.parse(asset.created_at);
  return {
    id: asset.id,
    filename: asset.filename,
    kind: asset.kind,
    media_kind: asset.media_kind,
    media_type: asset.media_type,
    size: asset.size,
    digest: asset.digest,
    version: asset.version,
    review_state: asset.review_state,
    created_at: asset.created_at,
    created_at_ms: Number.isFinite(at) ? at : null,
    created_bucket: createdBucket(asset.created_at, nowMs),
    tags: [...asset.tags],
    integrity: asset.provenance?.integrity ?? null,
    stale: asset.provenance?.stale ?? null,
    license_label: asset.provenance?.license_label ?? null,
    license_verification: asset.provenance?.license_verification ?? null,
    deleted: asset.deleted,
    reference_counts: null,
  };
}

export function assetBrowserRows(assets: readonly AssetBrowserAsset[], nowMs: number): AssetBrowserRow[] {
  return assets.map(asset => assetBrowserRow(asset, nowMs));
}

/* ------------------------------------------------------------------ 引用索引 */

export function emptyReferenceCounts(): AssetBrowserReferenceCounts {
  return {
    total: 0,
    by_kind: { ASSET: 0, CHAPTER: 0, SCREENPLAY: 0, UNKNOWN: 0 },
    by_relationship: {
      SOURCE_OF: 0, DERIVED_FROM: 0, REFERENCES: 0, USED_IN: 0, ALTERNATE_VERSION: 0, APPROVED_FOR: 0, LINKED_CONTEXT: 0,
    },
    not_current: 0,
  };
}

export function referenceCounts(entries: readonly AssetBrowserReferencedBy[]): AssetBrowserReferenceCounts {
  const byKind = { ASSET: 0, CHAPTER: 0, SCREENPLAY: 0, UNKNOWN: 0 } as Record<AssetBrowserReferenceKind, number>;
  const byRelationship = {
    SOURCE_OF: 0, DERIVED_FROM: 0, REFERENCES: 0, USED_IN: 0, ALTERNATE_VERSION: 0, APPROVED_FOR: 0, LINKED_CONTEXT: 0,
  } as Record<AssetBrowserRelationshipType, number>;
  let notCurrent = 0;
  for (const entry of entries) {
    byKind[entry.kind] += 1;
    byRelationship[entry.relationship] += 1;
    if (entry.state !== 'CURRENT') notCurrent += 1;
  }
  return { total: entries.length, by_kind: byKind, by_relationship: byRelationship, not_current: notCurrent };
}

/** 按当前行集合写入引用计数；没有索引时保持不变（`null` = 未核实）。 */
export function withReferenceCounts(
  rows: readonly AssetBrowserRow[], index: ReadonlyMap<string, readonly AssetBrowserReferencedBy[]>,
): AssetBrowserRow[] {
  return rows.map(row => ({ ...row, reference_counts: referenceCounts(index.get(row.id) ?? []) }));
}

/**
 * 由 `GET /projects/{nid}/studio/relationships` 的原始投影推导「谁引用了 X」。
 *
 * - 声明关系边（`owner === 'ASSET_RELATIONSHIPS'`）：`from` 引用 `target`，
 *   引用方的种类用 owner 给出的 `target.kind`（`ASSET` / `CHAPTER` / `SCREENPLAY`）；
 *   `UNAVAILABLE` 边没有任何可核实目标，因此归入 `UNKNOWN`。
 * - 原始来源边（`owner === 'ASSET_LINEAGE'`）：它是 `from` 派生自 `target`，
 *   所以 `target` 被 `from` 使用；这是 `DERIVED_FROM`，不是新关系类型。
 *
 * **绝不**从 id 猜模块。owner 的关系没有镜头 / 节点 / 时间线的种类信息，因此
 * 引用方的 `group` 一律是 `UNKNOWN`（界面显示未核实）；如果调用方**自己**知道
 * 目标模块（例如目标模块回传），再用 `registerModuleReference()` 补一条可核实的记录。
 */
export function referenceIndex(graph: AssetBrowserRelationshipGraph): Map<string, AssetBrowserReferencedBy[]> {
  const index = new Map<string, AssetBrowserReferencedBy[]>();
  const nodes = new Map(graph.nodes.map(node => [node.id, node]));
  const push = (assetIdValue: string, entry: AssetBrowserReferencedBy) => {
    if (assetIdValue === entry.id) return;
    const current = index.get(assetIdValue);
    if (current) current.push(entry);
    else index.set(assetIdValue, [entry]);
  };
  const sourceOf = (id: string): { label: string | null; version: number | null; digest: string | null } => {
    const node = nodes.get(id);
    return node ? { label: node.label || null, version: node.version, digest: node.digest } : { label: null, version: null, digest: null };
  };
  for (const edge of graph.edges) {
    const from = sourceOf(edge.from);
    const state: AssetBrowserReferenceState = (ASSET_BROWSER_REFERENCE_STATES as readonly string[]).includes(edge.state)
      ? edge.state : 'UNVERIFIED';
    if (edge.target.id === null) continue;
    if (edge.owner === 'ASSET_LINEAGE') {
      push(edge.target.id, {
        id: edge.from, kind: 'ASSET', group: 'UNKNOWN', label: from.label, relationship: 'DERIVED_FROM', state,
        bound_version: from.version, bound_digest: from.digest,
      });
      continue;
    }
    push(edge.target.id, {
      id: edge.from, kind: edge.target.kind ?? 'UNKNOWN', group: 'UNKNOWN', label: from.label,
      relationship: edge.type, state, bound_version: from.version, bound_digest: from.digest,
    });
  }
  const sorted = new Map<string, AssetBrowserReferencedBy[]>();
  for (const [assetIdValue, entries] of index) {
    const seen = new Set<string>();
    const unique = entries.filter(entry => {
      const key = JSON.stringify([entry.id, entry.kind, entry.relationship, entry.state, entry.bound_version, entry.bound_digest]);
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
    unique.sort((left, right) => (left.kind === right.kind
      ? String(left.id).localeCompare(String(right.id)) || left.relationship.localeCompare(right.relationship)
      : ASSET_BROWSER_REFERENCE_KINDS.indexOf(left.kind) - ASSET_BROWSER_REFERENCE_KINDS.indexOf(right.kind)));
    sorted.set(assetIdValue, unique);
  }
  return sorted;
}

/**
 * 用调用方**自己核实过**的目标模块信息补一条引用。owner 的关系没有模块种类，
 * 所以唯一能得到"镜头 / 节点 / 时间线"分组的途径就是目标模块主动回传。
 */
export function registerModuleReference(
  index: ReadonlyMap<string, readonly AssetBrowserReferencedBy[]>, assetIdValue: string,
  entry: { id: string; kind: AssetBrowserReferenceKind; group: AssetBrowserImpactGroup; label?: string | null;
    relationship: AssetBrowserRelationshipType; state?: AssetBrowserReferenceState;
    bound_version?: number | null; bound_digest?: string | null },
): Map<string, AssetBrowserReferencedBy[]> {
  const next = new Map<string, AssetBrowserReferencedBy[]>();
  for (const [key, value] of index) next.set(key, [...value]);
  const record: AssetBrowserReferencedBy = {
    id: entry.id,
    kind: entry.kind,
    group: entry.group,
    label: entry.label ?? null,
    relationship: entry.relationship,
    state: entry.state ?? 'UNVERIFIED',
    bound_version: entry.bound_version ?? null,
    bound_digest: entry.bound_digest ?? null,
  };
  const current = next.get(assetIdValue) ?? [];
  if (!current.some(item => JSON.stringify(item) === JSON.stringify(record))) next.set(assetIdValue, [...current, record]);
  return next;
}

/* ------------------------------------------------------------------ 搜索面 */

/**
 * 搜索面：**只**是 owner 已经投影出来的元数据。
 *
 * 刻意**不**包含 `parameters` 的任意嵌套值、内容、文件名以外的路径，或任何需要
 * 打开 / 解码 / 扫描磁盘才能得到的东西。因此搜索永远不可能越过授权范围。
 */
export function searchableText(row: AssetBrowserRow): string {
  const parts: string[] = [row.filename, row.kind, row.media_type, row.digest];
  if (row.media_kind) parts.push(ASSET_BROWSER_MEDIA_KIND_LABELS[row.media_kind]);
  parts.push(ASSET_BROWSER_REVIEW_LABELS[row.review_state]);
  for (const tag of row.tags) parts.push(tag, ASSET_BROWSER_TAG_LABELS[tag]);
  if (row.integrity) parts.push(row.integrity);
  if (row.license_label) parts.push(row.license_label);
  if (row.reference_counts) {
    for (const [kind, count] of Object.entries(row.reference_counts.by_kind)) {
      if (count > 0) parts.push(ASSET_BROWSER_REFERENCE_KIND_LABELS[kind as AssetBrowserReferenceKind]);
    }
    for (const [type, count] of Object.entries(row.reference_counts.by_relationship)) {
      if (count > 0) parts.push(ASSET_BROWSER_RELATIONSHIP_LABELS[type as AssetBrowserRelationshipType]);
    }
  }
  return parts.join('\u0000').toLocaleLowerCase();
}

export function matchesQuery(row: AssetBrowserRow, query: string): boolean {
  const needle = query.trim().toLocaleLowerCase();
  if (!needle) return true;
  const haystack = searchableText(row);
  return needle.split(/\s+/).every(term => haystack.includes(term));
}

/* ------------------------------------------------------------------ 过滤 / 面 */

export function rowMatchesFilters(row: AssetBrowserRow, filters: AssetBrowserFilters): boolean {
  if (!matchesQuery(row, filters.query)) return false;
  if (filters.media_kind !== null && row.media_kind !== filters.media_kind) return false;
  if (filters.tag !== null && !row.tags.includes(filters.tag)) return false;
  if (filters.review_state !== null && row.review_state !== filters.review_state) return false;
  if (filters.created_bucket !== null && row.created_bucket !== filters.created_bucket) return false;
  if (filters.reference !== null) {
    // 引用计数不可读时**不**匹配 REFERENCED / UNREFERENCED —— 未核实不等于 0。
    if (filters.reference === 'UNVERIFIED') return row.reference_counts === null;
    if (row.reference_counts === null) return false;
    if (filters.reference === 'REFERENCED' && row.reference_counts.total === 0) return false;
    if (filters.reference === 'UNREFERENCED' && row.reference_counts.total > 0) return false;
  }
  return true;
}

export function filterRows(rows: readonly AssetBrowserRow[], filters: AssetBrowserFilters): AssetBrowserRow[] {
  return rows.filter(row => rowMatchesFilters(row, filters));
}

/** 只换搜索词。 */
export function withQuery(filters: AssetBrowserFilters, query: string): AssetBrowserFilters {
  return { ...filters, query };
}
export function applyFacet<K extends keyof AssetBrowserFilters>(
  filters: AssetBrowserFilters, facet: K, value: AssetBrowserFilters[K],
): AssetBrowserFilters {
  return { ...filters, [facet]: value };
}
export function clearFilters(filters: AssetBrowserFilters): AssetBrowserFilters {
  return { ...ASSET_BROWSER_EMPTY_FILTERS, query: filters.query };
}
export function countActiveFilters(filters: AssetBrowserFilters): number {
  return [filters.media_kind, filters.tag, filters.review_state, filters.created_bucket, filters.reference]
    .filter(value => value !== null).length;
}

function options<T extends string>(rows: readonly AssetBrowserRow[], read: (row: AssetBrowserRow) => T[],
  order: readonly T[]): AssetBrowserFacetOption<T>[] {
  const counts = new Map<T, number>();
  for (const row of rows) for (const value of new Set(read(row))) counts.set(value, (counts.get(value) ?? 0) + 1);
  return order.map(value => ({ value, label: String(value), count: counts.get(value) ?? 0 }));
}

/**
 * 每个面的计数**只**由当前行集合推导（不是"总库计数"），并且每个面都保留计数为
 * 0 的取值 —— 0 是一个可核实的结论，"缺了这一项"不是。
 *
 * 引用面特别处理：引用计数为 `null`（关系投影不可读）的行计入 `UNVERIFIED`，
 * 绝不被算成 `UNREFERENCED`。
 */
export function facets(rows: readonly AssetBrowserRow[]): AssetBrowserFacets {
  const media = options<AssetBrowserMediaKind | 'UNKNOWN'>(rows, row => [row.media_kind ?? 'UNKNOWN'],
    [...ASSET_BROWSER_MEDIA_KINDS, 'UNKNOWN'] as const);
  const tagValues = [...ASSET_BROWSER_TAGS.map(([id]) => id), 'UNTAGGED'] as const;
  const tag = options<typeof tagValues[number]>(rows, row => row.tags.length ? [...row.tags] : ['UNTAGGED'], tagValues);
  const review = options<AssetBrowserReviewState>(rows, row => [row.review_state], ASSET_BROWSER_REVIEW_STATES);
  const bucket = options<AssetBrowserCreatedBucket>(rows, row => [row.created_bucket], ASSET_BROWSER_CREATED_BUCKETS);
  const reference = options<AssetBrowserReferenceFilter>(rows, row => [row.reference_counts === null
    ? 'UNVERIFIED' : row.reference_counts.total > 0 ? 'REFERENCED' : 'UNREFERENCED'],
    ['REFERENCED', 'UNREFERENCED', 'UNVERIFIED'] as const);
  return {
    media_kind: media.map(option => ({ ...option, label: option.value === 'UNKNOWN'
      ? ASSET_BROWSER_UNVERIFIED : ASSET_BROWSER_MEDIA_KIND_LABELS[option.value] })),
    tag: tag.map(option => ({ ...option, label: option.value === 'UNTAGGED'
      ? '未打标签' : ASSET_BROWSER_TAG_LABELS[option.value] })),
    review_state: review.map(option => ({ ...option, label: ASSET_BROWSER_REVIEW_LABELS[option.value] })),
    created_bucket: bucket.map(option => ({ ...option, label: ASSET_BROWSER_CREATED_BUCKET_LABELS[option.value] })),
    reference: reference.map(option => ({ ...option, label: ASSET_BROWSER_REFERENCE_FILTER_LABELS[option.value] })),
    total: rows.length,
    reference_unverified: rows.filter(row => row.reference_counts === null).length,
  };
}

/* -------------------------------------------------------------------- 分页 */

/** 页大小永远有界：既不一次拉全库，也不允许 0 或荒谬值。 */
export function boundPageSize(value: number): number {
  if (!Number.isFinite(value)) return ASSET_BROWSER_BOUNDS.page_size_default;
  const size = Math.floor(value);
  if (size < ASSET_BROWSER_BOUNDS.page_size_min) return ASSET_BROWSER_BOUNDS.page_size_min;
  if (size > ASSET_BROWSER_BOUNDS.page_size_max) return ASSET_BROWSER_BOUNDS.page_size_max;
  return size;
}
export function visibleRows(rows: readonly AssetBrowserRow[], visible: number): AssetBrowserRow[] {
  return rows.slice(0, Math.max(0, Math.min(Math.floor(visible), rows.length)));
}
export function hasMoreRows(rows: readonly AssetBrowserRow[], visible: number): boolean {
  return rows.length > visible;
}

/* ------------------------------------------------------------------ 传参引用 */

/**
 * 「送到目标模块」的**唯一**载荷：原资产 ID / 版本 / SHA-256。
 * 版本缺失时返回 `null`（调用方必须显式处理"无法传参"，绝不猜一个版本）。
 */
export function sendToReference(row: AssetBrowserRow): AssetBrowserReference | null {
  if (row.version === null || !Number.isSafeInteger(row.version) || row.version < 1) return null;
  return { asset_id: row.id, version: row.version, digest: row.digest };
}

export type AssetBrowserSendCheck =
  | { allowed: true; reference: AssetBrowserReference; target: AssetBrowserSendTarget }
  | { allowed: false; reason: 'NO_VERSION' | 'MEDIA_KIND_MISMATCH' | 'MEDIA_KIND_UNKNOWN';
      message: string; target: AssetBrowserSendTarget };

/**
 * 送到目标模块前的**本地预检**。它只判断"这种目标模块是否接受这种媒体"，不做任何
 * 执行、复制或写入；真正的准入仍由目标模块自己决定。
 */
export function checkSendTo(row: AssetBrowserRow, target: AssetBrowserSendTarget): AssetBrowserSendCheck {
  const reference = sendToReference(row);
  if (reference === null) {
    return { allowed: false, reason: 'NO_VERSION', target, message: '此素材没有可核实的版本号，无法传给其他模块。' };
  }
  if (row.media_kind === null) {
    return { allowed: false, reason: 'MEDIA_KIND_UNKNOWN', target,
      message: `原 owner 未把此素材归入图片 / 视频 / 音频，${ASSET_BROWSER_SEND_TARGET_LABELS[target]}不能引用它。` };
  }
  if (!ASSET_BROWSER_SEND_TARGET_KINDS[target].includes(row.media_kind)) {
    return { allowed: false, reason: 'MEDIA_KIND_MISMATCH', target,
      message: `${ASSET_BROWSER_SEND_TARGET_LABELS[target]}只接受${sendTargetAccepts(target)}；此素材是${ASSET_BROWSER_MEDIA_KIND_LABELS[row.media_kind]}。` };
  }
  return { allowed: true, reference, target };
}

/** 目标模块可接受的全部媒体种类（面板用它解释为什么某些目标被禁用）。 */
export function sendTargetAccepts(target: AssetBrowserSendTarget): string {
  return ASSET_BROWSER_SEND_TARGET_KINDS[target].map(kind => ASSET_BROWSER_MEDIA_KIND_LABELS[kind]).join(' / ');
}

/* ------------------------------------------------------------------ 版本对比 */

const parentText = (asset: AssetBrowserAsset): string | null => {
  const parents = asset.provenance?.parents;
  if (!parents || !parents.length) return null;
  return parents.map(parent => [
    parent.id ?? ASSET_BROWSER_UNVERIFIED,
    parent.version === null ? ASSET_BROWSER_UNVERIFIED : `v${parent.version}`,
    parent.digest ?? ASSET_BROWSER_UNVERIFIED,
    ASSET_BROWSER_SOURCE_STATE_LABELS[parent.state],
  ].join(' · ')).join(' | ');
};
const sourceText = (asset: AssetBrowserAsset): string | null => {
  const sources = asset.provenance?.sources;
  if (!sources || !sources.length) return null;
  return sources.map(source => [
    source.id ?? ASSET_BROWSER_UNVERIFIED,
    source.version === null ? ASSET_BROWSER_UNVERIFIED : `v${source.version}`,
    source.digest ?? ASSET_BROWSER_UNVERIFIED,
    ASSET_BROWSER_SOURCE_STATE_LABELS[source.state],
  ].join(' · ')).join(' | ');
};

/** 每个字段的展示值；`null` 表示"owner 没披露"，因此无法对比而不是"相同"。 */
function compareValue(asset: AssetBrowserAsset, field: AssetBrowserCompareField): string | null {
  switch (field) {
    case 'id': return asset.id;
    case 'filename': return asset.filename;
    case 'kind': return asset.kind;
    case 'media_type': return asset.media_type;
    case 'size': return String(asset.size);
    case 'digest': return asset.digest;
    case 'version': return asset.version === null ? null : String(asset.version);
    case 'created_at': return asset.created_at;
    case 'review_state': return ASSET_BROWSER_REVIEW_LABELS[asset.review_state];
    case 'tags': return asset.tags.length ? asset.tags.map(tag => ASSET_BROWSER_TAG_LABELS[tag]).join(' · ') : null;
    case 'origin': return asset.provenance?.origin ?? null;
    case 'integrity': return asset.provenance?.integrity ?? null;
    case 'stale': return asset.provenance?.stale === null || asset.provenance?.stale === undefined
      ? null : asset.provenance.stale ? '来源已过期' : '来源当前';
    case 'license_label': return asset.provenance?.license_label ?? null;
    case 'license_verification': return asset.provenance?.license_verification ?? null;
    case 'operation': return asset.provenance?.operation ?? null;
    case 'parents': return parentText(asset);
    case 'sources': return sourceText(asset);
  }
}

/**
 * 新旧版本对比：逐字段给出显式的 same / different / unverifiable。
 *
 * 规则**故意保守**：任一侧没有披露（`null`）就是 `UNVERIFIABLE`，既不是"相同"，
 * 也不是"不同"。`identical` 只统计被核实为相同且全部可比的情况；`differs` 只统计
 * 被核实为不同的字段。
 */
export function compareVersions(left: AssetBrowserAsset, right: AssetBrowserAsset): AssetBrowserCompareResult {
  const entries: AssetBrowserCompareEntry[] = ASSET_BROWSER_COMPARE_FIELDS.map(field => {
    const leftValue = compareValue(left, field), rightValue = compareValue(right, field);
    const verdict = leftValue === null || rightValue === null ? 'UNVERIFIABLE'
      : leftValue === rightValue ? 'SAME' : 'DIFFERENT';
    return { field, label: ASSET_BROWSER_COMPARE_FIELD_LABELS[field], verdict, left: leftValue, right: rightValue };
  });
  const changed = entries.filter(entry => entry.verdict === 'DIFFERENT').map(entry => entry.field);
  const unverifiable = entries.filter(entry => entry.verdict === 'UNVERIFIABLE').map(entry => entry.field);
  return {
    left_id: left.id,
    right_id: right.id,
    same_asset: left.id === right.id,
    entries,
    changed,
    unverifiable,
    identical: changed.length === 0 && unverifiable.length === 0,
    differs: changed.length > 0,
    content_differs: left.digest && right.digest ? left.digest !== right.digest : null,
  };
}

/* ------------------------------------------------------------------ 影响面 */

/**
 * 新的来源版本带来的影响面：老 vs 新的差异 + "被哪些镜头 / 节点 / 时间线使用"。
 *
 * `current.version` / `current.digest` 是**当前**（新）版本；每一条引用的
 * `bound_version` / `bound_digest` 是引用当时绑定的版本。只有两者都被披露才能
 * 判断"这条引用需要重新确认"；否则它是未核实。
 *
 * 关键约束：这里 `automatic_update: false`。本函数只**报告**差异，不会更新任何
 * 镜头 / 节点 / 时间线；只有用户显式选择才会由各自的 owner 更新绑定。
 */
export function sourceVersionImpact(
  current: { asset_id: string; version: number | null; digest: string }, referencedBy: readonly AssetBrowserReferencedBy[],
): AssetBrowserImpact {
  const entries: AssetBrowserImpactEntry[] = referencedBy.map(entry => {
    const comparable = entry.bound_version !== null && current.version !== null && entry.bound_digest !== null;
    const matches = !comparable ? null
      : entry.bound_version === current.version && entry.bound_digest === current.digest;
    return { ...entry, matches_current: matches };
  });
  const groups: AssetBrowserImpactGroupView[] = ASSET_BROWSER_IMPACT_GROUPS.map(group => {
    const items = entries.filter(entry => entry.group === group);
    return {
      group,
      label: ASSET_BROWSER_IMPACT_GROUP_LABELS[group],
      items,
      needs_decision: items.filter(entry => entry.matches_current === false).length,
      unverified: items.filter(entry => entry.group === 'UNKNOWN' || entry.matches_current === null).length,
    };
  });
  return {
    source: { asset_id: current.asset_id, version: current.version, digest: current.digest },
    groups,
    total: entries.length,
    versions_comparable: current.version !== null && referencedBy.some(entry => entry.bound_version !== null),
    automatic_update: false,
    unverified_is_not_absent: true,
  };
}

/**
 * 删除前的可用影响面报告（形状见 `assetBrowserTypes.ts::AssetBrowserDeleteImpact`）。
 *
 * owner（`workspace.py::lifecycle()`）在有子引用时直接拒绝并抛
 * `CREATIVE_ASSET_IN_USE`；`storage()` 自己声明 `physical_cleanup_available: false`，
 * 删除是软删除 + 回收站。这里**没有任何删除动作**，也没有任何"绕开安全删除"的
 * 路径：`physical_delete` 与 `content_removed` 永远是 `false`。
 */
export function assetDeleteImpact(row: AssetBrowserRow, referencedBy: readonly AssetBrowserReferencedBy[]): AssetBrowserDeleteImpact {
  const reported = sourceVersionImpact({ asset_id: row.id, version: row.version, digest: row.digest }, referencedBy);
  const all = reported.groups.flatMap(group => group.items);
  const blocking = all.filter(entry => entry.state !== 'DELETED');
  const unverified = all.filter(entry => entry.group === 'UNKNOWN' || entry.matches_current === null);
  return {
    asset: { asset_id: row.id, version: row.version, digest: row.digest, filename: row.filename },
    reported,
    blocking,
    blocking_total: blocking.length,
    unverified_total: unverified.length,
    physical_delete: false,
    content_removed: false,
    refusable_by_owner: blocking.length > 0,
    message: blocking.length
      ? `仍有 ${blocking.length} 处引用此素材，原资产 owner 会拒绝删除。删除仍然只是软删除（回收站），不会物理删除你的文件。`
      : '当前没有可核实的引用；删除仍由原资产 owner 执行软删除（回收站），不会物理删除你的文件。',
  };
}

/* ------------------------------------------------------------------ 选择模型 */

/**
 * 网格与列表共享的**同一个**选择模型：只有一个 `selectedId`，
 * 切换视图模式不改变选择，也不会因为某一行不在当前可见页而清空它。
 */
export type AssetBrowserSelection = { selectedId: string | null; anchorId: string | null };

export const EMPTY_SELECTION: AssetBrowserSelection = Object.freeze({ selectedId: null, anchorId: null });

export function selectAsset(selection: AssetBrowserSelection, assetIdValue: string | null): AssetBrowserSelection {
  if (assetIdValue === null) return { selectedId: null, anchorId: null };
  void selection;
  return { selectedId: assetIdValue, anchorId: assetIdValue };
}
export function selectionIsVisible(rows: readonly AssetBrowserRow[], visible: number, selection: AssetBrowserSelection): boolean {
  if (selection.selectedId === null) return false;
  return visibleRows(rows, visible).some(row => row.id === selection.selectedId);
}
