import { describe, expect, it } from 'vitest';
import { checkedTimeline } from './studioTimelineTypes';
import { checkedCanvasReturnBinding } from './studioCanvasReturnBinding';
import type { CanvasViewRecord } from './studioCanvasViewClient';
import type { StudioAsset } from './studioClient';
import {
  assertCanvasVideoTrimTaskTarget, canvasVideoTaskJobMatches, canvasVideoTrimTaskSource, captureCanvasVideoTrimTask,
  checkedCanvasVideoReturnBinding, checkedCanvasVideoTaskCommand, checkedCanvasVideoTaskJob, checkedCanvasVideoTaskPreview,
  compileCanvasVideoTimeline, replaceCanvasVideoTrimTaskResult,
  type CanvasVideoTaskCommand, type CanvasVideoTaskJob, type CanvasVideoTaskPreview,
} from './canvasVideoTrimTask';

const project = 'video-project', incarnation = 'file:00000000-0000-0000-0000-000000000001';
const hash = (letter: string) => letter.repeat(64);
const asset = (): StudioAsset => ({ id: 'video-source', novel_id: project, branch_id: null, version: 2, kind: 'video',
  media_type: 'video/mp4', filename: 'synthetic-source.mp4', size: 1000, sha256: hash('a'), created_at: '', updated_at: '' });
const canvas = (): CanvasViewRecord => ({ id: 'video-canvas', project_id: project, scope: { mode: 'local', novel_id: project },
  version: 3, definition_digest: hash('b'), definition: { schema_version: 1, title: 'Synthetic saved video card',
    viewport: { x: 12, y: 23, zoom: 0.8 }, groups: [{ id: 'group', name: 'Keep group', card_ids: ['origin', 'other'], collapsed: false }],
    cards: [{ id: 'origin', position: { x: 40, y: 80 }, asset: { asset_id: 'video-source', version: 2, digest: hash('a'), kind: 'video' } },
      { id: 'other', position: { x: 200, y: 120 }, asset: { asset_id: 'video-source', version: 2, digest: hash('a'), kind: 'video' } }] },
  reference_states: [{ card_id: 'origin', state: 'CURRENT_METADATA' }, { card_id: 'other', state: 'CURRENT_METADATA' }],
  created_at: '', updated_at: '', execution_authority: false, binary_content_verified: false, capacity: { history_used: 2, record_bytes: 1000 } });
const origin = () => captureCanvasVideoTrimTask(canvas(), 'origin', asset(), incarnation);
const command = (): CanvasVideoTaskCommand => ({ contract: 'studio-canvas-video-trim/1', operation_id: 'm9.timeline.multitrack',
  request_id: 'video-task-request', provider_id: null, model_id: null, prompt: '', allow_cloud: false, license_note: '',
  parameters: { in_ms: 1000, out_ms: 1600 }, source_snapshots: [canvasVideoTrimTaskSource(origin().source)],
  timeline_snapshot: { id: 'original-timeline', version: 1, digest: hash('c') }, canvas_return: origin().binding! });
const recipe = () => ({ contract: 'studio-execution-recipe/1' as const, operation_id: 'm9.timeline.multitrack', adapter: 'LOCAL_FFMPEG',
  output_profile: 'DELIVERY_H264_MP4', timeline: compileCanvasVideoTimeline(command().source_snapshots[0], command().parameters),
  export_profile: { preset: 'DELIVERY_H264_MP4', video_bitrate_kbps: 400, audio_bitrate_kbps: 96, crf: 23 }, automatic_fallback: false as const, recipe_digest: hash('d') });
const preview = (): CanvasVideoTaskPreview => ({ contract: 'studio-canvas-video-preview/1', novel_id: project, branch_id: null,
  command: command(), request_digest: hash('e'), preview_digest: hash('f'), execution_recipe: recipe(), execution_available: true,
  automatic_dispatch: false, product_acceptance: 'LOCAL_REQUIRED' });
