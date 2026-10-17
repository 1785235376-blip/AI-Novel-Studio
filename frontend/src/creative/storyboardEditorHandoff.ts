import type { CreativeCapabilities, CreativeDocument } from './types';
import type { PlanningSnapshot } from './studioProductionGraphContract';

/** Session-only intent. Scalar pins, never document objects or persisted navigation. */
export type StoryboardEditorRequest = Readonly<{
  requestId: number;
  target: Readonly<PlanningSnapshot & { mode: 'STORYBOARD' }>;
  source: Readonly<PlanningSnapshot>;
}>;
export type OpenStoryboardEditor = (request: StoryboardEditorRequest, isOriginCurrent: () => boolean) => void;
export type PreparedStoryboardEditor = Readonly<{
  request: StoryboardEditorRequest;
  receipt: { document: CreativeDocument; document_digest: string };
  capabilities: CreativeCapabilities;
}>;
export type StoryboardEditorHost = {
  module: 'IMAGE' | 'VIDEO'; prepared: PreparedStoryboardEditor;
  isCurrent: () => boolean; returnLabel: string;
};
let requestSequence = 0;
const record = (v: unknown): v is Record<string, unknown> => !!v && typeof v === 'object' && !Array.isArray(v);
const strings = (v: unknown): v is string[] => Array.isArray(v) && v.every(x => typeof x === 'string');
const fields = (v: Record<string, unknown>, names: string[]) => names.every(key => typeof v[key] === 'string');
const rows = (v: unknown, check: (row: Record<string, unknown>) => boolean) => Array.isArray(v) && v.every(row => record(row) && check(row));
const unique = (v: unknown) => Array.isArray(v) && v.every(row => record(row) && typeof row.id === 'string' && !!row.id) && new Set(v.map(row => row.id)).size === v.length;
const dialogue = (v: unknown) => rows(v, row => fields(row, ['speaker', 'text', 'delivery']));
const optionalStrings = (v: Record<string, unknown>, names: string[]) => names.every(key => v[key] == null || typeof v[key] === 'string');
const planning = (v: unknown) => v == null || record(v) && fields(v, ['rationale', 'sequence_reason', 'duration_reason', 'uncertainty']) && strings(v.assumptions)
  && rows(v.alternatives, row => fields(row, ['choice', 'tradeoff']))
  && rows(v.evidence, row => fields(row, ['scene_id', 'field', 'excerpt']) && (row.dialogue_index == null || Number.isSafeInteger(row.dialogue_index)));
