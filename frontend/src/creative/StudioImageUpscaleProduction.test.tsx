// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { StudioMediaExecutionPanel } from './StudioMediaExecutionPanel';
import { studioProductionClient, type MediaCommand, type ProductionProvider, type ProductionPreview } from './studioProductionClient';
import { mediaProviderKey } from './useStudioMediaExecution';
import { cutoutAssets } from './studioCpuCutout.testFixtures';
const project = 'synthetic-upscale', digest = 'a'.repeat(64), source = cutoutAssets()[0];
const provider: ProductionProvider = { operation_id: 'm5.image.upscale', provider_id: 'enabled-comfy', model_id: 'installed-upscaler', local: true, route_digest: digest,
  capability: 'IMAGE', supported_parameters: ['scale'], readiness: 'CONFIGURED_NOT_VERIFIED', image_capabilities: { recipe_id: 'comfy-upscale-model-v1', reference_limit: 1,
    reference_semantics: 'SINGLE_IMAGE_INITIALIZATION', mask_semantics: null, structural_only: true, inference_verified: false,
    upscaling: { scales: [2, 4], output_format: 'PNG', output_size_limit: 4096, output_pixel_limit: 16777216 } } };
const reply = (value: unknown) => ({ ok: true, status: 200, json: async () => value });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
function preview(command: MediaCommand): ProductionPreview { return { contract: 'studio-production-preview/1', novel_id: project, branch_id: null, request_id: command.request_id, operation_id: command.operation_id,
  preview_digest: digest, request_digest: digest, command, provider: { provider_id: provider.provider_id, model_id: provider.model_id, local: true, route_digest: digest },
  sources: command.source_snapshots.map(snapshot => ({ snapshot, measured: { width: 64, height: 64, media_type: 'image/png' } })), execution_recipe: { contract: 'studio-execution-recipe/1', operation_id: command.operation_id,
    adapter: 'COMFYUI_BUILTIN_IMAGE', recipe_digest: digest, automatic_fallback: false, parameters: command.parameters, workflow: {}, image_recipe_id: 'comfy-upscale-model-v1', reference_weights: [1],
    reference_semantics: 'SINGLE_IMAGE_INITIALIZATION', mask_semantics: null, source_dimensions: { width: 64, height: 64 }, target_dimensions: { width: 64 * Number(command.parameters.scale), height: 64 * Number(command.parameters.scale) } },
  product_acceptance: 'LOCAL_REQUIRED', execution_available: true, automatic_dispatch: false, output_policy: 'PRIVATE_CANDIDATE_THEN_EXPLICIT_REVIEW' }; }
describe('Standalone upscale over original task and controller', () => {
  it('requires an enabled route, exact source and explicit scale before preview; no prompt or automatic task', async () => {
    const fetcher = vi.fn(async (url: string, init: RequestInit) => {
      if (url.endsWith('/providers')) return reply({ items: [provider], health_probed: false, credentials_read: false });
      if (url.endsWith('/preview')) return reply(preview(JSON.parse(String(init.body)))); throw new Error(`Unexpected request ${url}`);
    }); vi.stubGlobal('fetch', fetcher); const client = studioProductionClient(project, { sessionToken: 'synthetic-unit-context' });
    render(<StudioMediaExecutionPanel client={client} assets={[source]} canMutate canReview busy={false} isCurrent={() => true} read={work => work()} mutate={work => work()} onDirtyChange={vi.fn()} onUnavailable={vi.fn()} />);
    fireEvent.change(screen.getByLabelText('操作'), { target: { value: 'm5.image.upscale' } }); await screen.findByRole('option', { name: /enabled-comfy/ });
    fireEvent.change(screen.getByLabelText('服务商与模型'), { target: { value: mediaProviderKey(provider) } });
    fireEvent.click(screen.getByLabelText(`${source.filename} · v${source.version}`));
    expect(screen.queryByLabelText('本次提示词')).toBeNull(); expect((screen.getByRole('button', { name: '读取制作预览' }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.change(screen.getByLabelText('超分倍率'), { target: { value: '2' } }); fireEvent.click(screen.getByRole('button', { name: '读取制作预览' }));
    await waitFor(() => expect(fetcher.mock.calls.some(([url]) => url.endsWith('/preview'))).toBe(true));
    const body = JSON.parse(String(fetcher.mock.calls.find(([url]) => url.endsWith('/preview'))![1].body));
    expect(body).toMatchObject({ operation_id: 'm5.image.upscale', prompt: '', parameters: { scale: 2 }, allow_cloud: false, image_source: { id: source.id, version: source.version, digest: source.sha256 } });
    expect(body.source_snapshots).toHaveLength(1); expect(body.image_references).toBeUndefined();
    expect(fetcher.mock.calls.every(([url]) => !url.includes('/jobs'))).toBe(true);
  });
  it('rejects malformed scale/source commands before sending', async () => {
    const fetcher = vi.fn(); vi.stubGlobal('fetch', fetcher); const client = studioProductionClient(project, { sessionToken: 'synthetic-unit-context' });
    const snapshot = { id: source.id, version: source.version, digest: source.sha256, kind: 'ASSET' as const, asset_kind: 'image' as const };
    const command: MediaCommand = { operation_id: 'm5.image.upscale', request_id: 'unit-upscale', provider_id: provider.provider_id, model_id: provider.model_id, prompt: '', parameters: { scale: '2' }, source_snapshots: [snapshot], image_source: snapshot, allow_cloud: false, license_note: '' };
    await expect(client.preview(command)).rejects.toBeTruthy(); await expect(client.preview({ ...command, parameters: { scale: 2 }, prompt: 'unused prompt' })).rejects.toBeTruthy(); expect(fetcher).not.toHaveBeenCalled();
  });
});
