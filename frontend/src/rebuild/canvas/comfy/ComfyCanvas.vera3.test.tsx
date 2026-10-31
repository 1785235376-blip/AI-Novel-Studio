// @vitest-environment jsdom
// [HERMIA-FE-20261031 DUALCANVAS-COMFY VERA-3] P2 菜单关闭后焦点回到「＋ 节点」；（P3 见 vera3p3.test）
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

