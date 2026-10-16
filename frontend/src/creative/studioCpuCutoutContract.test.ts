// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import mountedFixture from './fixtures/cpuCutout.mounted.json';
import type { StudioAsset } from './studioClient';
import { studioProductionContracts } from './studioWorkspaceOperationContract';
import { STUDIO_PRODUCTION_INTERFACE_KEYS, STUDIO_PRODUCTION_INTERFACE_REFERENCES } from './studioWorkspaceOperationTypes';
import { useLocalHostSession } from '../localHostSession';
import { studioProductionClient, type MediaCommand } from './studioProductionClient';
import { eligibleCutoutMask } from './studioCutoutContract';
import { GRAPH_MEDIA_OPERATION_LABELS, MEDIA_OPERATION_LABELS } from './useStudioMediaExecution';
import { createStudioGraphClient } from './studioGraphClient';
import { cutoutAssets, cutoutCommand, cutoutJob, cutoutPreview, cutoutProject } from './studioCpuCutout.testFixtures';
let fetcher: ReturnType<typeof vi.fn>;
beforeEach(() => { useLocalHostSession.setState({ token: 'fixture-host', actorId: '' }); fetcher = vi.fn(); vi.stubGlobal('fetch', fetcher); });
afterEach(() => vi.unstubAllGlobals());
const respond = (value: unknown) => fetcher.mockResolvedValue({ ok: true, status: 200, json: async () => value });
const client = () => studioProductionClient(cutoutProject, { sessionToken: '' });
describe('standalone CPU cutout strict original DTO', () => {
  it('decodes the actual synthetic mounted API preview, queue, result and approval projections unchanged', async () => {
    const api = studioProductionClient(mountedFixture.source.novel_id, { sessionToken: '' });
    expect(eligibleCutoutMask(mountedFixture.mask as unknown as StudioAsset, mountedFixture.source as StudioAsset)).toBe(true);
    respond(mountedFixture.preview); expect(await api.preview(mountedFixture.command as MediaCommand)).toEqual(mountedFixture.preview);
    for (const row of [mountedFixture.queued, mountedFixture.executed, mountedFixture.approved]) {
      respond(row); expect(await api.get('image', row.id)).toEqual(row);
    }
  });
  it.each(['sources', 'measurement', 'pair', 'unknown'])('rejects incomplete or misbound measured preview %s', async kind => {
    const value = cutoutPreview();
    if (kind === 'sources') value.sources = undefined;
    else if (kind === 'measurement') value.sources![0].measured.width = 63;
    else if (kind === 'pair') value.sources![1].measured.height = 128;
    else value.sources![0].measured.path = '/private';
    respond(value); await expect(client().preview(cutoutCommand())).rejects.toThrow();
  });
  it('accepts explicit local preview and original queued/result projections', async () => {
    respond(cutoutPreview()); expect(await client().preview(cutoutCommand())).toEqual(cutoutPreview());
    for (const row of [cutoutJob(), cutoutJob('AWAITING_REVIEW', 3), cutoutJob('APPROVED', 5)]) {
      respond(row); expect(await client().get('image', row.id)).toEqual(row);
    }
  });
  it.each([
    { provider_id: 'provider' }, { model_id: 'model' }, { prompt: 'infer a mask' }, { allow_cloud: true }, { parameters: { width: 64 } },
    { source_snapshots: [] }, { source_snapshots: cutoutCommand().source_snapshots.slice(0, 1) },
    { source_snapshots: [cutoutCommand().source_snapshots[0], cutoutCommand().source_snapshots[0]] },
    { source_snapshots: cutoutCommand().source_snapshots.map(row => ({ ...row, reference_only: true })) },
  ])('rejects unsupported local command before network %j', async patch => {
    await expect(client().preview({ ...cutoutCommand(), ...patch } as MediaCommand)).rejects.toMatchObject({ problem: { code: 'STUDIO_RESPONSE_INVALID' } });
    expect(fetcher).not.toHaveBeenCalled();
  });
  it.each([
    { adapter: 'LOCAL_FFMPEG' }, { output_profile: 'JPEG' }, { mask_policy: 'INFER_MASK' }, { automatic_fallback: true }, { recipe_digest: 'bad' },
    { parameters: { width: 64 } }, { provider_url: 'https://untrusted.invalid' },
  ])('rejects altered preview recipe %j', async patch => {
    const value = cutoutPreview(); respond({ ...value, execution_recipe: { ...value.execution_recipe, ...patch } });
    await expect(client().preview(cutoutCommand())).rejects.toThrow();
  });
  it.each([
    { source_sha256: 'b'.repeat(64) }, { mask_sha256: 'a'.repeat(64) }, { output_sha256: 'a'.repeat(64) },
    { width: 63 }, { height: 1025 }, { output_bytes: 0 }, { output_bytes: 1 }, { output_bytes: 20 * 1024 * 1024 }, { output_bytes: 25 * 1024 * 1024 + 1 }, { keep_pixels: 0 },
    { remove_pixels: 1 }, { contract: 'unverified' }, { raw_path: '/private' },
  ])('rejects malformed/misbound CPU proof %j', async patch => {
    const row = cutoutJob('AWAITING_REVIEW', 3); respond({ ...row, processing_proof: { ...row.processing_proof, ...patch } });
    await expect(client().get('image', row.id)).rejects.toThrow();
  });
  it.each([
    { processing_proof: undefined }, { processing_proof: null }, { provider: { provider_id: 'p', model_id: 'm', route_digest: 'a'.repeat(64), local: true } },
    { remote_compute_may_continue: true }, { cancellation_mode: 'REMOTE_CANCEL' }, { owner: 'video' }, { novel_id: 'other' }, { branch_id: 'other' },
  ])('rejects missing proof or foreign/local-invalid result %j', async patch => {
    respond({ ...cutoutJob('AWAITING_REVIEW', 3), ...patch }); await expect(client().get('image', 'cutout-job')).rejects.toThrow();
  });
  it('rejects a queued response substituting another source despite echoed request identifiers', async () => {
    const command = cutoutCommand(), altered = { ...command, source_snapshots: command.source_snapshots.map((row, index) => index ? row : { ...row, id: 'other-source' }) };
    respond(cutoutJob('QUEUED', 1, altered)); await expect(client().create(command, 'e'.repeat(64))).rejects.toThrow();
  });
  it.each(['source', 'recipe', 'version'])('rejects a cutout action response changing its original %s binding', async kind => {
    const expected = cutoutJob('QUEUED', 2), result = cutoutJob('AWAITING_REVIEW', 4);
    if (kind === 'source') { result.sources[0].id = 'other'; result.command!.source_snapshots[0].id = 'other'; }
    else if (kind === 'recipe') result.execution_recipe.recipe_digest = 'a'.repeat(64);
    else result.version = 1;
    respond(result); await expect(client().execute(expected)).rejects.toThrow();
  });
  it('retains completed proof without a published candidate after interrupted publication', async () => {
    const row = { ...cutoutJob('AWAITING_REVIEW', 3), status: 'UNKNOWN', output_candidate: null }; respond(row);
    expect(await client().get('image', 'cutout-job')).toEqual(row);
  });
  it('rejects cutout provider catalog entries', async () => {
    respond({ health_probed: false, credentials_read: false, items: [{ operation_id: 'm5.image.cutout', provider_id: 'p', model_id: 'm', local: true,
      route_digest: 'a'.repeat(64), readiness: 'CONFIGURED_NOT_VERIFIED', supported_parameters: [] }] }); await expect(client().providers()).rejects.toThrow();
  });
});
describe('authored mask selection and closed Graph boundary', () => {
  it('accepts only a verified original authored mask for the current exact source', () => {
    const [source, mask] = cutoutAssets(); expect(eligibleCutoutMask(mask, source)).toBe(true);
    expect(eligibleCutoutMask({ ...mask, manual_mask: undefined }, source)).toBe(false);
    expect(eligibleCutoutMask(mask, { ...source, version: 3 })).toBe(false);
    expect(eligibleCutoutMask(mask, { ...source, sha256: 'e'.repeat(64) })).toBe(false);
    expect(eligibleCutoutMask({ ...mask, deleted_at: 'removed' }, source)).toBe(false);
    expect(eligibleCutoutMask({ ...mask, provenance: { ...mask.provenance!, stale: true } }, source)).toBe(false);
    expect(eligibleCutoutMask({ ...mask, manual_mask: { ...mask.manual_mask!, keep_pixels: 4096 } }, source)).toBe(false);
  });
  it('does not expose the standalone operation in the original Graph selector or decoder', async () => {
    expect(MEDIA_OPERATION_LABELS['m5.image.cutout']).toBeTruthy(); expect(Object.keys(GRAPH_MEDIA_OPERATION_LABELS)).toHaveLength(9);
    expect(Object.keys(GRAPH_MEDIA_OPERATION_LABELS)).not.toContain('m5.image.cutout');
    const json = vi.fn(), graph = createStudioGraphClient(cutoutProject, {}, { json });
    expect(() => graph.create({ request_id: 'graph_request', expected_version: 0, definition: { title: 'Cutout is not Graph', schema_version: 3, nodes: [{ id: 'generate', definition_id: 'media_generate', definition_version: 1,
      enabled: true, position: { x: 0, y: 0 }, parameters: { operation_id: 'm5.image.cutout' } }], edges: [], viewport: { x: 0, y: 0, zoom: 1 } } } as never)).toThrow();
    expect(json).not.toHaveBeenCalled();
  });
});

