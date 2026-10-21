import { afterEach, expect, it, vi } from 'vitest';
import { assertCanvasImageTaskCommand, canvasImageTaskJobMatches, canvasImageTaskSource, captureCanvasImageTask, replaceCanvasImageTaskResult, type CanvasImageTaskBinding } from './canvasImageTask';
import { studioProductionClient, type MediaCommand, type ProductionJob, type ProductionPreview, type ProductionProvider } from './studioProductionClient';
import type { StudioAsset } from './studioClient';
import type { CanvasViewRecord } from './studioCanvasViewClient';
import captured from './fixtures/image-composite.capture.json';

const actual = captured as unknown as { command: MediaCommand; preview: ProductionPreview; queued: ProductionJob; executed: ProductionJob; approved: ProductionJob; assets: StudioAsset[]; saved: StudioAsset };
const clone = <T,>(value: T): T => structuredClone(value);
const incarnation = 'file:00000000-0000-4000-8000-000000000001';
afterEach(() => vi.unstubAllGlobals());
function fixture(bound = false) {
  const asset = clone(actual.assets[0]);
  const canvas = { project_id: asset.novel_id, scope: { mode: 'local', novel_id: asset.novel_id }, id: 'original-canvas', version: 3, definition_digest: 'c'.repeat(64),
    definition: { schema_version: 1, title: 'Original work', cards: [
      { id: 'original-card', position: { x: 41, y: 63 }, asset: { asset_id: asset.id, version: asset.version, digest: asset.sha256, kind: 'image' } },
      { id: 'other-card', position: { x: 200, y: 300 } }], groups: [{ id: 'original-group', name: 'Original', card_ids: ['original-card'], collapsed: false }], viewport: { x: 17, y: 23, zoom: 1 } },
    reference_states: [{ card_id: 'original-card', state: 'CURRENT_METADATA' }] } as CanvasViewRecord;
  const origin = captureCanvasImageTask(canvas, 'original-card', asset, bound ? incarnation : undefined);
  const task: CanvasImageTaskBinding = { source: canvasImageTaskSource(origin.source), isCurrent: () => true, ...(origin.binding ? { returnBinding: clone(origin.binding) } : {}) };
  const command = clone(actual.command), job = clone(actual.approved);
  if (origin.binding) { command.canvas_return = clone(origin.binding); job.command!.canvas_return = clone(origin.binding); }
  return { asset, canvas, origin, task, command, job, result: clone(actual.saved) };
}

