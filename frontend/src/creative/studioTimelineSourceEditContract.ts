import { ApiError } from '../api';
import type { StudioAsset } from './studioClient';
import { maskSha256 } from './studioManualMaskContract';
import { checkedTimeline, cloneTimeline, timelineInputKey, timelineSourcesCurrent, type StudioTimelineClip, type StudioTimelineRow, type StudioTimelineSource, type StudioTimelineTrack } from './studioTimelineTypes';

type TimelineSourceInsertTrack = Omit<StudioTimelineTrack, 'muted' | 'gain_db'> & Partial<Pick<StudioTimelineTrack, 'muted' | 'gain_db'>>;
export type TimelineSourceOperation = { op: 'track.insert'; track: TimelineSourceInsertTrack } | { op: 'clip.insert'; track_id: string; clip: StudioTimelineClip }
  | { op: 'clip.update'; clip_id: string; changes: { source_snapshot: StudioTimelineSource; in_ms: number; out_ms: number; include_audio?: boolean } };
export type TimelineSourceEditRequest = { expected_version: number; reviewed_timeline_digest: string; request_id: string; operations: TimelineSourceOperation[] };
export type TimelineSourceIntent = { mode: 'NEW_TRACK' | 'INSERT' | 'REPLACE'; asset_id: string; track_id: string; clip_id: string; start_ms: number; in_ms: number; out_ms: number; include_audio: boolean };
const resource = /^[A-Za-z0-9][A-Za-z0-9_-]{0,239}$/;
const invalid = () => { throw new ApiError({ status: 200, code: 'STUDIO_RESPONSE_INVALID', message: '时间线编辑回执与原请求或片段效果不一致，须读取原时间线核对。' }); };
function canonical(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(canonical).join(',')}]`;
  if (value && typeof value === 'object') { const row = value as Record<string, unknown>; return `{${Object.keys(row).sort().map(key => `${JSON.stringify(key)}:${canonical(row[key])}`).join(',')}}`; }
  return JSON.stringify(value);
}
/** This additive source action cannot send numeric forms whose original Python
 * JSON identity differs from JavaScript. Ordinary Timeline draft editing keeps
 * its existing fractional controls; never round or rewrite the author's body. */
function requestNumbers(value: unknown): void {
  if (typeof value === 'number' && (!Number.isFinite(value) || value !== 0 && Math.abs(value) < 1e-4)) throw new Error('本次来源操作的数字精度无法绑定原编辑回执。请通过原时间线草稿编辑并保存该参数。');
  if (Array.isArray(value)) value.forEach(requestNumbers);
  else if (value && typeof value === 'object') Object.values(value).forEach(requestNumbers);
}
export async function timelineSourceRequestDigest(value: TimelineSourceEditRequest): Promise<string> { requestNumbers(value.operations); return maskSha256(new TextEncoder().encode(canonical(value))); }
const isCurrent = (asset: StudioAsset) => !asset.deleted_at && ['video', 'audio', 'image'].includes(asset.kind) && resource.test(asset.id) && Number.isSafeInteger(asset.version) && asset.version >= 1 && /^[a-f0-9]{64}$/.test(asset.sha256);

/** A bounded author action compiles to the original owner's edit operations. */
export function prepareTimelineSourceEdit(source: StudioTimelineRow, assets: StudioAsset[], intent: TimelineSourceIntent, ids: { track: string; clip: string }): TimelineSourceOperation[] {
  if (!timelineSourcesCurrent(source.timeline, assets)) throw new Error('原时间线素材版本已变化，请先核对并保存当前来源。');
  const asset = assets.find(row => row.id === intent.asset_id && isCurrent(row)); if (!asset) throw new Error('请选择当前可访问的正式视频、音频或图片版本。');
  const extended = source.timeline.schema_version === 2, kind = asset.kind as StudioTimelineSource['asset_kind'];
  if (kind === 'image' && !extended) throw new Error('静态图片需要先明确采用扩展时间线版本 2 并保存。');
  if (![intent.start_ms, intent.in_ms, intent.out_ms].every(Number.isSafeInteger) || intent.start_ms < 0 || intent.in_ms < 0 || intent.out_ms <= intent.in_ms || intent.out_ms > 36_000_000 || typeof intent.include_audio !== 'boolean') throw new Error('请明确填写有效摆放时间和来源起止范围。');
  if (kind === 'image' && intent.in_ms !== 0 || intent.include_audio && (kind !== 'video' || !extended)) throw new Error('图片入点为零；视频原音轨仅在扩展视频片段中明确加入。');
  const snapshot: StudioTimelineSource = { id: asset.id, kind: 'ASSET', asset_kind: kind, version: asset.version, digest: asset.sha256 };
  const operations: TimelineSourceOperation[] = [], tracks = source.timeline.tracks;
  if (intent.mode === 'REPLACE') {
    const track = tracks.find(row => row.id === intent.track_id), clip = track?.clips.find(row => row.id === intent.clip_id);
    if (!track || !clip || track.locked || (track.kind === 'AUDIO' ? kind !== 'audio' : kind === 'audio')) throw new Error('替换需选择未锁定、素材类型兼容的原片段。');
    operations.push({ op: 'clip.update', clip_id: clip.id, changes: { source_snapshot: snapshot, in_ms: intent.in_ms, out_ms: intent.out_ms,
      ...(track.kind === 'VIDEO' && extended ? { include_audio: intent.include_audio } : {}) } });
  } else {
    let track = tracks.find(row => row.id === intent.track_id);
    if (intent.mode === 'NEW_TRACK') {
      if (!resource.test(ids.track) || tracks.some(row => row.id === ids.track)) throw new Error('新轨道标识需独立且有效。');
      const order = Array.from({ length: 8 }, (_, index) => index).find(value => !tracks.some(row => row.order === value));
      if (order === undefined) throw new Error('已达到八条轨道上限。');
      track = { id: ids.track, kind: kind === 'audio' ? 'AUDIO' : 'VIDEO', order, muted: false, gain_db: 0, clips: [], ...(extended ? { role: kind === 'audio' ? 'DIALOGUE' : 'OVERLAY', locked: false } : {}) };
      operations.push({ op: 'track.insert', track: cloneTimeline(track) });
    }
    if (!track || track.locked || (track.kind === 'AUDIO' ? kind !== 'audio' : kind === 'audio') || !resource.test(ids.clip) || tracks.some(row => row.clips.some(clip => clip.id === ids.clip))) throw new Error('加入需选择未锁定、素材类型兼容的轨道及独立片段标识。');
    const clip: StudioTimelineClip = { id: ids.clip, source_snapshot: snapshot, start_ms: intent.start_ms, in_ms: intent.in_ms, out_ms: intent.out_ms,
      ...(track.kind === 'VIDEO' ? { x: 0, y: 0, width: source.timeline.width, height: source.timeline.height } : {}),
      ...(extended ? { speed_num: 1, speed_den: 1, muted: false, gain_db: 0, fade_in_ms: 0, fade_out_ms: 0,
        ...(track.kind === 'VIDEO' ? { opacity: 1, include_audio: intent.include_audio } : {}) } : {}) };
    operations.push({ op: 'clip.insert', track_id: track.id, clip });
  }
  applyTimelineSourceEdits(source, operations); return operations;
}

/** Only these three existing operations are exposed by this source Inspector. */
export function applyTimelineSourceEdits(source: StudioTimelineRow, operations: TimelineSourceOperation[]) {
  if (!Array.isArray(operations) || !operations.length || operations.length > 2) throw new Error('正式素材操作需包含一至两项原编辑操作。');
  const timeline = cloneTimeline(source.timeline);
  for (const operation of operations) {
    if (!operation || typeof operation !== 'object' || Array.isArray(operation)) throw new Error('原编辑操作无效。');
    if (operation.op === 'track.insert') {
      if (Object.keys(operation).length !== 2 || Object.keys(operation).some(key => !['op', 'track'].includes(key)) || !operation.track || operation.track.clips.length || timeline.tracks.some(row => row.id === operation.track.id)) throw new Error('新轨道必须为空，并在同一批次明确加入首个片段。');
      timeline.tracks.push({ ...cloneTimeline(operation.track), muted: operation.track.muted === undefined ? false : operation.track.muted, gain_db: operation.track.gain_db === undefined ? 0 : operation.track.gain_db });
    } else if (operation.op === 'clip.insert') {
      const track = timeline.tracks.find(row => row.id === operation.track_id);
      if (Object.keys(operation).length !== 3 || Object.keys(operation).some(key => !['op', 'track_id', 'clip'].includes(key)) || !track || track.locked) throw new Error('目标轨道不可用或已锁定。');
      track.clips.push(cloneTimeline(operation.clip));
    } else if (operation.op === 'clip.update') {
      const track = timeline.tracks.find(row => row.clips.some(clip => clip.id === operation.clip_id)), clip = track?.clips.find(row => row.id === operation.clip_id);
      if (Object.keys(operation).length !== 3 || Object.keys(operation).some(key => !['op', 'clip_id', 'changes'].includes(key)) || !track || track.locked || !clip || !operation.changes
        || Object.keys(operation.changes).some(key => !['source_snapshot', 'in_ms', 'out_ms', 'include_audio'].includes(key)) || !['source_snapshot', 'in_ms', 'out_ms'].every(key => Object.hasOwn(operation.changes, key))) throw new Error('原片段替换字段无效或轨道已锁定。');
      Object.assign(clip, cloneTimeline(operation.changes));
    } else throw new Error('此入口仅支持正式素材加入或替换。');
  }
  return checkedTimeline(timeline);
}
export function checkedTimelineSourceRequest(source: StudioTimelineRow, body: TimelineSourceEditRequest) {
  if (!body || Object.keys(body).length !== 4 || Object.keys(body).some(key => !['expected_version', 'reviewed_timeline_digest', 'request_id', 'operations'].includes(key))
    || body.expected_version !== source.version || body.reviewed_timeline_digest !== source.timeline_digest || !/^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$/.test(body.request_id)) throw new Error('本次编辑需要原时间线的确切版本、摘要与独立请求标识。');
  requestNumbers(body.operations); applyTimelineSourceEdits(source, body.operations); return cloneTimeline(body);
}
export async function checkedTimelineSourceEffect(row: StudioTimelineRow, source: StudioTimelineRow, body: TimelineSourceEditRequest): Promise<StudioTimelineRow> {
  const input = checkedTimelineSourceRequest(source, body), receipt = row.edit_receipt;
  if (!receipt || row.id !== source.id || row.version !== source.version + 1 || row.title !== source.title || receipt.request_id !== input.request_id
    || receipt.request_digest !== await timelineSourceRequestDigest(input) || receipt.input_version !== source.version || receipt.input_digest !== source.timeline_digest || receipt.output_digest !== row.timeline_digest
    || timelineInputKey({ title: row.title, timeline: row.timeline }) !== timelineInputKey({ title: source.title, timeline: applyTimelineSourceEdits(source, input.operations) })) invalid();
  return row;
}
