import { graphDraftIncarnation, studioGraphDraftKey, type StudioGraphDraftOwner } from './studioGraphLocalDraft';
import type { CreativeInput, CreativeDocument } from './types';
import type { PlanningSnapshot } from './studioProductionGraphContract';

export type DirectorAuthorLocalDraft = {
  schema_version: 1; owner: StudioGraphDraftOwner; saved_at: string;
  base: { id: string; version: number; digest?: string } | null;
  draft: CreativeInput; uncertain: boolean;
};
const LIMIT = 2 * 1024 * 1024;
const invalid = (): never => { throw new Error('导演本机草稿格式无效或超出恢复上限；未覆盖缓存。'); };
const object = (v: unknown): Record<string, unknown> => { if (!v || typeof v !== 'object' || Array.isArray(v)) invalid(); return v as Record<string, unknown>; };
type Check = (v: unknown) => unknown;
const text: Check = v => typeof v === 'string' && v.length <= 128_000 ? v : invalid();
const number: Check = v => typeof v === 'number' && Number.isFinite(v) ? v : invalid();
const bool: Check = v => typeof v === 'boolean' ? v : invalid();
const nullable = (check: Check): Check => v => v === null ? null : check(v);
const list = (check: Check): Check => v => Array.isArray(v) && v.length <= 200 ? v.map(check) : invalid();
/** Closed structural author DTO, deliberately permits incomplete/IME author values.
 * This is not server validation, a saved document, or execution authority. */
const shape = (fields: Record<string, Check>, optional: string[] = []): Check => v => {
  const row = object(v);
  if (Object.keys(row).some(k => !Object.hasOwn(fields, k)) || Object.keys(fields).some(k => !optional.includes(k) && !Object.hasOwn(row, k))) invalid();
  return Object.fromEntries(Object.keys(row).map(k => [k, fields[k](row[k])]));
};
const strings = list(text), point = shape({ x: number, y: number });
const camera = shape({ scene_purpose: text, viewpoint: text, shot_function: text, focus_intent: text, screen_direction: text,
  coordinate_system: text, character_positions: v => {
    const row = object(v); if (Object.keys(row).length > 30 || Object.keys(row).some(k => !k || k.length > 240 || ['__proto__', 'constructor', 'prototype'].includes(k))) invalid();
    return Object.fromEntries(Object.entries(row).map(([k, p]) => [k, point(p)]));
  }, axis: strings, camera_position: nullable(point), subject_movement: nullable(shape({ start: point, end: point })),
  intentional_axis_crossing: bool, intentions: strings, override_reason: text });
const planning = shape({ rationale: text, sequence_reason: text, duration_reason: text, uncertainty: text, assumptions: strings,
  alternatives: list(shape({ choice: text, tradeoff: text })), evidence: list(shape({ scene_id: text, field: text, dialogue_index: nullable(number), excerpt: text })) });
const noteFields = { id: text, note: text, shot_size: text, camera_angle: text, camera_motion: text, duration_seconds: number,
  emotion: text, pacing: text, performance: text, blocking: text, camera_grammar: nullable(camera), planning: nullable(planning),
  shot_suggestion: nullable(text), composition: nullable(text), lens: nullable(text), character_state: nullable(text),
  performances: nullable(list(shape({ character: text, action: text, expression: text, state: text }))), lighting: nullable(text),
  color_palette: nullable(text), material: nullable(text), transition: nullable(text) };
const optionalNotes = ['blocking', 'camera_grammar', 'planning', 'shot_suggestion', 'composition', 'lens', 'character_state', 'performances', 'lighting', 'color_palette', 'material', 'transition'];
const note = shape(noteFields, optionalNotes);
const scene = shape({ id: text, sequence: number, source_chapter_id: nullable(text), heading: text, time: text, location: text,
  characters: strings, action: text, dialogue: list(shape({ speaker: text, text, delivery: text })), emotion: text, director_notes: list(note) });
const visual = shape({ style: text, atmosphere: text, reference_works: strings, color: text, rhythm: text, genre: nullable(text),
  target_audience: nullable(text), target_platform: nullable(text), production_budget_constraints: nullable(text) },
  ['genre', 'target_audience', 'target_platform', 'production_budget_constraints']);
