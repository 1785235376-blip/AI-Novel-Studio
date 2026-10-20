// @vitest-environment jsdom
// Focused modern-path migration variant; the protected legacy scenario remains unchanged.
// This preserves an alternate fixture/control path and is not a new unique scenario.
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { webcrypto } from 'node:crypto';
import { Blob as NodeBlob } from 'node:buffer';
import { useStudio } from '../store';
import { useLocalHostSession } from '../localHostSession';
import { IndependentStudioWorkspace } from './IndependentStudioWorkspace';
import type { StudioAsset, StudioOverview } from './studioClient';
import type { MediaCommand, MediaOperation, ProductionJob, ProductionPreview, ProductionProvider, ProductionRecipe } from './studioProductionClient';
import { cutoutAssets, cutoutBytes, cutoutHash, cutoutProject } from './studioCpuCutout.testFixtures';
import { mediaProviderKey } from './useStudioMediaExecution';

// Mounted HTTP fixtures exercise original controller/Host/client/review fences.
// These are not ComfyUI, model inference, GPU or final Windows evidence.
const project = cutoutProject, base = `/api/projects/${project}/studio`, production = `${base}/production`, jobId = 'image-runtime-job';
const sha = 'a'.repeat(64), deferred = <T,>() => { let resolve!: (value: T) => void; const promise = new Promise<T>(yes => { resolve = yes; }); return { promise, resolve }; };
let rows: StudioAsset[], providers: ProductionProvider[], currentJob: ProductionJob | undefined, fetcher: ReturnType<typeof vi.fn>, media: Blob;
let previewResponse: ReturnType<typeof deferred<ReturnType<typeof reply>>> | undefined;
let createResponse: ReturnType<typeof deferred<ReturnType<typeof reply>>> | undefined;
const reply = (value: unknown, status = 200) => ({ ok: status < 400, status, json: async () => value, blob: async () => media });
const provider = (operation_id: MediaOperation, local = true, reference_limit = 5): ProductionProvider => ({ operation_id, provider_id: 'image-provider', model_id: 'image-model', local,
  route_digest: sha, capability: 'IMAGE', readiness: 'CONFIGURED_NOT_VERIFIED', supported_parameters: ['steps', 'seed', 'negative_prompt', 'denoising_strength'],
  image_capabilities: { recipe_id: 'comfy-flux1-v1', reference_limit, reference_semantics: 'WEIGHTED_PIXEL_INITIALIZATION',
    mask_semantics: operation_id === 'm5.image.inpaint' ? 'WHITE_KEEP_BLACK_REPAINT' : null, structural_only: true, inference_verified: false } });
