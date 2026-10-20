// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { ApiError } from '../api';
import { GraphCanvas, type GraphCanvasProps } from './GraphCanvas';
import { GraphNodeRemovalControl } from './GraphNodeRemovalControl';
import { graphNodeRemovalImpact } from './graphNodeRemovalImpact';
import { removeGraphNodes } from './graphCanvasGeometry';
import { imageGraphCatalog, imageGraphRecord } from './studioImageGraph.testFixtures';
import { useStudioGraphEditorController, type StudioGraphEditorController, type StudioGraphEditorProps } from './useStudioGraphEditorController';
import type { StudioClient } from './studioClient';

const retained = (element: HTMLElement) => (element as any)[Object.keys(element).find(key => key.startsWith('__reactProps$'))!].onClick;
const consentLabel = '已核对结构影响，确认移除这些节点';
const applyLabel = '确认移除节点到本地草稿';
const inspect = () => fireEvent.click(screen.getByRole('button', { name: '移除当前节点' }));
const confirm = () => fireEvent.click(screen.getByLabelText(consentLabel));
afterEach(() => { cleanup(); vi.restoreAllMocks(); });
function fixture() {
  return { definition: imageGraphRecord().definition, nodeIds: ['prompt'], selectionIds: ['prompt'],
    protectedNodeIds: ['asset'], definitions: imageGraphCatalog().definitions,
    owner: {}, sourceOwner: {}, disabled: false, isCurrent: () => true, onApply: vi.fn() };
}

it('reports removed nodes and incident edges, retained downstream and new required-input gaps without mutating source', () => {
  const p = fixture(), before = structuredClone(p.definition);
  const result = graphNodeRemovalImpact(p.definition, ['prompt', 'asset', 'prompt'], p.protectedNodeIds, p.definitions);
  expect(result.removed).toEqual(['prompt']); expect(result.protectedIds).toEqual(['asset']);
  expect(result.removedEdges.map(edge => edge.id)).toEqual(['references_prompt', 'prompt_generate']);
  expect(result.affected).toEqual(['generate', 'review']); expect(result.unaffected).toEqual(['asset', 'references']);
  expect(result.newMissing).toEqual(['generate.prompt']); expect(result.remainingMissing).toContain('generate.prompt');
  expect(result.definition).toEqual(removeGraphNodes(p.definition, ['prompt'], p.protectedNodeIds));
  expect(result.definition.nodes.find(node => node.id === 'asset')).toEqual(before.nodes[0]);
  result.definition.nodes[0].parameters.asset_id = 'changed-only-in-copy';
  expect(p.definition).toEqual(before);
});

it('uses original group cleanup and orphan promotion while preserving notes, views and unrelated metadata', () => {
  const p = fixture(); p.definition.presentation = { comment: 'Keep the author note', view: { show_grid: true, snap: false, grid_step: 24, show_minimap: true },
    groups: [{ id: 'parent', name: 'Parent', node_ids: ['prompt'] },
      { id: 'child', name: 'Child', node_ids: ['generate'], parent_id: 'parent' },
      { id: 'mixed', name: 'Mixed', node_ids: ['prompt', 'references'] }] };
  const result = graphNodeRemovalImpact(p.definition, p.nodeIds, p.protectedNodeIds, p.definitions);
  expect(result.definition).toEqual(removeGraphNodes(p.definition, p.nodeIds, p.protectedNodeIds));
  expect(result.removedGroups).toEqual(['parent']); expect(result.changedGroups).toEqual(['child', 'mixed']);
  expect(result.definition.presentation!.groups).toEqual([{ id: 'child', name: 'Child', node_ids: ['generate'] }, { id: 'mixed', name: 'Mixed', node_ids: ['references'] }]);
  expect(result.definition.presentation!.comment).toBe('Keep the author note');
  expect(result.definition.presentation!.view).toEqual(p.definition.presentation.view);
});

