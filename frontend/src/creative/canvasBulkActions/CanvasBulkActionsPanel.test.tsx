// @vitest-environment jsdom
import { StrictMode } from 'react';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { CanvasBulkActionsPanel, type CanvasBulkActionsPanelProps } from './CanvasBulkActionsPanel';
import { input } from './canvasBulkActions.testFixtures';
import { planCanvasBulkAction } from './planCanvasBulkAction';

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
const props = (): CanvasBulkActionsPanelProps => ({ input: input(), ownerToken: {}, current: true, busy: false, canApply: true, isCurrent: () => true, onApply: vi.fn() });
const checkbox = (id = 'Card0') => screen.getByRole('checkbox', { name: `确认卡片 ${id} 的本次影响` }) as HTMLInputElement;
const button = () => screen.getByRole('button', { name: '应用到当前画布草稿（仍需 Save）' }) as HTMLButtonElement;
function retained<T = () => void>(element: HTMLElement, name = 'onClick'): T {
  return (element as any)[Object.keys(element).find(key => key.startsWith('__reactProps$'))!][name] as T;
}
const confirm = () => { fireEvent.click(checkbox('Card0')); fireEvent.click(checkbox('Card1')); };
const settled = async () => { await act(async () => { await Promise.resolve(); }); };

it('renders exact metadata effects and starts with no blanket or default consent', () => {
  const value = props(), network = vi.fn(); vi.stubGlobal('fetch', network); render(<CanvasBulkActionsPanel {...value} />);
  expect(screen.getAllByRole('checkbox')).toHaveLength(2); expect(checkbox().checked).toBe(false); expect(button().disabled).toBe(true);
  expect(screen.getByText(/当前元数据可用/)).toBeTruthy(); expect(screen.getByText(/元数据已过期/)).toBeTruthy();
  expect(screen.getAllByText(/解除其分组成员关系/)).toHaveLength(2);
  expect(screen.getByText(/本次只改当前画布草稿/).textContent).toContain('不会生成或删除素材文件');
  expect(screen.queryByRole('button', { name: /全选/ })).toBeNull(); expect(network).not.toHaveBeenCalled(); expect(value.onApply).not.toHaveBeenCalled();
});

it('requires every checkbox, rejects a bypass callback, and emits exactly one original draft edit', async () => {
  const value = props(), expected = planCanvasBulkAction(value.input).definition; render(<CanvasBulkActionsPanel {...value} />);
  act(() => retained(button())()); expect(value.onApply).not.toHaveBeenCalled();
  fireEvent.click(checkbox()); act(() => retained(button())()); expect(value.onApply).not.toHaveBeenCalled();
  fireEvent.click(checkbox('Card1')); const apply = retained(button());
  act(() => { apply(); apply(); }); await settled();
  expect(value.onApply).toHaveBeenCalledTimes(1); expect(value.onApply).toHaveBeenCalledWith(expected);
  expect(button().disabled).toBe(true); expect(screen.getByText(/已交回原画布草稿编辑/)).toBeTruthy();
});

it('withdraws a single item consent and keeps keyboard labels and focus usable', () => {
  const value = props(); render(<CanvasBulkActionsPanel {...value} />); confirm(); expect(button().disabled).toBe(false);
  checkbox().focus(); expect(document.activeElement).toBe(checkbox()); fireEvent.click(checkbox());
  expect(button().disabled).toBe(true); expect(checkbox('Card1').checked).toBe(true); expect(value.onApply).not.toHaveBeenCalled();
});

