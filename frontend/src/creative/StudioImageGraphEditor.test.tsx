// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useStudio } from '../store';
import { bindLocalHostSession, useLocalHostSession } from '../localHostSession';
import { IndependentStudioWorkspace } from './IndependentStudioWorkspace';
import { studioClient, type StudioClient, type StudioOverview } from './studioClient';
import type { StudioGraphCreateInput, StudioGraphRecord, StudioGraphSaveInput } from './studioGraphTypes';
import { blankGraph } from './graphDraft';
import { imageGraphCatalog, imageGraphProject, imageGraphRecord } from './studioImageGraph.testFixtures';

vi.mock('./studioClient', async importOriginal => ({ ...await importOriginal<typeof import('./studioClient')>(), studioClient: vi.fn() }));
let client: StudioClient, rows: StudioGraphRecord[], saved: StudioGraphRecord;
const deferred = <T,>() => { let resolve!: (value: T) => void; const promise = new Promise<T>(yes => { resolve = yes; }); return { promise, resolve }; };
function originalCatalog() {
  const value = imageGraphCatalog(); value.definitions = value.definitions.filter(row => !row.id.startsWith('image_'));
  delete value.capabilities.image_graph; delete value.capabilities.image_graph_schema_version; delete value.capabilities.image_graph_evidence;
  delete value.capabilities.image_reference_semantics; delete value.capabilities.image_upscale_execution; return value;
}
beforeEach(() => {
  localStorage.clear(); useStudio.setState({ novelId: imageGraphProject, sessionToken: '', actor: undefined, scope: undefined });
  useLocalHostSession.setState({ token: 'image-graph-host', actorId: '' }); saved = { ...imageGraphRecord(), definition: blankGraph(), reference_states: [] }; rows = [saved];
  const overview: StudioOverview = { project: { id: imageGraphProject, title: 'Image graph fixture', entry_kind: 'NEUTRAL_STUDIO' }, preferences: { version: 1, intents: [], preset: 'IMAGE', custom_intent: '' },
    capabilities: { can_mutate: true, can_review: true, manual_import: true, manual_export: true, model_required: false, chapter_required: false, intent_is_permission: false, media_validator_configured: true, asset_kinds: ['image', 'video', 'audio'] } };
  client = { overview: vi.fn().mockResolvedValue(overview), assets: vi.fn().mockResolvedValue({ items: [] }), graphs: {
    catalog: vi.fn().mockResolvedValue(originalCatalog()), imageCatalog: vi.fn().mockResolvedValue(imageGraphCatalog()), list: vi.fn(async () => ({ items: rows })),
    get: vi.fn(async () => structuredClone(saved)), create: vi.fn(async (input: StudioGraphCreateInput) => { saved = { ...saved, definition: structuredClone(input.definition) }; return structuredClone(saved); }),
    save: vi.fn(async (_id: string, input: StudioGraphSaveInput) => { saved = { ...saved, version: saved.version + 1, definition: structuredClone(input.definition) }; return structuredClone(saved); }),
    preflight: vi.fn(), runs: vi.fn().mockResolvedValue({ items: [] }), createRun: vi.fn(), getRun: vi.fn(), action: vi.fn(), previewMedia: vi.fn(), dispatchMedia: vi.fn(), executeMedia: vi.fn(),
  } } as unknown as StudioClient; vi.mocked(studioClient).mockReturnValue(client);
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); });
function mount() {
  const query = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={query}><IndependentStudioWorkspace projectId={imageGraphProject} context={{ sessionToken: '' }} scope={{ workspace: '本机', project: 'Image graph fixture', storyline: '默认', branch: '主线' }}
    actor="作者" module="IMAGE" onModuleChange={vi.fn()} onProjectChoice={vi.fn()} /></QueryClientProvider>);
}
const click = (name: string) => fireEvent.click(screen.getByRole('button', { name }));
const change = (name: string, value: string) => fireEvent.change(screen.getByLabelText(name), { target: { value } });
async function enter() { fireEvent.click(await screen.findByRole('button', { name: '创作图' })); await waitFor(() => expect((screen.getByLabelText('创作图标题') as HTMLInputElement).disabled).toBe(false)); }
async function readImageCatalog() { click('明确读取图片节点目录'); await screen.findByRole('region', { name: '图片图版本确认' }); }
function upgrade() { fireEvent.click(screen.getByLabelText('确认将当前兼容草稿采用为图片图 v4，保持原资产绑定与人工审核')); click('明确采用图片图 v4'); }
function add(kind: string) { change('节点类型', kind); click('添加节点'); }
function expectNoExecution() { expect(client.graphs.createRun).not.toHaveBeenCalled(); expect(client.graphs.previewMedia).not.toHaveBeenCalled(); expect(client.graphs.dispatchMedia).not.toHaveBeenCalled(); expect(client.graphs.executeMedia).not.toHaveBeenCalled(); }
describe('image Graph authoring through original controller and mounted workspace', () => {
  it('requires explicit catalog read then separate schema consent and never dispatches while authoring', async () => {
    mount(); await enter(); expect(client.graphs.imageCatalog).not.toHaveBeenCalled(); expect(screen.queryByRole('option', { name: '图片生成（需分别确认）' })).toBeNull();
    await readImageCatalog(); expect(screen.getByText(/当前图格式：v1/)).toBeTruthy(); expect((screen.getByRole('button', { name: '明确采用图片图 v4' }) as HTMLButtonElement).disabled).toBe(true);
    upgrade(); expect(screen.getByText(/当前图格式：v4/)).toBeTruthy(); expect(screen.getByRole('option', { name: '图片生成（需分别确认）' })).toBeTruthy();
    expect(screen.queryByRole('option', { name: '时间线剪辑与导出（需分别确认）' })).toBeNull(); expect(screen.queryByRole('option', { name: '媒体制作（需分别确认）' })).toBeNull(); expectNoExecution();
  });
  it('binds consent to the current draft and refuses to remove incompatible old nodes during upgrade', async () => {
    mount(); await enter(); add('draft_prepare'); await readImageCatalog();
    fireEvent.click(screen.getByLabelText('确认将当前兼容草稿采用为图片图 v4，保持原资产绑定与人工审核')); change('创作图标题', 'Edited after consent');
    expect((screen.getByRole('button', { name: '明确采用图片图 v4' }) as HTMLButtonElement).disabled).toBe(true);
    upgrade(); expect(await screen.findByText(/当前图含图片图 v4 不支持的节点/)).toBeTruthy(); expect(screen.getByText(/当前图格式：v1/)).toBeTruthy();
    click('保存创作图'); await screen.findByText('创作图已保存 · v1。没有自动创建运行。');
    expect(vi.mocked(client.graphs.create).mock.calls[0][0].definition.nodes[0].definition_id).toBe('draft_prepare'); expectNoExecution();
  });
  it('saves weighted reference and prompt parameters through original actions with no arbitrary JSON or direct generation', async () => {
    mount(); await enter(); await readImageCatalog(); upgrade(); add('image_reference');
    fireEvent.click(screen.getByLabelText('明确使用参考端口 source_1')); change('参考权重 source_1', '0.75'); add('image_prompt'); change('图片提示词', 'Image controller prompt');
    add('image_generate'); change('图片操作', 'm5.image.reference'); change('图片服务商 ID', 'image-provider'); change('图片模型 ID', 'image-model');
    expect(screen.queryByLabelText('宽度')).toBeNull(); expect(screen.queryByLabelText('高度')).toBeNull(); expect(screen.queryByLabelText('图片规格')).toBeNull(); expect(screen.queryByLabelText('图片质量')).toBeNull();
    change('重绘强度（大于 0 至 1）', '0.5'); click('保存创作图'); await screen.findByText('创作图已保存 · v1。没有自动创建运行。');
    const definition = vi.mocked(client.graphs.create).mock.calls[0][0].definition;
    expect(definition.schema_version).toBe(4); expect(definition.nodes[0].parameters.bindings).toEqual([{ port: 'source_1', weight: 0.75 }]);
    expect(definition.nodes[1].parameters.prompt).toBe('Image controller prompt'); expect(definition.nodes[2].parameters.parameters).toEqual({ denoising_strength: 0.5 }); expectNoExecution();
  });
  it('opens a saved schema 4 via the same owner image catalog without upgrading or executing an old graph', async () => {
    saved = imageGraphRecord(); rows = [saved]; mount(); await enter(); change('已保存创作图', saved.id); await screen.findByText(/当前图格式：v4/);
    expect(client.graphs.imageCatalog).toHaveBeenCalledTimes(1); expect(client.graphs.create).not.toHaveBeenCalled(); expect(client.graphs.save).not.toHaveBeenCalled(); expectNoExecution();
  });
  it('ignores an image catalog arriving after a same-token Host identity replacement', async () => {
    const late = deferred<ReturnType<typeof imageGraphCatalog>>(); vi.mocked(client.graphs.imageCatalog!).mockReturnValue(late.promise);
    mount(); await enter(); click('明确读取图片节点目录'); await waitFor(() => expect(client.graphs.imageCatalog).toHaveBeenCalledTimes(1));
    act(() => bindLocalHostSession('image-graph-host', { session_mode: 'LOCAL_HOST', actor_id: 'replacement-author' })); await act(async () => late.resolve(imageGraphCatalog()));
    expect(screen.queryByRole('region', { name: '图片图版本确认' })).toBeNull(); expect(client.graphs.create).not.toHaveBeenCalled(); expectNoExecution();
  });
});
