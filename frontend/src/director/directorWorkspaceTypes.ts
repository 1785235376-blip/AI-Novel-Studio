import type { DirectorCameraEvidence } from './directorCameraEvidence';
/**
 * Phase14-A 导演工作台 — 表示层类型与冻结词表。
 *
 * 这里没有第二个导演/镜头/场景/资产模型：所有事实都来自既有 owner
 * （`DirectorVisualTarget`、`ShotCard`、`ShotContinuity`、`camera_language`），
 * 经后端只读投影 `studio-director-workspace/1` 暴露。本文件只声明呈现层类型，
 * 并冻结"必须显示的字段"，让视图无法漏掉一个必填维度。
 *
 * 两条规则写进类型里：
 *  - **测量不等于已authoring**：`camera_language` / `lighting` /
 *    `performance_direction` 没有文档级归属，只能是 `PER_SHOT_MEASURED`，
 *    并且 `authored` 恒为 `false`。界面不得把它渲染成"导演已决定的文档值"。
 *  - **提示不是修改**：连续性面板只有 `WARNING`，没有写入口。
 */

/** `app/creative/director_intent.py` 的契约字面量。 */
export const DIRECTOR_WORKSPACE_CONTRACT = 'studio-director-workspace/1';
export const DIRECTOR_INTENT_CONTRACT = 'studio-director-intent/1';
export const SHOT_CARD_CONTRACT = 'studio-shot-card/1';
export const CONTINUITY_PANEL_CONTRACT = 'studio-continuity-panel/1';
export const DIRECTOR_WORKSPACE_SCHEMA_VERSION = 1;

/**
 * 本工作区机器码。`STUDIO_RESPONSE_INVALID` 沿用既有分镜工作区的码，
 * 不另造一个（house style：契约解码失败只有一个码）。
 */
export const DIRECTOR_WORKSPACE_ERROR_CODES = {
  responseInvalid: 'STUDIO_RESPONSE_INVALID',
  readFailed: 'STUDIO_DIRECTOR_WORKSPACE_READ_FAILED',
  scopeMismatch: 'STUDIO_DIRECTOR_WORKSPACE_SCOPE_MISMATCH',
  documentRequired: 'STUDIO_DIRECTOR_WORKSPACE_DOCUMENT_REQUIRED',
} as const;

/** 后端 `Identifier` 上限（`app/creative/models.py`）。 */
export const DIRECTOR_WORKSPACE_BOUNDS = { identifier: 240, text: 4000, members: 64 } as const;

/** 必须显示的七个导演意图维度（顺序即显示顺序）。 */
export const DIRECTOR_INTENT_FIELDS = [
  'visual_goal', 'mood', 'genre', 'camera_language', 'lighting', 'color_direction', 'performance_direction',
] as const;
export type DirectorIntentField = typeof DIRECTOR_INTENT_FIELDS[number];

/** 必须显示的十一个镜头卡字段（顺序即显示顺序）。 */
export const SHOT_CARD_FIELDS = [
  'shot_id', 'duration', 'camera', 'lens', 'movement', 'composition',
  'lighting', 'character', 'action', 'emotion', 'audio',
] as const;
export type ShotCardField = typeof SHOT_CARD_FIELDS[number];

/** 必须检查的五个连续性维度。 */
export const CONTINUITY_DIMENSIONS = ['characters', 'outfit', 'environment', 'time', 'lighting'] as const;
export type ContinuityDimensionField = typeof CONTINUITY_DIMENSIONS[number];

export const DOCUMENT_AUTHORED = 'DOCUMENT_AUTHORED';
export const PER_SHOT_MEASURED = 'PER_SHOT_MEASURED';

export type AuthoredScope = 'DOCUMENT' | 'PER_SHOT';
export type ShotValueCode = 'CANONICAL' | 'LEGACY_PASSTHROUGH' | 'EMPTY';

export type DirectorIntentRecord = {
  field: DirectorIntentField;
  label: string;
  kind: typeof DOCUMENT_AUTHORED | typeof PER_SHOT_MEASURED;
  authored_scope: AuthoredScope;
  value: string;
  authored: boolean;
  source: string;
  owner: string;
  detail?: { rhythm: string; reference_works: string[] };
  usage: CameraLanguageUsage | SimpleUsage | null;
};

