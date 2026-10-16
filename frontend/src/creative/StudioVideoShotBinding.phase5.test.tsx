// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useStudio } from '../store';
import { useLocalHostSession } from '../localHostSession';
import { IndependentStudioWorkspace } from './IndependentStudioWorkspace';
import { studioClient, type StudioClient, type StudioOverview } from './studioClient';
import { createStudioGraphClient } from './studioGraphClient';
import type { StudioGraphCreateInput, StudioGraphRecord } from './studioGraphTypes';
import { imageGraphCatalog, imageGraphProject, imageGraphRecord } from './studioImageGraph.testFixtures';
import catalogFixture from './fixtures/phase5.capture.video-catalog.json';
import { studioProductionClient } from './studioProductionClient';
import { mediaProviderKey } from './useStudioMediaExecution';
vi.mock('./studioProductionClient', async original => ({ ...await original<typeof import('./studioProductionClient')>(), studioProductionClient: vi.fn() }));
const pickerRow = { operation_id: 'm7.video.t2v' as const, provider_id: 'synthetic-comfy', model_id: 'observed-only-model', local: true, route_digest: 'a'.repeat(64), capability: 'MEDIA', supported_parameters: [], readiness: 'CONFIGURED_NOT_VERIFIED' as const };
vi.mock('./studioClient', async importOriginal => ({ ...await importOriginal<typeof import('./studioClient')>(), studioClient: vi.fn() }));
const copy = <T,>(value: T): T => structuredClone(value);
let client: StudioClient;
beforeEach(() => {
  vi.mocked(studioProductionClient).mockReturnValue({ providers: vi.fn().mockResolvedValue([pickerRow]) } as unknown as ReturnType<typeof studioProductionClient>);
  localStorage.clear(); useStudio.setState({ novelId: imageGraphProject, sessionToken: '', actor: undefined, scope: undefined }); useLocalHostSession.setState({ token: 'synthetic-shot-binding-unit', actorId: '' });
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

describe('Phase 5 actual Video catalog retains optional true-only binding', () => {
  it('decodes the newly mounted catalog without changing old graph semantics', async () => {
    const json = vi.fn().mockResolvedValue(copy(catalogFixture)), client = createStudioGraphClient(imageGraphProject, {}, { json });
    const result = await client.videoCatalog!(); expect(result.definitions.find(row => row.id === 'video_generate')?.parameters_schema.properties.bind_shot).toEqual({ type: 'boolean', const: true });
    expect(json).toHaveBeenCalledOnce(); expect(json.mock.calls[0][0]).toContain('include_video=true');
  });
  it.each(['lost-original-property', 'false-allowed'])('rejects a changed binding catalog %s', async mutation => {
    const value = copy(catalogFixture), schema = value.definitions.find(row => row.id === 'video_generate')!.parameters_schema as unknown as { properties: Record<string, unknown> };
    if (mutation === 'lost-original-property') delete schema.properties.operation_id;
    else schema.properties.bind_shot = { anyOf: [{ type: 'boolean' }, { type: 'null' }], default: null };
    await expect(createStudioGraphClient(imageGraphProject, {}, { json: vi.fn().mockResolvedValue(value) }).videoCatalog!()).rejects.toBeTruthy();
  });
});

describe('Phase 5 independent Video author flow can explicitly omit a new Shot binding', () => {
  it('allows unchecking the initial true flag without a connected Shot and saves no implicit pin', async () => {
    const original = imageGraphCatalog(); original.definitions = original.definitions.filter(row => !row.id.startsWith('image_'));
    const json = vi.fn().mockResolvedValue(copy(catalogFixture)), video = await createStudioGraphClient(imageGraphProject, {}, { json }).videoCatalog!();
    const overview: StudioOverview = { project: { id: imageGraphProject, title: 'Synthetic standalone video', entry_kind: 'NEUTRAL_STUDIO' }, preferences: { version: 1, intents: [], preset: 'VIDEO', custom_intent: '' }, capabilities: { can_mutate: true, can_review: true, manual_import: true, manual_export: true, model_required: false, chapter_required: false, intent_is_permission: false, media_validator_configured: true, asset_kinds: ['image', 'video', 'audio'] } };
    client = { overview: vi.fn().mockResolvedValue(overview), assets: vi.fn().mockResolvedValue({ items: [] }), graphs: { catalog: vi.fn().mockResolvedValue(original), videoCatalog: vi.fn().mockResolvedValue(video),
      list: vi.fn().mockResolvedValue({ items: [] }), create: vi.fn(async (input: StudioGraphCreateInput): Promise<StudioGraphRecord> => ({ ...imageGraphRecord(), definition: input.definition, reference_states: [] })), runs: vi.fn().mockResolvedValue({ items: [] }),
      get: vi.fn(), save: vi.fn(), preflight: vi.fn(), createRun: vi.fn(), previewMedia: vi.fn(), dispatchMedia: vi.fn(), executeMedia: vi.fn() } } as unknown as StudioClient;
    vi.mocked(studioClient).mockReturnValue(client); const query = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
    render(<QueryClientProvider client={query}><IndependentStudioWorkspace projectId={imageGraphProject} context={{ sessionToken: '' }} scope={{ workspace: '本机', project: 'Synthetic', storyline: '默认', branch: '主线' }} actor="作者" module="VIDEO" onModuleChange={vi.fn()} onProjectChoice={vi.fn()} /></QueryClientProvider>);
    fireEvent.click(await screen.findByRole('button', { name: '创作图' })); await waitFor(() => expect((screen.getByLabelText('创作图标题') as HTMLInputElement).disabled).toBe(false));
    fireEvent.click(screen.getByRole('button', { name: '明确读取视频图节点目录' })); await screen.findByRole('region', { name: '视频图版本确认' });
    fireEvent.click(screen.getByLabelText('确认当前兼容草稿采用视频图 v5，保留来源、审核与原任务')); fireEvent.click(screen.getByRole('button', { name: '明确采用视频图 v5' }));
    fireEvent.change(screen.getByLabelText('节点类型'), { target: { value: 'video_generate' } }); fireEvent.click(screen.getByRole('button', { name: '添加节点' }));
    const binding = screen.getByLabelText('绑定镜头来源') as HTMLInputElement; expect(binding.checked).toBe(true); expect(binding.disabled).toBe(false);
    fireEvent.click(binding); expect(binding.checked).toBe(false); expect(binding.disabled).toBe(true);
    fireEvent.click(screen.getByRole('button', { name: '读取节点服务配置' })); await screen.findByRole('option', { name: 'synthetic-comfy · observed-only-model · 本地' }); fireEvent.change(screen.getByLabelText('节点服务商与模型'), { target: { value: mediaProviderKey(pickerRow) } });
    fireEvent.change(screen.getByLabelText('视频提示词'), { target: { value: 'An independent authored short clip' } }); fireEvent.click(screen.getByRole('button', { name: '保存创作图' }));
    await screen.findByText('创作图已保存 · v1。没有自动创建运行。'); const saved = vi.mocked(client.graphs.create).mock.calls[0][0].definition;
    expect(Object.hasOwn(saved.nodes[0].parameters, 'bind_shot')).toBe(false); expect(saved.nodes[0].parameters.prompt).toBe('An independent authored short clip'); expect(saved.edges).toEqual([]);
    expect(client.graphs.createRun).not.toHaveBeenCalled(); expect(client.graphs.previewMedia).not.toHaveBeenCalled(); expect(client.graphs.dispatchMedia).not.toHaveBeenCalled(); expect(client.graphs.executeMedia).not.toHaveBeenCalled();
  });
});
