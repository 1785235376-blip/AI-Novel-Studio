import { ApiError } from '../api';
import {
  ASSET_BROWSER_AUTHOR_DECLARATION, ASSET_BROWSER_BOUNDS, ASSET_BROWSER_ERROR_CODES,
  ASSET_BROWSER_INTEGRITY_STATES, ASSET_BROWSER_MEDIA_KINDS, ASSET_BROWSER_OWNER_REVIEW_STATUSES,
  ASSET_BROWSER_RELATIONSHIP_REFERENCE_KINDS,
  ASSET_BROWSER_RELATIONSHIP_SEMANTICS, ASSET_BROWSER_RELATIONSHIP_STATES, ASSET_BROWSER_RELATIONSHIP_TYPES,
  ASSET_BROWSER_SOURCE_STATES, ASSET_BROWSER_TAGS,
  type AssetBrowserAsset, type AssetBrowserIntegrity, type AssetBrowserMediaKind,
  type AssetBrowserProvenanceParent, type AssetBrowserProvenanceSource, type AssetBrowserProvenanceView,
  type AssetBrowserRelationshipEdge, type AssetBrowserRelationshipGraph, type AssetBrowserRelationshipNode,
  type AssetBrowserRelationshipReferenceKind, type AssetBrowserRelationshipState, type AssetBrowserRelationshipType,
  type AssetBrowserReviewState, type AssetBrowserSourceState, type AssetBrowserTag,
} from './assetBrowserTypes';

/**
 * UX-03 严格解码器。
 *
 * 规则与 `productionWorkflowContract.ts` / `taskCenterContract.ts` 完全一致：
 * 未知键一律拒绝；每个字符串有界且不得含控制字符；整数必须是安全整数且在范围内；
 * 缺失**不**补默认值 —— 任何「owner 没说的字段」在类型里就是 `null`，绝不猜成
 * `false` / `0` / `CURRENT`。
 *
 * 覆盖的真实形状：
 * - `GET /api/projects/{nid}/studio/assets` → `{ items: StudioAsset[] }`
 *   （`workspace.py::list_assets()` → `_view()` → `asset_library_service.py::public()`）。
 * - `GET /api/projects/{nid}/studio/assets/{aid}` → 单个 `StudioAsset`。
 * - `GET /api/projects/{nid}/studio/relationships` → `StudioRelationshipsGraph`
 *   （`workspace_relationships.py::graph()`）。
 *
 * 刻意**不接受**的东西：`parameters.asset_relationships_v2`（owner 总是剥掉）、
 * A09 关闭时的 `parameters.asset_lineage_v2`、以及任何 `_` 前缀的内部标记 ——
 * 它们要么不会出现，要么就是越权信息。
 */

/* ---------------------------------------------------------------- 基础检查器 */

function invalid(code: string, message: string): never {
  throw new ApiError({ status: 200, code, message });
}
function listInvalid(): never {
  invalid(ASSET_BROWSER_ERROR_CODES.listInvalid, '素材目录数据不可用，请重新读取。');
}
function detailInvalid(): never {
  invalid(ASSET_BROWSER_ERROR_CODES.detailInvalid, '资产详情数据不可用，请重新读取。');
}
function graphInvalid(): never {
  invalid(ASSET_BROWSER_ERROR_CODES.relationshipsInvalid, '引用关系数据不可用，请重新读取。');
}
function mismatch(): never {
  invalid(ASSET_BROWSER_ERROR_CODES.scopeMismatch, '返回内容与当前项目或分支不一致，请重新读取。');
}
function object(value: unknown, allowed: readonly string[], refuse: () => never): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) refuse();
  const row = value as Record<string, unknown>;
  if (Object.keys(row).some(key => !allowed.includes(key))) refuse();
  return row;
}
/** 控制字符（含 DEL）在用户可见文本里一律是拒绝项，不是清洗项。 */
const CONTROL = /[\u0000-\u001f\u007f]/;

