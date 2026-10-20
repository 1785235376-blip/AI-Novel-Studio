import { describe, expect, it, vi } from 'vitest';
import { ApiError } from '../api';
import { createStudioGraphClient } from './studioGraphClient';
import { providerCatalog, taskMatch, taskRequirement } from './studioProvider.testFixtures';

function setup(value: unknown, scope?: { projectId: string; workspaceId: string; storylineId: string; branchId: string }) {
  const json = vi.fn().mockResolvedValue(value), client = createStudioGraphClient('model_project', { scope }, { json }); return { json, client };
}
describe('advisory provider contract transport', () => {
  it('reads only on explicit request and uses the original scoped transport', async () => {
    const raw = providerCatalog(), { client, json } = setup(raw), signal = new AbortController().signal;
    expect(json).not.toHaveBeenCalled(); expect(await client.providerContracts(signal)).toEqual(raw);
    expect(json).toHaveBeenCalledWith('/api/projects/model_project/studio/graphs/provider-contracts', 'GET', undefined, signal);
  });
  it('sends only a bounded requirement and never a dispatch or an idempotent mutation', async () => {
    const requirement = taskRequirement({ preferred_route: 'd'.repeat(64), min_host_ram_mib: 8000, min_host_vram_mib: 4000 }), raw = taskMatch(requirement);
    const { client, json } = setup(raw); expect(await client.modelMatch(requirement)).toEqual(raw);
    expect(json.mock.calls).toEqual([['/api/projects/model_project/studio/graphs/model-match', 'POST', requirement, undefined]]);
  });
  it.each([
    (x: any) => { x.schema_version = 2; }, (x: any) => { x.contract = 'future/2'; },
    (x: any) => { x.advisory_only = false; }, (x: any) => { x.dispatch_authorized = true; },
    (x: any) => { x.automatic_fallback = true; }, (x: any) => { x.quality_verification = 'PASSED'; },
    (x: any) => { x.execution_available = true; }, (x: any) => { x.future_execution = { enabled: true }; },
    (x: any) => { x.task_types.push('AUDIO_GENERATION'); }, (x: any) => { x.providers.pop(); },
    (x: any) => { x.providers[0].availability.execution_available = true; },
    (x: any) => { x.providers[0].availability.execution_authority = 'PROVIDER'; },
    (x: any) => { x.providers[0].capability.verified.push('IMAGE_GENERATION'); },
    (x: any) => { x.providers[0].capability.inference_verification = 'PASSED'; },
    (x: any) => { x.providers[0].registered_routes = []; },
    (x: any) => { x.providers[1].availability.adapter_available = true; },
    (x: any) => { x.providers[2].capability.advertised = ['TEXT_GENERATION']; },
    (x: any) => { x.providers[4].availability.status = 'REGISTERED'; },
    (x: any) => { x.providers[0].availability.reasons = ['UNAVAILABLE']; },
    (x: any) => { x.providers[0].secret = 'private'; },
  ])('rejects malformed HTTP-200 catalogs and unknown authority claims %j', async mutate => {
    const raw = providerCatalog(); mutate(raw); const { client } = setup(raw);
    await expect(client.providerContracts()).rejects.toMatchObject({ problem: { status: 200, code: 'STUDIO_RESPONSE_INVALID' } });
  });
  it.each([
    (x: any) => { x.project_id = 'other'; }, (x: any) => { x.scope.novel_id = 'other'; },
    (x: any) => { x.scope.mode = 'collaboration'; }, (x: any) => { x.scope.branch_id = 'foreign'; },
  ])('rejects owner mismatches for catalog and matching %j', async mutate => {
    for (const raw of [providerCatalog(), taskMatch()]) {
      mutate(raw); const { client } = setup(raw);
      await expect('providers' in raw ? client.providerContracts() : client.modelMatch(taskRequirement())).rejects.toMatchObject({ problem: { status: 403, code: 'STUDIO_RESPONSE_SCOPE_MISMATCH' } });
    }
  });
  it('captures collaboration scope and rejects another branch even after caller mutation', async () => {
    const scope = { projectId: 'model_project', workspaceId: 'w', storylineId: 's', branchId: 'b' };
    const raw = { ...providerCatalog(), scope: { mode: 'collaboration', novel_id: 'model_project', workspace_id: 'w', storyline_id: 's', branch_id: 'b' } };
    const { client, json } = setup(raw, scope); scope.branchId = 'other'; expect((await client.providerContracts()).scope).toEqual(raw.scope);
    json.mockResolvedValue({ ...raw, scope: { ...raw.scope, branch_id: 'other' } }); await expect(client.providerContracts()).rejects.toBeInstanceOf(ApiError);
  });
  it.each([
    { min_host_ram_mib: 0 }, { min_host_ram_mib: -1 }, { min_host_vram_mib: 1.5 }, { min_host_vram_mib: 10000001 },
    { min_host_ram_mib: '1000' }, { min_host_ram_mib: true }, { min_host_vram_mib: Infinity },
    { task_type: 'AUDIO_GENERATION' }, { preferred_route: 'guessed' }, { allow_synthetic: 'true' },
    { local_only: false }, { api_available: true }, { dispatch_authorized: true },
  ])('rejects invalid inputs before sending %j', patch => {
    const { client, json } = setup(taskMatch()); expect(() => client.modelMatch({ ...taskRequirement(), ...patch } as never)).toThrow(ApiError); expect(json).not.toHaveBeenCalled();
  });
  it.each([
    (x: any) => { x.requirement.allow_synthetic = true; }, (x: any) => { x.requirement.preferred_route = 'e'.repeat(64); },
    (x: any) => { x.api_provider.execution_available = true; }, (x: any) => { x.api_provider.status = 'AVAILABLE'; },
    (x: any) => { x.hardware.free_memory = 8000; }, (x: any) => { x.hardware.state = 'GPU_VERIFIED'; },
    (x: any) => { x.hardware.ram_mib = '16384'; }, (x: any) => { x.hardware.warning = 'Guaranteed fit'; },
    (x: any) => { x.matches[0].hardware_state = 'TOTAL_CAPACITY_ONLY'; },
    (x: any) => { x.matches[0].execution_authority = true; }, (x: any) => { x.matches[0].automatic_fallback = true; },
    (x: any) => { x.matches[0].gpu_fit_verified = true; }, (x: any) => { x.matches[0].api_available = true; },
    (x: any) => { x.matches[0].execution_available = true; }, (x: any) => { x.matches[0].preferred = true; },
    (x: any) => { x.matches[0].synthetic = true; }, (x: any) => { x.matches[0].reasons = ['UNAVAILABLE']; },
    (x: any) => { x.matches[0].route_id = 'guessed'; }, (x: any) => { x.matches.push(x.matches[0]); },
  ])('rejects malformed or unrequested positive match projections %j', async mutate => {
    const raw = taskMatch(); mutate(raw); const { client } = setup(raw); await expect(client.modelMatch(taskRequirement())).rejects.toMatchObject({ problem: { status: 200, code: 'STUDIO_RESPONSE_INVALID' } });
  });
  it.each(['IMAGE_GENERATION', 'VIDEO_GENERATION'] as const)('retains reserved modality explanations for %s and rejects eligible claims', async task_type => {
    const requirement = taskRequirement({ task_type }), raw = taskMatch(requirement), { client, json } = setup(raw);
    expect((await client.modelMatch(requirement)).matches[0].eligible).toBe(false);
    raw.matches[0].eligible = true; raw.matches[0].reasons = []; json.mockResolvedValue(raw); await expect(client.modelMatch(requirement)).rejects.toBeInstanceOf(ApiError);
  });
  it('accepts unknown capacity only as ineligible when memory was requested', async () => {
    const requirement = taskRequirement({ min_host_ram_mib: 1000 }), raw = taskMatch(requirement);
    raw.hardware = { state: 'UNAVAILABLE', ram_mib: null, vram_mib: null, free_memory: null };
    Object.assign(raw.matches[0], { eligible: false, reasons: ['HOST_RAM_UNKNOWN'], hardware_state: 'UNKNOWN' });
    const { client } = setup(raw); expect(await client.modelMatch(requirement)).toEqual(raw);
    raw.matches[0].eligible = true; raw.matches[0].reasons = []; await expect(client.modelMatch(requirement)).rejects.toBeInstanceOf(ApiError);
  });
});
