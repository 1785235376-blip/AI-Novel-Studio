/**
 * UX-04 无限画布与节点工作流操作 —— 纯函数集合。
 *
 * 复用（不重实现）：
 * - `connectionIssue`（`../creative/graphDraft`）是连接合法性的**唯一权威**；本文件的
 *   `compatibleTargets` / `explainConnection` 只消费它的返回值，从不自行判定合法性；
 * - `graphCatalogForSchema`（同上）是图格式与目录的过滤权威；
 * - `graphSelectionRect` / `graphNodesInScreenRect` / `graphNodeHeight` / `clampGraphPosition`
 *   （`../creative/graphCanvasGeometry`）是框选与布局几何的权威；
 * - `GRAPH_NODE_LABELS`（`../creative/studioGraphLabels`）是节点中文名的权威；
 * - `imageGraphDefinitions` / `videoGraphDefinitions` / `productionGraphDefinitions` 是
 *   图格式成员关系的权威。
 *
 * 本文件不发起任何网络请求，不定义新的节点类型，也不改变任何已保存图契约。
 */
import {
  connectionIssue, graphCatalogForSchema, imageGraphDefinitions, videoGraphDefinitions,
} from '../creative/graphDraft';
import {
  GRAPH_NODE_WIDTH, GRAPH_PORT_ROW_HEIGHT, clampGraphPosition, graphNodeHeight,
  graphNodesInScreenRect, graphSelectionRect,
} from '../creative/graphCanvasGeometry';
import { productionGraphDefinitions } from '../creative/studioProductionGraphContract';
import { GRAPH_NODE_LABELS } from '../creative/studioGraphLabels';
import type {
  StudioGraphCatalog, StudioGraphCatalogDefinition, StudioGraphDefinition, StudioGraphDefinitionId,
  StudioGraphEdge, StudioGraphNode, StudioGraphPort, StudioGraphPortType, StudioGraphReferenceState,
} from '../creative/studioGraphTypes';
import {
  CANVAS_OPS_LOCAL_BOUNDS, CANVAS_OPS_LOCAL_SCHEMA, CANVAS_OPS_NODE_ID, CANVAS_NODE_CATEGORIES,
  CANVAS_NODE_CATEGORY_LABELS, CANVAS_SEARCH_MATCH_MAX, CANVAS_SEARCH_QUERY_MAX,
  type CanvasAutoLayoutOptions, type CanvasCatalogEntry, type CanvasCatalogMatch, type CanvasChangeClassification,
  type CanvasChangeReasonCode, type CanvasCompatibleTarget, type CanvasConnectionExplanation,
  type CanvasConnectionIssueCategory, type CanvasConnectionIssueCode, type CanvasMarqueeGeometry,
  type CanvasNodeBudget, type CanvasNodeCategory, type CanvasSearchMatch, type CanvasEdgeBudget,
  type LocalCanvasAnnotation, type LocalCanvasGroup, type LocalCanvasState, type LocalCanvasStateUpdate,
} from './canvasOpsTypes';

/** 本地校验失败：不是网络错误，也不代表服务端结论。 */
export class CanvasOpsLocalError extends Error {
  constructor(public code: string, message: string) {
    super(message);
    this.name = 'CanvasOpsLocalError';
  }
}
function refuse(code: string, message: string): never {
  throw new CanvasOpsLocalError(code, message);
}

/* ------------------------------------------------------------------ *
 * 严格读取器（沿用 productionWorkflowContract 的写法）
 * ------------------------------------------------------------------ */
function record(value: unknown, allowed: readonly string[] | null, code: string, message: string): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) refuse(code, message);
  const row = value as Record<string, unknown>;
  if (allowed && Object.keys(row).some(key => !allowed.includes(key))) refuse(code, message);
  return row;
}
function boundedText(value: unknown, maximum: number, code: string, message: string): string {
  if (typeof value !== 'string' || !value.trim() || value.length > maximum || /[\u0000-\u001f\u007f]/.test(value)) refuse(code, message);
  return value;
}
function flag(value: unknown, code: string, message: string): boolean {
  if (typeof value !== 'boolean') refuse(code, message);
  return value;
}
function rows(value: unknown, maximum: number, code: string, message: string): unknown[] {
  if (!Array.isArray(value) || value.length > maximum) refuse(code, message);
  return value;
}

/**
 * `studioGraphTypes` 的端口类型联合没有对应的运行时数组，这里镜像它以便严格校验。
 * 本批不新增端口类型；端口类型集合的权威仍是 `StudioGraphPortType` 联合本身。
 */
const CANVAS_PORT_TYPES: readonly StudioGraphPortType[] = ['TEXT', 'DIRECTOR_NOTES', 'DRAFT', 'ASSET_REF',
  'MEDIA_CANDIDATE', 'IMAGE_REFERENCES', 'IMAGE_PROMPT', 'DIRECTOR_PLAN', 'STORYBOARD_DATA', 'STORYBOARD_SHOT', 'VIDEO_CANDIDATE'];

/** `GRAPH_NODE_LABELS` 是 `Record<StudioGraphDefinitionId, string>`：它的键就是现存节点类型的闭集。 */
const CANVAS_DEFINITION_IDS: readonly StudioGraphDefinitionId[] = Object.keys(GRAPH_NODE_LABELS) as StudioGraphDefinitionId[];
const CANVAS_DEFINITION_ID_SET = new Set<string>(CANVAS_DEFINITION_IDS);

/**
 * 呈现层角色分类表。类型是 `Record<StudioGraphDefinitionId, …>`：
 * 少写一个现存节点类型或发明一个新类型都无法通过 `tsc`。
 */
export const CANVAS_NODE_ROLE: Record<StudioGraphDefinitionId, CanvasNodeCategory> = {
  text_input: 'TEXT', text_reference: 'TEXT', draft_prepare: 'TEXT', manual_transform: 'TEXT',
  director_note: 'TEXT', human_review: 'TEXT', text_generate: 'TEXT',
  asset_reference: 'ASSET',
  media_generate: 'MEDIA', media_review: 'MEDIA', timeline_export: 'MEDIA',
  image_reference: 'IMAGE', image_prompt: 'IMAGE', image_generate: 'IMAGE', image_style: 'IMAGE', image_upscale: 'IMAGE',
  director_plan: 'STORYBOARD', storyboard_plan: 'STORYBOARD', storyboard_prompt: 'STORYBOARD', storyboard_shot: 'STORYBOARD',
  video_generate: 'VIDEO',
};

