// @vitest-environment jsdom
// Additive scenarios extracted from the pre-reconciliation suite.
// The protected original test file remains byte-for-byte unchanged.
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useStudio } from '../store';
import { useLocalHostSession } from '../localHostSession';
import { IndependentStudioWorkspace } from './IndependentStudioWorkspace';
import { studioClient, type StudioClient, type StudioOverview } from './studioClient';
import type { StudioGraphCreateInput, StudioGraphRecord } from './studioGraphTypes';

import { imageGraphCatalog, imageGraphProject, imageGraphRecord } from './studioImageGraph.testFixtures';
import rawProductionCatalog from './fixtures/productionGraph.catalog.json';
import type { StudioGraphCatalog } from './studioGraphTypes';
import { creativeClient, type DirectorProposal } from './client';
import { newDocument, newScene, type CreativeDocument } from './types';
vi.mock('./client', async original => ({ ...await original<typeof import('./client')>(), creativeClient: vi.fn() }));
import type { PlanningDocument } from './studioProductionGraphContract';

import { studioProductionClient } from './studioProductionClient';
// [HERMIA-FE-20261023 M1-flaky] Root cause: these long jsdom integration flows take 3-5s unloaded and exceed vitest's default 5000ms testTimeout under full-suite CPU load. Budget raised per file; no assertion, step or mock changed.
vi.setConfig({ testTimeout: 30000 });

vi.mock('./studioProductionClient', async original => ({ ...await original<typeof import('./studioProductionClient')>(), studioProductionClient: vi.fn() }));
const pickerRow = { operation_id: 'm5.image.upscale' as const, provider_id: 'enabled-comfy', model_id: 'installed-upscaler', local: true, route_digest: 'a'.repeat(64), capability: 'MEDIA', supported_parameters: [], readiness: 'CONFIGURED_NOT_VERIFIED' as const };
vi.mock('./studioClient', async importOriginal => ({ ...await importOriginal<typeof import('./studioClient')>(), studioClient: vi.fn() }));
let client: StudioClient;
const document: PlanningDocument = { id: 'synthetic-director', mode: 'DIRECTOR', title: 'Synthetic Director', version: 3, digest: 'a'.repeat(64) };

beforeEach(() => {
  vi.mocked(creativeClient).mockReturnValue({} as ReturnType<typeof creativeClient>);
  vi.mocked(studioProductionClient).mockReturnValue({ providers: vi.fn().mockResolvedValue([pickerRow]) } as unknown as ReturnType<typeof studioProductionClient>);
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
  it('lays out already-saved Director pins without rewriting their source or executing', async () => {
    mount(); await enter(); await production(); change('节点类型', 'director_plan');
    click('明确读取已保存导演与分镜文档'); await screen.findByRole('option', { name: 'Synthetic Director · v3' });
    change('原创作文档', document.id); click('添加节点');
    click('保存创作图'); await screen.findByText('创作图已保存 · v1。没有自动创建运行。');
    const original = structuredClone(vi.mocked(client.graphs.create).mock.calls[0][0].definition);
    vi.mocked(client.graphs.save).mockImplementation(async (_id, input) => ({ ...imageGraphRecord(), version: 2, definition: input.definition,
      reference_states: [{ node_id: original.nodes[0].id, state: 'CURRENT' }] }));
    click('应用自动布局到草稿'); click('保存创作图'); await screen.findByText('创作图已保存 · v2。没有自动创建运行。');
    const updated = vi.mocked(client.graphs.save).mock.calls[0][1];
    expect(updated.expected_version).toBe(1);
    expect(updated.definition.viewport).toEqual(original.viewport);
    expect(updated.definition.edges).toEqual(original.edges);
    expect(updated.definition.nodes[0].position).toEqual({ x: 0, y: 0 });
    expect({ ...updated.definition.nodes[0], position: original.nodes[0].position }).toEqual(original.nodes[0]);
    expect(client.graphs.createRun).not.toHaveBeenCalled(); expect(client.graphs.dispatchMedia).not.toHaveBeenCalled();
  });
});

