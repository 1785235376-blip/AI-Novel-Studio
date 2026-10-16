// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { blankGraph } from './graphDraft';
import { StudioGraphDraftRecovery } from './StudioGraphDraftRecovery';
import { modelCatalog, modelGraph } from './studioGraphModel.testFixtures';
import type { StudioClient, StudioOverview } from './studioClient';
import { graphDraftRecoverable, readStudioGraphLocalDraft, studioGraphDraftKey, type StudioGraphDraftOwner, type StudioGraphLocalDraft } from './studioGraphLocalDraft';
import { useStudioGraphEditorController, type StudioGraphEditorController } from './useStudioGraphEditorController';

const owner: StudioGraphDraftOwner = { projectId: 'model_project', incarnation: 'file:original', actorId: 'author',
  actorWorkspaceId: '', mode: 'local', workspaceId: '', storylineId: '', branchId: '' };
const key = studioGraphDraftKey(owner);
const noteText = '中文便笺\n第二行 🪷\n<img src=x onerror="alert(1)">';
const comment = '缓存图注释\n<script>alert(1)</script>';
const snapshot = (count = 2): StudioGraphLocalDraft => ({ schema_version: 1, owner, saved_at: '2026-10-16T00:00:00Z',
  request_id: `graph_${'1'.repeat(32)}`, base: null, uncertain: false,
  definition: { ...modelGraph().definition, presentation: { comment, notes: Array.from({ length: count }, (_, i) => ({
    id: `n${i}`, text: i === 0 ? noteText : i === 1 ? '' : `笺${i}`, position: { x: i, y: i === 0 ? 0 : -i },
  })) } } });
