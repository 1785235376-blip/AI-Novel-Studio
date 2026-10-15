/**
 * R3-U 严格解码器。
 *
 * 规则（沿用本仓库既有约定）：
 *  1. 未知键一律拒绝，所以后端多一个键就是明确的契约变化，而不是静默忽略。
 *  2. `UNKNOWN` / `TRUNCATED` / `UNDECODABLE` / `REDACTED` / `CONFLICTED` 必须**原样
 *     保留**，绝不被降级成空字符串或“看起来正常”的内容。
 *  3. 任何不一致都抛 `ApiError`，带稳定的机器码，不把原始 payload 拼进文案。
 */

import { ApiError } from '../api';
import {
  PROMPT_BOUNDS, PROMPT_ERROR_CODES, UNKNOWN,
  type BodyState, type PromptAnomaly, type PromptBindingRow, type PromptBindings,
  type PromptBody, type PromptEntry, type PromptField, type PromptLibrary,
  type PromptReceipt, type PromptVersionRow,
} from './promptTypes';

const { responseInvalid } = PROMPT_ERROR_CODES;

export function promptInvalid(): never {
  throw new ApiError({
    status: 200, code: responseInvalid,
    message: 'Prompt 数据不完整或与契约不符，请重新读取。',
  });
}

function record(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) promptInvalid();
  return value as Record<string, unknown>;
}

/** 未知键一律拒绝；`optional` 里的键允许缺席。 */
function closed(row: Record<string, unknown>, required: readonly string[],
  optional: readonly string[] = []): void {
  if (required.some(key => !Object.hasOwn(row, key))
    || Object.keys(row).some(key => !required.includes(key) && !optional.includes(key))) {
    promptInvalid();
  }
}

function text(value: unknown, maximum: number, allowEmpty = true): string {
  if (typeof value !== 'string' || value.length > maximum || (!allowEmpty && !value.trim())) {
    promptInvalid();
  }
  return value;
}

function identifier(value: unknown): string {
  const value2 = text(value, PROMPT_BOUNDS.identifier, false);
  if (/[\u0000-\u001f\u007f]/.test(value2)) promptInvalid();
  return value2;
}

function optionalIdentifier(value: unknown): string | null {
  return value === null || value === undefined ? null : identifier(value);
}

function count(value: unknown): number {
  if (typeof value !== 'number' || !Number.isInteger(value) || value < 0 || value > 1e9) promptInvalid();
  return value;
}

function optionalCount(value: unknown): number | null {
  return value === null || value === undefined ? null : count(value);
}

function flag(value: unknown): boolean {
  if (typeof value !== 'boolean') promptInvalid();
  return value;
}

function list<T>(value: unknown, maximum: number, item: (row: unknown) => T): T[] {
  if (!Array.isArray(value) || value.length > maximum) promptInvalid();
  return value.map(item);
}

function stringList(value: unknown, maximum: number): string[] {
  return list(value, maximum, row => identifier(row));
}

/** 正文：状态必须原样保留，预览/脱敏/不可读不得伪装成完整正文。 */
export function promptBody(value: unknown): PromptBody {
  const row = record(value);
  closed(row, ['state', 'value', 'digest', 'truncated', 'decodable', 'original_length', 'preview_length', 'limit', 'fetch'],
    ['body_validated', 'tail_unverified', 'digest_of']);
  const states: readonly BodyState[] = ['COMPLETE', 'TRUNCATED', 'UNDECODABLE', 'REDACTED', 'DELETED', 'UNAVAILABLE'];
  const state = text(row.state, 32) as BodyState;
  if (!states.includes(state)) promptInvalid();
  const raw = row.value;
  if (raw !== null && typeof raw !== 'string') promptInvalid();
  // COMPLETE 携带完整正文；TRUNCATED 携带**有效预览**；其余状态不得携带任何正文。
  // 把 TRUNCATED 和 REDACTED/UNDECODABLE 混为一谈会丢掉真实的预览内容。
  const carriesText = state === 'COMPLETE' || state === 'TRUNCATED';
  if (carriesText && typeof raw !== 'string') promptInvalid();
  if (!carriesText && raw !== null) promptInvalid();
  const bodyText = typeof raw === 'string' ? text(raw, PROMPT_BOUNDS.textBytes, true) : '';
  return {
    state,
    value: typeof raw === 'string' ? bodyText : null,
    digest: row.digest === null || row.digest === undefined ? null : text(row.digest, 128, false),
    truncated: flag(row.truncated),
    decodable: flag(row.decodable),
    originalLength: optionalCount(row.original_length),
    fetch: text(row.fetch, 32, false),
  };
}

