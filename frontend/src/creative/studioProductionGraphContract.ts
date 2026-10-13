import { ApiError } from '../api';
import type { CreativeInput, VisualTarget, CreativeShot } from './types';

export type PlanningSnapshot = { id: string; version: number; digest: string };
export type PlanningDocument = PlanningSnapshot & { title: string; mode: 'DIRECTOR' | 'STORYBOARD' };
export type PlanningProjection = { document_snapshot: PlanningSnapshot; content: CreativeInput };
export const productionGraphDefinitions = ['image_style', 'image_upscale', 'director_plan', 'storyboard_plan', 'storyboard_prompt'] as const;
const limits: Record<string, number> = { id: 240, scene_id: 240, shot_id: 240, title: 240, note: 8000, shot_suggestion: 8000, shot_size: 80,
  camera_angle: 80, camera_motion: 80, emotion: 4000, pacing: 2000, performance: 4000, blocking: 4000, composition: 4000, lens: 1000,
  character_state: 4000, color_palette: 2000, material: 4000, transition: 2000, heading: 500, time: 1000, location: 1000, action: 32000, frame_prompt: 16000, color: 2000,
  lighting: 4000, environment: 4000, sound: 4000, sound_effect: 4000, speaker: 240, text: 16000, delivery: 2000,
  character: 240, expression: 2000, state: 2000, style: 2000, atmosphere: 2000, rhythm: 2000 };