it('distinguishes pre-existing gaps from new gaps and excludes deleted nodes from remaining missing inputs', () => {
  const p = fixture(); p.definition.edges = p.definition.edges.filter(edge => edge.id !== 'generate_review');
  const result = graphNodeRemovalImpact(p.definition, ['prompt'], p.protectedNodeIds, p.definitions);
  expect(result.newMissing).toEqual(['generate.prompt']); expect(result.remainingMissing).toEqual(['generate.prompt', 'review.candidate']);
  const all = graphNodeRemovalImpact(p.definition, ['prompt', 'generate', 'review'], p.protectedNodeIds, p.definitions);
  expect(all.newMissing).toEqual([]); expect(all.remainingMissing).toEqual([]); expect(all.affected).toEqual([]);
});

it('handles disabled sources, cycles and disconnected nodes as structure only', () => {
  const p = fixture(); p.definition.nodes.find(node => node.id === 'prompt')!.enabled = false;
  p.definition.edges.push({ id: 'back', source_node_id: 'review', source_port: 'candidate', target_node_id: 'generate', target_port: 'prompt' });
  const result = graphNodeRemovalImpact(p.definition, ['prompt'], p.protectedNodeIds, p.definitions);
  expect(result.affected).toEqual(['generate', 'review']); expect(result.newMissing).toEqual([]);
  expect(result.definition.nodes.find(node => node.id === 'generate')!.enabled).toBe(true);
});

it.each(['empty', 'missing-node', 'protected-only', 'missing-catalog', 'wrong-version', 'disabled-unknown'])('fails closed for %s', mode => {
  const p = fixture();
  if (mode === 'empty') p.nodeIds = [];
  if (mode === 'missing-node') p.nodeIds = ['absent'];
  if (mode === 'protected-only') p.nodeIds = ['asset'];
  if (mode === 'missing-catalog') p.definitions = [];
  if (mode === 'wrong-version') (p.definition.nodes[0] as any).definition_version = 2;
  if (mode === 'disabled-unknown') { p.definition.nodes[0].enabled = false; p.definitions = p.definitions.filter(spec => spec.id !== 'asset_reference'); }
  expect(() => graphNodeRemovalImpact(p.definition, p.nodeIds, p.protectedNodeIds, p.definitions)).toThrow();
});

it('requires preview and consent, then consumes repeated retained Apply callbacks once', () => {
  const p = fixture(); render(<GraphNodeRemovalControl {...p} />); inspect();
  expect(p.onApply).not.toHaveBeenCalled(); expect(screen.getByText('新增缺少的必需输入：generate.prompt。')).toBeTruthy();
  expect((screen.getByText(applyLabel) as HTMLButtonElement).disabled).toBe(true);
  act(() => retained(screen.getByText(applyLabel))()); expect(p.onApply).not.toHaveBeenCalled();
  confirm(); const callback = retained(screen.getByText(applyLabel)); act(() => { callback(); callback(); });
  expect(p.onApply).toHaveBeenCalledTimes(1); expect(p.onApply.mock.calls[0][1]).toEqual(['prompt']);
  expect(p.onApply.mock.calls[0][0].nodes.map((node: { id: string }) => node.id)).toEqual(['asset', 'references', 'generate', 'review']);
});

