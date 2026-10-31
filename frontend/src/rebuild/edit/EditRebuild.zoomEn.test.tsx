// @vitest-environment jsdom
/** [HERMIA-FE-20261031 VERA-P3 zoom] 剪辑页缩放按钮用固定键：en = Zoom out / Zoom in（不得撞 Upscale）；zh 不变。 */
import {cleanup, render} from '@testing-library/react';
import {act} from 'react';
import {afterEach, expect, it} from 'vitest';
import {setLocale} from '../../i18n';
import {EditRebuild} from './EditRebuild';
afterEach(() => { act(() => setLocale('zh-CN')); cleanup(); });
const labels = (c: HTMLElement) => ['#nleZoomOut', '#nleZoomIn'].map(s => c.querySelector(s)?.getAttribute('aria-label'));
it.each([['en', ['Zoom out', 'Zoom in']], ['zh-CN', ['缩小', '放大']]] as const)('%s zoom aria-labels', (loc, want) => {
  act(() => setLocale(loc));
  const {container} = render(<EditRebuild novelId="n1" shellMode="pro" editable={false} handoffs={[]} onBackToVideo={() => {}} />);
  expect(labels(container)).toEqual(want);
});
