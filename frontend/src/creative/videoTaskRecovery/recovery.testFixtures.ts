import { compileCanvasVideoTimeline, type CanvasVideoTaskCommand, type CanvasVideoTaskJob, type CanvasVideoTrimTaskBinding } from '../canvasVideoTrimTask';

export const hash = (letter: string) => letter.repeat(64);
export function recoveryFixture(includeAudio?: boolean) {
  const command: CanvasVideoTaskCommand = {
    contract: 'studio-canvas-video-trim/1', operation_id: 'm9.timeline.multitrack', request_id: 'original-request',
    provider_id: null, model_id: null, prompt: '', allow_cloud: false, license_note: '',
    parameters: { in_ms: 1000, out_ms: 1600, ...(includeAudio === undefined ? {} : { include_audio: includeAudio }) },
    source_snapshots: [{ id: 'video-source', kind: 'ASSET', asset_kind: 'video', version: 2, digest: hash('a') }],
    timeline_snapshot: { id: 'original-timeline', version: 3, digest: hash('b') },
    canvas_return: { contract: 'studio-canvas-return/1', project_id: 'project', scope: { mode: 'local', novel_id: 'project' },
      incarnation: 'file:00000000-0000-0000-0000-000000000001', canvas_id: 'original-canvas', canvas_version: 4,
      canvas_digest: hash('c'), card_id: 'original-card',
      source: { id: 'video-source', kind: 'ASSET', asset_kind: 'video', version: 2, digest: hash('a') } },
  };
  const job: CanvasVideoTaskJob = { contract: 'studio-production-job/1', owner: 'timeline', id: 'original-failed-job',
    novel_id: 'project', branch_id: null, version: 5, operation_id: command.operation_id, request_id: command.request_id,
    status: 'FAILED', request_digest: hash('d'), receipt_digest: hash('e'), command: null, canvas_video: structuredClone(command),
    provider: null, execution_recipe: { contract: 'studio-execution-recipe/1', operation_id: command.operation_id,
      adapter: 'LOCAL_FFMPEG', output_profile: 'DELIVERY_H264_MP4', automatic_fallback: false, recipe_digest: hash('f'),
      timeline: compileCanvasVideoTimeline(command.source_snapshots[0], command.parameters),
      export_profile: { preset: 'DELIVERY_H264_MP4', video_bitrate_kbps: 400, audio_bitrate_kbps: 96, crf: 23 } },
    sources: structuredClone(command.source_snapshots), timeline_snapshot: structuredClone(command.timeline_snapshot),
    output_candidate: null, approved_asset_version: null, media_measurement: null, product_acceptance: 'LOCAL_REQUIRED',
    automatic_replay: false, remote_compute_may_continue: false, created_at: '', updated_at: '' };
  const task: CanvasVideoTrimTaskBinding = { source: structuredClone(command.source_snapshots[0]),
    returnBinding: structuredClone(command.canvas_return), isCurrent: () => true };
  return { job, task };
}