export type CameraVocabulary = {
  members: string[];
  aliases: Record<string, string>;
  /** 别名键是 `normalise` 实际匹配的折叠形式（大写、分隔符归一）。 */
  alias_keys_are_folded: true;
};

export type CameraLanguageUsage = {
  measured_over_rows: number;
  dimensions: Record<string, {
    rows: number;
    authored_rows: number;
    values: { value: string; code: ShotValueCode; count: number }[];
  }>;
  authored_values: number;
  canonical_values: number;
  /** 非规范写法原样保留，绝不折算——这是向后兼容的可核对证据。 */
  legacy_values_preserved: string[];
  canonical_ratio: number;
  vocabulary: Record<string, CameraVocabulary>;
};

export type SimpleUsage = {
  measured_over_rows: number;
  authored_rows: number;
  unauthored_rows: number;
  dimensions: Record<string, {
    rows: number;
    authored_rows: number;
    values: { value: string; count: number }[];
  }>;
};

export type ShotValue = { field: string; value: string; authored: boolean; source: string; owner: string };
export type ClassifiedShotValue = ShotValue & { code: ShotValueCode };

export type ShotCardProjection = {
  contract: string;
  shot_id: string;
  number: number | null;
  scene_id: string;
  duration: { seconds: number | null; authored: boolean };
  camera: { shot_size: string; camera_motion: string; lens: string; composition: string; angle: string };
  camera_classification: Record<string, ShotValueCode>;
  camera_canonical_ratio: number;
  lens: ClassifiedShotValue;
  movement: ClassifiedShotValue;
  composition: ClassifiedShotValue;
  lighting: ShotValue;
  character: { field: string; values: string[]; authored: boolean; source: string; owner: string };
  action: ShotValue;
  emotion: ShotValue;
  audio: {
    field: string; sound: string; sound_effect: string;
    dialogue: { speaker: string; text: string; delivery: string }[];
    authored: boolean; source: string; owner: string;
  };
  director_note_ids: string[];
};

export type ContinuityDimension = {
  field: ContinuityDimensionField;
  label: string;
  code: string;
  sources: string[];
  compared_pairs: number;
  unknown_pairs: number;
};

export type ContinuityWarning = {
  code: string;
  field: string;
  label: string;
  severity: 'WARNING';
  previous_shot_id: string;
  next_shot_id: string;
  previous: string;
  next: string;
};

export type ContinuityPanel = {
  contract: string;
  schema_version: number;
  warning_only: true;
  auto_modify: false;
  required_dimensions: ContinuityDimensionField[];
  dimensions: ContinuityDimension[];
  excluded: { field: string; reason: string }[];
  shot_count: number;
  compared_pairs: number;
  warnings: ContinuityWarning[];
};

export type DirectorIntentProjection = {
  contract: string;
  schema_version: number;
  advisory_only: true;
  auto_modify: false;
  measured_over: 'SHOTS' | 'DIRECTOR_NOTES' | 'NONE';
  required_fields: DirectorIntentField[];
  fields: DirectorIntentRecord[];
  dimensions: Record<DirectorIntentField, DirectorIntentRecord>;
};

export type DirectorWorkspaceProjection = {
  contract: string;
  schema_version: number;
  advisory_only: true;
  execution_authority: false;
  auto_modify: false;
  project_id: string;
  scope: Record<string, string>;
  generated_at: string;
  /** 项目自己已有的题材：继承来的上下文，不是导演 authoring 的值。 */
  project_context: { title: string; genre: string; inherited_not_authored: true };
  document: { id: string; version: number; mode: string; title: string; status: string };
  required_shot_card_fields: ShotCardField[];
  director_intent: DirectorIntentProjection;
  shot_cards: ShotCardProjection[];
  continuity: ContinuityPanel;
  camera_geometry?: DirectorCameraEvidence;
};

export type DirectorWorkspaceSurfaceState = 'IDLE' | 'LOADING' | 'READY' | 'EMPTY' | 'DENIED' | 'FAILED';
export type DirectorWorkspaceProblem = { code: string; message: string };

/** 本工作区只读：没有写入口，也没有派发入口。 */
export type DirectorWorkspaceClient = {
  readDirectorWorkspace: (documentId: string, signal?: AbortSignal) => Promise<DirectorWorkspaceProjection>;
};
