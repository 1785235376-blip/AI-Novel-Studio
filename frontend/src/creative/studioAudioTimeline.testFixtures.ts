import { createHash } from 'node:crypto';
import type { StudioAsset } from './studioClient';
import type { ProductionJob } from './studioProductionClient';
import { checkedTimeline, checkedTimelineRow, type StudioTimelineRow } from './studioTimelineTypes';
import type { TimelineExportPreview } from './studioTimelineExportTypes';
import type { TimelinePlayback } from './studioTimelinePlaybackTypes';

// Generated in memory for component/contract tests; no claims of acoustic quality.
export const audioTimelineProject = 'audio-timeline-project';
export const audioTimelineSource = { id: 'audio-source', kind: 'ASSET' as const, asset_kind: 'audio' as const, version: 1, digest: 'a'.repeat(64) };
export const audioTimelineAssets = (): StudioAsset[] => [{ id: audioTimelineSource.id, kind: 'audio', version: 1, sha256: audioTimelineSource.digest,
  filename: 'voice.wav', deleted_at: null, novel_id: audioTimelineProject, branch_id: null, media_type: 'audio/wav', size: 192044, created_at: '', updated_at: '' } as StudioAsset];
export function audioTimelineRow(): StudioTimelineRow {
  return checkedTimelineRow({ id: 'audio-timeline', title: 'Audio only', version: 1, timeline_digest: 'b'.repeat(64), created_at: 'now', updated_at: 'now',
    timeline: { schema_version: 3, media_kind: 'AUDIO', duration_ms: 1000, tracks: [{ id: 'dialogue', kind: 'AUDIO', order: 0, muted: false, gain_db: -2,
      role: 'DIALOGUE', clips: [{ id: 'voice', source_snapshot: audioTimelineSource, start_ms: 0, in_ms: 0, out_ms: 1000, gain_db: -3, fade_in_ms: 100, fade_out_ms: 200 }] }] } });
}
export function audioTimelineBytes(): Uint8Array {
  const bytes = new Uint8Array(192044), view = new DataView(bytes.buffer);
  const text = (offset: number, value: string) => [...value].forEach((letter, i) => { bytes[offset + i] = letter.charCodeAt(0); });
  text(0, 'RIFF'); view.setUint32(4, bytes.length - 8, true); text(8, 'WAVEfmt '); view.setUint32(16, 16, true);
  view.setUint16(20, 1, true); view.setUint16(22, 2, true); view.setUint32(24, 48000, true); view.setUint32(28, 192000, true);
  view.setUint16(32, 4, true); view.setUint16(34, 16, true); text(36, 'data'); view.setUint32(40, 192000, true); return bytes;
}
export function audioTimelineExport(source = audioTimelineRow()): TimelineExportPreview {
  return { contract: 'studio-timeline-export-preview/1', timeline_snapshot: { id: source.id, version: source.version, digest: source.timeline_digest },
    export_profile: { preset: 'AUDIO_WAV_PCM16' }, sources: [audioTimelineSource], execution_recipe: { contract: 'studio-execution-recipe/1', operation_id: 'm9.timeline.multitrack',
      adapter: 'LOCAL_FFMPEG', output_profile: 'AUDIO_WAV_PCM16', export_profile: { preset: 'AUDIO_WAV_PCM16' }, timeline: checkedTimeline(source.timeline), automatic_fallback: false, recipe_digest: 'c'.repeat(64) },
    limits: { max_output_bytes: 25 * 1024 * 1024, render_timeout_seconds: 120 }, preview_digest: 'd'.repeat(64), model_called: false, automatic_replay: false, product_acceptance: 'LOCAL_REQUIRED' };
}
export function audioTimelineJob(source = audioTimelineRow()): ProductionJob {
  const preview = audioTimelineExport(source);
  return { contract: 'studio-production-job/1', novel_id: audioTimelineProject, branch_id: null, owner: 'timeline', id: 'e'.repeat(64), version: 3,
    status: 'AWAITING_REVIEW', request_id: `playback_${'f'.repeat(64)}`, request_digest: '1'.repeat(64), receipt_digest: '2'.repeat(64), operation_id: 'm9.timeline.multitrack',
    command: null, provider: null, execution_recipe: preview.execution_recipe, timeline_snapshot: preview.timeline_snapshot, sources: preview.sources,
    output_candidate: { id: 'audio-result', version: 1, kind: 'audio', digest: createHash('sha256').update(audioTimelineBytes()).digest('hex') }, approved_asset_version: null,
    media_measurement: { duration_ms: 1000, byte_count: 192044, audio_codec: 'pcm_s16le', sample_rate: 48000, channels: 2, sample_count: 48000, bits_per_sample: 16,
      container: 'wav', profile_validation: 'NATIVE_FFPROBE_EXACT', render_profile: 'STUDIO_MULTITRACK_LOCAL_FFMPEG_AUDIO_WAV_PCM16', export_profile: preview.export_profile },
    created_at: 'now', updated_at: 'now', product_acceptance: 'LOCAL_REQUIRED', automatic_replay: false, remote_compute_may_continue: false };
}
export function audioTimelinePlayback(job: ProductionJob | null = null, source = audioTimelineRow()): TimelinePlayback {
  return { contract: 'studio-timeline-playback/1', novel_id: audioTimelineProject, branch_id: null, cache_key: 'f'.repeat(64), request_id: `playback_${'f'.repeat(64)}`,
    job_id: 'e'.repeat(64), export_preview: audioTimelineExport(source), job, cache_state: job ? 'RECORDED' : 'MISSING', playback_digest: '3'.repeat(64),
    model_called: false, automatic_replay: false, product_acceptance: 'LOCAL_REQUIRED' };
}
