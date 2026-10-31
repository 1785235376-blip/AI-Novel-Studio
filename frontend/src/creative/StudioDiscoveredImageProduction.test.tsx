// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { webcrypto } from 'node:crypto';
import { Blob as NodeBlob } from 'node:buffer';
import { useStudio } from '../store';
import { bindLocalHostSession, useLocalHostSession } from '../localHostSession';
import { IndependentStudioWorkspace } from './IndependentStudioWorkspace';
import type { StudioOverview } from './studioClient';
import type { CollaborationContext } from '../api';
import type { MediaCommand, ProductionJob, ProductionPreview, ProductionProvider, ProductionRecipe } from './studioProductionClient';
import { cutoutBytes, cutoutHash } from './studioCpuCutout.testFixtures';
import { mediaProviderKey } from './useStudioMediaExecution';

// HTTP fixtures verify the mounted controller/client boundary, not ComfyUI,
// native decoding, Windows playback, GPU inference or product acceptance.
// Reuse original bounded real PNG bytes only for private candidate SHA checks.
const project = 'discovered-image-project', base = `/api/projects/${project}/studio`, production = `${base}/production`;
const modelId = 'local-comfyui-candidate-1', providerId = `discovery-${modelId}`, jobId = 'discovered-image-job';
const routeDigest = 'a'.repeat(64), requestDigest = 'b'.repeat(64), previewDigest = 'c'.repeat(64);
const deferred = <T,>() => { let resolve!: (value: T) => void; const promise = new Promise<T>(yes => { resolve = yes; }); return { promise, resolve }; };
const reply = (value: unknown, status = 200) => ({ ok: status < 400, status, json: async () => value, blob: async () => media });
const provider = (digest = routeDigest): ProductionProvider => ({ operation_id: 'm5.image.t2i', provider_id: providerId,
  model_id: modelId, local: true, route_digest: digest, capability: 'TEXT_TO_IMAGE',
  supported_parameters: ['width', 'height', 'steps', 'seed', 'negative_prompt'], readiness: 'CONFIGURED_NOT_VERIFIED' });
const route = (command: MediaCommand) => ({ provider_id: command.provider_id!, model_id: command.model_id!, local: true, route_digest: routeDigest });
const recipe = (command: MediaCommand): ProductionRecipe => ({ contract: 'studio-execution-recipe/1', operation_id: command.operation_id,
  adapter: 'COMFYUI_BUILTIN_IMAGE', parameters: { ...command.parameters }, workflow: { fixture: 'original-comfyui-owner-recipe' },
  automatic_fallback: false, recipe_digest: 'd'.repeat(64) });
const preview = (command: MediaCommand): ProductionPreview => ({ contract: 'studio-production-preview/1', novel_id: project, branch_id: null,
  operation_id: command.operation_id, request_id: command.request_id, command, preview_digest: previewDigest, request_digest: requestDigest,
  sources: [], provider: route(command), execution_recipe: recipe(command), product_acceptance: 'LOCAL_REQUIRED', execution_available: true,
  automatic_dispatch: false, output_policy: 'PRIVATE_CANDIDATE_THEN_EXPLICIT_REVIEW' });
function job(command: MediaCommand, status: ProductionJob['status'] = 'QUEUED', version = 1): ProductionJob {
  const rendered = status === 'AWAITING_REVIEW' || status === 'APPROVED';
  return { contract: 'studio-production-job/1', owner: 'image', id: jobId, novel_id: project, branch_id: null, version, operation_id: command.operation_id,
    request_id: command.request_id, status, request_digest: requestDigest, receipt_digest: rendered ? 'e'.repeat(64) : null,
    output_candidate: rendered ? { id: 'discovered-image-candidate', version: 1, digest: cutoutHash, kind: 'image' } : null,
    product_acceptance: 'LOCAL_REQUIRED', automatic_replay: false, remote_compute_may_continue: false, timeline_snapshot: null,
    sources: [], command, provider: route(command), execution_recipe: recipe(command), approved_asset_version: status === 'APPROVED' ? 2 : null,
    created_at: '', updated_at: '' };
}
const overview = (): StudioOverview => ({ project: { id: project, title: 'Discovered Image fixture', entry_kind: 'NEUTRAL_STUDIO' },
  preferences: { version: 1, intents: [], preset: 'IMAGE', custom_intent: '' }, capabilities: { can_mutate: true, can_review: true,
    manual_import: true, manual_export: true, chapter_required: false, model_required: false, media_validator_configured: true,
    asset_kinds: ['image', 'video', 'audio'], intent_is_permission: false } });