it.each(['draft', 'owner', 'source-owner', 'selection', 'target', 'protected', 'catalog', 'permission', 'current', 'consent', 'cancel', 'unmount'])('rejects a retained confirmed removal after %s changes', mode => {
  const p = fixture(), view = render(<GraphNodeRemovalControl {...p} />); inspect(); confirm();
  const callback = retained(screen.getByText(applyLabel));
  if (mode === 'draft') view.rerender(<GraphNodeRemovalControl {...p} definition={{ ...p.definition, title: 'Changed' }} />);
  if (mode === 'owner') { view.rerender(<GraphNodeRemovalControl {...p} owner={{}} />); view.rerender(<GraphNodeRemovalControl {...p} />); }
  if (mode === 'source-owner') view.rerender(<GraphNodeRemovalControl {...p} sourceOwner={{}} />);
  if (mode === 'selection') { view.rerender(<GraphNodeRemovalControl {...p} selectionIds={['prompt', 'generate']} />); view.rerender(<GraphNodeRemovalControl {...p} />); }
  if (mode === 'target') view.rerender(<GraphNodeRemovalControl {...p} nodeIds={['generate']} />);
  if (mode === 'protected') view.rerender(<GraphNodeRemovalControl {...p} protectedNodeIds={['asset', 'prompt']} />);
  if (mode === 'catalog') view.rerender(<GraphNodeRemovalControl {...p} definitions={[]} />);
  if (mode === 'permission') { view.rerender(<GraphNodeRemovalControl {...p} disabled />); view.rerender(<GraphNodeRemovalControl {...p} />); }
  if (mode === 'current') view.rerender(<GraphNodeRemovalControl {...p} isCurrent={() => false} />);
  if (mode === 'consent') confirm();
  if (mode === 'cancel') fireEvent.click(screen.getByText('保留原节点'));
  if (mode === 'unmount') view.unmount();
  act(() => callback()); expect(p.onApply).not.toHaveBeenCalled();
});

it('checks a live lock even without a React render', () => {
  const p = fixture(); let current = true; render(<GraphNodeRemovalControl {...p} isCurrent={() => current} />); inspect(); confirm();
  const callback = retained(screen.getByText(applyLabel)); current = false; act(() => callback()); expect(p.onApply).not.toHaveBeenCalled();
});

it('reopening requires fresh consent and invalidates the earlier Apply callback', () => {
  const p = fixture(); render(<GraphNodeRemovalControl {...p} />); inspect(); confirm();
  const callback = retained(screen.getByText(applyLabel)); inspect(); act(() => callback());
  expect(p.onApply).not.toHaveBeenCalled(); expect((screen.getByText(applyLabel) as HTMLButtonElement).disabled).toBe(true);
  confirm(); fireEvent.click(screen.getByText(applyLabel)); expect(p.onApply).toHaveBeenCalledTimes(1);
});

it('ignores a retained cancellation from an older preview', () => {
  const p = fixture(); render(<GraphNodeRemovalControl {...p} />); inspect();
  const cancel = retained(screen.getByText('保留原节点')); inspect(); confirm(); act(() => cancel());
  expect(screen.getByLabelText('移除节点影响预览')).toBeTruthy();
  fireEvent.click(screen.getByText(applyLabel)); expect(p.onApply).toHaveBeenCalledTimes(1);
});

it('does not reopen a preview through a retained trigger after an owner round trip', () => {
  const p = fixture(), view = render(<GraphNodeRemovalControl {...p} />);
  const trigger = retained(screen.getByText('移除当前节点'));
  view.rerender(<GraphNodeRemovalControl {...p} owner={{}} />); view.rerender(<GraphNodeRemovalControl {...p} />);
  act(() => trigger()); expect(screen.queryByLabelText('移除节点影响预览')).toBeNull(); expect(p.onApply).not.toHaveBeenCalled();
});

it('Escape cancels the inline preview and returns focus without changing nodes', () => {
  const p = fixture(); render(<GraphNodeRemovalControl {...p} />);
  const trigger = screen.getByRole('button', { name: '移除当前节点' }); trigger.focus(); inspect();
  const panel = screen.getByRole('region', { name: '移除节点影响预览' }); expect(document.activeElement).toBe(panel);
  fireEvent.keyDown(panel, { key: 'Escape' }); expect(screen.queryByLabelText('移除节点影响预览')).toBeNull();
  expect(document.activeElement).toBe(trigger); expect(p.onApply).not.toHaveBeenCalled();
});

