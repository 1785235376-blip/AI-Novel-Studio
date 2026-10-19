import { checkedTimelineRow, type StudioTimelineClip } from '../creative/studioTimelineTypes';
import type { StudioAsset } from '../creative/studioClient';

// Synthetic DTOs, never claims of measured source media or render acceptance.
const source = (kind: 'video' | 'audio') => ({ id: `asset-${kind}`, kind: 'ASSET' as const,
  asset_kind: kind, version: 1, digest: 'a'.repeat(64) });
const audio = (id: string, start_ms: number): StudioTimelineClip => ({ id, source_snapshot: source('audio'),
  start_ms, in_ms: 600, out_ms: 3600, speed_num: 3, speed_den: 2, gain_db: -3, fade_in_ms: 100, fade_out_ms: 200 });
export function selectionRemoveRow() {
  return checkedTimelineRow({ id: 'timeline-selection-remove', version: 1, timeline_digest: 'b'.repeat(64),
    title: 'Selection remove fixture', created_at: '2026-10-19', updated_at: '2026-10-19',
    timeline: { schema_version: 2, duration_ms: 8000, width: 64, height: 64, fps: 25,
      captions: [{ start_ms: 6600, end_ms: 6900, text: 'Keep this caption' }], tracks: [
        { id: 'visual', kind: 'VIDEO', order: 0, muted: false, gain_db: 0, clips: [
          { id: 'video-remove', source_snapshot: source('video'), start_ms: 0, in_ms: 500, out_ms: 2500,
            x: 0, y: 0, width: 64, height: 64, opacity: 0.8 },
          { id: 'video-keep', source_snapshot: source('video'), start_ms: 3000, in_ms: 0, out_ms: 2000,
            x: 0, y: 0, width: 64, height: 64, crop: { x: 0, y: 0, width: 64, height: 64 } },
        ] },
        { id: 'sound', kind: 'AUDIO', order: 1, muted: false, gain_db: -2,
          clips: [audio('audio-remove', 1000), audio('audio-keep', 4500)] },
      ] } });
}
export const selectionRemoveAssets = () => ['video', 'audio'].map(kind => ({ id: `asset-${kind}`, kind,
  version: 1, sha256: 'a'.repeat(64), filename: `${kind}.fixture`, deleted_at: null })) as unknown as StudioAsset[];
