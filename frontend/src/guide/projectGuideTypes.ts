/**
 * UX-08 内置项目提示助手 —— 类型、稳定机器码与冻结词表。
 *
 * 这个文件夹是**消费者**：它不新增任何项目 / 素材 / 任务 / 图谱 / 时间线 owner，
 * 也不产生任何模型调用、网络请求或后端字段。每一条提示都必须从一个**真实原
 * owner 已经给出的字段**推导出来（见 `projectGuideOps.ts` 的 `nextSteps`），
 * 没有 owner 事实就不产生提示，而不是猜一个。
 *
 * 事实来源（全部是既有消费者已经解码的投影）：
 * - `frontend/src/production/*`：`ProductionWorkflowProjection`
 *   （`studio-production-workflow/1`，七个模块 + 创作意图 + 素材概览 + 看板）。
 * - `frontend/src/taskcenter/*`：`TaskCenterTasksProjection` / `ReviewInboxProjection`
 *   （原 `WorkspaceToolsService.tasks` / `UnifiedReviewInbox` 投影）。
 * - `frontend/src/assetbrowser/*`：`AssetBrowserRow`（原 `_index_row()` / `public()` 投影）。
 * - `frontend/src/creative/studioGraphTypes.ts`：`StudioGraphReferenceState`
 *   （`{node_id, state: CURRENT|STALE|UNAVAILABLE}`，来自已保存图定义）。
 * - `frontend/src/creative/studioTimelineTypes.ts`：轨道 / 片段 id（已保存时间线）。
 * - `frontend/src/onboarding/studioEntryTypes.ts`：`StudioIntentValue[]`。
 *
 * **青简（QingJian）是暂停的**：这里只保留一个 `available: false` 的隐藏扩展点，
 * 没有客户端、没有端点、没有适配器，界面既不显示"已连接青简"，也不伪造任何导师建议。
 */

/* ------------------------------------------------------------------ 事实来源 */

/** 本助手可能引用的事实来源标识。每一个都必须对应一个真实存在的原 owner 投影。 */
export const GUIDE_SOURCE_IDS = [
  'PRODUCTION_WORKFLOW_PROJECTION', 'CREATIVE_INTENT', 'ASSET_OVERVIEW', 'PRODUCTION_MODULES',
  'TASK_PROJECTION', 'REVIEW_INBOX_PROJECTION', 'ASSET_BROWSER_PROJECTION',
  'GRAPH_REFERENCE_STATES', 'TIMELINE_TRACKS', 'STORYBOARD_RECEIPT',
] as const;
export type GuideSourceId = typeof GUIDE_SOURCE_IDS[number];

/** 界面自己写的机器码（稳定，可测）。用户可见文案一律中文，码不改。 */
export const GUIDE_CODES = {
  /** 声明的输入形状不合法：按失败处理，绝不按"空项目"处理。 */
  factsInvalid: 'PROJECT_GUIDE_FACTS_INVALID',
  /** 没有任何可读的原 owner 投影：提示助手拒绝编造建议。 */
  factsUnreadable: 'PROJECT_GUIDE_FACTS_UNREADABLE',
  /** 提示没有引用任何原 owner 字段：被 `noFabrication()` 拒绝。 */
  uncitedHint: 'PROJECT_GUIDE_HINT_UNCITED',
  /** 全部原 owner 事实都读到了，且没有任何下一步：未验证的"看起来没问题"。 */
  noFactsAvailable: 'PROJECT_GUIDE_NO_FACTS_AVAILABLE',
  /** 阻塞原因只有原 owner 能给，这里不给通用重试文案。 */
  blockerOwnerOnly: 'PROJECT_GUIDE_BLOCKER_OWNER_ONLY',
  /** 阻塞该模块的依据是本助手没有读到的 owner 阅读面。 */
  blockerUnverified: 'PROJECT_GUIDE_BLOCKER_UNVERIFIED',
  /** 未验证的进度结论：绝不写成"可以交付/可以渲染"。 */
  notVerifiedByGuide: 'PROJECT_GUIDE_NOT_VERIFIED',
  /** 青简扩展点当前不可用（停止接线）；扩展点自身在 `qingjianExtension.ts`。 */
  qingjianUnavailable: 'PROJECT_GUIDE_QINGJIAN_UNAVAILABLE',
  /** 空项目 ≠ 被拒绝：只有读成功且确实没有事实时才是 EMPTY。 */
  emptyIsNotDenied: 'PROJECT_GUIDE_EMPTY_IS_NOT_DENIED',
} as const;
export type GuideCode = typeof GUIDE_CODES[keyof typeof GUIDE_CODES];

