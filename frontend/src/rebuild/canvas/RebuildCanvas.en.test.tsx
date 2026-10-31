// @vitest-environment jsdom
/** [HERMIA-FE-20261031 VERA-EN] en 下 RebuildCanvas（含「所选图片节点参数」面板、端口、菜单、状态行）不显示中文。 */
import {act, cleanup, fireEvent, render} from '@testing-library/react';
import {afterEach, beforeEach, expect, it, vi} from 'vitest';
import {setLocale} from '../../i18n';
import {RebuildCanvas, type CvGraph} from './RebuildCanvas';

const HAN = /[\u4e00-\u9fff]/;
function chinese(root: HTMLElement): string[] {
  const out: string[] = [];
  if (HAN.test(root.textContent || '')) out.push(`text: ${root.textContent}`);
  root.querySelectorAll('*').forEach(el => { for (const a of ['aria-label', 'title', 'placeholder']) { const v = el.getAttribute(a); if (v && HAN.test(v)) out.push(`${a}: ${v}`); } });
  return out;
}
function select(id: string) {
  const node = document.querySelector(`[data-node-id="${id}"]`)!;
  fireEvent.pointerDown(node, {button: 0, pointerId: 1, clientX: 40, clientY: 40});
  fireEvent.pointerUp(node, {button: 0, pointerId: 1, clientX: 40, clientY: 40});
}
const graph = (t: string): CvGraph => ({nodes: [{id: 'n1', t: t as CvGraph['nodes'][number]['t'], x: 0, y: 0, title: t === 'image_generate' ? '新生成图片' : '新生成视频', prompt: 'a lighthouse'}], edges: []});
beforeEach(() => { localStorage.clear(); vi.stubGlobal('PointerEvent', MouseEvent); act(() => setLocale('en')); });
afterEach(() => { act(() => setLocale('zh-CN')); cleanup(); vi.unstubAllGlobals(); });

it('image canvas with selected image node parameters panel shows no Chinese in en', () => {
  const {container} = render(<RebuildCanvas kind="image" scope="en-a" seed={graph('image_generate')} onImageTaskIntent={() => {}} />);
  select('n1');
  expect(container.querySelector('[aria-label="Selected image node parameters"]')).toBeTruthy();
  expect(chinese(container)).toEqual([]);
});
it('image panel without task entry, empty canvas and context menu show no Chinese in en', () => {
  const a = render(<RebuildCanvas kind="image" scope="en-b" seed={graph('image_generate')} />);
  select('n1');
  expect(chinese(a.container)).toEqual([]);
  a.unmount();
  const b = render(<RebuildCanvas kind="image" scope="en-c" seed={{nodes: [], edges: []}} />);
  fireEvent.contextMenu(b.container.querySelector('svg')!, {clientX: 50, clientY: 50});
  expect(chinese(b.container)).toEqual([]);
});
it('video canvas unsupported notices show no Chinese in en', () => {
  const {container} = render(<RebuildCanvas kind="video" scope="en-d" seed={graph('video_generate')} />);
  select('n1');
  expect(chinese(container)).toEqual([]);
});
// [HERMIA-FE-20261031 VERA-P2] caller-supplied zh canvas labels render English in en.
it.each([['图片画布', 'Image canvas'], ['视频画布', 'Video canvas'], ['创作画布', 'Creation canvas'], ['执行画布', 'Execution canvas']])('label %s shows %s in en', (zh, en) => {
  const {container} = render(<RebuildCanvas kind="image" scope={`en-l-${zh}`} label={zh} seed={{nodes: [], edges: []}} />);
  expect(container.querySelector('.rcv-label')?.textContent).toBe(en);
  expect(chinese(container)).toEqual([]);
});