it.each(['definition', 'base', 'pin', 'selection', 'operation', 'owner', 'permission', 'busy', 'current'])(
  'retires consent and retained callbacks after %s A/B/A', async kind => {
    const value = props(), original = structuredClone(value.input), firstOwner = value.ownerToken;
    const view = render(<CanvasBulkActionsPanel {...value} />); confirm(); const oldApply = retained(button());
    const oldCheck = retained<(event: { target: { checked: boolean } }) => void>(checkbox(), 'onChange');
    const next = { ...value, input: structuredClone(value.input) };
    if (kind === 'definition') next.input.definition.title = 'Changed';
    if (kind === 'base') next.input.base!.version++;
    if (kind === 'pin') next.input.definition.cards[0].asset!.version++;
    if (kind === 'selection') next.input.selectedIds = ['Card0', 'Card2'];
    if (kind === 'operation') next.input.operation = 'ALIGN_LEFT';
    if (kind === 'owner') next.ownerToken = {};
    if (kind === 'permission') next.canApply = false;
    if (kind === 'busy') next.busy = true;
    if (kind === 'current') next.current = false;
    view.rerender(<CanvasBulkActionsPanel {...next} />);
    view.rerender(<CanvasBulkActionsPanel {...value} input={original} ownerToken={firstOwner} />);
    act(() => { oldCheck({ target: { checked: true } }); oldApply(); }); await settled();
    expect(value.onApply).not.toHaveBeenCalled(); expect(checkbox().checked).toBe(false); expect(button().disabled).toBe(true);
    confirm(); fireEvent.click(button()); await settled(); expect(value.onApply).toHaveBeenCalledTimes(1);
  });

it('replans in-place changes without rerender and retires an observed B before A returns', async () => {
  const value = props(); const view = render(<CanvasBulkActionsPanel {...value} />); confirm(); const oldApply = retained(button());
  const oldX = value.input.definition.cards[2].position.x; value.input.definition.cards[2].position.x++;
  act(() => oldApply()); value.input.definition.cards[2].position.x = oldX;
  act(() => oldApply()); await settled(); expect(value.onApply).not.toHaveBeenCalled(); expect(button().disabled).toBe(true);
  view.rerender(<CanvasBulkActionsPanel {...value} />);
  confirm(); fireEvent.click(button()); await settled(); expect(value.onApply).toHaveBeenCalledTimes(1);
});

it('retires a false live getter observation and does not read stale input content getters', async () => {
  let live = true; const value = props(); value.isCurrent = () => live;
  const view = render(<CanvasBulkActionsPanel {...value} />); confirm(); const oldApply = retained(button());
  const original = value.input.definition, getter = vi.fn(() => { throw new Error('stale content'); });
  Object.defineProperty(value.input, 'definition', { configurable: true, get: getter }); live = false;
  act(() => oldApply()); expect(getter).not.toHaveBeenCalled(); live = true;
  Object.defineProperty(value.input, 'definition', { configurable: true, value: original });
  view.rerender(<CanvasBulkActionsPanel {...value} />); act(() => oldApply()); await settled();
  expect(value.onApply).not.toHaveBeenCalled(); expect(checkbox().checked).toBe(false);
});

it('does not read any input content when the outer owner is stale', () => {
  const value = props(), getter = vi.fn(() => { throw new Error('stale content'); });
  Object.defineProperty(value.input, 'definition', { get: getter }); value.current = false;
  render(<CanvasBulkActionsPanel {...value} />); expect(getter).not.toHaveBeenCalled(); expect(screen.queryByRole('checkbox')).toBeNull();
});

it('blocks overlapping calls while the parent edit is pending, and ignores late feedback after input replacement', async () => {
  let resolve!: (result: boolean) => void; const value = props(); value.onApply = vi.fn(() => new Promise<boolean>(done => { resolve = done; }));
  const view = render(<CanvasBulkActionsPanel {...value} />); confirm(); const oldApply = retained(button()); act(() => oldApply());
  const next = { ...value, input: { ...value.input, operation: 'ALIGN_TOP' as const } }; view.rerender(<CanvasBulkActionsPanel {...next} />);
  act(() => { retained(button())(); oldApply(); }); expect(value.onApply).toHaveBeenCalledTimes(1);
  await act(async () => resolve(true)); expect(screen.queryByText(/已交回原画布草稿编辑/)).toBeNull();
  expect(checkbox().checked).toBe(false); expect(button().disabled).toBe(true);
});

