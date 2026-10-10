import type { ExperimentalClient } from './api';
export type Point = { x: number; y: number };
export type CameraGrammar = {
  shot_function?: 'UNSPECIFIED' | 'ESTABLISHING' | 'OTS' | 'POV' | 'INSERT'; focus_intent?: 'UNSPECIFIED' | 'HOLD' | 'RACK_FOCUS';
  scene_purpose: string; viewpoint: string; screen_direction: 'UNKNOWN' | 'LEFT_TO_RIGHT' | 'RIGHT_TO_LEFT' | 'STATIONARY';
  coordinate_system: string; character_positions: Record<string, Point>; axis: string[]; camera_position: Point | null;
  subject_movement: { start: Point; end: Point } | null; intentional_axis_crossing: boolean; intentions: ('LONG_TAKE' | 'JUMP_CUT')[]; override_reason: string;
};
export type DirectorShot = { id: string; number: number; scene_id: string; shot_size: string; camera_angle: string; camera_motion: string; duration_seconds: number; director?: CameraGrammar };
export type ShotPatch = Omit<DirectorShot, 'id' | 'number' | 'scene_id'> & { shot_id: string; director: CameraGrammar };
export type CameraCheck = { state: string; kind: string; message: string; from_shot_id?: string; to_shot_id?: string; shot_id?: string; cross_products?: string[]; computed?: string };
export type DirectorScreenplay = { id: string; title: string; edit_version: number; shot_status: string; shots: DirectorShot[]; checks: CameraCheck[] };
export type DirectorCatalog = { screenplays: DirectorScreenplay[]; characters: { id: string; name: string }[] };
export type DirectorPlan = { id: string; title: string; version: number; status: string; stale: boolean; screenplay_id: string; screenplay_version: number; shots?: ShotPatch[]; checks?: CameraCheck[] };
export type DirectorComparison = { screenplay_id: string; screenplay_version: number; original: DirectorShot[]; candidates: DirectorPlan[]; comparison_digest: string; application_digests: Record<string, string> };
export const newGrammar = (): CameraGrammar => ({ shot_function: 'UNSPECIFIED', focus_intent: 'UNSPECIFIED', scene_purpose: '', viewpoint: '', screen_direction: 'UNKNOWN', coordinate_system: '', character_positions: {}, axis: [], camera_position: null, subject_movement: null, intentional_axis_crossing: false, intentions: [], override_reason: '' });
export function directorClient(client: ExperimentalClient) {
  return {
    catalog: (signal?: AbortSignal) => client.get<DirectorCatalog>('/director/catalog', signal),
    plans: (signal?: AbortSignal) => client.get<{ items: DirectorPlan[] }>('/director/plans', signal),
    save: (screenplay: DirectorScreenplay, title: string, shots: ShotPatch[]) => client.post<DirectorPlan>('/director/plans', { screenplay_id: screenplay.id, expected_screenplay_version: screenplay.edit_version, title, shots }),
    compare: (plan_ids: string[]) => client.post<DirectorComparison>('/director/compare', { plan_ids }),
    apply: (row: DirectorPlan, comparison_digest: string) => client.post<{ screenplay_id: string; edit_version: number; shot_status: string }>(`/director/plans/${encodeURIComponent(row.id)}/apply`, { expected_version: row.version, comparison_digest }),
    reject: (row: DirectorPlan) => client.post(`/director/plans/${encodeURIComponent(row.id)}/reject`, { expected_version: row.version }),
  };
}
