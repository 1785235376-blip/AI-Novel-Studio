import { expect, it } from 'vitest';
import { assertCanvasAudioTrimTaskCommand, assertCanvasAudioTrimTaskTarget, canvasAudioTrimTaskJobMatches,
  canvasAudioTrimTaskSource, captureCanvasAudioTrimTask, replaceCanvasAudioTrimTaskResult } from './canvasAudioTrimTask';
import type { CanvasAssetReference, CanvasViewRecord } from './studioCanvasViewClient';
import type { StudioAsset } from './studioClient';
import type { MediaCommand, ProductionJob, ProductionSource } from './studioProductionClient';

const sourceDigest = 'a'.repeat(64), outputDigest = 'b'.repeat(64), canvasDigest = 'c'.repeat(64);
const incarnation = 'file:01234567-89ab-4cde-8fab-0123456789ab';
function fixture(bound = false) {
  const source: CanvasAssetReference = { asset_id: 'original-audio', version: 2, digest: sourceDigest, kind: 'audio' };
  const asset: StudioAsset = { id: source.asset_id, novel_id: 'project', branch_id: null, filename: 'synthetic.wav',
    media_type: 'audio/wav', size: 384_044, created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z',
    version: source.version, sha256: source.digest, kind: 'audio', deleted_at: null };
  const canvas: CanvasViewRecord = { project_id: 'project', scope: { mode: 'local', novel_id: 'project' }, id: 'canvas', version: 3,
    definition_digest: canvasDigest, created_at: asset.created_at, updated_at: asset.updated_at,
    execution_authority: false, binary_content_verified: false, capacity: { history_used: 2, record_bytes: 1000 },
    definition: { schema_version: 1, title: 'Synthetic audio work', cards: [
      { id: 'target', position: { x: 41, y: 63 }, asset: source },
      { id: 'other', position: { x: 500, y: 200 }, asset: { ...source } },
    ], groups: [{ id: 'group', name: 'Work group', card_ids: ['target'], collapsed: false }],
    viewport: { x: 17, y: 23, zoom: 1 }, view_options: { grid: true, snap_step: 8 } },
    reference_states: [{ card_id: 'target', state: 'CURRENT_METADATA', filename: asset.filename },
      { card_id: 'other', state: 'CURRENT_METADATA', filename: asset.filename }] };
  const input: ProductionSource = { id: source.asset_id, kind: 'ASSET', version: source.version, digest: source.digest, asset_kind: 'audio' };
  const origin = captureCanvasAudioTrimTask(canvas, 'target', asset, bound ? incarnation : undefined);
  const command: MediaCommand = { operation_id: 'm8.audio.trim', request_id: 'synthetic-audio-request', provider_id: null,
    model_id: null, prompt: '', parameters: { in_ms: 250, out_ms: 1250 }, allow_cloud: false,
    source_snapshots: [structuredClone(input)], license_note: 'Synthetic test audio', ...(origin.binding ? { canvas_return: origin.binding } : {}) };
  const job: ProductionJob = { contract: 'studio-production-job/1', owner: 'audio', id: 'synthetic-job', novel_id: 'project',
    branch_id: null, version: 4, operation_id: 'm8.audio.trim', request_id: command.request_id, status: 'APPROVED',
    request_digest: 'd'.repeat(64), receipt_digest: outputDigest, output_candidate: { id: 'formal-audio', version: 1, digest: outputDigest, kind: 'audio' },
    product_acceptance: 'LOCAL_REQUIRED', automatic_replay: false, remote_compute_may_continue: false, timeline_snapshot: null,
    sources: structuredClone(command.source_snapshots), command: structuredClone(command), provider: null,
    execution_recipe: { contract: 'studio-execution-recipe/1', operation_id: 'm8.audio.trim', adapter: 'LOCAL_FFMPEG',
      recipe_digest: 'e'.repeat(64), automatic_fallback: false, parameters: { ...command.parameters }, output_profile: 'PCM_S16LE_WAV_48000_STEREO' },
    approved_asset_version: 2, media_measurement: { duration_ms: 1000, byte_count: 192_044, sample_rate: 48000, channels: 2,
      container: 'wav', audio_codec: 'pcm_s16le', profile_validation: 'PCM_DECODED', output_sha256: outputDigest },
    created_at: asset.created_at, updated_at: asset.updated_at };
  const result: StudioAsset = { ...asset, id: 'formal-audio', filename: 'synthetic-trimmed.wav', sha256: outputDigest, size: 192_044 };
  const binding = { source: input, returnBinding: origin.binding, isCurrent: () => true };
  return { source, asset, canvas, origin, input, command, job, result, binding };
}

