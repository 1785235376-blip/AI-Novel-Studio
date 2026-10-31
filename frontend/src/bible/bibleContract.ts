/**
 * Round2-B 严格解码器。
 *
 * 遵循既有 house style（见 `storyboard/storyboardWorkspaceContract.ts`、
 * `director/directorWorkspaceContract.ts`）：拒绝未知键、给字符串上界、拒绝控制字符，
 * 失败一律 `ApiError` + 稳定机器码 + 中文文案。
 *
 * 两处比普通解码更严，因为它们是本轮的**真实性规则**：
 *  1. `state === 'UNKNOWN'` 时 `value` 必须**就是**字面量 `UNKNOWN`，且 `authored` 必须为
 *     `false`；反过来 `AUTHORED` 时值不得为空。任何"未知被渲染成空白"的可能都在这里被拒绝。
 *  2. 每个维度的允许键集合按字段冻结，所以后端多一个或少一个键都会明确失败。
 */

import { ApiError } from '../api';
import {
  BIBLE_BOUNDS, BIBLE_CONTRACT, BIBLE_ERROR_CODES, BIBLE_SCHEMA_VERSION,
  CHARACTER_BIBLE_CONTRACT, CHARACTER_BIBLE_FIELDS, DIMENSION_BASE_KEYS,
  GEOGRAPHY_DIMENSION_EXTRA_KEYS, REFERENCE_DIMENSION_EXTRA_KEYS,
  RELATIONSHIP_DIMENSION_EXTRA_KEYS, SCENE_BIBLE_CONTRACT, SCENE_BIBLE_FIELDS, UNKNOWN,
  VISUAL_DIMENSION_EXTRA_KEYS, VISUAL_FIELDS,
  type BibleDimension, type BibleGap, type BibleProjection, type BibleReference,
  type BibleUsageEntry, type CharacterBibleEntry, type DimensionState,
  type ReferenceResolution, type ReferenceVerification, type SceneBibleEntry,
} from './bibleTypes';

const { responseInvalid, scopeMismatch } = BIBLE_ERROR_CODES;

export function bibleInvalid(): never {
  throw new ApiError({
    status: 200, code: responseInvalid,
    message: '角色与场景圣经拿到的数据不完整或与契约不符，请读取后重试。',
  });
}

function mismatch(): never {
  throw new ApiError({
    status: 403, code: scopeMismatch,
    message: '角色与场景圣经与当前项目或分支不一致，请重新打开工作区。',
  });
}

function record(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) bibleInvalid();
  return value as Record<string, unknown>;
}

/** 未知键一律拒绝；`optional` 里的键允许缺席。 */
function closed(row: Record<string, unknown>, required: readonly string[], optional: readonly string[] = []): void {
  if (required.some(key => !Object.hasOwn(row, key))
      || Object.keys(row).some(key => !required.includes(key) && !optional.includes(key))) {
    bibleInvalid();
  }
}

function text(value: unknown, maximum: number, allowEmpty = true): string {
  if (typeof value !== 'string' || value.length > maximum || (!allowEmpty && !value.trim())) bibleInvalid();
  if (/[\u0000-\u001f\u007f]/.test(value)) bibleInvalid();
  return value;
}

function boundedInteger(value: unknown, minimum: number, maximum: number): number {
  if (typeof value !== 'number' || !Number.isSafeInteger(value) || value < minimum || value > maximum) bibleInvalid();
  return value;
}

function boolean(value: unknown): boolean {
  if (typeof value !== 'boolean') bibleInvalid();
  return value;
}

function literal<T extends string>(value: unknown, allowed: readonly T[]): T {
  if (typeof value !== 'string' || !allowed.includes(value as T)) bibleInvalid();
  return value as T;
}

function list(value: unknown, maximum: number): unknown[] {
  if (!Array.isArray(value) || value.length > maximum) bibleInvalid();
  return value;
}

