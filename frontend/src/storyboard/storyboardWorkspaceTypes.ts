/**
 * UX-05 导演与分镜实际工作区 — 表示层类型与冻结词表。
 *
 * 这里没有第二个分镜引擎：镜头身份、版本、批准与绑定全部来自既有 owner
 * （`app/creative/storyboard.py::StoryboardWorkspace` 投影，经
 * `frontend/src/creative/studioStoryboardContract.ts` 严格解码）。本文件只声明
 * 本工作区自己的呈现层类型，让视图无法凭"看起来像"就补出一个原文档没有的值。
 *
 * 冻结字面量必须与 owner 一致，UI 不允许自行漂移：
 *  - 镜头身份 `shot_id` 与显示序号 `number` 是两个字段
 *    （`app/creative/service.py::prepare_content` 只按 `number` 排序，身份不变）。
 *  - 批准契约 `studio-storyboard-approval/1`、内容摘要 `content_digest`。
 *  - 绑定请求体 `ShotImageBinding` / `ShotVideoBinding`（都继承 `ShotAction`）。
 */

import type { CreativeShot, DirectorNote } from '../creative/types';
import type { DirectorAdvice } from '../creative/studioStoryboardContract';
import type { PlanningSnapshot } from '../creative/studioProductionGraphContract';
import type {
  StoryboardImage, StoryboardReceipt, StoryboardShot,
  StoryboardTimelineDraft, StoryboardVideoAsset, StoryboardVideoResult, VideoJobPin,
} from '../creative/studioStoryboardContract';

export type {
  CreativeShot, DirectorAdvice, DirectorNote, PlanningSnapshot, StoryboardImage, StoryboardReceipt,
  StoryboardShot, StoryboardTimelineDraft, StoryboardVideoAsset, StoryboardVideoResult, VideoJobPin,
};

/** 只用于身份核对；不携带可执行内容，也不会被当成版本针使用。 */
export type StoryboardScopeEnvelope = {
  novel_id: string;
  scope_key: string;
  document_id: string;
  branch_id: string | null;
  mode: 'local' | 'collaboration' | null;
};

/** `app/creative/storyboard.py::storyboard_receipt` 的契约字面量。 */
export const STORYBOARD_CONTRACT = 'studio-storyboard/1';
/** `StoryboardApproval.contract`。 */
export const STORYBOARD_APPROVAL_CONTRACT = 'studio-storyboard-approval/1';
/** `DirectorProposalService._current` 允许的分镜来源模式（`service.py::derive` 第 281 行）。 */
export const STORYBOARD_DERIVATION_SOURCES = ['SCREENPLAY', 'DIRECTOR'] as const;

export const STORYBOARD_WORKSPACE_BOUNDS = {
  /** `Identifier` 上限（`app/creative/models.py`）。 */
  identifier: 240,
  /** `CreativeShot.duration_seconds` 的 owner 边界（`Field(ge=1, le=600)`）。 */
  duration_seconds_min: 1,
  duration_seconds_max: 600,
  /** `StoryboardTimelineDraft.shot_ids` 上限 30；`timeline_draft` 总时长上限 600_000 ms。 */
  timeline_shots: 30,
  timeline_total_ms: 600_000,
  /** `ShotImageRequest.parameters` 里 `steps` 边界，用于"参考比较"的只读检查。 */
  steps_min: 1,
  steps_max: 150,
  seed_max: 2147483647,
  /** 一个镜头最多关联的绑定/版本条目数（呈现层，不会写回 owner）。 */
  overrides: 32,
  /** `creator` 声明的镜头/版本数量上限（`storyboard_receipt` 的 200）。 */
  shots: 200,
} as const;

/**
 * 本工作区自有机器码。`STUDIO_RESPONSE_INVALID` 是既有
 * `studioStoryboardContract.ts::storyboardInvalid` 的码，这里沿用而不另造。
 */
export const STORYBOARD_WORKSPACE_ERROR_CODES = {
  responseInvalid: 'STUDIO_RESPONSE_INVALID',
  readFailed: 'STUDIO_STORYBOARD_READ_FAILED',
  scopeMismatch: 'STUDIO_STORYBOARD_SCOPE_MISMATCH',
  orderLocalInvalid: 'STUDIO_STORYBOARD_ORDER_LOCAL_INVALID',
  reorderDraftInvalid: 'STUDIO_STORYBOARD_REORDER_DRAFT_INVALID',
  sendLocalInvalid: 'STUDIO_STORYBOARD_SEND_LOCAL_INVALID',
  /** 请求体在离开客户端前就被本地确定性地拒绝：不发往目标模块。 */
  targetNotDeclared: 'STUDIO_STORYBOARD_TARGET_NOT_DECLARED',
  goalLocalInvalid: 'STUDIO_STORYBOARD_GOAL_LOCAL_INVALID',
  proposalScopeMismatch: 'STUDIO_STORYBOARD_PROPOSAL_SCOPE_MISMATCH',
  authorityInvalid: 'CREATIVE_AUTHORITY_INVALID',
  authorityChanged: 'CREATIVE_AUTHORITY_CHANGED',
  storageLowSpace: 'CREATIVE_STORAGE_LOW_SPACE',
  storageUnavailable: 'CREATIVE_STORAGE_UNAVAILABLE',
} as const;

