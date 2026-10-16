import { ApiError } from '../api';
import type { CreativeShot } from './types';
import { checkedCreativeShot, checkedPlanningSnapshot, type PlanningSnapshot } from './studioProductionGraphContract';
import { checkedTimelineRow, type StudioTimelineRow } from './studioTimelineTypes';
import type { RecordedMediaCommand } from './studioProductionClient';
import { checkedImageRuntimeInputs } from './studioImageRuntimeContract';
import { checkedStoryboardShotContext, storyboardShotFields } from './studioVideoRuntimeContract';

export type StoryboardImage = { asset_id: string; version: number; digest: string; kind: 'image' };
export type StoryboardVideoAsset = { asset_id: string; version: number; digest: string; kind: 'video' };
export type VideoJobPin = { id: string; version: number; request_digest: string; receipt_digest: string };
export type StoryboardVideoResult = { asset: StoryboardVideoAsset; source_shot: ShotPin; job: VideoJobPin };
export type StoryboardShot = { shot_id: string; shot_version: number; shot_digest: string; shot: CreativeShot; image_asset: StoryboardImage | null; video_result?: StoryboardVideoResult };
export type StoryboardReceipt = { contract: 'studio-storyboard/1'; document_snapshot: PlanningSnapshot; content_digest: string; approved: boolean; shots: StoryboardShot[];
  director_sources: PlanningSnapshot[]; model_called: false; product_acceptance: 'LOCAL_REQUIRED' };
export type ShotPin = Pick<StoryboardShot, 'shot_id' | 'shot_version' | 'shot_digest'> & { document_snapshot: PlanningSnapshot };
export type StoryboardImageRequest = { contract: 'studio-storyboard-image-request/1'; shot_pin: ShotPin; command: RecordedMediaCommand; automatic_dispatch: false;
  model_called: false; output_policy: 'PRIVATE_CANDIDATE_THEN_EXPLICIT_REVIEW'; product_acceptance: 'LOCAL_REQUIRED' };
export type StoryboardVideoRequest = Omit<StoryboardImageRequest, 'contract'> & { contract: 'studio-storyboard-video-request/1' };
export type DirectorAdvice = { contract: 'studio-director-advice/1'; document_snapshot: PlanningSnapshot; notes: { note_id: string; scene_id: string;
  camera: { shot_size: string; angle: string; movement: string; lens: string; composition: string }; visual_style: { color: string; lighting: string; material: string; style: string };
  rhythm: { pacing: string; duration_seconds: number; transition: string } }[]; advice_only: true; automatic_apply: false; model_called: false; product_acceptance: 'LOCAL_REQUIRED' };
export type StoryboardTimelineOrigin = { contract: 'studio-storyboard-timeline-draft/1'; document_snapshot: PlanningSnapshot; content_digest: string; timeline_snapshot: PlanningSnapshot;
  shots: { clip_id: string; shot_id: string; shot_version: number; shot_digest: string }[]; model_called: false; rendered: false };
export type StoryboardTimelineDraft = { contract: 'studio-storyboard-timeline-draft/1'; timeline: StudioTimelineRow; storyboard_origin: StoryboardTimelineOrigin;
  automatic_dispatch: false; model_called: false; rendered: false; product_acceptance: 'LOCAL_REQUIRED' };
