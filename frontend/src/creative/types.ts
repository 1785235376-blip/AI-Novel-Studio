export const WORKSPACE_MODES = [
  { id: 'NOVEL', label: '小说', english: 'Novel' },
  { id: 'SCREENPLAY', label: '剧本', english: 'Screenplay' },
  { id: 'DIRECTOR', label: '导演', english: 'Director' },
  { id: 'STORYBOARD', label: '分镜', english: 'Storyboard' },
  { id: 'PRODUCTION', label: '制作', english: 'Production' },
] as const;
export type WorkspaceMode = typeof WORKSPACE_MODES[number]['id'];
export type CreativeMode = Exclude<WorkspaceMode, 'NOVEL'> | 'VIDEO_PLANNING';
export type Dialogue = { speaker: string; text: string; delivery: string };
export type DirectorNote = { id: string; note: string; shot_size: string; camera_angle: string; camera_motion: string; duration_seconds: number; emotion: string; pacing: string; performance: string };
export type DirectorSceneNote = DirectorNote & { number: number; scene_id: string; blocking: string };
export type CreativeScene = { id: string; sequence: number; source_chapter_id: string | null; heading: string; time: string; location: string; characters: string[]; action: string; dialogue: Dialogue[]; emotion: string; director_notes: DirectorNote[] };
export type CreativeShot = { id: string; number: number; scene_id: string; shot_size: string; camera_angle: string; camera_motion: string; duration_seconds: number; frame_prompt: string; composition: string; color: string; action: string; dialogue: Dialogue[]; sound_effect: string; lens: string; lighting: string; environment: string; sound: string; director_notes: DirectorNote[] };
export type VideoSegment = { shot_id: string; duration_seconds: number; note: string };
export type VideoPlan = { frame_rate: number; width: number; height: number; notes: string; segments: VideoSegment[] };
export type CreativeInput = { mode: CreativeMode; title: string; source_chapter_ids: string[]; source_independent: boolean; scenes: CreativeScene[]; director_notes: DirectorSceneNote[]; shots: CreativeShot[]; video_plan: VideoPlan | null };
export type CreativeDocument = CreativeInput & { id: string; version: number; status: string; created_at: string; updated_at: string; actor_id: string; source_evidence: Record<string, unknown>; source_documents?: Record<string, { version: number; digest: string }> };
export type CreativeCapabilities = { enabled: boolean; modes: CreativeMode[]; can_mutate: boolean };
export type CreativeAsset = { id: string; filename: string; kind: string; media_type: string; size: number };
export type CreativeReferences = { characters: { id: string; name: string }[]; locations: { id: string; name: string }[]; story_routes: { id: string; name: string }[] };
export const modeForDocument = (mode: CreativeMode): WorkspaceMode => mode === 'VIDEO_PLANNING' ? 'PRODUCTION' : mode;
export function documentInput(row: CreativeInput): CreativeInput {
  return { mode: row.mode, title: row.title, source_chapter_ids: [...row.source_chapter_ids], source_independent: row.source_independent, scenes: structuredClone(row.scenes), director_notes: structuredClone(row.director_notes || []), shots: structuredClone(row.shots), video_plan: row.video_plan ? structuredClone(row.video_plan) : null };
}
export const creativeId = () => globalThis.crypto?.randomUUID?.() || `draft-${Date.now()}-${Math.random().toString(16).slice(2)}`;
export function newScene(sequence: number, chapterId?: string): CreativeScene {
  return { id: creativeId(), sequence, source_chapter_id: chapterId || null, heading: `场景 ${sequence}`, time: '', location: '', characters: [], action: '', dialogue: [], emotion: '', director_notes: [] };
}
export function newShot(number: number, sceneId: string): CreativeShot {
  return { id: creativeId(), number, scene_id: sceneId, shot_size: 'MEDIUM', camera_angle: 'EYE_LEVEL', camera_motion: 'STATIC', duration_seconds: 5, frame_prompt: '', composition: '', color: '', action: '', dialogue: [], sound_effect: '', lens: '', lighting: '', environment: '', sound: '', director_notes: [] };
}
export function newDocument(mode: CreativeMode, chapterId?: string): CreativeInput {
  return { mode, title: '', source_chapter_ids: chapterId ? [chapterId] : [], source_independent: false, scenes: [], director_notes: [], shots: [], video_plan: mode === 'PRODUCTION' || mode === 'VIDEO_PLANNING' ? { frame_rate: 24, width: 1920, height: 1080, notes: '', segments: [] } : null };
}