function port(value: unknown, code: string, message: string): StudioGraphPort {
  const row = record(value, ['id', 'type', 'required', 'multiple'], code, message);
  const type = boundedText(row.type, 40, code, message);
  if (!CANVAS_PORT_TYPES.includes(type as StudioGraphPortType)) refuse(code, message);
  if (row.multiple !== false) refuse(code, message);
  return {
    id: boundedText(row.id, 120, code, message), type: type as StudioGraphPortType,
    required: flag(row.required, code, message), multiple: false,
  };
}
function portList(value: unknown, code: string, message: string): StudioGraphPort[] {
  return rows(value, 8, code, message).map(item => port(item, code, message));
}

/** 目录一行 -> 只读检索投影；节点类型必须是现存闭集内的取值。 */
function catalogEntry(value: unknown): CanvasCatalogEntry {
  const code = 'CANVAS_OPS_CATALOG_INVALID';
  const message = '节点目录不可用，请重新读取创作图目录。';
  const row = record(value, null, code, message);
  const id = typeof row.id === 'string' && CANVAS_DEFINITION_ID_SET.has(row.id) ? row.id as StudioGraphDefinitionId : undefined;
  if (!id) refuse('CANVAS_OPS_UNKNOWN_DEFINITION', '节点目录包含未知节点类型，请重新读取创作图目录。');
  if (row.version !== 1) refuse(code, message);
  const inputs = portList(row.inputs, code, message), outputs = portList(row.outputs, code, message);
  const blockers = rows(row.blockers, 16, code, message).map(item => boundedText(item, 300, code, message));
  const categories: CanvasNodeCategory[] = [CANVAS_NODE_ROLE[id]];
  if (imageGraphDefinitions.some(item => item === id)) categories.push('IMAGE');
  if (videoGraphDefinitions.some(item => item === id)) categories.push('VIDEO');
  if (productionGraphDefinitions.some(item => item === id)) categories.push('STORYBOARD');
  const label = GRAPH_NODE_LABELS[id];
  const keywords = [id, label, ...categories.map(item => CANVAS_NODE_CATEGORY_LABELS[item]),
    ...inputs.flatMap(item => [item.id, item.type, ...(item.required ? ['必填'] : [])]),
    ...outputs.flatMap(item => [item.id, item.type]), ...blockers]
    .join(' ').toLowerCase().split(/\s+/).filter(Boolean);
  return {
    id, label, category: CANVAS_NODE_ROLE[id], categories: [...new Set(categories)],
    executable: flag(row.executable, code, message), model_called: false, blockers, inputs, outputs,
    keywords, haystack: keywords.join(' '),
  };
}

/**
 * 从现存目录建立只读检索索引。目录缺失时返回空列表（尚未读取目录，不是错误）；
 * 目录存在但结构不符合原所有者声明时抛 `CanvasOpsLocalError`，不猜测、不静默跳过。
 */
export function nodeSearchIndex(catalog?: StudioGraphCatalog | null): CanvasCatalogEntry[] {
  if (catalog === undefined || catalog === null) return [];
  const row = record(catalog, null, 'CANVAS_OPS_CATALOG_INVALID', '节点目录不可用，请重新读取创作图目录。');
  const definitions = rows(row.definitions, 64, 'CANVAS_OPS_CATALOG_INVALID', '节点目录不可用，请重新读取创作图目录。');
  const entries = definitions.map(item => catalogEntry(item));
  const seen = new Set<string>();
  for (const entry of entries) {
    if (seen.has(entry.id)) refuse('CANVAS_OPS_CATALOG_INVALID', '节点目录出现重复节点类型，请重新读取创作图目录。');
    seen.add(entry.id);
  }
  return entries;
}

/** 检索词规范化：去掉控制字符、折叠空白、按上限截断。非法输入返回 null（不猜测）。 */
function normalizedQuery(query: unknown): string | null {
  if (typeof query !== 'string') return null;
  const cleaned = query.replace(/[\u0000-\u001f\u007f]/g, ' ').replace(/\s+/g, ' ').trim();
  return cleaned.slice(0, CANVAS_SEARCH_QUERY_MAX).toLowerCase();
}
function matchRank(match: CanvasSearchMatch): number {
  return ['ID_EXACT', 'ID_PREFIX', 'LABEL_PREFIX', 'LABEL_CONTAINS', 'TOKEN_CONTAINS', 'ALL'].indexOf(match);
}
function entryMatch(entry: CanvasCatalogEntry, tokens: readonly string[]): CanvasSearchMatch | null {
  const id = entry.id.toLowerCase(), label = entry.label.toLowerCase();
  let best: CanvasSearchMatch | null = null;
  for (const token of tokens) {
    const candidate: CanvasSearchMatch | null = id === token ? 'ID_EXACT'
      : id.startsWith(token) ? 'ID_PREFIX'
        : label.startsWith(token) ? 'LABEL_PREFIX'
          : label.includes(token) ? 'LABEL_CONTAINS'
            : entry.haystack.includes(token) ? 'TOKEN_CONTAINS' : null;
    if (!candidate) return null;
    if (best === null || matchRank(candidate) < matchRank(best)) best = candidate;
  }
  return best;
}

/**
 * 按检索词与分类过滤现存目录定义。分类不是已知取值时返回空列表（失败关闭，不忽略筛选）。
 * 顺序稳定：先按命中强度，再按目录原始顺序。
 */
export function filterNodes(catalog: StudioGraphCatalog | null | undefined, query: string, category?: CanvasNodeCategory | 'ALL' | null): CanvasCatalogMatch[] {
  const entries = nodeSearchIndex(catalog);
  if (category !== undefined && category !== null && category !== 'ALL' && !CANVAS_NODE_CATEGORIES.includes(category)) return [];
  const scoped = category === undefined || category === null || category === 'ALL'
    ? entries : entries.filter(entry => entry.categories.includes(category));
  const tokens = (normalizedQuery(query) ?? '').split(' ').filter(Boolean);
  const matches = scoped.map(entry => ({ entry, match: tokens.length ? entryMatch(entry, tokens) : 'ALL' as CanvasSearchMatch }))
    .filter((row): row is CanvasCatalogMatch => row.match !== null);
  return matches
    .map((row, index) => ({ row, index }))
    .sort((left, right) => matchRank(left.row.match) - matchRank(right.row.match) || left.index - right.index)
    .slice(0, CANVAS_SEARCH_MATCH_MAX)
    .map(item => item.row);
}

