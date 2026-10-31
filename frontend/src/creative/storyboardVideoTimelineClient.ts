import { checkedTimelineDraft, checkedTimelineRow, type StudioTimeline, type StudioTimelineRow } from './studioTimelineTypes';
import { checkedPlanningSnapshot } from './studioProductionGraphContract';
import { checkedStoryboardVideoResult, storyboardArray, storyboardClosed, storyboardDigest, storyboardInvalid, storyboardRecord, storyboardResource,
  type StoryboardReceipt, type StoryboardTimelineOrigin, type StoryboardVideoResult } from './studioStoryboardContract';
import { sameStoryboardValue } from './studioStoryboardPipelineContract';
export type VideoTimelineClip = { shot_id: string; shot_version: number; shot_digest: string; in_ms: number; out_ms: number | null; include_audio: boolean };
export type VideoTimelineInput = { expected_version: number; reviewed_content_digest: string; title: string; clips: VideoTimelineClip[]; width: number; height: number; fps: number };
export type VideoTimelineCreate = VideoTimelineInput & { request_id: string; preview_digest: string };
export const VIDEO_TIMELINE_CONTRACT = 'studio-storyboard-video-timeline/1';
export type VideoTimelinePreview = { contract: typeof VIDEO_TIMELINE_CONTRACT; document_snapshot: StoryboardReceipt['document_snapshot']; content_digest: string; request: VideoTimelineInput;
  clips: (VideoTimelineClip & { clip_id: string; start_ms: number; out_ms: number; video_result: StoryboardVideoResult;
    measured: { width: number; height: number; duration_ms: number; validation: 'DECODED'; extension: string; media_type: string; codec: string | null } })[];
  timeline: StudioTimeline; preview_digest: string; automatic_dispatch: false; model_called: false; rendered: false };
export type VideoTimelineCreation = { timeline: StudioTimelineRow; storyboard_origin: StoryboardTimelineOrigin; request_id: string; replayed: boolean };
const integer = (v: unknown, min: number, max: number): number => typeof v !== 'number' || !Number.isSafeInteger(v) || v < min || v > max ? storyboardInvalid() : v;
const flags = (r: Record<string, unknown>) => { if (r.automatic_dispatch !== false || r.model_called !== false || r.rendered !== false) storyboardInvalid(); };
const canonical = (v: unknown): string => JSON.stringify(v, (_key, item) => item && typeof item === 'object' && !Array.isArray(item)
  ? Object.fromEntries(Object.keys(item).sort().map(key => [key, item[key]])) : item);