let media: Blob, providers: ProductionProvider[], currentJob: ProductionJob | undefined;
let fetcher: ReturnType<typeof vi.fn>, context: CollaborationContext;
let providerResponse: ReturnType<typeof deferred<ReturnType<typeof reply>>> | undefined;
let createResponse: ReturnType<typeof deferred<ReturnType<typeof reply>>> | undefined;
beforeEach(() => {
  localStorage.clear(); vi.stubGlobal('crypto', webcrypto);
  Object.defineProperty(URL, 'createObjectURL', { configurable: true, value: vi.fn(() => 'blob:private-discovered-image') });
  Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: vi.fn() });
  media = new NodeBlob([cutoutBytes], { type: 'image/png' }) as unknown as Blob;
  providers = [provider()]; currentJob = undefined; providerResponse = undefined; createResponse = undefined;
  context = { sessionToken: '' }; useStudio.setState({ novelId: project, sessionToken: '', actor: undefined, scope: undefined });
  useLocalHostSession.setState({ token: 'discovered-image-host', actorId: '' });
  fetcher = vi.fn(async (url: string, init?: RequestInit) => {
    if (url === base) return reply(overview());
    if (url.includes('/assets?')) return reply({ items: [] });
    if (url === `${base}/production-contracts`) return reply({ code: 'FIXTURE_CATALOG_UNAVAILABLE' }, 400);
    if (url === `${production}/providers`) return providerResponse?.promise ?? reply({ items: providers, health_probed: false, credentials_read: false });
    if (url === `${production}/timelines`) return reply({ items: [] });
    if (url === `${production}/preview`) return reply(preview(JSON.parse(init!.body as string)));
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
  const leave = vi.fn(), query = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  const node = () => <QueryClientProvider client={query}><IndependentStudioWorkspace projectId={project} context={context}
    scope={{ workspace: '本机', project: 'Discovered Image fixture', storyline: '默认', branch: '主线' }} actor="作者" module="IMAGE"
    onModuleChange={leave} onProjectChoice={leave} /></QueryClientProvider>;
  return { ...render(node()), leave, node };
}
function button(name: string) { return screen.getByRole('button', { name }) as HTMLButtonElement; }
function calls(suffix: string) { return fetcher.mock.calls.filter(([url]) => url.endsWith(suffix)); }
function mutations() { return fetcher.mock.calls.filter(([, init]) => init?.method === 'POST'); }
function change(name: string, value: string) { fireEvent.change(screen.getByLabelText(name), { target: { value } }); }
async function open() {
  fireEvent.click(await screen.findByRole('button', { name: '制作操作' }));
  await waitFor(() => expect((screen.getByLabelText('操作') as HTMLSelectElement).disabled).toBe(false));
}
async function choose() {
  await open(); await screen.findByRole('option', { name: `${providerId} · ${modelId} · 本地` });
  change('服务商与模型', mediaProviderKey(provider())); change('本次提示词', 'Independent local image fixture');
  change('种子（0–2147483647）', '42');
}
async function readPreview() { await choose(); fireEvent.click(button('读取制作预览')); await screen.findByRole('region', { name: '制作预览确认' }); }
async function queue() { await readPreview(); fireEvent.click(screen.getByLabelText('已核对本次输入、来源和处理边界')); fireEvent.click(button('仅创建任务并入队')); await screen.findByText('任务已保存入队。执行仍需单独点击。'); }
async function candidate() { await queue(); fireEvent.click(button('明确执行当前入队任务')); await waitFor(() => expect(button('读取并核对候选媒体').disabled).toBe(false)); fireEvent.click(button('读取并核对候选媒体')); await screen.findByAltText('本任务经摘要核对的图片候选'); }

describe('discovered Image routes through the original mounted production workspace', () => {
  it('consumes exact passive discovered IDs without selecting, probing or dispatching automatically', async () => {
    mount(); await open(); const option = await screen.findByRole('option', { name: `${providerId} · ${modelId} · 本地` });
    expect((option as HTMLOptionElement).value).toBe(mediaProviderKey(provider()));
    expect((screen.getByLabelText('服务商与模型') as HTMLSelectElement).value).toBe('');
    expect(screen.getByText(/配置参考不代表服务已验证可用/)).toBeTruthy();
    expect(button('读取制作预览').disabled).toBe(true);
    expect(mutations()).toHaveLength(0); expect(calls('/providers')).toHaveLength(1);
    expect(fetcher.mock.calls.some(([url]) => /model-center|scan|system_stats|object_info|runtimes/.test(url))).toBe(false);
    expect(URL.createObjectURL).not.toHaveBeenCalled();
  });
  it('preserves explicit preview, queue, execute, byte verification and review for the discovered route', async () => {
    mount(); await readPreview(); const command = JSON.parse(calls('/preview')[0][1]!.body as string) as MediaCommand;
    expect(command).toEqual({ operation_id: 'm5.image.t2i', request_id: command.request_id, provider_id: providerId, model_id: modelId,
      prompt: 'Independent local image fixture', parameters: { seed: 42 }, source_snapshots: [], allow_cloud: false, license_note: '' });
    expect(calls('/jobs')).toHaveLength(0); expect(calls('/execute')).toHaveLength(0);
    expect(screen.queryByLabelText(/确认本次允许将提示词/)).toBeNull(); expect(button('仅创建任务并入队').disabled).toBe(true);
    fireEvent.click(screen.getByLabelText('已核对本次输入、来源和处理边界')); fireEvent.click(button('仅创建任务并入队'));
    await screen.findByText('任务已保存入队。执行仍需单独点击。');
    expect(JSON.parse(calls('/jobs')[0][1]!.body as string)).toEqual({ command, reviewed_preview_digest: previewDigest });
    expect(calls('/execute')).toHaveLength(0); expect(URL.createObjectURL).not.toHaveBeenCalled();
    fireEvent.click(button('明确执行当前入队任务')); await waitFor(() => expect(button('读取并核对候选媒体').disabled).toBe(false));
    expect(JSON.parse(calls('/execute')[0][1]!.body as string)).toEqual({ expected_version: 1, expected_request_digest: requestDigest });
    expect(calls('/review')).toHaveLength(0); expect(URL.createObjectURL).not.toHaveBeenCalled();
    fireEvent.click(button('读取并核对候选媒体')); await screen.findByAltText('本任务经摘要核对的图片候选');
    expect(button('明确审核并入素材库').disabled).toBe(true);
    fireEvent.click(screen.getByLabelText('已查看本次候选，确认采用当前任务版本与输出摘要')); fireEvent.click(button('明确审核并入素材库'));
    await screen.findByText('原任务已审核入库。产品里程碑验收状态仍为 LOCAL_REQUIRED。');
    expect(JSON.parse(calls('/review')[0][1]!.body as string)).toEqual({ expected_version: 3, expected_request_digest: requestDigest, reviewed_output_digest: cutoutHash });
    expect(calls('/execute')).toHaveLength(1); expect(calls('/review')).toHaveLength(1);
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:private-discovered-image');
  });
  it('does not expose the T2I-only discovered route as I2I or fall back to a different operation', async () => {
    mount(); await choose(); change('操作', 'm5.image.i2i');
    expect(screen.queryByRole('option', { name: `${providerId} · ${modelId} · 本地` })).toBeNull();
    expect((screen.getByLabelText('服务商与模型') as HTMLSelectElement).value).toBe('');
    expect(button('读取制作预览').disabled).toBe(true); expect(mutations()).toHaveLength(0);
  });
  it('invalidates prior route consent when a fresh passive list has a different route digest', async () => {
    mount(); await readPreview(); fireEvent.click(screen.getByLabelText('已核对本次输入、来源和处理边界'));
    providers = [provider('f'.repeat(64))]; fireEvent.click(button('重新读取配置'));
    await waitFor(() => expect(calls('/providers')).toHaveLength(2));
    await waitFor(() => expect(screen.queryByRole('region', { name: '制作预览确认' })).toBeNull());
    expect(screen.queryByRole('button', { name: '仅创建任务并入队' })).toBeNull();
    expect(calls('/jobs')).toHaveLength(0); expect(calls('/execute')).toHaveLength(0);
  });
  it('recovers a lost create using the exact original discovered request without replay', async () => {
    mount(); await readPreview(); createResponse = deferred(); fireEvent.click(screen.getByLabelText('已核对本次输入、来源和处理边界'));
    fireEvent.click(button('仅创建任务并入队')); await waitFor(() => expect(calls('/jobs')).toHaveLength(1));
    const original = JSON.parse(calls('/jobs')[0][1]!.body as string).command as MediaCommand;
    await act(async () => createResponse!.resolve(reply({ code: 'UNKNOWN' }, 503)));
    expect(screen.getByText(/操作结果尚未确认/)).toBeTruthy(); fireEvent.click(button('读取任务列表'));
    await screen.findByText('已找到原请求的保存记录；不会重新创建或执行。');
    expect(currentJob!.request_id).toBe(original.request_id); expect(currentJob!.provider).toEqual(route(original));
    expect(calls('/jobs').filter(([, init]) => init?.method === 'POST')).toHaveLength(1);
    expect(calls('/execute')).toHaveLength(0); expect(calls('/review')).toHaveLength(0);
  });
  it.each(['host-rebind', 'project-aba'] as const)('redacts candidate bytes and review consent after %s', async identity => {
    mount(); await candidate(); fireEvent.click(screen.getByLabelText('已查看本次候选，确认采用当前任务版本与输出摘要'));
    act(() => {
      if (identity === 'host-rebind') bindLocalHostSession('discovered-image-host', { session_mode: 'LOCAL_HOST', actor_id: 'replacement-author' });
      else { useStudio.setState({ novelId: 'other-project' }); useStudio.setState({ novelId: project }); }
    });
    expect(screen.queryByAltText('本任务经摘要核对的图片候选')).toBeNull();
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:private-discovered-image'); expect(calls('/review')).toHaveLength(0);
  });
  it('ignores a provider list arriving after same-token Host replacement without dispatch', async () => {
    providerResponse = deferred(); const view = mount(); await open(); await waitFor(() => expect(calls('/providers')).toHaveLength(1));
    act(() => bindLocalHostSession('discovered-image-host', { session_mode: 'LOCAL_HOST', actor_id: 'replacement-author' }));
    await act(async () => providerResponse!.resolve(reply({ items: [provider()], health_probed: false, credentials_read: false })));
    view.rerender(view.node()); expect(screen.queryByRole('option', { name: `${providerId} · ${modelId} · 本地` })).toBeNull();
    expect(mutations()).toHaveLength(0); expect(URL.createObjectURL).not.toHaveBeenCalled();
  });
  it('rejects candidate bytes with a different digest without enabling review', async () => {
    mount(); await queue(); fireEvent.click(button('明确执行当前入队任务')); await waitFor(() => expect(button('读取并核对候选媒体').disabled).toBe(false));
    media = new NodeBlob([cutoutBytes.slice(0, -1)], { type: 'image/png' }) as unknown as Blob;
    fireEvent.click(button('读取并核对候选媒体')); await screen.findByText('候选字节摘要与任务回执不符，不可审核。');
    expect(URL.createObjectURL).not.toHaveBeenCalled(); expect(button('明确审核并入素材库').disabled).toBe(true); expect(calls('/review')).toHaveLength(0);
  });
});
