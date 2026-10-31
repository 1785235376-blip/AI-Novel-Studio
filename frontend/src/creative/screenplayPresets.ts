import { newDocument, newScene, type CreativeInput } from './types';

export const SCREENPLAY_PRESET_IDS = ['FEATURE_FILM', 'SHORT_FILM', 'ANIMATION', 'ADVERTISEMENT'] as const;
export type ScreenplayPreset = { id: typeof SCREENPLAY_PRESET_IDS[number]; version: 1; title: string; description: string; document: CreativeInput };
export type ScreenplayPresetCatalog = { schema_version: 1; templates: ScreenplayPreset[] };
const invalid = () => new Error('起稿模板目录的版本或结构不可用，请重新读取。');
const object = (v: unknown): v is Record<string, unknown> => !!v && typeof v === 'object' && !Array.isArray(v);
const text = (v: unknown, max: number, required = false): v is string => typeof v === 'string' && v.length <= max && (!required || !!v.trim());
const empty = (v: unknown) => Array.isArray(v) && v.length === 0;
const keys = (v: Record<string, unknown>, allowed: string[]) => Object.keys(v).length === allowed.length && allowed.every(k => Object.hasOwn(v, k));
function validPreset(value: unknown): value is ScreenplayPreset {
  if (!object(value) || !keys(value, ['id', 'version', 'title', 'description', 'document']) || !SCREENPLAY_PRESET_IDS.includes(value.id as ScreenplayPreset['id']) || value.version !== 1 || !text(value.title, 80, true) || !text(value.description, 400, true)) return false;
  const d = value.document;
  if (!object(d) || !keys(d, ['mode', 'title', 'source_chapter_ids', 'source_independent', 'scenes', 'director_notes', 'shots', 'video_plan', 'script']) || d.mode !== 'SCREENPLAY' || d.title !== value.title || d.source_independent !== true || !empty(d.source_chapter_ids) || !empty(d.director_notes) || !empty(d.shots) || d.video_plan !== null || d.script !== null || !Array.isArray(d.scenes) || !d.scenes.length || d.scenes.length > 12) return false;
  const ids = new Set<string>();
  return d.scenes.every((s, i) => {
    if (!object(s) || !keys(s, ['id', 'sequence', 'source_chapter_id', 'heading', 'time', 'location', 'characters', 'action', 'dialogue', 'emotion', 'director_notes']) || !text(s.id, 240, true) || ids.has(s.id) || s.sequence !== i + 1 || s.source_chapter_id !== null || !text(s.heading, 500, true) || !text(s.action, 32000, true) || !text(s.time, 1000) || !text(s.location, 1000) || !text(s.emotion, 4000) || !empty(s.characters) || !empty(s.dialogue) || !empty(s.director_notes)) return false;
    ids.add(s.id); return true;
  });
}
export function parseScreenplayPresets(value: unknown): ScreenplayPresetCatalog {
  if (!object(value) || !keys(value, ['schema_version', 'templates']) || value.schema_version !== 1 || !Array.isArray(value.templates) || value.templates.length !== SCREENPLAY_PRESET_IDS.length || !value.templates.every((p, i) => validPreset(p) && p.id === SCREENPLAY_PRESET_IDS[i])) throw invalid();
  return structuredClone(value) as ScreenplayPresetCatalog;
}
/** Only explicit user use creates fresh local IDs; reading/previewing has no side effect. */
export function instantiateScreenplayPreset(preset: ScreenplayPreset): CreativeInput {
  if (!validPreset(preset)) throw invalid();
  return { ...newDocument('SCREENPLAY'), title: preset.title, source_independent: true,
    scenes: preset.document.scenes.map((s, i) => ({ ...newScene(i + 1), heading: s.heading, action: s.action, time: s.time, location: s.location, emotion: s.emotion })) };
}
