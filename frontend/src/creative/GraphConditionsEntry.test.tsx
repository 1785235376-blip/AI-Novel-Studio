// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, renderHook, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import actual from './fixtures/conditions.file-api.json';
import { modelCatalog } from './studioGraphModel.testFixtures';
import { useStudioGraphEditorController, type StudioGraphEditorProps } from './useStudioGraphEditorController';
import { studioGraphEditorView } from './studioGraphEditorView';
import { GraphRunPanel } from './GraphRunPanel';
import type { StudioClient } from './studioClient';
import type { StudioGraphDefinition, StudioGraphRecord, StudioGraphCatalog, StudioGraphPreflight, StudioGraphRun } from './studioGraphTypes';
afterEach(() => { cleanup(); vi.restoreAllMocks(); });
function setup() {
  const create = vi.fn(async (body: { definition: StudioGraphDefinition }) => ({ ...structuredClone(actual.graph), definition: body.definition }) as unknown as StudioGraphRecord), createRun = vi.fn(), action = vi.fn();
  const props: StudioGraphEditorProps = { active: true, denied: false, identity: 'conditions-owner', canMutate: true, canReview: true, busy: false, externalDirty: false, isCurrent: () => true, read: work => work(), mutate: work => work(), client: { graphs: { catalog: vi.fn(async () => modelCatalog(false)), list: vi.fn(async () => ({ items: [] })), conditionsCatalog: vi.fn(async () => structuredClone(actual.catalog)), conditionsList: vi.fn(async () => ({ items: [] })), create, createRun, action, runs: vi.fn(async () => ({ items: [] })) } } as unknown as StudioClient };
  return { props, create, createRun, action };
}
it('prepares only after explicit discovery and blank source; uses original history and Save without automatic run', async () => {
  const { props, create, createRun, action } = setup();
  function Harness() { const c = useStudioGraphEditorController(props), v = studioGraphEditorView(c, props); return <>{v.content}{v.inspector}</>; }
  render(<Harness />); await screen.findByLabelText('节点类型');
  expect(screen.queryByRole('button', { name: '准备六节点条件草稿' })).toBeNull(); expect(props.client.graphs.conditionsCatalog).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: '核对条件图能力与目录' }));
  await screen.findByRole('button', { name: '准备六节点条件草稿' }); fireEvent.click(screen.getByRole('button', { name: '准备六节点条件草稿' }));
  expect(screen.getByLabelText('条件类型')).toBeTruthy();
  fireEvent.change(screen.getByLabelText('条件类型'), { target: { value: 'enum' } }); fireEvent.change(screen.getByLabelText('比较目标'), { target: { value: 'B' } });
  expect(create).not.toHaveBeenCalled(); expect(createRun).not.toHaveBeenCalled(); expect(action).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: '撤销图编辑' })); expect((screen.getByLabelText('比较目标') as HTMLSelectElement).value).toBe('A');
  fireEvent.click(screen.getByRole('button', { name: '重做图编辑' })); expect((screen.getByLabelText('比较目标') as HTMLSelectElement).value).toBe('B');
  fireEvent.click(screen.getByRole('button', { name: '保存创作图' })); await waitFor(() => expect(create).toHaveBeenCalledTimes(1));
  const d = create.mock.calls[0][0].definition; expect(d.schema_version).toBe(7); expect(d.nodes).toHaveLength(6); expect(d.edges).toHaveLength(5); expect(d.nodes[1].parameters.predicate).toEqual({ kind: 'enum', value: 'A', equals: 'B' });
  expect(createRun).not.toHaveBeenCalled(); expect(action).not.toHaveBeenCalled();
});
it('fences retained condition callbacks on busy, source, permission and selection ABA; rejects structural edits', async () => {
  const { props } = setup(); const view = renderHook(p => useStudioGraphEditorController(p), { initialProps: props }); await waitFor(() => expect(view.result.current.catalog).toBeTruthy());
  await act(async () => view.result.current.loadConditions()); act(() => view.result.current.createConditions());
  const initial = structuredClone(view.result.current.draft), retained = view.result.current.updateCondition, oldChange = view.result.current.change;
  view.rerender({ ...props, busy: true }); view.rerender(props); act(() => retained({ kind: 'boolean', value: false })); expect(view.result.current.draft).toEqual(initial);
  const permission = view.result.current.updateCondition; view.rerender({ ...props, canMutate: false }); view.rerender(props); act(() => permission({ kind: 'boolean', value: false })); expect(view.result.current.draft).toEqual(initial);
  const selection = view.result.current.updateCondition; act(() => view.result.current.setSelected(['input'])); act(() => view.result.current.setSelected(['condition'])); act(() => selection({ kind: 'boolean', value: false })); expect(view.result.current.draft).toEqual(initial);
  act(() => oldChange({ ...initial, title: 'old callback' })); expect(view.result.current.draft.title).toBe(initial.title);
  act(() => view.result.current.change({ ...initial, edges: [] })); expect(view.result.current.draft.edges).toEqual(initial.edges);
  act(() => view.result.current.updateCondition({ kind: 'boolean', value: false })); expect(view.result.current.draft.nodes[1].parameters.predicate).toEqual({ kind: 'boolean', value: false });
  act(() => view.result.current.createConditions()); expect(view.result.current.draft.nodes).toHaveLength(6);
});
it('drops a late capability read across source ABA and keeps dirty/permission/busy guards', async () => {
  const { props } = setup(); let resolve!: (v: StudioGraphCatalog) => void;
  props.client.graphs.conditionsCatalog = vi.fn(() => new Promise<StudioGraphCatalog>(r => { resolve = r; }));
  const view = renderHook(p => useStudioGraphEditorController(p), { initialProps: props }); await waitFor(() => expect(view.result.current.catalog).toBeTruthy());
  let pending!: Promise<void>; act(() => { pending = view.result.current.loadConditions(); });
  act(() => view.result.current.change({ ...view.result.current.draft, title: 'Changed during read' }));
  await act(async () => { resolve(actual.catalog as unknown as StudioGraphCatalog); await pending; }); expect(view.result.current.conditionCatalog).toBeUndefined();
  view.rerender({ ...props, externalDirty: true }); await act(async () => view.result.current.loadConditions()); expect(props.client.graphs.conditionsCatalog).toHaveBeenCalledTimes(1);
});

