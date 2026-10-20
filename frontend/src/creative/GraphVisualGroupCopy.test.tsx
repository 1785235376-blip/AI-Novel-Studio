// @vitest-environment jsdom
import { StrictMode } from 'react';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import * as draftHelpers from './graphDraft';
import { graphVisualGroupCopy } from './graphVisualGroupCopy';
import { graphSelectionCopy } from './graphSelectionCopy';
import { modelCatalog, modelGraph } from './studioGraphModel.testFixtures';
import { useStudioGraphEditorController, type StudioGraphEditorProps } from './useStudioGraphEditorController';
import { studioGraphEditorView } from './studioGraphEditorView';
import type { StudioClient } from './studioClient';
import type { StudioGraphDefinition, StudioGraphSaveInput } from './studioGraphTypes';

afterEach(() => { cleanup(); vi.restoreAllMocks(); });
function fixture() {
  const record = modelGraph(), catalog = modelCatalog(false);
  record.definition = { schema_version: 1, title: 'Reusable authoring group', viewport: { x: 16, y: 24, zoom: 1 }, nodes: [
    { id: 'a', definition_id: 'text_input', definition_version: 1, enabled: true, parameters: { text: 'Author α' }, position: { x: 0, y: 0 } },
    { id: 'b', definition_id: 'text_reference', definition_version: 1, enabled: true, parameters: {}, position: { x: 280, y: 0 } },
    { id: 'c', definition_id: 'draft_prepare', definition_version: 1, enabled: false, parameters: {}, position: { x: 560, y: 0 } },
    { id: 'd', definition_id: 'text_input', definition_version: 1, enabled: true, parameters: { text: 'Untouched' }, position: { x: 0, y: 320 } },
    { id: 'e', definition_id: 'human_review', definition_version: 1, enabled: true, parameters: {}, position: { x: 840, y: 0 } },
  ], edges: [
    { id: 'ab', source_node_id: 'a', source_port: 'text', target_node_id: 'b', target_port: 'text' },
    { id: 'bc', source_node_id: 'b', source_port: 'text', target_node_id: 'c', target_port: 'text' },
    { id: 'ce', source_node_id: 'c', source_port: 'draft', target_node_id: 'e', target_port: 'draft' },
  ], presentation: { comment: 'Original authored note', groups: [
    { id: 'module', name: '作者链', node_ids: ['a'] },
    { id: 'stage', name: '草稿阶段', node_ids: ['b', 'c'], parent_id: 'module' },
    { id: 'other', name: '其他分支', node_ids: ['d'] },
  ] } };
  return { record, catalog };
}
const selected = ['a', 'b', 'c'];
it('group copy preserves the exact source and remaps a complete nested authored subgraph once', () => {
  const f = fixture(); f.record.definition.nodes[0].parameters = { text: 'Author' };
  Object.assign(f.record.definition.nodes[0].parameters, { pin: { version: 7, digest: 'a'.repeat(64), license: 'synthetic-preservation-only' } });
  const before = structuredClone(f.record.definition), result = graphVisualGroupCopy(f.record.definition, selected, f.catalog);
  expect(f.record.definition).toEqual(before); expect(result.nodeCount).toBe(3); expect(result.edgeCount).toBe(2); expect(result.excludedEdges).toBe(1);
  expect(result.definition.nodes.slice(0, 5)).toEqual(before.nodes); expect(result.definition.edges.slice(0, 3)).toEqual(before.edges);
  expect(result.definition.viewport).toEqual(before.viewport); expect(result.definition.presentation?.comment).toBe(before.presentation?.comment);
  expect(result.definition.presentation?.groups?.slice(0, 3)).toEqual(before.presentation?.groups);
  const [parent, child] = result.groupCopy.groups;
  expect(result.groupCopy).toMatchObject({ nested: 1, promoted: 0 }); expect(parent.node_ids).toEqual([result.selected[0]]); expect(child.node_ids).toEqual(result.selected.slice(1)); expect(child.parent_id).toBe(parent.id);
  expect(parent.id).not.toBe('module'); expect(child.id).not.toBe('stage'); expect(parent.name).toBe('作者链'); expect(child.name).toBe('草稿阶段');
  expect(result.definition.nodes.slice(5).map(node => node.parameters)).toEqual(before.nodes.slice(0, 3).map(node => node.parameters));
  expect(result.definition.nodes[7].enabled).toBe(false); expect(result.definition.nodes[5].parameters).not.toBe(before.nodes[0].parameters);
  expect(result.definition.edges.slice(3).map(edge => [edge.source_node_id, edge.target_node_id])).toEqual([[result.selected[0], result.selected[1]], [result.selected[1], result.selected[2]]]);
});
it('group copy explicitly promotes an independently copied complete child and rejects partial parent subtrees', () => {
  const f = fixture(), result = graphVisualGroupCopy(f.record.definition, ['b', 'c'], f.catalog);
  expect(result.groupCopy).toMatchObject({ nested: 0, promoted: 1 }); expect(result.groupCopy.groups).toHaveLength(1); expect(result.groupCopy.groups[0]).not.toHaveProperty('parent_id');
  expect(result.definition.presentation?.groups?.slice(0, 3)).toEqual(f.record.definition.presentation?.groups);
  for (const ids of [['a'], ['a', 'b'], ['b'], ['e'], ['a', 'a', 'b', 'c']]) expect(() => graphVisualGroupCopy(f.record.definition, ids, f.catalog)).toThrow();
});
it('group copy rejects ambiguous membership, invalid hierarchy and copied invalid ports without a partial draft', () => {
  const f = fixture();
  const mutations: ((value: StudioGraphDefinition) => void)[] = [d => d.presentation!.groups![1].id = 'module', d => d.presentation!.groups![1].node_ids.push('a'), d => d.presentation!.groups![1].node_ids.push('unknown'), d => d.presentation!.groups![0].parent_id = 'stage', d => d.presentation!.groups![1].name = ' ', d => d.edges[0].source_port = 'missing'];
  for (const mutate of mutations) { const d = structuredClone(f.record.definition); mutate(d); const before = structuredClone(d); expect(() => graphVisualGroupCopy(d, selected, f.catalog)).toThrow(); expect(d).toEqual(before); }
});
it('group copy keeps original node/edge/byte limits and rejects group capacity or new group-ID collisions', () => {
  const f = fixture(), before = structuredClone(f.record.definition);
  const nodeCatalog = structuredClone(f.catalog); Object.assign(nodeCatalog.limits, { nodes: 5 });
  expect(() => graphVisualGroupCopy(before, selected, nodeCatalog)).toThrow(/限制/);
  const ordinary = graphSelectionCopy(before, selected, f.catalog), bytes = new TextEncoder().encode(JSON.stringify(ordinary.definition)).length;
  const byteCatalog = structuredClone(f.catalog); Object.assign(byteCatalog.limits, { definition_bytes: bytes + 1 });
  expect(() => graphVisualGroupCopy(before, selected, byteCatalog)).toThrow(/大小/);
  const full = structuredClone(before); full.nodes = Array.from({ length: 24 }, (_, i) => ({ ...before.nodes[0], id: `n${i}` })); full.edges = []; full.presentation!.groups = full.nodes.map(node => ({ id: `g${node.id}`, name: node.id, node_ids: [node.id] }));
  expect(() => graphVisualGroupCopy(full, ['n0'], f.catalog)).toThrow(/24/);
  const original = draftHelpers.graphId; vi.spyOn(draftHelpers, 'graphId').mockImplementation(prefix => prefix === 'group' ? 'module' : original(prefix));
  expect(() => graphVisualGroupCopy(before, selected, f.catalog)).toThrow(/标识冲突/); expect(f.record.definition).toEqual(before);
});
const click = (name: string) => fireEvent.click(screen.getByRole('button', { name }));
const retained = (name: string) => { const button = screen.getByRole('button', { name }); return (button as any)[Object.keys(button).find(key => key.startsWith('__reactProps$'))!].onClick as () => void; };
async function mounted() {
  const f = fixture(); let record = f.record;
  const graphs = { catalog: vi.fn(async () => f.catalog), list: vi.fn(async () => ({ items: [structuredClone(record)] })), get: vi.fn(async () => structuredClone(record)),
    save: vi.fn(async (_id: string | undefined, input: StudioGraphSaveInput) => { record = { ...record, version: record.version + 1, definition: structuredClone(input.definition) }; return structuredClone(record); }),
    preflight: vi.fn(), createRun: vi.fn(), action: vi.fn(), runs: vi.fn(async () => ({ items: [] })) };
  const props: StudioGraphEditorProps = { active: true, denied: false, identity: 'group-copy-owner', client: { graphs } as unknown as StudioClient, canMutate: true, canReview: true, busy: false, externalDirty: false, isCurrent: () => true, read: async work => work(), mutate: async work => work() };
  let controller!: ReturnType<typeof useStudioGraphEditorController>;
  function Harness({ value }: { value: StudioGraphEditorProps }) { controller = useStudioGraphEditorController(value); return studioGraphEditorView(controller, value).content; }
  const view = render(<StrictMode><Harness value={props} /></StrictMode>);
  await waitFor(() => expect(controller.editable).toBe(true)); await act(() => controller.open(record.id)); act(() => controller.setSelected(selected));
  const rerender = (value: StudioGraphEditorProps) => view.rerender(<StrictMode><Harness value={value} /></StrictMode>);
  return { ...f, graphs, props, controller: () => controller, view, rerender };
}
it('group copy real owner preview, one history/undo/redo and explicit CAS save/reopen preserve the entire graph', async () => {
  const f = await mounted(), before = structuredClone(f.controller().draft);
  click('预览复制完整视觉组'); expect(screen.getByLabelText('完整视觉组复制预览').textContent).toContain('保留 1 个父子关系');
  expect(f.controller().draft).toEqual(before); expect(f.controller().past).toHaveLength(0); const paste = retained('粘贴到当前图'); act(() => { paste(); paste(); });
  const expected = structuredClone(f.controller().draft); expect(expected.nodes).toHaveLength(8); expect(expected.presentation?.groups).toHaveLength(5); expect(f.controller().past).toHaveLength(1);
  expect(f.graphs.save).not.toHaveBeenCalled(); click('撤销图编辑'); expect(f.controller().draft).toEqual(before); click('重做图编辑'); expect(f.controller().draft).toEqual(expected);
  click('保存创作图'); await waitFor(() => expect(f.graphs.save).toHaveBeenCalledTimes(1)); expect(f.graphs.save.mock.calls[0][1]).toEqual({ expected_version: 1, definition: expected });
  await waitFor(() => expect(f.controller().base?.version).toBe(2)); await act(() => f.controller().open('model_graph')); expect(f.controller().draft).toEqual(expected);
  for (const fn of [f.graphs.preflight, f.graphs.createRun, f.graphs.action]) expect(fn).not.toHaveBeenCalled();
});
it('group copy retires synchronous selection ABA, cancelled or replaced previews and unmounted callbacks', async () => {
  const f = await mounted(), before = structuredClone(f.controller().draft);
  click('预览复制完整视觉组'); const oldSelection = retained('粘贴到当前图'); act(() => { f.controller().setSelected(['d']); f.controller().setSelected(selected); oldSelection(); }); expect(f.controller().draft).toEqual(before);
  click('预览复制完整视觉组'); const cancelled = retained('粘贴到当前图'); act(() => { f.controller().cancelSelectionCopy(); cancelled(); }); expect(f.controller().draft).toEqual(before);
  click('预览复制完整视觉组'); const replaced = retained('粘贴到当前图'); act(() => { f.controller().previewSelectionCopy(); replaced(); }); expect(f.controller().draft).toEqual(before);
  click('预览复制完整视觉组'); const unmounted = retained('粘贴到当前图'); f.view.unmount(); act(() => unmounted()); expect(f.graphs.save).not.toHaveBeenCalled();
});
it.each(['busy', 'externalDirty', 'owner', 'draft'] as const)('group copy retires the full preview through observed %s ABA', async mode => {
  const f = await mounted(), before = structuredClone(f.controller().draft); click('预览复制完整视觉组'); const old = retained('粘贴到当前图');
  if (mode === 'draft') { act(() => f.controller().change({ ...f.controller().draft, title: 'Edited' })); act(() => f.controller().travel(false)); }
  else { f.rerender({ ...f.props, ...(mode === 'owner' ? { identity: 'other-owner' } : { [mode]: true }) }); f.rerender(f.props); }
  act(() => old()); expect(f.controller().draft).toEqual(before); expect(f.controller().past).toHaveLength(0);
});
it('group copy retires approval on an original saved-graph check even when the same source returns', async () => {
  const f = await mounted(), before = structuredClone(f.controller().draft); click('预览复制完整视觉组'); const oldPaste = retained('粘贴到当前图'), oldPreview = f.controller().previewGroupedSelectionCopy;
  let finish!: (value: typeof f.record) => void; f.graphs.get.mockImplementationOnce(() => new Promise(resolve => { finish = resolve; }));
  let pending!: Promise<void>; act(() => { pending = f.controller().checkServer(); oldPaste(); }); expect(f.controller().draft).toEqual(before);
  await act(async () => { finish(structuredClone(f.record)); await pending; }); act(() => { oldPaste(); oldPreview(); }); expect(f.controller().draft).toEqual(before); expect(f.controller().currentCopy).toBeUndefined();
  click('预览复制完整视觉组'); click('粘贴到当前图'); expect(f.controller().draft.nodes).toHaveLength(8);
});
