import { checkedTimeline, timelineClipDuration } from '../creative/studioTimelineTypes';
import { NLE_OWNER_LIMITS, type NleOwnerOperation } from './timelineOpsTypes';

export type SelectionDuplicateIds = Readonly<Record<string, string>>;
export type SelectionDuplicateOperation = Extract<NleOwnerOperation, { op: 'clip.duplicate' | 'clip.update' }>;

/** Preflight before allocating identities; no edits, source reads or collision repair. */
export function selectionDuplicateTargets(timeline: unknown, clipIds: readonly string[], offsetMs: number) {
  if (!Array.isArray(clipIds) || !clipIds.length || Array.from(clipIds).some(id => typeof id !== 'string')
    || new Set(clipIds).size !== clipIds.length) throw new Error('请选择互不重复的原片段。');
  if (!Number.isSafeInteger(offsetMs)) throw new Error('整体复制需要整数毫秒增量，可为负或零。');
  const source = checkedTimeline(timeline);
  if (source.tracks.reduce((count, track) => count + track.clips.length, 0) + clipIds.length > NLE_OWNER_LIMITS.clips) {
    throw new Error('复制后时间线总片段不能超过 30。');
  }
  return clipIds.map(id => {
    const track = source.tracks.find(row => row.clips.some(clip => clip.id === id));
    const clip = track?.clips.find(row => row.id === id);
    if (!track || !clip) throw new Error('找不到所选原片段，请重新选择。');
    if (track.locked) throw new Error('所选片段包含锁定轨道，请先通过原服务明确解锁。');
    const start = clip.start_ms + offsetMs;
    if (!Number.isSafeInteger(start) || start < 0 || start + timelineClipDuration(clip) > source.duration_ms) {
      throw new Error('复制后的片段必须全部位于原时间线范围内。');
    }
    return { track, clip, start };
  });
}

/** Existing owner operations only: all copies first, then remapped internal dissolves. */
export function selectionDuplicateOperations(timeline: unknown, clipIds: readonly string[], offsetMs: number,
  newIds: SelectionDuplicateIds): SelectionDuplicateOperation[] {
  const targets = selectionDuplicateTargets(timeline, clipIds, offsetMs);
  if (!newIds || typeof newIds !== 'object' || Array.isArray(newIds)
    || ![Object.prototype, null].includes(Object.getPrototypeOf(newIds))
    || Reflect.ownKeys(newIds).length !== clipIds.length || clipIds.some(id => {
      const field = Object.getOwnPropertyDescriptor(newIds, id);
      return !field || !field.enumerable || !('value' in field);
    })) {
    throw new Error('复制需要完整且仅包含当前选择的新片段标识映射。');
  }
  const existing = new Set(checkedTimeline(timeline).tracks.flatMap(track => track.clips.map(clip => clip.id)));
  const ids = clipIds.map(id => newIds[id]);
  if (ids.some(id => typeof id !== 'string' || !/^[A-Za-z0-9][A-Za-z0-9_-]{0,239}$/.test(id) || existing.has(id))
    || new Set(ids).size !== ids.length) throw new Error('新片段标识无效或重复；不会自动更换标识重试。');
  const operations: SelectionDuplicateOperation[] = targets.map(({ track, clip, start }) => ({
    op: 'clip.duplicate', clip_id: clip.id, new_clip_id: newIds[clip.id], track_id: track.id, start_ms: start,
  }));
  for (const { clip } of targets) {
    const transition = clip.transition_out;
    if (transition && clipIds.includes(transition.to_clip_id)) operations.push({ op: 'clip.update', clip_id: newIds[clip.id],
      changes: { transition_out: { ...transition, to_clip_id: newIds[transition.to_clip_id] } } });
  }
  // Match Python json.dumps default separators used by the original batch owner.
  const bytes = new TextEncoder().encode(JSON.stringify(operations).replace(/([,:])/g, '$1 ')).length;
  if (operations.length > NLE_OWNER_LIMITS.editOperationsPerBatch || bytes > NLE_OWNER_LIMITS.editBatchBytes) {
    throw new Error('整体复制超出原编辑批次 40 项操作或 128000 字节上限。');
  }
  return operations;
}

/** Strict recursive descriptor verification, including extra undefined-valued fields. */
export function sameSelectionDuplicateDescriptors(actual: unknown, expected: unknown): boolean {
  if (actual === expected) return true;
  if (!actual || !expected || typeof actual !== 'object' || typeof expected !== 'object'
    || Array.isArray(actual) !== Array.isArray(expected)) return false;
  const a = actual as Record<string, unknown>, b = expected as Record<string, unknown>;
  if (![Array.isArray(actual) ? Array.prototype : Object.prototype, null].includes(Object.getPrototypeOf(actual))) return false;
  const keys = Reflect.ownKeys(b);
  return Reflect.ownKeys(a).length === keys.length && keys.every(key => {
    const left = Object.getOwnPropertyDescriptor(a, key), right = Object.getOwnPropertyDescriptor(b, key)!;
    return !!left && 'value' in left && left.enumerable === right.enumerable
      && sameSelectionDuplicateDescriptors(left.value, right.value);
  });
}
