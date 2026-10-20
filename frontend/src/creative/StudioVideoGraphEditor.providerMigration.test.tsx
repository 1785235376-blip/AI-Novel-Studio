// @vitest-environment jsdom
// Focused modern-path migration variant; the protected legacy scenario remains unchanged.
// This preserves an alternate fixture/control path and is not a new unique scenario.
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useStudio } from '../store';
import { useLocalHostSession } from '../localHostSession';
import { IndependentStudioWorkspace } from './IndependentStudioWorkspace';
import { studioClient, type StudioClient, type StudioOverview } from './studioClient';
import type { StudioGraphCreateInput, StudioGraphRecord, StudioGraphCatalog } from './studioGraphTypes';
import { imageGraphCatalog, imageGraphProject, imageGraphRecord } from './studioImageGraph.testFixtures';
import videoCatalog from './fixtures/phase4.video-catalog.json';
import storyboard from './fixtures/phase4.file-api-storyboard.json';
import { checkedStoryboardReceipt } from './studioStoryboardContract';

import type { PlanningDocument } from './studioProductionGraphContract';
import { studioProductionClient } from './studioProductionClient';
import { mediaProviderKey } from './useStudioMediaExecution';
vi.mock('./studioProductionClient', async original => ({ ...await original<typeof import('./studioProductionClient')>(), studioProductionClient: vi.fn() }));
const pickerRow = { operation_id: 'm7.video.t2v' as const, provider_id: 'synthetic-comfy', model_id: 'observed-model', local: true, route_digest: 'a'.repeat(64), capability: 'MEDIA', supported_parameters: [], readiness: 'CONFIGURED_NOT_VERIFIED' as const };
vi.mock('./studioClient', async importOriginal => ({ ...await importOriginal<typeof import('./studioClient')>(), studioClient: vi.fn() }));
let client: StudioClient;
const document: PlanningDocument = { ...storyboard.document_snapshot, mode: 'STORYBOARD', title: 'Synthetic saved storyboard' };

beforeEach(() => {
  vi.mocked(studioProductionClient).mockReturnValue({ providers: vi.fn().mockResolvedValue([pickerRow]) } as unknown as ReturnType<typeof studioProductionClient>);
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
async function addBoard() { change('节点类型', 'storyboard_plan'); click('明确读取已保存导演与分镜文档'); await screen.findByRole('option', { name: 'Synthetic saved storyboard · v4' }); change('原创作文档', document.id); click('添加节点'); }
describe('Explicit video Graph keeps saved shot and original execution authority', () => {
  it("migration: adds exact current shot pins and video controls without starting a job", async () => {
    mount(); await enter(); expect(client.graphs.videoCatalog).not.toHaveBeenCalled(); await adopt(); await addBoard();
    change('节点类型', 'storyboard_shot'); expect((screen.getByRole('button', { name: '添加节点' }) as HTMLButtonElement).disabled).toBe(true);
    const source = screen.getByLabelText('图中分镜来源') as HTMLSelectElement; change('图中分镜来源', source.options[1].value); click('明确读取来源分镜镜头');
    await screen.findByRole('option', { name: 'SHOT 1 · shot-1 · v1' }); change('原分镜镜头', 'shot-1'); click('添加节点');
    change('节点类型', 'video_generate'); click('添加节点'); click('读取节点服务配置'); await screen.findByRole('option', { name: 'synthetic-comfy · observed-model · 本地' }); change('节点服务商与模型', mediaProviderKey(pickerRow));
    change('视频操作', 'm7.video.v2v'); change('参考视频用途', 'camera'); click('保存创作图'); await screen.findByText('创作图已保存 · v1。没有自动创建运行。');
    const definition = vi.mocked(client.graphs.create).mock.calls[0][0].definition;
    expect(definition.schema_version).toBe(5); expect(definition.nodes[1].parameters).toEqual({ shot_id: 'shot-1', shot_version: storyboard.shots[0].shot_version, shot_digest: storyboard.shots[0].shot_digest });
    expect(definition.nodes[2].parameters.reference_purpose).toBe('camera');
    expect(client.graphs.createRun).not.toHaveBeenCalled(); expect(client.graphs.previewMedia).not.toHaveBeenCalled(); expect(client.graphs.dispatchMedia).not.toHaveBeenCalled(); expect(client.graphs.executeMedia).not.toHaveBeenCalled();
  });
});