/** 节点上限的只读展示：沿用原编辑器同一表达式，绝不抬高上限。 */
export function canvasNodeBudget(catalog: StudioGraphCatalog | null | undefined, definition: StudioGraphDefinition): CanvasNodeBudget {
  const media = definition.schema_version >= 3;
  const limit = media ? catalog?.media_limits?.nodes ?? 24 : catalog?.limits.nodes ?? 16;
  const used = definition.nodes.length, remaining = Math.max(0, limit - used), full = used >= limit;
  return {
    used, limit, remaining, full, source: media ? 'CATALOG_MEDIA_LIMITS' : 'CATALOG_LIMITS',
    message: full ? `已达本图节点上限 ${limit} 个；本工具不会抬高上限，请拆分工作流（例如把审核与导出放到另一张图），或移除不再需要的节点。` : null,
  };
}

/** 连接数上限的只读展示：达到上限时说明并建议拆分工作流。 */
export function canvasEdgeBudget(catalog: StudioGraphCatalog | null | undefined, definition: StudioGraphDefinition): CanvasEdgeBudget {
  const limit = catalog?.limits.edges ?? 40;
  const used = definition.edges.length, remaining = Math.max(0, limit - used), full = used >= limit;
  return {
    used, limit, remaining, full,
    message: full ? `已达本图连接上限 ${limit} 条；本工具不会抬高上限，请拆分工作流（例如把媒体审核之前与之后拆成两张图）。` : null,
  };
}

/* ------------------------------------------------------------------ *
 * 框选
 * ------------------------------------------------------------------ */
/**
 * 屏幕坐标框选：用 `graphSelectionRect` 求矩形、用 `graphNodesInScreenRect` 求命中集合。
 * 起止点重合（单击）返回空；任一坐标非有限数时不猜测，返回空。
 */
export function marqueeSelection(geometry: CanvasMarqueeGeometry, nodes: readonly StudioGraphNode[]): string[] {
  const points = [geometry.start, geometry.end];
  if (points.some(point => !point || !Number.isFinite(point.x) || !Number.isFinite(point.y))) return [];
  if (!geometry.viewport || !Number.isFinite(geometry.viewport.x) || !Number.isFinite(geometry.viewport.y)) return [];
  const rect = graphSelectionRect(geometry.start, geometry.end);
  if (rect.width <= 0 || rect.height <= 0) return [];
  return graphNodesInScreenRect(nodes, rect, geometry.viewport, geometry.definitions ?? []);
}

/* ------------------------------------------------------------------ *
 * 自动布局（确定性、可撤销、只改位置）
 * ------------------------------------------------------------------ */
const CANVAS_LAYOUT_COLUMN_GAP = 96;
const CANVAS_LAYOUT_ROW_GAP = 48;

/** 最长路径深度。迭代次数有界，含环时仍然收敛到确定值。 */
function graphDepths(nodes: readonly StudioGraphNode[], edges: readonly StudioGraphEdge[]): Map<string, number> {
  const depth = new Map<string, number>(nodes.map(node => [node.id, 0]));
  const usable = edges.filter(edge => depth.has(edge.source_node_id) && depth.has(edge.target_node_id) && edge.source_node_id !== edge.target_node_id);
  for (let pass = 0; pass < nodes.length && usable.length; pass += 1) {
    let changed = false;
    for (const edge of usable) {
      const next = (depth.get(edge.source_node_id) ?? 0) + 1;
      if (next > (depth.get(edge.target_node_id) ?? 0)) { depth.set(edge.target_node_id, next); changed = true; }
    }
    if (!changed) break;
  }
  return depth;
}
function boundedGap(value: unknown, fallback: number): number {
  return typeof value === 'number' && Number.isFinite(value) ? Math.min(2000, Math.max(0, value)) : fallback;
}

/**
 * 确定性自动布局：按最长路径分层，层内保持节点原始顺序。
 * 只修改 `node.position`；节点顺序、参数、启用状态、连接、视口、标题与 schema 一律原样返回，
 * 因此它产生的差异是纯 `POSITION_CHANGED`。可撤销来自调用方把返回值交给原控制器的
 * `change()`（进入 past/future），本函数自身不保存历史。
 */
export function autoLayout(definition: StudioGraphDefinition, options: CanvasAutoLayoutOptions = {}): StudioGraphDefinition {
  const columnGap = boundedGap(options.column_gap, CANVAS_LAYOUT_COLUMN_GAP);
  const rowGap = boundedGap(options.row_gap, CANVAS_LAYOUT_ROW_GAP);
  const origin = {
    x: clampGraphPosition(options.origin?.x ?? 0), y: clampGraphPosition(options.origin?.y ?? 0),
  };
  const depth = graphDepths(definition.nodes, definition.edges);
  const layers: string[][] = [];
  for (const node of definition.nodes) {
    const index = depth.get(node.id) ?? 0;
    (layers[index] ??= []).push(node.id);
  }
  const positions = new Map<string, { x: number; y: number }>();
  for (let layer = 0; layer < layers.length; layer += 1) {
    const ids = layers[layer];
    if (!ids?.length) continue;
    const rowHeight = Math.max(...ids.map(id => graphNodeHeight(
      options.definitions?.find(item => item.id === definition.nodes.find(node => node.id === id)?.definition_id))));
    ids.forEach((id, rank) => positions.set(id, {
      x: clampGraphPosition(origin.x + layer * (GRAPH_NODE_WIDTH + columnGap)),
      y: clampGraphPosition(origin.y + rank * (rowHeight + rowGap)),
    }));
  }
  return {
    ...definition,
    nodes: definition.nodes.map(node => ({ ...node, position: positions.get(node.id) ?? node.position })),
  };
}

/* ------------------------------------------------------------------ *
 * 连接建议（合法性由 connectionIssue 判定）
 * ------------------------------------------------------------------ */
/** `studioGraphEditorView.tsx` 的端口键编码：`JSON.stringify([nodeId, portId])`。 */
export function canvasPortKey(nodeId: string, portId: string): string {
  return JSON.stringify([nodeId, portId]);
}
/** 解码端口键；无法证明是两个有界字符串时返回 null，不猜测。 */
export function parseCanvasPortKey(value: unknown): { nodeId: string; portId: string } | null {
  if (typeof value !== 'string' || !value.startsWith('[') || value.length > 300) return null;
  let parsed: unknown;
  try { parsed = JSON.parse(value); } catch { return null; }
  if (!Array.isArray(parsed) || parsed.length !== 2) return null;
  const [nodeId, portId] = parsed;
  if (typeof nodeId !== 'string' || typeof portId !== 'string') return null;
  if (!CANVAS_OPS_NODE_ID.test(nodeId) || !portId.trim() || portId.length > 120) return null;
  return { nodeId, portId };
}

/**
 * 候选目标：(节点, 输入端口) 中由目录声明为同一端口类型的组合。
 * 类型必须完全一致 —— 这是 `connectionIssue` 既有规则（`output.type !== input.type`）的直接体现；
 * 本函数只做候选预筛，**合法性标签 `legal`/`issue` 一律来自 `connectionIssue`**。
 * 输出顺序稳定：合法候选在前，其次按目录顺序与端口顺序。
 */
