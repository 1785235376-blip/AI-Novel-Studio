// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, renderHook, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { useStudioGraphEditorController, type StudioGraphEditorProps } from './useStudioGraphEditorController';
import { modelCatalog, modelGraph } from './studioGraphModel.testFixtures';
import type { StudioClient } from './studioClient';
import { studioGraphEditorView } from './studioGraphEditorView';
import { connectionIssue } from './graphDraft';

afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });
const source = { nodeId: 'input', portId: 'text', direction: 'output' as const };
const target = { nodeId: 'generate', portId: 'text', direction: 'input' as const };
async function fixture(patch: Partial<StudioGraphEditorProps> = {}) {
  let record = modelGraph(); record.definition.edges = [];
  const catalog = modelCatalog();
  const save = vi.fn(async (_id, input) => {
    record = { ...record, definition: structuredClone(input.definition), version: record.version + 1 };
    return structuredClone(record);
  });
  const initial: StudioGraphEditorProps = { active: true, denied: false, identity: 'project-A:actor-A', canMutate: true,
    canReview: true, busy: false, externalDirty: false, isCurrent: () => true, read: work => work(), mutate: work => work(),
    client: { graphs: { catalog: vi.fn().mockResolvedValue(catalog), list: vi.fn().mockResolvedValue({ items: [] }),
      get: vi.fn(async () => structuredClone(record)), save } } as unknown as StudioClient, ...patch };
  const hook = renderHook(value => useStudioGraphEditorController(value), { initialProps: initial });
  await waitFor(() => expect(hook.result.current.editable).toBe(true));
  await act(() => hook.result.current.open(record.id));
  return { hook, initial, save, catalog };
}
it('stages only pending endpoints, then original Connect owns history/save/reopen', async () => {
  const { hook, save } = await fixture(); const before = hook.result.current.draft;
  const token = hook.result.current.connectionScope;
  act(() => expect(hook.result.current.stageConnection(source, target, token)).toBe(true));
  expect(hook.result.current.connectionScope).toBe(token); expect(hook.result.current.draft).toBe(before);
  expect(hook.result.current.past).toHaveLength(0); expect(save).not.toHaveBeenCalled();
  expect(hook.result.current.sourcePort).toBe(JSON.stringify(['input', 'text']));
  expect(hook.result.current.targetPort).toBe(JSON.stringify(['generate', 'text']));
  act(() => hook.result.current.connect()); expect(hook.result.current.draft.edges).toHaveLength(1);
  expect(hook.result.current.past).toHaveLength(1); expect(hook.result.current.sourcePort).toBe('');
  act(() => hook.result.current.travel(false)); expect(hook.result.current.draft.edges).toHaveLength(0);
  act(() => hook.result.current.travel(true)); expect(hook.result.current.draft.edges).toHaveLength(1);
  await act(() => hook.result.current.save()); expect(save).toHaveBeenCalledTimes(1);
  await act(() => hook.result.current.open('model_graph')); expect(hook.result.current.draft.edges).toHaveLength(1);
});
it.each(['identity', 'client', 'active', 'denied', 'canMutate', 'externalDirty', 'busy'] as const)('rejects captured endpoint staging after %s ABA', async field => {
  const { hook, initial } = await fixture(); const token = hook.result.current.connectionScope, stale = hook.result.current.stageConnection;
  const changed = { ...initial, [field]: field === 'identity' ? 'project-B:actor-A' : field === 'client' ? { ...initial.client }
    : field === 'active' || field === 'canMutate' ? false : true };
  hook.rerender(changed); hook.rerender(initial);
  act(() => expect(stale(source, target, token)).toBe(false));
  act(() => expect(hook.result.current.stageConnection(source, target, token)).toBe(false));
  expect(hook.result.current.sourcePort).toBe(''); expect(hook.result.current.draft.edges).toHaveLength(0);
});
it.each(['busy', 'current'] as const)('rechecks synchronous %s fence without a render', async fence => {
  let allowed = true;
  const { hook } = await fixture({ isBusy: () => fence === 'busy' && !allowed, isCurrent: () => fence !== 'current' || allowed });
  const stage = hook.result.current.stageConnection, token = hook.result.current.connectionScope;
  allowed = false; act(() => expect(stage(source, target, token)).toBe(false));
  expect(hook.result.current.sourcePort).toBe('');
});
it('rejects draft ABA, wrong direction, type mismatch and duplicate through the original authority', async () => {
  const { hook } = await fixture(); const old = hook.result.current.connectionScope;
  act(() => hook.result.current.change({ ...hook.result.current.draft, title: 'changed' }));
  act(() => hook.result.current.travel(false));
  act(() => expect(hook.result.current.stageConnection(source, target, old)).toBe(false));
  act(() => expect(hook.result.current.stageConnection(target, source, hook.result.current.connectionScope)).toBe(false));
  act(() => expect(hook.result.current.stageConnection(source, { ...target, portId: 'direction' }, hook.result.current.connectionScope)).toBe(false));
  act(() => hook.result.current.stageConnection(source, target, hook.result.current.connectionScope));
  act(() => hook.result.current.connect());
  act(() => expect(hook.result.current.stageConnection(source, target, hook.result.current.connectionScope)).toBe(false));
  expect(hook.result.current.draft.edges).toHaveLength(1);
});
it('leaves the original edge limit enforcement with explicit Connect', async () => {
  const { hook, catalog } = await fixture();
  // A typed fixture catalog exposes forty distinct, single-connection inputs.
  // Every preexisting edge is checked by the original validator, with the real
  // contract limit unchanged at 40 and a separate valid pending input remaining.
  const receiver = catalog.definitions.find(value => value.id === 'text_reference')!;
  receiver.inputs = Array.from({ length: 40 }, (_, index) => ({ id: `slot_${index}`, type: 'TEXT', required: false, multiple: false }));
  const full = structuredClone(hook.result.current.draft);
  full.nodes.push({ id: 'capacity', definition_id: 'text_reference', definition_version: 1,
    enabled: true, position: { x: 0, y: 400 }, parameters: {} });
  for (let index = 0; index < catalog.limits.edges; index++) {
    const edge = { id: `existing_${index}`, source_node_id: source.nodeId, source_port: source.portId,
      target_node_id: 'capacity', target_port: `slot_${index}` };
    expect(connectionIssue(full, catalog.definitions, edge)).toBeUndefined(); full.edges.push(edge);
  }
  act(() => hook.result.current.change(full));
  const history = hook.result.current.past.length;
  act(() => expect(hook.result.current.stageConnection(source, target, hook.result.current.connectionScope)).toBe(true));
  act(() => hook.result.current.connect()); expect(hook.result.current.draft.edges).toHaveLength(40);
  expect(hook.result.current.past).toHaveLength(history);
});

