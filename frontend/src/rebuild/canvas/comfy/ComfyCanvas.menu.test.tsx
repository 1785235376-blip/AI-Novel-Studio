// @vitest-environment jsdom
// [HERMIA-FE-20261031 DUALCANVAS-COMFY P2-2] 添加节点菜单 = combobox + listbox：分组 role=group 有名称；↑↓ 移动、Enter 添加、Esc 关闭。
import {describe, it, expect, beforeEach, afterEach} from 'vitest';
import {render, fireEvent, cleanup, within} from '@testing-library/react';
import {DualStack} from '../DualStack';
import {sessionCanvasStore} from '../RebuildCanvas';
import {sessionLayoutStore} from '../dualLayout';
import {useStudio} from '../../../store';

const low = () => document.querySelector('[data-canvas-layer=lower]') as HTMLElement;
const open = () => fireEvent.click(low().querySelector('[data-comfy-add]')!);
const menu = () => low().querySelector('[data-add-node-menu]') as HTMLElement | null;
beforeEach(() => { cleanup(); localStorage.clear(); sessionCanvasStore.clear(); sessionLayoutStore.clear(); useStudio.setState({novelId: 'n1', actor: undefined, scope: undefined}); });
afterEach(() => cleanup());

describe('add-node menu a11y pattern', () => {
  it('combobox controls a listbox whose children are named groups of options', () => {
    render(<DualStack kind="image" scope="n1" />); open();
    const cb = within(menu()!).getByRole('combobox');
    const lb = document.getElementById(cb.getAttribute('aria-controls')!)!;
    expect(lb.getAttribute('role')).toBe('listbox'); expect(cb.getAttribute('aria-expanded')).toBe('true');
    const groups = [...lb.children].filter(e => e.getAttribute('role') === 'group');
    expect(groups.length).toBe(11); expect(lb.children.length).toBe(11);
    for (const g of groups) { const id = g.getAttribute('aria-labelledby'); expect(id && document.getElementById(id)?.textContent).toBeTruthy(); }
    expect(lb.querySelectorAll('[role=option]').length).toBe(53);
    expect(menu()!.querySelectorAll('[role=menu],[role=menuitem]').length).toBe(0);
  });
  it('ArrowDown/ArrowUp move aria-activedescendant, Enter adds, Esc closes', () => {
    render(<DualStack kind="video" scope="n1" />); open();
    const cb = within(menu()!).getByRole('combobox');
    fireEvent.change(cb, {target: {value: 'ksampler'}});
    fireEvent.keyDown(cb, {key: 'ArrowDown'}); fireEvent.keyDown(cb, {key: 'ArrowDown'}); fireEvent.keyDown(cb, {key: 'ArrowUp'});
    const act = document.getElementById(cb.getAttribute('aria-activedescendant')!)!;
    expect(act.getAttribute('data-node-type')).toBe('KSampler'); expect(act.getAttribute('aria-selected')).toBe('true');
    fireEvent.keyDown(cb, {key: 'Enter'});
    expect(menu()).toBeNull(); expect(low().querySelectorAll('[data-node-class=KSampler]').length).toBe(1);
    open(); fireEvent.keyDown(within(menu()!).getByRole('combobox'), {key: 'Escape'}); expect(menu()).toBeNull();
  });
});