/** 507 存储准入码（原 owner 的 storage-admission）。 */
export const STORYBOARD_WORKSPACE_CAPACITY_CODES: readonly string[] = [
  STORYBOARD_WORKSPACE_ERROR_CODES.storageLowSpace,
  STORYBOARD_WORKSPACE_ERROR_CODES.storageUnavailable,
];

/**
 * 原 owner 抛出的、本工作区必须翻译成有界文案的码。分组只用来说明"这张卡要怎么读"，
 * 不改变 owner 自己何时抛哪个码。
 */
export const STORYBOARD_OWNER_STALE_CODES: readonly string[] = [
  'CREATIVE_STORYBOARD_APPROVAL_CHANGED',
  'CREATIVE_STORYBOARD_REVIEW_CHANGED',
  'CREATIVE_STORYBOARD_SHOT_CHANGED',
  'CREATIVE_STORYBOARD_IMAGE_BINDING_CHANGED',
  'CREATIVE_STORYBOARD_VIDEO_BINDING_CHANGED',
  'CREATIVE_STORYBOARD_VIDEO_SOURCE_CHANGED',
  'CREATIVE_STORYBOARD_VIDEO_SHOT_CHANGED',
  'CREATIVE_STORYBOARD_VIDEO_IMAGE_CHANGED',
  'CREATIVE_STORYBOARD_VIDEO_APPROVAL_REQUIRED',
  'CREATIVE_STORYBOARD_VIDEO_SOURCE_PIN_REQUIRED',
  'CREATIVE_STORYBOARD_VIDEO_ASSET_CHANGED',
  'CREATIVE_STORYBOARD_VIDEO_RESULT_CHANGED',
  'CREATIVE_STORYBOARD_VIDEO_BINDING_REVIEW_REQUIRED',
  'CREATIVE_STORYBOARD_GRAPH_APPROVAL_CHANGED',
  'CREATIVE_STORYBOARD_GRAPH_REVIEW_REQUIRED',
  'CREATIVE_STORYBOARD_TIMELINE_ORIGIN_CHANGED',
  'CREATIVE_STORYBOARD_TIMELINE_SHOT_CHANGED',
  'CREATIVE_STORYBOARD_CREATE_IDEMPOTENCY_CONFLICT',
  'CREATIVE_STORYBOARD_ADOPTION_IDEMPOTENCY_CONFLICT',
  'CREATIVE_SOURCE_DOCUMENT_CHANGED',
  'CREATIVE_SOURCE_DOCUMENT_UNAVAILABLE',
  'CREATIVE_PROPOSAL_SOURCE_CHANGED',
] as const;

/** 需要"本工作区不能代做"的码：原 owner 要求换一条恢复路径，这里只如实呈现。 */
export const STORYBOARD_OWNER_UNAVAILABLE_CODES: readonly string[] = [
  'CREATIVE_STORYBOARD_ASSET_OWNER_REQUIRED',
  'CREATIVE_STORYBOARD_TIMELINE_OWNER_REQUIRED',
  'CREATIVE_STORYBOARD_VIDEO_OWNER_REQUIRED',
  'CREATIVE_STORYBOARD_GRAPH_OWNER_REQUIRED',
  'CREATIVE_MODEL_RUNTIME_UNAVAILABLE',
  'CREATIVE_MODEL_LIVE_AUTHORITY_REQUIRED',
  'CREATIVE_PROPOSAL_NOT_REVIEWABLE',
] as const;

/**
 * 由 owner 事实推导出的本镜"下一步"可用动作。这不是权限授予，只是**呈现**：
 * 真正的放行仍由原 owner 与 `domain.read/write/review` 决定。
 */
