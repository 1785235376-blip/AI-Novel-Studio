// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { useStudioGraphEditor, type StudioGraphEditorProps } from './useStudioGraphEditor';
const state = vi.hoisted(() => ({ externalDirty: false, discard: vi.fn() }));
vi.mock('./useStudioGraphEditorController', () => ({ useStudioGraphEditorController: (props: StudioGraphEditorProps) => {
 state.externalDirty = props.externalDirty;
 return { executionDirty: false, dirty: false, blocked: false, retired: false, catalog: undefined, draft: { nodes: [], edges: [], title: 'Graph' }, selected: [], discard: state.discard }; } }));
vi.mock('./studioGraphEditorView', () => ({ studioGraphEditorView: () => ({ content: null, inspector: null }) }));
afterEach(cleanup);
it('propagates media draft dirtiness through original graph owner and explicit discard', () => {
 const props = { active: true, denied: false, identity: 'original', client: { graphs: { canvasViews: {} } }, canMutate: true, canReview: false, busy: false, externalDirty: false, isCurrent: () => true, read: async <T,>(f: () => Promise<T>) => f(), mutate: async <T,>(f: () => Promise<T>) => f() } as unknown as StudioGraphEditorProps;
 function Mounted() { const graph = useStudioGraphEditor(props); return <>{graph.content}<output aria-label="owner dirty">{String(graph.dirty)}</output><button onClick={graph.discard}>Owner discard</button></>; }
 render(<Mounted />); expect(screen.getByLabelText('owner dirty').textContent).toBe('false');
 fireEvent.change(screen.getByLabelText('画布标题'), { target: { value: 'Pending' } }); expect(screen.getByLabelText('owner dirty').textContent).toBe('true'); expect(state.externalDirty).toBe(true);
 fireEvent.click(screen.getByText('Owner discard')); expect(screen.getByLabelText('owner dirty').textContent).toBe('false'); expect(state.discard).toHaveBeenCalled(); expect((screen.getByLabelText('画布标题') as HTMLInputElement).value).toBe('媒体素材画布');
});