function recipe(command: MediaCommand): ProductionRecipe {
  return { contract: 'studio-execution-recipe/1', operation_id: command.operation_id, adapter: 'COMFYUI_BUILTIN_IMAGE',
    parameters: command.parameters, workflow: { fixture: 'bounded-original-owner-workflow' }, automatic_fallback: false, recipe_digest: 'b'.repeat(64),
    image_recipe_id: 'comfy-flux1-v1', reference_weights: [...(command.image_source ? [1] : []), ...(command.image_references?.map(row => row.weight) || [])],
    reference_semantics: 'WEIGHTED_PIXEL_INITIALIZATION', mask_semantics: command.mask_source ? 'WHITE_KEEP_BLACK_REPAINT' : null };
}
function preview(command: MediaCommand): ProductionPreview {
  return { contract: 'studio-production-preview/1', novel_id: project, branch_id: null, operation_id: command.operation_id, request_id: command.request_id,
    command, provider: { provider_id: 'image-provider', model_id: 'image-model', local: providers.find(row => row.operation_id === command.operation_id)!.local, route_digest: sha },
    sources: command.source_snapshots.map(snapshot => ({ snapshot, measured: { media_type: 'image/png', width: 64, height: 64 } })),
    execution_recipe: recipe(command), preview_digest: 'c'.repeat(64), request_digest: 'd'.repeat(64), product_acceptance: 'LOCAL_REQUIRED',
    execution_available: true, automatic_dispatch: false, output_policy: 'PRIVATE_CANDIDATE_THEN_EXPLICIT_REVIEW' };
}
function job(command: MediaCommand, status: ProductionJob['status'] = 'QUEUED', version = 1): ProductionJob {
  const ready = status === 'AWAITING_REVIEW' || status === 'APPROVED';
  return { contract: 'studio-production-job/1', owner: 'image', id: jobId, novel_id: project, branch_id: null, version, operation_id: command.operation_id,
    request_id: command.request_id, status, request_digest: 'd'.repeat(64), receipt_digest: ready ? 'e'.repeat(64) : null,
    output_candidate: ready ? { id: 'image-runtime-candidate', version: 1, digest: cutoutHash, kind: 'image' } : null,
    product_acceptance: 'LOCAL_REQUIRED', automatic_replay: false, remote_compute_may_continue: false, timeline_snapshot: null,
    sources: command.source_snapshots, command, provider: preview(command).provider, execution_recipe: recipe(command), approved_asset_version: status === 'APPROVED' ? 2 : null,
    created_at: '', updated_at: '' };
}
beforeEach(() => {
  localStorage.clear(); vi.stubGlobal('crypto', webcrypto);
  Object.defineProperty(URL, 'createObjectURL', { configurable: true, value: vi.fn(() => 'blob:private-image-runtime') });
  Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: vi.fn() });
  media = new NodeBlob([cutoutBytes], { type: 'image/png' }) as unknown as Blob;
  rows = cutoutAssets(); rows.push({ ...rows[0], id: 'second', filename: 'second.png', sha256: 'f'.repeat(64), version: 3, manual_mask: undefined });
  providers = ['m5.image.i2i', 'm5.image.reference', 'm5.image.inpaint'].map(operation => provider(operation as MediaOperation));
  currentJob = undefined; previewResponse = undefined; createResponse = undefined;
  useStudio.setState({ novelId: project, sessionToken: '', actor: undefined, scope: undefined }); useLocalHostSession.setState({ token: 'image-runtime-host', actorId: '' });
  const overview: StudioOverview = { project: { id: project, title: 'Image runtime fixture', entry_kind: 'NEUTRAL_STUDIO' },
    preferences: { version: 1, intents: [], preset: 'IMAGE', custom_intent: '' }, capabilities: { can_mutate: true, can_review: true,
      manual_import: true, manual_export: true, chapter_required: false, model_required: false, media_validator_configured: true, asset_kinds: ['image', 'video', 'audio'], intent_is_permission: false } };
  fetcher = vi.fn(async (url: string, init?: RequestInit) => {
    if (url === base) return reply(overview);
    if (url.includes('/assets?')) return reply({ items: rows });
    if (url === `${base}/production-contracts`) return reply({ code: 'FIXTURE_CATALOG_UNAVAILABLE' }, 400);
    if (url === `${production}/providers`) return reply({ items: providers, health_probed: false, credentials_read: false });
    if (url === `${production}/timelines`) return reply({ items: [] });
    if (url === `${production}/preview`) return previewResponse?.promise ?? reply(preview(JSON.parse(init!.body as string)));
    if (url === `${production}/jobs`) {
      if (init?.method === 'POST') { currentJob = job(JSON.parse(init.body as string).command); return createResponse?.promise ?? reply(currentJob); }
      return reply({ items: currentJob ? [currentJob] : [] });
    }
    if (url === `${production}/jobs/image/${jobId}`) return reply(currentJob);
    if (url.endsWith(`/${jobId}/execute`)) { currentJob = job(currentJob!.command as MediaCommand, 'AWAITING_REVIEW', 3); return reply(currentJob); }
    if (url.endsWith(`/${jobId}/candidate`)) return reply({});
    if (url.endsWith(`/${jobId}/review`)) { currentJob = job(currentJob!.command as MediaCommand, 'APPROVED', currentJob!.version + 1); return reply(currentJob); }
    throw new Error(`Unexpected fixture request: ${url}`);
  }); vi.stubGlobal('fetch', fetcher);
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });
function mount() {
  const query = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={query}><IndependentStudioWorkspace projectId={project} context={{ sessionToken: '' }}
    scope={{ workspace: '本机', project: 'Image runtime fixture', storyline: '默认', branch: '主线' }} actor="作者" module="IMAGE"
    onModuleChange={vi.fn()} onProjectChoice={vi.fn()} /></QueryClientProvider>);
}
const button = (name: string) => screen.getByRole('button', { name }) as HTMLButtonElement;
const change = (name: string, value: string) => fireEvent.change(screen.getByLabelText(name), { target: { value } });
const calls = (suffix: string) => fetcher.mock.calls.filter(([url]) => url.endsWith(suffix));
async function choose(operation: MediaOperation) {
  fireEvent.click(await screen.findByRole('button', { name: '制作操作' })); await waitFor(() => expect((screen.getByLabelText('操作') as HTMLSelectElement).disabled).toBe(false));
  change('操作', operation); await screen.findByRole('option', { name: 'image-provider · image-model · 本地' }).catch(() => undefined);
  if (!providers.find(row => row.operation_id === operation)!.local) change('制作路线', 'cloud');
  change('服务商与模型', mediaProviderKey(providers.find(row => row.operation_id === operation)!)); change('本次提示词', 'Image fixture prompt');
}
async function reference() { await choose('m5.image.reference'); fireEvent.click(screen.getByLabelText('参考 source.png · v2')); fireEvent.click(screen.getByLabelText('参考 second.png · v3'));
  change('参考权重 · source.png · v2', '0.25'); change('参考权重 · second.png · v3', '0.75'); }

describe('image runtime source roles through the mounted original workspace', () => {
  it("migration: requires fresh cloud consent after reference weights change and never falls back or sends automatically", async () => {
    providers[1] = provider('m5.image.reference', false); mount(); await reference();
    const cloud = screen.getByLabelText(/确认本次允许将提示词及选中的参考素材/) as HTMLInputElement;
    expect(button('读取制作预览').disabled).toBe(true); fireEvent.click(cloud); expect(button('读取制作预览').disabled).toBe(false);
    change('参考权重 · source.png · v2', '0.5'); expect(cloud.checked).toBe(false); expect(button('读取制作预览').disabled).toBe(true); expect(calls('/preview')).toHaveLength(0);
  });
});