function text(value: unknown, maximum: number, refuse: () => never, allowEmpty = false): string {
  if (typeof value !== 'string' || value.length > maximum || CONTROL.test(value)
    || (!allowEmpty && !value.trim())) refuse();
  return value;
}
function optionalText(value: unknown, maximum: number, refuse: () => never, allowEmpty = false): string | null {
  if (value === null || value === undefined) return null;
  return text(value, maximum, refuse, allowEmpty);
}
function unboundedText(value: unknown, refuse: () => never, allowEmpty = false): string {
  if (typeof value !== 'string' || (!allowEmpty && !value.trim()) || CONTROL.test(value)) refuse();
  return value;
}
function integer(value: unknown, maximum: number, refuse: () => never): number {
  if (typeof value !== 'number' || !Number.isSafeInteger(value) || value < 0 || value > maximum) refuse();
  return value;
}
function optionalInteger(value: unknown, maximum: number, refuse: () => never): number | null {
  if (value === null || value === undefined) return null;
  return integer(value, maximum, refuse);
}
function bool(value: unknown, refuse: () => never): boolean {
  if (typeof value !== 'boolean') refuse();
  return value;
}
function array(value: unknown, maximum: number, refuse: () => never): unknown[] {
  if (!Array.isArray(value) || value.length > maximum) refuse();
  return value;
}
function enumerated<T extends string>(value: unknown, allowed: readonly T[], refuse: () => never): T {
  if (typeof value !== 'string' || !(allowed as readonly string[]).includes(value)) refuse();
  return value as T;
}
function optionalEnumerated<T extends string>(value: unknown, allowed: readonly T[], refuse: () => never): T | null {
  if (value === null || value === undefined) return null;
  return enumerated(value, allowed, refuse);
}
function digest(value: unknown, refuse: () => never): string {
  if (typeof value !== 'string' || !/^[a-f0-9]{64}$/.test(value)) refuse();
  return value;
}
function optionalDigest(value: unknown, refuse: () => never): string | null {
  if (value === null || value === undefined) return null;
  return digest(value, refuse);
}
/**
 * 时间戳：接受 owner 实际写出的两种形状 ——
 * - `asset_library_service.py` 的 `now()`（带时区的 ISO-8601）；
 * - 测试/夹具里合法的 `YYYY-MM-DDTHH:MM:SS(.fff)?Z`。
 * 解析不了就是拒绝，不是"排序时当作 0"。
 */
function timestamp(value: unknown, refuse: () => never, allowEmpty = false): string {
  if (allowEmpty && value === '') return '';
  const stamp = text(value, ASSET_BROWSER_BOUNDS.timestamp, refuse);
  if (Number.isNaN(Date.parse(stamp))) refuse();
  return stamp;
}
function optionalTimestamp(value: unknown, refuse: () => never): string | null {
  if (value === null || value === undefined) return null;
  return timestamp(value, refuse);
}
/** 资产 / 关系标识：owner 的 `_identifier()` 语法是 `[A-Za-z0-9][A-Za-z0-9_-]{0,239}`。 */
function assetId(value: unknown, refuse: () => never): string {
  if (typeof value !== 'string' || !/^[A-Za-z0-9][A-Za-z0-9_-]{0,239}$/.test(value)) refuse();
  return value;
}
const tags: readonly string[] = ASSET_BROWSER_TAGS.map(([id]) => id);
function checkedTags(value: unknown, refuse: () => never): AssetBrowserTag[] {
  const rows = array(value, ASSET_BROWSER_BOUNDS.tags, refuse).map(item => {
    const tag = enumerated(item, tags, refuse);
    return tag as AssetBrowserTag;
  });
  if (new Set(rows).size !== rows.length) refuse();
  return rows;
}
/**
 * `license.label` 只在 owner 写了字符串时取用；`source` / `note` 在真实投影里
 * 允许是空字符串（`{"label": "UNSPECIFIED", "source": "", "note": ""}`），
 * 因此这里用 `allowEmpty`，但标签本身仍然必须非空。
 */
