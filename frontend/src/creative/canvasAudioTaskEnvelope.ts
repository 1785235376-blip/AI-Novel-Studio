/** Closed projection of the original AudioJob trim controls; owns no execution state. */
export type CanvasAudioTaskEnvelope = {
  in_ms: number;
  out_ms: number;
  gain_db?: number;
  fade_in_ms?: number;
  fade_out_ms?: number;
};

const controls = new Set(['in_ms', 'out_ms', 'gain_db', 'fade_in_ms', 'fade_out_ms']);
// Only the original recorded MediaParameters null projection is admissible.
const recordedNullParameters = new Set(['width', 'height', 'steps', 'seed', 'cfg', 'negative_prompt',
  'size', 'quality', 'duration_seconds', 'frame_rate', 'voice_id', 'speech_rate']);
const integer = (value: unknown, maximum: number): value is number =>
  typeof value === 'number' && Number.isSafeInteger(value) && value >= 0 && value <= maximum;

export function checkedCanvasAudioTaskEnvelope(value: unknown, recorded = false): CanvasAudioTaskEnvelope | undefined {
  if (!value || typeof value !== 'object' || Array.isArray(value)
    || !Object.hasOwn(value, 'in_ms') || !Object.hasOwn(value, 'out_ms')) return;
  const parameters = value as Record<string, unknown>;
  if (Reflect.ownKeys(parameters).some(key => typeof key !== 'string'
    || !controls.has(key) && (!recorded || !recordedNullParameters.has(key) || parameters[key] !== null))) return;
  const start = parameters.in_ms, end = parameters.out_ms;
  if (!integer(start, 600_000) || !integer(end, 600_000) || end <= start || end - start > 120_000) return;
  const result: CanvasAudioTaskEnvelope = { in_ms: start, out_ms: end };
  if (Object.hasOwn(parameters, 'gain_db')) {
    const gain = parameters.gain_db;
    if (typeof gain !== 'number' || !Number.isFinite(gain) || gain < -60 || gain > 12) return;
    result.gain_db = gain;
  }
  for (const key of ['fade_in_ms', 'fade_out_ms'] as const) {
    if (!Object.hasOwn(parameters, key)) continue;
    const fade = parameters[key];
    if (!integer(fade, 120_000)) return;
    result[key] = fade;
  }
  if ((result.fade_in_ms ?? 0) + (result.fade_out_ms ?? 0) > end - start) return;
  return result;
}
