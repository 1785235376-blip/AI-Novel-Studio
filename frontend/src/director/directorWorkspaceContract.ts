import { checkedDirectorCameraEvidence } from './directorCameraEvidence';
/**
 * Phase14-A 严格解码器。
 *
 * 遵循既有 house style（见 `storyboard/storyboardWorkspaceContract.ts`）：拒绝未知键、
 * 给字符串上界、拒绝控制字符与越界整数，失败一律 `ApiError` + 稳定机器码 + 中文文案。
 *
 * 额外一条：解码器会把后端声明的**必填字段表**与前端冻结词表逐一比对。后端少报一个
 * 必填维度、或改名，都会在这里变成明确失败，而不是安静地少显示一行。
 */

import { ApiError } from '../api';
import {
  CONTINUITY_DIMENSIONS, DIRECTOR_INTENT_FIELDS, DIRECTOR_WORKSPACE_BOUNDS,
  DIRECTOR_WORKSPACE_CONTRACT, DIRECTOR_WORKSPACE_ERROR_CODES, DIRECTOR_WORKSPACE_SCHEMA_VERSION,
  DIRECTOR_INTENT_CONTRACT, SHOT_CARD_CONTRACT, CONTINUITY_PANEL_CONTRACT,
  SHOT_CARD_FIELDS,
  type CameraLanguageUsage, type ClassifiedShotValue, type ContinuityDimension, type ContinuityPanel,
  type ContinuityWarning, type DirectorIntentProjection, type DirectorIntentRecord,
  type DirectorWorkspaceProjection, type ShotCardProjection, type ShotValue, type ShotValueCode,
  type SimpleUsage,
} from './directorWorkspaceTypes';

const { responseInvalid, scopeMismatch } = DIRECTOR_WORKSPACE_ERROR_CODES;

export function directorWorkspaceInvalid(): never {
  throw new ApiError({
    status: 200, code: responseInvalid,
    message: '导演工作台拿到的数据不完整或与契约不符，请读取原文档核对后重试。',
  });
}

function mismatch(): never {
  throw new ApiError({
    status: 403, code: scopeMismatch,
    message: '导演工作台与当前项目、分支或文档不一致，请重新打开工作区。',
  });
}

function record(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) directorWorkspaceInvalid();
  return value as Record<string, unknown>;
}

/** 未知键一律拒绝；`optional` 里的键允许缺席。 */
function closed(row: Record<string, unknown>, required: readonly string[], optional: readonly string[] = []): void {
  if (required.some(key => !Object.hasOwn(row, key))
      || Object.keys(row).some(key => !required.includes(key) && !optional.includes(key))) {
    directorWorkspaceInvalid();
  }
}

function text(value: unknown, maximum: number, allowEmpty = true): string {
  if (typeof value !== 'string' || value.length > maximum || (!allowEmpty && !value.trim())) directorWorkspaceInvalid();
  if (/[\u0000-\u001f\u007f]/.test(value)) directorWorkspaceInvalid();
  return value;
}

function boundedInteger(value: unknown, minimum: number, maximum: number): number {
  if (typeof value !== 'number' || !Number.isSafeInteger(value) || value < minimum || value > maximum) {
    directorWorkspaceInvalid();
  }
  return value;
}

function boolean(value: unknown): boolean {
  if (typeof value !== 'boolean') directorWorkspaceInvalid();
  return value;
}

function literal<T extends string>(value: unknown, allowed: readonly T[]): T {
  if (typeof value !== 'string' || !allowed.includes(value as T)) directorWorkspaceInvalid();
  return value as T;
}

function list(value: unknown, maximum: number): unknown[] {
  if (!Array.isArray(value) || value.length > maximum) directorWorkspaceInvalid();
  return value;
}

