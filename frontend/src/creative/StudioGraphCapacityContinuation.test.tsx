// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../api';
import type { StudioClient, StudioOverview } from './studioClient';
import type { StudioGraphCreateInput, StudioGraphRecord, StudioGraphSaveInput } from './studioGraphTypes';
import { modelCatalog, modelGraph } from './studioGraphModel.testFixtures';
import { studioGraphDraftKey, type StudioGraphDraftOwner, type StudioGraphLocalDraft } from './studioGraphLocalDraft';
import { useStudioGraphEditor, type StudioGraphEditorProps } from './useStudioGraphEditor';

const owner: StudioGraphDraftOwner = { projectId: 'model_project', incarnation: 'file:original', actorId: 'author', actorWorkspaceId: '', mode: 'local', workspaceId: '', storylineId: '', branchId: '' };
const key = studioGraphDraftKey(owner);
let client: StudioClient, original: StudioGraphRecord, live: boolean, syncBusy: boolean;
const read = async <T,>(work: () => Promise<T>) => work();
const current = () => live;
const busy = () => syncBusy;
const selection = vi.fn();
const cache = () => JSON.parse(localStorage.getItem(key)!) as StudioGraphLocalDraft;
const title = () => screen.getByLabelText('创作图标题') as HTMLInputElement;
const button = (name: string) => screen.getByRole('button', { name }) as HTMLButtonElement;
const click = (name: string) => fireEvent.click(button(name));
const consent = () => fireEvent.click(screen.getByLabelText('确认将完整当前草稿准备为独立新图，保留原图与历史'));
const prepare = () => { consent(); click('准备独立新图草稿'); };
const quota = (message: string) => new ApiError({ status: 422, code: 'EXPERIMENTAL_INVALID', message });
beforeEach(() => {
  localStorage.clear(); live = true; syncBusy = false; selection.mockClear();
  original = modelGraph();
  original.capacity = { history_used: 20, history_limit: 20, record_bytes: 100000, record_limit_bytes: 2000000 };
  original.definition.presentation = { comment: '原作者注释', groups: [{ id: 'scene', name: '雨夜', node_ids: ['input', 'generate'] }],
    view: { show_grid: false, snap: true, grid_step: 32, show_minimap: false },
    notes: [{ id: 'note_one', text: '雨夜中景', position: { x: -300, y: 150 } }, { id: 'note_two', text: '窗前特写', position: { x: 400, y: 250 } }] };
  original.definition.viewport = { x: -250, y: 500, zoom: 0.75 };
  client = { overview: vi.fn(async () => ({ project: { id: owner.projectId, incarnation: owner.incarnation }, capabilities: { can_mutate: true } } as StudioOverview)), graphs: {
    catalog: vi.fn(async () => modelCatalog()), list: vi.fn(async () => ({ items: [structuredClone(original)] })), get: vi.fn(async () => structuredClone(original)),
    create: vi.fn(async (input: StudioGraphCreateInput) => ({ ...structuredClone(original), id: 'independent_graph', version: 1, definition: input.definition,
      capacity: { ...original.capacity!, history_used: 0 } })),
    save: vi.fn(async (_id: string, input: StudioGraphSaveInput) => ({ ...structuredClone(original), version: 2, definition: input.definition })),
    runs: vi.fn(async () => ({ items: [] })), createRun: vi.fn(), preflight: vi.fn(), modelCapabilities: vi.fn(), previewModel: vi.fn(), dispatchModel: vi.fn(),
  } } as unknown as StudioClient;
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); });
function Harness(props: Partial<StudioGraphEditorProps>) {
  const editor = useStudioGraphEditor({ active: true, denied: false, identity: 'captured-author', client, canMutate: true, canReview: true,
    busy: false, externalDirty: false, isCurrent: current, isBusy: busy, read, mutate: read, draftOwner: owner, onSelectionChange: selection, ...props });
  return <>{editor.content}{editor.inspector}</>;
}
async function mount(props: Partial<StudioGraphEditorProps> = {}) {
  const mounted = render(<Harness {...props} />);
  await waitFor(() => expect(title().disabled).toBe(false));
  fireEvent.change(screen.getByLabelText('已保存创作图'), { target: { value: original.id } });
  await waitFor(() => expect(title().value).toBe(original.definition.title));
  return mounted;
}

