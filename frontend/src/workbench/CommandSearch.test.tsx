// @vitest-environment jsdom
// [HERMIA-FE-20261022 M1-2] Real React render of useWorkbench + CommandSearch (no network).
import {afterEach, describe, expect, it, vi} from 'vitest';
import {act, cleanup, fireEvent, render, screen} from '@testing-library/react';
afterEach(cleanup);
import {useState} from 'react';
import {useWorkbench} from './useWorkbench';
import {CommandSearch} from './CommandSearch';

function Harness({nav, project}: {nav: (id: string) => void; project: string}) {
  const wb = useWorkbench(nav, {projectId: project});
  return <><CommandSearch workbench={wb} onLegacy={nav}/><button onClick={() => void wb.open('experimental-x', nav)}>legacy</button></>;
}
describe('CommandSearch wiring', () => {
  it('opens via sidebar button, filters, executes registry action through legacy navigation', async () => {
    const nav = vi.fn(); render(<Harness nav={nav} project="p1"/>);
    fireEvent.click(screen.getByRole('button', {name: /搜索功能/}));
    const input = screen.getByRole('textbox', {name: '搜索功能'});
    fireEvent.change(input, {target: {value: '版本'}});
    const opts = screen.getAllByRole('option').map(o => o.textContent);
    expect(opts).toContain('打开：版本历史');
    await act(async () => { fireEvent.click(screen.getByRole('option', {name: '打开：版本历史'})); });
    expect(nav).toHaveBeenCalledTimes(1); expect(nav).toHaveBeenCalledWith('history');
    expect(screen.queryByRole('dialog')).toBeNull();
  });
  it('does not steal Ctrl+K (owned by AppShell global command)', () => {
    render(<Harness nav={vi.fn()} project="p1"/>);
    fireEvent.keyDown(document, {key: 'k', ctrlKey: true});
    expect(screen.queryByRole('dialog')).toBeNull();
  });
  it('IME Enter does not execute; unregistered ids fall back to legacy path', async () => {
    const nav = vi.fn(); render(<Harness nav={nav} project="p1"/>);
    fireEvent.click(screen.getByRole('button', {name: /搜索功能/}));
    fireEvent.keyDown(screen.getByRole('textbox'), {key: 'Enter', isComposing: true});
    expect(nav).not.toHaveBeenCalled();
    await act(async () => { fireEvent.click(screen.getByText('legacy')); });
    expect(nav).toHaveBeenCalledWith('experimental-x');
  });
  it('project switch A→B→A re-renders with a new epoch (old context becomes stale)', async () => {
    let wbRef: ReturnType<typeof useWorkbench> | undefined;
    function H() { const [p, setP] = useState('A'); wbRef = useWorkbench(() => {}, {projectId: p}); return <button onClick={() => setP(x => x === 'A' ? 'B' : 'A')}>switch</button>; }
    render(<H/>); const old = wbRef!.context();
    fireEvent.click(screen.getByText('switch')); fireEvent.click(screen.getByText('switch'));
    expect(await wbRef!.actions.execute('panel.open.history', old)).toEqual({status: 'stale'});
  });
});