function licenseView(value: unknown, refuse: () => never): Pick<AssetBrowserProvenanceView, 'license_label' | 'license_source'> {
  if (value === undefined || value === null) return { license_label: null, license_source: null };
  if (typeof value === 'string') {
    return { license_label: text(value, ASSET_BROWSER_BOUNDS.license_label, refuse, true), license_source: null };
  }
  const row = value as Record<string, unknown>;
  if (typeof row !== 'object' || Array.isArray(row)) refuse();
  return {
    license_label: row.label === null || row.label === undefined
      ? null : text(row.label, ASSET_BROWSER_BOUNDS.license_label, refuse),
    license_source: optionalText(row.source, ASSET_BROWSER_BOUNDS.license_source, refuse, true),
  };
}

/* ------------------------------------------------------------ owner 参数投影 */

/**
 * owner 披露的 `parameters`：原样保留，只做有界与 JSON 安全检查。
 * **不做**语义解读，也**不**把 `asset_relationships_v2` / 关闭状态下的
 * `asset_lineage_v2` 当成可用信息（owner 已经剥掉；若真的出现则是对方违约，
 * 这里同样拒绝，因为那是越权投影）。
 */
function parameters(value: unknown, refuse: () => never): Readonly<Record<string, unknown>> | null {
  if (value === null || value === undefined) return null;
  if (typeof value !== 'object' || Array.isArray(value)) refuse();
  const row = value as Record<string, unknown>;
  if (Object.keys(row).some(key => key.startsWith('_') || key === 'asset_relationships_v2')) refuse();
  let remaining = ASSET_BROWSER_BOUNDS.parameters_entries;
  const walk = (node: unknown, depth: number): unknown => {
    if (remaining <= 0) refuse();
    remaining--;
    if (node === null || typeof node === 'boolean') return node;
    if (typeof node === 'number') {
      if (!Number.isFinite(node)) refuse();
      return node;
    }
    if (typeof node === 'string') return text(node, ASSET_BROWSER_BOUNDS.parameters_string, refuse, true);
    if (depth >= ASSET_BROWSER_BOUNDS.parameters_depth) refuse();
    if (Array.isArray(node)) return node.map(item => walk(item, depth + 1));
    if (typeof node === 'object') {
      const record = node as Record<string, unknown>;
      if (Object.keys(record).some(key => key.startsWith('_'))) refuse();
      return Object.fromEntries(Object.entries(record).map(([key, item]) => [text(key, 120, refuse), walk(item, depth + 1)]));
    }
    refuse();
  };
  const checked = Object.fromEntries(Object.entries(row).map(([key, item]) => [text(key, 120, refuse), walk(item, 1)]));
  return Object.freeze(checked);
}

/* ---------------------------------------------------------------- provenance */

function parentState(value: unknown, refuse: () => never): AssetBrowserSourceState {
  return enumerated(value, ASSET_BROWSER_SOURCE_STATES, refuse);
}
function provenanceParent(value: unknown, refuse: () => never): AssetBrowserProvenanceParent {
  const row = object(value, ['id', 'label', 'version', 'digest', 'state'], refuse);
  return {
    kind: 'PARENT',
    id: optionalText(row.id, ASSET_BROWSER_BOUNDS.asset_id, refuse, true),
    label: optionalText(row.label, ASSET_BROWSER_BOUNDS.label, refuse, true),
    version: optionalInteger(row.version, Number.MAX_SAFE_INTEGER, refuse),
    digest: optionalDigest(row.digest, refuse),
    state: parentState(row.state, refuse),
  };
}
function provenanceSource(value: unknown, refuse: () => never): AssetBrowserProvenanceSource {
  const row = object(value, ['id', 'label', 'version', 'digest', 'state'], refuse);
  return {
    kind: 'SOURCE',
    id: optionalText(row.id, ASSET_BROWSER_BOUNDS.asset_id, refuse, true),
    version: optionalInteger(row.version, Number.MAX_SAFE_INTEGER, refuse),
    digest: optionalDigest(row.digest, refuse),
    state: parentState(row.state, refuse),
  };
}
/**
 * 两个真实生产者（`workspace.py::_production_provenance()` 与
 * `production_lineage.py::_project_asset()`）写入的投影。两者的键集合不同，
 * 但**并集是确定的**：这里列出全部允许键，未知键仍然拒绝。
 */
