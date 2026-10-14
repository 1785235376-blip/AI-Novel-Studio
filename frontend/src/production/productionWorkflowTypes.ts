/**
 * Phase 7 unified production workflow projection (contract `studio-production-workflow/1`).
 *
 * The projection is advisory: it reads the original Director / Storyboard / Image /
 * Video / Audio / Timeline / Asset owners and never becomes a second execution owner.
 * The frozen literals below mirror `app/creative/production_workflow*.py` so the UI
 * cannot drift from the owner's declared vocabulary.
 */

export const PRODUCTION_WORKFLOW_SCHEMA_VERSION = 1;
export const PRODUCTION_WORKFLOW_CONTRACT = 'studio-production-workflow/1';

/** Fixed integration order. The projection always returns exactly these seven modules. */
export const PRODUCTION_WORKFLOW_MODULES = ['director', 'storyboard', 'image', 'video', 'audio', 'timeline', 'asset'] as const;
export type ProductionWorkflowModuleId = typeof PRODUCTION_WORKFLOW_MODULES[number];
export const PRODUCTION_WORKFLOW_MODULE_LABELS: Record<ProductionWorkflowModuleId, string> = {
  director: '导演', storyboard: '分镜', image: '图像', video: '视频', audio: '音频', timeline: '时间线', asset: '资产',
};
export const PRODUCTION_WORKFLOW_STAGES_TOTAL = PRODUCTION_WORKFLOW_MODULES.length;

export const PRODUCTION_WORKFLOW_STATUSES = ['NOT_STARTED', 'PLANNED', 'IN_PRODUCTION', 'REVIEW_PENDING', 'REVIEWED'] as const;
export type ProductionWorkflowStatus = typeof PRODUCTION_WORKFLOW_STATUSES[number];
export const PRODUCTION_WORKFLOW_STATUS_LABELS: Record<ProductionWorkflowStatus, string> = {
  NOT_STARTED: '未开始', PLANNED: '已规划', IN_PRODUCTION: '制作中', REVIEW_PENDING: '待审核', REVIEWED: '已审核',
};
export const PRODUCTION_WORKFLOW_STATUS_TONES: Record<ProductionWorkflowStatus, 'neutral' | 'info' | 'warning' | 'success'> = {
  NOT_STARTED: 'neutral', PLANNED: 'info', IN_PRODUCTION: 'info', REVIEW_PENDING: 'warning', REVIEWED: 'success',
};

export const PRODUCTION_WORKFLOW_START_STATES = ['NOT_STARTED', 'READY', 'STARTED'] as const;
export type ProductionWorkflowStartState = typeof PRODUCTION_WORKFLOW_START_STATES[number];
export const PRODUCTION_WORKFLOW_START_STATE_LABELS: Record<ProductionWorkflowStartState, string> = {
  NOT_STARTED: '尚未开始', READY: '可能已开始', STARTED: '独立项目已开始',
};

export const PRODUCTION_WORKFLOW_ASSET_KINDS = ['image', 'audio', 'video', 'text', 'other'] as const;
export type ProductionWorkflowAssetKind = typeof PRODUCTION_WORKFLOW_ASSET_KINDS[number];
export const PRODUCTION_WORKFLOW_ASSET_KIND_LABELS: Record<ProductionWorkflowAssetKind, string> = {
  image: '图片', audio: '音频', video: '视频', text: '文本', other: '其他',
};

/** The original preference owner's own creation presets. A preset is a presentation hint, never a grant. */
export const PRODUCTION_WORKFLOW_PRESETS = ['BLANK', 'TEXT', 'IMAGE', 'VIDEO', 'AUDIO', 'EDITING', 'MIXED'] as const;
export type ProductionWorkflowPreset = typeof PRODUCTION_WORKFLOW_PRESETS[number];

/** The original owner stores at most this many saved intents (`WorkspacePreferences.intents`). */
export const PRODUCTION_WORKFLOW_INTENT_LIMIT = 11;

/** The frozen start action of the original project owner. This view never dispatches it. */
export const PRODUCTION_WORKFLOW_START_ACTION = {
  method: 'POST', path: '/api/experimental/projects', requires_original_host_session: true,
} as const;

/** The original owner's identifier grammar for one saved intent (`^[a-z][a-z0-9_]{0,63}$`). */
export const PRODUCTION_WORKFLOW_INTENT_ID = /^[a-z][a-z0-9_]{0,63}$/;

export const PRODUCTION_WORKFLOW_BOUNDS = {
  project_id: 240, label: 120, owner: 120, next_action: 500, blocked_reason: 300, blocked_reasons: 16,
  preset: 32, incarnation: 120, timestamp: 64, intent_id: 64,
} as const;

