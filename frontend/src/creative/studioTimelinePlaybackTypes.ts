import { ApiError } from '../api';
import type { ProductionJob } from './studioProductionClient';
import { checkedTimelineExportPreview, type TimelineExportPreview } from './studioTimelineExportTypes';
import type { StudioTimelineRow } from './studioTimelineTypes';

export type TimelinePlayback = { contract: 'studio-timeline-playback/1'; novel_id: string; branch_id: string | null;
  cache_key: string; request_id: string; job_id: string; export_preview: TimelineExportPreview; job: ProductionJob | null;
  cache_state: 'MISSING' | 'RECORDED'; playback_digest: string; model_called: false; automatic_replay: false; product_acceptance: 'LOCAL_REQUIRED' };
const hex = (value: unknown): value is string => typeof value === 'string' && /^[a-f0-9]{64}$/.test(value);
function invalid(): never { throw new ApiError({ status: 200, code: 'STUDIO_RESPONSE_INVALID', message: '播放缓存回执与原保存版本不一致，请读取核对，勿重复生成。' }); }
const canonical = (value: unknown): string => Array.isArray(value) ? `[${value.map(canonical).join(',')}]`
  : value !== null && typeof value === 'object' ? `{${Object.keys(value).sort().map(key => `${JSON.stringify(key)}:${canonical((value as Record<string, unknown>)[key])}`).join(',')}}`
    : JSON.stringify(value) ?? 'null';
export function checkedTimelinePlayback(value: unknown, source: StudioTimelineRow, decodeJob: (value: unknown) => ProductionJob,
  scope: { novelId: string; branchId: string | null }): TimelinePlayback {
  if (!value || typeof value !== 'object' || Array.isArray(value)) invalid();
  const row = value as Record<string, unknown>;
  if (Object.keys(row).some(key => !['contract', 'novel_id', 'branch_id', 'cache_key', 'request_id', 'job_id', 'export_preview', 'job', 'cache_state',
    'playback_digest', 'model_called', 'automatic_replay', 'product_acceptance'].includes(key))
    || row.contract !== 'studio-timeline-playback/1' || row.novel_id !== scope.novelId || row.branch_id !== scope.branchId
    || !hex(row.cache_key) || !hex(row.job_id) || !hex(row.playback_digest) || row.request_id !== `playback_${row.cache_key}`
    || row.model_called !== false || row.automatic_replay !== false || row.product_acceptance !== 'LOCAL_REQUIRED'
    || !['MISSING', 'RECORDED'].includes(String(row.cache_state)) || (row.cache_state === 'MISSING') !== (row.job === null)) invalid();
  const rawPreview = row.export_preview as Record<string, unknown> | undefined;
  const limits = rawPreview?.limits as { max_output_bytes?: number } | undefined;
  if (!limits || typeof limits.max_output_bytes !== 'number' || !Number.isSafeInteger(limits.max_output_bytes)) invalid();
  const video = Math.min(1500, Math.max(100, Math.floor((limits.max_output_bytes - 128000) * 8 / (source.timeline.duration_ms / 1000 * 1.10) / 1000) - 97));
  const preview = checkedTimelineExportPreview(row.export_preview, source,
    source.timeline.schema_version === 3 ? { preset: 'AUDIO_WAV_PCM16' }
      : { preset: 'DELIVERY_H264_MP4', video_bitrate_kbps: video, audio_bitrate_kbps: 96, crf: 28 });
  const job = row.job === null ? null : decodeJob(row.job);
  if (job && (job.owner !== 'timeline' || job.id !== row.job_id || job.request_id !== row.request_id || job.operation_id !== 'm9.timeline.multitrack'
    || canonical(job.timeline_snapshot) !== canonical(preview.timeline_snapshot)
    || canonical(job.sources) !== canonical(preview.sources)
    || canonical(job.execution_recipe) !== canonical(preview.execution_recipe))) invalid();
  return { ...row, export_preview: preview, job } as TimelinePlayback;
}

export function playbackJobMatches(job: ProductionJob, playback: TimelinePlayback): boolean {
  return job.owner === 'timeline' && job.id === playback.job_id && job.request_id === playback.request_id
    && canonical(job.timeline_snapshot) === canonical(playback.export_preview.timeline_snapshot)
    && canonical(job.sources) === canonical(playback.export_preview.sources)
    && canonical(job.execution_recipe) === canonical(playback.export_preview.execution_recipe);
}

/** Playback MIME is derived from the exact validated bound export recipe. */
export function timelinePlaybackMediaType(playback: TimelinePlayback): 'audio/wav' | 'video/mp4' {
  return playback.export_preview.export_profile.preset === 'AUDIO_WAV_PCM16' ? 'audio/wav' : 'video/mp4';
}