const PROVENANCE_KEYS = [
  'id', 'label', 'kind', 'version', 'digest', 'deleted', 'integrity', 'origin', 'license', 'license_verification',
  'operation', 'parents', 'sources', 'stale', 'producer', 'declaration_history_versions', 'generation',
  'source_task_id', 'reference_only', 'product_acceptance',
] as const;
const PARENT_KEYS = ['id', 'label', 'version', 'digest', 'state'] as const;
const LICENSE_KEYS = ['label', 'source', 'note'] as const;

function producerView(value: unknown, refuse: () => never): AssetBrowserProvenanceView['producer'] {
  if (value === null || value === undefined) return null;
  const row = object(value, ['declared_by', 'provider_id', 'model_id'], refuse);
  // The original owner exposes these IDs. Actor and arbitrary metadata are not
  // part of this browser projection; never infer an ID from generation/parameters.
  return {
    provider_id: optionalText(row.provider_id, ASSET_BROWSER_BOUNDS.producer_id, refuse, true),
    model_id: optionalText(row.model_id, ASSET_BROWSER_BOUNDS.producer_id, refuse, true),
  };
}

function provenance(value: unknown, refuse: () => never): AssetBrowserProvenanceView | null {
  if (value === null || value === undefined) return null;
  const row = object(value, PROVENANCE_KEYS, refuse);
  const licenseRow = row.license;
  if (licenseRow !== undefined && licenseRow !== null && typeof licenseRow === 'object' && !Array.isArray(licenseRow)) {
    object(licenseRow, LICENSE_KEYS, refuse);
  }
  const license = licenseView(licenseRow, refuse);
  const verification = row.license_verification === undefined || row.license_verification === null
    ? null : enumerated(row.license_verification, [ASSET_BROWSER_AUTHOR_DECLARATION], refuse);
  return {
    // `origin` / `operation` 在真实投影里可以是空字符串，`label` 也可以是空串；
    // "空" 与 "没有披露" 都由 `null` 与 `''` 分别表达，绝不互相顶替。
    origin: optionalText(row.origin, ASSET_BROWSER_BOUNDS.origin, refuse, true),
    producer: producerView(row.producer, refuse),
    integrity: optionalEnumerated<AssetBrowserIntegrity>(row.integrity, ASSET_BROWSER_INTEGRITY_STATES, refuse),
    stale: row.stale === undefined || row.stale === null ? null : bool(row.stale, refuse),
    license_label: license.license_label,
    license_source: license.license_source,
    license_verification: verification,
    operation: optionalText(row.operation, ASSET_BROWSER_BOUNDS.operation, refuse, true),
    parents: array(row.parents === undefined ? [] : row.parents, ASSET_BROWSER_BOUNDS.provenance_parents, refuse)
      .map(item => provenanceParent(item, refuse)),
    sources: array(row.sources === undefined ? [] : row.sources, ASSET_BROWSER_BOUNDS.provenance_sources, refuse)
      .map(item => provenanceSource(item, refuse)),
    declaration_history_versions: array(row.declaration_history_versions === undefined ? [] : row.declaration_history_versions,
      ASSET_BROWSER_BOUNDS.declaration_history, refuse)
      .map(item => integer(item, Number.MAX_SAFE_INTEGER, refuse)),
  };
}

/* -------------------------------------------------------------------- 单资产 */

/** 作者声明的用途标签只能来自 owner 的 `tags`；旧的 `parameters.tags` 也认。 */
function tagsOf(row: Record<string, unknown>): AssetBrowserTag[] {
  if (row.tags !== undefined && row.tags !== null) return checkedTags(row.tags, detailInvalid);
  const declared = row.parameters;
  if (declared && typeof declared === 'object' && !Array.isArray(declared)) {
    const nested = (declared as Record<string, unknown>).tags;
    if (nested !== undefined && nested !== null) return checkedTags(nested, detailInvalid);
  }
  return [];
}