it.each([false, true])('admits original local CPU composite and its recorded APPROVED Job (bound=%s)', bound => {
  const f = fixture(bound);
  expect(() => assertCanvasImageTaskCommand(f.task, f.command)).not.toThrow();
  expect(canvasImageTaskJobMatches(f.task, f.job)).toBe(true);
});
it.each([false, true])('keeps the original target when explicit order puts the original image on top (bound=%s)', bound => {
  const f = fixture(bound);
  f.command.source_snapshots.reverse(); f.command.image_layers!.reverse();
  expect(() => assertCanvasImageTaskCommand(f.task, f.command)).not.toThrow();
  // A new queued order has no processing proof or candidate; no claim of CPU execution.
  const job = clone(actual.queued); job.command = clone(f.command); job.sources = clone(f.command.source_snapshots);
  job.execution_recipe = { ...clone(job.execution_recipe), layers: clone(f.command.image_layers!) };
  expect(canvasImageTaskJobMatches(f.task, job)).toBe(true);
});
it.each([[true, 0], [false, 255], [true, 255]] as const)('retains real layer visibility=%s opacity=%s without a new execution capability', (visible, opacity) => {
  const f = fixture(); f.command.image_layers![1].visible = visible; f.command.image_layers![1].opacity = opacity;
  expect(() => assertCanvasImageTaskCommand(f.task, f.command)).not.toThrow();
});
it('refuses a provider picker for a provider-null CPU composite', () => {
  const f = fixture(); expect(() => assertCanvasImageTaskCommand(f.task, f.command, { local: true } as ProductionProvider)).toThrow();
});
it.each(['provider', 'model', 'prompt', 'cloud', 'parameters', 'width', 'height', 'operation', 'missing original', 'original version', 'original digest', 'duplicate original', 'third source', 'source order only', 'layer order only', 'third layer', 'missing layer', 'opacity string', 'opacity float', 'opacity negative', 'opacity overflow', 'visibility number', 'x', 'y', 'transform', 'source kind', 'source extra', 'layer pin', 'image_source', 'image_references', 'mask_source', 'video_frames', 'unknown route', 'retired target'] as const)('rejects unsupported or substituted composite input: %s', kind => {
  const f = fixture(), c = f.command as any;
  if (kind === 'provider') c.provider_id = 'local'; if (kind === 'model') c.model_id = 'model'; if (kind === 'prompt') c.prompt = 'generate'; if (kind === 'cloud') c.allow_cloud = true;
  if (kind === 'parameters') c.parameters = { seed: 1 }; if (kind === 'width') c.parameters = { width: 128 }; if (kind === 'height') c.parameters = { height: 128 }; if (kind === 'operation') c.operation_id = 'm5.image.t2i';
  if (kind === 'missing original') { c.source_snapshots[0].id = 'replacement'; c.image_layers[0].source.id = 'replacement'; }
  if (kind === 'original version') { c.source_snapshots[0].version++; c.image_layers[0].source.version++; }
  if (kind === 'original digest') { c.source_snapshots[0].digest = 'e'.repeat(64); c.image_layers[0].source.digest = 'e'.repeat(64); }
  if (kind === 'duplicate original') { c.source_snapshots[1] = clone(c.source_snapshots[0]); c.image_layers[1].source = clone(c.source_snapshots[0]); }
  if (kind === 'third source') c.source_snapshots.push({ ...c.source_snapshots[1], id: 'third' }); if (kind === 'source order only') c.source_snapshots.reverse(); if (kind === 'layer order only') c.image_layers.reverse();
  if (kind === 'third layer') c.image_layers.push(clone(c.image_layers[0])); if (kind === 'missing layer') c.image_layers.pop();
  if (kind === 'opacity string') c.image_layers[1].opacity = '128'; if (kind === 'opacity float') c.image_layers[1].opacity = 0.5; if (kind === 'opacity negative') c.image_layers[1].opacity = -1; if (kind === 'opacity overflow') c.image_layers[1].opacity = 256;
  if (kind === 'visibility number') c.image_layers[1].visible = 1; if (['x', 'y', 'transform'].includes(kind)) c.image_layers[1][kind] = 0;
  if (kind === 'source kind') { c.source_snapshots[1].asset_kind = 'audio'; c.image_layers[1].source.asset_kind = 'audio'; } if (kind === 'source extra') c.source_snapshots[1].secret = 'not-a-pin'; if (kind === 'layer pin') c.image_layers[1].source.version++;
  if (['image_source', 'image_references', 'mask_source', 'video_frames'].includes(kind)) c[kind] = undefined;
  if (kind === 'unknown route') c.provider_url = 'https://invalid.example'; if (kind === 'retired target') f.task.isCurrent = () => false;
  expect(() => assertCanvasImageTaskCommand(f.task, c)).toThrow();
});

it.each(['owner', 'provider', 'command route', 'command operation', 'request', 'job source order', 'job source version', 'job source digest', 'command original', 'command layers', 'recipe adapter', 'recipe order', 'recipe alpha', 'recipe visibility', 'recipe parameters', 'recipe dimensions', 'recipe extra', 'recipe profile', 'recipe algorithm', 'recipe digest', 'fallback', 'automatic replay', 'remote compute', 'proof null', 'proof source order', 'proof source digest', 'proof width', 'proof height', 'proof bytes', 'proof output', 'proof layers digest', 'proof algorithm', 'candidate kind'] as const)('refuses mismatched composite Job/recipe/proof: %s', kind => {
  const f = fixture(), j = f.job as any;
  if (kind === 'owner') j.owner = 'audio'; if (kind === 'provider') j.provider = { local: true }; if (kind === 'command route') j.command.provider_id = 'local'; if (kind === 'command operation') j.command.operation_id = 'm5.image.cutout'; if (kind === 'request') j.request_id = 'another-request';
  if (kind === 'job source order') j.sources.reverse(); if (kind === 'job source version') j.sources[1].version++; if (kind === 'job source digest') j.sources[1].digest = 'e'.repeat(64);
  if (kind === 'command original') { j.command.source_snapshots[0].version++; j.command.image_layers[0].source.version++; } if (kind === 'command layers') j.command.image_layers[1].opacity++;
  if (kind === 'recipe adapter') j.execution_recipe.adapter = 'LOCAL_CPU_MASK'; if (kind === 'recipe order') j.execution_recipe.layers.reverse(); if (kind === 'recipe alpha') j.execution_recipe.layers[1].opacity++; if (kind === 'recipe visibility') j.execution_recipe.layers[1].visible = false;
  if (kind === 'recipe parameters') j.execution_recipe.parameters = { seed: 1 }; if (kind === 'recipe dimensions') j.execution_recipe.width = 128; if (kind === 'recipe extra') j.execution_recipe.graph = {}; if (kind === 'recipe profile') j.execution_recipe.output_profile = 'JPEG'; if (kind === 'recipe algorithm') j.execution_recipe.algorithm = 'AI_BLEND'; if (kind === 'recipe digest') j.execution_recipe.recipe_digest = 'unknown';
  if (kind === 'fallback') j.execution_recipe.automatic_fallback = true; if (kind === 'automatic replay') j.automatic_replay = true; if (kind === 'remote compute') j.remote_compute_may_continue = true;
  if (kind === 'proof null') j.processing_proof = null; if (kind === 'proof source order') j.processing_proof.source_sha256.reverse(); if (kind === 'proof source digest') j.processing_proof.source_sha256[1] = 'e'.repeat(64);
  if (kind === 'proof width') j.processing_proof.width = 63; if (kind === 'proof height') j.processing_proof.height = 1032; if (kind === 'proof bytes') j.processing_proof.output_bytes = 1; if (kind === 'proof output') j.processing_proof.output_sha256 = 'e'.repeat(64); if (kind === 'proof layers digest') j.processing_proof.layers_digest = 'unknown'; if (kind === 'proof algorithm') j.processing_proof.algorithm = 'AI_BLEND'; if (kind === 'candidate kind') j.output_candidate.kind = 'audio';
  expect(canvasImageTaskJobMatches(f.task, j)).toBe(false);
});
it.each([0, 1])('rejects sparse Job sources missing slot %s', index => {
  const f = fixture(); delete f.job.sources[index]; expect(canvasImageTaskJobMatches(f.task, f.job)).toBe(false);
});
it.each([undefined, null, {}, [], { operation_id: 'm5.image.composite' }, { operation_id: 'm5.image.composite', owner: 'image', provider: null, command: {} }])('returns false without throwing for damaged composite Jobs: %j', job => {
  const task = fixture().task; expect(() => canvasImageTaskJobMatches(task, job as ProductionJob)).not.toThrow(); expect(canvasImageTaskJobMatches(task, job as ProductionJob)).toBe(false);
});