it('accepts the bounded original AudioJob command and replaces only the captured card without mutating the canvas', () => {
  const f = fixture(), before = structuredClone(f.canvas);
  expect(() => assertCanvasAudioTrimTaskCommand(f.binding, f.command)).not.toThrow();
  expect(canvasAudioTrimTaskJobMatches(f.binding, f.job)).toBe(true);
  const result = replaceCanvasAudioTrimTaskResult(f.origin, f.canvas, f.job, f.result);
  expect(result.cards[0]).toEqual({ ...before.definition.cards[0], asset: { asset_id: f.result.id, version: 2, digest: outputDigest, kind: 'audio' } });
  expect(result.cards[1]).toBe(f.canvas.definition.cards[1]);
  expect(result.groups).toBe(f.canvas.definition.groups); expect(result.viewport).toBe(f.canvas.definition.viewport);
  expect(result.view_options).toBe(f.canvas.definition.view_options); expect(f.canvas).toEqual(before);
});

it.each(['wrong card kind', 'wrong asset kind', 'deleted', 'different project', 'different branch', 'asset version', 'asset digest', 'stale', 'missing card'] as const)(
  'refuses an invalid captured source: %s', kind => {
    const f = fixture();
    if (kind === 'wrong card kind') f.canvas.definition.cards[0].asset!.kind = 'image';
    if (kind === 'wrong asset kind') f.asset.kind = 'video';
    if (kind === 'deleted') f.asset.deleted_at = f.asset.updated_at;
    if (kind === 'different project') f.asset.novel_id = 'other-project';
    if (kind === 'different branch') f.asset.branch_id = 'other-branch';
    if (kind === 'asset version') f.asset.version++;
    if (kind === 'asset digest') f.asset.sha256 = 'f'.repeat(64);
    if (kind === 'stale') f.canvas.reference_states[0].state = 'STALE';
    if (kind === 'missing card') f.canvas.definition.cards.shift();
    expect(() => captureCanvasAudioTrimTask(f.canvas, 'target', f.asset)).toThrow();
  });

it.each(['retired', 'cloud', 'provider', 'model', 'prompt', 'other operation', 'extra input', 'wrong source', 'image input',
  'video frames', 'storyboard', 'audio profile', 'extra parameter', 'missing time', 'fractional', 'negative', 'reversed', 'too long'] as const)(
  'rejects unsupported task execution before original dispatch: %s', kind => {
    const f = fixture();
    if (kind === 'retired') f.binding.isCurrent = () => false;
    if (kind === 'cloud') f.command.allow_cloud = true;
    if (kind === 'provider') f.command.provider_id = 'cloud-provider';
    if (kind === 'model') f.command.model_id = 'model';
    if (kind === 'prompt') f.command.prompt = 'generate speech';
    if (kind === 'other operation') f.command.operation_id = 'm8.audio.speech';
    if (kind === 'extra input') f.command.source_snapshots.push({ ...f.input, id: 'extra' });
    if (kind === 'wrong source') f.command.source_snapshots[0].version++;
    if (kind === 'image input') f.command.image_source = { ...f.input, asset_kind: 'image' };
    if (kind === 'video frames') f.command.video_frames = [];
    if (kind === 'storyboard') f.command.storyboard_speech = {} as MediaCommand['storyboard_speech'];
    if (kind === 'audio profile') f.command.audio_profile = 'studio-audio-mp3/1';
    if (kind === 'extra parameter') f.command.parameters.sample_rate = 48000;
    if (kind === 'missing time') delete f.command.parameters.out_ms;
    if (kind === 'fractional') f.command.parameters.in_ms = .5;
    if (kind === 'negative') f.command.parameters.in_ms = -1;
    if (kind === 'reversed') f.command.parameters.out_ms = f.command.parameters.in_ms;
    if (kind === 'too long') f.command.parameters.out_ms = 120_251;
    expect(() => assertCanvasAudioTrimTaskCommand(f.binding, f.command)).toThrow();
  });