function promptField(value: unknown): PromptField {
  const row = record(value);
  closed(row, ['field', 'label', 'value', 'authored', 'state']);
  const state = text(row.state, 16);
  if (state !== 'KNOWN' && state !== UNKNOWN) promptInvalid();
  const authored = flag(row.authored);
  // 未 authored 的字段其值必须是 UNKNOWN，不能是空串冒充“已填写”。
  if (!authored && row.value !== UNKNOWN) promptInvalid();
  return { field: text(row.field, 64, false), label: text(row.label, 64),
    value: row.value, authored, state: state as 'KNOWN' | 'UNKNOWN' };
}

function promptVersion(value: unknown): PromptVersionRow {
  const row = record(value);
  closed(row, ['asset_id', 'revision', 'asset_version', 'change_note', 'change_reason',
    'previous_asset_id', 'redacted', 'available']);
  const maybeText = (input: unknown, max: number): string | null =>
    input === null || input === undefined ? null : text(input, max);
  const revision = count(row.revision);
  if (revision < 1) promptInvalid();
  return {
    assetId: identifier(row.asset_id),
    revision,
    assetVersion: optionalCount(row.asset_version),
    changeNote: maybeText(row.change_note, 512),
    changeReason: maybeText(row.change_reason, 512),
    previousAssetId: optionalIdentifier(row.previous_asset_id),
    redacted: flag(row.redacted),
    available: flag(row.available),
  };
}

function bindingRow(value: unknown): PromptBindingRow {
  const row = record(value);
  const id = identifier(row.id);
  const resolution = text(row.resolution, 16);
  if (resolution !== 'KNOWN' && resolution !== UNKNOWN) promptInvalid();
  return {
    id, resolution,
    label: row.label === undefined || row.label === null ? null : text(row.label, 240),
  };
}

function bindings(value: unknown): PromptBindings {
  const row = record(value);
  closed(row, ['characters', 'scenes', 'shots', 'assets']);
  return {
    characters: list(row.characters, PROMPT_BOUNDS.bindings, bindingRow),
    scenes: list(row.scenes, PROMPT_BOUNDS.bindings, bindingRow),
    shots: list(row.shots, PROMPT_BOUNDS.bindings, bindingRow),
    assets: list(row.assets, PROMPT_BOUNDS.bindings, bindingRow),
  };
}

function anomaly(value: unknown): PromptAnomaly {
  const row = record(value);
  if (!Object.hasOwn(row, 'kind')) promptInvalid();
  const kind = text(row.kind, 64, false);
  const detail = Object.entries(row)
    .filter(([key]) => key !== 'kind')
    .map(([key, item]) => `${key}=${typeof item === 'string' || typeof item === 'number' ? String(item) : '…'}`)
    .join(' ');
  return { kind, detail };
}