export const storyboardRecord = (v: unknown): Record<string, unknown> => { if (!v || typeof v !== 'object' || Array.isArray(v)) storyboardInvalid(); return v as Record<string, unknown>; };
export function storyboardInvalid(): never { throw new ApiError({ status: 200, code: 'STUDIO_RESPONSE_INVALID', message: '分镜回执或版本绑定不完整，请读取原文档核对。' }); }
export function storyboardClosed(v: Record<string, unknown>, keys: string[]) { if (Object.keys(v).length !== keys.length || keys.some(key => !Object.hasOwn(v, key))) storyboardInvalid(); }
export function storyboardText(v: unknown, maximum = 240, empty = false): string { if (typeof v !== 'string' || v.length > maximum || !empty && !v.trim()) storyboardInvalid(); return v; }
export function storyboardResource(v: unknown): string { const result = storyboardText(v); if (/[\u0000-\u001f\u007f]/.test(result)) storyboardInvalid(); return result; }
export function storyboardDigest(v: unknown): string { if (typeof v !== 'string' || !/^[a-f0-9]{64}$/.test(v)) storyboardInvalid(); return v; }
export function storyboardVersion(v: unknown): number { if (typeof v !== 'number' || !Number.isSafeInteger(v) || v < 1) storyboardInvalid(); return v; }
export function storyboardArray(v: unknown, maximum: number): unknown[] { if (!Array.isArray(v) || v.length > maximum) storyboardInvalid(); return v; }
const canonicalValue = (value: unknown): unknown => Array.isArray(value) ? value.map(canonicalValue) : value && typeof value === 'object'
  ? Object.fromEntries(Object.entries(value).sort(([left], [right]) => left.localeCompare(right)).map(([key, item]) => [key, canonicalValue(item)])) : value;
export function checkedStoryboardImage(v: unknown): StoryboardImage { const r = storyboardRecord(v); storyboardClosed(r, ['asset_id', 'version', 'digest', 'kind']);
  if (r.kind !== 'image') storyboardInvalid(); return { asset_id: storyboardText(r.asset_id), version: storyboardVersion(r.version), digest: storyboardDigest(r.digest), kind: 'image' }; }
export function checkedStoryboardVideoAsset(v: unknown): StoryboardVideoAsset { const r = storyboardRecord(v); storyboardClosed(r, ['asset_id', 'version', 'digest', 'kind']); if (r.kind !== 'video') storyboardInvalid(); return { asset_id: storyboardResource(r.asset_id), version: storyboardVersion(r.version), digest: storyboardDigest(r.digest), kind: 'video' }; }
export function checkedVideoJobPin(v: unknown): VideoJobPin { const r = storyboardRecord(v); storyboardClosed(r, ['id', 'version', 'request_digest', 'receipt_digest']); return { id: storyboardResource(r.id), version: storyboardVersion(r.version), request_digest: storyboardDigest(r.request_digest), receipt_digest: storyboardDigest(r.receipt_digest) }; }
export function checkedStoryboardVideoResult(v: unknown): StoryboardVideoResult { const r = storyboardRecord(v); storyboardClosed(r, ['asset', 'source_shot', 'job']); return { asset: checkedStoryboardVideoAsset(r.asset), source_shot: checkedStoryboardShotContext(r.source_shot), job: checkedVideoJobPin(r.job) }; }
export function checkedStoryboardShot(v: unknown): StoryboardShot { const r = storyboardRecord(v); storyboardClosed(r, ['shot_id', 'shot_version', 'shot_digest', 'shot', 'image_asset', ...(r.video_result === undefined ? [] : ['video_result'])]);
  const shot = checkedCreativeShot(r.shot), shotId = storyboardText(r.shot_id); if (shot.id !== shotId) storyboardInvalid();
  const shotVersion = storyboardVersion(r.shot_version), shotDigest = storyboardDigest(r.shot_digest), video = r.video_result === undefined ? undefined : checkedStoryboardVideoResult(r.video_result);
  if (video && (video.source_shot.shot_id !== shotId || video.source_shot.shot_version !== shotVersion || video.source_shot.shot_digest !== shotDigest)) storyboardInvalid();
  return { shot_id: shotId, shot_version: shotVersion, shot_digest: shotDigest, shot, image_asset: r.image_asset === null ? null : checkedStoryboardImage(r.image_asset), ...(video ? { video_result: video } : {}) }; }
