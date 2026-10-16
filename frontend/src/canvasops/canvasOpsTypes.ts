/**
 * UX-04 无限画布与节点工作流操作 —— 呈现层类型（`frontend/src/canvasops/`）。
 *
 * 本文件夹是**唯一节点引擎的消费者**，不是第二个引擎：
 * - 图定义、节点、连接、目录与端口类型全部从 `../creative/studioGraphTypes` 派生（下方再导出）；
 * - 连接合法性只由 `../creative/graphDraft` 的 `connectionIssue` 判定；
 * - 画布几何只由 `../creative/graphCanvasGeometry` 提供。
 *
 * 本批**不修改任何持久化图契约**：不新增 `studioGraphTypes` / 后端定义字段，
 * 分组、标注与折叠只是**会话内呈现状态**（`LocalCanvasState`）。
 * 若将来需要持久化它们，必须由原所有者（`studioGraphTypes` + 后端定义）先做一次
 * 带类型的、向后兼容的扩展，并单独走一次变更评审；本文件夹不得自行加字段。
 */
import type { GraphCanvasNodeDefinition } from '../creative/graphCanvasGeometry';
import type {
  StudioGraphCatalog, StudioGraphCatalogDefinition, StudioGraphDefinition, StudioGraphDefinitionId,
  StudioGraphEdge, StudioGraphNode, StudioGraphPort, StudioGraphPortType, StudioGraphPosition,
  StudioGraphReferenceState, StudioGraphViewport,
} from '../creative/studioGraphTypes';

/** 原图契约：再导出而不是重新声明，保证全仓库只有一份图模型。 */
export type {
  StudioGraphCatalog, StudioGraphCatalogDefinition, StudioGraphDefinition, StudioGraphDefinitionId,
  StudioGraphEdge, StudioGraphNode, StudioGraphPort, StudioGraphPortType, StudioGraphPosition,
  StudioGraphReferenceState, StudioGraphViewport,
};

/* ------------------------------------------------------------------ *
 * 目录检索（只读现存目录，不新增节点类型）
 * ------------------------------------------------------------------ */

/** 呈现层角色分类。每一项都必须映射到 `StudioGraphDefinitionId` 已声明的取值。 */
export type CanvasNodeCategory = 'TEXT' | 'ASSET' | 'MEDIA' | 'IMAGE' | 'STORYBOARD' | 'VIDEO';

export const CANVAS_NODE_CATEGORIES: readonly CanvasNodeCategory[] = ['TEXT', 'ASSET', 'MEDIA', 'IMAGE', 'STORYBOARD', 'VIDEO'];

export const CANVAS_NODE_CATEGORY_LABELS: Record<CanvasNodeCategory, string> = {
  TEXT: '文本与草稿', ASSET: '资产引用', MEDIA: '媒体与时间线', IMAGE: '图片图 v4 节点', STORYBOARD: '导演与分镜', VIDEO: '视频图 v5 节点',
};

/** 用户可输入检索词的上限；超出即视为无效输入，不做猜测。 */
export const CANVAS_SEARCH_QUERY_MAX = 80;

export const CANVAS_SEARCH_MATCH_MAX = 200;

/** 检索命中原因：仅用于排序与提示，不改变目录本身。`ALL` 表示未输入检索词。 */
export type CanvasSearchMatch = 'ID_EXACT' | 'ID_PREFIX' | 'LABEL_PREFIX' | 'LABEL_CONTAINS' | 'TOKEN_CONTAINS' | 'ALL';

/** 目录一行的只读检索投影；`catalog` 仍是唯一事实来源。 */
export type CanvasCatalogEntry = {
  id: StudioGraphDefinitionId;
  label: string;
  category: CanvasNodeCategory;
  categories: CanvasNodeCategory[];
  executable: boolean;
  model_called: false;
  blockers: string[];
  inputs: StudioGraphPort[];
  outputs: StudioGraphPort[];
  /** 已经是小写的检索词，保持插入顺序以便排序稳定。 */
  keywords: string[];
  /** 无空格的小写检索文本；仅由现存目录字段拼装。 */
  haystack: string;
};

export type CanvasCatalogMatch = { entry: CanvasCatalogEntry; match: CanvasSearchMatch };

