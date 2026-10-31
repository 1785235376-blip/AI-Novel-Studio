// @vitest-environment jsdom
// [HERMIA-FE-20261022 M1-2 / X-UX-02 / X-UX-05] Real React render of useWorkbench + CommandSearch (no network).
import {afterEach, describe, expect, it, vi} from 'vitest';
import {act, cleanup, fireEvent, render, screen} from '@testing-library/react';
afterEach(cleanup);
import {useEffect, useRef, useState} from 'react';
import {useWorkbench} from './useWorkbench';
import {CommandSearch, commandGroupOf, COMMAND_GROUP_ORDER} from './CommandSearch';
import {registerLayoutActions} from './useWorkbenchLayout';
import type {StudioModule} from '../ui/moduleRegistry';

function Harness({
  nav, project, openModule,
}: {
  nav: (id: string) => void;
  project: string;
  openModule?: (m: StudioModule) => void;
}) {
  const wb = useWorkbench(nav, {projectId: project}, [], undefined, openModule);
  const modeRef = useRef<'basic' | 'pro'>('basic');
  useEffect(() => registerLayoutActions(wb.actions, {
    getMode: () => modeRef.current,
    setMode: m => { modeRef.current = m; },
  }), [wb.actions]);
  return <><CommandSearch workbench={wb} onLegacy={nav}/><button onClick={() => void wb.open('experimental-x', nav)}>legacy</button></>;
}