function exactFields(declared: unknown, expected: readonly string[]): void {
  // 后端声明的必填表必须与前端冻结词表完全一致（顺序也一致，因为顺序即显示顺序）。
  if (!Array.isArray(declared) || declared.length !== expected.length
      || declared.some((item, index) => item !== expected[index])) {
    directorWorkspaceInvalid();
  }
}

const SHOT_VALUE_CODES: readonly ShotValueCode[] = ['CANONICAL', 'LEGACY_PASSTHROUGH', 'EMPTY'];
const INTENT_KINDS = ['DOCUMENT_AUTHORED', 'PER_SHOT_MEASURED'] as const;
const AUTHORED_SCOPES = ['DOCUMENT', 'PER_SHOT'] as const;

/** `extra` lets the classified variant accept its own `code` key without duplicating the shape. */
function shotValue(value: unknown, field: string, extra: readonly string[] = []): ShotValue {
  const row = record(value);
  closed(row, ['field', 'value', 'authored', 'source', 'owner', ...extra]);
  if (row.field !== field) directorWorkspaceInvalid();
  return {
    field, value: text(row.value, DIRECTOR_WORKSPACE_BOUNDS.text),
    authored: boolean(row.authored), source: text(row.source, 300), owner: text(row.owner, 300),
  };
}

function classifiedShotValue(value: unknown, field: string): ClassifiedShotValue {
  const row = record(value);
  return { ...shotValue(value, field, ['code']), code: literal(row.code, SHOT_VALUE_CODES) };
}

function simpleUsage(value: unknown): SimpleUsage {
  const row = record(value);
  closed(row, ['measured_over_rows', 'authored_rows', 'unauthored_rows', 'dimensions']);
  const dimensions: SimpleUsage['dimensions'] = {};
  for (const [key, raw] of Object.entries(record(row.dimensions))) {
    const entry = record(raw);
    closed(entry, ['rows', 'authored_rows', 'values']);
    dimensions[key] = {
      rows: boundedInteger(entry.rows, 0, 100000),
      authored_rows: boundedInteger(entry.authored_rows, 0, 100000),
      values: list(entry.values, 1000).map(item => {
        const row2 = record(item);
        closed(row2, ['value', 'count']);
        return { value: text(row2.value, DIRECTOR_WORKSPACE_BOUNDS.text), count: boundedInteger(row2.count, 1, 100000) };
      }),
    };
  }
  const measured = boundedInteger(row.measured_over_rows, 0, 100000);
  const authored = boundedInteger(row.authored_rows, 0, 100000);
  const unauthored = boundedInteger(row.unauthored_rows, 0, 100000);
  if (authored + unauthored !== measured) directorWorkspaceInvalid();
  return { measured_over_rows: measured, authored_rows: authored, unauthored_rows: unauthored, dimensions };
}

function cameraUsage(value: unknown): CameraLanguageUsage {
  const row = record(value);
  closed(row, ['measured_over_rows', 'dimensions', 'authored_values', 'canonical_values',
               'legacy_values_preserved', 'canonical_ratio', 'vocabulary']);
  const dimensions: CameraLanguageUsage['dimensions'] = {};
  for (const [key, raw] of Object.entries(record(row.dimensions))) {
    const entry = record(raw);
    closed(entry, ['rows', 'authored_rows', 'values']);
    dimensions[key] = {
      rows: boundedInteger(entry.rows, 0, 100000),
      authored_rows: boundedInteger(entry.authored_rows, 0, 100000),
      values: list(entry.values, 1000).map(item => {
        const row2 = record(item);
        closed(row2, ['value', 'code', 'count']);
        return { value: text(row2.value, DIRECTOR_WORKSPACE_BOUNDS.text),
                 code: literal(row2.code, SHOT_VALUE_CODES), count: boundedInteger(row2.count, 1, 100000) };
      }),
    };
  }
  const ratio = row.canonical_ratio;
  if (typeof ratio !== 'number' || !Number.isFinite(ratio) || ratio < 0 || ratio > 1) directorWorkspaceInvalid();
  const vocabulary: CameraLanguageUsage['vocabulary'] = {};
  for (const [key, raw] of Object.entries(record(row.vocabulary))) {
    const entry = record(raw);
    closed(entry, ['members', 'aliases', 'alias_keys_are_folded']);
    if (entry.alias_keys_are_folded !== true) directorWorkspaceInvalid();
    const aliases: Record<string, string> = {};
    for (const [alias, target] of Object.entries(record(entry.aliases))) {
      aliases[alias] = text(target, 200, false);
    }
    vocabulary[key] = {
      members: list(entry.members, DIRECTOR_WORKSPACE_BOUNDS.members).map(item => text(item, 200, false)),
      aliases, alias_keys_are_folded: true,
    };
  }
  return {
    measured_over_rows: boundedInteger(row.measured_over_rows, 0, 100000), dimensions,
    authored_values: boundedInteger(row.authored_values, 0, 1000000),
    canonical_values: boundedInteger(row.canonical_values, 0, 1000000),
    legacy_values_preserved: list(row.legacy_values_preserved, 1000).map(item => text(item, DIRECTOR_WORKSPACE_BOUNDS.text)),
    canonical_ratio: ratio, vocabulary,
  };
}