// The actual IndependentStudioWorkspace mounts both authoring and Graph owners.
it('authors a director in the canvas, saves its exact node pin and reopens the bound source', async () => {
  let authored: CreativeDocument = { ...newDocument('DIRECTOR'), source_independent: true, title: '画布导演', id: document.id,
    version: 3, status: 'DRAFT', created_at: '', updated_at: '', actor_id: 'author', source_evidence: {} };
  const source = { capabilities: vi.fn().mockResolvedValue({ enabled: true, can_mutate: true, modes: ['DIRECTOR'] }),
    history: vi.fn(async () => ({ document_id: document.id, current_version: authored.version, items: [authored], snapshot_digests: [{ version: authored.version, digest: document.digest }] })),
    list: vi.fn(async () => ({ items: [authored] })),
    create: vi.fn(async input => authored = { ...authored, ...input }), update: vi.fn(),
    export: vi.fn(async () => ({ document: authored, document_digest: document.digest, format: '', boundary: '' })) };
  vi.mocked(creativeClient).mockReturnValue(source as unknown as ReturnType<typeof creativeClient>);
  const first = mount(); await enter(); click('打开导演总控台');
  await waitFor(() => expect((screen.getByLabelText('文档标题') as HTMLInputElement).closest('fieldset')!.disabled).toBe(false));
  change('文档标题', '画布导演'); click('添加场景'); click('添加导演调度'); change('导演意图', '停顿后看向窗外');
  expect((screen.getByRole('button', { name: '保存创作图' }) as HTMLButtonElement).disabled).toBe(true);
  click('保存草稿'); await screen.findByText(/导演原文档已保存/);
  await production(); change('节点类型', 'director_plan'); click('明确读取已保存导演与分镜文档');
  await screen.findByRole('option', { name: 'Synthetic Director · v3' }); change('原创作文档', document.id); click('添加节点');
  change('创作图标题', '导演工作台回环'); click('保存创作图'); await screen.findByText('创作图已保存 · v1。没有自动创建运行。');
  const saved = await vi.mocked(client.graphs.create).mock.results[0].value as StudioGraphRecord;
  expect(saved.definition.nodes[0].parameters.document_snapshot).toEqual({ id: document.id, version: 3, digest: document.digest });
  expect(authored.director_notes[0].note).toBe('停顿后看向窗外');
  first.unmount(); localStorage.clear();
  vi.mocked(client.graphs.list).mockResolvedValue({ items: [saved] }); vi.mocked(client.graphs.get).mockResolvedValue(saved);
  mount(); await enter(); change('已保存创作图', saved.id);
  const select = await screen.findByRole('button', { name: new RegExp(`选择节点 .*${saved.definition.nodes[0].id}`) }); fireEvent.click(select);
  click('打开导演总控台'); await waitFor(() => expect((screen.getByLabelText('文档标题') as HTMLInputElement).closest('fieldset')!.disabled).toBe(false));
  click('读取选中导演节点原文档'); await screen.findByDisplayValue('停顿后看向窗外');
  click('读取／刷新导演来源影响'); await screen.findByText(/历史快照版本与原 Owner 摘要匹配/);
  expect(screen.getByText(/选中 director_plan 节点：/).textContent).toContain(saved.definition.nodes[0].id);
  expect(saved.definition.nodes[0].parameters.document_snapshot).toEqual({ id: document.id, version: 3, digest: document.digest });
  expect(source.export).toHaveBeenCalledWith(document.id); expect(source.update).not.toHaveBeenCalled();
  expect(client.graphs.createRun).not.toHaveBeenCalled(); expect(client.graphs.dispatchMedia).not.toHaveBeenCalled();
});

