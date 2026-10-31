// @vitest-environment jsdom
// [HERMIA-FE-20261031 DUALCANVAS-COMFY P2-1] en 下双画布（顶栏、分隔条 aria、下画布 label/aria、已选、接入确认对话框）不显示汉字。
import {act, cleanup, fireEvent, render, within} from '@testing-library/react';
import {afterEach, beforeEach, describe, expect, it, vi} from 'vitest';
import {setLocale} from '../../i18n';
import {DualStack} from './DualStack';
import {sessionCanvasStore} from './RebuildCanvas';
import {sessionLayoutStore} from './dualLayout';
import {useStudio} from '../../store';

const HAN = /[\u4e00-\u9fff]/;
const ATTRS = ['aria-label', 'title', 'placeholder', 'aria-valuetext'];
function chinese(root: Element): string[] {
  const out: string[] = [];
  const walk = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  for (let n = walk.nextNode(); n; n = walk.nextNode()) if (HAN.test(n.textContent || '')) out.push(`text: ${n.textContent}`);
  root.querySelectorAll('*').forEach(el => { for (const a of ATTRS) { const v = el.getAttribute(a); if (v && HAN.test(v)) out.push(`${a}: ${v}`); } });
  return out;
}
const low = () => document.querySelector('[data-canvas-layer=lower]') as HTMLElement;
const add = (type: string) => {
  fireEvent.contextMenu(within(low()).getByRole('application'), {clientX: 50, clientY: 50});
  fireEvent.click(low().querySelector(`[data-add-node-menu] [data-node-type=${type}]`)!);
};
beforeEach(() => { cleanup(); localStorage.clear(); sessionCanvasStore.clear(); sessionLayoutStore.clear(); vi.stubGlobal('PointerEvent', MouseEvent);
  useStudio.setState({novelId: 'n1', actor: undefined, scope: undefined}); act(() => setLocale('en')); });
afterEach(() => { act(() => setLocale('zh-CN')); cleanup(); vi.unstubAllGlobals(); });

describe.each(['image', 'video'] as const)('DualStack en (%s)', kind => {
  it('chrome, splitter, lower label/aria and empty hint have no Chinese', () => {
    render(<DualStack kind={kind} scope="n1" />);
    const sec = document.querySelector('[data-dual-stack]')!;
    // upper RebuildCanvas content is covered by RebuildCanvas.en.test; here: everything DualStack owns + lower canvas
    const own = [...sec.querySelectorAll('.dstk__bar, .dstk__panehead, .dstk__split, [data-canvas-layer=lower]')];
    expect(sec.getAttribute('aria-label')).not.toMatch(HAN);
    expect(own.flatMap(chinese)).toEqual([]);
    expect(chinese(document.querySelector('[data-canvas-layer=upper] .rcv-label')!.parentElement!.querySelector('[role=application]')!.parentElement!.querySelector('.rcv-label')!)).toEqual([]);
    expect(document.querySelector('[data-canvas-layer=upper] [role=application]')!.getAttribute('aria-label')).not.toMatch(HAN);
  });
  it('splitter aria-label / aria-valuetext are the en strings (VERA-3 E2/E6)', () => {
    render(<DualStack kind={kind} scope="n1" />);
    const sp = document.querySelector('[data-dual-splitter]')!;
    expect(sp.getAttribute('aria-label')).toBe('Resize canvases (arrows / PageUp / PageDown / Home / End, Enter resets)');
    expect(sp.getAttribute('aria-valuetext')).toBe(`top ${sp.getAttribute('aria-valuenow')}%`);
  });
  it('selected node (new default title shown translated), feed hint and confirm dialog have no Chinese', () => {
    render(<DualStack kind={kind} scope="n1" />);
    add('KSampler');
    expect(chinese(low())).toEqual([]);
    expect(low().querySelector('.dstk__lowbar')!.textContent).toContain('KSampler');
    add(kind === 'image' ? 'image_reference' : 'director_note');
    fireEvent.click(low().querySelector('[data-feed-upper]')!);
    const dlg = document.querySelector('[role=dialog], [role=alertdialog]')!;
    expect(dlg).toBeTruthy(); expect(chinese(dlg)).toEqual([]); expect(chinese(low())).toEqual([]);
    fireEvent.click(document.querySelector('[data-feed-confirm]')!);
    expect(chinese(low())).toEqual([]);
  });
});