function intentRecord(value: unknown): DirectorIntentRecord {
  const row = record(value);
  closed(row, ['field', 'value', 'authored', 'source', 'owner', 'label', 'kind', 'authored_scope', 'usage'],
         ['detail']);
  const field = literal(row.field, DIRECTOR_INTENT_FIELDS);
  const kind = literal(row.kind, INTENT_KINDS);
  const authoredScope = literal(row.authored_scope, AUTHORED_SCOPES);
  // 文档级与逐镜头级的区分是契约的一部分：混淆它就会把测量结果说成导演决定。
  if ((kind === 'DOCUMENT_AUTHORED') !== (authoredScope === 'DOCUMENT')) directorWorkspaceInvalid();
  const usage = row.usage === null ? null : kind === 'PER_SHOT_MEASURED'
    ? (field === 'camera_language' ? cameraUsage(row.usage) : simpleUsage(row.usage)) : directorWorkspaceInvalid();
  const entry: DirectorIntentRecord = {
    field, label: text(row.label, 100, false), kind, authored_scope: authoredScope,
    value: text(row.value, DIRECTOR_WORKSPACE_BOUNDS.text), authored: boolean(row.authored),
    source: text(row.source, 300), owner: text(row.owner, 300), usage,
  };
  if (Object.hasOwn(row, 'detail')) {
    const detail = record(row.detail);
    closed(detail, ['rhythm', 'reference_works']);
    entry.detail = {
      rhythm: text(detail.rhythm, DIRECTOR_WORKSPACE_BOUNDS.text),
      reference_works: list(detail.reference_works, 20).map(item => text(item, 1000, false)),
    };
  }
  return entry;
}