/** 节点上限的只读展示；`source` 记录这个数字取自原所有者的哪一个声明。 */
export type CanvasNodeBudget = {
  used: number;
  limit: number;
  remaining: number;
  full: boolean;
  source: 'CATALOG_LIMITS' | 'CATALOG_MEDIA_LIMITS';
  message: string | null;
};

/** 连接数上限的只读展示；`message` 只在达到上限时说明并建议拆分工作流。 */
export type CanvasEdgeBudget = {
  used: number;
  limit: number;
  remaining: number;
  full: boolean;
  message: string | null;
};

/* ------------------------------------------------------------------ *
 * 框选（复用 graphCanvasGeometry）
 * ------------------------------------------------------------------ */

/** 屏幕坐标（视口内）起止点 + 当前视口 + 现存节点描述符。 */
export type CanvasMarqueeGeometry = {
  start: StudioGraphPosition;
  end: StudioGraphPosition;
  viewport: StudioGraphViewport;
  definitions: readonly GraphCanvasNodeDefinition[];
};

/* ------------------------------------------------------------------ *
 * 自动布局
 * ------------------------------------------------------------------ */

export type CanvasAutoLayoutOptions = {
  origin?: StudioGraphPosition;
  column_gap?: number;
  row_gap?: number;
  /** 现存节点描述符；只影响行距（节点高度），不改变任何节点内容。 */
  definitions?: readonly GraphCanvasNodeDefinition[];
};

/* ------------------------------------------------------------------ *
 * 连接建议（合法性仍由 connectionIssue 判定）
 * ------------------------------------------------------------------ */

/**
 * 问题分类。前四项是工作包要求的口径：
 * 类型不匹配 / 未审核候选输入 / 过期来源绑定 / 缺少必填输入。
 */
export type CanvasConnectionIssueCategory = 'LEGAL' | 'TYPE_MISMATCH' | 'UNAPPROVED_CANDIDATE_INPUT'
  | 'STALE_SOURCE_BINDING' | 'MISSING_REQUIRED_INPUT' | 'SCHEMA_VERSION_REQUIRED' | 'LOCAL_STRUCTURE' | 'UNKNOWN';

/** 稳定机器码；UI 文案可改，这些码不可改。 */
export type CanvasConnectionIssueCode = 'CONNECTION_LEGAL' | 'PORT_TYPE_MISMATCH' | 'CANDIDATE_REVIEW_REQUIRED'
  | 'UNREVIEWED_PROPOSAL' | 'EXCLUSIVE_INPUT' | 'DUPLICATE_EDGE' | 'INPUT_OCCUPIED' | 'CYCLE'
  | 'SELF_CONNECTION' | 'NODES_MISSING' | 'PORT_UNKNOWN' | 'SCHEMA_VERSION_REQUIRED'
  | 'SOURCE_BINDING_STALE' | 'REQUIRED_INPUT_MISSING' | 'UNCLASSIFIED_LOCAL_ISSUE';

export type CanvasConnectionExplanation = {
  code: CanvasConnectionIssueCode;
  category: CanvasConnectionIssueCategory;
  /** 中文原因；当它来自原所有者时逐字保留，不改写也不吞掉。 */
  message: string;
  /** 原 `connectionIssue` 的原文；本地检查通过时为 null。 */
  ownerMessage: string | null;
  /** 仅表示**本地**检查是否通过；服务端校验仍是唯一权威。 */
  legal: boolean;
  /** 达到上限或需要拆分工作流时的具体建议。 */
  hints: string[];
};

/** `compatibleTargets` 的候选行：合法性来自 `connectionIssue`，不来自本函数。 */
export type CanvasCompatibleTarget = {
  nodeId: string;
  definitionId: StudioGraphDefinitionId;
  label: string;
  portId: string;
  portType: StudioGraphPortType;
  required: boolean;
  occupied: boolean;
  /** `connectionIssue(definition, catalog, 候选连接)` 的结果。 */
  issue: string | null;
  legal: boolean;
  explanation: CanvasConnectionExplanation;
};

/* ------------------------------------------------------------------ *
 * 变更影响分类
 * ------------------------------------------------------------------ */

export type CanvasChangeVerdict = 'PRESENTATION' | 'GENERATION_AFFECTING';

