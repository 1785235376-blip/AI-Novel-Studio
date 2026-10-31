import { checkedTimeline, cloneTimeline, timelineClipDuration, type StudioTimeline } from '../creative/studioTimelineTypes';
import type { NleOwnerOperation } from './timelineOpsTypes';
import { sameSelectionDuplicateDescriptors } from './timelineSelectionDuplicate';

export type SelectionSplitIds = Readonly<Record<string, string>>;
export type SelectionSplitOperation = Extract<NleOwnerOperation, { op: 'clip.split' }>;

/** Explicit ordered selection only; exact timeline milliseconds, never snapped. */
export function selectionSplitTargets(timeline: unknown, clipIds: readonly string[], playheadMs: number) {
  if (!Array.isArray(clipIds) || !clipIds.length || Array.from(clipIds).some(id => typeof id !== 'string')
    || new Set(clipIds).size !== clipIds.length) throw new Error('请选择互不重复的原片段。');
  if (!Number.isSafeInteger(playheadMs)) throw new Error('拆分需要整数毫秒播放头。');
  const source = checkedTimeline(timeline);
  const targets = clipIds.map(id => {
    const track = source.tracks.find(row => row.clips.some(clip => clip.id === id));
    const clip = track?.clips.find(row => row.id === id);
    if (!track || !clip) throw new Error('找不到所选原片段，请重新选择。');
    const end = clip.start_ms + timelineClipDuration(clip), affected = clip.start_ms < playheadMs && playheadMs < end;
    const offset = playheadMs - clip.start_ms;
    if (affected && track.locked) throw new Error('跨越播放头的所选片段包含锁定轨道。');
    if (affected && (!Number.isSafeInteger(offset * (clip.speed_num ?? 1))
      || offset * (clip.speed_num ?? 1) % (clip.speed_den ?? 1))) throw new Error('播放头不能按当前速度映射至整数毫秒素材入点。');
    return { track, clip, end, affected, cut: clip.in_ms + offset * (clip.speed_num ?? 1) / (clip.speed_den ?? 1) };
  });
  if (source.tracks.reduce((sum, track) => sum + track.clips.length, 0) + targets.filter(row => row.affected).length > 30) {
    throw new Error('拆分后时间线总片段不能超过 30。');
  }
  return targets;
}

function applyTargets(timeline: unknown, clipIds: readonly string[], playheadMs: number, newIds: SelectionSplitIds): StudioTimeline {
  const result = cloneTimeline(checkedTimeline(timeline));
  for (const { clip, track, affected, cut } of selectionSplitTargets(result, clipIds, playheadMs)) {
    if (!affected) continue;
    const target = result.tracks.find(row => row.id === track.id)!;
    const left = target.clips.find(row => row.id === clip.id)!;
    const right = { ...cloneTimeline(left), id: newIds[clip.id], start_ms: playheadMs, in_ms: cut };
    if (left.source_snapshot.asset_kind === 'image') { right.in_ms = 0; right.out_ms = left.out_ms - (playheadMs - left.start_ms); }
    left.out_ms = cut;
    delete left.transition_out;
    if ('fade_out_ms' in left) left.fade_out_ms = 0;
    if ('fade_in_ms' in right) right.fade_in_ms = 0;
    target.clips.push(right);
  }
  return checkedTimeline(result);
}

/** Validate the full final shape before any identities are allocated. */
export function selectionSplitPreview(timeline: unknown, clipIds: readonly string[], playheadMs: number) {
  const targets = selectionSplitTargets(timeline, clipIds, playheadMs);
  const existing = new Set(checkedTimeline(timeline).tracks.flatMap(track => track.clips.map(clip => clip.id)));
  const placeholders: Record<string, string> = Object.create(null);
  targets.filter(row => row.affected).forEach(({ clip }, index) => {
    let id = `split-preview-${index}`;
    while (existing.has(id)) id += '-';
    existing.add(id); placeholders[clip.id] = id;
  });
  applyTargets(timeline, clipIds, playheadMs, placeholders);
  return targets;
}

export function selectionSplitOperations(timeline: unknown, clipIds: readonly string[], playheadMs: number,
  newIds: SelectionSplitIds): SelectionSplitOperation[] {
  const affected = selectionSplitPreview(timeline, clipIds, playheadMs).filter(row => row.affected);
  if (!affected.length) throw new Error('播放头未穿过任何所选片段；边界与范围外片段均跳过。');
  if (!newIds || typeof newIds !== 'object' || Array.isArray(newIds)
    || ![Object.prototype, null].includes(Object.getPrototypeOf(newIds))
    || Reflect.ownKeys(newIds).length !== affected.length || affected.some(({ clip }) => {
      const field = Object.getOwnPropertyDescriptor(newIds, clip.id);
      return !field || !field.enumerable || !('value' in field);
    })) throw new Error('拆分需要完整且仅包含受影响片段的新标识映射。');
  const existing = new Set(checkedTimeline(timeline).tracks.flatMap(track => track.clips.map(clip => clip.id)));
  const ids = affected.map(({ clip }) => newIds[clip.id]);
  if (ids.some(id => typeof id !== 'string' || !/^[A-Za-z0-9][A-Za-z0-9_-]{0,239}$/.test(id) || existing.has(id))
    || new Set(ids).size !== ids.length) throw new Error('新片段标识无效或重复；不会自动更换标识重试。');
  return affected.map(({ clip }) => ({ op: 'clip.split', clip_id: clip.id, at_ms: playheadMs, new_clip_id: newIds[clip.id] }));
}

export function applySelectionSplit(timeline: unknown, clipIds: readonly string[], playheadMs: number, newIds: SelectionSplitIds) {
  selectionSplitOperations(timeline, clipIds, playheadMs, newIds);
  return applyTargets(timeline, clipIds, playheadMs, newIds);
}
export const sameSelectionSplitDescriptors = sameSelectionDuplicateDescriptors;