it('a retired callback uses the latest synchronous lock predicate', async () => {
  const { hook, initial } = await fixture({ isBusy: () => false });
  const stale = hook.result.current.stageConnection, select = hook.result.current.selectConnectionPort, token = hook.result.current.connectionScope;
  hook.rerender({ ...initial, isBusy: () => true });
  act(() => expect(stale(source, target, token)).toBe(false));
  act(() => select(source, token)); expect(hook.result.current.sourcePort).toBe('');
});
it('invalidates same-ID record refresh and schema transitions', async () => {
  const { hook } = await fixture(); const token = hook.result.current.connectionScope;
  await act(() => hook.result.current.open('model_graph'));
  act(() => expect(hook.result.current.stageConnection(source, target, token)).toBe(false));
  const refreshed = hook.result.current.connectionScope;
  act(() => hook.result.current.change({ ...hook.result.current.draft, schema_version: 1 }));
  act(() => expect(hook.result.current.stageConnection(source, target, refreshed)).toBe(false));
  const expected = !connectionIssue(hook.result.current.draft, hook.result.current.catalog!.definitions,
    { id: 'pending', source_node_id: source.nodeId, source_port: source.portId, target_node_id: target.nodeId, target_port: target.portId });
  act(() => expect(hook.result.current.stageConnection(source, target, hook.result.current.connectionScope)).toBe(expected));
  expect(hook.result.current.draft.edges).toHaveLength(0);
});

it('wires a real canvas drop through the view into pending fields before explicit Connect', async () => {
  class Pointer extends MouseEvent {
    readonly pointerId: number;
    constructor(type: string, options: PointerEventInit = {}) { super(type, options); this.pointerId = options.pointerId ?? 1; }
  }
  vi.stubGlobal('PointerEvent', Pointer);
  const { hook, initial, save } = await fixture();
  const view = render(studioGraphEditorView(hook.result.current, initial).content);
  const output = document.querySelector('[data-graph-node-id="input"] [data-graph-port="text"]')!;
  const input = document.querySelector('[data-graph-node-id="generate"] [data-graph-port="text"]')!;
  Object.defineProperty(document, 'elementFromPoint', { configurable: true, value: vi.fn(() => input) });
  const viewport = screen.getByRole('group', { name: '节点图交互区域' });
  fireEvent.pointerDown(output, { button: 0, pointerId: 1, clientX: 100, clientY: 100 });
  fireEvent.pointerMove(viewport, { pointerId: 1, clientX: 400, clientY: 100 });
  fireEvent.pointerUp(viewport, { pointerId: 1, clientX: 400, clientY: 100 });
  expect(hook.result.current.sourcePort).toBe(JSON.stringify(['input', 'text']));
  expect(hook.result.current.targetPort).toBe(JSON.stringify(['generate', 'text']));
  expect(hook.result.current.draft.edges).toHaveLength(0); expect(save).not.toHaveBeenCalled();
  view.rerender(studioGraphEditorView(hook.result.current, initial).content);
  fireEvent.click(screen.getByRole('button', { name: '连接所选端口' }));
  expect(hook.result.current.draft.edges).toHaveLength(1); expect(save).not.toHaveBeenCalled();
});
