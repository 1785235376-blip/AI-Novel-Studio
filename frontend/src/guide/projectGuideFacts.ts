/**
 * UX-08 内置项目提示助手 —— 事实解码（唯一信任边界）。
 *
 * `ProjectGuidePanelProps` 的每一个输入都是 `unknown`。本文件把它们解码成
 * `GuideProjection`，并且：
 *
 * - **复用原 owner 自己的解码器**，绝不重新实现第二套：
 *   `productionWorkflowProjection()`（`production/productionWorkflowContract.ts`）与
 *   `checkedStoryboardReceipt()`（`creative/studioStoryboardContract.ts`）。
 * - 其余投影（素材浏览器行、任务中心投影、审核收件箱、图谱来源绑定、时间线）
 *   只**读取既有消费者已经投影出来的字段**，不重新取数、不重新解码整个响应；
 *   形状不合法就判该来源不可读（fail-closed），绝不按"空"处理。
 * - 一个输入被声明过但形状不合法 ⇒ 该来源不可读并记录原因；控制器的状态是
 *   `FAILED`，而不是"读到空项目"。
 *
 * 这里没有网络、没有模型、没有定时器：全部输入都是调用方已经加载好的数据。
 */
import { ApiError } from '../api';
import { checkedStoryboardReceipt } from '../creative/studioStoryboardContract';
import { ASSET_BROWSER_MEDIA_KINDS } from '../assetbrowser/assetBrowserTypes';
import {
  TASK_CENTER_STATUS_TOKEN, TASK_OWNER_FORMAL_STAGES, TASK_OWNER_STAGES, REVIEW_INBOX_ACTION_TOKEN,
} from '../taskcenter/taskCenterTypes';
import {
  PRODUCTION_WORKFLOW_ASSET_KINDS, PRODUCTION_WORKFLOW_INTENT_ID, PRODUCTION_WORKFLOW_PRESETS,
  type ProductionWorkflowAssetKind,
} from '../production/productionWorkflowTypes';
import { productionWorkflowProjection } from '../production/productionWorkflowContract';
import {
  GUIDE_BOUNDS, GUIDE_CODES, GUIDE_SOURCE_IDS,
  type GuideFacts, type GuideIntentFacts, type GuideModuleFacts, type GuideProblem, type GuideProjection,
  type GuideReadability, type GuideSourceId,
} from './projectGuideTypes';

/** 被声明的输入形状：每一个都是 `unknown`，解码前一律不可信。 */
export type GuideInput = {
  projectId?: unknown;
  identity?: unknown;
  /** 分镜文档身份（原 owner 的 `document_snapshot.id`）；缺失时退回 `projectId`。 */
  documentId?: unknown;
  workflow?: unknown;
  tasks?: unknown;
  inbox?: unknown;
  assets?: unknown;
  graph?: unknown;
  timeline?: unknown;
  storyboard?: unknown;
};

/* ------------------------------------------------------------ 基础校验器 */

function invalid(reason: string): never {
  throw new ApiError({ status: 200, code: GUIDE_CODES.factsInvalid, message: `项目提示事实不可用：${reason}。` });
}
function record(value: unknown, allowed: readonly string[]): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) invalid('不是对象');
  const row = value as Record<string, unknown>;
  if (Object.keys(row).some(key => !allowed.includes(key))) invalid('出现未知字段');
  return row;
}
/**
 * 只读投影的**逐字段**校验：`required` 是必须存在且由下面逐个校验的字段，
 * `allowed` 是允许出现（可能被忽略）的字段。这样既不会因为原 owner 新增一个
 * 字段就把整个来源判为不可读，也不会让一个残缺的行被当成可读。
 */
