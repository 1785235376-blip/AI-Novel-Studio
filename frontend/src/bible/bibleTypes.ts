/**
 * Round2-B 角色与场景圣经 — 表示层类型与冻结词表。
 *
 * 本工作面**只展示 projection**：没有第二个角色/场景/资产系统，也没有任何写入口。
 * 所有事实来自既有 owner（`characters`/`locations` 记录、`WorldService` 语义记录、
 * 既有资产索引、既有创作文档），经 `GET /api/projects/{nid}/studio/bible` 暴露。
 *
 * 三条真实性规则写进类型与解码器，而不是写在注释里：
 *  - `UNKNOWN` 是**状态**，不是一个空白字符串；
 *  - `DRAFT` 不是 canon，只有 `APPROVED` 才是；
 *  - 未在资产索引中出现的引用是 `UNRESOLVED`，绝不猜测。
 */

/** `app/creative/bible_projection.py` 的契约字面量。 */
export const BIBLE_CONTRACT = 'studio-bible/1';
export const CHARACTER_BIBLE_CONTRACT = 'studio-character-bible/1';
export const SCENE_BIBLE_CONTRACT = 'studio-scene-bible/1';
export const BIBLE_SCHEMA_VERSION = 1;

/** 后端未作者化时使用的**字面量值**。界面必须原样显示它，而不是留空。 */
export const UNKNOWN = 'UNKNOWN';

export const BIBLE_ERROR_CODES = {
  responseInvalid: 'STUDIO_RESPONSE_INVALID',
  readFailed: 'STUDIO_BIBLE_READ_FAILED',
  scopeMismatch: 'STUDIO_BIBLE_SCOPE_MISMATCH',
} as const;

export const BIBLE_BOUNDS = { identifier: 240, text: 8000, assets: 200, usage: 500 } as const;

/** 六个必填角色圣经维度（顺序即显示顺序）。 */
export const CHARACTER_BIBLE_FIELDS = [
  'identity', 'appearance', 'clothing', 'reference', 'behavior', 'relationship',
] as const;
export type CharacterBibleField = typeof CHARACTER_BIBLE_FIELDS[number];

/** 七个必填场景圣经维度（顺序即显示顺序）。 */
export const SCENE_BIBLE_FIELDS = [
  'location', 'architecture', 'material', 'lighting', 'weather', 'time', 'mood',
] as const;
export type SceneBibleField = typeof SCENE_BIBLE_FIELDS[number];

/**
 * 每个维度的**允许键集合**，逐个字段冻结。
 * 解码器据此拒绝未知键：后端多出或少掉一个键都会明确失败，而不是安静地少显示一行。
 */
export const DIMENSION_BASE_KEYS = ['field', 'label', 'source', 'value', 'authored', 'state'] as const;
export const VISUAL_DIMENSION_EXTRA_KEYS = ['authoritative', 'record_status'] as const;
export const REFERENCE_DIMENSION_EXTRA_KEYS = ['references', 'unresolved_references', 'verification'] as const;
export const RELATIONSHIP_DIMENSION_EXTRA_KEYS = ['relationships'] as const;
export const GEOGRAPHY_DIMENSION_EXTRA_KEYS = ['geography_records'] as const;

/** 由 `CharacterVisualData` / `SceneVisualData` 承载的维度。 */
export const VISUAL_FIELDS: readonly string[] = [
  'appearance', 'clothing', 'architecture', 'material', 'lighting', 'weather', 'time', 'mood',
];

export type DimensionState = 'AUTHORED' | typeof UNKNOWN;
export type ReferenceResolution = 'RESOLVED' | 'UNRESOLVED';
export type ReferenceVerification = 'INDEX_SUPPLIED' | 'NO_INDEX_SUPPLIED';

/** 由既有 owner 的 `status` 派生的 canon 判定。界面据此显示 DRAFT / CANON。 */
export type CanonState = 'CANON' | 'DRAFT' | 'NOT_APPLICABLE';

export type BibleReference = { asset_id: string; resolution: ReferenceResolution };

export type BibleDimension = {
  field: string;
  label: string;
  source: string;
  /** `state === 'UNKNOWN'` 时恒等于字面量 `UNKNOWN`。 */
  value: string;
  authored: boolean;
  state: DimensionState;
  /** 仅视觉维度：该维度所属世界记录是否已批准。 */
  authoritative?: boolean;
  /** 仅视觉维度：记录自身的 status（`APPROVED` / `DRAFT` / null）。 */
  record_status?: string | null;
  /** 仅 reference 维度。 */
  references?: BibleReference[];
  unresolved_references?: string[];
  verification?: ReferenceVerification;
  /** 仅 relationship 维度。 */
  relationships?: { target_character_id: string; state: string; authoritative: boolean }[];
  /** 仅 location 维度。 */
  geography_records?: number;
};

export type BibleUsageEntry = {
  document_id: string;
  mode: string;
  role: 'SCENE_CAST' | 'SHOT_CAST' | 'SHOT_CONTINUITY' | 'SCENE_LOCATION' | string;
  scene_id?: string;
  shot_id?: string;
};

export type CharacterBibleEntry = {
  character_id: string;
  name: string;
  dimensions: BibleDimension[];
  used_in: BibleUsageEntry[];
  visual_record_status: string | null;
  visual_authoritative: boolean;
};

export type SceneBibleEntry = {
  location_id: string;
  name: string;
  dimensions: BibleDimension[];
  reference_asset_ids: string[];
  used_in: BibleUsageEntry[];
  visual_record_status: string | null;
  visual_authoritative: boolean;
};

export type BibleGap = { field: string; character_id?: string; location_id?: string };

export type BibleProjection = {
  contract: string;
  schema_version: number;
  advisory_only: true;
  execution_authority: false;
  auto_modify: false;
  unknown_is_explicit: true;
  required_character_fields: CharacterBibleField[];
  required_scene_fields: SceneBibleField[];
  character_bible: {
    contract: string;
    schema_version: number;
    required_fields: CharacterBibleField[];
    entries: CharacterBibleEntry[];
    character_count: number;
  };
  scene_bible: {
    contract: string;
    schema_version: number;
    required_fields: SceneBibleField[];
    entries: SceneBibleEntry[];
    location_count: number;
  };
  gaps: { characters: BibleGap[]; scenes: BibleGap[] };
  project_id: string;
  scope: Record<string, string>;
  generated_at: string;
  project_context: { title: string; genre: string; inherited_not_authored: true };
  visual_owner: string;
  world_owner_available: boolean;
};

export type BibleSurfaceState = 'IDLE' | 'LOADING' | 'READY' | 'EMPTY' | 'DENIED' | 'FAILED';
export type BibleProblem = { code: string; message: string };

/** 本工作面只读：只有读取通道。 */
export type BibleClient = { readBible: (signal?: AbortSignal) => Promise<BibleProjection> };

/** 由既有 owner 的 status 派生界面判定；这不是新的持久化状态。 */
export function canonState(dimension: BibleDimension): CanonState {
  if (!dimension.authored) return 'NOT_APPLICABLE';
  if (dimension.record_status === null || dimension.record_status === undefined) return 'CANON';
  return dimension.authoritative ? 'CANON' : 'DRAFT';
}