it('keeps protected-only removal disabled and displays a warning for an incomplete catalog', () => {
  const p = fixture(), view = render(<GraphNodeRemovalControl {...p} nodeIds={['asset']} />);
  expect((screen.getByText('移除当前节点') as HTMLButtonElement).disabled).toBe(true);
  view.rerender(<GraphNodeRemovalControl {...p} definitions={[]} />); inspect();
  expect(screen.getByRole('status').textContent).toContain('无法核对移除影响'); expect(screen.queryByText(applyLabel)).toBeNull(); expect(p.onApply).not.toHaveBeenCalled();
});

function canvasFixture(): GraphCanvasProps {
  const p = fixture(); return { definition: p.definition, nodeDefinitions: p.definitions, removalDefinitions: p.definitions,
    removalOwner: p.owner, preferencesSource: p.sourceOwner, interactionKey: 'actor:graph', selectedNodeIds: p.nodeIds,
    protectedNodeIds: p.protectedNodeIds, onDefinitionChange: vi.fn(), onSelectionChange: vi.fn(), isRemovalCurrent: () => true };
}

it.each(['toolbar', 'Delete', 'Backspace'])('routes canvas %s through the same explicit preview and one history record', route => {
  const p = canvasFixture(); render(<GraphCanvas {...p} />);
  if (route === 'toolbar') fireEvent.click(screen.getByRole('button', { name: '删除所选图节点' }));
  else fireEvent.keyDown(screen.getByRole('group', { name: '节点图交互区域' }), { key: route });
  expect(p.onDefinitionChange).not.toHaveBeenCalled(); expect(p.onSelectionChange).not.toHaveBeenCalled();
  confirm(); fireEvent.click(screen.getByText(applyLabel));
  expect(p.onDefinitionChange).toHaveBeenCalledTimes(1); expect(p.onDefinitionChange).toHaveBeenCalledWith(expect.objectContaining({ nodes: expect.not.arrayContaining([expect.objectContaining({ id: 'prompt' })]) }), true);
  expect(p.onSelectionChange).toHaveBeenCalledWith([]);
});

it('retains protected nodes in a mixed canvas selection and prevents preview keyboard events editing the canvas', () => {
  const p = canvasFixture(); render(<GraphCanvas {...p} selectedNodeIds={['asset', 'prompt']} />);
  fireEvent.click(screen.getByRole('button', { name: '删除所选图节点' }));
  expect(screen.getByText('保留的受保护来源引用：asset。')).toBeTruthy();
  const panel = screen.getByRole('region', { name: '移除节点影响预览' });
  for (const key of ['Delete', 'Backspace', 'ArrowRight']) fireEvent.keyDown(panel, { key });
  expect(p.onDefinitionChange).not.toHaveBeenCalled(); confirm(); fireEvent.click(screen.getByText(applyLabel));
  expect(p.onSelectionChange).toHaveBeenCalledWith(['asset']);
  expect(vi.mocked(p.onDefinitionChange).mock.calls[0][0].nodes.find(node => node.id === 'asset')).toEqual(p.definition.nodes[0]);
});

it.each(['source', 'authority', 'selection', 'permission', 'busy', 'form', 'scope'])('fences canvas removal after %s changes and returns', mode => {
  const p = canvasFixture(), view = render(<GraphCanvas {...p} />);
  fireEvent.click(screen.getByRole('button', { name: '删除所选图节点' })); confirm(); const callback = retained(screen.getByText(applyLabel));
  const changes: Partial<GraphCanvasProps> = mode === 'source' ? { preferencesSource: {} } : mode === 'authority' ? { interactionKey: 'other' }
    : mode === 'selection' ? { selectedNodeIds: ['generate'] } : mode === 'permission' ? { readonly: true } : mode === 'busy' ? { busy: true }
    : mode === 'form' ? { removalDisabled: true } : { removalOwner: {} };
  view.rerender(<GraphCanvas {...p} {...changes} />); view.rerender(<GraphCanvas {...p} />); act(() => callback());
  expect(p.onDefinitionChange).not.toHaveBeenCalled(); expect(p.onSelectionChange).not.toHaveBeenCalled();
});

