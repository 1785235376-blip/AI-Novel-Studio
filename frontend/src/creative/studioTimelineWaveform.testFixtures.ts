import type { StudioAsset } from './studioClient';
import type { TimelineWaveform } from './studioTimelineWaveformTypes';
import { checkedTimelineRow, type StudioTimelineRow } from './studioTimelineTypes';
export const waveformRow = (): StudioTimelineRow => checkedTimelineRow({ id: 'timeline-waveform', version: 1, timeline_digest: 'b'.repeat(64),
  title: 'Waveform fixture', created_at: '2026-10-17', updated_at: '2026-10-17', timeline: { schema_version: 2, duration_ms: 5000,
    width: 64, height: 64, fps: 25, captions: [], tracks: [
      { id: 'video-track', kind: 'VIDEO', order: 0, muted: false, gain_db: 0, clips: [{ id: 'still',
        source_snapshot: { id: 'asset-image', kind: 'ASSET', asset_kind: 'image', version: 1, digest: 'c'.repeat(64) },
        start_ms: 0, in_ms: 0, out_ms: 5000, x: 0, y: 0, width: 64, height: 64 }] },
      { id: 'audio-track', kind: 'AUDIO', order: 1, muted: true, gain_db: -6, clips: [{ id: 'audio-clip',
        source_snapshot: { id: 'asset-audio', kind: 'ASSET', asset_kind: 'audio', version: 2, digest: 'a'.repeat(64) },
        start_ms: 1000, in_ms: 1, out_ms: 1000, speed_num: 3, speed_den: 2, gain_db: -3, fade_in_ms: 12, fade_out_ms: 15, muted: true }] },
    ] } });
export const waveformAssets = () => [{ id: 'asset-image', kind: 'image', version: 1, sha256: 'c'.repeat(64), filename: 'still.png', deleted_at: null },
  { id: 'asset-audio', kind: 'audio', version: 2, sha256: 'a'.repeat(64), filename: 'source.wav', deleted_at: null }] as unknown as StudioAsset[];
export const waveformDto = (): TimelineWaveform => ({ contract: 'studio-timeline-waveform-preview/1', novel_id: 'project-waveform', branch_id: null,
  timeline_id: 'timeline-waveform', timeline_version: 1, timeline_digest: 'b'.repeat(64), clip_id: 'audio-clip',
  source_snapshot: { id: 'asset-audio', kind: 'ASSET', asset_kind: 'audio', version: 2, digest: 'a'.repeat(64) },
  status: 'MEASURED_PCM16_PEAKS', scope: 'CLIP_SOURCE_ENVELOPE', byte_count: 88244, frame_count: 44100, sample_rate: 44100, channels: 1,
  duration_seconds: { num: 44100, den: 44100 }, start_frame: 45, end_frame: 44100, samples_per_bucket: 87,
  peaks: Array.from({ length: 507 }, (_, index) => index % 2 ? 1 : 0.5),
  clip: { in_ms: 1, out_ms: 1000, start_ms: 1000, speed_num: 3, speed_den: 2 } });
