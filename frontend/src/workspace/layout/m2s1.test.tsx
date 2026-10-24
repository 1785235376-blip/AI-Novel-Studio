// @vitest-environment jsdom
// [HERMIA-FE-20261024 M2-s1] N4 (floats clamped to the zoom-aware viewport) and N5 (visible main-panel tabs + layout.showPanel).
// jsdom's CSSOM drops `zoom`, so zoom is set as inline style text (what devtools/extensions/page CSS-zoom do); browsers read it via getComputedStyle.
import {act, cleanup, fireEvent, render, screen, waitFor} from '@testing-library/react';
import {afterEach, describe, expect, it} from 'vitest';
import {DockLayout, effectiveZoom, readViewport} from './DockLayout';
import {MemStorage, SCOPE, SPECS, VP} from './testSpecs';
import {ActionRegistry} from '../../workbench/actions';
import {LifecycleTracker} from '../../workbench/lifecycle';
import {LAYOUT_ACTION_IDS, ShortcutTable} from '../actions/layoutActions';

if (typeof window !== 'undefined' && !('PointerEvent' in window)) {
  (window as unknown as {PointerEvent: unknown}).PointerEvent = class extends MouseEvent {};
}
afterEach(() => { cleanup(); document.documentElement.removeAttribute('style'); document.body.removeAttribute('style'); });

describe('N4 zoom-aware viewport', () => {
  it('effectiveZoom/readViewport divide innerWidth by html×body CSS zoom (number or %)', () => {
    expect(effectiveZoom()).toBe(1);
    document.documentElement.setAttribute('style', 'zoom: 2');
    document.body.setAttribute('style', 'zoom:125%');
    expect(effectiveZoom()).toBeCloseTo(2.5);
    expect(readViewport()).toEqual({width: Math.floor(window.innerWidth / 2.5), height: Math.floor(window.innerHeight / 2.5)});
  });
  it('a float near the lower-right is re-clamped when CSS zoom is applied and on window resize', async () => {
    render(<DockLayout specs={SPECS} scope={SCOPE} storage={new MemStorage()} renderPanel={id => <p>{id}</p>} />);
    const root = screen.getByTestId('dock-layout');
    root.getBoundingClientRect = () => ({left: 0, top: 0, width: 1024, height: 768, right: 1024, bottom: 768, x: 0, y: 0, toJSON: () => ({})});
    fireEvent.change(screen.getByLabelText('「属性」停靠位置'), {target: {value: 'float'}});
    const p0 = screen.getByTestId('panel-inspector');
    const x0 = parseFloat(p0.style.left), y0 = parseFloat(p0.style.top);
    // move it to the lower-right of the 1024×768 window but outside the edge dock zones, so it stays floating.
    fireEvent.pointerDown(screen.getByTestId('drag-inspector'), {clientX: 0, clientY: 0});
    fireEvent.pointerMove(window, {clientX: 700 - x0, clientY: 600 - y0});
    fireEvent.pointerUp(window, {clientX: 700 - x0, clientY: 600 - y0});
    const p = () => screen.getByTestId('panel-inspector');
    expect(p().dataset.dock).toBe('float');
    expect(p().style.left).toBe('700px'); expect(p().style.top).toBe('600px');
    act(() => { document.documentElement.setAttribute('style', 'zoom: 2'); });
    const w = Math.floor(window.innerWidth / 2), h = Math.floor(window.innerHeight / 2);
    await waitFor(() => expect(parseFloat(p().style.left)).toBeLessThanOrEqual(w - 48));
    expect(p().dataset.dock).toBe('float');
    expect(parseFloat(p().style.top)).toBeLessThanOrEqual(h - 48);
    // and back via a plain resize event after zoom is removed: stays inside (no jump off-screen)
    act(() => { document.documentElement.removeAttribute('style'); window.dispatchEvent(new Event('resize')); });
    await waitFor(() => expect(parseFloat(p().style.left)).toBeLessThanOrEqual(window.innerWidth - 48));
  });
});

describe('N5 visible main-panel tabs + layout.showPanel', () => {
  function setup() {
    const tracker = new LifecycleTracker(); const reg = new ActionRegistry(tracker);
    render(<DockLayout specs={SPECS} scope={SCOPE} storage={new MemStorage()} viewport={VP} actionRegistry={reg} shortcutTable={new ShortcutTable()} tracker={tracker}
      renderPanel={id => <p>{id} 内容</p>} />);
    const ctx = (input: unknown) => ({token: tracker.current(), targetId: String(input), targetVersion: null, permissions: new Set<string>(), input});
    return {reg, ctx};
  }
  it('both main panels have a tab; clicking 执行画布 brings it to front, aria-pressed follows', async () => {
    setup();
    const tabs = screen.getByTestId('uw-main-tabs');
    const exec = tabs.querySelector<HTMLButtonElement>('[data-panel-tab=exec]')!;
    const canvas = tabs.querySelector<HTMLButtonElement>('[data-panel-tab=canvas]')!;
    expect(exec.textContent).toBe('执行画布');
    if (exec.getAttribute('aria-pressed') === 'true') { fireEvent.change(screen.getByLabelText('切换中间面板'), {target: {value: 'canvas'}}); }
    expect(exec.getAttribute('aria-pressed')).toBe('false');
    expect(screen.queryByText('exec 内容')).toBeNull();
    fireEvent.click(exec);
    await waitFor(() => expect(screen.getByText('exec 内容')).toBeTruthy());
    expect(exec.getAttribute('aria-pressed')).toBe('true');
    expect(canvas.getAttribute('aria-pressed')).toBe('false');
  });
  it('layout.showPanel reopens a closed panel, rejects unknown ids with a reason', async () => {
    const {reg, ctx} = setup();
    fireEvent.click(screen.getByLabelText('关闭「任务」'));
    await waitFor(() => expect(screen.queryByTestId('panel-tasks')).toBeNull());
    expect(reg.availability(LAYOUT_ACTION_IDS.show, ctx('nope'))).toEqual({enabled: false, reason: '没有这个面板'});
    const r = await act(() => reg.execute(LAYOUT_ACTION_IDS.show, ctx('tasks')));
    expect(r.status).toBe('done');
    await waitFor(() => expect(screen.getByTestId('panel-tasks')).toBeTruthy());
  });
});
