// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { useStudioGraphEditorController, type StudioGraphEditorProps } from './useStudioGraphEditorController';
import { studioGraphEditorView } from './studioGraphEditorView';
import { modelCatalog } from './studioGraphModel.testFixtures';
import { blankLocalCanvasState } from '../canvasops/canvasOps';
import type { StudioClient } from './studioClient';
afterEach(() => { cleanup(); vi.restoreAllMocks(); });
const viewport = () => screen.getByRole('group', { name: '节点图交互区域' });
const palette = () => within(screen.getByRole('region', { name: '节点面板' }));
const add = () => palette().getByRole('button', { name: '添加所选节点（由原控制器执行）' }) as HTMLButtonElement;
async function setup() {
  const save = vi.fn(), create = vi.fn(), createRun = vi.fn();
  const props: StudioGraphEditorProps = { active: true, denied: false, identity: 'A', canMutate: true, canReview: true,
    busy: false, externalDirty: false, isCurrent: () => true, read: work => work(), mutate: work => work(),
    client: { graphs: { catalog: vi.fn().mockResolvedValue(modelCatalog()), list: vi.fn().mockResolvedValue({ items: [] }), save, create, createRun } } as unknown as StudioClient };
  function Harness() {
    const controller = useStudioGraphEditorController(props);
    return studioGraphEditorView(controller, props, { local: blankLocalCanvasState(), onLocal: vi.fn() }).content;
  }
  render(<Harness/>); await waitFor(() => expect(screen.getByRole('searchbox', { name: '搜索节点' })).toBeTruthy());
  vi.spyOn(viewport(), 'getBoundingClientRect').mockReturnValue({ left: 40, top: 20, width: 800, height: 400, x: 40, y: 20, right: 840, bottom: 420, toJSON: () => ({}) });
  return { save, create, createRun };
}
it('reuses exactly one searchable palette, requires explicit Add, and preserves explicit Save', async () => {
  const { save, create, createRun } = await setup();
  fireEvent.contextMenu(viewport(), { clientX: 240, clientY: 140 });
  const search = screen.getByRole('searchbox', { name: '搜索节点' }); expect(document.activeElement).toBe(search);
  expect(screen.getAllByRole('searchbox', { name: '搜索节点' })).toHaveLength(1);
  fireEvent.change(search, { target: { value: 'text_input' } });
  fireEvent.click(palette().getByRole('button', { name: /text_input/ }));
  expect(document.querySelectorAll('[data-graph-node-id]')).toHaveLength(0);
  fireEvent.keyDown(search, { key: 'Enter' }); expect(document.querySelectorAll('[data-graph-node-id]')).toHaveLength(0);
  fireEvent.click(add());
  const node = document.querySelector<HTMLElement>('[data-graph-node-id]')!;
  expect(node.style.left).toBe('200px'); expect(node.style.top).toBe('120px'); expect(document.activeElement).toBe(viewport());
  expect(palette().queryByRole('button', { name: '取消指定位置添加' })).toBeNull();
  expect(save).not.toHaveBeenCalled(); expect(create).not.toHaveBeenCalled(); expect(createRun).not.toHaveBeenCalled();
});
it('explains and disables positioned v1 implicit upgrade without changing schema', async () => {
  await setup(); fireEvent.contextMenu(viewport(), { clientX: 240, clientY: 140 });
  fireEvent.change(screen.getByRole('searchbox', { name: '搜索节点' }), { target: { value: 'text_generate' } });
  fireEvent.click(palette().getByRole('button', { name: /text_generate/ }));
  expect(palette().getByText(/指定位置添加不会自动升级 v1/)).toBeTruthy(); expect(add().disabled).toBe(true);
  fireEvent.click(add()); expect(document.querySelectorAll('[data-graph-node-id]')).toHaveLength(0);
});
it('ignores IME Escape, cancels on ordinary Escape and returns focus', async () => {
  await setup(); viewport().focus(); fireEvent.keyDown(viewport(), { key: 'F10', shiftKey: true });
  const search = screen.getByRole('searchbox', { name: '搜索节点' });
  fireEvent.keyDown(search, { key: 'Escape', isComposing: true }); expect(palette().getByRole('button', { name: '取消指定位置添加' })).toBeTruthy();
  fireEvent.keyDown(search, { key: 'Escape', keyCode: 229 }); expect(palette().getByRole('button', { name: '取消指定位置添加' })).toBeTruthy();
  fireEvent.keyDown(search, { key: 'Escape' }); expect(palette().queryByRole('button', { name: '取消指定位置添加' })).toBeNull();
  expect(document.activeElement).toBe(viewport()); expect(document.querySelectorAll('[data-graph-node-id]')).toHaveLength(0);
});
it('keeps expired point disabled until explicit cancellation, restoring same-owner focus', async () => {
  await setup(); fireEvent.contextMenu(viewport(), { clientX: 240, clientY: 140 });
  fireEvent.change(screen.getByLabelText('创作图标题'), { target: { value: 'Changed title' } });
  expect(palette().getByText(/指定位置已失效/)).toBeTruthy(); expect(add().disabled).toBe(true);
  const cancel = palette().getByRole('button', { name: '取消指定位置添加' }); cancel.focus(); fireEvent.click(cancel);
  expect(document.activeElement).toBe(viewport()); expect(add().disabled).toBe(false);
});
