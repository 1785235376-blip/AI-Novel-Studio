// @vitest-environment jsdom
import { cleanup, render } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { useStudioGraphEditor, type StudioGraphEditorProps } from './useStudioGraphEditor';
import type { OpenStoryboardEditor } from './storyboardEditorHandoff';
const state = vi.hoisted(() => ({ executionDirty: false, onOpen: undefined as OpenStoryboardEditor | undefined, discard: vi.fn() }));
vi.mock('./useStudioGraphEditorController', () => ({ useStudioGraphEditorController: () => ({ executionDirty: state.executionDirty, dirty: false, blocked: false, retired: false, catalog: undefined, draft: { nodes: [], edges: [], title: 'Graph' }, selected: [], discard: state.discard }) }));
vi.mock('./studioGraphEditorView', () => ({ studioGraphEditorView: () => ({ content: null, inspector: null }) }));
vi.mock('./GraphDirectorConsole', () => ({ GraphDirectorConsole: (props: { onOpenStoryboard?: OpenStoryboardEditor }) => { state.onOpen = props.onOpenStoryboard; return null; } }));
vi.mock('./StudioGraphDraftRecovery', () => ({ StudioGraphDraftRecovery: () => null }));
afterEach(() => { cleanup(); state.executionDirty = false; state.onOpen = undefined; });
it('retires retained editor Open across original graph execution-input ABA without weakening discard', () => {
  const open = vi.fn();
  const props = { active: true, denied: false, identity: 'original', client: {}, directorSource: {}, canMutate: true, canReview: false, busy: false, externalDirty: false, isCurrent: () => true, read: async <T,>(work: () => Promise<T>) => work(), mutate: async <T,>(work: () => Promise<T>) => work(), onOpenStoryboard: open } as unknown as StudioGraphEditorProps;
  function Mounted() { const graph = useStudioGraphEditor(props); return graph.content; }
  const view = render(<Mounted />);
  const retained = state.onOpen!;
  const request = { requestId: 1, target: { id: 'board', mode: 'STORYBOARD' as const, version: 1, digest: 'b'.repeat(64) }, source: { id: 'director', version: 2, digest: 'a'.repeat(64) } };
  retained(request, () => true); const authority = open.mock.calls[0][1]; expect(authority()).toBe(true);
  state.executionDirty = true; view.rerender(<Mounted />); expect(state.onOpen).toBeUndefined(); expect(authority()).toBe(false);
  state.executionDirty = false; view.rerender(<Mounted />); expect(authority()).toBe(false);
  retained(request, () => true); expect(open.mock.calls[1][1]()).toBe(false); expect(state.discard).not.toHaveBeenCalled();
});
