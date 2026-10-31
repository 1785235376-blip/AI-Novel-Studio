// @vitest-environment jsdom
// [HERMIA-FE-20261031 DUALCANVAS-COMFY P3] 「接入上画布」按钮 disabled={!feedable}：选中非 PoemSeed 节点必须禁用（杀死 `!picked` 变异）；节点数锁定。
import {describe, it, expect, beforeEach, afterEach} from 'vitest';
import {render, fireEvent, cleanup, within} from '@testing-library/react';
import {DualStack} from './DualStack';
import {sessionCanvasStore} from './RebuildCanvas';
import {sessionLayoutStore} from './dualLayout';
import {defaultRegistry, NODE_GROUPS} from './comfy/comfyRegistry';
import {useStudio} from '../../store';

const low = () => document.querySelector('[data-canvas-layer=lower]') as HTMLElement;
const add = (type: string) => {
  fireEvent.contextMenu(within(low()).getByRole('application'), {clientX: 50, clientY: 50});
  fireEvent.click(low().querySelector(`[data-add-node-menu] [data-node-type=${type}]`)!);
};
const btn = () => low().querySelector('[data-feed-upper]') as HTMLButtonElement;
beforeEach(() => { cleanup(); localStorage.clear(); sessionCanvasStore.clear(); sessionLayoutStore.clear(); useStudio.setState({novelId: 'n1', actor: undefined, scope: undefined}); });
afterEach(() => cleanup());

describe('feed button follows feedable, not just picked', () => {
  it.each(['image', 'video'] as const)('%s: nothing picked → disabled; ComfyUI node picked → still disabled; PoemSeed node → enabled', kind => {
    render(<DualStack kind={kind} scope="n1" />);
    expect(btn().disabled).toBe(true);
    add('KSampler');
    expect(low().querySelector('.dstk__lowbar b')).not.toBeNull(); // a node IS picked
    expect(btn().disabled).toBe(true);
    add(kind === 'image' ? 'image_reference' : 'director_note');
    expect(btn().disabled).toBe(false);
  });
});
describe('node library size lock', () => {
  it('IMAGE 53, VIDEO 52, 11 categories', () => {
    expect(defaultRegistry('image').defs.length).toBe(53);
    expect(defaultRegistry('video').defs.length).toBe(52);
    // 11 populated categories; NODE_GROUPS also declares the 'other' bucket for unknown /object_info categories (empty by default)
    expect(NODE_GROUPS.length).toBe(12); expect(NODE_GROUPS[NODE_GROUPS.length - 1]).toBe('other');
    for (const k of ['image', 'video'] as const) expect(new Set(defaultRegistry(k).defs.map(d => d.group)).size).toBe(11);
  });
});
