/**
 * UX-01 project entry / creative intent / novice-professional mode: types + frozen literals.
 *
 * The intent vocabulary and its Chinese labels already belong to two existing owners:
 * `STUDIO_INTENTS` (`frontend/src/creative/studioWorkspacePreferences.ts`, the saved
 * preference catalog) and `PRODUCTION_WORKFLOW_*` (`frontend/src/production/...`, the
 * Phase 7 projection contract). Nothing is copied here: the identifiers are derived
 * from the existing label catalog and the request/response literals are re-exported,
 * so a second catalog can never drift from the owner's declared value set.
 *
 * Intent is a presentation hint. It is never a permission, never restricts a module and
 * never triggers generation.
 */
import { STUDIO_INTENTS } from '../creative/studioWorkspacePreferences';
import {
  PRODUCTION_WORKFLOW_BOUNDS, PRODUCTION_WORKFLOW_ERROR_CODES, PRODUCTION_WORKFLOW_INTENT_ID,
  PRODUCTION_WORKFLOW_INTENT_LIMIT, PRODUCTION_WORKFLOW_MODULES, PRODUCTION_WORKFLOW_MODULE_LABELS,
  PRODUCTION_WORKFLOW_PRESETS,
  type ProductionWorkflowIntentValueInput, type ProductionWorkflowModuleId, type ProductionWorkflowPreset,
} from '../production/productionWorkflowTypes';

export {
  PRODUCTION_WORKFLOW_BOUNDS, PRODUCTION_WORKFLOW_ERROR_CODES, PRODUCTION_WORKFLOW_INTENT_ID,
  PRODUCTION_WORKFLOW_INTENT_LIMIT, PRODUCTION_WORKFLOW_MODULES, PRODUCTION_WORKFLOW_MODULE_LABELS,
  PRODUCTION_WORKFLOW_PRESETS,
};
export type { ProductionWorkflowIntentValueInput, ProductionWorkflowModuleId, ProductionWorkflowPreset };

/** House style: a contract singleton of frozen literals instead of loose string tests. */
export const STUDIO_ENTRY_CONTRACT = {
  schema_version: 1,
  contract: 'studio-project-entry/1',
  modes: ['NOVICE', 'PROFESSIONAL'],
  states: ['idle', 'loading', 'ready', 'empty', 'missing', 'denied', 'failed'],
  kinds: ['blank', 'intent'],
  /** The original owner's own routes. This view never dispatches the start action itself. */
  paths: {
    projects: '/api/novels',
    blank_project: '/api/experimental/projects',
    preferences: (projectId: string) => `/api/projects/${encodeURIComponent(projectId)}/studio/preferences`,
  },
  bounds: { title: 200, project_id: 240, label: 120, entry_kind: 32, timestamp: 64, genre: 120, status: 64 },
  notices: {
    intent_scope: '创作意图只影响推荐布局与提示，不是权限：它不会限制可用模块，不会改变项目、素材或任务数据，也不会触发任何生成。',
    mode_scope: '新手模式与专业模式共用同一份项目、素材、任务与图谱数据；切换只改变界面呈现，不会转换、复制或删除任何内容。',
    manual_scope: '没有模型或网络时，手动编辑、导入、素材管理与既有素材的编辑始终可用。',
    adopt_scope: '采用推荐方案只写入创作偏好，不执行任何生成、排队或素材变更。',
  },
  messages: {
    response_invalid: '项目入口数据不可用，请重新读取。',
    scope_mismatch: '返回的项目与当前入口请求不一致，请重新打开。',
    read_failed: '项目入口读取失败，请稍后重新核对。',
    project_missing: '这个项目编号已不可用：它可能已被删除，或当前身份无权访问。请选择其他项目，入口不会自动创建一个替代项目。',
    denied: '当前会话无权读取项目入口。请重新核对身份与项目范围。',
    empty: '还没有任何项目。可以空白开始，或按创作意图开始。',
    save_failed: '创作意图保存结果未确认，当前输入仍保留。',
    create_failed: '项目未创建，请核对名称与连接状态后重试。',
    conflict_reread: '服务端创作意图已更新，你的选择仍保留；已重新读取最新版本，请核对后重新提交。',
    custom_incomplete: '自定义创作意图需要 1–120 个字符的名称。',
    skipped: '已跳过创作意图设置；之后可随时在项目入口或工作台中重新设置。',
    adopted: '推荐方案已写入创作偏好；没有生成任何内容。',
  },
} as const;

export const STUDIO_ENTRY_ERROR_CODES = {
  responseInvalid: 'STUDIO_ENTRY_RESPONSE_INVALID',
  scopeMismatch: 'STUDIO_ENTRY_SCOPE_MISMATCH',
  readFailed: 'STUDIO_ENTRY_READ_FAILED',
  projectMissing: 'STUDIO_ENTRY_PROJECT_MISSING',
  localInvalid: 'STUDIO_ENTRY_INTENT_LOCAL_INVALID',
  conflict: PRODUCTION_WORKFLOW_ERROR_CODES.conflict,
  invalid: PRODUCTION_WORKFLOW_ERROR_CODES.invalid,
  authorityInvalid: PRODUCTION_WORKFLOW_ERROR_CODES.authorityInvalid,
  authorityChanged: PRODUCTION_WORKFLOW_ERROR_CODES.authorityChanged,
} as const;