const job = (status: 'QUEUED' | 'SUCCEEDED' | 'APPROVED' = 'APPROVED'): CanvasVideoTaskJob => ({
  contract: 'studio-production-job/1', owner: 'timeline', id: 'original-job', novel_id: project, branch_id: null, version: status === 'QUEUED' ? 1 : 4,
  operation_id: 'm9.timeline.multitrack', request_id: command().request_id, status, request_digest: hash('e'), receipt_digest: hash('f'),
  command: null, provider: null, canvas_video: command(), execution_recipe: recipe(), sources: command().source_snapshots,
  timeline_snapshot: command().timeline_snapshot, output_candidate: status === 'QUEUED' ? null : { id: 'formal-output', version: 1, digest: hash('1'), kind: 'video' },
  approved_asset_version: status === 'APPROVED' ? 2 : null,
  media_measurement: status === 'QUEUED' ? null : { duration_ms: 600, byte_count: 1994, width: 640, height: 360, fps: 25,
    video_codec: 'h264', audio_codec: 'aac', sample_rate: 48000, channels: 2, container: 'mp4', profile_validation: 'NATIVE_FFPROBE_EXACT',
    render_profile: 'STUDIO_MULTITRACK_LOCAL_FFMPEG_DELIVERY_H264_MP4',
    export_profile: { preset: 'DELIVERY_H264_MP4', video_bitrate_kbps: 400, audio_bitrate_kbps: 96, crf: 23 } },
  product_acceptance: 'LOCAL_REQUIRED', automatic_replay: false, remote_compute_may_continue: false, created_at: '', updated_at: '',
});
const output = (): StudioAsset => ({ ...asset(), id: 'formal-output', version: 2, sha256: hash('1'), filename: 'reviewed.mp4', size: 1994 });