/**
 * 单资产的严格投影。
 *
 * `media_kind` 只在 owner 的 `kind` 正是三种标准取值时存在；`review_state`
 * 在 `public()` 之后**总是** `UNREVIEWED`（owner 剥掉了 `_text_result_review`），
 * 只有调用方显式注入索引时才会通过 `withReviewState()` 覆盖 —— 界面因此绝不
 * 会在目录视图里假装知道审核结论。
 */
export function assetBrowserAsset(value: unknown, projectId: string): AssetBrowserAsset {
  if (typeof projectId !== 'string' || !projectId || projectId.length > ASSET_BROWSER_BOUNDS.project_id) {
    invalid(ASSET_BROWSER_ERROR_CODES.readLocalInvalid, '项目标识不可用，请重新打开工作区。');
  }
  const row = object(value, [
    'id', 'novel_id', 'filename', 'kind', 'media_type', 'size', 'sha256', 'created_at', 'updated_at', 'version',
    'branch_id', 'deleted_at', 'provenance', 'relationships', 'parameters', 'tags', 'manual_mask',
  ], detailInvalid);
  // 缺失或非字符串的 `novel_id` 是**形状**问题（拒绝读取），不是"别的项目"。
  // 只有 owner 明确写出了一个不同的项目标识时才是 scope mismatch。
  if (typeof row.novel_id !== 'string' || !row.novel_id.trim()) detailInvalid();
  if (row.novel_id !== projectId) mismatch();
  const version = integer(row.version, Number.MAX_SAFE_INTEGER, detailInvalid);
  if (version < 1) detailInvalid();
  const kind = unboundedText(row.kind, detailInvalid);
  return {
    id: assetId(row.id, detailInvalid),
    filename: text(row.filename, ASSET_BROWSER_BOUNDS.filename, detailInvalid),
    kind,
    media_kind: (ASSET_BROWSER_MEDIA_KINDS as readonly string[]).includes(kind) ? kind as AssetBrowserMediaKind : null,
    media_type: text(row.media_type, ASSET_BROWSER_BOUNDS.media_type, detailInvalid),
    size: integer(row.size, Number.MAX_SAFE_INTEGER, detailInvalid),
    digest: digest(row.sha256, detailInvalid),
    created_at: timestamp(row.created_at, detailInvalid),
    updated_at: optionalTimestamp(row.updated_at, detailInvalid),
    version,
    branch_id: optionalText(row.branch_id, ASSET_BROWSER_BOUNDS.project_id, detailInvalid),
    deleted: row.deleted_at !== null && row.deleted_at !== undefined,
    review_state: 'UNREVIEWED',
    tags: tagsOf(row),
    provenance: provenance(row.provenance, detailInvalid),
    parameters: parameters(row.parameters, detailInvalid),
  };
}

/**
 * 目录列表：`GET /projects/{nid}/studio/assets` → `{ items: [...] }`。
 * 超出有界条数即拒绝，绝不静默截断成"这是完整清单"。
 */
export function assetBrowserList(value: unknown, projectId: string): AssetBrowserAsset[] {
  const envelope = object(value, ['items'], listInvalid);
  const rows = array(envelope.items, ASSET_BROWSER_BOUNDS.list_items, listInvalid);
  const items = rows.map(item => {
    try {
      return assetBrowserAsset(item, projectId);
    } catch (reason) {
      // 任何单行的形状问题都必须以**列表**码暴露（不是详情码）。
      if (reason instanceof ApiError && reason.problem.code === ASSET_BROWSER_ERROR_CODES.detailInvalid) listInvalid();
      throw reason;
    }
  });
  if (new Set(items.map(item => item.id)).size !== items.length) listInvalid();
  return items;
}

/* ---------------------------------------------------------------- 关系投影 */

