// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../api';
import { useStudio } from '../store';
import { useLocalHostSession } from '../localHostSession';
import { IndependentStudioWorkspace } from './IndependentStudioWorkspace';
import { studioClient, type StudioClient, type StudioOverview } from './studioClient';
import type { StudioGraphCatalog, StudioGraphDefinitionId, StudioGraphRecord, StudioGraphCreateInput, StudioGraphSaveInput } from './studioGraphTypes';
import { blankGraph } from './graphDraft';
import { modelCatalog } from './studioGraphModel.testFixtures';

vi.mock('./studioClient', async importOriginal => ({ ...await importOriginal<typeof import('./studioClient')>(), studioClient: vi.fn() }));
const id = 'graph-ui-project', digest = 'a'.repeat(64);
const overview: StudioOverview = { project: { id, title: '独立图项目', entry_kind: 'NEUTRAL_STUDIO' }, preferences: { version: 1, intents: [], preset: 'BLANK', custom_intent: '' }, capabilities: { can_mutate: true, can_review: true, manual_import: true, manual_export: true, model_required: false, chapter_required: false, intent_is_permission: false, media_validator_configured: true, asset_kinds: ['image', 'video', 'audio'] } };
const record = (): StudioGraphRecord => ({ project_id: id, scope: { mode: 'local', novel_id: id }, id: 'saved-graph', version: 1, definition: blankGraph(), definition_digest: digest, execution_digest: digest, can_edit: true, reference_states: [], created_at: '', updated_at: '' });
function catalog(): StudioGraphCatalog {
  const specs: { id: StudioGraphDefinitionId; inputs: [string, 'TEXT' | 'DRAFT' | 'DIRECTOR_NOTES'][]; outputs: [string, 'TEXT' | 'DRAFT' | 'DIRECTOR_NOTES' | 'ASSET_REF'][]; parameter?: 'text' | 'result' | 'note' }[] = [
    { id: 'text_input', inputs: [], outputs: [['text', 'TEXT']], parameter: 'text' },
    { id: 'text_reference', inputs: [['text', 'TEXT']], outputs: [['text', 'TEXT']] },
    { id: 'draft_prepare', inputs: [['text', 'TEXT'], ['direction', 'DIRECTOR_NOTES']], outputs: [['draft', 'DRAFT']] },
    { id: 'manual_transform', inputs: [['text', 'TEXT'], ['direction', 'DIRECTOR_NOTES']], outputs: [['draft', 'DRAFT']], parameter: 'result' },
    { id: 'director_note', inputs: [], outputs: [['direction', 'DIRECTOR_NOTES']], parameter: 'note' },
    { id: 'human_review', inputs: [['draft', 'DRAFT']], outputs: [] },
    { id: 'asset_reference', inputs: [], outputs: [['asset', 'ASSET_REF']] },
  ];
  return { definitions: specs.map(spec => ({ id: spec.id, version: 1,
    inputs: spec.inputs.map(([id, type]) => ({ id, type, required: id !== 'direction', multiple: false })),
    outputs: spec.outputs.map(([id, type]) => ({ id, type, required: false, multiple: false })),
    parameters_schema: { type: 'object', additionalProperties: false, properties: spec.id === 'asset_reference'
      ? { asset_id: { type: 'string', minLength: 1, maxLength: 240 }, version: { type: 'integer', minimum: 1 }, digest: { type: 'string', pattern: '^[a-f0-9]{64}$' }, kind: { type: 'string', enum: ['image', 'video', 'audio'] } }
      : spec.parameter ? { [spec.parameter]: { type: 'string', default: '', maxLength: spec.parameter === 'note' ? 4000 : 8000 } } : {} },
    default_parameters: spec.id === 'asset_reference' ? null : spec.parameter ? { [spec.parameter]: '' } : {},
    executable: spec.id !== 'asset_reference', model_called: false,
    blockers: spec.id === 'asset_reference' ? ['CREATIVE_GRAPH_ATOMIC_INPUT_OWNER_ADAPTER_REQUIRED'] : [] })),
  limits: { nodes: 16, edges: 40, definition_bytes: 96000, output_bytes: 64000, graphs: 25, runs: 100, history: 20, runtime_timeout_seconds: 3600, node_timeout_seconds: 5 },
  capabilities: { local_execution: true, chapter_required: false, model_execution: false, external_reference_execution: false, external_reference_detach: false,
    binary_cache: false, parallel_execution: false, automatic_retry: false, actor_private: true, cache_mode: 'SAME_GRAPH_VERSION_REVIEWED_LOCAL_ONLY' } };
}