it('accepts cutout only as a nonexecuting standalone advisory contract', () => {
  const value = { schema_version: 1, contract: 'studio-production-operation-contracts/1', project_id: cutoutProject,
    scope: { mode: 'local', novel_id: cutoutProject }, studio_entry_kind: 'NEUTRAL_STUDIO', advisory_only: true, execution_authority: false,
    acceptance_sequence: ['M4', 'M5', 'M6', 'M7', 'M8', 'M9'], acceptance_evidence: 'NOT_EVALUATED_BY_THIS_ENDPOINT',
    interface_schemas: Object.fromEntries(STUDIO_PRODUCTION_INTERFACE_KEYS.map(key => [key, { type: 'object', additionalProperties: false, properties: {} }])),
    operations: [{ id: 'm5.image.cutout', milestone: 'M5', title: '本地抠图', capability_status: 'EXISTING_OWNER_CONTRACT',
      acceptance_status: 'LOCAL_REQUIRED', acceptance_evidence: 'NOT_EVALUATED_BY_THIS_ENDPOINT', execution_available: false,
      blocked_reasons: ['WINDOWS_PRODUCT_ACCEPTANCE_LOCAL_REQUIRED'], owner: { module: 'original', class_name: 'ImageJobService', methods: ['execute_studio'] },
      actions: [{ id: 'execute', method: 'POST', path: '/api/projects/{id}/studio/production/jobs/image/{job}/execute', permission: 'domain.write',
        input_schema: 'ProductionAction', owner_method: 'execute_studio', requires_original_host_session: true, execution_grant: false, conditions: ['Exact CAS'] }],
      input_requirements: [], source_requirements: [], output_requirements: [], review_requirements: [], limitations: [], interface_contracts: STUDIO_PRODUCTION_INTERFACE_REFERENCES }] };
  expect(studioProductionContracts(value, cutoutProject).operations[0].id).toBe('m5.image.cutout');
  value.operations[0].actions[0].path = '/api/projects/{id}/studio/graphs/{graph}/execute';
  expect(() => studioProductionContracts(value, cutoutProject)).toThrow();
});