it('requires an explicit original workspace navigation confirmation to abandon an UNKNOWN director create', async () => {
  const source = { capabilities: vi.fn().mockResolvedValue({ enabled: true, can_mutate: true, modes: ['DIRECTOR'] }),
    create: vi.fn().mockRejectedValue(new Error('offline')), update: vi.fn(), export: vi.fn(), list: vi.fn() };
  vi.mocked(creativeClient).mockReturnValue(source as unknown as ReturnType<typeof creativeClient>);
  mount(); await enter(); fireEvent.click(await screen.findByRole('button', { name: '打开导演总控台' }));
  await waitFor(() => expect((screen.getByLabelText('文档标题') as HTMLInputElement).closest('fieldset')!.disabled).toBe(false));
  change('文档标题', '未知回执'); click('保存草稿'); await screen.findByText(/保存冲突或回执不确定/);
  click('返回项目列表'); await screen.findByText(/放弃只移除本地草稿，不代表远端写入失败/);
  expect((screen.getByRole('button', { name: '确认离开' }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(screen.getByLabelText('确认放弃未保存输入')); click('确认离开');
  await screen.findByRole('button', { name: '打开导演总控台' }); expect(source.create).toHaveBeenCalledTimes(1);
});

it('keeps an UNKNOWN storyboard handoff pending through cancelled workspace navigation', async () => {
  let authored: CreativeDocument = { ...newDocument('DIRECTOR'), source_independent: true, title: '人工调度', id: document.id,
    version: 3, status: 'DRAFT', created_at: '', updated_at: '', actor_id: 'author', source_evidence: {} };
  const source = { capabilities: vi.fn().mockResolvedValue({ enabled: true, can_mutate: true, modes: ['DIRECTOR', 'STORYBOARD'] }),
    create: vi.fn(async input => authored = { ...authored, ...input }), update: vi.fn(), list: vi.fn().mockResolvedValue({ items: [] }),
    derive: vi.fn().mockRejectedValue(new Error('handoff offline')),
    export: vi.fn(async () => ({ document: authored, document_digest: document.digest, format: '', boundary: '' })) };
  vi.mocked(creativeClient).mockReturnValue(source as unknown as ReturnType<typeof creativeClient>);
  mount(); await enter(); fireEvent.click(await screen.findByRole('button', { name: '打开导演总控台' }));
  await waitFor(() => expect((screen.getByLabelText('文档标题') as HTMLInputElement).closest('fieldset')!.disabled).toBe(false));
  change('文档标题', '人工调度'); click('添加场景'); click('添加导演调度'); click('保存草稿');
  await screen.findByText(/导演原文档已保存/); click('核对导演原文档版本'); await screen.findByText(/交接来源/);
  fireEvent.click(screen.getByLabelText('已核对来源，明确建立新的分镜草稿，仍需人工复审')); click('交接到原分镜草稿');
  await screen.findByText('handoff offline'); expect((screen.getByRole('button', { name: '保存创作图' }) as HTMLButtonElement).disabled).toBe(true);
  click('返回项目列表'); await screen.findByText(/放弃只移除本地草稿，不代表远端写入失败/); click('继续编辑');
  expect(screen.getByText(/分镜建立结果未知或待核对/)).toBeTruthy();
  expect((screen.getByRole('button', { name: '交接到原分镜草稿' }) as HTMLButtonElement).disabled).toBe(true);
  click('读取关联分镜与状态'); await waitFor(() => expect(source.list).toHaveBeenCalledTimes(1));
  click('返回项目列表'); await screen.findByText(/放弃只移除本地草稿，不代表远端写入失败/);
  expect((screen.getByRole('button', { name: '确认离开' }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(screen.getByLabelText('确认放弃未保存输入')); click('确认离开');
  await screen.findByRole('button', { name: '打开导演总控台' }); expect(source.derive).toHaveBeenCalledTimes(1);
  expect(client.graphs.createRun).not.toHaveBeenCalled(); expect(client.graphs.dispatchMedia).not.toHaveBeenCalled();
});

it('reviews an original screenplay proposal, explicitly pins the DRAFT and reopens both owners without model execution', async () => {
  const scene = newScene(1), sourceDigest = 'b'.repeat(64);
  const screenplay: CreativeDocument = { ...newDocument('SCREENPLAY'), id: 'screenplay-owner', version: 2,
    title: '原剧本', source_independent: true, scenes: [{ ...scene, heading: 'EXT. HARBOR - MORNING', action: 'The visitor stops.' }],
    status: 'DRAFT', created_at: '', updated_at: '', actor_id: 'author', source_evidence: {} };
  const note = { id: 'note-one', number: 1, scene_id: scene.id, note: 'Pause before turning', shot_size: 'MEDIUM',
    camera_angle: 'EYE_LEVEL', camera_motion: 'STATIC', duration_seconds: 5, emotion: '', pacing: '', performance: '', blocking: '' };
  let proposal: DirectorProposal | undefined, director: CreativeDocument | undefined;
  const source = {
    capabilities: vi.fn().mockResolvedValue({ enabled: true, can_mutate: true, modes: ['SCREENPLAY', 'DIRECTOR', 'STORYBOARD'] }),
    list: vi.fn(async () => ({ items: [screenplay, ...(director ? [director] : [])] })),
    proposals: vi.fn(async () => ({ items: proposal ? [proposal] : [] })),
    proposal: vi.fn(async () => proposal!), get: vi.fn(async () => director!),
    propose: vi.fn(async () => proposal = { id: 'proposal-owner', version: 1, status: 'NEEDS_REVIEW',
      source_document_id: screenplay.id, source_version: screenplay.version, source_digest: sourceDigest, title: '待审导演建议',
      director_notes: [note], output_digest: 'c'.repeat(64), provenance: { model_called: false } }),
    review: vi.fn(async (_proposal: DirectorProposal, title: string) => {
      director = { ...newDocument('DIRECTOR'), id: document.id, version: 3, title, source_independent: true,
        scenes: screenplay.scenes, director_notes: [note], source_documents: { [screenplay.id]: { version: screenplay.version, digest: sourceDigest } },
        status: 'DRAFT', created_at: '', updated_at: '', actor_id: 'author', source_evidence: {} };
      proposal = { ...proposal!, version: 2, status: 'APPROVED', document_id: director.id };
      return { proposal, document: director };
    }),
    modelRoutes: vi.fn().mockResolvedValue({ items: [] }), previewModel: vi.fn(), dispatchModel: vi.fn(), refreshModel: vi.fn(), cancelProposal: vi.fn(),
    create: vi.fn(), update: vi.fn(), derive: vi.fn(), history: vi.fn(),
    export: vi.fn(async () => ({ document: director!, document_digest: document.digest, format: '', boundary: '' })),
  };
  vi.mocked(creativeClient).mockReturnValue(source as unknown as ReturnType<typeof creativeClient>);
  vi.mocked(client.graphs.planningDocuments!).mockImplementation(async () => ({ documents: director ? [{ ...document, title: director.title }] : [] }));
  const view = mount(); await enter(); expect(source.proposals).not.toHaveBeenCalled(); click('打开导演总控台');
  await screen.findByRole('button', { name: '从已保存剧本打开导演建议审核' });
  click('从已保存剧本打开导演建议审核'); await screen.findByRole('option', { name: '原剧本 · v2' });
  click('准备待审导演建议'); await screen.findByRole('region', { name: '导演建议审核' });
  expect(source.review).not.toHaveBeenCalled(); expect(source.create).not.toHaveBeenCalled(); expect(client.graphs.create).not.toHaveBeenCalled();
  expect((screen.getByRole('button', { name: '审核并采用' }) as HTMLButtonElement).disabled).toBe(true);
  change('采用后的导演文档标题', '审核后的导演草稿');
  expect((screen.getByRole('button', { name: '保存创作图' }) as HTMLButtonElement).disabled).toBe(true);
  click('返回项目列表'); await screen.findByText(/有未保存的创作图／导演输入/); click('继续编辑');
  expect((screen.getByLabelText('采用后的导演文档标题') as HTMLInputElement).value).toBe('审核后的导演草稿');
  fireEvent.click(screen.getByLabelText('已核对来源、场面调度与导演建议；创建独立导演文档')); click('审核并采用');
  await screen.findByText(/已读取人工审核后的原导演草稿/);
  expect((screen.getByLabelText('文档标题') as HTMLInputElement).value).toBe('审核后的导演草稿');
  expect(client.graphs.create).not.toHaveBeenCalled(); expect(source.create).not.toHaveBeenCalled();
  click('核对导演原文档版本'); await screen.findByText(/当前原文档：/);
  await production(); change('节点类型', 'director_plan'); click('明确读取已保存导演与分镜文档');
  await screen.findByRole('option', { name: '审核后的导演草稿 · v3' }); change('原创作文档', document.id); click('添加节点');
  click('保存创作图'); await screen.findByText('创作图已保存 · v1。没有自动创建运行。');
  const saved = await vi.mocked(client.graphs.create).mock.results[0].value as StudioGraphRecord;
  expect(saved.definition.nodes[0].parameters.document_snapshot).toEqual({ id: document.id, version: 3, digest: document.digest });
  vi.mocked(client.graphs.list).mockResolvedValue({ items: [saved] }); vi.mocked(client.graphs.get).mockResolvedValue(saved);
  view.unmount(); mount(); await enter(); change('已保存创作图', saved.id);
  fireEvent.click(await screen.findByRole('button', { name: new RegExp(`选择节点 .*${saved.definition.nodes[0].id}`) })); click('打开导演总控台');
  await screen.findByRole('button', { name: '从已保存剧本打开导演建议审核' }); click('从已保存剧本打开导演建议审核');
  fireEvent.click(await screen.findByRole('button', { name: /待审导演建议.*APPROVED/ }));
  click('核对并打开已采用的导演草稿'); await screen.findByText(/已读取人工审核后的原导演草稿/);
  expect(source.proposal).toHaveBeenCalledWith('proposal-owner', expect.any(AbortSignal));
  expect(source.get).toHaveBeenCalledWith(document.id, expect.any(AbortSignal));
  expect(source.review).toHaveBeenCalledTimes(1); expect(source.propose).toHaveBeenCalledTimes(1);
  expect(source.dispatchModel).not.toHaveBeenCalled(); expect(source.previewModel).not.toHaveBeenCalled(); expect(client.graphs.createRun).not.toHaveBeenCalled();
  expect(client.graphs.dispatchMedia).not.toHaveBeenCalled(); expect(client.graphs.save).not.toHaveBeenCalled();
});