export function compatibleTargets(
  definition: StudioGraphDefinition, catalog: StudioGraphCatalog | null | undefined,
  sourceNodeId: string, sourcePort: string,
): CanvasCompatibleTarget[] {
  if (!catalog || !sourceNodeId || !sourcePort) return [];
  const source = definition.nodes.find(node => node.id === sourceNodeId);
  if (!source) return [];
  const descriptors = graphCatalogForSchema(catalog.definitions, definition.schema_version);
  const output = descriptors.find(row => row.id === source.definition_id)?.outputs.find(item => item.id === sourcePort);
  if (!output) return [];
  const rows: CanvasCompatibleTarget[] = [];
  for (const node of definition.nodes) {
    if (node.id === source.id) continue;
    const descriptor = descriptors.find(row => row.id === node.definition_id);
    if (!descriptor) continue;
    for (const input of descriptor.inputs) {
      if (input.type !== output.type) continue;
      const probe: StudioGraphEdge = {
        id: 'canvasops-probe', source_node_id: source.id, source_port: output.id,
        target_node_id: node.id, target_port: input.id,
      };
      const issue = connectionIssue(definition, descriptors, probe) ?? null;
      const occupied = definition.edges.some(edge => edge.target_node_id === node.id && edge.target_port === input.id);
      rows.push({
        nodeId: node.id, definitionId: node.definition_id, label: GRAPH_NODE_LABELS[node.definition_id],
        portId: input.id, portType: input.type, required: input.required, occupied,
        issue, legal: issue === null, explanation: explainConnection(issue),
      });
    }
  }
  return rows
    .map((row, index) => ({ row, index }))
    .sort((left, right) => Number(right.row.legal) - Number(left.row.legal) || left.index - right.index)
    .map(item => item.row);
}

/** 必填输入尚未连接的节点端口（原所有者 `port.required` 的事实陈述，不是连接合法性判定）。 */
export function requiredInputGaps(
  definition: StudioGraphDefinition, catalog: StudioGraphCatalog | null | undefined, nodeIds?: readonly string[],
): { nodeId: string; portId: string }[] {
  if (!catalog) return [];
  const wanted = nodeIds ? new Set(nodeIds) : null;
  const descriptors = graphCatalogForSchema(catalog.definitions, definition.schema_version);
  const gaps: { nodeId: string; portId: string }[] = [];
  for (const node of definition.nodes) {
    if (wanted && !wanted.has(node.id)) continue;
    for (const input of descriptors.find(row => row.id === node.definition_id)?.inputs ?? []) {
      if (!input.required) continue;
      if (!definition.edges.some(edge => edge.target_node_id === node.id && edge.target_port === input.id)) {
        gaps.push({ nodeId: node.id, portId: input.id });
      }
    }
  }
  return gaps;
}

/** 原所有者的引用状态事实：过期绑定；连接合法性不受它影响，但它必须被显示。 */
export function staleReferenceNodeIds(states?: readonly StudioGraphReferenceState[] | null): string[] {
  return [...new Set((states ?? []).filter(row => row.state === 'STALE').map(row => row.node_id))];
}

/**
 * 把 `connectionIssue` 的结果映射为具体中文原因与稳定机器码。
 *
 * 该函数**只翻译**现有结果：能识别的原文逐字保留在 `ownerMessage`，无法识别的原文原样返回，
 * 既不发明合法性，也不把未知结果当作通过。`legal` 只表示**本地**端口检查是否通过；
 * 服务端校验、版本与摘要校验永远不被绕过。
 *
 * `facts` 用于补充两类原所有者事实（连接合法性之外的状态）：
 * - `staleSourceNodeIds`：`StudioGraphRecord.reference_states` 判定为 STALE 的来源节点；
 * - `missingRequiredInputNodeIds`：必填输入尚未连接的节点。
 * 这两类事实不会把本来合法的连接改判为非法，只会加一条明确的提示。
 */