function shotCard(value: unknown): ShotCardProjection {
  const row = record(value);
  closed(row, ['contract', 'shot_id', 'number', 'scene_id', 'duration', 'camera', 'camera_classification',
               'camera_canonical_ratio', 'lens', 'movement', 'composition', 'lighting', 'character',
               'action', 'emotion', 'audio', 'director_note_ids']);
  if (row.contract !== SHOT_CARD_CONTRACT) directorWorkspaceInvalid();
  const duration = record(row.duration);
  closed(duration, ['seconds', 'authored']);
  const camera = record(row.camera);
  closed(camera, ['shot_size', 'camera_motion', 'lens', 'composition', 'angle']);
  const classification: Record<string, ShotValueCode> = {};
  for (const [key, raw] of Object.entries(record(row.camera_classification))) {
    classification[key] = literal(raw, SHOT_VALUE_CODES);
  }
  const ratio = row.camera_canonical_ratio;
  if (typeof ratio !== 'number' || !Number.isFinite(ratio) || ratio < 0 || ratio > 1) directorWorkspaceInvalid();
  const character = record(row.character);
  closed(character, ['field', 'values', 'authored', 'source', 'owner']);
  if (character.field !== 'character') directorWorkspaceInvalid();
  const audio = record(row.audio);
  closed(audio, ['field', 'sound', 'sound_effect', 'dialogue', 'authored', 'source', 'owner']);
  if (audio.field !== 'audio') directorWorkspaceInvalid();
  const number = row.number === null ? null : boundedInteger(row.number, 1, 10000);
  const seconds = duration.seconds === null ? null : boundedInteger(duration.seconds, 1, 600);
  if ((seconds !== null) !== boolean(duration.authored)) directorWorkspaceInvalid();
  return {
    contract: SHOT_CARD_CONTRACT,
    shot_id: text(row.shot_id, DIRECTOR_WORKSPACE_BOUNDS.identifier, false),
    number, scene_id: text(row.scene_id, DIRECTOR_WORKSPACE_BOUNDS.identifier),
    duration: { seconds, authored: boolean(duration.authored) },
    camera: {
      shot_size: text(camera.shot_size, DIRECTOR_WORKSPACE_BOUNDS.text),
      camera_motion: text(camera.camera_motion, DIRECTOR_WORKSPACE_BOUNDS.text),
      lens: text(camera.lens, DIRECTOR_WORKSPACE_BOUNDS.text),
      composition: text(camera.composition, DIRECTOR_WORKSPACE_BOUNDS.text),
      angle: text(camera.angle, 200),
    },
    camera_classification: classification, camera_canonical_ratio: ratio,
    lens: classifiedShotValue(row.lens, 'lens'),
    movement: classifiedShotValue(row.movement, 'movement'),
    composition: classifiedShotValue(row.composition, 'composition'),
    lighting: shotValue(row.lighting, 'lighting'),
    character: {
      field: 'character', values: list(character.values, 100).map(item => text(item, DIRECTOR_WORKSPACE_BOUNDS.identifier)),
      authored: boolean(character.authored), source: text(character.source, 300), owner: text(character.owner, 300),
    },
    action: shotValue(row.action, 'action'),
    emotion: shotValue(row.emotion, 'emotion'),
    audio: {
      field: 'audio', sound: text(audio.sound, DIRECTOR_WORKSPACE_BOUNDS.text),
      sound_effect: text(audio.sound_effect, DIRECTOR_WORKSPACE_BOUNDS.text),
      dialogue: list(audio.dialogue, 200).map(item => {
        const line = record(item);
        closed(line, ['speaker', 'text', 'delivery']);
        return { speaker: text(line.speaker, 240), text: text(line.text, 16000), delivery: text(line.delivery, 2000) };
      }),
      authored: boolean(audio.authored), source: text(audio.source, 300), owner: text(audio.owner, 300),
    },
    director_note_ids: list(row.director_note_ids, 100).map(item => text(item, DIRECTOR_WORKSPACE_BOUNDS.identifier)),
  };
}

function continuityDimension(value: unknown): ContinuityDimension {
  const row = record(value);
  closed(row, ['field', 'label', 'code', 'sources', 'compared_pairs', 'unknown_pairs']);
  return {
    field: literal(row.field, CONTINUITY_DIMENSIONS),
    label: text(row.label, 100, false),
    code: text(row.code, 200, false),
    sources: list(row.sources, 8).map(item => text(item, 200, false)),
    compared_pairs: boundedInteger(row.compared_pairs, 0, 100000),
    unknown_pairs: boundedInteger(row.unknown_pairs, 0, 100000),
  };
}

