// @vitest-environment jsdom
import { useLayoutEffect } from 'react';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { useStyleDNALeaveGuard, type StyleDNALeaveOwner } from './useStyleDNALeaveGuard';
let gate: ReturnType<typeof useStyleDNALeaveGuard>;
function Harness({ owner, identity = 'A' }: { owner?: StyleDNALeaveOwner; identity?: string }) {
  gate = useStyleDNALeaveGuard(() => true, identity);
  useLayoutEffect(() => owner && gate.register(owner), [owner]);
  return gate.dialog;
}
function owner() {
  const state = { dirty: true, busy: false, canSave: true, retired: false, revision: 1 };
  const value: StyleDNALeaveOwner = { key: {}, read: () => state,
    save: vi.fn(async () => { state.dirty = false; return state.revision; }),
    discard: vi.fn(() => { state.dirty = false; return true; }) };
  return { value, state };
}
const click = (name: string) => fireEvent.click(screen.getByRole('button', { name }));
const pending = () => screen.queryByRole('region', { name: 'Style DNA 未保存修改' });
afterEach(cleanup);
it('cancel preserves draft; discard executes only the newest intent once', async () => {
  const o = owner(), old = vi.fn(), next = vi.fn(); render(<Harness owner={o.value} />);
  act(() => { void gate.request(old); }); click('继续编辑 Style DNA'); expect(o.state.dirty).toBe(true); expect(old).not.toHaveBeenCalled();
  act(() => { void gate.request(old); void gate.request(next); });
  await act(async () => click('放弃 Style DNA 修改并离开'));
  expect(next).toHaveBeenCalledTimes(1); expect(old).not.toHaveBeenCalled(); expect(o.value.discard).toHaveBeenCalledTimes(1); expect(pending()).toBeNull();
});
it('requires successful save of the captured revision', async () => {
  const o = owner(), move = vi.fn(); render(<Harness owner={o.value} />);
  vi.mocked(o.value.save).mockResolvedValue(undefined);
  act(() => { void gate.request(move); }); await act(async () => click('保存 Style DNA 后离开'));
  expect(move).not.toHaveBeenCalled(); expect(pending()).toBeTruthy(); expect(o.state.dirty).toBe(true);
  vi.mocked(o.value.save).mockImplementation(async () => { o.state.dirty = false; return 99; });
  await act(async () => click('保存 Style DNA 后离开')); expect(move).not.toHaveBeenCalled();
  vi.mocked(o.value.save).mockResolvedValue(1);
  await act(async () => click('保存 Style DNA 后离开')); expect(move).toHaveBeenCalledTimes(1);
});
it('cancel does not cancel the remote save or allow its late result to navigate', async () => {
  const o = owner(), move = vi.fn(); let finish!: (revision: number | undefined) => void;
  o.value.save = vi.fn(() => { o.state.busy = true; gate.changed(o.value.key); return new Promise<number | undefined>(resolve => { finish = resolve; }); });
  render(<Harness owner={o.value} />); act(() => { void gate.request(move); }); click('保存 Style DNA 后离开');
  expect((screen.getByRole('button', { name: '放弃 Style DNA 修改并离开' }) as HTMLButtonElement).disabled).toBe(true);
  click('继续编辑 Style DNA');
  await act(async () => { o.state.busy = false; o.state.dirty = false; finish(1); });
  expect(move).not.toHaveBeenCalled(); expect(pending()).toBeNull(); expect(o.value.save).toHaveBeenCalledTimes(1);
});
it('old owner cleanup and updates cannot clear a newer registration', async () => {
  const a = owner(), b = owner(), move = vi.fn(); render(<Harness />); let release!: () => void;
  act(() => { release = gate.register(a.value); gate.register(b.value); release(); a.state.retired = true; gate.register(a.value); gate.changed(a.value.key); void gate.request(move); });
  expect(pending()).toBeTruthy(); await act(async () => click('放弃 Style DNA 修改并离开'));
  expect(a.value.discard).not.toHaveBeenCalled(); expect(b.value.discard).toHaveBeenCalledTimes(1);
});
it('retirement and A/B/A replacement suppress delayed saves', async () => {
  const a = owner(), b = owner(), move = vi.fn(); let finish!: (revision: number | undefined) => void;
  a.value.save = vi.fn(() => new Promise<number | undefined>(resolve => { finish = resolve; }));
  const view = render(<Harness owner={a.value} />); act(() => { void gate.request(move); }); click('保存 Style DNA 后离开');
  view.rerender(<Harness owner={b.value} identity="B" />); view.rerender(<Harness owner={a.value} identity="A" />);
  await act(async () => { a.state.dirty = false; finish(1); }); expect(move).not.toHaveBeenCalled(); expect(pending()).toBeNull();
  a.state.dirty = true; act(() => { void gate.request(move); a.state.retired = true; gate.changed(a.value.key); });
  expect(pending()).toBeNull(); expect(move).not.toHaveBeenCalled();
});
it('new intent invalidates already-running navigation', () => {
  render(<Harness />); let current!: () => boolean;
  act(() => { void gate.request(check => { current = check; }); }); expect(current()).toBe(true);
  act(() => { void gate.request(() => {}); }); expect(current()).toBe(false);
});

it('aborted original route retires only its own ticket and never saves', async () => {
  const o = owner(), first = new AbortController(), second = new AbortController(), move = vi.fn(); render(<Harness owner={o.value} />);
  act(() => { void gate.request(move, first.signal); void gate.request(move, second.signal); first.abort(); });
  expect(pending()).toBeTruthy(); act(() => second.abort()); expect(pending()).toBeNull();
  expect(move).not.toHaveBeenCalled(); expect(o.value.save).not.toHaveBeenCalled();
});

it('does not save a second version when the editor saved while the prompt was open', async () => {
  const o = owner(), move = vi.fn(); render(<Harness owner={o.value} />);
  act(() => { void gate.request(move); o.state.dirty = false; gate.changed(o.value.key); });
  await act(async () => click('保存 Style DNA 后离开'));
  expect(move).toHaveBeenCalledTimes(1); expect(o.value.save).not.toHaveBeenCalled();
});
