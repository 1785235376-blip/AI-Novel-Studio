/** The existing A08 CameraGrammar wire contract, authored on original documents. */
export type CameraPoint = { x: number; y: number };
export type CameraGrammar = {
  scene_purpose: string; viewpoint: string;
  shot_function: 'UNSPECIFIED' | 'ESTABLISHING' | 'OTS' | 'POV' | 'INSERT';
  focus_intent: 'UNSPECIFIED' | 'HOLD' | 'RACK_FOCUS';
  screen_direction: 'UNKNOWN' | 'LEFT_TO_RIGHT' | 'RIGHT_TO_LEFT' | 'STATIONARY';
  coordinate_system: string; character_positions: Record<string, CameraPoint>; axis: string[];
  camera_position: CameraPoint | null; subject_movement: { start: CameraPoint; end: CameraPoint } | null;
  intentional_axis_crossing: boolean; intentions: ('LONG_TAKE' | 'JUMP_CUT')[]; override_reason: string;
};
export const emptyCameraGrammar = (): CameraGrammar => ({ scene_purpose: '', viewpoint: '', shot_function: 'UNSPECIFIED',
  focus_intent: 'UNSPECIFIED', screen_direction: 'UNKNOWN', coordinate_system: '', character_positions: {}, axis: [],
  camera_position: null, subject_movement: null, intentional_axis_crossing: false, intentions: [], override_reason: '' });
const object = (v: unknown): v is Record<string, unknown> => !!v && typeof v === 'object' && !Array.isArray(v);
const closed = (v: Record<string, unknown>, keys: string[]) => Object.keys(v).length === keys.length && keys.every(k => Object.hasOwn(v, k));
const text = (v: unknown, max: number): v is string => typeof v === 'string' && Array.from(v).length <= max;
const point = (v: unknown): v is CameraPoint => object(v) && closed(v, ['x', 'y']) && ['x', 'y'].every(k => typeof v[k] === 'number' && Number.isFinite(v[k]) && Math.abs(v[k] as number) <= 1_000_000);
export function validCameraGrammar(v: unknown): v is CameraGrammar {
  if (!object(v) || !closed(v, Object.keys(emptyCameraGrammar())) || !text(v.scene_purpose, 2000) || !text(v.viewpoint, 500)
    || !text(v.coordinate_system, 120) || !text(v.override_reason, 2000)
    || !['UNSPECIFIED', 'ESTABLISHING', 'OTS', 'POV', 'INSERT'].includes(v.shot_function as string)
    || !['UNSPECIFIED', 'HOLD', 'RACK_FOCUS'].includes(v.focus_intent as string)
    || !['UNKNOWN', 'LEFT_TO_RIGHT', 'RIGHT_TO_LEFT', 'STATIONARY'].includes(v.screen_direction as string)
    || typeof v.intentional_axis_crossing !== 'boolean' || !Array.isArray(v.intentions) || v.intentions.length > 2
    || v.intentions.some(x => !['LONG_TAKE', 'JUMP_CUT'].includes(x)) || !object(v.character_positions)
    || Object.keys(v.character_positions).length > 30 || Object.keys(v.character_positions).some(key => !key.trim() || Array.from(key).length > 240 || /[\u0000-\u001f\u007f]/.test(key))
    || new Set(Object.keys(v.character_positions).map(key => key.trim())).size !== Object.keys(v.character_positions).length
    || !Object.values(v.character_positions).every(point)
    || !Array.isArray(v.axis) || v.axis.some(x => typeof x !== 'string')
    || v.axis.length !== 0 && (v.axis.length !== 2 || new Set(v.axis).size !== 2 || v.axis.some(x => !Object.hasOwn(v.character_positions as object, x)))
    || v.camera_position !== null && !point(v.camera_position)
    || v.subject_movement !== null && (!object(v.subject_movement) || !closed(v.subject_movement, ['start', 'end']) || !point(v.subject_movement.start) || !point(v.subject_movement.end))
    || (v.intentional_axis_crossing || v.intentions.length > 0) && !v.override_reason.trim()) return false;
  return true;
}
