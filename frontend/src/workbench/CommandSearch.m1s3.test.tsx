// @vitest-environment jsdom
// [HERMIA-FE-20261023 M1-s3] Vera P3: raw action ids are not visible text, but still searchable; layout.* → 「布局」.
import {afterEach, describe, expect, it} from 'vitest';
import {cleanup, fireEvent, render, screen, within} from '@testing-library/react';
import {useEffect} from 'react';
import {useWorkbench} from './useWorkbench';
import {CommandSearch, commandGroupOf, COMMAND_GROUP_ORDER} from './CommandSearch';
import {registerLayoutActions} from './useWorkbenchLayout';
afterEach(cleanup);

function H() {
  const wb = useWorkbench(() => {}, {projectId: 'p1'});
  useEffect(() => registerLayoutActions(wb.actions, {getMode: () => 'basic', setMode: () => {}}), [wb.actions]);
  return <CommandSearch workbench={wb} onLegacy={() => {}}/>;
}
const open = () => fireEvent.click(screen.getByRole('button', {name: /搜索功能/}));

describe('CommandSearch M1-s3', () => {
  it('no option shows its raw id as visible text', () => {
    render(<H/>); open();
    const opts = screen.getAllByRole('option');
    expect(opts.length).toBeGreaterThan(5);
    for (const o of opts) {
      const id = o.getAttribute('data-action-id')!;
      expect(o.textContent).not.toContain(id);
    }
    expect(document.querySelector('.wb-command__id')).toBeNull();
    expect(screen.getByTestId('command-search-overlay').textContent).not.toMatch(/panel\.open\.|layout\.|workspace\.open\./);
  });
  it('ids still participate in search matching', () => {
    render(<H/>); open();
    fireEvent.change(screen.getByRole('textbox', {name: '搜索功能'}), {target: {value: 'panel.open.history'}});
    const ids = screen.getAllByRole('option').map(o => o.getAttribute('data-action-id'));
    expect(ids).toContain('panel.open.history');
    fireEvent.change(screen.getByRole('textbox', {name: '搜索功能'}), {target: {value: 'open history'}});
    expect(screen.getAllByRole('option').map(o => o.getAttribute('data-action-id'))).toContain('panel.open.history');
  });
  it('layout.* actions are in 「布局」 group, not 壳·设置', () => {
    expect(COMMAND_GROUP_ORDER).toEqual(['写作', '媒体', '布局', '壳·设置']);
    for (const id of ['layout.reset', 'layout.reopenPanel', 'layout.toggleCollapse', 'layout.switchSplit']) expect(commandGroupOf(id)).toBe('布局');
    expect(commandGroupOf('workspace.open.control')).toBe('壳·设置');
    render(<H/>); open();
    const shell = screen.queryByRole('group', {name: '壳·设置'});
    if (shell) for (const o of within(shell).queryAllByRole('option')) expect(o.getAttribute('data-action-id')!.startsWith('layout.')).toBe(false);
  });
});
