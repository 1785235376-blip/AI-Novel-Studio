import type { StudioTimeline, StudioTimelineClipLink } from './studioTimelineTypes';
import { linkedPairFacts, stableLinkedValue } from './studioTimelineLinkedSplit';

export function linkedTrimFacts(timeline: StudioTimeline, ids: readonly string[], keepFromMs: number, keepToMs: number) {
  const facts = linkedPairFacts(timeline, ids);
  if (!Number.isSafeInteger(keepFromMs) || !Number.isSafeInteger(keepToMs) || keepFromMs < 0 || keepFromMs >= keepToMs || keepToMs > facts.commonLength)
    throw new Error('保留区间须为共同来源区间内非空的整数毫秒范围；不扩展、不波纹。');
  if (keepFromMs === 0 && [facts.video, facts.audio].every(({ clip }) => clip.out_ms - clip.in_ms === keepToMs))
    throw new Error('双方范围没有变化，未新增裁剪。');
  return { ...facts, keepFromMs, keepToMs, durationMs: keepToMs - keepFromMs };
}

/** Same fixed-start, non-ripple semantics as original clip.trim, on both members. */
export function trimLinkedTimeline(timeline: StudioTimeline, ids: readonly string[], keepFromMs: number, keepToMs: number): StudioTimeline {
  const result = JSON.parse(JSON.stringify(timeline)) as StudioTimeline;
  const facts = linkedTrimFacts(result, ids, keepFromMs, keepToMs);
  for (const { clip } of [facts.video, facts.audio]) {
    const origin = clip.in_ms; clip.in_ms = origin + keepFromMs; clip.out_ms = origin + keepToMs;
  }
  return result;
}

export function matchesLinkedTrim(before: StudioTimeline, after: StudioTimeline, pair: StudioTimelineClipLink): boolean {
  const old = new Map(before.tracks.flatMap(track => track.clips.map(clip => [clip.id, { trackId: track.id, clip }] as const)));
  const next = new Map(after.tracks.flatMap(track => track.clips.map(clip => [clip.id, { trackId: track.id, clip }] as const)));
  const video = old.get(pair.video_clip_id), changed = next.get(pair.video_clip_id);
  if (!video || !changed || !next.has(pair.audio_clip_id)) return false;
  try {
    const expected = trimLinkedTimeline(before, [pair.video_clip_id, pair.audio_clip_id], changed.clip.in_ms - video.clip.in_ms, changed.clip.out_ms - video.clip.in_ms);
    return stableLinkedValue(after) === stableLinkedValue(expected);
  } catch { return false; }
}