function readRow(value: unknown, required: readonly string[], allowed: readonly string[]): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) invalid('不是对象');
  const row = value as Record<string, unknown>;
  if (required.some(key => !Object.hasOwn(row, key))) invalid('缺少必需字段');
  if (Object.keys(row).some(key => !allowed.includes(key))) invalid('出现未知字段');
  return row;
}
function text(value: unknown, maximum: number = GUIDE_BOUNDS.id, empty = false): string {
  if (typeof value !== 'string' || value.length > maximum || /[\u0000-\u001f\u007f]/.test(value)) invalid('文本不合法');
  if (!empty && !value.trim()) invalid('文本为空');
  return value;
}
function integer(value: unknown, maximum: number = Number.MAX_SAFE_INTEGER): number {
  if (typeof value !== 'number' || !Number.isSafeInteger(value) || value < 0 || value > maximum) invalid('整数不合法');
  return value;
}
function boolean(value: unknown): boolean {
  if (typeof value !== 'boolean') invalid('布尔值不合法');
  return value;
}
function array(value: unknown, maximum: number): unknown[] {
  if (!Array.isArray(value) || value.length > maximum) invalid('数组不合法或超出上限');
  return value;
}
function strings(value: unknown, maximumItems: number, maximumLength: number): string[] {
  return array(value, maximumItems).map(item => text(item, maximumLength));
}
function oneOf<T extends string>(value: unknown, allowed: readonly T[]): T {
  if (typeof value !== 'string' || !allowed.includes(value as T)) invalid('取值不在 owner 词表内');
  return value as T;
}
/** 有界标识：`file:<uuid4>` / `postgres:<id>` / 资产 id。 */
function identifier(value: unknown, maximum: number = GUIDE_BOUNDS.id): string {
  const token = text(value, maximum);
  if (!/^[A-Za-z0-9][A-Za-z0-9:._@+-]*$/.test(token)) invalid('标识不合法');
  return token;
}

/* ------------------------------------------------------------- 各来源解码 */

const INTENT_VALUE_KEYS = ['intent_id', 'label', 'selected', 'custom'] as const;

export function readIntentFacts(value: unknown): GuideIntentFacts {
  const row = record(value, ['version', 'preset', 'values', 'editable', 'history_retained']);
  if (row.editable !== true || row.history_retained !== true) invalid('创作意图不是可编辑且保留历史的形状');
  if (row.preset !== null) oneOf(row.preset, PRODUCTION_WORKFLOW_PRESETS);
  const values = array(row.values, 32).map(item => {
    const entry = record(item, INTENT_VALUE_KEYS);
    const intentId = text(entry.intent_id, GUIDE_BOUNDS.detail);
    if (!PRODUCTION_WORKFLOW_INTENT_ID.test(intentId)) invalid('创作意图标识不符合 owner 语法');
    text(entry.label, 120, true);
    return { selected: boolean(entry.selected), custom: boolean(entry.custom) };
  });
  return Object.freeze({
    version: integer(row.version),
    value_count: values.length,
    selected_count: values.filter(entry => entry.selected).length,
  });
}

const MODULE_KEYS = ['id', 'label', 'status', 'document_count', 'asset_count', 'job_count', 'blocked_reasons', 'owner', 'next_action'] as const;

export function readModuleFacts(value: unknown): GuideModuleFacts[] {
  return array(value, 7).map(item => {
    const row = record(item, MODULE_KEYS);
    return Object.freeze({
      id: text(row.id, GUIDE_BOUNDS.detail),
      status: text(row.status, GUIDE_BOUNDS.detail),
      owner: text(row.owner, 120),
      blocked_reasons: Object.freeze(strings(row.blocked_reasons, 16, 300)),
    });
  });
}

const ASSET_OVERVIEW_KEYS = ['total', 'by_kind', 'private_pending_review', 'reviewed'] as const;

export type GuideAssetOverviewDecoded = GuideFacts['asset_overview'];