it.each(['canvas version', 'canvas digest', 'source pin', 'missing card', 'metadata stale', 'project'] as const)(
  'rejects a changed return target: %s', kind => {
    const f = fixture();
    if (kind === 'canvas version') f.canvas.version++;
    if (kind === 'canvas digest') f.canvas.definition_digest = 'f'.repeat(64);
    if (kind === 'source pin') f.canvas.definition.cards[0].asset!.version++;
    if (kind === 'missing card') f.canvas.definition.cards.shift();
    if (kind === 'metadata stale') f.canvas.reference_states[0].state = 'STALE';
    if (kind === 'project') f.canvas.project_id = 'other-project';
    expect(() => assertCanvasAudioTrimTaskTarget(f.origin, f.canvas)).toThrow();
  });

it.each(['owner', 'provider', 'source', 'adapter', 'operation', 'parameters', 'format', 'fallback'] as const)(
  'does not match an unrelated or altered original receipt: %s', kind => {
    const f = fixture();
    if (kind === 'owner') f.job.owner = 'image';
    if (kind === 'provider') f.job.provider = { provider_id: 'provider', model_id: 'model', local: false, route_digest: sourceDigest };
    if (kind === 'source') f.job.sources[0].id = 'other-source';
    if (kind === 'adapter') f.job.execution_recipe.adapter = 'HTTP_API';
    if (kind === 'operation') f.job.execution_recipe.operation_id = 'm8.audio.music';
    if (kind === 'parameters') f.job.execution_recipe.parameters = { in_ms: 250, out_ms: 1500 };
    if (kind === 'format') f.job.execution_recipe.output_profile = 'FLAC_S16_48000_STEREO_COMPRESSION5';
    if (kind === 'fallback') Object.assign(f.job.execution_recipe, { automatic_fallback: true });
    expect(canvasAudioTrimTaskJobMatches(f.binding, f.job)).toBe(false);
  });

it.each(['unreviewed', 'candidate kind', 'candidate digest', 'approved version', 'deleted result', 'wrong project', 'wrong branch', 'wrong media'] as const)(
  'preserves the original card when the adopted asset is not the exact formal WAV result: %s', kind => {
    const f = fixture(), before = structuredClone(f.canvas);
    if (kind === 'unreviewed') f.job.status = 'AWAITING_REVIEW';
    if (kind === 'candidate kind') f.job.output_candidate!.kind = 'video';
    if (kind === 'candidate digest') f.result.sha256 = 'f'.repeat(64);
    if (kind === 'approved version') f.result.version--;
    if (kind === 'deleted result') f.result.deleted_at = f.result.updated_at;
    if (kind === 'wrong project') f.result.novel_id = 'other-project';
    if (kind === 'wrong branch') f.result.branch_id = 'other-branch';
    if (kind === 'wrong media') f.result.media_type = 'audio/mpeg';
    expect(() => replaceCanvasAudioTrimTaskResult(f.origin, f.canvas, f.job, f.result)).toThrow();
    expect(f.canvas).toEqual(before);
  });

it('keeps the original source type and accepts a null-free provider/model command', () => {
  const f = fixture(); delete f.command.provider_id; delete f.command.model_id;
  expect(canvasAudioTrimTaskSource(f.source)).toEqual(f.input);
  expect(() => canvasAudioTrimTaskSource({ ...f.source, kind: 'image' })).toThrow();
  expect(() => assertCanvasAudioTrimTaskCommand(f.binding, f.command)).not.toThrow();
});

