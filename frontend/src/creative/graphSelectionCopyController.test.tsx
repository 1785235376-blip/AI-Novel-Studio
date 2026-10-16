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
