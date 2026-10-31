// @vitest-environment jsdom
/** [HERMIA-FE-20261031 VERA-P3 zoom] 时间轴标尺缩放按钮用固定键：en 为 Zoom out / Zoom in（不得撞 Upscale）；zh 不变。 */
import { act, cleanup, render } from '@testing-library/react';
import { afterEach, expect, it } from 'vitest';
import { setLocale } from '../i18n';
import { TimelineRulerPanel } from './TimelineRulerPanel';
afterEach(() => { act(() => setLocale('zh-CN')); cleanup(); });
it.each([['en', ['Zoom out', 'Zoom in']], ['zh-CN', ['缩小', '放大']]] as const)('%s ruler zoom buttons', (loc, want) => {
  act(() => setLocale(loc));
  const { container } = render(<TimelineRulerPanel timebase={{ durationMs: 10000, fps: 25 }} view={{ startMs: 0, scale: 0.5 }} playheadMs={0}
    marks={{ inMs: null, outMs: null }} editable onPlayhead={() => {}} onView={() => {}} />);
  expect([...container.querySelectorAll('.nle-ruler__bar button')].slice(0, 2).map(b => b.textContent)).toEqual(want);
});
