// @vitest-environment jsdom
import { studioGraphEditorView } from './studioGraphEditorView';
import { act, cleanup, fireEvent, render, renderHook, screen, waitFor, within } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { useStudioGraphEditorController, type StudioGraphEditorProps } from './useStudioGraphEditorController';
import { modelCatalog, modelGraph, modelRun } from './studioGraphModel.testFixtures';
import type { StudioClient } from './studioClient';
import type { StudioGraphCatalog, StudioGraphRecord } from './studioGraphTypes';
import rawProductionCatalog from './fixtures/productionGraph.catalog.json';
afterEach(() => { cleanup(); vi.restoreAllMocks(); });
async function fixture(patch: Partial<StudioGraphEditorProps> = {}, catalog: StudioGraphCatalog = modelCatalog()) {
  let record = modelGraph();
  const save = vi.fn(async (_id, input) => {
    record = { ...record, definition: structuredClone(input.definition), version: record.version + 1 };
    return structuredClone(record);
  });
  const planning = [{ id: 'director-a', mode: 'DIRECTOR', title: 'Director', version: 3, digest: 'a'.repeat(64) },
    { id: 'storyboard-a', mode: 'STORYBOARD', title: 'Storyboard', version: 4, digest: 'b'.repeat(64) }];
  const initial: StudioGraphEditorProps = { active: true, denied: false, identity: 'project-A:actor-A', canMutate: true,
    canReview: true, busy: false, externalDirty: false, isCurrent: () => true, read: work => work(), mutate: work => work(),
    client: { asset: vi.fn().mockResolvedValue({ id: 'asset-a', version: 4, sha256: 'c'.repeat(64), kind: 'image' }), assets: vi.fn().mockResolvedValue({ items: [{ id: 'asset-a', version: 4, sha256: 'c'.repeat(64), kind: 'image' }] }),
      graphs: { catalog: vi.fn().mockResolvedValue(catalog), list: vi.fn().mockResolvedValue({ items: [] }),
        imageCatalog: vi.fn().mockResolvedValue(catalog), productionCatalog: vi.fn().mockResolvedValue(catalog),
        planningDocuments: vi.fn().mockResolvedValue({ documents: planning }),
        get: vi.fn(async () => structuredClone(record)), save } } as unknown as StudioClient, ...patch };
  const hook = renderHook(value => useStudioGraphEditorController(value), { initialProps: initial });
  await waitFor(() => expect(hook.result.current.editable).toBe(true));
  await act(() => hook.result.current.open(record.id));
  const choosePoint = (position = { x: -125, y: 365 }) => {
    const restore = vi.fn(); act(() => expect(hook.result.current.requestPositionedInsertion(position, hook.result.current.insertionScope, restore)).toBe(true));
    return { request: hook.result.current.positionedInsertion!, restore };
  };
  return { hook, initial, save, choosePoint, planning, setRecord: (next: StudioGraphRecord) => { record = next; } };
}

it('selects the exact saved node and focuses the original inspector without draft/history changes', async () => {
  const { hook, save } = await fixture(); const before = hook.result.current;
  const inspector = document.createElement('section'); inspector.tabIndex = -1; document.body.append(inspector);
  Object.assign(hook.result.current.nodeInspectorRef, { current: inspector });
  act(() => expect(hook.result.current.locateRunNode(before.base!.definition.nodes[0].id, before.base!)).toBe(true));
  expect(hook.result.current.selected).toEqual([before.base!.definition.nodes[0].id]);
  expect(document.activeElement).toBe(inspector); expect(hook.result.current.draft).toBe(before.draft);
  expect(hook.result.current.past).toEqual(before.past); expect(save).not.toHaveBeenCalled(); inspector.remove();
});
it.each(['busy', 'externalDirty', 'denied', 'identity', 'active'] as const)('rejects retained node selection after %s transitions including return', async key => {
  const { hook, initial } = await fixture(); const before = hook.result.current, locate = before.locateRunNode;
  const changed = { ...initial, [key]: key === 'identity' ? 'project-B:actor-B' : key === 'active' ? false : true };
  hook.rerender(changed);
  act(() => expect(locate(before.base!.definition.nodes[0].id, before.base!)).toBe(false));
  hook.rerender(initial);
  act(() => expect(locate(before.base!.definition.nodes[0].id, before.base!)).toBe(false));
});
it('preserves author edits and rejects wrong graph objects or missing node identities', async () => {
  const { hook } = await fixture(); const before = hook.result.current;
  act(() => expect(before.locateRunNode('absent', before.base!)).toBe(false));
  act(() => expect(before.locateRunNode(before.base!.definition.nodes[0].id, structuredClone(before.base!))).toBe(false));
  act(() => hook.result.current.change({ ...before.draft, title: 'Unsaved author title' }));
  act(() => expect(hook.result.current.locateRunNode(before.base!.definition.nodes[0].id, before.base!)).toBe(false));
  expect(hook.result.current.draft.title).toBe('Unsaved author title');
});
it('checks the live pending IMAGE fence and preserves current selection', async () => {
  let pending = false; const { hook } = await fixture({ isDirectorImagePending: () => pending });
  const before = hook.result.current; pending = true;
  act(() => expect(before.locateRunNode(before.base!.definition.nodes[0].id, before.base!)).toBe(false));
  expect(hook.result.current.selected).toEqual(before.selected);
});

it('mounts the original run-to-inspector path and focuses the exact failed node', async () => {
  const { initial, hook, save } = await fixture(); hook.unmount();
  const getRun = vi.fn().mockResolvedValue(modelRun({ status: 'FAILED', model_runtime: undefined,
    node_states: { input: { status: 'FAILED', error: { code: 'CREATIVE_GRAPH_NODE_FAILED' }, output: null } } }));
  const props = { ...initial, requestedGraphId: 'model_graph', requestedRunId: 'model_run',
    client: { ...initial.client, graphs: { ...initial.client.graphs, getRun } } };
  function Mounted() {
    const controller = useStudioGraphEditorController(props), view = studioGraphEditorView(controller, props);
    return <>{view.content}{view.inspector}</>;
  }
  render(<Mounted />);
  fireEvent.click(await screen.findByRole('button', { name: '检查节点 input' }));
  const inspector = screen.getByRole('region', { name: '创作图节点检查器' });
  expect(document.activeElement).toBe(inspector);
  expect(within(inspector).getByText(/input · 定义 v1/)).toBeTruthy();
  expect(save).not.toHaveBeenCalled(); expect(getRun).toHaveBeenCalledTimes(1);
});
