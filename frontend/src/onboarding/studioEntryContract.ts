import { ApiError } from '../api';
import {
  STUDIO_ENTRY_CONTRACT, STUDIO_ENTRY_ERROR_CODES, STUDIO_INTENT_CATALOG, STUDIO_INTENT_IDS,
  STUDIO_INTENT_STORAGE_LIMIT, type StudioEntryIntent, type StudioEntryProject, type StudioIntentDraft,
  type StudioIntentValue,
} from './studioEntryTypes';
import {
  PRODUCTION_WORKFLOW_BOUNDS, PRODUCTION_WORKFLOW_INTENT_ID, PRODUCTION_WORKFLOW_PRESETS,
  type ProductionWorkflowPreset,
} from '../production/productionWorkflowTypes';

/**
 * Never trust a returned row: an unknown key, unbounded text, a control character, a
 * duplicated intent identifier, an out-of-range version or a foreign project is a
 * refused read. The incoming request is validated by the same vocabulary before it
 * leaves the client, so a locally impossible body never reaches the owner.
 */
function invalid(): never {
  throw new ApiError({ status: 200, code: STUDIO_ENTRY_ERROR_CODES.responseInvalid, message: STUDIO_ENTRY_CONTRACT.messages.response_invalid });
}
function mismatch(): never {
  throw new ApiError({ status: 403, code: STUDIO_ENTRY_ERROR_CODES.scopeMismatch, message: STUDIO_ENTRY_CONTRACT.messages.scope_mismatch });
}
function object(value: unknown, allowed: readonly string[]): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) invalid();
  const row = value as Record<string, unknown>;
  if (Object.keys(row).some(key => !allowed.includes(key))) invalid();
  return row;
}
function text(value: unknown, maximum: number): string {
  if (typeof value !== 'string' || !value.trim() || value.length > maximum || /[\u0000-\u001f\u007f]/.test(value)) invalid();
  return value;
}
function optionalText(value: unknown, maximum: number): string | null {
  if (value === undefined || value === null) return null;
  return text(value, maximum);
}
function integer(value: unknown, maximum = Number.MAX_SAFE_INTEGER): number {
  if (typeof value !== 'number' || !Number.isSafeInteger(value) || value < 0 || value > maximum) invalid();
  return value;
}
function bool(value: unknown): boolean {
  if (typeof value !== 'boolean') invalid();
  return value;
}
function list(value: unknown, maximum: number): unknown[] {
  if (!Array.isArray(value) || value.length > maximum) invalid();
  return value;
}
/** An owner timestamp is accepted only in the exact UTC shape the other owners emit. */
function timestamp(value: unknown, maximum: number): string {
  const stamp = text(value, maximum);
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?(?:Z|\+00:00)$/.test(stamp) || Number.isNaN(Date.parse(stamp))) invalid();
  return stamp;
}
function optionalTimestamp(value: unknown): string | null {
  if (value === undefined || value === null) return null;
  return timestamp(value, STUDIO_ENTRY_CONTRACT.bounds.timestamp);
}
function intentId(value: unknown): string {
  if (typeof value !== 'string' || !PRODUCTION_WORKFLOW_INTENT_ID.test(value)) invalid();
  return value;
}
function preset(value: unknown): ProductionWorkflowPreset | null {
  if (value === undefined || value === null) return null;
  if (typeof value !== 'string') invalid();
  const upper = value.toUpperCase();
  if (!(PRODUCTION_WORKFLOW_PRESETS as readonly string[]).includes(upper)) invalid();
  return upper as ProductionWorkflowPreset;
}
/** One declared project id, bounded and never a path, a query or a traversal. */
function projectId(value: unknown): string {
  const id = text(value, STUDIO_ENTRY_CONTRACT.bounds.project_id);
  if (!/^[A-Za-z0-9][A-Za-z0-9._-]*$/.test(id)) invalid();
  return id;
}

/**
 * `GET /api/novels` rows, restricted to the fields this entry needs. The owner returns
 * more than the entry renders; every accepted extra field is bounded here.
 */
