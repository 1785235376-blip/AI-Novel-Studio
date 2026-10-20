import type { StudioTimeline, StudioTimelineClipLink, StudioTimelineTrack } from './studioTimelineTypes';
import { matchesLinkedSplit } from './studioTimelineLinkedSplit';
import { matchesLinkedTrim } from './studioTimelineLinkedTrim';

const identity = /^[A-Za-z0-9][A-Za-z0-9_-]{0,239}$/;
export const CLIP_LINK_EDIT_REFUSAL = '链接片段暂不支持独立裁剪、拆分、滑移或替换来源；请先明确解除链接。';

export function checkedClipLinks(value: unknown, tracks: StudioTimelineTrack[]): StudioTimelineClipLink[] {
  if (!Array.isArray(value) || value.length > 15) throw new Error('同一时间线最多十五对片段链接，每个片段只属于一对。');
  const clips = new Map(tracks.flatMap(track => track.clips.map(clip => [clip.id, { track, clip }] as const)));
  const used = new Set<string>();
  return value.map(raw => {
    if (!raw || typeof raw !== 'object' || Array.isArray(raw) || Object.keys(raw).length !== 3
      || Object.keys(raw).some(key => !['video_clip_id', 'audio_clip_id', 'offset_ms'].includes(key))) throw new Error('片段链接字段无效。');
    const pair = raw as StudioTimelineClipLink, video = clips.get(pair.video_clip_id), audio = clips.get(pair.audio_clip_id);
    if (typeof pair.video_clip_id !== 'string' || !identity.test(pair.video_clip_id) || typeof pair.audio_clip_id !== 'string'
      || !identity.test(pair.audio_clip_id) || pair.video_clip_id === pair.audio_clip_id || used.has(pair.video_clip_id) || used.has(pair.audio_clip_id)
      || video?.track.kind !== 'VIDEO' || audio?.track.kind !== 'AUDIO') throw new Error('链接必须是同一时间线中互不重复的一对视频轨与音频轨片段。');
    if (!Number.isSafeInteger(pair.offset_ms) || Math.abs(pair.offset_ms) > 600000
      || audio.clip.start_ms - video.clip.start_ms !== pair.offset_ms) throw new Error('链接片段须保持原起点偏移；独立修改未应用，请使用联动移动或先解除链接。');
    used.add(pair.video_clip_id); used.add(pair.audio_clip_id);
    return { video_clip_id: pair.video_clip_id, audio_clip_id: pair.audio_clip_id, offset_ms: pair.offset_ms };
  }).sort((left, right) => left.video_clip_id < right.video_clip_id ? -1 : left.video_clip_id > right.video_clip_id ? 1
    : left.audio_clip_id < right.audio_clip_id ? -1 : left.audio_clip_id > right.audio_clip_id ? 1 : 0);
}

export const clipLink = (timeline: StudioTimeline, id: string) => timeline.clip_links?.find(pair => pair.video_clip_id === id || pair.audio_clip_id === id);