export function readAssetOverviewFacts(value: unknown): NonNullable<GuideAssetOverviewDecoded> {
  const row = record(value, ASSET_OVERVIEW_KEYS);
  const kinds = record(row.by_kind, PRODUCTION_WORKFLOW_ASSET_KINDS);
  const byKind = Object.fromEntries(PRODUCTION_WORKFLOW_ASSET_KINDS.map(kind =>
    [kind, integer(kinds[kind])])) as Record<ProductionWorkflowAssetKind, number>;
  const total = integer(row.total);
  if (PRODUCTION_WORKFLOW_ASSET_KINDS.reduce((count, kind) => count + byKind[kind], 0) !== total) {
    invalid('素材概览的各分类之和不等于总数');
  }
  return Object.freeze({
    total,
    by_kind_image: byKind.image, by_kind_audio: byKind.audio, by_kind_video: byKind.video,
    private_pending_review: integer(row.private_pending_review),
    reviewed: integer(row.reviewed),
  });
}

/** 原 owner 会输出的全部状态码（与 `taskcenter` 同一份词表，逐条转写而不是重声明）。 */
const TASK_OWNER_STATUS_CODES: readonly string[] = [
  ...TASK_OWNER_STAGES.map(row => row[0]), ...TASK_OWNER_FORMAL_STAGES.map(row => row[0]),
];

/** 任务行：只读既有消费者已经投影出来的状态、过期标记、进度与 owner 自己声明的刷新事实。 */
export type GuideTaskRow = { authority: string; id: string; status: string; stale: boolean; has_progress: boolean };
export type GuideTaskDecoded = {
  total: number; without_progress: number; stale: number; unavailable: number; truncated: boolean;
  undefined_status: readonly string[];
};

function readTaskRow(value: unknown): GuideTaskRow {
  const row = readRow(value, ['authority', 'id', 'status', 'stale', 'progress'],
    ['authority', 'id', 'label', 'feature', 'status', 'raw_status', 'stage_label', 'version', 'progress',
      'history', 'stale', 'cost', 'error_code', 'provider_id', 'model_id', 'route_state', 'actions',
      'action_limits', 'retry_policy', 'lifecycle', 'source', 'owner_navigation', 'navigation_contract',
      'source_domain', 'revision']);
  const status = text(row.status, GUIDE_BOUNDS.detail);
  if (!TASK_CENTER_STATUS_TOKEN.test(status)) invalid('任务状态语法不合法');
  // `progress` 只在 owner 同时给出 completed+total 时才算存在；缺失保持"无进度"。
  const progress = row.progress === null ? null : readRow(row.progress, ['completed', 'total'],
    ['completed', 'total', 'unit']);
  if (progress) { integer(progress.completed); integer(progress.total); text(progress.unit, 16, true); }
  const actions = row.actions === undefined ? [] : strings(row.actions, 32, 64);
  for (const action of actions) if (!/^[a-z][a-z0-9_]{0,31}$/.test(action)) invalid('任务动作语法不合法');
  return { authority: text(row.authority, GUIDE_BOUNDS.detail), id: identifier(row.id), status, stale: boolean(row.stale), has_progress: progress !== null };
}

export function readTaskFacts(value: unknown): GuideTaskDecoded {
  const row = readRow(value, ['project_id', 'items', 'unavailable', 'truncated'],
    ['project_id', 'scope_verified', 'items', 'unavailable', 'truncated', 'executor', 'refresh', 'automatic_retries']);
  if (row.executor !== false || row.refresh !== 'MANUAL' || row.automatic_retries !== false) {
    invalid('任务投影没有声明"没有执行器、手动刷新、不自动重试"');
  }
  if (row.scope_verified !== undefined) boolean(row.scope_verified);
  const items = array(row.items, 500).map(readTaskRow);
  const unavailable = array(row.unavailable, 64).map(entry =>
    readRow(entry, ['authority', 'reason'], ['authority', 'label', 'reason']));
  const known = new Set<string>(TASK_OWNER_STATUS_CODES);
  return Object.freeze({
    total: items.length,
    without_progress: items.filter(task => !task.has_progress).length,
    stale: items.filter(task => task.stale).length,
    unavailable: unavailable.length,
    truncated: boolean(row.truncated),
    /** owner 未定义的状态：保留原始码，只用于呈现"按结果未知处理"，不猜成别的阶段。 */
    undefined_status: Object.freeze(items.filter(task => !known.has(task.status)).map(task => task.status)),
  });
}

