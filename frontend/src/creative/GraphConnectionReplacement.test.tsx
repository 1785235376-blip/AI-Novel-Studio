// @vitest-environment jsdom
import { StrictMode } from 'react';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { GraphConnectionReplacement } from './GraphConnectionReplacement';
import { graphConnectionReplacement } from './graphConnectionReplacementHelpers';
import { modelCatalog, modelGraph } from './studioGraphModel.testFixtures';
import { useStudioGraphEditorController, type StudioGraphEditorProps } from './useStudioGraphEditorController';
import { studioGraphEditorView } from './studioGraphEditorView';
import type { StudioClient } from './studioClient';
import type { StudioGraphSaveInput } from './studioGraphTypes';

afterEach(() => { cleanup(); vi.restoreAllMocks(); });
function fixture() {
  const record = modelGraph(), catalog = modelCatalog(false);
  record.definition = { schema_version: 1, title: 'Reconnect author input', viewport: { x: 0, y: 0, zoom: 1 }, nodes: [
    ...['old', 'fresh'].map((id, i) => ({ id, definition_id: 'text_input' as const, definition_version: 1 as const, enabled: true, position: { x: 0, y: i * 120 }, parameters: { text: `Author ${id}` } })),
    ...['middle', 'tail'].map((id, i) => ({ id, definition_id: 'text_reference' as const, definition_version: 1 as const, enabled: true, position: { x: 280 + i * 280, y: 0 }, parameters: {} })),
    { id: 'plan', definition_id: 'draft_prepare', definition_version: 1, enabled: true, position: { x: 840, y: 0 }, parameters: {} },
    { id: 'review', definition_id: 'human_review', definition_version: 1, enabled: true, position: { x: 1120, y: 0 }, parameters: {} },
  ], edges: [
    { id: 'original', source_node_id: 'old', source_port: 'text', target_node_id: 'middle', target_port: 'text' },
    { id: 'middle_tail', source_node_id: 'middle', source_port: 'text', target_node_id: 'tail', target_port: 'text' },
    { id: 'tail_plan', source_node_id: 'tail', source_port: 'text', target_node_id: 'plan', target_port: 'text' },
    { id: 'plan_review', source_node_id: 'plan', source_port: 'draft', target_node_id: 'review', target_port: 'draft' },
  ], presentation: { comment: 'Preserve annotation', groups: [{ id: 'authors', name: 'Author inputs', node_ids: ['old', 'fresh'] }] } };
  return { record, catalog };
}
const fresh = { nodeId: 'fresh', portId: 'text' };
const click = (name: string) => fireEvent.click(screen.getByRole('button', { name }));
const choose = (label: string, value: string) => fireEvent.change(screen.getByLabelText(label), { target: { value } });
const retained = (name: string) => { const button = screen.getByRole('button', { name }); return (button as any)[Object.keys(button).find(key => key.startsWith('__reactProps$'))!].onClick as () => void; };
function review() {
  choose('要重接的输入', 'original'); choose('重接的新输出', JSON.stringify(['fresh', 'text'])); click('预览输入重接');
  fireEvent.click(screen.getByLabelText('已核对旧新来源与下游范围，确认只替换此连接'));
}

