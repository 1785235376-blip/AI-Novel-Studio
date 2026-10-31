// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useStudio } from '../store';
import { bindLocalHostSession, useLocalHostSession } from '../localHostSession';
import { IndependentStudioWorkspace } from './IndependentStudioWorkspace';
import { studioClient, type StudioClient, type StudioOverview } from './studioClient';
import type { StudioGraphCreateInput, StudioGraphRecord } from './studioGraphTypes';
import { blankGraph } from './graphDraft';
import { imageGraphCatalog, imageGraphProject, imageGraphRecord } from './studioImageGraph.testFixtures';
import rawProductionCatalog from './fixtures/productionGraph.catalog.json';
import type { StudioGraphCatalog } from './studioGraphTypes';
import type { PlanningDocument } from './studioProductionGraphContract';
import { fixtureProjection } from '../director/directorWorkspaceFixtures.testFixture';
vi.mock('./studioClient', async importOriginal => ({ ...await importOriginal<typeof import('./studioClient')>(), studioClient: vi.fn() }));
let client: StudioClient;
const document: PlanningDocument = { id: 'synthetic-director', mode: 'DIRECTOR', title: 'Synthetic Director', version: 3, digest: 'a'.repeat(64) };
const deferred = <T,>() => { let resolve!: (value: T) => void; const promise = new Promise<T>(yes => { resolve = yes; }); return { promise, resolve }; };
beforeEach(() => {
  localStorage.clear(); useStudio.setState({ novelId: imageGraphProject, sessionToken: '', actor: undefined, scope: undefined });
  useLocalHostSession.setState({ token: 'production-graph-host', actorId: '' });
  const original = imageGraphCatalog(); original.definitions = original.definitions.filter(row => !row.id.startsWith('image_'));
  delete original.capabilities.image_graph; delete original.capabilities.image_graph_schema_version; delete original.capabilities.image_graph_evidence;
  delete original.capabilities.image_reference_semantics; delete original.capabilities.image_upscale_execution;
  const overview: StudioOverview = { project: { id: imageGraphProject, title: 'Synthetic Production', entry_kind: 'NEUTRAL_STUDIO' }, preferences: { version: 1, intents: [], preset: 'IMAGE', custom_intent: '' }, capabilities: { can_mutate: true, can_review: true, manual_import: true, manual_export: true, model_required: false, chapter_required: false, intent_is_permission: false, media_validator_configured: true, asset_kinds: ['image', 'video', 'audio'] } };
  client = { overview: vi.fn().mockResolvedValue(overview), assets: vi.fn().mockResolvedValue({ items: [] }), graphs: {
    catalog: vi.fn().mockResolvedValue(original), imageCatalog: vi.fn().mockResolvedValue(imageGraphCatalog()), productionCatalog: vi.fn().mockResolvedValue(rawProductionCatalog as unknown as StudioGraphCatalog),
    planningDocuments: vi.fn().mockResolvedValue({ documents: [document] }), list: vi.fn().mockResolvedValue({ items: [] }),
    create: vi.fn(async (input: StudioGraphCreateInput): Promise<StudioGraphRecord> => ({ ...imageGraphRecord(), definition: input.definition, reference_states: [{ node_id: input.definition.nodes.find(node => node.definition_id === 'director_plan')!.id, state: 'CURRENT' }] })),
    get: vi.fn(), save: vi.fn(), preflight: vi.fn(), runs: vi.fn().mockResolvedValue({ items: [] }), createRun: vi.fn(), getRun: vi.fn(), action: vi.fn(), previewMedia: vi.fn(), dispatchMedia: vi.fn(), executeMedia: vi.fn(),
  } } as unknown as StudioClient; vi.mocked(studioClient).mockReturnValue(client);
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); });
function mount() { Object.defineProperty(window, 'innerWidth', { value: 1440, configurable: true }); const query = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={query}><IndependentStudioWorkspace projectId={imageGraphProject} context={{ sessionToken: '' }} scope={{ workspace: '本机', project: 'Synthetic Production', storyline: '默认', branch: '主线' }} actor="作者" module="IMAGE" onModuleChange={vi.fn()} onProjectChoice={vi.fn()} /></QueryClientProvider>);
}
const click = (name: string) => fireEvent.click(screen.getByRole('button', { name }));
const change = (name: string, value: string) => fireEvent.change(screen.getByLabelText(name), { target: { value } });
async function enter() { fireEvent.click(await screen.findByRole('button', { name: '创作图' })); await waitFor(() => expect((screen.getByLabelText('创作图标题') as HTMLInputElement).disabled).toBe(false)); fireEvent.click(screen.getByRole('button', { name: '执行画布' })); }
async function production() { click('明确读取导演、分镜与视觉制作节点目录'); await screen.findByRole('region', { name: '图片图版本确认' });
  fireEvent.click(screen.getByLabelText('确认将当前兼容草稿采用为图片图 v4，保持原资产绑定与人工审核')); click('明确采用图片图 v4');
}
describe('Production Graph UI keeps original controller and execution authority', () => {
  it('mounts the existing read-only Director Console in a selected Director graph node', async () => {
    const projection = fixtureProjection(); projection.document = { ...projection.document, id: document.id, version: document.version, mode: 'DIRECTOR' };
    client.graphs.readDirectorWorkspace = vi.fn().mockResolvedValue(projection);
    mount(); await enter(); await production(); change('节点类型', 'director_plan');
    click('明确读取已保存导演与分镜文档'); await screen.findByRole('option', { name: 'Synthetic Director · v3' });
    change('原创作文档', document.id); click('添加节点');
    const consoleRegion = await screen.findByRole('region', { name: '图节点导演控制台' }); expect(consoleRegion).toBeTruthy();
    expect(client.graphs.readDirectorWorkspace).not.toHaveBeenCalled();
    click('展开导演控制台并核对来源'); await screen.findByLabelText('导演意图');
    expect(client.graphs.readDirectorWorkspace).toHaveBeenCalledWith({ id: document.id, version: document.version, digest: document.digest }, expect.any(AbortSignal));
    expect(client.graphs.create).not.toHaveBeenCalled(); expect(client.graphs.createRun).not.toHaveBeenCalled();
    expect(client.graphs.dispatchMedia).not.toHaveBeenCalled();
  });
  it('explicitly binds authored documents, style and upscale parameters without dispatch', async () => {
    mount(); await enter(); expect(client.graphs.productionCatalog).not.toHaveBeenCalled(); await production();
    change('节点类型', 'image_style'); click('添加节点'); change('图片风格', 'quiet cinematic');
    change('节点类型', 'director_plan'); expect((screen.getByRole('button', { name: '添加节点' }) as HTMLButtonElement).disabled).toBe(true);
    click('明确读取已保存导演与分镜文档'); await screen.findByRole('option', { name: 'Synthetic Director · v3' }); change('原创作文档', document.id); click('添加节点');
    change('节点类型', 'image_upscale'); click('添加节点'); change('超分服务商 ID', 'enabled-comfy'); change('超分模型 ID', 'installed-upscaler'); change('超分倍率（2 或 4）', '4');
    click('保存创作图'); await screen.findByText('创作图已保存 · v1。没有自动创建运行。');
    const input = vi.mocked(client.graphs.create).mock.calls[0][0]; expect(input.definition.schema_version).toBe(4);
    expect(input.definition.nodes[0].parameters.style).toBe('quiet cinematic');
    expect(input.definition.nodes[1].parameters.document_snapshot).toEqual({ id: document.id, version: 3, digest: document.digest });
    expect(input.definition.nodes[2].parameters.parameters).toEqual({ scale: 4 });
    expect(client.graphs.createRun).not.toHaveBeenCalled(); expect(client.graphs.previewMedia).not.toHaveBeenCalled(); expect(client.graphs.dispatchMedia).not.toHaveBeenCalled(); expect(client.graphs.executeMedia).not.toHaveBeenCalled();
  });
  it('ignores late document references after a same-token Host replacement', async () => {
    const late = deferred<{ documents: PlanningDocument[] }>(); vi.mocked(client.graphs.planningDocuments!).mockReturnValue(late.promise);
    mount(); await enter(); await production(); change('节点类型', 'director_plan'); click('明确读取已保存导演与分镜文档');
    await waitFor(() => expect(client.graphs.planningDocuments).toHaveBeenCalledTimes(1));
    act(() => bindLocalHostSession('production-graph-host', { session_mode: 'LOCAL_HOST', actor_id: 'replacement-author' })); await act(async () => late.resolve({ documents: [document] }));
    expect(screen.queryByRole('option', { name: 'Synthetic Director · v3' })).toBeNull(); expect(client.graphs.create).not.toHaveBeenCalled();
  });
  it('keeps Style inspector and controller bounds aligned to the backend', async () => {
    mount(); await enter(); await production(); change('节点类型', 'image_style'); click('添加节点');
    expect((screen.getByLabelText('图片风格') as HTMLTextAreaElement).maxLength).toBe(2000);
    for (const label of ['图片氛围', '图片色彩']) {
      const input = screen.getByLabelText(label) as HTMLTextAreaElement; expect(input.maxLength).toBe(1000);
      change(label, 'a'.repeat(1000)); expect(input.value).toBe('a'.repeat(1000));
      change(label, 'b'.repeat(1001)); expect(input.value).toBe('a'.repeat(1000));
    }
    expect(client.graphs.create).not.toHaveBeenCalled(); expect(client.graphs.createRun).not.toHaveBeenCalled();
  });
});
