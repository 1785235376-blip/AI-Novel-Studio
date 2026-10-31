// @vitest-environment jsdom
// [HERMIA-FE-20261031 DUALCANVAS-COMFY VERA-3] P3 K4/K6 多结果 ↓↓↑ 与过滤重置；E5 存储标题不随 locale。
import {describe, it, expect, beforeEach, afterEach, vi} from 'vitest';
import {act, render, fireEvent, cleanup, within} from '@testing-library/react';
import {DualStack} from '../DualStack';
import {sessionCanvasStore} from '../RebuildCanvas';
import {sessionLayoutStore} from '../dualLayout';
import {sessionComfyStore} from './ComfyCanvas';
import {useStudio} from '../../../store';
import {setLocale} from '../../../i18n';

const low = () => document.querySelector('[data-canvas-layer=lower]') as HTMLElement;
const btn = () => low().querySelector('[data-comfy-add]') as HTMLButtonElement;
const menu = () => low().querySelector('[data-add-node-menu]') as HTMLElement | null;
const cb = () => within(menu()!).getByRole('combobox');
const opts = () => [...menu()!.querySelectorAll('[role=option]')];
const activeId = () => cb().getAttribute('aria-activedescendant');
beforeEach(() => { cleanup(); localStorage.clear(); sessionCanvasStore.clear(); sessionLayoutStore.clear(); useStudio.setState({novelId: 'n1', actor: undefined, scope: undefined}); });
afterEach(() => { act(() => setLocale('zh-CN')); vi.restoreAllMocks(); cleanup(); });

describe('P2 focus returns to add button', () => {
  it('after Esc', () => {
    render(<DualStack kind="image" scope="n1" />); fireEvent.click(btn());
    expect(document.activeElement).toBe(cb());
    fireEvent.keyDown(cb(), {key: 'Escape'}); expect(menu()).toBeNull();
    expect(document.activeElement).toBe(btn());
  });
  it('after Enter adds a node', () => {
    render(<DualStack kind="video" scope="n1" />); fireEvent.click(btn());
    fireEvent.change(cb(), {target: {value: 'ksampler'}}); fireEvent.keyDown(cb(), {key: 'Enter'});
    expect(menu()).toBeNull(); expect(low().querySelectorAll('[data-node-class=KSampler]').length).toBe(1);
    expect(document.activeElement).toBe(btn());
  });
});

describe('P3 K4/K6 active option with multi-result filter', () => {
  it('↓↓↑ lands on the 2nd option (not the 1st)', () => {
    render(<DualStack kind="image" scope="n1" />); fireEvent.click(btn());
    fireEvent.change(cb(), {target: {value: 'vae'}});
    const o = opts(); expect(o.length).toBeGreaterThanOrEqual(3);
    expect(activeId()).toBe(o[0].id);
    fireEvent.keyDown(cb(), {key: 'ArrowDown'}); expect(activeId()).toBe(o[1].id);
    fireEvent.keyDown(cb(), {key: 'ArrowDown'}); expect(activeId()).toBe(o[2].id);
    fireEvent.keyDown(cb(), {key: 'ArrowUp'}); expect(activeId()).toBe(o[1].id);
    expect(o[1].getAttribute('aria-selected')).toBe('true'); expect(o[0].getAttribute('aria-selected')).toBe('false');
  });
  it('changing the filter resets active to the first option', () => {
    render(<DualStack kind="image" scope="n1" />); fireEvent.click(btn());
    fireEvent.change(cb(), {target: {value: 'vae'}});
    fireEvent.keyDown(cb(), {key: 'ArrowDown'}); fireEvent.keyDown(cb(), {key: 'ArrowDown'});
    fireEvent.change(cb(), {target: {value: 'va'}});
    expect(activeId()).toBe(opts()[0].id);
  });
});

describe('P3 E5 stored title is locale-independent', () => {
  it('en: stored title is the canonical registry key (zh-CN label), shown translated', () => {
    act(() => setLocale('en'));
    const spy = vi.spyOn(sessionComfyStore, 'set');
    render(<DualStack kind="video" scope="n1" />); fireEvent.click(btn());
    fireEvent.change(cb(), {target: {value: 'ksampler'}}); fireEvent.keyDown(cb(), {key: 'Enter'});
    const last = spy.mock.calls.at(-1)![1] as {nodes: {t: string; title: string}[]};
    const n = last.nodes.find(x => x.t === 'KSampler')!;
    expect(n.title).toBe('K 采样器');
    expect(low().querySelector('[data-node-class=KSampler]')!.textContent).not.toMatch(/[\u4e00-\u9fff]/);
  });
});