/** 后端声明的必填表必须与前端冻结词表**完全一致**（顺序也一致，因为顺序即显示顺序）。 */
function exactFields(declared: unknown, expected: readonly string[]): void {
  if (!Array.isArray(declared) || declared.length !== expected.length
      || declared.some((item, index) => item !== expected[index])) {
    bibleInvalid();
  }
}

const STATES: readonly DimensionState[] = ['AUTHORED', UNKNOWN];
const RESOLUTIONS: readonly ReferenceResolution[] = ['RESOLVED', 'UNRESOLVED'];
const VERIFICATIONS: readonly ReferenceVerification[] = ['INDEX_SUPPLIED', 'NO_INDEX_SUPPLIED'];

/** 每个字段允许的额外键；基础六键恒在。 */
function allowedKeysFor(field: string): readonly string[] {
  if (field === 'reference') return REFERENCE_DIMENSION_EXTRA_KEYS;
  if (field === 'relationship') return RELATIONSHIP_DIMENSION_EXTRA_KEYS;
  if (field === 'location') return GEOGRAPHY_DIMENSION_EXTRA_KEYS;
  if (VISUAL_FIELDS.includes(field)) return VISUAL_DIMENSION_EXTRA_KEYS;
  return [];
}

const USAGE_ROLES = ['SCENE_CAST', 'SHOT_CAST', 'SHOT_CONTINUITY', 'SCENE_LOCATION'] as const;

function usageEntries(value: unknown): BibleUsageEntry[] {
  return list(value, BIBLE_BOUNDS.usage).map(item => {
    const row = record(item);
    closed(row, ['document_id', 'mode', 'role'], ['scene_id', 'shot_id']);
    const entry: BibleUsageEntry = {
      document_id: text(row.document_id, BIBLE_BOUNDS.identifier, false),
      mode: text(row.mode, 60, false),
      role: text(row.role, 60, false),
    };
    if (Object.hasOwn(row, 'scene_id')) entry.scene_id = text(row.scene_id, BIBLE_BOUNDS.identifier);
    if (Object.hasOwn(row, 'shot_id')) entry.shot_id = text(row.shot_id, BIBLE_BOUNDS.identifier);
    if (!USAGE_ROLES.includes(entry.role as typeof USAGE_ROLES[number])) bibleInvalid();
    return entry;
  });
}

function dimension(value: unknown, field: string): BibleDimension {
  const row = record(value);
  closed(row, DIMENSION_BASE_KEYS, allowedKeysFor(field));
  if (row.field !== field) bibleInvalid();
  const state = literal(row.state, STATES);
  const authored = boolean(row.authored);
  const raw = text(row.value, BIBLE_BOUNDS.text);
  // 真实性规则 1：未知必须**是** UNKNOWN，已 authoring 的值不得为空。
  if (state === UNKNOWN) {
    if (raw !== UNKNOWN || authored !== false) bibleInvalid();
  } else if (!raw || authored !== true) {
    bibleInvalid();
  }
  const result: BibleDimension = {
    field, label: text(row.label, 100, false), source: text(row.source, 300, false),
    value: raw, authored, state,
  };
  if (allowedKeysFor(field) === VISUAL_DIMENSION_EXTRA_KEYS) {
    result.authoritative = boolean(row.authoritative);
    result.record_status = row.record_status === null ? null : text(row.record_status, 40, false);
  }
  if (field === 'reference') {
    result.references = list(row.references, BIBLE_BOUNDS.assets).map(item => {
      const entry = record(item);
      closed(entry, ['asset_id', 'resolution']);
      return {
        asset_id: text(entry.asset_id, BIBLE_BOUNDS.identifier, false),
        resolution: literal(entry.resolution, RESOLUTIONS),
      } satisfies BibleReference;
    });
    result.unresolved_references = list(row.unresolved_references, BIBLE_BOUNDS.assets)
      .map(item => text(item, BIBLE_BOUNDS.identifier, false));
    result.verification = literal(row.verification, VERIFICATIONS);
    // 声明与结论必须自洽：未解析清单恰好等于 references 中 UNRESOLVED 的那些。
    const derived = result.references.filter(item => item.resolution === 'UNRESOLVED').map(item => item.asset_id);
    if (derived.length !== result.unresolved_references.length
        || derived.some((id, index) => id !== result.unresolved_references![index])) {
      bibleInvalid();
    }
    if ((result.verification === 'NO_INDEX_SUPPLIED') && result.references.some(item => item.resolution === 'RESOLVED')) {
      bibleInvalid();
    }
  }
  if (field === 'relationship') {
    result.relationships = list(row.relationships, 200).map(item => {
      const entry = record(item);
      closed(entry, ['target_character_id', 'state', 'authoritative']);
      return {
        target_character_id: text(entry.target_character_id, BIBLE_BOUNDS.identifier, false),
        state: text(entry.state, BIBLE_BOUNDS.text, false),
        authoritative: boolean(entry.authoritative),
      };
    });
  }
  if (field === 'location') {
    result.geography_records = boundedInteger(row.geography_records, 0, 100000);
  }
  return result;
}