async function controllerFixture() {
  let controller!: StudioGraphEditorController;
  const original = imageGraphRecord(), save = vi.fn(async (_id: string, body: any) => ({ ...original, version: 2, definition: body.definition }));
  const createRun = vi.fn(), preflight = vi.fn(), deleteAsset = vi.fn();
  const props: StudioGraphEditorProps = { active: true, denied: false, identity: 'owner', canMutate: true, canReview: true,
    busy: false, externalDirty: false, isCurrent: () => true, read: work => work(), mutate: work => work(),
    client: { deleteAsset, graphs: { catalog: vi.fn(async () => imageGraphCatalog()), imageCatalog: vi.fn(async () => imageGraphCatalog()),
      list: vi.fn(async () => ({ items: [original] })), get: vi.fn(async () => original), save, createRun, preflight } } as unknown as StudioClient };
  function Harness() {
    controller = useStudioGraphEditorController(props);
    return controller.catalog ? <GraphNodeRemovalControl definition={controller.draft} nodeIds={['prompt']} selectionIds={controller.selected}
      protectedNodeIds={controller.protectedNodes} definitions={controller.catalog.definitions} owner={controller.insertionScope}
      sourceOwner={controller.base} disabled={!controller.editable || controller.timelineEditor.formDirty}
      isCurrent={controller.isPlanningForkCurrent} onApply={next => { controller.change(next); controller.setSelected([]); }} /> : null;
  }
  render(<Harness />); await waitFor(() => expect(controller.catalog).toBeTruthy()); await act(async () => controller.open(original.id));
  return { get controller() { return controller; }, original, save, createRun, preflight, deleteAsset };
}

it('uses original undo/redo and explicit CAS save without starting a run or deleting an asset', async () => {
  const h = await controllerFixture(); inspect(); expect(h.controller.draft).toEqual(h.original.definition);
  confirm(); fireEvent.click(screen.getByText(applyLabel)); expect(h.controller.draft.nodes.some(node => node.id === 'prompt')).toBe(false);
  expect(h.controller.past).toHaveLength(1); expect(h.save).not.toHaveBeenCalled();
  act(() => h.controller.travel(false)); expect(h.controller.draft).toEqual(h.original.definition);
  act(() => h.controller.travel(true)); expect(h.controller.draft.nodes.some(node => node.id === 'prompt')).toBe(false);
  await act(async () => h.controller.save()); expect(h.save).toHaveBeenCalledTimes(1); expect(h.save.mock.calls[0][1].expected_version).toBe(1);
  expect(h.createRun).not.toHaveBeenCalled(); expect(h.preflight).not.toHaveBeenCalled(); expect(h.deleteAsset).not.toHaveBeenCalled();
});

it.each(['edit', 'selection'])('uses the existing controller fence to reject a same-tick %s before React rerenders', async mode => {
  const h = await controllerFixture(); inspect(); confirm(); const callback = retained(screen.getByText(applyLabel));
  act(() => {
    if (mode === 'edit') h.controller.change({ ...h.controller.draft, title: 'Newer author draft' });
    else h.controller.setSelected(['generate']);
    callback();
  });
  expect(h.controller.draft.nodes.some(node => node.id === 'prompt')).toBe(true); expect(h.save).not.toHaveBeenCalled();
});

it('preserves a removal draft on CAS conflict without auto retry or reintroducing a deleted node', async () => {
  const h = await controllerFixture(); inspect(); confirm(); fireEvent.click(screen.getByText(applyLabel));
  const local = structuredClone(h.controller.draft);
  h.save.mockRejectedValueOnce(new ApiError({ status: 409, code: 'CREATIVE_GRAPH_VERSION_CONFLICT', message: 'Conflict' }));
  await act(async () => h.controller.save()); expect(h.controller.blocked).toBe(true); expect(h.controller.draft).toEqual(local);
  expect(h.save).toHaveBeenCalledTimes(1); expect(h.createRun).not.toHaveBeenCalled(); expect(h.preflight).not.toHaveBeenCalled(); expect(h.deleteAsset).not.toHaveBeenCalled();
});
