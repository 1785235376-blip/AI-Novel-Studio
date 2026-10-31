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
import type { StudioGraphCreateInput, StudioGraphRecord, StudioGraphSaveInput } from './studioGraphTypes';
import { blankGraph } from './graphDraft';
import { imageGraphCatalog, imageGraphProject, imageGraphRecord } from './studioImageGraph.testFixtures';

import { studioProductionClient } from './studioProductionClient';
import { mediaProviderKey } from './useStudioMediaExecution';
vi.mock('./studioProductionClient', async original => ({ ...await original<typeof import('./studioProductionClient')>(), studioProductionClient: vi.fn() }));
const pickerRow = { operation_id: 'm5.image.reference' as const, provider_id: 'image-provider', model_id: 'image-model', local: true, route_digest: 'a'.repeat(64), capability: 'MEDIA', supported_parameters: [], readiness: 'CONFIGURED_NOT_VERIFIED' as const };
vi.mock('./studioClient', async importOriginal => ({ ...await importOriginal<typeof import('./studioClient')>(), studioClient: vi.fn() }));
let client: StudioClient, rows: StudioGraphRecord[], saved: StudioGraphRecord;

function originalCatalog() {
  const value = imageGraphCatalog(); value.definitions = value.definitions.filter(row => !row.id.startsWith('image_'));
  delete value.capabilities.image_graph; delete value.capabilities.image_graph_schema_version; delete value.capabilities.image_graph_evidence;
  delete value.capabilities.image_reference_semantics; delete value.capabilities.image_upscale_execution; return value;
}
beforeEach(() => {
  vi.mocked(studioProductionClient).mockReturnValue({ providers: vi.fn().mockResolvedValue([pickerRow]) } as unknown as ReturnType<typeof studioProductionClient>);
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
  Object.defineProperty(window, 'innerWidth', { value: 1440, configurable: true });
  const query = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={query}><IndependentStudioWorkspace projectId={imageGraphProject} context={{ sessionToken: '' }} scope={{ workspace: '本机', project: 'Image graph fixture', storyline: '默认', branch: '主线' }}
    actor="作者" module="IMAGE" onModuleChange={vi.fn()} onProjectChoice={vi.fn()} /></QueryClientProvider>);
}
const click = (name: string) => fireEvent.click(screen.getByRole('button', { name }));
const change = (name: string, value: string) => fireEvent.change(screen.getByLabelText(name), { target: { value } });
async function enter() { fireEvent.click(await screen.findByRole('button', { name: '创作图' })); await waitFor(() => expect((screen.getByLabelText('创作图标题') as HTMLInputElement).disabled).toBe(false));fireEvent.click(screen.getByRole('button', { name: '执行画布' })); }
async function readImageCatalog() { click('明确读取图片节点目录'); await screen.findByRole('region', { name: '图片图版本确认' }); }
function upgrade() { fireEvent.click(screen.getByLabelText('确认将当前兼容草稿采用为图片图 v4，保持原资产绑定与人工审核')); click('明确采用图片图 v4'); }
function add(kind: string) { change('节点类型', kind); click('添加节点'); }
function expectNoExecution() { expect(client.graphs.createRun).not.toHaveBeenCalled(); expect(client.graphs.previewMedia).not.toHaveBeenCalled(); expect(client.graphs.dispatchMedia).not.toHaveBeenCalled(); expect(client.graphs.executeMedia).not.toHaveBeenCalled(); }
describe('image Graph authoring through original controller and mounted workspace', () => {
  it("migration: saves weighted reference and prompt parameters through original actions with no arbitrary JSON or direct generation", async () => {
    mount(); await enter(); await readImageCatalog(); upgrade(); add('image_reference');
    fireEvent.click(screen.getByLabelText('明确使用参考端口 source_1')); change('参考权重 source_1', '0.75'); add('image_prompt'); change('图片提示词', 'Image controller prompt');
    add('image_generate'); change('图片操作', 'm5.image.reference'); click('读取节点服务配置'); await screen.findByRole('option', { name: 'image-provider · image-model · 本地' }); change('节点服务商与模型', mediaProviderKey(pickerRow));
    expect(screen.queryByLabelText('宽度')).toBeNull(); expect(screen.queryByLabelText('高度')).toBeNull(); expect(screen.queryByLabelText('图片规格')).toBeNull(); expect(screen.queryByLabelText('图片质量')).toBeNull();
    change('重绘强度（大于 0 至 1）', '0.5'); click('保存创作图'); await screen.findByText('创作图已保存 · v1。没有自动创建运行。');
    const definition = vi.mocked(client.graphs.create).mock.calls[0][0].definition;
    expect(definition.schema_version).toBe(4); expect(definition.nodes[0].parameters.bindings).toEqual([{ port: 'source_1', weight: 0.75 }]);
    expect(definition.nodes[1].parameters.prompt).toBe('Image controller prompt'); expect(definition.nodes[2].parameters.parameters).toEqual({ denoising_strength: 0.5 }); expectNoExecution();
  });
});