/* ------------------------------------------------------------------ 提示码 */

/**
 * 提示码：每一条都逐条绑定一个真实原 owner 字段（`GUIDE_CODES` 之上的一层）。
 * 冻结顺序就是**依赖顺序**，也是展示顺序。
 */
export const GUIDE_HINT_CODES = [
  'FACTS_UNREADABLE', 'FACTS_PARTIALLY_UNREADABLE', 'NO_FACTS_READ',
  'BLOCKED_SOURCE_REFERENCE', 'UNREADY_GRAPH_PREFLIGHT', 'REQUIREMENT_UNMET_ASSET_DEPENDENCY',
  'INTENT_NOT_SET', 'INTENT_UNREADABLE', 'REVIEW_ITEMS_UNRESOLVED', 'TASKS_NONE_READ',
  'ASSETS_LIBRARY_EMPTY', 'TIMELINE_UNRENDERED', 'STORYBOARD_NOT_APPROVED', 'NO_NEXT_STEP_VERIFIED',
] as const;
export type GuideHintCode = typeof GUIDE_HINT_CODES[number];

/** 展示严重度（呈现用；不改变任何 owner 状态）。 */
export const GUIDE_HINT_SEVERITIES = ['CRITICAL', 'BLOCKING', 'ATTENTION', 'INFO'] as const;
export type GuideHintSeverity = typeof GUIDE_HINT_SEVERITIES[number];
export const GUIDE_HINT_SEVERITY_TONES: Readonly<Record<GuideHintSeverity, 'error' | 'warning' | 'info' | 'neutral'>> =
  Object.freeze({ CRITICAL: 'error', BLOCKING: 'error', ATTENTION: 'warning', INFO: 'info' });

/** 冻结的提示定义：中文文案 + 原 owner + 该提示允许导航到的既有视图。 */
export type GuideHintDefinition = {
  readonly label: string;
  readonly message: string;
  readonly severity: GuideHintSeverity;
  /** 该提示在 owner 服务端投影上的归属（模块 id 或 owner 名），不是界面发明的模块。 */
  readonly owner: string;
  /** 既有的工作区视图名之一；`null` 表示此提示没有导航目标。 */
  readonly navigate: GuideViewName | null;
};