export function studioEntryProjects(value: unknown): StudioEntryProject[] {
  return list(value, 2000).map(item => {
    const row = object(item, ['id', 'title', 'updated_at', 'updated', 'entry_kind', 'genre', 'status']);
    // `updated_at` is preferred; the owner's shorter `updated` alias is accepted unchanged.
    const stamp = row.updated_at === undefined ? optionalTimestamp(row.updated) : optionalTimestamp(row.updated_at);
    return {
      id: projectId(row.id), title: text(row.title, STUDIO_ENTRY_CONTRACT.bounds.title),
      updated_at: stamp,
      entry_kind: optionalText(row.entry_kind, STUDIO_ENTRY_CONTRACT.bounds.entry_kind),
      genre: optionalText(row.genre, STUDIO_ENTRY_CONTRACT.bounds.genre),
      status: optionalText(row.status, STUDIO_ENTRY_CONTRACT.bounds.status),
    };
  });
}

/** One `creative_intent.values[]` entry. The wire `custom` marker is accepted but never re-sent. */
function intentValues(value: unknown): StudioIntentValue[] {
  const values = list(value, STUDIO_INTENT_STORAGE_LIMIT).map(item => {
    const row = object(item, ['intent_id', 'label', 'selected', 'custom']);
    return {
      intent_id: intentId(row.intent_id), label: text(row.label, STUDIO_ENTRY_CONTRACT.bounds.label),
      selected: bool(row.selected), custom: bool(row.custom),
    };
  });
  if (new Set(values.map(item => item.intent_id)).size !== values.length) invalid();
  return values;
}

/**
 * The entry projection of the saved intent, mirroring the Phase 7 `creative_intent` shape.
 * A foreign project id or a foreign captured scope is a refused read, never a second project.
 */
export function studioIntentState(value: unknown, scopeProjectId: string, expectedScope?: { project_id?: string | null }): StudioEntryIntent {
  if (typeof scopeProjectId !== 'string' || !scopeProjectId) invalid();
  if (expectedScope?.project_id !== undefined && expectedScope.project_id !== null && expectedScope.project_id !== scopeProjectId) mismatch();
  const row = object(value, ['version', 'preset', 'values', 'editable', 'history_retained']);
  if (row.editable !== true || row.history_retained !== true) invalid();
  return {
    version: integer(row.version), preset: preset(row.preset), values: intentValues(row.values),
    editable: true, history_retained: true,
  };
}

/**
 * The outgoing replacement: `{expected_version, values[], preset?}` with bound strings, the
 * owner's identifier grammar and NO `note` field (the owner refuses an unknown key with 422).
 */
export function studioIntentRequest(value: unknown): StudioIntentDraft {
  const row = object(value, ['expected_version', 'values', 'preset']);
  const values = list(row.values, STUDIO_INTENT_STORAGE_LIMIT).map(item => {
    const entry = object(item, ['intent_id', 'label', 'selected']);
    return {
      intent_id: intentId(entry.intent_id), label: text(entry.label, STUDIO_ENTRY_CONTRACT.bounds.label),
      selected: bool(entry.selected),
    };
  });
  if (new Set(values.map(item => item.intent_id)).size !== values.length) invalid();
  if (values.length > STUDIO_INTENT_IDS.length || values.some(item => !STUDIO_INTENT_IDS.includes(item.intent_id))) invalid();
  const request: StudioIntentDraft = { expected_version: integer(row.expected_version), values };
  if (row.preset !== undefined) request.preset = preset(row.preset);
  return request;
}

/** One created project row, with the owner's own entry acknowledgement when it is present. */
export function studioProjectCreation(value: unknown): { id: string; title: string; studio_ready: boolean | null; requires_scope_selection: boolean | null } {
  const row = object(value, ['id', 'title', 'studio_ready', 'requires_scope_selection']);
  return {
    id: projectId(row.id), title: text(row.title, STUDIO_ENTRY_CONTRACT.bounds.title),
    studio_ready: row.studio_ready === undefined ? null : bool(row.studio_ready),
    requires_scope_selection: row.requires_scope_selection === undefined ? null : bool(row.requires_scope_selection),
  };
}

/** The bounded label of one catalog entry, used only for a locally built custom entry. */
export function studioIntentLabel(intentId_: string): string {
  const entry = STUDIO_INTENT_CATALOG.find(item => item.intent_id === intentId_);
  if (!entry) invalid();
  return entry.label.slice(0, PRODUCTION_WORKFLOW_BOUNDS.label);
}