export function explainConnection(
  issue: unknown,
  facts?: { staleSourceNodeIds?: readonly string[]; missingRequiredInputNodeIds?: readonly string[] },
): CanvasConnectionExplanation {
  if (typeof issue !== 'undefined' && issue !== null && typeof issue !== 'string') {
    return {
      code: 'UNCLASSIFIED_LOCAL_ISSUE', category: 'UNKNOWN', legal: false, ownerMessage: null,
      message: '本地端口检查返回了无法识别的结果，无法证明可以连接；请重新选择端口后再试。',
      hints: ['重新选择起始输出端口与目标输入端口；服务端与版本校验仍是唯一权威。'],
    };
  }
  const ownerMessage = typeof issue === 'string' && issue.trim() ? issue : null;
  if (!ownerMessage) {
    const stale = [...new Set(facts?.staleSourceNodeIds ?? [])];
    const gaps = [...new Set(facts?.missingRequiredInputNodeIds ?? [])];
    if (stale.length) {
      return {
        code: 'SOURCE_BINDING_STALE', category: 'STALE_SOURCE_BINDING', legal: true, ownerMessage: null,
        message: `本地端口检查通过；但来源节点的原资产/文档绑定已过期（${stale.join('、')}）。过期绑定不会被自动替换或重新摘要，保存前请先重新绑定当前版本。`,
        hints: ['在原节点重新绑定当前版本；不要用旧摘要继续执行。'],
      };
    }
    if (gaps.length) {
      return {
        code: 'REQUIRED_INPUT_MISSING', category: 'MISSING_REQUIRED_INPUT', legal: true, ownerMessage: null,
        message: `本地端口检查通过；但以下节点仍有必填输入未连接：${gaps.join('、')}。必填输入缺失不会自动补全，也不会绕过原图执行前的检查。`,
        hints: ['补齐必填输入；若一时无法补齐，可把工作流拆分为可独立保存的两张图。'],
      };
    }
    return {
      code: 'CONNECTION_LEGAL', category: 'LEGAL', legal: true, ownerMessage: null,
      message: '本地端口检查通过（类型一致、无环、输入端口未被占用）。连接合法性最终仍由服务端校验决定。',
      hints: [],
    };
  }
  const typeMismatch = /^端口类型不匹配：(.+) → (.+)。$/.exec(ownerMessage);
  const table: { test: (value: string) => boolean; code: CanvasConnectionIssueCode; category: CanvasConnectionIssueCategory; message: string; hints: string[] }[] = [
    {
      test: value => value === '先连接原文字模型的 draft 到人工审核，再将该审核节点的 reviewed_draft 连接到媒体 draft；未审核模型提案不能直接进入媒体。',
      code: 'UNREVIEWED_PROPOSAL', category: 'UNAPPROVED_CANDIDATE_INPUT',
      message: '未审核的模型提案不能直接进入媒体节点：必须先由原文字模型输出 draft、经原人工审核节点审核后，再把 reviewed_draft 接过来。',
      hints: ['增加或改用原人工审核节点，并先完成一次明确审核；本工具不会替你跳过审核。'],
    },
    {
      test: value => value === '图片候选须连接原媒体审核节点，审核后才输出正式素材。',
      code: 'CANDIDATE_REVIEW_REQUIRED', category: 'UNAPPROVED_CANDIDATE_INPUT',
      message: '图片生成结果是候选，不是正式素材：必须先连接到原媒体审核节点的 candidate 输入端口并完成审核。',
      hints: ['把图片生成节点连接到原媒体审核节点；审核通过前的候选不会被下游采用。'],
    },
    {
      test: value => value === '视频候选必须通过原媒体审核节点。',
      code: 'CANDIDATE_REVIEW_REQUIRED', category: 'UNAPPROVED_CANDIDATE_INPUT',
      message: '视频生成结果是候选：必须通过原媒体审核节点的 candidate 输入端口，审核后才可能成为正式素材。',
      hints: ['把视频生成节点连接到原媒体审核节点，再连接下游。'],
    },
    {
      test: value => value === '时间线导出候选须连接原媒体审核节点，审核后才可作为正式视频素材。',
      code: 'CANDIDATE_REVIEW_REQUIRED', category: 'UNAPPROVED_CANDIDATE_INPUT',
      message: '时间线导出的结果同样是候选：必须经原媒体审核节点审核后才能作为正式视频素材使用。',
      hints: ['把时间线导出连接到原媒体审核节点的 candidate 端口。'],
    },
    {
      test: value => value === '媒体节点的文本与已审核草稿输入互斥，请先明确移除另一条输入连接。',
      code: 'EXCLUSIVE_INPUT', category: 'LOCAL_STRUCTURE',
      message: '媒体节点的「文本输入」与「已审核草稿输入」互斥：请先明确移除另一条输入连接，本工具不会替你选择。',
      hints: ['先移除另一条输入连接，再建立新的连接。'],
    },
    {
      test: value => value === '图片节点需要明确采用图片图 v4。', code: 'SCHEMA_VERSION_REQUIRED', category: 'SCHEMA_VERSION_REQUIRED',
      message: '当前草稿不是图片图 v4：含图片节点时需先在原图版本确认区明确升级，旧图不会自动升级。',
      hints: ['在「图片图版本确认」中明确确认并保存，再连接图片节点。'],
    },
    {
      test: value => value === '视频节点需要明确采用视频图 v5。', code: 'SCHEMA_VERSION_REQUIRED', category: 'SCHEMA_VERSION_REQUIRED',
      message: '当前草稿不是视频图 v5：含视频/分镜节点时需先明确升级为 v5，旧图不会自动升级。',
      hints: ['在「视频图版本确认」中明确确认并保存，再连接视频节点。'],
    },
    {
      test: value => value === '时间线剪辑与导出需要明确升级为媒体图 v3。', code: 'SCHEMA_VERSION_REQUIRED', category: 'SCHEMA_VERSION_REQUIRED',
      message: '时间线剪辑与导出节点需要先明确升级为媒体图 v3，旧图保持原行为。',
      hints: ['在「媒体图版本」中明确升级并保存，再连接时间线节点。'],
    },
    {
      test: value => value === '该输入端口只接受一个连接。', code: 'INPUT_OCCUPIED', category: 'LOCAL_STRUCTURE',
      message: '该输入端口已被占用（目录声明 `multiple: false`）：请先移除端口上已有的那条连接。',
      hints: ['先移除该输入端口上已有的连接；连接数达到上限时可把工作流拆分为两张图。'],
    },
    {
      test: value => value === '此连接已经存在。', code: 'DUPLICATE_EDGE', category: 'LOCAL_STRUCTURE',
      message: '这条连接已经存在，无需重复添加。', hints: [],
    },
    {
      test: value => value === '此连接会形成循环，无法保存。', code: 'CYCLE', category: 'LOCAL_STRUCTURE',
      message: '这条连接会让草稿形成环，无法保存：请改为下游方向，或把工作流拆成两张可独立保存的图。',
      hints: ['改成不形成环的方向；必要时拆分工作流。'],
    },
    {
      test: value => value === '节点不能连接自身。', code: 'SELF_CONNECTION', category: 'LOCAL_STRUCTURE',
      message: '节点不能连接自身：请选择两个不同的节点。', hints: [],
    },
    {
      test: value => value === '请选择真实的输出端口和输入端口。', code: 'PORT_UNKNOWN', category: 'LOCAL_STRUCTURE',
      message: '端口在当前图格式下不存在：请重新选择真实的输出端口与输入端口（目录已按当前图格式过滤）。',
      hints: ['重新选择端口；不兼容的节点不会被自动移除或转换。'],
    },
    {
      test: value => value === '请选择当前图中的两个节点。', code: 'NODES_MISSING', category: 'LOCAL_STRUCTURE',
      message: '起始或目标节点已不在当前草稿中：请重新选择图中的两个节点。', hints: [],
    },
  ];
  if (typeMismatch) {
    return {
      code: 'PORT_TYPE_MISMATCH', category: 'TYPE_MISMATCH', legal: false, ownerMessage,
      message: `端口类型不匹配：${typeMismatch[1]} → ${typeMismatch[2]}。请改用类型完全一致的端口。`,
      hints: ['查看下方「兼容目标」列表中的合法候选；本工具不会把不匹配的类型强行接上。'],
    };
  }
  const found = table.find(row => row.test(ownerMessage));
  if (found) return { code: found.code, category: found.category, legal: false, ownerMessage, message: found.message, hints: found.hints };
  return {
    code: 'UNCLASSIFIED_LOCAL_ISSUE', category: 'UNKNOWN', legal: false, ownerMessage,
    message: `本地连接检查未通过：${ownerMessage}`,
    hints: ['请按上面的原文处理；无法在本地解释时不要绕过检查。'],
  };
}

/* ------------------------------------------------------------------ *
 * 变更影响分类（保守）
 * ------------------------------------------------------------------ */
