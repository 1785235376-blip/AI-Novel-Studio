import { ApiError } from '../api';
import type { ProductionRecipe } from './studioProductionClient';
import { checkedTimeline, timelineSources, type StudioTimelineRow, type StudioTimelineSource } from './studioTimelineTypes';

export type TimelineExportPreset = 'REVIEW_MP4' | 'DELIVERY_H264_MP4' | 'DELIVERY_VP9_WEBM';
export type TimelineExportProfile = { preset: TimelineExportPreset; video_bitrate_kbps?: number; audio_bitrate_kbps?: number; crf?: number };
export type TimelineExportInput = { expected_version: number; reviewed_timeline_digest: string; export_profile: TimelineExportProfile };
export type TimelineExportPreview = { contract: 'studio-timeline-export-preview/1'; timeline_snapshot: { id: string; version: number; digest: string };
  export_profile: TimelineExportProfile; sources: StudioTimelineSource[]; execution_recipe: ProductionRecipe;
  limits: { max_output_bytes: number; render_timeout_seconds: number }; preview_digest: string; model_called: false;
  automatic_replay: false; product_acceptance: 'LOCAL_REQUIRED' };

export const timelineExportPresets: TimelineExportPreset[] = ['REVIEW_MP4', 'DELIVERY_H264_MP4', 'DELIVERY_VP9_WEBM'];
export function checkedTimelineExportProfile(value: unknown): TimelineExportProfile {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('请明确选择导出配置。');
  const row = value as Record<string, unknown>;
  if (!timelineExportPresets.includes(row.preset as TimelineExportPreset) || Object.keys(row).some(key => !['preset', 'video_bitrate_kbps', 'audio_bitrate_kbps', 'crf'].includes(key))) throw new Error('导出配置字段无效。');
  if (row.preset === 'REVIEW_MP4') {
    if (Object.keys(row).some(key => key !== 'preset')) throw new Error('审核 MP4 使用原渲染配置，不接受交付编码参数。');
    return { preset: 'REVIEW_MP4' };
  }
  const vp9 = row.preset === 'DELIVERY_VP9_WEBM';
  const number = (key: string, fallback: number, min: number, max: number) => {
    const result = key in row ? row[key] : fallback;
    if (typeof result !== 'number' || !Number.isSafeInteger(result) || result < min || result > max) throw new Error(`导出参数 ${key} 需要是 ${min} 至 ${max} 的整数。`);
    return result;
  };
  return { preset: row.preset as TimelineExportPreset, video_bitrate_kbps: number('video_bitrate_kbps', vp9 ? 2000 : 4000, 100, 20000),
    audio_bitrate_kbps: number('audio_bitrate_kbps', vp9 ? 128 : 192, 32, 320), crf: number('crf', vp9 ? 30 : 20, 0, vp9 ? 63 : 51) };
}
export const timelineExportKey = (profile: TimelineExportProfile) => JSON.stringify(checkedTimelineExportProfile(profile));
export function checkedTimelineExportPreview(value: unknown, source: StudioTimelineRow, profile: TimelineExportProfile): TimelineExportPreview {
  function invalid(): never { throw new ApiError({ status: 200, code: 'STUDIO_RESPONSE_INVALID', message: '导出预览与确认的时间线、素材或配置不一致，请重新读取核对。' }); }
  if (!value || typeof value !== 'object' || Array.isArray(value)) invalid();
  const row = value as Record<string, unknown>, snapshot = row.timeline_snapshot as Record<string, unknown> | null;
  const limits = row.limits as Record<string, unknown> | null, expectedSources = timelineSources(source.timeline);
  if (Object.keys(row).some(key => !['contract', 'timeline_snapshot', 'export_profile', 'sources', 'execution_recipe', 'limits', 'preview_digest', 'model_called', 'automatic_replay', 'product_acceptance'].includes(key))
    || row.contract !== 'studio-timeline-export-preview/1' || typeof row.preview_digest !== 'string' || !/^[a-f0-9]{64}$/.test(row.preview_digest)
    || row.model_called !== false || row.automatic_replay !== false || row.product_acceptance !== 'LOCAL_REQUIRED'
    || !snapshot || Array.isArray(snapshot) || Object.keys(snapshot).some(key => !['id', 'version', 'digest'].includes(key))
    || snapshot.id !== source.id || snapshot.version !== source.version || snapshot.digest !== source.timeline_digest
    || !limits || Array.isArray(limits) || Object.keys(limits).some(key => !['max_output_bytes', 'render_timeout_seconds'].includes(key))
    || ![limits.max_output_bytes, limits.render_timeout_seconds].every(field => typeof field === 'number' && Number.isSafeInteger(field) && field > 0)
    || (typeof limits.max_output_bytes === 'number' && limits.max_output_bytes > 25 * 1024 * 1024) || limits.render_timeout_seconds !== 120
    || !Array.isArray(row.sources) || row.sources.length !== expectedSources.length || row.sources.some((raw, index) => {
      if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return true;
      const actual = raw as Record<string, unknown>, expected = expectedSources[index];
      return Object.keys(actual).some(key => !['id', 'kind', 'asset_kind', 'version', 'digest'].includes(key))
        || ['id', 'kind', 'asset_kind', 'version', 'digest'].some(key => actual[key] !== expected[key as keyof StudioTimelineSource]);
    })) invalid();
  let normalized: TimelineExportProfile;
  try { normalized = checkedTimelineExportProfile(row.export_profile); if (timelineExportKey(normalized) !== timelineExportKey(profile)) invalid(); }
  catch { return invalid(); }
  const recipe = row.execution_recipe as Record<string, unknown> | null;
  if (!recipe || typeof recipe !== 'object' || Array.isArray(recipe) || Object.keys(recipe).some(key => !['contract', 'operation_id', 'adapter', 'output_profile', 'timeline', 'export_profile', 'automatic_fallback', 'recipe_digest'].includes(key))
    || recipe.contract !== 'studio-execution-recipe/1' || recipe.operation_id !== 'm9.timeline.multitrack' || recipe.adapter !== 'LOCAL_FFMPEG'
    || recipe.output_profile !== normalized.preset || recipe.automatic_fallback !== false || typeof recipe.recipe_digest !== 'string' || !/^[a-f0-9]{64}$/.test(recipe.recipe_digest)
    || JSON.stringify(recipe).length > 131072) invalid();
  try {
    if (timelineExportKey(checkedTimelineExportProfile(recipe.export_profile)) !== timelineExportKey(normalized)
      || JSON.stringify(checkedTimeline(recipe.timeline)) !== JSON.stringify(checkedTimeline(source.timeline))) invalid();
  } catch { return invalid(); }
  return { ...row, export_profile: normalized } as unknown as TimelineExportPreview;
}
