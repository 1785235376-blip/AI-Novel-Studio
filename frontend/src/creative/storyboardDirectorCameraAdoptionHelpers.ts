import { DIRECTOR_CAMERA_FIELDS, type DirectorCameraField } from './directorCameraReuseHelpers';
import type { CreativeInput } from './types';

export const STORYBOARD_CAMERA_TARGET_LIMIT = 4;

/** Use only the existing author-owned, explicitly linked direction snapshot. */
export function previewStoryboardDirectorCameraAdoption(draft: CreativeInput, sceneId: string,
  sourceId: string, targetIds: string[], fields: DirectorCameraField[]) {
  if (draft.mode !== 'STORYBOARD' || draft.scenes.filter(scene => scene.id === sceneId).length !== 1)
    throw new Error('请先选择当前分镜场景。');
  const noteIds = draft.director_notes.map(note => note.id), shotIds = draft.shots.map(shot => shot.id);
  if (new Set(noteIds).size !== noteIds.length || new Set(shotIds).size !== shotIds.length)
    throw new Error('调度或镜头 ID 重复，请先核对。');
  const source = draft.director_notes.find(note => note.id === sourceId && note.scene_id === sceneId);
  if (!source || !targetIds.length || targetIds.length > STORYBOARD_CAMERA_TARGET_LIMIT || new Set(targetIds).size !== targetIds.length)
    throw new Error('请选择一个原调度及 1–4 个已关联镜头。');
  if (!fields.length || new Set(fields).size !== fields.length || fields.some(key => !DIRECTOR_CAMERA_FIELDS.some(field => field.key === key)))
    throw new Error('请明确选择要采用的摄影字段。');
  const values = new Map<DirectorCameraField, string>();
  for (const key of fields) {
    const field = DIRECTOR_CAMERA_FIELDS.find(field => field.key === key)!, raw = source[key];
    if (raw == null && field.max === 80 || raw != null && (typeof raw !== 'string' || Array.from(raw).length > field.max))
      throw new Error('原调度摄影参数无效，请先核对。');
    values.set(key, raw ?? '');
  }
  for (const id of targetIds) {
    const shot = draft.shots.find(row => row.id === id), bindings = shot?.director_note_ids;
    if (!shot || shot.scene_id !== sceneId || !Array.isArray(bindings) || !bindings.includes(sourceId)
      || new Set(bindings).size !== bindings.length
      || bindings.some(binding => !draft.director_notes.some(note => note.id === binding && note.scene_id === sceneId)))
      throw new Error('目标必须是当前场景中已明确关联该调度、且来源绑定完整的镜头。');
  }
  const changes: { id: string; number: number; field: DirectorCameraField; before: string; after: string }[] = [];
  const shots = draft.shots.map(shot => {
    if (!targetIds.includes(shot.id)) return shot;
    const patch: Partial<typeof shot> = {};
    for (const field of fields) {
      const after = values.get(field)!;
      if (shot[field] === after) continue;
      changes.push({ id: shot.id, number: shot.number, field, before: shot[field], after });
      Object.assign(patch, { [field]: after });
    }
    return Object.keys(patch).length ? { ...shot, ...patch } : shot;
  });
  return { draft: changes.length ? { ...draft, shots } : draft, changes };
}
