// @vitest-environment jsdom
// [HERMIA-FE-20261031 DUALCANVAS-COMFY] 下画布节点库：分类可搜索菜单；类型不匹配的端口不能连线；不伪装执行。
import {describe, it, expect, beforeEach, afterEach} from 'vitest';
import {render, fireEvent, cleanup, within} from '@testing-library/react';
import {DualStack} from '../DualStack';
import {sessionCanvasStore} from '../RebuildCanvas';
import {sessionLayoutStore} from '../dualLayout';
import {useStudio} from '../../../store';

const low = () => document.querySelector('[data-canvas-layer=lower]') as HTMLElement;
const add = (type: string) => {
  fireEvent.contextMenu(within(low()).getByRole('application'), {clientX: 50, clientY: 50});
  fireEvent.click(low().querySelector(`[data-add-node-menu] [data-node-type=${type}]`)!);
};
beforeEach(() => { cleanup(); localStorage.clear(); sessionCanvasStore.clear(); sessionLayoutStore.clear(); useStudio.setState({novelId: 'n1', actor: undefined, scope: undefined}); });
afterEach(() => cleanup());

describe('ComfyCanvas', () => {
  it('status never claims execution', () => {
    render(<DualStack kind="video" scope="n1" />);
    expect(low().querySelector('[data-comfy-status]')!.textContent).toContain('不会执行');
    expect(low().textContent).not.toMatch(/已连接 ComfyUI|运行中|排队|¥|\$/);
  });
  it('menu is grouped by ComfyUI categories and searchable', () => {
    render(<DualStack kind="video" scope="n1" />);
    fireEvent.contextMenu(within(low()).getByRole('application'), {clientX: 10, clientY: 10});
    const menu = low().querySelector('[data-add-node-menu]') as HTMLElement;
    expect(menu.querySelectorAll('[data-node-type]').length).toBeGreaterThan(40);
    for (const t of ['KSampler', 'CheckpointLoaderSimple', 'ControlNetApply', 'SaveVideo', 'director_note']) expect(menu.querySelector(`[data-node-type=${t}]`)).not.toBeNull();
    fireEvent.change(within(menu).getByRole('searchbox'), {target: {value: 'ksampler'}});
    expect(menu.querySelector('[data-node-type=KSampler]')).not.toBeNull(); expect(menu.querySelector('[data-node-type=VAELoader]')).toBeNull();
  });
  it('compatible types link, mismatched types are refused', () => {
    render(<DualStack kind="image" scope="n1" />);
    add('CheckpointLoaderSimple'); add('KSampler'); add('CLIPTextEncode');
    const ids = [...low().querySelectorAll('[data-node-id]')].map(n => n.getAttribute('data-node-id')!);
    const [ck, ks] = ids;
    const drag = (from: string, to: string) => {
      fireEvent.pointerDown(low().querySelector(`[data-out="${from}"]`)!, {clientX: 1, clientY: 1});
      fireEvent.pointerUp(low().querySelector(`[data-in="${to}"]`)!, {clientX: 2, clientY: 2});
    };
    const status = () => low().querySelector('[data-comfy-status]')!.textContent!;
    drag(`${ck}:1`, `${ks}:0`); // CLIP → MODEL : refused
    const edges = () => low().querySelectorAll('.cfy-edge').length;
    expect(edges()).toBe(0); expect(status()).toContain('类型不匹配');
    drag(`${ck}:0`, `${ks}:0`); // MODEL → MODEL
    expect(edges()).toBe(1); expect(low().querySelector('.cfy-edge')!.getAttribute('data-edge-type')).toBe('MODEL');
  });
});
