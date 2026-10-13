import { createHash } from 'node:crypto';
import type { StudioAsset } from './studioClient';
import type { AudioWavMeasurement, MediaCommand, ProductionJob, ProductionPreview, ProductionRecipe } from './studioProductionClient';
export const audioProject = 'audio-wav-project';
// Deterministic PCM bytes for private candidate lifetime/hash checks. This is a
// structural frontend fixture, not evidence of native ffmpeg processing.
export function audioBytes(command = audioCommand()): Uint8Array {
  const rate = Number(command.parameters.sample_rate ?? 48000), channels = Number(command.parameters.channels ?? 2);
  const frames = Math.round((Number(command.parameters.out_ms) - Number(command.parameters.in_ms)) * rate / 1000), dataBytes = frames * channels * 2;
  const bytes = Buffer.alloc(44 + dataBytes); bytes.write('RIFF', 0); bytes.writeUInt32LE(36 + dataBytes, 4); bytes.write('WAVEfmt ', 8);
  bytes.writeUInt32LE(16, 16); bytes.writeUInt16LE(1, 20); bytes.writeUInt16LE(channels, 22); bytes.writeUInt32LE(rate, 24);
  bytes.writeUInt32LE(rate * channels * 2, 28); bytes.writeUInt16LE(channels * 2, 32); bytes.writeUInt16LE(16, 34); bytes.write('data', 36); bytes.writeUInt32LE(dataBytes, 40);
  return new Uint8Array(bytes);
}
export const audioAssets = (): StudioAsset[] => [{ id: 'audio-source', novel_id: audioProject, branch_id: null, version: 2, kind: 'audio', media_type: 'audio/wav',
  filename: 'source.wav', sha256: 'a'.repeat(64), size: 192044, created_at: '', updated_at: '' }];
export const audioCommand = (requestId = 'audio-request', controls: Record<string, number> = {}): MediaCommand => ({ operation_id: 'm8.audio.trim', request_id: requestId,
  provider_id: null, model_id: null, prompt: '', parameters: { in_ms: 100, out_ms: 600, ...controls },
  source_snapshots: audioAssets().map(row => ({ id: row.id, kind: 'ASSET', asset_kind: 'audio', version: row.version, digest: row.sha256 })), allow_cloud: false, license_note: '' });
export const audioRecipe = (command = audioCommand()): ProductionRecipe => ({ contract: 'studio-execution-recipe/1', operation_id: 'm8.audio.trim', adapter: 'LOCAL_FFMPEG',
  parameters: { ...command.parameters }, output_profile: `PCM_S16LE_WAV_${command.parameters.sample_rate ?? 48000}_${command.parameters.channels === 1 ? 'MONO' : 'STEREO'}`,
  automatic_fallback: false, recipe_digest: 'd'.repeat(64) });
export const audioPreview = (command = audioCommand()): ProductionPreview => ({ contract: 'studio-production-preview/1', novel_id: audioProject, branch_id: null,
  operation_id: command.operation_id, request_id: command.request_id, command, preview_digest: 'e'.repeat(64), request_digest: 'f'.repeat(64),
  sources: command.source_snapshots.map(snapshot => ({ snapshot, measured: { media_type: 'audio/wav', extension: 'wav', duration_ms: 1000, sample_rate: 48000, channels: 2, validation: 'DECODED' } })),
  provider: null, execution_recipe: audioRecipe(command), product_acceptance: 'LOCAL_REQUIRED', execution_available: true, automatic_dispatch: false,
  output_policy: 'PRIVATE_CANDIDATE_THEN_EXPLICIT_REVIEW' });
export const audioMeasurement = (command = audioCommand()): AudioWavMeasurement => ({ duration_ms: Number(command.parameters.out_ms) - Number(command.parameters.in_ms),
  byte_count: audioBytes(command).length, sample_rate: Number(command.parameters.sample_rate ?? 48000), channels: command.parameters.channels === 1 ? 1 : 2,
  sample_width: 2, container: 'wav', audio_codec: 'pcm_s16le', profile_validation: 'PCM_DECODED', output_sha256: createHash('sha256').update(audioBytes(command)).digest('hex') });
export const audioJob = (status: ProductionJob['status'] = 'QUEUED', version = 1, command = audioCommand()): ProductionJob => {
  const rendered = ['AWAITING_REVIEW', 'APPROVED'].includes(status), measured = audioMeasurement(command);
  return { contract: 'studio-production-job/1', owner: 'audio', id: 'audio-job', novel_id: audioProject, branch_id: null, version, operation_id: command.operation_id,
    request_id: command.request_id, status, request_digest: 'f'.repeat(64), receipt_digest: rendered ? 'd'.repeat(64) : null,
    output_candidate: rendered ? { id: 'audio-candidate', version: 1, digest: measured.output_sha256, kind: 'audio' } : null,
    product_acceptance: 'LOCAL_REQUIRED', automatic_replay: false, remote_compute_may_continue: false, timeline_snapshot: null,
    sources: command.source_snapshots, command, provider: null, execution_recipe: audioRecipe(command), approved_asset_version: status === 'APPROVED' ? 2 : null,
    media_measurement: rendered ? measured : null, created_at: '', updated_at: '' };
};
