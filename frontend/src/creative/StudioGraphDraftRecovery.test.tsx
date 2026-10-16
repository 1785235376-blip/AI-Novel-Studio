// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { blankGraph } from './graphDraft';
import type { StudioClient, StudioOverview } from './studioClient';
import type { StudioGraphCreateInput, StudioGraphSaveInput } from './studioGraphTypes';
import { modelCatalog, modelGraph } from './studioGraphModel.testFixtures';
import { studioGraphDraftKey, type StudioGraphDraftOwner, type StudioGraphLocalDraft } from './studioGraphLocalDraft';
import { useStudioGraphEditor, type StudioGraphEditorProps } from './useStudioGraphEditor';

const owner: StudioGraphDraftOwner = { projectId: 'model_project', incarnation: 'file:original', actorId: 'author',
  actorWorkspaceId: '', mode: 'local', workspaceId: '', storylineId: '', branchId: '' };
const key = studioGraphDraftKey(owner), request = `graph_${'1'.repeat(32)}`;
const snapshot = (saved = false): StudioGraphLocalDraft => ({ schema_version: 1, owner, saved_at: '2026-10-16T00:00:00Z', request_id: request,
  base: saved ? { id: 'model_graph', version: 1, definition_digest: 'a'.repeat(64), execution_digest: 'a'.repeat(64) } : null,
  definition: { ...modelGraph().definition, title: '待恢复的作者图' }, uncertain: false });
let client: StudioClient, live: boolean;
let read: StudioGraphEditorProps['read'];
const overview = (): StudioOverview => ({ project: { id: owner.projectId, title: '创作项目', entry_kind: 'NEUTRAL_STUDIO', incarnation: owner.incarnation },
  preferences: { version: 1, intents: [], preset: 'BLANK', custom_intent: '' }, capabilities: { can_mutate: true, can_review: true,
    manual_import: true, manual_export: true, model_required: false, chapter_required: false, media_validator_configured: true, asset_kinds: ['image', 'video', 'audio'], intent_is_permission: false } });
beforeEach(() => {
  localStorage.clear(); live = true; read = async <T,>(work: () => Promise<T>) => work();
  client = { overview: vi.fn(async () => overview()), graphs: {
    catalog: vi.fn(async () => modelCatalog()), list: vi.fn(async () => ({ items: [modelGraph()] })), get: vi.fn(async () => modelGraph()),
    create: vi.fn(async (input: StudioGraphCreateInput) => ({ ...modelGraph(), definition: input.definition })),
    save: vi.fn(async (_id: string, input: StudioGraphSaveInput) => ({ ...modelGraph(), version: 2, definition: input.definition })),
    runs: vi.fn(async () => ({ items: [] })), createRun: vi.fn(), preflight: vi.fn(), modelCapabilities: vi.fn(), previewModel: vi.fn(), dispatchModel: vi.fn(),
  } } as unknown as StudioClient;
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); });
const current = () => live;
function Harness(props: Partial<StudioGraphEditorProps>) {
  const editor = useStudioGraphEditor({ active: true, denied: false, identity: 'captured-author', client, canMutate: true, canReview: true,
    busy: false, externalDirty: false, isCurrent: current, read, mutate: read, draftOwner: owner, ...props });
  return <>{editor.content}{editor.inspector}</>;
}
async function mount(props: Partial<StudioGraphEditorProps> = {}) {
  const result = render(<Harness {...props} />);
  await waitFor(() => expect((screen.getByLabelText('创作图标题') as HTMLInputElement).disabled).toBe(false));
  return result;
}
const title = () => screen.getByLabelText('创作图标题') as HTMLInputElement;
const button = (name: string) => screen.getByRole('button', { name }) as HTMLButtonElement;
const click = (name: string) => fireEvent.click(button(name));
const cache = () => JSON.parse(localStorage.getItem(key)!) as StudioGraphLocalDraft;
const seed = (value = snapshot()) => localStorage.setItem(key, JSON.stringify(value));

