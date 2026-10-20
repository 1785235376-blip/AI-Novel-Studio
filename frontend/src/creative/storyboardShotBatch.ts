import { creativeTextLength, type CreativeInput } from './types';

export const STORYBOARD_SHOT_BATCH_FIELDS = [
  { key: 'shot_size', label: '景别' },
  { key: 'camera_angle', label: '机位角度' },
  { key: 'camera_motion', label: '运镜' },
] as const;
export type StoryboardShotBatchField = typeof STORYBOARD_SHOT_BATCH_FIELDS[number]['key'];
export const STORYBOARD_SHOT_BATCH_LIMIT = 200;
/** Synchronous admission supplied by the original draft owner, without a second store. */
export type StoryboardShotBatchOwner = { revision: () => number; isCurrent: () => boolean };

/** A single authored text field; original Save retains validation and authority. */
export function previewStoryboardShotBatch(draft: CreativeInput, sceneId: string, selected: readonly string[], field: StoryboardShotBatchField, value: string) {
  if (draft.mode !== 'STORYBOARD') throw new Error('请选择分镜作者草稿。');
  if (!STORYBOARD_SHOT_BATCH_FIELDS.some(item => item.key === field)) throw new Error('请选择受支持的镜头文字字段。');
  if (typeof value !== 'string' || !value.trim() || creativeTextLength(value) > 80) throw new Error('新值须为 1–80 个 Unicode 字符，且不能只有空白。');
  if (!draft.shots.length || draft.shots.length > STORYBOARD_SHOT_BATCH_LIMIT
    || new Set(draft.shots.map(shot => shot.id)).size !== draft.shots.length || draft.shots.some(shot => !shot.id)) throw new Error('请先核对镜头数量与唯一身份。');
  if (!sceneId || new Set(draft.scenes.map(scene => scene.id)).size !== draft.scenes.length || !draft.scenes.some(scene => scene.id === sceneId)) throw new Error('请明确选择当前文档的唯一场景。');
  const selectedIds = new Set(selected);
  if (!selected.length || selected.length > STORYBOARD_SHOT_BATCH_LIMIT || selectedIds.size !== selected.length) throw new Error('请明确选择 1–200 个不同镜头。');
  const targets = draft.shots.filter(shot => selectedIds.has(shot.id));
  if (targets.length !== selected.length || targets.some(shot => shot.scene_id !== sceneId || typeof shot[field] !== 'string')) throw new Error('所选镜头不属于当前场景或已变化，请重新选择。');
  const rows = targets.map(shot => ({ id: shot.id, number: shot.number, before: shot[field], after: value }));
  const changedIds = new Set(rows.filter(row => row.before !== row.after).map(row => row.id));
  return { field, rows, changedCount: changedIds.size,
    draft: changedIds.size ? { ...draft, shots: draft.shots.map(shot => changedIds.has(shot.id) ? { ...shot, [field]: value } : shot) } : draft };
}