/** Guard all original draft inputs, including the numeric editor and whole DTO saves. */
export function requireClipLinkPreservation(before: StudioTimeline, after: StudioTimeline, allowLinkedTrim = true): void {
  if (!before.clip_links && !after.clip_links) return;
  if (after.clip_links && after.schema_version !== 2) throw new Error('片段链接需要版本 2 的视频与音频时间线。');
  const previous = before.clip_links ?? [], current = after.clip_links ? checkedClipLinks(after.clip_links, after.tracks) : [];
  const old = new Map(before.tracks.flatMap(track => track.clips.map(clip => [clip.id, { track, clip }] as const)));
  const next = new Map(after.tracks.flatMap(track => track.clips.map(clip => [clip.id, { track, clip }] as const)));
  let linkedEditCount = 0;
  for (const pair of previous) {
    const match = current.find(row => row.video_clip_id === pair.video_clip_id && row.audio_clip_id === pair.audio_clip_id);
    if (!match) continue;
    if (pair.offset_ms !== match.offset_ms) throw new Error('已保存链接的偏移不可重定义；请先解除并保存，再建立新链接。');
    const rangeChanged = [pair.video_clip_id, pair.audio_clip_id].some(id => {
      const left = old.get(id)!.clip, right = next.get(id)!.clip;
      return JSON.stringify(left.source_snapshot) !== JSON.stringify(right.source_snapshot)
        || ['in_ms', 'out_ms', 'speed_num', 'speed_den'].some(key => (left[key as 'in_ms'] ?? 1) !== (right[key as 'in_ms'] ?? 1));
    });
    const pairedSplit = rangeChanged && matchesLinkedSplit(before, after, pair);
    const pairedTrim = allowLinkedTrim && rangeChanged && matchesLinkedTrim(before, after, pair);
    if ((pairedSplit || pairedTrim) && ++linkedEditCount > 1) throw new Error('首片联动编辑一次只支持一对链接。');
    for (const id of [pair.video_clip_id, pair.audio_clip_id]) {
      const left = old.get(id)!, right = next.get(id)!;
      if (!(pairedSplit || pairedTrim) && (JSON.stringify(left.clip.source_snapshot) !== JSON.stringify(right.clip.source_snapshot)
        || ['in_ms', 'out_ms', 'speed_num', 'speed_den'].some(key => (left.clip[key as 'in_ms'] ?? 1) !== (right.clip[key as 'in_ms'] ?? 1)))) throw new Error(CLIP_LINK_EDIT_REFUSAL);
      if ((left.track.locked || right.track.locked) && (left.track.id !== right.track.id || left.clip.start_ms !== right.clip.start_ms)) throw new Error('链接包含锁定轨道，整批移动未应用。');
    }
  }
  const same = (a: StudioTimelineClipLink, b: StudioTimelineClipLink) => a.video_clip_id === b.video_clip_id && a.audio_clip_id === b.audio_clip_id && a.offset_ms === b.offset_ms;
  for (const pair of [...previous.filter(row => !current.some(other => same(row, other))), ...current.filter(row => !previous.some(other => same(row, other)))]) {
    if ([pair.video_clip_id, pair.audio_clip_id].some(id => old.get(id)?.track.locked || next.get(id)?.track.locked)) throw new Error('锁定轨道上的片段不能建立或解除链接。');
  }
}

export function changeClipLinks(timeline: StudioTimeline, ids: readonly string[], unlink: boolean): StudioTimeline {
  if (timeline.schema_version !== 2 || !ids.length || ids.length > 2 || new Set(ids).size !== ids.length) throw new Error('请选择同一时间线的一对视频／音频片段；解除时可选中该对任一片段。');
  const result = JSON.parse(JSON.stringify(timeline)) as StudioTimeline;
  if (result.schema_version !== 2) throw new Error('请先明确升级到时间线版本 2。');
  if (unlink) {
    const pair = clipLink(result, ids[0]);
    if (!pair || ids.some(id => ![pair.video_clip_id, pair.audio_clip_id].includes(id))) throw new Error('请仅选择同一链接的片段进行解除。');
    result.clip_links = result.clip_links!.filter(row => row.video_clip_id !== pair.video_clip_id);
    if (!result.clip_links.length) delete result.clip_links;
  } else {
    const chosen = result.tracks.flatMap(track => track.clips.filter(clip => ids.includes(clip.id)).map(clip => ({ track, clip })));
    const video = chosen.find(row => row.track.kind === 'VIDEO'), audio = chosen.find(row => row.track.kind === 'AUDIO');
    if (ids.length !== 2 || chosen.length !== 2 || !video || !audio || ids.some(id => clipLink(result, id))) throw new Error('链接需要尚未链接的一对视频轨／音频轨片段。');
    result.clip_links = [...(result.clip_links ?? []), { video_clip_id: video.clip.id, audio_clip_id: audio.clip.id, offset_ms: audio.clip.start_ms - video.clip.start_ms }];
  }
  requireClipLinkPreservation(timeline, result);
  if (result.clip_links) result.clip_links = checkedClipLinks(result.clip_links, result.tracks);
  return result;
}