function dimensions(value: unknown, expected: readonly string[]): BibleDimension[] {
  const rows = list(value, expected.length).map((item, index) => dimension(item, expected[index]));
  if (rows.length !== expected.length) bibleInvalid();
  return rows;
}

function characterEntry(value: unknown): CharacterBibleEntry {
  const row = record(value);
  closed(row, ['character_id', 'name', 'dimensions', 'used_in', 'visual_record_status', 'visual_authoritative']);
  return {
    character_id: text(row.character_id, BIBLE_BOUNDS.identifier, false),
    name: text(row.name, 500),
    dimensions: dimensions(row.dimensions, CHARACTER_BIBLE_FIELDS),
    used_in: usageEntries(row.used_in),
    visual_record_status: row.visual_record_status === null ? null : text(row.visual_record_status, 40, false),
    visual_authoritative: boolean(row.visual_authoritative),
  };
}

function sceneEntry(value: unknown): SceneBibleEntry {
  const row = record(value);
  closed(row, ['location_id', 'name', 'dimensions', 'reference_asset_ids', 'used_in',
               'visual_record_status', 'visual_authoritative']);
  return {
    location_id: text(row.location_id, BIBLE_BOUNDS.identifier, false),
    name: text(row.name, 500),
    dimensions: dimensions(row.dimensions, SCENE_BIBLE_FIELDS),
    reference_asset_ids: list(row.reference_asset_ids, BIBLE_BOUNDS.assets)
      .map(item => text(item, BIBLE_BOUNDS.identifier, false)),
    used_in: usageEntries(row.used_in),
    visual_record_status: row.visual_record_status === null ? null : text(row.visual_record_status, 40, false),
    visual_authoritative: boolean(row.visual_authoritative),
  };
}

function gaps(value: unknown, allowed: readonly string[], subjectKey: string): BibleGap[] {
  return list(value, 5000).map(item => {
    const row = record(item);
    closed(row, [subjectKey, 'field']);
    const field = text(row.field, 100, false);
    if (!allowed.includes(field)) bibleInvalid();
    return { field, [subjectKey]: text(row[subjectKey], BIBLE_BOUNDS.identifier, false) } as BibleGap;
  });
}

