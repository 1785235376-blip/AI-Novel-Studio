// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, renderHook, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { useStudioGraphEditorController, type StudioGraphEditorProps } from './useStudioGraphEditorController';
import { studioGraphEditorView } from './studioGraphEditorView';
import { imageGraphCatalog } from './studioImageGraph.testFixtures';
import { samplingProvider, samplingRecord } from './studioGraphRecipeParameters.testFixtures';
import type { StudioClient } from './studioClient';
import type { StudioGraphPreflight, StudioGraphPreflightInput, StudioGraphSaveInput } from './studioGraphTypes';
afterEach(cleanup);
function fixture() {
  let saved = samplingRecord();
  const providers = vi.fn().mockResolvedValue([samplingProvider()]);
  const noExecution = { createRun: vi.fn(), previewMedia: vi.fn(), dispatchMedia: vi.fn(), executeMedia: vi.fn() };
  const client = { graphs: { catalog: vi.fn().mockResolvedValue(imageGraphCatalog()), imageCatalog: vi.fn().mockResolvedValue(imageGraphCatalog()),
    list: vi.fn(async () => ({ items: [structuredClone(saved)] })), get: vi.fn(async () => structuredClone(saved)),
    save: vi.fn(async (_id: string, input: StudioGraphSaveInput) => { expect(input.expected_version).toBe(saved.version); saved = { ...saved, definition: structuredClone(input.definition), version: saved.version + 1 }; return structuredClone(saved); }),
    runs: vi.fn().mockResolvedValue({ items: [] }),
    preflight: vi.fn(async (_id: string, input: StudioGraphPreflightInput): Promise<StudioGraphPreflight> => ({ project_id: saved.project_id, scope: saved.scope,
      graph_id: saved.id, valid: true, executable: true, issues: [], execution_order: ['prompt', 'generate', 'review'], selected_closure: ['prompt', 'generate', 'review'], definition_digest: saved.definition_digest,
      preflight_digest: 'd'.repeat(64), expected_version: saved.version, target_node_ids: input.target_node_ids, model_called: false, external_calls: 0 })), ...noExecution,
  } } as unknown as StudioClient;
  const props: StudioGraphEditorProps = { active: true, denied: false, identity: 'sampling-owner', client, providerSource: { providers }, canMutate: true, canReview: true,
    busy: false, externalDirty: false, isCurrent: () => true, read: work => work(), mutate: work => work() };
  return { client, props, providers, noExecution, saved: () => saved };
}
async function setup() {
  const f = fixture(), hook = renderHook(props => useStudioGraphEditorController(props), { initialProps: f.props });
  await waitFor(() => expect(hook.result.current.editable).toBe(true));
  await act(() => hook.result.current.open(f.saved().id));
  act(() => hook.result.current.setSelected(['generate']));
  await act(() => hook.result.current.providerPicker.load());
  expect(hook.result.current.recipeParameters.canEdit).toBe(true);
  return { ...f, ...hook };
}
it('applies once through original history, undoes/redoes, then CAS-saves and reopens the same configuration without dispatch', async () => {
  const api = await setup(), original = structuredClone(api.result.current.draft), oldSave = api.result.current.save, oldCurrent = api.result.current.runInputCurrent;
  act(() => { api.result.current.recipeParameters.edit('steps', '37'); expect(oldCurrent()).toBe(false); void oldSave(); });
  act(() => api.result.current.recipeParameters.edit('seed', '424242'));
  expect(api.result.current.draft).toEqual(original); expect(api.client.graphs.save).not.toHaveBeenCalled(); expect(api.result.current.dirty).toBe(true);
  const count = api.result.current.past.length, apply = api.result.current.recipeParameters.apply;
  act(() => { apply(); apply(); expect(oldCurrent()).toBe(false); });
  expect(api.result.current.past).toHaveLength(count + 1); expect(api.result.current.node!.parameters.parameters).toMatchObject({ steps: 37, seed: 424242 });
  expect(api.result.current.recipeParameters.formDirty).toBe(false);
  const edited = structuredClone(api.result.current.draft);
  act(() => api.result.current.travel(false)); expect(api.result.current.draft).toEqual(original);
  act(() => api.result.current.travel(true)); expect(api.result.current.draft).toEqual(edited);
  await act(() => api.result.current.save()); expect(api.client.graphs.save).toHaveBeenCalledTimes(1);
  await act(() => api.result.current.open(api.saved().id)); expect(api.result.current.draft).toEqual(edited); expect(api.result.current.base?.version).toBe(2);
  Object.values(api.noExecution).forEach(fn => expect(fn).not.toHaveBeenCalled());
});
it.each(['draft ABA', 'selection ABA'] as const)('retires a retained Apply synchronously after %s, even before React renders', async kind => {
  const api = await setup(); act(() => api.result.current.recipeParameters.edit('steps', '37'));
  const controller = api.result.current, apply = controller.recipeParameters.apply, original = controller.draft;
  act(() => {
    if (kind === 'draft ABA') { controller.change({ ...original, title: 'temporary' }); controller.change(original); }
    else { controller.setSelected(['prompt']); controller.setSelected(['generate']); }
    apply();
  });
  expect(api.result.current.draft).toEqual(original); expect(api.result.current.recipeParameters.stale).toBe(true);
  act(() => api.result.current.recipeParameters.apply()); expect(api.result.current.draft).toEqual(original);
  expect(api.client.graphs.save).not.toHaveBeenCalled(); Object.values(api.noExecution).forEach(fn => expect(fn).not.toHaveBeenCalled());
});
it('retires original run intent synchronously after graph A/B/A even when no parameter form is open', async () => {
  const api = await setup(), controller = api.result.current, original = controller.draft, current = controller.runInputCurrent;
  expect(current()).toBe(true);
  act(() => { controller.change({ ...original, title: 'temporary run input' }); controller.change(original); expect(current()).toBe(false); });
  expect(api.result.current.draft).toEqual(original); expect(api.result.current.runInputCurrent()).toBe(true);
  Object.values(api.noExecution).forEach(fn => expect(fn).not.toHaveBeenCalled());
});
it('keeps expired author input until discard and refuses stale Apply after write authority A/B/A', async () => {
  const api = await setup(); act(() => api.result.current.recipeParameters.edit('seed', '424242')); const apply = api.result.current.recipeParameters.apply;
  api.rerender({ ...api.props, canMutate: false }); api.rerender(api.props);
  act(() => apply()); expect(api.result.current.node!.parameters.parameters?.seed).toBe(7);
  expect(api.result.current.recipeParameters.fields.seed).toBe('424242'); expect(api.result.current.recipeParameters.canApply).toBe(false);
  act(() => api.result.current.recipeParameters.clear()); expect(api.result.current.recipeParameters.formDirty).toBe(false);
});
it('blocks form edits while the original run owner reports unresolved execution and never resends', async () => {
  const api = await setup(), edit = api.result.current.recipeParameters.edit;
  act(() => api.result.current.setExecutionDirty(true)); act(() => edit('steps', '37'));
  expect(api.result.current.recipeParameters.canEdit).toBe(false); expect(api.result.current.draft.nodes[1].parameters.parameters?.steps).toBe(20);
  Object.values(api.noExecution).forEach(fn => expect(fn).not.toHaveBeenCalled());
});
it('renders the new lower-flow form through the real owner/view and invalidates existing preflight when author input starts', async () => {
  const f = fixture(); let controller!: ReturnType<typeof useStudioGraphEditorController>;
  function Harness() { controller = useStudioGraphEditorController(f.props); const view = studioGraphEditorView(controller, f.props); return <>{view.content}{view.inspector}</>; }
  render(<Harness/>); await waitFor(() => expect(controller.editable).toBe(true)); await act(() => controller.open(f.saved().id));
  act(() => controller.setSelected(['generate'])); fireEvent.click(screen.getByRole('button', { name: '核对本节点配置' }));
  await waitFor(() => expect((screen.getByLabelText('执行流程采样步数') as HTMLInputElement).disabled).toBe(false));
  const preflight = screen.getByRole('button', { name: '核对运行范围' }); fireEvent.click(preflight); await screen.findByLabelText('运行预检');
  fireEvent.change(screen.getByLabelText('执行流程采样步数'), { target: { value: '37' } });
  expect((screen.getByRole('button', { name: '保存创作图' }) as HTMLButtonElement).disabled).toBe(true);
  expect(controller.runInputCurrent()).toBe(false);
  const consent = screen.queryByLabelText('已核对当前图版本、节点范围与本地处理边界') as HTMLInputElement | null;
  if (consent) expect(consent.disabled).toBe(true);
  fireEvent.change(screen.getByLabelText('执行流程种子'), { target: { value: '424242' } });
  fireEvent.click(screen.getByRole('button', { name: '应用采样参数到原图草稿' }));
  expect(controller.node!.parameters.parameters).toMatchObject({ steps: 37, seed: 424242 });
  expect(f.client.graphs.preflight).toHaveBeenCalledTimes(1); Object.values(f.noExecution).forEach(fn => expect(fn).not.toHaveBeenCalled());
});