it('replacement preserves all fields except the one source and reports disabled-input impact', () => {
  const { record, catalog } = fixture(), before = structuredClone(record.definition);
  const result = graphConnectionReplacement(record.definition, catalog, 'original', fresh);
  const expected = structuredClone(before); expected.edges[0].source_node_id = 'fresh';
  expect(result.definition).toEqual(expected); expect(record.definition).toEqual(before);
  expect(result.type).toBe('TEXT'); expect(result.affected).toEqual(['middle', 'tail', 'plan', 'review']); expect(result.newMissing).toEqual([]);
  record.definition.nodes.find(node => node.id === 'fresh')!.enabled = false;
  expect(graphConnectionReplacement(record.definition, catalog, 'original', fresh).newMissing).toEqual(['middle.text']);
  // Full edge capacity does not preclude a replacement that adds no edges.
  expect(graphConnectionReplacement(before, { ...catalog, limits: { ...catalog.limits, edges: before.edges.length } }, 'original', fresh).definition.edges).toHaveLength(before.edges.length);
});
it('replacement rejects no-op, missing, type/self/cycle, ambiguous input and byte capacity without partial changes', () => {
  const { record, catalog } = fixture(), graph = record.definition;
  for (const output of [{ nodeId: 'old', portId: 'text' }, { nodeId: 'missing', portId: 'text' },
    { nodeId: 'plan', portId: 'draft' }, { nodeId: 'middle', portId: 'text' }, { nodeId: 'tail', portId: 'text' }]) {
    const before = structuredClone(graph); expect(() => graphConnectionReplacement(graph, catalog, 'original', output)).toThrow(); expect(graph).toEqual(before);
  }
  const ambiguous = structuredClone(graph); ambiguous.edges.push({ ...ambiguous.edges[0], id: 'another', source_node_id: 'fresh' });
  expect(() => graphConnectionReplacement(ambiguous, catalog, 'original', fresh)).toThrow(/单输入/);
  expect(() => graphConnectionReplacement(graph, catalog, 'gone', fresh)).toThrow(/变化/);
  expect(() => graphConnectionReplacement(graph, { ...catalog, limits: { ...catalog.limits, definition_bytes: 10 } }, 'original', fresh)).toThrow(/容量/);
});
it('replacement requires explicit current consent, retires batched selection ABA and consumes a confirmed callback once', () => {
  const { record, catalog } = fixture(), apply = vi.fn(() => true);
  const view = render(<StrictMode><GraphConnectionReplacement definition={record.definition} catalog={catalog} owner={{}} disabled={false} isCurrent={() => true} onApply={apply} /></StrictMode>);
  review(); expect(apply).not.toHaveBeenCalled(); const stale = retained('确认重接到本地草稿');
  act(() => { choose('重接的新输出', JSON.stringify(['old', 'text'])); choose('重接的新输出', JSON.stringify(['fresh', 'text'])); stale(); });
  expect(apply).not.toHaveBeenCalled(); click('预览输入重接'); fireEvent.click(screen.getByLabelText('已核对旧新来源与下游范围，确认只替换此连接'));
  const current = retained('确认重接到本地草稿'); act(() => { current(); current(); });
  expect(apply).toHaveBeenCalledTimes(1); expect(apply).toHaveBeenCalledWith('original', 'fresh', 'text');
  view.unmount(); act(() => current()); expect(apply).toHaveBeenCalledTimes(1);
});
it.each(['owner', 'draft', 'busy'] as const)('replacement retires reviewed preview and retained confirmation through %s ABA', kind => {
  const { record, catalog } = fixture(), apply = vi.fn(() => true), owner = {};
  const props = { definition: record.definition, catalog, owner, disabled: false, isCurrent: () => true, onApply: apply };
  const view = render(<GraphConnectionReplacement {...props} />); review(); const stale = retained('确认重接到本地草稿');
  const changed = kind === 'owner' ? { owner: {} } : kind === 'draft' ? { definition: { ...record.definition, title: 'Other' } } : { disabled: true };
  view.rerender(<GraphConnectionReplacement {...props} {...changed} />); view.rerender(<GraphConnectionReplacement {...props} />);
  act(() => stale()); expect(apply).not.toHaveBeenCalled(); expect(screen.queryByRole('region', { name: '输入重接影响预览' })).toBeNull();
});
async function mounted() {
  const f = fixture(); let record = f.record;
  const graphs = { catalog: vi.fn(async () => f.catalog), list: vi.fn(async () => ({ items: [structuredClone(record)] })), get: vi.fn(async () => structuredClone(record)),
    save: vi.fn(async (_id: string | undefined, input: StudioGraphSaveInput) => { record = { ...record, version: record.version + 1, definition: structuredClone(input.definition) }; return structuredClone(record); }),
    preflight: vi.fn(), createRun: vi.fn(), action: vi.fn(), runs: vi.fn(async () => ({ items: [] })) };
  const props: StudioGraphEditorProps = { active: true, denied: false, identity: 'reconnect-owner', client: { graphs } as unknown as StudioClient,
    canMutate: true, canReview: true, busy: false, externalDirty: false, isCurrent: () => true, read: async work => work(), mutate: async work => work() };
  let controller!: ReturnType<typeof useStudioGraphEditorController>;
  function Harness({ value }: { value: StudioGraphEditorProps }) { controller = useStudioGraphEditorController(value); return studioGraphEditorView(controller, value).content; }
  const view = render(<Harness value={props} />);
  await waitFor(() => expect(controller.editable).toBe(true)); await act(() => controller.open(record.id));
  return { ...f, graphs, props, controller: () => controller, view, Harness };
}
it('replacement wires the actual view/controller to one undo/redo then explicit save/reopen with zero execution', async () => {
  const f = await mounted(), before = structuredClone(f.controller().draft);
  review(); expect(f.controller().draft).toEqual(before); expect(f.controller().past).toHaveLength(0);
  click('确认重接到本地草稿'); const expected = structuredClone(before); expected.edges[0].source_node_id = 'fresh';
  expect(f.controller().draft).toEqual(expected); expect(f.controller().past).toHaveLength(1); expect(f.graphs.save).not.toHaveBeenCalled();
  click('撤销图编辑'); expect(f.controller().draft).toEqual(before); expect(f.controller().past).toHaveLength(0);
  click('重做图编辑'); expect(f.controller().draft).toEqual(expected); expect(f.controller().past).toHaveLength(1);
  click('保存创作图'); await waitFor(() => expect(f.graphs.save).toHaveBeenCalledTimes(1));
  expect(f.graphs.save.mock.calls[0][1]).toEqual({ expected_version: 1, definition: expected });
  await waitFor(() => expect(f.controller().base?.version).toBe(2)); await act(() => f.controller().open('model_graph'));
  expect(f.controller().draft).toEqual(expected);
  for (const fn of [f.graphs.preflight, f.graphs.createRun, f.graphs.action]) expect(fn).not.toHaveBeenCalled();
});
it('replacement original controller rejects synchronous selection/lock fences and retained authority or draft ABA', async () => {
  const f = await mounted(), before = structuredClone(f.controller().draft), scope = f.controller().connectionReplacementScope, stale = f.controller().replaceConnection;
  act(() => { f.controller().setSelected(['fresh']); expect(stale('original', 'fresh', 'text', scope)).toBe(false); });
  expect(f.controller().past).toHaveLength(0);
  const currentScope = f.controller().connectionReplacementScope, previous = f.controller().replaceConnection;
  f.view.rerender(<f.Harness value={{ ...f.props, busy: true }} />); f.view.rerender(<f.Harness value={f.props} />);
  act(() => expect(previous('original', 'fresh', 'text', currentScope)).toBe(false));
  const draftScope = f.controller().connectionReplacementScope, old = f.controller().replaceConnection;
  act(() => f.controller().change({ ...f.controller().draft, title: 'Change then undo' })); act(() => f.controller().travel(false));
  act(() => expect(old('original', 'fresh', 'text', draftScope)).toBe(false));
  expect(f.controller().draft).toEqual(before); expect(f.controller().past).toHaveLength(0); expect(f.graphs.save).not.toHaveBeenCalled();
});
it('replacement retires approval synchronously when the original saved-graph recheck starts and after it completes', async () => {
  const f = await mounted(), before = structuredClone(f.controller().draft), scope = f.controller().connectionReplacementScope, stale = f.controller().replaceConnection;
  let finish!: (record: typeof f.record) => void;
  f.graphs.get.mockImplementationOnce(() => new Promise(resolve => { finish = resolve; }));
  act(() => { void f.controller().checkServer(); expect(stale('original', 'fresh', 'text', scope)).toBe(false); });
  expect(f.controller().draft).toEqual(before); expect(f.controller().past).toHaveLength(0);
  await act(async () => finish(structuredClone(f.record))); await waitFor(() => expect(f.controller().checking).toBe(false));
  act(() => expect(stale('original', 'fresh', 'text', scope)).toBe(false));
  act(() => expect(f.controller().replaceConnection('original', 'fresh', 'text', f.controller().connectionReplacementScope)).toBe(true));
  expect(f.controller().draft.edges[0].source_node_id).toBe('fresh'); expect(f.controller().past).toHaveLength(1); expect(f.graphs.save).not.toHaveBeenCalled();
});