describe('single original Timeline video-card contract', () => {
  it('compiles only one bounded real silent clip, matching the original normalizer', () => {
    const c = command(), value = compileCanvasVideoTimeline(c.source_snapshots[0], c.parameters);
    expect(value).toEqual(checkedTimeline(value));
    expect(value).toMatchObject({ schema_version: 2, width: 640, height: 360, fps: 25, duration_ms: 600, captions: [] });
    expect(value.tracks).toHaveLength(1); expect(value.tracks[0].clips).toHaveLength(1);
    expect(value.tracks[0]).toMatchObject({ id: 'canvas-video-track', kind: 'VIDEO', role: 'PRIMARY', order: 0 });
    expect(value.tracks[0].clips[0]).toMatchObject({ id: 'canvas-video-clip', source_snapshot: c.source_snapshots[0],
      in_ms: 1000, out_ms: 1600, start_ms: 0, include_audio: false, speed_num: 1, speed_den: 1 });
    expect(checkedCanvasVideoTaskCommand(c)).toEqual(c);
  });
  it.each([[-40, 1600], [0, 0], [1600, 1000], [0, 120040], [1, 1600], [1000, 1601],
    [0.5, 1600], [0, Number.NaN], [0, Number.POSITIVE_INFINITY], [36_000_000, 36_000_040]])('rejects unsupported range %s/%s', (start, end) => {
    expect(() => compileCanvasVideoTimeline(command().source_snapshots[0], { in_ms: start, out_ms: end })).toThrow();
  });
  it('admits the exact 120 second boundary without adding clips or changing the source', () => {
    const source = command().source_snapshots[0], result = compileCanvasVideoTimeline(source, { in_ms: 40, out_ms: 120040 });
    expect(result.duration_ms).toBe(120000); expect(result.tracks[0].clips[0].source_snapshot).toEqual(source);
  });
  it.each(['gain', 'cloud', 'model', 'prompt', 'license', 'operation', 'request', 'snapshot', 'duplicate-source', 'source-pin', 'marker'])('rejects unsupported command %s', mode => {
    const c: any = command();
    if (mode === 'gain') c.parameters.gain_db = 0; if (mode === 'cloud') c.allow_cloud = true; if (mode === 'model') c.model_id = 'model';
    if (mode === 'prompt') c.prompt = 'generate'; if (mode === 'license') c.license_note = 'different'; if (mode === 'operation') c.operation_id = 'm7.video.v2v';
    if (mode === 'request') c.request_id = 'not/a/request'; if (mode === 'snapshot') c.timeline_snapshot.version = 0;
    if (mode === 'duplicate-source') c.source_snapshots.push(c.source_snapshots[0]); if (mode === 'source-pin') c.source_snapshots[0].digest = hash('2');
    if (mode === 'marker') c.source_snapshots[0].reference_only = true;
    expect(() => checkedCanvasVideoTaskCommand(c)).toThrow();
  });
  it('requires all versioned fields and does not normalize unknown or missing fields away', () => {
    const c: any = command(); delete c.provider_id; expect(() => checkedCanvasVideoTaskCommand(c)).toThrow();
    expect(() => checkedCanvasVideoTaskCommand({ ...command(), extra: undefined })).toThrow();
    expect(() => checkedCanvasVideoTaskCommand({ ...command(), parameters: { ...command().parameters, extra: undefined } })).toThrow();
  });
  it('uses an additive video origin without loosening the original image/audio origin parser', () => {
    const binding = origin().binding!; expect(checkedCanvasVideoReturnBinding(binding)).toEqual(binding);
    expect(() => checkedCanvasReturnBinding(binding)).toThrow();
    expect(() => checkedCanvasVideoReturnBinding({ ...binding, source: { ...binding.source, asset_kind: 'audio' } })).toThrow();
    expect(() => checkedCanvasVideoReturnBinding({ ...binding, source: { ...binding.source, reference_only: true } })).toThrow();
  });
  it.each(['scope', 'incarnation', 'card-version', 'pin-version', 'extra'])('rejects malformed origin %s', mode => {
    const b: any = origin().binding!;
    if (mode === 'scope') b.scope.novel_id = 'other-project'; if (mode === 'incarnation') b.incarnation = 'unknown';
    if (mode === 'card-version') b.canvas_version = 0; if (mode === 'pin-version') b.source.version = 0; if (mode === 'extra') b.extra = 'ignored';
    expect(() => checkedCanvasVideoReturnBinding(b)).toThrow();
  });
  it('checks collaboration branch scope without inferring it from a selected card', () => {
    const c = command(); c.canvas_return.scope = { mode: 'collaboration', novel_id: project, workspace_id: 'workspace', storyline_id: 'storyline', branch_id: 'branch-a' };
    const p = { ...preview(), command: c, branch_id: 'branch-a' }; expect(checkedCanvasVideoTaskPreview(p, c).branch_id).toBe('branch-a');
    expect(() => checkedCanvasVideoTaskPreview({ ...p, branch_id: 'branch-b' }, c)).toThrow();
    delete (c.canvas_return.scope as any).storyline_id; expect(() => checkedCanvasVideoTaskCommand(c)).toThrow();
  });
});

