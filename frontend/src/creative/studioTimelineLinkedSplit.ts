import type { StudioTimeline, StudioTimelineClipLink } from './studioTimelineTypes';

export type LinkedSplitIds = { video: string; audio: string };
export function linkedPairFacts(timeline: StudioTimeline, ids: readonly string[]) {
  const pair = timeline.clip_links?.find(row => ids.includes(row.video_clip_id) || ids.includes(row.audio_clip_id));
  if (timeline.schema_version !== 2 || !ids.length || ids.length > 2 || new Set(ids).size !== ids.length || !pair
    || ids.some(id => ![pair.video_clip_id, pair.audio_clip_id].includes(id))) throw new Error('联动编辑须仅选择同一已保存链接的一对视频／音频片段。');
  const clips = new Map(timeline.tracks.flatMap(track => track.clips.map(clip => [clip.id, { track, clip }] as const)));
  const video = clips.get(pair.video_clip_id), audio = clips.get(pair.audio_clip_id);
  if (!video || !audio) throw new Error('链接成员已改变，请重新读取。');
  if (video.track.locked || audio.track.locked) throw new Error('链接包含锁定轨道，联动编辑未应用。');
  if (video.clip.source_snapshot.asset_kind !== 'video' || audio.clip.source_snapshot.asset_kind !== 'audio'
    || [video.clip, audio.clip].some(clip => (clip.speed_num ?? 1) !== 1 || (clip.speed_den ?? 1) !== 1 || clip.fade_in_ms || clip.fade_out_ms)
    || [...clips.values()].some(({ clip }) => clip.transition_out && ([pair.video_clip_id, pair.audio_clip_id].includes(clip.id)
      || [pair.video_clip_id, pair.audio_clip_id].includes(clip.transition_out.to_clip_id)))) throw new Error('首片联动编辑仅支持 1× 视频／音频且无转场、淡入淡出；其他模式明确拒绝。');
  return { pair, video, audio, commonLength: Math.min(video.clip.out_ms - video.clip.in_ms, audio.clip.out_ms - audio.clip.in_ms) };
}
export function linkedSplitFacts(timeline: StudioTimeline, ids: readonly string[], videoAtMs: number) {
  const { pair, video, audio, commonLength } = linkedPairFacts(timeline, ids);
  const elapsed = videoAtMs - video.clip.start_ms;
  if (!Number.isSafeInteger(videoAtMs) || !Number.isSafeInteger(elapsed) || elapsed <= 0 || elapsed >= commonLength) throw new Error('视频切点须位于两成员共同相对区间内部；边界与区间外不拆分。');
  return { pair, video, audio, elapsed, videoAtMs, audioAtMs: audio.clip.start_ms + elapsed,
    commonStart: video.clip.start_ms, commonEnd: video.clip.start_ms + commonLength };
}

/** Detached partition only; original editor/history/CAS remain the owner. */
export function splitLinkedTimeline(timeline: StudioTimeline, ids: readonly string[], videoAtMs: number, newIds: LinkedSplitIds): StudioTimeline {
  const result = JSON.parse(JSON.stringify(timeline)) as StudioTimeline;
  const facts = linkedSplitFacts(result, ids, videoAtMs);
  if (result.schema_version !== 2) throw new Error('联动拆分需要版本 2。');
  const existing = new Set(result.tracks.flatMap(track => track.clips.map(clip => clip.id)));
  if (!newIds || Object.keys(newIds).length !== 2 || !Object.hasOwn(newIds, 'video') || !Object.hasOwn(newIds, 'audio')
    || [newIds.video, newIds.audio].some(id => typeof id !== 'string' || !/^[A-Za-z0-9][A-Za-z0-9_-]{0,239}$/.test(id) || existing.has(id))
    || newIds.video === newIds.audio) throw new Error('两侧新标识必须唯一且尚不存在；不会换键重试。');
  if (existing.size + 2 > 30 || (result.clip_links?.length ?? 0) + 1 > 15) throw new Error('联动拆分超过原 30 片段／15 对链接上限。');
  for (const [member, id] of [[facts.video, newIds.video], [facts.audio, newIds.audio]] as const) {
    const left = member.clip, right = { ...JSON.parse(JSON.stringify(left)), id, start_ms: left.start_ms + facts.elapsed, in_ms: left.in_ms + facts.elapsed };
    left.out_ms = left.in_ms + facts.elapsed; member.track.clips.push(right);
  }
  result.clip_links!.push({ video_clip_id: newIds.video, audio_clip_id: newIds.audio, offset_ms: facts.pair.offset_ms });
  return result;
}

export const stableLinkedValue = (value: unknown): string => value && typeof value === 'object'
  ? Array.isArray(value) ? '[' + value.map(stableLinkedValue).join(',') + ']'
    : '{' + Object.entries(value).sort(([a], [b]) => a < b ? -1 : a > b ? 1 : 0).map(([key, item]) => JSON.stringify(key) + ':' + stableLinkedValue(item)).join(',') + '}'
  : JSON.stringify(value) ?? 'undefined';

export function matchesLinkedSplit(before: StudioTimeline, after: StudioTimeline, pair: StudioTimelineClipLink): boolean {
  const old = new Map(before.tracks.flatMap(track => track.clips.map(clip => [clip.id, { trackId: track.id, clip }] as const)));
  const next = new Map(after.tracks.flatMap(track => track.clips.map(clip => [clip.id, { trackId: track.id, clip }] as const)));
  const video = old.get(pair.video_clip_id), left = next.get(pair.video_clip_id);
  if (!video || !left || !next.has(pair.audio_clip_id)) return false;
  const elapsed = left.clip.out_ms - video.clip.in_ms;
  let matches = 0;
  for (const tail of after.clip_links ?? []) {
    if (old.has(tail.video_clip_id) || old.has(tail.audio_clip_id) || tail.offset_ms !== pair.offset_ms) continue;
    try {
      const expected = splitLinkedTimeline(before, [pair.video_clip_id, pair.audio_clip_id], video.clip.start_ms + elapsed, { video: tail.video_clip_id, audio: tail.audio_clip_id });
      const expectedClips = new Map(expected.tracks.flatMap(track => track.clips.map(clip => [clip.id, { trackId: track.id, clip }] as const)));
      if ([pair.video_clip_id, pair.audio_clip_id, tail.video_clip_id, tail.audio_clip_id].every(id => stableLinkedValue(next.get(id)) === stableLinkedValue(expectedClips.get(id)))) matches++;
    } catch { /* Does not match a supported exact partition. */ }
  }
  return matches === 1;
}