function invalid(input = false): never { throw new ApiError({ status: input ? 400 : 200, code: input ? 'STUDIO_GRAPH_INPUT_INVALID' : 'STUDIO_RESPONSE_INVALID', message: '导演或分镜数据不完整，请核对原文档版本。' }); }
function row(value: unknown, input = false): Record<string, unknown> { if (!value || typeof value !== 'object' || Array.isArray(value)) invalid(input); return value as Record<string, unknown>; }
function closed(value: Record<string, unknown>, required: string[], optional: string[] = [], input = false) {
  if (required.some(key => !Object.hasOwn(value, key)) || Object.keys(value).some(key => !required.includes(key) && !optional.includes(key))) invalid(input);
}
function string(value: unknown, maximum: number, empty = true, input = false): string {
  if (typeof value !== 'string' || value.length > maximum || !empty && !value.trim() || /[\u0000\u007f]/.test(value)) invalid(input); return value;
}
function integer(value: unknown, minimum: number, maximum: number, input = false) { if (typeof value !== 'number' || !Number.isSafeInteger(value) || value < minimum || value > maximum) invalid(input); return value; }
function array(value: unknown, maximum: number) { if (!Array.isArray(value) || value.length > maximum) invalid(); return value; }
function strings(value: unknown, maximum: number, length = 240, unique = true) { const result = array(value, maximum).map(value => string(value, length, false)); if (unique && new Set(result).size !== result.length) invalid(); return result; }
function fields(value: Record<string, unknown>, keys: string[]) { for (const key of keys) string(value[key], limits[key], !['id', 'scene_id', 'shot_id', 'title', 'heading', 'speaker', 'text', 'character'].includes(key)); }
export function checkedPlanningSnapshot(value: unknown, input = false): PlanningSnapshot {
  const record = row(value, input); closed(record, ['id', 'version', 'digest'], [], input);
  const id = string(record.id, 240, false, input); if (/[\u0000-\u001f\u007f]/.test(id) || typeof record.digest !== 'string' || !/^[a-f0-9]{64}$/.test(record.digest)) invalid(input);
  return { id, version: integer(record.version, 1, Number.MAX_SAFE_INTEGER, input), digest: record.digest };
}
export function checkedPlanningDocument(value: unknown): PlanningDocument {
  const record = row(value); closed(record, ['id', 'version', 'digest', 'title', 'mode']);
  if (record.mode !== 'DIRECTOR' && record.mode !== 'STORYBOARD') invalid();
  return { ...checkedPlanningSnapshot({ id: record.id, version: record.version, digest: record.digest }), title: string(record.title, 240, false), mode: record.mode };
}
export function checkedVisualTarget(value: unknown): VisualTarget {
  const record = row(value); closed(record, ['style', 'atmosphere', 'reference_works', 'color', 'rhythm']); fields(record, ['style', 'atmosphere', 'color', 'rhythm']);
  array(record.reference_works, 20).forEach(value => string(value, 1000, false)); return record as VisualTarget;
}
function dialogue(value: unknown) { const record = row(value); closed(record, ['speaker', 'text', 'delivery']); fields(record, ['speaker', 'text', 'delivery']); }
function note(value: unknown, ordered = false) {
  const record = row(value), required = ['id', 'note', 'shot_size', 'camera_angle', 'camera_motion', 'duration_seconds', 'emotion', 'pacing', 'performance', 'blocking', ...(ordered ? ['number', 'scene_id'] : [])];
  closed(record, required, ['shot_suggestion', 'composition', 'lens', 'character_state', 'performances', 'lighting', 'color_palette', 'material', 'transition']);
  fields(record, required.filter(key => !['duration_seconds', 'number'].includes(key))); integer(record.duration_seconds, 1, 600);
  string(record.emotion, 2000);
  if (ordered) integer(record.number, 1, 10000);
  for (const key of ['shot_suggestion', 'composition', 'lens', 'character_state', 'lighting', 'color_palette', 'material', 'transition']) if (record[key] != null) string(record[key], limits[key]);
  if (record.performances != null) {
    const actors = array(record.performances, 100).map(value => { const actor = row(value); closed(actor, ['character', 'action', 'expression', 'state']); fields(actor, ['character', 'action', 'expression', 'state']); string(actor.action, 4000); return actor.character; });
    if (new Set(actors).size !== actors.length) invalid();
  }
  return record;
}
export function checkedCreativeShot(value: unknown): CreativeShot {
    const shot = row(value); const required = ['id', 'number', 'scene_id', 'shot_size', 'camera_angle', 'camera_motion', 'duration_seconds', 'frame_prompt', 'composition', 'lens', 'lighting', 'environment', 'sound', 'color', 'action', 'dialogue', 'sound_effect', 'director_notes'];
    closed(shot, required, ['characters', 'emotion', 'continuity', 'director_note_ids']); fields(shot, required.filter(key => !['number', 'duration_seconds', 'dialogue', 'director_notes'].includes(key)));
    string(shot.action, 16000); integer(shot.number, 1, 10000); integer(shot.duration_seconds, 1, 600);
    if (shot.characters != null) strings(shot.characters, 100); if (shot.emotion != null) string(shot.emotion, 4000);
    array(shot.dialogue, 200).forEach(dialogue); array(shot.director_notes, 100).forEach(value => note(value)); if (shot.director_note_ids != null) strings(shot.director_note_ids, 100);
    if (shot.continuity != null) { const continuity = row(shot.continuity); closed(continuity, ['characters', 'outfit', 'environment', 'camera'], ['previous_shot_id', 'next_shot_id']);
      for (const key of ['characters', 'outfit', 'environment', 'camera']) string(continuity[key], 4000);
      for (const key of ['previous_shot_id', 'next_shot_id']) if (continuity[key] != null && string(continuity[key], 240, false) === shot.id) invalid(); }
    return shot as CreativeShot;
}
/** The graph projects the original closed document DTO, never an arbitrary payload. */
export function checkedPlanningProjection(value: unknown, mode: 'DIRECTOR' | 'STORYBOARD'): PlanningProjection {
  const record = row(value); closed(record, ['document_snapshot', 'content']); const snapshot = checkedPlanningSnapshot(record.document_snapshot), content = row(record.content);
  closed(content, ['mode', 'title', 'source_chapter_ids', 'source_independent', 'scenes', 'director_notes', 'shots', 'video_plan'], ['script', 'visual_target']);
  if (content.mode !== mode || typeof content.source_independent !== 'boolean' || content.video_plan !== null || content.script != null) invalid();
  string(content.title, 240, false); const chapters = strings(content.source_chapter_ids, 64);
  if (content.visual_target != null) checkedVisualTarget(content.visual_target);
  const scenes = array(content.scenes, 200).map(value => {
    const scene = row(value); closed(scene, ['id', 'sequence', 'source_chapter_id', 'heading', 'time', 'location', 'characters', 'action', 'dialogue', 'emotion', 'director_notes']);
    fields(scene, ['id', 'heading', 'time', 'location', 'action', 'emotion']); integer(scene.sequence, 1, 10000); strings(scene.characters, 100, 240, false);
    if (scene.source_chapter_id !== null && !chapters.includes(string(scene.source_chapter_id, 240, false))) invalid();
    array(scene.dialogue, 200).forEach(dialogue); array(scene.director_notes, 100).forEach(value => note(value)); return scene;
  });
  const notes = array(content.director_notes, 200).map(value => note(value, true));
  const shots = array(content.shots, 200).map(checkedCreativeShot);
  for (const [rows, number] of [[scenes, 'sequence'], [notes, 'number'], [shots, 'number']] as const) {
    if (new Set(rows.map(row => row.id)).size !== rows.length || new Set(rows.map(row => (row as unknown as Record<string, unknown>)[number])).size !== rows.length) invalid();
  }
  if (shots.some(shot => [shot.continuity?.previous_shot_id, shot.continuity?.next_shot_id].some(id => id != null && !shots.some(other => other.id === id)))) invalid();
  if ([...shots, ...notes].some(row => !scenes.some(scene => scene.id === row.scene_id)) || mode === 'DIRECTOR' && shots.length) invalid();
  return { document_snapshot: snapshot, content: content as CreativeInput };
}