export const GUIDE_HINTS: Readonly<Record<GuideHintCode, GuideHintDefinition>> = Object.freeze({
  FACTS_UNREADABLE: {
    label: '项目事实不可读',
    message: '这个项目的数据面当前读不到（可能是加载失败、范围不一致或响应形状不合法）。提示助手不会据此编造建议。',
    severity: 'CRITICAL', owner: 'PRODUCTION_WORKFLOW_PROJECTION', navigate: 'PRODUCTION',
  },
  FACTS_PARTIALLY_UNREADABLE: {
    label: '部分原 owner 事实不可读',
    message: '有原 owner 的阅读面读取失败或被拒绝。下面只根据读到的部分给出提示，缺失的部分按"未核实"处理，绝不当作"没有问题"。',
    severity: 'ATTENTION', owner: 'ASSET_BROWSER_PROJECTION', navigate: 'ASSETS',
  },
  NO_FACTS_READ: {
    label: '没有可读的项目事实',
    message: '当前没有传入任何可读的原 owner 投影（项目状态、素材、任务、图谱或时间线）。这不是"项目没有问题"，而是"事实不可读"。',
    severity: 'CRITICAL', owner: 'PRODUCTION_WORKFLOW_PROJECTION', navigate: 'START',
  },
  BLOCKED_SOURCE_REFERENCE: {
    label: '存在被阻塞的来源绑定',
    message: '已有保存的节点引用了过期或不可读的来源。解除阻塞只能由原图谱 owner 重新核对来源版本后完成，这里不会自动重连或自动重跑。',
    severity: 'BLOCKING', owner: 'GRAPH_REFERENCE_STATES', navigate: 'GRAPH',
  },
  UNREADY_GRAPH_PREFLIGHT: {
    label: '图谱尚未通过预检',
    message: '已保存图里存在未启用的节点或空的连接，原预检不会通过。这里只报告状态，不接受改动、不派发执行。',
    severity: 'ATTENTION', owner: 'GRAPH_REFERENCE_STATES', navigate: 'GRAPH',
  },
  REQUIREMENT_UNMET_ASSET_DEPENDENCY: {
    label: '模块前置条件未满足',
    message: '这个模块依赖的素材库阅读面当前不可读，因此它的前置条件只能算"未核实"，不能当作已满足。',
    severity: 'ATTENTION', owner: 'ASSET_OVERVIEW', navigate: 'ASSETS',
  },
  INTENT_NOT_SET: {
    label: '尚未选择创作意图',
    message: '当前项目的创作意图一项都没有选中。创作意图只影响推荐布局与提示，不是权限；点开项目入口可以随时设置。',
    severity: 'INFO', owner: 'CREATIVE_INTENT', navigate: 'START',
  },
  INTENT_UNREADABLE: {
    label: '创作意图不可读',
    message: '没有读到创作意图的版本与取值。是否存在已保存的意图**无法核实**，因此这里不会声称"还没有设置意图"。',
    severity: 'ATTENTION', owner: 'CREATIVE_INTENT', navigate: 'START',
  },
  REVIEW_ITEMS_UNRESOLVED: {
    label: '有未处理的审核候选',
    message: '审核收件箱里还有待处理的候选。决定只能由原领域审核服务执行；这里不代替批准或驳回。',
    severity: 'ATTENTION', owner: 'REVIEW_INBOX_PROJECTION', navigate: 'TASKS',
  },
  TASKS_NONE_READ: {
    label: '任务队列没有可核实的条目',
    message: '任务投影当前没有返回任何条目，或有来源不可读。原 owner 声明执行器与自动重试都不存在，因此这里也不会自动重试。',
    severity: 'INFO', owner: 'TASK_PROJECTION', navigate: 'TASKS',
  },
  ASSETS_LIBRARY_EMPTY: {
    label: '素材库为空',
    message: '原素材投影报告当前项目没有任何素材。导入与手动编辑不依赖模型或网络，随时可用。',
    severity: 'INFO', owner: 'ASSET_OVERVIEW', navigate: 'ASSETS',
  },
  TIMELINE_UNRENDERED: {
    label: '时间线尚未成片',
    message: '已保存时间线还没有可渲染的片段。渲染与导出仍由原时间线服务决定，且产物是私有候选，需要人工审核。',
    severity: 'ATTENTION', owner: 'TIMELINE_TRACKS', navigate: 'PRODUCTION',
  },
  STORYBOARD_NOT_APPROVED: {
    label: '分镜尚未批准',
    message: '原分镜回执报告当前文档版本尚未批准。批准只能由原分镜 owner 执行，这里不代替批准。',
    severity: 'ATTENTION', owner: 'STORYBOARD_RECEIPT', navigate: 'STORYBOARD',
  },
  NO_NEXT_STEP_VERIFIED: {
    label: '没有可核实的下一步',
    message: '已读到的原 owner 事实里没有出现待处理项。这**不是**产品验收结论，也不代表可以交付：执行完成不等于交付。',
    severity: 'INFO', owner: 'PRODUCTION_MODULES', navigate: 'PRODUCTION',
  },
});

/** 每条提示的中文说明里必须出现的原 owner 归属串（测试与审计用，不可省略）。 */
export const GUIDE_HINT_OWNER_LABELS: Readonly<Record<string, string>> = Object.freeze({
  PRODUCTION_WORKFLOW_PROJECTION: '制作工作流投影',
  CREATIVE_INTENT: '创作意图',
  ASSET_OVERVIEW: '素材概览',
  PRODUCTION_MODULES: '制作模块',
  TASK_PROJECTION: '任务投影',
  REVIEW_INBOX_PROJECTION: '审核收件箱',
  ASSET_BROWSER_PROJECTION: '素材浏览器',
  GRAPH_REFERENCE_STATES: '图谱来源绑定',
  TIMELINE_TRACKS: '时间线轨道',
  STORYBOARD_RECEIPT: '分镜回执',
});

/** 一个来源的中文说明（呈现与审计共用）。每一个已声明来源都必须有名字。 */
export function guideSourceDescription(source: GuideSourceId): string {
  return GUIDE_HINT_OWNER_LABELS[source] ?? source;
}

/* ------------------------------------------------------------------ 边界 */

