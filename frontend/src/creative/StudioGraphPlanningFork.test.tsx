// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, renderHook, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useStudioGraphEditorController, type StudioGraphEditorProps } from './useStudioGraphEditorController';
import type { StudioClient } from './studioClient';
import type { StudioGraphCatalog, StudioGraphCreateInput, StudioGraphRecord } from './studioGraphTypes';
import { imageGraphRecord } from './studioImageGraph.testFixtures';
import catalog from './fixtures/productionGraph.catalog.json';
import type { PlanningDocument } from './studioProductionGraphContract';
import { useStudioGraphEditor } from './useStudioGraphEditor';

const pin = { id: 'saved-director', version: 1, digest: 'a'.repeat(64) };
const next: PlanningDocument = { ...pin, version: 2, digest: 'b'.repeat(64), title: 'Updated source', mode: 'DIRECTOR' };
const read = async <T,>(work: () => Promise<T>) => work();
let original: StudioGraphRecord, client: StudioClient, live: boolean, syncBusy: boolean;
const current = () => live;
const busy = () => syncBusy;
beforeEach(() => {
  localStorage.clear(); live = true; syncBusy = false;
  original = imageGraphRecord();
  original.definition = { schema_version: 4, title: 'Keep original', nodes: [{ id: 'director', definition_id: 'director_plan',
    definition_version: 1, enabled: true, position: { x: 30, y: 50 }, parameters: { document_snapshot: { ...pin } } }],
    edges: [], viewport: { x: 11, y: 12, zoom: 1.3 }, presentation: { comment: 'Keep authored comment' } };
  original.reference_states = [{ node_id: 'director', state: 'STALE' }]; original.can_edit = true;
  client = { graphs: {
    catalog: vi.fn(async () => structuredClone(catalog) as unknown as StudioGraphCatalog),
    productionCatalog: vi.fn(async () => structuredClone(catalog) as unknown as StudioGraphCatalog),
    list: vi.fn(async () => ({ items: [structuredClone(original)] })), get: vi.fn(async () => structuredClone(original)),
    create: vi.fn(async (body: StudioGraphCreateInput) => ({ ...structuredClone(original), id: 'new-independent', version: 1,
      definition: body.definition, reference_states: [{ node_id: 'director', state: 'CURRENT' }] })),
    save: vi.fn(), createRun: vi.fn(), dispatchModel: vi.fn(),
  } } as unknown as StudioClient;
});
afterEach(cleanup);
async function setup() {
  const result = renderHook((extra: Partial<StudioGraphEditorProps>) => useStudioGraphEditorController({
    active: true, denied: false, identity: 'author-project', client, canMutate: true, canReview: true,
    busy: false, externalDirty: false, isCurrent: current, isBusy: busy, read, mutate: read, ...extra,
  }), { initialProps: {} as Partial<StudioGraphEditorProps> });
  await waitFor(() => expect(result.result.current.loading).toBe(false));
  await act(async () => result.result.current.open(original.id));
  act(() => result.result.current.setSelected(['director']));
  expect(result.result.current.base?.id).toBe(original.id);
  expect(result.result.current.node?.id).toBe('director');
  return result;
}