it('replaces only the explicitly bound original card after original APPROVED review, keeping layout/groups/other cards', () => {
  const f = fixture(true), before = clone(f.canvas), next = replaceCanvasImageTaskResult(f.origin, f.canvas, f.job, f.result);
  expect(next.cards[0].asset).toEqual({ asset_id: f.result.id, version: f.result.version, digest: f.result.sha256, kind: 'image' });
  expect(next.cards[0].position).toEqual(before.definition.cards[0].position); expect(next.cards[1]).toBe(f.canvas.definition.cards[1]); expect(next.groups).toBe(f.canvas.definition.groups); expect(next.viewport).toBe(f.canvas.definition.viewport); expect(f.canvas).toEqual(before);
});
it.each(['unreviewed', 'canvas version', 'canvas digest', 'deleted card', 'replaced source', 'scope', 'incarnation', 'wrong target card', 'result digest', 'result version', 'result deleted', 'wrong project'] as const)('blocks composite adoption on stale original target/review: %s', kind => {
  const f = fixture(true);
  if (kind === 'unreviewed') f.job.status = 'AWAITING_REVIEW'; if (kind === 'canvas version') f.canvas.version++; if (kind === 'canvas digest') f.canvas.definition_digest = 'f'.repeat(64); if (kind === 'deleted card') f.canvas.definition.cards = []; if (kind === 'replaced source') f.canvas.definition.cards[0].asset!.version++;
  if (kind === 'scope') f.canvas.scope = { mode: 'local', novel_id: 'foreign' }; if (kind === 'incarnation') f.job.command!.canvas_return!.incarnation = 'file:11111111-1111-4111-8111-111111111111'; if (kind === 'wrong target card') f.job.command!.canvas_return!.card_id = 'other-card';
  if (kind === 'result digest') f.result.sha256 = 'f'.repeat(64); if (kind === 'result version') f.result.version++; if (kind === 'result deleted') f.result.deleted_at = 'deleted'; if (kind === 'wrong project') f.job.novel_id = 'foreign';
  expect(() => replaceCanvasImageTaskResult(f.origin, f.canvas, f.job, f.result)).toThrow();
});
it('decodes original native preview, queued/executed/approved CPU receipts with exact binding through the original strict SDK', async () => {
  const f = fixture(true), client = studioProductionClient(f.asset.novel_id, { sessionToken: '' });
  const reply = (value: unknown) => vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, status: 200, json: async () => clone(value) })));
  const preview = clone(actual.preview); preview.command.canvas_return = clone(f.origin.binding!); reply(preview);
  expect(await client.preview(f.command)).toEqual(preview);
  for (const native of [actual.queued, actual.executed, actual.approved]) {
    const row = clone(native); row.command!.canvas_return = clone(f.origin.binding!); reply(row);
    const decoded = await client.get('image', row.id); expect(canvasImageTaskJobMatches(f.task, decoded)).toBe(true);
    if (decoded.status === 'APPROVED') expect(replaceCanvasImageTaskResult(f.origin, f.canvas, decoded, f.result).cards[0].asset!.asset_id).toBe(f.result.id);
  }
});
