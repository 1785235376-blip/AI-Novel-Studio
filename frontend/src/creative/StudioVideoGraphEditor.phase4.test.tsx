// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useStudio } from '../store';
import { bindLocalHostSession, useLocalHostSession } from '../localHostSession';
import { IndependentStudioWorkspace } from './IndependentStudioWorkspace';
import { studioClient, type StudioClient, type StudioOverview } from './studioClient';
import type { StudioGraphCreateInput, StudioGraphRecord, StudioGraphCatalog } from './studioGraphTypes';
import { imageGraphCatalog, imageGraphProject, imageGraphRecord } from './studioImageGraph.testFixtures';
import videoCatalog from './fixtures/phase4.video-catalog.json';
import storyboard from './fixtures/phase4.file-api-storyboard.json';
import { checkedStoryboardReceipt } from './studioStoryboardContract';
import { connectionIssue, graphCatalogForSchema } from './graphDraft';
import type { PlanningDocument } from './studioProductionGraphContract';
vi.mock('./studioClient', async importOriginal => ({ ...await importOriginal<typeof import('./studioClient')>(), studioClient: vi.fn() }));
let client: StudioClient;
const document: PlanningDocument = { ...storyboard.document_snapshot, mode: 'STORYBOARD', title: 'Synthetic saved storyboard' };
const deferred = <T,>() => { let resolve!: (value: T) => void; const promise = new Promise<T>(yes => { resolve = yes; }); return { promise, resolve }; };
beforeEach(() => {
  localStorage.clear(); useStudio.setState({ novelId: imageGraphProject, sessionToken: '', actor: undefined, scope: undefined });
  useLocalHostSession.setState({ token: 'video-graph-host', actorId: '' });
  const original = imageGraphCatalog(); original.definitions = original.definitions.filter(row => !row.id.startsWith('image_'));
  delete original.capabilities.image_graph; delete original.capabilities.image_graph_schema_version; delete original.capabilities.image_graph_evidence;
  delete original.capabilities.image_reference_semantics; delete original.capabilities.image_upscale_execution;
  const overview: StudioOverview = { project: { id: imageGraphProject, title: 'Synthetic video', entry_kind: 'NEUTRAL_STUDIO' }, preferences: { version: 1, intents: [], preset: 'VIDEO', custom_intent: '' }, capabilities: { can_mutate: true, can_review: true, manual_import: true, manual_export: true, model_required: false, chapter_required: false, intent_is_permission: false, media_validator_configured: true, asset_kinds: ['image', 'video', 'audio'] } };
  client = { overview: vi.fn().mockResolvedValue(overview), assets: vi.fn().mockResolvedValue({ items: [] }), graphs: {
    catalog: vi.fn().mockResolvedValue(original), imageCatalog: vi.fn().mockResolvedValue(imageGraphCatalog()), videoCatalog: vi.fn().mockResolvedValue(videoCatalog as unknown as StudioGraphCatalog),
    planningDocuments: vi.fn().mockResolvedValue({ documents: [document] }), videoStoryboard: vi.fn().mockResolvedValue(checkedStoryboardReceipt(storyboard)), list: vi.fn().mockResolvedValue({ items: [] }),
    create: vi.fn(async (input: StudioGraphCreateInput): Promise<StudioGraphRecord> => ({ ...imageGraphRecord(), definition: input.definition, reference_states: input.definition.nodes.filter(node => ['director_plan', 'storyboard_plan', 'asset_reference'].includes(node.definition_id)).map(node => ({ node_id: node.id, state: 'CURRENT' })) })),
    get: vi.fn(), save: vi.fn(), preflight: vi.fn(), runs: vi.fn().mockResolvedValue({ items: [] }), createRun: vi.fn(), getRun: vi.fn(), action: vi.fn(), previewMedia: vi.fn(), dispatchMedia: vi.fn(), executeMedia: vi.fn(),
  } } as unknown as StudioClient; vi.mocked(studioClient).mockReturnValue(client);
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); });
function mount() { const query = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={query}><IndependentStudioWorkspace projectId={imageGraphProject} context={{ sessionToken: '' }} scope={{ workspace: '本机', project: 'Synthetic video', storyline: '默认', branch: '主线' }} actor="作者" module="VIDEO" onModuleChange={vi.fn()} onProjectChoice={vi.fn()} /></QueryClientProvider>);
}
const click = (name: string) => fireEvent.click(screen.getByRole('button', { name }));
const change = (name: string, value: string) => fireEvent.change(screen.getByLabelText(name), { target: { value } });
async function enter() { fireEvent.click(await screen.findByRole('button', { name: '创作图' })); await waitFor(() => expect((screen.getByLabelText('创作图标题') as HTMLInputElement).disabled).toBe(false)); }
async function adopt() { click('明确读取视频图节点目录'); await screen.findByRole('region', { name: '视频图版本确认' });
  fireEvent.click(screen.getByLabelText('确认当前兼容草稿采用视频图 v5，保留来源、审核与原任务')); click('明确采用视频图 v5');
}
async function addBoard() { change('节点类型', 'storyboard_plan'); click('明确读取已保存导演与分镜文档'); await waitFor(() => expect((screen.getByLabelText('原创作文档') as HTMLSelectElement).options.length).toBeGreaterThan(1)); change('原创作文档', document.id); click('添加节点'); }
describe('Explicit video Graph keeps saved shot and original execution authority', () => {
  it('retains Image schema descriptors and author input while a Video catalog awaits consent', async () => {
    mount(); await enter(); click('明确读取图片节点目录'); await screen.findByRole('region', { name: '图片图版本确认' }); fireEvent.click(screen.getByLabelText('确认将当前兼容草稿采用为图片图 v4，保持原资产绑定与人工审核')); click('明确采用图片图 v4');
    change('节点类型', 'image_prompt'); click('添加节点'); change('图片提示词', 'retained authored prompt');
    click('明确读取视频图节点目录'); await screen.findByRole('region', { name: '视频图版本确认' });
    expect(screen.getByLabelText('节点类型').querySelector('option[value="image_generate"]')).toBeTruthy(); expect((screen.getByLabelText('图片提示词') as HTMLTextAreaElement).value).toBe('retained authored prompt');
    fireEvent.click(screen.getByLabelText('确认当前兼容草稿采用视频图 v5，保留来源、审核与原任务')); click('明确采用视频图 v5'); await screen.findByText('当前图含视频图不支持的节点。请保留原图，明确新建空图；不会自动删除节点。');
    click('保存创作图'); await screen.findByText('创作图已保存 · v1。没有自动创建运行。');
    expect(vi.mocked(client.graphs.create).mock.calls[0][0].definition).toMatchObject({ schema_version: 4, nodes: [{ definition_id: 'image_prompt', parameters: { prompt: 'retained authored prompt' } }] }); expect(client.graphs.createRun).not.toHaveBeenCalled();
  });
  it('adds exact current shot pins and video controls without starting a job', async () => {
    mount(); await enter(); expect(client.graphs.videoCatalog).not.toHaveBeenCalled(); await adopt(); await addBoard();
    change('节点类型', 'storyboard_shot'); expect((screen.getByRole('button', { name: '添加节点' }) as HTMLButtonElement).disabled).toBe(true);
    const source = screen.getByLabelText('图中分镜来源') as HTMLSelectElement; change('图中分镜来源', source.options[1].value); click('明确读取来源分镜镜头');
    await waitFor(() => expect((screen.getByLabelText('原分镜镜头') as HTMLSelectElement).options.length).toBeGreaterThan(1)); change('原分镜镜头', 'shot-1'); click('添加节点');
    change('节点类型', 'video_generate'); click('添加节点'); change('视频服务商 ID', 'synthetic-comfy'); change('视频模型 ID', 'observed-model');
    change('视频操作', 'm7.video.v2v'); change('参考视频用途', 'camera'); click('保存创作图'); await screen.findByText('创作图已保存 · v1。没有自动创建运行。');
    const definition = vi.mocked(client.graphs.create).mock.calls[0][0].definition;
    expect(definition.schema_version).toBe(5); expect(definition.nodes[1].parameters).toEqual({ shot_id: 'shot-1', shot_version: storyboard.shots[0].shot_version, shot_digest: storyboard.shots[0].shot_digest });
    expect(definition.nodes[2].parameters.reference_purpose).toBe('camera');
    expect(client.graphs.createRun).not.toHaveBeenCalled(); expect(client.graphs.previewMedia).not.toHaveBeenCalled(); expect(client.graphs.dispatchMedia).not.toHaveBeenCalled(); expect(client.graphs.executeMedia).not.toHaveBeenCalled();
  });
  it('ignores a late saved shot receipt after same-token Host replacement', async () => {
    const late = deferred<ReturnType<typeof checkedStoryboardReceipt>>(); vi.mocked(client.graphs.videoStoryboard!).mockReturnValue(late.promise);
    mount(); await enter(); await adopt(); await addBoard(); change('节点类型', 'storyboard_shot');
    const source = screen.getByLabelText('图中分镜来源') as HTMLSelectElement; change('图中分镜来源', source.options[1].value); click('明确读取来源分镜镜头');
    await waitFor(() => expect(client.graphs.videoStoryboard).toHaveBeenCalledTimes(1)); act(() => bindLocalHostSession('video-graph-host', { session_mode: 'LOCAL_HOST', actor_id: 'replacement' }));
    await act(async () => late.resolve(checkedStoryboardReceipt(storyboard))); expect(screen.queryByRole('option', { name: 'SHOT 1 · shot-1 · v1' })).toBeNull(); expect(client.graphs.create).not.toHaveBeenCalled();
  });
  it('permits Director to Storyboard to Shot ports only in compatible schema', () => {
    const definitions = graphCatalogForSchema((videoCatalog as unknown as StudioGraphCatalog).definitions, 5);
    const nodes = [{ id: 'director', definition_id: 'director_plan', definition_version: 1, enabled: true, position: { x: 0, y: 0 }, parameters: {} }, { id: 'board', definition_id: 'storyboard_plan', definition_version: 1, enabled: true, position: { x: 1, y: 0 }, parameters: {} }, { id: 'shot', definition_id: 'storyboard_shot', definition_version: 1, enabled: true, position: { x: 2, y: 0 }, parameters: {} }] as StudioGraphRecord['definition']['nodes'];
    const graph = { schema_version: 5, title: 'Synthetic', nodes, edges: [], viewport: { x: 0, y: 0, zoom: 1 } } as StudioGraphRecord['definition'];
    expect(connectionIssue(graph, definitions, { id: 'd-b', source_node_id: 'director', source_port: 'direction', target_node_id: 'board', target_port: 'direction' })).toBeUndefined();
    expect(connectionIssue(graph, definitions, { id: 'b-s', source_node_id: 'board', source_port: 'storyboard', target_node_id: 'shot', target_port: 'storyboard' })).toBeUndefined();
    expect(connectionIssue({ ...graph, schema_version: 4 }, definitions, { id: 'b-s', source_node_id: 'board', source_port: 'storyboard', target_node_id: 'shot', target_port: 'storyboard' })).toBeTruthy();
  });
});