const CANVAS_NODE_KEYS = ['id', 'definition_id', 'definition_version', 'enabled', 'position', 'parameters'] as const;
const CANVAS_EDGE_KEYS = ['id', 'source_node_id', 'source_port', 'target_node_id', 'target_port'] as const;
const CANVAS_PRESENTATION_REASONS: readonly CanvasChangeReasonCode[] = ['NO_CHANGE', 'POSITION_CHANGED', 'VIEWPORT_CHANGED'];
const CANVAS_REASON_ORDER: readonly CanvasChangeReasonCode[] = ['NO_CHANGE', 'POSITION_CHANGED', 'VIEWPORT_CHANGED',
  'NODE_ADDED', 'NODE_REMOVED', 'NODE_REORDERED', 'NODE_DEFINITION_CHANGED', 'NODE_ENABLED_CHANGED', 'NODE_PARAMETERS_CHANGED',
  'NODE_SHAPE_UNKNOWN', 'EDGE_ADDED', 'EDGE_REMOVED', 'EDGE_REORDERED', 'EDGE_ENDPOINT_CHANGED', 'EDGE_SHAPE_UNKNOWN',
  'SCHEMA_CHANGED', 'TITLE_CHANGED', 'UNKNOWN_FIELD_CHANGED', 'NOT_COMPARABLE'];
const CANVAS_REASON_MESSAGES: Record<CanvasChangeReasonCode, string> = {
  NO_CHANGE: '与比较基准一致，没有本地差异。',
  POSITION_CHANGED: '只有节点位置发生变化，属于画布呈现。',
  VIEWPORT_CHANGED: '只有画布视口（平移/缩放）发生变化，属于画布呈现。',
  NODE_ADDED: '新增了节点。',
  NODE_REMOVED: '移除了节点。',
  NODE_REORDERED: '节点顺序发生变化；执行顺序可能随之变化，本地无法证明只影响呈现。',
  NODE_DEFINITION_CHANGED: '节点的定义类型或定义版本发生变化。',
  NODE_ENABLED_CHANGED: '节点的启用状态发生变化。',
  NODE_PARAMETERS_CHANGED: '节点参数发生变化（含来源绑定：资产的 ID/版本/摘要、文档快照等）。',
  NODE_SHAPE_UNKNOWN: '节点上出现了本工具不认识的字段，本地无法证明它只影响呈现。',
  EDGE_ADDED: '新增了连接。',
  EDGE_REMOVED: '移除了连接。',
  EDGE_REORDERED: '连接顺序发生变化，本地无法证明只影响呈现。',
  EDGE_ENDPOINT_CHANGED: '连接的两端或端口发生变化。',
  EDGE_SHAPE_UNKNOWN: '连接上出现了本工具不认识的字段，本地无法证明它只影响呈现。',
  SCHEMA_CHANGED: '图格式（schema_version）发生变化。',
  TITLE_CHANGED: '图标题属于已保存的图内容，本地无法证明只影响呈现。',
  UNKNOWN_FIELD_CHANGED: '图定义上出现了本工具不认识的顶层字段，本地无法证明它只影响呈现。',
  NOT_COMPARABLE: '缺少可比较的已保存定义，或定义结构不符合原图契约，本地无法证明差异只影响呈现。',
};
const CANVAS_DEFINITION_KEYS = ['schema_version', 'title', 'nodes', 'edges', 'viewport'] as const;

/** 键有序的规范化序列化；无法可靠序列化的值会得到明确的标记，从而落到「无法证明」一侧。 */
function canonical(value: unknown, depth = 0): string {
  if (depth > 12) return '¬DEPTH';
  if (value === null) return 'null';
  if (Array.isArray(value)) return `[${value.map(item => canonical(item, depth + 1)).join(',')}]`;
  switch (typeof value) {
    case 'string': return JSON.stringify(value);
    case 'number': return Number.isFinite(value) ? String(value) : '¬NUMBER';
    case 'boolean': return String(value);
    case 'undefined': return '¬UNDEFINED';
    case 'object': {
      const row = value as Record<string, unknown>;
      return `{${Object.keys(row).sort().map(key => `${JSON.stringify(key)}:${canonical(row[key], depth + 1)}`).join(',')}}`;
    }
    default: return '¬UNSERIALIZABLE';
  }
}
function isDefinitionShaped(value: unknown): value is StudioGraphDefinition {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return false;
  const row = value as Record<string, unknown>;
  return Array.isArray(row.nodes) && Array.isArray(row.edges) && typeof row.schema_version === 'number' && typeof row.title === 'string';
}
function nodeShape(node: unknown): string {
  return node && typeof node === 'object' && !Array.isArray(node) ? Object.keys(node as Record<string, unknown>).sort().join('|') : '¬NOT_OBJECT';
}

/**
 * 分类草稿差异：`PRESENTATION`（可证明只影响呈现）或 `GENERATION_AFFECTING`（其余一切）。
 *
 * 保守规则只有一条：**仅当所有差异原因都落在 {位置、视口、无变化} 内时才判定为呈现**。
 * 未知字段、未知结构、缺少可比较的定义、节点/连接顺序变化一律计入 `GENERATION_AFFECTING`。
 * 这个分类只描述本地草稿差异，不代表任何执行、调用或审核结果，也不绕过版本/摘要校验。
 */
