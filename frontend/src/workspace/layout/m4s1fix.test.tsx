// @vitest-environment jsdom
// [HERMIA-FE-20261024 M4-s1fix] tab wrap-around, Home/End, aria-controls/labelledby, multiselectable in split.
import {act, cleanup, fireEvent, render, screen} from '@testing-library/react';
import {afterEach, describe, expect, it} from 'vitest';
import {DockLayout} from './DockLayout';
import {MemStorage, SCOPE, SPECS, VP} from './testSpecs';

afterEach(cleanup);
const SPECS3 = [...SPECS, {id: 'third', title: '第三面板', defaultDock: 'main' as const, docks: ['main' as const], defaultSize: 800, minSize: 320}];
const setup = (specs = SPECS3) => render(<DockLayout specs={specs} scope={SCOPE} storage={new MemStorage()} viewport={VP} renderPanel={id => <p>{id} 内容</p>} />);
const tabs = () => Array.from(screen.getByRole('tablist', {name: '中间面板'}).querySelectorAll<HTMLElement>('[role="tab"]'));
const key = (k: string) => { fireEvent.keyDown(document.activeElement!, {key: k}); };
const focused = () => (document.activeElement as HTMLElement).dataset.panelTab;

describe('M4-s1fix tablist', () => {
  it('ArrowRight wraps last→first, ArrowLeft wraps first→last, Home/End jump', async () => {
    setup();
    expect(tabs().length).toBe(3);
    // Activation may reorder main panels, so each expectation is relative to the order right before the key press.
    const step = async (k: string, target: (i: number, n: number) => number) => {
      await act(async () => { await new Promise(r => setTimeout(r, 350)); });
      const ids = tabs().map(t => t.dataset.panelTab); const i = ids.indexOf(focused());
      expect(i).toBeGreaterThanOrEqual(0);
      await act(async () => { key(k); }); expect(focused()).toBe(ids[target(i, ids.length)]);
    };
    await act(async () => { tabs()[0].focus(); });
    await step('ArrowLeft', (_i, n) => n - 1);          // first → last (wrap)
    await step('End', (_i, n) => n - 1);
    await step('ArrowRight', () => 0);                  // last → first (wrap)
    await step('Home', () => 0);
    await step('ArrowRight', i => i + 1);
    await step('End', (_i, n) => n - 1);
    await step('Home', () => 0);
    await step('ArrowDown', i => i + 1);
    await step('ArrowUp', i => i - 1);
    // explicit wrap checks from the edges
    await act(async () => { tabs()[2].focus(); }); await step('ArrowRight', () => 0);
    await act(async () => { tabs()[0].focus(); }); await step('ArrowUp', (_i, n) => n - 1);
  });

  // [HERMIA-FE-20261024 M4-s1fix2] exact accessible names in split (two main panels rendered) + aria-controls only for rendered panels.
  it('split: each main region is named exactly "<its tab> <its header>"', async () => {
    setup();
    fireEvent.change(screen.getByLabelText('分屏方式'), {target: {value: 'split-h'}});
    await act(async () => { await new Promise(r => setTimeout(r, 400)); });
    const shown = tabs().filter(t => t.getAttribute('aria-selected') === 'true');
    expect(shown).toHaveLength(2);
    for (const t of shown) {
      const title = SPECS3.find(s => s.id === t.dataset.panelTab)!.title;
      expect(screen.getByRole('region', {name: new RegExp(`^${title} ${title}$`)})).toBe(document.getElementById(`uw-panel-${t.dataset.panelTab}`));
    }
  });

  it('single view: aria-controls only on tabs whose panel is in the DOM', () => {
    setup();
    let hidden = 0;
    for (const t of tabs()) {
      const c = t.getAttribute('aria-controls');
      if (t.getAttribute('aria-selected') === 'true') expect(document.getElementById(c!)).not.toBeNull();
      else { hidden++; expect(c).toBeNull(); expect(document.getElementById(`uw-panel-${t.dataset.panelTab}`)).toBeNull(); }
    }
    expect(hidden).toBe(2);
  });

  it('every tab has id; selected tabs have aria-controls; visible main panels are labelledby their tab and header', () => {
    setup();
    for (const t of tabs()) expect(t.id).toBe(`uw-tab-${t.dataset.panelTab}`);
    for (const t of tabs().filter(t => t.getAttribute('aria-selected') === 'true')) expect(t.getAttribute('aria-controls')).toBe(`uw-panel-${t.dataset.panelTab}`);
    const shown = tabs().filter(t => t.getAttribute('aria-selected') === 'true');
    expect(shown.length).toBeGreaterThan(0);
    for (const t of shown) {
      const panel = document.getElementById(t.getAttribute('aria-controls')!)!;
      expect(panel.getAttribute('aria-labelledby')!.split(' ')).toEqual([t.id, `uw-panel-title-${t.dataset.panelTab}`]);
      expect(document.getElementById(`uw-panel-title-${t.dataset.panelTab}`)).not.toBeNull();
    }
    const outline = document.getElementById('uw-panel-outline')!;
    expect(outline.getAttribute('aria-labelledby')).toBe('uw-panel-title-outline');
  });

  it('aria-multiselectable only when split shows two tabs selected', () => {
    setup();
    const list = () => screen.getByRole('tablist', {name: '中间面板'});
    expect(list().hasAttribute('aria-multiselectable')).toBe(false);
    expect(tabs().filter(t => t.getAttribute('aria-selected') === 'true')).toHaveLength(1);
    fireEvent.change(screen.getByLabelText('分屏方式'), {target: {value: 'split-h'}});
    return new Promise<void>(r => setTimeout(r, 400)).then(() => {
      expect(tabs().filter(t => t.getAttribute('aria-selected') === 'true')).toHaveLength(2);
      expect(list().getAttribute('aria-multiselectable')).toBe('true');
    });
  });
});