/** 唯一入口。身份不符抛 `scopeMismatch`，其余契约问题抛 `responseInvalid`。 */
export function bibleProjection(value: unknown, expectedProjectId: string): BibleProjection {
  if (typeof expectedProjectId !== 'string' || !expectedProjectId.trim()
      || expectedProjectId.length > BIBLE_BOUNDS.identifier) bibleInvalid();
  const row = record(value);
  closed(row, ['contract', 'schema_version', 'advisory_only', 'execution_authority', 'auto_modify',
               'unknown_is_explicit', 'required_character_fields', 'required_scene_fields',
               'character_bible', 'scene_bible', 'gaps', 'project_id', 'scope', 'generated_at',
               'project_context', 'visual_owner', 'world_owner_available']);
  if (row.contract !== BIBLE_CONTRACT || row.schema_version !== BIBLE_SCHEMA_VERSION) bibleInvalid();
  if (row.advisory_only !== true || row.execution_authority !== false || row.auto_modify !== false) bibleInvalid();
  if (row.unknown_is_explicit !== true) bibleInvalid();
  const projectId = text(row.project_id, BIBLE_BOUNDS.identifier, false);
  if (projectId !== expectedProjectId) mismatch();
  exactFields(row.required_character_fields, CHARACTER_BIBLE_FIELDS);
  exactFields(row.required_scene_fields, SCENE_BIBLE_FIELDS);

  const characters = record(row.character_bible);
  closed(characters, ['contract', 'schema_version', 'required_fields', 'entries', 'character_count']);
  if (characters.contract !== CHARACTER_BIBLE_CONTRACT) bibleInvalid();
  exactFields(characters.required_fields, CHARACTER_BIBLE_FIELDS);
  const characterEntries = list(characters.entries, 5000).map(characterEntry);
  if (boundedInteger(characters.character_count, 0, 5000) !== characterEntries.length) bibleInvalid();

  const scenes = record(row.scene_bible);
  closed(scenes, ['contract', 'schema_version', 'required_fields', 'entries', 'location_count']);
  if (scenes.contract !== SCENE_BIBLE_CONTRACT) bibleInvalid();
  exactFields(scenes.required_fields, SCENE_BIBLE_FIELDS);
  const sceneEntries = list(scenes.entries, 5000).map(sceneEntry);
  if (boundedInteger(scenes.location_count, 0, 5000) !== sceneEntries.length) bibleInvalid();

  const gapRow = record(row.gaps);
  closed(gapRow, ['characters', 'scenes']);
  const context = record(row.project_context);
  closed(context, ['title', 'genre', 'inherited_not_authored']);
  if (context.inherited_not_authored !== true) bibleInvalid();
  const scope: Record<string, string> = {};
  for (const [key, raw] of Object.entries(record(row.scope))) scope[key] = text(raw, 300);

  return {
    contract: BIBLE_CONTRACT,
    schema_version: BIBLE_SCHEMA_VERSION,
    advisory_only: true, execution_authority: false, auto_modify: false, unknown_is_explicit: true,
    required_character_fields: [...CHARACTER_BIBLE_FIELDS],
    required_scene_fields: [...SCENE_BIBLE_FIELDS],
    character_bible: {
      contract: CHARACTER_BIBLE_CONTRACT, schema_version: BIBLE_SCHEMA_VERSION,
      required_fields: [...CHARACTER_BIBLE_FIELDS], entries: characterEntries,
      character_count: characterEntries.length,
    },
    scene_bible: {
      contract: SCENE_BIBLE_CONTRACT, schema_version: BIBLE_SCHEMA_VERSION,
      required_fields: [...SCENE_BIBLE_FIELDS], entries: sceneEntries,
      location_count: sceneEntries.length,
    },
    gaps: {
      characters: gaps(gapRow.characters, CHARACTER_BIBLE_FIELDS, 'character_id'),
      scenes: gaps(gapRow.scenes, SCENE_BIBLE_FIELDS, 'location_id'),
    },
    project_id: projectId,
    scope,
    generated_at: text(row.generated_at, 100, false),
    project_context: {
      title: text(context.title, 500), genre: text(context.genre, 500), inherited_not_authored: true,
    },
    visual_owner: text(row.visual_owner, 300),
    world_owner_available: boolean(row.world_owner_available),
  };
}

// ---------------------------------------------------------------- 界面派生 --

/** 一个条目里仍未 authoring 的维度字段（后端 `gaps` 的本地等价物，用于面板内提示）。 */
export function unknownFields(entry: { dimensions: BibleDimension[] }): string[] {
  return entry.dimensions.filter(item => !item.authored).map(item => item.field);
}

/** 一个条目里处于 DRAFT（已 authoring 但未批准）的维度字段。 */
export function draftFields(entry: { dimensions: BibleDimension[] }): string[] {
  return entry.dimensions.filter(item => item.authored && item.authoritative === false).map(item => item.field);
}