export function classifyGraphChange(
  before: StudioGraphDefinition | undefined, after: StudioGraphDefinition | undefined,
): CanvasChangeClassification {
  const reasons = new Set<CanvasChangeReasonCode>();
  const add = (code: CanvasChangeReasonCode) => { reasons.add(code); };
  if (before === after) add('NO_CHANGE');
  else if (!isDefinitionShaped(before) || !isDefinitionShaped(after)) add('NOT_COMPARABLE');
  else {
    const beforeKeys = Object.keys(before), afterKeys = Object.keys(after);
    if ([...beforeKeys, ...afterKeys].some(key => !CANVAS_DEFINITION_KEYS.includes(key as typeof CANVAS_DEFINITION_KEYS[number]))) add('UNKNOWN_FIELD_CHANGED');
    if (before.schema_version !== after.schema_version) add('SCHEMA_CHANGED');
    if (before.title !== after.title) add('TITLE_CHANGED');
    if (canonical(before.viewport) !== canonical(after.viewport)) add('VIEWPORT_CHANGED');
    classifyNodes(before.nodes, after.nodes, add);
    classifyEdges(before.edges, after.edges, add);
    if (!reasons.size) add('NO_CHANGE');
  }
  const reasonCodes = CANVAS_REASON_ORDER.filter(code => reasons.has(code));
  const verdict = reasonCodes.every(code => CANVAS_PRESENTATION_REASONS.includes(code)) ? 'PRESENTATION' : 'GENERATION_AFFECTING';
  return { verdict, reasonCodes, messages: reasonCodes.map(code => CANVAS_REASON_MESSAGES[code]), localOnly: true };
}
function classifyNodes(before: readonly StudioGraphNode[], after: readonly StudioGraphNode[], add: (code: CanvasChangeReasonCode) => void): void {
  const beforeIds = before.map(node => node.id), afterIds = after.map(node => node.id);
  const beforeSet = new Set(beforeIds), afterSet = new Set(afterIds);
  if (afterIds.some(id => !beforeSet.has(id))) add('NODE_ADDED');
  if (beforeIds.some(id => !afterSet.has(id))) add('NODE_REMOVED');
  if (beforeIds.length === afterIds.length && beforeIds.some((id, index) => afterIds[index] !== id)) add('NODE_REORDERED');
  for (const id of afterIds) {
    const left = before.find(node => node.id === id), right = after.find(node => node.id === id);
    if (!left || !right) continue;
    if (nodeShape(left) !== nodeShape(right)) { add('NODE_SHAPE_UNKNOWN'); continue; }
    const leftRow = left as unknown as Record<string, unknown>, rightRow = right as unknown as Record<string, unknown>;
    if (Object.keys(leftRow).some(key => !CANVAS_NODE_KEYS.includes(key as typeof CANVAS_NODE_KEYS[number]))) { add('NODE_SHAPE_UNKNOWN'); continue; }
    if (left.definition_id !== right.definition_id || left.definition_version !== right.definition_version) add('NODE_DEFINITION_CHANGED');
    if (left.enabled !== right.enabled) add('NODE_ENABLED_CHANGED');
    if (canonical(left.parameters) !== canonical(right.parameters)) add('NODE_PARAMETERS_CHANGED');
    if (canonical(left.position) !== canonical(right.position)) add('POSITION_CHANGED');
  }
}
function classifyEdges(before: readonly StudioGraphEdge[], after: readonly StudioGraphEdge[], add: (code: CanvasChangeReasonCode) => void): void {
  const beforeIds = before.map(edge => edge.id), afterIds = after.map(edge => edge.id);
  const beforeSet = new Set(beforeIds), afterSet = new Set(afterIds);
  if (afterIds.some(id => !beforeSet.has(id))) add('EDGE_ADDED');
  if (beforeIds.some(id => !afterSet.has(id))) add('EDGE_REMOVED');
  if (beforeIds.length === afterIds.length && beforeIds.some((id, index) => afterIds[index] !== id)) add('EDGE_REORDERED');
  for (const id of afterIds) {
    const left = before.find(edge => edge.id === id), right = after.find(edge => edge.id === id);
    if (!left || !right) continue;
    if (nodeShape(left) !== nodeShape(right)) { add('EDGE_SHAPE_UNKNOWN'); continue; }
    if (canonical({ ...left, id: '' }) !== canonical({ ...right, id: '' })) add('EDGE_ENDPOINT_CHANGED');
  }
}

/* ------------------------------------------------------------------ *
 * 会话内呈现状态：折叠 / 分组 / 标注（不持久化）
 * ------------------------------------------------------------------ */
/**
 * 重要限制：分组、标注与折叠是**会话内呈现状态**，本批不把它们写入已保存图，
 * 也不给 `studioGraphTypes` / 后端定义增加字段。若要持久化，必须由原所有者先做一次
 * 带类型、向后兼容的扩展（新字段 + 版本化迁移 + 校验），并单独评审；届时本模块的
 * `LocalCanvasState` 才能作为该扩展的输入，而不是自行定义第二套契约。
 */
export function blankLocalCanvasState(): LocalCanvasState {
  return { schema: CANVAS_OPS_LOCAL_SCHEMA, collapsed: [], groups: [], annotations: [] };
}
function localText(value: unknown, maximum: number, code: string, message: string): string {
  if (typeof value !== 'string' || !value.trim() || value.length > maximum || /[\u0000-\u001f\u007f]/.test(value)) refuse(code, message);
  return value;
}
function nodeId(value: unknown, code: string, message: string): string {
  if (typeof value !== 'string' || !CANVAS_OPS_NODE_ID.test(value)) refuse(code, message);
  return value;
}
function nodeIdList(value: unknown, maximum: number, code: string, message: string): string[] {
  const list = rows(value, maximum, code, message).map(item => nodeId(item, code, message));
  if (new Set(list).size !== list.length) refuse(code, message);
  return list;
}
function localGroups(value: unknown): LocalCanvasGroup[] {
  const code = 'CANVAS_OPS_LOCAL_INVALID';
  const message = '本地分组数据不可用，已按空分组处理。';
  const groups = rows(value, CANVAS_OPS_LOCAL_BOUNDS.groups, code, message).map(item => {
    const row = record(item, ['id', 'label', 'node_ids'], code, message);
    return {
      id: localText(row.id, CANVAS_OPS_LOCAL_BOUNDS.group_id, code, message),
      label: localText(row.label, CANVAS_OPS_LOCAL_BOUNDS.group_label, code, message),
      node_ids: nodeIdList(row.node_ids, CANVAS_OPS_LOCAL_BOUNDS.group_nodes, code, message),
    };
  });
  if (new Set(groups.map(group => group.id)).size !== groups.length) refuse(code, message);
  return groups;
}
function localAnnotations(value: unknown): LocalCanvasAnnotation[] {
  const code = 'CANVAS_OPS_LOCAL_INVALID';
  const message = '本地标注数据不可用，已按空标注处理。';
  const annotations = rows(value, CANVAS_OPS_LOCAL_BOUNDS.annotations, code, message).map(item => {
    const row = record(item, ['id', 'text', 'anchor_node_id'], code, message);
    const anchor = row.anchor_node_id === null ? null : nodeId(row.anchor_node_id, code, message);
    return {
      id: localText(row.id, CANVAS_OPS_LOCAL_BOUNDS.annotation_id, code, message),
      text: localText(row.text, CANVAS_OPS_LOCAL_BOUNDS.annotation_text, code, message), anchor_node_id: anchor,
    };
  });
  if (new Set(annotations.map(annotation => annotation.id)).size !== annotations.length) refuse(code, message);
  return annotations;
}

/** 严格本地校验：未知字段、越界、控制字符、重复 ID 都判为不可用。通过时返回 undefined。 */
export function localCanvasStateIssue(value: unknown): string | undefined {
  try {
    validateLocalCanvasState(value);
    return undefined;
  } catch (error) {
    return error instanceof CanvasOpsLocalError ? error.message : '本地画布状态不可用，已按空状态处理。';
  }
}
function validateLocalCanvasState(value: unknown): LocalCanvasState {
  const code = 'CANVAS_OPS_LOCAL_INVALID';
  const message = '本地画布状态不可用，已按空状态处理。';
  const row = record(value, ['schema', 'collapsed', 'groups', 'annotations'], code, message);
  if (row.schema !== CANVAS_OPS_LOCAL_SCHEMA) refuse(code, message);
  return {
    schema: CANVAS_OPS_LOCAL_SCHEMA,
    collapsed: nodeIdList(row.collapsed, CANVAS_OPS_LOCAL_BOUNDS.collapsed, code, message),
    groups: localGroups(row.groups), annotations: localAnnotations(row.annotations),
  };
}