function continuityWarning(value: unknown): ContinuityWarning {
  const row = record(value);
  closed(row, ['code', 'field', 'previous_shot_id', 'next_shot_id', 'previous', 'next', 'label', 'severity']);
  return {
    code: text(row.code, 200, false), field: text(row.field, 100, false),
    label: text(row.label, 100, false),
    // 只有一种严重级别：这是提示，不是错误，更不是待执行的修改。
    severity: literal(row.severity, ['WARNING'] as const),
    previous_shot_id: text(row.previous_shot_id, DIRECTOR_WORKSPACE_BOUNDS.identifier),
    next_shot_id: text(row.next_shot_id, DIRECTOR_WORKSPACE_BOUNDS.identifier),
    previous: text(row.previous, DIRECTOR_WORKSPACE_BOUNDS.text),
    next: text(row.next, DIRECTOR_WORKSPACE_BOUNDS.text),
  };
}

function continuityPanel(value: unknown): ContinuityPanel {
  const row = record(value);
  closed(row, ['contract', 'schema_version', 'warning_only', 'auto_modify', 'required_dimensions',
               'dimensions', 'excluded', 'shot_count', 'compared_pairs', 'warnings']);
  if (row.contract !== CONTINUITY_PANEL_CONTRACT) directorWorkspaceInvalid();
  if (row.warning_only !== true || row.auto_modify !== false) directorWorkspaceInvalid();
  exactFields(row.required_dimensions, CONTINUITY_DIMENSIONS);
  const dimensions = list(row.dimensions, 16).map(continuityDimension);
  if (dimensions.length !== CONTINUITY_DIMENSIONS.length
      || dimensions.some((item, index) => item.field !== CONTINUITY_DIMENSIONS[index])) {
    directorWorkspaceInvalid();
  }
  const shotCount = boundedInteger(row.shot_count, 0, 10000);
  const comparedPairs = boundedInteger(row.compared_pairs, 0, 10000);
  if (comparedPairs !== Math.max(shotCount - 1, 0)) directorWorkspaceInvalid();
  return {
    contract: CONTINUITY_PANEL_CONTRACT,
    schema_version: boundedInteger(row.schema_version, 1, 1000),
    warning_only: true, auto_modify: false,
    required_dimensions: [...CONTINUITY_DIMENSIONS],
    dimensions,
    excluded: list(row.excluded, 16).map(item => {
      const entry = record(item);
      closed(entry, ['field', 'reason']);
      return { field: text(entry.field, 100, false), reason: text(entry.reason, 200, false) };
    }),
    shot_count: shotCount, compared_pairs: comparedPairs,
    warnings: list(row.warnings, 1000).map(continuityWarning),
  };
}

function directorIntent(value: unknown): DirectorIntentProjection {
  const row = record(value);
  closed(row, ['contract', 'schema_version', 'advisory_only', 'auto_modify', 'measured_over',
               'required_fields', 'fields', 'dimensions']);
  if (row.contract !== DIRECTOR_INTENT_CONTRACT || row.advisory_only !== true || row.auto_modify !== false) {
    directorWorkspaceInvalid();
  }
  exactFields(row.required_fields, DIRECTOR_INTENT_FIELDS);
  const fields = list(row.fields, 16).map(intentRecord);
  if (fields.length !== DIRECTOR_INTENT_FIELDS.length
      || fields.some((item, index) => item.field !== DIRECTOR_INTENT_FIELDS[index])) {
    directorWorkspaceInvalid();
  }
  const dimensions = record(row.dimensions);
  if (Object.keys(dimensions).length !== DIRECTOR_INTENT_FIELDS.length
      || DIRECTOR_INTENT_FIELDS.some(key => !Object.hasOwn(dimensions, key))) {
    directorWorkspaceInvalid();
  }
  return {
    contract: DIRECTOR_INTENT_CONTRACT,
    schema_version: boundedInteger(row.schema_version, 1, 1000),
    advisory_only: true, auto_modify: false,
    measured_over: literal(row.measured_over, ['SHOTS', 'DIRECTOR_NOTES', 'NONE'] as const),
    required_fields: [...DIRECTOR_INTENT_FIELDS], fields,
    dimensions: Object.fromEntries(fields.map(item => [item.field, item])) as DirectorIntentProjection['dimensions'],
  };
}