describe('preview and original Job receipt congruence', () => {
  it('reads a matching preview and preserves unavailable execution as unavailable', () => {
    expect(checkedCanvasVideoTaskPreview(preview(), command())).toEqual(preview());
    expect(checkedCanvasVideoTaskPreview({ ...preview(), execution_available: false }, command()).execution_available).toBe(false);
  });
  it.each(['range', 'origin', 'timeline-version', 'request', 'provider', 'unknown-adapter', 'extra-step', 'audio', 'preset', 'auto'])('rejects swapped preview %s', mode => {
    const p: any = preview();
    if (mode === 'range') { p.command.parameters.out_ms = 1640; p.execution_recipe.timeline = compileCanvasVideoTimeline(p.command.source_snapshots[0], p.command.parameters); }
    if (mode === 'origin') p.command.canvas_return.card_id = 'other'; if (mode === 'timeline-version') p.command.timeline_snapshot.version++;
    if (mode === 'request') p.command.request_id = 'other'; if (mode === 'provider') p.command.provider_id = 'provider';
    if (mode === 'unknown-adapter') p.execution_recipe.adapter = 'UNKNOWN'; if (mode === 'extra-step') p.execution_recipe.timeline.tracks[0].clips.push(p.execution_recipe.timeline.tracks[0].clips[0]);
    if (mode === 'audio') p.execution_recipe.timeline.tracks[0].clips[0].include_audio = true; if (mode === 'preset') p.execution_recipe.export_profile.preset = 'REVIEW_MP4';
    if (mode === 'auto') p.automatic_dispatch = true;
    expect(() => checkedCanvasVideoTaskPreview(p, command())).toThrow();
  });
  it('rejects unrecorded recipe fields and unknown preview fields', () => {
    expect(() => checkedCanvasVideoTaskPreview({ ...preview(), provider: null }, command())).toThrow();
    const p: any = preview(); p.execution_recipe.timeline.debug = undefined; expect(() => checkedCanvasVideoTaskPreview(p, command())).toThrow();
  });
  it.each(['video_bitrate_kbps', 'audio_bitrate_kbps', 'crf'])('requires the exact H264 recipe and measurement %s', field => {
    const missing: any = preview(); delete missing.execution_recipe.export_profile[field];
    expect(() => checkedCanvasVideoTaskPreview(missing, command())).toThrow();
    const altered: any = preview(); altered.execution_recipe.export_profile[field] += 1;
    expect(() => checkedCanvasVideoTaskPreview(altered, command())).toThrow();
    const measured: any = job(); measured.media_measurement.export_profile[field] += 1;
    expect(() => checkedCanvasVideoTaskJob(measured)).toThrow();
  });
  it('rejects extra H264 export fields and the old MPEG4 candidate', () => {
    const p: any = preview(); p.execution_recipe.export_profile.unrecognised = null;
    expect(() => checkedCanvasVideoTaskPreview(p, command())).toThrow();
    const extra: any = job(); extra.media_measurement.export_profile.unrecognised = null;
    expect(() => checkedCanvasVideoTaskJob(extra)).toThrow();
    const old: any = job(); old.media_measurement.video_codec = 'mpeg4';
    old.media_measurement.render_profile = 'STUDIO_MULTITRACK_LOCAL_FFMPEG_REVIEW_MP4';
    expect(() => checkedCanvasVideoTaskJob(old)).toThrow();
  });
  it.each(['QUEUED', 'SUCCEEDED', 'APPROVED'] as const)('reads the original %s Job only with the exact new capsule', status => {
    const value = job(status); expect(checkedCanvasVideoTaskJob(value)).toEqual(value);
    expect(canvasVideoTaskJobMatches({ source: command().source_snapshots[0], returnBinding: origin().binding, isCurrent: () => true }, value)).toBe(true);
  });
  it('keeps legacy Timeline command=null Jobs readable elsewhere but never guesses a video-card task', () => {
    const legacy: any = job(); delete legacy.canvas_video;
    expect(() => checkedCanvasVideoTaskJob(legacy)).toThrow();
    expect(canvasVideoTaskJobMatches({ source: command().source_snapshots[0], returnBinding: origin().binding, isCurrent: () => true }, legacy)).toBe(false);
  });
  it.each(['owner', 'project', 'branch', 'request', 'snapshot', 'sources', 'provider', 'recipe', 'measurement', 'candidate-kind', 'approved-version', 'remote-state'])('rejects mismatched Job %s', mode => {
    const value: any = job();
    if (mode === 'owner') value.owner = 'video'; if (mode === 'project') value.novel_id = 'another'; if (mode === 'branch') value.branch_id = 'another';
    if (mode === 'request') value.request_id = 'another'; if (mode === 'snapshot') value.timeline_snapshot.version = 2;
    if (mode === 'sources') value.sources[0].version = 3; if (mode === 'provider') value.provider = { local: true };
    if (mode === 'recipe') value.execution_recipe.timeline.tracks[0].clips[0].out_ms = 1640; if (mode === 'measurement') value.media_measurement = null;
    if (mode === 'candidate-kind') value.output_candidate.kind = 'audio'; if (mode === 'approved-version') value.approved_asset_version = 1;
    if (mode === 'remote-state') value.status = 'REMOTE_RUNNING';
    expect(() => checkedCanvasVideoTaskJob(value)).toThrow();
  });
  it.each(['duration_ms', 'fps', 'width', 'sample_rate', 'video_codec', 'profile_validation', 'export_profile'])('does not accept a missing or altered measured %s', key => {
    const value: any = job(); delete value.media_measurement[key]; expect(() => checkedCanvasVideoTaskJob(value)).toThrow();
  });
  it('retires a matcher when its task is no longer current, without creating or replaying anything', () => {
    expect(canvasVideoTaskJobMatches({ source: command().source_snapshots[0], returnBinding: origin().binding, isCurrent: () => false }, job())).toBe(false);
  });
});

