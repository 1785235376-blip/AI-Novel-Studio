import type { CreativeDocument } from './types';
import type { PlanningSnapshot } from './studioProductionGraphContract';
/** JSON object member order is transport/storage detail; array order and values remain exact. */
export function sameDirectorSceneScopeContent(left: unknown, right: unknown): boolean {
  const canonical = (value: unknown) => JSON.stringify(value, (_key, item) => item && typeof item === 'object' && !Array.isArray(item)
    ? Object.fromEntries(Object.keys(item).sort().map(key => [key, item[key]])) : item);
  return canonical(left) === canonical(right);
}
export function directorSceneScopeBody(source: CreativeDocument, snapshot: PlanningSnapshot, responsibility: string, sceneIds: string[]) {
  if (source.mode !== 'DIRECTOR' || source.status === 'ARCHIVED' || snapshot.id !== source.id || snapshot.version !== source.version || !/^[a-f0-9]{64}$/.test(snapshot.digest)
      || !responsibility.trim() || Array.from(responsibility).length > 120 || /[\u0000-\u001f\u007f]/.test(responsibility)
      || !sceneIds.length || sceneIds.length > 200 || new Set(sceneIds).size !== sceneIds.length || sceneIds.some(id => !source.scenes.some(scene => scene.id === id))) throw new Error('子导演职责、场景或原版本未通过核对。');
  return { expected_version: source.version, mode: 'DIRECTOR' as const, director_scope: { source_digest: snapshot.digest, responsibility, scene_ids: [...sceneIds] } };
}
export function checkedDirectorSceneScopeResult(value: unknown, source: CreativeDocument, snapshot: PlanningSnapshot, responsibility: string, sceneIds: string[]): CreativeDocument {
  directorSceneScopeBody(source,snapshot,responsibility,sceneIds);
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('子导演创建回执无效。');
  const row=value as CreativeDocument & { provenance?: any }, scenes=source.scenes.filter(scene=>sceneIds.includes(scene.id));
  const notes=source.director_notes.filter(note=>sceneIds.includes(note.scene_id));
  const provenance=row.provenance;
  if (typeof row.id !== 'string' || !row.id || row.id===source.id || row.mode!=='DIRECTOR' || row.version!==1 || row.status!=='DRAFT' || typeof row.title!=='string' || !row.title.trim() || Array.from(row.title).length>240
      || row.source_independent!==false || !Array.isArray(row.shots) || row.shots.length || row.video_plan!==null
      || !sameDirectorSceneScopeContent(row.visual_target??null,source.visual_target??null)
      || !sameDirectorSceneScopeContent(row.scenes,scenes) || !sameDirectorSceneScopeContent(row.director_notes,notes)
      || !sameDirectorSceneScopeContent(row.source_documents,{[source.id]:{version:source.version,digest:snapshot.digest}})
      || provenance?.method!=='STRUCTURED_DERIVATION' || provenance.model_called!==false || provenance.source_document_id!==source.id
      || provenance.source_version!==source.version || provenance.input_digest!==snapshot.digest
      || provenance.parameters?.rule_version!=='creative-director-scene-scope-v1' || provenance.parameters.responsibility!==responsibility
      || JSON.stringify(provenance.parameters.scene_ids)!==JSON.stringify(scenes.map(scene=>scene.id))
      || provenance.parameters.copied_approval!==false || provenance.parameters.execution_authority!==false) throw new Error('子导演创建回执与已确认范围不一致，请核对原目录。');
  return row;
}
