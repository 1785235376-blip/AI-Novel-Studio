import { ApiError } from '../api';
import type { CreativeIntent, StudioPreferences, StudioPreferencesInput, WorkspacePreset } from './studioClient';

export const STUDIO_INTENTS: readonly [CreativeIntent, string][] = [['NOVEL_WRITING', '小说创作'], ['NOVEL_ADAPTATION', '小说改编'], ['AI_SHORT_FILM', '短片'], ['COMMERCIAL_CG', '商业 CG'], ['ADVERTISEMENT', '广告'], ['MUSIC_VIDEO', 'MV'], ['GAME_PREVIS', '游戏预演'], ['IMAGE_DESIGN', '图片设计'], ['PODCAST_VOICE', '播客 / 配音'], ['BLANK', '空白创作'], ['CUSTOM', '自定义']];
export const STUDIO_PRESETS: readonly [WorkspacePreset, string][] = [['BLANK', '空白'], ['TEXT', '文本'], ['IMAGE', '图片'], ['VIDEO', '视频'], ['AUDIO', '声音'], ['EDITING', '剪辑'], ['MIXED', '混合']];

/** The original preference DTO is a presentation hint, never an authority grant. */
export function checkedStudioPreferences(value: unknown): StudioPreferences {
  const invalid = (): never => { throw new ApiError({ status: 200, code: 'STUDIO_RESPONSE_INVALID', message: '服务返回的创作偏好不可用，请重新读取。' }); };
  if (!value || typeof value !== 'object' || Array.isArray(value)) invalid();
  const row = value as Record<string, unknown>;
  if (typeof row.version !== 'number' || !Number.isSafeInteger(row.version) || row.version < 0
    || !Array.isArray(row.intents) || row.intents.length > STUDIO_INTENTS.length
    || row.intents.some(item => !STUDIO_INTENTS.some(([id]) => id === item))
    || new Set(row.intents).size !== row.intents.length
    || !STUDIO_PRESETS.some(([id]) => id === row.preset)
    || typeof row.custom_intent !== 'string' || row.custom_intent.length > 240) invalid();
  return { version: row.version as number, intents: [...row.intents as CreativeIntent[]], preset: row.preset as WorkspacePreset, custom_intent: row.custom_intent as string };
}

export function preferenceInput(value: StudioPreferencesInput): StudioPreferencesInput {
  return { intents: [...value.intents], preset: value.preset, custom_intent: value.custom_intent };
}

export function samePreferenceInput(left: StudioPreferencesInput, right: StudioPreferencesInput): boolean {
  // The author chooses a set of intents; response ordering alone is not an edit.
  return left.preset === right.preset && left.custom_intent === right.custom_intent
    && left.intents.length === right.intents.length && left.intents.every(item => right.intents.includes(item));
}

export function preferenceSaveFailure(reason: unknown): 'CONFLICT' | 'UNKNOWN' | 'REJECTED' {
  if (reason instanceof ApiError) {
    if (reason.status === 409) return 'CONFLICT';
    if (reason.status === 0 || reason.status >= 500 || reason.problem.code === 'STUDIO_RESPONSE_INVALID') return 'UNKNOWN';
    return 'REJECTED';
  }
  // A canceled transport does not prove the server canceled its mutation.
  return 'UNKNOWN';
}
