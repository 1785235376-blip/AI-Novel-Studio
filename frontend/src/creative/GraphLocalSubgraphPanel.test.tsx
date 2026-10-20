// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, renderHook, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import actual from './fixtures/localSubgraph.file-api.json';
import { modelCatalog } from './studioGraphModel.testFixtures';
import { useStudioGraphEditorController, type StudioGraphEditorProps } from './useStudioGraphEditorController';
import { studioGraphEditorView } from './studioGraphEditorView';
import { useGraphLocalSubgraphParent } from './useGraphLocalSubgraphParent';
import type { StudioClient } from './studioClient';
import type { StudioGraphCatalog, StudioGraphDefinition, StudioGraphRecord } from './studioGraphTypes';

afterEach(() => { cleanup(); vi.restoreAllMocks(); });
const child = () => structuredClone(actual.child) as unknown as StudioGraphRecord;
const catalog = () => structuredClone(actual.catalog) as unknown as StudioGraphCatalog;
const button = (name: string) => screen.getByRole('button', { name });
const deferred = <T,>() => { let resolve!: (value: T) => void; const promise = new Promise<T>(value => { resolve = value; }); return { promise, resolve }; };

it('uses original change/undo/redo/Save/reopen for the fixed parent and never creates or executes a run automatically', async () => {
  let saved: StudioGraphRecord | undefined;
  const create = vi.fn(async (body: { definition: StudioGraphDefinition }) => {
    saved = { ...structuredClone(actual.parent), id: 'saved-local-parent', definition: body.definition,
      reference_states: [{ node_id: body.definition.nodes[1].id, state: 'CURRENT' }] } as unknown as StudioGraphRecord;
    return saved;
  });
  const get = vi.fn(async (id: string) => id === saved?.id ? saved : child()), createRun = vi.fn(), action = vi.fn();
  const preflight = vi.fn(async (_id: string, input: { target_node_ids: string[] }) => {
    const ids = saved!.definition.nodes.filter(node => node.enabled).map(node => node.id);
    return { ...actual.preflight, graph_id: saved!.id, expected_version: saved!.version,
      target_node_ids: input.target_node_ids.length ? input.target_node_ids : ids, selected_closure: ids, execution_order: ids };
  });
  const props: StudioGraphEditorProps = { active: true, denied: false, identity: 'original-owner', canMutate: true, canReview: true,
    busy: false, externalDirty: false, isCurrent: () => true, read: work => work(), mutate: work => work(),
    client: { graphs: { catalog: vi.fn(async () => modelCatalog(false)), list: vi.fn(async () => ({ items: [child()] })),
      localSubgraphCatalog: vi.fn(async () => catalog()), localSubgraphList: vi.fn(async () => ({ items: [child(), ...(saved ? [saved] : [])] })),
      get, create, createRun, action, preflight, runs: vi.fn(async () => ({ items: [] })) } } as unknown as StudioClient };
  function Harness() { const controller = useStudioGraphEditorController(props); return studioGraphEditorView(controller, props).content; }
  render(<Harness />);
  await screen.findByLabelText('节点类型');
  fireEvent.click(screen.getByText('受限本地子调用 · 首片'));
  fireEvent.click(button('明确读取受限子调用与已保存图目录'));
  await waitFor(() => expect(screen.getByRole('option', { name: /Reusable local author rule/ })).toBeTruthy());
  fireEvent.change(screen.getByLabelText('已保存 schema 1 子图'), { target: { value: actual.child.id } });
  fireEvent.click(button('读取当前版本并核对接口闭包'));
  await screen.findByLabelText('受限父草稿预览');
  fireEvent.change(screen.getByLabelText('受限父级作者文本'), { target: { value: 'Explicit authored parent scene' } });
  fireEvent.click(screen.getByLabelText('我已核对当前 pin、接口与容量，仅生成父草稿，之后明确保存'));
  fireEvent.click(button('明确生成受限父草稿'));
  expect(document.querySelectorAll('[data-graph-node-id]')).toHaveLength(3);
  expect(create).not.toHaveBeenCalled(); expect(createRun).not.toHaveBeenCalled(); expect(action).not.toHaveBeenCalled();
  expect((button('添加节点') as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(button('撤销图编辑')); expect(document.querySelectorAll('[data-graph-node-id]')).toHaveLength(0);
  fireEvent.click(button('重做图编辑')); expect(document.querySelectorAll('[data-graph-node-id]')).toHaveLength(3);
  fireEvent.click(button('保存创作图'));
  await waitFor(() => expect(create).toHaveBeenCalledTimes(1));
  expect(create.mock.calls[0][0].definition.nodes[1].parameters.expected_version).toBe(1);
  fireEvent.click(button('新建空图'));
  fireEvent.change(screen.getByLabelText('已保存创作图'), { target: { value: saved!.id } });
  await waitFor(() => expect(get).toHaveBeenCalledWith(saved!.id));
  await waitFor(() => expect(document.querySelectorAll('[data-graph-node-id]')).toHaveLength(3));
  fireEvent.click(button('核对运行范围'));
  await screen.findByLabelText('已核对当前图版本、节点范围与本地处理边界');
  fireEvent.click(screen.getByLabelText('已核对当前图版本、节点范围与本地处理边界'));
  expect((button('创建本地运行') as HTMLButtonElement).disabled).toBe(false);
  expect(preflight.mock.calls[0][1].target_node_ids).toEqual(saved!.definition.nodes.map(node => node.id));
  expect(createRun).not.toHaveBeenCalled(); expect(action).not.toHaveBeenCalled();
});

function hookProps() {
  return { client: { localSubgraphCatalog: vi.fn(async () => catalog()), localSubgraphList: vi.fn(async () => ({ items: [child()] })),
    get: vi.fn(async () => child()) } as unknown as StudioClient['graphs'], identity: 'A', scope: {}, readable: true, blank: true,
    current: () => true, locked: () => false, read: <T,>(work: () => Promise<T>) => work(), onRecords: vi.fn(), onCatalog: vi.fn(), apply: vi.fn(() => true) };
}
async function prepared(result: { current: ReturnType<typeof useGraphLocalSubgraphParent> }) {
  await act(async () => { await result.current.load(); });
  act(() => result.current.choose(actual.child.id));
  await act(async () => { await result.current.verify(); });
  act(() => result.current.edit('Author input'));
  act(() => result.current.confirm(true));
  expect(result.current.confirmed).toBe(true);
}

it('retires old confirmation callbacks on source/owner/busy ABA and same-batch uncheck, then consumes a fresh apply once', async () => {
  const props = hookProps(), view = renderHook(value => useGraphLocalSubgraphParent(value), { initialProps: props });
  await prepared(view.result);
  const old = view.result.current.create;
  act(() => { view.result.current.confirm(false); old(); });
  expect(props.apply).not.toHaveBeenCalled();
  act(() => view.result.current.confirm(true));
  const busyCallback = view.result.current.create;
  view.rerender({ ...props, locked: () => true }); view.rerender(props);
  act(() => busyCallback()); expect(props.apply).not.toHaveBeenCalled();
  const ownerCallback = view.result.current.create;
  view.rerender({ ...props, identity: 'B', scope: {} }); view.rerender(props);
  act(() => ownerCallback()); expect(props.apply).not.toHaveBeenCalled(); expect(view.result.current.preview).toBeUndefined();
  await prepared(view.result);
  const fresh = view.result.current.create;
  act(() => { fresh(); fresh(); }); expect(props.apply).toHaveBeenCalledTimes(1);
});

it('hides late source results after authority loss and refuses a current-version change rather than adopting a newer pin', async () => {
  const props = hookProps(), gate = deferred<StudioGraphRecord>();
  const get = vi.fn(() => gate.promise); props.client.get = get;
  const view = renderHook(value => useGraphLocalSubgraphParent(value), { initialProps: props });
  await act(async () => { await view.result.current.load(); });
  act(() => view.result.current.choose(actual.child.id));
  let pending!: Promise<void>;
  act(() => { pending = view.result.current.verify(); });
  view.rerender({ ...props, readable: false });
  await act(async () => { gate.resolve(child()); await pending; });
  expect(view.result.current.preview).toBeUndefined(); expect(view.result.current.rows).toEqual([]); expect(props.apply).not.toHaveBeenCalled();
  const changed = child(); changed.version = 2;
  props.client.get = vi.fn(async () => changed); view.rerender(props);
  await act(async () => { await view.result.current.load(); });
  act(() => view.result.current.choose(actual.child.id));
  await act(async () => { await view.result.current.verify(); });
  expect(view.result.current.preview).toBeUndefined(); expect(view.result.current.error).toContain('旧 pin 未采用');
});
