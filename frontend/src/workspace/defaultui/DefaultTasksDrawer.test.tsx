// @vitest-environment jsdom
import {afterEach, describe, expect, it, vi} from 'vitest';
import {cleanup, fireEvent, render, screen} from '@testing-library/react';
import {DefaultTasksDrawer} from './DefaultTasksDrawer';

afterEach(cleanup);
describe('DefaultTasksDrawer (default UI port of the unified task loop)', () => {
  it('closed by default; opens a labelled dialog; Esc closes and returns focus', () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch');
    render(<DefaultTasksDrawer novelId="p1" actor={undefined} scope={undefined} sessionToken="" />);
    expect(screen.queryByRole('dialog')).toBeNull();
    const btn = screen.getByRole('button', {name: '任务与结果'});
    fireEvent.click(btn);
    const dlg = screen.getByRole('dialog', {name: '任务与结果'});
    expect(dlg.textContent).toContain('仅本次会话');
    expect(dlg.textContent).not.toMatch(/定位来源节点|查看执行画布|画布|p1/);
    fireEvent.keyDown(dlg, {key: 'Escape'});
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(document.activeElement).toBe(btn);
    expect(fetchSpy).not.toHaveBeenCalled();
  });
});

describe('DefaultTasksDrawer focus trap + scroll (Vera P1)', () => {
  it('Tab / Shift+Tab stay inside the dialog; Esc still closes after cycling', () => {
    render(<DefaultTasksDrawer novelId="p1" actor={undefined} scope={undefined} sessionToken="" />);
    fireEvent.click(screen.getByRole('button', {name: '任务与结果'}));
    const dlg = screen.getByRole('dialog');
    const f = [...dlg.querySelectorAll<HTMLElement>('button:not([disabled])')];
    expect(f.length).toBeGreaterThan(0);
    f[f.length - 1].focus(); fireEvent.keyDown(f[f.length - 1], {key: 'Tab'});
    expect(document.activeElement).toBe(f[0]);
    fireEvent.keyDown(f[0], {key: 'Tab', shiftKey: true});
    expect(document.activeElement).toBe(f[f.length - 1]);
    dlg.focus(); fireEvent.keyDown(dlg, {key: 'Tab', shiftKey: true});
    expect(dlg.contains(document.activeElement)).toBe(true);
    fireEvent.keyDown(document.activeElement!, {key: 'Escape'});
    expect(screen.queryByRole('dialog')).toBeNull();
  });
  it('drawer is height-capped and scrollable so the last action stays reachable', () => {
    render(<DefaultTasksDrawer novelId="p1" actor={undefined} scope={undefined} sessionToken="" />);
    fireEvent.click(screen.getByRole('button', {name: '任务与结果'}));
    const st = screen.getByRole('dialog').style;
    expect(st.maxHeight).toMatch(/vh|calc/);
    expect(st.overflowY).toBe('auto');
  });
});

describe('DefaultTasksDrawer focus recovery (Vera P1-2 / M10)', () => {
  it('document-level Esc closes when focus is outside the dialog (kills M10)', () => {
    render(<DefaultTasksDrawer novelId="p1" actor={undefined} scope={undefined} sessionToken="" />);
    fireEvent.click(screen.getByRole('button', {name: '任务与结果'}));
    (document.activeElement as HTMLElement | null)?.blur();
    expect(document.activeElement).toBe(document.body);
    fireEvent.keyDown(document, {key: 'Escape'});
    expect(screen.queryByRole('dialog')).toBeNull();
  });
  it('Tab from body (focused element unmounted) re-enters the dialog', () => {
    render(<DefaultTasksDrawer novelId="p1" actor={undefined} scope={undefined} sessionToken="" />);
    fireEvent.click(screen.getByRole('button', {name: '任务与结果'}));
    (document.activeElement as HTMLElement | null)?.blur();
    fireEvent.keyDown(document, {key: 'Tab'});
    expect(screen.getByRole('dialog').contains(document.activeElement)).toBe(true);
    expect(document.activeElement).toBe(screen.getByTestId('dui-tasks-home'));
  });
  it('when the focused confirm button unmounts, focus moves to the stable drawer title', async () => {
    render(<DefaultTasksDrawer novelId="p1" actor={undefined} scope={undefined} sessionToken="" />);
    fireEvent.click(screen.getByRole('button', {name: '任务与结果'}));
    const dlg = screen.getByRole('dialog');
    const b = document.createElement('button'); b.textContent = '确认采用'; dlg.appendChild(b); b.focus();
    expect(document.activeElement).toBe(b);
    b.remove();
    await new Promise(r => setTimeout(r, 0));
    expect(document.activeElement).toBe(screen.getByTestId('dui-tasks-home'));
  });
});