/** 审核收件箱行：只读 id / domain / status / stale / allowed_actions / version。 */
export type GuideInboxRow = { id: string; domain: string; status: string; stale: boolean };
export type GuideInboxDecoded = { total: number; unresolved: number; unavailable: number };

const INBOX_ITEM_FIELDS = ['id', 'domain', 'status', 'stale', 'preview', 'target', 'target_navigation_contract',
  'version', 'allowed_actions', 'batch_actions', 'batch_safe', 'source', 'source_versions', 'source_hash',
  'privacy_state', 'risk', 'created_by', 'recovery_state', 'promotion_recovery_required', 'novel_id',
  'project', 'workspace', 'branch', 'scope'] as const;

function readInboxRow(value: unknown): GuideInboxRow {
  const row = readRow(value, ['id', 'domain', 'status', 'stale', 'allowed_actions', 'version'], INBOX_ITEM_FIELDS);
  integer(row.version);
  for (const action of strings(row.allowed_actions, 32, 64)) {
    if (!REVIEW_INBOX_ACTION_TOKEN.test(action)) invalid('审核动作语法不合法');
  }
  if (row.batch_actions !== undefined) strings(row.batch_actions, 32, 64);
  return {
    id: identifier(row.id), domain: text(row.domain, GUIDE_BOUNDS.detail),
    status: text(row.status, GUIDE_BOUNDS.detail), stale: boolean(row.stale),
  };
}

export function readInboxFacts(value: unknown): GuideInboxDecoded {
  const row = readRow(value, ['items', 'total', 'unavailable'],
    ['project_id', 'items', 'total', 'unavailable', 'approval_authority', 'batch_semantics']);
  if (row.approval_authority !== undefined && row.approval_authority !== 'DOMAIN_SERVICE') {
    invalid('审核收件箱没有声明原领域审批权属');
  }
  if (row.batch_semantics !== undefined && row.batch_semantics !== 'PER_ITEM_CHECKPOINT') {
    invalid('审核收件箱没有声明逐项 checkpoint');
  }
  const items = array(row.items, 500).map(readInboxRow);
  const unavailable = array(row.unavailable, 64).map(entry => readRow(entry, ['domain', 'reason'], ['domain', 'reason']));
  const total = integer(row.total);
  if (total < items.length) invalid('审核收件箱总数小于条目数');
  return Object.freeze({
    total,
    /** 未处理 = 仍在收件箱里的条目（领域自己的状态）+ 不可读领域：不可读绝不是"已处理"。 */
    unresolved: items.filter(item => item.status.trim().length > 0).length,
    unavailable: unavailable.length,
  });
}

const ASSET_ROW_FIELDS = ['id', 'filename', 'kind', 'media_kind', 'media_type', 'size', 'digest', 'version',
  'review_state', 'created_at', 'created_at_ms', 'created_bucket', 'tags', 'integrity', 'stale',
  'license_label', 'license_verification', 'deleted', 'reference_counts', 'origin', 'operation',
  'parents', 'sources', 'declaration_history_versions'] as const;

export type GuideAssetLibraryDecoded = { total: number; deleted: number; by_kind: Record<string, number> };

export function readAssetLibraryFacts(value: unknown): GuideAssetLibraryDecoded {
  const rows = array(value, 500).map(item => {
    const row = readRow(item, ['id', 'kind', 'deleted'], ASSET_ROW_FIELDS);
    identifier(row.id);
    if (row.filename !== undefined) text(row.filename, 255, true);
    text(row.kind, 40);
    if (row.media_kind !== null && row.media_kind !== undefined) oneOf(row.media_kind, ASSET_BROWSER_MEDIA_KINDS);
    boolean(row.deleted);
    return row;
  });
  return Object.freeze({
    total: rows.length,
    deleted: rows.filter(row => row.deleted === true).length,
    by_kind: Object.freeze(Object.fromEntries(ASSET_BROWSER_MEDIA_KINDS.map(kind =>
      [kind, rows.filter(row => row.media_kind === kind).length])) as Record<string, number>),
  });
}