describe('original graph capacity and explicit independent draft preparation', () => {
  it('shows server usage, keeps the full draft editable at history capacity and writes only on original Save', async () => {
    await mount(); expect(screen.getByText(/历史 20 \/ 20；记录 100000 \/ 2000000 字节/)).toBeTruthy();
    fireEvent.change(title(), { target: { value: '作者最新未保存修改' } });
    expect(title().disabled).toBe(false); expect(button('保存创作图').disabled).toBe(true);
    consent(); fireEvent.change(title(), { target: { value: '作者再次修改' } });
    expect(button('准备独立新图草稿').disabled).toBe(true);
    prepare(); expect(client.graphs.create).not.toHaveBeenCalled(); expect(client.graphs.save).not.toHaveBeenCalled();
    expect(selection).toHaveBeenLastCalledWith({});
    expect(screen.getByLabelText('独立新图来源上下文').textContent).toContain(original.id);
    const expected = { ...original.definition, title: '作者再次修改' };
    await waitFor(() => expect(cache().definition).toEqual(expected)); expect(cache().base).toBeNull();
    const request = cache().request_id;
    click('保存创作图'); await screen.findByText(/独立新图已保存 · v1/);
    expect(client.graphs.create).toHaveBeenCalledTimes(1);
    expect(client.graphs.create).toHaveBeenCalledWith({ request_id: request, expected_version: 0, definition: expected });
    expect(client.graphs.save).not.toHaveBeenCalled(); expect(client.graphs.createRun).not.toHaveBeenCalled();
    expect(client.graphs.preflight).not.toHaveBeenCalled(); expect(client.graphs.dispatchModel).not.toHaveBeenCalled();
    expect(original.definition.title).toBe('Explicit local model graph');
    expect(selection).toHaveBeenLastCalledWith({ graphId: 'independent_graph' });
    click('返回原图（保留原历史）'); await waitFor(() => expect(title().value).toBe(original.definition.title));
    expect(screen.queryByLabelText('独立新图来源上下文')).toBeNull();
  });
  it('distinguishes unavailable capacity from zero usage', async () => {
    delete original.capacity; const mounted = await mount();
    expect(screen.getByText(/剩余保存容量未知/)).toBeTruthy();
    mounted.unmount(); original.capacity = { history_used: 0, history_limit: 20, record_bytes: 1200, record_limit_bytes: 2000000 };
    await mount(); expect(screen.getByText(/历史 0 \/ 20；记录 1200/)).toBeTruthy(); expect(screen.queryByText(/剩余保存容量未知/)).toBeNull();
  });
  it.each(['CREATIVE_GRAPH_HISTORY_CAPACITY', 'CREATIVE_GRAPH_SCOPE_CAPACITY', 'CREATIVE_GRAPH_COLLECTION_CAPACITY'])('keeps input editable after a known atomic quota refusal: %s', async code => {
    delete original.capacity; vi.mocked(client.graphs.save).mockRejectedValueOnce(quota(code));
    await mount(); fireEvent.change(title(), { target: { value: '拒绝后仍保留' } }); click('保存创作图');
    await waitFor(() => expect(screen.getAllByText(/草稿仍保留/).length).toBeGreaterThan(0));
    expect(title().value).toBe('拒绝后仍保留'); expect(title().disabled).toBe(false);
    prepare(); expect(title().value).toBe('拒绝后仍保留'); expect(client.graphs.create).not.toHaveBeenCalled();
  });
  it('keeps the full unsaved independent draft and request after a known create refusal', async () => {
    await mount(); prepare(); const snapshot = cache(); vi.mocked(client.graphs.create).mockRejectedValueOnce(quota('CREATIVE_GRAPH_SCOPE_CAPACITY'));
    click('保存创作图'); await screen.findByText(/新图也受同一范围容量限制/);
    expect(title().disabled).toBe(false); expect(cache().definition).toEqual(snapshot.definition);
    expect(cache().base).toBeNull(); expect(cache().request_id).toBe(snapshot.request_id);
    expect(screen.getByLabelText('独立新图来源上下文')).toBeTruthy();
    click('保存创作图'); await screen.findByText(/独立新图已保存 · v1/);
    expect(vi.mocked(client.graphs.create).mock.calls[0][0]).toEqual(vi.mocked(client.graphs.create).mock.calls[1][0]);
  });
  it('freezes an unknown create and recovers the exact base-null snapshot and request after remount', async () => {
    const mounted = await mount(); prepare(); const snapshot = cache();
    vi.mocked(client.graphs.create).mockRejectedValueOnce(new ApiError({ status: 0, code: 'NETWORK', message: '回执丢失' }));
    click('保存创作图'); await screen.findByText('保存版本或回执不确定。草稿已保留，不会自动覆盖或重试。');
    expect(title().disabled).toBe(true); expect(screen.queryByRole('button', { name: '准备独立新图草稿' })).toBeNull();
    expect(cache()).toMatchObject({ base: null, uncertain: true, request_id: snapshot.request_id, definition: snapshot.definition });
    mounted.unmount(); render(<Harness />); await screen.findByText('发现本机文本图草稿');
    click('核对并恢复本机图草稿'); await screen.findByText('保存版本或回执不确定。草稿已保留，不会自动覆盖或重试。');
    expect(client.graphs.create).toHaveBeenCalledTimes(1); click('使用同一请求重试保存');
    await screen.findByText('创作图已保存 · v1。没有自动创建运行。');
    expect(vi.mocked(client.graphs.create).mock.calls[0][0]).toEqual(vi.mocked(client.graphs.create).mock.calls[1][0]);
    expect(vi.mocked(client.graphs.create).mock.calls[1][0]).toMatchObject({ request_id: snapshot.request_id, expected_version: 0, definition: snapshot.definition });
  });
  it('checks current identity and the synchronous busy fence again at preparation', async () => {
    await mount(); consent(); syncBusy = true; click('准备独立新图草稿');
    expect(screen.queryByLabelText('独立新图来源上下文')).toBeNull(); syncBusy = false; live = false; click('准备独立新图草稿');
    expect(screen.queryByLabelText('独立新图来源上下文')).toBeNull(); expect(client.graphs.create).not.toHaveBeenCalled();
  });
  it('retains stale version labels and exact pins without upgrading or approving them', async () => {
    original.definition.nodes.push({ id: 'asset', definition_id: 'asset_reference', definition_version: 1, enabled: true, position: { x: 0, y: 300 },
      parameters: { asset_id: 'original_asset', version: 2, digest: 'b'.repeat(64), kind: 'image' } });
    original.reference_states = [{ node_id: 'asset', state: 'STALE' }];
    await mount(); prepare(); expect(screen.getByLabelText('独立新图来源上下文').textContent).toContain('STALE');
    click('保存创作图'); await screen.findByText(/独立新图已保存 · v1/);
    expect(vi.mocked(client.graphs.create).mock.calls[0][0].definition.nodes.at(-1)).toEqual(original.definition.nodes.at(-1));
    expect(client.graphs.createRun).not.toHaveBeenCalled();
  });
  it('retires the independent definition and origin on denial without transmitting it', async () => {
    const mounted = await mount(); prepare(); live = false; mounted.rerender(<Harness denied />);
    expect(screen.queryByLabelText('独立新图来源上下文')).toBeNull();
    expect(document.body.textContent).not.toContain('original_asset'); expect(client.graphs.create).not.toHaveBeenCalled();
  });
});
