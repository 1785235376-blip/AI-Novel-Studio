/**
 * [HERMIA-FE-20261025 AUDIO-M10] Second media slice (audio) over the SAME registry / task feed / results / history.
 * Pure projections of existing owner data (studioProductionClient ProductionJob, m8.audio.*). No second state system,
 * no new endpoint, no model call. Raw ids stay in data-* attributes; text here is human-readable only.
 *
 * Exact interface gaps (static read of 575501b9):
 *  G-AUD-1 list: creative/studioProductionClient.ts:647-649 GET /jobs has no owner/operation filter and no paging (≤1000)
 *          → audio list = client-side filter of the shared bounded list (said on screen).
 *  G-AUD-2 detail: studioProductionClient.ts:651-653 get(owner,id) exists and is owner-generic → covered, no audio-specific fields beyond media_measurement.
 *  G-AUD-3 candidate: studioProductionClient.ts:659 candidate(job) returns an unvalidated Blob (no MIME / digest check in client)
 *          → preview checks job.output_candidate.kind==='audio' and blob.type starts with 'audio/' before playing.
 *  G-AUD-4 adopt location: studioProductionClient.ts:407-411 canvas_return for asset_kind 'audio' is only accepted with
 *          LOCAL_FFMPEG + PCM_S16LE_WAV_48000_STEREO (i.e. m8.audio.trim); speech/music/effects jobs carry no canvas_return
 *          → integration/useUnifiedLoop.ts:20-24 targetOf() = undefined → results/history panels say "没有记录作品位置".
 *  G-AUD-5 history: creative/studioCanvasViewClient.ts:103-104 history/restore is canvas-level only; there is no
 *          per-audio-asset version history endpoint → audio history only exists for trim jobs placed on a canvas card.
 *  G-AUD-6 review: studioProductionClient.ts:658 review(job) is owner-generic → reused via results/adoptFlow (explicit confirm).
 *  G-AUD-7 cost: taskcenter/taskCenterContract.ts:200-204 cost always UNKNOWN → 未知.
 */
import type {ProductionJob} from '../../creative/studioProductionClient';
import type {TaskRef} from '../contracts';
import type {MediaSlice} from '../registry/workspaceRegistry';

export type MediaFilter = MediaSlice | 'all';
export const MEDIA_FILTER_TEXT: Record<MediaFilter, string> = {all: '全部', image: '图片', audio: '音频'};
export const AUDIO_LIST_GAP_TEXT = '服务端任务列表不能按媒介筛选：这里只是在已读取的列表里挑出音频任务。';

/** Media of a task row. Only production jobs carry an owner; task-center rows are not media-typed (→ null). */
export function mediaOfRef(ref: Pick<TaskRef, 'source' | 'owner'>): MediaSlice | null {
  if (ref.source !== 'production-job') return null;
  return ref.owner === 'audio' ? 'audio' : ref.owner === 'image' ? 'image' : null;
}
export function filterByMedia<T extends Pick<TaskRef, 'source' | 'owner'>>(items: readonly T[], f: MediaFilter): T[] {
  return f === 'all' ? items.slice() : items.filter(t => mediaOfRef(t) === f);
}

const OP_TEXT: Record<string, string> = {'m8.audio.speech': '配音', 'm8.audio.music': '音乐', 'm8.audio.effects': '音效', 'm8.audio.trim': '音频裁剪'};
export const audioOperationText = (op: string) => OP_TEXT[op] ?? '音频任务';

export interface AudioCandidateInfo {
  playable: boolean;
  /** human sentence; never an id or code */
  text: string;
  durationText: string | null;
  formatText: string | null;
  hasWorkLocation: boolean;
}
export function audioCandidateInfo(job: ProductionJob): AudioCandidateInfo {
  const hasWorkLocation = !!job.command?.canvas_return;
  const m = job.media_measurement as {duration_ms?: number; container?: string; sample_rate?: number; channels?: number} | null | undefined;
  const durationText = typeof m?.duration_ms === 'number' ? `${(m.duration_ms / 1000).toFixed(1)} 秒` : null;
  const formatText = m?.container ? `${m.container.toUpperCase()}${m.sample_rate ? ` · ${m.sample_rate / 1000} kHz` : ''}${m.channels ? (m.channels === 1 ? ' · 单声道' : ' · 立体声') : ''}` : null;
  if (job.owner !== 'audio') return {playable: false, text: '这不是音频任务。', durationText: null, formatText: null, hasWorkLocation};
  if (job.status === 'UNKNOWN' || job.needs_reconciliation) return {playable: false, text: '任务结果未知：请先在原任务界面核对，不会自动重试或重新生成。', durationText, formatText, hasWorkLocation};
  if (!job.output_candidate) return {playable: false, text: '这个音频任务还没有返回候选结果。', durationText, formatText, hasWorkLocation};
  if (job.output_candidate.kind !== 'audio') return {playable: false, text: '返回的候选不是音频，不能在这里试听。', durationText, formatText, hasWorkLocation};
  return {playable: true, text: `${audioOperationText(job.operation_id)}候选，可手动试听。试听只读取已返回的文件，不会重新生成。`, durationText, formatText, hasWorkLocation};
}