let client: StudioClient, rows: StudioGraphRecord[], saved: StudioGraphRecord;
beforeEach(() => {
  localStorage.clear(); saved = record(); rows = [saved];
  useStudio.setState({ novelId: id, chapterId: '', sessionToken: '', actor: undefined, scope: undefined }); useLocalHostSession.setState({ token: '', actorId: '' });
  client = { overview: vi.fn().mockResolvedValue(overview), assets: vi.fn().mockResolvedValue({ items: [] }), graphs: {
    catalog: vi.fn().mockResolvedValue(catalog()), list: vi.fn(async () => ({ items: rows })), get: vi.fn(async () => structuredClone(saved)),
    create: vi.fn(async (input: StudioGraphCreateInput) => { saved = { ...record(), definition: structuredClone(input.definition) }; rows = [saved]; return structuredClone(saved); }),
    save: vi.fn(async (_id: string, input: StudioGraphSaveInput) => { saved = { ...saved, version: saved.version + 1, definition: structuredClone(input.definition) }; return structuredClone(saved); }),
    preflight: vi.fn(), runs: vi.fn().mockResolvedValue({ items: [] }), createRun: vi.fn(), getRun: vi.fn(), action: vi.fn(),
  } } as unknown as StudioClient;
  vi.mocked(studioClient).mockReturnValue(client);
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); });
function mount() {
  const leave = vi.fn(), query = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  const mounted = render(<QueryClientProvider client={query}><IndependentStudioWorkspace projectId={id} context={{ sessionToken: '' }} scope={{ workspace: '本机', project: '独立图项目', storyline: '默认', branch: '主线' }} actor="作者" module="IMAGE" onModuleChange={leave} onProjectChoice={leave} /></QueryClientProvider>);
  return { ...mounted, leave };
}
async function enter() { fireEvent.click(await screen.findByRole('button', { name: '创作图' })); await waitFor(() => expect((screen.getByLabelText('创作图标题') as HTMLInputElement).disabled).toBe(false)); }
const title = () => screen.getByLabelText('创作图标题') as HTMLInputElement;
const click = (name: string) => fireEvent.click(screen.getByRole('button', { name }));
async function open() { fireEvent.change(screen.getByLabelText('已保存创作图'), { target: { value: saved.id } }); await waitFor(() => expect((screen.getByLabelText('已保存创作图') as HTMLSelectElement).value).toBe(saved.id)); }
function add(kind: StudioGraphDefinitionId) { fireEvent.change(screen.getByLabelText('节点类型'), { target: { value: kind } }); click('添加节点'); }