it('guards unmounted checkbox/apply callbacks and a parent edit resolving after unmount', async () => {
  let resolve!: () => void; const value = props(); value.onApply = vi.fn(() => new Promise<void>(done => { resolve = done; }));
  const view = render(<CanvasBulkActionsPanel {...value} />); confirm(); const oldApply = retained(button());
  const oldCheck = retained<(event: { target: { checked: boolean } }) => void>(checkbox(), 'onChange');
  act(() => oldApply()); view.unmount(); act(() => { oldCheck({ target: { checked: true } }); oldApply(); }); await act(async () => resolve());
  expect(value.onApply).toHaveBeenCalledTimes(1);
});

it('hides old success feedback after a new selection and never revives consent on a harmless parent render', async () => {
  const value = props(), view = render(<CanvasBulkActionsPanel {...value} />); confirm();
  const oldApply = retained(button()); view.rerender(<CanvasBulkActionsPanel {...value} />);
  expect(checkbox().checked).toBe(true); act(() => oldApply()); expect(value.onApply).not.toHaveBeenCalled();
  fireEvent.click(button()); await settled(); expect(screen.getByText(/已交回原画布草稿编辑/)).toBeTruthy();
  view.rerender(<CanvasBulkActionsPanel {...value} input={{ ...value.input, operation: 'ALIGN_LEFT' }} />);
  expect(screen.queryByText(/已交回原画布草稿编辑/)).toBeNull(); expect(checkbox().checked).toBe(false);
});

it('ignores a late rejection after an in-place pin change and after owner retirement', async () => {
  let reject!: (error: Error) => void; const value = props();
  value.onApply = vi.fn(() => new Promise<void>((_resolve, fail) => { reject = fail; }));
  render(<CanvasBulkActionsPanel {...value} />); confirm(); fireEvent.click(button());
  value.input.definition.cards[0].asset!.version++;
  await act(async () => reject(new Error('late private failure')));
  expect(screen.queryByText(/本次草稿编辑未确认/)).toBeNull(); expect(screen.queryByText(/late private failure/)).toBeNull();
  expect(checkbox().checked).toBe(false); expect(value.onApply).toHaveBeenCalledTimes(1);
});

it('observes and retires in-place changes even through a disabled pending callback', async () => {
  let resolve!: () => void; const value = props(); value.onApply = vi.fn(() => new Promise<void>(done => { resolve = done; }));
  render(<CanvasBulkActionsPanel {...value} />); confirm(); fireEvent.click(button());
  const pendingClick = retained(button()), original = value.input.definition.cards[0].asset!.version;
  value.input.definition.cards[0].asset!.version++;
  act(() => pendingClick()); value.input.definition.cards[0].asset!.version = original;
  await act(async () => resolve()); expect(screen.queryByText(/已交回原画布草稿编辑/)).toBeNull();
  expect(checkbox().checked).toBe(false); expect(value.onApply).toHaveBeenCalledTimes(1);
});

it.each([false, new Error('raw provider secret')])('shows bounded parent failure feedback without retrying or exposing errors', async outcome => {
  const value = props(); value.onApply = vi.fn(() => outcome === false ? false : Promise.reject(outcome)); render(<CanvasBulkActionsPanel {...value} />);
  confirm(); fireEvent.click(button()); await settled(); fireEvent.click(button());
  expect(value.onApply).toHaveBeenCalledTimes(1); expect(button().disabled).toBe(true); expect(screen.queryByText(/raw provider secret/)).toBeNull();
});

it('works in StrictMode and renders explicit unavailable and unverified pin states', async () => {
  const value = props(); value.input.base = undefined; delete value.input.definition.cards[0].asset;
  render(<StrictMode><CanvasBulkActionsPanel {...value} /></StrictMode>);
  expect(screen.getByText(/来源不可见或不可用/)).toBeTruthy(); expect(screen.getByText(/当前元数据未核验/)).toBeTruthy();
  confirm(); fireEvent.click(button()); await settled(); expect(value.onApply).toHaveBeenCalledTimes(1);
});
