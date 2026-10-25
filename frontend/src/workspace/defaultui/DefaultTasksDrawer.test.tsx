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