describe('independent studio graph content integration', () => {
  it('promotes only an explicitly added model node to schema 2 and does not preview or dispatch while editing', async () => {
    vi.mocked(client.graphs.catalog).mockResolvedValue(modelCatalog());
    client.graphs.modelCapabilities = vi.fn(); client.graphs.previewModel = vi.fn(); client.graphs.dispatchModel = vi.fn();
    mount(); await enter(); add('text_input'); click('保存创作图'); await screen.findByText('创作图已保存 · v1。没有自动创建运行。');
    expect(saved.definition.schema_version).toBe(1);
    add('text_generate'); fireEvent.change(screen.getByLabelText('本地模型写作指令'), { target: { value: '只生成待审核文本' } });
    fireEvent.change(screen.getByLabelText('最大输出 token'), { target: { value: '256' } }); click('保存创作图');
    await screen.findByText('创作图已保存 · v2。没有自动创建运行。');
    expect(saved.definition.schema_version).toBe(2); expect(saved.definition.nodes.at(-1)?.parameters).toEqual({ instruction: '只生成待审核文本', max_output_tokens: 256 });
    expect(client.graphs.modelCapabilities).not.toHaveBeenCalled(); expect(client.graphs.previewModel).not.toHaveBeenCalled(); expect(client.graphs.dispatchModel).not.toHaveBeenCalled();
  });
  it('keeps graphs lazy until an explicit content choice, with unchanged eight shell modules', async () => {
    mount(); await screen.findByRole('button', { name: '上传资产' });
    expect(client.graphs.catalog).not.toHaveBeenCalled(); expect(screen.getAllByRole('tab')).toHaveLength(8);
    await enter(); expect(client.graphs.catalog).toHaveBeenCalledTimes(1); expect(client.graphs.list).toHaveBeenCalledTimes(1);
    expect(client.graphs.createRun).not.toHaveBeenCalled(); expect(client.graphs.action).not.toHaveBeenCalled();
  });
  it('saves an empty disconnected definition through the scoped owner and reopens it without creating a run', async () => {
    const mounted = mount(); await enter(); fireEvent.change(title(), { target: { value: '空白手工图' } }); click('保存创作图');
    await screen.findByText('创作图已保存 · v1。没有自动创建运行。');
    expect(client.graphs.create).toHaveBeenCalledWith({ expected_version: 0, request_id: expect.any(String), definition: { ...blankGraph(), title: '空白手工图' } });
    mounted.unmount(); mount(); await enter(); await open(); expect(title().value).toBe('空白手工图'); expect(client.graphs.createRun).not.toHaveBeenCalled();
  });
  it('allows optional Director removal and bounded undo without adding a chapter or starting a job', async () => {
    mount(); await enter(); add('text_input'); fireEvent.change(screen.getByLabelText('作者输入文本'), { target: { value: '保留作者文本' } }); add('director_note');
    fireEvent.change(screen.getByLabelText('可选导演备注'), { target: { value: '完全可选' } }); click('移除当前节点'); click('保存创作图');
    await screen.findByText('创作图已保存 · v1。没有自动创建运行。'); expect(saved.definition.nodes.map(node => node.definition_id)).toEqual(['text_input']); expect(saved.definition.edges).toEqual([]);
    add('director_note'); click('撤销图编辑'); click('保存创作图'); expect(client.graphs.save).not.toHaveBeenCalled(); expect(client.graphs.createRun).not.toHaveBeenCalled();
  });
  it('retains the CAS-conflicted draft until an explicit checked adoption of the separately fetched server version', async () => {
    mount(); await enter(); await open(); fireEvent.change(title(), { target: { value: '我的未保存输入' } });
    vi.mocked(client.graphs.save).mockRejectedValueOnce(new ApiError({ status: 409, code: 'CREATIVE_GRAPH_VERSION_CONFLICT', message: '版本冲突' }));
    click('保存创作图'); await screen.findByText('保存版本或回执不确定。草稿已保留，不会自动覆盖或重试。'); expect(title().value).toBe('我的未保存输入');
    saved = { ...saved, version: 2, definition: { ...saved.definition, title: '另一保存版本' } }; click('核对图服务端版本'); await screen.findByRole('region', { name: '图服务端版本' });
    expect(title().value).toBe('我的未保存输入'); expect((screen.getByRole('button', { name: '采用图服务端版本' }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByLabelText('确认放弃当前图草稿，采用已核对服务端版本')); click('采用图服务端版本'); expect(title().value).toBe('另一保存版本'); expect(client.graphs.save).toHaveBeenCalledTimes(1);
  });
  it('protects unsaved graph input when leaving the graph content or fixed module switcher', async () => {
    const { leave } = mount(); await enter(); fireEvent.change(title(), { target: { value: '尚未保存的图' } }); click('素材工作区');
    await screen.findByText('有未保存的创作图输入。可以继续编辑，或确认放弃后离开。'); click('继续编辑'); expect(title().value).toBe('尚未保存的图');
    fireEvent.click(within(screen.getByRole('tablist', { name: '创作模块' })).getByRole('tab', { name: '视频' })); expect(leave).not.toHaveBeenCalled();
    fireEvent.click(screen.getByLabelText('确认放弃未保存输入')); click('确认离开'); expect(leave).toHaveBeenCalledTimes(1);
  });
  it('clears private graph draft after authoritative access denial and rejects a late scope response', async () => {
    mount(); await enter(); fireEvent.change(title(), { target: { value: '私人草稿' } });
    vi.mocked(client.graphs.catalog).mockRejectedValueOnce(new ApiError({ status: 403, code: 'FORBIDDEN', message: '权限失效' })); click('刷新创作图目录');
    await screen.findByText('当前会话无权访问此项目'); expect(screen.queryByLabelText('创作图标题')).toBeNull(); expect(document.body.textContent).not.toContain('私人草稿');
  });
  it('does not replace the editor when an opened graph resolves after the selected project changes', async () => {
    let resolve!: (value: StudioGraphRecord) => void; vi.mocked(client.graphs.get).mockImplementationOnce(() => new Promise(done => { resolve = done; }));
    mount(); await enter(); fireEvent.change(screen.getByLabelText('已保存创作图'), { target: { value: saved.id } });
    useStudio.setState({ novelId: 'other-project' }); const late = { ...saved, definition: { ...saved.definition, title: '旧范围私人图' } }; await act(async () => resolve(late));
    expect(title().value).toBe('独立创作图'); expect(document.body.textContent).not.toContain('旧范围私人图');
  });
  it('displays redacted saved references without enabling a full-save or deletion roundtrip', async () => {
    saved = { ...saved, can_edit: false, reference_states: [{ node_id: 'hidden_ref', state: 'UNAVAILABLE' }], definition: { ...blankGraph(), nodes: [{ id: 'hidden_ref', definition_id: 'asset_reference', definition_version: 1, enabled: true, position: { x: 0, y: 0 }, parameters: {} }] } }; rows = [saved];
    mount(); await enter(); await open(); await screen.findByText('图中包含不可见的资产引用，当前仅可查看。原绑定不会被省略、删除或重新保存；需恢复访问后重新读取。');
    expect(title().disabled).toBe(true); expect((screen.getByRole('button', { name: '保存创作图' }) as HTMLButtonElement).disabled).toBe(true); expect(client.graphs.save).not.toHaveBeenCalled();
  });
});