let client: StudioClient, current: boolean, controller: StudioGraphEditorController;
const live = () => current;
const read = async <T,>(work: () => Promise<T>) => work();
const overview = () => ({ project: { id: owner.projectId, incarnation: owner.incarnation }, capabilities: { can_mutate: true } }) as StudioOverview;
function Harness({ denied = false }: { denied?: boolean }) {
  controller = useStudioGraphEditorController({ active: true, denied, identity: 'author', client, canMutate: true, canReview: true,
    busy: false, externalDirty: false, isCurrent: live, read, mutate: read, draftOwner: owner });
  return <StudioGraphDraftRecovery controller={controller} />;
}
const seed = (value: StudioGraphLocalDraft) => { const raw = JSON.stringify(value); localStorage.setItem(key, raw); return raw; };
const click = (name: string) => fireEvent.click(screen.getByRole('button', { name }));
const field = (name: string) => screen.getByLabelText(name) as HTMLTextAreaElement;
async function mount() {
  const view = render(<Harness />);
  await screen.findByRole('heading', { name: '发现本机文本图草稿' });
  fireEvent.click(screen.getByText('查看待恢复的作者输入'));
  return view;
}
function noWrites() {
  for (const fn of [client.graphs.create, client.graphs.save, client.graphs.createRun, client.graphs.preflight,
    client.graphs.previewModel, client.graphs.dispatchModel]) expect(fn).not.toHaveBeenCalled();
}
beforeEach(() => {
  localStorage.clear(); current = true;
  client = { overview: vi.fn(async () => overview()), graphs: {
    catalog: vi.fn(async () => modelCatalog()), list: vi.fn(async () => ({ items: [modelGraph()] })), get: vi.fn(async () => modelGraph()),
    runs: vi.fn(async () => ({ items: [] })), create: vi.fn(), save: vi.fn(), createRun: vi.fn(), preflight: vi.fn(), previewModel: vi.fn(), dispatchModel: vi.fn(),
  } } as unknown as StudioClient;
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

describe('cached presentation recovery inspection through the original controller', () => {
  it('shows full Chinese, multiline and empty note text plus literal comment HTML read-only without reads or writes', async () => {
    const original = seed(snapshot()); await mount();
    expect(screen.getByText('本机草稿 · 2 张空间便笺')).toBeTruthy();
    expect(screen.getByText(/未与当前服务端内容逐项比对/)).toBeTruthy();
    for (const [label, text] of [['本机草稿便笺 n0', noteText], ['本机草稿便笺 n1', ''], ['本机草稿 · 图注释', comment]]) {
      expect(field(label).value).toBe(text); expect(field(label).readOnly).toBe(true);
    }
    expect(document.querySelector('script, img')).toBeNull();
    expect(client.overview).not.toHaveBeenCalled(); expect(client.graphs.get).not.toHaveBeenCalled();
    expect(localStorage.getItem(key)).toBe(original); expect(controller.draft).toEqual(blankGraph()); noWrites();
  });
  it('pages every one of 1024 eligible short notes with at most twenty textareas and no truncation', async () => {
    const original = seed(snapshot(1024));
    expect(readStudioGraphLocalDraft(original, owner).definition.presentation?.notes).toHaveLength(1024);
    await mount(); const region = screen.getByRole('region', { name: '本机草稿空间便笺' });
    const seen: string[] = [];
    for (let page = 0; page < 52; page++) {
      const fields = within(region).getAllByRole('textbox') as HTMLTextAreaElement[];
      expect(fields.length).toBeLessThanOrEqual(20); seen.push(...fields.map(input => input.value));
      if (page < 51) click('下一页缓存便笺');
    }
    expect(seen).toEqual(snapshot(1024).definition.presentation!.notes!.map(note => note.text));
    expect((screen.getByRole('button', { name: '下一页缓存便笺' }) as HTMLButtonElement).disabled).toBe(true);
    click('上一页缓存便笺'); expect(field('本机草稿便笺 n1000').value).toBe('笺1000');
    expect(localStorage.getItem(key)).toBe(original); expect(client.overview).not.toHaveBeenCalled(); noWrites();
  });
  it('keeps conflict preview, editor and exact cache intact', async () => {
    const value = snapshot(); const graph = modelGraph();
    value.base = { id: graph.id, version: graph.version, definition_digest: graph.definition_digest, execution_digest: graph.execution_digest };
    const original = seed(value); vi.mocked(client.graphs.get).mockResolvedValue({ ...graph, version: graph.version + 1 });
    await mount(); click('核对并恢复本机图草稿');
    await screen.findByText(/图服务端版本或摘要已改变/);
    expect(field('本机草稿便笺 n0').value).toBe(noteText); expect(field('本机草稿 · 图注释').value).toBe(comment);
    expect(controller.draft).toEqual(blankGraph()); expect(localStorage.getItem(key)).toBe(original); noWrites();
  });
  it('explicit recovery restores exact notes, positions and comment without saving or running', async () => {
    const value = snapshot(); seed(value); await mount(); click('核对并恢复本机图草稿');
    await waitFor(() => expect(controller.localRecovery).toBeUndefined());
    expect(controller.draft).toEqual(value.definition); expect(client.overview).toHaveBeenCalledTimes(1);
    expect(client.graphs.get).not.toHaveBeenCalled(); noWrites();
  });
  it('hides cached note/comment text immediately when authority retires, including a late recheck', async () => {
    const original = seed(snapshot()); let resolve!: (value: StudioOverview) => void;
    vi.mocked(client.overview).mockImplementationOnce(() => new Promise(done => { resolve = done; }));
    const view = await mount(); click('核对并恢复本机图草稿');
    await act(async () => { current = false; view.rerender(<Harness denied />); resolve(overview()); });
    expect(screen.queryByLabelText('本机草稿便笺 n0')).toBeNull(); expect(screen.queryByLabelText('本机草稿 · 图注释')).toBeNull();
    expect(document.body.textContent).not.toContain(noteText); expect(document.body.textContent).not.toContain(comment);
    expect(localStorage.getItem(key)).toBe(original); noWrites();
  });
  it('supports empty comment and absent presentation without inventing note content', async () => {
    const value = snapshot(); value.definition.presentation = { comment: '' }; seed(value); await mount();
    expect(field('本机草稿 · 图注释').value).toBe(''); expect(screen.getByText('本机草稿 · 0 张空间便笺')).toBeTruthy();
    cleanup(); delete value.definition.presentation; seed(value); await mount();
    expect(screen.queryByLabelText('本机草稿 · 图注释')).toBeNull(); expect(screen.queryByRole('region', { name: '本机草稿空间便笺' })).toBeNull();
  });
  it('retains schema 1/2 eligibility, schema 3–5 and external reference exclusion and envelope bound', () => {
    for (const schema_version of [1, 2] as const) expect(graphDraftRecoverable({ ...blankGraph(), schema_version, presentation: snapshot().definition.presentation })).toBe(true);
    for (const schema_version of [3, 4, 5] as const) expect(graphDraftRecoverable({ ...blankGraph(), schema_version, presentation: snapshot().definition.presentation })).toBe(false);
    const value = snapshot(); value.definition.nodes = [{ id: 'asset', definition_id: 'asset_reference', definition_version: 1, enabled: true,
      position: { x: 0, y: 0 }, parameters: { asset_id: 'asset', version: 1, digest: 'a'.repeat(64), kind: 'image' } }]; value.definition.edges = [];
    expect(graphDraftRecoverable(value.definition)).toBe(false);
    expect(() => readStudioGraphLocalDraft(' '.repeat(110001), owner)).toThrow('GRAPH_DRAFT_TOO_LARGE');
  });
});