/** 校验并规范化会话内状态；不可用时失败关闭为空状态，并给出中文说明。 */
export function normalizeLocalCanvasState(value: unknown): LocalCanvasStateUpdate {
  try {
    return { state: validateLocalCanvasState(value) };
  } catch (error) {
    return {
      state: blankLocalCanvasState(),
      issue: error instanceof CanvasOpsLocalError ? error.message : '本地画布状态不可用，已按空状态处理。',
    };
  }
}

/** 折叠/展开（仅本地）。返回新对象，不修改入参。 */
export function toggleCollapse(state: LocalCanvasState, id: string): LocalCanvasStateUpdate {
  const current = normalizeLocalCanvasState(state).state;
  if (!CANVAS_OPS_NODE_ID.test(id)) return { state: current, issue: '节点标识不可用，未改变本地折叠状态。' };
  if (!current.collapsed.includes(id) && current.collapsed.length >= CANVAS_OPS_LOCAL_BOUNDS.collapsed) {
    return { state: current, issue: `本地折叠最多记录 ${CANVAS_OPS_LOCAL_BOUNDS.collapsed} 个节点；该上限属于本地呈现状态，不会被抬高，请拆分工作流或先展开其他节点。` };
  }
  return {
    state: {
      ...current,
      collapsed: current.collapsed.includes(id) ? current.collapsed.filter(item => item !== id) : [...current.collapsed, id],
    },
  };
}

/** 新建本地分组；达到上限时保留原状态并说明。 */
export function createLocalGroup(state: LocalCanvasState, id: string, label: string, nodeIds: readonly string[]): LocalCanvasStateUpdate {
  const current = normalizeLocalCanvasState(state).state;
  const code = 'CANVAS_OPS_LOCAL_GROUP_INVALID';
  try {
    if (current.groups.length >= CANVAS_OPS_LOCAL_BOUNDS.groups) {
      return { state: current, issue: `本地分组最多 ${CANVAS_OPS_LOCAL_BOUNDS.groups} 组；该上限不会被抬高，请合并现有分组或拆分工作流。` };
    }
    if (current.groups.some(group => group.id === id)) return { state: current, issue: '该本地分组已存在，未重复创建。' };
    const group: LocalCanvasGroup = {
      id: localText(id, CANVAS_OPS_LOCAL_BOUNDS.group_id, code, '本地分组标识不可用。'),
      label: localText(label, CANVAS_OPS_LOCAL_BOUNDS.group_label, code, '本地分组名称不可用（需 1–60 字且不含控制字符）。'),
      node_ids: nodeIdList([...nodeIds], CANVAS_OPS_LOCAL_BOUNDS.group_nodes, code, '本地分组包含不可用的节点标识。'),
    };
    return { state: { ...current, groups: [...current.groups, group] } };
  } catch (error) {
    return { state: current, issue: error instanceof CanvasOpsLocalError ? error.message : '本地分组不可用，未改变分组。' };
  }
}

/** 改名本地分组。 */
export function renameLocalGroup(state: LocalCanvasState, id: string, label: string): LocalCanvasStateUpdate {
  const current = normalizeLocalCanvasState(state).state;
  if (!current.groups.some(group => group.id === id)) return { state: current, issue: '该本地分组不存在。' };
  if (typeof label !== 'string' || !label.trim() || label.length > CANVAS_OPS_LOCAL_BOUNDS.group_label || /[\u0000-\u001f\u007f]/.test(label)) {
    return { state: current, issue: '本地分组名称不可用（需 1–60 字且不含控制字符）。' };
  }
  return { state: { ...current, groups: current.groups.map(group => group.id === id ? { ...group, label } : group) } };
}

export function removeLocalGroup(state: LocalCanvasState, id: string): LocalCanvasStateUpdate {
  const current = normalizeLocalCanvasState(state).state;
  return { state: { ...current, groups: current.groups.filter(group => group.id !== id) } };
}

/** 新建本地标注；达到上限时保留原状态并说明。 */
export function createLocalAnnotation(state: LocalCanvasState, id: string, text: string, anchorNodeId: string | null): LocalCanvasStateUpdate {
  const current = normalizeLocalCanvasState(state).state;
  const code = 'CANVAS_OPS_LOCAL_ANNOTATION_INVALID';
  try {
    if (current.annotations.length >= CANVAS_OPS_LOCAL_BOUNDS.annotations) {
      return { state: current, issue: `本地标注最多 ${CANVAS_OPS_LOCAL_BOUNDS.annotations} 条；该上限不会被抬高，请合并现有标注或拆分工作流。` };
    }
    if (current.annotations.some(annotation => annotation.id === id)) return { state: current, issue: '该本地标注已存在，未重复创建。' };
    const anchor = anchorNodeId === null ? null : nodeId(anchorNodeId, code, '本地标注锚点不可用。');
    return {
      state: {
        ...current,
        annotations: [...current.annotations, {
          id: localText(id, CANVAS_OPS_LOCAL_BOUNDS.annotation_id, code, '本地标注标识不可用。'),
          text: localText(text, CANVAS_OPS_LOCAL_BOUNDS.annotation_text, code, '本地标注内容不可用（需 1–400 字且不含控制字符）。'),
          anchor_node_id: anchor,
        }],
      },
    };
  } catch (error) {
    return { state: current, issue: error instanceof CanvasOpsLocalError ? error.message : '本地标注不可用，未改变标注。' };
  }
}

export function removeLocalAnnotation(state: LocalCanvasState, id: string): LocalCanvasStateUpdate {
  const current = normalizeLocalCanvasState(state).state;
  return { state: { ...current, annotations: current.annotations.filter(annotation => annotation.id !== id) } };
}

/** 节点被移除后清理本地状态中的悬空引用；不会改变任何已保存内容。 */
export function pruneLocalCanvasState(state: LocalCanvasState, knownNodeIds: readonly string[]): LocalCanvasState {
  const current = normalizeLocalCanvasState(state).state;
  const known = new Set(knownNodeIds);
  return {
    ...current,
    collapsed: current.collapsed.filter(id => known.has(id)),
    groups: current.groups.map(group => ({ ...group, node_ids: group.node_ids.filter(id => known.has(id)) })),
    annotations: current.annotations.map(annotation => annotation.anchor_node_id && !known.has(annotation.anchor_node_id)
      ? { ...annotation, anchor_node_id: null } : annotation),
  };
}