export const GUIDE_BOUNDS = Object.freeze({
  project_id: 240,
  identity: 240,
  /** 一次最多接受的提示条数；提示码本身有限，超出说明输入被污染。 */
  hints: 32,
  /** 一条提示最多引用多少个原 owner 事实。 */
  citations: 8,
  /** 一次最多接受多少个不可读来源记录。 */
  problems: 16,
  /** `detail` 是 owner 自己给的短标识（状态码 / 模块 id / 资产 id），不是自由文本。 */
  detail: 240,
  id: 240,
  /** 预览文本上限（与 `studioGraphTypes` 的 `preview` 同一量级）。 */
  text: 2000,
  reason: 300,
});

/* ------------------------------------------------------------------ 事实形状 */

/** 一个具体 owner 字段引用：`<source>:<key>`，key 里可以再带 owner 自己的 id。 */
export const GUIDE_FACT_PREFIX = 'fact:';

export type GuideFact = {
  /** 精确到字段的来源标识，例如 `director.blocked_reasons`、`graph.node:n_1.state`。 */
  readonly source: string;
  /** owner 自己给出的有界标识或状态码；不是界面拼的自由文本。 */
  readonly detail: string;
};

export type GuideIntentFacts = { readonly version: number; readonly selected_count: number; readonly value_count: number };
export type GuideModuleFacts = {
  readonly id: string;
  readonly status: string;
  readonly owner: string;
  readonly blocked_reasons: readonly string[];
};
export type GuideAssetOverviewFacts = {
  readonly total: number;
  /** 逐媒体种类的计数取自 owner 自己的 `by_kind`（`PRODUCTION_WORKFLOW_ASSET_KINDS`）。 */
  readonly by_kind_image: number;
  readonly by_kind_audio: number;
  readonly by_kind_video: number;
  readonly private_pending_review: number;
  readonly reviewed: number;
};
export type GuideTaskFacts = {
  readonly total: number;
  readonly without_progress: number;
  readonly stale: number;
  readonly unavailable: number;
  readonly truncated: boolean;
  /** owner 未定义的原始状态码（只用于"按结果未知处理"）。 */
  readonly undefined_status?: readonly string[];
};
export type GuideReviewInboxFacts = {
  readonly total: number;
  /** 仍在收件箱里的条目（领域自己的状态）。 */
  readonly unresolved: number;
  /** 不可读的领域；永远不会被算成"已处理"。 */
  readonly unavailable: number;
};
export type GuideAssetLibraryFacts = { readonly total: number };
export type GuideGraphFacts = {
  readonly nodes: number;
  readonly edges: number;
  readonly disabled_nodes: number;
  readonly reference_states: readonly { readonly node_id: string; readonly state: string }[];
};
export type GuideTimelineFacts = { readonly track_count: number; readonly clip_count: number };
export type GuideStoryboardFacts = { readonly shot_count: number; readonly approved: boolean | null };

/**
 * 已经解码的项目事实。`GuideFacts` **不声明** `readable`：哪些来源真的读到了，
 * 只由 `ProjectGuideFacts.sources_readable` 决定，提示生成器对不可读来源一律抛错。
 */
export type GuideFacts = {
  readonly project_id: string;
  readonly identity: string;
  readonly intent: GuideIntentFacts | null;
  readonly modules: readonly GuideModuleFacts[] | null;
  readonly asset_overview: GuideAssetOverviewFacts | null;
  readonly tasks: GuideTaskFacts | null;
  readonly review_inbox: GuideReviewInboxFacts | null;
  readonly asset_library: GuideAssetLibraryFacts | null;
  readonly graph: GuideGraphFacts | null;
  readonly timeline: GuideTimelineFacts | null;
  readonly storyboard: GuideStoryboardFacts | null;
};

/** 一个来源不可读：要么它根本没有传入，要么它的形状不合法（fail-closed）。 */
export type GuideProblem = { readonly code: string; readonly source: GuideSourceId | 'INPUT'; readonly message: string };

export type GuideReadability = Readonly<Record<GuideSourceId, boolean>>;

/** 解码结果：事实 + 逐来源可读性 + 不可读原因。 */
export type GuideProjection = {
  readonly facts: GuideFacts;
  readonly sources_readable: GuideReadability;
  readonly problems: readonly GuideProblem[];
  /** 真的读到（而不是"读到 0 条"）的来源数。 */
  readonly sources_read_count: number;
};

