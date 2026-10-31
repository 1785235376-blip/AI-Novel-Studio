import { beforeEach, describe, expect, it, vi } from 'vitest';
import requestFixture from './fixtures/phase5.capture.video-request.json';
import jobFixture from './fixtures/phase5.capture.video-approved.json';
import legacyGraphFixture from './fixtures/phase4.file-api-video-graph.json';
import legacyJobFixture from './fixtures/phase4.file-api-job-reviewed.json';
import { checkedStoryboardShotContext, storyboardShotFields, sameStoryboardShot } from './studioVideoRuntimeContract';
import { createStudioGraphClient } from './studioGraphClient';
import { studioProductionClient, type RecordedProductionSource } from './studioProductionClient';

const transport = vi.hoisted(() => ({ json: vi.fn(), blob: vi.fn() }));
vi.mock('./studioClient', async importOriginal => ({ ...await importOriginal<typeof import('./studioClient')>(), studioTransport: () => transport }));
const copy = <T,>(value: T): T => structuredClone(value);
const row = (value: unknown) => value as Record<string, unknown>;
const pin = () => checkedStoryboardShotContext(copy(requestFixture.shot_pin));
// Inert identity in a transport-only unit: no Host/session/network is invoked.
const unitContext = { sessionToken: 'synthetic-transport-unit' };
const sources = (): RecordedProductionSource[] => requestFixture.command.source_snapshots.map(source => {
  const base = { id: source.id, version: source.version, digest: source.digest, reference_only: true as const };
  return source.kind === 'CREATIVE_DOCUMENT' ? { ...base, kind: 'CREATIVE_DOCUMENT' } : { ...base, kind: 'ASSET', asset_kind: 'image' };
});
beforeEach(() => { transport.json.mockReset(); transport.blob.mockReset(); });

describe('Phase 5 Shot input is explicit and does not widen old media identity', () => {
  it('keeps an absent original field absent and validates actual opt-in input', () => {
    expect(storyboardShotFields(undefined, [], 'm7.video.t2v')).toEqual({});
    expect(Object.hasOwn(storyboardShotFields(undefined, [], 'm7.video.t2v'), 'storyboard_shot')).toBe(false);
    expect(storyboardShotFields(requestFixture.command.storyboard_shot, sources(), requestFixture.command.operation_id)).toEqual({ storyboard_shot: pin() });
    expect(sameStoryboardShot({}, { command: 'legacy' })).toBe(true);
    expect(sameStoryboardShot({ storyboard_shot: pin() }, {})).toBe(false);
    expect(sameStoryboardShot({}, { storyboard_shot: pin() })).toBe(false);
    expect(() => storyboardShotFields(null, sources(), 'm7.video.t2v')).toThrow();
  });
  it.each([
    ['document owner', (v: Record<string, unknown>) => { row(v.document_snapshot).id = 'other'; }],
    ['document revision', (v: Record<string, unknown>) => { row(v.document_snapshot).version = 0; }],
    ['document digest', (v: Record<string, unknown>) => { row(v.document_snapshot).digest = 'bad'; }],
    ['Shot version bool', (v: Record<string, unknown>) => { v.shot_version = true; }],
    ['Shot identity controls', (v: Record<string, unknown>) => { v.shot_id = 'shot\n'; }],
    ['unknown approval grant', (v: Record<string, unknown>) => { v.approved = true; }],
  ])('rejects malformed %s before original media consumption', (_name, mutate) => {
    const value = row(copy(requestFixture.shot_pin)); mutate(value);
    expect(() => storyboardShotFields(value, sources(), requestFixture.command.operation_id)).toThrow();
  });
  it('requires exactly the original Creative source and a Video operation', () => {
    expect(() => storyboardShotFields(pin(), [], 'm7.video.t2v')).toThrow();
    expect(() => storyboardShotFields(pin(), sources(), 'm8.audio.speech')).toThrow();
    expect(() => storyboardShotFields(pin(), [...sources(), sources()[0]], 'm7.video.i2v')).toThrow();
    const changed = sources(); changed[0].version++;
    expect(() => storyboardShotFields(pin(), changed, 'm7.video.i2v')).toThrow();
  });
});

describe('Original production Job decoder and late response retain exact Shot context', () => {
  it('accepts the actual approved original Job with new immutable input', async () => {
    transport.json.mockResolvedValue(copy(jobFixture));
    const client = studioProductionClient(jobFixture.novel_id, unitContext);
    const job = await client.get('video', jobFixture.id);
    expect(job.command?.storyboard_shot).toEqual(pin());
    expect(job.status).toBe('APPROVED'); expect(job.automatic_replay).toBe(false);
  });
  it('still decodes the original Phase 4 approved Job without injecting a field', async () => {
    transport.json.mockResolvedValue(copy(legacyJobFixture));
    const job = await studioProductionClient(legacyJobFixture.novel_id, unitContext).get('video', legacyJobFixture.id);
    expect(Object.hasOwn(job.command!, 'storyboard_shot')).toBe(false);
  });
  it('rejects a pin that disagrees with original persisted Job sources', async () => {
    const bad = copy(jobFixture); bad.command.storyboard_shot.document_snapshot.version++;
    transport.json.mockResolvedValue(bad);
    await expect(studioProductionClient(jobFixture.novel_id, unitContext).get('video', jobFixture.id)).rejects.toBeTruthy();
  });
  it('does not adopt an action response that drops the observed new pin', async () => {
    transport.json.mockResolvedValueOnce(copy(jobFixture));
    const client = studioProductionClient(jobFixture.novel_id, unitContext), job = await client.get('video', jobFixture.id);
    const changed = row(copy(jobFixture)); delete row(changed.command).storyboard_shot;
    transport.json.mockResolvedValueOnce(changed);
    // This transport-unit assertion only exercises an original response fence.
    // The real controller/server separately deny cancelling an approved Job.
    await expect(client.cancel(job)).rejects.toBeTruthy();
  });
});

describe('Schema 5 stored Video graph only admits explicit bind_shot true', () => {
  it('keeps the actual original graph request body free of default new fields', async () => {
    const json = vi.fn().mockResolvedValue(copy(legacyGraphFixture));
    const client = createStudioGraphClient(legacyGraphFixture.project_id, {}, { json });
    const graph = await client.get(legacyGraphFixture.id), node = graph.definition.nodes.find(node => node.definition_id === 'video_generate')!;
    expect(Object.hasOwn(node.parameters, 'bind_shot')).toBe(false);
  });
  it('reads an explicitly opted-in node without replacing its original Shot source', async () => {
    const value = copy(legacyGraphFixture), node = value.definition.nodes.find(node => node.definition_id === 'video_generate')!;
    row(node.parameters).bind_shot = true;
    const json = vi.fn().mockResolvedValue(value), client = createStudioGraphClient(value.project_id, {}, { json });
    expect((await client.get(value.id)).definition.nodes.find(node => node.definition_id === 'video_generate')!.parameters.bind_shot).toBe(true);
    expect(value.definition.edges.some(edge => edge.target_node_id === node.id && edge.target_port === 'shot')).toBe(true);
  });
  it.each([false, null, 1, 'true'])('rejects a non-explicit true flag %s', async flag => {
    const value = copy(legacyGraphFixture), node = value.definition.nodes.find(node => node.definition_id === 'video_generate')!;
    row(node.parameters).bind_shot = flag;
    const json = vi.fn().mockResolvedValue(value);
    await expect(createStudioGraphClient(value.project_id, {}, { json }).get(value.id)).rejects.toBeTruthy();
  });
});
