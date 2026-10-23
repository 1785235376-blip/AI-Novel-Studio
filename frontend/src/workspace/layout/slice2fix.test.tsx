// @vitest-environment jsdom
// [HERMIA-FE-20261023 M1-s2fix] Vera M1-s2 MUST-FIX 1–4 + nice-to-haves.
import {act, cleanup, fireEvent, render, screen, waitFor} from '@testing-library/react';
import {afterEach, describe, expect, it} from 'vitest';
import {DockLayout} from './DockLayout';
import {emptyZoneBox} from './model';
import {MemStorage, SCOPE, SPECS} from './testSpecs';
import {displayShortcut} from '../actions/layoutActions';
import {UnifiedWorkspacePreview} from '../UnifiedWorkspacePreview';
import {QueryClient, QueryClientProvider} from '@tanstack/react-query';
// [HERMIA-FE-20261023 M1-s3] preview now hosts real react-query panels → wrap in a provider (same as main.tsx). Assertions unchanged.
const withQc = (n: JSX.Element) => <QueryClientProvider client={new QueryClient({defaultOptions: {queries: {retry: false}}})}>{n}</QueryClientProvider>;

afterEach(() => { cleanup(); localStorage.clear(); });
if (typeof window !== 'undefined' && !('PointerEvent' in window)) {
  (window as unknown as {PointerEvent: unknown}).PointerEvent = class extends MouseEvent {};
}
const rect = (left: number, top: number, width: number, height: number) =>
  ({left, top, width, height, right: left + width, bottom: top + height, x: left, y: top, toJSON: () => ({})}) as DOMRect;
const flush = () => act(async () => {});
function setup(storage = new MemStorage()) {
  render(<DockLayout specs={SPECS} scope={SCOPE} storage={storage} viewport={{width: 1366, height: 768}}
    renderPanel={id => id === 'inspector' ? <textarea aria-label="草稿" /> : <p>{id} 内容</p>} />);
  screen.getByTestId('dock-layout').getBoundingClientRect = () => rect(0, 0, 1366, 768);
  return {storage};
}
const dockOf = (id: string) => screen.getByTestId(`panel-${id}`).dataset.dock;

describe('MUST-FIX 1: empty dock zone has its own drop box (never the root)', () => {
  it('emptyZoneBox matches the hit regions and is never the whole root', () => {
    const r = {width: 1366, height: 768};
    expect(emptyZoneBox('right', r, 34)).toEqual({left: 1366 - 273, top: 34, width: 273, height: 734});
    expect(emptyZoneBox('left', r, 34)).toEqual({left: 0, top: 34, width: 273, height: 734});
    expect(emptyZoneBox('bottom', r, 34)).toEqual({left: 273, top: 576, width: 820, height: 192});
    expect(emptyZoneBox('main', r)).toBeNull();
  });
  it('dragging to an empty right zone: indicator limited to the right strip, ghost boxes present, drop works', async () => {
    setup(); await flush();
    // empty the right zone: move inspector to bottom via its dock select
    fireEvent.change(screen.getByLabelText('「属性」停靠位置'), {target: {value: 'bottom'}});
    expect(document.querySelectorAll('section[data-dock="right"]').length).toBe(0);
    fireEvent.pointerDown(screen.getByTestId('drag-outline'), {clientX: 50, clientY: 100});
    fireEvent.pointerMove(window, {clientX: 1300, clientY: 300});
    const ind = screen.getByTestId('drop-indicator');
    expect(ind.dataset.zone).toBe('right'); expect(ind.dataset.allowed).toBe('true');
    expect(ind.className).toContain('uw-drop-indicator--zone');
    const w = parseFloat(ind.style.width), l = parseFloat(ind.style.left);
    expect(w).toBeGreaterThan(0); expect(w).toBeLessThan(1366 / 2); expect(l).toBeGreaterThan(1366 / 2);
    expect(!(l === 0 && w === 1366)).toBe(true);
    expect(screen.getByTestId('zone-ghost-right').dataset.zoneBox).toBe('right');
    fireEvent.pointerUp(window, {clientX: 1300, clientY: 300});
    expect(dockOf('outline')).toBe('right');
    expect(screen.queryByTestId('zone-ghost-right')).toBeNull();
  });
  it('non-empty side columns expose data-zone-box too', async () => {
    setup(); await flush();
    for (const z of ['left', 'right', 'bottom', 'main']) expect(document.querySelector(`[data-zone-box="${z}"]:not([data-zone-ghost])`)).not.toBeNull();
  });
  it('translucent zone overlay (no opaque fill) — css rule present', async () => {
    const css = (await import('node:fs')).readFileSync(process.cwd() + '/src/workspace/layout/DockLayout.css', 'utf8');
    expect(css).toMatch(/\.uw-drop-indicator--zone\{background:color-mix\(in srgb,var\(--color-accent-primary\) 14%,transparent\)\}/);
  });
});