const GRAPH_KEYS = ['nodes', 'edges', 'reference_states'] as const;

export type GuideGraphDecoded = {
  nodes: number; edges: number; disabled_nodes: number;
  reference_states: readonly { node_id: string; state: string }[];
};

export function readGraphFacts(value: unknown): GuideGraphDecoded {
  const row = record(value, GRAPH_KEYS);
  const nodes = array(row.nodes, 500).map(item => record(item, ['id', 'definition_id', 'enabled']));
  const edges = array(row.edges, 2000).map(item =>
    record(item, ['id', 'source_node_id', 'source_port', 'target_node_id', 'target_port']));
  const referenceStates = array(row.reference_states, 500).map(item => {
    const state = record(item, ['node_id', 'state']);
    return Object.freeze({
      node_id: identifier(state.node_id),
      state: oneOf(state.state, ['CURRENT', 'STALE', 'UNAVAILABLE'] as const),
    });
  });
  return Object.freeze({
    nodes: nodes.length,
    edges: edges.length,
    disabled_nodes: nodes.filter(node => node.enabled === false).length,
    reference_states: Object.freeze(referenceStates),
  });
}

export type GuideTimelineDecoded = { track_count: number; clip_count: number };

export function readTimelineFacts(value: unknown): GuideTimelineDecoded {
  const row = record(value, ['tracks', 'clips']);
  const tracks = array(row.tracks, 8).map(item => record(item, ['id', 'kind']));
  const clips = array(row.clips, 30).map(item => record(item, ['id', 'track_id', 'start_ms']));
  return Object.freeze({ track_count: tracks.length, clip_count: clips.length });
}

export type GuideStoryboardDecoded = { shot_count: number; approved: boolean | null };

export function readStoryboardFacts(value: unknown, documentId: string): GuideStoryboardDecoded {
  const receipt = checkedStoryboardReceipt(value, documentId);
  return Object.freeze({ shot_count: receipt.shots.length, approved: receipt.approved });
}

/**
 * `facts` 信封：挂载方可以按同一形状整体传入。今天它**只**承载分镜回执
 * （其余事实一律走具名投影），未知键与残缺形状都会被拒绝。
 */
export type GuideFactsEnvelope = { storyboard?: unknown };

export function readFactsEnvelope(value: unknown): GuideFactsEnvelope {
  const row = readRow(value, [], ['storyboard']);
  return Object.freeze({
    ...(row.storyboard === undefined ? {} : { storyboard: row.storyboard }),
  });
}

/* --------------------------------------------------------------- 组合解码 */

/* --------------------------------------------------------------- 组合解码 */

/** 一个输入被声明但不可读时的原因（`source` 精确到来源）。 */
function problemOf(reason: unknown, source: GuideSourceId | 'INPUT'): GuideProblem {
  return Object.freeze({
    // 输入形状层面的问题一律用本模块自己的稳定码（owner 的码只描述它自己的投影）。
    code: GUIDE_CODES.factsInvalid,
    source,
    message: reason instanceof ApiError ? reason.problem.message : `原 owner 投影不可用：${source}。`,
  });
}

/**
 * 一个来源要么没被声明（不可读），要么被声明且形状合法（可读）；
 * 声明了但形状不合法就是不可读 + 一条原因，绝不按"空投影"处理。
 */
