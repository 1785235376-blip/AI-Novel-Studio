import type { CanvasAudioTrimTaskBinding } from '../canvasAudioTrimTask';
import type { MediaCommand, ProductionJob, ProductionSource } from '../studioProductionClient';

export function recoveryFixture() {
  const source: ProductionSource = { id: 'audio-source', kind: 'ASSET', asset_kind: 'audio', version: 2, digest: 'a'.repeat(64) };
  const task: CanvasAudioTrimTaskBinding = { source, isCurrent: () => true, returnBinding: {
    contract: 'studio-canvas-return/1', project_id: 'project', scope: { mode: 'local', novel_id: 'project' },
    incarnation: 'file:01234567-89ab-4cde-8fab-0123456789ab', canvas_id: 'canvas', canvas_version: 3,
    canvas_digest: 'b'.repeat(64), card_id: 'audio-card', source: { ...source },
  } };
  const command: MediaCommand = { operation_id: 'm8.audio.trim', request_id: 'original-request', provider_id: null, model_id: null,
    prompt: '', parameters: { in_ms: 0, out_ms: 1000, gain_db: -6, fade_in_ms: 100, fade_out_ms: 200 },
    source_snapshots: [{ ...source }], allow_cloud: false, license_note: 'Synthetic fixture', canvas_return: structuredClone(task.returnBinding) };
  const job: ProductionJob = { contract: 'studio-production-job/1', owner: 'audio', id: 'original-failed-job', novel_id: 'project', branch_id: null,
    version: 4, operation_id: 'm8.audio.trim', request_id: command.request_id, status: 'FAILED', request_digest: 'c'.repeat(64),
    receipt_digest: 'd'.repeat(64), output_candidate: null, error_code: 'LOCAL_RENDER_FAILED', product_acceptance: 'LOCAL_REQUIRED',
    automatic_replay: false, remote_compute_may_continue: false, timeline_snapshot: null, sources: structuredClone(command.source_snapshots),
    command: structuredClone(command), provider: null, execution_recipe: { contract: 'studio-execution-recipe/1', operation_id: 'm8.audio.trim',
      adapter: 'LOCAL_FFMPEG', recipe_digest: 'e'.repeat(64), automatic_fallback: false, parameters: { ...command.parameters },
      output_profile: 'PCM_S16LE_WAV_48000_STEREO' }, approved_asset_version: null, created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z' };
  return { source, task, command, job };
}