const author = shape({ mode: v => v === 'DIRECTOR' ? v : invalid(), title: text, source_chapter_ids: strings, source_independent: bool,
  scenes: list(scene), director_notes: list(shape({ ...noteFields, number, scene_id: text }, optionalNotes)),
  shots: v => Array.isArray(v) && !v.length ? [] : invalid(), video_plan: v => v === null ? null : invalid(),
  script: v => v === null ? null : invalid(), visual_target: nullable(visual) }, ['script', 'visual_target']);
export function checkedDirectorAuthorInput(v: unknown): CreativeInput { return author(v) as CreativeInput; }
const id = (v: unknown): v is string => typeof v === 'string' && !!v && v.length <= 240 && !/[\u0000-\u001f\u007f]/.test(v);
export function directorAuthorDraftKey(owner: StudioGraphDraftOwner): string {
  const keys = ['projectId', 'incarnation', 'actorId', 'actorWorkspaceId', 'mode', 'workspaceId', 'storylineId', 'branchId'];
  if (Object.keys(owner).some(k => !keys.includes(k)) || !id(owner.projectId) || !id(owner.actorId) || !graphDraftIncarnation(owner.incarnation)
    || !['local', 'collaboration'].includes(owner.mode) || keys.some(k => typeof (owner as unknown as Record<string, unknown>)[k] !== 'string')) invalid();
  if (owner.mode === 'collaboration' && (![owner.actorWorkspaceId, owner.workspaceId, owner.storylineId, owner.branchId].every(id) || owner.actorWorkspaceId !== owner.workspaceId)) invalid();
  if (owner.mode === 'local' && [owner.actorWorkspaceId, owner.workspaceId, owner.storylineId, owner.branchId].some(Boolean)) invalid();
  return `studio-director-author:v1:${studioGraphDraftKey(owner)}`;
}
export function encodeDirectorAuthorDraft(owner: StudioGraphDraftOwner, draft: CreativeInput, base: CreativeDocument | undefined, pin: PlanningSnapshot | undefined, uncertain: boolean): string {
  const value: DirectorAuthorLocalDraft = { schema_version: 1, owner, saved_at: new Date().toISOString(), uncertain,
    base: base ? { id: base.id, version: base.version, ...(pin?.id === base.id && pin.version === base.version ? { digest: pin.digest } : {}) } : null,
    draft: checkedDirectorAuthorInput(draft) };
  const raw = JSON.stringify(value); readDirectorAuthorDraft(raw, owner); return raw;
}
export function readDirectorAuthorDraft(raw: string, owner: StudioGraphDraftOwner): DirectorAuthorLocalDraft {
  if (raw.length > LIMIT || new TextEncoder().encode(raw).byteLength > LIMIT) invalid();
  const row = object(JSON.parse(raw));
  if (Object.keys(row).sort().join() !== ['schema_version', 'owner', 'saved_at', 'base', 'draft', 'uncertain'].sort().join()
    || row.schema_version !== 1 || directorAuthorDraftKey(object(row.owner) as StudioGraphDraftOwner) !== directorAuthorDraftKey(owner)
    || typeof row.uncertain !== 'boolean' || typeof row.saved_at !== 'string' || !Number.isFinite(Date.parse(row.saved_at))) invalid();
  let base: DirectorAuthorLocalDraft['base'] = null;
  if (row.base !== null) {
    const b = object(row.base);
    if (Object.keys(b).some(k => !['id', 'version', 'digest'].includes(k)) || !id(b.id) || !Number.isSafeInteger(b.version) || (b.version as number) < 1
      || b.digest !== undefined && (typeof b.digest !== 'string' || !/^[a-f0-9]{64}$/.test(b.digest))) invalid();
    base = { id: b.id as string, version: b.version as number, ...(b.digest ? { digest: b.digest as string } : {}) };
  }
  return { schema_version: 1, owner: { ...owner }, saved_at: row.saved_at as string, uncertain: row.uncertain as boolean, base, draft: checkedDirectorAuthorInput(row.draft) };
}