it('matches the native receipt null projection while keeping fresh commands strict', () => {
  const f = fixture();
  // Same bounded historical projection as the real CPU AudioJob preview receipt.
  Object.assign(f.job.command!.parameters, { width: null, height: null, steps: null, seed: null, cfg: null,
    negative_prompt: null, size: null, quality: null, duration_seconds: null, frame_rate: null, voice_id: null, speech_rate: null });
  f.job.sources[0].reference_only = true;
  f.job.command!.source_snapshots[0].reference_only = true;
  expect(canvasAudioTrimTaskJobMatches(f.binding, f.job)).toBe(true);
  expect(replaceCanvasAudioTrimTaskResult(f.origin, f.canvas, f.job, f.result).cards[0].asset?.asset_id).toBe(f.result.id);
  expect(() => assertCanvasAudioTrimTaskCommand(f.binding, { ...f.command, parameters: f.job.command!.parameters })).toThrow();
});

it.each(['unknown null', 'known real value', 'audio control null', 'recipe null', 'changed pin'] as const)(
  'rejects an unsafe native receipt projection: %s', kind => {
    const f = fixture();
    if (kind === 'unknown null') Object.assign(f.job.command!.parameters, { unknown_control: null });
    if (kind === 'known real value') Object.assign(f.job.command!.parameters, { seed: 0 });
    if (kind === 'audio control null') Object.assign(f.job.command!.parameters, { gain_db: null });
    if (kind === 'recipe null') f.job.execution_recipe.parameters = { ...f.job.command!.parameters, seed: null };
    if (kind === 'changed pin') {
      f.job.command!.source_snapshots[0].reference_only = true;
      f.job.command!.source_snapshots[0].version++;
    }
    expect(canvasAudioTrimTaskJobMatches(f.binding, f.job)).toBe(false);
  });

it('captures and rechecks the original persisted audio binding without guessing another target', () => {
  const f = fixture(true);
  expect(f.origin.binding?.incarnation).toBe(incarnation);
  expect(() => assertCanvasAudioTrimTaskCommand(f.binding, f.command)).not.toThrow();
  expect(canvasAudioTrimTaskJobMatches(f.binding, f.job)).toBe(true);
  expect(replaceCanvasAudioTrimTaskResult(f.origin, f.canvas, f.job, f.result).cards[0].asset?.asset_id).toBe('formal-audio');
});

it.each(['scope', 'incarnation', 'card', 'missing binding'] as const)('rejects an altered persisted binding: %s', kind => {
  const f = fixture(true);
  if (kind === 'scope') f.canvas.scope = { mode: 'collaboration', novel_id: 'project', workspace_id: 'workspace', storyline_id: 'storyline', branch_id: 'branch' };
  if (kind === 'incarnation') f.job.command!.canvas_return!.incarnation = 'file:11234567-89ab-4cde-8fab-0123456789ab';
  if (kind === 'card') f.job.command!.canvas_return!.card_id = 'other';
  if (kind === 'missing binding') delete f.job.command!.canvas_return;
  expect(() => replaceCanvasAudioTrimTaskResult(f.origin, f.canvas, f.job, f.result)).toThrow();
});


it('preserves optional canvas gain/fades in the original command and exact recipe, including explicit zero', () => {
  const f=fixture(true);
  Object.assign(f.command.parameters,{gain_db:-6,fade_in_ms:100,fade_out_ms:200});
  f.job.command=structuredClone(f.command);f.job.execution_recipe.parameters={...f.command.parameters};
  expect(()=>assertCanvasAudioTrimTaskCommand(f.binding,f.command)).not.toThrow();
  expect(canvasAudioTrimTaskJobMatches(f.binding,f.job)).toBe(true);
  f.job.execution_recipe.parameters={in_ms:250,out_ms:1250,gain_db:-5,fade_in_ms:100,fade_out_ms:200};
  expect(canvasAudioTrimTaskJobMatches(f.binding,f.job)).toBe(false);
  Object.assign(f.command.parameters,{gain_db:0,fade_in_ms:0,fade_out_ms:0});
  f.job.command=structuredClone(f.command);f.job.execution_recipe.parameters={...f.command.parameters};
  expect(canvasAudioTrimTaskJobMatches(f.binding,f.job)).toBe(true);
});