export const SHOT_ACTIONS = [
  'REVIEW_APPROVAL',
  'COMPARE_REFERENCE',
  'PREPARE_IMAGE_DRAFT',
  'PREPARE_VIDEO_DRAFT',
  'PREPARE_TIMELINE_DRAFT',
  'DIRECTOR_ADVICE',
] as const;
export type ShotAction = typeof SHOT_ACTIONS[number];
export const SHOT_ACTION_LABELS: Readonly<Record<ShotAction, string>> = Object.freeze({
  REVIEW_APPROVAL: '核对并批准当前分镜版本',
  COMPARE_REFERENCE: '只读比较绑定素材与镜头版本',
  PREPARE_IMAGE_DRAFT: '准备图片请求草稿（不派发）',
  PREPARE_VIDEO_DRAFT: '准备视频请求草稿（不派发）',
  PREPARE_TIMELINE_DRAFT: '准备时间线底稿请求（不派发）',
  DIRECTOR_ADVICE: '只读读取导演调度建议',
});

/** 本工作区能形成的草稿目标。三者都是 DRAFT，永不执行。 */
export const SEND_TARGETS = ['IMAGE', 'VIDEO', 'TIMELINE'] as const;
export type SendTarget = typeof SEND_TARGETS[number];
export const SEND_TARGET_LABELS: Readonly<Record<SendTarget, string>> = Object.freeze({
  IMAGE: '图片候选', VIDEO: '视频候选', TIMELINE: '时间线底稿',
});

/** `SendToPanel` 唯一允许交给父级的载荷：精确到原版本，不含任何执行意图。 */
export type SendToDraft = {
  shot_id: string;
  shot_version: number;
  document_version: number;
  source_digest: string;
};

/** owner 声明的每条绑定里"会被引用"的确切原版本。 */
export type ShotImageBindingRef = { asset_id: string; version: number; digest: string };
export type ShotVideoBindingRef = {
  asset_id: string; version: number; digest: string;
  job: VideoJobPin;
  source_shot: { shot_id: string; shot_version: number; shot_digest: string };
};

/**
 * `sendToDraft` 的完整结果：`target/document_version/shot_id/shot_version/source_digest`
 * 是冻结契约要求的字段，`bindings` 只是把它们**已经存在**的原版本摊开给人看。
 * 没有 `dispatch`、没有 `request_id`、没有队列：这里无法执行任何东西。
 *
 * `document_version` 在纯函数里是 `null`：草稿在形成时还不知道、也绝不允许猜
 * 一个文档版本。用已核对的原回执 `bindDraftToReceipt` 补上它之后才是可提交的形状。
 */
export type ShotTargetDraft = {
  target: SendTarget;
  document_version: number | null;
  shot_id: string;
  shot_version: number;
  source_digest: string;
  bindings: { IMAGE: ShotImageBindingRef | null; VIDEO: ShotVideoBindingRef | null };
  /** `TIMELINE` 会让原片段按显示顺序排列；这是 owner `timeline_draft` 的实际行为。 */
  order_shot_ids: string[];
};

/** 已经用原回执核对过文档版本的草稿；只有这个形状能交给父级。 */
export type BoundShotTargetDraft = Omit<ShotTargetDraft, 'document_version'> & { document_version: number };

export type SourceStalenessKind =
  | 'DIRECTOR_SOURCE_CHANGED'
  | 'DIRECTOR_SOURCE_UNAVAILABLE'
  | 'CANDIDATE_SOURCE_SHOT_CHANGED'
  | 'BINDING_NOT_CURRENT';

export type ShotStalenessNote = {
  kind: SourceStalenessKind;
  detail: string;
  /** 只有能指出确切原版本时才给出。 */
  expected: { id: string; version: number; digest: string } | null;
  actual: { id: string; version: number; digest: string } | null;
};

/** 视图只读这张卡：owner 没有的字段一律是显式的 `null` 或空数组。 */
export type ShotSummary = {
  shot_id: string;
  /** 显示序号。重排会改变它，**不会**改变 `shot_id`。 */
  number: number;
  scene_id: string;
  subject: string | null;
  duration: { seconds: number; source: 'SHOT' } | null;
  framing: { shot_size: string | null; camera_angle: string | null; camera_motion: string | null; lens: string | null; composition: string | null };
  lighting_color: { lighting: string | null; color: string | null; environment: string | null };
  references: {
    characters: string[];
    director_note_ids: string[];
    continuity: { previous_shot_id: string | null; next_shot_id: string | null; fidelity: string[] } | null;
  };
  candidate: { kind: 'IMAGE' | 'VIDEO'; ref: ShotImageBindingRef | ShotVideoBindingRef } | null;
  audio: { sound_effect: string | null; sound: string | null } | null;
  staleness: ShotStalenessNote[];
  next_actions: ShotAction[];
  /** 每个字段的来源，便于"不发明值"这条要求在界面上可核对。 */
  evidence: { fields: string[]; absent: string[] };
};

export type DirectorGoalKind = 'SCENE' | 'SHOT_ALIGNED';

