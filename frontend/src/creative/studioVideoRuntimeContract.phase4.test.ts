import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useLocalHostSession } from '../localHostSession';
import providersFixture from './fixtures/phase4.file-api-providers.json';
import previewFixture from './fixtures/phase4.file-api-preview.json';
import queuedFixture from './fixtures/phase4.file-api-job-queued.json';
import runningFixture from './fixtures/phase4.file-api-job-running.json';
import candidateFixture from './fixtures/phase4.file-api-job-candidate.json';
import reviewedFixture from './fixtures/phase4.file-api-job-reviewed.json';
import { checkedVideoCapabilities, checkedVideoRecipe, checkedVideoReference, sameVideoReference, VIDEO_RECIPE_IDS } from './studioVideoRuntimeContract';
import { studioProductionClient, type MediaCommand, type ProductionSource } from './studioProductionClient';

const copy = <T,>(value: T): T => structuredClone(value);
const record = (value: unknown) => value as Record<string, unknown>;
const source: ProductionSource = { id: 'synthetic-video', kind: 'ASSET', asset_kind: 'video', version: 2, digest: 'a'.repeat(64) };
const capability = () => copy(providersFixture.items.find(item => item.operation_id === 'm7.video.t2v')!.video_capabilities!);
const recipe = () => copy(previewFixture.execution_recipe);
const command = (): MediaCommand => copy(queuedFixture.command) as MediaCommand;

describe('Fixed Video recipes describe structure without claiming inference', () => {
  it.each(VIDEO_RECIPE_IDS)('accepts only a structural %s capability', recipe_id => {
    const value = { ...capability(), recipe_id, operations: recipe_id === 'comfy-hunyuan10-t2v-v1' ? ['t2v'] : ['t2v', 'i2v'] };
    expect(checkedVideoCapabilities(value, 'm7.video.t2v').inference_verified).toBe(false);
    if (recipe_id === 'comfy-hunyuan10-t2v-v1') expect(() => checkedVideoCapabilities(value, 'm7.video.i2v')).toThrow();
    else expect(checkedVideoCapabilities(value, 'm7.video.i2v').reference_video_execution).toBe(false);
  });
  it('rejects Hunyuan I2V in both metadata and fixed execution recipes', () => {
    expect(() => checkedVideoCapabilities({ ...capability(), recipe_id: 'comfy-hunyuan10-t2v-v1' }, 'm7.video.t2v')).toThrow();
    expect(() => checkedVideoRecipe({ ...recipe(), video_recipe_id: 'comfy-hunyuan10-t2v-v1' }, 'm7.video.i2v')).toThrow();
  });
  it.each([
    { inference_verified: true }, { structural_only: false }, { reference_video_execution: true },
    { output_format: 'MP4' }, { reference_semantics: 'NATIVE_MOTION' }, { recipe_id: 'arbitrary-workflow' },
    { operations: ['i2v', 't2v'] }, { operations: ['t2v', 'i2v', 'v2v'] }, { command: 'download' },
  ])('rejects unsupported capability claims %j', fields => {
    expect(() => checkedVideoCapabilities({ ...capability(), ...fields }, 'm7.video.t2v')).toThrow();
  });
  it('requires the requested operation to be structurally supported', () => {
    expect(() => checkedVideoCapabilities({ ...capability(), operations: ['t2v'] }, 'm7.video.i2v')).toThrow();
    expect(() => checkedVideoCapabilities(capability(), 'm7.video.v2v')).toThrow();
  });
  it('accepts the mounted fixed WAN recipe with nine frames and 1125 ms duration', () => {
    expect(() => checkedVideoRecipe(recipe(), 'm7.video.t2v')).not.toThrow();
    expect(recipe().timing).toEqual({ width: 64, height: 64, frames: 9, frame_rate: 8, duration_ms: 1125 });
  });
  it.each(['frames', 'duration_ms', 'width', 'height', 'frame_rate'] as const)('rejects inconsistent fixed timing %s', field => {
    const value = recipe(); value.timing[field]++; expect(() => checkedVideoRecipe(value, 'm7.video.t2v')).toThrow();
  });
  it.each([
    ['fractional duration', { duration_seconds: 1.5 }], ['unbounded duration', { duration_seconds: 11 }],
    ['unaligned dimensions', { width: 65 }], ['unbounded dimensions', { width: 1056 }],
    ['unbounded frame rate', { frame_rate: 31 }],
  ])('rejects %s before accepting a recipe', (_label, fields) => {
    const value = recipe(); Object.assign(value.parameters, fields); expect(() => checkedVideoRecipe(value, 'm7.video.t2v')).toThrow();
  });
  it('checks each family frame stride rather than copying a nominal duration', () => {
    const ltx = recipe(); ltx.video_recipe_id = 'comfy-ltx095-video-v1'; ltx.parameters.frame_rate = 10;
    Object.assign(ltx.timing, { frames: 17, frame_rate: 10, duration_ms: 1700 });
    expect(() => checkedVideoRecipe(ltx, 'm7.video.t2v')).not.toThrow();
    ltx.timing.frames = 13; ltx.timing.duration_ms = 1300; expect(() => checkedVideoRecipe(ltx, 'm7.video.t2v')).toThrow();
    const wan = recipe(); wan.parameters.frame_rate = 10; Object.assign(wan.timing, { frames: 13, frame_rate: 10, duration_ms: 1300 });
    expect(() => checkedVideoRecipe(wan, 'm7.video.t2v')).not.toThrow();
  });
  it('rejects a local v2v inference claim and allows unrelated legacy recipes', () => {
    expect(() => checkedVideoRecipe(recipe(), 'm7.video.v2v')).toThrow();
    expect(() => checkedVideoRecipe({ adapter: 'LEGACY_FIXED_PROVIDER' }, 'm7.video.t2v')).not.toThrow();
    const verified = { ...recipe(), inference_verified: true }; expect(() => checkedVideoRecipe(verified, 'm7.video.t2v')).toThrow();
  });
});

