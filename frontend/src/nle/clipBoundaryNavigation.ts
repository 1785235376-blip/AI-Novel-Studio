import { timelineClipDuration } from '../creative/studioTimelineTypes';
import { NLE_CODES, type NleRefusal } from './timelineOpsTypes';
import { safeTimeline } from './timelineOps';

/** Local navigation facts over the original bounded timeline; no marks, rounding or synthetic endpoints. */
export function clipBoundaryNavigation(timeline: unknown, playheadMs: unknown): NleRefusal | {
  ok: true; durationMs: number; timelineKey: string; pointsMs: number[]; previousMs: number | null; nextMs: number | null;
} {
  const checked = safeTimeline(timeline);
  if (!checked.ok) return checked;
  if (typeof playheadMs !== 'number' || !Number.isSafeInteger(playheadMs) || playheadMs < 0 || playheadMs > checked.timeline.duration_ms) {
    return { ok: false, code: NLE_CODES.integerRequired, message: '剪切点导航需要位于时间线范围内的整数毫秒播放头。' };
  }
  const pointsMs = [...new Set(checked.timeline.tracks.flatMap(track => track.clips.flatMap(clip =>
    [clip.start_ms, clip.start_ms + timelineClipDuration(clip)])))].sort((left, right) => left - right);
  return { ok: true, durationMs: checked.timeline.duration_ms, timelineKey: JSON.stringify(checked.timeline), pointsMs,
    previousMs: pointsMs.filter(ms => ms < playheadMs).at(-1) ?? null,
    nextMs: pointsMs.find(ms => ms > playheadMs) ?? null };
}