const NODE_KEYS = ['id', 'kind', 'asset_kind', 'label', 'version', 'digest'] as const;
const EDGE_TARGET_KEYS = ['kind', 'id', 'version', 'digest', 'label', 'deleted'] as const;
/**
 * 边的允许键：服务端声明关系带 `expected` / `reason` / `created_by` / `created_at`
 * / `semantics`，原始来源边只带 `owner`；本消费者的解码结果两者都会带上，
 * 因此并集是确定且封闭的。
 */
const EDGE_KEYS = ['id', 'from', 'type', 'owner', 'state', 'target', 'expected', 'reason',
  'created_by', 'created_at', 'semantics'] as const;

function relationshipTarget(value: unknown, refuse: () => never, allowPartial: boolean): AssetBrowserRelationshipEdge['target'] {
  const row = object(value, EDGE_TARGET_KEYS, refuse);
  const kind = optionalEnumerated<AssetBrowserRelationshipReferenceKind>(
    row.kind, ASSET_BROWSER_RELATIONSHIP_REFERENCE_KINDS, refuse);
  if (!allowPartial && kind === null) refuse();
  const id = optionalText(row.id, ASSET_BROWSER_BOUNDS.asset_id, refuse);
  const version = optionalInteger(row.version, Number.MAX_SAFE_INTEGER, refuse);
  const digestValue = optionalDigest(row.digest, refuse);
  const label = optionalText(row.label, ASSET_BROWSER_BOUNDS.label, refuse);
  const deleted = row.deleted === undefined || row.deleted === null ? null : bool(row.deleted, refuse);
  // 一条可核实的目标必须四项齐全；否则它只能是 `UNAVAILABLE` 的那种占位。
  if (!allowPartial && (id === null || version === null || digestValue === null)) refuse();
  if (version !== null && version < 1) refuse();
  if (label === null && id === null && kind === null) refuse();
  return { kind, id, version, digest: digestValue, label, deleted };
}

/** 关联当时的绑定目标（`expected`）：四项齐全，缺一项就是拒绝。 */
function expectedTarget(value: unknown, refuse: () => never): NonNullable<
  Extract<AssetBrowserRelationshipEdge, { owner: 'ASSET_RELATIONSHIPS' }>['expected']
> {
  const row = object(value, ['kind', 'id', 'version', 'digest'], refuse);
  return {
    kind: enumerated(row.kind, ASSET_BROWSER_RELATIONSHIP_REFERENCE_KINDS, refuse) as AssetBrowserRelationshipReferenceKind,
    id: optionalText(row.id, ASSET_BROWSER_BOUNDS.asset_id, refuse),
    version: optionalInteger(row.version, Number.MAX_SAFE_INTEGER, refuse),
    digest: optionalDigest(row.digest, refuse),
  };
}

function relationshipNode(value: unknown): AssetBrowserRelationshipNode {  const row = object(value, NODE_KEYS, graphInvalid);
  if (row.kind !== 'ASSET') graphInvalid();
  return {
    id: assetId(row.id, graphInvalid),
    kind: 'ASSET',
    asset_kind: text(row.asset_kind, ASSET_BROWSER_BOUNDS.kind, graphInvalid),
    label: text(row.label, ASSET_BROWSER_BOUNDS.label, graphInvalid, true),
    version: integer(row.version, Number.MAX_SAFE_INTEGER, graphInvalid),
    digest: digest(row.digest, graphInvalid),
  };
}

/**
 * `GET /projects/{nid}/studio/relationships`。
 *
 * owner 的三条自我声明（`executable` / `knowledge_graph` /
 * `automatic_regeneration`）必须是 `false`；这里只复述，不改写。
 * `ASSET_LINEAGE` 的边没有 `semantics` 字段（它是原始 lineage DAG），
 * 本消费者为它补上同一个语义常量而不是另一套词表。
 */
