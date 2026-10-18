// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { MediaCanvasViewPanel } from './MediaCanvasViewPanel';
import type { CanvasDefinition } from './studioCanvasViewClient';
afterEach(cleanup);
const blank = (): CanvasDefinition => ({ schema_version: 1, title: '媒体素材画布', cards: [], viewport: { x: 0, y: 0, zoom: 1 } });
function record(definition = blank()) { return { id: 'view', version: 1, definition, reference_states: definition.cards.map(c => ({ card_id: c.id, state: 'CURRENT_METADATA', filename: 'a.png' })), execution_authority: false }; }
function fixture() { const views = { list: vi.fn().mockResolvedValue({ items: [{ id: 'view', version: 1, title: 'Saved', card_count: 0 }] }), get: vi.fn().mockResolvedValue(record()), create: vi.fn(async (d: CanvasDefinition) => record(d)), save: vi.fn(async (_id: string, _v: number, d: CanvasDefinition) => ({ ...record(d), version: 2 })) };
 const props = { active: true, denied: false, identity: 'owner', client: { graphs: { canvasViews: views }, assets: vi.fn().mockResolvedValue({ items: [{ id: 'asset', filename: 'a.png', kind: 'image', version: 1, sha256: 'a'.repeat(64) }] }) } as any, canMutate: true, busy: false, externalDirty: false, isCurrent: () => true, read: async <T,>(f: () => Promise<T>) => f(), mutate: async <T,>(f: () => Promise<T>) => f(), onDirtyChange: vi.fn() }; return { props, views }; }
it('loads actual client assets, creates a view, saves movement and reopens', async () => { const { props, views } = fixture(); render(<MediaCanvasViewPanel {...props} />);
 fireEvent.click(screen.getByText('读取可用素材')); await screen.findByText('a.png'); fireEvent.change(screen.getByLabelText('素材'), { target: { value: 'asset' } }); fireEvent.click(screen.getByText('加入引用卡片'));
 expect(screen.getByText(/共 1\/1000/)).toBeTruthy(); fireEvent.click(screen.getByText('保存媒体画布')); await waitFor(() => expect(views.create).toHaveBeenCalledTimes(1)); await screen.findByText('已保存媒体画布');
 fireEvent.click(screen.getByRole('button', { name: 'a.png' })); fireEvent.change(screen.getByLabelText('卡片 x'), { target: { value: '60' } });
 fireEvent.click(screen.getByText('保存媒体画布')); await waitFor(() => expect(views.save).toHaveBeenCalledTimes(1)); expect(views.save.mock.calls[0][2].cards[0].position.x).toBe(60);
 fireEvent.click(screen.getByText('读取已存画布')); await screen.findByText('Saved · v1 · 0 张'); fireEvent.click(screen.getByText('Saved · v1 · 0 张')); await waitFor(() => expect(views.get).toHaveBeenCalledWith('view')); });
it('preserves an uncertain write and requires explicit replacement', async () => { const { props, views } = fixture(); views.create.mockRejectedValue(new Error('offline')); render(<MediaCanvasViewPanel {...props} />);
 fireEvent.change(screen.getByLabelText('画布标题'), { target: { value: 'Unsaved' } }); fireEvent.click(screen.getByText('保存媒体画布')); await screen.findByText(/保存结果尚未确认/);
 expect((screen.getByText('保存媒体画布') as HTMLButtonElement).disabled).toBe(true); expect((screen.getByLabelText('画布标题') as HTMLInputElement).value).toBe('Unsaved');
 fireEvent.click(screen.getByText('新建空白视图')); expect((screen.getByLabelText('画布标题') as HTMLInputElement).value).toBe('Unsaved');
 fireEvent.click(screen.getByLabelText('允许用所选已存版本或空白视图替换当前草稿')); fireEvent.click(screen.getByText('新建空白视图')); expect((screen.getByLabelText('画布标题') as HTMLInputElement).value).toBe('媒体素材画布'); });
function retained(element: HTMLElement) { const key = Object.keys(element).find(k => k.startsWith('__reactProps$'))!; return (element as any)[key].onClick as () => void; }
it.each(['permission ABA', 'unmount', 'draft', 'current'])('retires captured save callback across %s', mode => { const { props, views } = fixture(); let current = true; props.isCurrent = () => current; const view = render(<MediaCanvasViewPanel {...props} />), save = retained(screen.getByText('保存媒体画布'));
 if (mode === 'permission ABA') { view.rerender(<MediaCanvasViewPanel {...props} canMutate={false} />); view.rerender(<MediaCanvasViewPanel {...props} />); }
 if (mode === 'unmount') view.unmount(); if (mode === 'draft') fireEvent.change(screen.getByLabelText('画布标题'), { target: { value: 'New' } }); if (mode === 'current') current = false;
 act(save); expect(views.create).not.toHaveBeenCalled(); });