export const PRODUCTION_WORKFLOW_ERROR_CODES = {
  responseInvalid: 'PRODUCTION_WORKFLOW_RESPONSE_INVALID',
  scopeMismatch: 'PRODUCTION_WORKFLOW_SCOPE_MISMATCH',
  readFailed: 'PRODUCTION_WORKFLOW_READ_FAILED',
  localInvalid: 'PRODUCTION_WORKFLOW_INTENT_LOCAL_INVALID',
  conflict: 'PRODUCTION_WORKFLOW_INTENT_CONFLICT',
  invalid: 'PRODUCTION_WORKFLOW_INTENT_INVALID',
  authorityInvalid: 'CREATIVE_AUTHORITY_INVALID',
  authorityChanged: 'CREATIVE_AUTHORITY_CHANGED',
  storageLowSpace: 'CREATIVE_STORAGE_LOW_SPACE',
  storageUnavailable: 'CREATIVE_STORAGE_UNAVAILABLE',
} as const;

/** 507 capacity codes raised by the original storage-admission owner. */
export const PRODUCTION_WORKFLOW_CAPACITY_CODES: readonly string[] = [
  PRODUCTION_WORKFLOW_ERROR_CODES.storageLowSpace, PRODUCTION_WORKFLOW_ERROR_CODES.storageUnavailable,
];

export type ProductionWorkflowScope = {
  mode: 'local' | 'collaboration'; novel_id: string;
  workspace_id?: string | null; project_id?: string | null; storyline_id?: string | null; branch_id?: string | null;
};
export type ProductionWorkflowStartAction = {
  method: 'POST'; path: string; requires_original_host_session: true;
};
export type ProductionWorkflowProjectStart = {
  state: ProductionWorkflowStartState; entry_kind: 'NEUTRAL_STUDIO'; incarnation: string | null;
  has_creative_documents: boolean; start_action: ProductionWorkflowStartAction;
};
export type ProductionWorkflowIntentValue = {
  intent_id: string; label: string; selected: boolean; custom: boolean;
};
export type ProductionWorkflowIntent = {
  version: number;
  /** Absent on the wire normalizes to `null`: nothing is invented about the saved preset. */
  preset: ProductionWorkflowPreset | null;
  values: ProductionWorkflowIntentValue[];
  editable: true; history_retained: true;
};
export type ProductionWorkflowModule = {
  id: ProductionWorkflowModuleId; label: string; status: ProductionWorkflowStatus;
  document_count: number; asset_count: number; job_count: number;
  blocked_reasons: string[]; owner: string; next_action: string | null;
};
export type ProductionWorkflowAssetOverview = {
  total: number; by_kind: Record<ProductionWorkflowAssetKind, number>;
  private_pending_review: number; reviewed: number;
};
export type ProductionWorkflowDashboard = {
  stages_total: 7; stages_started: number; stages_reviewed: number; open_reviews: number;
  blocked_stages: ProductionWorkflowModuleId[];
};
export type ProductionWorkflowProjection = {
  schema_version: 1; contract: 'studio-production-workflow/1'; project_id: string; scope: ProductionWorkflowScope;
  advisory_only: true; execution_authority: false; generated_at: string; project_start: ProductionWorkflowProjectStart;
  creative_intent: ProductionWorkflowIntent; modules: ProductionWorkflowModule[];
  asset_overview: ProductionWorkflowAssetOverview; dashboard: ProductionWorkflowDashboard;
};

/** One explicit, lossless replacement of the saved intent set. `preset` is optional by design. */
export type ProductionWorkflowIntentValueInput = { intent_id: string; label: string; selected: boolean };
export type ProductionWorkflowIntentDraft = {
  expected_version: number | null; values: ProductionWorkflowIntentValueInput[];
  preset?: ProductionWorkflowPreset | null;
};

/** Data-surface states only; the original owners keep every execution state transition. */
export type ProductionWorkflowSurfaceState = 'IDLE' | 'LOADING' | 'READY' | 'ERROR' | 'UNAVAILABLE' | 'DENIED';
export type ProductionWorkflowProblem = { code: string; message: string };

/** Exactly one read and one versioned intent write. Nothing here can start a job or a model. */
export type ProductionWorkflowClient = {
  read: (signal?: AbortSignal) => Promise<ProductionWorkflowProjection>;
  updateIntent: (input: ProductionWorkflowIntentDraft, signal?: AbortSignal) => Promise<ProductionWorkflowIntent>;
};