export function checkedStoryboardReceipt(v: unknown, documentId?: string): StoryboardReceipt { const r = storyboardRecord(v); storyboardClosed(r, ['contract', 'document_snapshot', 'content_digest', 'approved', 'shots', 'director_sources', 'model_called', 'product_acceptance']);
  if (r.contract !== 'studio-storyboard/1' || r.model_called !== false || r.product_acceptance !== 'LOCAL_REQUIRED' || typeof r.approved !== 'boolean') storyboardInvalid();
  const pin = checkedPlanningSnapshot(r.document_snapshot); if (documentId !== undefined && pin.id !== documentId) storyboardInvalid();
  const shots = storyboardArray(r.shots, 200).map(checkedStoryboardShot), sources = storyboardArray(r.director_sources, 200).map(v => checkedPlanningSnapshot(v));
  if (new Set(shots.map(shot => shot.shot_id)).size !== shots.length || new Set(shots.map(shot => shot.shot.number)).size !== shots.length
    || shots.some((shot, index) => index > 0 && shot.shot.number <= shots[index - 1].shot.number) || new Set(sources.map(source => source.id)).size !== sources.length) storyboardInvalid();
  if (shots.some(shot => [shot.shot.continuity?.previous_shot_id, shot.shot.continuity?.next_shot_id].some(id => id != null && !shots.some(other => other.shot_id === id)))) storyboardInvalid();
  if (shots.some(shot => shot.video_result && (shot.video_result.source_shot.document_snapshot.id !== pin.id || shot.video_result.source_shot.document_snapshot.version > pin.version || shot.video_result.source_shot.document_snapshot.version === pin.version && shot.video_result.source_shot.document_snapshot.digest !== pin.digest))) storyboardInvalid();
  return { contract: 'studio-storyboard/1', document_snapshot: pin, content_digest: storyboardDigest(r.content_digest), approved: r.approved, shots, director_sources: sources, model_called: false, product_acceptance: 'LOCAL_REQUIRED' };
}
export function checkedStoryboardImageRequest(v: unknown, expected: ShotPin): StoryboardImageRequest {
  const r = storyboardRecord(v); storyboardClosed(r, ['contract', 'shot_pin', 'command', 'automatic_dispatch', 'model_called', 'output_policy', 'product_acceptance']);
  if (r.contract !== 'studio-storyboard-image-request/1' || r.automatic_dispatch !== false || r.model_called !== false || r.output_policy !== 'PRIVATE_CANDIDATE_THEN_EXPLICIT_REVIEW' || r.product_acceptance !== 'LOCAL_REQUIRED') storyboardInvalid();
  const pin = storyboardRecord(r.shot_pin); storyboardClosed(pin, ['document_snapshot', 'shot_id', 'shot_version', 'shot_digest']);
  const checkedPin = { document_snapshot: checkedPlanningSnapshot(pin.document_snapshot), shot_id: storyboardText(pin.shot_id), shot_version: storyboardVersion(pin.shot_version), shot_digest: storyboardDigest(pin.shot_digest) };
  if (JSON.stringify(checkedPin) !== JSON.stringify(expected)) storyboardInvalid();
  const c = storyboardRecord(r.command), keys = ['operation_id', 'request_id', 'provider_id', 'model_id', 'prompt', 'parameters', 'source_snapshots', 'allow_cloud', 'license_note'];
  if (keys.some(key => !Object.hasOwn(c, key)) || Object.keys(c).some(key => ![...keys, 'image_source', 'image_references'].includes(key)) || !['m5.image.t2i', 'm5.image.i2i', 'm5.image.reference'].includes(String(c.operation_id)) || c.allow_cloud !== false) storyboardInvalid();
  storyboardText(c.provider_id); storyboardText(c.model_id); storyboardText(c.prompt, 16000); storyboardText(c.license_note, 2000, true);
  const requestId = storyboardText(c.request_id, 100); if (!/^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$/.test(requestId)) storyboardInvalid();
  const rawParams = storyboardRecord(c.parameters), parameters: Record<string, string | number> = {};
  const known = ['width', 'height', 'steps', 'seed', 'negative_prompt', 'size', 'quality', 'denoising_strength', 'duration_seconds', 'frame_rate', 'voice_id', 'speech_rate', 'in_ms', 'out_ms'];
  for (const [key, value] of Object.entries(rawParams)) { if (!known.includes(key)) storyboardInvalid(); if (value === null) continue;
    if (!['width', 'height', 'steps', 'seed', 'negative_prompt', 'size', 'quality', ...(c.operation_id === 'm5.image.t2i' ? [] : ['denoising_strength'])].includes(key)) storyboardInvalid();
    if (typeof value === 'string') { storyboardText(value, key === 'negative_prompt' ? 8000 : 100, true); if (key !== 'negative_prompt' && !['size', 'quality'].includes(key)) storyboardInvalid(); }
    else if (typeof value !== 'number' || !Number.isFinite(value)) storyboardInvalid();
    if (['width', 'height', 'steps', 'seed'].includes(key)) { const bounds = key === 'steps' ? [1, 150] : key === 'seed' ? [0, 2147483647] : [64, 2048]; if (typeof value !== 'number' || !Number.isSafeInteger(value) || value < bounds[0] || value > bounds[1]) storyboardInvalid(); }
    if (key === 'denoising_strength' && (typeof value !== 'number' || value <= 0 || value > 1) || key === 'size' && !['auto', '1024x1024', '1536x1024', '1024x1536'].includes(String(value)) || key === 'quality' && !['auto', 'low', 'medium', 'high', 'standard', 'hd'].includes(String(value))) storyboardInvalid(); parameters[key] = value as string | number;
  }
  const sources = storyboardArray(c.source_snapshots, 8).map(v => { const source = storyboardRecord(v); if (Object.keys(source).some(key => !['id', 'kind', 'version', 'digest', 'asset_kind', 'reference_only'].includes(key)) || source.reference_only !== true) storyboardInvalid();
    const snapshot = checkedPlanningSnapshot({ id: source.id, version: source.version, digest: source.digest });
    if (source.kind === 'CREATIVE_DOCUMENT' && source.asset_kind == null) return { ...snapshot, kind: 'CREATIVE_DOCUMENT' as const, reference_only: true as const };
    if (source.kind !== 'ASSET' || source.asset_kind !== 'image') storyboardInvalid(); return { ...snapshot, kind: 'ASSET' as const, asset_kind: 'image' as const, reference_only: true as const };
  });
  const docs = sources.filter(source => source.kind === 'CREATIVE_DOCUMENT'); if (docs.length !== 1 || ['id', 'version', 'digest'].some(key => (docs[0] as Record<string, unknown>)[key] !== (expected.document_snapshot as Record<string, unknown>)[key])) storyboardInvalid();
  if (sources[0].kind !== 'CREATIVE_DOCUMENT' || new Set(sources.map(source => `${source.kind}:${source.id}`)).size !== sources.length || sources.length !== (c.operation_id === 'm5.image.t2i' ? 1 : 2)) storyboardInvalid();
  const command = { ...c, parameters, source_snapshots: sources, ...checkedImageRuntimeInputs(c, sources, String(c.operation_id)) } as unknown as RecordedMediaCommand;
  return { ...r, shot_pin: checkedPin, command } as StoryboardImageRequest;
}
export function checkedStoryboardVideoRequest(v: unknown, expected: ShotPin): StoryboardVideoRequest {
  const r = storyboardRecord(v); storyboardClosed(r, ['contract', 'shot_pin', 'command', 'automatic_dispatch', 'model_called', 'output_policy', 'product_acceptance']);
  if (r.contract !== 'studio-storyboard-video-request/1' || r.automatic_dispatch !== false || r.model_called !== false || r.output_policy !== 'PRIVATE_CANDIDATE_THEN_EXPLICIT_REVIEW' || r.product_acceptance !== 'LOCAL_REQUIRED') storyboardInvalid();
  const pin = checkedStoryboardShotContext(r.shot_pin); if (JSON.stringify(pin) !== JSON.stringify(expected)) storyboardInvalid();
  const c = storyboardRecord(r.command); storyboardClosed(c, ['operation_id', 'request_id', 'provider_id', 'model_id', 'prompt', 'parameters', 'source_snapshots', 'allow_cloud', 'license_note', 'storyboard_shot']);
  if (!['m7.video.t2v', 'm7.video.i2v'].includes(String(c.operation_id)) || c.allow_cloud !== false) storyboardInvalid();
  storyboardText(c.provider_id); storyboardText(c.model_id); storyboardText(c.prompt, 16000); storyboardText(c.license_note, 2000, true);
  const requestId = storyboardText(c.request_id, 100); if (!/^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$/.test(requestId)) storyboardInvalid();
  const rawParameters = storyboardRecord(c.parameters), parameters: Record<string, string | number> = {}, ranges: Record<string, [number, number]> = { width: [64, 2048], height: [64, 2048], seed: [0, 2147483647], duration_seconds: [1, 600], frame_rate: [1, 60] };
  const allParameters = ['width', 'height', 'seed', 'negative_prompt', 'duration_seconds', 'frame_rate', 'steps', 'size', 'quality', 'voice_id', 'speech_rate', 'in_ms', 'out_ms', 'gain_db', 'sample_rate', 'channels', 'denoising_strength', 'scale'];
  for (const [key, value] of Object.entries(rawParameters)) { if (!allParameters.includes(key)) storyboardInvalid(); if (value === null) continue;
    if (key === 'negative_prompt') parameters[key] = storyboardText(value, 8000, true); else { const bound = ranges[key]; if (!bound || typeof value !== 'number' || !Number.isSafeInteger(value) || value < bound[0] || value > bound[1]) storyboardInvalid(); parameters[key] = value; }
  }
  const sources = storyboardArray(c.source_snapshots, 8).map(value => { const source = storyboardRecord(value); storyboardClosed(source, ['id', 'kind', 'version', 'digest', 'asset_kind', 'reference_only']); if (source.reference_only !== true) storyboardInvalid(); const snapshot = checkedPlanningSnapshot({ id: source.id, version: source.version, digest: source.digest });
    if (source.kind === 'CREATIVE_DOCUMENT' && source.asset_kind === null) return { ...snapshot, kind: 'CREATIVE_DOCUMENT' as const, reference_only: true as const };
    if (source.kind !== 'ASSET' || source.asset_kind !== 'image') storyboardInvalid(); return { ...snapshot, kind: 'ASSET' as const, asset_kind: 'image' as const, reference_only: true as const };
  });
  if (sources.length !== (c.operation_id === 'm7.video.t2v' ? 1 : 2) || sources[0].kind !== 'CREATIVE_DOCUMENT' || new Set(sources.map(source => `${source.kind}:${source.id}`)).size !== sources.length) storyboardInvalid();
  const command = { ...c, parameters, source_snapshots: sources, ...storyboardShotFields(c.storyboard_shot, sources, String(c.operation_id)) } as unknown as RecordedMediaCommand;
  if (JSON.stringify(command.storyboard_shot) !== JSON.stringify(pin)) storyboardInvalid();
  return { ...r, shot_pin: pin, command } as StoryboardVideoRequest;
}
export function checkedDirectorAdvice(v: unknown, documentId: string): DirectorAdvice { const r = storyboardRecord(v); storyboardClosed(r, ['contract', 'document_snapshot', 'notes', 'advice_only', 'automatic_apply', 'model_called', 'product_acceptance']);
  if (r.contract !== 'studio-director-advice/1' || r.advice_only !== true || r.automatic_apply !== false || r.model_called !== false || r.product_acceptance !== 'LOCAL_REQUIRED') storyboardInvalid();
  const pin = checkedPlanningSnapshot(r.document_snapshot); if (pin.id !== documentId) storyboardInvalid();
  const notes = storyboardArray(r.notes, 200).map(v => { const note = storyboardRecord(v); storyboardClosed(note, ['note_id', 'scene_id', 'camera', 'visual_style', 'rhythm']);
    storyboardText(note.note_id); storyboardText(note.scene_id); const camera = storyboardRecord(note.camera), visual = storyboardRecord(note.visual_style), rhythm = storyboardRecord(note.rhythm);
    storyboardClosed(camera, ['shot_size', 'angle', 'movement', 'lens', 'composition']); storyboardClosed(visual, ['color', 'lighting', 'material', 'style']); storyboardClosed(rhythm, ['pacing', 'duration_seconds', 'transition']);
    for (const key of ['shot_size', 'angle', 'movement']) storyboardText(camera[key], 80, true); storyboardText(camera.lens, 1000, true); storyboardText(camera.composition, 4000, true);
    for (const key of ['color', 'style']) storyboardText(visual[key], 2000, true); for (const key of ['lighting', 'material']) storyboardText(visual[key], 4000, true);
    storyboardText(rhythm.pacing, 2000, true); storyboardText(rhythm.transition, 2000, true); if (storyboardVersion(rhythm.duration_seconds) > 600) storyboardInvalid(); return note;
  }); if (new Set(notes.map(note => note.note_id)).size !== notes.length) storyboardInvalid(); return { ...r, document_snapshot: pin, notes } as unknown as DirectorAdvice;
}
export function checkedStoryboardTimeline(v: unknown, projectId: string, branchId: string | null): StoryboardTimelineDraft { const r = storyboardRecord(v); storyboardClosed(r, ['contract', 'timeline', 'storyboard_origin', 'automatic_dispatch', 'model_called', 'rendered', 'product_acceptance']);
  if (r.contract !== 'studio-storyboard-timeline-draft/1' || r.automatic_dispatch !== false || r.model_called !== false || r.rendered !== false || r.product_acceptance !== 'LOCAL_REQUIRED') storyboardInvalid();
  const raw = storyboardRecord(r.timeline); if (raw.novel_id !== projectId || (raw.branch_id ?? null) !== branchId) storyboardInvalid(); const timeline = checkedTimelineRow(raw), origin = storyboardRecord(r.storyboard_origin);
  storyboardClosed(origin, ['contract', 'document_snapshot', 'content_digest', 'timeline_snapshot', 'shots', 'model_called', 'rendered']); if (origin.contract !== r.contract || origin.model_called !== false || origin.rendered !== false) storyboardInvalid();
  const pin = checkedPlanningSnapshot(origin.timeline_snapshot), document = checkedPlanningSnapshot(origin.document_snapshot); if (pin.id !== timeline.id || pin.version !== timeline.version || pin.digest !== timeline.timeline_digest || JSON.stringify(canonicalValue(raw.storyboard_origin)) !== JSON.stringify(canonicalValue(origin))) storyboardInvalid();
  const shots = storyboardArray(origin.shots, 30).map(v => { const shot = storyboardRecord(v); storyboardClosed(shot, ['clip_id', 'shot_id', 'shot_version', 'shot_digest']); return { clip_id: storyboardText(shot.clip_id), shot_id: storyboardText(shot.shot_id), shot_version: storyboardVersion(shot.shot_version), shot_digest: storyboardDigest(shot.shot_digest) }; });
  const clips = timeline.timeline.tracks.flatMap(track => track.clips); if (!shots.length || new Set(shots.map(shot => shot.shot_id)).size !== shots.length || clips.length !== shots.length || clips.some((clip, index) => clip.id !== shots[index].clip_id)) storyboardInvalid();
  return { contract: 'studio-storyboard-timeline-draft/1', timeline, storyboard_origin: { contract: 'studio-storyboard-timeline-draft/1', document_snapshot: document, content_digest: storyboardDigest(origin.content_digest), timeline_snapshot: pin, shots, model_called: false, rendered: false }, automatic_dispatch: false, model_called: false, rendered: false, product_acceptance: 'LOCAL_REQUIRED' };
}