describe('original controller owns updated-source independent drafts', () => {
  it('mounts the inspector flow and uses explicit original Save after consent', async () => {
    client.graphs.planningDocuments = vi.fn(async () => ({ documents: [next] }));
    function Harness() {
      const editor = useStudioGraphEditor({ active: true, denied: false, identity: 'author-project', client,
        canMutate: true, canReview: true, busy: false, externalDirty: false, isCurrent: current, isBusy: busy, read, mutate: read });
      return <>{editor.content}{editor.inspector}</>;
    }
    render(<Harness />);
    await waitFor(() => expect(screen.getByLabelText('创作图标题')).toHaveProperty('disabled', false));
    fireEvent.change(screen.getByLabelText('已保存创作图'), { target: { value: original.id } });
    await waitFor(() => expect(screen.getByLabelText('创作图标题')).toHaveProperty('value', 'Keep original'));
    fireEvent.click(screen.getByRole('button', { name: '选择节点 导演节点（已保存文档） · director' }));
    fireEvent.click(screen.getByRole('button', { name: '核对更新来源用于独立新图' }));
    const checkbox = await screen.findByLabelText('确认以这份更新来源准备独立新图草稿，保留原图');
    fireEvent.click(checkbox);
    fireEvent.click(screen.getByRole('button', { name: '准备使用更新来源的独立草稿' }));
    expect(client.graphs.create).not.toHaveBeenCalled(); expect(client.graphs.save).not.toHaveBeenCalled();
    expect(screen.getByLabelText('独立新图来源上下文').textContent).toContain(original.id);
    fireEvent.click(screen.getByRole('button', { name: '保存创作图' }));
    await waitFor(() => expect(client.graphs.create).toHaveBeenCalledTimes(1));
    expect(vi.mocked(client.graphs.create).mock.calls[0][0].definition.nodes[0].parameters.document_snapshot)
      .toEqual({ id: next.id, version: next.version, digest: next.digest });
    expect(client.graphs.save).not.toHaveBeenCalled(); expect(client.graphs.createRun).not.toHaveBeenCalled();
  });
  it('prepares once, keeps complete author data and saves only through original create', async () => {
    const before = structuredClone(original), { result } = await setup();
    const prepare = result.current.preparePlanningGraphFork, scope = result.current.planningForkScope;
    act(() => {
      expect(prepare(next, scope)).toBe(true);
      expect(prepare(next, scope)).toBe(false);
    });
    expect(result.current.base).toBeUndefined();
    const expected = structuredClone(before.definition);
    expected.nodes[0].parameters.document_snapshot = { id: next.id, version: next.version, digest: next.digest };
    expect(result.current.draft).toEqual(expected);
    expect(original).toEqual(before);
    expect(result.current.independentOrigin?.id).toBe(original.id);
    expect(client.graphs.create).not.toHaveBeenCalled(); expect(client.graphs.save).not.toHaveBeenCalled();
    await act(async () => result.current.save());
    expect(client.graphs.create).toHaveBeenCalledTimes(1);
    expect(vi.mocked(client.graphs.create).mock.calls[0][0]).toMatchObject({ expected_version: 0, definition: expected });
    expect(result.current.base?.id).toBe('new-independent');
    expect(client.graphs.save).not.toHaveBeenCalled(); expect(client.graphs.createRun).not.toHaveBeenCalled();
    expect(client.graphs.dispatchModel).not.toHaveBeenCalled();
  });
  it.each([{ canMutate: false }, { busy: true }, { externalDirty: true }, { denied: true }, { active: false }, { identity: 'other' }])(
    'rejects a retained action after authority transition %j, including restoration', async transition => {
      const { result, rerender } = await setup();
      const prepare = result.current.preparePlanningGraphFork, scope = result.current.planningForkScope;
      rerender(transition); act(() => expect(prepare(next, scope)).toBe(false));
      rerender({}); act(() => expect(prepare(next, scope)).toBe(false));
      expect(client.graphs.create).not.toHaveBeenCalled(); expect(client.graphs.save).not.toHaveBeenCalled();
    });
  it('rejects stale consent after authored edits or selection ABA', async () => {
    const { result } = await setup(); let prepare = result.current.preparePlanningGraphFork, scope = result.current.planningForkScope;
    act(() => result.current.change({ ...result.current.draft, title: 'More recent author input' }));
    act(() => expect(prepare(next, scope)).toBe(false));
    prepare = result.current.preparePlanningGraphFork; scope = result.current.planningForkScope;
    act(() => result.current.setSelected([])); act(() => result.current.setSelected(['director']));
    act(() => expect(prepare(next, scope)).toBe(false));
    expect(result.current.draft.title).toBe('More recent author input');
  });
  it.each(['CURRENT', 'UNAVAILABLE'] as const)('does not fork an unverified or unavailable source: %s', async state => {
    original.reference_states = [{ node_id: 'director', state }];
    if (state === 'UNAVAILABLE') original.can_edit = false;
    const { result } = await setup();
    act(() => expect(result.current.preparePlanningGraphFork(next, result.current.planningForkScope)).toBe(false));
  });
  it('checks live locks and unmount before any local transition', async () => {
    const { result, unmount } = await setup();
    const prepare = result.current.preparePlanningGraphFork, scope = result.current.planningForkScope;
    syncBusy = true; act(() => expect(prepare(next, scope)).toBe(false)); syncBusy = false;
    live = false; act(() => expect(prepare(next, scope)).toBe(false)); live = true;
    unmount(); expect(prepare(next, scope)).toBe(false);
  });
});
