import { checkedTimeline, timelineClipDuration } from '../creative/studioTimelineTypes';
import { NLE_OWNER_LIMITS, type NleOwnerOperation } from './timelineOpsTypes';

export type SelectionMoveOperation = Extract<NleOwnerOperation, { op: 'clip.move' }>;

/** Compile one selection intent to existing owner descriptors, without applying edits. */
export function selectionMoveOperations(timeline: unknown, clipIds: readonly string[], offsetMs: number): SelectionMoveOperation[] {
  if (!Array.isArray(clipIds) || !clipIds.length || clipIds.length > NLE_OWNER_LIMITS.editOperationsPerBatch
    || clipIds.some(id => typeof id !== 'string') || new Set(clipIds).size !== clipIds.length) {
    throw new Error('请选择互不重复的原片段；单批最多 40 项操作，时间线总片段上限仍为 30。');
  }
  if (!Number.isSafeInteger(offsetMs)) throw new Error('整体移动需要整数毫秒增量，可为负。');
  const source = checkedTimeline(timeline);
  const operations = clipIds.map(id => {
    const track = source.tracks.find(row => row.clips.some(clip => clip.id === id));
    const clip = track?.clips.find(row => row.id === id);
    if (!track || !clip) throw new Error('找不到所选原片段，请重新选择。');
    if (track.locked) throw new Error('所选片段包含锁定轨道，请先通过原服务明确解锁。');
    const start = clip.start_ms + offsetMs;
    if (!Number.isSafeInteger(start) || start < 0 || start + timelineClipDuration(clip) > source.duration_ms) {
      throw new Error('整体移动后的片段必须全部位于原时间线范围内。');
    }
    return { op: 'clip.move' as const, clip_id: id, track_id: track.id, start_ms: start };
  });
  if (new TextEncoder().encode(JSON.stringify(operations)).length > NLE_OWNER_LIMITS.editBatchBytes) {
    throw new Error('整体移动超出原编辑批次字节上限。');
  }
  return operations;
}