describe('CommandSearch wiring', () => {
  it('opens via sidebar button, filters, executes registry action through legacy navigation', async () => {
    const nav = vi.fn(); render(<Harness nav={nav} project="p1"/>);
    fireEvent.click(screen.getByRole('button', {name: /搜索功能/}));
    const input = screen.getByRole('textbox', {name: '搜索功能'});
    fireEvent.change(input, {target: {value: '版本'}});
    const opts = screen.getAllByRole('option').map(o => o.textContent);
    expect(opts.some(t => t?.includes('打开：版本历史'))).toBe(true);
    await act(async () => { fireEvent.click(screen.getByRole('option', {name: /打开：版本历史/})); });
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

  it('X-UX-02: finds CONTROL/PLUGIN/WORKFLOW and executes workspace.open.*', async () => {
    const nav = vi.fn();
    const openModule = vi.fn();
    render(<Harness nav={nav} project="p1" openModule={openModule}/>);
    fireEvent.click(screen.getByRole('button', {name: /搜索功能/}));
    fireEvent.change(screen.getByRole('textbox', {name: '搜索功能'}), {target: {value: '主控'}});
    const opts = screen.getAllByRole('option');
    expect(opts.some(o => o.getAttribute('data-action-id') === 'workspace.open.control')).toBe(true);
    await act(async () => {
      fireEvent.click(opts.find(o => o.getAttribute('data-action-id') === 'workspace.open.control')!);
    });
    expect(openModule).toHaveBeenCalledWith('CONTROL');
    expect(screen.queryByRole('dialog')).toBeNull();
  });

  it('X-UX-02: id keyword search reaches plugin; Esc closes overlay (X-UX-05)', async () => {
    const openModule = vi.fn();
    render(<Harness nav={vi.fn()} project="p1" openModule={openModule}/>);
    fireEvent.click(screen.getByRole('button', {name: /搜索功能/}));
    fireEvent.change(screen.getByRole('textbox', {name: '搜索功能'}), {target: {value: 'plugin'}});
    expect(screen.getAllByRole('option').some(o => o.getAttribute('data-action-id') === 'workspace.open.plugin')).toBe(true);
    fireEvent.keyDown(screen.getByRole('dialog'), {key: 'Escape'});
    expect(screen.queryByRole('dialog')).toBeNull();
  });

  it('X-UX-05: ArrowDown + Enter runs active option', async () => {
    const openModule = vi.fn();
    render(<Harness nav={vi.fn()} project="p1" openModule={openModule}/>);
    fireEvent.click(screen.getByRole('button', {name: /搜索功能/}));
    const input = screen.getByRole('textbox', {name: '搜索功能'});
    fireEvent.change(input, {target: {value: 'workspace.open'}});
    const opts = screen.getAllByRole('option');
    expect(opts.length).toBeGreaterThan(1);
    fireEvent.keyDown(input, {key: 'ArrowDown'});
    await act(async () => { fireEvent.keyDown(input, {key: 'Enter'}); });
    expect(openModule).toHaveBeenCalled();
  });
});

// [HERMIA-FE-20261022 X-UX-11] groups + honest empty state + reachability
describe('X-UX-11 CommandSearch groups', () => {
  it('maps ids into 写作 / 媒体 / 壳·设置 with safe fallback', () => {
    expect(commandGroupOf('novel.open.overview')).toBe('写作');
    expect(commandGroupOf('panel.open.history')).toBe('写作');
    expect(commandGroupOf('workspace.open.novel')).toBe('写作');
    for (const m of ['image', 'video', 'audio', 'edit', 'assets']) expect(commandGroupOf(`workspace.open.${m}`)).toBe('媒体');
    expect(commandGroupOf('workspace.open.control')).toBe('壳·设置');
    expect(commandGroupOf('layout.reset')).toBe('布局'); // [HERMIA-FE-20261023 M1-s3]
    expect(commandGroupOf('something.unknown')).toBe('壳·设置');
  });
  it('renders group headers in order and every listed action stays reachable as an option', () => {
    let wbRef: ReturnType<typeof useWorkbench> | undefined;
    function H() {
      const wb = useWorkbench(() => {}, {projectId: 'p1'}); wbRef = wb;
      useEffect(() => registerLayoutActions(wb.actions, {getMode: () => 'basic', setMode: () => {}}), [wb.actions]);
      return <CommandSearch workbench={wb} onLegacy={() => {}}/>;
    }
    render(<H/>);
    fireEvent.click(screen.getByRole('button', {name: /搜索功能/}));
    const groups = screen.getAllByRole('group').map(g => g.getAttribute('data-command-group'));
    expect(groups).toEqual(COMMAND_GROUP_ORDER.filter(g => groups.includes(g)));
    expect(groups).toEqual(expect.arrayContaining(['写作', '媒体', '壳·设置']));
    const listed = wbRef!.actions.list('commandSearch', wbRef!.context()).map(a => a.id).sort();
    const shown = screen.getAllByRole('option').map(o => o.getAttribute('data-action-id')).sort();
    expect(shown).toEqual(listed);
  });
  it('ArrowDown order follows grouped visual order', () => {
    render(<Harness nav={vi.fn()} project="p1"/>);
    fireEvent.click(screen.getByRole('button', {name: /搜索功能/}));
    const opts = screen.getAllByRole('option');
    fireEvent.keyDown(screen.getByRole('textbox'), {key: 'ArrowDown'});
    expect(screen.getAllByRole('option')[1].getAttribute('aria-selected')).toBe('true');
    expect(opts[0].closest('[role="group"]')!.getAttribute('data-command-group')).toBe('写作');
  });
  it('no results shows honest empty state naming the query and no options', () => {
    render(<Harness nav={vi.fn()} project="p1"/>);
    fireEvent.click(screen.getByRole('button', {name: /搜索功能/}));
    fireEvent.change(screen.getByRole('textbox', {name: '搜索功能'}), {target: {value: 'zzqqxx不存在'}});
    expect(screen.queryAllByRole('option')).toHaveLength(0);
    expect(screen.queryAllByRole('group')).toHaveLength(0);
    expect(screen.getByTestId('command-search-empty').textContent).toContain('zzqqxx不存在');
  });
});

// [HERMIA-FE-20261022 X-UX-11-FIX] visibility: overlay must be a viewport-centered fixed panel, not anchored under the sidebar trigger.
import {readFileSync} from 'node:fs';
import {resolve} from 'node:path';
describe('CommandSearch overlay visibility', () => {
  it('portals to body and CSS fixes it centered and clamped to viewport', () => {
    render(<Harness nav={vi.fn()} project="p1"/>);
    fireEvent.click(screen.getByRole('button', {name: /搜索功能/}));
    const ov = screen.getByTestId('command-search-overlay');
    expect(ov.parentElement).toBe(document.body);
    const css = readFileSync(resolve(__dirname, 'commandSearch.css'), 'utf8');
    const rule = /\.wb-command__overlay\{([^}]*)\}/.exec(css)![1];
    expect(rule).toContain('position:fixed');
    expect(rule).not.toContain('top:100%');
    expect(rule).toMatch(/max-height:calc\(100vh/);
    expect(rule).toContain('translateX(-50%)');
  });
});