/* ------------------------------------------------------------------ 提示 */

export type GuideViewName = 'START' | 'ASSETS' | 'GRAPH' | 'PRODUCTION' | 'TASKS' | 'STORYBOARD';

/**
 * 既有工作区视图名。前五个逐字来自 `creative/studioWorkspaceResume.ts` 的
 * `StudioWorkspaceView`；`STORYBOARD` 是本工作包新增的既有模块视图，**不**写入
 * 那个 resume 记录，也不新增任何导航面。
 */
export const GUIDE_VIEW_NAMES: readonly GuideViewName[] = Object.freeze(
  ['START', 'ASSETS', 'GRAPH', 'PRODUCTION', 'TASKS', 'STORYBOARD'] as const);

/** 一条提示：claim + 引用的原 owner 事实 + 精确的下一步动作。 */
export type GuideHint = {
  readonly code: GuideHintCode;
  readonly severity: GuideHintSeverity;
  readonly label: string;
  readonly message: string;
  /** 原 owner 归属（`GUIDE_HINTS[code].owner`）。 */
  readonly owner: string;
  /** 这条提示引用的每一个原 owner 事实。没有它就是未引用的提示。 */
  readonly sources: readonly GuideFact[];
  /** 精确的下一步动作文案（由原 owner 的事实决定，不是通用"请稍后重试"）。 */
  readonly next_action: string;
  /** 既有工作区视图名；`null` = 此提示没有导航目标。 */
  readonly navigate: GuideViewName | null;
};

/** `explainBlocker()` 的结论：阻塞进度的是哪一个具体 owner 事实。 */
export type GuideBlockerExplanation = {
  readonly code: GuideHintCode;
  readonly severity: GuideHintSeverity;
  readonly claim: string;
  readonly next_action: string;
  readonly navigate: GuideViewName | null;
  /** 明确到字段的 owner 事实，不是"网络错误"这类通用说法。 */
  readonly sources: readonly GuideFact[];
  /** `null` = 本助手读到了这个事实；否则说明为什么读不到。 */
  readonly refusal: GuideRefusal | null;
};

/** 拒绝形状：宁可什么都不说，也不编造。 */
export type GuideRefusal = { readonly ok: false; readonly code: string; readonly message: string; readonly reason: string };
export type GuideAcceptance = { readonly ok: true; readonly hint: GuideHint };

/* ------------------------------------------------------------------ 数据面状态 */

/** 与 `TaskCenterSurfaceState` / `AssetBrowserSurfaceState` 同一套显式状态。 */
export const GUIDE_SURFACE_STATES = ['IDLE', 'LOADING', 'READY', 'EMPTY', 'DENIED', 'FAILED'] as const;
export type GuideSurfaceState = typeof GUIDE_SURFACE_STATES[number];

/** 界面自己说的边界话术（有界、可测）。 */
export const GUIDE_NOTICES = Object.freeze({
  /** 事实不可读是唯一正确的说法；绝不退化成"项目很干净"。 */
  unreadable: '原项目事实当前不可读，因此这里不给建议：提示助手只复述原 owner 的字段，不会编造下一步。',
  /** 被拒绝 ≠ 空项目。 */
  deniedIsNotUnknownProject: '当前会话无权读取这个项目的提示事实；这不是"项目还没有内容"。',
  /** 空项目 ≠ 被拒绝。 */
  emptyIsNotDenied: '当前项目没有可读的原 owner 事实：这是"读到了空的投影"，不是"被拒绝"。',
  /** 部分不可读必须显式说明。 */
  partialUnreadable: '部分原 owner 阅读面不可读，下面的提示只基于读到的部分。',
  /** 提示永远引用来源。 */
  everyHintCitesOwner: '每条提示都列出它引用的原 owner 字段；没有来源的提示不会被显示。',
  /** 不承诺当前不具备的能力。 */
  capabilityBoundary: '提示只描述当前项目状态与既有入口：不包含 Windows 安装、GPU 或重型渲染的承诺，也不代表产品验收通过。',
  /** 扩展点。 */
  qingjianDisabled: '青简接入当前暂停：扩展点存在但保持禁用，不注册任何适配器、不显示连接状态、不产生导师建议。',
  /** 扩展点注册被拒绝时的说明。 */
  qingjianRegistrationRefused: '青简扩展点当前不可用：没有注册任何导师适配器，因此也没有任何导师建议可以被显示。',
} as const);