describe('Video references bind a single original Asset version and authored purpose', () => {
  it.each(['style', 'action', 'camera'] as const)('accepts %s without changing the source pin', purpose => {
    expect(checkedVideoReference({ source, purpose }, [source], 'm7.video.v2v')).toEqual({ video_reference: { source, purpose } });
  });
  it('omits old unset references and includes purpose in equality', () => {
    expect(checkedVideoReference(undefined, [], 'm7.video.t2v')).toEqual({});
    const expected = { video_reference: { source, purpose: 'camera' as const } };
    expect(sameVideoReference(expected, copy(expected))).toBe(true);
    expect(sameVideoReference(expected, { video_reference: { source, purpose: 'action' } })).toBe(false);
    expect(sameVideoReference(expected, {})).toBe(false);
  });
  it.each([
    ['changed version', { source: { ...source, version: 3 }, purpose: 'style' }],
    ['changed digest', { source: { ...source, digest: 'b'.repeat(64) }, purpose: 'style' }],
    ['wrong Asset kind', { source: { ...source, asset_kind: 'image' }, purpose: 'style' }],
    ['unknown purpose', { source, purpose: 'identity-guarantee' }],
    ['unknown source field', { source: { ...source, path: '/private/media' }, purpose: 'style' }],
    ['source not reference', { source: { ...source, reference_only: false }, purpose: 'style' }],
  ])('rejects %s', (_label, value) => {
    expect(() => checkedVideoReference(value, [source], 'm7.video.v2v')).toThrow();
  });
  it('rejects a second reference or a reference on unrelated operations', () => {
    expect(() => checkedVideoReference({ source, purpose: 'style' }, [source, { ...source, id: 'second-video' }], 'm7.video.v2v')).toThrow();
    expect(() => checkedVideoReference({ source, purpose: 'style' }, [source], 'm7.video.t2v')).toThrow();
  });
});