/**
 * 导演目标（只读投影）。`adopted` 是原文档里已经确定的值，`suggested` 是
 * 待审建议；后者永远不会被当成前者渲染（`proposals.py` 的
 * `status: NEEDS_REVIEW` + `quality_verification: HUMAN_REVIEW_REQUIRED`）。
 */
export type DirectorGoal = {
  kind: DirectorGoalKind;
  scene_id: string;
  note_id: string;
  number: number;
  /** 以 `SCREENPLAY/DIRECTOR` 文档为来源时的原版本；没有来源就是 `null`。 */
  source_document: { id: string; version: number; digest: string } | null;
  adopted: {
    note: string; shot_size: string; camera_angle: string; camera_motion: string;
    duration_seconds: number; emotion: string; pacing: string; performance: string; blocking: string;
  };
  /** 建议区：`DirectorProposal` 的 `status` 不为 `APPROVED` 时只读展示。 */
  suggestion: {
    id: string; status: DirectorProposalStatus; output_digest: string | null;
    quality_verification: 'HUMAN_REVIEW_REQUIRED' | null;
    model_called: boolean;
    visual_target: DirectorVisualTargetValue | null;
    notes: DirectorNote[];
  } | null;
};

export type DirectorVisualTargetValue = {
  style: string; atmosphere: string; color: string; rhythm: string; reference_works: string[];
};

export const DIRECTOR_PROPOSAL_STATUSES = ['NEEDS_REVIEW', 'APPROVED', 'CANCELLED', 'MODEL_UNAVAILABLE'] as const;
export type DirectorProposalStatus = typeof DIRECTOR_PROPOSAL_STATUSES[number];

/** 编辑器里的可编辑目标（本地草稿）。它不会自己变成原文档。 */
export type DirectorGoalDraft = {
  scene_id: string;
  note_id: string;
  shot_size: string;
  camera_angle: string;
  camera_motion: string;
  duration_seconds: string;
  emotion: string;
  pacing: string;
  performance: string;
};

export const DIRECTOR_OVERRIDE_FIELDS = [
  'shot_size', 'camera_angle', 'camera_motion', 'lens', 'composition', 'frame_prompt',
  'lighting', 'color', 'duration_seconds', 'emotion', 'pacing', 'performance',
] as const;
export type DirectorOverrideField = typeof DIRECTOR_OVERRIDE_FIELDS[number];

export type DirectorFieldResolution = {
  field: DirectorOverrideField;
  /** 镜头文档当前值。 */
  shot_value: string | number | null;
  /** 从镜头已链接的导演备注继承到的值；没有继承依据就是 `null`。 */
  inherited_value: string | number | null;
  /** 真正生效的那一侧。 */
  effective: 'SHOT_OVERRIDE' | 'DIRECTOR_INHERITED' | 'ABSENT';
  /** 生效值是否与继承值不同（即镜头级覆写赢了）。 */
  overridden: boolean;
};

export type DirectorVsShotResolution = {
  shot_id: string;
  scene_id: string;
  /** 提供继承依据的导演备注 id；没有就是空数组。 */
  inherited_from_note_ids: string[];
  director_document: { id: string; version: number; digest: string } | null;
  fields: DirectorFieldResolution[];
  /** 明确写出结论：修改导演目标不会改写已批准的下游结果。 */
  downstream: 'DIRECTOR_GOAL_EDIT_DOES_NOT_OVERWRITE_APPROVED_RESULTS';
};

/** 显示顺序草稿。`saved: false` 时视图必须说明"尚未保存到原文档"。 */
export type ShotOrderDraft = {
  shot_ids: string[];
  saved: boolean;
  /** 被重排改变了显示序号的镜头（身份不变）。 */
  renumbered: string[];
  /** owner 的既有约束会让重排撤销批准、丢弃不一致绑定。 */
  approval_effect: 'REVOKES_APPROVAL_AND_DROPS_MISMATCHED_BINDINGS';
  invalidated_bindings: string[];
};

export type StoryboardShotRow = {
  shot: StoryboardShot;
  summary: ShotSummary;
  staleness: ShotStalenessNote[];
};

export type StoryboardSurfaceState = 'IDLE' | 'LOADING' | 'READY' | 'EMPTY' | 'DENIED' | 'FAILED';
export type StoryboardProblem = { code: string; message: string };

/** 本工作区只声明读与"形成草稿"；没有执行、没有派发、没有队列。 */
export type StoryboardWorkspaceClient = {
  readStoryboard: (documentId: string, signal?: AbortSignal) => Promise<StoryboardReceipt>;
  readDirectorAdvice: (documentId: string, signal?: AbortSignal) => Promise<DirectorAdvice>;
};