describe('MUST-FIX 2: Esc cancels a drag', () => {
  it('docked panel: Esc then release → no drop, indicator gone', async () => {
    setup(); await flush();
    fireEvent.pointerDown(screen.getByTestId('drag-tasks'), {clientX: 600, clientY: 740});
    fireEvent.pointerMove(window, {clientX: 30, clientY: 300});
    expect(screen.getByTestId('drop-indicator').dataset.zone).toBe('left');
    fireEvent.keyDown(window, {key: 'Escape'});
    expect(screen.queryByTestId('drop-indicator')).toBeNull();
    fireEvent.pointerUp(window, {clientX: 30, clientY: 300});
    expect(dockOf('tasks')).toBe('bottom');
  });
  it('floating panel: Esc returns it to its origin', async () => {
    setup(); await flush();
    fireEvent.change(screen.getByLabelText('「属性」停靠位置'), {target: {value: 'float'}});
    const el = screen.getByTestId('panel-inspector'); const ox = el.style.left, oy = el.style.top;
    fireEvent.pointerDown(screen.getByTestId('drag-inspector'), {clientX: 500, clientY: 300});
    fireEvent.pointerMove(window, {clientX: 560, clientY: 350});
    expect(screen.getByTestId('panel-inspector').style.left).not.toBe(ox);
    fireEvent.keyDown(window, {key: 'Escape'});
    fireEvent.pointerUp(window, {clientX: 560, clientY: 350});
    expect(screen.getByTestId('panel-inspector').style.left).toBe(ox);
    expect(screen.getByTestId('panel-inspector').style.top).toBe(oy);
    expect(dockOf('inspector')).toBe('float');
  });
});

describe('nice-to-have: floating panel can be dragged back into a dock zone', () => {
  it('release over the right edge docks it; centre keeps it floating', async () => {
    setup(); await flush();
    fireEvent.change(screen.getByLabelText('「属性」停靠位置'), {target: {value: 'float'}});
    fireEvent.pointerDown(screen.getByTestId('drag-inspector'), {clientX: 600, clientY: 300});
    fireEvent.pointerMove(window, {clientX: 650, clientY: 320});
    expect(screen.queryByTestId('drop-indicator')).toBeNull();
    fireEvent.pointerUp(window, {clientX: 650, clientY: 320});
    expect(dockOf('inspector')).toBe('float');
    fireEvent.pointerDown(screen.getByTestId('drag-inspector'), {clientX: 600, clientY: 300});
    fireEvent.pointerMove(window, {clientX: 1320, clientY: 300});
    expect(screen.getByTestId('drop-indicator').dataset.zone).toBe('right');
    fireEvent.pointerUp(window, {clientX: 1320, clientY: 300});
    expect(dockOf('inspector')).toBe('right');
  });
});