it('uses whole-graph preflight despite a single selected node, then original create/execute/review and normal skip rendering', async () => {
  const preflight = vi.fn(async (_id: string, _input: unknown) => structuredClone(actual.preflight) as unknown as StudioGraphPreflight), createRun = vi.fn(async () => structuredClone(actual.queued) as unknown as StudioGraphRun), action = vi.fn(async (_id: string, command: string, _input: unknown) => structuredClone(command === 'approve' ? actual.approved : actual.waiting) as unknown as StudioGraphRun);
  const client = { preflight, createRun, action, runs: vi.fn(async () => ({ items: [] })) } as unknown as StudioClient['graphs'];
  render(<GraphRunPanel client={client} graph={actual.graph as unknown as StudioGraphRecord} targetNodeIds={['yes_review']} dirty={false} busy={false} canMutate canReview isCurrent={() => true} read={work => work()} mutate={work => work()} />);
  fireEvent.click(screen.getByRole('button', { name: '核对运行范围' })); await screen.findByText(/整图条件预检/);
  expect(preflight.mock.calls[0][1]).toEqual({ expected_version: 2, target_node_ids: [] });
  fireEvent.click(screen.getByLabelText('已核对当前图版本、节点范围与本地处理边界')); fireEvent.click(screen.getByRole('button', { name: '创建本地运行' }));
  await screen.findAllByText('条件未选中，已正常跳过；派发 0，输出 0。'); expect(createRun).toHaveBeenCalledTimes(1); expect(action).not.toHaveBeenCalled();
  expect(screen.queryByRole('button', { name: '检查节点 no' })).toBeNull();
  fireEvent.click(screen.getByRole('button', { name: '执行本地节点' })); await screen.findByText('待审核输出 · yes_review');
  fireEvent.click(screen.getByLabelText('已阅读本次输出并核对当前审核摘要')); fireEvent.click(screen.getByRole('button', { name: '批准节点输出' }));
  await waitFor(() => expect(action).toHaveBeenCalledTimes(2)); expect(action.mock.calls[1][2]).toMatchObject({ node_id: 'yes_review', reviewed_output_digest: actual.waiting.review.output_digest });
});
