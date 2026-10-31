// @vitest-environment jsdom
// [HERMIA-FE-20261030 B4] 英文界面下剪辑页主表面（监视器 / 工具条 / 检视器 / 媒体池 / 轨道头）不再残留中文。
import {afterEach, expect, it} from 'vitest';
import {act} from 'react';
import {createRoot, type Root} from 'react-dom/client';
import {EditRebuild} from './EditRebuild';
import {setLocale} from '../../i18n';

(globalThis as {IS_REACT_ACT_ENVIRONMENT?: boolean}).IS_REACT_ACT_ENVIRONMENT = true;
let host: HTMLDivElement; let root: Root;
afterEach(() => { act(() => root?.unmount()); host?.remove(); act(() => setLocale('zh-CN')); });
const CJK = /[\u4e00-\u9fff]/;
function cjkLeft(el: HTMLElement): string[] {
  const out = new Set<string>(); const w = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
  for (let n = w.nextNode(); n; n = w.nextNode()) if (CJK.test(n.textContent!)) out.add(n.textContent!.trim());
  el.querySelectorAll('[aria-label],[title]').forEach(e => ['aria-label', 'title'].forEach(a => { const v = e.getAttribute(a); if (v && CJK.test(v)) out.add(`@${a}:${v}`); }));
  return [...out];
}
for (const mode of ['basic', 'pro'] as const) it(`en ${mode}: edit timeline surface has no Chinese left`, () => {
  act(() => setLocale('en'));
  host = document.createElement('div'); document.body.append(host); root = createRoot(host);
  act(() => root.render(<EditRebuild novelId="n1" shellMode={mode} editable={false} handoffs={[]} onBackToVideo={() => {}} />));
  const surface = [...host.querySelectorAll<HTMLElement>('.nle-mons, .nle-tl, .nle-insp, #nleBin')];
  expect(surface.length).toBeGreaterThanOrEqual(4);
  expect(surface.flatMap(cjkLeft)).toEqual([]);
});