describe('Original production client parses actual mounted synthetic Video receipts', () => {
  let fetchMock: ReturnType<typeof vi.fn>;
  const reply = (value: unknown) => ({ ok: true, status: 200, json: async () => value });
  const client = () => studioProductionClient(queuedFixture.novel_id, { sessionToken: '', localHostToken: '' });
  beforeEach(() => { fetchMock = vi.fn(); vi.stubGlobal('fetch', fetchMock); useLocalHostSession.setState({ token: '', actorId: '' }); });
  afterEach(() => { vi.unstubAllGlobals(); useLocalHostSession.setState({ token: '', actorId: '' }); });
  it('lists metadata without dispatch, model probing or inferred readiness', async () => {
    fetchMock.mockResolvedValueOnce(reply(copy(providersFixture)));
    const result = await client().providers(); expect(result.filter(row => row.operation_id.startsWith('m7.'))).toHaveLength(2);
    expect(result.find(row => row.operation_id === 'm7.video.t2v')).toMatchObject({ local: true, readiness: 'CONFIGURED_NOT_VERIFIED', video_capabilities: { structural_only: true, inference_verified: false } });
    expect(fetchMock).toHaveBeenCalledTimes(1); expect(fetchMock.mock.calls[0][1].method).toBe('GET');
  });
  it('requires explicit reviewed preview, execute and human review of a private candidate', async () => {
    fetchMock.mockResolvedValueOnce(reply(copy(previewFixture))).mockResolvedValueOnce(reply(copy(queuedFixture)))
      .mockResolvedValueOnce(reply(copy(runningFixture))).mockResolvedValueOnce(reply(copy(candidateFixture))).mockResolvedValueOnce(reply(copy(reviewedFixture)));
    const api = client(), preview = await api.preview(command()), queued = await api.create(command(), preview.preview_digest);
    expect(queued.status).toBe('QUEUED'); expect(queued.output_candidate).toBeNull(); expect(queued.approved_asset_version).toBeNull();
    const running = await api.execute(queued); expect(running.status).toBe('REMOTE_RUNNING');
    const candidate = await api.refresh(running); expect(candidate.status).toBe('AWAITING_REVIEW'); expect(candidate.output_candidate?.version).toBe(1); expect(candidate.approved_asset_version).toBeNull();
    const reviewed = await api.review(candidate); expect(reviewed.status).toBe('APPROVED'); expect(reviewed.approved_asset_version).toBe(2);
    expect(fetchMock.mock.calls.map(([url]) => String(url).split('/').at(-1))).toEqual(['preview', 'jobs', 'execute', 'refresh', 'review']);
    expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toEqual({ command: command(), reviewed_preview_digest: preview.preview_digest });
    expect(JSON.parse(fetchMock.mock.calls[4][1].body)).toEqual({ expected_version: candidate.version, expected_request_digest: candidate.request_digest, reviewed_output_digest: candidate.output_candidate!.digest });
    expect(reviewed.product_acceptance).toBe('LOCAL_REQUIRED'); expect(reviewed.automatic_replay).toBe(false);
  });
  it.each([queuedFixture, runningFixture, candidateFixture, reviewedFixture])('reads the actual job at status $status', async value => {
    fetchMock.mockResolvedValueOnce(reply(copy(value))); const result = await client().get('video', value.id);
    expect(result.status).toBe(value.status); expect(result.execution_recipe).toEqual(value.execution_recipe);
  });
  it.each([
    ['scope', (r: Record<string, unknown>) => { r.novel_id = 'foreign-project'; }],
    ['branch', (r: Record<string, unknown>) => { r.branch_id = 'foreign-branch'; }],
    ['owner', (r: Record<string, unknown>) => { r.owner = 'image'; }],
    ['inference claim', (r: Record<string, unknown>) => { record(r.execution_recipe).inference_verified = true; }],
    ['frame count', (r: Record<string, unknown>) => { record(record(r.execution_recipe).timing).frames = 8; }],
    ['automatic replay', (r: Record<string, unknown>) => { r.automatic_replay = true; }],
    ['arbitrary recipe', (r: Record<string, unknown>) => { record(r.execution_recipe).shell = 'execute'; }],
  ])('rejects invalid job %s', async (_label, mutate) => {
    const value = record(copy(candidateFixture)); mutate(value); fetchMock.mockResolvedValueOnce(reply(value));
    await expect(client().get('video', candidateFixture.id)).rejects.toBeTruthy();
  });
  it('rejects provider inference claims and mismatched preview timing', async () => {
    const rows = copy(providersFixture); rows.items[1].video_capabilities!.inference_verified = true; fetchMock.mockResolvedValueOnce(reply(rows));
    await expect(client().providers()).rejects.toBeTruthy();
    const preview = copy(previewFixture); preview.execution_recipe.timing.frames++;
    fetchMock.mockResolvedValueOnce(reply(preview)); await expect(client().preview(command())).rejects.toBeTruthy();
  });
});
