// @vitest-environment jsdom
// [HERMIA-FE-20261024 M4-s1] keyboard operability + ARIA for the unified DockLayout.
import {cleanup, fireEvent, render, screen} from '@testing-library/react';
import {afterEach, describe, expect, it} from 'vitest';
import {DockLayout} from './DockLayout';
import {MemStorage, SCOPE, SPECS, VP} from './testSpecs';

afterEach(cleanup);
if (typeof window !== 'undefined' && !('PointerEvent' in window)) {
  (window as unknown as {PointerEvent: unknown}).PointerEvent = class extends MouseEvent {};
}
const setup = () => render(<DockLayout specs={SPECS} scope={SCOPE} storage={new MemStorage()} viewport={VP} renderPanel={id => <p>{id} 内容</p>} />);

describe('M4-s1 keyboard + aria', () => {
  it('skip link is the first focusable element and moves focus to the main region', () => {
    setup();
    const root = screen.getByTestId('dock-layout');
    const first = root.querySelector('a,button,select,[tabindex="0"]');
    const skip = screen.getByTestId('uw-skip-main');
    expect(first).toBe(skip);
    fireEvent.click(skip);
    const main = screen.getByRole('main', {name: '主区域'});
    expect(document.activeElement).toBe(main);
  });

  it('panels are labelled regions; collapse button names its panel and controls it', () => {
    setup();
    for (const s of SPECS) {
      const el = document.getElementById(`uw-panel-${s.id}`);
      if (!el) continue;
      expect(el.getAttribute('role')).toBe('region');
      // [HERMIA-FE-20261024 M4-s1fix] name now comes from aria-labelledby (tab + header), so it contains the title.
      expect(screen.getByRole('region', {name: new RegExp(s.title)})).toBe(el);
    }
    const btn = document.getElementById('uw-panel-outline')!.querySelector('button[aria-expanded]')!;
    expect(document.getElementById(btn.getAttribute('aria-controls')!)).not.toBeNull();
  });

  it('splitter: arrows change aria-valuenow, Shift = 4x, Home/End hit min/max, valuemax set', () => {
    setup();
    const sep = () => screen.getByTestId('resize-outline');
    const now = () => Number(sep().getAttribute('aria-valuenow'));
    const min = Number(sep().getAttribute('aria-valuemin')); const max = Number(sep().getAttribute('aria-valuemax'));
    expect(min).toBe(180); expect(max).toBeGreaterThan(min);
    expect(sep().getAttribute('aria-controls')).toBe('uw-panel-outline');
    fireEvent.keyDown(sep(), {key: 'Home'}); expect(now()).toBe(180);
    fireEvent.keyDown(sep(), {key: 'ArrowRight'}); expect(now()).toBe(196);
    fireEvent.keyDown(sep(), {key: 'ArrowLeft'}); expect(now()).toBe(180);
    fireEvent.keyDown(sep(), {key: 'ArrowRight', shiftKey: true}); expect(now()).toBe(244);
    fireEvent.keyDown(sep(), {key: 'End'}); expect(now()).toBe(Number(sep().getAttribute('aria-valuemax')));
    expect(now()).toBeGreaterThan(244);
  });

  it('Esc during a pointer resize restores the original size', () => {
    setup();
    const sep = screen.getByTestId('resize-outline');
    const before = Number(sep.getAttribute('aria-valuenow'));
    fireEvent.pointerDown(sep, {clientX: 300, clientY: 300});
    fireEvent.pointerMove(window, {clientX: 360, clientY: 360});
    const moved = Number(screen.getByTestId('resize-outline').getAttribute('aria-valuenow'));
    expect(moved).not.toBe(before);
    fireEvent.keyDown(window, {key: 'Escape'});
    expect(Number(screen.getByTestId('resize-outline').getAttribute('aria-valuenow'))).toBe(before);
    fireEvent.pointerMove(window, {clientX: 420, clientY: 420});
    expect(Number(screen.getByTestId('resize-outline').getAttribute('aria-valuenow'))).toBe(before);
  });

  it('main tabs: tablist with roving tabindex; ArrowRight moves focus and selects', async () => {
    setup();
    const list = screen.queryByRole('tablist', {name: '中间面板'});
    if (!list) throw new Error('tablist missing');
    const tabs = () => Array.from(list.querySelectorAll<HTMLElement>('[role="tab"]'));
    expect(tabs().filter(t => t.tabIndex === 0)).toHaveLength(1);
    const start = tabs().find(t => t.tabIndex === 0)!; start.focus();
    fireEvent.keyDown(start, {key: 'ArrowRight'});
    const next = tabs()[(tabs().indexOf(start) + 1) % tabs().length];
    expect(document.activeElement).toBe(next);
    await new Promise(r => setTimeout(r, 400));
    expect(next.getAttribute('aria-selected')).toBe('true');
  });
});