it('renders at most 128 overlapping cards while retaining 1000 saved bindings', async () => {
 const { props, views } = fixture(); const definition = blank(); definition.cards = Array.from({ length: 1000 }, (_, i) => ({ id: `Card_${i}`, position: { x: 0, y: 0 }, asset: { asset_id: 'asset', version: 1, digest: 'a'.repeat(64), kind: 'image' as const } })); views.get.mockResolvedValue(record(definition));
 render(<MediaCanvasViewPanel {...props} />); fireEvent.click(screen.getByText('读取已存画布')); await screen.findByText('Saved · v1 · 0 张'); fireEvent.click(screen.getByText('Saved · v1 · 0 张')); await screen.findByText(/共 1000\/1000/);
 expect(document.querySelectorAll('.media-canvas__card')).toHaveLength(128); fireEvent.change(screen.getByLabelText('查找卡片或素材 ID'), { target: { value: 'Card_999' } }); expect(document.querySelectorAll('.media-canvas__card')).toHaveLength(1);
 fireEvent.click(screen.getByText('保存媒体画布')); await waitFor(() => expect(views.save).toHaveBeenCalledTimes(1)); expect(views.save.mock.calls[0][2].cards).toHaveLength(1000);
});
it('does not adopt a late saved result after permission ABA; keeps uncertainty visible', async () => {
 const { props, views } = fixture(); let resolve!: (value: ReturnType<typeof record>) => void; views.create.mockImplementation(() => new Promise(r => { resolve = r; })); const view = render(<MediaCanvasViewPanel {...props} />);
 fireEvent.change(screen.getByLabelText('画布标题'), { target: { value: 'Original pending' } }); fireEvent.click(screen.getByText('保存媒体画布'));
 view.rerender(<MediaCanvasViewPanel {...props} canMutate={false} />); view.rerender(<MediaCanvasViewPanel {...props} />);
 await act(async () => resolve(record({ ...blank(), title: 'Late private result' })));
 expect(screen.queryByDisplayValue('Late private result')).toBeNull(); expect((screen.getByLabelText('画布标题') as HTMLInputElement).value).toBe('Original pending'); expect(screen.getByText(/保存结果尚未确认/)).toBeTruthy();
});

// These owner/gesture tests do not exercise bitmap pixels; the dedicated minimap test checks drawing calls.
beforeEach(() => { vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(null); });
afterEach(() => vi.restoreAllMocks());
it('undoes and redoes local canvas edits without transport, then resets after explicit save', async () => {
 const { props, views } = fixture(); render(<MediaCanvasViewPanel {...props} />); const title = screen.getByLabelText('画布标题') as HTMLInputElement;
 fireEvent.change(title, { target: { value: 'Edited view' } }); fireEvent.click(screen.getByText('撤销媒体画布编辑')); expect(title.value).toBe('媒体素材画布'); fireEvent.click(screen.getByText('重做媒体画布编辑')); expect(title.value).toBe('Edited view'); expect(views.create).not.toHaveBeenCalled();
 fireEvent.click(screen.getByText('保存媒体画布')); await screen.findByText('已保存媒体画布'); expect((screen.getByText('撤销媒体画布编辑') as HTMLButtonElement).disabled).toBe(true);
});
it('leaves text-field undo alone and handles scoped canvas shortcuts', () => {
 const { props } = fixture(); render(<MediaCanvasViewPanel {...props} />); const title = screen.getByLabelText('画布标题') as HTMLInputElement; fireEvent.change(title, { target: { value: 'Edited' } });
 fireEvent.keyDown(title, { key: 'z', ctrlKey: true }); expect(title.value).toBe('Edited'); fireEvent.keyDown(screen.getByLabelText('媒体卡片视口'), { key: 'z', ctrlKey: true }); expect(title.value).toBe('媒体素材画布'); fireEvent.keyDown(screen.getByLabelText('媒体卡片视口'), { key: 'z', ctrlKey: true, shiftKey: true }); expect(title.value).toBe('Edited');
});
it('retires an alignment callback when the selected cohort changes', async () => {
 const { props, views } = fixture(); const d = blank(); d.cards = [0, 200, 400].map((x, i) => ({ id: `Card_${i}`, position: { x, y: 0 }, asset: { asset_id: 'asset', version: 1, digest: 'a'.repeat(64), kind: 'image' as const } })); views.get.mockResolvedValue(record(d));
 render(<MediaCanvasViewPanel {...props} />); fireEvent.click(screen.getByText('读取已存画布')); await screen.findByText('Saved · v1 · 0 张'); fireEvent.click(screen.getByText('Saved · v1 · 0 张')); await screen.findByText(/共 3\/1000/);
 fireEvent.click(screen.getByText('选择全部卡片（含视口外）')); const align = retained(screen.getByText('左对齐所选卡片'));
 fireEvent.click(screen.getAllByRole('button', { name: 'a.png' })[1], { shiftKey: true }); act(align);
 expect((screen.getByLabelText('卡片 x') as HTMLInputElement).value).toBe('200'); expect(screen.queryByText('尚未保存')).toBeNull();
});
