/** Fixed local processing profile; no user-supplied filter, model or new job owner. */
export const AUDIO_DENOISE_PROFILE = 'STATIONARY_FFT_V1';
export type AudioDenoiseProof = {
  contract: 'studio-audio-fft-denoise/1'; profile: typeof AUDIO_DENOISE_PROFILE;
  source_id: string; source_version: number; source_sha256: string; in_ms: number; out_ms: number;
  sample_rate: number; channels: number; selected_frames: number; selected_pcm_sha256: string;
  source_peak_s16: number; source_rms_s16: number; output_frames: number; output_pcm_sha256: string;
  output_peak_s16: number; output_rms_s16: number; output_sha256: string;
};
type Parameters = Record<string, string | number>;
export function validDenoiseParameters(p: Parameters) {
  return p.denoise_profile === AUDIO_DENOISE_PROFILE && Number(p.out_ms) - Number(p.in_ms) >= 1000
    && ['output_format', 'target_peak_dbfs', 'target_lufs'].every(key => p[key] === undefined)
    && ['gain_db', 'fade_in_ms', 'fade_out_ms'].every(key => Number(p[key] ?? 0) === 0);
}
export function validDenoiseProof(value: unknown, p: Parameters, source: unknown, outputSha: unknown): value is AudioDenoiseProof {
  const record = (v: unknown): v is Record<string, unknown> => !!v && typeof v === 'object' && !Array.isArray(v);
  if (!record(value) || !record(source) || !validDenoiseParameters(p)) return false;
  const keys = ['contract', 'profile', 'source_id', 'source_version', 'source_sha256', 'in_ms', 'out_ms', 'sample_rate', 'channels',
    'selected_frames', 'selected_pcm_sha256', 'source_peak_s16', 'source_rms_s16', 'output_frames', 'output_pcm_sha256', 'output_peak_s16', 'output_rms_s16', 'output_sha256'];
  if (Object.keys(value).length !== keys.length || keys.some(key => !Object.hasOwn(value, key))
    || value.contract !== 'studio-audio-fft-denoise/1' || value.profile !== AUDIO_DENOISE_PROFILE) return false;
  for (const key of ['source_version', 'in_ms', 'out_ms', 'sample_rate', 'channels', 'selected_frames', 'output_frames', 'source_peak_s16', 'output_peak_s16']) {
    if (typeof value[key] !== 'number' || !Number.isSafeInteger(value[key])) return false;
  }
  for (const key of ['source_rms_s16', 'output_rms_s16']) if (typeof value[key] !== 'number' || !Number.isFinite(value[key]) || value[key] < 0 || value[key] > 32768) return false;
  for (const key of ['source_sha256', 'selected_pcm_sha256', 'output_pcm_sha256', 'output_sha256']) if (typeof value[key] !== 'string' || !/^[a-f0-9]{64}$/.test(value[key])) return false;
  const v = value as AudioDenoiseProof, rate = Number(p.sample_rate ?? 48000), channels = Number(p.channels ?? 2);
  return source.kind === 'ASSET' && source.asset_kind === 'audio' && v.source_id === source.id && v.source_version === source.version && v.source_sha256 === source.digest
    && v.source_version > 0 && v.in_ms === p.in_ms && v.out_ms === p.out_ms && v.sample_rate === rate && v.channels === channels
    && v.in_ms * rate % 1000 === 0 && v.out_ms * rate % 1000 === 0 && v.selected_frames > 0
    && v.selected_frames === (v.out_ms - v.in_ms) * rate / 1000 && v.output_frames === v.selected_frames
    && v.source_peak_s16 >= v.source_rms_s16 && v.source_peak_s16 <= 32768 && v.output_peak_s16 >= v.output_rms_s16 && v.output_peak_s16 <= 32768
    && v.output_sha256 === outputSha;
}
