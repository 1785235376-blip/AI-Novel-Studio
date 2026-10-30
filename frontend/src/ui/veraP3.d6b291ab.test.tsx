// @vitest-environment jsdom
// [HERMIA-FE-20261030 VERA-P3] Vera d6b291ab 复审 P3：参考叠看 aria-pressed、原始 id 判定过宽、英文缺词、引导关闭焦点兜底
import {act} from 'react';
import {createRoot, type Root} from 'react-dom/client';
import {afterEach, describe, expect, it, vi} from 'vitest';
import {render, cleanup} from '@testing-library/react';
import {looksLikeRawId} from './AppShell';
import {translateZh} from '../i18n';
import {ImageRebuild} from '../rebuild/image/ImageRebuild';
import {OnboardingTour, useOnboarding} from './onboarding/OnboardingTour';
import {__resetOnboarding} from './onboarding/onboarding';

(globalThis as {IS_REACT_ACT_ENVIRONMENT?: boolean}).IS_REACT_ACT_ENVIRONMENT = true;
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.useRealTimers(); });

describe('looksLikeRawId (M4 narrowed)', () => {
  it('keeps real human names', () => {
    for (const n of ['Ann-Marie', 'li_wei', 'Jo-Ann', 'mei_lin', 'Kim-Lee', '王小明']) expect(looksLikeRawId(n), n).toBe(false);
  });
  it('still hides opaque ids', () => {
    for (const n of ['', 'u-a', 'u-m5', 'ab-12', 'usr_7', 'user42', 'actor-3', '0f8fad5b-d9cb-469f-a165-70867728950e']) expect(looksLikeRawId(n), n).toBe(true);
  });
});

describe('EN entries for M2/M3 copy and IMAGE sidebar', () => {
  it('translates every string', () => {
    for (const s of ['三步做视频', '① 列出镜头', '② 在画布上摆参考', '③ 看导演建议', '先选一张图片，才能叠看参考', '图片生成', '参考叠看 开', '参考叠看 关']) {
      const out = translateZh('en', s);
      expect(out, s).not.toBe(s);
      expect(/[\u4e00-\u9fff]/.test(out), `${s} -> ${out}`).toBe(false);
    }
  });
});

describe('参考叠看 toggle (M3)', () => {
  it('disabled without a current image is not announced as pressed', () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(new Response('[]', {status: 200, headers: {'Content-Type': 'application/json'}}))));
    render(<ImageRebuild novelId="n1" view="browse" onViewChange={() => {}} shellMode="basic" />);
    const b = document.getElementById('imgToggleRef')!;
    expect(b).not.toBeNull();
    expect((b as HTMLButtonElement).disabled).toBe(true);
    expect(b.getAttribute('aria-pressed')).toBe('false');
    expect(b.textContent).toContain('关');
  });
});

describe('onboarding close focus fallback', () => {
  it('without module switcher or settings, focus lands on a real target, not BODY', () => {
    vi.useFakeTimers(); localStorage.clear(); __resetOnboarding();
    const host = document.createElement('div'); document.body.append(host);
    const main = document.createElement('main'); main.textContent = 'work'; document.body.append(main);
    const root: Root = createRoot(host);
    function H() { const c = useOnboarding({shellMode: 'basic', auto: true}); return <OnboardingTour c={c} />; }
    act(() => root.render(<H />)); act(() => { vi.advanceTimersByTime(500); });
    act(() => (document.querySelector('[data-onboarding-skip]') as HTMLButtonElement).click());
    act(() => { vi.advanceTimersByTime(10); });
    expect(document.activeElement).not.toBe(document.body);
    expect(document.activeElement).toBe(main);
    act(() => root.unmount()); host.remove(); main.remove();
  });
});
