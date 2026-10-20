// @vitest-environment jsdom
import { act, cleanup, renderHook, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { useStudioGraphEditorController, type StudioGraphEditorProps } from './useStudioGraphEditorController';
import { modelCatalog, modelGraph } from './studioGraphModel.testFixtures';
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
it('records positioned Add once, preserves dirty author text/viewport, then undo/redo/explicit Save/reopen', async () => {
  const { hook, save, choosePoint } = await fixture();
  act(() => hook.result.current.change({ ...hook.result.current.draft, title: 'Unsaved author text', viewport: { x: 48, y: -80, zoom: 1.5 } }));
  const before = structuredClone(hook.result.current.draft), history = hook.result.current.past.length;
  const { request, restore } = choosePoint(); const add = hook.result.current.addNode;
  expect(save).not.toHaveBeenCalled(); expect(hook.result.current.draft).toEqual(before);
  act(() => { add(request); add(request); });
  expect(hook.result.current.draft.nodes).toHaveLength(before.nodes.length + 1);
  expect(hook.result.current.draft.nodes.at(-1)?.position).toEqual(request.position);
  expect(hook.result.current.draft.title).toBe(before.title); expect(hook.result.current.draft.viewport).toEqual(before.viewport);
  expect(hook.result.current.past).toHaveLength(history + 1); expect(restore).toHaveBeenCalledTimes(1);
  expect(save).not.toHaveBeenCalled();
  act(() => hook.result.current.travel(false)); expect(hook.result.current.draft).toEqual(before);
  act(() => hook.result.current.travel(true)); await act(() => hook.result.current.save());
  expect(save).toHaveBeenCalledTimes(1); await act(() => hook.result.current.open('model_graph'));
  expect(hook.result.current.draft.nodes.at(-1)?.position).toEqual(request.position);
});
it.each(['identity', 'client', 'active', 'denied', 'canMutate', 'busy', 'externalDirty'] as const)('rejects point and retained callbacks after %s ABA', async key => {
  const { hook, initial, choosePoint } = await fixture(); const { request } = choosePoint(); const add = hook.result.current.addNode;
  const changed = { ...initial, [key]: key === 'identity' ? 'B' : key === 'client' ? { ...initial.client } : key === 'active' || key === 'canMutate' ? false : true };
  hook.rerender(changed); hook.rerender(initial); const before = hook.result.current.draft;
  act(() => { add(request); hook.result.current.addNode(request); hook.result.current.cancelPositionedInsertion(request); });
  expect(hook.result.current.draft).toBe(before);
});
it('rejects stale kind callbacks but retains the point for fresh deliberate selection', async () => {
  const { hook, choosePoint } = await fixture(); const { request } = choosePoint(), staleAdd = hook.result.current.addNode;
  act(() => hook.result.current.setKind('director_note')); act(() => hook.result.current.setKind('text_input'));
  const before = hook.result.current.draft; act(() => staleAdd(request)); expect(hook.result.current.draft).toBe(before);
  expect(hook.result.current.insertionExpired).toBe(false); act(() => hook.result.current.addNode(request));
  expect(hook.result.current.draft.nodes.at(-1)?.position).toEqual(request.position);
});
it.each(['director_plan', 'storyboard_plan'] as const)('retains point through explicit source read/choice and pins current %s', async kind => {
  const { hook, choosePoint, planning } = await fixture({}, rawProductionCatalog as unknown as StudioGraphCatalog);
  act(() => hook.result.current.change({ ...hook.result.current.draft, nodes: [], edges: [], schema_version: 4 }));
  const { request } = choosePoint(); act(() => hook.result.current.setKind(kind));
  const before = hook.result.current.draft; act(() => hook.result.current.addNode(request)); expect(hook.result.current.draft).toBe(before);
  await act(() => hook.result.current.loadPlanningDocuments());
  const pin = planning[kind === 'director_plan' ? 0 : 1];
  act(() => hook.result.current.choosePlanningDocument(pin.id)); const stale = hook.result.current.addNode;
  act(() => hook.result.current.choosePlanningDocument('')); act(() => hook.result.current.choosePlanningDocument(pin.id));
  act(() => stale(request)); expect(hook.result.current.draft).toBe(before);
  act(() => hook.result.current.addNode(request)); const node = hook.result.current.draft.nodes.at(-1)!;
  expect(node.position).toEqual(request.position); expect(node.parameters.document_snapshot).toEqual({ id: pin.id, version: pin.version, digest: pin.digest });
});
it('keeps original asset source validation and exact pin constructor', async () => {
  const { hook, choosePoint } = await fixture(); const { request } = choosePoint();
  act(() => hook.result.current.setKind('asset_reference')); const before = hook.result.current.draft;
  act(() => hook.result.current.addNode(request)); expect(hook.result.current.draft).toBe(before);
  await act(() => hook.result.current.loadAssets()); act(() => hook.result.current.setAssetChoice('asset-a'));
  act(() => hook.result.current.addNode(request));
  expect(hook.result.current.draft.nodes.at(-1)?.parameters).toEqual({ asset_id: 'asset-a', version: 4, digest: 'c'.repeat(64), kind: 'image' });
});
it('retains no-argument grid placement and refuses only positioned implicit v1 upgrade', async () => {
  const { hook, choosePoint } = await fixture();
  act(() => hook.result.current.change({ ...hook.result.current.draft, nodes: [], edges: [], schema_version: 1 }));
  const { request } = choosePoint(); act(() => hook.result.current.setKind('text_generate')); act(() => hook.result.current.addNode(request));
  expect(hook.result.current.draft.nodes).toHaveLength(0); expect(hook.result.current.draft.schema_version).toBe(1);
  act(() => hook.result.current.cancelPositionedInsertion(request)); act(() => hook.result.current.addNode());
  expect(hook.result.current.draft.schema_version).toBe(2); expect(hook.result.current.draft.nodes[0].position).toEqual({ x: 24, y: 24 });
});
it('invalidates point after draft undo ABA and gesture start without silently reverting Add', async () => {
  const { hook, choosePoint } = await fixture(); let { request } = choosePoint();
  act(() => hook.result.current.change({ ...hook.result.current.draft, title: 'Changed' })); act(() => hook.result.current.travel(false));
  expect(hook.result.current.positionedInsertion).toBe(request); expect(hook.result.current.insertionExpired).toBe(true);
  const before = hook.result.current.draft; act(() => hook.result.current.addNode(request)); expect(hook.result.current.draft).toBe(before);
  ({ request } = choosePoint()); const staleAdd = hook.result.current.addNode;
  act(() => { hook.result.current.invalidatePositionedInsertion(); staleAdd(request); });
  expect(hook.result.current.draft).toBe(before); expect(hook.result.current.insertionExpired).toBe(true);
});
it('rechecks synchronous busy and unknown-save fences', async () => {
  let busy = false; const { hook, save, choosePoint } = await fixture({ isBusy: () => busy }); const { request } = choosePoint();
  const before = hook.result.current.draft; busy = true; act(() => hook.result.current.addNode(request)); expect(hook.result.current.draft).toBe(before);
  busy = false; act(() => hook.result.current.addNode(request)); save.mockRejectedValueOnce(new Error('Unknown receipt'));
  await act(() => hook.result.current.save()); expect(hook.result.current.blocked).toBe(true);
  act(() => expect(hook.result.current.requestPositionedInsertion({ x: 1, y: 1 }, hook.result.current.insertionScope, vi.fn())).toBe(false));
});
it('bounds finite coordinates and keeps the original catalog node budget', async () => {
  const catalog = modelCatalog();
  const { hook, choosePoint } = await fixture({}, catalog);
  act(() => hook.result.current.change({ ...hook.result.current.draft, edges: [],
    nodes: Array.from({ length: catalog.limits.nodes }, (_, index) => ({ ...structuredClone(modelGraph().definition.nodes[0]), id: `budget_${index}` })),
  }));
  const { request } = choosePoint({ x: 1e9, y: -1e9 });
  expect(request.position).toEqual({ x: 100000, y: -100000 }); const before = hook.result.current.draft;
  act(() => hook.result.current.addNode(request)); expect(hook.result.current.draft).toBe(before);
  act(() => expect(hook.result.current.requestPositionedInsertion({ x: NaN, y: 0 }, hook.result.current.insertionScope, vi.fn())).toBe(false));
});
it('keeps provider fields unbound and cloud execution unapproved on positioned image nodes', async () => {
  const { hook, choosePoint } = await fixture({}, rawProductionCatalog as unknown as StudioGraphCatalog);
  act(() => hook.result.current.change({ ...hook.result.current.draft, nodes: [], edges: [], schema_version: 4 }));
  const { request } = choosePoint(); act(() => hook.result.current.setKind('image_generate')); act(() => hook.result.current.addNode(request));
  expect(hook.result.current.draft.nodes[0].parameters).toMatchObject({ provider_id: '', model_id: '', allow_cloud: false });
  expect(hook.result.current.draft.schema_version).toBe(4);
});
it('retains media sub-budget and rejects schema-incompatible choices through original authority', async () => {
  const { hook, choosePoint } = await fixture({}, rawProductionCatalog as unknown as StudioGraphCatalog);
  act(() => hook.result.current.change({ ...hook.result.current.draft, nodes: [], edges: [], schema_version: 4 }));
  act(() => hook.result.current.setKind('image_generate'));
  for (let index = 0; index < 4; index++) act(() => hook.result.current.addNode());
  const { request } = choosePoint(); const before = hook.result.current.draft;
  act(() => hook.result.current.addNode(request)); expect(hook.result.current.draft).toBe(before);
  act(() => hook.result.current.setKind('video_generate')); act(() => hook.result.current.addNode(request));
  expect(hook.result.current.draft).toBe(before);
});
it('makes an execution edit invalidate positioned intent', async () => {
  const { hook, choosePoint } = await fixture(); const { request } = choosePoint();
  act(() => hook.result.current.setExecutionDirty(true)); act(() => hook.result.current.setExecutionDirty(false));
  const before = hook.result.current.draft; act(() => hook.result.current.addNode(request)); expect(hook.result.current.draft).toBe(before);
});

it('invalidates point when the original timeline editor has unsaved form input', async () => {
  const { hook, choosePoint } = await fixture();
  act(() => hook.result.current.change({ ...hook.result.current.draft, schema_version: 3, nodes: [
    { id: 'timeline', definition_id: 'timeline_export', definition_version: 1, enabled: true, position: { x: 0, y: 0 }, parameters: {} },
  ], edges: [] }));
  act(() => hook.result.current.setSelected(['timeline'])); const { request } = choosePoint();
  act(() => hook.result.current.timelineEditor.changeForm('clip_id', 'author-input'));
  expect(hook.result.current.timelineEditor.formDirty).toBe(true); const before = hook.result.current.draft;
  act(() => hook.result.current.addNode(request)); expect(hook.result.current.draft).toBe(before);
  expect(hook.result.current.insertionExpired).toBe(true);
});