/** Presentation only. The workspace's own view-location owner persists this; nothing here writes storage. */
export const STUDIO_INTERFACE_MODES = STUDIO_ENTRY_CONTRACT.modes;
export type StudioInterfaceMode = typeof STUDIO_INTERFACE_MODES[number];
export const STUDIO_INTERFACE_MODE_LABELS: Record<StudioInterfaceMode, string> = {
  NOVICE: '新手模式', PROFESSIONAL: '专业模式',
};

export const STUDIO_ENTRY_STATES = STUDIO_ENTRY_CONTRACT.states;
export type StudioEntryState = typeof STUDIO_ENTRY_STATES[number];
export type StudioEntryKind = 'blank' | 'intent';

/** One intent entry of the entry projection. `custom` is the owner's own marker for the free-text entry. */
export type StudioIntentValue = {
  intent_id: string; label: string; selected: boolean; custom: boolean;
};

/**
 * The canonical intent vocabulary: the existing label catalog plus the owner's identifier
 * grammar (the Phase 7 wire form is the lower-case literal). The label is read from
 * `STUDIO_INTENTS`; only the derived identifier is added, and it is checked against the
 * owner's frozen grammar so a drift fails loudly instead of silently.
 */
export type StudioIntentDefinition = { intent_id: string; label: string; custom: boolean };
export const STUDIO_INTENT_CATALOG: readonly StudioIntentDefinition[] = Object.freeze(STUDIO_INTENTS.map(([id, label]) => {
  const intent_id = id.toLowerCase();
  if (!PRODUCTION_WORKFLOW_INTENT_ID.test(intent_id)) {
    throw new Error(`STUDIO_INTENT_IDENTIFIER_INVALID:${id}`);
  }
  return Object.freeze({ intent_id, label, custom: id === 'CUSTOM' });
}));
export const STUDIO_INTENT_CUSTOM_ID = 'custom';
export const STUDIO_INTENT_IDS: readonly string[] = Object.freeze(STUDIO_INTENT_CATALOG.map(entry => entry.intent_id));
export const STUDIO_INTENT_LABELS: Readonly<Record<string, string>> = Object.freeze(Object.fromEntries(
  STUDIO_INTENT_CATALOG.map(entry => [entry.intent_id, entry.label]),
));
/** The owner stores at most this many saved intents. Re-exported, never re-declared. */
export const STUDIO_INTENT_STORAGE_LIMIT = PRODUCTION_WORKFLOW_INTENT_LIMIT;

/** One row of `GET /api/novels`. `updated_at` mirrors the owner's `updated` stamp when it is present. */
export type StudioEntryProject = {
  id: string; title: string;
  updated_at: string | null; entry_kind: string | null;
  genre: string | null; status: string | null;
};

/** The entry projection of the saved intent: the Phase 7 `creative_intent` shape, read from the preference owner. */
export type StudioEntryIntent = {
  version: number; preset: ProductionWorkflowPreset | null; values: StudioIntentValue[];
  editable: true; history_retained: true;
};
/** One lossless replacement of the saved intent set (no `note`, no free-form extra key). */
export type StudioIntentDraft = {
  expected_version: number; values: ProductionWorkflowIntentValueInput[];
  preset?: ProductionWorkflowPreset | null;
};
export type StudioEntryProblem = { code: string; message: string };
export type StudioProjectCreation = {
  id: string; title: string; studio_ready: boolean | null; requires_scope_selection: boolean | null;
};

/**
 * Exactly one project list, one blank-project creation and one versioned intent read/replacement.
 * Nothing in this seam starts a model, a job or a generation.
 */
export type StudioEntryClient = {
  listProjects: (signal?: AbortSignal) => Promise<StudioEntryProject[]>;
  createBlankProject: (input: { title: string; id?: string }, signal?: AbortSignal) => Promise<StudioProjectCreation>;
  readIntent: (projectId: string, signal?: AbortSignal) => Promise<StudioEntryIntent>;
  saveIntent: (projectId: string, draft: StudioIntentDraft, signal?: AbortSignal) => Promise<StudioEntryIntent>;
};

/** One deterministic recommendation. Adopting it writes the preference only. */
export type StudioSuggestionPlan = {
  plan_id: string;
  title: string;
  intent_ids: string[];
  layout: string;
  modules: ProductionWorkflowModuleId[];
  nodes: string[];
  preset: ProductionWorkflowPreset;
  note: string;
};

/** The controller contract every entry view consumes: the return type of `useStudioEntry()`. */
export type { StudioEntryController } from './useStudioEntry';
