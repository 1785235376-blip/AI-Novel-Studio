import type { CreativeInput, DirectorSceneNote } from './types';

export const DIRECTOR_CAMERA_FIELDS = [
  { key: 'shot_size', label: '景别', max: 80 },
  { key: 'camera_angle', label: '机位角度', max: 80 },
  { key: 'camera_motion', label: '运镜', max: 80 },
  { key: 'lens', label: '镜头与焦距', max: 1000 },
  { key: 'composition', label: '构图', max: 4000 },
] as const;
export type DirectorCameraField = typeof DIRECTOR_CAMERA_FIELDS[number]['key'];
export const cameraValueLabel = (value: DirectorSceneNote[DirectorCameraField]) => value == null || value === '' ? '（空，应用后清空此项）' : value;

/** An author-only patch: never derive notes, renumber IDs or touch downstream owners. */
export function previewDirectorCameraReuse(draft: CreativeInput, sceneId: string, sourceId: string, targetIds: string[], fields: DirectorCameraField[]) {
  if (draft.mode !== 'DIRECTOR' || draft.scenes.filter(scene => scene.id === sceneId).length !== 1) throw new Error('请先选择当前导演场景。');
  const ids = draft.director_notes.map(note => note.id);
  if (new Set(ids).size !== ids.length) throw new Error('导演调度 ID 重复，请先核对。');
  const source = draft.director_notes.find(note => note.id === sourceId && note.scene_id === sceneId);
  if (!source || !targetIds.length || new Set(targetIds).size !== targetIds.length || targetIds.includes(sourceId)) throw new Error('请选择一个来源和其他目标调度。');
  if (!fields.length || new Set(fields).size !== fields.length || fields.some(key => !DIRECTOR_CAMERA_FIELDS.some(field => field.key === key))) throw new Error('请明确选择要复用的摄影参数。');
  for (const key of fields) {
    const value = source[key], field = DIRECTOR_CAMERA_FIELDS.find(field => field.key === key)!;
    if (value != null && (typeof value !== 'string' || Array.from(value).length > field.max) || value == null && field.max === 80) throw new Error('来源摄影参数无效，请先修正。');
  }
  if (targetIds.some(id => !draft.director_notes.some(note => note.id === id && note.scene_id === sceneId))) throw new Error('目标必须是当前场景的原导演调度。');
  const changes: { id: string; number: number; field: DirectorCameraField; before: DirectorSceneNote[DirectorCameraField]; after: DirectorSceneNote[DirectorCameraField] }[] = [];
  const director_notes = draft.director_notes.map(note => {
    if (!targetIds.includes(note.id)) return note;
    const next = { ...note };
    for (const field of fields) {
      if (note[field] === source[field]) continue;
      changes.push({ id: note.id, number: note.number, field, before: note[field], after: source[field] });
      if (source[field] === undefined) delete next[field];
      else Object.assign(next, { [field]: source[field] });
    }
    return next;
  });
  return { draft: { ...draft, director_notes }, changes };
}