/** 一个家族条目。`head_asset_id` 是 library 的字段名，`asset_id` 属于回执。 */
export function promptEntry(value: unknown): PromptEntry {
  const row = record(value);
  closed(row, ['contract', 'family_id', 'head_asset_id', 'revision', 'asset_version', 'purpose',
    'origin', 'review_status', 'approved', 'redacted', 'body', 'bindings', 'unresolved_bindings',
    'reference_asset_ids', 'output_asset_ids', 'anomalies', 'versions', 'fields',
    'history_complete', 'read_complete'],
  ['used_by', 'schema_version', 'advisory_only', 'execution_authority', 'auto_modify']);
  const review = text(row.review_status, 16);
  if (review !== 'DRAFT' && review !== 'APPROVED') promptInvalid();
  const revision = count(row.revision);
  if (revision < 1) promptInvalid();
  return {
    familyId: identifier(row.family_id),
    headAssetId: identifier(row.head_asset_id),
    revision,
    assetVersion: optionalCount(row.asset_version),
    purpose: text(row.purpose, 32, false),
    origin: text(row.origin, 32, false),
    reviewStatus: review,
    approved: flag(row.approved),
    redacted: flag(row.redacted),
    body: promptBody(row.body),
    bindings: bindings(row.bindings),
    unresolvedBindings: stringList(row.unresolved_bindings, PROMPT_BOUNDS.bindings),
    referenceAssetIds: stringList(row.reference_asset_ids, PROMPT_BOUNDS.bindings),
    outputAssetIds: stringList(row.output_asset_ids, PROMPT_BOUNDS.bindings),
    anomalies: list(row.anomalies, PROMPT_BOUNDS.anomalies, anomaly),
    versions: list(row.versions, PROMPT_BOUNDS.versions, promptVersion),
    fields: list(row.fields, PROMPT_BOUNDS.fieldCount, promptField),
    historyComplete: flag(row.history_complete),
    readComplete: flag(row.read_complete),
  };
}

export function promptLibrary(value: unknown): PromptLibrary {
  const row = record(value);
  closed(row, ['contract', 'entries', 'prompt_count', 'revision_count', 'malformed', 'malformed_count',
    'conflicted', 'conflicted_count', 'scanned_assets', 'projected_families', 'returned', 'limit',
    'truncated', 'has_more', 'total_known', 'read_complete'],
  ['unknown_is_explicit', 'bible_index_supplied', 'schema_version', 'advisory_only',
    'execution_authority', 'auto_modify']);
  const entries = list(row.entries, PROMPT_BOUNDS.versions, promptEntry);
  const conflicted = list(row.conflicted, PROMPT_BOUNDS.versions, item => {
    const conf = record(item);
    closed(conf, ['asset_id', 'family_id', 'revision', 'request_id']);
    return { assetId: identifier(conf.asset_id), familyId: identifier(conf.family_id),
      revision: count(conf.revision) };
  });
  const promptCount = count(row.prompt_count);
  // 投影自洽性：条目数必须与计数一致，否则“计数”和“列表”会互相矛盾。
  if (promptCount !== entries.length) promptInvalid();
  if (count(row.projected_families) !== entries.length) promptInvalid();
  return {
    entries,
    promptCount,
    revisionCount: count(row.revision_count),
    malformedCount: count(row.malformed_count),
    conflicted,
    conflictedCount: count(row.conflicted_count),
    scannedAssets: count(row.scanned_assets),
    projectedFamilies: count(row.projected_families),
    limit: optionalCount(row.limit),
    truncated: flag(row.truncated),
    hasMore: flag(row.has_more),
    totalKnown: flag(row.total_known),
    readComplete: flag(row.read_complete),
  };
}

export function promptReceipt(value: unknown): PromptReceipt {
  const row = record(value);
  closed(row, ['family_id', 'asset_id', 'revision', 'asset_version', 'text_digest',
    'idempotent_replay', 'previous_asset_id', 'payload_digest']);
  const revision = count(row.revision);
  if (revision < 1) promptInvalid();
  return {
    familyId: identifier(row.family_id),
    assetId: identifier(row.asset_id),
    revision,
    assetVersion: optionalCount(row.asset_version),
    textDigest: text(row.text_digest, 128, false),
    idempotentReplay: flag(row.idempotent_replay),
    previousAssetId: optionalIdentifier(row.previous_asset_id),
  };
}