describe('mounted text graph autosave and explicit recovery', () => {
  it('autosaves local authoring, survives remount and restores only after a live owner check without executing', async () => {
    const first = await mount();
    fireEvent.change(title(), { target: { value: '未保存的新图' } }); click('添加节点');
    fireEvent.change(screen.getByLabelText('作者输入文本'), { target: { value: '真实作者输入' } });
    await waitFor(() => expect(cache().definition.nodes[0].parameters.text).toBe('真实作者输入'));
    const originalRequest = cache().request_id; first.unmount(); await mount();
    await screen.findByText('发现本机文本图草稿'); expect(title().value).toBe(blankGraph().title);
    expect(client.overview).not.toHaveBeenCalled(); click('核对并恢复本机图草稿');
    await waitFor(() => expect(title().value).toBe('未保存的新图'));
    expect(client.overview).toHaveBeenCalledTimes(1); expect(client.graphs.create).not.toHaveBeenCalled();
    expect(client.graphs.createRun).not.toHaveBeenCalled(); expect(client.graphs.dispatchModel).not.toHaveBeenCalled();
    click('保存创作图'); await screen.findByText('创作图已保存 · v1。没有自动创建运行。');
    expect(client.graphs.create).toHaveBeenCalledWith(expect.objectContaining({ request_id: originalRequest, expected_version: 0 }));
    await waitFor(() => expect(localStorage.getItem(key)).toBeNull());
  });
  it('rechecks a saved baseline exactly and keeps the original CAS version for explicit save', async () => {
    seed(snapshot(true)); await mount(); click('核对并恢复本机图草稿');
    await waitFor(() => expect(title().value).toBe('待恢复的作者图'));
    expect(client.graphs.get).toHaveBeenCalledWith('model_graph');
    expect(client.graphs.previewModel).not.toHaveBeenCalled(); click('保存创作图');
    await screen.findByText('创作图已保存 · v2。没有自动创建运行。');
    expect(client.graphs.save).toHaveBeenCalledWith('model_graph', expect.objectContaining({ expected_version: 1 }));
  });
  it('retains a conflicting cache and exposes its author input without replacing the current editor', async () => {
    seed(snapshot(true)); vi.mocked(client.graphs.get).mockResolvedValue({ ...modelGraph(), version: 2 });
    await mount(); click('核对并恢复本机图草稿');
    await screen.findByText('图服务端版本或摘要已改变；本机草稿保持，请先核对下方作者输入与当前服务端版本。');
    expect(title().value).toBe(blankGraph().title); expect(cache().definition.title).toBe('待恢复的作者图');
    expect((screen.getByLabelText('本机草稿 input · text') as HTMLTextAreaElement).value).toBe('Author source');
    expect(client.graphs.save).not.toHaveBeenCalled();
  });
  it('rejects same-public-ID recreation before reading or resurrecting an old graph', async () => {
    seed(); vi.mocked(client.overview).mockResolvedValue({ ...overview(), project: { ...overview().project, incarnation: 'file:replacement' } });
    const original = await mount(); click('核对并恢复本机图草稿');
    await screen.findByText('项目代次已经改变；旧草稿未恢复到当前项目。');
    expect(client.graphs.get).not.toHaveBeenCalled(); expect(client.graphs.create).not.toHaveBeenCalled();
    original.unmount(); await mount({ draftOwner: { ...owner, incarnation: 'file:replacement' } });
    expect(screen.queryByText('发现本机文本图草稿')).toBeNull(); expect(document.body.textContent).not.toContain('待恢复的作者图');
    expect(localStorage.getItem(key)).not.toBeNull();
  });
  it('does not overwrite an existing local recovery cache with new unreviewed editor input', async () => {
    seed(); await mount(); fireEvent.change(title(), { target: { value: '当前另一个未保存输入' } });
    expect(button('核对并恢复本机图草稿').disabled).toBe(true);
    expect(cache().definition.title).toBe('待恢复的作者图'); expect(title().value).toBe('当前另一个未保存输入');
    fireEvent.click(screen.getByLabelText('确认放弃此本机恢复草稿')); click('放弃本机图恢复草稿');
    await waitFor(() => expect(cache().definition.title).toBe('当前另一个未保存输入'));
  });
  it('preserves a lost-create request identity and uncertainty across reload instead of replaying it', async () => {
    const cached = snapshot(); cached.uncertain = true; seed(cached); await mount(); click('核对并恢复本机图草稿');
    await screen.findByText('保存版本或回执不确定。草稿已保留，不会自动覆盖或重试。');
    expect(client.graphs.create).not.toHaveBeenCalled(); expect(title().disabled).toBe(true);
    click('使用同一请求重试保存'); await screen.findByText('创作图已保存 · v1。没有自动创建运行。');
    expect(client.graphs.create).toHaveBeenCalledWith(expect.objectContaining({ request_id: request, definition: cached.definition }));
  });
  it('fences a late recovery response after the captured authority is retired', async () => {
    seed(); let resolve!: (value: StudioOverview) => void;
    vi.mocked(client.overview).mockImplementationOnce(() => new Promise(done => { resolve = done; }));
    const mounted = await mount(); click('核对并恢复本机图草稿');
    await act(async () => { live = false; mounted.rerender(<Harness denied />); resolve(overview()); });
    expect(document.body.textContent).not.toContain('待恢复的作者图'); expect(client.graphs.create).not.toHaveBeenCalled();
    expect(localStorage.getItem(key)).not.toBeNull();
  });
  it('keeps current input in memory with an explicit warning if browser storage refuses a write', async () => {
    await mount(); vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('quota'); });
    fireEvent.change(title(), { target: { value: '仍然保留在页面' } });
    await screen.findByText('本机图草稿未能保存，请保留此页面；服务端保存仍需明确操作。');
    expect(title().value).toBe('仍然保留在页面'); expect(client.graphs.create).not.toHaveBeenCalled();
  });
  it('detects an externally changed recovery cache before a later autosave or discard can overwrite it', async () => {
    await mount(); fireEvent.change(title(), { target: { value: '当前页面输入' } });
    const foreign = snapshot(); foreign.definition.title = '另一个页面的草稿'; seed(foreign);
    fireEvent.change(title(), { target: { value: '当前页面后续输入' } });
    await screen.findByText('其他页面已更新本机图草稿，原缓存保持；当前输入只保留在本页。');
    expect(cache().definition.title).toBe('另一个页面的草稿'); expect(title().value).toBe('当前页面后续输入');
  });
  it('does not delete a cache updated by another page after the displayed recovery was read', async () => {
    seed(); await mount(); await screen.findByRole('heading', { name: '发现本机文本图草稿' });
    const changed = snapshot(); changed.definition.title = '后来的未审核草稿'; seed(changed);
    fireEvent.click(screen.getByLabelText('确认放弃此本机恢复草稿')); click('放弃本机图恢复草稿');
    await screen.findByText('其他页面已更新本机图草稿，未删除未经核对的新缓存。');
    expect(cache().definition.title).toBe('后来的未审核草稿');
  });
  it('does not persist or offer recovery when the verified incarnation/actor owner is unavailable', async () => {
    await mount({ draftOwner: undefined }); fireEvent.change(title(), { target: { value: '页面内草稿' } });
    expect(localStorage.length).toBe(0); expect(screen.getByText('作者身份或项目代次尚未确认，图草稿只保留在本页。')).toBeTruthy();
  });
});