const visual = (v: unknown) => v == null || record(v) && fields(v, ['style', 'atmosphere', 'color', 'rhythm']) && strings(v.reference_works) && optionalStrings(v, ['genre']);
const continuity = (v: unknown) => v == null || record(v) && fields(v, ['characters', 'outfit', 'environment', 'camera']) && optionalStrings(v, ['previous_shot_id', 'next_shot_id', 'time', 'lighting']);
const notes = (v: unknown) => unique(v) && rows(v, row => fields(row, ['id', 'note', 'shot_size', 'camera_angle', 'camera_motion', 'emotion', 'pacing', 'performance']) && typeof row.duration_seconds === 'number' && Number.isFinite(row.duration_seconds) && planning(row.planning) && optionalStrings(row, ['shot_suggestion', 'composition', 'lens', 'character_state', 'lighting', 'color_palette', 'material', 'transition', 'scene_id', 'blocking']) && (row.number == null || Number.isSafeInteger(row.number)) && (row.performances == null || rows(row.performances, item => fields(item, ['character', 'action', 'expression', 'state']))));
export function validStoryboardDocument(v: unknown): v is CreativeDocument {
  if (!record(v) || v.mode !== 'STORYBOARD' || !fields(v, ['id', 'title', 'status', 'created_at', 'updated_at', 'actor_id']) || !v.id
    || !Number.isSafeInteger(v.version) || Number(v.version) < 1 || typeof v.source_independent !== 'boolean' || !strings(v.source_chapter_ids) || !record(v.source_evidence)) return false;
  return unique(v.scenes) && rows(v.scenes, row => fields(row, ['id', 'heading', 'time', 'location', 'action', 'emotion']) && Number.isSafeInteger(row.sequence) && strings(row.characters) && dialogue(row.dialogue) && notes(row.director_notes))
    && notes(v.director_notes) && unique(v.shots) && rows(v.shots, row => fields(row, ['id', 'scene_id', 'shot_size', 'camera_angle', 'camera_motion', 'frame_prompt', 'composition', 'color', 'action', 'sound_effect', 'lens', 'lighting', 'environment', 'sound']) && Number.isSafeInteger(row.number) && typeof row.duration_seconds === 'number' && Number.isFinite(row.duration_seconds) && dialogue(row.dialogue) && notes(row.director_notes) && (row.characters == null || strings(row.characters)) && (row.director_note_ids == null || strings(row.director_note_ids)) && optionalStrings(row, ['emotion', 'video_generation_hint']) && continuity(row.continuity))
    && visual(v.visual_target) && v.video_plan === null
    && (v.source_documents == null || record(v.source_documents) && Object.values(v.source_documents).every(binding => record(binding) && Number.isSafeInteger(binding.version) && Number(binding.version) > 0 && typeof binding.digest === 'string' && /^[a-f0-9]{64}$/.test(binding.digest)));
}
const pinValid = (pin: PlanningSnapshot) => !!pin && typeof pin.id === 'string' && !!pin.id && Number.isSafeInteger(pin.version) && pin.version > 0 && typeof pin.digest === 'string' && /^[a-f0-9]{64}$/.test(pin.digest);
export function storyboardEditorRequest(document: CreativeDocument, digest: string, source: PlanningSnapshot): StoryboardEditorRequest {
  const request = Object.freeze({ requestId: ++requestSequence, target: Object.freeze({ id: document.id, version: document.version, digest, mode: 'STORYBOARD' as const }), source: Object.freeze({ id: source.id, version: source.version, digest: source.digest }) });
  checkedStoryboardReceipt(request, { document, document_digest: digest });
  return request;
}
export function checkedStoryboardReceipt(request: StoryboardEditorRequest, value: unknown): CreativeDocument {
  if (!request || !Number.isSafeInteger(request.requestId) || request.requestId < 1 || !pinValid(request.target) || !pinValid(request.source) || request.target.mode !== 'STORYBOARD' || request.target.id === request.source.id
    || !record(value) || value.document_digest !== request.target.digest || !validStoryboardDocument(value.document)) throw new Error('分镜交接回执不完整，请重新核对原文档。');
  const row = value.document, binding = row.source_documents?.[request.source.id];
  if (row.id !== request.target.id || row.version !== request.target.version || !binding || binding.version !== request.source.version || binding.digest !== request.source.digest) throw new Error('分镜版本、摘要或导演来源已变化，未打开其他版本。');
  return row;
}
export function checkedStoryboardCapabilities(value: CreativeCapabilities) {
  if (!value || value.enabled !== true || value.can_mutate !== true || !Array.isArray(value.modes) || !value.modes.includes('STORYBOARD')) throw new Error('当前身份不可打开原分镜编辑器。');
}
function freeze<T>(value: T): T {
  if (value && typeof value === 'object') { Object.values(value).forEach(freeze); Object.freeze(value); }
  return value;
}
export function prepareStoryboardEditor(request: StoryboardEditorRequest, receipt: PreparedStoryboardEditor['receipt'], capabilities: CreativeCapabilities): PreparedStoryboardEditor {
  checkedStoryboardCapabilities(capabilities); checkedStoryboardReceipt(request, receipt);
  return freeze(structuredClone({ request, receipt, capabilities }));
}
