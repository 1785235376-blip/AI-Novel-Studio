import { checkedTimeline, cloneTimeline, timelineClipDuration } from '../creative/studioTimelineTypes';
import { NLE_OWNER_LIMITS, type NleOwnerOperation } from './timelineOpsTypes';

type RemoveOperation = Extract<NleOwnerOperation, { op: 'clip.remove' }>;

/** One bounded non-ripple intent over the original DTO; no storage or execution. */
export function selectionRemovePreview(timeline: unknown, clipIds: readonly string[]) {
  if (!Array.isArray(clipIds) || !clipIds.length || clipIds.length > NLE_OWNER_LIMITS.editOperationsPerBatch
    || clipIds.some(id => typeof id !== 'string') || new Set(clipIds).size !== clipIds.length) {
    throw new Error('请选择互不重复的原片段，删除批次不得超过原操作上限。');
  }
  const source = checkedTimeline(timeline);
  const selected = new Set(clipIds);
  const targets = clipIds.map(id => {
    const track = source.tracks.find(row => row.clips.some(clip => clip.id === id));
    const clip = track?.clips.find(row => row.id === id);
    if (!track || !clip) throw new Error('找不到所选原片段，请重新选择。');
    if (track.locked) throw new Error('所选片段包含锁定轨道，请先通过原服务明确解锁。');
    return { clipId: id, trackId: track.id, kind: track.kind,
      startMs: clip.start_ms, endMs: clip.start_ms + timelineClipDuration(clip) };
  });
  for (const track of source.tracks) {
    if (track.clips.every(clip => selected.has(clip.id))) {
      throw new Error('删除会清空轨道；原时间线要求每轨至少保留一个片段，本次未删除。');
    }
    if (track.clips.some(clip => !selected.has(clip.id) && clip.transition_out
      && selected.has(clip.transition_out.to_clip_id))) {
      throw new Error('删除会留下未选片段的悬空转场，请先在原编辑区明确移除该转场。');
    }
  }
  const operations: RemoveOperation[] = clipIds.map(id => ({ op: 'clip.remove', clip_id: id, ripple: false }));
  if (new TextEncoder().encode(JSON.stringify(operations)).length > NLE_OWNER_LIMITS.editBatchBytes) {
    throw new Error('删除超出原编辑批次字节上限。');
  }
  // Preserve the input's exact other fields; validation must not normalize an
  // unrelated source pin, caption, track or clip as a side effect of deletion.
  const next = cloneTimeline(timeline as typeof source);
  for (const track of next.tracks) track.clips = track.clips.filter(clip => !selected.has(clip.id));
  checkedTimeline(next);
  return { targets, operations, timeline: next };
}

export function sameSelectionRemoveDescriptors(value: unknown, expected: readonly RemoveOperation[]): boolean {
  return Array.isArray(value) && value.length === expected.length && value.every((operation, index) =>
    operation && typeof operation === 'object' && !Array.isArray(operation)
    && Object.keys(operation).length === 3
    && Object.keys(operation).every(key => ['op', 'clip_id', 'ripple'].includes(key))
    && operation.op === expected[index].op && operation.clip_id === expected[index].clip_id
    && operation.ripple === false);
}