export function assetBrowserRelationships(value: unknown): AssetBrowserRelationshipGraph {
  const row = object(value, ['graph_kind', 'nodes', 'edges', 'executable', 'knowledge_graph', 'automatic_regeneration'], graphInvalid);
  if (row.graph_kind !== 'ASSET_RELATIONSHIPS' || row.executable !== false
    || row.knowledge_graph !== false || row.automatic_regeneration !== false) graphInvalid();
  const nodes = array(row.nodes, ASSET_BROWSER_BOUNDS.graph_nodes, graphInvalid).map(relationshipNode);
  if (new Set(nodes.map(node => node.id)).size !== nodes.length) graphInvalid();
  const nodeIDs = new Set(nodes.map(node => node.id));
  const edges = array(row.edges, ASSET_BROWSER_BOUNDS.graph_edge_ceiling, graphInvalid).map((item): AssetBrowserRelationshipEdge => {
    const edge = object(item, EDGE_KEYS, graphInvalid);    const from = assetId(edge.from, graphInvalid);
    if (!nodeIDs.has(from)) graphInvalid();
    const id = text(edge.id, ASSET_BROWSER_BOUNDS.relationship_id, graphInvalid);
    const type = enumerated(edge.type, ASSET_BROWSER_RELATIONSHIP_TYPES, graphInvalid) as AssetBrowserRelationshipType;
    const state = enumerated(edge.state, ASSET_BROWSER_RELATIONSHIP_STATES, graphInvalid) as AssetBrowserRelationshipState;
    if (edge.owner === 'ASSET_LINEAGE') {
      if (type !== 'DERIVED_FROM') graphInvalid();
      // 原始来源边在服务端没有 `semantics` / `expected` / `reason`；本消费者为它
      // 补上同一个语义常量与显式的"无"，因此解码结果自己也必须能被再次解码。
      if (edge.semantics !== undefined && edge.semantics !== ASSET_BROWSER_RELATIONSHIP_SEMANTICS) graphInvalid();
      if (edge.expected !== undefined && edge.expected !== null) graphInvalid();
      if (edge.reason !== undefined && edge.reason !== null) graphInvalid();
      const lineageTarget = relationshipTarget(edge.target, graphInvalid, state === 'UNAVAILABLE');
      if (lineageTarget.kind !== null && lineageTarget.kind !== 'ASSET') graphInvalid();
      return {
        owner: 'ASSET_LINEAGE', id, from, type: 'DERIVED_FROM', state,
        target: { ...lineageTarget, kind: lineageTarget.kind as 'ASSET' | null },
        expected: null, reason: null, created_by: null, created_at: null,
        semantics: ASSET_BROWSER_RELATIONSHIP_SEMANTICS,
      };
    }
    // 服务端自己不带 `owner`（只有原始来源边带 `ASSET_LINEAGE`）；本消费者的
    // 解码结果会显式写 `ASSET_RELATIONSHIPS`，因此两者都接受 —— 任何其他取值
    // 都拒绝。
    if (edge.owner !== undefined && edge.owner !== 'ASSET_RELATIONSHIPS') graphInvalid();
    if (state !== 'UNAVAILABLE') {
      if (edge.semantics !== undefined && edge.semantics !== ASSET_BROWSER_RELATIONSHIP_SEMANTICS) graphInvalid();
      if (edge.expected === undefined || edge.expected === null) graphInvalid();
      relationshipTarget(edge.expected, graphInvalid, false);
    } else {
      // 不可核实的关系既没有绑定快照，也不会伪造一个空的 `expected`。
      if (edge.expected !== undefined && edge.expected !== null) graphInvalid();
      if (edge.semantics !== undefined && edge.semantics !== ASSET_BROWSER_RELATIONSHIP_SEMANTICS) graphInvalid();
    }
    const target = relationshipTarget(edge.target, graphInvalid, state === 'UNAVAILABLE');
    if (state === 'UNAVAILABLE' && target.id !== null) graphInvalid();
    return {
      owner: 'ASSET_RELATIONSHIPS', id, from, type, state, target,
      expected: edge.expected === undefined || edge.expected === null
        ? null : expectedTarget(edge.expected, graphInvalid),
      reason: optionalText(edge.reason, ASSET_BROWSER_BOUNDS.reason, graphInvalid, true),
      created_by: optionalText(edge.created_by, ASSET_BROWSER_BOUNDS.actor, graphInvalid, true),
      created_at: edge.created_at === undefined || edge.created_at === null
        ? null : timestamp(edge.created_at, graphInvalid),
      semantics: ASSET_BROWSER_RELATIONSHIP_SEMANTICS,
    };
  });
  if (edges.length > ASSET_BROWSER_BOUNDS.graph_edge_ceiling) graphInvalid();
  return { graph_kind: 'ASSET_RELATIONSHIPS', nodes, edges, executable: false, knowledge_graph: false, automatic_regeneration: false };
}