/** 唯一的顶层解码入口。任何身份不符都抛 `scopeMismatch`，其余契约问题抛 `responseInvalid`。 */
export function directorWorkspaceProjection(value: unknown, expectedDocumentId: string): DirectorWorkspaceProjection {
  if (typeof expectedDocumentId !== 'string' || !expectedDocumentId.trim()
      || expectedDocumentId.length > DIRECTOR_WORKSPACE_BOUNDS.identifier) directorWorkspaceInvalid();
  const row = record(value);
  closed(row, ['contract', 'schema_version', 'advisory_only', 'execution_authority', 'auto_modify',
               'project_id', 'scope', 'generated_at', 'project_context', 'document',
               'required_shot_card_fields', 'director_intent', 'shot_cards', 'continuity'], ['camera_geometry']);
  if (row.contract !== DIRECTOR_WORKSPACE_CONTRACT) directorWorkspaceInvalid();
  if (row.advisory_only !== true || row.execution_authority !== false || row.auto_modify !== false) {
    directorWorkspaceInvalid();
  }
  const document = record(row.document);
  closed(document, ['id', 'version', 'mode', 'title', 'status']);
  const documentId = text(document.id, DIRECTOR_WORKSPACE_BOUNDS.identifier, false);
  if (documentId !== expectedDocumentId) mismatch();
  exactFields(row.required_shot_card_fields, SHOT_CARD_FIELDS);
  const context = record(row.project_context);
  closed(context, ['title', 'genre', 'inherited_not_authored']);
  if (context.inherited_not_authored !== true) directorWorkspaceInvalid();
  const scope: Record<string, string> = {};
  for (const [key, raw] of Object.entries(record(row.scope))) scope[key] = text(raw, 300);
  return {
    contract: DIRECTOR_WORKSPACE_CONTRACT,
    schema_version: boundedInteger(row.schema_version, 1, 1000),
    advisory_only: true, execution_authority: false, auto_modify: false,
    project_id: text(row.project_id, DIRECTOR_WORKSPACE_BOUNDS.identifier, false),
    scope,
    generated_at: text(row.generated_at, 100, false),
    project_context: { title: text(context.title, 500), genre: text(context.genre, 500), inherited_not_authored: true },
    document: {
      id: documentId, version: boundedInteger(document.version, 1, 1000000),
      mode: text(document.mode, 40, false), title: text(document.title, 500), status: text(document.status, 40, false),
    },
    required_shot_card_fields: [...SHOT_CARD_FIELDS],
    director_intent: directorIntent(row.director_intent),
    shot_cards: list(row.shot_cards, 1000).map(shotCard),
    continuity: continuityPanel(row.continuity),
    ...(row.camera_geometry === undefined ? {} : { camera_geometry: checkedDirectorCameraEvidence(row.camera_geometry, { id: documentId, version: Number(document.version), mode: String(document.mode) }, directorWorkspaceInvalid) }),
  };
}

// 便于测试与复用的小工具：把后端发布的镜头语言词表摊平成下拉选项。
export function cameraVocabularyOptions(vocabulary: CameraLanguageUsage['vocabulary']): {
  field: string; members: string[]; aliases: Record<string, string>;
}[] {
  return Object.entries(vocabulary).map(([field, entry]) => ({
    field, members: [...entry.members], aliases: { ...entry.aliases },
  }));
}

/**
 * 从意图投影里取出后端发布的镜头语言词表。
 *
 * 词表只有这一个来源：界面不得自己写死景别/运动/镜头/构图字面量。
 * 文档还没有可统计内容时返回空表，而不是回退到本地硬编码词表。
 */
export function cameraVocabulary(intent: DirectorIntentProjection): CameraLanguageUsage['vocabulary'] {
  const usage = intent.dimensions.camera_language?.usage;
  return usage && 'vocabulary' in usage ? usage.vocabulary : {};
}
