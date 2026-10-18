import { checkedTimeline, type StudioTimeline, type StudioTimelineColorAdjustment } from '../creative/studioTimelineTypes';
import type { NleOwnerOperation } from './timelineOpsTypes';

/** Basic color is one existing clip.update, scoped to the single reviewed clip. */
export function clipColorOperation(timeline: unknown, selected: string[], color: StudioTimelineColorAdjustment | null): NleOwnerOperation {
  const operation: NleOwnerOperation = { op: 'clip.update', clip_id: selected[0], changes: { color_adjustment: color } };
  applyClipColorOperation(timeline, selected, operation);
  return operation;
}

export function applyClipColorOperation(input: unknown, selected: string[], value: unknown): StudioTimeline {
  const timeline = checkedTimeline(input);
  if (timeline.schema_version !== 2 || selected.length !== 1) throw new Error('基础调色需要扩展版本 2，并且只选择一个视频或图片片段。');
  const track = timeline.tracks.find(row => row.clips.some(clip => clip.id === selected[0]));
  const clip = track?.clips.find(row => row.id === selected[0]);
  if (!track || track.kind !== 'VIDEO' || track.locked || !clip) throw new Error('请选择未锁定的视频轨道片段，音频片段不能调色。');
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('基础调色指令无效。');
  const operation = value as Record<string, unknown>, changes = operation.changes;
  if (Object.keys(operation).length !== 3 || operation.op !== 'clip.update' || operation.clip_id !== clip.id
    || !changes || typeof changes !== 'object' || Array.isArray(changes)
    || Object.keys(changes).length !== 1 || !Object.hasOwn(changes, 'color_adjustment')) throw new Error('基础调色只允许修改当前所选片段的亮度、对比度和饱和度。');
  const color = (changes as Record<string, unknown>).color_adjustment;
  if (color === null) delete clip.color_adjustment;
  else clip.color_adjustment = color as StudioTimelineColorAdjustment;
  return checkedTimeline(timeline);
}