export function decodeGuideInput(input: GuideInput): GuideProjection {
  const projectId = text(input.projectId, GUIDE_BOUNDS.project_id);
  const identity = text(input.identity, GUIDE_BOUNDS.identity);
  // 分镜回执自带文档身份；没有显式给出时按项目身份核对，绝不因此放行别的文档。
  const documentId = input.documentId === undefined
    ? projectId : text(input.documentId, GUIDE_BOUNDS.id);
  const problems: GuideProblem[] = [];
  const read: Record<GuideSourceId, boolean> = Object.fromEntries(
    GUIDE_SOURCE_IDS.map(id => [id, false])) as Record<GuideSourceId, boolean>;

  function attempt<T>(source: GuideSourceId, declared: boolean, work: () => T): T | null {
    if (!declared) return null;
    try {
      const value = work();
      read[source] = true;
      return value;
    } catch (reason) {
      problems.push(problemOf(reason, source));
      return null;
    }
  }

  // 制作工作流：唯一的"整套投影"输入，仍然由原 owner 自己的严格解码器核对。
  let workflow: ReturnType<typeof productionWorkflowProjection> | null = null;
  if (input.workflow !== undefined) {
    workflow = attempt('PRODUCTION_WORKFLOW_PROJECTION', true,
      () => productionWorkflowProjection(input.workflow, projectId, { mode: 'local', novel_id: projectId }));
  }

  const intent = attempt('CREATIVE_INTENT', workflow !== null, () => readIntentFacts(workflow?.creative_intent));
  const modules = attempt('PRODUCTION_MODULES', workflow !== null, () => readModuleFacts(workflow?.modules));
  const assetOverview = attempt('ASSET_OVERVIEW', workflow !== null, () => readAssetOverviewFacts(workflow?.asset_overview));

  const tasks = attempt('TASK_PROJECTION', input.tasks !== undefined, () => readTaskFacts(input.tasks));
  const inbox = attempt('REVIEW_INBOX_PROJECTION', input.inbox !== undefined, () => readInboxFacts(input.inbox));
  const assets = attempt('ASSET_BROWSER_PROJECTION', input.assets !== undefined, () => readAssetLibraryFacts(input.assets));
  const graph = attempt('GRAPH_REFERENCE_STATES', input.graph !== undefined, () => readGraphFacts(input.graph));
  const timeline = attempt('TIMELINE_TRACKS', input.timeline !== undefined, () => readTimelineFacts(input.timeline));
  const storyboard = attempt('STORYBOARD_RECEIPT', input.storyboard !== undefined,
    () => readStoryboardFacts(input.storyboard, documentId));

  const facts: GuideFacts = Object.freeze({
    project_id: projectId,
    identity,
    intent,
    modules: modules === null ? null : Object.freeze(modules),
    asset_overview: assetOverview,
    tasks,
    review_inbox: inbox,
    asset_library: assets,
    graph,
    timeline,
    storyboard,
  });
  const sourcesReadable: GuideReadability = Object.freeze({ ...read });
  return Object.freeze({
    facts,
    sources_readable: sourcesReadable,
    problems: Object.freeze(problems.slice(0, GUIDE_BOUNDS.problems)),
    sources_read_count: GUIDE_SOURCE_IDS.filter(id => sourcesReadable[id]).length,
  });
}

/** 兼容入口：`unknown` 输入 → 解码后的事实，或一个显式拒绝（形状层不合法）。 */
export function decodeProjectGuideInput(input: unknown): GuideProjection | { ok: false; code: string; message: string; reason: string } {
  if (!input || typeof input !== 'object' || Array.isArray(input)) {
    return { ok: false, code: GUIDE_CODES.factsInvalid, message: '项目提示事实不可用：输入不是对象。', reason: 'input 不是对象' };
  }
  try {
    return decodeGuideInput(input as GuideInput);
  } catch (reason) {
    return reason instanceof ApiError
      ? { ok: false, code: reason.problem.code, message: reason.problem.message, reason: '项目事实形状不合法' }
      : { ok: false, code: GUIDE_CODES.factsInvalid, message: '项目提示事实不可用。', reason: '本地解码失败' };
  }
}
