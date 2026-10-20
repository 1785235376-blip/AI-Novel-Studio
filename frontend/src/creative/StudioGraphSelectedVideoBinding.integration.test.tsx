// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { studioGraphEditorView } from './studioGraphEditorView';
import { useStudioGraphEditorController, type StudioGraphEditorController, type StudioGraphEditorProps } from './useStudioGraphEditorController';
import type { StudioClient } from './studioClient';
import { videoBindingCatalog, videoBindingGraph, videoBindingProvider } from './graphSelectedVideoBinding.testFixtures';
import { mediaProviderKey } from './useStudioMediaExecution';

afterEach(cleanup);
it('mounts in the original v5 view and uses original undo/redo without saving or admitting any task', async () => {
  const provider = videoBindingProvider(), providers = vi.fn().mockResolvedValue([provider]);
  const writes = { create: vi.fn(), save: vi.fn(), createRun: vi.fn(), preflight: vi.fn(), previewMedia: vi.fn(), dispatchMedia: vi.fn(), executeMedia: vi.fn(), reviewMedia: vi.fn(), previewModel: vi.fn(), dispatchModel: vi.fn() };
  const client = { graphs: { catalog: vi.fn().mockResolvedValue(videoBindingCatalog()), list: vi.fn().mockResolvedValue({ items: [] }), ...writes } } as unknown as StudioClient;
  const props: StudioGraphEditorProps = { active: true, denied: false, canMutate: true, canReview: true, identity: 'original-author', client,
    providerSource: { providers }, busy: false, externalDirty: false, isCurrent: () => true, read: work => work(), mutate: work => work() };
  let controller!: StudioGraphEditorController;
  function Harness() { controller = useStudioGraphEditorController(props); const view = studioGraphEditorView(controller, props); return <>{view.content}{view.inspector}</>; }
  render(<Harness />); await waitFor(() => expect(controller.editable).toBe(true));
  act(() => { controller.change(videoBindingGraph()); controller.setSelected(['video-1', 'video-3']); });
  const before = structuredClone(controller.draft), history = controller.past.length;
  expect(providers).not.toHaveBeenCalled(); expect(screen.getByLabelText('所选视频节点本地批量绑定')).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: '读取批量绑定本地配置' }));
  await waitFor(() => expect(controller.selectedVideoBinding.rows).toHaveLength(1));
  fireEvent.change(screen.getByLabelText('批量绑定本地服务商与模型'), { target: { value: mediaProviderKey(provider) } });
  fireEvent.click(screen.getByRole('button', { name: '预览所选视频节点绑定' }));
  expect(controller.draft).toEqual(before); expect(controller.past).toHaveLength(history);
  expect(screen.getByLabelText('所选视频节点绑定预览').textContent).toContain('video-3');
  fireEvent.click(screen.getByRole('button', { name: '确认应用所选视频节点本地绑定' }));
  const after = structuredClone(controller.draft); expect(controller.past).toHaveLength(history + 1);
  expect(after.nodes[0].parameters.provider_id).toBe('local-one'); expect(after.nodes[1]).toEqual(before.nodes[1]);
  fireEvent.click(screen.getByRole('button', { name: '撤销图编辑' })); expect(controller.draft).toEqual(before);
  fireEvent.click(screen.getByRole('button', { name: '重做图编辑' })); expect(controller.draft).toEqual(after);
  expect(providers).toHaveBeenCalledTimes(1); Object.values(writes).forEach(write => expect(write).not.toHaveBeenCalled());
});
