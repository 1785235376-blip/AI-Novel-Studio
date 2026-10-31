// @vitest-environment jsdom
import { act, cleanup, renderHook, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { useStudioGraphEditorController, type StudioGraphEditorProps } from './useStudioGraphEditorController';
import { modelCatalog } from './studioGraphModel.testFixtures';
import type { StudioClient } from './studioClient';
afterEach(cleanup);
const props = (): StudioGraphEditorProps => ({ active: true, denied: false, identity: 'project-A:actor-A', canMutate: true, canReview: true, busy: false, externalDirty: false, isCurrent: () => true,
  read: work => work(), mutate: work => work(), client: { graphs: { catalog: vi.fn().mockResolvedValue(modelCatalog()), list: vi.fn().mockResolvedValue({ items: [] }) } } as unknown as StudioClient });
it.each(['identity', 'client', 'denied', 'canMutate', 'externalDirty', 'active'] as const)('invalidates copied content on %s change', async key => {
  const initial = props(), hook = renderHook(value => useStudioGraphEditorController(value), { initialProps: initial });
  await waitFor(() => expect(hook.result.current.editable).toBe(true));
  act(() => hook.result.current.addNode());
  act(() => hook.result.current.previewSelectionCopy()); expect(hook.result.current.currentCopy).toBeTruthy();
  const changed = { ...initial, [key]: key === 'identity' ? 'project-B:actor-A' : key === 'client' ? props().client : key === 'canMutate' || key === 'active' ? false : true };
  hook.rerender(changed); expect(hook.result.current.currentCopy).toBeUndefined();
  act(() => hook.result.current.pasteSelectionCopy());
  expect(hook.result.current.draft.nodes.length).toBe(key === 'denied' ? 0 : 1);
});
it('rechecks synchronous busy fence before atomic application', async () => {
  let busy = false;
  const initial = { ...props(), isBusy: () => busy }, hook = renderHook(() => useStudioGraphEditorController(initial));
  await waitFor(() => expect(hook.result.current.editable).toBe(true));
  act(() => hook.result.current.addNode()); act(() => hook.result.current.previewSelectionCopy());
  busy = true; act(() => hook.result.current.pasteSelectionCopy()); expect(hook.result.current.draft.nodes).toHaveLength(1);
  busy = false; act(() => hook.result.current.pasteSelectionCopy()); expect(hook.result.current.draft.nodes).toHaveLength(2);
  act(() => hook.result.current.pasteSelectionCopy()); expect(hook.result.current.draft.nodes).toHaveLength(2);
});

it('does not resurrect a preview after draft edit and undo return to identical source', async () => {
  const initial = props(), hook = renderHook(() => useStudioGraphEditorController(initial));
  await waitFor(() => expect(hook.result.current.editable).toBe(true));
  act(() => hook.result.current.addNode()); act(() => hook.result.current.previewSelectionCopy());
  const source = structuredClone(hook.result.current.draft);
  act(() => hook.result.current.change({ ...source, title: 'Changed' }));
  act(() => hook.result.current.travel(false)); expect(hook.result.current.draft).toEqual(source);
  expect(hook.result.current.currentCopy).toBeUndefined();
  act(() => hook.result.current.pasteSelectionCopy()); expect(hook.result.current.draft.nodes).toHaveLength(1);
});

import { modelGraph } from './studioGraphModel.testFixtures';
import { blankGraph } from './graphDraft';
import type { StudioGraphRecord } from './studioGraphTypes';
async function crossFixture() {
  const initial = props(), source = modelGraph(), target: StudioGraphRecord = { ...structuredClone(source), id: 'target', definition: { ...blankGraph(), schema_version: 2, title: 'Target' } };
  const rows = [source, target];
  initial.client.graphs.get = vi.fn(async id => structuredClone(rows.find(row => row.id === id)!));
  initial.client.graphs.save = vi.fn(async (id, input) => ({ ...structuredClone(rows.find(row => row.id === id)!), definition: input.definition, version: input.expected_version + 1 }));
  const hook = renderHook(value => useStudioGraphEditorController(value), { initialProps: initial });
  await waitFor(() => expect(hook.result.current.editable).toBe(true));
  await act(() => hook.result.current.open(source.id));
  act(() => hook.result.current.setSelected(['input', 'generate']));
  act(() => hook.result.current.captureSelectionForGraph());
  return { hook, initial, source, target };
}
it('keeps exact captured source across graph switches and pastes once through original undo/save', async () => {
  const { hook, source, target, initial } = await crossFixture();
  const receipt = structuredClone(hook.result.current.sourceCopy!.record);
  source.version++; source.definition_digest = 'e'.repeat(64); source.definition.nodes[0].parameters.text = 'Later change';
  await act(() => hook.result.current.open(target.id));
  expect(hook.result.current.sourceCopy!.record).toEqual(receipt);
  act(() => hook.result.current.previewCrossGraphCopy());
  expect(hook.result.current.currentCrossCopy?.nodeCount).toBe(2);
  expect(initial.client.graphs.save).not.toHaveBeenCalled();
  act(() => { hook.result.current.pasteCrossGraphCopy(); hook.result.current.pasteCrossGraphCopy(); });
  expect(hook.result.current.draft.nodes).toHaveLength(2);
  expect(hook.result.current.draft.nodes[0].parameters.text).toBe('Author source');
  act(() => hook.result.current.travel(false)); expect(hook.result.current.draft.nodes).toHaveLength(0);
  act(() => hook.result.current.travel(true)); await act(() => hook.result.current.save());
  expect(initial.client.graphs.save).toHaveBeenCalledWith('target', expect.objectContaining({ expected_version: 1 }));
  expect(hook.result.current.base?.version).toBe(2);
});
it.each(['identity', 'client', 'denied', 'canMutate', 'active'] as const)('clears cross-graph snapshot on %s change and does not resurrect it', async key => {
  const { hook, initial } = await crossFixture();
  expect(hook.result.current.sourceCopy).toBeTruthy();
  hook.rerender({ ...initial, [key]: key === 'identity' ? 'different-owner' : key === 'client' ? props().client : key === 'denied' });
  expect(hook.result.current.sourceCopy).toBeUndefined();
  hook.rerender(initial); expect(hook.result.current.sourceCopy).toBeUndefined();
});
it.each(['project', 'scope', 'readonly'] as const)('fails closed on target %s mismatch', async mode => {
  const { hook, target } = await crossFixture();
  if (mode === 'project') target.project_id = 'other-project';
  if (mode === 'scope') target.scope = { mode: 'local', novel_id: 'other-scope' };
  if (mode === 'readonly') target.can_edit = false;
  await act(() => hook.result.current.open(target.id));
  act(() => hook.result.current.previewCrossGraphCopy());
  expect(hook.result.current.sourceCopy).toBeUndefined(); expect(hook.result.current.currentCrossCopy).toBeUndefined();
  act(() => hook.result.current.pasteCrossGraphCopy()); expect(hook.result.current.draft.nodes).toHaveLength(0);
});
it('invalidates target preview on edit/undo and preserves the snapshot for explicit re-preview', async () => {
  const { hook, target } = await crossFixture(); await act(() => hook.result.current.open(target.id));
  act(() => hook.result.current.previewCrossGraphCopy()); expect(hook.result.current.currentCrossCopy).toBeTruthy();
  act(() => hook.result.current.change({ ...hook.result.current.draft, title: 'Edited' }));
  act(() => hook.result.current.travel(false)); expect(hook.result.current.currentCrossCopy).toBeUndefined();
  act(() => hook.result.current.pasteCrossGraphCopy()); expect(hook.result.current.draft.nodes).toHaveLength(0);
  expect(hook.result.current.sourceCopy).toBeTruthy();
});
it('keeps original dirty navigation confirmation and UNKNOWN fence, without capturing unsaved edits', async () => {
  const { hook, target, source } = await crossFixture();
  act(() => hook.result.current.change({ ...hook.result.current.draft, title: 'Unsaved source' }));
  act(() => hook.result.current.captureSelectionForGraph()); expect(hook.result.current.sourceCopy!.record.definition.title).toBe(source.definition.title);
  const move = vi.fn(() => void hook.result.current.open(target.id));
  act(() => hook.result.current.navigate(move)); expect(move).not.toHaveBeenCalled(); expect(hook.result.current.pendingNavigation).toBeTruthy();
  act(() => hook.result.current.setDiscardConfirmed(true));
  act(() => hook.result.current.confirmNavigation()); await waitFor(() => expect(hook.result.current.base?.id).toBe(target.id)); expect(move).toHaveBeenCalledOnce();
  expect(hook.result.current.sourceCopy).toBeTruthy();
  act(() => hook.result.current.previewCrossGraphCopy()); act(() => hook.result.current.setExecutionDirty(true));
  act(() => hook.result.current.pasteCrossGraphCopy()); expect(hook.result.current.draft.nodes).toHaveLength(0);
  const other = vi.fn(); act(() => hook.result.current.navigate(other)); expect(other).not.toHaveBeenCalled();
  act(() => hook.result.current.setExecutionDirty(false)); expect(hook.result.current.currentCrossCopy).toBeUndefined();
});
it('honors synchronous busy before cross-graph paste and rejects a known stale captured binding', async () => {
  const { hook, initial, target, source } = await crossFixture(); let locked = false;
  hook.rerender({ ...initial, isBusy: () => locked });
  await act(() => hook.result.current.open(target.id)); act(() => hook.result.current.previewCrossGraphCopy());
  locked = true; act(() => hook.result.current.pasteCrossGraphCopy()); expect(hook.result.current.draft.nodes).toHaveLength(0);
  locked = false; act(() => hook.result.current.clearGraphCopy());
  source.reference_states = [{ node_id: 'input', state: 'STALE' }];
  await act(() => hook.result.current.open(source.id)); act(() => hook.result.current.setSelected(['input'])); act(() => hook.result.current.captureSelectionForGraph());
  expect(hook.result.current.sourceCopy).toBeUndefined(); expect(hook.result.current.error).toMatch(/已变化/);
});

it('rejects retained paste callbacks after clearing or replacing their preview, including same-tick clear', async () => {
  const { hook, target } = await crossFixture(); await act(() => hook.result.current.open(target.id));
  act(() => hook.result.current.previewCrossGraphCopy()); const stalePaste = hook.result.current.pasteCrossGraphCopy;
  act(() => { hook.result.current.clearGraphCopy(); stalePaste(); }); expect(hook.result.current.draft.nodes).toHaveLength(0);
});
it('rejects retained target preview after edit and undo back to the identical draft', async () => {
  const { hook, target } = await crossFixture(); await act(() => hook.result.current.open(target.id));
  act(() => hook.result.current.previewCrossGraphCopy()); const stalePaste = hook.result.current.pasteCrossGraphCopy;
  act(() => hook.result.current.change({ ...hook.result.current.draft, title: 'Change' }));
  act(() => hook.result.current.travel(false)); act(() => stalePaste());
  expect(hook.result.current.draft.nodes).toHaveLength(0);
});
it('does not capture a saved snapshot using a retained clean-render handler after a same-tick draft edit', async () => {
  const { hook } = await crossFixture(); act(() => hook.result.current.clearGraphCopy());
  const capture = hook.result.current.captureSelectionForGraph;
  act(() => { hook.result.current.change({ ...hook.result.current.draft, title: 'Unsaved now' }); capture(); });
  expect(hook.result.current.sourceCopy).toBeUndefined();
});