describe('exact original card adoption', () => {
  it('replaces only the captured card after formal review, retaining layout, group, source and other card', () => {
    const original = canvas(), before = structuredClone(original), value = replaceCanvasVideoTrimTaskResult(origin(), original, job(), output(), incarnation);
    expect(value.cards[0].asset).toEqual({ asset_id: 'formal-output', version: 2, digest: hash('1'), kind: 'video' });
    expect(value.cards[0].position).toEqual(original.definition.cards[0].position); expect(value.cards[1]).toEqual(original.definition.cards[1]);
    expect(value.groups).toEqual(original.definition.groups); expect(value.viewport).toEqual(original.definition.viewport); expect(original).toEqual(before);
  });
  it.each(['version', 'digest', 'deleted-card', 'replaced-source', 'scope', 'unavailable'])('rejects a changed target %s and leaves it untouched', mode => {
    const current = canvas();
    if (mode === 'version') current.version++; if (mode === 'digest') current.definition_digest = hash('2');
    if (mode === 'deleted-card') current.definition.cards = current.definition.cards.slice(1);
    if (mode === 'replaced-source') current.definition.cards[0].asset!.asset_id = 'replacement';
    if (mode === 'scope') current.scope = { mode: 'local', novel_id: 'another' };
    if (mode === 'unavailable') current.reference_states[0].state = 'UNAVAILABLE';
    const before = structuredClone(current); expect(() => replaceCanvasVideoTrimTaskResult(origin(), current, job(), output(), incarnation)).toThrow(); expect(current).toEqual(before);
  });
  it('rejects a new incarnation supplied by the live history owner', () => {
    expect(() => assertCanvasVideoTrimTaskTarget(origin(), canvas(), 'file:00000000-0000-0000-0000-000000000002')).toThrow();
  });
  it.each(['deleted', 'version', 'hash', 'project', 'branch', 'type'])('refuses changed formal asset %s', mode => {
    const value: any = output(); if (mode === 'deleted') value.deleted_at = 'now'; if (mode === 'version') value.version++;
    if (mode === 'hash') value.sha256 = hash('2'); if (mode === 'project') value.novel_id = 'other'; if (mode === 'branch') value.branch_id = 'other';
    if (mode === 'type') value.media_type = 'video/webm';
    expect(() => replaceCanvasVideoTrimTaskResult(origin(), canvas(), job(), value, incarnation)).toThrow();
  });
  it('refuses a private candidate or an origin without a durable incarnation binding', () => {
    expect(() => replaceCanvasVideoTrimTaskResult(origin(), canvas(), job('SUCCEEDED'), output(), incarnation)).toThrow();
    const missing = captureCanvasVideoTrimTask(canvas(), 'origin', asset()); expect(missing.binding).toBeUndefined();
    expect(() => replaceCanvasVideoTrimTaskResult(missing, canvas(), job(), output())).toThrow();
  });
  it.each(['asset-version', 'asset-project', 'asset-deleted', 'card-kind'])('does not capture stale or unsuitable source %s', mode => {
    const source: any = asset(), view = canvas(); if (mode === 'asset-version') source.version++; if (mode === 'asset-project') source.novel_id = 'other';
    if (mode === 'asset-deleted') source.deleted_at = 'now'; if (mode === 'card-kind') view.definition.cards[0].asset!.kind = 'image';
    expect(() => captureCanvasVideoTrimTask(view, 'origin', source, incarnation)).toThrow();
  });
});
