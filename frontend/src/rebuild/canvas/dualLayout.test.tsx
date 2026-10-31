// @vitest-environment jsdom
// [HERMIA-FE-20261031 DUALCANVAS-COMFY] 上下画布布局：分隔条键盘/最大化/互换；按身份记忆，无身份仅本次会话；互换只改位置不改语义。
import {describe, it, expect, beforeEach, afterEach} from 'vitest';
import {render, fireEvent, cleanup, within} from '@testing-library/react';
import {DualStack} from './DualStack';
import {sessionCanvasStore} from './RebuildCanvas';
import {DEFAULT_LAYOUT, RATIO_MAX, RATIO_MIN, LAYOUT_KEY_PREFIX, clampRatio, splitterKey, toggleMax, toggleSwap, topShare, withTopShare, sanitizeLayout, layoutStore, readLayout, writeLayout, sessionLayoutStore} from './dualLayout';
import {resolveWorkspaceIdentity} from '../../workspace/state/scopeLease';
import {useStudio} from '../../store';

const COLLAB = {workspaceId: 'ws1', projectId: 'n1', storylineId: 's1', branchId: 'b1'};
const q = (s: string) => document.querySelector(s) as HTMLElement;
beforeEach(() => { cleanup(); localStorage.clear(); sessionCanvasStore.clear(); sessionLayoutStore.clear(); useStudio.setState({novelId: 'n1', actor: undefined, scope: undefined}); });
afterEach(() => { cleanup(); useStudio.setState({actor: undefined, scope: undefined}); });

describe('dualLayout (pure)', () => {
  it('clamps ratio and survives garbage', () => {
    expect(clampRatio(5)).toBe(RATIO_MAX); expect(clampRatio(-1)).toBe(RATIO_MIN); expect(clampRatio(Number.NaN)).toBe(DEFAULT_LAYOUT.ratio);
    expect(sanitizeLayout({ratio: 'x', swapped: 1, max: 'evil'})).toEqual(DEFAULT_LAYOUT);
    expect(sanitizeLayout({ratio: 0.3, swapped: true, max: 'lower'})).toEqual({ratio: 0.3, swapped: true, max: 'lower'});
  });
  it('splitter keys move the visual top pane, also when swapped', () => {
    const d = splitterKey(DEFAULT_LAYOUT, 'ArrowDown')!; expect(topShare(d)).toBeCloseTo(0.65);
    const s = toggleSwap(DEFAULT_LAYOUT); expect(topShare(s)).toBeCloseTo(0.4);
    expect(topShare(splitterKey(s, 'ArrowDown')!)).toBeCloseTo(0.45);
    expect(topShare(splitterKey(DEFAULT_LAYOUT, 'End')!)).toBe(RATIO_MAX);
    expect(splitterKey(DEFAULT_LAYOUT, 'Enter')!.ratio).toBe(DEFAULT_LAYOUT.ratio);
    expect(splitterKey(DEFAULT_LAYOUT, 'a')).toBeNull();
    expect(withTopShare(s, 0.7).ratio).toBeCloseTo(0.3);
  });
  it('swap keeps sizes with the canvas; max toggles', () => {
    const s = toggleSwap({...DEFAULT_LAYOUT, ratio: 0.7}); expect(s.ratio).toBe(0.7); expect(toggleSwap(s).swapped).toBe(false);
    expect(toggleMax(DEFAULT_LAYOUT, 'upper').max).toBe('upper'); expect(toggleMax(toggleMax(DEFAULT_LAYOUT, 'upper'), 'upper').max).toBe('none');
  });
  it('store: real identity → localStorage per user/project; none → session only', () => {
    const real = layoutStore('video', resolveWorkspaceIdentity({actorId: 'actor-1', collabScope: COLLAB, projectId: 'n1'}));
    expect(real.persist).toBe('local'); expect(real.key.startsWith(LAYOUT_KEY_PREFIX)).toBe(true); expect(real.key).toContain('actor-1');
    writeLayout(real, {ratio: 0.3, swapped: true, max: 'none'}); expect(readLayout(real)).toEqual({ratio: 0.3, swapped: true, max: 'none'});
    const other = layoutStore('video', resolveWorkspaceIdentity({actorId: 'actor-2', collabScope: COLLAB, projectId: 'n1'}));
    expect(readLayout(other)).toEqual(DEFAULT_LAYOUT);
    const ses = layoutStore('video', resolveWorkspaceIdentity({actorId: undefined, collabScope: null, projectId: 'n1'}));
    expect(ses.persist).toBe('session'); writeLayout(ses, {...DEFAULT_LAYOUT, swapped: true});
    expect(Object.keys(localStorage).filter(k => k.startsWith(LAYOUT_KEY_PREFIX) && !k.includes('actor'))).toHaveLength(0);
    expect(readLayout(ses).swapped).toBe(true);
  });
});

describe('DualStack layout UI', () => {
  it('splitter is an ARIA separator driven by keyboard', () => {
    render(<DualStack kind="video" scope="n1" />);
    const sp = q('[data-dual-splitter]');
    expect(sp.getAttribute('role')).toBe('separator'); expect(sp.getAttribute('aria-valuenow')).toBe('60');
    fireEvent.keyDown(sp, {key: 'ArrowDown'}); expect(sp.getAttribute('aria-valuenow')).toBe('65');
    fireEvent.keyDown(sp, {key: 'Home'}); expect(sp.getAttribute('aria-valuenow')).toBe(String(RATIO_MIN * 100));
  });
  it('maximize hides the other pane and restore brings it back', () => {
    render(<DualStack kind="image" scope="n1" />);
    fireEvent.click(q('[data-pane-max=lower]'));
    expect(q('[data-canvas-layer=upper]').hidden).toBe(true); expect(q('[data-dual-splitter]')).toBeNull();
    fireEvent.click(q('[data-pane-max=lower]'));
    expect(q('[data-canvas-layer=upper]').hidden).toBe(false); expect(q('[data-canvas-layer=lower]').hidden).toBe(false);
  });
  it('swap only changes visual order; layers keep their semantics', () => {
    render(<DualStack kind="video" scope="n1" />);
    fireEvent.click(q('[data-pane-swap]'));
    const up = q('[data-canvas-layer=upper]'), low = q('[data-canvas-layer=lower]');
    expect(Number(low.style.order)).toBeLessThan(Number(up.style.order));
    expect(within(low).getByRole('application')).toBeTruthy();
    expect(low.querySelector('[data-comfy-status]')).not.toBeNull(); expect(up.querySelector('[data-comfy-status]')).toBeNull();
  });
  it('no identity → layout chip says session only and nothing written to localStorage', () => {
    render(<DualStack kind="video" scope="n1" />);
    expect(q('[data-layout-identity]').getAttribute('data-layout-identity')).toBe('session');
    expect(q('[data-layout-identity]').textContent).toContain('仅本次会话');
    fireEvent.click(q('[data-pane-swap]'));
    expect(Object.keys(localStorage).filter(k => k.startsWith(LAYOUT_KEY_PREFIX))).toHaveLength(0);
    cleanup(); render(<DualStack kind="video" scope="n1" />);
    expect(q('[data-pane-swap]').getAttribute('aria-pressed')).toBe('true');
  });
});
