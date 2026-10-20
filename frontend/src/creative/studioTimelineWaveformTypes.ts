import { ApiError } from '../api';
import { checkedTimelineRow, type StudioTimelineClip, type StudioTimelineRow, type StudioTimelineSource } from './studioTimelineTypes';

export const TIMELINE_WAVEFORM_MAX_BYTES = 8 * 1024 * 1024;
export const TIMELINE_WAVEFORM_MAX_PEAKS = 512;
export type TimelineWaveform = {
  contract: 'studio-timeline-waveform-preview/1'; novel_id: string; branch_id: string | null;
  timeline_id: string; timeline_version: number; timeline_digest: string; clip_id: string; source_snapshot: StudioTimelineSource;
  status: 'MEASURED_PCM16_PEAKS'; scope: 'CLIP_SOURCE_ENVELOPE'; byte_count: number;
  frame_count: number; sample_rate: number; channels: 1 | 2; duration_seconds: { num: number; den: number };
  start_frame: number; end_frame: number; samples_per_bucket: number; peaks: number[];
  clip: { in_ms: number; out_ms: number; start_ms: number; speed_num: number; speed_den: number };
};
function invalid(): never { throw new ApiError({ status: 200, code: 'STUDIO_RESPONSE_INVALID', message: '源波形回执与所选已保存片段不一致，请重新核对。' }); }
function exact(value: unknown, keys: readonly string[]): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) invalid();
  const row = value as Record<string, unknown>;
  if (Object.keys(row).length !== keys.length || keys.some(key => !Object.hasOwn(row, key))) invalid();
  return row;
}
function integer(value: unknown, min: number, max: number): number {
  if (typeof value !== 'number' || !Number.isSafeInteger(value) || value < min || value > max) invalid();
  return value;
}
const identity = (value: unknown): value is string => typeof value === 'string' && /^[A-Za-z0-9][A-Za-z0-9_-]{0,239}$/.test(value);
export function waveformSelectedClip(source: StudioTimelineRow, clipId: string): StudioTimelineClip {
  const row = checkedTimelineRow(source), matches = row.timeline.tracks.flatMap(track => track.clips
    .filter(clip => clip.id === clipId).map(clip => ({ track, clip })));
  if (matches.length !== 1 || matches[0].track.kind !== 'AUDIO' || matches[0].clip.source_snapshot.asset_kind !== 'audio') invalid();
  return matches[0].clip;
}
export function timelineWaveformRequest(source: StudioTimelineRow, clipId: string) {
  const clip = waveformSelectedClip(source, clipId);
  return { expected_version: source.version, reviewed_timeline_digest: source.timeline_digest, clip_id: clip.id,
    source_snapshot: { ...clip.source_snapshot } };
}
/** Closed original-owner projection. It cannot adopt a timeline or refresh source pins. */
export function checkedTimelineWaveform(value: unknown, source: StudioTimelineRow, clipId: string,
  scope?: { novelId: string; branchId?: string | null }): TimelineWaveform {
  const clip = waveformSelectedClip(source, clipId);
  const row = exact(value, ['contract', 'novel_id', 'branch_id', 'timeline_id', 'timeline_version', 'timeline_digest', 'clip_id', 'source_snapshot',
    'status', 'scope', 'byte_count', 'frame_count', 'sample_rate', 'channels', 'duration_seconds', 'start_frame', 'end_frame', 'samples_per_bucket', 'peaks', 'clip']);
  if (row.contract !== 'studio-timeline-waveform-preview/1' || row.status !== 'MEASURED_PCM16_PEAKS' || row.scope !== 'CLIP_SOURCE_ENVELOPE'
    || !identity(row.novel_id) || row.branch_id !== null && !identity(row.branch_id)
    || scope && (row.novel_id !== scope.novelId || scope.branchId !== undefined && row.branch_id !== scope.branchId)
    || row.timeline_id !== source.id || row.timeline_version !== source.version || row.timeline_digest !== source.timeline_digest || row.clip_id !== clipId) invalid();
  const pin = exact(row.source_snapshot, ['id', 'kind', 'asset_kind', 'version', 'digest']);
  if (Object.keys(pin).some(key => pin[key] !== clip.source_snapshot[key as keyof StudioTimelineSource])) invalid();
  const mapping = exact(row.clip, ['in_ms', 'out_ms', 'start_ms', 'speed_num', 'speed_den']);
  if (mapping.in_ms !== clip.in_ms || mapping.out_ms !== clip.out_ms || mapping.start_ms !== clip.start_ms
    || mapping.speed_num !== (clip.speed_num ?? 1) || mapping.speed_den !== (clip.speed_den ?? 1)) invalid();
  const bytes = integer(row.byte_count, 1, TIMELINE_WAVEFORM_MAX_BYTES), rate = integer(row.sample_rate, 1, 192000);
  const channels = integer(row.channels, 1, 2), frames = integer(row.frame_count, 1, TIMELINE_WAVEFORM_MAX_BYTES / (2 * channels));
  if (frames > rate * 600 || frames * channels * 2 > bytes) invalid();
  const duration = exact(row.duration_seconds, ['num', 'den']);
  if (duration.num !== frames || duration.den !== rate) invalid();
  const start = integer(row.start_frame, 0, frames - 1), end = integer(row.end_frame, start + 1, frames);
  if (start !== Math.ceil(clip.in_ms * rate / 1000) || end !== Math.ceil(clip.out_ms * rate / 1000)) invalid();
  const stride = integer(row.samples_per_bucket, 1, frames);
  if (stride !== Math.ceil((end - start) / TIMELINE_WAVEFORM_MAX_PEAKS) || !Array.isArray(row.peaks)
    || row.peaks.length !== Math.ceil((end - start) / stride) || row.peaks.length > TIMELINE_WAVEFORM_MAX_PEAKS
    || Array.from(row.peaks).some(peak => typeof peak !== 'number' || !Number.isFinite(peak) || peak < 0 || peak > 1 || !Number.isInteger(peak * 32768))) invalid();
  return { ...row, source_snapshot: { ...pin }, clip: { ...mapping }, duration_seconds: { ...duration }, peaks: [...row.peaks] } as TimelineWaveform;
}

export type WaveformCoordinate = { num: number; den: number };
/** Integer arithmetic until the SVG boundary. Source sample frames are not rounded milliseconds. */
export function waveformTimelineCoordinate(value: TimelineWaveform, frame: number): WaveformCoordinate {
  const { sample_rate: rate, clip } = value;
  if (!Number.isSafeInteger(frame) || frame < value.start_frame || frame > value.end_frame) invalid();
  const num = clip.start_ms * rate * clip.speed_num + (frame * 1000 - clip.in_ms * rate) * clip.speed_den;
  const den = rate * clip.speed_num;
  if (!Number.isSafeInteger(num) || !Number.isSafeInteger(den) || den <= 0) invalid();
  return { num, den };
}