export type CanvasChangeReasonCode = 'NO_CHANGE' | 'NOT_COMPARABLE' | 'POSITION_CHANGED' | 'VIEWPORT_CHANGED'
  | 'SCHEMA_CHANGED' | 'TITLE_CHANGED' | 'NODE_ADDED' | 'NODE_REMOVED' | 'NODE_REORDERED'
  | 'NODE_DEFINITION_CHANGED' | 'NODE_ENABLED_CHANGED' | 'NODE_PARAMETERS_CHANGED' | 'NODE_SHAPE_UNKNOWN'
  | 'EDGE_ADDED' | 'EDGE_REMOVED' | 'EDGE_REORDERED' | 'EDGE_ENDPOINT_CHANGED' | 'EDGE_SHAPE_UNKNOWN'
  | 'UNKNOWN_FIELD_CHANGED';

export type CanvasChangeClassification = {
  verdict: CanvasChangeVerdict;
  reasonCodes: CanvasChangeReasonCode[];
  messages: string[];
  /** 仅在本地可证明的结论；服务端摘要/版本校验永不因此被绕过。 */
  localOnly: true;
};

/* ------------------------------------------------------------------ *
 * 会话内呈现状态（分组 / 标注 / 折叠）—— 不持久化
 * ------------------------------------------------------------------ */

export const CANVAS_OPS_LOCAL_SCHEMA = 'canvasops-local/1' as const;

export const CANVAS_OPS_LOCAL_BOUNDS = {
  node_id: 120, group_id: 120, group_label: 60, group_nodes: 64, groups: 24,
  annotation_id: 120, annotation_text: 400, annotations: 64, collapsed: 200,
} as const;

/** 节点 ID 语法：与图中现存 ID 一致的有界标识（`graphId()` 生成 `node_<hex>`）。 */
export const CANVAS_OPS_NODE_ID = /^[A-Za-z0-9][A-Za-z0-9._:-]{0,119}$/;

export type LocalCanvasGroup = { id: string; label: string; node_ids: string[] };
export type LocalCanvasAnnotation = { id: string; text: string; anchor_node_id: string | null };

export type LocalCanvasState = {
  schema: 'canvasops-local/1';
  collapsed: string[];
  groups: LocalCanvasGroup[];
  annotations: LocalCanvasAnnotation[];
};

/** 会话内状态的变更结果：达到上限时保留原状态并给出中文说明与拆分建议。 */
export type LocalCanvasStateUpdate = { state: LocalCanvasState; issue?: string };

/** 本地校验失败时的诊断（不是网络错误，不带 status）。 */
export type CanvasOpsValidationProblem = { code: string; message: string };

/* ------------------------------------------------------------------ *
 * 组件 props（仅呈现；所有变更都通过原控制器的回调）
 * ------------------------------------------------------------------ */

export type NodePalettePanelProps = {
  catalog?: StudioGraphCatalog;
  definition: StudioGraphDefinition;
  kind: string;
  editable: boolean;
  onKind: (kind: string) => void;
  onAddNode: () => void;
};

export type CanvasSelectionBarProps = {
  selected: readonly string[];
  /** 框选命中数；`undefined` 表示调用方未提供（本栏不会凭空编造数字）。 */
  marqueeCount?: number;
  past: number;
  future: number;
  editable: boolean;
  protectedNodeIds: readonly string[];
  /** 会话内呈现状态：只用于显示折叠/分组/标注数量与折叠开关，不写入已保存图。 */
  local?: LocalCanvasState;
  onLocal?: (next: LocalCanvasState) => void;
  onFocusSelected: (nodeId: string) => void;
  onSelect: (ids: string[]) => void;
  onTravel: (direction: 'UNDO' | 'REDO') => void;
};

export type ConnectionAdvisorPanelProps = {
  definition: StudioGraphDefinition;
  catalog?: StudioGraphCatalog;
  sourcePort: string;
  targetPort: string;
  connectionExplanation?: string;
  editable: boolean;
  referenceStates?: readonly StudioGraphReferenceState[];
  onSourcePort: (port: string) => void;
  onTargetPort: (port: string) => void;
  onConnect: () => void;
};

export type ChangeImpactNoticeProps = {
  definition: StudioGraphDefinition;
  base?: StudioGraphDefinition;
  dirty: boolean;
};

/** 画布操作栏的组合 props 在 `CanvasOpsRail.tsx` 中冻结导出（工作包要求逐字一致）。 */