/**
 * `workspace.py::asset_index()` 的 `_index_row()` 投影。它**不是**本模块新增的
 * 端点：调用方（组合根）已经拿到索引时才注入，用来补上目录列表里 owner 不披露的
 * `review_status`。没有注入就是"没有标记"。
 */
export function assetBrowserIndexRow(value: unknown): { id: string; review_status: AssetBrowserReviewState; deleted: boolean } {
  const row = object(value, ['id', 'kind', 'version', 'review_status', 'source_job_id', 'deleted', 'created_at'], detailInvalid);
  const review = row.review_status === null || row.review_status === undefined
    ? 'UNREVIEWED' as AssetBrowserReviewState
    : enumerated(row.review_status, ASSET_BROWSER_OWNER_REVIEW_STATUSES, detailInvalid) as AssetBrowserReviewState;
  return {
    id: assetId(row.id, detailInvalid),
    review_status: review,
    deleted: bool(row.deleted, detailInvalid),
  };
}

/** 覆盖单资产的 owner 审核标记（只允许 owner 自己的三个取值）。 */
export function withReviewState(asset: AssetBrowserAsset, state: AssetBrowserReviewState): AssetBrowserAsset {
  if (!(ASSET_BROWSER_OWNER_REVIEW_STATUSES as readonly string[]).includes(state) && state !== 'UNREVIEWED') {
    invalid(ASSET_BROWSER_ERROR_CODES.readLocalInvalid, '审核标记不可用，请重新读取。');
  }
  return { ...asset, review_state: state };
}

/**
 * 请求侧的本地校验：标识在离开浏览器之前就有界。绝不把未校验的标识拼进 URL。
 */
export function assetBrowserReadTarget(projectId: string, assetIdValue?: string): { project_id: string; asset_id: string | null } {
  if (typeof projectId !== 'string' || !/^[A-Za-z0-9][A-Za-z0-9_-]{0,239}$/.test(projectId)) {
    invalid(ASSET_BROWSER_ERROR_CODES.readLocalInvalid, '项目标识不可用，请重新打开工作区。');
  }
  if (assetIdValue === undefined) return { project_id: projectId, asset_id: null };
  if (typeof assetIdValue !== 'string' || !/^[A-Za-z0-9][A-Za-z0-9_-]{0,239}$/.test(assetIdValue)) {
    invalid(ASSET_BROWSER_ERROR_CODES.readLocalInvalid, '资产标识不可用，请重新选择资产。');
  }
  return { project_id: projectId, asset_id: assetIdValue };
}

/**
 * 本地搜索词：有界、去掉控制字符。**不**做任何磁盘 / 内容访问 —— 搜索面永远是
 * owner 已经投影出来的元数据（见 `assetBrowserOps.ts::searchableText`）。
 */
export function assetBrowserQuery(value: unknown): string {
  if (typeof value !== 'string') {
    invalid(ASSET_BROWSER_ERROR_CODES.queryLocalInvalid, '搜索词不可用，请重新输入。');
  }
  const cleaned = (value as string).replace(/[\u0000-\u001f\u007f]/g, '').trim();
  if (cleaned.length > ASSET_BROWSER_BOUNDS.query) {
    invalid(ASSET_BROWSER_ERROR_CODES.queryLocalInvalid, `搜索词最多 ${ASSET_BROWSER_BOUNDS.query} 个字符，请缩短后重试。`);
  }
  return cleaned;
}