const hashText = async (v: string) => [...new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(v)))].map(v => v.toString(16).padStart(2, '0')).join('');
const hash = (v: unknown) => hashText(canonical(v));
// Fresh creation previews only: the original normalizer serializes these two
// numeric defaults as Python floats. Never use this for edited Timeline hashes.
const creationTimelineCanonical = (v: unknown, key = ''): string => {
  if (typeof v === 'number' && ['gain_db', 'opacity'].includes(key) && Number.isInteger(v)) return v.toFixed(1);
  if (Array.isArray(v)) return '[' + v.map(item => creationTimelineCanonical(item)).join(',') + ']';
  if (v && typeof v === 'object') return '{' + Object.keys(v).sort().map(key => JSON.stringify(key) + ':' + creationTimelineCanonical((v as Record<string, unknown>)[key], key)).join(',') + '}';
  return JSON.stringify(v);
};
function input(receipt: StoryboardReceipt, body: VideoTimelineInput) {
  if (!receipt.approved || body.expected_version !== receipt.document_snapshot.version || body.reviewed_content_digest !== receipt.content_digest
    || !body.title.trim() || body.title.length > 240 || !body.clips.length || body.clips.length > 4 || new Set(body.clips.map(clip => clip.shot_id)).size !== body.clips.length) storyboardInvalid();
  integer(body.width, 16, 1920); integer(body.height, 16, 1080); integer(body.fps, 1, 60);
  for (const clip of body.clips) {
    const shot = receipt.shots.find(shot => shot.shot_id === clip.shot_id);
    if (!shot?.video_result || shot.shot_version !== clip.shot_version || shot.shot_digest !== clip.shot_digest || typeof clip.include_audio !== 'boolean') storyboardInvalid();
    integer(clip.in_ms, 0, 600000); if (clip.out_ms !== null) integer(clip.out_ms, clip.in_ms + 1, 600000);
  }
  return structuredClone(body);
}
export function checkedVideoTimelinePreview(value: unknown, receipt: StoryboardReceipt, body: VideoTimelineInput): VideoTimelinePreview {
  const request = input(receipt, body), r = storyboardRecord(value); flags(r);
  storyboardClosed(r, ['contract','document_snapshot','content_digest','request','clips','timeline','preview_digest','automatic_dispatch','model_called','rendered']);
  const pin = checkedPlanningSnapshot(r.document_snapshot);
  if (r.contract !== VIDEO_TIMELINE_CONTRACT || !sameStoryboardValue(pin, receipt.document_snapshot) || r.content_digest !== receipt.content_digest || !sameStoryboardValue(r.request, request)) storyboardInvalid();
  let start = 0;
  const clips = storyboardArray(r.clips, 4).map((value, index) => {
    const item = storyboardRecord(value), selected = request.clips[index], measured = storyboardRecord(item.measured);
    storyboardClosed(item, ['clip_id','shot_id','shot_version','shot_digest','video_result','measured','start_ms','in_ms','out_ms','include_audio']);
    storyboardClosed(measured, ['width','height','duration_ms','validation','extension','media_type','codec']);
    if (!selected || item.shot_id !== selected.shot_id || item.shot_version !== selected.shot_version || item.shot_digest !== selected.shot_digest || item.in_ms !== selected.in_ms
      || item.include_audio !== selected.include_audio || item.start_ms !== start || measured.validation !== 'DECODED' || typeof measured.codec !== 'string' && measured.codec !== null) storyboardInvalid();
    const duration = integer(measured.duration_ms, 1, 36000000), out = integer(item.out_ms, selected.in_ms + 1, duration);
    if (out !== (selected.out_ms ?? duration)) storyboardInvalid();
    const video = checkedStoryboardVideoResult(item.video_result), original = receipt.shots.find(shot => shot.shot_id === selected.shot_id)!;
    if (!sameStoryboardValue(video, original.video_result)) storyboardInvalid();
    const result = { ...selected, out_ms: out, clip_id: storyboardResource(item.clip_id), start_ms: start, video_result: video,
      measured: { width: integer(measured.width, 1, 4096), height: integer(measured.height, 1, 4096), duration_ms: duration, validation: 'DECODED' as const,
        extension: storyboardResource(measured.extension), media_type: storyboardResource(measured.media_type), codec: measured.codec as string | null } };
    start += out - selected.in_ms; return result;
  });
  if (clips.length !== request.clips.length || new Set(clips.map(clip => clip.clip_id)).size !== clips.length || start > 600000) storyboardInvalid();
  const timeline = checkedTimelineDraft({ title: body.title, timeline: r.timeline as StudioTimeline }).timeline;
  const expected = { schema_version: 2, duration_ms: start, width: body.width, height: body.height, fps: body.fps,
    tracks: [{ id: 'storyboard-video', kind: 'VIDEO', order: 0, muted: false, gain_db: 0, clips: clips.map(item => ({ id: item.clip_id, start_ms: item.start_ms, in_ms: item.in_ms, out_ms: item.out_ms,
      x: 0, y: 0, width: body.width, height: body.height, include_audio: item.include_audio, source_snapshot: { kind: 'ASSET', asset_kind: 'video', id: item.video_result.asset.asset_id, version: item.video_result.asset.version, digest: item.video_result.asset.digest } })) }], captions: [] };
  if (!sameStoryboardValue(r.timeline, checkedTimelineDraft({ title: body.title, timeline: expected as StudioTimeline }).timeline)) storyboardInvalid();
  return { contract: VIDEO_TIMELINE_CONTRACT, document_snapshot: pin, content_digest: receipt.content_digest, request, clips, timeline,
    preview_digest: storyboardDigest(r.preview_digest), automatic_dispatch: false, model_called: false, rendered: false };
}
async function creation(value: unknown, receipt: StoryboardReceipt, body: VideoTimelineCreate, projectId: string, branchId: string | null, shown: VideoTimelinePreview): Promise<VideoTimelineCreation> {
  const r = storyboardRecord(value); flags(r); storyboardClosed(r, ['contract','creation_receipt','timeline','storyboard_origin','replayed','automatic_dispatch','model_called','rendered']);
  if (r.contract !== VIDEO_TIMELINE_CONTRACT || typeof r.replayed !== 'boolean') storyboardInvalid();
  const raw = storyboardRecord(r.timeline), proof = storyboardRecord(r.creation_receipt), origin = storyboardRecord(r.storyboard_origin);
  storyboardClosed(proof, ['contract','request','document_id','request_digest','creation_snapshot','origin_digest','preview']);
  if (raw.novel_id !== projectId || (raw.branch_id ?? null) !== branchId || proof.contract !== r.contract || proof.document_id !== receipt.document_snapshot.id
    || !sameStoryboardValue(proof.request, body) || !sameStoryboardValue(proof.preview, shown) || !sameStoryboardValue(raw.video_creation_receipt, proof)
    || !sameStoryboardValue(raw.storyboard_origin, origin) || proof.request_digest !== await hash({ contract: VIDEO_TIMELINE_CONTRACT, document_id: receipt.document_snapshot.id, request: body })
    || proof.origin_digest !== await hash(origin)) storyboardInvalid();
  const row = checkedTimelineRow(raw), snapshot = checkedPlanningSnapshot(proof.creation_snapshot);
  const mapping = shown.clips.map(item => ({ clip_id: item.clip_id, shot_id: item.shot_id, shot_version: item.shot_version, shot_digest: item.shot_digest }));
  const expectedOrigin = { contract: 'studio-storyboard-timeline-draft/1', document_snapshot: receipt.document_snapshot, content_digest: receipt.content_digest,
    timeline_snapshot: snapshot, shots: mapping, model_called: false, rendered: false };
  if (snapshot.id !== row.id || snapshot.version !== 1 || row.version < 1 || snapshot.digest !== await hashText(creationTimelineCanonical(shown.timeline)) || !sameStoryboardValue(origin, expectedOrigin)
    || row.version === 1 && (!sameStoryboardValue(row.timeline, shown.timeline) || row.title !== body.title || row.timeline_digest !== snapshot.digest)) storyboardInvalid();
  return { timeline: row, storyboard_origin: expectedOrigin as StoryboardTimelineOrigin, request_id: body.request_id, replayed: r.replayed as boolean };
}
export function createStoryboardVideoTimelineClient(projectId: string, base: string, branchId: string | null, request: <T>(url: string, method?: string, body?: unknown, signal?: AbortSignal) => Promise<T>) {
  const url = (receipt: StoryboardReceipt) => `${base}/documents/${encodeURIComponent(receipt.document_snapshot.id)}/storyboard/video-timeline`;
  return {
    storyboardVideoTimelinePreview: (receipt: StoryboardReceipt, body: VideoTimelineInput) => { input(receipt, body); return request(`${url(receipt)}/preview`, 'POST', body).then(value => checkedVideoTimelinePreview(value, receipt, body)); },
    storyboardVideoTimelineCreate: (receipt: StoryboardReceipt, body: VideoTimelineCreate, shown: VideoTimelinePreview) => { input(receipt, body); if (body.preview_digest !== shown.preview_digest || !/^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$/.test(body.request_id)) storyboardInvalid();
      return request(`${url(receipt)}/create`, 'POST', body).then(value => creation(value, receipt, body, projectId, branchId, shown)); },
    storyboardVideoTimelineCreation: (receipt: StoryboardReceipt, body: VideoTimelineCreate, shown: VideoTimelinePreview) => {
      if (!/^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$/.test(body.request_id)) storyboardInvalid();
      return request(`${url(receipt)}/creations/${encodeURIComponent(body.request_id)}`).then(value => creation(value, receipt, body, projectId, branchId, shown)); },
  };
}