describe('MUST-FIX 3: reset disabled when already default', () => {
  it('default → disabled with 「已经是默认布局」; after a change → enabled; after reset → disabled again', async () => {
    setup(); await flush();
    const btn = () => document.querySelector<HTMLButtonElement>('[data-action-id="layout.reset"]')!;
    expect(btn().disabled).toBe(true); expect(btn().title).toBe('已经是默认布局');
    expect(screen.getByTestId('reset-reason').textContent).toBe('已经是默认布局');
    fireEvent.change(screen.getByLabelText('分屏方式'), {target: {value: 'split-h'}});
    await waitFor(() => expect(btn().disabled).toBe(false));
    fireEvent.click(btn());
    fireEvent.click(await screen.findByText('恢复默认'));
    await waitFor(() => expect(btn().disabled).toBe(true));
  });
  it('focus alone does not count as a layout change', async () => {
    setup(); await flush();
    fireEvent.focus(screen.getByTestId('panel-tasks'));
    expect(document.querySelector<HTMLButtonElement>('[data-action-id="layout.reset"]')!.disabled).toBe(true);
  });
});

describe('MUST-FIX 4: ?uw=1 preview — Ctrl+K command palette lists and runs layout actions', () => {
  it('Ctrl+K opens the shared registry palette with the 4 layout actions; running split works', async () => {
    render(withQc(<UnifiedWorkspacePreview />)); await flush();
    fireEvent.keyDown(window, {key: 'k', ctrlKey: true});
    const overlay = await screen.findByTestId('command-search-overlay');
    for (const id of ['layout.reset', 'layout.reopenPanel', 'layout.toggleCollapse', 'layout.switchSplit'])
      expect(overlay.querySelector(`[data-action-id="${id}"]`)).not.toBeNull();
    fireEvent.click(overlay.querySelector<HTMLElement>('[data-action-id="layout.switchSplit"]')!);
    await waitFor(() => expect(screen.getByTestId('main-zone').dataset.split).toBe('split-h'));
    await waitFor(() => expect(screen.queryByTestId('command-search-overlay')).toBeNull(), {timeout: 2000});
  });
  it('a disabled action from the palette reports its Chinese reason and changes nothing', async () => {
    render(withQc(<UnifiedWorkspacePreview />)); await flush();
    fireEvent.keyDown(window, {key: 'k', metaKey: true});
    const overlay = await screen.findByTestId('command-search-overlay');
    fireEvent.click(overlay.querySelector<HTMLElement>('[data-action-id="layout.reset"]')!);
    expect(await screen.findByText('无法执行：已经是默认布局')).toBeTruthy();
    expect(screen.queryByText(/只恢复面板位置/)).toBeNull();
  });
});

describe('nice-to-have: double-trigger guard + visible busy; shortcut text localized', () => {
  it('two real key presses ~50ms apart execute once; aria-busy visible meanwhile', async () => {
    setup(); await flush();
    fireEvent.keyDown(window, {key: 's', code: 'KeyS', ctrlKey: true, altKey: true});
    await act(async () => { await new Promise(r => setTimeout(r, 50)); });
    expect(screen.getByLabelText('分屏方式').getAttribute('aria-busy')).toBe('true');
    fireEvent.keyDown(window, {key: 's', code: 'KeyS', ctrlKey: true, altKey: true});
    expect(screen.getByTestId('main-zone').dataset.split).toBe('split-h');
    await act(async () => { await new Promise(r => setTimeout(r, 350)); });
    expect(screen.getByLabelText('分屏方式').getAttribute('aria-busy')).toBeNull();
    fireEvent.keyDown(window, {key: 's', code: 'KeyS', ctrlKey: true, altKey: true});
    expect(screen.getByTestId('main-zone').dataset.split).toBe('split-v');
  });
  it('displayShortcut', () => {
    expect(displayShortcut('Mod+Alt+S', false)).toBe('Ctrl+Alt+S');
    expect(displayShortcut('mod+alt+0', true)).toBe('⌘⌥0');
  });
});
